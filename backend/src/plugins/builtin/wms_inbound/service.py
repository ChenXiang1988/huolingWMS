"""收货与上架：入库域唯一会动库存的两条链路。

收货确认时一次性过账（好货进可发、破损进破损），上架只是把货从暂存位挪到存储位。
不等到上架才入账——货在月台上账面就得认它，否则丢了系统完全不知道。
"""
from datetime import datetime
from decimal import Decimal, ROUND_CEILING
from typing import Optional, Sequence

from sqlalchemy import and_, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.plugins.builtin.wms_inbound import models as m
from src.plugins.builtin.wms_inventory.models import (
    STOCK_AVAILABLE,
    STOCK_DAMAGED,
)
from src.plugins.builtin.wms_inventory.service import (
    StockError,
    ensure_lot,
    post_stock,
)
from src.plugins.builtin.wms_master_data.service import next_code
from src.plugins.builtin.wms_returns.models import WmsDisposal


# ── 读商品与库位（不 import 主数据模型，只取需要的列）──────────


async def _sku_info(db: AsyncSession, sku_ids: Sequence[int]) -> dict[int, dict]:
    if not sku_ids:
        return {}
    from sqlalchemy import bindparam

    # IN 参数必须声明 expanding，否则驱动会把 list 当成单个参数值
    stmt = text(
        "SELECT id, owner_id, lot_required, temp_requirement, default_zone_id "
        "FROM wms_master_data_sku WHERE id IN :ids"
    ).bindparams(bindparam("ids", expanding=True))
    rows = (await db.execute(stmt, {"ids": list(sku_ids)})).all()
    return {
        r.id: {
            "owner_id": r.owner_id,
            "lot_required": bool(r.lot_required),
            "temp_requirement": r.temp_requirement or "ambient",
            "default_zone_id": r.default_zone_id,
        }
        for r in rows
    }


async def _pick_location(
    db: AsyncSession,
    *,
    sku: dict,
    sample: bool,
) -> tuple[int, bool]:
    """选目标库位，返回 ``(location_id, 温区不匹配)``。

    优先级：同温区 → 放宽温区（记 mismatch）→ 报错。
    专属库位与同商品就近合并留给 P4 的选位策略，P2 只保证落得进存储区。
    """
    location_type = "sample" if sample else "storage"
    if sample:
        stmt = text(
            "SELECT id FROM wms_master_data_location "
            "WHERE location_type='sample' AND status=1 ORDER BY id LIMIT 1"
        )
        loc = (await db.execute(stmt)).scalar()
        if loc is None:
            raise StockError("没有留样库位，请先建一个 location_type=sample 的库位")
        return int(loc), False

    temp = sku["temp_requirement"]
    matches = (
        await db.execute(
            text(
                "SELECT id FROM wms_master_data_location "
                "WHERE location_type='storage' AND status=1 AND temp_zone=:temp "
                "ORDER BY id LIMIT 1"
            ),
            {"temp": temp},
        )
    ).scalar()
    if matches is not None:
        return int(matches), False

    fallback = (
        await db.execute(
            text(
                "SELECT id FROM wms_master_data_location "
                "WHERE location_type='storage' AND status=1 ORDER BY id LIMIT 1"
            )
        )
    ).scalar()
    if fallback is None:
        raise StockError("没有可用存储库位，请先建 location_type=storage 的库位")
    return int(fallback), True


async def _receiving_location(db: AsyncSession) -> int:
    loc = (
        await db.execute(
            text(
                "SELECT id FROM wms_master_data_location "
                "WHERE location_type='receiving' AND status=1 ORDER BY id LIMIT 1"
            )
        )
    ).scalar()
    if loc is None:
        raise StockError("没有收货暂存库位，请先建一个 location_type=receiving 的库位")
    return int(loc)


# ── 建预报（后台与开放接口共用）─────────────────────────


