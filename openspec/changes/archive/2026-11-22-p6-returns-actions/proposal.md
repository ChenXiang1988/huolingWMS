# Proposal

## Why

用户 2026-11-22 调整优先级：**报表、打印这类「看数 / 出纸」的能力往后延，先把能改变单据与库存的业务动作做完**。

本期只交付两类业务动作：客户退货入库、货主自助建单。三张报表（库存汇总、吞吐量、计费预览）
与门户查询类页面（我的库存、我的账单）一起挪到最终验收前，不纳入本期。

## What Changes

- **退货入库**：`wms_returns` 扩 `return` / `return_line` 两张表。退货单建单 → 按品质判定
  （可发 / 破损）→ 收货入库，走 `post_stock` 增加库存，同事务写流水。
- **货主自助建单**：门户新增「入库预报」「出库订单」两页，复用后台既有建单服务，
  但 `owner_id` 由登录账号绑定的货主决定，不读请求体。
- **接入 ERP 的货主只读**：`sync_enabled=true` 时门户建单入口关闭，只保留查询，
  与 `integrate-warehouse-network` 已定的主从关系一致。

## Capabilities

### New Capabilities

无。

### Modified Capabilities

无。行为已在 `wms/owner-access`、`wms/stock-ledger`、`wms/domain-map` 里写明。

## Impact

- `wms_returns` 追加 2 张表；退货单页面 1 个。
- 门户路由表、`OwnerLayout` 菜单来源、门户菜单 seed 三处同步新增 2 页。
- 新建 `wms_reporting` 插件包与三张报表**顺延**；打印 16 条、P4 三条形式化验收同样顺延。
- 不新增依赖。

## 顺延清单

| 项 | 原属 | 顺延到 |
|---|---|---|
| 库存汇总、吞吐量、计费预览三张报表 | P6 | 最终验收前 |
| 门户「我的库存」「我的账单」 | P1 / P8 | 最终验收前 |
| hiprint 打印 16 条 | P4 | 最终验收前 |
| 打印模板设计器 | P4 6.4 | 最终验收前 |
