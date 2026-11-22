# Proposal

## Why

P1 让系统能录基础数据和记库存账，但货进不来——没有入库预报、没有收货、没有上架。

P2 是第一个真正改变库存数量的期次：货到了，系统要知道来的是什么、收了多少、破损几件、放哪儿、留不留样。它也第一次真实调用 `post_stock`，把 P1 只做过单测级别的记账契约放到生产路径上。

## What Changes

- **入库预报**：货主经 API 或门户建 ASN，一个 ASN 可挂多张收货单（分批到货），收不满可人工结案。
- **服务订单**：随 ASN 提交留样要求，按比例或固定数量，留样数量按实收封顶。
- **收货**：按批次录入批号与效期，记录应收/实收/破损；未建档条码拒扫；超收拒绝。
- **上架**：按 D21 三条优先级选位，温区不匹配时提示但放行并留痕；同一商品不同批次分两条库存记录。
- **留样分离**：上架完成时生成留样记录并落到留样区，记录里带批次。
- **破损处置**：转回可发或报废；退回货主留到 P3（依赖出库）。
- **对外接口 v1**：交付 `openapi-owner.json`，货主可用 `X-API-Key` 调 ASN 与服务订单。

## Capabilities

### New Capabilities

无。`wms/domain-map`、`wms/stock-ledger`、`wms/lot-control`、`wms/owner-access` 已经把这一期的行为写清楚了。

### Modified Capabilities

无。

## Impact

- 新增 6 张表：`asn`、`asn_line`、`service_order`、`receipt`、`receipt_line`、`receipt_lot`、`putaway`、`putaway_line`（8 张）。
- 入库域从骨架变成可用插件，挂 4 个后台页面。
- 首次在生产路径调用 `inventory.post_stock` 与 `ensure_lot`，跨域契约在这一期定型。
- 门户新增入库预报与服务订单两个入口。
- 不新增第三方依赖。
