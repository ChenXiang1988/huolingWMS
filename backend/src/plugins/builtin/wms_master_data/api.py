"""主数据域路由。

字段分组在两个 Pydantic 模型上表达，不用字段级动态校验：
``SkuBaseIn`` 是货主能写的，``SkuStorageIn`` 是仓库能写的，两组不重叠。
「这个字段谁能改」应该是看代码就知道的事，不该等到运行时才判定。
"""
import hashlib
import secrets
from datetime import datetime
from decimal import Decimal
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.deps import get_current_user, require_permission
from src.core.exceptions import NotFoundException, ValidationException, success_response
from src.db import get_db
from src.models import User
from src.plugins.builtin.wms_master_data import models as m
from src.plugins.builtin.wms_master_data.service import (
    affected_members,
    bulk_transfer_team,
    create_owner,
    create_staff,
    create_team,
    delete_team as remove_team,
    finish_leave,
    get_staff_by_user,
    join_team,
    leave_team,
    list_staffs as query_staffs,
    list_teams as query_teams,
    mark_leave_pending,
    next_code,
    set_staff_certs,
    set_staff_skills,
    set_team_leader,
    toggle_team,
    transfer_team,
    update_staff,
    update_team,
    zone_coverage,
)

router = APIRouter(prefix="/wms-master-data", tags=["主数据"])


# ── 登录落点 ─────────────────────────────────────────


@router.get("/me/portal", summary="当前账号是否货主")
async def me_portal(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    """不挂 require_permission——每个登录用户都要调它，包括还没有业务权限的子账号。"""
    binding = (
        await db.execute(
            select(m.WmsUserOwner).where(
                m.WmsUserOwner.user_id == user.id, m.WmsUserOwner.status == 1
            )
        )
    ).scalars().first()
    return success_response(data={"is_owner": binding is not None})


class OwnerLoginIn(BaseModel):
    username: str
    password: str


@router.post("/owner-login", summary="货主门户登录")
async def owner_login(
    payload: OwnerLoginIn,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """货主门户的独立登录入口。

    不复用基座 ``/auth/login``：那个接口对任何合法账号发 token，然后由前端判断该去
    哪个界面。两个端要真正分开，就得在登录这一步就判身份——不匹配直接拒，而不是
    "先登录成功再送回去"。

    本接口只接受绑定了货主的账号；员工账号走后台登录，两边互不通用。
    """
    from src.core.security import create_access_token, create_refresh_token, verify_password

    user = (
        await db.execute(
            select(User).where(
                User.username == payload.username, User.deleted_at.is_(None)
            )
        )
    ).scalars().first()

    # 用户不存在与密码错误给同一个提示，避免account枚举
    if user is None or not verify_password(payload.password, user.password):
        raise ValidationException("用户名或密码错误")
    if user.status != 1:
        raise ValidationException("账号已停用，请联系货主主账号")

    binding = (
        await db.execute(
            select(m.WmsUserOwner).where(
                m.WmsUserOwner.user_id == user.id, m.WmsUserOwner.status == 1
            )
        )
    ).scalars().first()
    if binding is None:
        raise ValidationException("该账号不是货主方账号，请从管理后台登录")

    owner = (
        await db.execute(select(m.WmsOwner).where(m.WmsOwner.id == binding.owner_id))
    ).scalars().first()
    if owner is None or owner.status != 1:
        raise ValidationException("所属货主已停用")

    return success_response(
        data={
            "access_token": create_access_token(
                user.id, extra={"username": user.username}
            ),
            "token_type": "bearer",
            "refresh_token": create_refresh_token(user.id),
            "owner_id": owner.id,
            "owner_name": owner.name,
            "is_primary": binding.is_primary,
        }
    )


# ── 仓库配置 ─────────────────────────────────────────


class WarehouseIn(BaseModel):
    name: str
    topology: str = Field("FLAT", pattern="^(FLAT|MULTI_FLOOR|ASRS)$")


@router.get("/warehouse", summary="仓库配置")
async def get_warehouse(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permission("wms_master_data:warehouse:edit"))],
):
    row = (await db.execute(select(m.WmsWarehouse))).scalars().first()
    if row is None:
        return success_response(data=None)
    return success_response(
        data={"id": row.id, "code": row.code, "name": row.name, "topology": row.topology}
    )


@router.put("/warehouse", summary="保存仓库配置")
async def save_warehouse(
    payload: WarehouseIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permission("wms_master_data:warehouse:edit"))],
):
    row = (await db.execute(select(m.WmsWarehouse))).scalars().first()
    if row is None:
        row = m.WmsWarehouse(code="MAIN", name=payload.name, topology=payload.topology)
        db.add(row)
    else:
        row.name = payload.name
        row.topology = payload.topology
    await db.commit()
    return success_response(data={"id": row.id, "topology": row.topology})


