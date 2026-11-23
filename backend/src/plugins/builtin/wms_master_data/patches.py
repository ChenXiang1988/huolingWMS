"""幂等表结构补丁。

基座用 ``create_all`` 建表，它只建不存在的表、不改已有表的结构。P0 建的
``wms_master_data_owner`` 只有四个业务字段，P1 要补上联系方式、主账号、账期等，
只能走 ALTER。

写法要求：重复执行不报错（列已存在就跳过），这样每次启用插件都跑一遍是安全的。
"""
from loguru import logger
from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import AsyncEngine

# 表名 → {列名: 建列 DDL 片段}。片段只写类型与默认值，MySQL 与 SQLite 都能接受。
_COLUMNS: dict[str, dict[str, str]] = {
    "wms_master_data_owner": {
        "contact": "VARCHAR(64)",
        "phone": "VARCHAR(32)",
        "address": "VARCHAR(255)",
        "primary_user_id": "INTEGER",
        "settle_period": "VARCHAR(32)",
        "remark": "VARCHAR(255)",
    },
    "wms_master_data_team": {
        "floor_no": "INTEGER",
        "dispatch_limit_default": "INTEGER",
    },
    "wms_master_data_staff": {
        "role": "VARCHAR(32)",
        "left_pending_at": "DATETIME",
        "left_at": "DATETIME",
        "quality_cert": "INTEGER DEFAULT 0",
        "quality_team": "VARCHAR(64)",
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
                logger.info(f"[wms_master_data] 补列 {table}.{name}")
