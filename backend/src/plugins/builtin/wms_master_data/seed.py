"""主数据域的菜单与角色基线。

菜单归属靠前缀匹配：``permission`` 以 ``wms_master_data:`` 开头、或 ``path`` 以
``/wms-master-data`` 开头，即被基座认作本插件所有，停用插件时自动隐藏。

P0 只建两个后台入口（货主管理）与门户（概览、子账号）。其余菜单随 P1 及之后
的期次补——先建出来只会得到一堆点了白屏的死链。
"""
from loguru import logger
from sqlalchemy import insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models import Menu, Role
from src.models.rbac import role_menu

# 角色清单：code, 名称, 备注
ROLE_SPECS = [
    ("wms_owner_admin", "货主主账号", "可管理子账号，可查看全部门户功能"),
    ("wms_owner_operator", "货主子账号", "可查库存与单据，不能管理子账号"),
    ("wms_owner_viewer", "货主只读", "只读，不能建单"),
]


async def _ensure_menu(
    db: AsyncSession,
    cache: list[Menu],
    *,
    name: str,
    parent_id: int,
    mtype: str,
    path: str | None = None,
    component: str | None = None,
    permission: str | None = None,
    icon: str | None = None,
    sort: int = 0,
    align_fields: bool = False,
) -> Menu:
    """按 (name, parent_id) 判重后创建菜单，返回已存在或新建的记录。

    align_fields 仅用于归属迁移：定位到已有行时回填 permission/component/path，
    让重复 seed 能把旧归属纠正过来。默认不回填，避免覆盖管理员的手工改动。
    """
    for m in cache:
        if m.name == name and m.parent_id == parent_id:
            if align_fields:
                m.permission = permission
                m.component = component
                m.path = path
            return m

    menu = Menu(
        name=name,
        parent_id=parent_id,
        type=mtype,
        path=path,
        component=component,
        permission=permission,
        icon=icon,
        sort=sort,
        visible=1,
        status=1,
    )
    db.add(menu)
    await db.flush()
    cache.append(menu)
    return menu


async def _ensure_role(db: AsyncSession, code: str, name: str, remark: str) -> Role:
    """按 code 判重后创建角色。"""
    role = (await db.execute(select(Role).where(Role.code == code))).scalars().first()
    if role:
        return role
    role = Role(code=code, name=name, remark=remark, sort=50, status=1, data_scope=1)
    db.add(role)
    await db.flush()
    logger.info(f"Created role '{name}' ({code})")
    return role


async def _bind(db: AsyncSession, role: Role, menus: list[Menu]) -> None:
    """把菜单绑到角色上，已是绑定关系的跳过。

    直接查关联表而不用 ``role.menus``：新建的角色该关系尚未加载，在异步会话里
    读它会抛 MissingGreenlet。
    """
    if not menus:
        return
    bound = set(
        (
            await db.execute(
                select(role_menu.c.menu_id).where(role_menu.c.role_id == role.id)
            )
        ).scalars().all()
    )
    rows = [
        {"role_id": role.id, "menu_id": m.id} for m in menus if m.id not in bound
    ]
    if rows:
        await db.execute(insert(role_menu), rows)
        await db.flush()