# ── 库区 ─────────────────────────────────────────────


class ZoneIn(BaseModel):
    code: str
    name: str
    zone_type: str = "storage"
    temp_zone: str = "ambient"
    floor_no: int = 1


@router.get("/zones", summary="库区列表")
async def list_zones(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permission("wms_master_data:location:list"))],
):
    rows = (await db.execute(select(m.WmsZone).order_by(m.WmsZone.code))).scalars().all()
    return success_response(
        data=[
            {
                "id": r.id,
                "code": r.code,
                "name": r.name,
                "zone_type": r.zone_type,
                "temp_zone": r.temp_zone,
                "floor_no": r.floor_no,
            }
            for r in rows
        ]
    )


@router.post("/zones", summary="新建库区")
async def create_zone(
    payload: ZoneIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permission("wms_master_data:location:create"))],
):
    wh = (await db.execute(select(m.WmsWarehouse))).scalars().first()
    if wh is None:
        raise ValidationException("请先完成仓库配置")

    row = m.WmsZone(
        warehouse_id=wh.id,
        code=payload.code,
        name=payload.name,
        zone_type=payload.zone_type,
        temp_zone=payload.temp_zone,
        floor_no=payload.floor_no,
    )
    db.add(row)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise ValidationException(f"库区编码 {payload.code} 已存在") from exc
    return success_response(data={"id": row.id})


# ── 库位 ─────────────────────────────────────────────


class LocationIn(BaseModel):
    zone_id: int
    code: str
    owner_id: Optional[int] = None
    location_type: str = "storage"
    temp_zone: Optional[str] = None
    floor_no: Optional[int] = None
    aisle: Optional[str] = None
    rack: Optional[str] = None
    level: Optional[str] = None
    bin: Optional[str] = None
    capacity: Decimal = Decimal("0")
    replenish_min: Optional[Decimal] = None
    replenish_max: Optional[Decimal] = None


def _location_dict(r: m.WmsLocation) -> dict:
    return {
        "id": r.id,
        "zone_id": r.zone_id,
        "code": r.code,
        "owner_id": r.owner_id,
        "location_type": r.location_type,
        "temp_zone": r.temp_zone,
        "floor_no": r.floor_no,
        "aisle": r.aisle,
        "rack": r.rack,
        "level": r.level,
        "bin": r.bin,
        "capacity": str(r.capacity),
        "replenish_min": str(r.replenish_min) if r.replenish_min is not None else None,
        "replenish_max": str(r.replenish_max) if r.replenish_max is not None else None,
        "status": r.status,
    }


@router.get("/locations", summary="库位列表")
async def list_locations(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permission("wms_master_data:location:list"))],
    zone_id: Optional[int] = Query(None),
    location_type: Optional[str] = Query(None),
    temp_zone: Optional[str] = Query(None),
    keyword: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=500),
):
    cond = []
    if zone_id:
        cond.append(m.WmsLocation.zone_id == zone_id)
    if location_type:
        cond.append(m.WmsLocation.location_type == location_type)
    if temp_zone:
        cond.append(m.WmsLocation.temp_zone == temp_zone)
    if keyword:
        cond.append(m.WmsLocation.code.like(f"%{keyword}%"))

    base = select(m.WmsLocation).where(*cond)
    total = (
        await db.execute(select(func.count()).select_from(base.subquery()))
    ).scalar() or 0
    rows = (
        await db.execute(
            base.order_by(m.WmsLocation.code)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).scalars().all()
    return success_response(
        data={
            "total": total,
            "page": page,
            "page_size": page_size,
            "items": [_location_dict(r) for r in rows],
        }
    )


@router.post("/locations", summary="新建库位")
async def create_location(
    payload: LocationIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permission("wms_master_data:location:create"))],
):
    zone = (
        await db.execute(select(m.WmsZone).where(m.WmsZone.id == payload.zone_id))
    ).scalars().first()
    if zone is None:
        raise ValidationException("库区不存在")

    _check_location_shape(await _topology(db), payload)

    # 温区与楼层默认继承库区，显式传值时以传的为准
    row = m.WmsLocation(
        zone_id=payload.zone_id,
        code=payload.code,
        owner_id=payload.owner_id,
        location_type=payload.location_type,
        temp_zone=payload.temp_zone or zone.temp_zone,
        floor_no=payload.floor_no or zone.floor_no,
        aisle=payload.aisle,
        rack=payload.rack,
        level=payload.level,
        bin=payload.bin,
        capacity=payload.capacity,
        replenish_min=payload.replenish_min,
        replenish_max=payload.replenish_max,
    )
    db.add(row)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise ValidationException(f"库位编码 {payload.code} 已存在") from exc
    return success_response(data={"id": row.id, "code": row.code})


