# 接口与权限清单

**层：详细设计** ｜ 蓝图见 [design.md](../../openspec/changes/archive/2026-11-21-define-wms-blueprint/design.md)，字段见 [data-model.md](data-model.md)。这里列的是要实现的东西，不是示例。

## 权限标识

格式 `wms_<域>:<资源>:<动作>`，动作取 `list / view / create / edit / delete / confirm / cancel / execute`。

| 域 | 资源 | 动作 | 权限标识 |
|---|---|---|---|
| 主数据 | 仓库配置 | view/edit | `wms_master_data:warehouse:*` |
| 主数据 | 货主 | list/create/edit/delete | `wms_master_data:owner:*` |
| 主数据 | 货主 API 凭证 | list/create/edit/delete | `wms_master_data:apikey:*` |
| 主数据 | 子账号 | list/create/edit | `wms_master_data:subaccount:*` |
| 主数据 | 库区 | list/create/edit/delete | `wms_master_data:zone:*` |
| 主数据 | 库位 | list/create/edit/delete | `wms_master_data:location:*` |
| 主数据 | 商品（基础信息） | list/create/edit/delete | `wms_master_data:sku:*` |
| 主数据 | 商品（存储要求） | configure | `wms_master_data:sku:configure` |
| 主数据 | 合作方 | list/create/edit/delete | `wms_master_data:partner:*` |
| 主数据 | 班组 | list/create/edit/delete | `wms_master_data:team:*` |
| 主数据 | 人员档案（人员字段来自用户管理） | list/create/edit/bulk-team/skill/cert/leave | `wms_master_data:staff:*` |
| 主数据 | 门户入口 | view | `wms_master_data:portal:view` |
| 库存 | 库存 | list/view | `wms_inventory:stock:list` / `:view` |
| 库存 | 库存调整 | create | `wms_inventory:adjust:create` |
| 库存 | 流水 | list | `wms_inventory:txn:list` |
| 库存 | 批次 | list/view | `wms_inventory:lot:list` / `:view` |
| 库存 | 临期清单 | list | `wms_inventory:lot:expiring` |
| 入库 | 入库预报 | list/view/create/edit/cancel | `wms_inbound:asn:*` |
| 入库 | 服务订单 | list/create/edit/cancel | `wms_inbound:service_order:*` |
| 入库 | 收货 | list/create/execute | `wms_inbound:receipt:*` |
| 入库 | 上架 | list/create/execute | `wms_inbound:putaway:*` |
| 库内 | 移库 | list/create/execute | `wms_internal_ops:transfer:*` |
| 库内 | 盘点 | list/create/execute/confirm | `wms_internal_ops:count:*` |
| 库内 | 留样 | list/view/execute | `wms_internal_ops:sample:*` |
| 出库 | 出库订单 | list/view/create/edit/cancel | `wms_outbound:order:*` |
| 出库 | 波次规则 | list/create/edit/delete | `wms_outbound:wave_rule:*` |
| 出库 | 波次 | list/create/execute/cancel | `wms_outbound:wave:*` |
| 出库 | 分配 | execute | `wms_outbound:allocation:execute` |
| 出库 | 拣货 | list/execute | `wms_outbound:pick:execute` |
| 出库 | 分播 | execute | `wms_outbound:seed:execute` |
| 出库 | 复核称重 | execute | `wms_outbound:check:execute` |
| 出库 | 发运与打面单 | execute | `wms_outbound:shipment:execute` |
| 库内 | 补货 | list/create/execute | `wms_internal_ops:replenish:*` |
| 逆向 | 库存处置 | list/create/execute | `wms_returns:disposal:*` |
| 逆向 | 退货单 | list/create/execute | `wms_returns:return:*` |
| 任务 | 任务 | list/create/execute | `wms_tasking:task:*` |
| 计费 | 费率 | list/create/edit | `wms_billing:rate:*` |
| 计费 | 费用明细 | list | `wms_billing:charge:list` |
| 计费 | 账单 | list/create/confirm | `wms_billing:invoice:*` |
| 报表 | 报表 | list | `wms_reporting:report:list` |
| 集成 | 同步配置 | list/create/edit | `wms_integration:endpoint:*` |
| 集成 | 同步日志 | list/execute | `wms_integration:log:*` |
| 集成 | 手工同步 | execute | `wms_integration:sync:execute` |

角色绑定（D13）：