async def seed_master_data(db: AsyncSession) -> None:
    """建菜单与角色，并把门户菜单绑给三个货主角色。"""
    cache: list[Menu] = list((await db.execute(select(Menu))).scalars().all())

    # ── 后台：主数据目录 ────────────────────────────────
    top = await _ensure_menu(
        db, cache,
        name="主数据", parent_id=0, mtype="M",
        path="/wms-master-data", icon="Files", sort=10,
    )

    owner_menu = await _ensure_menu(
        db, cache,
        name="货主管理", parent_id=top.id, mtype="C",
        path="owner", component="wms_master_data/owner/index",
        permission="wms_master_data:owner:list", icon="User", sort=1,
    )
    await _ensure_menu(
        db, cache,
        name="新增货主", parent_id=owner_menu.id, mtype="F",
        permission="wms_master_data:owner:create", sort=1,
    )
    await _ensure_menu(
        db, cache,
        name="编辑货主", parent_id=owner_menu.id, mtype="F",
        permission="wms_master_data:owner:edit", sort=2,
    )

    backend_pages: list[Menu] = [owner_menu]

    # ── 其余后台页面：仓库配置、库位、商品、合作方、API 凭证 ──
    warehouse_page = await _ensure_menu(
        db, cache,
        name="仓库配置", parent_id=top.id, mtype="C",
        path="warehouse", component="wms_master_data/warehouse/index",
        permission="wms_master_data:warehouse:edit", icon="OfficeBuilding", sort=0,
    )
    backend_pages.append(warehouse_page)

    location_page = await _ensure_menu(
        db, cache,
        name="库位管理", parent_id=top.id, mtype="C",
        path="location", component="wms_master_data/location/index",
        permission="wms_master_data:location:list", icon="Location", sort=2,
    )
    backend_pages.append(location_page)
    for sort, name, perm in (
        (1, "新建库位", "wms_master_data:location:create"),
        (2, "编辑库位", "wms_master_data:location:edit"),
    ):
        await _ensure_menu(
            db, cache, name=name, parent_id=location_page.id, mtype="F",
            permission=perm, sort=sort,
        )

    sku_page = await _ensure_menu(
        db, cache,
        name="商品管理", parent_id=top.id, mtype="C",
        path="sku", component="wms_master_data/sku/index",
        permission="wms_master_data:sku:list", icon="Goods", sort=3,
    )
    backend_pages.append(sku_page)
    for sort, name, perm in (
        (1, "新建商品", "wms_master_data:sku:create"),
        (2, "编辑商品", "wms_master_data:sku:edit"),
        (3, "编辑存储要求", "wms_master_data:sku:configure"),
    ):
        await _ensure_menu(
            db, cache, name=name, parent_id=sku_page.id, mtype="F",
            permission=perm, sort=sort,
        )

    partner_page = await _ensure_menu(
        db, cache,
        name="合作方", parent_id=top.id, mtype="C",
        path="partner", component="wms_master_data/partner/index",
        permission="wms_master_data:partner:list", icon="Avatar", sort=4,
    )
    backend_pages.append(partner_page)
    await _ensure_menu(
        db, cache, name="新建合作方", parent_id=partner_page.id, mtype="F",
        permission="wms_master_data:partner:create", sort=1,
    )

    apikey_page = await _ensure_menu(
        db, cache,
        name="API 凭证", parent_id=top.id, mtype="C",
        path="apikey", component="wms_master_data/apikey/index",
        permission="wms_master_data:apikey:list", icon="Key", sort=5,
    )
    backend_pages.append(apikey_page)
    await _ensure_menu(
        db, cache, name="签发凭证", parent_id=apikey_page.id, mtype="F",
        permission="wms_master_data:apikey:create", sort=1,
    )

    team_page = await _ensure_menu(
        db, cache,
        name="班组管理", parent_id=top.id, mtype="C",
        path="team", component="wms_master_data/team/index",
        permission="wms_master_data:team:list", icon="OfficeBuilding", sort=6,
    )
    backend_pages.append(team_page)
    for sort, name, perm in (
        (1, "新建班组", "wms_master_data:team:create"),
        (2, "编辑班组", "wms_master_data:team:edit"),
        (3, "删除班组", "wms_master_data:team:delete"),
    ):
        await _ensure_menu(
            db, cache, name=name, parent_id=team_page.id, mtype="F",
            permission=perm, sort=sort,
        )

    staff_page = await _ensure_menu(
        db, cache,
        name="人员档案", parent_id=top.id, mtype="C",
        path="staff", component="wms_master_data/staff/index",
        permission="wms_master_data:staff:list", icon="User", sort=7,
    )
    backend_pages.append(staff_page)
    for sort, name, perm in (
        (1, "新建人员", "wms_master_data:staff:create"),
        (2, "编辑人员", "wms_master_data:staff:edit"),
        (3, "批量调组", "wms_master_data:staff:bulk-team"),
        (4, "维护工序", "wms_master_data:staff:skill"),
        (5, "维护认证", "wms_master_data:staff:cert"),
        (6, "离职处置", "wms_master_data:staff:leave"),
    ):
        await _ensure_menu(
            db, cache, name=name, parent_id=staff_page.id, mtype="F",
            permission=perm, sort=sort,
        )

    # ── 门户：顶级目录 + 两个页面 ───────────────────────
    portal = await _ensure_menu(
        db, cache,
        name="货主门户", parent_id=0, mtype="M",
        path="/owner", permission="wms_master_data:portal:view",
        icon="Shop", sort=90,
    )

    dashboard = await _ensure_menu(
        db, cache,
        name="概览", parent_id=portal.id, mtype="C",
        path="dashboard", component="wms_master_data/portal/dashboard/index",
        permission="wms_master_data:portal:view", icon="Odometer", sort=1,
    )

    account = await _ensure_menu(
        db, cache,
        name="子账号", parent_id=portal.id, mtype="C",
        path="account", component="wms_master_data/portal/account/index",
        permission="wms_master_data:subaccount:list", icon="UserFilled", sort=2,
    )
    await _ensure_menu(
        db, cache,
        name="新增子账号", parent_id=account.id, mtype="F",
        permission="wms_master_data:subaccount:create", sort=1,
    )

    # P6 业务动作：货主自助建入库预报与出库订单。
    # 门户页面是显式注册的，菜单 component 必须与 router/owner.ts、页面目录三方对齐。
    # 归属靠 permission 前缀表达：停对应业务域时只收起该入口，不动 /owner 子树。
    # component 保持 wms_master_data/portal/* 的物理路径，不迁页面目录。
    portal_asn = await _ensure_menu(
        db, cache,
        name="入库预报", parent_id=portal.id, mtype="C",
        path="asn", component="wms_master_data/portal/asn/index",
        permission="wms_inbound:portal:asn:create", icon="Download", sort=3,
        align_fields=True,
    )
    portal_order = await _ensure_menu(
        db, cache,
        name="出库订单", parent_id=portal.id, mtype="C",
        path="order", component="wms_master_data/portal/order/index",
        permission="wms_outbound:portal:order:create", icon="Upload", sort=4,
        align_fields=True,
    )
    # 商品/库存/账单：三档货主角色都可见，写操作靠 F 按钮与接口权限区分。
    portal_sku = await _ensure_menu(
        db, cache,
        name="商品档案", parent_id=portal.id, mtype="C",
        path="sku", component="wms_master_data/portal/sku/index",
        permission="wms_master_data:portal:view", icon="Goods", sort=5,
    )
    portal_sku_create = await _ensure_menu(
        db, cache,
        name="新建商品", parent_id=portal_sku.id, mtype="F",
        permission="wms_master_data:sku:create", sort=1,
    )
    portal_stock = await _ensure_menu(
        db, cache,
        name="库存查询", parent_id=portal.id, mtype="C",
        path="stock", component="wms_master_data/portal/stock/index",
        permission="wms_inventory:portal:stock:view", icon="Box", sort=6,
        align_fields=True,
    )
    # 账单归属计费域；wms_billing 插件尚未落地，入口保留空状态页，
    # 待计费插件上线后由它接管这块菜单的启停。
    portal_bill = await _ensure_menu(
        db, cache,
        name="账单查询", parent_id=portal.id, mtype="C",
        path="bill", component="wms_master_data/portal/bill/index",
        permission="wms_billing:portal:bill:view", icon="Tickets", sort=7,
        align_fields=True,
    )

    # ── 角色 ────────────────────────────────────────────
    roles = {}
    for code, name, remark in ROLE_SPECS:
        roles[code] = await _ensure_role(db, code, name, remark)

    portal_menus = [portal, dashboard, account]
    await _bind(db, roles["wms_owner_admin"], portal_menus)
    await _bind(db, roles["wms_owner_operator"], [portal, dashboard])
    await _bind(db, roles["wms_owner_viewer"], [portal, dashboard])
    # 建单是业务动作，只读子账号不给
    await _bind(db, roles["wms_owner_admin"], [portal_asn, portal_order])
    await _bind(db, roles["wms_owner_operator"], [portal_asn, portal_order])
    # 查询类页面三档都给；商品新建按钮只给主账号与操作员
    read_menus = [portal_sku, portal_stock, portal_bill]
    await _bind(db, roles["wms_owner_admin"], read_menus + [portal_sku_create])
    await _bind(db, roles["wms_owner_operator"], read_menus + [portal_sku_create])
    await _bind(db, roles["wms_owner_viewer"], read_menus)

    # ── 超管只绑后台菜单，不绑门户 ───────────────────────
    # 门户菜单若绑给超管，员工侧边栏会多出一个点不进去的"货主门户"；
    # 且动态路由是按用户菜单生成的，不绑也就天然隔离了两套界面。
    admin = (await db.execute(select(Role).where(Role.code == "admin"))).scalars().first()
    if admin:
        page_ids = {p.id for p in backend_pages}
        created = [top, *backend_pages]
        # 按钮级权限挂在各页面下，一并绑给超管
        created += [m for m in cache if m.parent_id in page_ids and m.type == "F"]
        await _bind(db, admin, list({m.id: m for m in created}.values()))

    await _ensure_staff_roles(db, cache)
    await _ensure_sku_sequence(db)
    logger.info("主数据域菜单与角色就绪")


