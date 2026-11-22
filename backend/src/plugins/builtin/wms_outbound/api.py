"""出库域路由：订单、分配、拣货、复核、发运。"""
from decimal import Decimal
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import bindparam, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.deps import get_current_user, require_permission
from src.core.exceptions import NotFoundException, ValidationException, success_response
from src.db import get_db
from src.models import User
from src.plugins.builtin.wms_outbound import models as m
from src.plugins.builtin.wms_outbound.service import (
    OutboundError,
    allocate_fefo,
    cancel_order,
    confirm_pick_line,
    create_order,
    release_to_pick,
    save_check,
    ship,
)

router = APIRouter(prefix="/wms-outbound", tags=["出库"])


# ── 订单 ──────────────────────────────────────────────


class OrderLineIn(BaseModel):
    sku_id: int
    qty: Decimal = Field(..., gt=0)
    lot_id: Optional[int] = None


class OrderIn(BaseModel):
    owner_id: int
    owner_doc_no: str = Field(..., max_length=64)
    order_type: str = Field("C", pattern="^(B|C)$")
    customer_name: Optional[str] = None
    receiver: Optional[str] = None
    receiver_phone: Optional[str] = None
    receiver_address: Optional[str] = None
    carrier_code: Optional[str] = None
    lines: list[OrderLineIn] = Field(..., min_length=1)


def _order_dict(r: m.WmsOrder) -> dict:
    return {
        "id": r.id,
        "code": r.code,
        "owner_id": r.owner_id,
        "owner_doc_no": r.owner_doc_no,
        "order_type": r.order_type,
        "source": r.source,
        "receiver": r.receiver,
        "carrier_code": r.carrier_code,
        "status": r.status,
        "weight_theory": str(r.weight_theory) if r.weight_theory is not None else None,
        "weight_actual": str(r.weight_actual) if r.weight_actual is not None else None,
        "created_at": r.created_at.isoformat() if r.created_at else None,
    }


@router.get("/orders", summary="出库订单列表")
async def list_orders(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permission("wms_outbound:order:list"))],
    owner_id: Optional[int] = Query(None),
    status: Optional[str] = Query(None),
    keyword: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
):
    cond = []
    if owner_id:
        cond.append(m.WmsOrder.owner_id == owner_id)
    if status:
        cond.append(m.WmsOrder.status == status)
    if keyword:
        cond.append(
            (m.WmsOrder.code.like(f"%{keyword}%"))
            | (m.WmsOrder.owner_doc_no.like(f"%{keyword}%"))
        )
    base = select(m.WmsOrder).where(*cond)
    total = (
        await db.execute(select(func.count()).select_from(base.subquery()))
    ).scalar() or 0
    rows = (
        await db.execute(
            base.order_by(m.WmsOrder.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).scalars().all()
    return success_response(
        data={
            "total": total,
            "page": page,
            "page_size": page_size,
            "items": [_order_dict(r) for r in rows],
        }
    )


@router.get("/orders/{order_id}", summary="订单详情")
async def get_order(
    order_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permission("wms_outbound:order:list"))],
):
    order = (
        await db.execute(select(m.WmsOrder).where(m.WmsOrder.id == order_id))
    ).scalars().first()
    if order is None:
        raise NotFoundException("订单不存在")

    lines = (
        await db.execute(
            select(m.WmsOrderLine).where(m.WmsOrderLine.order_id == order_id)
        )
    ).scalars().all()
    allocs = (
        await db.execute(
            select(m.WmsAllocation).where(
                m.WmsAllocation.order_id == order_id,
                m.WmsAllocation.status == "active",
            )
        )
    ).scalars().all()

    data = _order_dict(order)
    data["lines"] = [
        {
            "id": ln.id,
            "sku_id": ln.sku_id,
            "qty": str(ln.qty),
            "lot_id": ln.lot_id,
            "allocated_qty": str(ln.allocated_qty),
        }
        for ln in lines
    ]
    data["allocations"] = [
        {
            "id": a.id,
            "sku_id": a.sku_id,
            "lot_id": a.lot_id,
            "location_id": a.location_id,
            "qty": str(a.qty),
        }
        for a in allocs
    ]
    return success_response(data=data)


