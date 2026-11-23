# Proposal: 重构管理后台导航

## Why

管理后台侧栏把货主门户当成普通业务目录展示,员工点进去却没有可用页面;作业动作散在单据目录里,货主推送的订单与仓库内部单据混在一起。404 页的「返回首页」跳到不存在的 `/dashboard`,又落回 404。这些都是导航结构问题,逐页改配置会反复出现同样的错配。

## What Changes

- 管理后台侧栏不再渲染货主门户顶级目录;菜单表和货主独立入口保留。
- 新增一级菜单「作业台」,收纳分播作业、拣货、复核与发运;三页从「出库」迁出,已有库原位改挂父级。
- 新增一级菜单「客户服务」,收纳入库预报与出库订单;这两张是当前仅有的货主推送单据,从「入库」「出库」迁出,已有库原位改挂父级。服务订单、退货单由仓库建单,留在原处。
- 404 页「返回首页」按端跳转:后台去 `/dashboard-monitor`,货主门户仍去 `/dashboard`。

**BREAKING**: 作业页与订单页的完整路由前缀变化,例如 `/wms-outbound/seed` 变为 `/wms-workbench/seed`、`/wms-inbound/asn` 变为 `/wms-customer-service/asn`。旧书签会落到 404。

## Capabilities

### New Capabilities

- `wms/admin-navigation`: 管理后台一级导航的分组规则——门户隔离、作业台、客户服务,以及 404 页回首页行为。

### Modified Capabilities

- `wms/platform-bootstrap`: 「菜单基线只含货灵模块」原要求初始化后呈现门户根,改为门户根只存在于菜单表、不进管理后台侧栏。

## Impact

- `backend/src/core/seed.py`: 基座菜单增加客户服务顶级目录。
- `backend/src/plugins/builtin/wms_outbound/seed.py`: 作业台与出库订单的挂靠与迁移。
- `backend/src/plugins/builtin/wms_inbound/seed.py`: 入库预报的挂靠与迁移。
- `frontend/src/components/ApeSidebar.vue`: 侧栏过滤门户目录。
- `frontend/src/views/error/404.vue`: 按端决定回首页目标。
- 已初始化的数据库在下次启动时原位迁移菜单父级,不重建记录、不丢按钮权限与新菜单的角色绑定。