# 岗位角色 → 该岗位至少要能看到的权限。
# 入库、出库、盘点各自的菜单在对应期次才建，所以这里先绑"查看类"权限；
# 每期新增菜单后扩展这张表即可，不需要新建角色。
_STAFF_ROLES: list[tuple[str, str, list[str]]] = [
    (
        "wms_receiver",
        "收货员",
        ["wms_master_data:sku:list", "wms_master_data:partner:list", "wms_inventory:stock:list"],
    ),
    (
        "wms_putaway",
        "上架员",
        ["wms_master_data:location:list", "wms_master_data:sku:list", "wms_inventory:stock:list"],
    ),
    (
        "wms_picker",
        "拣货员",
        ["wms_master_data:sku:list", "wms_inventory:stock:list", "wms_inventory:lot:list"],
    ),
    (
        "wms_checker",
        "复核员",
        ["wms_master_data:sku:list", "wms_inventory:txn:list"],
    ),
    (
        "wms_counter",
        "盘点员",
        [
            "wms_master_data:location:list",
            "wms_master_data:sku:list",
            "wms_inventory:stock:list",
            "wms_inventory:lot:list",
            "wms_inventory:adjust:create",
        ],
    ),
    (
        "wms_readonly",
        "只读查看",
        [
            "wms_master_data:owner:list",
            "wms_master_data:location:list",
            "wms_master_data:sku:list",
            "wms_master_data:partner:list",
            "wms_inventory:stock:list",
            "wms_inventory:txn:list",
            "wms_inventory:lot:list",
        ],
    ),
]


