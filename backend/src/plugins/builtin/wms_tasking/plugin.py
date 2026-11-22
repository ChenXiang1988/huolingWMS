"""任务插件入口。"""
from fastapi import FastAPI
from loguru import logger
from sqlalchemy import delete, select

from src.core.config import settings
from src.db import Base, SessionLocal, engine
from src.plugins import PluginInterface
from src.plugins.builtin.wms_tasking import models as m
from src.plugins.builtin.wms_tasking.seed import seed_tasking

_TABLES = [m.WmsTask.__table__]


class WmsTaskingPlugin(PluginInterface):
    name = "wms_tasking"
    display_name = "任务"
    description = "作业任务生成、领取、提交与超时回收"
    version = "0.1.0"
    author = "货灵"
    dependencies: tuple[str, ...] = (
        "wms_master_data", "wms_inventory", "wms_internal_ops", "wms_outbound",
    )

    async def install(self) -> None:
        async with engine.begin() as conn:
            await conn.run_sync(
                lambda sync_conn: Base.metadata.create_all(sync_conn, tables=_TABLES)
            )
        async with SessionLocal() as db:
            await seed_tasking(db)
            await db.commit()
        logger.info("[wms_tasking] installed — 任务表与菜单就绪")

    async def uninstall(self) -> None:
        from src.models import Menu
        from src.models.rbac import role_menu

        async with SessionLocal() as db:
            ids = list((await db.execute(
                select(Menu.id).where(
                    (Menu.permission.like("wms_tasking:%"))
                    | (Menu.path.like("/wms-tasking%"))
                )
            )).scalars().all())
            if ids:
                await db.execute(delete(role_menu).where(role_menu.c.menu_id.in_(ids)))
                await db.execute(delete(Menu).where(Menu.id.in_(ids)))
                await db.commit()
        async with engine.begin() as conn:
            await conn.run_sync(
                lambda sync_conn: Base.metadata.drop_all(sync_conn, tables=_TABLES)
            )
        logger.info("[wms_tasking] uninstalled — 表与菜单已清理")

    def register(self, app: FastAPI) -> None:
        from src.plugins.builtin.wms_tasking.api import router
        app.include_router(router, prefix=settings.API_PREFIX)
        logger.info("[wms_tasking] registered — routes mounted")
