"""货主会话上下文：从登录账号反查绑定的货主。

门户与开放接口都用它注入 ``owner_id``——请求体里不收这个字段，
否则改一下报文就能替别的货主建单。
"""
from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.exceptions import AuthException


@dataclass
class OwnerContext:
    owner_id: int
    owner_name: str
    sync_enabled: bool

    @property
    def can_create(self) -> bool:
        """接了 ERP 的货主订单由上游下发，门户建单入口关闭。"""
        return not self.sync_enabled


async def owner_of_user(db: AsyncSession, user_id: int) -> OwnerContext:
    row = (
        await db.execute(
            text(
                "SELECT o.id, o.name, o.sync_enabled, o.status "
                "FROM wms_master_data_user_owner uo "
                "JOIN wms_master_data_owner o ON o.id = uo.owner_id "
                "WHERE uo.user_id = :uid AND uo.status = 1 "
                "ORDER BY uo.is_primary DESC LIMIT 1"
            ),
            {"uid": user_id},
        )
    ).first()
    if row is None:
        raise AuthException("该账号未绑定货主")
    if int(row.status) != 1:
        raise AuthException("所属货主已停用")
    return OwnerContext(
        owner_id=int(row.id),
        owner_name=row.name,
        sync_enabled=bool(row.sync_enabled),
    )
