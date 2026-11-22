"""P5 库内作业：移库、盘点、留样台账、批次临期冻结。

库存数量的写入只走 ``post_stock`` / ``transfer_status``，本文件不碰库存表。
"""
import asyncio
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional

from loguru import logger
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.plugins.builtin.wms_inventory.models import (
    LOT_ACTIVE,
    LOT_FROZEN,
    STOCK_AVAILABLE,
    STOCK_FROZEN,
)
from src.plugins.builtin.wms_inventory.service import (
    StockError,
    post_stock,
    transfer_status,
)
from src.plugins.builtin.wms_internal_ops import models as m
from src.plugins.builtin.wms_master_data.service import next_code


class OpsError(StockError):
    """库内作业被拒绝。"""


# ── 移库 ──────────────────────────────────────────────


async def create_transfer(
    db: AsyncSession,
    *,
    owner_id: int,
    sku_id: int,
    lot_id: int,
    from_location_id: int,
    to_location_id: int,
    qty: Decimal,
    reason: Optional[str],
) -> m.WmsTransfer:
    if qty <= 0:
        raise OpsError("移库数量必须大于 0")
    if from_location_id == to_location_id:
        raise OpsError("源库位与目标库位不能相同")

    sku_owner = (
        await db.execute(
            text("SELECT owner_id FROM wms_master_data_sku WHERE id = :id"),
            {"id": sku_id},
        )
    ).scalar()
    if sku_owner is None:
        raise OpsError("商品未建档")
    if int(sku_owner) != owner_id:
        raise OpsError("商品不属于该货主")

    available = (
        await db.execute(
            text(
                "SELECT COALESCE(SUM(qty), 0) FROM wms_inventory_stock "
                "WHERE owner_id = :owner AND sku_id = :sku AND lot_id = :lot "
                "AND location_id = :loc AND stock_status = :status"
            ),
            {"owner": owner_id, "sku": sku_id, "lot": lot_id,
             "loc": from_location_id, "status": STOCK_AVAILABLE},
        )
    ).scalar() or 0
    if Decimal(str(available)) < qty:
        raise OpsError(
            f"源库位可发库存不足：当前 {available}，需要 {qty}；冻结与破损的货不能移"
        )

    row = m.WmsTransfer(
        code=await next_code(db, "MOV", "", 6),
        owner_id=owner_id,
        sku_id=sku_id,
        lot_id=lot_id,
        from_location_id=from_location_id,
        to_location_id=to_location_id,
        qty=qty,
        reason=reason,
    )
    db.add(row)
    await db.flush()
    return row


async def execute_transfer(
    db: AsyncSession, *, transfer_id: int, operator_id: Optional[int]
) -> m.WmsTransfer:
    row = (
        await db.execute(
            select(m.WmsTransfer)
            .where(m.WmsTransfer.id == transfer_id)
            .with_for_update()
        )
    ).scalars().first()
    if row is None:
        raise OpsError("移库单不存在")
    if row.status == m.TRANSFER_DONE:
        return row
    if row.status != m.TRANSFER_PENDING:
        raise OpsError(f"移库单状态 {row.status} 不能执行")

    qty = Decimal(str(row.qty))
    await post_stock(
        db, sku_id=row.sku_id, lot_id=row.lot_id,
        location_id=row.from_location_id, stock_status=STOCK_AVAILABLE,
        delta=-qty, ref_type="transfer", ref_id=row.id,
        action="transfer_out", operator_id=operator_id,
    )
    await post_stock(
        db, sku_id=row.sku_id, lot_id=row.lot_id,
        location_id=row.to_location_id, stock_status=STOCK_AVAILABLE,
        delta=qty, ref_type="transfer", ref_id=row.id,
        action="transfer_in", operator_id=operator_id,
    )
    row.status = m.TRANSFER_DONE
    row.done_at = datetime.now()
    row.operator_id = operator_id
    await db.flush()
    return row


# ── 盘点 ──────────────────────────────────────────────


async def create_count(
    db: AsyncSession, *, owner_id: int, sku_id: Optional[int], note: Optional[str]
) -> m.WmsCount:
    """按商品+批次+库位生成盘点行，同时冻结账面快照。"""
    cond = "owner_id = :owner AND stock_status = :status AND qty > 0"
    params: dict = {"owner": owner_id, "status": STOCK_AVAILABLE}
    if sku_id is not None:
        cond += " AND sku_id = :sku"
        params["sku"] = sku_id

    rows = (
        await db.execute(
            text(
                f"SELECT sku_id, lot_id, location_id, SUM(qty) AS qty "
                f"FROM wms_inventory_stock WHERE {cond} "
                f"GROUP BY sku_id, lot_id, location_id ORDER BY sku_id, lot_id, location_id"
            ),
            params,
        )
    ).all()
    if not rows:
        raise OpsError("没有可盘点的库存")

    head = m.WmsCount(
        code=await next_code(db, "CNT", "", 6),
        owner_id=owner_id, status=m.COUNT_PENDING, note=note,
    )
    db.add(head)
    await db.flush()

    for r in rows:
        db.add(
            m.WmsCountLine(
                count_id=head.id,
                sku_id=r.sku_id,
                lot_id=r.lot_id,
                location_id=r.location_id,
                qty_book=Decimal(str(r.qty)),
            )
        )
    await db.flush()
    return head


