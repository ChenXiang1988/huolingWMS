"""货主门户上下文。"""
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.deps import get_current_user
from src.core.exceptions import success_response
from src.db import get_db
from src.models import User
from src.plugins.builtin.wms_master_data.portal import owner_of_user

router = APIRouter(prefix="/wms-master-data", tags=["货主门户"])


@router.get("/portal/context", summary="当前货主与建单权限")
async def portal_context(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    ctx = await owner_of_user(db, user.id)
    return success_response(data={
        "owner_id": ctx.owner_id,
        "owner_name": ctx.owner_name,
        "sync_enabled": ctx.sync_enabled,
        "can_create": ctx.can_create,
    })


@router.get("/portal/skus", summary="货主门户可建单的商品")
async def portal_skus(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    """只列出本货主的商品，不暴露别的货主档案。

    门户建单要用商品下拉，但后台商品列表有仓库侧权限，货主角色调不了；
    这里给一份最小字段的只读清单。
    """
    from sqlalchemy import text

    ctx = await owner_of_user(db, user.id)
    rows = (
        await db.execute(
            text(
                "SELECT id, code, owner_sku_code, name, lot_required "
                "FROM wms_master_data_sku "
                "WHERE owner_id = :owner AND status = 1 ORDER BY id"
            ),
            {"owner": ctx.owner_id},
        )
    ).all()
    return success_response(data=[
        {
            "id": r.id,
            "code": r.code,
            "owner_sku_code": r.owner_sku_code,
            "name": r.name,
            "lot_required": bool(r.lot_required),
        }
        for r in rows
    ])
