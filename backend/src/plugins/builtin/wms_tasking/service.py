"""任务领取与提交。

提交时对能直接推进的业务（移库）调对应域的既有服务；其余只记录作业结果，
由业务页面确认。这样任务域停用不会留下"任务完成了但单据没动"的假象。
"""
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.plugins.builtin.wms_inventory.service import StockError
from src.plugins.builtin.wms_master_data.service import next_code
from src.plugins.builtin.wms_tasking import models as m


class TaskError(StockError):
    """任务被拒绝。"""


async def create_task(
    db: AsyncSession,
    *,
    task_type: str,
    ref_type: str,
    ref_id: int,
    title: str,
    target_location_id: Optional[int] = None,
    timeout_minutes: int = 60,
    note: Optional[str] = None,
) -> m.WmsTask:
    # 同一来源单据同一类型只生成一条未完成任务
    exists = (
        await db.execute(
            select(m.WmsTask).where(
                m.WmsTask.task_type == task_type,
                m.WmsTask.ref_type == ref_type,
                m.WmsTask.ref_id == ref_id,
                m.WmsTask.status.in_([m.TASK_PENDING, m.TASK_CLAIMED]),
            )
        )
    ).scalars().first()
    if exists is not None:
        return exists

    row = m.WmsTask(
        code=await next_code(db, "TSK", "", 6),
        task_type=task_type, title=title, ref_type=ref_type, ref_id=ref_id,
        target_location_id=target_location_id, timeout_minutes=timeout_minutes,
        note=note,
    )
    db.add(row)
    await db.flush()
    return row


async def claim_task(
    db: AsyncSession, *, task_id: int, user_id: int
) -> m.WmsTask:
    row = (
        await db.execute(
            select(m.WmsTask).where(m.WmsTask.id == task_id).with_for_update()
        )
    ).scalars().first()
    if row is None:
        raise TaskError("任务不存在")
    if row.status == m.TASK_CLAIMED and row.claimed_by == user_id:
        return row
    if row.status != m.TASK_PENDING:
        raise TaskError(f"任务状态 {row.status} 不能领取")

    row.status = m.TASK_CLAIMED
    row.claimed_by = user_id
    row.claimed_at = datetime.now()
    await db.flush()
    return row


async def submit_task(
    db: AsyncSession, *, task_id: int, user_id: int, note: Optional[str]
) -> m.WmsTask:
    row = (
        await db.execute(
            select(m.WmsTask).where(m.WmsTask.id == task_id).with_for_update()
        )
    ).scalars().first()
    if row is None:
        raise TaskError("任务不存在")
    if row.status == m.TASK_DONE:
        return row
    if row.status != m.TASK_CLAIMED:
        raise TaskError("任务未领取，不能提交")
    if row.claimed_by != user_id:
        raise TaskError("任务由其他作业员领取，不能提交")

    # 移库单可以直接推进业务；其余由对应页面确认，避免跨域改坏状态机
    if row.task_type == "transfer" and row.ref_type == "transfer":
        from src.plugins.builtin.wms_internal_ops.ops_service import execute_transfer
        await execute_transfer(db, transfer_id=row.ref_id, operator_id=user_id)

    row.status = m.TASK_DONE
    row.submitted_at = datetime.now()
    if note:
        row.note = note
    await db.flush()
    return row


async def recycle_timeout(db: AsyncSession) -> int:
    """领取超时的任务回归待领，不做自动改派。"""
    rows = (
        await db.execute(select(m.WmsTask).where(m.WmsTask.status == m.TASK_CLAIMED))
    ).scalars().all()
    n = 0
    for row in rows:
        if row.claimed_at is None:
            continue
        if datetime.now() - row.claimed_at < timedelta(minutes=row.timeout_minutes):
            continue
        row.status = m.TASK_PENDING
        row.claimed_by = None
        row.claimed_at = None
        n += 1
    if n:
        await db.flush()
    return n


async def generate_from_sources(db: AsyncSession) -> int:
    """从待办业务生成任务：待执行移库单、待处理盘点单、待拣货单、待上架行。"""
    created = 0
    sources = [
        (
            "transfer", "transfer",
            "SELECT id, from_location_id, CONCAT('移库 ', code) FROM wms_internal_ops_transfer "
            "WHERE status='pending'",
        ),
        (
            "count", "count",
            "SELECT id, NULL, CONCAT('盘点 ', code) FROM wms_internal_ops_count "
            "WHERE status='pending'",
        ),
        (
            "pick", "pick",
            "SELECT id, NULL, CONCAT('拣货 ', code) FROM wms_outbound_pick "
            "WHERE status='pending'",
        ),
        (
            "putaway", "putaway_line",
            "SELECT id, to_location_id, CONCAT('上架行 #', id) "
            "FROM wms_inbound_putaway_line WHERE done_at IS NULL",
        ),
    ]
    for task_type, ref_type, sql in sources:
        rows = (await db.execute(text(sql))).all()
        for r in rows:
            before = (
                await db.execute(
                    select(m.WmsTask.id).where(
                        m.WmsTask.task_type == task_type,
                        m.WmsTask.ref_type == ref_type,
                        m.WmsTask.ref_id == r[0],
                        m.WmsTask.status.in_([m.TASK_PENDING, m.TASK_CLAIMED, m.TASK_DONE]),
                    )
                )
            ).scalars().first()
            if before is not None:
                continue
            await create_task(
                db, task_type=task_type, ref_type=ref_type, ref_id=r[0],
                title=str(r[2]), target_location_id=r[1],
            )
            created += 1
    await db.flush()
    return created
