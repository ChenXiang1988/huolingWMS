# Tasks

## 1. 数据模型与建表

- [x] 1.1 在 `backend/src/plugins/builtin/wms_master_data/models.py` 给 `WmsTeam` 加 `floor_no`、`dispatch_limit_default`，给 `WmsStaff` 加 `role`、`left_pending_at`、`left_at`、`quality_cert`、`quality_team`，全部可空。验证：模型可导入，字段类型与 design.md 的 ER 图逐项一致。
- [x] 1.2 新建 `WmsTeamZone`、`WmsStaffSkill`、`WmsStaffCert`、`WmsStaffLog` 四个模型及索引与唯一约束，并在 `plugin.py` 注册。验证：后端连 MySQL 启动后四张表存在，`SHOW CREATE TABLE` 含预期索引，重启不报建表错误。
- [x] 1.3 更新 `docs/design/data-model.md` 的班组与人员字段、四张新表、状态与在办上限口径。验证：文档字段与模型定义逐项对照无遗漏，`status` 描述改为在岗／不在岗与启用／停用。

## 2. 后端业务规则

- [x] 2.1 改造 `create_team`／`update_team`：名称同仓唯一与 1–20 字、楼层属本仓启用集、区域属该楼层且至少一个、换楼层清空越层区域并回传数量、组长必填且新建选中即归组、编辑只从本组成员中选、区域关联写入 `WmsTeamZone`、编号走 `WmsSequence` 不回收。验证：TC-01、TC-02、TC-03 与 E-01～E-05 手工调用均得到规格中的结果。
- [x] 2.2 改造 `toggle_team`：移除"有在职成员拒绝停用"的前置，停用只改状态并保留归属与位置，响应回传受影响组成员。验证：TC-04 中 7 人班组可直接停用，人员归属不变、状态标记同步，重新启用后恢复。
- [x] 2.3 新增 `delete_team`：有成员时拒绝，只剩组长时二次确认后删除，组长转未分组待配置并写 `WmsStaffLog(kind=team)`，编号不回收。验证：E-13、E-14、TC-15 逐条通过，删除后人员档案仍在。
- [x] 2.4 改造单人调组并新增 `bulk_transfer`：班组长、已离职、已在目标组的人跳过并逐条列名，其余改归属且各写一条归属日志，两组人数与在岗数重算。验证：TC-07、TC-08、E-06、E-08 通过，最新日志的新组等于当前归属。
- [x] 2.5 改造 `update_staff`：状态按在岗／不在岗两态、`left_at` 非空时拒绝复职、待离职与离职时间写入、可做工序与认证及质检持证写子表、已归组人员至少保留一道工序。验证：TC-09、TC-10、TC-11 与 S-ST-15 通过，`left_at` 有值的人员不可改回在岗。
- [x] 2.6 实现派生读数与查询过滤：可承接工序、可派人数、成员数、在岗数、配置状态、认证到期三态、组内身份、区域覆盖；班组 6 类与人员 11 类查询参数、多词全命中、时间含端点且起点晚于终点返回 400。验证：TC-05、TC-06、TC-12、TC-13、E-09 通过，组合条件按且收窄。
- [x] 2.7 实现绑定单元与在办数的可选 provider 注入，缺 provider 时回落「未登录」与 0 并在响应中标记未同步。验证：不注入 provider 启动后端，人员列表不报错且显示回落值，下游模块不产生 import 依赖。

## 3. API 与权限

- [x] 3.1 在 `api.py` 扩展两个列表接口的查询参数，新增 `DELETE /teams/{id}`、`POST /staffs/bulk-team`、`PUT /staffs/{id}/skills`、`PUT /staffs/{id}/certs`、`POST /staffs/{id}/leave`。验证：接口文档可见全部端点，成功与校验失败路径的响应码符合 specs。
- [x] 3.2 在 `seed.py` 补齐 `wms_master_data:team:delete` 与 `staff:bulk-team`、`staff:skill`、`staff:cert`、`staff:leave` 权限及菜单按钮。验证：管理员可见新建、编辑、启停、删除与批量栏，只读角色无这些入口。
- [x] 3.3 更新 `docs/design/interface-map.md` 的权限清单、接口表与规则说明。验证：文档接口数与 `api.py` 实际路由一致，停用与离职规则说明已替换为新口径。

## 4. 前端 API 客户端

- [x] 4.1 在 `frontend/src/api/wms_master_data.ts` 补齐新增接口与查询参数类型，移除不再使用的旧字段。验证：`npm run build` 退出码 0，无类型错误与未使用导入。

## 5. 前端班组视图

- [x] 5.1 改造 `frontend/src/views/wms_master_data/team/index.vue` 列表：状态页签、六类查询条件、区域覆盖读数、班组编号／名称／仓库／楼层／管辖区域／班组长／成员数／在岗／可派人数／可承接工序／状态／操作列。验证：TC-05、TC-13、TC-14 通过，读数随仓与班组启停重算。
- [x] 5.2 改造班组抽屉：新建与编辑共用、楼层与区域联动、组长候选按新建／编辑分流、在办上限默认可空、启停结果提示、删除二次确认、行内「成员」下钻。验证：TC-01～TC-04、TC-06、TC-15 通过，保存失败时抽屉不关且已填内容保留。
- [x] 5.3 更新 `docs/design/ui-map.md` 的班组与人员菜单、页面与抽屉说明。验证：文档页面路径与 `frontend/src/views/wms_master_data/` 实际目录一致，两个视图的分段与按钮描述完整。

## 6. 前端人员视图

- [x] 6.1 改造 `frontend/src/views/wms_master_data/staff/index.vue` 列表：在岗／不在岗页签、11 类查询条件（常用三项常显、其余默认收起）、条件回显 chip 与逐项移除、重置、工号／姓名／仓库／班组加班组长标签／角色／可做工序／认证／状态／绑定单元／操作列、勾选后的批量栏。验证：TC-07、TC-08、TC-11、TC-12 通过，页签切换清空查询条件。
- [x] 6.2 改造人员抽屉：基本信息、班组归属（班组长置灰）、离职处置（仅待离职显示，含全部回池与改派跳转）、可做工序、认证与质检持证、最近记录；空绑定单元显示「未登录」。验证：TC-09、TC-10 与 E-06、E-07 通过，离职确认后行显示「不在岗 已离职」。

## 7. 集成走查

- [x] 7.1 按 PRD 的 TC-01～TC-15 全量走查两次保存链路：班组保存后人员视图同步、人员调组后班组读数同步。验证：15 条用例逐条有通过或失败结论，失败项定位到具体接口与字段。
- [x] 7.2 执行 `docker compose run --rm backend pytest` 与 `npm run build`（在 `backend/`、`frontend/` 各自目录运行；项目无测试目录时以启动与接口冒烟替代）。验证：两条命令退出码 0，无新增 lint 错误。

## Workflow follow-up

- 评审通过后归档变更，把 `specs/wms/team-staff/spec.md` 的增量同步到 `openspec/specs/wms/team-staff/spec.md`。
- 归档前执行 `openspec validate enrich-team-staff-data --strict`，确认无未满足依赖。
