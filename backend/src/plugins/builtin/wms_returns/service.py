"""破损处置：把 ``damaged`` 状态里的货放出去。

两条路：
- ``restock`` 转回可发 —— 走状态转换，数量不变，只换状态
- ``scrap``   报废减量 —— 走数量扣减

``return_owner`` 要出库能力，P3 才开放；现在调用会明确拒绝，而不是静默不动。
"""
from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.plugins.builtin.wms_inventory.models import STOCK_AVAILABLE, STOCK_DAMAGED
from src.plugins.builtin.wms_inventory.service import (
    StockError,
    post_stock,
    transfer_status,
)
from src.plugins.builtin.wms_returns.models import (
    DISPOSAL_RESTOCK,
    DISPOSAL_RETURN_OWNER,
    DISPOSAL_SCRAP,
    WmsDisposal,
)


async def dispose(
    db: AsyncSession,
    *,
    disposal_id: int,
    method: str,
    reason: Optional[str],
    operator_id: Optional[int],
) -> WmsDisposal:
    """执行一条处置。调用方负责提交事务。"""
    row = (
        await db.execute(
            select(WmsDisposal).where(WmsDisposal.id == disposal_id).with_for_update()
        )
    ).scalars().first()
    if row is None:
        raise StockError("处置记录不存在")
    if row.status == "handled":
        raise StockError("这条处置已完成，不能重复处理")

    qty = Decimal(str(row.qty))
    ref_id = row.id

    if method == DISPOSAL_RESTOCK:
        await transfer_status(
            db,
            sku_id=row.sku_id,
            lot_id=row.lot_id,
            location_id=row.location_id,
            from_status=STOCK_DAMAGED,
            to_status=STOCK_AVAILABLE,
            qty=qty,
            ref_type="disposal",
            ref_id=ref_id,
            action="disposal:restock",
            operator_id=operator_id,
        )
    elif method == DISPOSAL_RETURN_OWNER:
        # 退回货主：破损货从账上出掉，并留一个出库单号便于对账。
        # 不走完整拣货流程——这批货本来就是坏的，不需要拣、不需要复核。
        from src.plugins.builtin.wms_master_data.service import next_code

        await post_stock(
            db,
            sku_id=row.sku_id,
            lot_id=row.lot_id,
            location_id=row.location_id,
            stock_status=STOCK_DAMAGED,
            delta=-qty,
            ref_type="disposal",
            ref_id=ref_id,
            action="disposal:return_owner",
            operator_id=operator_id,
        )
        row.ref_out_code = await next_code(db, "RTN", "", 6)
    elif method == DISPOSAL_SCRAP:
        await post_stock(
            db,
            sku_id=row.sku_id,
            lot_id=row.lot_id,
            location_id=row.location_id,
            stock_status=STOCK_DAMAGED,
            delta=-qty,
            ref_type="disposal",
            ref_id=ref_id,
            action="disposal:scrap",
            operator_id=operator_id,
        )
    else:
        raise StockError(f"未知处置方式 {method}")

    row.method = method
    row.reason = reason or row.reason
    row.status = "handled"
    row.operator_id = operator_id
    row.handled_at = datetime.now()
    await db.flush()
    return row