async def save_count_lines(
    db: AsyncSession, *, count_id: int, lines: list[dict]
) -> None:
    head = (
        await db.execute(select(m.WmsCount).where(m.WmsCount.id == count_id))
    ).scalars().first()
    if head is None:
        raise OpsError("盘点单不存在")
    if head.status != m.COUNT_PENDING:
        raise OpsError("盘点单已确认，不能改实盘数")

    rows = (
        await db.execute(
            select(m.WmsCountLine).where(m.WmsCountLine.count_id == count_id)
        )
    ).scalars().all()
    by_id = {r.id: r for r in rows}
    for ln in lines:
        row = by_id.get(ln["line_id"])
        if row is None or row.adjusted:
            continue
        actual = Decimal(str(ln["qty_actual"]))
        if actual < 0:
            raise OpsError("实盘数不能为负")
        row.qty_actual = actual
        row.qty_diff = actual - Decimal(str(row.qty_book))
    await db.flush()


async def confirm_count(
    db: AsyncSession, *, count_id: int, operator_id: Optional[int]
) -> m.WmsCount:
    """按差异过账，不把实盘数直接写回库存。"""
    head = (
        await db.execute(
            select(m.WmsCount).where(m.WmsCount.id == count_id).with_for_update()
        )
    ).scalars().first()
    if head is None:
        raise OpsError("盘点单不存在")
    if head.status == m.COUNT_DONE:
        return head

    lines = (
        await db.execute(
            select(m.WmsCountLine).where(m.WmsCountLine.count_id == count_id)
        )
    ).scalars().all()
    missing = [x for x in lines if x.qty_actual is None]
    if missing:
        raise OpsError(f"还有 {len(missing)} 行没录实盘数")

    for ln in lines:
        if ln.adjusted:
            continue
        diff = Decimal(str(ln.qty_diff))
        if diff != 0:
            await post_stock(
                db, sku_id=ln.sku_id, lot_id=ln.lot_id,
                location_id=ln.location_id, stock_status=STOCK_AVAILABLE,
                delta=diff, ref_type="count_line", ref_id=ln.id,
                action="count_adjust", operator_id=operator_id,
            )
        ln.adjusted = True

    head.status = m.COUNT_DONE
    head.done_at = datetime.now()
    head.operator_id = operator_id
    await db.flush()
    return head


# ── 留样台账 ──────────────────────────────────────────


async def backfill_samples(db: AsyncSession) -> int:
    """把 P2 已完成的历史留样上架行回填成台账。唯一键挡重复。"""
    rows = (
        await db.execute(
            text(
                """
                SELECT pl.id, pl.sku_id, pl.lot_id, pl.to_location_id,
                       pl.qty, pl.done_at, p.owner_id, p.receipt_id
                FROM wms_inbound_putaway_line pl
                JOIN wms_inbound_putaway p ON p.id = pl.putaway_id
                WHERE pl.sample_flag = 1 AND pl.done_at IS NOT NULL
                  AND pl.to_location_id IS NOT NULL
                """
            )
        )
    ).all()
    created = 0
    for r in rows:
        exists = (
            await db.execute(
                select(m.WmsSample.id).where(
                    m.WmsSample.putaway_line_id == r.id
                )
            )
        ).scalars().first()
        if exists is not None:
            continue

        # 留样要求随预报提交，按该 ASN 最近一张服务订单取保留天数
        so = (
            await db.execute(
                text(
                    """
                    SELECT so.retain_days, so.on_expiry
                    FROM wms_inbound_service_order so
                    JOIN wms_inbound_receipt r ON r.asn_id = so.asn_id
                    WHERE r.id = :receipt AND so.status = 'confirmed'
                    ORDER BY so.id DESC LIMIT 1
                    """
                ),
                {"receipt": r.receipt_id},
            )
        ).first()
        retain = int(so.retain_days) if so and so.retain_days else 30
        on_expiry = so.on_expiry if so and so.on_expiry else "scrap"

        sampled_at = r.done_at or datetime.now()
        db.add(
            m.WmsSample(
                putaway_line_id=r.id,
                owner_id=r.owner_id,
                sku_id=r.sku_id,
                lot_id=r.lot_id or 0,
                location_id=r.to_location_id,
                qty=Decimal(str(r.qty)),
                sampled_at=sampled_at,
                expire_at=sampled_at + timedelta(days=retain),
                retain_days=retain,
                on_expiry=on_expiry,
                status=m.SAMPLE_HOLDING,
            )
        )
        created += 1
    await db.flush()
    return created