| 角色 | 授权范围 |
|---|---|
| `wms_admin` | 全部 `wms_*:*:*` |
| `wms_receiver` | `wms_inbound:asn:list`、`wms_inbound:receipt:*` |
| `wms_putaway` | `wms_inbound:putaway:*`、`wms_tasking:task:execute` |
| `wms_picker` | `wms_outbound:pick:execute`、`wms_tasking:task:execute` |
| `wms_checker` | `wms_outbound:check:execute`、`wms_outbound:shipment:execute` |
| `wms_counter` | `wms_internal_ops:count:*` |
| `wms_viewer` | 各域 `:list` |
| `wms_owner_admin` | 本货主的 `:list`、`wms_master_data:sku:create/edit`、`wms_inbound:asn:create`、`wms_inbound:service_order:create`、`wms_outbound:order:create`、`wms_master_data:subaccount:*`、`wms_master_data:portal:view` |
| `wms_owner_operator` | 本货主的 `:list`、`wms_master_data:sku:create/edit`、`wms_inbound:asn:create`、`wms_inbound:service_order:create`、`wms_outbound:order:create`、`wms_master_data:portal:view` |
| `wms_owner_viewer` | 本货主的 `:list`、`wms_master_data:portal:view` |

货主侧与仓库侧用两个不同权限：`sku:create/edit` 只写基础信息组（含 `qty_per_box`），`sku:configure` 只写仓库侧字段（`default_zone_id`、`qty_per_pallet`、`putaway_note`）。两组字段不重叠，`services.update_sku` 按调用的权限拒绝越组字段，接口也拆成两个——`PUT /skus/{id}` 与 `PUT /skus/{id}/storage`。

## 后台路由

前缀 `/api/v1/wms-<域>`，全部要求 JWT 登录态 + 权限标识。响应统一 `success_response(data, msg)`。

