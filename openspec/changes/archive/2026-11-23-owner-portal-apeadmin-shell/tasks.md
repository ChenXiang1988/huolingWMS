# Tasks

## 1. 门户外壳复用后台 shell

- [x] 1.1 改 `frontend/src/main-owner.ts`：挂载 i18n 实例、Element Plus locale 映射、`fetchPublicSettings()`，保留 `owner-login` 与 `ownerRouter`，验证打开 `/owner/login` 仍走货主登录接口且登录页视觉不变。
- [x] 1.2 改 `frontend/src/OwnerApp.vue` 与 `frontend/src/layout/OwnerLayout.vue`：引入 `ApeSidebar` / `ApeHeader` 同构 shell，菜单仍从 user store 的 `/owner` 子树读取，验证主账号登录后侧栏只出现货主菜单、没有后台内部模块。
- [x] 1.3 保持 `vite.config.ts` 的双入口与 dev HTML 替换插件不动，验证 `npm run dev:owner` 打开 `http://127.0.0.1:5174/` 跳到 `/owner/login`，`npm run build:owner` 产物落在 `dist/owner`。
- [x] 1.4 验证跨端会话：员工 token 打开门户、货主 token 打开后台，各自清空会话回本端登录页，不出现重定向到另一端。

## 2. 货主商品档案自助创建

- [x] 2.1 在 `wms_master_data` 插件新增 `POST /wms-master-data/portal/skus`：`owner_id` 从会话取，只接收货主侧字段，仓库侧字段由默认值初始化且构造请求提交时忽略或拒绝；验证用货主 token 创建成功且商品归属正确。
- [x] 2.2 在 `frontend/src/api/wms_portal.ts` 增加商品创建与列表调用，新增 `src/views/wms_master_data/portal/sku/index.vue` 表单与列表，验证表单不出现仓库侧字段。
- [x] 2.3 在 `router/owner.ts` 注册 `sku` 路由并在 seed 增加菜单与角色绑定，验证主账号与操作员可见、只读账号不可见且直接访问被拒。

## 3. 货主库存查询

- [x] 3.1 在 `wms_inventory` 插件新增 `/portal/stocks`、`/portal/stocks/detail`、`/portal/txns`，内部复用现有查询实现并按会话 `owner_id` 过滤；验证 own001 与 own002 查询结果互不串数据。
- [x] 3.2 在 `frontend/src/api/wms_portal.ts` 增加库存查询调用，新增 `src/views/wms_master_data/portal/stock/index.vue` 展示库存与流水，验证页面能调通接口且货主看不到其他货主商品。
- [x] 3.3 在 `router/owner.ts` 注册 `stock` 路由并在 seed 增加菜单与角色绑定，验证三种货主角色都可见、只读账号可读不可写。

## 4. 货主账单查询契约

- [x] 4.1 新增账单 portal 只读接口（无 `wms_billing` 插件时返回空列表），接口按会话 `owner_id` 限定范围且不接受写操作；验证返回结构含账期与明细字段、货主无法修改。
- [x] 4.2 在 `frontend/src/api/wms_portal.ts` 增加账单调用，新增 `src/views/wms_master_data/portal/bill/index.vue`，验证无数据时显示"账单随计费上线开放"而非报错或空白。
- [x] 4.3 在 `router/owner.ts` 注册 `bill` 路由并在 seed 增加菜单与角色绑定，验证三种货主角色都可见。

## 5. 端到端验收

- [x] 5.1 用 `own001`（主账号）登录门户，逐个打开概览、库存、账单、商品档案、入库预报、出库订单、子账号七个入口，确认无 404 且数据与本货主一致。
- [x] 5.2 新建 `own001` 的只读子账号并登录，确认只见查询类页面、无创建与管理入口，直接调用商品创建接口被拒。
- [x] 5.3 停用一个货主域后重新登录，确认对应门户入口消失，验证 spec 中"自助端菜单随所属域停用而收起"的场景。（由 separate-portal-menu-management 修正域归属后验证通过：停 wms_inventory / wms_outbound 入口收起，停 wms_master_data 整个门户收起）
- [x] 5.4 更新 `docs/演示手册.md` 的门户账号段（用户名小写）与页面清单，验证手册描述与实际界面一致。
