"""波次异步生成。

不重写分配：逐单复用 P3 的 ``allocate_fefo`` 与 ``release_to_pick``。
波次只是在外面套一层批量编排，所以分配"只记账不动库存"的契约保持不变。

``POST /waves`` 落一条 pending 记录就返回，后台任务自己开数据库会话；
不能用请求里的 session——请求一结束它就被关掉了。
"""
import asyncio
from datetime import datetime
from typing import Optional

from loguru import logger
from sqlalchemy import bindparam, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.db import SessionLocal
from src.plugins.builtin.wms_master_data.service import next_code
from src.plugins.builtin.wms_outbound import models as m

# 保持 task 引用，避免被 GC 提前回收
_RUNNING: set[asyncio.Task] = set()

_YIELD_EVERY = 50


async def _load_candidates(
    db: AsyncSession, rule: Optional[m.WmsWaveRule]
) -> list[m.WmsOrder]:
    """按规则筛 confirmed 且还没进波的订单。"""
    stmt = select(m.WmsOrder).where(
        m.WmsOrder.status == m.ORDER_CONFIRMED,
        m.WmsOrder.wave_id.is_(None),
    )
    if rule is not None:
        if rule.carrier_code:
            stmt = stmt.where(m.WmsOrder.carrier_code == rule.carrier_code)
        if rule.region_prefix:
            stmt = stmt.where(
                m.WmsOrder.receiver_address.like(f"{rule.region_prefix}%")
            )
        if rule.cutoff_at:
            stmt = stmt.where(
                text("TIME(created_at) <= :cutoff").bindparams(cutoff=rule.cutoff_at)
            )
    stmt = stmt.order_by(m.WmsOrder.id)

    limit = rule.max_orders if rule is not None else 200
    stmt = stmt.limit(limit)
    rows = (await db.execute(stmt)).scalars().all()

    if rule is not None and rule.hot_only:
        # 热门单 = 行数不超过阈值。200 单规模下在内存里过滤比写 HAVING 子查询简单。
        filtered = []
        for order in rows:
            cnt = (
                await db.execute(
                    select(m.WmsOrderLine.id).where(
                        m.WmsOrderLine.order_id == order.id
                    )
                )
            ).all()
            if len(cnt) <= rule.hot_line_limit:
                filtered.append(order)
        return filtered
    return list(rows)


async def create_wave(
    db: AsyncSession,
    *,
    rule_id: Optional[int],
    operator_id: Optional[int],
) -> m.WmsWave:
    """落一条 pending 记录并挂起后台任务。调用方负责 commit。"""
    rule = None
    if rule_id is not None:
        rule = (
            await db.execute(
                select(m.WmsWaveRule).where(m.WmsWaveRule.id == rule_id)
            )
        ).scalars().first()
        if rule is None:
            raise ValueError("波次规则不存在")

    orders = await _load_candidates(db, rule)
    wave = m.WmsWave(
        code=await next_code(db, "WAV", "", 6),
        rule_id=rule_id,
        status=m.WAVE_PENDING,
        total=len(orders),
        operator_id=operator_id,
    )
    db.add(wave)
    await db.flush()

    # 把订单先绑定到波次，避免另一个波次同时抢走同一批单
    for order in orders:
        order.wave_id = wave.id
    await db.flush()
    return wave


async def schedule_generation(wave_id: int) -> None:
    """挂后台任务。任务引用存进模块级集合，跑完再移除。"""
    task = asyncio.create_task(generate_wave(wave_id))
    _RUNNING.add(task)
    task.add_done_callback(_RUNNING.discard)


