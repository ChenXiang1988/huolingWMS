"""库存记账契约。

两条唯一的写入口：

- ``post_stock``      增减数量，跨库位移动就是"扣源 + 加目标"两次调用
- ``transfer_status`` 同一库位内的状态转换，只写一条带前后状态的流水

四道闸同时成立才算记对：锁行、幂等、非负、同事务。
幂等由流水表的唯一键保证，不靠应用层判断"我上次是不是做过"。
"""
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

from loguru import logger
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.plugins.builtin.wms_inventory.models import WmsStock, WmsTxn


class StockError(Exception):
    """记账被拒绝，调用方应把整笔业务回滚。"""


@dataclass
class StockPosting:
    """一次过账的结果。``applied=False`` 表示幂等命中，本次没有改动数量。"""

    txn_id: int
    qty_after: Decimal
    applied: bool


async def _owner_of_sku(db: AsyncSession, sku_id: int) -> int:
    """从商品档案取货主。库存域不 import 主数据域的模型，只读这一列。"""
    owner_id = (
        await db.execute(
            text("SELECT owner_id FROM wms_master_data_sku WHERE id = :id"),
            {"id": sku_id},
        )
    ).scalar()
    if owner_id is None:
        raise StockError(f"货品 {sku_id} 不存在")
    return int(owner_id)


async def _lock_stock(
    db: AsyncSession,
    *,
    owner_id: int,
    sku_id: int,
    lot_id: int,
    location_id: int,
    stock_status: str,
    create: bool = True,
) -> Optional[WmsStock]:
    """取库存行并加行锁。

    行不存在时插入一条零数量记录再锁它——先插入是为了让并发方拿到同一行，
    否则两个事务会各自认为"没有这行"，双双插入后撞唯一键。
    """
    stmt = (
        select(WmsStock)
        .where(
            WmsStock.owner_id == owner_id,
            WmsStock.sku_id == sku_id,
            WmsStock.lot_id == lot_id,
            WmsStock.location_id == location_id,
            WmsStock.stock_status == stock_status,
        )
        .with_for_update()
    )
    row = (await db.execute(stmt)).scalars().first()
    if row is not None or not create:
        return row

    row = WmsStock(
        owner_id=owner_id,
        sku_id=sku_id,
        lot_id=lot_id,
        location_id=location_id,
        stock_status=stock_status,
        qty=Decimal("0"),
    )
    db.add(row)
    try:
        async with db.begin_nested():
            await db.flush()
    except IntegrityError:
        # 并发方已经插入，重新取一次并加锁
        row = (await db.execute(stmt)).scalars().first()
        if row is None:
            raise StockError("并发建立库存行失败，请重试") from None
    return row


async def ensure_lot(
    db: AsyncSession,
    *,
    owner_id: int,
    sku_id: int,
    lot_code: str,
    production_date=None,
    expiry_date=None,
) -> int:
    """按批号取批次，没有就建。返回 ``lot_id``。

    同一货主同一商品下批号唯一。批号已存在但效期不同时直接拒绝——
    一个批号两个到期日，先到期先出就无从算起，宁可让人换批号。
    """
    from datetime import date

    from src.plugins.builtin.wms_inventory.models import WmsLot

    stmt = (
        select(WmsLot)
        .where(
            WmsLot.owner_id == owner_id,
            WmsLot.sku_id == sku_id,
            WmsLot.lot_code == lot_code,
        )
        .with_for_update()
    )
    row = (await db.execute(stmt)).scalars().first()

    if row is not None:
        for field, given in (("expiry_date", expiry_date), ("production_date", production_date)):
            if given is None:
                continue
            existing = getattr(row, field)
            if existing is not None and existing != given:
                raise StockError(
                    f"批号 {lot_code} 的 {field} 与已有记录不一致："
                    f"已有 {existing}，本次 {given}"
                )
        return row.id

    lot = WmsLot(
        owner_id=owner_id,
        sku_id=sku_id,
        lot_code=lot_code,
        production_date=production_date if isinstance(production_date, date) else None,
        expiry_date=expiry_date if isinstance(expiry_date, date) else None,
    )
    db.add(lot)
    try:
        async with db.begin_nested():
            await db.flush()
    except IntegrityError:
        row = (await db.execute(stmt)).scalars().first()
        if row is None:
            raise StockError("并发建立批次失败，请重试") from None
        return row.id
    return lot.id