async def create_asn(
    db: AsyncSession,
    *,
    owner_id: int,
    owner_doc_no: str,
    lines: list[dict],
    source: str = "manual",
    supplier_id: Optional[int] = None,
    expect_arrive_at=None,
    remark: Optional[str] = None,
    confirm: bool = True,
    created_by: Optional[int] = None,
) -> m.WmsAsn:
    """建预报。后台与开放接口都走这里，校验只有一处。

    ``owner_doc_no`` 与货主一起唯一——上游重复推送同一张单时应当被识别为重复，
    而不是建出两张预报。
    """
    sku_ids = [ln["sku_id"] for ln in lines]
    if len(set(sku_ids)) != len(sku_ids):
        raise StockError("同一预报里同一商品只能出现一次")

    skus = await _sku_info(db, sku_ids)
    missing = [sid for sid in sku_ids if sid not in skus]
    if missing:
        raise StockError(f"商品未建档：{missing}")
    wrong_owner = [sid for sid, s in skus.items() if s["owner_id"] != owner_id]
    if wrong_owner:
        raise StockError(f"商品不属于该货主：{wrong_owner}")

    asn = m.WmsAsn(
        code=await next_code(db, "ASN", "", 6),
        owner_id=owner_id,
        source=source,
        owner_doc_no=owner_doc_no,
        supplier_id=supplier_id,
        expect_arrive_at=expect_arrive_at,
        status=m.ASN_CONFIRMED if confirm else m.ASN_DRAFT,
        remark=remark,
        created_by=created_by,
    )
    db.add(asn)
    try:
        await db.flush()
    except IntegrityError as exc:
        await db.rollback()
        raise StockError(
            f"货主单号 {owner_doc_no} 已存在，请勿重复推送"
        ) from exc

    for ln in lines:
        db.add(
            m.WmsAsnLine(
                asn_id=asn.id,
                sku_id=ln["sku_id"],
                expect_qty=ln["expect_qty"],
                remark=ln.get("remark"),
            )
        )

    await db.flush()
    return asn


# ── 开收货单 ──────────────────────────────────────────


async def open_receipt(
    db: AsyncSession, *, asn_id: int, operator_id: Optional[int]
) -> m.WmsReceipt:
    """按预报开一张收货单，复制还没收的应收数量。

    一个预报可以开多张——分批到货是常态。已经在别处收掉的部分不计入本次应收。
    """
    asn = (
        await db.execute(select(m.WmsAsn).where(m.WmsAsn.id == asn_id))
    ).scalars().first()
    if asn is None:
        raise StockError("预报单不存在")
    if asn.status not in (m.ASN_CONFIRMED, m.ASN_RECEIVING):
        raise StockError(f"预报状态 {asn.status} 不能开收货单")

    lines = (
        await db.execute(select(m.WmsAsnLine).where(m.WmsAsnLine.asn_id == asn_id))
    ).scalars().all()

    # 已收数量：按商品汇总此前所有收货单的实收
    received_rows = (
        await db.execute(
            text(
                "SELECT rl.sku_id, COALESCE(SUM(rl.received_qty), 0) AS qty "
                "FROM wms_inbound_receipt_line rl "
                "JOIN wms_inbound_receipt r ON r.id = rl.receipt_id "
                "WHERE r.asn_id = :asn AND r.status <> 'cancelled' "
                "GROUP BY rl.sku_id"
            ),
            {"asn": asn_id},
        )
    ).all()
    received = {r.sku_id: Decimal(str(r.qty)) for r in received_rows}

    receipt = m.WmsReceipt(
        code=await next_code(db, "RCV", "", 6),
        asn_id=asn_id,
        owner_id=asn.owner_id,
        status=m.RECEIPT_OPEN,
        operator_id=operator_id,
    )
    db.add(receipt)
    await db.flush()

    created = 0
    for ln in lines:
        remain = Decimal(str(ln.expect_qty)) - received.get(ln.sku_id, Decimal("0"))
        if remain <= 0:
            continue
        db.add(
            m.WmsReceiptLine(
                receipt_id=receipt.id,
                sku_id=ln.sku_id,
                expect_qty=remain,
            )
        )
        created += 1

    if created == 0:
        raise StockError("这张预报已经收满，没有需要收的数量")

    asn.status = m.ASN_RECEIVING
    await db.flush()
    return receipt


# ── 录实收与批次 ──────────────────────────────────────


