# Design

## Context

P2 的收货链路已验证：批次、过账、上架、破损处置都跑通了生产路径。`post_stock` 的四道闸（锁行、幂等、非负、同事务）在并发下不双扣。

P3 引入一个新问题：**分配只是"记账预占"，不是"库存变动"**。库存数量在发运时才动。这条决定了任何一步失败都能退回，账不会被污染。

## Decisions

### F1 分配不改数量，只写 allocation

```mermaid
flowchart LR
  order["订单 confirmed"] --> alloc["allocate_fefo<br/>只读库存 + 写 allocation"]
  alloc --> pick["拣货单<br/>按库位排序"]
  pick --> check["复核 + 称重拦截"]
  check --> ship["发运<br/>post_stock 扣减"]
  ship --> done["订单 shipped"]
```

`allocation` 记录"这行订单要从哪个库位哪个批次拿多少"。库存 `qty` 全程不变，直到发运。

好处是取消订单只要把 allocation 标记作废，不需要反向补库存——反向操作最容易出错。

代价是**超卖风险**：两个订单可能分配到同一批货。P3 的应对是**分配时加行锁**（`SELECT ... FOR UPDATE` 锁住候选库存行），并在 `allocation` 上记可用量快照。真正的并发瓶颈在 P4 波次，那时再考虑批量预占。

### F2 一条 IN 查询 + 内存排序

单订单所有行一次取完候选库存：

```sql
SELECT s.sku_id, s.lot_id, s.location_id, s.qty, l.expiry_date
FROM wms_inventory_stock s
LEFT JOIN wms_inventory_lot l ON l.id = s.lot_id
WHERE s.owner_id = :owner
  AND s.sku_id IN (:skus)
  AND s.stock_status = 'available'
  AND s.qty > 0
  AND s.location_id IN (SELECT id FROM wms_master_data_location
                        WHERE location_type IN ('storage','picking') AND status = 1)
ORDER BY l.expiry_date IS NULL, l.expiry_date, s.lot_id
FOR UPDATE
```

**留样区在 SQL 里排除**，不在应用层判断——散在各处的判断迟早漏一处，而漏一处就是把留样货发出去。

### F3 指定批次不自动换批

货主指定批次时，`allocation` 只用那个批次；不够就整行失败并告知缺口。

换批意味着客户收到他没指定的批次，在效期敏感品类上是事故。宁可让人改单。

### F4 拣货按库位路径排序

行按 `aisle → rack → level → bin` 排序，作业员走一趟不用来回折返。排序在 SQL 里做，分页按拣货单整体，不打断路径。

### F5 称重用相对偏差，不拦截已打包的

理论重量 = Σ(行数量 × 商品单件重量)。缺重量的商品跳过该项计算并记告警——不能因为一个商品没维护重量就卡住整单。

超差阈值按货主配置，默认 5%。超差拦的是「发运」按钮，不是「复核」动作：复核员可以先记录实称，再决定是否放行。

### F6 发运幂等靠订单状态

`ship()` 先锁订单行，状态必须是 `checked`。已 `shipped` 直接返回成功且不重复扣减。

不额外建幂等表——订单状态本身就是幂等键，比再造一层简单。

## Risks / Trade-offs

- **两个订单并发分配到同一批货** → P3 用行锁挡住，代价是高并发时分配会排队。三万单/天的分配是 1.7 单/秒，行锁足够；真正的热点在波次（P4），届时再引入批量预占。
- **`FOR UPDATE` 锁的范围偏大**（一次锁住该货主该商品的所有库存行）→ 同一商品并发分配会串行。单仓场景下可接受。
- **理论重量依赖商品维护重量** → 未维护时该行跳过并告警，不阻断发货。这条在 P2 的字段里已经留好（`weight`）。
- **拣货扫码需要设备** → 页面先支持手工填库位编码，扫码枪接入随 P5 作业端。
