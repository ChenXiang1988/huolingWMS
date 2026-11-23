"""主数据域的领域服务：取号、建货主、建货主主账号。

取号必须走行锁。三万个单号并发下，"先查后加一"会在两个人同时取号时发出同一个号，
而单号重复在账上无法分辨是哪一单。
"""
from typing import Optional

from loguru import logger
from sqlalchemy import func, select, update
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
    WmsTeam,
    WmsUserOwner,
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
    name: str,
    phone: Optional[str] = None,
    user_id: Optional[int] = None,
) -> WmsStaff:
    """建人员档案。账号只在建档时绑定，货主账号与重复绑定都拒绝。"""
    if user_id is not None:
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

    staff = WmsStaff(code=code, name=name, phone=phone, user_id=user_id, status=1)
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
    db: AsyncSession, staff_id: int, *, name: str, phone: Optional[str], status: int
) -> WmsStaff:
    """编辑姓名、联系方式与在职状态；离职时自动解除班长。"""
    staff = await _get_staff(db, staff_id)
    staff.name = name
    staff.phone = phone
    if status == 0 and staff.status == 1:
        await _clear_leader(db, staff_id)
    staff.status = status
    await db.flush()
    return staff


async def join_team(db: AsyncSession, staff_id: int, team_id: int) -> WmsStaff:
    """未归属人员加入班组。"""
    staff = await _get_staff(db, staff_id)
    team = await _get_team(db, team_id)
    if team.status != 1:
        raise ValidationException("班组已停用")
    if staff.team_id is not None:
        raise ValidationException("该人员已归属班组，请先办理调组")
    staff.team_id = team_id
    await db.flush()
    return staff


async def transfer_team(db: AsyncSession, staff_id: int, team_id: int) -> WmsStaff:
    """已归属人员调到另一班组，原班组的班长资格一并解除。"""
    staff = await _get_staff(db, staff_id)
    team = await _get_team(db, team_id)
    if team.status != 1:
        raise ValidationException("班组已停用")
    if staff.team_id is None or staff.team_id == team_id:
        raise ValidationException("请先选择不同的目标班组")
    staff.team_id = team_id
    await _clear_leader(db, staff_id)
    await db.flush()
    return staff


async def leave_team(db: AsyncSession, staff_id: int) -> WmsStaff:
    """退出班组，用于停用班组前清空成员。"""
    staff = await _get_staff(db, staff_id)
    staff.team_id = None
    await _clear_leader(db, staff_id)
    await db.flush()
    return staff


async def set_team_leader(
    db: AsyncSession, team_id: int, staff_id: Optional[int]
) -> WmsTeam:
    """指定或清空班长。班长须为本组在职成员。"""
    team = await _get_team(db, team_id)
    if staff_id is None:
        team.leader_staff_id = None
    else:
        staff = await _get_staff(db, staff_id)
        if staff.team_id != team_id or staff.status != 1:
            raise ValidationException("班长须为本班组在职成员")
        team.leader_staff_id = staff_id
    await db.flush()
    return team


async def toggle_team(db: AsyncSession, team_id: int, enabled: bool) -> WmsTeam:
    """启用或停用班组。停用前须无在职成员。"""
    team = await _get_team(db, team_id)
    if not enabled:
        active = (
            await db.execute(
                select(func.count()).select_from(WmsStaff).where(
                    WmsStaff.team_id == team_id, WmsStaff.status == 1
                )
            )
        ).scalar() or 0
        if active:
            raise ValidationException("班组仍有在职成员，请先调走或办理离职")
        team.leader_staff_id = None
    team.status = 1 if enabled else 0
    await db.flush()
    return team


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
    return {
        "id": staff.id,
        "code": staff.code,
        "name": staff.name,
        "team_id": staff.team_id,
        "team_name": team.name if team is not None else None,
        "function_type": team.function_type if team is not None else None,
    }