_TOPOLOGY_RULES = {
    # 仓型 → 必填坐标，以及禁止出现的坐标
    "FLAT": {"required": (), "forbidden": ("level",)},
    "MULTI_FLOOR": {"required": (), "forbidden": ()},
    "ASRS": {"required": ("aisle", "rack", "level"), "forbidden": ()},
}


def _check_location_shape(topology: str, payload: "LocationIn") -> None:
    """坐标字段按仓型解释，组合不合法直接拒。

    ``FLAT`` 是单层平面仓，``level`` 没有意义；``ASRS`` 是货架到顶的立库，
    没有巷-架-层就定位不到具体货格。放任这些组合入库，选位时会算出一个
    不存在的空间域。
    """
    rule = _TOPOLOGY_RULES.get(topology)
    if rule is None:
        raise ValidationException(f"未知仓型 {topology}")

    for field in rule["required"]:
        if not getattr(payload, field, None):
            raise ValidationException(f"{topology} 仓型的库位必须填写 {field}")

    for field in rule["forbidden"]:
        if getattr(payload, field, None):
            raise ValidationException(f"{topology} 仓型的库位不应填写 {field}")

    if topology == "FLAT" and (payload.floor_no or 1) != 1:
        raise ValidationException("FLAT 仓型只有一层，floor_no 必须为 1")


async def _topology(db: AsyncSession) -> str:
    wh = (await db.execute(select(m.WmsWarehouse))).scalars().first()
    if wh is None:
        raise ValidationException("请先完成仓库配置")
    return wh.topology


@router.put("/locations/{location_id}", summary="编辑库位")
async def update_location(
    location_id: int,
    payload: LocationIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permission("wms_master_data:location:edit"))],
):
    row = (
        await db.execute(select(m.WmsLocation).where(m.WmsLocation.id == location_id))
    ).scalars().first()
    if row is None:
        raise NotFoundException("库位不存在")

    for field in ("owner_id", "location_type", "capacity", "replenish_min",
                  "replenish_max", "aisle", "rack", "level", "bin"):
        value = getattr(payload, field)
        if value is not None:
            setattr(row, field, value)
    if payload.temp_zone:
        row.temp_zone = payload.temp_zone

    _check_location_shape(await _topology(db), row)

    await db.commit()
    return success_response(data={"id": row.id})


class BatchLocationIn(BaseModel):
    """批量建库位：给前缀与数量，编码按序号拼接。

    一次最多 200 条——超过这个量说明该换导入文件了，而不是让人在弹窗里数。
    """

    zone_id: int
    prefix: str = Field(..., description="编码前缀，如 F2-A-")
    start: int = 1
    count: int = Field(..., ge=1, le=200)
    width: int = Field(2, ge=1, le=6, description="序号补零位数")
    location_type: str = "storage"
    temp_zone: Optional[str] = None
    floor_no: Optional[int] = None
    aisle: Optional[str] = None
    rack: Optional[str] = None
    level: Optional[str] = None
    bin: Optional[str] = None
    capacity: Decimal = Decimal("0")
    replenish_min: Optional[Decimal] = None
    replenish_max: Optional[Decimal] = None


@router.post("/locations/batch", summary="批量新建库位")
async def batch_create_locations(
    payload: BatchLocationIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permission("wms_master_data:location:create"))],
):
    zone = (
        await db.execute(select(m.WmsZone).where(m.WmsZone.id == payload.zone_id))
    ).scalars().first()
    if zone is None:
        raise ValidationException("库区不存在")

    topology = await _topology(db)
    probe = LocationIn(
        zone_id=payload.zone_id,
        code=payload.prefix,
        location_type=payload.location_type,
        temp_zone=payload.temp_zone,
        floor_no=payload.floor_no,
        aisle=payload.aisle,
        rack=payload.rack,
        level=payload.level,
        bin=payload.bin,
        capacity=payload.capacity,
    )
    _check_location_shape(topology, probe)

    codes = [
        f"{payload.prefix}{payload.start + i:0{payload.width}d}"
        for i in range(payload.count)
    ]
    existing = set(
        (
            await db.execute(
                select(m.WmsLocation.code).where(m.WmsLocation.code.in_(codes))
            )
        ).scalars().all()
    )

    created: list[str] = []
    for code in codes:
        if code in existing:
            continue
        db.add(
            m.WmsLocation(
                zone_id=payload.zone_id,
                code=code,
                location_type=payload.location_type,
                temp_zone=payload.temp_zone or zone.temp_zone,
                floor_no=payload.floor_no or zone.floor_no,
                aisle=payload.aisle,
                rack=payload.rack,
                level=payload.level,
                bin=payload.bin,
                capacity=payload.capacity,
                replenish_min=payload.replenish_min,
                replenish_max=payload.replenish_max,
            )
        )
        created.append(code)

    await db.commit()
    return success_response(
        data={
            "created": len(created),
            "skipped": len(codes) - len(created),
            "codes": created,
        }
    )


