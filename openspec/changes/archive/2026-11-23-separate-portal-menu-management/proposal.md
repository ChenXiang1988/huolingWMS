# Proposal

## Why

货主门户的菜单当前全部归入 `wms_master_data` 域（component 前缀 `wms_master_data/portal/*`、permission 前缀 `wms_master_data:*`），与 `docs/design/ui-map.md:63-78` 的域归属规划不符。后果是停用库存、入库、出库等域时，门户对应入口不会收起——spec `wms/owner-access` 的"自助端菜单随所属域停用而收起"在当前实现中不成立。

同时，后台「系统管理 → 菜单管理」把后台菜单和 `/owner` 门户菜单混在同一棵树里，管理员只能靠 path/component 肉眼区分，容易误改。用户明确要求两端菜单分开维护。

## What Changes

- 修正门户菜单的域归属标签：库存查询改挂 `wms_inventory`、入库预报改挂 `wms_inbound`、出库订单改挂 `wms_outbound`、账单查询改挂 `wms_billing`（无插件时保持隐藏或不注册）、商品档案与概览保持 `wms_master_data`。
- 修正方式只动菜单行的 `permission` 与 `component` 前缀，不动 `path`（`/owner` 顶级节点与其子树结构不变），因此后台侧栏和动态路由现有的 `path==='/owner'` 过滤继续有效，门户菜单不会出现在 admin 侧栏。
- 后台 `/menus/tree` 接口增加按端筛选的参数，使菜单管理页能分别取后台菜单树与货主门户菜单树。
- 后台菜单管理页拆成两个视图（标签页或分区）：「后台菜单」与「货主门户菜单」，各自只显示、编辑、新增本端的菜单；新增时自动带上本端约束（后台视图排除 `/owner`，门户视图限定 `/owner` 子树）。
- 后端在菜单写接口增加端归属校验，防止管理员通过后端口径把门户菜单挂到后台目录或反之。

## Capabilities

### New Capabilities

无。

### Modified Capabilities

- `wms/owner-access`: 明确"自助端菜单随所属域停用而收起"的具体归属规则——门户每个功能入口归属于其业务域而非统一挂主数据域；明确两端菜单在管理侧分开维护、但共用一张菜单表与一套角色绑定。
- `wms/admin-navigation`: 补充后台菜单管理能力的可见范围——菜单管理页分「后台菜单」「货主门户菜单」两棵独立树，新增/编辑时按当前视图约束归属。

## Impact

- 后端：`wms_master_data/seed.py` 门户菜单行的 permission/component 前缀；`api/menu.py` 的 `/menus/tree` 与写接口的端归属校验；`manager.py` 的域停用匹配规则不变（靠前缀自动生效）。
- 前端：`src/views/system/menu/index.vue` 拆两棵树视图；`src/api` 菜单接口调用带端参数。
- 数据：现有库里已 seed 的门户菜单行需要随新 seed 更新前缀（幂等 `_ensure_menu` 按 name+parent 定位后更新字段，或提供一次性迁移）。
- 兼容性：货主看到的菜单名称、顺序、页面内容不变；只是域归属标签与后台管理界面分组变化。停用主数据域仍会让整个门户收起（顶级 `/owner` 归主数据，符合 spec）。
