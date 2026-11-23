"""主数据域的领域服务：取号、建货主、建货主主账号。

取号必须走行锁。三万个单号并发下，"先查后加一"会在两个人同时取号时发出同一个号，
而单号重复在账上无法分辨是哪一单。
"""
from datetime import date, datetime, timedelta
from typing import Optional

from loguru import logger
from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.exceptions import NotFoundException, ValidationException
from src.core.security import hash_password
from src.models import Role, User
from src.models.rbac import user_role
from src.plugins.builtin.wms_master_data.models import (
    WmsOwner,
    WmsSequence,
    WmsStaff,
    WmsStaffCert,
    WmsStaffLog,
    WmsStaffSkill,
    WmsTeam,
    WmsTeamZone,
    WmsUserOwner,
    WmsZone,
)

DEFAULT_OWNER_PASSWORD = "Owner@123456"


async def next_code(db: AsyncSession, prefix: str, period: str = "", width: int = 6) -> str:
    """取下一个编号。``period`` 为空表示全局序列。"""
    row = (
        await db.execute(
            select(WmsSequence)
            .where(WmsSequence.prefix == prefix, WmsSequence.period == period)
            .with_for_update()
        )
    ).scalars().first()

    if row is None:
        row = WmsSequence(prefix=prefix, period=period, current=0)
        db.add(row)
        try:
            async with db.begin_nested():
                await db.flush()
        except IntegrityError:
            row = (
                await db.execute(
                    select(WmsSequence)
                    .where(WmsSequence.prefix == prefix, WmsSequence.period == period)
                    .with_for_update()
                )
            ).scalars().first()
            if row is None:
                raise

    row.current += 1
    await db.flush()
    return f"{prefix}{row.current:0{width}d}"


async def create_owner(
    db: AsyncSession,
    *,
    code: str,
    name: str,
    contact: Optional[str] = None,
    phone: Optional[str] = None,
    address: Optional[str] = None,
    sync_enabled: bool = False,
    with_primary_account: bool = True,
) -> tuple[WmsOwner, Optional[str]]:
    """建货主，可选同时开一个主账号。

    返回 ``(货主, 初始密码)``。主账号的用户名取货主编码，密码仅在这里返回一次。
    """
    owner = WmsOwner(
        code=code,
        name=name,
        contact=contact,
        phone=phone,
        address=address,
        sync_enabled=sync_enabled,
        status=1,
    )
    db.add(owner)
    await db.flush()

    if not with_primary_account:
        return owner, None

    username = code.lower()
    user = User(
        username=username,
        nickname=f"{name}-主账号",
        password=hash_password(DEFAULT_OWNER_PASSWORD),
        status=1,
    )
    db.add(user)
    await db.flush()

    owner.primary_user_id = user.id
    db.add(WmsUserOwner(user_id=user.id, owner_id=owner.id, is_primary=True, status=1))

    role = (
        await db.execute(select(Role).where(Role.code == "wms_owner_admin"))
    ).scalars().first()
    if role is not None:
        await db.execute(user_role.insert().values(user_id=user.id, role_id=role.id))
    else:
        logger.warning("角色 wms_owner_admin 不存在，主账号未绑定角色")

    await db.flush()
    return owner, DEFAULT_OWNER_PASSWORD


async def _get_staff(db: AsyncSession, staff_id: int) -> WmsStaff:
    staff = (
        await db.execute(select(WmsStaff).where(WmsStaff.id == staff_id))
    ).scalars().first()
    if staff is None:
        raise NotFoundException("人员档案不存在")
    return staff


async def _get_team(db: AsyncSession, team_id: int) -> WmsTeam:
    team = (
        await db.execute(select(WmsTeam).where(WmsTeam.id == team_id))
    ).scalars().first()
    if team is None:
        raise NotFoundException("班组不存在")
    return team