# ── 货主 ─────────────────────────────────────────────


class OwnerIn(BaseModel):
    code: str = Field(..., max_length=64)
    name: str
    contact: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    sync_enabled: bool = False
    with_primary_account: bool = True


@router.get("/owners", summary="货主列表")
async def list_owners(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permission("wms_master_data:owner:list"))],
    keyword: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
):
    cond = []
    if keyword:
        cond.append(
            (m.WmsOwner.code.like(f"%{keyword}%")) | (m.WmsOwner.name.like(f"%{keyword}%"))
        )
    base = select(m.WmsOwner).where(*cond)
    total = (
        await db.execute(select(func.count()).select_from(base.subquery()))
    ).scalar() or 0
    rows = (
        await db.execute(
            base.order_by(m.WmsOwner.id).offset((page - 1) * page_size).limit(page_size)
        )
    ).scalars().all()
    return success_response(
        data={
            "total": total,
            "page": page,
            "page_size": page_size,
            "items": [
                {
                    "id": r.id,
                    "code": r.code,
                    "name": r.name,
                    "contact": r.contact,
                    "phone": r.phone,
                    "sync_enabled": r.sync_enabled,
                    "primary_user_id": r.primary_user_id,
                    "status": r.status,
                }
                for r in rows
            ],
        }
    )


@router.post("/owners", summary="新建货主")
async def post_owner(
    payload: OwnerIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permission("wms_master_data:owner:create"))],
):
    try:
        owner, initial_pwd = await create_owner(
            db,
            code=payload.code,
            name=payload.name,
            contact=payload.contact,
            phone=payload.phone,
            address=payload.address,
            sync_enabled=payload.sync_enabled,
            with_primary_account=payload.with_primary_account,
        )
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise ValidationException(f"货主编码 {payload.code} 或主账号用户名已被占用") from exc

    return success_response(
        data={
            "id": owner.id,
            "code": owner.code,
            "username": payload.code.lower() if initial_pwd else None,
            "initial_password": initial_pwd,
        }
    )


@router.put("/owners/{owner_id}", summary="编辑货主")
async def update_owner(
    owner_id: int,
    payload: OwnerIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permission("wms_master_data:owner:edit"))],
):
    row = (
        await db.execute(select(m.WmsOwner).where(m.WmsOwner.id == owner_id))
    ).scalars().first()
    if row is None:
        raise NotFoundException("货主不存在")
    row.name = payload.name
    row.contact = payload.contact
    row.phone = payload.phone
    row.address = payload.address
    row.sync_enabled = payload.sync_enabled
    await db.commit()
    return success_response(data={"id": row.id})


@router.post("/owners/{owner_id}/toggle", summary="启用或停用货主")
async def toggle_owner(
    owner_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permission("wms_master_data:owner:edit"))],
    enabled: bool = Query(...),
):
    row = (
        await db.execute(select(m.WmsOwner).where(m.WmsOwner.id == owner_id))
    ).scalars().first()
    if row is None:
        raise NotFoundException("货主不存在")
    row.status = 1 if enabled else 0
    await db.commit()
    return success_response(data={"id": row.id, "status": row.status})


# ── 商品 ─────────────────────────────────────────────


class SkuBaseIn(BaseModel):
    """货主可写的字段：这是什么货。"""

    owner_sku_code: str
    name: str
    spec: Optional[str] = None
    unit_code: str = "件"
    category: Optional[str] = None
    weight: Optional[Decimal] = None
    volume: Optional[Decimal] = None
    temp_requirement: str = "ambient"
    lot_required: bool = False
    expiry_warn_days: int = 30
    qty_per_box: Decimal = Decimal("1")


class SkuStorageIn(BaseModel):
    """仓库可写的字段：这货怎么存。"""

    default_zone_id: Optional[int] = None
    qty_per_pallet: Optional[Decimal] = None
    putaway_note: Optional[str] = None


class SkuCreateIn(SkuBaseIn):
    owner_id: int


def _sku_dict(r: m.WmsSku) -> dict:
    return {
        "id": r.id,
        "owner_id": r.owner_id,
        "code": r.code,
        "owner_sku_code": r.owner_sku_code,
        "name": r.name,
        "spec": r.spec,
        "unit_code": r.unit_code,
        "category": r.category,
        "weight": str(r.weight) if r.weight is not None else None,
        "volume": str(r.volume) if r.volume is not None else None,
        "temp_requirement": r.temp_requirement,
        "lot_required": r.lot_required,
        "expiry_warn_days": r.expiry_warn_days,
        "qty_per_box": str(r.qty_per_box),
        "default_zone_id": r.default_zone_id,
        "qty_per_pallet": str(r.qty_per_pallet) if r.qty_per_pallet is not None else None,
        "putaway_note": r.putaway_note,
        "status": r.status,
    }