async def save_receipt_lines(
    db: AsyncSession,
    *,
    receipt_id: int,
    lines: list[dict],
) -> None:
    """保存实收与批次拆分。校验批次之和等于该行实收。"""
    receipt = (
        await db.execute(select(m.WmsReceipt).where(m.WmsReceipt.id == receipt_id))
    ).scalars().first()
    if receipt is None:
        raise StockError("收货单不存在")
    if receipt.status != m.RECEIPT_OPEN:
        raise StockError(f"收货单状态 {receipt.status} 不能修改")

    sku_ids = [ln["sku_id"] for ln in lines]
    skus = await _sku_info(db, sku_ids)

    existing = (
        await db.execute(
            select(m.WmsReceiptLine).where(m.WmsReceiptLine.receipt_id == receipt_id)
        )
    ).scalars().all()
    by_sku = {r.sku_id: r for r in existing}

    for ln in lines:
        row = by_sku.get(ln["sku_id"])
        if row is None:
            raise StockError(f"收货单里没有商品 {ln['sku_id']} 这一行")

        received = Decimal(str(ln.get("received_qty") or 0))
        damaged = Decimal(str(ln.get("damaged_qty") or 0))
        if received < 0 or damaged < 0:
            raise StockError("数量不能为负")
        if damaged > received:
            raise StockError("破损数量不能大于实收数量")

        # 超收不静默接收：多出来的必须由货主追加预报，否则账上多出的货没有来源
        if received > Decimal(str(row.expect_qty)):
            raise StockError(
                f"商品 {ln['sku_id']} 实收 {received} 超过应收 {row.expect_qty}，"
                "请让货主追加预报后再收"
            )

        lots = ln.get("lots") or []
        if skus.get(ln["sku_id"], {}).get("lot_required"):
            if not lots:
                raise StockError(f"商品 {ln['sku_id']} 启用批次管理，必须录入批次")
            lot_sum = sum(Decimal(str(x.get("received_qty") or 0)) for x in lots)
            if lot_sum != received:
                raise StockError(
                    f"商品 {ln['sku_id']} 各批次合计 {lot_sum} 与实收 {received} 不一致"
                )

        row.received_qty = received
        row.damaged_qty = damaged

        # 批次行整体重建，避免残留上一版录入
        old = (
            await db.execute(
                select(m.WmsReceiptLot).where(
                    m.WmsReceiptLot.receipt_line_id == row.id
                )
            )
        ).scalars().all()
        for o in old:
            await db.delete(o)
        await db.flush()

        for lot in lots:
            db.add(
                m.WmsReceiptLot(
                    receipt_line_id=row.id,
                    lot_code=lot["lot_code"],
                    production_date=lot.get("production_date"),
                    expiry_date=lot.get("expiry_date"),
                    received_qty=Decimal(str(lot.get("received_qty") or 0)),
                    damaged_qty=Decimal(str(lot.get("damaged_qty") or 0)),
                )
            )

    await db.flush()


# ── 收货确认：过账 + 生成上架 ─────────────────────────


async def _sample_qty(db: AsyncSession, asn_id: int, sku_id: int, received: Decimal) -> Decimal:
    """按服务订单算留样数量。没配就返回 0。"""
    rows = (
        await db.execute(
            select(m.WmsServiceOrder).where(
                m.WmsServiceOrder.asn_id == asn_id,
                m.WmsServiceOrder.status == m.SO_CONFIRMED,
                (m.WmsServiceOrder.sku_id == sku_id)
                | (m.WmsServiceOrder.sku_id.is_(None)),
            )
        )
    ).scalars().all()
    if not rows:
        return Decimal("0")

    total = Decimal("0")
    for so in rows:
        if so.sample_mode == "ratio" and so.sample_ratio:
            want = (received * Decimal(str(so.sample_ratio))).to_integral_value(
                rounding=ROUND_CEILING
            )
        else:
            want = Decimal(str(so.sample_qty or 0))
        total += want

    # 留样不能超过实收：收 0 件不可能留 1 件
    return min(total, received)