async def dispose_sample(
    db: AsyncSession,
    *,
    sample_id: int,
    method: str,
    reason: Optional[str],
    operator_id: Optional[int],
) -> m.WmsSample:
    row = (
        await db.execute(
            select(m.WmsSample)
            .where(m.WmsSample.id == sample_id)
            .with_for_update()
        )
    ).scalars().first()
    if row is None:
        raise OpsError("留样记录不存在")
    if row.status == m.SAMPLE_DISPOSED:
        raise OpsError("这条留样已处置，不能重复处理")

    qty = Decimal(str(row.qty))
    if method == "extend":
        if row.expire_at is None:
            raise OpsError("这条留样没有到期日，不能延期")
        row.expire_at = row.expire_at + timedelta(days=row.retain_days)
        row.reason = reason
        await db.flush()
        return row

    if method in ("scrap", "return_owner"):
        await post_stock(
            db, sku_id=row.sku_id, lot_id=row.lot_id,
            location_id=row.location_id, stock_status=STOCK_AVAILABLE,
            delta=-qty, ref_type="sample", ref_id=row.id,
            action=f"sample:{method}", operator_id=operator_id,
        )
        if method == "return_owner":
            row.ref_out_code = await next_code(db, "RTN", "", 6)
    elif method == "restock":
        # 留样本身就是 available，只是放在留样位；转回可发 = 搬回存储区
        target = (
            await db.execute(
                text(
                    "SELECT id FROM wms_master_data_location "
                    "WHERE location_type='storage' AND status=1 ORDER BY id LIMIT 1"
                )
            )
        ).scalar()
        if target is None:
            raise OpsError("没有可用的存储库位，无法转回可发")
        await post_stock(
            db, sku_id=row.sku_id, lot_id=row.lot_id,
            location_id=row.location_id, stock_status=STOCK_AVAILABLE,
            delta=-qty, ref_type="sample", ref_id=row.id,
            action="sample:restock_out", operator_id=operator_id,
        )
        await post_stock(
            db, sku_id=row.sku_id, lot_id=row.lot_id,
            location_id=int(target), stock_status=STOCK_AVAILABLE,
            delta=qty, ref_type="sample", ref_id=row.id,
            action="sample:restock_in", operator_id=operator_id,
        )
    else:
        raise OpsError(f"未知处置方式 {method}")

    row.status = m.SAMPLE_DISPOSED
    row.method = method
    row.reason = reason
    row.disposed_at = datetime.now()
    await db.flush()
    return row


# ── 批次临期自动冻结 ───────────────────────────────────


_freeze_task: Optional[asyncio.Task] = None


async def freeze_expiring_lots(db: AsyncSession) -> int:
    """按商品预警天数扫临期批次，把该批次所有 available 行转成 frozen。

    按批次而非按库存行冻结：同批号不同库位的货要一起停发，否则 FEFO 会绕开
    冻结的那一格继续发同批次的另一格。
    """
    from src.plugins.builtin.wms_inventory.models import WmsLot, WmsStock

    lots = (
        await db.execute(
            select(WmsLot).where(
                WmsLot.status == LOT_ACTIVE,
                WmsLot.expiry_date.is_not(None),
            )
        )
    ).scalars().all()

    frozen = 0
    for lot in lots:
        warn_days = (
            await db.execute(
                text(
                    "SELECT COALESCE(expiry_warn_days, 0) "
                    "FROM wms_master_data_sku WHERE id = :id"
                ),
                {"id": lot.sku_id},
            )
        ).scalar() or 0
        if warn_days <= 0:
            continue
        if lot.expiry_date > datetime.now().date() + timedelta(days=int(warn_days)):
            continue

        stock_rows = (
            await db.execute(
                select(WmsStock).where(
                    WmsStock.lot_id == lot.id,
                    WmsStock.stock_status == STOCK_AVAILABLE,
                    WmsStock.qty > 0,
                )
            )
        ).scalars().all()
        for s in stock_rows:
            await transfer_status(
                db, sku_id=s.sku_id, lot_id=s.lot_id,
                location_id=s.location_id,
                from_status=STOCK_AVAILABLE, to_status=STOCK_FROZEN,
                qty=Decimal(str(s.qty)),
                ref_type="lot_expiry", ref_id=lot.id,
                action="freeze", operator_id=None,
            )
        lot.status = LOT_FROZEN
        lot.frozen_reason = "expiry_warn"
        frozen += 1

    await db.commit()
    if frozen:
        logger.info(f"[lot_expiry] frozen {frozen} lots")
    return frozen


async def _freeze_loop() -> None:
    """启动立即跑一次，之后每小时。进程重启靠"立即跑一次"兜底。"""
    from src.db import SessionLocal

    while True:
        try:
            async with SessionLocal() as db:
                await freeze_expiring_lots(db)
        except Exception as exc:  # noqa: BLE001
            logger.exception(f"[lot_expiry] scan failed: {exc}")
        await asyncio.sleep(3600)


def start_freeze_scheduler() -> None:
    """幂等启动：install 每次进程启动都调，但不重复挂任务。"""
    global _freeze_task
    if _freeze_task is not None and not _freeze_task.done():
        return
    _freeze_task = asyncio.create_task(_freeze_loop())
    logger.info("[lot_expiry] scheduler started (hourly, asyncio)")