@router.get("/skus", summary="商品列表")
async def list_skus(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permission("wms_master_data:sku:list"))],
    owner_id: Optional[int] = Query(None),
    keyword: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
):
    cond = []
    if owner_id:
        cond.append(m.WmsSku.owner_id == owner_id)
    if keyword:
        cond.append(
            (m.WmsSku.code.like(f"%{keyword}%"))
            | (m.WmsSku.name.like(f"%{keyword}%"))
            | (m.WmsSku.owner_sku_code.like(f"%{keyword}%"))
        )
    base = select(m.WmsSku).where(*cond)
    total = (
        await db.execute(select(func.count()).select_from(base.subquery()))
    ).scalar() or 0
    rows = (
        await db.execute(
            base.order_by(m.WmsSku.id).offset((page - 1) * page_size).limit(page_size)
        )
    ).scalars().all()
    return success_response(
        data={
            "total": total,
            "page": page,
            "page_size": page_size,
            "items": [_sku_dict(r) for r in rows],
        }
    )


@router.post("/skus", summary="新建商品")
async def create_sku(
    payload: SkuCreateIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permission("wms_master_data:sku:create"))],
):
    owner = (
        await db.execute(select(m.WmsOwner).where(m.WmsOwner.id == payload.owner_id))
    ).scalars().first()
    if owner is None:
        raise ValidationException("货主不存在")

    code = await next_code(db, "SKU", "", 6)
    row = m.WmsSku(
        owner_id=payload.owner_id,
        code=code,
        owner_sku_code=payload.owner_sku_code,
        name=payload.name,
        spec=payload.spec,
        unit_code=payload.unit_code,
        category=payload.category,
        weight=payload.weight,
        volume=payload.volume,
        temp_requirement=payload.temp_requirement,
        lot_required=payload.lot_required,
        expiry_warn_days=payload.expiry_warn_days,
        qty_per_box=payload.qty_per_box,
        status=1,
    )
    db.add(row)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise ValidationException(
            f"该货主下货主编码 {payload.owner_sku_code} 已存在"
        ) from exc
    return success_response(data={"id": row.id, "code": row.code})


@router.put("/skus/{sku_id}", summary="编辑商品基础信息")
async def update_sku(
    sku_id: int,
    payload: SkuBaseIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permission("wms_master_data:sku:edit"))],
):
    row = (await db.execute(select(m.WmsSku).where(m.WmsSku.id == sku_id))).scalars().first()
    if row is None:
        raise NotFoundException("商品不存在")
    for field in (
        "owner_sku_code", "name", "spec", "unit_code", "category", "weight",
        "volume", "temp_requirement", "lot_required", "expiry_warn_days", "qty_per_box",
    ):
        setattr(row, field, getattr(payload, field))
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise ValidationException("货主编码冲突") from exc
    return success_response(data={"id": row.id, "code": row.code})


@router.put("/skus/{sku_id}/storage", summary="编辑商品存储要求")
async def update_sku_storage(
    sku_id: int,
    payload: SkuStorageIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permission("wms_master_data:sku:configure"))],
):
    row = (await db.execute(select(m.WmsSku).where(m.WmsSku.id == sku_id))).scalars().first()
    if row is None:
        raise NotFoundException("商品不存在")
    row.default_zone_id = payload.default_zone_id
    row.qty_per_pallet = payload.qty_per_pallet
    row.putaway_note = payload.putaway_note
    await db.commit()
    return success_response(data={"id": row.id})


# ── 条码 ─────────────────────────────────────────────


class BarcodeIn(BaseModel):
    barcode: str
    is_primary: bool = False


@router.get("/skus/{sku_id}/barcodes", summary="商品条码列表")
async def list_barcodes(
    sku_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permission("wms_master_data:sku:list"))],
):
    rows = (
        await db.execute(
            select(m.WmsBarcode).where(m.WmsBarcode.sku_id == sku_id)
        )
    ).scalars().all()
    return success_response(
        data=[{"id": r.id, "barcode": r.barcode, "is_primary": r.is_primary} for r in rows]
    )


