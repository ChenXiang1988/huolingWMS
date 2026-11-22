# Proposal

## Why

系统行为散在 8 份常驻规格和多个变更的 spec delta 里，没有一处能回答"验收这套系统到底要跑哪些场景"。项目没有测试目录，验收靠可复现的操作步骤（`docs/design/inbound-walkthrough.md` 是唯一成型的脚本），而 P2、P3 两期没有 spec delta，新人和货主对接时无法判断覆盖是否完整，也无从知道某条场景来自哪份规格。

## What Changes

- 新增验收规格 `wms/test-scenarios`：按业务域枚举系统必须通过的验收场景，每条给出 WHEN/THEN 与来源。
- 覆盖 8 份常驻规格的全部场景，并补入尚未进入常驻规格的增量场景：平台基座（`platform-bootstrap`）、上游同步（`upstream-sync`）、作业端浏览器形态、hiprint 打印、门户登录隔离、`integrate-warehouse-network` 的域增量。
- 每条场景标注来源规格路径与 Requirement 标题；后续某域行为变更时按来源回溯更新，不维护第二份行为定义。
- 不改变任何业务行为、接口或现有规格。**BREAKING**：无。

## Capabilities

### New Capabilities

- `wms/test-scenarios`: 集中枚举系统必须通过的业务验收场景，按业务域分组，每条可追溯到来源规格。

### Modified Capabilities

无。

## Impact

- 仅新增 `openspec/changes/wms-test-scenarios/` 下的规划产物，以及归档后 `openspec/specs/wms/test-scenarios/` 这一份常驻规格。
- 不触碰 `backend/`、`frontend/`、`mobile/`，不改变运行时行为、接口与数据模型。
- 验收执行仍按现有方式进行（可复现的操作步骤），本变更只提供场景清单与来源，不引入测试框架。