@router.post("/orders", summary="新建出库订单")
async def post_order(
    payload: OrderIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permission("wms_outbound:order:create"))],
):
    try:
        order = await create_order(
            db,
            owner_id=payload.owner_id,
            owner_doc_no=payload.owner_doc_no,
            lines=[ln.model_dump() for ln in payload.lines],
            order_type=payload.order_type,
            customer_name=payload.customer_name,
            receiver=payload.receiver,
            receiver_phone=payload.receiver_phone,
            receiver_address=payload.receiver_address,
            carrier_code=payload.carrier_code,
            created_by=user.id,
        )
    except OutboundError as exc:
        raise ValidationException(str(exc)) from exc
    await db.commit()
    return success_response(data={"id": order.id, "code": order.code, "status": order.status})


@router.post("/orders/{order_id}/allocate", summary="分配")
async def allocate(
    order_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permission("wms_outbound:order:allocate"))],
):
    try:
        allocs = await allocate_fefo(db, order_id=order_id, operator_id=user.id)
    except OutboundError as exc:
        raise ValidationException(str(exc)) from exc
    await db.commit()
    return success_response(
        data={
            "allocations": len(allocs),
            "qty": str(sum((Decimal(str(a.qty)) for a in allocs), Decimal("0"))),
        }
    )


@router.post("/orders/{order_id}/cancel", summary="取消订单")
async def cancel(
    order_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permission("wms_outbound:order:cancel"))],
):
    try:
        order = await cancel_order(db, order_id=order_id)
    except OutboundError as exc:
        raise ValidationException(str(exc)) from exc
    data = {"id": order.id, "code": order.code, "status": order.status}
    await db.commit()
    return success_response(data=data)


@router.post("/orders/{order_id}/pick", summary="生成拣货单")
async def make_pick(
    order_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permission("wms_outbound:pick:list"))],
):
    try:
        pick = await release_to_pick(db, order_id=order_id, operator_id=user.id)
    except OutboundError as exc:
        raise ValidationException(str(exc)) from exc
    await db.commit()
    return success_response(data={"id": pick.id, "code": pick.code})


# ── 拣货 ──────────────────────────────────────────────


@router.get("/picks", summary="拣货单列表")
async def list_picks(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permission("wms_outbound:pick:list"))],
    status: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
):
    cond = []
    if status:
        cond.append(m.WmsPick.status == status)
    base = select(m.WmsPick).where(*cond)
    total = (
        await db.execute(select(func.count()).select_from(base.subquery()))
    ).scalar() or 0
    rows = (
        await db.execute(
            base.order_by(m.WmsPick.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).scalars().all()
    return success_response(
        data={
            "total": total,
            "page": page,
            "page_size": page_size,
            "items": [
                {
                    "id": r.id,
                    "code": r.code,
                    "order_id": r.order_id,
                    "owner_id": r.owner_id,
                    "status": r.status,
                }
                for r in rows
            ],
        }
    )


@router.get("/picks/{pick_id}", summary="拣货单详情")
async def get_pick(
    pick_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permission("wms_outbound:pick:list"))],
):
    head = (
        await db.execute(select(m.WmsPick).where(m.WmsPick.id == pick_id))
    ).scalars().first()
    if head is None:
        raise NotFoundException("拣货单不存在")

    lines = (
        await db.execute(
            select(m.WmsPickLine)
            .where(m.WmsPickLine.pick_id == pick_id)
            .order_by(m.WmsPickLine.seq)
        )
    ).scalars().all()

    return success_response(
        data={
            "id": head.id,
            "code": head.code,
            "order_id": head.order_id,
            "status": head.status,
            "lines": [
                {
                    "id": x.id,
                    "seq": x.seq,
                    "sku_id": x.sku_id,
                    "lot_id": x.lot_id,
                    "location_id": x.location_id,
                    "qty": str(x.qty),
                    "picked": x.picked_at is not None,
                }
                for x in lines
            ],
        }
    )


class PickLineIn(BaseModel):
    location_code: Optional[str] = None


