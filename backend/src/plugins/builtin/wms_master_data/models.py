"""主数据域的表。

表名统一以插件名 ``wms_master_data_`` 开头，与基座的插件表约定一致。
字段与约束对齐 ``docs/design/data-model.md``，不在这里临时简化——P2 起入库、
出库都会往这些表写数据，少一个字段就是一次补丁，改一个名字就是一层转换代码。
"""
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Index, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.db import Base
from src.models.mixins import IDMixin, TimestampMixin


class WmsOwner(IDMixin, TimestampMixin, Base):
    """货主档案。

    ``sync_enabled`` 表示该货主是否已接入上游 ERP：接入后其建单入口关闭，
    订单改由上游下发。
    """

    __tablename__ = "wms_master_data_owner"

    code: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False, comment="货主编码"
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False, comment="货主名称")
    contact: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    address: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    primary_user_id: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, comment="货主主账号的 sys_user.id"
    )
    settle_period: Mapped[Optional[str]] = mapped_column(
        String(32), nullable=True, comment="账期，如 natural_month"
    )
    sync_enabled: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False, comment="是否接入上游 ERP"
    )
    status: Mapped[int] = mapped_column(
        Integer, default=1, nullable=False, comment="状态: 0=停用 1=启用"
    )
    remark: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    def __repr__(self) -> str:
        return f"<WmsOwner {self.code}>"


class WmsUserOwner(IDMixin, TimestampMixin, Base):
    """账号与货主的绑定。一个账号只能绑一个货主，隔离边界靠 ``user_id`` 唯一。"""

    __tablename__ = "wms_master_data_user_owner"

    user_id: Mapped[int] = mapped_column(
        Integer, unique=True, nullable=False, index=True, comment="系统用户 ID"
    )
    owner_id: Mapped[int] = mapped_column(
        Integer, nullable=False, index=True, comment="货主 ID"
    )
    is_primary: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False, comment="是否货主主账号"
    )
    status: Mapped[int] = mapped_column(
        Integer, default=1, nullable=False, comment="状态: 0=停用 1=启用"
    )

    def __repr__(self) -> str:
        return f"<WmsUserOwner user={self.user_id} owner={self.owner_id}>"


class WmsWarehouse(IDMixin, TimestampMixin, Base):
    """仓库。单仓部署，这张表只有一行，``topology`` 决定坐标字段怎么解释。"""

    __tablename__ = "wms_master_data_warehouse"

    code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    topology: Mapped[str] = mapped_column(
        String(32), default="FLAT", nullable=False,
        comment="FLAT 平面仓 / MULTI_FLOOR 楼层仓 / ASRS 钢结构立库",
    )
    status: Mapped[int] = mapped_column(Integer, default=1, nullable=False)


class WmsZone(IDMixin, TimestampMixin, Base):
    """库区。温区与楼层以库区为准，库位上冗余一份。"""

    __tablename__ = "wms_master_data_zone"

    warehouse_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    zone_type: Mapped[Optional[str]] = mapped_column(String(32), nullable=True,
                                                     comment="receiving/storage/picking/sorting/packing/staging/sample")
    temp_zone: Mapped[str] = mapped_column(String(16), default="ambient", nullable=False,
                                           comment="ambient 常温 / chilled 冷藏")
    floor_no: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    status: Mapped[int] = mapped_column(Integer, default=1, nullable=False)


class WmsUnit(IDMixin, TimestampMixin, Base):
    """计量单位。库存数量一律以最小单位存储。"""

    __tablename__ = "wms_master_data_unit"

    code: Mapped[str] = mapped_column(String(16), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(32), nullable=False)
    decimal_places: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class WmsLocation(IDMixin, TimestampMixin, Base):
    """库位。坐标五字段随仓型解释，``space_domain()`` 用它们判定空间域。"""

    __tablename__ = "wms_master_data_location"

    zone_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    owner_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True,
                                                    comment="空=共享库位")
    location_type: Mapped[str] = mapped_column(String(32), default="storage", nullable=False,
                                               index=True)
    temp_zone: Mapped[str] = mapped_column(String(16), default="ambient", nullable=False)
    floor_no: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    aisle: Mapped[Optional[str]] = mapped_column(String(16), nullable=True, comment="巷道")
    rack: Mapped[Optional[str]] = mapped_column(String(16), nullable=True, comment="货架")
    level: Mapped[Optional[str]] = mapped_column(String(16), nullable=True, comment="层")
    bin: Mapped[Optional[str]] = mapped_column(String(16), nullable=True, comment="位")
    capacity: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0"), nullable=False,
                                              comment="单库位可放几托")
    replenish_min: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4), nullable=True,
                                                             comment="拆零补货下限，仅 picking 生效")
    replenish_max: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4), nullable=True)
    status: Mapped[int] = mapped_column(Integer, default=1, nullable=False)


