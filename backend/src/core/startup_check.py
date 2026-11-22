"""启动前提校验。

这套系统的幂等依赖唯一索引，而唯一索引的行为受排序规则影响：
``utf8mb4_general_ci`` 下 ``ASN001`` 与 ``asn001`` 会被判为同值，唯一约束会挡掉
本该新建的单。这类问题不报错，只表现为"偶尔建不出单"，事后再查成本极高。

所以宁可启动时拦住，也不带着错误的排序规则继续跑。

SQLite 没有排序规则与时区的概念，开发机走 SQLite 时跳过这两项；单进程校验保留。
"""
from loguru import logger
from sqlalchemy import text

from src.core.config import settings

EXPECTED_COLLATION = "utf8mb4_0900_ai_ci"
EXPECTED_TIME_ZONE = "+08:00"


class StartupCheckError(RuntimeError):
    """启动前提不满足。"""


async def verify_runtime() -> None:
    """校验运行前提，不满足则抛异常终止启动。"""
    _verify_single_process()

    if settings.DB_TYPE != "mysql":
        logger.warning(
            f"DB_TYPE={settings.DB_TYPE}：跳过排序规则与时区校验（仅 MySQL 模式强制）"
        )
        return

    from src.db import engine

    async with engine.connect() as conn:
        collation = (await conn.execute(text("SELECT @@collation_server"))).scalar()
        time_zone = (await conn.execute(text("SELECT @@session.time_zone"))).scalar()

    if collation != EXPECTED_COLLATION:
        raise StartupCheckError(
            f"数据库排序规则不符：期望 {EXPECTED_COLLATION}，实际 {collation}。"
            "排序规则不一致会让唯一索引误判大小写，导致偶发的建单失败。"
        )

    if time_zone != EXPECTED_TIME_ZONE:
        raise StartupCheckError(
            f"数据库会话时区不符：期望 {EXPECTED_TIME_ZONE}，实际 {time_zone}。"
            "时区不同会让按日切分的占用快照与账期算错。"
        )

    logger.info(f"运行前提校验通过：{settings.DB_TYPE} / {collation} / {time_zone}")


def _verify_single_process() -> None:
    """确认插件运行时模式仍是单进程。

    运行时无法可靠探测 uvicorn 开了几个 worker，所以这里校验的是配置项没被改动；
    真正的约束写在 README：启动命令不要加 ``--workers``。
    """
    if settings.PLUGIN_RUNTIME_MODE != "single_process":
        raise StartupCheckError(
            f"PLUGIN_RUNTIME_MODE={settings.PLUGIN_RUNTIME_MODE}："
            "插件运行时状态在进程内存中，多进程会让插件启停与菜单同步各自为政。"
        )