async def confirm_receipt(
    db: AsyncSession, *, receipt_id: int, operator_id: Optional[int]
) -> dict:
    """收货确认：好货入可发、破损入破损，并生成上架任务。"""
    receipt = (
        await db.execute(
            select(m.WmsReceipt).where(m.WmsReceipt.id == receipt_id).with_for_update()
        )
    ).scalars().first()
    if receipt is None:
        raise StockError("收货单不存在")
    if receipt.status != m.RECEIPT_OPEN:
        raise StockError(f"收货单状态 {receipt.status} 不能确认")

    lines = (
        await db.execute(
            select(m.WmsReceiptLine).where(m.WmsReceiptLine.receipt_id == receipt_id)
        )
    ).scalars().all()
    if not lines:
        raise StockError("收货单没有明细")

    skus = await _sku_info(db, [ln.sku_id for ln in lines])
    receiving_loc = await _receiving_location(db)

    putaway = m.WmsPutaway(
        code=await next_code(db, "PUT", "", 6),
        receipt_id=receipt.id,
        owner_id=receipt.owner_id,
        status=m.PUTAWAY_PENDING,
        operator_id=operator_id,
    )
    db.add(putaway)
    await db.flush()

    total_received = Decimal("0")
    for ln in lines:
        if Decimal(str(ln.received_qty)) <= 0:
            continue
        sku = skus.get(ln.sku_id, {})
        lot_rows = (
            await db.execute(
                select(m.WmsReceiptLot).where(m.WmsReceiptLot.receipt_line_id == ln.id)
            )
        ).scalars().all()

        # 非批次商品合成一条虚拟批次行，后面逻辑只走一条路径
        batches = (
            [
                {
                    "lot_code": r.lot_code,
                    "lot_id": None,
                    "received": Decimal(str(r.received_qty)),
                    "damaged": Decimal(str(r.damaged_qty)),
                    "expiry": r.expiry_date,
                    "production": r.production_date,
                    "row": r,
                }
                for r in lot_rows
            ]
            if sku.get("lot_required")
            else [
                {
                    "lot_code": None,
                    "lot_id": 0,
                    "received": Decimal(str(ln.received_qty)),
                    "damaged": Decimal(str(ln.damaged_qty)),
                    "expiry": None,
                    "production": None,
                    "row": None,
                }
            ]
        )

        sample_left = await _sample_qty(
            db, receipt.asn_id, ln.sku_id, Decimal(str(ln.received_qty))
        )
        ln.sample_qty = sample_left

        for b in batches:
            lot_id = b["lot_id"]
            if b["lot_code"]:
                lot_id = await ensure_lot(
                    db,
                    owner_id=receipt.owner_id,
                    sku_id=ln.sku_id,
                    lot_code=b["lot_code"],
                    production_date=b["production"],
                    expiry_date=b["expiry"],
                )
                if b["row"] is not None:
                    b["row"].lot_id = lot_id

            good = b["received"] - b["damaged"]
            if good > 0:
                await post_stock(
                    db,
                    sku_id=ln.sku_id,
                    lot_id=lot_id,
                    location_id=receiving_loc,
                    stock_status=STOCK_AVAILABLE,
                    delta=good,
                    ref_type="receipt",
                    ref_id=ln.id,
                    action="receipt",
                    operator_id=operator_id,
                )

            if b["damaged"] > 0:
                await post_stock(
                    db,
                    sku_id=ln.sku_id,
                    lot_id=lot_id,
                    location_id=receiving_loc,
                    stock_status=STOCK_DAMAGED,
                    delta=b["damaged"],
                    ref_type="receipt",
                    ref_id=ln.id,
                    action="receipt_damaged",
                    operator_id=operator_id,
                )
                db.add(
                    WmsDisposal(
                        owner_id=receipt.owner_id,
                        sku_id=ln.sku_id,
                        lot_id=lot_id,
                        location_id=receiving_loc,
                        qty=b["damaged"],
                        status="pending",
                        source_ref_type="receipt_line",
                        source_ref_id=ln.id,
                    )
                )

            if good <= 0:
                continue

            # 留样优先拆出去，剩余进存储区
            sample_take = min(sample_left, good)
            sample_left -= sample_take
            normal = good - sample_take

            if sample_take > 0:
                target, _ = await _pick_location(db, sku=sku, sample=True)
                db.add(
                    m.WmsPutawayLine(
                        putaway_id=putaway.id,
                        receipt_lot_id=b["row"].id if b["row"] is not None else None,
                        sku_id=ln.sku_id,
                        lot_id=lot_id,
                        qty=sample_take,
                        from_location_id=receiving_loc,
                        to_location_id=target,
                        sample_flag=True,
                    )
                )
            if normal > 0:
                db.add(
                    m.WmsPutawayLine(
                        putaway_id=putaway.id,
                        receipt_lot_id=b["row"].id if b["row"] is not None else None,
                        sku_id=ln.sku_id,
                        lot_id=lot_id,
                        qty=normal,
                        from_location_id=receiving_loc,
                        to_location_id=None,
                        sample_flag=False,
                    )
                )

        total_received += Decimal(str(ln.received_qty))

    receipt.status = m.RECEIPT_CHECKED
    receipt.received_at = datetime.now()

    # 累计收满才推进 ASN，否则留在 receiving 等下一批
    expect_total = (
        await db.execute(
            text(
                "SELECT COALESCE(SUM(expect_qty), 0) FROM wms_inbound_asn_line "
                "WHERE asn_id = :asn"
            ),
            {"asn": receipt.asn_id},
        )
    ).scalar() or 0
    got_total = (
        await db.execute(
            text(
                "SELECT COALESCE(SUM(rl.received_qty), 0) FROM wms_inbound_receipt_line rl "
                "JOIN wms_inbound_receipt r ON r.id = rl.receipt_id "
                "WHERE r.asn_id = :asn AND r.status <> 'cancelled'"
            ),
            {"asn": receipt.asn_id},
        )
    ).scalar() or 0

    asn = (
        await db.execute(select(m.WmsAsn).where(m.WmsAsn.id == receipt.asn_id))
    ).scalars().first()
    if asn is not None and Decimal(str(got_total)) >= Decimal(str(expect_total)):
        asn.status = m.ASN_RECEIVED

    await db.flush()
    return {
        "receipt_id": receipt.id,
        "putaway_id": putaway.id,
        "received": str(total_received),
    }


