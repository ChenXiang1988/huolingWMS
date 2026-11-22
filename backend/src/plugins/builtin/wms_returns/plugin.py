"""逆向插件入口。P2 只承载破损处置。"""
from fastapi import FastAPI
from loguru import logger
from sqlalchemy import delete, select

from src.core.config import settings
from src.db import Base, SessionLocal, engine
from src.plugins import PluginInterface
from src.plugins.builtin.wms_returns import models as m
from src.plugins.builtin.wms_returns.seed import seed_returns

_TABLES = [
    m.WmsDisposal.__table__,
    m.WmsReturn.__table__,
    m.WmsReturnLine.__table__,
]


class WmsReturnsPlugin(PluginInterface):
    name = "wms_returns"
    display_name = "逆向"
    description = "破损处置（P2 起）、退货单（P6 起）"
    version = "0.1.0"
    author = "货灵"
    dependencies: tuple[str, ...] = ("wms_master_data", "wms_inventory")

    async def install(self) -> None:
        async with engine.begin() as conn:
            await conn.run_sync(
                lambda sync_conn: Base.metadata.create_all(sync_conn, tables=_TABLES)
            )

        async with SessionLocal() as db:
            await seed_returns(db)
            await db.commit()

        logger.info("[wms_returns] installed — 破损处置就绪")

    async def uninstall(self) -> None:
        from src.models import Menu
        from src.models.rbac import role_menu

        async with SessionLocal() as db:
            stmt = select(Menu.id).where(
                (Menu.permission.like("wms_returns:%"))
                | (Menu.path.like("/wms-returns%"))
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

        logger.info("[wms_returns] uninstalled — 表与菜单已清理")

    def register(self, app: FastAPI) -> None:
        from src.plugins.builtin.wms_returns.api import router

        app.include_router(router, prefix=settings.API_PREFIX)
        logger.info("[wms_returns] registered — routes mounted")