@router.post("/pick-lines/{line_id}/confirm", summary="拣货确认")
async def confirm_pick(
    line_id: int,
    payload: PickLineIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permission("wms_outbound:pick:execute"))],
):
    try:
        line = await confirm_pick_line(
            db,
            line_id=line_id,
            location_code=payload.location_code,
            operator_id=user.id,
        )
    except OutboundError as exc:
        raise ValidationException(str(exc)) from exc
    await db.commit()

    # 整单拣完自动推进状态
    remaining = (
        await db.execute(
            select(func.count())
            .select_from(m.WmsPickLine)
            .where(
                m.WmsPickLine.pick_id == line.pick_id,
                m.WmsPickLine.picked_at.is_(None),
            )
        )
    ).scalar() or 0
    if remaining == 0:
        head = (
            await db.execute(select(m.WmsPick).where(m.WmsPick.id == line.pick_id))
        ).scalars().first()
        if head is not None:
            head.status = m.PICK_DONE
            await db.commit()

    return success_response(data={"id": line.id, "remaining": remaining})


# ── 复核与发运 ─────────────────────────────────────────


class CheckIn(BaseModel):
    weight_actual: Decimal = Field(..., gt=0)
    tolerance: Optional[Decimal] = None


@router.post("/orders/{order_id}/check", summary="记录实称")
async def record_check(
    order_id: int,
    payload: CheckIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permission("wms_outbound:check:record"))],
):
    try:
        kwargs = {"order_id": order_id, "weight_actual": payload.weight_actual,
                  "operator_id": user.id}
        if payload.tolerance is not None:
            kwargs["tolerance"] = payload.tolerance
        row = await save_check(db, **kwargs)
    except OutboundError as exc:
        raise ValidationException(str(exc)) from exc
    await db.commit()
    return success_response(
        data={
            "passed": row.passed,
            "deviation": str(row.deviation) if row.deviation is not None else None,
            "weight_theory": str(row.weight_theory) if row.weight_theory is not None else None,
            "reason": row.reason,
        }
    )


class ShipIn(BaseModel):
    tracking_no: Optional[str] = None


@router.post("/orders/{order_id}/ship", summary="发运")
async def ship_order(
    order_id: int,
    payload: ShipIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permission("wms_outbound:check:ship"))],
):
    try:
        row = await ship(
            db,
            order_id=order_id,
            tracking_no=payload.tracking_no,
            operator_id=user.id,
        )
    except OutboundError as exc:
        raise ValidationException(str(exc)) from exc
    await db.commit()
    return success_response(data={"code": row.code, "shipped_at": str(row.shipped_at)})


# ── 货主门户建单 ────────────────────────────────────────


class PortalOrderLineIn(BaseModel):
    sku_id: int
    qty: Decimal = Field(..., gt=0)
    lot_id: Optional[int] = None


class PortalOrderIn(BaseModel):
    owner_doc_no: str = Field(..., max_length=64)
    order_type: str = Field("C", pattern="^(B|C)$")
    receiver: Optional[str] = None
    receiver_phone: Optional[str] = None
    receiver_address: Optional[str] = None
    carrier_code: Optional[str] = None
    lines: list[PortalOrderLineIn] = Field(..., min_length=1)


