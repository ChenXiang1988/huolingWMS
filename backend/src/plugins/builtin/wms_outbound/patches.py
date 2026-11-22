"""出库域的幂等表结构补丁。

P3 建的 ``wms_outbound_order`` 没有 ``wave_id``；P4 才引入波次，不能靠
``create_all`` 加列（它只建新表、不改旧表），所以用与 ``wms_master_data``
同一套的幂等 ALTER：列已存在就跳过，每次启用插件跑一遍是安全的。
"""
from loguru import logger
from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import AsyncEngine

_COLUMNS: dict[str, dict[str, str]] = {
    "wms_outbound_order": {
        "wave_id": "INTEGER NULL",
    },
}


async def apply_patches(engine: AsyncEngine) -> None:
    """补齐缺失的列。"""
    async with engine.begin() as conn:
        for table, columns in _COLUMNS.items():
            existing = await conn.run_sync(
                lambda sync_conn, t=table: {
                    col["name"] for col in inspect(sync_conn).get_columns(t)
                }
            )
            missing = {k: v for k, v in columns.items() if k not in existing}
            for name, ddl in missing.items():
                await conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}"))
                logger.info(f"[wms_outbound] 补列 {table}.{name}")
