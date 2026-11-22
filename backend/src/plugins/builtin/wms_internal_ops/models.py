"""库内作业的表。P4 只有补货。"""
from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import Boolean, DateTime, Index, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.db import Base
from src.models.mixins import IDMixin, TimestampMixin

REPLENISH_SUGGESTED = "suggested"
REPLENISH_DONE = "done"
REPLENISH_CANCELLED = "cancelled"


class WmsReplenish(IDMixin, TimestampMixin, Base):
    """补货建议 / 执行记录。

    先生成建议（只读、不动库存），人工确认后才执行。这样存储区不足、
    或货主临时改了箱规，都不会造成半吊子的库存移动。
    """

    __tablename__ = "wms_internal_ops_replenish"
    __table_args__ = (
        UniqueConstraint(
            "owner_id", "sku_id", "to_location_id", "status",
            name="uq_replenish_pending",
        ),
        Index("ix_replenish_status", "status", "created_at"),
    )

    owner_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    sku_id: Mapped[int] = mapped_column(Integer, nullable=False)
    lot_id: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False,
        comment="补货按批次移动，0 表示不启用批次管理的商品",
    )
    from_location_id: Mapped[int] = mapped_column(Integer, nullable=False)
    to_location_id: Mapped[int] = mapped_column(Integer, nullable=False)
    qty: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    current_qty: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), default=Decimal("0"), nullable=False, comment="建议时拣选区现有量"
    )
    min_qty: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), default=Decimal("0"), nullable=False, comment="补货下限"
    )
    status: Mapped[str] = mapped_column(
        String(16), default=REPLENISH_SUGGESTED, nullable=False
    )
    done_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    operator_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    reason: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)


# ── P5：移库、盘点、留样台账 ───────────────────────────────

TRANSFER_PENDING = "pending"
TRANSFER_DONE = "done"
TRANSFER_CANCELLED = "cancelled"

COUNT_PENDING = "pending"
COUNT_DONE = "done"

SAMPLE_HOLDING = "holding"
SAMPLE_DISPOSED = "disposed"


class WmsTransfer(IDMixin, TimestampMixin, Base):
    """移库单。一次一行——多商品搬家用多张单，避免一行失败拖累整单。"""

    __tablename__ = "wms_internal_ops_transfer"
    __table_args__ = (Index("ix_transfer_status", "status", "created_at"),)

    code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    owner_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    sku_id: Mapped[int] = mapped_column(Integer, nullable=False)
    lot_id: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    from_location_id: Mapped[int] = mapped_column(Integer, nullable=False)
    to_location_id: Mapped[int] = mapped_column(Integer, nullable=False)
    qty: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    status: Mapped[str] = mapped_column(String(16), default=TRANSFER_PENDING, nullable=False)
    done_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    operator_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    reason: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)


class WmsCount(IDMixin, TimestampMixin, Base):
    """盘点单。生成时冻结账面快照，之后账面再变也不刷新。"""

    __tablename__ = "wms_internal_ops_count"

    code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    owner_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(16), default=COUNT_PENDING, nullable=False)
    done_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    operator_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    note: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)


class WmsCountLine(IDMixin, TimestampMixin, Base):
    """盘点行。``qty_diff`` 是调整量，确认时按它过账而不是覆盖账面。"""

    __tablename__ = "wms_internal_ops_count_line"
    __table_args__ = (
        UniqueConstraint("count_id", "sku_id", "lot_id", "location_id",
                        name="uq_count_line_dimension"),
    )

    count_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    sku_id: Mapped[int] = mapped_column(Integer, nullable=False)
    lot_id: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    location_id: Mapped[int] = mapped_column(Integer, nullable=False)
    qty_book: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), default=Decimal("0"), nullable=False, comment="生成时的账面快照"
    )
    qty_actual: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4), nullable=True)
    qty_diff: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0"), nullable=False)
    adjusted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class WmsSample(IDMixin, TimestampMixin, Base):
    """留样台账。一条对应一条已完成的留样上架行。"""

    __tablename__ = "wms_internal_ops_sample"
    __table_args__ = (
        UniqueConstraint("putaway_line_id", name="uq_sample_putaway_line"),
        Index("ix_sample_expire_status", "expire_at", "status"),
    )

    putaway_line_id: Mapped[int] = mapped_column(Integer, nullable=False)
    owner_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    sku_id: Mapped[int] = mapped_column(Integer, nullable=False)
    lot_id: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    location_id: Mapped[int] = mapped_column(Integer, nullable=False)
    qty: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    sampled_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    expire_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    retain_days: Mapped[int] = mapped_column(Integer, default=30, nullable=False)
    on_expiry: Mapped[str] = mapped_column(
        String(16), default="scrap", nullable=False,
        comment="scrap / return_owner / restock / extend",
    )
    status: Mapped[str] = mapped_column(String(16), default=SAMPLE_HOLDING, nullable=False)
    disposed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    method: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    ref_out_code: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    reason: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
