"""出库：分配、拣货、复核、发运。

分配只写 ``allocation``，不动库存数量；库存在发运时才扣。这条决定了任何一步
失败都能退回，账不会被污染。
"""
from datetime import datetime
from decimal import Decimal
from typing import Optional, Sequence

from sqlalchemy import bindparam, select, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.plugins.builtin.wms_inventory.models import STOCK_AVAILABLE
from src.plugins.builtin.wms_inventory.service import StockError, post_stock
from src.plugins.builtin.wms_master_data.service import next_code
from src.plugins.builtin.wms_outbound import models as m

DEFAULT_WEIGHT_TOLERANCE = Decimal("0.05")


class OutboundError(StockError):
    """出库被拒绝。"""


async def _sku_info(db: AsyncSession, sku_ids: Sequence[int]) -> dict[int, dict]:
    from sqlalchemy import bindparam

    if not sku_ids:
        return {}
    stmt = text(
        "SELECT id, owner_id, weight FROM wms_master_data_sku WHERE id IN :ids"
    ).bindparams(bindparam("ids", expanding=True))
    rows = (await db.execute(stmt, {"ids": list(sku_ids)})).all()
    return {
        r.id: {
            "owner_id": r.owner_id,
            "weight": Decimal(str(r.weight)) if r.weight is not None else None,
        }
        for r in rows
    }


async def create_order(
    db: AsyncSession,
    *,
    owner_id: int,
    owner_doc_no: str,
    lines: list[dict],
    order_type: str = "C",
    source: str = "manual",
    customer_name: Optional[str] = None,
    receiver: Optional[str] = None,
    receiver_phone: Optional[str] = None,
    receiver_address: Optional[str] = None,
    carrier_code: Optional[str] = None,
    created_by: Optional[int] = None,
) -> m.WmsOrder:
    """建单。三个入口（后台/门户/开放接口）共用这一处校验。"""
    sku_ids = [ln["sku_id"] for ln in lines]
    if len(set(sku_ids)) != len(sku_ids):
        raise OutboundError("同一订单里同一商品只能出现一次")

    skus = await _sku_info(db, sku_ids)
    missing = [s for s in sku_ids if s not in skus]
    if missing:
        raise OutboundError(f"商品未建档：{missing}")
    wrong = [s for s in sku_ids if skus[s]["owner_id"] != owner_id]
    if wrong:
        raise OutboundError(f"商品不属于该货主：{wrong}")

    order = m.WmsOrder(
        code=await next_code(db, "SO", "", 6),
        owner_id=owner_id,
        owner_doc_no=owner_doc_no,
        order_type=order_type,
        source=source,
        customer_name=customer_name,
        receiver=receiver,
        receiver_phone=receiver_phone,
        receiver_address=receiver_address,
        carrier_code=carrier_code,
        status=m.ORDER_CONFIRMED,
        created_by=created_by,
    )
    db.add(order)
    try:
        await db.flush()
    except IntegrityError as exc:
        await db.rollback()
        raise OutboundError(f"货主单号 {owner_doc_no} 已存在，请勿重复推送") from exc

    for ln in lines:
        db.add(
            m.WmsOrderLine(
                order_id=order.id,
                sku_id=ln["sku_id"],
                qty=Decimal(str(ln["qty"])),
                lot_id=ln.get("lot_id"),
            )
        )
    await db.flush()
    return order


