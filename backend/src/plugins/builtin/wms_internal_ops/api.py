"""库内作业路由。P4 只有补货。"""
from datetime import datetime
from decimal import Decimal
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.deps import require_permission
from src.core.exceptions import NotFoundException, ValidationException, success_response
from src.db import get_db
from src.models import User
from src.plugins.builtin.wms_internal_ops import models as m
from src.plugins.builtin.wms_internal_ops.ops_service import (
    OpsError,
    backfill_samples,
    confirm_count,
    create_count,
    create_transfer,
    dispose_sample,
    execute_transfer,
    save_count_lines,
)
from src.plugins.builtin.wms_internal_ops.service import (
    ReplenishError,
    build_suggestions,
    execute_replenish,
)

router = APIRouter(prefix="/wms-internal-ops", tags=["库内作业"])


def _dict(r: m.WmsReplenish) -> dict:
    return {
        "id": r.id,
        "owner_id": r.owner_id,
        "sku_id": r.sku_id,
        "lot_id": r.lot_id,
        "from_location_id": r.from_location_id,
        "to_location_id": r.to_location_id,
        "qty": str(r.qty),
        "current_qty": str(r.current_qty),
        "min_qty": str(r.min_qty),
        "status": r.status,
        "done_at": r.done_at.isoformat() if r.done_at else None,
        "created_at": r.created_at.isoformat() if r.created_at else None,
    }


@router.get("/replenishments", summary="补货建议列表")
async def list_replenishments(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permission("wms_internal_ops:replenish:list"))],
    owner_id: Optional[int] = Query(None),
    status: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
):
    cond = []
    if owner_id:
        cond.append(m.WmsReplenish.owner_id == owner_id)
    if status:
        cond.append(m.WmsReplenish.status == status)
    base = select(m.WmsReplenish).where(*cond)
    total = (
        await db.execute(select(func.count()).select_from(base.subquery()))
    ).scalar() or 0
    rows = (
        await db.execute(
            base.order_by(m.WmsReplenish.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).scalars().all()
    return success_response(
        data={
            "total": total,
            "page": page,
            "page_size": page_size,
            "items": [_dict(r) for r in rows],
        }
    )


@router.post("/replenishments/suggest", summary="生成补货建议")
async def suggest(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permission("wms_internal_ops:replenish:create"))],
    owner_id: Optional[int] = Query(None),
):
    """只读扫描，不动库存。重复调用不会产生重复建议。"""
    rows = await build_suggestions(db, owner_id=owner_id)
    await db.commit()
    return success_response(data={"created": len(rows)})


@router.post("/replenishments/{row_id}/execute", summary="执行补货")
async def execute(
    row_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permission("wms_internal_ops:replenish:execute"))],
):
    try:
        row = await execute_replenish(db, replenish_id=row_id, operator_id=user.id)
    except ReplenishError as exc:
        raise ValidationException(str(exc)) from exc
    await db.commit()
    return success_response(data=_dict(row))


# ── 移库 ──────────────────────────────────────────────


class TransferIn(BaseModel):
    owner_id: int
    sku_id: int
    lot_id: int = 0
    from_location_id: int
    to_location_id: int
    qty: Decimal
    reason: Optional[str] = None


def _transfer_dict(r: m.WmsTransfer) -> dict:
    return {
        "id": r.id, "code": r.code, "owner_id": r.owner_id,
        "sku_id": r.sku_id, "lot_id": r.lot_id,
        "from_location_id": r.from_location_id,
        "to_location_id": r.to_location_id,
        "qty": str(r.qty), "status": r.status,
        "reason": r.reason,
        "done_at": r.done_at.isoformat() if r.done_at else None,
    }


@router.get("/transfers", summary="移库单列表")
async def list_transfers(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permission("wms_internal_ops:transfer:list"))],
    status: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
):
    cond = []
    if status:
        cond.append(m.WmsTransfer.status == status)
    base = select(m.WmsTransfer).where(*cond)
    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar() or 0
    rows = (
        await db.execute(base.order_by(m.WmsTransfer.id.desc())
                         .offset((page - 1) * page_size).limit(page_size))
    ).scalars().all()
    return success_response(data={
        "total": total, "page": page, "page_size": page_size,
        "items": [_transfer_dict(r) for r in rows],
    })


@router.post("/transfers", summary="新建移库单")
async def post_transfer(
    payload: TransferIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permission("wms_internal_ops:transfer:create"))],
):
    try:
        row = await create_transfer(db, **payload.model_dump())
    except OpsError as exc:
        raise ValidationException(str(exc)) from exc
    await db.commit()
    return success_response(data=_transfer_dict(row))


@router.post("/transfers/{transfer_id}/execute", summary="执行移库")
async def run_transfer(
    transfer_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permission("wms_internal_ops:transfer:execute"))],
):
    try:
        row = await execute_transfer(db, transfer_id=transfer_id, operator_id=user.id)
    except OpsError as exc:
        raise ValidationException(str(exc)) from exc
    await db.commit()
    return success_response(data=_transfer_dict(row))


# ── 盘点 ──────────────────────────────────────────────


class CountIn(BaseModel):
    owner_id: int
    sku_id: Optional[int] = None
    note: Optional[str] = None


