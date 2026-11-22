"""库存域的表：批次、库存台账、库存流水。

这个域是全系统唯一能写库存数量的地方。三张表的约束不是"数据库层的保险"，
而是幂等机制本身——流水表的唯一键就是过账的幂等键，冲突即代表这次调用已经做过。
"""
from datetime import date
from decimal import Decimal
from typing import Optional

from sqlalchemy import Date, Index, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.db import Base
from src.models.mixins import IDMixin, TimestampMixin

# 库存状态：可发 / 冻结 / 破损
STOCK_AVAILABLE = "available"
STOCK_FROZEN = "frozen"
STOCK_DAMAGED = "damaged"

# 批次状态：可发 / 冻结 / 已清空
LOT_ACTIVE = "active"
LOT_FROZEN = "frozen"
LOT_CONSUMED = "consumed"


class WmsLot(IDMixin, TimestampMixin, Base):
    """批次。

    ``lot_id = 0`` 是约定，表示"该商品不启用批次管理"，不建实体记录。
    这样所有库存行都带批次维度，业务代码只有一条路径。
    """

    __tablename__ = "wms_inventory_lot"
    __table_args__ = (
        UniqueConstraint("owner_id", "sku_id", "lot_code", name="uq_lot_owner_sku_code"),
        Index("ix_lot_expiry_status", "expiry_date", "status"),
    )

    owner_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    sku_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    lot_code: Mapped[str] = mapped_column(String(64), nullable=False, comment="批号")
    production_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    expiry_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True, comment="到期日")
    status: Mapped[str] = mapped_column(String(16), default=LOT_ACTIVE, nullable=False)
    frozen_reason: Mapped[Optional[str]] = mapped_column(
        String(32), nullable=True, comment="expiry_warn 临期 / manual 手工"
    )


class WmsStock(IDMixin, TimestampMixin, Base):
    """库存台账。粒度：货主 + 货品 + 批次 + 库位 + 状态。"""

    __tablename__ = "wms_inventory_stock"
    __table_args__ = (
        UniqueConstraint(
            "owner_id", "sku_id", "lot_id", "location_id", "stock_status",
            name="uq_stock_dimension",
        ),
        Index("ix_stock_sku_lot", "sku_id", "lot_id"),
        Index("ix_stock_location", "location_id"),
    )

    owner_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    sku_id: Mapped[int] = mapped_column(Integer, nullable=False)
    lot_id: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    location_id: Mapped[int] = mapped_column(Integer, nullable=False)
    stock_status: Mapped[str] = mapped_column(String(16), default=STOCK_AVAILABLE, nullable=False)
    qty: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0"), nullable=False)


class WmsTxn(IDMixin, TimestampMixin, Base):
    """库存流水。只追加，不修改，不删除。

    唯一键 ``(ref_type, ref_id, sku_id, lot_id, location_id, action)`` 就是幂等键：
    同一来源单据的同一动作重复提交，会在这里撞键，于是不重复记账。
    """

    __tablename__ = "wms_inventory_txn"
    __table_args__ = (
        UniqueConstraint(
            "ref_type", "ref_id", "sku_id", "lot_id", "location_id", "action",
            name="uq_txn_idempotent",
        ),
        Index("ix_txn_sku_lot_time", "sku_id", "lot_id"),
        Index("ix_txn_ref", "ref_type", "ref_id"),
    )

    ref_type: Mapped[str] = mapped_column(String(32), nullable=False,
                                          comment="receipt/putaway/order/shipment/count/adjust/lot_expiry")
    ref_id: Mapped[int] = mapped_column(Integer, nullable=False)
    action: Mapped[str] = mapped_column(String(32), nullable=False,
                                        comment="同一单据内的动作，状态转换取 status:from->to")
    owner_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    sku_id: Mapped[int] = mapped_column(Integer, nullable=False)
    lot_id: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    location_id: Mapped[int] = mapped_column(Integer, nullable=False)
    stock_status: Mapped[str] = mapped_column(String(16), nullable=False,
                                              comment="变动后的状态")
    from_status: Mapped[Optional[str]] = mapped_column(String(16), nullable=True,
                                                       comment="状态转换时的源状态")
    to_status: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    delta: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False,
                                           comment="正数入库、负数出库；状态转换时为 0")
    qty_after: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False,
                                               comment="变动后该库存行的数量")
    operator_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
