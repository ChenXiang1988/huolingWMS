"""任务域菜单。"""
from loguru import logger
from sqlalchemy import insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models import Menu, Role
from src.models.rbac import role_menu


async def seed_tasking(db: AsyncSession) -> None:
    cache: list[Menu] = list((await db.execute(select(Menu))).scalars().all())

    def find(name: str, parent_id: int) -> Menu | None:
        return next((m for m in cache if m.name == name and m.parent_id == parent_id), None)

    async def ensure(menu: Menu) -> Menu:
        db.add(menu)
        await db.flush()
        cache.append(menu)
        logger.info(f"Created menu '{menu.name}'")
        return menu

    top = find("任务", 0)
    if top is None:
        top = await ensure(Menu(
            name="任务", parent_id=0, type="M", path="/wms-tasking",
            icon="Calendar", sort=60, visible=1, status=1,
        ))

    page = find("我的任务", top.id)
    if page is None:
        page = await ensure(Menu(
            name="我的任务", parent_id=top.id, type="C", path="task",
            component="wms_tasking/task/index",
            permission="wms_tasking:task:list",
            icon="List", sort=1, visible=1, status=1,
        ))

    buttons: list[Menu] = []
    for sort, name, perm in (
        (1, "生成任务", "wms_tasking:task:create"),
        (2, "领取任务", "wms_tasking:task:claim"),
        (3, "提交任务", "wms_tasking:task:submit"),
    ):
        btn = find(name, page.id)
        if btn is None:
            btn = await ensure(Menu(
                name=name, parent_id=page.id, type="F", path=None,
                component=None, permission=perm, sort=sort, visible=1, status=1,
            ))
        buttons.append(btn)

    admin = (await db.execute(select(Role).where(Role.code == "admin"))).scalars().first()
    if admin:
        bound = set((await db.execute(
            select(role_menu.c.menu_id).where(role_menu.c.role_id == admin.id)
        )).scalars().all())
        rows = [{"role_id": admin.id, "menu_id": x.id}
                for x in [top, page, *buttons] if x.id not in bound]
        if rows:
            await db.execute(insert(role_menu), rows)
            await db.flush()