class WmsSku(IDMixin, TimestampMixin, Base):
    """货品档案。

    两套编码并存，属于两个主体：
    ``code`` 是本仓编码（全仓唯一，库内作业用），``owner_sku_code`` 是货主编码
    （同货主内唯一，对接匹配用）。两者互不覆盖。
    """

    __tablename__ = "wms_master_data_sku"
    __table_args__ = (
        UniqueConstraint("owner_id", "owner_sku_code", name="uq_sku_owner_code"),
    )

    owner_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False,
                                      comment="仓库编码，自动取号 SKU000001")
    owner_sku_code: Mapped[str] = mapped_column(String(64), nullable=False, comment="货主编码")

    # ── 事实层：上游或货主维护 ─────────────────────────
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    spec: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    unit_code: Mapped[str] = mapped_column(String(16), default="件", nullable=False)
    category: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    weight: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4), nullable=True)
    volume: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4), nullable=True)
    temp_requirement: Mapped[str] = mapped_column(String(16), default="ambient", nullable=False)
    lot_required: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False,
                                               comment="是否启用批次管理")
    expiry_warn_days: Mapped[int] = mapped_column(Integer, default=30, nullable=False,
                                                  comment="临期预警天数，0=到期当天")
    qty_per_box: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("1"), nullable=False,
                                                 comment="一箱几件，货主维护")

    # ── 存储属性：仓库维护 ────────────────────────────
    default_zone_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    qty_per_pallet: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4), nullable=True,
                                                              comment="一托几件，仓库维护")
    putaway_note: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    status: Mapped[int] = mapped_column(Integer, default=1, nullable=False)


class WmsBarcode(IDMixin, TimestampMixin, Base):
    """货品条码，一品多码。"""

    __tablename__ = "wms_master_data_barcode"
    __table_args__ = (
        UniqueConstraint("owner_id", "barcode", name="uq_barcode_owner_code"),
    )

    owner_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    sku_id: Mapped[int] = mapped_column(Integer, ForeignKey("wms_master_data_sku.id"),
                                        nullable=False, index=True)
    barcode: Mapped[str] = mapped_column(String(64), nullable=False)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class WmsPartner(IDMixin, TimestampMixin, Base):
    """合作方：供应商与客户。"""

    __tablename__ = "wms_master_data_partner"

    owner_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    partner_type: Mapped[str] = mapped_column(String(16), default="supplier", nullable=False,
                                              comment="supplier 供应商 / customer 客户")
    contact: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    status: Mapped[int] = mapped_column(Integer, default=1, nullable=False)


class WmsApiKey(IDMixin, TimestampMixin, Base):
    """货主 API 凭证。只存哈希，明文只在签发时返回一次。"""

    __tablename__ = "wms_master_data_apikey"

    owner_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    key_prefix: Mapped[str] = mapped_column(String(16), nullable=False, index=True,
                                            comment="密钥前缀，便于识别是哪一把")
    key_hash: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    status: Mapped[int] = mapped_column(Integer, default=1, nullable=False)