async def create_staff(
    db: AsyncSession,
    *,
    code: str,
    user_id: int,
    role: Optional[str] = None,
) -> WmsStaff:
    """建人员档案。账号是人员身份来源，货主账号与重复绑定都拒绝。"""
    user = (
        await db.execute(
            select(User).where(User.id == user_id, User.deleted_at.is_(None))
        )
    ).scalars().first()
    if user is None:
        raise ValidationException("账号不存在或已删除")
    owner_binding = (
        await db.execute(
            select(WmsUserOwner).where(WmsUserOwner.user_id == user_id)
        )
    ).scalars().first()
    if owner_binding is not None:
        raise ValidationException("该账号已绑定货主，只能绑定员工账号")
    existing = (
        await db.execute(select(WmsStaff).where(WmsStaff.user_id == user_id))
    ).scalars().first()
    if existing is not None:
        raise ValidationException("该账号已绑定其他人员")

    staff = WmsStaff(
        code=code, name=user.nickname, phone=user.phone,
        user_id=user_id, role=role, status=1,
    )
    db.add(staff)
    await db.flush()
    return staff


async def _clear_leader(db: AsyncSession, staff_id: int) -> None:
    """成员资格失效时清空其担任的班长字段。"""
    await db.execute(
        update(WmsTeam)
        .where(WmsTeam.leader_staff_id == staff_id)
        .values(leader_staff_id=None)
    )


async def update_staff(
    db: AsyncSession,
    staff_id: int,
    *,
    status: int,
    role: Optional[str] = None,
    quality_cert: Optional[int] = None,
    quality_team: Optional[str] = None,
) -> WmsStaff:
    """编辑 WMS 专有字段与在岗状态；已离职不可复职，离岗时解除班长。"""
    staff = await _get_staff(db, staff_id)
    if staff.left_at is not None and status == 1:
        raise ValidationException("离职为终态，不可改回在岗")
    staff.status = status
    if role is not None:
        staff.role = role
    if quality_cert is not None:
        staff.quality_cert = quality_cert
    if quality_team is not None:
        staff.quality_team = quality_team
    if status == 0 and staff.left_at is None:
        await _clear_leader(db, staff_id)
    await db.flush()
    return staff


async def _write_log(
    db: AsyncSession,
    staff_id: int,
    kind: str,
    *,
    from_team_id: Optional[int] = None,
    to_team_id: Optional[int] = None,
    reason: Optional[str] = None,
    operator_id: Optional[int] = None,
) -> None:
    db.add(WmsStaffLog(
        staff_id=staff_id, kind=kind,
        from_team_id=from_team_id, to_team_id=to_team_id,
        reason=reason, operator_id=operator_id, occurred_at=datetime.now(),
    ))


async def _sync_team_zones(db: AsyncSession, team_id: int, zone_ids: list[int]) -> None:
    await db.execute(delete(WmsTeamZone).where(WmsTeamZone.team_id == team_id))
    for zone_id in zone_ids:
        db.add(WmsTeamZone(team_id=team_id, zone_id=zone_id))


async def set_staff_skills(
    db: AsyncSession, staff_id: int, process_codes: list[str]
) -> WmsStaff:
    """维护可做工序；已归组人员至少保留一项。"""
    staff = await _get_staff(db, staff_id)
    codes = list(dict.fromkeys(c.strip() for c in process_codes if c and c.strip()))
    if staff.team_id is not None and not codes:
        raise ValidationException("已归组人员至少保留一项工序")
    await db.execute(delete(WmsStaffSkill).where(WmsStaffSkill.staff_id == staff_id))
    for code in codes:
        db.add(WmsStaffSkill(staff_id=staff_id, process_code=code))
    await _write_log(db, staff_id, "skill", reason="维护工序")
    await db.flush()
    return staff


async def set_staff_certs(db: AsyncSession, staff_id: int, certs: list[dict]) -> WmsStaff:
    """维护证照，每项含 cert_type 与可选 expire_on。"""
    await _get_staff(db, staff_id)
    await db.execute(delete(WmsStaffCert).where(WmsStaffCert.staff_id == staff_id))
    seen: set[str] = set()
    for cert in certs:
        cert_type = cert.get("cert_type")
        if not cert_type or cert_type in seen:
            continue
        seen.add(cert_type)
        db.add(WmsStaffCert(
            staff_id=staff_id, cert_type=cert_type, expire_on=cert.get("expire_on")
        ))
    await _write_log(db, staff_id, "cert", reason="维护认证")
    await db.flush()
    return await _get_staff(db, staff_id)


async def mark_leave_pending(db: AsyncSession, staff_id: int) -> WmsStaff:
    """收到离职同步但尚有在办事项时标记待离职，人仍在岗。"""
    staff = await _get_staff(db, staff_id)
    staff.left_pending_at = datetime.now()
    await _write_log(db, staff_id, "leave", reason="待离职")
    await db.flush()
    return staff