async def allocate_fefo(
    db: AsyncSession, *, order_id: int, operator_id: Optional[int] = None
) -> list[m.WmsAllocation]:
    """按先到期先出分配。只读库存，写 allocation。

    候选库存在一条 SQL 里取回（含批次到期日），内存里按到期日排序后逐行扣减。
    留样区在 SQL 里就被排除——散在应用层的判断迟早漏一处，而漏一处就是把
    留样货发给客户。
    """
    order = (
        await db.execute(
            select(m.WmsOrder).where(m.WmsOrder.id == order_id).with_for_update()
        )
    ).scalars().first()
    if order is None:
        raise OutboundError("订单不存在")
    if order.status != m.ORDER_CONFIRMED:
        raise OutboundError(f"订单状态 {order.status} 不能分配")

    lines = (
        await db.execute(
            select(m.WmsOrderLine).where(m.WmsOrderLine.order_id == order_id)
        )
    ).scalars().all()
    if not lines:
        raise OutboundError("订单没有明细")

    skus = [ln.sku_id for ln in lines]
    stmt = text(
        """
        SELECT s.id AS stock_id, s.sku_id, s.lot_id, s.location_id, s.qty,
               l.expiry_date
        FROM wms_inventory_stock s
        LEFT JOIN wms_inventory_lot l ON l.id = s.lot_id
        JOIN wms_master_data_location loc ON loc.id = s.location_id
        WHERE s.owner_id = :owner_id
          AND s.sku_id IN :skus
          AND s.stock_status = :status
          AND s.qty > 0
          AND loc.status = 1
          AND loc.location_type IN ('storage', 'picking')
        ORDER BY (l.expiry_date IS NULL), l.expiry_date, s.lot_id, s.location_id
        FOR UPDATE
        """
    ).bindparams(bindparam("skus", expanding=True))

    rows = (await db.execute(stmt, {
        "owner_id": order.owner_id,
        "skus": skus,
        "status": STOCK_AVAILABLE,
    })).all()

    # Row 不可变，转成可变结构再逐行扣减；否则同一批次会被两行重复分配
    by_sku: dict[int, list[dict]] = {}
    for r in rows:
        by_sku.setdefault(r.sku_id, []).append(
            {
                "lot_id": r.lot_id,
                "location_id": r.location_id,
                "avail": Decimal(str(r.qty)),
            }
        )

    created: list[m.WmsAllocation] = []
    for ln in lines:
        need = Decimal(str(ln.qty)) - Decimal(str(ln.allocated_qty))
        if need <= 0:
            continue

        candidates = by_sku.get(ln.sku_id, [])
        if ln.lot_id:
            candidates = [c for c in candidates if c["lot_id"] == ln.lot_id]

        taken = Decimal("0")
        for c in candidates:
            if taken >= need:
                break
            available = c["avail"]
            if available <= 0:
                continue
            qty = min(available, need - taken)
            c["avail"] = available - qty
            row = m.WmsAllocation(
                order_id=order_id,
                order_line_id=ln.id,
                owner_id=order.owner_id,
                sku_id=ln.sku_id,
                lot_id=c["lot_id"],
                location_id=c["location_id"],
                qty=qty,
            )
            db.add(row)
            created.append(row)
            taken += qty

        if taken < need:
            shortage = need - taken
            if ln.lot_id:
                raise OutboundError(
                    f"商品 {ln.sku_id} 指定批次 {ln.lot_id} 只剩 {taken}，"
                    f"缺口 {shortage}；不自动换批，请改单"
                )
            raise OutboundError(
                f"商品 {ln.sku_id} 可用库存不足：需要 {need}，可分配 {taken}"
            )

        ln.allocated_qty = Decimal(str(ln.allocated_qty)) + taken

    order.status = m.ORDER_ALLOCATED
    await db.flush()
    return created


