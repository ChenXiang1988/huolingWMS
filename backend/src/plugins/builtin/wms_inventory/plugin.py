"""库存插件入口。

这个域承载全系统唯一能写库存数量的契约（``service.post_stock`` 与
``service.transfer_status``），以及批次、库存台账与流水三张表。

依赖主数据：库存行要带 ``owner_id``，而货主归属只由商品档案派生。
"""
from fastapi import FastAPI
from loguru import logger
from sqlalchemy import delete, select

from src.core.config import settings
from src.db import Base, SessionLocal, engine
from src.plugins import PluginInterface
from src.plugins.builtin.wms_inventory import models as m
from src.plugins.builtin.wms_inventory.seed import seed_inventory

_TABLES = [
    m.WmsLot.__table__,
    m.WmsStock.__table__,
    m.WmsTxn.__table__,
]


class WmsInventoryPlugin(PluginInterface):
    name = "wms_inventory"
    display_name = "库存"
    description = "库存台账、库存流水、批次与效期"
    version = "0.1.0"
    author = "货灵"
    dependencies: tuple[str, ...] = ("wms_master_data",)

    async def install(self) -> None:
        """建三张表并登记菜单。重复执行不产生重复数据。"""
        async with engine.begin() as conn:
            await conn.run_sync(
                lambda sync_conn: Base.metadata.create_all(sync_conn, tables=_TABLES)
            )

        async with SessionLocal() as db:
            await seed_inventory(db)
            await db.commit()

        logger.info("[wms_inventory] installed — 批次、台账、流水就绪")

    async def uninstall(self) -> None:
        """删表并清理本插件拥有的菜单。"""
        from src.models import Menu
        from src.models.rbac import role_menu

        async with SessionLocal() as db:
            stmt = select(Menu.id).where(
                (Menu.permission.like("wms_inventory:%"))
                | (Menu.path.like("/wms-inventory%"))
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

        logger.info("[wms_inventory] uninstalled — 表与菜单已清理")

    def register(self, app: FastAPI) -> None:
        """挂载库存域路由（后台 + 货主门户只读视图）。"""
        from src.plugins.builtin.wms_inventory.api import router
        from src.plugins.builtin.wms_inventory.portal_api import router as portal_router

        app.include_router(router, prefix=settings.API_PREFIX)
        app.include_router(portal_router, prefix=settings.API_PREFIX)
        logger.info("[wms_inventory] registered — routes mounted")
