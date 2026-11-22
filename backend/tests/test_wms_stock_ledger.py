"""库存记账的四道闸：幂等、非负、状态守恒、流水只追加。

对应 `wms/stock-ledger` 规格里"数量只有库存域能写、过账按来源单据幂等"的约定。
跑法：`pytest tests/test_wms_stock_ledger.py`，需要 MySQL 已启动。
"""

import uuid
from decimal import Decimal

import pytest
from sqlalchemy import text

from src.db import SessionLocal
from src.plugins.builtin.wms_inventory.service import StockError, post_stock, transfer_status


def _ref_id() -> int:
    return int(uuid.uuid4().int % 1_000_000_000)


async def _qty(location_id: int, status: str) -> Decimal:
    async with SessionLocal() as db:
        value = (
            await db.execute(
                text(
                    "SELECT qty FROM wms_inventory_stock "
                    "WHERE location_id = :l AND stock_status = :s"
                ),
                {"l": location_id, "s": status},
            )
        ).scalar()
    return Decimal(str(value)) if value is not None else Decimal("0")


async def test_post_stock_is_idempotent(domain_ctx):
    """同一来源单据重复过账只记一次账，数量不叠加。"""
    ref_id = _ref_id()
    kwargs = {
        "sku_id": domain_ctx["sku_id"],
        "lot_id": 0,
        "location_id": domain_ctx["location_id"],
        "stock_status": "available",
        "delta": Decimal("10"),
        "ref_type": "pytest",
        "ref_id": ref_id,
        "action": "in",
    }

    async with SessionLocal() as db:
        first = await post_stock(db, **kwargs)
        await db.commit()
    assert first.applied is True
    assert first.qty_after == Decimal("10")

    async with SessionLocal() as db:
        second = await post_stock(db, **kwargs)
        await db.commit()
    assert second.applied is False, "同一来源单据重复过账必须判为幂等命中"
    assert second.qty_after == Decimal("10")

    assert await _qty(domain_ctx["location_id"], "available") == Decimal("10")
    async with SessionLocal() as db:
        rows = (
            await db.execute(
                text(
                    "SELECT COUNT(*) FROM wms_inventory_txn "
                    "WHERE location_id = :l AND ref_id = :r"
                ),
                {"l": domain_ctx["location_id"], "r": ref_id},
            )
        ).scalar()
    assert rows == 1, "幂等命中不应再追加流水"


async def test_post_stock_rejects_negative(domain_ctx):
    """扣到负数直接拒绝，不留半条账。"""
    async with SessionLocal() as db:
        with pytest.raises(StockError):
            await post_stock(
                db,
                sku_id=domain_ctx["sku_id"],
                lot_id=0,
                location_id=domain_ctx["location_id"],
                stock_status="available",
                delta=Decimal("-5"),
                ref_type="pytest",
                ref_id=_ref_id(),
                action="out",
            )
        await db.rollback()

    assert await _qty(domain_ctx["location_id"], "available") == Decimal("0")


async def test_transfer_status_keeps_total(domain_ctx):
    """available → frozen 是状态转换，两者之和必须等于转换前的可用量。"""
    async with SessionLocal() as db:
        await post_stock(
            db,
            sku_id=domain_ctx["sku_id"],
            lot_id=0,
            location_id=domain_ctx["location_id"],
            stock_status="available",
            delta=Decimal("100"),
            ref_type="pytest",
            ref_id=_ref_id(),
            action="in",
        )
        await db.commit()

    async with SessionLocal() as db:
        moved = await transfer_status(
            db,
            sku_id=domain_ctx["sku_id"],
            lot_id=0,
            location_id=domain_ctx["location_id"],
            from_status="available",
            to_status="frozen",
            qty=Decimal("30"),
            ref_type="pytest",
            ref_id=_ref_id(),
            action="freeze",
        )
        await db.commit()
    assert moved.applied is True

    available = await _qty(domain_ctx["location_id"], "available")
    frozen = await _qty(domain_ctx["location_id"], "frozen")
    assert available == Decimal("70")
    assert frozen == Decimal("30")
    assert available + frozen == Decimal("100"), "状态转换不能改变总量"

    async with SessionLocal() as db:
        delta = (
            await db.execute(
                text(
                    "SELECT delta FROM wms_inventory_txn "
                    "WHERE location_id = :l AND action = 'freeze'"
                ),
                {"l": domain_ctx["location_id"]},
            )
        ).scalar()
    assert Decimal(str(delta)) == Decimal("0"), "状态转换的数量变动记为 0，由前后状态承载"


async def test_transfer_status_rejects_overdraw(domain_ctx):
    """转出量超过源状态持有量时拒绝，不做部分转换。"""
    async with SessionLocal() as db:
        await post_stock(
            db,
            sku_id=domain_ctx["sku_id"],
            lot_id=0,
            location_id=domain_ctx["location_id"],
            stock_status="available",
            delta=Decimal("10"),
            ref_type="pytest",
            ref_id=_ref_id(),
            action="in",
        )
        await db.commit()

    async with SessionLocal() as db:
        with pytest.raises(StockError):
            await transfer_status(
                db,
                sku_id=domain_ctx["sku_id"],
                lot_id=0,
                location_id=domain_ctx["location_id"],
                from_status="available",
                to_status="frozen",
                qty=Decimal("11"),
                ref_type="pytest",
                ref_id=_ref_id(),
                action="freeze",
            )
        await db.rollback()

    assert await _qty(domain_ctx["location_id"], "available") == Decimal("10")
    assert await _qty(domain_ctx["location_id"], "frozen") == Decimal("0")
