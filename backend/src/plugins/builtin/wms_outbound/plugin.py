"""出库插件入口。"""
from fastapi import FastAPI
from loguru import logger
from sqlalchemy import delete, select

from src.core.config import settings
from src.db import Base, SessionLocal, engine
from src.plugins import PluginInterface
from src.plugins.builtin.wms_outbound import models as m
from src.plugins.builtin.wms_outbound.patches import apply_patches
from src.plugins.builtin.wms_outbound.seed import seed_outbound

_TABLES = [
    m.WmsOrder.__table__,
    m.WmsOrderLine.__table__,
    m.WmsAllocation.__table__,
    m.WmsPick.__table__,
    m.WmsPickLine.__table__,
    m.WmsCheck.__table__,
    m.WmsShipment.__table__,
    m.WmsWaveRule.__table__,
    m.WmsWave.__table__,
    m.WmsSortCell.__table__,
    m.WmsSeed.__table__,
]


class WmsOutboundPlugin(PluginInterface):
    name = "wms_outbound"
    display_name = "出库"
    description = "出库订单、FEFO 分配、拣货、复核称重、发运"
    version = "0.1.0"
    author = "货灵"
    dependencies: tuple[str, ...] = ("wms_master_data", "wms_inventory")

    async def install(self) -> None:
        async with engine.begin() as conn:
            await conn.run_sync(
                lambda sync_conn: Base.metadata.create_all(sync_conn, tables=_TABLES)
            )

        # 已有表补列：create_all 不改已存在的表结构
        await apply_patches(engine)

        async with SessionLocal() as db:
            await seed_outbound(db)
            await db.commit()

        # 进程启动时收敛上次卡住的波次（带超时阈值，不会误判正在跑的任务）
        async with SessionLocal() as db:
            from src.plugins.builtin.wms_outbound.wave_service import recover_interrupted
            await recover_interrupted(db)

        logger.info("[wms_outbound] installed — 订单、波次、分配、拣货、发运表就绪")

    async def uninstall(self) -> None:
        from src.models import Menu
        from src.models.rbac import role_menu

        async with SessionLocal() as db:
            stmt = select(Menu.id).where(
                (Menu.permission.like("wms_outbound:%"))
                | (Menu.path.like("/wms-outbound%"))
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

        logger.info("[wms_outbound] uninstalled — 表与菜单已清理")

    def register(self, app: FastAPI) -> None:
        from src.plugins.builtin.wms_outbound.api import router
        from src.plugins.builtin.wms_outbound.open_api import router as open_router
        from src.plugins.builtin.wms_outbound.wave_api import router as wave_router

        app.include_router(router, prefix=settings.API_PREFIX)
        app.include_router(wave_router, prefix=settings.API_PREFIX)
        app.include_router(open_router, prefix=f"{settings.API_PREFIX}/open/v1")
        logger.info("[wms_outbound] registered — 后台、波次与开放接口均已挂载")
