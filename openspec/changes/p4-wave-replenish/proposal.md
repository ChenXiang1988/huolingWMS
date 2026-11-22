# Proposal

## Why

P3 已把单笔出库跑通：建单 → FEFO 分配 → 拣货 → 复核 → 发运，重复发运不双扣，留样区不会被分配。但三万单/天 ≈ 1.7 单/秒，一笔一笔点「分配」不成立，真正的瓶颈在**组波与分播**。

P4 把出库从「逐单操作」变成「批量作业」：按规则把订单合成波次、后台异步生成拣货单、播种墙按格口分播；同时给拣选区补货，并落地拣货单/装箱单打印。

## What Changes

- **波次规则**：按截单时间、承运商、区域、热度组合成可复用的规则；`POST /waves` 只落一条 `pending` 记录并立刻返回 id。
- **异步生成**：后台 `asyncio.create_task` 分页拉订单、逐单调用已有的 `allocate_fefo` 与 `release_to_pick`，每 50 单 `await asyncio.sleep(0)` 让出事件循环；状态 `pending → generating → ready → picking → done`，前端轮询进度。
- **可中止**：任意阶段可 `cancel`；已生成的拣货单不回滚，但标记作废，避免"中止了却还在拣"。
- **播种墙分播**：C 端小件按格口（订单）分播；B 端整箱走边拣边分。
- **整箱补货**：拣选区低于 `replenish_min` 时按 `qty_per_box` 向上整箱取整，从存储区移库到拣选区。
- **打印**：落地 `adopt-hiprint-print` 既定方案——模板存 JSON 后台管理、前端渲染经 socket.io 下发到 `electron-hiprint` 客户端，由 Windows 驱动出纸。
- **新建 `wms_internal_ops` 插件包**：本期只做补货，移库/盘点/留样台账留到 P5。

## Capabilities

### New Capabilities

无。

### Modified Capabilities

无。`wms/wave-picking`、`wms/location-policy`、`wms/stock-ledger` 已把这一期行为写清楚。

## Impact

- `wms_outbound` 追加 4 张表：`wave_rule`、`wave`、`sort_cell`、`seed`；`order` 表补 `wave_id`。
- 新建 `wms_internal_ops` 插件包，首期只含 `replenish` 表。
- 前端新增：波次看板、分播作业、补货建议、打印模板 4 个页面。
- 前端引入 `vue-plugin-hiprint` 与 `socket.io-client`（唯一新增依赖）；仓库工位需安装 `electron-hiprint` 客户端。
- 定时任务用进程内 `asyncio`，不引 APScheduler（基座里没有）。