async def finish_leave(
    db: AsyncSession, staff_id: int, operator_id: Optional[int] = None
) -> WmsStaff:
    """确认离职：写离职时间、清待离职标记、转不在岗并解除班长。"""
    staff = await _get_staff(db, staff_id)
    if staff.left_at is not None:
        raise ValidationException("该人员已离职")
    staff.left_at = datetime.now()
    staff.left_pending_at = None
    staff.status = 0
    await _clear_leader(db, staff_id)
    await _write_log(db, staff_id, "leave", reason="离职生效", operator_id=operator_id)
    await db.flush()
    return staff


async def _check_team_fields(
    db: AsyncSession,
    name: str,
    floor_no: int,
    zone_ids: list[int],
    dispatch_limit_default: Optional[int],
) -> None:
    if not name or not name.strip():
        raise ValidationException("请填写班组名称")
    if len(name.strip()) > 20:
        raise ValidationException("班组名称不超过 20 字")
    if not zone_ids:
        raise ValidationException("至少选择一个管辖区域")
    if dispatch_limit_default is not None and not 1 <= dispatch_limit_default <= 20:
        raise ValidationException("在办上限默认须为 1 至 20 的整数")
    valid = (await db.execute(
        select(WmsZone.id).where(
            WmsZone.id.in_(zone_ids), WmsZone.floor_no == floor_no, WmsZone.status == 1
        )
    )).scalars().all()
    if len(set(valid)) != len(set(zone_ids)):
        raise ValidationException("所选区域不在该楼层或未启用")


async def create_team(
    db: AsyncSession,
    *,
    name: str,
    function_type: str,
    leader_staff_id: int,
    floor_no: int,
    zone_ids: list[int],
    dispatch_limit_default: Optional[int] = None,
    remark: Optional[str] = None,
) -> WmsTeam:
    """新建班组：组长必填且选中即归组，编号按仓取号不回收。"""
    await _check_team_fields(db, name, floor_no, zone_ids, dispatch_limit_default)
    dup = (await db.execute(select(WmsTeam.id).where(WmsTeam.name == name.strip()))).first()
    if dup is not None:
        raise ValidationException("本仓已有同名班组")
    leader = await _get_staff(db, leader_staff_id)
    if leader.status != 1:
        raise ValidationException("班组长须为在岗人员")
    other = (await db.execute(
        select(WmsTeam.id).where(WmsTeam.leader_staff_id == leader_staff_id)
    )).first()
    if other is not None:
        raise ValidationException("该人员已担任其他班组班组长")
    team = WmsTeam(
        code=await next_code(db, "NC-T", period="MAIN", width=2),
        name=name.strip(), function_type=function_type,
        leader_staff_id=leader_staff_id, floor_no=floor_no,
        dispatch_limit_default=dispatch_limit_default, status=1, remark=remark,
    )
    db.add(team)
    await db.flush()
    await _sync_team_zones(db, team.id, zone_ids)
    from_team_id = leader.team_id
    leader.team_id = team.id
    await _write_log(db, leader.id, "team", from_team_id=from_team_id,
                     to_team_id=team.id, reason="新建班组")
    await db.flush()
    return team


async def update_team(
    db: AsyncSession,
    team_id: int,
    *,
    name: str,
    function_type: str,
    leader_staff_id: int,
    floor_no: int,
    zone_ids: list[int],
    dispatch_limit_default: Optional[int] = None,
    remark: Optional[str] = None,
) -> WmsTeam:
    """编辑班组；换组长只从本组成员中选。"""
    team = await _get_team(db, team_id)
    await _check_team_fields(db, name, floor_no, zone_ids, dispatch_limit_default)
    dup = (await db.execute(
        select(WmsTeam.id).where(WmsTeam.name == name.strip(), WmsTeam.id != team_id)
    )).first()
    if dup is not None:
        raise ValidationException("本仓已有同名班组")
    if leader_staff_id != team.leader_staff_id:
        leader = await _get_staff(db, leader_staff_id)
        if leader.team_id != team_id or leader.status != 1:
            raise ValidationException("班组长须为本组在岗成员")
    team.name = name.strip()
    team.function_type = function_type
    team.leader_staff_id = leader_staff_id
    team.floor_no = floor_no
    team.dispatch_limit_default = dispatch_limit_default
    team.remark = remark
    await _sync_team_zones(db, team.id, zone_ids)
    await db.flush()
    return team


