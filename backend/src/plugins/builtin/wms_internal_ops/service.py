"""补货：先出建议（只读），人工确认后才动库存。"""
from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.plugins.builtin.wms_inventory.models import STOCK_AVAILABLE
from src.plugins.builtin.wms_inventory.service import StockError, post_stock
from src.plugins.builtin.wms_internal_ops import models as m


class ReplenishError(StockError):
    """补货被拒绝。"""


async def build_suggestions(db: AsyncSession, *, owner_id: Optional[int] = None) -> list[m.WmsReplenish]:
    """按拣选区下限生成补货建议。

    只处理「已有库存但低于下限」的拣选位。完全没有库存行的空库位属于首次铺货，
    系统不知道该铺哪个商品，留到 P5 的铺货功能，不在这里瞎猜。

    建议量按 ``qty_per_box`` **向下**取整到整箱：向上取整会超过 ``replenish_max``，
    而拆箱补会让拣选位出现散箱，作业员没法整箱搬。
    """
    rows = (
        await db.execute(
            text(
                """
                SELECT s.owner_id, s.sku_id, s.lot_id, s.location_id,
                       SUM(s.qty) AS qty, loc.replenish_min, loc.replenish_max
                FROM wms_inventory_stock s
                JOIN wms_master_data_location loc ON loc.id = s.location_id
                WHERE s.stock_status = :status
                  AND s.qty > 0
                  AND loc.location_type = 'picking'
                  AND loc.status = 1
                  AND loc.replenish_min IS NOT NULL
                GROUP BY s.owner_id, s.sku_id, s.lot_id, s.location_id,
                         loc.replenish_min, loc.replenish_max
                HAVING SUM(s.qty) < loc.replenish_min
                """
            ),
            {"status": STOCK_AVAILABLE},
        )
    ).all()

    created: list[m.WmsReplenish] = []
    for r in rows:
        if owner_id is not None and r.owner_id != owner_id:
            continue
        current = Decimal(str(r.qty))
        min_qty = Decimal(str(r.replenish_min or 0))
        max_qty = Decimal(str(r.replenish_max or min_qty))
        if current >= min_qty or max_qty <= current:
            continue

        sku = (
            await db.execute(
                text("SELECT qty_per_box FROM wms_master_data_sku WHERE id = :id"),
                {"id": r.sku_id},
            )
        ).scalar()
        box = Decimal(str(sku or 1))
        if box <= 0:
            box = Decimal("1")

        # 整箱数向下取整，保证不超 replenish_max
        boxes = int((max_qty - current) // box)
        qty = Decimal(boxes) * box
        if qty <= 0:
            continue

        # 来源：同货主同商品在存储区有足够可用量的库位
        source = (
            await db.execute(
                text(
                    """
                    SELECT s.location_id, SUM(s.qty) AS qty
                    FROM wms_inventory_stock s
                    JOIN wms_master_data_location loc ON loc.id = s.location_id
                    WHERE s.owner_id = :owner AND s.sku_id = :sku
                      AND s.lot_id = :lot
                      AND s.stock_status = :status AND s.qty > 0
                      AND loc.location_type = 'storage' AND loc.status = 1
                    GROUP BY s.location_id
                    HAVING SUM(s.qty) >= :need
                    ORDER BY s.location_id
                    LIMIT 1
                    """
                ),
                {"owner": r.owner_id, "sku": r.sku_id, "lot": r.lot_id,
                 "status": STOCK_AVAILABLE, "need": str(qty)},
            )
        ).first()
        if source is None:
            # 没有足够整箱货可补，不生成做不到的建议
            continue

        # 同一拣选位同一商品已有待处理建议时不重复建
        existing = (
            await db.execute(
                select(m.WmsReplenish).where(
                    m.WmsReplenish.owner_id == r.owner_id,
                    m.WmsReplenish.sku_id == r.sku_id,
                    m.WmsReplenish.lot_id == r.lot_id,
                    m.WmsReplenish.to_location_id == r.location_id,
                    m.WmsReplenish.status == m.REPLENISH_SUGGESTED,
                )
            )
        ).scalars().first()
        if existing is not None:
            continue

        row = m.WmsReplenish(
            owner_id=r.owner_id,
            sku_id=r.sku_id,
            lot_id=r.lot_id,
            from_location_id=int(source.location_id),
            to_location_id=r.location_id,
            qty=qty,
            current_qty=current,
            min_qty=min_qty,
            status=m.REPLENISH_SUGGESTED,
        )
        db.add(row)
        created.append(row)

    await db.flush()
    return created


async def execute_replenish(
    db: AsyncSession, *, replenish_id: int, operator_id: Optional[int]
) -> m.WmsReplenish:
    """执行一条建议：扣存储区、加拣选区，两条流水同事务。

    幂等靠记录状态：已 done 直接返回，不再过账。
    """
    row = (
        await db.execute(
            select(m.WmsReplenish)
            .where(m.WmsReplenish.id == replenish_id)
            .with_for_update()
        )
    ).scalars().first()
    if row is None:
        raise ReplenishError("补货建议不存在")
    if row.status == m.REPLENISH_DONE:
        return row
    if row.status != m.REPLENISH_SUGGESTED:
        raise ReplenishError(f"建议状态 {row.status} 不能执行")

    qty = Decimal(str(row.qty))
    # 执行时重新校验来源库存：建议是只读快照，期间可能被别的作业用掉
    available = (
        await db.execute(
            text(
                "SELECT COALESCE(SUM(qty), 0) FROM wms_inventory_stock "
                "WHERE owner_id = :owner AND sku_id = :sku AND lot_id = :lot "
                "AND location_id = :loc AND stock_status = :status"
            ),
            {"owner": row.owner_id, "sku": row.sku_id, "lot": row.lot_id,
             "loc": row.from_location_id, "status": STOCK_AVAILABLE},
        )
    ).scalar() or 0
    if Decimal(str(available)) < qty:
        raise ReplenishError(
            f"来源库位可用量不足：当前 {available}，需要 {qty}，不做部分补货"
        )

    await post_stock(
        db,
        sku_id=row.sku_id,
        lot_id=row.lot_id,
        location_id=row.from_location_id,
        stock_status=STOCK_AVAILABLE,
        delta=-qty,
        ref_type="replenish",
        ref_id=row.id,
        action="replenish_out",
        operator_id=operator_id,
    )
    await post_stock(
        db,
        sku_id=row.sku_id,
        lot_id=row.lot_id,
        location_id=row.to_location_id,
        stock_status=STOCK_AVAILABLE,
        delta=qty,
        ref_type="replenish",
        ref_id=row.id,
        action="replenish_in",
        operator_id=operator_id,
    )

    row.status = m.REPLENISH_DONE
    row.done_at = datetime.now()
    row.operator_id = operator_id
    await db.flush()
    return row
