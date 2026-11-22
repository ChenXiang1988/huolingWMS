"""入库域路由：预报与服务订单。

收货与上架是"改变库存"的动作，逻辑放在 ``service.py``，这里只做校验与编排。
"""
from datetime import datetime
from decimal import Decimal
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.deps import get_current_user, require_permission
from src.core.exceptions import NotFoundException, ValidationException, success_response
from src.db import get_db
from src.models import User
from src.plugins.builtin.wms_inbound import models as m
from src.plugins.builtin.wms_master_data.service import next_code

router = APIRouter(prefix="/wms-inbound", tags=["入库"])


# ── 校验小工具 ────────────────────────────────────────


async def _sku_map(db: AsyncSession, sku_ids: list[int]) -> dict[int, dict]:
    """取商品档案的归属与批次开关。入库不 import 主数据模型，直接读需要的列。"""
    if not sku_ids:
        return {}
    from sqlalchemy import bindparam, text

    stmt = text(
        "SELECT id, owner_id, lot_required, name FROM wms_master_data_sku "
        "WHERE id IN :ids"
    ).bindparams(bindparam("ids", expanding=True))

    rows = (await db.execute(stmt, {"ids": list(sku_ids)})).all()
    return {
        r.id: {"owner_id": r.owner_id, "lot_required": r.lot_required, "name": r.name}
        for r in rows
    }


# ── 入库预报 ──────────────────────────────────────────


class AsnLineIn(BaseModel):
    sku_id: int
    expect_qty: Decimal = Field(..., gt=0)
    remark: Optional[str] = None


class AsnIn(BaseModel):
    owner_id: int
    owner_doc_no: str = Field(..., max_length=64, description="货主侧单号，用于去重")
    source: str = "manual"
    supplier_id: Optional[int] = None
    expect_arrive_at: Optional[datetime] = None
    remark: Optional[str] = None
    confirm: bool = True
    lines: list[AsnLineIn] = Field(..., min_length=1)


def _asn_dict(row: m.WmsAsn) -> dict:
    return {
        "id": row.id,
        "code": row.code,
        "owner_id": row.owner_id,
        "owner_doc_no": row.owner_doc_no,
        "source": row.source,
        "supplier_id": row.supplier_id,
        "expect_arrive_at": row.expect_arrive_at.isoformat()
        if row.expect_arrive_at
        else None,
        "status": row.status,
        "remark": row.remark,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


@router.get("/asns", summary="入库预报列表")
async def list_asns(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permission("wms_inbound:asn:list"))],
    owner_id: Optional[int] = Query(None),
    status: Optional[str] = Query(None),
    keyword: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
):
    cond = []
    if owner_id:
        cond.append(m.WmsAsn.owner_id == owner_id)
    if status:
        cond.append(m.WmsAsn.status == status)
    if keyword:
        cond.append(
            (m.WmsAsn.code.like(f"%{keyword}%"))
            | (m.WmsAsn.owner_doc_no.like(f"%{keyword}%"))
        )

    base = select(m.WmsAsn).where(*cond)
    total = (
        await db.execute(select(func.count()).select_from(base.subquery()))
    ).scalar() or 0
    rows = (
        await db.execute(
            base.order_by(m.WmsAsn.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).scalars().all()
    return success_response(
        data={
            "total": total,
            "page": page,
            "page_size": page_size,
            "items": [_asn_dict(r) for r in rows],
        }
    )


@router.get("/asns/{asn_id}", summary="入库预报详情")
async def get_asn(
    asn_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permission("wms_inbound:asn:list"))],
):
    asn = (
        await db.execute(select(m.WmsAsn).where(m.WmsAsn.id == asn_id))
    ).scalars().first()
    if asn is None:
        raise NotFoundException("预报单不存在")

    lines = (
        await db.execute(
            select(m.WmsAsnLine).where(m.WmsAsnLine.asn_id == asn_id)
        )
    ).scalars().all()
    receipts = (
        await db.execute(
            select(m.WmsReceipt).where(m.WmsReceipt.asn_id == asn_id)
        )
    ).scalars().all()

    data = _asn_dict(asn)
    data["lines"] = [
        {
            "id": ln.id,
            "sku_id": ln.sku_id,
            "expect_qty": str(ln.expect_qty),
            "remark": ln.remark,
        }
        for ln in lines
    ]
    data["receipts"] = [
        {"id": r.id, "code": r.code, "status": r.status} for r in receipts
    ]
    return success_response(data=data)