class CountLineIn(BaseModel):
    line_id: int
    qty_actual: Decimal


class CountSaveIn(BaseModel):
    lines: list[CountLineIn]


def _count_dict(r: m.WmsCount) -> dict:
    return {
        "id": r.id, "code": r.code, "owner_id": r.owner_id,
        "status": r.status, "note": r.note,
        "done_at": r.done_at.isoformat() if r.done_at else None,
    }


@router.get("/counts", summary="盘点单列表")
async def list_counts(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permission("wms_internal_ops:count:list"))],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
):
    base = select(m.WmsCount)
    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar() or 0
    rows = (
        await db.execute(base.order_by(m.WmsCount.id.desc())
                         .offset((page - 1) * page_size).limit(page_size))
    ).scalars().all()
    return success_response(data={
        "total": total, "page": page, "page_size": page_size,
        "items": [_count_dict(r) for r in rows],
    })


@router.post("/counts", summary="生成盘点单")
async def post_count(
    payload: CountIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permission("wms_internal_ops:count:create"))],
):
    try:
        row = await create_count(db, owner_id=payload.owner_id,
                                sku_id=payload.sku_id, note=payload.note)
    except OpsError as exc:
        raise ValidationException(str(exc)) from exc
    await db.commit()
    return success_response(data=_count_dict(row))


@router.get("/counts/{count_id}", summary="盘点单明细")
async def get_count(
    count_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permission("wms_internal_ops:count:list"))],
):
    head = (await db.execute(select(m.WmsCount).where(m.WmsCount.id == count_id))).scalars().first()
    if head is None:
        raise NotFoundException("盘点单不存在")
    lines = (
        await db.execute(select(m.WmsCountLine).where(m.WmsCountLine.count_id == count_id))
    ).scalars().all()
    data = _count_dict(head)
    data["lines"] = [
        {
            "id": x.id, "sku_id": x.sku_id, "lot_id": x.lot_id,
            "location_id": x.location_id,
            "qty_book": str(x.qty_book),
            "qty_actual": str(x.qty_actual) if x.qty_actual is not None else None,
            "qty_diff": str(x.qty_diff), "adjusted": x.adjusted,
        }
        for x in lines
    ]
    return success_response(data=data)


@router.put("/counts/{count_id}/lines", summary="录实盘数")
async def put_count_lines(
    count_id: int,
    payload: CountSaveIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permission("wms_internal_ops:count:count"))],
):
    try:
        await save_count_lines(db, count_id=count_id,
                               lines=[x.model_dump() for x in payload.lines])
    except OpsError as exc:
        raise ValidationException(str(exc)) from exc
    await db.commit()
    return success_response(data={"id": count_id})


@router.post("/counts/{count_id}/confirm", summary="确认盘点并调整")
async def post_confirm_count(
    count_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permission("wms_internal_ops:count:confirm"))],
):
    try:
        row = await confirm_count(db, count_id=count_id, operator_id=user.id)
    except OpsError as exc:
        raise ValidationException(str(exc)) from exc
    await db.commit()
    return success_response(data=_count_dict(row))


# ── 留样台账 ──────────────────────────────────────────


def _sample_dict(r: m.WmsSample) -> dict:
    days_left = None
    if r.expire_at:
        days_left = (r.expire_at.date() - datetime.now().date()).days
    return {
        "id": r.id, "putaway_line_id": r.putaway_line_id,
        "owner_id": r.owner_id, "sku_id": r.sku_id, "lot_id": r.lot_id,
        "location_id": r.location_id, "qty": str(r.qty),
        "sampled_at": r.sampled_at.isoformat() if r.sampled_at else None,
        "expire_at": r.expire_at.isoformat() if r.expire_at else None,
        "days_left": days_left, "retain_days": r.retain_days,
        "on_expiry": r.on_expiry, "status": r.status,
        "method": r.method, "ref_out_code": r.ref_out_code,
    }


@router.get("/samples", summary="留样台账")
async def list_samples(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permission("wms_internal_ops:sample:list"))],
    status: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
):
    cond = []
    if status:
        cond.append(m.WmsSample.status == status)
    base = select(m.WmsSample).where(*cond)
    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar() or 0
    rows = (
        await db.execute(base.order_by(m.WmsSample.expire_at)
                         .offset((page - 1) * page_size).limit(page_size))
    ).scalars().all()
    return success_response(data={
        "total": total, "page": page, "page_size": page_size,
        "items": [_sample_dict(r) for r in rows],
    })


@router.post("/samples/backfill", summary="回填历史留样")
async def post_backfill(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permission("wms_internal_ops:sample:create"))],
):
    n = await backfill_samples(db)
    await db.commit()
    return success_response(data={"created": n})


class SampleDisposeIn(BaseModel):
    method: str
    reason: Optional[str] = None


@router.post("/samples/{sample_id}/dispose", summary="留样到期处置")
async def post_dispose_sample(
    sample_id: int,
    payload: SampleDisposeIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permission("wms_internal_ops:sample:dispose"))],
):
    try:
        row = await dispose_sample(
            db, sample_id=sample_id, method=payload.method,
            reason=payload.reason, operator_id=user.id,
        )
    except OpsError as exc:
        raise ValidationException(str(exc)) from exc
    await db.commit()
    return success_response(data=_sample_dict(row))