@router.post("/skus/{sku_id}/barcodes", summary="新增条码")
async def create_barcode(
    sku_id: int,
    payload: BarcodeIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permission("wms_master_data:sku:edit"))],
):
    sku = (await db.execute(select(m.WmsSku).where(m.WmsSku.id == sku_id))).scalars().first()
    if sku is None:
        raise NotFoundException("商品不存在")
    row = m.WmsBarcode(
        owner_id=sku.owner_id, sku_id=sku_id, barcode=payload.barcode,
        is_primary=payload.is_primary,
    )
    db.add(row)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise ValidationException("该条码已被本货主占用") from exc
    return success_response(data={"id": row.id})


@router.delete("/barcodes/{barcode_id}", summary="删除条码")
async def delete_barcode(
    barcode_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permission("wms_master_data:sku:edit"))],
):
    row = (
        await db.execute(select(m.WmsBarcode).where(m.WmsBarcode.id == barcode_id))
    ).scalars().first()
    if row is None:
        raise NotFoundException("条码不存在")
    await db.delete(row)
    await db.commit()
    return success_response(data={"id": barcode_id})


# ── 合作方 ───────────────────────────────────────────


class PartnerIn(BaseModel):
    owner_id: int
    code: str
    name: str
    partner_type: str = "supplier"
    contact: Optional[str] = None
    phone: Optional[str] = None


@router.get("/partners", summary="合作方列表")
async def list_partners(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permission("wms_master_data:partner:list"))],
    owner_id: Optional[int] = Query(None),
    partner_type: Optional[str] = Query(None),
):
    cond = []
    if owner_id:
        cond.append(m.WmsPartner.owner_id == owner_id)
    if partner_type:
        cond.append(m.WmsPartner.partner_type == partner_type)
    rows = (
        await db.execute(select(m.WmsPartner).where(*cond).order_by(m.WmsPartner.id))
    ).scalars().all()
    return success_response(
        data=[
            {
                "id": r.id,
                "owner_id": r.owner_id,
                "code": r.code,
                "name": r.name,
                "partner_type": r.partner_type,
                "contact": r.contact,
                "phone": r.phone,
            }
            for r in rows
        ]
    )


@router.post("/partners", summary="新建合作方")
async def create_partner(
    payload: PartnerIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permission("wms_master_data:partner:create"))],
):
    row = m.WmsPartner(**payload.model_dump())
    db.add(row)
    await db.commit()
    return success_response(data={"id": row.id})


# ── API 凭证 ─────────────────────────────────────────


class ApiKeyIn(BaseModel):
    owner_id: int
    name: str


def _hash_key(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


@router.get("/apikeys", summary="API 凭证列表")
async def list_apikeys(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permission("wms_master_data:apikey:list"))],
    owner_id: Optional[int] = Query(None),
):
    cond = []
    if owner_id:
        cond.append(m.WmsApiKey.owner_id == owner_id)
    rows = (await db.execute(select(m.WmsApiKey).where(*cond))).scalars().all()
    return success_response(
        data=[
            {
                "id": r.id,
                "owner_id": r.owner_id,
                "name": r.name,
                "key_prefix": r.key_prefix,
                "status": r.status,
            }
            for r in rows
        ]
    )


@router.post("/apikeys", summary="签发 API 凭证")
async def create_apikey(
    payload: ApiKeyIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permission("wms_master_data:apikey:create"))],
):
    raw = "wms_live_" + secrets.token_urlsafe(32)
    row = m.WmsApiKey(
        owner_id=payload.owner_id,
        name=payload.name,
        key_prefix=raw[:16],
        key_hash=_hash_key(raw),
        status=1,
    )
    db.add(row)
    await db.commit()
    # 明文只在签发时返回这一次，库里只存哈希
    return success_response(data={"id": row.id, "api_key": raw, "key_prefix": row.key_prefix})


@router.post("/apikeys/{key_id}/rotate", summary="重置 API 凭证")
async def rotate_apikey(
    key_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permission("wms_master_data:apikey:create"))],
):
    """换一把新密钥并让旧的立即失效。

    不做"新旧并存一段过渡期"——货主换密钥是低频动作，并存只会让旧密钥在某处
    继续被用着而没人清理。
    """
    row = (
        await db.execute(select(m.WmsApiKey).where(m.WmsApiKey.id == key_id))
    ).scalars().first()
    if row is None:
        raise NotFoundException("凭证不存在")

    raw = "wms_live_" + secrets.token_urlsafe(32)
    row.key_prefix = raw[:16]
    row.key_hash = _hash_key(raw)
    await db.commit()
    return success_response(data={"id": row.id, "api_key": raw, "key_prefix": row.key_prefix})


# ── 职能班组 ─────────────────────────────────────────


def _dt(value: Optional[str]) -> Optional[datetime]:
    return datetime.fromisoformat(value) if value else None


class TeamIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=20)
    function_type: str = Field(
        "other",
        pattern=r"^(receiving|putaway|picking|sorting|checking|shipping|internal_ops|other)$",
    )
    leader_staff_id: int
    floor_no: int
    zone_ids: list[int] = Field(..., min_length=1)
    dispatch_limit_default: Optional[int] = Field(None, ge=1, le=20)
    remark: Optional[str] = None


