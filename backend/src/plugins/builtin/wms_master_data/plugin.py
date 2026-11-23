"""主数据插件入口。

P0 阶段这个域只承载两件事：账号与货主的绑定关系、登录落点判定。
业务主数据（仓库、库位、商品、条码）在 P1 填进来。
"""
from typing import Any

from fastapi import FastAPI
from loguru import logger
from sqlalchemy import delete, select

from src.core.config import settings
from src.db import Base, SessionLocal, engine
from src.plugins import PluginInterface
from src.plugins.builtin.wms_master_data import models as m
from src.plugins.builtin.wms_master_data.patches import apply_patches
from src.plugins.builtin.wms_master_data.seed import seed_master_data

_TABLES = [
    m.WmsOwner.__table__,
    m.WmsUserOwner.__table__,
    m.WmsWarehouse.__table__,
    m.WmsZone.__table__,
    m.WmsUnit.__table__,
    m.WmsLocation.__table__,
    m.WmsSku.__table__,
    m.WmsBarcode.__table__,
    m.WmsPartner.__table__,
    m.WmsApiKey.__table__,
    m.WmsSequence.__table__,
    m.WmsTeam.__table__,
    m.WmsStaff.__table__,
]


class WmsMasterDataPlugin(PluginInterface):
    name = "wms_master_data"
    display_name = "主数据"
    description = "仓库配置、货主、库位、商品、合作方、API 凭证与打印模板"
    version = "0.1.0"
    author = "货灵"
    dependencies: tuple[str, ...] = ()

    async def install(self) -> None:
        """建表 + 建菜单与角色。重复执行不产生重复数据。"""
        async with engine.begin() as conn:
            await conn.run_sync(
                lambda sync_conn: Base.metadata.create_all(sync_conn, tables=_TABLES)
            )

        # 已有表补列：create_all 不改已存在的表结构
        await apply_patches(engine)

        async with SessionLocal() as db:
            await seed_master_data(db)
            await db.commit()

        logger.info("[wms_master_data] installed — 表、菜单、角色就绪")

    async def uninstall(self) -> None:
        """删表并清理本插件拥有的菜单。"""
        from src.models import Menu
        from src.models.rbac import role_menu

        async with SessionLocal() as db:
            stmt = select(Menu.id).where(
                (Menu.permission.like("wms_master_data:%"))
                | (Menu.path.like("/wms-master-data%"))
                | (Menu.path == "/owner")
            )
            menu_ids = list((await db.execute(stmt)).scalars().all())
            if menu_ids:
                await db.execute(
                    delete(role_menu).where(role_menu.c.menu_id.in_(menu_ids))
                )
                await db.execute(delete(Menu).where(Menu.id.in_(menu_ids)))
                await db.commit()

        async with engine.begin() as conn:
            await conn.run_sync(
                lambda sync_conn: Base.metadata.drop_all(sync_conn, tables=_TABLES)
            )

        logger.info("[wms_master_data] uninstalled — 表与菜单已清理")

    def register(self, app: FastAPI) -> None:
        """挂载主数据域路由。"""
        from src.plugins.builtin.wms_master_data.api import router
        from src.plugins.builtin.wms_master_data.portal_api import router as portal_router

        app.include_router(router, prefix=settings.API_PREFIX)
        app.include_router(portal_router, prefix=settings.API_PREFIX)
        logger.info("[wms_master_data] registered — routes mounted")

    async def before_login(self, payload: dict[str, Any]) -> None:
        """挡住两类不该从后台登录的账号。

        1. 绑定了货主的账号：它们属于货主门户，后台登录页直接拒，
           而不是先发 token 再由前端送回去。
        2. 货主已停用或绑定已停用：基座只校验 ``sys_user.status``，
           不知道货主侧的状态。
        """
        from src.core.exceptions import AuthException
        from src.models import User
        from src.plugins.builtin.wms_master_data.models import WmsOwner, WmsUserOwner

        username = payload.get("username")
        if not username:
            return

        async with SessionLocal() as db:
            user = (
                await db.execute(select(User).where(User.username == username))
            ).scalars().first()
            if user is None:
                return
            binding = (
                await db.execute(
                    select(WmsUserOwner).where(WmsUserOwner.user_id == user.id)
                )
            ).scalars().first()
            if binding is None:
                return
            if binding.status != 1:
                raise AuthException("该账号所属货主已停用")
            owner = (
                await db.execute(
                    select(WmsOwner).where(WmsOwner.id == binding.owner_id)
                )
            ).scalars().first()
            if owner is not None and owner.status != 1:
                raise AuthException("该账号所属货主已停用")
            raise AuthException("该账号属于货主方，请从货主门户登录")