async def release_to_pick(
    db: AsyncSession, *, order_id: int, operator_id: Optional[int] = None
) -> m.WmsPick:
    """按分配结果生成拣货单，行按库位路径排序。"""
    order = (
        await db.execute(select(m.WmsOrder).where(m.WmsOrder.id == order_id))
    ).scalars().first()
    if order is None:
        raise OutboundError("订单不存在")
    if order.status != m.ORDER_ALLOCATED:
        raise OutboundError(f"订单状态 {order.status} 不能生成拣货单")

    allocs = (
        await db.execute(
            select(m.WmsAllocation).where(
                m.WmsAllocation.order_id == order_id,
                m.WmsAllocation.status == "active",
            )
        )
    ).scalars().all()
    if not allocs:
        raise OutboundError("没有有效的分配记录")

    # 库位路径顺序：巷 → 架 → 层 → 位，作业员走一趟不用折返
    loc_ids = [a.location_id for a in allocs]
    loc_rows = (
        await db.execute(
            text(
                "SELECT id, aisle, rack, level, bin FROM wms_master_data_location "
                "WHERE id IN :ids"
            ).bindparams(bindparam("ids", expanding=True)),
            {"ids": loc_ids},
        )
    ).all()
    loc_key = {
        r.id: tuple((x or "") for x in (r.aisle, r.rack, r.level, r.bin))
        for r in loc_rows
    }

    pick = m.WmsPick(
        code=await next_code(db, "PK", "", 6),
        order_id=order_id,
        owner_id=order.owner_id,
        status=m.PICK_PENDING,
        operator_id=operator_id,
    )
    db.add(pick)
    await db.flush()

    ordered = sorted(allocs, key=lambda a: (loc_key.get(a.location_id, ("",) * 4), a.id))
    for seq, a in enumerate(ordered, start=1):
        db.add(
            m.WmsPickLine(
                pick_id=pick.id,
                allocation_id=a.id,
                sku_id=a.sku_id,
                lot_id=a.lot_id,
                location_id=a.location_id,
                qty=a.qty,
                seq=seq,
            )
        )

    order.status = m.ORDER_PICKING
    await db.flush()
    return pick


async def confirm_pick_line(
    db: AsyncSession, *, line_id: int, location_code: Optional[str], operator_id: Optional[int]
) -> m.WmsPickLine:
    """扫库位确认一行。扫错库位直接拒，不"记下来事后查"。"""
    line = (
        await db.execute(
            select(m.WmsPickLine).where(m.WmsPickLine.id == line_id).with_for_update()
        )
    ).scalars().first()
    if line is None:
        raise OutboundError("拣货行不存在")
    if line.picked_at is not None:
        raise OutboundError("这行已经拣过，不能重复确认")

    if location_code:
        expected = (
            await db.execute(
                text("SELECT code FROM wms_master_data_location WHERE id = :id"),
                {"id": line.location_id},
            )
        ).scalar()
        if expected and location_code.strip() != expected:
            raise OutboundError(
                f"库位不对：应扫 {expected}，扫到的是 {location_code.strip()}"
            )

    line.picked_at = datetime.now()
    await db.flush()
    return line


async def save_check(
    db: AsyncSession,
    *,
    order_id: int,
    weight_actual: Decimal,
    tolerance: Decimal = DEFAULT_WEIGHT_TOLERANCE,
    operator_id: Optional[int] = None,
) -> m.WmsCheck:
    """记录实称并算偏差。缺重量的商品跳过，不阻断发货。"""
    order = (
        await db.execute(select(m.WmsOrder).where(m.WmsOrder.id == order_id))
    ).scalars().first()
    if order is None:
        raise OutboundError("订单不存在")
    if order.status not in (m.ORDER_PICKING, m.ORDER_ALLOCATED, m.ORDER_CHECKED):
        raise OutboundError(f"订单状态 {order.status} 不能复核")

    lines = (
        await db.execute(
            select(m.WmsOrderLine).where(m.WmsOrderLine.order_id == order_id)
        )
    ).scalars().all()
    skus = await _sku_info(db, [ln.sku_id for ln in lines])

    theory = Decimal("0")
    incomplete = False
    for ln in lines:
        w = skus.get(ln.sku_id, {}).get("weight")
        if w is None:
            incomplete = True
            continue
        theory += Decimal(str(ln.qty)) * w

    reason = "部分商品未维护重量，本单按剩余商品计算理论重量" if incomplete else None
    deviation = None
    passed = True
    if theory > 0:
        deviation = abs(Decimal(str(weight_actual)) - theory) / theory
        passed = deviation <= tolerance
    else:
        # 全部缺重量：没有基准可比，放行但记录原因
        reason = "订单商品均未维护重量，跳过称重比对"

    row = (
        await db.execute(select(m.WmsCheck).where(m.WmsCheck.order_id == order_id))
    ).scalars().first()
    if row is None:
        row = m.WmsCheck(order_id=order_id, owner_id=order.owner_id)
        db.add(row)

    row.weight_actual = Decimal(str(weight_actual))
    row.weight_theory = theory
    row.deviation = deviation
    row.passed = passed
    row.reason = reason
    row.operator_id = operator_id

    order.weight_theory = theory
    order.weight_actual = Decimal(str(weight_actual))
    order.status = m.ORDER_CHECKED
    await db.flush()
    return row