@router.post("/asns", summary="新建入库预报")
async def create_asn(
    payload: AsnIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permission("wms_inbound:asn:create"))],
):
    """建预报。``confirm=True`` 直接进 confirmed，否则留草稿。

    货主侧单号 ``owner_doc_no`` 与货主一起唯一——同一个单号重复推送时
    应当被识别为重复，而不是建出两张预报。
    """
    from src.plugins.builtin.wms_inbound.service import StockError, create_asn as _create

    try:
        asn = await _create(
            db,
            owner_id=payload.owner_id,
            owner_doc_no=payload.owner_doc_no,
            lines=[ln.model_dump() for ln in payload.lines],
            source=payload.source,
            supplier_id=payload.supplier_id,
            expect_arrive_at=payload.expect_arrive_at,
            remark=payload.remark,
            confirm=payload.confirm,
            created_by=user.id,
        )
    except StockError as exc:
        raise ValidationException(str(exc)) from exc

    await db.commit()
    return success_response(data={"id": asn.id, "code": asn.code, "status": asn.status})


async def _load_asn(db: AsyncSession, asn_id: int) -> m.WmsAsn:
    row = (
        await db.execute(select(m.WmsAsn).where(m.WmsAsn.id == asn_id))
    ).scalars().first()
    if row is None:
        raise NotFoundException("预报单不存在")
    return row


@router.post("/asns/{asn_id}/confirm", summary="确认预报")
async def confirm_asn(
    asn_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permission("wms_inbound:asn:edit"))],
):
    asn = await _load_asn(db, asn_id)
    if asn.status != m.ASN_DRAFT:
        raise ValidationException(f"当前状态 {asn.status} 不能确认")
    asn.status = m.ASN_CONFIRMED
    await db.commit()
    return success_response(data={"id": asn.id, "status": asn.status})


@router.post("/asns/{asn_id}/cancel", summary="取消预报")
async def cancel_asn(
    asn_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permission("wms_inbound:asn:edit"))],
):
    asn = await _load_asn(db, asn_id)
    if asn.status not in (m.ASN_DRAFT, m.ASN_CONFIRMED):
        raise ValidationException(
            f"当前状态 {asn.status} 不能取消：已经开始收货的单据请先结案"
        )
    asn.status = m.ASN_CANCELLED
    await db.commit()
    return success_response(data={"id": asn.id, "status": asn.status})


@router.post("/asns/{asn_id}/close", summary="结案")
async def close_asn(
    asn_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permission("wms_inbound:asn:close"))],
):
    """人工结案：把没收满的差额定性为放弃。

    没有这一步，分批到货少来几件时单据会永远挂在 receiving，
    仓里也没法判断这单还算不算在途。
    """
    asn = await _load_asn(db, asn_id)
    if asn.status not in (m.ASN_CONFIRMED, m.ASN_RECEIVING):
        raise ValidationException(f"当前状态 {asn.status} 不能结案")
    asn.status = m.ASN_CLOSED
    await db.commit()
    return success_response(data={"id": asn.id, "status": asn.status})


# ── 收货 ──────────────────────────────────────────────


@router.post("/asns/{asn_id}/receipts", summary="开收货单")
async def open_receipt(
    asn_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permission("wms_inbound:receipt:create"))],
):
    from src.plugins.builtin.wms_inbound.service import StockError, open_receipt as _open

    try:
        receipt = await _open(db, asn_id=asn_id, operator_id=user.id)
    except StockError as exc:
        raise ValidationException(str(exc)) from exc
    await db.commit()
    return success_response(data={"id": receipt.id, "code": receipt.code})


