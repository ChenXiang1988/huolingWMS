# Design

## Context

P4 之后系统有 6 个插件、35 张表。库存数量的写入口只有两个：`post_stock`（增减）与
`transfer_status`（状态转换）。P5 的四项库内作业都必须复用这两个函数，不能自己改
`wms_inventory_stock.qty`，否则幂等键与流水约束都会被绕过。

## Decisions

### I1 移库是两次过账，不是一行 UPDATE

```mermaid
flowchart LR
  t["移库单 confirmed"] --> out["post_stock(-qty, 源库位)"]
  out --> in["post_stock(+qty, 目标库位)"]
  in --> done["transfer done<br/>总量守恒"]
```

两条流水用同一个 `ref_id`（移库行 id）、不同的 `action`（`transfer_out` / `transfer_in`）。
幂等键含 `lot_id` 与 `location_id`，所以同批次多库位移动不会被判成重复。

不移已冻结或破损的货：只有 `available` 能移，这是仓库作业的实际约束。

### I2 盘点差异是"调整量"，不是"新账面"

盘点行存三列：`qty_book`（生成时的账面快照）、`qty_actual`（实盘）、
`qty_diff = qty_actual - qty_book`。

确认时按 `qty_diff` 调 `post_stock`，而不是把 `qty_actual` 直接写回库存表。
理由：生成盘点单到确认之间，货可能被别的作业动过。用调整量过账，那一笔变动会
单独留一条流水，账实怎么变的能查；直接覆盖会把中间的变动抹掉。

盘点单生成时就冻结账面快照，之后不再刷新——否则作业员一边盘、账面一边跳，
永远盘不完。

### I3 留样台账从上架行回填

P2 的 `wms_inbound_putaway_line` 有 `sample_flag`，上架确认时货已经进了留样区，
但当时没有台账表。P5 建表后：

- 首次启用插件时，把所有 `sample_flag=true` 且 `done_at` 非空的历史行回填成台账
- 之后由 `confirm_putaway_line` 完成时同步写一条（跨域只写入库域已有的字段，不改库存）
- 到期日 = 上架完成日 + 服务订单 `retain_days`

四条处置路径都走已有能力：`scrap` 调 `post_stock` 减量、`restock` 调
`transfer_status` 转成 `available`、`return_owner` 减量并记出库单号、`extend` 只改到期日。

### I4 临期冻结用进程内 asyncio，不引调度库

基座没有 APScheduler。单进程部署下 `asyncio.create_task` + 每小时算一次即可：

```
startup → 立即跑一次 → 每 3600s 跑一次
每次：查 expiry_date <= today + warn_days 且 status=active 的批次
     → 把该批次所有 available 库存行转成 frozen（transfer_status）
     → 批次置 frozen，frozen_reason='expiry_warn'
```

冻结按批次而非按库存行：同批号不同库位的货要一起停发，否则 FEFO 会绕开冻结的
那一格继续发同批次的另一格。

幂等靠 `ref_type='lot_expiry', ref_id=lot_id`，重复扫描不会重复转换。

风险是进程重启会丢定时器；靠"启动时立即跑一次"兜底，不持久化调度状态。

### I5 任务域只管调度，不管业务

`wms_tasking.task` 记录：类型（移库/盘点/上架/拣货/复核）、来源单据 id、目标库位、
领取人、状态（pending/claimed/done/cancelled）、领取时间、超时时间。

任务提交时**由任务服务回调对应域的既有接口**，不重写业务状态机。这样业务域停用
时任务自然失效，不会出现"任务完成了但单据没动"。

超时回收：领取超过 N 分钟未提交，`pending` 回归、领取人清空。不做自动改派。

## Risks / Trade-offs

- **盘点快照会过期** → 确认时若账面已变，差异过账仍成立（是对"当前账面"再调一次），但要提示作业员重新盘点。本期先给明确提示，不做自动重盘。
- **临期冻结与发运并发** → `transfer_status` 带行锁；发运时若状态已是 `frozen`，`post_stock` 会因可用量不足拒绝，不会超发。
- **任务领取并发** → 领取时 `SELECT ... FOR UPDATE` 锁任务行，状态非 `pending` 直接拒。
- **回填历史留样** → 只在插件首次安装时跑一次，用 `sample` 表的唯一键挡重复。
