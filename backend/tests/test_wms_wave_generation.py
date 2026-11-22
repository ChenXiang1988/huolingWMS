"""波次生成的可重跑回归：编排出拣货单，进度收敛到 ready。

不验并发性能（那是验收脚本的活），只守住"单子进波次、分配不丢、状态收敛"。
跑法：`pytest tests/test_wms_wave_generation.py`，需要 MySQL 已启动。
"""

import uuid
from decimal import Decimal

from sqlalchemy import text

from src.db import SessionLocal
from src.plugins.builtin.wms_inventory.service import post_stock
from src.plugins.builtin.wms_outbound import models as m
from src.plugins.builtin.wms_outbound.service import create_order
from src.plugins.builtin.wms_outbound.wave_service import (
    cancel_wave,
    create_wave,
    generate_wave,
)

ORDER_COUNT = 30


async def _cleanup(prefix: str, rule_id: int, wave_id: int, location_id: int) -> None:
    async with SessionLocal() as db:
        await db.execute(
            text(
                "DELETE FROM wms_outbound_pick_line WHERE pick_id IN ("
                " SELECT id FROM wms_outbound_pick WHERE order_id IN ("
                "  SELECT id FROM wms_outbound_order WHERE owner_doc_no LIKE :p))"
            ),
            {"p": f"{prefix}%"},
        )
        for sql in (
            "DELETE FROM wms_outbound_pick WHERE order_id IN ("
            " SELECT id FROM wms_outbound_order WHERE owner_doc_no LIKE :p)",
            "DELETE FROM wms_outbound_allocation WHERE order_id IN ("
            " SELECT id FROM wms_outbound_order WHERE owner_doc_no LIKE :p)",
            "DELETE FROM wms_outbound_order_line WHERE order_id IN ("
            " SELECT id FROM wms_outbound_order WHERE owner_doc_no LIKE :p)",
            "DELETE FROM wms_outbound_order WHERE owner_doc_no LIKE :p",
        ):
            await db.execute(text(sql), {"p": f"{prefix}%"})
        await db.execute(text("DELETE FROM wms_outbound_wave WHERE id = :w"), {"w": wave_id})
        await db.execute(
            text("DELETE FROM wms_outbound_wave_rule WHERE id = :r"), {"r": rule_id}
        )
        await db.execute(
            text("DELETE FROM wms_inventory_txn WHERE location_id = :l"),
            {"l": location_id},
        )
        await db.execute(
            text("DELETE FROM wms_inventory_stock WHERE location_id = :l"),
            {"l": location_id},
        )
        await db.commit()


async def test_wave_generation_converges(domain_ctx):
    """整波跑完：total 等于候选单数，processed 全部落账，每单都有拣货单。"""
    prefix = f"PYTEST-{uuid.uuid4().hex[:8].upper()}"
    location_id = domain_ctx["location_id"]
    wave_id = rule_id = 0

    try:
        # 备货：每单 1 件，留一倍余量
        async with SessionLocal() as db:
            await post_stock(
                db,
                sku_id=domain_ctx["sku_id"],
                lot_id=0,
                location_id=location_id,
                stock_status="available",
                delta=Decimal(ORDER_COUNT * 2),
                ref_type="pytest",
                ref_id=int(uuid.uuid4().int % 1_000_000_000),
                action="in",
            )
            await db.commit()

        # 规则承运商过滤，避免把库里历史 confirmed 单卷进来
        async with SessionLocal() as db:
            rule = m.WmsWaveRule(
                code=prefix,
                name="pytest wave rule",
                carrier_code=prefix,
                hot_only=False,
                max_orders=ORDER_COUNT,
            )
            db.add(rule)
            await db.commit()
            rule_id = int(rule.id)

        async with SessionLocal() as db:
            for i in range(ORDER_COUNT):
                await create_order(
                    db,
                    owner_id=domain_ctx["owner_id"],
                    owner_doc_no=f"{prefix}-{i:03d}",
                    lines=[{"sku_id": domain_ctx["sku_id"], "qty": 1, "lot_id": 0}],
                    carrier_code=prefix,
                )
                await db.commit()

        async with SessionLocal() as db:
            wave = await create_wave(db, rule_id=rule_id, operator_id=None)
            wave_id = int(wave.id)
            total = int(wave.total)
            await db.commit()

        assert total == ORDER_COUNT, f"波次只吃到 {total} 单，规则过滤没生效"

        # 直接跑生成协程，不等后台调度，结果确定
        await generate_wave(wave_id)

        async with SessionLocal() as db:
            status, processed, failed = (
                await db.execute(
                    text(
                        "SELECT status, processed, failed FROM wms_outbound_wave "
                        "WHERE id = :w"
                    ),
                    {"w": wave_id},
                )
            ).one()
            picked = (
                await db.execute(
                    text(
                        "SELECT COUNT(DISTINCT o.id) FROM wms_outbound_order o "
                        "JOIN wms_outbound_pick p ON p.order_id = o.id "
                        "WHERE o.owner_doc_no LIKE :p"
                    ),
                    {"p": f"{prefix}%"},
                )
            ).scalar()
            still_confirmed = (
                await db.execute(
                    text(
                        "SELECT COUNT(*) FROM wms_outbound_order "
                        "WHERE owner_doc_no LIKE :p AND status = 'confirmed'"
                    ),
                    {"p": f"{prefix}%"},
                )
            ).scalar()

        assert status == m.WAVE_READY
        assert processed == ORDER_COUNT
        assert failed == 0
        assert picked == ORDER_COUNT, "有订单没生成拣货单"
        assert still_confirmed == 0, "订单应已从 confirmed 推进到分配/拣货"
    finally:
        if wave_id and rule_id:
            await _cleanup(prefix, rule_id, wave_id, location_id)