@router.get("/receipts", summary="收货单列表")
async def list_receipts(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permission("wms_inbound:receipt:list"))],
    asn_id: Optional[int] = Query(None),
    status: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
):
    cond = []
    if asn_id:
        cond.append(m.WmsReceipt.asn_id == asn_id)
    if status:
        cond.append(m.WmsReceipt.status == status)
    base = select(m.WmsReceipt).where(*cond)
    total = (
        await db.execute(select(func.count()).select_from(base.subquery()))
    ).scalar() or 0
    rows = (
        await db.execute(
            base.order_by(m.WmsReceipt.id.desc())
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
                    "asn_id": r.asn_id,
                    "owner_id": r.owner_id,
                    "status": r.status,
                    "received_at": r.received_at.isoformat() if r.received_at else None,
                }
                for r in rows
            ],
        }
    )


@router.get("/receipts/{receipt_id}", summary="收货单详情")
async def get_receipt(
    receipt_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permission("wms_inbound:receipt:list"))],
):
    receipt = (
        await db.execute(select(m.WmsReceipt).where(m.WmsReceipt.id == receipt_id))
    ).scalars().first()
    if receipt is None:
        raise NotFoundException("收货单不存在")

    lines = (
        await db.execute(
            select(m.WmsReceiptLine).where(m.WmsReceiptLine.receipt_id == receipt_id)
        )
    ).scalars().all()

    items = []
    for ln in lines:
        lots = (
            await db.execute(
                select(m.WmsReceiptLot).where(m.WmsReceiptLot.receipt_line_id == ln.id)
            )
        ).scalars().all()
        items.append(
            {
                "id": ln.id,
                "sku_id": ln.sku_id,
                "expect_qty": str(ln.expect_qty),
                "received_qty": str(ln.received_qty),
                "damaged_qty": str(ln.damaged_qty),
                "sample_qty": str(ln.sample_qty),
                "lots": [
                    {
                        "id": x.id,
                        "lot_code": x.lot_code,
                        "lot_id": x.lot_id,
                        "production_date": x.production_date.isoformat()
                        if x.production_date
                        else None,
                        "expiry_date": x.expiry_date.isoformat() if x.expiry_date else None,
                        "received_qty": str(x.received_qty),
                        "damaged_qty": str(x.damaged_qty),
                    }
                    for x in lots
                ],
            }
        )

    return success_response(
        data={
            "id": receipt.id,
            "code": receipt.code,
            "asn_id": receipt.asn_id,
            "owner_id": receipt.owner_id,
            "status": receipt.status,
            "lines": items,
        }
    )


@router.get("/receipts/{receipt_id}/scan", summary="收货扫码校验")
async def scan_receipt_barcode(
    receipt_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permission("wms_inbound:receipt:list"))],
    code: str = Query(..., min_length=1, max_length=64),
):
    """按收货单归属的货主解析商品条码。

    条码在同一货主内唯一，跨货主可重复，所以归属只从收货单取，不收请求体里的
    ``owner_id``——否则扫到别的货主的码会把别家商品定位到本单上。
    """
    from sqlalchemy import text

    key = code.strip()
    owner_id = (
        await db.execute(
            text("SELECT owner_id FROM wms_inbound_receipt WHERE id = :id"),
            {"id": receipt_id},
        )
    ).scalar()
    if owner_id is None:
        raise NotFoundException("收货单不存在")

    row = (
        await db.execute(
            text(
                "SELECT b.sku_id, s.code, s.name, s.lot_required "
                "FROM wms_master_data_barcode b "
                "JOIN wms_master_data_sku s ON s.id = b.sku_id "
                "WHERE b.owner_id = :owner AND b.barcode = :code"
            ),
            {"owner": int(owner_id), "code": key},
        )
    ).first()
    if row is None:
        raise ValidationException(f"条码 {key} 未建档，请先维护商品条码")
    return success_response(data={
        "sku_id": int(row.sku_id),
        "code": row.code,
        "name": row.name,
        "lot_required": bool(row.lot_required),
        "barcode": key,
    })


class ReceiptLineIn(BaseModel):
    sku_id: int
    received_qty: Decimal
    damaged_qty: Decimal = Decimal("0")
    lots: list[dict] = Field(default_factory=list)


class ReceiptSaveIn(BaseModel):
    lines: list[ReceiptLineIn] = Field(..., min_length=1)


