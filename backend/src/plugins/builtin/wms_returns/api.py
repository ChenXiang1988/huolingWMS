"""逆向域路由：待处置清单、处置提交、退货单。"""
from decimal import Decimal
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.deps import require_permission
from src.core.exceptions import NotFoundException, ValidationException, success_response
from src.db import get_db
from src.models import User
from src.plugins.builtin.wms_inventory.service import StockError
from src.plugins.builtin.wms_returns import models as m
from src.plugins.builtin.wms_returns.return_service import (
    ReturnError,
    create_return,
    receive_return,
)
from src.plugins.builtin.wms_returns.service import dispose

router = APIRouter(prefix="/wms-returns", tags=["逆向"])


@router.get("/disposals", summary="待处置库存")
async def list_disposals(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permission("wms_returns:disposal:list"))],
    owner_id: Optional[int] = Query(None),
    status: str = Query("pending"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
):
    """默认只看待处置。按创建时间升序——积压最久的排在最前。"""
    cond = [m.WmsDisposal.status == status]
    if owner_id:
        cond.append(m.WmsDisposal.owner_id == owner_id)

    base = select(m.WmsDisposal).where(*cond)
    total = (
        await db.execute(select(func.count()).select_from(base.subquery()))
    ).scalar() or 0
    rows = (
        await db.execute(
            base.order_by(m.WmsDisposal.created_at)
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
                    "owner_id": r.owner_id,
                    "sku_id": r.sku_id,
                    "lot_id": r.lot_id,
                    "location_id": r.location_id,
                    "qty": str(r.qty),
                    "method": r.method,
                    "status": r.status,
                    "source_ref_type": r.source_ref_type,
                    "source_ref_id": r.source_ref_id,
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                    "handled_at": r.handled_at.isoformat() if r.handled_at else None,
                }
                for r in rows
            ],
        }
    )


class DisposeIn(BaseModel):
    method: str = Field(..., pattern="^(restock|scrap|return_owner)$")
    reason: Optional[str] = Field(None, max_length=255)


@router.post("/disposals/{disposal_id}/handle", summary="处置")
async def handle_disposal(
    disposal_id: int,
    payload: DisposeIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permission("wms_returns:disposal:list"))],
):
    try:
        row = await dispose(
            db,
            disposal_id=disposal_id,
            method=payload.method,
            reason=payload.reason,
            operator_id=user.id,
        )
    except StockError as exc:
        raise ValidationException(str(exc)) from exc

    await db.commit()
    return success_response(
        data={"id": row.id, "status": row.status, "method": row.method}
    )


# ── 退货单 ────────────────────────────────────────────


class ReturnLineIn(BaseModel):
    sku_id: int
    lot_id: int = 0
    qty: Decimal = Field(..., gt=0)
    quality: str = Field("good", pattern="^(good|damaged)$")


class ReturnIn(BaseModel):
    owner_id: int
    owner_doc_no: Optional[str] = None
    customer_name: Optional[str] = None
    source_order_code: Optional[str] = None
    remark: Optional[str] = None
    lines: list[ReturnLineIn] = Field(..., min_length=1)


def _return_dict(r: m.WmsReturn, *, include_dates: bool = True) -> dict:
    """``include_dates=False`` 用于刚 flush 的对象。

    ``created_at`` / ``updated_at`` 由数据库生成，flush 后处于 expired 状态；
    在异步会话里读它们会触发隐式 SELECT 并抛 MissingGreenlet。
    """
    return {
        "id": r.id, "code": r.code, "owner_id": r.owner_id,
        "owner_doc_no": r.owner_doc_no, "customer_name": r.customer_name,
        "source_order_code": r.source_order_code,
        "status": r.status, "remark": r.remark,
        "received_at": (
            r.received_at.isoformat() if r.received_at else None
        ) if include_dates else None,
        "created_at": (
            r.created_at.isoformat() if r.created_at else None
        ) if include_dates else None,
    }


@router.get("/returns", summary="退货单列表")
async def list_returns(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permission("wms_returns:return:list"))],
    owner_id: Optional[int] = Query(None),
    status: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
):
    cond = []
    if owner_id:
        cond.append(m.WmsReturn.owner_id == owner_id)
    if status:
        cond.append(m.WmsReturn.status == status)
    base = select(m.WmsReturn).where(*cond)
    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar() or 0
    rows = (
        await db.execute(base.order_by(m.WmsReturn.id.desc())
                         .offset((page - 1) * page_size).limit(page_size))
    ).scalars().all()
    return success_response(data={
        "total": total, "page": page, "page_size": page_size,
        "items": [_return_dict(r) for r in rows],
    })


@router.get("/returns/{return_id}", summary="退货单详情")
async def get_return(
    return_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permission("wms_returns:return:list"))],
):
    head = (await db.execute(select(m.WmsReturn).where(m.WmsReturn.id == return_id))).scalars().first()
    if head is None:
        raise NotFoundException("退货单不存在")
    lines = (
        await db.execute(select(m.WmsReturnLine).where(m.WmsReturnLine.return_id == return_id))
    ).scalars().all()
    data = _return_dict(head)
    data["lines"] = [
        {
            "id": x.id, "sku_id": x.sku_id, "lot_id": x.lot_id,
            "qty": str(x.qty), "quality": x.quality, "posted": x.posted,
        }
        for x in lines
    ]
    return success_response(data=data)


@router.post("/returns", summary="新建退货单")
async def post_return(
    payload: ReturnIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permission("wms_returns:return:create"))],
):
    try:
        head = await create_return(
            db, owner_id=payload.owner_id,
            lines=[x.model_dump() for x in payload.lines],
            owner_doc_no=payload.owner_doc_no,
            customer_name=payload.customer_name,
            source_order_code=payload.source_order_code,
            remark=payload.remark,
        )
    except ReturnError as exc:
        raise ValidationException(str(exc)) from exc
    # 刚 flush 的对象不带 created_at，不能读
    data = _return_dict(head, include_dates=False)
    await db.commit()
    return success_response(data=data)


@router.post("/returns/{return_id}/receive", summary="确认退货入库")
async def post_receive_return(
    return_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permission("wms_returns:return:receive"))],
):
    try:
        head = await receive_return(db, return_id=return_id, operator_id=user.id)
    except ReturnError as exc:
        raise ValidationException(str(exc)) from exc
    data = _return_dict(head, include_dates=False)
    await db.commit()
    return success_response(data=data)
