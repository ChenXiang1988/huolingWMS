# Tasks

## 1. 规格校验

- [ ] 1.1 运行 `openspec validate wms-test-scenarios --strict`，验证 spec delta 结构合法、每条 Requirement 至少一个 Scenario；输出无错误
- [ ] 1.2 运行 `openspec status --change wms-test-scenarios`，验证 proposal、specs、design、tasks 四项均为 done
- [ ] 1.3 对照 design.md 的场景分布表统计 `spec.md` 中 Scenario 总数，验证与表中各分组数量之和一致（260 条）

## 2. 来源追溯核对

- [ ] 2.1 逐 Requirement 核对其描述行的来源路径存在，验证每个路径指向实际文件或 change 目录
- [ ] 2.2 抽查 8 份常驻规格各 3 条场景，验证本清单的 WHEN/THEN 与来源语义一致、无行为偏差
- [ ] 2.3 核对 4 类增量场景（platform-bootstrap、upstream-sync、浏览器形态、hiprint 打印、双端登录隔离）均已纳入，验证每个增量 change 的场景无遗漏

## 3. 归档与常驻化

- [ ] 3.1 评审通过后归档本变更，验证 `openspec/specs/wms/test-scenarios/spec.md` 生成且场景清单完整保留
- [ ] 3.2 运行 `openspec list --specs`，验证 `wms/test-scenarios` 出现在能力清单中
- [ ] 3.3 在 `CODEBUDDY.md` 规格表补一行指向新常驻规格，验证文档索引与实际文件一致

## 4. 后续同步约定落地

- [ ] 4.1 在本清单归档后的下一次域变更评审时，验证变更方已检查是否需要同步更新对应验收场景；以评审记录为证
- [ ] 4.2 待 `p3-outbound-basic`、`integrate-warehouse-network` 等 in-progress 变更关闭后，复核其最终 tasks 与 delta，验证本清单的出库、集成场景与最终交付一致

## Workflow follow-up

- 本变更只产出规划产物，应用与归档按项目 review 流程另起请求执行。
- 执行验收时以本清单为场景索引，具体操作脚本仍按 `docs/design/inbound-walkthrough.md` 及各期 tasks 的验证标准。