class WmsSequence(IDMixin, TimestampMixin, Base):
    """单号与编码序列。

    ``period`` 为空表示全局序列（如 SKU 编码），有值表示按该周期重置（如日期单号）。
    取号必须用 ``SELECT ... FOR UPDATE``，否则并发下会重号。
    """

    __tablename__ = "wms_master_data_sequence"
    __table_args__ = (
        UniqueConstraint("prefix", "period", name="uq_sequence_prefix_period"),
    )

    prefix: Mapped[str] = mapped_column(String(16), nullable=False)
    period: Mapped[str] = mapped_column(String(16), default="", nullable=False)
    current: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class WmsTeam(IDMixin, TimestampMixin, Base):
    """作业班组。楼层与管辖区域来自仓库档案，班组长是本组成员。"""

    __tablename__ = "wms_master_data_team"

    code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, comment="班组编码")
    name: Mapped[str] = mapped_column(String(100), nullable=False, comment="班组名称")
    function_type: Mapped[str] = mapped_column(
        String(32), default="other", nullable=False,
        comment="receiving/putaway/picking/sorting/checking/shipping/internal_ops/other",
    )
    leader_staff_id: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, comment="班组长 staff.id"
    )
    status: Mapped[int] = mapped_column(
        Integer, default=1, nullable=False, comment="状态: 0=停用 1=启用"
    )
    floor_no: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, comment="作业楼层，取自库区 floor_no"
    )
    dispatch_limit_default: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, comment="组级在办上限默认 1-20，空继承仓级"
    )
    remark: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)


class WmsStaff(IDMixin, TimestampMixin, Base):
    """仓库作业人员档案。user_id 为空即临时工，不产生登录能力。"""

    __tablename__ = "wms_master_data_staff"
    __table_args__ = (
        Index("ix_wms_staff_team_status", "team_id", "status"),
    )

    code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, comment="工号")
    name: Mapped[str] = mapped_column(String(100), nullable=False, comment="姓名")
    phone: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    role: Mapped[Optional[str]] = mapped_column(String(32), nullable=True, comment="岗位角色，用户中心同步")
    user_id: Mapped[Optional[int]] = mapped_column(
        Integer, unique=True, nullable=True, index=True,
        comment="绑定的 sys_user.id，空=临时工",
    )
    team_id: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, comment="所属班组 id"
    )
    status: Mapped[int] = mapped_column(
        Integer, default=1, nullable=False, comment="状态: 0=不在岗 1=在岗"
    )
    left_pending_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True, comment="待离职时间，有值时仍在岗"
    )
    left_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True, comment="离职时间，终态不可逆"
    )
    quality_cert: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False, comment="质检持证: 0=未持证 1=持证"
    )
    quality_team: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, comment="持证时的质检组")
    remark: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)


class WmsTeamZone(IDMixin, TimestampMixin, Base):
    """班组管辖区域。一区多组合法，不按区域做唯一约束。"""

    __tablename__ = "wms_master_data_team_zone"
    __table_args__ = (
        UniqueConstraint("team_id", "zone_id", name="uq_team_zone"),
    )

    team_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    zone_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)


class WmsStaffSkill(IDMixin, TimestampMixin, Base):
    """人员可做的工序码，按码存储，字典外的码原样保留。"""

    __tablename__ = "wms_master_data_staff_skill"
    __table_args__ = (
        UniqueConstraint("staff_id", "process_code", name="uq_staff_skill"),
    )

    staff_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    process_code: Mapped[str] = mapped_column(String(32), nullable=False)


class WmsStaffCert(IDMixin, TimestampMixin, Base):
    """人员持证与到期日，到期只用于显示与筛选。"""

    __tablename__ = "wms_master_data_staff_cert"
    __table_args__ = (
        UniqueConstraint("staff_id", "cert_type", name="uq_staff_cert"),
    )

    staff_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    cert_type: Mapped[str] = mapped_column(String(32), nullable=False, comment="如 forklift/quality_inspector")
    expire_on: Mapped[Optional[date]] = mapped_column(Date, nullable=True)


class WmsStaffLog(IDMixin, TimestampMixin, Base):
    """人员操作与归属记录，kind=team 的每行是一条归属变更。"""

    __tablename__ = "wms_master_data_staff_log"
    __table_args__ = (
        Index("ix_wms_staff_log_staff_time", "staff_id", "occurred_at"),
    )

    staff_id: Mapped[int] = mapped_column(Integer, nullable=False)
    kind: Mapped[str] = mapped_column(String(16), nullable=False, comment="team/skill/cert/quality/leave")
    from_team_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    to_team_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    reason: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    operator_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
