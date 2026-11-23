# Tasks

## 1. 数据模型与插件安装

- [x] 1.1 在 `backend/src/plugins/builtin/wms_master_data/models.py` 追加 `WmsTeam`、`WmsStaff` 两个模型（字段与约束见 design.md 第 3 节），并把两个 `__table__` 加入 `plugin.py` 的 `_TABLES`。验证：重启 backend 触发插件安装后，在 MySQL 执行 `SHOW TABLES LIKE 'wms_master_data_%'` 能看到两张新表。
- [x] 1.2 为 `team.code`、`staff.code`、`staff.user_id` 建唯一索引，为 `staff(team_id, status)` 建普通索引。验证：`SHOW INDEX` 能看到上述索引，重复工号写入被唯一约束拒绝。

## 2. service 层约束与映射查询

- [x] 2.1 在 `service.py` 实现建档时的账号绑定校验：查 `WmsUserOwner.user_id` 拒绝已绑定货主的账号，查 `WmsStaff.user_id` 拒绝重复绑定，未指定 `user_id` 时直接建档。验证：按 spec「人员档案可绑账号也可独立存在」的四个场景逐个调用，货主账号与重复绑定均返回明确拒绝提示，临时工建档成功且账号为空。
- [x] 2.2 实现调组、离职、停用班组时的班长自动清空与在职成员计数，三条动作共用同一份归属校验。验证：按 spec「班长是本班组成员」和「班组停用前清空在职成员」的全部场景操作，班长调离后自动清空、有在职成员时停用被拒绝、清空后停用成功。
- [x] 2.3 实现 `get_staff_by_user(user_id)` 只读映射查询，只返回在职且已绑定账号的人员。验证：按 spec「提供账号到在职人员的映射查询」的三个场景调用，未绑定、货主账号、已离职均返回空结果。

## 3. 后端接口

- [x] 3.1 在 `api.py` 增加 teams 的 list/create/edit/leader/toggle 五个路由与入参类，挂载 `wms_master_data:team:*` 权限。验证：超管逐个调用返回统一响应，未授权账号被拒绝，停用接口走 2.2 的成员校验。
- [x] 3.2 在 `api.py` 增加 staffs 的 list/create/edit/team/by-user 五个路由与入参类，挂载 `wms_master_data:staff:*` 权限，`team_id` 不出现在通用编辑的入参中。验证：超管逐个调用返回统一响应，按 `team_id`、`status` 筛选结果正确，未授权账号被拒绝。

## 4. 菜单权限与前端页面

- [x] 4.1 在 `frontend/src/api/wms_master_data.ts` 追加上述 10 个接口调用方法。验证：`npm run build` 类型检查通过，页面调用返回预期数据。
- [x] 4.2 在 `seed.py` 注册两个叶子菜单与按钮权限，`component` 分别为 `wms_master_data/team/index` 与 `wms_master_data/staff/index`。验证：重新登录后台后主数据域下出现「班组管理」「人员档案」，角色绑定的按钮权限可勾选。
- [x] 4.3 新建 `frontend/src/views/wms_master_data/team/index.vue`，实现班组列表、新建、编辑、指定班长、停用与启用。验证：`npm run dev` 后页面无报错，按 spec 的班组场景走通指定班长与有成员停用拦截。
- [x] 4.4 新建 `frontend/src/views/wms_master_data/staff/index.vue`，实现人员列表、建档时可选账号、状态变更与调组。验证：`npm run dev` 后页面无报错，按 spec 的人员场景走通临时工建档、账号重复绑定拦截与重复加入拦截。

## 5. 详设同步与集成验证

- [x] 5.1 更新 `docs/design/data-model.md` 的主数据域表清单，更新 `docs/design/interface-map.md` 的权限标识表与后台路由表。验证：文档中的表名、权限标识、路径与代码逐项一致，无遗漏条目。
- [x] 5.2 端到端走一遍：建班组 → 建正式员工并绑账号 → 建临时工 → 加入班组 → 指定班长 → 调组 → 停用班组 → 按账号查人员。验证：每步结果与 spec 场景一致，既有单据页的 `operator_id` 显示未发生变化。
