"""库存域路由：库存查询、流水、批次、手工调整。

查询一律带 ``owner_id`` 过滤；手工调整走 ``post_stock``，不自己写 SQL 改数量。
"""
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.deps import require_permission
from src.core.exceptions import ValidationException, success_response
from src.db import get_db
from src.models import User
from src.plugins.builtin.wms_inventory.models import WmsLot, WmsStock, WmsTxn
from src.plugins.builtin.wms_inventory.service import StockError, post_stock

router = APIRouter(prefix="/wms-inventory", tags=["库存"])


# ── 库存查询 ──────────────────────────────────────────


@router.get("/stocks", summary="库存列表（按商品聚合）")
async def list_stocks(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permission("wms_inventory:stock:list"))],
    owner_id: Optional[int] = Query(None),
    sku_id: Optional[int] = Query(None),
    location_id: Optional[int] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
):
    """默认按「货主 + 商品 + 状态」聚合。

    三万单量级下把批次铺开会让列表直接卡死，所以批次明细只在 ``/lots`` 里看。
    """
    # 数量归零的行是过账留下的锚点，不该出现在列表里
    cond = [WmsStock.qty != 0]
    if owner_id:
        cond.append(WmsStock.owner_id == owner_id)
    if sku_id:
        cond.append(WmsStock.sku_id == sku_id)
    if location_id:
        cond.append(WmsStock.location_id == location_id)

    grouped = (
        select(
            WmsStock.owner_id,
            WmsStock.sku_id,
            WmsStock.stock_status,
            func.sum(WmsStock.qty).label("qty"),
            func.count(func.distinct(WmsStock.lot_id)).label("lot_count"),
        )
        .where(*cond)
        .group_by(WmsStock.owner_id, WmsStock.sku_id, WmsStock.stock_status)
    )

    total = (
        await db.execute(select(func.count()).select_from(grouped.subquery()))
    ).scalar() or 0

    rows = (
        await db.execute(
            grouped.order_by(WmsStock.owner_id, WmsStock.sku_id)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).all()

    items = [
        {
            "owner_id": r.owner_id,
            "sku_id": r.sku_id,
            "stock_status": r.stock_status,
            "qty": str(r.qty),
            "lot_count": r.lot_count,
        }
        for r in rows
    ]
    return success_response(
        data={"total": total, "page": page, "page_size": page_size, "items": items}
    )


@router.get("/stocks/detail", summary="库存明细（到批次与库位）")
async def list_stock_detail(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permission("wms_inventory:stock:list"))],
    sku_id: int = Query(...),
    owner_id: Optional[int] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
):
    cond = [WmsStock.sku_id == sku_id, WmsStock.qty != 0]
    if owner_id:
        cond.append(WmsStock.owner_id == owner_id)

    base = select(WmsStock).where(*cond)
    total = (
        await db.execute(select(func.count()).select_from(base.subquery()))
    ).scalar() or 0
    rows = (
        await db.execute(
            base.order_by(WmsStock.lot_id, WmsStock.location_id)
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
                    "stock_status": r.stock_status,
                    "qty": str(r.qty),
                }
                for r in rows
            ],
        }
    )


# ── 流水 ─────────────────────────────────────────────


@router.get("/txns", summary="库存流水")
async def list_txns(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permission("wms_inventory:txn:list"))],
    owner_id: Optional[int] = Query(None),
    sku_id: Optional[int] = Query(None),
    lot_id: Optional[int] = Query(None),
    action: Optional[str] = Query(None),
    start_at: Optional[datetime] = Query(None),
    end_at: Optional[datetime] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
):
    cond = []
    if owner_id:
        cond.append(WmsTxn.owner_id == owner_id)
    if sku_id:
        cond.append(WmsTxn.sku_id == sku_id)
    if lot_id is not None:
        cond.append(WmsTxn.lot_id == lot_id)
    if action:
        cond.append(WmsTxn.action == action)
    if start_at:
        cond.append(WmsTxn.created_at >= start_at)
    if end_at:
        cond.append(WmsTxn.created_at <= end_at)

    base = select(WmsTxn).where(*cond)
    total = (
        await db.execute(select(func.count()).select_from(base.subquery()))
    ).scalar() or 0
    rows = (
        await db.execute(
            base.order_by(WmsTxn.id.desc())
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
                    "ref_type": r.ref_type,
                    "ref_id": r.ref_id,
                    "action": r.action,
                    "owner_id": r.owner_id,
                    "sku_id": r.sku_id,
                    "lot_id": r.lot_id,
                    "location_id": r.location_id,
                    "stock_status": r.stock_status,
                    "from_status": r.from_status,
                    "to_status": r.to_status,
                    "delta": str(r.delta),
                    "qty_after": str(r.qty_after),
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                }
                for r in rows
            ],
        }
    )


# ── 批次 ─────────────────────────────────────────────


@router.get("/lots", summary="批次列表")
async def list_lots(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permission("wms_inventory:lot:list"))],
    owner_id: Optional[int] = Query(None),
    sku_id: Optional[int] = Query(None),
    expiring_days: Optional[int] = Query(
        None, description="只看剩余天数小于该值的批次"
    ),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
):
    cond = []
    if owner_id:
        cond.append(WmsLot.owner_id == owner_id)
    if sku_id:
        cond.append(WmsLot.sku_id == sku_id)
    if expiring_days is not None:
        cond.append(WmsLot.expiry_date.is_not(None))
        cond.append(WmsLot.expiry_date <= date.today() + _days(expiring_days))

    base = select(WmsLot).where(*cond)
    total = (
        await db.execute(select(func.count()).select_from(base.subquery()))
    ).scalar() or 0
    rows = (
        await db.execute(
            base.order_by(WmsLot.expiry_date.is_(None), WmsLot.expiry_date, WmsLot.id)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).scalars().all()

    today = date.today()
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
                    "lot_code": r.lot_code,
                    "production_date": r.production_date.isoformat()
                    if r.production_date
                    else None,
                    "expiry_date": r.expiry_date.isoformat() if r.expiry_date else None,
                    "days_left": (r.expiry_date - today).days if r.expiry_date else None,
                    "status": r.status,
                }
                for r in rows
            ],
        }
    )


def _days(n: int):
    from datetime import timedelta

    return timedelta(days=n)


# ── 手工调整 ─────────────────────────────────────────


class AdjustIn(BaseModel):
    """手工调整。

    ``request_id`` 由调用方生成并在重试时复用，作为幂等键——同一个
    ``request_id`` 重复提交只会记一次账。
    """

    request_id: int = Field(..., description="幂等键，重试时复用同一个值")
    sku_id: int
    lot_id: int = 0
    location_id: int
    stock_status: str = "available"
    delta: Decimal
    reason: Optional[str] = None


@router.post("/adjustments", summary="手工调整库存")
async def create_adjustment(
    payload: AdjustIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permission("wms_inventory:adjust:create"))],
):
    try:
        result = await post_stock(
            db,
            sku_id=payload.sku_id,
            lot_id=payload.lot_id,
            location_id=payload.location_id,
            stock_status=payload.stock_status,
            delta=payload.delta,
            ref_type="adjust",
            ref_id=payload.request_id,
            action="adjust",
            operator_id=user.id,
        )
    except StockError as exc:
        raise ValidationException(str(exc)) from exc

    await db.commit()
    return success_response(
        data={
            "txn_id": result.txn_id,
            "qty_after": str(result.qty_after),
            "applied": result.applied,
        }
    )
