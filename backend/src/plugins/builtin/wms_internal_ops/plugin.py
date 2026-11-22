"""库内作业插件入口。P4 只承载补货。"""
from fastapi import FastAPI
from loguru import logger
from sqlalchemy import delete, select

from src.core.config import settings
from src.db import Base, SessionLocal, engine
from src.plugins import PluginInterface
from src.plugins.builtin.wms_internal_ops import models as m
from src.plugins.builtin.wms_internal_ops.seed import seed_internal_ops

_TABLES = [
    m.WmsReplenish.__table__,
    m.WmsTransfer.__table__,
    m.WmsCount.__table__,
    m.WmsCountLine.__table__,
    m.WmsSample.__table__,
]


class WmsInternalOpsPlugin(PluginInterface):
    name = "wms_internal_ops"
    display_name = "库内作业"
    description = "补货（P4 起）、移库、盘点、留样台账（P5 起）"
    version = "0.1.0"
    author = "货灵"
    dependencies: tuple[str, ...] = ("wms_master_data", "wms_inventory", "wms_outbound")

    async def install(self) -> None:
        async with engine.begin() as conn:
            await conn.run_sync(
                lambda sync_conn: Base.metadata.create_all(sync_conn, tables=_TABLES)
            )

        async with SessionLocal() as db:
            await seed_internal_ops(db)
            await db.commit()

        # P5：回填 P2 时期已完成但未建台账的历史留样行。唯一键挡重复，
        # 每次启动跑一遍是安全的。
        async with SessionLocal() as db:
            from src.plugins.builtin.wms_internal_ops.ops_service import backfill_samples
            n = await backfill_samples(db)
            await db.commit()
            if n:
                logger.info(f"[wms_internal_ops] backfilled {n} sample records")

        # 临期批次冻结：进程内 asyncio 定时，启动立即跑一次兜底
        from src.plugins.builtin.wms_internal_ops.ops_service import start_freeze_scheduler
        start_freeze_scheduler()

        logger.info("[wms_internal_ops] installed — 补货/移库/盘点/留样表与菜单就绪")

    async def uninstall(self) -> None:
        from src.models import Menu
        from src.models.rbac import role_menu

        async with SessionLocal() as db:
            stmt = select(Menu.id).where(
                (Menu.permission.like("wms_internal_ops:%"))
                | (Menu.path.like("/wms-internal-ops%"))
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

        logger.info("[wms_internal_ops] uninstalled — 表与菜单已清理")

    def register(self, app: FastAPI) -> None:
        from src.plugins.builtin.wms_internal_ops.api import router

        app.include_router(router, prefix=settings.API_PREFIX)
        logger.info("[wms_internal_ops] registered — routes mounted")
