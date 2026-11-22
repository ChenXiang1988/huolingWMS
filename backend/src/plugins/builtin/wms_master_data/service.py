"""主数据域的领域服务：取号、建货主、建货主主账号。

取号必须走行锁。三万个单号并发下，"先查后加一"会在两个人同时取号时发出同一个号，
而单号重复在账上无法分辨是哪一单。
"""
from typing import Optional

from loguru import logger
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.security import hash_password
from src.models import Role, User
from src.models.rbac import user_role
from src.plugins.builtin.wms_master_data.models import (
    WmsOwner,
    WmsSequence,
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