async def post_stock(
    db: AsyncSession,
    *,
    sku_id: int,
    lot_id: int,
    location_id: int,
    stock_status: str,
    delta: Decimal,
    ref_type: str,
    ref_id: int,
    action: str,
    operator_id: Optional[int] = None,
) -> StockPosting:
    """增减库存并写一条流水。调用方负责提交事务。"""
    delta = Decimal(str(delta))
    if delta == 0:
        raise StockError("过账数量不能为 0")

    owner_id = await _owner_of_sku(db, sku_id)
    row = await _lock_stock(
        db,
        owner_id=owner_id,
        sku_id=sku_id,
        lot_id=lot_id,
        location_id=location_id,
        stock_status=stock_status,
    )
    assert row is not None

    qty_after = Decimal(str(row.qty)) + delta
    if qty_after < 0:
        raise StockError(
            f"库存不足：当前 {row.qty}，本次扣减 {abs(delta)}，"
            f"货品 {sku_id} 批次 {lot_id} 库位 {location_id}"
        )

    txn = WmsTxn(
        ref_type=ref_type,
        ref_id=ref_id,
        action=action,
        owner_id=owner_id,
        sku_id=sku_id,
        lot_id=lot_id,
        location_id=location_id,
        stock_status=stock_status,
        delta=delta,
        qty_after=qty_after,
        operator_id=operator_id,
    )
    try:
        async with db.begin_nested():
            db.add(txn)
            await db.flush()
    except IntegrityError:
        logger.info(
            f"过账幂等命中：{ref_type}/{ref_id} {action} sku={sku_id} lot={lot_id} "
            f"loc={location_id} {stock_status}"
        )
        existing = (
            await db.execute(
                select(WmsTxn).where(
                    WmsTxn.ref_type == ref_type,
                    WmsTxn.ref_id == ref_id,
                    WmsTxn.sku_id == sku_id,
                    WmsTxn.lot_id == lot_id,
                    WmsTxn.location_id == location_id,
                    WmsTxn.action == action,
                )
            )
        ).scalars().first()
        return StockPosting(
            txn_id=existing.id if existing else 0,
            qty_after=Decimal(str(row.qty)),
            applied=False,
        )

    row.qty = qty_after
    await db.flush()
    return StockPosting(txn_id=txn.id, qty_after=qty_after, applied=True)


async def transfer_status(
    db: AsyncSession,
    *,
    sku_id: int,
    lot_id: int,
    location_id: int,
    from_status: str,
    to_status: str,
    qty: Decimal,
    ref_type: str,
    ref_id: int,
    action: str,
    operator_id: Optional[int] = None,
) -> StockPosting:
    """同一库位内的状态转换，例如 available → frozen。

    总量守恒：源状态减多少，目标状态加多少。写一条流水，带前后状态，
    ``delta`` 为 0——它不是数量变动，是状态变动。
    """
    qty = Decimal(str(qty))
    if qty <= 0:
        raise StockError("状态转换数量必须大于 0")
    if from_status == to_status:
        raise StockError("源状态与目标状态相同")

    owner_id = await _owner_of_sku(db, sku_id)
    src = await _lock_stock(
        db,
        owner_id=owner_id,
        sku_id=sku_id,
        lot_id=lot_id,
        location_id=location_id,
        stock_status=from_status,
        create=False,
    )
    if src is None or Decimal(str(src.qty)) < qty:
        current = src.qty if src else 0
        raise StockError(f"{from_status} 数量不足：当前 {current}，需要 {qty}")

    dst = await _lock_stock(
        db,
        owner_id=owner_id,
        sku_id=sku_id,
        lot_id=lot_id,
        location_id=location_id,
        stock_status=to_status,
    )
    assert dst is not None

    txn = WmsTxn(
        ref_type=ref_type,
        ref_id=ref_id,
        action=action,
        owner_id=owner_id,
        sku_id=sku_id,
        lot_id=lot_id,
        location_id=location_id,
        stock_status=to_status,
        from_status=from_status,
        to_status=to_status,
        delta=Decimal("0"),
        qty_after=Decimal(str(dst.qty)) + qty,
        operator_id=operator_id,
    )
    try:
        async with db.begin_nested():
            db.add(txn)
            await db.flush()
    except IntegrityError:
        logger.info(f"状态转换幂等命中：{ref_type}/{ref_id} {action}")
        return StockPosting(
            txn_id=0, qty_after=Decimal(str(dst.qty)), applied=False
        )

    src.qty = Decimal(str(src.qty)) - qty
    dst.qty = Decimal(str(dst.qty)) + qty
    await db.flush()
    return StockPosting(txn_id=txn.id, qty_after=Decimal(str(dst.qty)), applied=True)
