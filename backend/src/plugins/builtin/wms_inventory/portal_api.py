"""货主门户库存查询：只读，owner_id 由会话注入。

后台库存路由需要仓库侧权限，货主角色调不了；这里给一份同构的只读视图，
查询条件与后台一致，但 owner_id 强制取会话绑定货主，请求体里改不了。
"""
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.deps import get_current_user
from src.core.exceptions import success_response
from src.db import get_db
from src.models import User
from src.plugins.builtin.wms_inventory.models import WmsStock, WmsTxn
from src.plugins.builtin.wms_master_data.portal import owner_of_user

router = APIRouter(prefix="/wms-inventory", tags=["货主门户库存"])


@router.get("/portal/stocks", summary="货主门户库存列表")
async def portal_list_stocks(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    sku_id: Optional[int] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
):
    ctx = await owner_of_user(db, user.id)
    cond = [WmsStock.qty != 0, WmsStock.owner_id == ctx.owner_id]
    if sku_id:
        cond.append(WmsStock.sku_id == sku_id)

    grouped = (
        select(
            WmsStock.sku_id,
            WmsStock.stock_status,
            func.sum(WmsStock.qty).label("qty"),
            func.count(func.distinct(WmsStock.lot_id)).label("lot_count"),
        )
        .where(*cond)
        .group_by(WmsStock.sku_id, WmsStock.stock_status)
    )
    total = (await db.execute(select(func.count()).select_from(grouped.subquery()))).scalar() or 0
    rows = (
        await db.execute(
            grouped.order_by(WmsStock.sku_id).offset((page - 1) * page_size).limit(page_size)
        )
    ).all()
    return success_response(data={
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [
            {
                "sku_id": r.sku_id,
                "stock_status": r.stock_status,
                "qty": str(r.qty),
                "lot_count": r.lot_count,
            }
            for r in rows
        ],
    })


@router.get("/portal/stocks/detail", summary="货主门户库存明细")
async def portal_stock_detail(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    sku_id: int = Query(...),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
):
    ctx = await owner_of_user(db, user.id)
    cond = [
        WmsStock.sku_id == sku_id,
        WmsStock.owner_id == ctx.owner_id,
        WmsStock.qty != 0,
    ]
    base = select(WmsStock).where(*cond)
    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar() or 0
    rows = (
        await db.execute(
            base.order_by(WmsStock.lot_id, WmsStock.location_id)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).scalars().all()
    return success_response(data={
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [
            {
                "lot_id": r.lot_id,
                "location_id": r.location_id,
                "stock_status": r.stock_status,
                "qty": str(r.qty),
            }
            for r in rows
        ],
    })


@router.get("/portal/txns", summary="货主门户库存流水")
async def portal_list_txns(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    sku_id: Optional[int] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
):
    ctx = await owner_of_user(db, user.id)
    cond = [WmsTxn.owner_id == ctx.owner_id]
    if sku_id:
        cond.append(WmsTxn.sku_id == sku_id)

    base = select(WmsTxn).where(*cond)
    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar() or 0
    rows = (
        await db.execute(
            base.order_by(WmsTxn.id.desc()).offset((page - 1) * page_size).limit(page_size)
        )
    ).scalars().all()
    return success_response(data={
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [
            {
                "id": r.id,
                "ref_type": r.ref_type,
                "ref_id": r.ref_id,
                "action": r.action,
                "sku_id": r.sku_id,
                "lot_id": r.lot_id,
                "location_id": r.location_id,
                "stock_status": r.stock_status,
                "delta": str(r.delta),
                "qty_after": str(r.qty_after),
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ],
    })
