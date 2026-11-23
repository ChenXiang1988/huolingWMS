# Tasks

## 1. 修正门户菜单域归属

- [x] 1.1 扩展 `wms_master_data/seed.py` 的 `_ensure_menu`，使按 name+parent 定位到已有行时回填期望的 permission/component；验证重复执行 seed 不产生重复菜单且字段被纠正。
- [x] 1.2 把门户库存查询 permission 改为 `wms_inventory:portal:stock:view`、入库预报改为 `wms_inbound:portal:asn:create`、出库订单改为 `wms_outbound:portal:order:create`；保持 path 与 component 原值；验证种子执行后数据库字段正确。
- [x] 1.3 重新执行 seed 并验证 own001 登录后菜单名称与顺序不变、页面可正常打开；验证 `auth/userinfo` 返回的 permissions 含新前缀且不含旧前缀。
- [x] 1.4 停 `wms_inventory` 域后重新登录 own001，验证库存查询入口消失而概览、商品档案、入库预报、出库订单仍在；恢复域后入口回来。

## 2. 菜单树接口按端隔离

- [x] 2.1 `GET /menus/tree` 增加可选 `scope=admin|owner` 参数，分别返回 `path!='/owner'` 的分支和 `/owner` 整支，不传时返回全量；验证三种取值返回集合正确。
- [x] 2.2 菜单新增/编辑请求体增加可选 `scope`，后端校验父子关系不得跨端（owner 的 parent 必须在 `/owner` 子树、admin 的 parent 不得在 `/owner` 子树）；验证构造跨端请求被拒绝。
- [x] 2.3 更新 `frontend/src/api` 的菜单接口类型，支持 scope 参数，验证 typecheck 通过。

## 3. 菜单管理页拆两棵树

- [x] 3.1 `frontend/src/views/system/menu/index.vue` 顶部加「后台菜单 / 货主门户菜单」切换，按当前 scope 拉取对应树；验证切换后表格只显示本端菜单。
- [x] 3.2 新增/编辑 dialog 提交时带上当前 scope，父节点下拉只列本端节点；验证在门户视图新增的菜单出现在 `/owner` 子树、后台视图看不到。
- [x] 3.3 验证跨端编辑被拒绝并有明确提示：门户菜单的父节点选项里没有后台目录，直接构造请求也被后端 2.2 拦住。

## 4. 端到端验收与回归

- [x] 4.1 验证后台侧栏不出现货主门户菜单，货主侧栏不出现后台菜单，与改动前一致。
- [x] 4.2 停 `wms_outbound` 域后 own001 重新登录，出库订单入口消失、后台侧栏无门户菜单；恢复后入口回来。
- [x] 4.3 验证停 `wms_master_data` 域后整个门户收起（顶级 `/owner` 仍归主数据），符合 spec。
- [x] 4.4 更新 `docs/design/ui-map.md` 的门户菜单表，把账单行标注为"待 wms_billing 插件落地后注册"，其余行的 component 保持实际值并补一句说明归属由 permission 前缀表达，验证文档与 seed 一致。