# ── 上架确认 ──────────────────────────────────────────


async def confirm_putaway_line(
    db: AsyncSession,
    *,
    line_id: int,
    to_location_id: Optional[int],
    operator_id: Optional[int],
) -> m.WmsPutawayLine:
    """扫库位确认一行。扣暂存、加目标，两条流水同事务。"""
    line = (
        await db.execute(
            select(m.WmsPutawayLine).where(m.WmsPutawayLine.id == line_id).with_for_update()
        )
    ).scalars().first()
    if line is None:
        raise StockError("上架行不存在")
    if line.done_at is not None:
        raise StockError("这行已经上架完成，不能重复确认")

    putaway = (
        await db.execute(select(m.WmsPutaway).where(m.WmsPutaway.id == line.putaway_id))
    ).scalars().first()
    if putaway is None or putaway.status in (m.PUTAWAY_DONE, m.PUTAWAY_CANCELLED):
        raise StockError("上架单状态不允许操作")

    skus = await _sku_info(db, [line.sku_id])
    sku = skus.get(line.sku_id, {})

    mismatch = False
    target = to_location_id or line.to_location_id
    if target is None:
        target, mismatch = await _pick_location(db, sku=sku, sample=line.sample_flag)

    qty = Decimal(str(line.qty))
    await post_stock(
        db,
        sku_id=line.sku_id,
        lot_id=line.lot_id,
        location_id=line.from_location_id,
        stock_status=STOCK_AVAILABLE,
        delta=-qty,
        ref_type="putaway_line",
        ref_id=line.id,
        action="putaway_out",
        operator_id=operator_id,
    )
    await post_stock(
        db,
        sku_id=line.sku_id,
        lot_id=line.lot_id,
        location_id=int(target),
        stock_status=STOCK_AVAILABLE,
        delta=qty,
        ref_type="putaway_line",
        ref_id=line.id,
        action="putaway_in",
        operator_id=operator_id,
    )

    line.to_location_id = int(target)
    line.temp_mismatch = mismatch
    line.done_at = datetime.now()

    if putaway.status == m.PUTAWAY_PENDING:
        putaway.status = m.PUTAWAY_DOING

    remaining = (
        await db.execute(
            select(m.WmsPutawayLine).where(
                and_(
                    m.WmsPutawayLine.putaway_id == putaway.id,
                    m.WmsPutawayLine.done_at.is_(None),
                    m.WmsPutawayLine.id != line.id,
                )
            )
        )
    ).scalars().all()
    if not remaining:
        putaway.status = m.PUTAWAY_DONE
        receipt = (
            await db.execute(
                select(m.WmsReceipt).where(m.WmsReceipt.id == putaway.receipt_id)
            )
        ).scalars().first()
        if receipt is not None:
            receipt.status = m.RECEIPT_PUTAWAY_DONE

    await db.flush()
    return line