async def _ensure_staff_roles(db: AsyncSession, cache: list[Menu]) -> None:
    """建岗位角色并按权限标识绑菜单。

    只绑叶子页面与按钮，不绑顶级目录——目录靠 ``permission`` 前缀由基座联动，
    重复绑会让停用插件时目录摘不干净。
    """
    for code, name, perms in _STAFF_ROLES:
        role = await _ensure_role(db, code, name, f"岗位：{name}")
        wanted = {p for p in perms}
        targets = [m for m in cache if (m.permission or "") in wanted]
        if targets:
            await _bind(db, role, targets)


async def _ensure_sku_sequence(db: AsyncSession) -> None:
    """给货品编码序列补一个起始值。

    这条序列在首次安装时不存在，而 P0 阶段可能已经手工插入过 ``SKU000001``。
    不校正起点的话，第一次正规建档就会撞唯一键。
    """
    from src.plugins.builtin.wms_master_data.models import WmsSequence, WmsSku

    row = (
        await db.execute(
            select(WmsSequence).where(
                WmsSequence.prefix == "SKU", WmsSequence.period == ""
            )
        )
    ).scalars().first()
    if row is not None:
        return

    codes = (await db.execute(select(WmsSku.code))).scalars().all()
    current = 0
    for code in codes:
        suffix = code[3:] if code.startswith("SKU") else ""
        if suffix.isdigit():
            current = max(current, int(suffix))

    db.add(WmsSequence(prefix="SKU", period="", current=current))
    await db.flush()