async def delete_team(db: AsyncSession, team_id: int) -> None:
    """组员清空后删除；最后一名班组长随组解除转未分组。"""
    team = await _get_team(db, team_id)
    members = (await db.execute(
        select(WmsStaff).where(WmsStaff.team_id == team_id)
    )).scalars().all()
    if len(members) > 1 or (len(members) == 1 and members[0].id != team.leader_staff_id):
        raise ValidationException("班组仍有成员，请先移出全部成员")
    for staff in members:
        from_team_id = staff.team_id
        staff.team_id = None
        await _write_log(db, staff.id, "team", from_team_id=from_team_id,
                         to_team_id=None, reason="删除班组")
    await db.execute(delete(WmsTeamZone).where(WmsTeamZone.team_id == team_id))
    await db.delete(team)
    await db.flush()


async def affected_members(db: AsyncSession, team_id: int) -> list[int]:
    """停用时需要任务中心处置的在岗成员。"""
    return list((await db.execute(
        select(WmsStaff.id).where(WmsStaff.team_id == team_id, WmsStaff.status == 1)
    )).scalars().all())


async def _ensure_can_transfer(db: AsyncSession, staff_id: int) -> None:
    leader_of = (await db.execute(
        select(WmsTeam.id).where(WmsTeam.leader_staff_id == staff_id)
    )).first()
    if leader_of is not None:
        raise ValidationException("班组长不可直接调组，请先在班组视图更换班组长")


async def _change_team(
    db: AsyncSession, staff: WmsStaff, team_id: Optional[int], reason: str
) -> None:
    from_team_id = staff.team_id
    staff.team_id = team_id
    await _clear_leader(db, staff.id)
    await _write_log(db, staff.id, "team", from_team_id=from_team_id,
                     to_team_id=team_id, reason=reason)


async def join_team(db: AsyncSession, staff_id: int, team_id: int) -> WmsStaff:
    """未归属人员加入班组。"""
    staff = await _get_staff(db, staff_id)
    team = await _get_team(db, team_id)
    if team.status != 1:
        raise ValidationException("班组已停用")
    if staff.team_id is not None:
        raise ValidationException("该人员已归属班组，请先办理调组")
    await _ensure_can_transfer(db, staff_id)
    await _change_team(db, staff, team_id, "加入班组")
    await db.flush()
    return staff


async def transfer_team(db: AsyncSession, staff_id: int, team_id: int) -> WmsStaff:
    """已归属人员调到另一班组。"""
    staff = await _get_staff(db, staff_id)
    team = await _get_team(db, team_id)
    if team.status != 1:
        raise ValidationException("班组已停用")
    if staff.team_id is None or staff.team_id == team_id:
        raise ValidationException("请先选择不同的目标班组")
    await _ensure_can_transfer(db, staff_id)
    await _change_team(db, staff, team_id, "调组")
    await db.flush()
    return staff


async def leave_team(db: AsyncSession, staff_id: int) -> WmsStaff:
    """退出班组，转为未分组待配置。"""
    staff = await _get_staff(db, staff_id)
    await _ensure_can_transfer(db, staff_id)
    await _change_team(db, staff, None, "移出班组")
    await db.flush()
    return staff


async def bulk_transfer_team(
    db: AsyncSession, staff_ids: list[int], team_id: Optional[int]
) -> dict:
    """批量调组：逐条处理，跳过的人带原因返回。"""
    if team_id is not None:
        target = await _get_team(db, team_id)
        if target.status != 1:
            raise ValidationException("目标班组已停用")
    moved: list[int] = []
    skipped: list[dict] = []
    for staff_id in staff_ids:
        staff = await _get_staff(db, staff_id)
        if staff.left_at is not None:
            skipped.append({"staff_id": staff_id, "reason": "已离职"})
            continue
        leader_of = (await db.execute(
            select(WmsTeam.id).where(WmsTeam.leader_staff_id == staff_id)
        )).first()
        if leader_of is not None:
            skipped.append({"staff_id": staff_id, "reason": "班组长，请先换组长"})
            continue
        if staff.team_id == team_id:
            skipped.append({"staff_id": staff_id, "reason": "已在目标组"})
            continue
        from_team_id = staff.team_id
        staff.team_id = team_id
        await _clear_leader(db, staff_id)
        await _write_log(db, staff_id, "team", from_team_id=from_team_id,
                         to_team_id=team_id, reason="批量调组")
        moved.append(staff_id)
    await db.flush()
    return {"moved": moved, "skipped": skipped}


