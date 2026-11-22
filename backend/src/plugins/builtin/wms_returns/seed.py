"""逆向域菜单：一个目录、一个待处置页面、两个处置按钮。"""
from loguru import logger
from sqlalchemy import insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models import Menu, Role
from src.models.rbac import role_menu


async def seed_returns(db: AsyncSession) -> None:
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

    top = find("逆向", 0)
    if top is None:
        top = await ensure(
            Menu(
                name="逆向", parent_id=0, type="M", path="/wms-returns",
                icon="RefreshLeft", sort=60, visible=1, status=1,
            )
        )

    disposal = find("待处置库存", top.id)
    if disposal is None:
        disposal = await ensure(
            Menu(
                name="待处置库存", parent_id=top.id, type="C", path="disposal",
                component="wms_returns/disposal/index",
                permission="wms_returns:disposal:list",
                icon="Warning", sort=1, visible=1, status=1,
            )
        )

    buttons: list[Menu] = []
    for sort, name, perm in (
        (1, "转回可发", "wms_returns:disposal:restock"),
        (2, "报废", "wms_returns:disposal:scrap"),
        (3, "退回货主", "wms_returns:disposal:return_owner"),
    ):
        menu = find(name, disposal.id)
        if menu is None:
            menu = await ensure(
                Menu(
                    name=name, parent_id=disposal.id, type="F", path=None,
                    component=None, permission=perm,
                    sort=sort, visible=1, status=1,
                )
            )
        buttons.append(menu)

    # P6 退货单
    ret_page = find("退货单", top.id)
    if ret_page is None:
        ret_page = await ensure(
            Menu(
                name="退货单", parent_id=top.id, type="C", path="return",
                component="wms_returns/return/index",
                permission="wms_returns:return:list",
                icon="RefreshLeft", sort=2, visible=1, status=1,
            )
        )
    for sort, name, perm in (
        (1, "新建退货单", "wms_returns:return:create"),
        (2, "确认入库", "wms_returns:return:receive"),
    ):
        btn = find(name, ret_page.id)
        if btn is None:
            btn = await ensure(
                Menu(
                    name=name, parent_id=ret_page.id, type="F", path=None,
                    component=None, permission=perm, sort=sort, visible=1, status=1,
                )
            )
        buttons.append(btn)

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
        rows = [
            {"role_id": admin.id, "menu_id": m.id}
            for m in [top, disposal, ret_page, *buttons]
            if m.id not in bound
        ]
        if rows:
            await db.execute(insert(role_menu), rows)
            await db.flush()
