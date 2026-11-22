"""入库域的表：预报、服务订单、收货、上架。

一个 ASN 可挂多张收货单——分批到货是常态，不是异常。这条决定了 ``receipt.asn_id``
不能唯一，也决定了 ASN 的状态要靠"累计实收 vs 应收"来推进，而不是收一次就收口。
"""
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import Boolean, Date, DateTime, Index, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.db import Base
from src.models.mixins import IDMixin, TimestampMixin

# ASN 状态
ASN_DRAFT = "draft"
ASN_CONFIRMED = "confirmed"
ASN_RECEIVING = "receiving"
ASN_RECEIVED = "received"
ASN_CLOSED = "closed"
ASN_CANCELLED = "cancelled"

# 收货单状态
RECEIPT_OPEN = "open"
RECEIPT_CHECKED = "checked"
RECEIPT_PUTAWAY_DONE = "putaway_done"
RECEIPT_CANCELLED = "cancelled"

# 上架单状态
PUTAWAY_PENDING = "pending"
PUTAWAY_DOING = "doing"
PUTAWAY_DONE = "done"
PUTAWAY_CANCELLED = "cancelled"

# 服务订单状态
SO_DRAFT = "draft"
SO_CONFIRMED = "confirmed"
SO_DONE = "done"
SO_CANCELLED = "cancelled"


class WmsAsn(IDMixin, TimestampMixin, Base):
    """入库预报（Advance Shipping Notice）。"""

    __tablename__ = "wms_inbound_asn"
    __table_args__ = (
        UniqueConstraint("owner_id", "owner_doc_no", name="uq_asn_owner_doc"),
        Index("ix_asn_status_expect", "status", "expect_arrive_at"),
    )

    code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False, comment="ASN 号")
    owner_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    source: Mapped[str] = mapped_column(
        String(16), default="api", nullable=False, comment="api / portal / manual"
    )
    owner_doc_no: Mapped[str] = mapped_column(
        String(64), nullable=False, comment="货主侧单号，用于去重"
    )
    supplier_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    expect_arrive_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(16), default=ASN_DRAFT, nullable=False)
    remark: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_by: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)


class WmsAsnLine(IDMixin, TimestampMixin, Base):
    """预报明细。数量以最小单位记。"""

    __tablename__ = "wms_inbound_asn_line"
    __table_args__ = (UniqueConstraint("asn_id", "sku_id", name="uq_asn_line_sku"),)

    asn_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    sku_id: Mapped[int] = mapped_column(Integer, nullable=False)
    expect_qty: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    remark: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)


class WmsServiceOrder(IDMixin, TimestampMixin, Base):
    """货主服务订单。P2 只承载留样要求，其余服务类型后面再加。

    ``sku_id`` 为空表示对整张 ASN 的全部商品生效。
    """

    __tablename__ = "wms_inbound_service_order"

    code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    owner_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    asn_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    sku_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    service_type: Mapped[str] = mapped_column(
        String(32), default="sample", nullable=False, comment="sample 留样"
    )
    sample_mode: Mapped[str] = mapped_column(
        String(8), default="fixed", nullable=False, comment="fixed 固定数量 / ratio 按比例"
    )
    sample_qty: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4), nullable=True)
    sample_ratio: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(8, 4), nullable=True, comment="0–1 之间"
    )
    retain_days: Mapped[int] = mapped_column(Integer, default=30, nullable=False)
    on_expiry: Mapped[str] = mapped_column(
        String(16), default="scrap", nullable=False, comment="scrap / return_owner"
    )
    status: Mapped[str] = mapped_column(String(16), default=SO_CONFIRMED, nullable=False)
    created_by: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)


class WmsReceipt(IDMixin, TimestampMixin, Base):
    """收货单。一个 ASN 可对应多张，``asn_id`` 不唯一。"""

    __tablename__ = "wms_inbound_receipt"
    __table_args__ = (Index("ix_receipt_asn_status", "asn_id", "status"),)

    code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    asn_id: Mapped[int] = mapped_column(Integer, nullable=False)
    owner_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    received_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(16), default=RECEIPT_OPEN, nullable=False)
    operator_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)


class WmsReceiptLine(IDMixin, TimestampMixin, Base):
    """收货明细。数量是汇总值，启用批次的商品由 ``receipt_lot`` 汇总写回。"""

    __tablename__ = "wms_inbound_receipt_line"
    __table_args__ = (UniqueConstraint("receipt_id", "sku_id", name="uq_receipt_line_sku"),)

    receipt_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    sku_id: Mapped[int] = mapped_column(Integer, nullable=False)
    expect_qty: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    received_qty: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0"), nullable=False)
    damaged_qty: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0"), nullable=False)
    sample_qty: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0"), nullable=False)
    putaway_qty: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0"), nullable=False)
    variance_reason: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)


class WmsReceiptLot(IDMixin, TimestampMixin, Base):
    """收货批次。只有启用批次管理的商品才建行。

    ``lot_id`` 是过账前由 ``inventory.ensure_lot`` 换来的真实批次 ID，
    收货确认时才有值——录入阶段货主只给了批号。
    """

    __tablename__ = "wms_inbound_receipt_lot"
    __table_args__ = (
        UniqueConstraint("receipt_line_id", "lot_code", name="uq_receipt_lot_code"),
    )

    receipt_line_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    lot_code: Mapped[str] = mapped_column(String(64), nullable=False)
    lot_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    production_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    expiry_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    received_qty: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0"), nullable=False)
    damaged_qty: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0"), nullable=False)


class WmsPutaway(IDMixin, TimestampMixin, Base):
    """上架单。一张收货单对应一张上架单。"""

    __tablename__ = "wms_inbound_putaway"

    code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    receipt_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    owner_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(16), default=PUTAWAY_PENDING, nullable=False)
    operator_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)


class WmsPutawayLine(IDMixin, TimestampMixin, Base):
    """上架明细。

    ``sample_flag`` 为真的行要落到留样区，扫完才生成留样记录；
    ``temp_mismatch`` 记录这行被上到了非匹配温区——放行了但留痕。
    """

    __tablename__ = "wms_inbound_putaway_line"
    __table_args__ = (Index("ix_putaway_line_putaway_status", "putaway_id"),)

    putaway_id: Mapped[int] = mapped_column(Integer, nullable=False)
    receipt_lot_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    sku_id: Mapped[int] = mapped_column(Integer, nullable=False)
    lot_id: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    qty: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    from_location_id: Mapped[int] = mapped_column(Integer, nullable=False, comment="收货暂存位")
    to_location_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    sample_flag: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    temp_mismatch: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    done_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
