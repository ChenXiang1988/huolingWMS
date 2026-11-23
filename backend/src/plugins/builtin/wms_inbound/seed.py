"""入库域的菜单基线：一个目录、四个页面、若干按钮权限。"""
from loguru import logger
from sqlalchemy import insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models import Menu, Role
from src.models.rbac import role_menu

_PAGES = [
    ("服务订单", "service_order", "wms_inbound/service_order/index",
     "wms_inbound:service_order:list", "Document", 2),
    ("收货", "receipt", "wms_inbound/receipt/index", "wms_inbound:receipt:list", "Box", 3),
    ("上架", "putaway", "wms_inbound/putaway/index", "wms_inbound:putaway:list", "Sort", 4),
]

# 入库预报由货主通过开放 API 或自助端推送，归到基座创建的「客户服务」目录
_CUSTOMER_SERVICE_PAGES = [
    ("入库预报", "asn", "wms_inbound/asn/index", "wms_inbound:asn:list", "Download", 1),
]

# (页面 path, 按钮名, 权限, 排序)
_BUTTONS = [
    ("asn", "新建预报", "wms_inbound:asn:create", 1),
    ("asn", "确认预报", "wms_inbound:asn:edit", 2),
    ("asn", "结案", "wms_inbound:asn:close", 3),
    ("service_order", "新建服务订单", "wms_inbound:service_order:create", 1),
    ("receipt", "开收货单", "wms_inbound:receipt:create", 1),
    ("receipt", "收货确认", "wms_inbound:receipt:confirm", 2),
    ("putaway", "上架确认", "wms_inbound:putaway:execute", 1),
]


async def seed_inbound(db: AsyncSession) -> None:
    """建入库域目录、四个页面与按钮权限，并绑给超管。"""
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

    top = find("入库", 0)
    if top is None:
        top = await ensure(
            Menu(
                name="入库", parent_id=0, type="M", path="/wms-inbound",
                icon="Download", sort=30, visible=1, status=1,
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

    for name, path, component, permission, icon, sort in _CUSTOMER_SERVICE_PAGES:
        menu = find(name, service.id)
        if menu is None:
            # 已初始化的库里入库预报挂在「入库」下，改挂到客户服务，保留按钮权限
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

    created_buttons: list[Menu] = []
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
        created_buttons.append(menu)

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
        targets = [top, service, *pages.values(), *created_buttons]
        rows = [
            {"role_id": admin.id, "menu_id": m.id} for m in targets if m.id not in bound
        ]
        if rows:
            await db.execute(insert(role_menu), rows)
            await db.flush()