| 方法 | 路径 | 权限 |
|---|---|---|
| GET | `/wms-master-data/warehouse` | `wms_master_data:warehouse:view` |
| PUT | `/wms-master-data/warehouse` | `wms_master_data:warehouse:edit` |
| GET | `/wms-master-data/owners` | `wms_master_data:owner:list` |
| POST | `/wms-master-data/owners` | `wms_master_data:owner:create` |
| PUT | `/wms-master-data/owners/{id}` | `wms_master_data:owner:edit` |
| GET | `/wms-master-data/owners/{id}/apikeys` | `wms_master_data:apikey:list` |
| POST | `/wms-master-data/owners/{id}/apikeys` | `wms_master_data:apikey:create` |
| DELETE | `/wms-master-data/apikeys/{id}` | `wms_master_data:apikey:delete` |
| GET | `/wms-master-data/portal/accounts` | `wms_master_data:subaccount:list` |
| POST | `/wms-master-data/portal/accounts` | `wms_master_data:subaccount:create` |
| PUT | `/wms-master-data/portal/accounts/{id}` | `wms_master_data:subaccount:edit` |
| POST | `/wms-master-data/portal/accounts/{id}/reset-password` | `wms_master_data:subaccount:edit` |
| GET | `/wms-master-data/me/portal` | 登录即可 |
| GET | `/wms-master-data/locations` | `wms_master_data:location:list` |
| POST | `/wms-master-data/locations` | `wms_master_data:location:create` |
| GET | `/wms-master-data/skus` | `wms_master_data:sku:list` |
| POST | `/wms-master-data/skus` | `wms_master_data:sku:create` |
| PUT | `/wms-master-data/skus/{id}` | `wms_master_data:sku:edit`（仅基础信息组） |
| PUT | `/wms-master-data/skus/{id}/storage` | `wms_master_data:sku:configure`（仅仓库侧字段） |
| GET | `/wms-master-data/teams` | `wms_master_data:team:list` |
| GET | `/wms-master-data/teams/coverage` | `wms_master_data:team:list` |
| POST | `/wms-master-data/teams` | `wms_master_data:team:create` |
| PUT | `/wms-master-data/teams/{team_id}` | `wms_master_data:team:edit` |
| DELETE | `/wms-master-data/teams/{team_id}` | `wms_master_data:team:delete` |
| PUT | `/wms-master-data/teams/{team_id}/leader` | `wms_master_data:team:edit` |
| POST | `/wms-master-data/teams/{team_id}/toggle` | `wms_master_data:team:edit` |
| GET | `/wms-master-data/staffs` | `wms_master_data:staff:list` |
| GET | `/wms-master-data/staffs/by-user/{user_id}` | `wms_master_data:staff:list` |
| POST | `/wms-master-data/staffs` | `wms_master_data:staff:create` |
| PUT | `/wms-master-data/staffs/{staff_id}` | `wms_master_data:staff:edit` |
| PUT | `/wms-master-data/staffs/{staff_id}/skills` | `wms_master_data:staff:skill` |
| PUT | `/wms-master-data/staffs/{staff_id}/certs` | `wms_master_data:staff:cert` |
| GET | `/wms-master-data/staffs/{staff_id}/logs` | `wms_master_data:staff:list` |
| POST | `/wms-master-data/staffs/bulk-team` | `wms_master_data:staff:bulk-team` |
| POST | `/wms-master-data/staffs/{staff_id}/leave` | `wms_master_data:staff:leave` |
| POST | `/wms-master-data/staffs/{staff_id}/leave/pending` | `wms_master_data:staff:leave` |
| POST | `/wms-master-data/staffs/{staff_id}/team` | `wms_master_data:staff:edit`（加入） |
| PUT | `/wms-master-data/staffs/{staff_id}/team` | `wms_master_data:staff:edit`（调组） |
| DELETE | `/wms-master-data/staffs/{staff_id}/team` | `wms_master_data:staff:edit`（退出） |
| GET | `/wms-inventory/stocks` | `wms_inventory:stock:list` |
| GET | `/wms-inventory/txns` | `wms_inventory:txn:list` |
| GET | `/wms-inventory/lots` | `wms_inventory:lot:list` |
| GET | `/wms-inventory/lots/expiring` | `wms_inventory:lot:expiring` |
| POST | `/wms-inventory/adjustments` | `wms_inventory:adjust:create` |
| GET | `/wms-inbound/asns` | `wms_inbound:asn:list` |
| POST | `/wms-inbound/asns` | `wms_inbound:asn:create` |
| POST | `/wms-inbound/asns/{id}/confirm` | `wms_inbound:asn:edit` |
| POST | `/wms-inbound/asns/{id}/cancel` | `wms_inbound:asn:cancel` |
| POST | `/wms-inbound/asns/{id}/close` | `wms_inbound:asn:edit`（收不满时人工结案） |
| GET | `/wms-inbound/service-orders` | `wms_inbound:service_order:list` |
| POST | `/wms-inbound/service-orders` | `wms_inbound:service_order:create` |
| POST | `/wms-inbound/receipts` | `wms_inbound:receipt:create` |
| POST | `/wms-inbound/receipts/{id}/check` | `wms_inbound:receipt:execute` |
| POST | `/wms-inbound/putaways/{id}/execute` | `wms_inbound:putaway:execute` |
| GET | `/wms-outbound/orders` | `wms_outbound:order:list` |
| POST | `/wms-outbound/orders` | `wms_outbound:order:create` |
| GET | `/wms-outbound/wave-rules` | `wms_outbound:wave_rule:list` |
| POST | `/wms-outbound/wave-rules` | `wms_outbound:wave_rule:create` |
| GET | `/wms-outbound/waves` | `wms_outbound:wave:list` |
| POST | `/wms-outbound/waves/generate` | `wms_outbound:wave:create`（异步，返回任务标识） |
| GET | `/wms-outbound/waves/{id}/progress` | `wms_outbound:wave:list` |
| POST | `/wms-outbound/waves/{id}/abort` | `wms_outbound:wave:cancel` |
| POST | `/wms-outbound/waves/{id}/allocate` | `wms_outbound:allocation:execute` |
| POST | `/wms-outbound/picks/{id}/execute` | `wms_outbound:pick:execute` |
| POST | `/wms-outbound/seeds/execute` | `wms_outbound:seed:execute` |
| POST | `/wms-outbound/checks/{id}/weigh` | `wms_outbound:check:execute` |
| POST | `/wms-outbound/checks/{id}/execute` | `wms_outbound:check:execute` |
| POST | `/wms-outbound/shipments` | `wms_outbound:shipment:execute` |
| POST | `/wms-outbound/shipments/{id}/print-label` | `wms_outbound:shipment:execute` |
| GET | `/wms-internal-ops/replenishments` | `wms_internal_ops:replenish:list` |
| POST | `/wms-internal-ops/replenishments` | `wms_internal_ops:replenish:create` |
| POST | `/wms-internal-ops/replenishments/{id}/execute` | `wms_internal_ops:replenish:execute` |
| GET | `/wms-returns/disposals` | `wms_returns:disposal:list` |
| POST | `/wms-returns/disposals` | `wms_returns:disposal:create` |
| POST | `/wms-returns/disposals/{id}/execute` | `wms_returns:disposal:execute` |
| GET | `/wms-internal-ops/samples` | `wms_internal_ops:sample:list` |
| POST | `/wms-internal-ops/samples/{id}/release` | `wms_internal_ops:sample:execute` |
| POST | `/wms-internal-ops/samples/{id}/ship` | `wms_internal_ops:sample:execute` |
| POST | `/wms-internal-ops/samples/{id}/dispose` | `wms_internal_ops:sample:execute` |
| POST | `/wms-internal-ops/samples/{id}/extend` | `wms_internal_ops:sample:execute` |
| GET | `/wms-billing/invoices` | `wms_billing:invoice:list` |
| POST | `/wms-billing/invoices/generate` | `wms_billing:invoice:create` |
| POST | `/wms-billing/invoices/{id}/confirm` | `wms_billing:invoice:confirm` |

完整清单以各域 `api.py` 的 `APIRouter` 为准，上表覆盖需要跨域约定的部分。

