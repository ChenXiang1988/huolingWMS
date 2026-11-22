"""WMS 业务域的测试夹具。

库存与波次的契约依赖真实 MySQL（行锁、唯一键、`FOR UPDATE`），SQLite 测不出来。
每个用例独占一个临时库位，跑完把自己写的行删干净，可反复执行。
"""

import uuid

import pytest
import pytest_asyncio
from sqlalchemy import text

from src.db import SessionLocal


@pytest_asyncio.fixture(autouse=True)
async def _release_pool():
    """每个用例结束后断开连接池。

    pytest-asyncio 给每个用例新建事件循环，而 engine 的连接池跨循环复用连接，
    归还时会持有已关闭的 loop（aiomysql 的 transport 报 'NoneType' has no 'send'）。
    用完即弃比让连接跨循环存活更省事。
    """
    yield
    from src.db import engine

    await engine.dispose()


@pytest_asyncio.fixture
async def domain_ctx():
    """临时库位 + 一个已建档商品。

    商品档案来自库里现成数据：库存记账要从 `wms_master_data_sku` 反查货主，
    凭空造一个 SKU 会把主数据域的字段约束也拖进测试。库里没有商品时明确跳过，
    而不是让用例在 None 上崩掉。
    """
    async with SessionLocal() as db:
        sku = (
            await db.execute(
                text("SELECT id, owner_id FROM wms_master_data_sku ORDER BY id LIMIT 1")
            )
        ).first()
    if sku is None:
        pytest.skip("库里没有商品档案，先初始化主数据再跑本测试")

    code = f"PYTEST-{uuid.uuid4().hex[:10].upper()}"
    async with SessionLocal() as db:
        await db.execute(
            text(
                "INSERT INTO wms_master_data_location "
                "(zone_id, code, location_type, temp_zone, floor_no, capacity, status) "
                "VALUES (1, :code, 'storage', 'ambient', 1, 0, 1)"
            ),
            {"code": code},
        )
        await db.commit()
        location_id = (
            await db.execute(
                text("SELECT id FROM wms_master_data_location WHERE code = :c"),
                {"c": code},
            )
        ).scalar()

    yield {
        "sku_id": int(sku.id),
        "owner_id": int(sku.owner_id),
        "location_id": int(location_id),
    }

    async with SessionLocal() as db:
        for sql in (
            "DELETE FROM wms_inventory_txn WHERE location_id = :l",
            "DELETE FROM wms_inventory_stock WHERE location_id = :l",
            "DELETE FROM wms_master_data_location WHERE id = :l",
        ):
            await db.execute(text(sql), {"l": location_id})
        await db.commit()