async def test_cancel_voids_generated_picks(domain_ctx):
    """中止已生成的波次：拣货单作废、分配作废、订单退回待分配，库存数量不动。"""
    prefix = f"PYTEST-{uuid.uuid4().hex[:8].upper()}"
    location_id = domain_ctx["location_id"]
    count = 5
    wave_id = rule_id = 0

    try:
        async with SessionLocal() as db:
            await post_stock(
                db,
                sku_id=domain_ctx["sku_id"],
                lot_id=0,
                location_id=location_id,
                stock_status="available",
                delta=Decimal(count * 2),
                ref_type="pytest",
                ref_id=int(uuid.uuid4().int % 1_000_000_000),
                action="in",
            )
            await db.commit()

        async with SessionLocal() as db:
            rule = m.WmsWaveRule(
                code=prefix,
                name="pytest cancel rule",
                carrier_code=prefix,
                hot_only=False,
                max_orders=count,
            )
            db.add(rule)
            await db.commit()
            rule_id = int(rule.id)

        async with SessionLocal() as db:
            for i in range(count):
                await create_order(
                    db,
                    owner_id=domain_ctx["owner_id"],
                    owner_doc_no=f"{prefix}-{i:03d}",
                    lines=[{"sku_id": domain_ctx["sku_id"], "qty": 1, "lot_id": 0}],
                    carrier_code=prefix,
                )
                await db.commit()

        async with SessionLocal() as db:
            wave = await create_wave(db, rule_id=rule_id, operator_id=None)
            wave_id = int(wave.id)
            await db.commit()

        await generate_wave(wave_id)

        async with SessionLocal() as db:
            before = (
                await db.execute(
                    text(
                        "SELECT COALESCE(SUM(qty),0) FROM wms_inventory_stock "
                        "WHERE location_id = :l"
                    ),
                    {"l": location_id},
                )
            ).scalar()

        async with SessionLocal() as db:
            await cancel_wave(
                db, wave_id=wave_id, reason="pytest 中止", operator_id=None
            )
            await db.commit()

        async with SessionLocal() as db:
            wave_status = (
                await db.execute(
                    text("SELECT status FROM wms_outbound_wave WHERE id = :w"),
                    {"w": wave_id},
                )
            ).scalar()
            pick_states = (
                await db.execute(
                    text(
                        "SELECT DISTINCT status FROM wms_outbound_pick "
                        "WHERE order_id IN ("
                        " SELECT id FROM wms_outbound_order WHERE owner_doc_no LIKE :p)"
                    ),
                    {"p": f"{prefix}%"},
                )
            ).scalars().all()
            alloc_states = (
                await db.execute(
                    text(
                        "SELECT DISTINCT status FROM wms_outbound_allocation "
                        "WHERE order_id IN ("
                        " SELECT id FROM wms_outbound_order WHERE owner_doc_no LIKE :p)"
                    ),
                    {"p": f"{prefix}%"},
                )
            ).scalars().all()
            orders = (
                await db.execute(
                    text(
                        "SELECT status, wave_id FROM wms_outbound_order "
                        "WHERE owner_doc_no LIKE :p"
                    ),
                    {"p": f"{prefix}%"},
                )
            ).all()
            after = (
                await db.execute(
                    text(
                        "SELECT COALESCE(SUM(qty),0) FROM wms_inventory_stock "
                        "WHERE location_id = :l"
                    ),
                    {"l": location_id},
                )
            ).scalar()

        assert wave_status == m.WAVE_CANCELLED
        assert list(pick_states) == ["cancelled"], "已生成的拣货单必须全部作废"
        assert list(alloc_states) == ["void"], "分配记录必须作废"
        assert all(
            row.status == m.ORDER_CONFIRMED and row.wave_id is None for row in orders
        ), "订单应退回待分配并解开波次绑定"
        assert Decimal(str(before)) == Decimal(str(after)), "中止不能改变库存数量"
    finally:
        if wave_id and rule_id:
            await _cleanup(prefix, rule_id, wave_id, location_id)