@router.get("/teams", summary="班组列表")
async def list_teams_route(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permission("wms_master_data:team:list"))],
    status: Optional[int] = Query(None),
    keyword: Optional[str] = Query(None),
    leader_name: Optional[str] = Query(None),
    floor_no: Optional[int] = Query(None),
    process_code: Optional[str] = Query(None),
    zone_id: Optional[int] = Query(None),
    updated_from: Optional[str] = Query(None),
    updated_to: Optional[str] = Query(None),
):
    return success_response(data=await query_teams(
        db, status=status, keyword=keyword, leader_name=leader_name,
        floor_no=floor_no, process_code=process_code, zone_id=zone_id,
        updated_from=_dt(updated_from), updated_to=_dt(updated_to),
    ))


@router.get("/teams/coverage", summary="区域覆盖读数")
async def team_coverage(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permission("wms_master_data:team:list"))],
):
    return success_response(data=await zone_coverage(db))


@router.post("/teams", summary="新建班组")
async def post_team(
    payload: TeamIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permission("wms_master_data:team:create"))],
):
    try:
        team = await create_team(db, **payload.model_dump())
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise ValidationException("班组编号或名称冲突") from exc
    return success_response(data={"id": team.id, "code": team.code})


@router.put("/teams/{team_id}", summary="编辑班组")
async def put_team(
    team_id: int,
    payload: TeamIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permission("wms_master_data:team:edit"))],
):
    team = await update_team(db, team_id, **payload.model_dump())
    await db.commit()
    return success_response(data={"id": team.id})


@router.delete("/teams/{team_id}", summary="删除班组")
async def delete_team_route(
    team_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permission("wms_master_data:team:delete"))],
):
    await remove_team(db, team_id)
    await db.commit()
    return success_response(data={"id": team_id})


class LeaderIn(BaseModel):
    staff_id: Optional[int] = None


@router.put("/teams/{team_id}/leader", summary="指定或清空班组长")
async def put_team_leader(
    team_id: int,
    payload: LeaderIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permission("wms_master_data:team:edit"))],
):
    team = await set_team_leader(db, team_id, payload.staff_id)
    await db.commit()
    return success_response(
        data={"id": team.id, "leader_staff_id": team.leader_staff_id}
    )


@router.post("/teams/{team_id}/toggle", summary="启用或停用班组")
async def toggle_team_status(
    team_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permission("wms_master_data:team:edit"))],
    enabled: bool = Query(...),
):
    team = await toggle_team(db, team_id, enabled)
    members = await affected_members(db, team_id) if not enabled else []
    await db.commit()
    return success_response(data={
        "id": team.id, "status": team.status, "affected_staff_ids": members,
    })


# ── 人员档案 ─────────────────────────────────────────


class StaffIn(BaseModel):
    code: str = Field(..., max_length=64)
    user_id: int
    role: Optional[str] = Field(None, max_length=32)


class StaffUpdateIn(BaseModel):
    status: int = Field(1, ge=0, le=1)
    role: Optional[str] = Field(None, max_length=32)
    quality_cert: Optional[int] = Field(None, ge=0, le=1)
    quality_team: Optional[str] = Field(None, max_length=64)


class TeamAssignIn(BaseModel):
    team_id: int


class BulkTeamIn(BaseModel):
    staff_ids: list[int]
    team_id: Optional[int] = None


class SkillsIn(BaseModel):
    process_codes: list[str]


class CertIn(BaseModel):
    cert_type: str = Field(..., max_length=32)
    expire_on: Optional[str] = None


class CertsIn(BaseModel):
    certs: list[CertIn]


@router.get("/staffs", summary="人员列表")
async def list_staffs_route(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permission("wms_master_data:staff:list"))],
    team_id: Optional[int] = Query(None),
    status: Optional[int] = Query(None),
    keyword: Optional[str] = Query(None),
    role: Optional[str] = Query(None),
    leader_flag: Optional[str] = Query(None),
    process_code: Optional[str] = Query(None),
    cert_type: Optional[str] = Query(None),
    config_state: Optional[str] = Query(None),
    employment_state: Optional[str] = Query(None),
    bound_state: Optional[str] = Query(None),
    cert_expiry: Optional[str] = Query(None),
    last_op_from: Optional[str] = Query(None),
    last_op_to: Optional[str] = Query(None),
):
    return success_response(data=await query_staffs(
        db, team_id=team_id, status=status, keyword=keyword, role=role,
        leader_flag=leader_flag, process_code=process_code, cert_type=cert_type,
        config_state=config_state, employment_state=employment_state,
        bound_state=bound_state, cert_expiry=cert_expiry,
        last_op_from=_dt(last_op_from), last_op_to=_dt(last_op_to),
    ))


