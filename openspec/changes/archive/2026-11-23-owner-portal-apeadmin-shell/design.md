# Design

## Context

现有前端是双产物工程：后台 `main.ts` + `router/index.ts`（base `/admin/`）与门户 `main-owner.ts` + `router/owner.ts`（base `/owner/`）。两端共享 Element Plus、主题 CSS、权限指令和 Pinia user store，但 shell 各写一套：后台用 `ApeSidebar` + `ApeHeader`，门户用 `OwnerLayout.vue` 自己的 220px 白底侧栏。

后端用 `/owner-login` 与 `/auth/login` 两个接口在登录阶段分流；`owner_of_user()` 从 `wms_master_data_user_owner` 注入 `owner_id`；前端门户页面只调 `wms_portal.ts` 里的接口，请求体不带 `owner_id`。

当前门户的菜单来自 seed 的 `/owner` 子树，经 `/auth/userinfo` 返回后在 `OwnerLayout.vue` 渲染；已有概览、子账号、入库预报、出库订单四个页面。库存域有 `/stocks`、`/stocks/detail`、`/txns` 等查询接口，但没有门户专用入口；后端没有 `wms_billing` 插件，账单数据尚无来源。

## Goals / Non-Goals

**Goals:**

- 门户登录后获得与后台一致的侧栏、顶栏、主题、国际化与品牌设置。
- 补齐规格承诺的库存查询、账单查询、商品档案创建页面及对应后端接口。
- 新增菜单与角色绑定按"主账号 / 操作员 / 只读"三档授权。
- 保持双产物、双登录接口、跨端会话判定不变。

**Non-Goals:**

- 不改登录页视觉，不把门户登录并入后台登录页。
- 不开放库位管理、盘点、任务执行、计费费率维护等仓库内部页面给货主。
- 本次不实现计费引擎、不出真实账单数据；账单查询交付只读接口契约与空状态，费用数据来源随 `wms/billing` 后续落地接入。
- 不调整商品档案的仓库侧字段（上架要求、温区、库位策略）。

## Decisions

### 1. 共享 shell 组件，不共享路由与入口

`main-owner.ts` 继续作为独立入口，挂载同一个 `ApeSidebar` / `ApeHeader` 组件；`OwnerApp.vue` 改为后台 `layout/index.vue` 同构的 shell 结构，但 router 仍是 `ownerRouter`（base `/owner/`），路由表与后台 `staticRoutes` 互不引用。

理由：历史隔离要求的是"入口、登录、会话判定分开"，组件本身无身份语义。直接复用组件比复制样式更不容易漂移，也不破坏 spec 的跨端清会话规则。

被否决的方案：把门户做成后台的动态路由子集——那会让 `createWebHistory('/admin/')` 改写门户地址，且货主 token 会进入后台路由守卫。

```mermaid
graph LR
    subgraph 门户产物[/owner/]
        OL[owner-login 接口] --> OT[货主 token]
        OT --> OS[ownerRouter + ApeSidebar/ApeHeader]
    end
    subgraph 后台产物[/admin/]
        AL[auth/login 接口] --> AT[员工 token]
        AT --> AS[router/index + ApeSidebar/ApeHeader]
    end
    OS -.共享组件.-> AS
    OS -.-x|跨端 token 清空回本端| AS
```

### 2. 门户页面保持独立实现，不挂后台动态路由

新增页面仍放在 `src/views/wms_master_data/portal/`，在 `router/owner.ts` 显式注册，菜单 `component` 与路由、目录三方对齐。后台动态路由对 `/owner` 目录继续跳过。

理由：门户页的数据接口都走 `wms_portal.ts`，由服务端注入 `owner_id`；后台页面的列表接口带仓库侧权限，直接复用会把货主导向无权限接口。

### 3. 库存查询复用库存域只读能力，新增门户代理接口

库存域已有 `/stocks`、`/stocks/detail`、`/txns`，但要求仓库侧权限。新增 `/wms-inventory/portal/stocks`、`/portal/stocks/detail`、`/portal/txns`，内部调用库存域同一份查询实现，入口按会话 `owner_id` 过滤。

理由：避免门户另写一套库存查询逻辑，也避免把后台接口权限直接授予货主角色。

### 4. 商品创建走主数据域，字段分工落在 API 边界

新增 `POST /wms-master-data/portal/skus`，只接收货主侧字段（编码、名称、规格、条码、批次开关），`owner_id` 从会话取；仓库侧字段由默认值初始化，不接受该接口写入。

理由：`createSku` 现有实现同时收两组字段，直接开放会让货主改到上架要求。边界处丢弃非法字段比在页面端隐藏更可靠——隐藏字段仍能通过构造请求提交。

### 5. 账单查询先建契约，数据来源留空

新增 `GET /wms-billing/portal/bills` 与 `/bills/{id}/items`（或并入主数据域的 portal 前缀，取决于插件落地方式），当前返回空列表。页面按账期展示，无数据时给出明确的"暂无账单"状态。

理由：后端没有 `wms_billing` 插件，现在生成假费用会违反 `wms/billing` 的"费用只由已完成作业事实派生"。先把接口契约和货主可见性固定下来，计费域落地时只换数据来源。

### 6. 菜单 seed 增量补齐，幂等绑定角色

在 `wms_master_data/seed.py` 的门户菜单段追加库存、账单、商品档案三个 C 类菜单和必要 F 类按钮，用现有 `_ensure_menu` 保证重复执行不产生重复行。角色绑定按三档：主账号全量，操作员除子账号管理，只读仅查询与查看明细。

理由：现有 seed 已用 `_ensure_menu` + `_bind` 做增量，沿用同一模式即可；角色绑定漏一处就会出现"菜单可见但点进去 404"。

## Risks / Trade-offs

- [共享 shell 组件后样式耦合] 后台改 `ApeSidebar` 会同时影响门户 → 接受；这正是统一视觉的目的，两端的差异留给菜单数据与品牌配置。
- [账单页短期无数据] 用户看到空列表可能误以为功能坏了 → 页面明确写"账单随计费上线开放"，不伪装成有数据。
- [商品创建字段分工靠 API 边界] 货主仍可能尝试构造仓库侧字段 → 边界忽略或拒绝这些字段，并在 spec 场景里固定该行为。
- [库存 portal 接口重复维护] 若库存域查询签名变化，代理层需同步 → 代理层只做 `owner_id` 注入，不做字段重排，缩小同步面。

## Migration Plan

1. 前端：改 `main-owner.ts` / `OwnerApp.vue` / `OwnerLayout.vue`，不碰 `main.ts` 与后台路由。
2. 后端：加 portal 接口与菜单 seed，重启后端触发 seed；既有账号密码不变，菜单在下次登录后出现。
3. 验证：用 `own001`（主账号）与新建只读子账号分别登录，核对菜单集合、库存隔离、商品创建字段边界、账单空状态。
4. 回滚：前端回退本次提交的 shell 与路由改动；后端撤回新增 portal 路由与菜单 seed 行，重启后菜单消失。

## Open Questions

无。