@router.post("/portal/orders", summary="货主门户建出库订单")
async def portal_create_order(
    payload: PortalOrderIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    """``owner_id`` 由会话注入；接了 ERP 的货主订单由上游下发。"""
    from src.plugins.builtin.wms_master_data.portal import owner_of_user
    from src.plugins.builtin.wms_outbound.service import OutboundError, create_order

    ctx = await owner_of_user(db, user.id)
    if not ctx.can_create:
        raise ValidationException("该货主已接入 ERP，出库订单由上游下发，门户不再建单")

    try:
        order = await create_order(
            db,
            owner_id=ctx.owner_id,
            owner_doc_no=payload.owner_doc_no,
            lines=[x.model_dump() for x in payload.lines],
            order_type=payload.order_type,
            source="portal",
            receiver=payload.receiver,
            receiver_phone=payload.receiver_phone,
            receiver_address=payload.receiver_address,
            carrier_code=payload.carrier_code,
        )
    except OutboundError as exc:
        raise ValidationException(str(exc)) from exc
    data = {"id": order.id, "code": order.code, "owner_id": ctx.owner_id}
    await db.commit()
    return success_response(data=data)


@router.get("/portal/orders", summary="货主门户订单列表")
async def portal_list_orders(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    status: Optional[str] = Query(None),
    keyword: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
):
    """只看自己货主的单。

    ``owner_id`` 不接受入参——货主传别家 id 也查不到，越权在参数层面就无从发起。
    """
    from src.plugins.builtin.wms_master_data.portal import owner_of_user

    ctx = await owner_of_user(db, user.id)
    cond = [m.WmsOrder.owner_id == ctx.owner_id]
    if status:
        cond.append(m.WmsOrder.status == status)
    if keyword:
        cond.append(
            (m.WmsOrder.code.like(f"%{keyword}%"))
            | (m.WmsOrder.owner_doc_no.like(f"%{keyword}%"))
        )

    base = select(m.WmsOrder).where(*cond)
    total = (
        await db.execute(select(func.count()).select_from(base.subquery()))
    ).scalar() or 0
    rows = (
        await db.execute(
            base.order_by(m.WmsOrder.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).scalars().all()

    ids = [r.id for r in rows]
    agg: dict[int, tuple[int, Decimal]] = {}
    if ids:
        for oid, cnt, qty in (
            await db.execute(
                text(
                    "SELECT order_id, COUNT(*), COALESCE(SUM(qty), 0) "
                    "FROM wms_outbound_order_line "
                    "WHERE order_id IN :ids GROUP BY order_id"
                ).bindparams(bindparam("ids", expanding=True)),
                {"ids": ids},
            )
        ).all():
            agg[int(oid)] = (int(cnt), Decimal(str(qty)))

    return success_response(
        data={
            "total": total,
            "page": page,
            "page_size": page_size,
            "items": [
                {
                    "id": r.id,
                    "code": r.code,
                    "owner_doc_no": r.owner_doc_no,
                    "order_type": r.order_type,
                    "status": r.status,
                    "receiver": r.receiver,
                    "carrier_code": r.carrier_code,
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                    "line_count": agg.get(r.id, (0, Decimal("0")))[0],
                    "qty_total": str(agg.get(r.id, (0, Decimal("0")))[1]),
                }
                for r in rows
            ],
        }
    )


@router.get("/portal/orders/{order_id}", summary="货主门户订单详情")
async def portal_get_order(
    order_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    """别家货主的单返回 404，不用 403——403 等于告诉对方「这单存在」。"""
    from src.plugins.builtin.wms_master_data.portal import owner_of_user

    ctx = await owner_of_user(db, user.id)
    order = (
        await db.execute(
            select(m.WmsOrder).where(
                m.WmsOrder.id == order_id,
                m.WmsOrder.owner_id == ctx.owner_id,
            )
        )
    ).scalars().first()
    if order is None:
        raise NotFoundException("订单不存在")

    lines = (
        await db.execute(
            text(
                "SELECT l.sku_id, l.qty, l.allocated_qty, l.lot_id, "
                "       s.code AS sku_code, s.owner_sku_code, s.name AS sku_name "
                "FROM wms_outbound_order_line l "
                "LEFT JOIN wms_master_data_sku s ON s.id = l.sku_id "
                "WHERE l.order_id = :oid ORDER BY l.id"
            ),
            {"oid": order_id},
        )
    ).all()

    # 运单号与发运时间都在发运记录上，订单表没有这两列
    ship = (
        await db.execute(
            text(
                "SELECT tracking_no, shipped_at FROM wms_outbound_shipment "
                "WHERE order_id = :oid ORDER BY id DESC LIMIT 1"
            ),
            {"oid": order_id},
        )
    ).first()

    return success_response(
        data={
            "id": order.id,
            "code": order.code,
            "owner_doc_no": order.owner_doc_no,
            "order_type": order.order_type,
            "status": order.status,
            "receiver": order.receiver,
            "receiver_phone": order.receiver_phone,
            "receiver_address": order.receiver_address,
            "carrier_code": order.carrier_code,
            "tracking_no": ship.tracking_no if ship else None,
            "weight_theory": str(order.weight_theory) if order.weight_theory is not None else None,
            "created_at": order.created_at.isoformat() if order.created_at else None,
            "shipped_at": ship.shipped_at.isoformat() if ship and ship.shipped_at else None,
            "lines": [
                {
                    "sku_id": r.sku_id,
                    "sku_code": r.sku_code,
                    "owner_sku_code": r.owner_sku_code,
                    "sku_name": r.sku_name,
                    "qty": str(r.qty),
                    "allocated_qty": str(r.allocated_qty),
                    "lot_id": r.lot_id,
                }
                for r in lines
            ],
        }
    )
