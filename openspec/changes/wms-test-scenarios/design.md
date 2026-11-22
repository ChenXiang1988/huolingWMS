# Design

## Context

场景已存在，分散在三处：8 份常驻规格（行为权威）、各期 change 的 spec delta（尚未归档的增量）、`docs/design/inbound-walkthrough.md`（P2 操作脚本）。P2 与 P3 两期没有 spec delta，验收点只写在 tasks.md 的"验证标准"列里。本变更把这批可观察行为集中成一份清单，不改任何行为定义。

场景总数与分布见下表，分组维度与核对依据都来自这张表。

| 分组 | 场景数 | 主要来源 |
|---|---:|---|
| 平台基座 | 17 | `p0-bootstrap` delta |
| 域边界与主数据 | 30 | `wms/domain-map` 常驻 |
| 货主访问 | 43 | `wms/owner-access` 常驻 + split + integrate 增量 |
| 入库 | 25 | `inbound-walkthrough.md` + `wms/lot-control` 收货段 |
| 库存台账 | 21 | `wms/stock-ledger` 常驻 |
| 批次与效期 | 16 | `wms/lot-control` 常驻 |
| 库位策略 | 20 | `wms/location-policy` 常驻 |
| 出库 | 38 | `wms/wave-picking` 常驻 + hiprint + p3 tasks |
| 计费 | 16 | `wms/billing` 常驻 |
| 移动作业端 | 17 | `wms/mobile-app` 常驻 + add-mobile-web |
| 集成与上游同步 | 17 | `upstream-sync` delta + integrate 增量 |
| **合计** | **260** | — |

## Goals / Non-Goals

**Goals:**

- 一份清单能回答"验收这套系统要跑哪些场景"，每条带明确的 WHEN/THEN。
- 每条场景标明来源，能追到规格文件或验收脚本的原文。
- 覆盖尚未进入常驻规格的增量场景，避免它们随 change 归档而失去验收依据。

**Non-Goals:**

- 不引入测试框架、测试目录或自动化代码；执行方式仍是人工按脚本操作。
- 不重写来源规格的措辞，不把本清单当作行为权威。
- 不为 P4–P7 尚未交付的期次预写场景。

## Decisions

### 按业务域分组，不按交付期分组

分组用 `wms/domain-map` 定义的业务能力归属，而不是 P0–P7 期次。理由：期次会随时间 past，一个域的行为会跨多期累积（出库场景横跨 P3 的基本出库、P4 的波次、P6 的打印）；按域分组让同一能力的场景聚在一起，验收人按职责领取。每条 Requirement 标题带"验收场景"，与来源规格的行为 Requirement 区分开。

### 场景逐条列出，不引用编号

每条场景完整写出 WHEN/THEN，而不是只在来源规格里标"见 wms/stock-ledger R4"。理由：验收时不会同时在心里装着 8 份规格；清单要能单独拿来执行。代价是同一行为在两处各写一遍——用来源标注把同步责任固定下来（见下一条）。

### 来源写在 Requirement 层，不逐场景标注

每条 Requirement 的描述行列出来源路径，组内场景沿用来源标题。理由：多数 Requirement 的场景来自单一规格，逐条重复标注是噪声；当一个 Requirement 混用多个来源（入库、货主访问、出库、移动作业端）时，按来源标题本身仍可回溯到分组内具体条目。

### 增量场景一并纳入，不等归档

`platform-bootstrap`、`upstream-sync` 仍是 in-progress change 的 delta，浏览器形态、hiprint 打印、双端登录隔离、域增量也属于进行中的 change。这些场景一旦 change 归档会并入常驻规格，但归档前若清单只覆盖常驻规格，就会漏掉当前已经要验的行为。因此按现状全部纳入。

### 场景取自 spec delta 与 tasks 验证标准，不取自 proposal

P2、P3 没有 spec delta，入库与出库的具体操作场景从 `inbound-walkthrough.md` 与 `p3-outbound-basic/tasks.md` 的"验证标准"列提取。proposal 描述的是范围与意图，不作为验收判定依据。

## Risks / Trade-offs

- **双份维护**：行为变更时需同时改来源规格与本清单。→ 本变更归档后，把同步更新本清单列为相关域变更的收尾动作；来源标注指向具体文件路径，便于定位。
- **场景粒度不均**：来源规格的场景详略不一，部分 delta 只有一行 WHEN/THEN。→ 本清单沿用来源粒度，不自行补写细节；需要更细步骤时由验收脚本承接，不写进规格。
- **来源仍在变动**：`p3-outbound-basic` 等 change 尚未关闭，其 tasks 验证标准可能再改。→ 本变更合入后可以由后续 change 更新对应 Requirement，不需要重做整份清单。
