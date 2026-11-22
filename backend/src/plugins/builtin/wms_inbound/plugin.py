"""入库插件入口。

依赖主数据（商品归属与批次开关）与库存（过账契约）。P2 起这个域第一次
真实调用 ``post_stock``——收货确认时把好货与破损分别入账。
"""
from fastapi import FastAPI
from loguru import logger
from sqlalchemy import delete, select

from src.core.config import settings
from src.db import Base, SessionLocal, engine
from src.plugins import PluginInterface
from src.plugins.builtin.wms_inbound import models as m
from src.plugins.builtin.wms_inbound.seed import seed_inbound

_TABLES = [
    m.WmsAsn.__table__,
    m.WmsAsnLine.__table__,
    m.WmsServiceOrder.__table__,
    m.WmsReceipt.__table__,
    m.WmsReceiptLine.__table__,
    m.WmsReceiptLot.__table__,
    m.WmsPutaway.__table__,
    m.WmsPutawayLine.__table__,
]


class WmsInboundPlugin(PluginInterface):
    name = "wms_inbound"
    display_name = "入库"
    description = "入库预报、服务订单、收货、上架"
    version = "0.1.0"
    author = "货灵"
    dependencies: tuple[str, ...] = ("wms_master_data", "wms_inventory")

    async def install(self) -> None:
        async with engine.begin() as conn:
            await conn.run_sync(
                lambda sync_conn: Base.metadata.create_all(sync_conn, tables=_TABLES)
            )

        async with SessionLocal() as db:
            await seed_inbound(db)
            await db.commit()

        logger.info("[wms_inbound] installed — 预报、收货、上架表就绪")

    async def uninstall(self) -> None:
        from src.models import Menu
        from src.models.rbac import role_menu

        async with SessionLocal() as db:
            stmt = select(Menu.id).where(
                (Menu.permission.like("wms_inbound:%"))
                | (Menu.path.like("/wms-inbound%"))
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

        logger.info("[wms_inbound] uninstalled — 表与菜单已清理")

    def register(self, app: FastAPI) -> None:
        from src.plugins.builtin.wms_inbound.api import router
        from src.plugins.builtin.wms_inbound.open_api import router as open_router

        app.include_router(router, prefix=settings.API_PREFIX)
        # 货主开放接口单独前缀：/api/v1/open/v1/asns
        app.include_router(open_router, prefix=f"{settings.API_PREFIX}/open/v1")
        logger.info("[wms_inbound] registered — 后台与开放接口均已挂载")