async def set_team_leader(
    db: AsyncSession, team_id: int, staff_id: Optional[int]
) -> WmsTeam:
    """指定或清空班组长；班组长须为本组在岗成员。"""
    team = await _get_team(db, team_id)
    if staff_id is None:
        team.leader_staff_id = None
    else:
        staff = await _get_staff(db, staff_id)
        if staff.team_id != team_id or staff.status != 1:
            raise ValidationException("班组长须为本班组在岗成员")
        team.leader_staff_id = staff_id
    await db.flush()
    return team


async def toggle_team(db: AsyncSession, team_id: int, enabled: bool) -> WmsTeam:
    """启用或停用班组。停用只改状态，成员归属与作业位置保留。"""
    team = await _get_team(db, team_id)
    team.status = 1 if enabled else 0
    await db.flush()
    return team


async def _staff_users(db: AsyncSession, user_ids: list[int]) -> dict:
    """按人员档案关联的账号批量取用户管理中的基础字段。"""
    ids = list(dict.fromkeys(uid for uid in user_ids if uid is not None))
    if not ids:
        return {}
    rows = (await db.execute(
        select(User.id, User.nickname, User.phone, User.status).where(User.id.in_(ids))
    )).all()
    return {r.id: r for r in rows}


async def get_staff_by_user(db: AsyncSession, user_id: int) -> Optional[dict]:
    """按账号查在职人员及其班组职能，未绑定或已离职返回空。"""
    row = (
        await db.execute(
            select(WmsStaff, WmsTeam)
            .join(WmsTeam, WmsTeam.id == WmsStaff.team_id, isouter=True)
            .where(WmsStaff.user_id == user_id, WmsStaff.status == 1)
        )
    ).first()
    if row is None:
        return None
    staff, team = row
    user = (await _staff_users(db, [user_id])).get(user_id)
    return {
        "id": staff.id,
        "code": staff.code,
        "name": user.nickname if user is not None else staff.name,
        "phone": user.phone if user is not None else staff.phone,
        "account_status": user.status if user is not None else None,
        "team_id": staff.team_id,
        "team_name": team.name if team is not None else None,
        "function_type": team.function_type if team is not None else None,
    }


async def zone_coverage(db: AsyncSession) -> dict:
    """当前仓启用区域的覆盖读数：无组数与多组数只提示不阻断。"""
    zone_ids = (await db.execute(
        select(WmsZone.id).where(WmsZone.status == 1)
    )).scalars().all()
    rows = (await db.execute(
        select(WmsTeamZone.zone_id, func.count(WmsTeamZone.team_id))
        .join(WmsTeam, WmsTeam.id == WmsTeamZone.team_id)
        .where(WmsTeam.status == 1)
        .group_by(WmsTeamZone.zone_id)
    )).all()
    counts = {r[0]: r[1] for r in rows}
    return {
        "total": len(zone_ids),
        "no_team": sum(1 for z in zone_ids if counts.get(z, 0) == 0),
        "multi_team": sum(1 for z in zone_ids if counts.get(z, 0) > 1),
    }


def _cert_state(expire_on: Optional[date], today: date) -> str:
    if expire_on is None:
        return "none"
    if expire_on < today:
        return "expired"
    if expire_on <= today + timedelta(days=30):
        return "within_30"
    return "valid"


_staff_extras_provider = None


def set_staff_extras_provider(provider) -> None:
    """注册执行单元等只读数据的提供者，避免主数据反向依赖其模块。"""
    global _staff_extras_provider
    _staff_extras_provider = provider


async def _staff_extras(staff_id: int) -> dict:
    if _staff_extras_provider is None:
        return {"bound_unit": None, "in_progress_count": 0, "extras_synced": False}
    data = await _staff_extras_provider(staff_id)
    return {
        "bound_unit": data.get("bound_unit"),
        "in_progress_count": data.get("in_progress_count", 0),
        "extras_synced": True,
    }