@router.get("/staffs/by-user/{user_id}", summary="按账号查在职人员")
async def get_staff_of_user(
    user_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permission("wms_master_data:staff:list"))],
):
    return success_response(data=await get_staff_by_user(db, user_id))


@router.post("/staffs", summary="新建人员档案")
async def post_staff(
    payload: StaffIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permission("wms_master_data:staff:create"))],
):
    try:
        staff = await create_staff(db, **payload.model_dump())
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise ValidationException(f"工号 {payload.code} 已占用") from exc
    return success_response(data={"id": staff.id, "code": staff.code})


@router.put("/staffs/{staff_id}", summary="编辑人员档案")
async def put_staff(
    staff_id: int,
    payload: StaffUpdateIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permission("wms_master_data:staff:edit"))],
):
    staff = await update_staff(db, staff_id, **payload.model_dump())
    await db.commit()
    return success_response(data={"id": staff.id, "status": staff.status})


@router.put("/staffs/{staff_id}/skills", summary="维护可做工序")
async def put_staff_skills(
    staff_id: int,
    payload: SkillsIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permission("wms_master_data:staff:skill"))],
):
    staff = await set_staff_skills(db, staff_id, payload.process_codes)
    await db.commit()
    return success_response(data={"id": staff.id, "skills": payload.process_codes})


@router.put("/staffs/{staff_id}/certs", summary="维护认证")
async def put_staff_certs(
    staff_id: int,
    payload: CertsIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permission("wms_master_data:staff:cert"))],
):
    certs = [
        {"cert_type": c.cert_type, "expire_on": _dt(c.expire_on).date() if c.expire_on else None}
        for c in payload.certs
    ]
    staff = await set_staff_certs(db, staff_id, certs)
    await db.commit()
    return success_response(data={"id": staff.id, "certs": certs})


@router.get("/staffs/{staff_id}/logs", summary="人员最近记录")
async def staff_logs(
    staff_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permission("wms_master_data:staff:list"))],
    limit: int = Query(10, ge=1, le=50),
):
    rows = (await db.execute(
        select(m.WmsStaffLog)
        .where(m.WmsStaffLog.staff_id == staff_id)
        .order_by(m.WmsStaffLog.occurred_at.desc())
        .limit(limit)
    )).scalars().all()
    return success_response(data=[
        {
            "id": r.id,
            "kind": r.kind,
            "from_team_id": r.from_team_id,
            "to_team_id": r.to_team_id,
            "reason": r.reason,
            "operator_id": r.operator_id,
            "occurred_at": r.occurred_at.isoformat(),
        }
        for r in rows
    ])


@router.post("/staffs/bulk-team", summary="批量调组")
async def bulk_staff_team(
    payload: BulkTeamIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permission("wms_master_data:staff:bulk-team"))],
):
    result = await bulk_transfer_team(db, payload.staff_ids, payload.team_id)
    await db.commit()
    return success_response(data=result)


@router.post("/staffs/{staff_id}/leave", summary="确认离职生效")
async def confirm_staff_leave(
    staff_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permission("wms_master_data:staff:leave"))],
):
    staff = await finish_leave(db, staff_id, operator_id=user.id)
    await db.commit()
    return success_response(data={"id": staff.id, "status": staff.status})


@router.post("/staffs/{staff_id}/leave/pending", summary="标记待离职")
async def pending_staff_leave(
    staff_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permission("wms_master_data:staff:leave"))],
):
    staff = await mark_leave_pending(db, staff_id)
    await db.commit()
    return success_response(data={"id": staff.id})


@router.post("/staffs/{staff_id}/team", summary="人员加入班组")
async def join_staff_team(
    staff_id: int,
    payload: TeamAssignIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permission("wms_master_data:staff:edit"))],
):
    staff = await join_team(db, staff_id, payload.team_id)
    await db.commit()
    return success_response(data={"id": staff.id, "team_id": staff.team_id})


@router.put("/staffs/{staff_id}/team", summary="人员调组")
async def transfer_staff_team(
    staff_id: int,
    payload: TeamAssignIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permission("wms_master_data:staff:edit"))],
):
    staff = await transfer_team(db, staff_id, payload.team_id)
    await db.commit()
    return success_response(data={"id": staff.id, "team_id": staff.team_id})


@router.delete("/staffs/{staff_id}/team", summary="人员退出班组")
async def leave_staff_team(
    staff_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permission("wms_master_data:staff:edit"))],
):
    staff = await leave_team(db, staff_id)
    await db.commit()
    return success_response(data={"id": staff.id, "team_id": staff.team_id})
