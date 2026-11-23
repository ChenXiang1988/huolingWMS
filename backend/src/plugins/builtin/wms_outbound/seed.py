"""出库域菜单：一个目录、四个页面（波次看板 P4 补）、按钮权限。"""
from loguru import logger
from sqlalchemy import insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models import Menu, Role
from src.models.rbac import role_menu

_CUSTOMER_SERVICE_PAGES = [
    ("出库订单", "order", "wms_outbound/order/index", "wms_outbound:order:list", "ShoppingCart", 1),
]

_PAGES = [
    ("波次看板", "wave", "wms_outbound/wave/index", "wms_outbound:wave:list", "DataLine", 2),
    # 打印模板表在主数据域，但页面入口归出库作业；权限前缀跟出库插件一致，
    # 否则停用出库插件时这个菜单删不掉
    ("打印模板", "print_template", "wms_outbound/print_template/index",
     "wms_outbound:print_template:list", "Printer", 3),
]

# 分播、拣货、复核是领取后扫码执行的动作，与单据管理能力分开，归到一级菜单「作业台」
_WORKBENCH_PAGES = [
    ("分播作业", "seed", "wms_outbound/seed/index", "wms_outbound:seed:list", "Grid", 1),
    ("拣货", "pick", "wms_outbound/pick/index", "wms_outbound:pick:list", "Sort", 2),
    ("复核与发运", "check", "wms_outbound/check/index", "wms_outbound:check:list", "ScaleToOriginal", 3),
]

_BUTTONS = [
    ("order", "新建订单", "wms_outbound:order:create", 1),
    ("order", "分配", "wms_outbound:order:allocate", 2),
    ("order", "取消订单", "wms_outbound:order:cancel", 3),
    ("wave", "生成波次", "wms_outbound:wave:create", 1),
    ("wave", "中止波次", "wms_outbound:wave:cancel", 2),
    ("seed", "分播扫码", "wms_outbound:seed:execute", 1),
    ("pick", "拣货确认", "wms_outbound:pick:execute", 1),
    ("check", "记录实称", "wms_outbound:check:record", 1),
    ("check", "发运", "wms_outbound:check:ship", 2),
]


async def seed_outbound(db: AsyncSession) -> None:
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

    top = find("出库", 0)
    if top is None:
        top = await ensure(
            Menu(
                name="出库", parent_id=0, type="M", path="/wms-outbound",
                icon="ShoppingCart", sort=40, visible=1, status=1,
            )
        )

    workbench = find("作业台", 0)
    if workbench is None:
        workbench = await ensure(
            Menu(
                name="作业台", parent_id=0, type="M", path="/wms-workbench",
                permission="wms_outbound:workbench:view",
                icon="Operation", sort=45, visible=1, status=1,
            )
        )

    service = find("客户服务", 0)

    pages: dict[str, Menu] = {}
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
        pages[path] = menu

    for name, path, component, permission, icon, sort in _WORKBENCH_PAGES:
        menu = find(name, workbench.id)
        if menu is None:
            # 已初始化的库里这些页面挂在「出库」下，改挂到作业台，保留原记录及其按钮权限
            old = find(name, top.id)
            if old is not None:
                old.parent_id = workbench.id
                await db.flush()
                menu = old
            else:
                menu = await ensure(
                    Menu(
                        name=name, parent_id=workbench.id, type="C", path=path,
                        component=component, permission=permission,
                        icon=icon, sort=sort, visible=1, status=1,
                    )
                )
        pages[path] = menu

    for name, path, component, permission, icon, sort in _CUSTOMER_SERVICE_PAGES:
        menu = find(name, service.id)
        if menu is None:
            # 已初始化的库里出库订单挂在「出库」下，改挂到客户服务，保留按钮权限
            old = find(name, top.id)
            if old is not None:
                old.parent_id = service.id
                await db.flush()
                menu = old
            else:
                menu = await ensure(
                    Menu(
                        name=name, parent_id=service.id, type="C", path=path,
                        component=component, permission=permission,
                        icon=icon, sort=sort, visible=1, status=1,
                    )
                )
        pages[path] = menu

    buttons: list[Menu] = []
    for page_path, name, permission, sort in _BUTTONS:
        parent = pages.get(page_path)
        if parent is None:
            continue
        menu = find(name, parent.id)
        if menu is None:
            menu = await ensure(
                Menu(
                    name=name, parent_id=parent.id, type="F", path=None,
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
        rows = [
            {"role_id": admin.id, "menu_id": m.id}
            for m in [top, workbench, service, *pages.values(), *buttons]
            if m.id not in bound
        ]
        if rows:
            await db.execute(insert(role_menu), rows)
            await db.flush()