def _split_terms(keyword: Optional[str]) -> list[str]:
    return [w for w in (keyword or "").split() if w]


def _check_range(start: Optional[datetime], end: Optional[datetime]) -> None:
    if start is not None and end is not None and start > end:
        raise ValidationException("时间起点不得晚于终点")


async def _team_read(db: AsyncSession, team: WmsTeam) -> dict:
    staffs = (await db.execute(
        select(WmsStaff).where(WmsStaff.team_id == team.id)
    )).scalars().all()
    active = [s for s in staffs if s.status == 1]
    skill_rows = []
    if active:
        skill_rows = (await db.execute(
            select(WmsStaffSkill.staff_id, WmsStaffSkill.process_code).where(
                WmsStaffSkill.staff_id.in_([s.id for s in active])
            )
        )).all()
    skilled_ids = {r.staff_id for r in skill_rows}
    zone_ids = (await db.execute(
        select(WmsTeamZone.zone_id).where(WmsTeamZone.team_id == team.id)
    )).scalars().all()
    leader_name = None
    if team.leader_staff_id is not None:
        leader_name = (await db.execute(
            select(WmsStaff.name).where(WmsStaff.id == team.leader_staff_id)
        )).scalar()
    return {
        "id": team.id, "code": team.code, "name": team.name,
        "function_type": team.function_type,
        "leader_staff_id": team.leader_staff_id, "leader_name": leader_name,
        "status": team.status, "floor_no": team.floor_no,
        "dispatch_limit_default": team.dispatch_limit_default,
        "zone_ids": list(zone_ids),
        "member_count": len(staffs), "active_count": len(active),
        "dispatchable_count": sum(1 for s in active if s.id in skilled_ids),
        "skills": sorted({r.process_code for r in skill_rows}) if team.status == 1 else [],
        "updated_at": team.updated_at.isoformat() if team.updated_at else None,
    }


async def list_teams(
    db: AsyncSession,
    *,
    status: Optional[int] = None,
    keyword: Optional[str] = None,
    leader_name: Optional[str] = None,
    floor_no: Optional[int] = None,
    process_code: Optional[str] = None,
    zone_id: Optional[int] = None,
    updated_from: Optional[datetime] = None,
    updated_to: Optional[datetime] = None,
) -> list[dict]:
    """班组列表：条件按且叠加，派生读数统一在 service 计算。"""
    _check_range(updated_from, updated_to)
    cond = []
    if status is not None:
        cond.append(WmsTeam.status == status)
    if floor_no is not None:
        cond.append(WmsTeam.floor_no == floor_no)
    if updated_from is not None:
        cond.append(WmsTeam.updated_at >= updated_from)
    if updated_to is not None:
        cond.append(WmsTeam.updated_at <= updated_to)
    teams = (await db.execute(
        select(WmsTeam).where(*cond).order_by(WmsTeam.id)
    )).scalars().all()
    result = []
    for team in teams:
        row = await _team_read(db, team)
        terms = _split_terms(keyword)
        if terms and not all(t in f"{team.code} {team.name}" for t in terms):
            continue
        if leader_name and leader_name not in (row["leader_name"] or ""):
            continue
        if process_code and process_code not in row["skills"]:
            continue
        if zone_id and zone_id not in row["zone_ids"]:
            continue
        result.append(row)
    return result