async def ship(
    db: AsyncSession, *, order_id: int, tracking_no: Optional[str], operator_id: Optional[int]
) -> m.WmsShipment:
    """发运：按分配逐批次扣减库存。

    幂等靠订单状态——已 shipped 直接返回既有记录，不再扣减。
    """
    order = (
        await db.execute(
            select(m.WmsOrder).where(m.WmsOrder.id == order_id).with_for_update()
        )
    ).scalars().first()
    if order is None:
        raise OutboundError("订单不存在")

    if order.status == m.ORDER_SHIPPED:
        existing = (
            await db.execute(
                select(m.WmsShipment).where(m.WmsShipment.order_id == order_id)
            )
        ).scalars().first()
        if existing is None:
            raise OutboundError("订单已发运但缺少发运记录，请联系管理员")
        return existing

    if order.status != m.ORDER_CHECKED:
        raise OutboundError(f"订单状态 {order.status} 不能发运，请先完成复核")

    check = (
        await db.execute(select(m.WmsCheck).where(m.WmsCheck.order_id == order_id))
    ).scalars().first()
    if check is not None and not check.passed:
        raise OutboundError(
            f"称重未通过（偏差 {check.deviation}），请复核后重新记录实称"
        )

    allocs = (
        await db.execute(
            select(m.WmsAllocation).where(
                m.WmsAllocation.order_id == order_id,
                m.WmsAllocation.status == "active",
            )
        )
    ).scalars().all()
    if not allocs:
        raise OutboundError("没有有效的分配记录")

    for a in allocs:
        try:
            await post_stock(
                db,
                sku_id=a.sku_id,
                lot_id=a.lot_id,
                location_id=a.location_id,
                stock_status=STOCK_AVAILABLE,
                delta=-Decimal(str(a.qty)),
                ref_type="allocation",
                ref_id=a.id,
                action="ship",
                operator_id=operator_id,
            )
        except StockError as exc:
            raise OutboundError(
                f"分配量与实际库存不符（{exc}），请重新分配后再发运"
            ) from exc
        a.status = "shipped"

    shipment = m.WmsShipment(
        code=await next_code(db, "SHP", "", 6),
        order_id=order_id,
        owner_id=order.owner_id,
        carrier_code=order.carrier_code,
        tracking_no=tracking_no,
        shipped_at=datetime.now(),
        operator_id=operator_id,
    )
    db.add(shipment)
    order.status = m.ORDER_SHIPPED
    await db.flush()
    return shipment


async def cancel_order(db: AsyncSession, *, order_id: int) -> m.WmsOrder:
    """取消订单：分配只占额、不动库存，把 active 分配作废即可。

    已发运的订单库存已经真正扣掉，不能靠改状态把账回滚回去。
    """
    order = (
        await db.execute(
            select(m.WmsOrder)
            .where(m.WmsOrder.id == order_id)
            .with_for_update()
        )
    ).scalars().first()
    if order is None:
        raise OutboundError("订单不存在")
    if order.status == m.ORDER_CANCELLED:
        return order
    if order.status == m.ORDER_SHIPPED:
        raise OutboundError("订单已发运，不能取消")

    await db.execute(
        update(m.WmsAllocation)
        .where(
            m.WmsAllocation.order_id == order_id,
            m.WmsAllocation.status == "active",
        )
        .values(status="void")
    )
    order.status = m.ORDER_CANCELLED
    await db.flush()
    return order
