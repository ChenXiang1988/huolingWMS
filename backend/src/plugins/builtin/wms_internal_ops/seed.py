"""库内作业菜单。P4 只有补货建议页，P5 再补移库/盘点/留样台账。"""
from loguru import logger
from sqlalchemy import insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models import Menu, Role
from src.models.rbac import role_menu


async def seed_internal_ops(db: AsyncSession) -> None:
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

    top = find("库内作业", 0)
    if top is None:
        top = await ensure(
            Menu(
                name="库内作业", parent_id=0, type="M", path="/wms-internal-ops",
                icon="Refresh", sort=50, visible=1, status=1,
            )
        )

    page = find("补货建议", top.id)
    if page is None:
        page = await ensure(
            Menu(
                name="补货建议", parent_id=top.id, type="C", path="replenish",
                component="wms_internal_ops/replenish/index",
                permission="wms_internal_ops:replenish:list",
                icon="Bottom", sort=1, visible=1, status=1,
            )
        )

    buttons: list[Menu] = []
    for sort, name, perm in (
        (1, "生成建议", "wms_internal_ops:replenish:create"),
        (2, "执行补货", "wms_internal_ops:replenish:execute"),
    ):
        btn = find(name, page.id)
        if btn is None:
            btn = await ensure(
                Menu(
                    name=name, parent_id=page.id, type="F", path=None,
                    component=None, permission=perm,
                    sort=sort, visible=1, status=1,
                )
            )
        buttons.append(btn)

    # P5 三页：移库单、盘点单、留样台账
    pages: list[Menu] = [page]
    for sort, name, path, perm, icon in (
        (2, "移库单", "transfer", "wms_internal_ops:transfer:list", "Sort"),
        (3, "盘点单", "count", "wms_internal_ops:count:list", "Tickets"),
        (4, "留样台账", "sample", "wms_internal_ops:sample:list", "Clock"),
    ):
        pg = find(name, top.id)
        if pg is None:
            pg = await ensure(
                Menu(
                    name=name, parent_id=top.id, type="C", path=path,
                    component=f"wms_internal_ops/{path}/index",
                    permission=perm, icon=icon, sort=sort, visible=1, status=1,
                )
            )
        pages.append(pg)

    action_map = {
        "移库单": [
            (1, "新建移库", "wms_internal_ops:transfer:create"),
            (2, "执行移库", "wms_internal_ops:transfer:execute"),
        ],
        "盘点单": [
            (1, "生成盘点", "wms_internal_ops:count:create"),
            (2, "录实盘", "wms_internal_ops:count:count"),
            (3, "确认盘点", "wms_internal_ops:count:confirm"),
        ],
        "留样台账": [
            (1, "回填历史", "wms_internal_ops:sample:create"),
            (2, "到期处置", "wms_internal_ops:sample:dispose"),
        ],
    }
    for pg in pages[1:]:
        for sort, name, perm in action_map.get(pg.name, []):
            btn = find(name, pg.id)
            if btn is None:
                btn = await ensure(
                    Menu(
                        name=name, parent_id=pg.id, type="F", path=None,
                        component=None, permission=perm,
                        sort=sort, visible=1, status=1,
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
            for m in [top, *pages, *buttons]
            if m.id not in bound
        ]
        if rows:
            await db.execute(insert(role_menu), rows)
            await db.flush()