用户管理创建账号（预置 `admin` 除外）时自动生成人员档案，工号取 `username`；货主主账号由货主管理创建，不生成档案。人员档案的姓名、手机与账号状态从 `sys_user` 投影。`POST /wms-master-data/staffs` 只接收 `code`、`user_id`、`role`，`PUT /wms-master-data/staffs/{staff_id}` 不接收姓名与手机；人员列表和按账号查询返回 `account_status`。

## 对外接口

前缀 `/api/v1/open/v1`，鉴权头 `X-API-Key`，不认 `Authorization`。响应统一：

```json
{ "code": "OK", "message": "", "data": {}, "request_id": "..." }
```

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/open/v1/asns` | 建入库预报，body 内 `owner_doc_no` 必填 |
| GET | `/open/v1/asns/{code}` | 查预报与其收货进度 |
| POST | `/open/v1/service-orders` | 提交服务订单（留样要求） |
| GET | `/open/v1/service-orders/{code}` | 查服务订单 |
| POST | `/open/v1/orders` | 建出库订单 |
| GET | `/open/v1/orders/{code}` | 查订单与发运状态 |
| GET | `/open/v1/stocks` | 查本货主库存（支持按商品筛选） |
| GET | `/open/v1/invoices` | 查账单列表 |
| GET | `/open/v1/invoices/{code}` | 查账单明细 |

错误码：

| code | HTTP | 含义 |
|---|---|---|
| `OK` | 200 | 成功 |
| `INVALID_PARAM` | 400 | 参数缺失或格式错误 |
| `UNAUTHORIZED` | 401 | 缺少或无效凭证 |
| `KEY_EXPIRED` | 401 | 凭证过期 |
| `FORBIDDEN` | 403 | 越权访问他人数据 |
| `NOT_FOUND` | 404 | 单据或商品不存在 |
| `DUPLICATE_DOC` | 409 | 货主单号重复，返回首次结果 |
| `RULE_VIOLATION` | 422 | 业务规则拒绝（如商品不属该货主） |
| `RATE_LIMITED` | 429 | 预留，当前不启用 |
| `SERVER_ERROR` | 500 | 未预期异常，带 `request_id` |

## 版本策略

`/open/v1` 为当前版本。破坏性变更时新增 `/open/v2`，v1 保留至少一个账期并在响应头返回 `Deprecation: <日期>`。非破坏性新增字段不升版本。

## 跨域契约

实现里只允许调用以下契约函数，不在契约上的能力一律视为越界。

| 提供方 | 契约 | 调用方 |
|---|---|---|
| `wms_inventory` | `post_stock(db, sku_id, lot_id, location_id, stock_status, delta, ref_type, ref_id, action, operator_id)` | 入库、出库、库内、逆向 |
| `wms_inventory` | `transfer_status(db, sku_id, lot_id, location_id, from_status, to_status, qty, ref_type, ref_id, action, operator_id)` | 库内、批次到期冻结 |
| `wms_inventory` | `ensure_lot(db, owner_id, sku_id, lot_code, production_date, expiry_date)` → 批次 id，已存在则复用并校验效期一致 | 入库 |
| `wms_inventory` | `pick_lots_fefo(db, sku_id, qty, temp_zone)` → 按到期日升序的批次与库位候选 | 出库 |
| `wms_inventory` | `snapshot_occupancy(db, day)` → 按 `location_type` 分组 | 计费 |
| `wms_master_data` | `get_owner_scope(user)`、`resolve_sku_owner(db, sku_id)` | 全部 |
| `wms_internal_ops` | `create_sample(db, owner_id, sku_id, qty, location_id, service_order_id, receipt_id, retain_days)` | 入库 |
| `wms_inbound` | `list_completed(db, doc_type, since, until)` | 计费 |
| `wms_outbound` | `list_completed(db, doc_type, since, until)` | 计费 |
| `wms_tasking` | `register_handler(task_type, handler)` | 入库、库内、出库、逆向 |

`wms_inventory` 的三个契约不接收 `owner_id`（由商品派生），`wms_master_data` 的 `get_owner_scope` 是唯一的货主范围判定入口。

## 幂等键汇总

| 场景 | 幂等键 |
|---|---|
| 库存增减 | `(ref_type, ref_id, sku_id, lot_id, location_id, action)` |
| 状态转换 | 同上，`action` 取 `status:<from>-><to>` |
| 批次创建 | `(owner_id, sku_id, lot_code)` |
| 到期冻结 | `(lot_expiry, lot_id, ...)`，批次已 `frozen` 时直接跳过 |
| 货主建单 | `(owner_id, owner_doc_no)` |
| 费用生成 | `(charge_item, ref_type, ref_id, period)` |
| 每日占用 | `(owner_id, day, location_type)` |
| 账单 | `(owner_id, period)` |