@router.put("/receipts/{receipt_id}/lines", summary="保存实收与批次")
async def save_receipt_lines(
    receipt_id: int,
    payload: ReceiptSaveIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permission("wms_inbound:receipt:create"))],
):
    from src.plugins.builtin.wms_inbound.service import (
        StockError,
        save_receipt_lines as _save,
    )

    try:
        await _save(
            db,
            receipt_id=receipt_id,
            lines=[ln.model_dump() for ln in payload.lines],
        )
    except StockError as exc:
        raise ValidationException(str(exc)) from exc
    await db.commit()
    return success_response(data={"id": receipt_id})


@router.post("/receipts/{receipt_id}/confirm", summary="收货确认")
async def confirm_receipt(
    receipt_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permission("wms_inbound:receipt:confirm"))],
):
    from src.plugins.builtin.wms_inbound.service import (
        StockError,
        confirm_receipt as _confirm,
    )

    try:
        result = await _confirm(db, receipt_id=receipt_id, operator_id=user.id)
    except StockError as exc:
        raise ValidationException(str(exc)) from exc
    await db.commit()
    return success_response(data=result)


# ── 上架 ──────────────────────────────────────────────


@router.get("/putaways", summary="上架单列表")
async def list_putaways(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permission("wms_inbound:putaway:list"))],
    status: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
):
    cond = []
    if status:
        cond.append(m.WmsPutaway.status == status)
    base = select(m.WmsPutaway).where(*cond)
    total = (
        await db.execute(select(func.count()).select_from(base.subquery()))
    ).scalar() or 0
    rows = (
        await db.execute(
            base.order_by(m.WmsPutaway.id.desc())
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
                    "receipt_id": r.receipt_id,
                    "owner_id": r.owner_id,
                    "status": r.status,
                }
                for r in rows
            ],
        }
    )


@router.get("/putaways/{putaway_id}", summary="上架单详情")
async def get_putaway(
    putaway_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permission("wms_inbound:putaway:list"))],
):
    head = (
        await db.execute(select(m.WmsPutaway).where(m.WmsPutaway.id == putaway_id))
    ).scalars().first()
    if head is None:
        raise NotFoundException("上架单不存在")

    lines = (
        await db.execute(
            select(m.WmsPutawayLine).where(m.WmsPutawayLine.putaway_id == putaway_id)
        )
    ).scalars().all()

    return success_response(
        data={
            "id": head.id,
            "code": head.code,
            "receipt_id": head.receipt_id,
            "status": head.status,
            "lines": [
                {
                    "id": x.id,
                    "sku_id": x.sku_id,
                    "lot_id": x.lot_id,
                    "qty": str(x.qty),
                    "from_location_id": x.from_location_id,
                    "to_location_id": x.to_location_id,
                    "sample_flag": x.sample_flag,
                    "temp_mismatch": x.temp_mismatch,
                    "done": x.done_at is not None,
                }
                for x in lines
            ],
        }
    )


class PutawayLineIn(BaseModel):
    to_location_id: Optional[int] = None


@router.post("/putaway-lines/{line_id}/confirm", summary="上架确认")
async def confirm_putaway_line(
    line_id: int,
    payload: PutawayLineIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permission("wms_inbound:putaway:execute"))],
):
    from src.plugins.builtin.wms_inbound.service import (
        StockError,
        confirm_putaway_line as _confirm,
    )

    try:
        line = await _confirm(
            db,
            line_id=line_id,
            to_location_id=payload.to_location_id,
            operator_id=user.id,
        )
    except StockError as exc:
        raise ValidationException(str(exc)) from exc
    await db.commit()
    return success_response(
        data={
            "id": line.id,
            "to_location_id": line.to_location_id,
            "temp_mismatch": line.temp_mismatch,
        }
    )


# ── 服务订单 ──────────────────────────────────────────


class ServiceOrderIn(BaseModel):
    owner_id: int
    asn_id: Optional[int] = None
    sku_id: Optional[int] = None
    service_type: str = "sample"
    sample_mode: str = Field("fixed", pattern="^(fixed|ratio)$")
    sample_qty: Optional[Decimal] = None
    sample_ratio: Optional[Decimal] = None
    retain_days: int = 30
    on_expiry: str = Field("scrap", pattern="^(scrap|return_owner)$")


