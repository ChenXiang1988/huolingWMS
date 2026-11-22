"""出库域的表：订单、分配、拣货、复核、发运。

``allocation`` 是"记账预占"，不改库存数量——库存到发运时才动。这条让每一步都能
退回而不污染账，也让取消订单只需把分配作废，不用反向补库存。
"""
from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from src.db import Base
from src.models.mixins import IDMixin, TimestampMixin

# 订单状态
ORDER_DRAFT = "draft"
ORDER_CONFIRMED = "confirmed"
ORDER_ALLOCATED = "allocated"
ORDER_PICKING = "picking"
ORDER_CHECKED = "checked"
ORDER_SHIPPED = "shipped"
ORDER_CANCELLED = "cancelled"

# 拣货单状态
PICK_PENDING = "pending"
PICK_DOING = "doing"
PICK_DONE = "done"


class WmsOrder(IDMixin, TimestampMixin, Base):
    """出库订单。``order_type`` 区分 B 端大货与 C 端电商。"""

    __tablename__ = "wms_outbound_order"
    __table_args__ = (
        UniqueConstraint("owner_id", "owner_doc_no", name="uq_order_owner_doc"),
        Index("ix_order_status_created", "status", "created_at"),
    )

    code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    owner_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    owner_doc_no: Mapped[str] = mapped_column(String(64), nullable=False)
    order_type: Mapped[str] = mapped_column(
        String(8), default="C", nullable=False, comment="B 端大货 / C 端电商"
    )
    source: Mapped[str] = mapped_column(String(16), default="manual", nullable=False)
    customer_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    receiver: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    receiver_phone: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    receiver_address: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    carrier_code: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    status: Mapped[str] = mapped_column(String(16), default=ORDER_DRAFT, nullable=False)
    weight_theory: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(18, 4), nullable=True, comment="理论重量，分配时算"
    )
    weight_actual: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(18, 4), nullable=True, comment="复核实称"
    )
    created_by: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    wave_id: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, index=True, comment="P4 波次；旧表由 patches.py 补列"
    )


class WmsOrderLine(IDMixin, TimestampMixin, Base):
    __tablename__ = "wms_outbound_order_line"
    __table_args__ = (UniqueConstraint("order_id", "sku_id", name="uq_order_line_sku"),)

    order_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    sku_id: Mapped[int] = mapped_column(Integer, nullable=False)
    qty: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    lot_id: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, comment="指定批次；为空表示按先到期先出"
    )
    allocated_qty: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), default=Decimal("0"), nullable=False
    )


class WmsAllocation(IDMixin, TimestampMixin, Base):
    """分配结果。只记账，不动库存数量。"""

    __tablename__ = "wms_outbound_allocation"
    __table_args__ = (
        UniqueConstraint(
            "order_line_id", "lot_id", "location_id", name="uq_alloc_line_lot_loc"
        ),
        Index("ix_alloc_order", "order_id"),
    )

    order_id: Mapped[int] = mapped_column(Integer, nullable=False)
    order_line_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    owner_id: Mapped[int] = mapped_column(Integer, nullable=False)
    sku_id: Mapped[int] = mapped_column(Integer, nullable=False)
    lot_id: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    location_id: Mapped[int] = mapped_column(Integer, nullable=False)
    qty: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    status: Mapped[str] = mapped_column(
        String(16), default="active", nullable=False, comment="active / void"
    )


class WmsPick(IDMixin, TimestampMixin, Base):
    __tablename__ = "wms_outbound_pick"

    code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    order_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    owner_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(16), default=PICK_PENDING, nullable=False)
    operator_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)


