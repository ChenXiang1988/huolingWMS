"""主数据域的出入参模型。"""
from pydantic import BaseModel


class PortalFlagOut(BaseModel):
    """登录后落点判定所需的身份标记。"""

    is_owner: bool