@router.get("/service-orders", summary="服务订单列表")
async def list_service_orders(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permission("wms_inbound:service_order:list"))],
    owner_id: Optional[int] = Query(None),
    asn_id: Optional[int] = Query(None),
):
    cond = []
    if owner_id:
        cond.append(m.WmsServiceOrder.owner_id == owner_id)
    if asn_id:
        cond.append(m.WmsServiceOrder.asn_id == asn_id)
    rows = (
        await db.execute(select(m.WmsServiceOrder).where(*cond).order_by(m.WmsServiceOrder.id.desc()))
    ).scalars().all()
    return success_response(
        data=[
            {
                "id": r.id,
                "code": r.code,
                "owner_id": r.owner_id,
                "asn_id": r.asn_id,
                "sku_id": r.sku_id,
                "service_type": r.service_type,
                "sample_mode": r.sample_mode,
                "sample_qty": str(r.sample_qty) if r.sample_qty is not None else None,
                "sample_ratio": str(r.sample_ratio) if r.sample_ratio is not None else None,
                "retain_days": r.retain_days,
                "on_expiry": r.on_expiry,
                "status": r.status,
            }
            for r in rows
        ]
    )


@router.post("/service-orders", summary="新建服务订单")
async def create_service_order(
    payload: ServiceOrderIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permission("wms_inbound:service_order:create"))],
):
    if payload.sample_mode == "fixed" and not payload.sample_qty:
        raise ValidationException("固定留样必须给数量")
    if payload.sample_mode == "ratio" and not payload.sample_ratio:
        raise ValidationException("按比例留样必须给比例")
    if payload.sample_ratio is not None and not (0 < payload.sample_ratio <= 1):
        raise ValidationException("留样比例应在 0 与 1 之间")

    if payload.asn_id:
        await _load_asn(db, payload.asn_id)
    if payload.sku_id:
        skus = await _sku_map(db, [payload.sku_id])
        if payload.sku_id not in skus:
            raise ValidationException("商品未建档")
        if skus[payload.sku_id]["owner_id"] != payload.owner_id:
            raise ValidationException("商品不属于该货主")

    code = await next_code(db, "DSO", "", 6)
    row = m.WmsServiceOrder(
        code=code,
        owner_id=payload.owner_id,
        asn_id=payload.asn_id,
        sku_id=payload.sku_id,
        service_type=payload.service_type,
        sample_mode=payload.sample_mode,
        sample_qty=payload.sample_qty,
        sample_ratio=payload.sample_ratio,
        retain_days=payload.retain_days,
        on_expiry=payload.on_expiry,
        status=m.SO_CONFIRMED,
        created_by=user.id,
    )
    db.add(row)
    await db.commit()
    return success_response(data={"id": row.id, "code": row.code})


# ── 货主门户建单 ────────────────────────────────────────


class PortalAsnLineIn(BaseModel):
    sku_id: int
    expect_qty: Decimal = Field(..., gt=0)


class PortalAsnIn(BaseModel):
    owner_doc_no: str = Field(..., max_length=64)
    expect_arrive_at: Optional[datetime] = None
    remark: Optional[str] = None
    lines: list[PortalAsnLineIn] = Field(..., min_length=1)


@router.post("/portal/asns", summary="货主门户建入库预报")
async def portal_create_asn(
    payload: PortalAsnIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    """``owner_id`` 由登录账号绑定的货主注入，不读请求体。

    接了 ERP 的货主预报由上游下发，这里直接拒绝，避免出现两个主数据源。
    """
    from src.plugins.builtin.wms_inbound.service import StockError, create_asn
    from src.plugins.builtin.wms_master_data.portal import owner_of_user

    ctx = await owner_of_user(db, user.id)
    if not ctx.can_create:
        raise ValidationException("该货主已接入 ERP，入库预报由上游下发，门户不再建单")

    try:
        asn = await create_asn(
            db,
            owner_id=ctx.owner_id,
            owner_doc_no=payload.owner_doc_no,
            lines=[x.model_dump() for x in payload.lines],
            source="portal",
            expect_arrive_at=payload.expect_arrive_at,
            remark=payload.remark,
            confirm=True,
        )
    except StockError as exc:
        raise ValidationException(str(exc)) from exc
    data = {"id": asn.id, "code": asn.code, "owner_id": ctx.owner_id}
    await db.commit()
    return success_response(data=data)
