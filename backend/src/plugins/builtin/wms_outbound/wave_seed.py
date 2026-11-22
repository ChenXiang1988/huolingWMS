"""播种墙分播：一个格口绑一个订单，扫商品即返回应放格口。

C 端小件走这里；B 端整箱走边拣边分，不进播种墙。
"""
from decimal import Decimal
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.plugins.builtin.wms_outbound import models as m


class SeedError(Exception):
    """分播被拒绝。"""


async def init_cells(db: AsyncSession, *, wave_id: int) -> list[m.WmsSortCell]:
    """按波次下的订单生成格口。重复调用不产生重复格口。"""
    wave = (
        await db.execute(select(m.WmsWave).where(m.WmsWave.id == wave_id))
    ).scalars().first()
    if wave is None:
        raise SeedError("波次不存在")

    orders = (
        await db.execute(
            select(m.WmsOrder).where(m.WmsOrder.wave_id == wave_id)
        )
    ).scalars().all()

    existing = set(
        (
            await db.execute(
                select(m.WmsSortCell.order_id).where(
                    m.WmsSortCell.wave_id == wave_id
                )
            )
        ).scalars().all()
    )

    created: list[m.WmsSortCell] = []
    for idx, order in enumerate(orders, start=1):
        if order.id in existing:
            continue
        required = (
            await db.execute(
                select(m.WmsOrderLine.qty).where(
                    m.WmsOrderLine.order_id == order.id
                )
            )
        ).scalars().all()
        total = sum((Decimal(str(q)) for q in required), Decimal("0"))
        cell = m.WmsSortCell(
            wave_id=wave_id,
            cell_no=f"C{idx:03d}",
            order_id=order.id,
            status="empty",
            required_qty=total,
        )
        db.add(cell)
        created.append(cell)

    await db.flush()
    return created


async def scan_to_cell(
    db: AsyncSession,
    *,
    wave_id: int,
    sku_id: int,
    cell_no: Optional[str],
    operator_id: Optional[int],
) -> m.WmsSortCell:
    """扫到一件商品，找到它该去的格口并记一笔。

    传了 ``cell_no`` 就校验是否匹配；不传则由系统返回应放格口。
    扫错订单/格口直接拒，不"记下来事后查"。
    """
    cells = (
        await db.execute(
            select(m.WmsSortCell).where(
                m.WmsSortCell.wave_id == wave_id,
                m.WmsSortCell.status != "full",
            ).order_by(m.WmsSortCell.cell_no)
        )
    ).scalars().all()

    target = None
    for cell in cells:
        if cell.order_id is None:
            continue
        has = (
            await db.execute(
                select(m.WmsOrderLine.id).where(
                    m.WmsOrderLine.order_id == cell.order_id,
                    m.WmsOrderLine.sku_id == sku_id,
                )
            )
        ).scalars().first()
        if has is not None:
            target = cell
            break

    if target is None:
        raise SeedError("这个商品不属于本波次任何待分播的订单，或已全部放完")
    if cell_no and cell_no != target.cell_no:
        raise SeedError(
            f"格口不对：应放 {target.cell_no}，扫到的是 {cell_no}"
        )

    db.add(
        m.WmsSeed(
            wave_id=wave_id,
            cell_id=target.id,
            order_id=target.order_id,
            sku_id=sku_id,
            qty=Decimal("1"),
            operator_id=operator_id,
        )
    )
    target.placed_qty = Decimal(str(target.placed_qty)) + Decimal("1")
    target.status = (
        "full" if target.placed_qty >= Decimal(str(target.required_qty)) else "filling"
    )

    if target.status == "full":
        order = (
            await db.execute(
                select(m.WmsOrder).where(m.WmsOrder.id == target.order_id)
            )
        ).scalars().first()
        if order is not None and order.status == m.ORDER_PICKING:
            # 分播完成直接进复核，省掉一次手工状态推进
            order.status = m.ORDER_CHECKED

    await db.flush()
    return target
