"""退货入库：按品质分流，复用 P2 的处置流程。"""
from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import bindparam, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.plugins.builtin.wms_inventory.models import STOCK_AVAILABLE, STOCK_DAMAGED
from src.plugins.builtin.wms_inventory.service import StockError, post_stock
from src.plugins.builtin.wms_master_data.service import next_code
from src.plugins.builtin.wms_returns import models as m


class ReturnError(StockError):
    """退货被拒绝。"""


async def create_return(
    db: AsyncSession,
    *,
    owner_id: int,
    lines: list[dict],
    owner_doc_no: Optional[str] = None,
    customer_name: Optional[str] = None,
    source_order_code: Optional[str] = None,
    remark: Optional[str] = None,
) -> m.WmsReturn:
    """建退货单。启用批次管理的商品必须给 ``lot_id``，否则 FEFO 无从算起。"""
    if not lines:
        raise ReturnError("退货单至少要有一行")

    sku_ids = [ln["sku_id"] for ln in lines]
    rows = (
        await db.execute(
            text(
                "SELECT id, owner_id, lot_required FROM wms_master_data_sku "
                "WHERE id IN :ids"
            ).bindparams(bindparam("ids", expanding=True)),
            {"ids": list(sku_ids)},
        )
    ).all()
    sku_map = {r.id: r for r in rows}
    for ln in lines:
        sku = sku_map.get(ln["sku_id"])
        if sku is None:
            raise ReturnError(f"商品未建档：{ln['sku_id']}")
        if int(sku.owner_id) != owner_id:
            raise ReturnError(f"商品 {ln['sku_id']} 不属于该货主")
        if sku.lot_required and not ln.get("lot_id"):
            raise ReturnError(
                f"商品 {ln['sku_id']} 启用批次管理，退货必须指定批次"
            )
        if Decimal(str(ln["qty"])) <= 0:
            raise ReturnError("退货数量必须大于 0")
        if ln.get("quality") not in (m.QUALITY_GOOD, m.QUALITY_DAMAGED):
            raise ReturnError("品质只能是 good 或 damaged")

    head = m.WmsReturn(
        code=await next_code(db, "RET", "", 6),
        owner_id=owner_id,
        owner_doc_no=owner_doc_no,
        customer_name=customer_name,
        source_order_code=source_order_code,
        status=m.RETURN_CONFIRMED,
        remark=remark,
    )
    db.add(head)
    await db.flush()

    for ln in lines:
        db.add(
            m.WmsReturnLine(
                return_id=head.id,
                sku_id=ln["sku_id"],
                lot_id=ln.get("lot_id") or 0,
                qty=Decimal(str(ln["qty"])),
                quality=ln["quality"],
            )
        )
    await db.flush()
    return head


async def receive_return(
    db: AsyncSession, *, return_id: int, operator_id: Optional[int]
) -> m.WmsReturn:
    """确认退货入库。

    好货进 ``available``，破损进 ``damaged`` 并生成一条待处置记录。
    重复确认靠 ``head.status`` 与 ``line.posted`` 双重挡住。
    """
    head = (
        await db.execute(
            select(m.WmsReturn)
            .where(m.WmsReturn.id == return_id)
            .with_for_update()
        )
    ).scalars().first()
    if head is None:
        raise ReturnError("退货单不存在")
    if head.status == m.RETURN_RECEIVED:
        return head
    if head.status != m.RETURN_CONFIRMED:
        raise ReturnError(f"退货单状态 {head.status} 不能入库")

    loc = (
        await db.execute(
            text(
                "SELECT id FROM wms_master_data_location "
                "WHERE location_type='receiving' AND status=1 ORDER BY id LIMIT 1"
            )
        )
    ).scalar()
    if loc is None:
        raise ReturnError("没有收货暂存库位，请先建一个 location_type=receiving 的库位")
    loc = int(loc)

    lines = (
        await db.execute(
            select(m.WmsReturnLine).where(m.WmsReturnLine.return_id == return_id)
        )
    ).scalars().all()

    for ln in lines:
        if ln.posted:
            continue
        qty = Decimal(str(ln.qty))
        if ln.quality == m.QUALITY_GOOD:
            await post_stock(
                db, sku_id=ln.sku_id, lot_id=ln.lot_id,
                location_id=loc, stock_status=STOCK_AVAILABLE,
                delta=qty, ref_type="return_line", ref_id=ln.id,
                action="return:good", operator_id=operator_id,
            )
        else:
            await post_stock(
                db, sku_id=ln.sku_id, lot_id=ln.lot_id,
                location_id=loc, stock_status=STOCK_DAMAGED,
                delta=qty, ref_type="return_line", ref_id=ln.id,
                action="return:damaged", operator_id=operator_id,
            )
            db.add(
                m.WmsDisposal(
                    owner_id=head.owner_id,
                    sku_id=ln.sku_id,
                    lot_id=ln.lot_id,
                    location_id=loc,
                    qty=qty,
                    status="pending",
                    source_ref_type="return_line",
                    source_ref_id=ln.id,
                )
            )
        ln.posted = True

    head.status = m.RETURN_RECEIVED
    head.received_at = datetime.now()
    head.operator_id = operator_id
    await db.flush()
    return head