async def list_staffs(
    db: AsyncSession,
    *,
    team_id: Optional[int] = None,
    status: Optional[int] = None,
    keyword: Optional[str] = None,
    role: Optional[str] = None,
    leader_flag: Optional[str] = None,
    process_code: Optional[str] = None,
    cert_type: Optional[str] = None,
    config_state: Optional[str] = None,
    employment_state: Optional[str] = None,
    bound_state: Optional[str] = None,
    cert_expiry: Optional[str] = None,
    last_op_from: Optional[datetime] = None,
    last_op_to: Optional[datetime] = None,
) -> list[dict]:
    """人员列表：批量取能力与日志，避免逐人查询。"""
    _check_range(last_op_from, last_op_to)
    cond = []
    if team_id is not None:
        cond.append(WmsStaff.team_id == team_id)
    if status is not None:
        cond.append(WmsStaff.status == status)
    if role is not None:
        cond.append(WmsStaff.role == role)
    staffs = (await db.execute(
        select(WmsStaff).where(*cond).order_by(WmsStaff.id)
    )).scalars().all()
    ids = [s.id for s in staffs]
    users = await _staff_users(db, [s.user_id for s in staffs if s.user_id is not None])
    skills_by: dict[int, list[str]] = {}
    certs_by: dict[int, list[dict]] = {}
    logs_by: dict[int, datetime] = {}
    if ids:
        for r in (await db.execute(
            select(WmsStaffSkill.staff_id, WmsStaffSkill.process_code).where(
                WmsStaffSkill.staff_id.in_(ids)
            )
        )).all():
            skills_by.setdefault(r.staff_id, []).append(r.process_code)
        for r in (await db.execute(
            select(WmsStaffCert.staff_id, WmsStaffCert.cert_type, WmsStaffCert.expire_on).where(
                WmsStaffCert.staff_id.in_(ids)
            )
        )).all():
            certs_by.setdefault(r.staff_id, []).append(
                {"cert_type": r.cert_type, "expire_on": r.expire_on}
            )
        for r in (await db.execute(
            select(WmsStaffLog.staff_id, func.max(WmsStaffLog.occurred_at)).where(
                WmsStaffLog.staff_id.in_(ids)
            ).group_by(WmsStaffLog.staff_id)
        )).all():
            logs_by[r.staff_id] = r[1]
    teams = {t.id: t for t in (await db.execute(select(WmsTeam))).scalars().all()}
    leader_ids = {t.leader_staff_id for t in teams.values() if t.leader_staff_id is not None}
    today = date.today()
    result = []
    for staff in staffs:
        skills = skills_by.get(staff.id, [])
        certs = certs_by.get(staff.id, [])
        team = teams.get(staff.team_id) if staff.team_id else None
        extras = await _staff_extras(staff.id)
        state = "left" if staff.left_at else ("pending" if staff.left_pending_at else "active")
        config = "configured" if staff.team_id and skills else "pending"
        expiry_states = [_cert_state(c["expire_on"], today) for c in certs]
        user = users.get(staff.user_id) if staff.user_id is not None else None
        name = user.nickname if user is not None else staff.name
        phone = user.phone if user is not None else staff.phone
        row = {
            "id": staff.id, "code": staff.code, "name": name,
            "phone": phone, "role": staff.role, "user_id": staff.user_id,
            "account_status": user.status if user is not None else None,
            "team_id": staff.team_id, "team_name": team.name if team else None,
            "floor_no": team.floor_no if team else None,
            "leader": staff.id in leader_ids, "team_status": team.status if team else None,
            "status": staff.status, "employment_state": state,
            "config_state": config, "skills": skills, "certs": certs,
            "cert_expiry": "expired" if "expired" in expiry_states
                           else ("within_30" if "within_30" in expiry_states else "valid"),
            "quality_cert": staff.quality_cert, "quality_team": staff.quality_team,
            "left_at": staff.left_at.isoformat() if staff.left_at else None,
            "left_pending_at": staff.left_pending_at.isoformat() if staff.left_pending_at else None,
            "last_op_at": logs_by[staff.id].isoformat() if staff.id in logs_by else None,
            **extras,
        }
        terms = _split_terms(keyword)
        if terms and not all(
            t in f"{staff.code} {name} {phone or ''} {extras['bound_unit'] or ''}"
            for t in terms
        ):
            continue
        if leader_flag == "leader" and not row["leader"]:
            continue
        if leader_flag == "member" and row["leader"]:
            continue
        if process_code and process_code not in skills:
            continue
        if cert_type and cert_type not in [c["cert_type"] for c in certs]:
            continue
        if config_state and config != config_state:
            continue
        if employment_state and state != employment_state:
            continue
        if bound_state == "bound" and extras["bound_unit"] is None:
            continue
        if bound_state == "unbound" and extras["bound_unit"] is not None:
            continue
        if cert_expiry and cert_expiry not in expiry_states:
            continue
        last = logs_by.get(staff.id)
        if last_op_from and (last is None or last < last_op_from):
            continue
        if last_op_to and (last is None or last > last_op_to):
            continue
        result.append(row)
    return result