class WmsPickLine(IDMixin, TimestampMixin, Base):
    """拣货行。``seq`` 是库位路径顺序，作业员按它走。"""

    __tablename__ = "wms_outbound_pick_line"
    __table_args__ = (Index("ix_pick_line_pick_seq", "pick_id", "seq"),)

    pick_id: Mapped[int] = mapped_column(Integer, nullable=False)
    allocation_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    sku_id: Mapped[int] = mapped_column(Integer, nullable=False)
    lot_id: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    location_id: Mapped[int] = mapped_column(Integer, nullable=False)
    qty: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    seq: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    picked_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class WmsCheck(IDMixin, TimestampMixin, Base):
    """复核记录。一次订单一条，可多次改实称。"""

    __tablename__ = "wms_outbound_check"
    __table_args__ = (UniqueConstraint("order_id", name="uq_check_order"),)

    order_id: Mapped[int] = mapped_column(Integer, nullable=False)
    owner_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    weight_actual: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4), nullable=True)
    weight_theory: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4), nullable=True)
    deviation: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(8, 4), nullable=True, comment="相对偏差，0.05 表示 5%"
    )
    passed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    reason: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    operator_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)


class WmsShipment(IDMixin, TimestampMixin, Base):
    __tablename__ = "wms_outbound_shipment"
    __table_args__ = (UniqueConstraint("order_id", name="uq_shipment_order"),)

    code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    order_id: Mapped[int] = mapped_column(Integer, nullable=False)
    owner_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    carrier_code: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    tracking_no: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    shipped_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    operator_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)


# ── P4 波次与分播 ────────────────────────────────────────

WAVE_PENDING = "pending"
WAVE_GENERATING = "generating"
WAVE_READY = "ready"
WAVE_PICKING = "picking"
WAVE_DONE = "done"
WAVE_CANCELLED = "cancelled"
WAVE_INTERRUPTED = "interrupted"


class WmsWaveRule(IDMixin, TimestampMixin, Base):
    """波次规则：按截单时间、承运商、区域、热度筛订单。"""

    __tablename__ = "wms_outbound_wave_rule"

    code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    cutoff_at: Mapped[Optional[str]] = mapped_column(
        String(8), nullable=True, comment="截单时间 HH:MM，空表示不限"
    )
    carrier_code: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    region_prefix: Mapped[Optional[str]] = mapped_column(
        String(32), nullable=True, comment="收件地址前缀"
    )
    hot_only: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False, comment="只组热门单（订单行数≤阈值）"
    )
    hot_line_limit: Mapped[int] = mapped_column(Integer, default=2, nullable=False)
    max_orders: Mapped[int] = mapped_column(
        Integer, default=200, nullable=False, comment="单波上限"
    )
    status: Mapped[int] = mapped_column(Integer, default=1, nullable=False)


class WmsWave(IDMixin, TimestampMixin, Base):
    """一次波次生成作业。进度落库，前端轮询它而不是等 HTTP 长请求。"""

    __tablename__ = "wms_outbound_wave"

    code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    rule_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(16), default=WAVE_PENDING, nullable=False)
    total: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    processed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    failed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    fail_detail: Mapped[Optional[str]] = mapped_column(
        String(2000), nullable=True, comment="失败订单与原因，截断保存"
    )
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    cancel_reason: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    operator_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)


class WmsSortCell(IDMixin, TimestampMixin, Base):
    """播种墙格口。一个格口绑一个订单。"""

    __tablename__ = "wms_outbound_sort_cell"
    __table_args__ = (
        UniqueConstraint("wave_id", "cell_no", name="uq_sort_cell_wave_no"),
    )

    wave_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    cell_no: Mapped[str] = mapped_column(String(16), nullable=False)
    order_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    status: Mapped[str] = mapped_column(
        String(16), default="empty", nullable=False, comment="empty / filling / full"
    )
    placed_qty: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), default=Decimal("0"), nullable=False
    )
    required_qty: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), default=Decimal("0"), nullable=False
    )


class WmsSeed(IDMixin, TimestampMixin, Base):
    """分播扫描记录：扫到某件商品，应放进哪个格口。"""

    __tablename__ = "wms_outbound_seed"
    __table_args__ = (Index("ix_seed_wave_cell", "wave_id", "cell_id"),)

    wave_id: Mapped[int] = mapped_column(Integer, nullable=False)
    cell_id: Mapped[int] = mapped_column(Integer, nullable=False)
    order_id: Mapped[int] = mapped_column(Integer, nullable=False)
    sku_id: Mapped[int] = mapped_column(Integer, nullable=False)
    qty: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("1"), nullable=False)
    operator_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
