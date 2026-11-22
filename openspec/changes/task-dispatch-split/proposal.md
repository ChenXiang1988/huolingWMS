# Proposal

## Why

现有任务域只有一种执行方式：任务进公共池，作业员抢单，超时回归但**不自动改派**（P5 定的 I5 与 service.py 的 `recycle_timeout` 都是这样）。对标仓库的做法是一张工单的某道工序按货量拆成多个小任务，直接派到指定 PDA 和对应登录人；只有货多时才拆，且要有派单与抢单两条路。现有 `task` 表没有父子字段、没有指派字段、没有拆分数量，无法表达这种结构。本变更在工单工序链之上补派工与拆分。

## What Changes

- 新增能力 `wms/task-dispatch-split`：任务派工与拆分。
- 任务增加指派人、来源工序、父任务与拆分序号；保留现有 `assignee_id / claimed_by` 作为领取结果，与"系统指派"区分。
- 支持两种分配方式并存：系统派单（按规则指定人或 PDA）与公共池抢单；派单任务超时后可改派或转公共池，不再一律只回归。
- 支持把一道工序的任务按数量或商品拆成多条子任务，子任务完成汇总回父任务。
- 派单与领取共用行锁并发控制，避免同一任务被两人拿到。
- **BREAKING**：无。现有抢单式任务继续可用，派单与拆分是叠加能力。

## Capabilities

### New Capabilities

- `wms/task-dispatch-split`: 任务派工与拆分能力——系统派单、抢单兜底、超时改派、父子任务拆分与汇总。

### Modified Capabilities

无。不修改 `wms_tasking` 常驻行为（任务域尚无常驻规格），也不修改 8 份常驻规格。

## Impact

- 扩展 `wms_tasking.task` 字段：新增 `parent_task_id`、`assignee_id`（系统指派）、`dispatch_mode`、`split_seq`、`step_id`。
- 复用 `work-order-process-chain` 的工序实例作为任务来源；该变更未归档时以契约引用，不硬依赖其表结构。
- 权限标识 `wms_tasking:task:dispatch` 新增；PDA 端按指派人过滤待办。
- 修改 `recycle_timeout` 语义：派单任务超时按策略改派或转池，抢单任务维持回归原行为。