async def generate_wave(wave_id: int) -> None:
    """逐单分配并生成拣货单。每 50 单让出事件循环。"""
    from src.plugins.builtin.wms_outbound.service import allocate_fefo, release_to_pick

    try:
        async with SessionLocal() as db:
            wave = (
                await db.execute(select(m.WmsWave).where(m.WmsWave.id == wave_id))
            ).scalars().first()
            if wave is None or wave.status != m.WAVE_PENDING:
                return
            # commit 会 expire 对象，之后访问 wave.* 会触发惰性加载，
            # 在 async 会话里抛 MissingGreenlet。先把要用的值取出来。
            operator_id = wave.operator_id
            wave.status = m.WAVE_GENERATING
            wave.started_at = datetime.now()
            await db.commit()

            orders = (
                await db.execute(
                    select(m.WmsOrder).where(m.WmsOrder.wave_id == wave_id)
                )
            ).scalars().all()
            # 失败时会 rollback，之后不能再去碰 ORM 对象（同样会 MissingGreenlet）
            plain = [(o.id, o.code) for o in orders]

            processed = 0
            failed = 0
            details: list[str] = []

            for idx, (order_id, order_code) in enumerate(plain, start=1):
                # 中止检查：每单开头查一次状态，避免取消后还在继续生成
                current = (
                    await db.execute(
                        select(m.WmsWave.status).where(m.WmsWave.id == wave_id)
                    )
                ).scalar()
                if current == m.WAVE_CANCELLED:
                    logger.info(f"[wave {wave_id}] 已中止，退出生成")
                    return

                try:
                    await allocate_fefo(db, order_id=order_id, operator_id=operator_id)
                    await release_to_pick(db, order_id=order_id, operator_id=operator_id)
                    await db.commit()
                    processed += 1
                except Exception as exc:  # noqa: BLE001
                    # 单笔失败不放整波失败，记下原因继续下一单
                    await db.rollback()
                    failed += 1
                    details.append(f"{order_code}: {str(exc)[:120]}")
                    logger.warning(f"[wave {wave_id}] {order_code} 分配失败：{exc}")

                if idx % 10 == 0 or idx == len(orders):
                    async with SessionLocal() as prog_db:
                        w = (
                            await prog_db.execute(
                                select(m.WmsWave).where(m.WmsWave.id == wave_id)
                            )
                        ).scalars().first()
                        if w is not None:
                            w.processed = processed
                            w.failed = failed
                            await prog_db.commit()

                # 单进程部署：不让出事件循环会把登录和查询一起卡住
                if idx % _YIELD_EVERY == 0:
                    await asyncio.sleep(0)

            async with SessionLocal() as done_db:
                w = (
                    await done_db.execute(
                        select(m.WmsWave).where(m.WmsWave.id == wave_id)
                    )
                ).scalars().first()
                if w is not None and w.status == m.WAVE_GENERATING:
                    w.status = m.WAVE_READY
                    w.processed = processed
                    w.failed = failed
                    w.fail_detail = "\n".join(details[:50]) or None
                    w.finished_at = datetime.now()
                    await done_db.commit()
            logger.info(
                f"[wave {wave_id}] ready: processed={processed} failed={failed}"
            )
    except Exception as exc:  # noqa: BLE001
        logger.exception(f"[wave {wave_id}] 生成异常：{exc}")
        async with SessionLocal() as fail_db:
            w = (
                await fail_db.execute(select(m.WmsWave).where(m.WmsWave.id == wave_id))
            ).scalars().first()
            if w is not None and w.status == m.WAVE_GENERATING:
                w.status = m.WAVE_INTERRUPTED
                w.finished_at = datetime.now()
                await fail_db.commit()


async def cancel_wave(
    db: AsyncSession, *, wave_id: int, reason: Optional[str], operator_id: Optional[int]
) -> m.WmsWave:
    """中止：不回滚已生成的拣货单，只把它们标记作废。

    回滚要么删记录、要么反向补库存，两条都容易出错。已经发运的订单不动——它本来就该发。
    """
    wave = (
        await db.execute(
            select(m.WmsWave).where(m.WmsWave.id == wave_id).with_for_update()
        )
    ).scalars().first()
    if wave is None:
        raise ValueError("波次不存在")
    if wave.status in (m.WAVE_DONE, m.WAVE_CANCELLED):
        raise ValueError(f"波次状态 {wave.status} 不能中止")

    wave.status = m.WAVE_CANCELLED
    wave.cancel_reason = reason
    wave.finished_at = datetime.now()

    orders = (
        await db.execute(select(m.WmsOrder.id).where(m.WmsOrder.wave_id == wave_id))
    ).scalars().all()
    if orders:
        picks = (
            await db.execute(
                select(m.WmsPick).where(m.WmsPick.order_id.in_(orders))
            )
        ).scalars().all()
        for pick in picks:
            order = (
                await db.execute(
                    select(m.WmsOrder.status).where(m.WmsOrder.id == pick.order_id)
                )
            ).scalar()
            if order != m.ORDER_SHIPPED:
                pick.status = "cancelled"

        # 未发运订单退回待分配状态，allocation 作废，库存数量始终没动过
        await db.execute(
            text(
                "UPDATE wms_outbound_allocation SET status='void' "
                "WHERE order_id IN :ids AND status='active'"
            ).bindparams(bindparam("ids", expanding=True)),
            {"ids": list(orders)},
        )
        for oid in orders:
            o = (
                await db.execute(select(m.WmsOrder).where(m.WmsOrder.id == oid))
            ).scalars().first()
            if o is not None and o.status == m.ORDER_PICKING:
                o.status = m.ORDER_CONFIRMED
                o.wave_id = None

    await db.flush()
    return wave


async def recover_interrupted(db: AsyncSession, timeout_minutes: int = 10) -> int:
    """启动时把卡住的波次标为 interrupted，不自动续跑。

    必须带超时阈值，且只能在进程启动时调一次：波次生成是后台任务，
    如果挂在列表查询里，前端一轮询就会把正在跑的波次误判为中断。
    自动续跑最容易重复分配，由人工重新发起更安全。
    """
    from datetime import timedelta

    cutoff = datetime.now() - timedelta(minutes=timeout_minutes)
    rows = (
        await db.execute(
            select(m.WmsWave).where(
                m.WmsWave.status == m.WAVE_GENERATING,
                m.WmsWave.started_at.is_not(None),
                m.WmsWave.started_at < cutoff,
            )
        )
    ).scalars().all()
    for w in rows:
        w.status = m.WAVE_INTERRUPTED
        w.finished_at = datetime.now()
    if rows:
        await db.commit()
        logger.warning(f"Marked {len(rows)} stale generating waves as interrupted")
    return len(rows)
