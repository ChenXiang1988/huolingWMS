"""逆向域的表。P2 只有破损处置，退货单在 P6 补。

破损处置比退货单早三个期次上线，因为收货现场就会压瘪摔坏——不给出口，
这些货只能一直堆在收货暂存位，且账上算在可发里。
"""
from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import Boolean, DateTime, Index, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.db import Base
from src.models.mixins import IDMixin, TimestampMixin

# 处置方式：转回可发 / 报废 / 退回货主（需出库能力，P3 起开放）
DISPOSAL_RESTOCK = "restock"
DISPOSAL_SCRAP = "scrap"
DISPOSAL_RETURN_OWNER = "return_owner"


class WmsDisposal(IDMixin, TimestampMixin, Base):
    """破损处置记录。

    记录的是"这批破损货怎么处理了"，不是审批流：单仓场景下审批会让人绕过系统。
    """

    __tablename__ = "wms_returns_disposal"
    __table_args__ = (
        Index("ix_disposal_pending", "status", "created_at"),
        Index("ix_disposal_owner_sku", "owner_id", "sku_id"),
    )

    owner_id: Mapped[int] = mapped_column(Integer, nullable=False)
    sku_id: Mapped[int] = mapped_column(Integer, nullable=False)
    lot_id: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    location_id: Mapped[int] = mapped_column(Integer, nullable=False)
    qty: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, comment="待处置数量"
    )
    method: Mapped[Optional[str]] = mapped_column(
        String(16), nullable=True, comment="restock / scrap / return_owner"
    )
    reason: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    ref_out_code: Mapped[Optional[str]] = mapped_column(
        String(32), nullable=True, comment="return_owner 时生成的出库单号"
    )
    status: Mapped[str] = mapped_column(
        String(16), default="pending", nullable=False, comment="pending / handled"
    )
    source_ref_type: Mapped[Optional[str]] = mapped_column(
        String(32), nullable=True, comment="来源单据类型，如 receipt"
    )
    source_ref_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    operator_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    handled_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


# ── P6 退货单 ────────────────────────────────────────────

RETURN_DRAFT = "draft"
RETURN_CONFIRMED = "confirmed"
RETURN_RECEIVED = "received"
RETURN_CANCELLED = "cancelled"

QUALITY_GOOD = "good"
QUALITY_DAMAGED = "damaged"


class WmsReturn(IDMixin, TimestampMixin, Base):
    """客户退货单。一张单可挂多行，逐行按品质分流。"""

    __tablename__ = "wms_returns_return"
    __table_args__ = (Index("ix_return_owner_status", "owner_id", "status"),)

    code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    owner_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    owner_doc_no: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    customer_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    source_order_code: Mapped[Optional[str]] = mapped_column(
        String(32), nullable=True, comment="原出库单号，便于追溯"
    )
    status: Mapped[str] = mapped_column(String(16), default=RETURN_CONFIRMED, nullable=False)
    remark: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    received_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    operator_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)


class WmsReturnLine(IDMixin, TimestampMixin, Base):
    """退货明细。

    好货与破损货分开录，确认时产生两条不同的流水；破损货还会生成一条
    ``disposal``，走 P2 已跑通的处置流程，不另起一套。
    """

    __tablename__ = "wms_returns_return_line"
    __table_args__ = (
        UniqueConstraint("return_id", "sku_id", "lot_id", "quality",
                        name="uq_return_line_dimension"),
    )

    return_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    sku_id: Mapped[int] = mapped_column(Integer, nullable=False)
    lot_id: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    qty: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    quality: Mapped[str] = mapped_column(
        String(16), default=QUALITY_GOOD, nullable=False, comment="good / damaged"
    )
    posted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
