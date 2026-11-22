"""货主 API 鉴权。

不复用基座的 ``get_current_user``：它绑死 ``Authorization: Bearer``，货主系统
不该为了调几个接口去换 token。这里用 ``X-API-Key`` 独立一套。

密钥只存 sha256 哈希，库里查不到明文；比对走哈希，不存明文也就没有"库被读走
就等于密钥泄露"的问题。
"""
import hashlib
from typing import Annotated, Optional

from fastapi import Depends, Header
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.exceptions import AuthException
from src.db import get_db
from src.plugins.builtin.wms_master_data import models as m


def hash_api_key(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


async def require_api_key(
    db: Annotated[AsyncSession, Depends(get_db)],
    x_api_key: Annotated[Optional[str], Header(alias="X-API-Key")] = None,
) -> int:
    """返回密钥所属的 ``owner_id``。

    三类失败都抛 401：没带头、密钥不存在或已停用、货主已停用。
    不区分"密钥不存在"与"密钥已停用"——对外只暴露一个结论。
    """
    if not x_api_key:
        raise AuthException("缺少 X-API-Key")

    row = (
        await db.execute(
            select(m.WmsApiKey).where(
                m.WmsApiKey.key_hash == hash_api_key(x_api_key),
                m.WmsApiKey.status == 1,
            )
        )
    ).scalars().first()
    if row is None:
        raise AuthException("API 密钥无效或已停用")

    owner = (
        await db.execute(
            select(m.WmsOwner).where(
                m.WmsOwner.id == row.owner_id, m.WmsOwner.status == 1
            )
        )
    ).scalars().first()
    if owner is None:
        raise AuthException("该密钥所属货主已停用")

    return int(row.owner_id)
