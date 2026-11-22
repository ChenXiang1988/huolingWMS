# Proposal

## Why

上一期把入库、出库、波次与补货做通了，但「库内管理」在界面上只有补货建议一页。
移库、盘点、留样台账、批次临期冻结四项能力都还没有，作业员也没有能领任务的入口。

这四项都是仓库日常动作：货放错库位要移、账实不符要盘、留样到期要处置、批次快过期要冻。
缺了它们，账面数量只能靠收货和发运两个端点推进，中间发生的任何变化系统都不知道。

## What Changes

- **移库**：按批次、按库位把货从 A 位搬到 B 位，两次 `post_stock` 同事务，两条流水。
- **盘点**：按批次列账面数与实盘数，差异实时算；确认后按差异调整库存，不直接覆盖账面。
- **留样台账**：从 P2 上架产生的 `sample_flag` 行回填记录，带到期日与四条处置路径（报废 / 退回货主 / 转回可发 / 延长留样）。
- **批次临期自动冻结**：进程内 `asyncio` 定时任务，按 `expiry_warn_days` 扫描临期批次，把 `available` 转 `frozen` 并写流水。
- **任务域**：新建 `wms_tasking` 插件包，把以上作业拆成任务，作业员领取、扫码执行、提交；超时自动回收。
- **作业端 Web**：把 `/m/tasks`、`/m/scan` 两个占位页换成真页面，与后台共用接口。
- 打印整块按用户 2026-11-22 的决定**顺延至最终验收前**，不纳入本期。

## Capabilities

### New Capabilities

无。

### Modified Capabilities

无。行为已在 `wms/lot-control`、`wms/location-policy`、`wms/stock-ledger` 里写明。

## Impact

- `wms_internal_ops` 追加 4 张表：`transfer`、`count`、`count_line`、`sample`。
- 新建 `wms_tasking` 插件包，1 张表 `task`。
- 前端 5 个页面：移库、盘点、留样台账、任务列表、作业端任务执行；作业端扫码页转正。
- 不新增依赖。定时任务用进程内 `asyncio` —— 基座 `pyproject.toml` 里没有 APScheduler，单进程部署不需要外部调度。
- 库存数量的写入仍只走 `inventory.service.post_stock` / `transfer_status`，本期不引入第三个写入口。
