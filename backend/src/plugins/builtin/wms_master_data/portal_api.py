"""货主门户上下文与自助建商品。"""
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.deps import get_current_user, require_permission
from src.core.exceptions import ValidationException, success_response
from src.db import get_db
from src.models import User
from src.plugins.builtin.wms_master_data import models as m
from src.plugins.builtin.wms_master_data.api import SkuBaseIn
from src.plugins.builtin.wms_master_data.portal import owner_of_user
from src.plugins.builtin.wms_master_data.service import next_code

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


@router.post("/portal/skus", summary="货主门户创建商品档案")
async def portal_create_sku(
    payload: SkuBaseIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permission("wms_master_data:sku:create"))],
):
    """货主只提交「这是什么货」，仓库侧「这货怎么存」字段不接受此入口写入。

    SkuBaseIn 与后台 SkuStorageIn 字段不重叠，构造请求多带的存储字段会被
    Pydantic 默认忽略，落到库里的是模型默认值。owner_id 取会话绑定货主。
    只读子账号无 sku:create 权限，require_permission 直接拒绝。
    """
    ctx = await owner_of_user(db, user.id)
    row = m.WmsSku(
        owner_id=ctx.owner_id,
        code=await next_code(db, "SKU", "", 6),
        **payload.model_dump(),
        status=1,
    )
    db.add(row)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise ValidationException(
            f"该货主下货主编码 {payload.owner_sku_code} 已存在"
        ) from exc
    return success_response(data={"id": row.id, "code": row.code, "owner_id": ctx.owner_id})


# ── 账单查询契约 ──────────────────────────────────────
# 当前没有 wms_billing 插件与费用表，账单尚无数据来源。先把货主可见的只读契约
# 固定下来：接口存在、按会话 owner_id 限定、不提供写操作。计费域落地后替换
# 数据来源即可，前端与权限不必改。


@router.get("/portal/bills", summary="货主门户账单列表")
async def portal_list_bills(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    period: str | None = None,
):
    await owner_of_user(db, user.id)
    return success_response(data={"items": [], "period": period})


@router.get("/portal/bills/{bill_id}/items", summary="货主门户账单明细")
async def portal_bill_items(
    bill_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    await owner_of_user(db, user.id)
    return success_response(data={"bill_id": bill_id, "items": []})
