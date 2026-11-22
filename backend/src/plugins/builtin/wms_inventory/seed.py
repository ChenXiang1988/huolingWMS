"""库存域的菜单基线。

菜单归属插件自己——基座靠 ``permission`` / ``component`` 前缀识别所有权，
停用插件时据此把整支菜单隐藏。
"""
from loguru import logger
from sqlalchemy import insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models import Menu, Role
from src.models.rbac import role_menu

# (名称, path, component, permission, icon, sort)
_PAGES = [
    ("库存查询", "stock", "wms_inventory/stock/index", "wms_inventory:stock:list", "Search", 1),
    ("库存流水", "txn", "wms_inventory/txn/index", "wms_inventory:txn:list", "Tickets", 2),
    ("批次查询", "lot", "wms_inventory/lot/index", "wms_inventory:lot:list", "Calendar", 3),
]

# 按钮级权限挂在库存查询下
_BUTTONS = [
    ("调整库存", "wms_inventory:adjust:create", 1),
]


async def seed_inventory(db: AsyncSession) -> None:
    """建库存域目录、三个页面与按钮权限，并绑给超管。"""
    cache: list[Menu] = list((await db.execute(select(Menu))).scalars().all())

    def find(name: str, parent_id: int) -> Menu | None:
        return next(
            (m for m in cache if m.name == name and m.parent_id == parent_id), None
        )

    async def ensure(menu: Menu) -> Menu:
        db.add(menu)
        await db.flush()
        cache.append(menu)
        logger.info(f"Created menu '{menu.name}'")
        return menu

    top = find("库存", 0)
    if top is None:
        top = await ensure(
            Menu(
                name="库存", parent_id=0, type="M", path="/wms-inventory",
                icon="Box", sort=20, visible=1, status=1,
            )
        )

    pages: list[Menu] = []
    for name, path, component, permission, icon, sort in _PAGES:
        menu = find(name, top.id)
        if menu is None:
            menu = await ensure(
                Menu(
                    name=name, parent_id=top.id, type="C", path=path,
                    component=component, permission=permission,
                    icon=icon, sort=sort, visible=1, status=1,
                )
            )
        pages.append(menu)

    stock_page = pages[0]
    buttons: list[Menu] = []
    for name, permission, sort in _BUTTONS:
        menu = find(name, stock_page.id)
        if menu is None:
            menu = await ensure(
                Menu(
                    name=name, parent_id=stock_page.id, type="F", path=None,
                    component=None, permission=permission,
                    sort=sort, visible=1, status=1,
                )
            )
        buttons.append(menu)

    admin = (
        await db.execute(select(Role).where(Role.code == "admin"))
    ).scalars().first()
    if admin:
        bound = set(
            (
                await db.execute(
                    select(role_menu.c.menu_id).where(role_menu.c.role_id == admin.id)
                )
            ).scalars().all()
        )
        targets = [top, *pages, *buttons]
        rows = [
            {"role_id": admin.id, "menu_id": m.id} for m in targets if m.id not in bound
        ]
        if rows:
            await db.execute(insert(role_menu), rows)
            await db.flush()
