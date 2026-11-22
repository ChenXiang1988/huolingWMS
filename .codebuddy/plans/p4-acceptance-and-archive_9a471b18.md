---
name: p4-acceptance-and-archive
overview: 跑完 p4-wave-replenish 剩余的两条验收（200 单生成期间接口可响应、生成到一半中止后库存不变），把结果写回 tasks.md，然后归档 p4、p5、p6、split-owner-portal-entry 四个变更。
todos:
  - id: backup-and-precheck
    content: 备份整库，核对可用库存是否够 200 件、有无 confirmed 遗留单
    status: completed
  - id: run-7-1
    content: 造 200 单跑 7.1，生成期间隔 200ms 探活登录并记录延迟
    status: completed
    dependencies:
      - backup-and-precheck
  - id: run-7-2
    content: 造 200 单跑 7.2，processed 过零后中止，核对作废与库存不变
    status: completed
    dependencies:
      - backup-and-precheck
  - id: write-results
    content: 回写 tasks.md 的 7.1、7.2 实测数据并勾选，删除临时脚本
    status: completed
    dependencies:
      - run-7-1
      - run-7-2
  - id: restore-db
    content: 停后端后还原备份，核对订单数与库存回到测试前
    status: completed
    dependencies:
      - run-7-1
      - run-7-2
  - id: archive-changes
    content: 用 [skill:openspec-archive-change] 归档 p4、p5、p6、split-owner-portal-entry
    status: completed
    dependencies:
      - write-results
      - restore-db
---

## 用户需求

把 `p4-wave-replenish` 剩下的两条验收跑完，把已完成的三个变更归档，让 `openspec list` 收敛。

## 产品概述

本轮不新增功能，只做验收与收尾。打印方案已确定延后，`p4` 里的打印条目九条已划给 `adopt-hiprint-print`，`p4` 现在 24/26，只剩两条验收。

## 核心功能

- **7.1 并发响应验收**：一次波次装 200 单，后台异步生成期间，登录接口必须持续可用，记录探活次数、状态码与延迟，波次最终到达 `ready` 且 `processed + failed = 200`。
- **7.2 中途中止验收**：200 单生成到一半时中止，校验波次转 `cancelled`、已生成的拣货单全部作废、分配记录不再有效、库存数量前后一致。
- **结果回写**：两条任务的实测数据写进 `p4` 的 `tasks.md` 并勾选，与既有验收记录的写法保持一致。
- **数据回滚**：两次验收会真实写入约 400 张订单及配套单据，结束后必须把库恢复到验收前状态，不留测试数据。
- **归档**：`p4`、`p5`、`p6`、`split-owner-portal-entry` 四个变更归档，`p5`/`p6` 不带 spec 增量，`split-owner-portal-entry` 的 `owner-access` 增量合并进常驻规格。

## 边界

- 不改产品代码。若验收暴露缺陷，只记录不修，是否修由用户另行决定。
- 不碰 `p0`、`p2`、`p3` 的遗留项，不碰 `adopt-hiprint-print`、`add-mobile-web`、`integrate-warehouse-network`。

## 技术栈

沿用现有栈，不引入新依赖：

- 后端 FastAPI + SQLAlchemy 2.0 async + MySQL 8（容器 `huoling-mysql`，宿主端口 3307，库 `huoling_wms`）
- 验收脚本用 Python 3.12（`backend/.venv`）+ `httpx`（已在 `pyproject.toml` 依赖里）
- 数据库备份还原用容器内 `mysqldump` / `mysql`
- 归档用 `openspec` CLI

## 实现策略

用一次性脚本走真实 HTTP 链路，不复用服务层直调——7.1 的判据本身就是"接口在生成期间仍可响应"，绕开 HTTP 就测不到。测试数据靠 `carrier_code` 隔离，不靠清空库；兜底靠整库备份还原，不手写 DELETE。

### 数据隔离

`_load_candidates` 在传了 `rule_id` 时会按 `rule.carrier_code` 过滤并 `limit(max_orders)`（`wave_service.py:35-49`）。因此：

- 7.1 造 200 单，`carrier_code = "P4ACC71"`，配一条同承运商规则、`max_orders=200`、无 `cutoff_at`、`hot_only=false`。
- 7.2 造 200 单，`carrier_code = "P4ACC72"`，独立规则。

这样库里历史 `confirmed` 单（P3 的 9.3 就留了一张）不会卷进波次，`total` 必然等于 200。

### 库存前提

`allocate_fefo`（`service.py:106-216`）只读 `wms_inventory_stock.qty` 写 `allocation`，不扣减库存、也不扣减"已分配量"。所以必须保证所选 SKU 在 `storage`/`picking` 库位上的可用量 ≥ 200 件，否则 200 单会全部"分配成功"而分配总量超过实物——那不是本轮要验的东西。

前置查询：

```sql
SELECT s.owner_id, s.sku_id, SUM(s.qty)
FROM wms_inventory_stock s
JOIN wms_master_data_location loc ON loc.id = s.location_id
WHERE s.stock_status='available' AND s.qty>0 AND loc.status=1
  AND loc.location_type IN ('storage','picking')
GROUP BY s.owner_id, s.sku_id
HAVING SUM(s.qty) >= 200;
```

查不到就选一组现有货主 + SKU + 库位，用手工调整接口 `POST /api/v1/wms-inventory/adjustments` 补足（`request_id` 幂等），补的量随整库还原一起回滚。

### 7.1 判据

1. 顺序建 200 单（每单 1 行 × 1 件），`owner_doc_no` 前缀 `P4W71-`；`create_order` 落库即 `confirmed`（`service.py:83`），无需额外确认。
2. `POST /api/v1/wms-outbound/waves` 传 `rule_id`，返回 `total=200`。
3. 生成期间每 200 ms 并发 `POST /api/v1/auth/login`（`admin` / `Admin@12345`，密码必须正确，登录有失败锁定），记录状态码与耗时。
4. 轮询 `GET /api/v1/wms-outbound/waves/{id}` 直到终态。
5. 判定：波次 `ready`；`processed + failed = 200`；探活次数 ≥ 5 且全部 200；打印最大延迟。

### 7.2 判据

1. 同样造 200 单，`owner_doc_no` 前缀 `P4W72-`。
2. 每 50 ms 轮询波次，出现 `0 < processed < total` 时立刻 `POST /waves/{id}/cancel`。
3. 判定：波次 `cancelled`；该波次下 `wms_outbound_pick` 全部 `cancelled`；`wms_outbound_allocation` 中该批订单无 `active`；无订单停留在 `picking`；`SUM(qty)` 与建波前一致。
4. 兜底：若 200 单在 cancel 送达前跑完（终态 `ready`），把规则的 `max_orders` 提到 400 并重跑一批，判据不变。

`cancel_wave`（`wave_service.py:208-264`）只把 `picking` 订单退回 `confirmed`，不删记录、不动库存；生成任务每单开头查一次状态（`wave_service.py:142-150`），所以 cancel 后最多再走完当前一单就退出。

### 数据回滚

两条都跑完后停掉后端，用备份还原整库。理由：测试会写约 400 张订单、400 条订单行、400 条分配、400 张拣货单及行、2 条波次、2 条规则；手写 DELETE 要跨 8 张表，错删风险高于还原。

备份与还原都走容器内文件 + `docker cp`，避开 PowerShell 的坑（见下）。

## 执行细节与坑

- **PowerShell 重定向编码**：PowerShell 5.1 的 `>` 默认写 UTF-16LE，还原时会砸坏 SQL。用 `docker exec huoling-mysql mysqldump --result-file=/tmp/x.sql ...` 再 `docker cp` 取出，不要用 `>`。
- **不要用 `--reload` 启后端**：脚本写在 `backend/scripts/` 下会触发重载，重载会跑 `recover_interrupted`，把正在生成的波次标成 `interrupted`，7.1 直接废掉。用 `python -m uvicorn src.main:app --port 8000`，单进程。
- **脚本必须自己删**：`backend/scripts/_accept_p4.py` 是临时件，跑完删除，不留孤儿。
- **探活别打错密码**：登录有连续失败锁定，探活统一用正确凭据，失败也要把状态码打进记录，不能吞。
- **归档顺序**：先回写 `tasks.md` 再归档，归档会把 `changes/` 下的目录整体移入 `archive/`，移完再改 `tasks.md` 就改错地方了。
- **p4 是 `skip_specs: true`**：归档不产出 spec 增量，`openspec/specs/wms/*` 不动；只有 `split-owner-portal-entry` 会合并 `owner-access` 增量。
- **不改产品代码**：验收若暴露 `allocate_fefo` 超分配之类的问题，写进实施记录并单独告知，不在本轮修。

## 目录结构

```
huolingWMS/
├── backend/scripts/
│   └── _accept_p4.py                    [NEW, 临时] 验收驱动。含三个函数：7.1 建单+规则+探活、
│                                        7.2 建单+轮询中止、结果汇总打印。跑完删除。
├── openspec/changes/p4-wave-replenish/
│   └── tasks.md                         [MODIFY] 勾选 7.1、7.2，写入波次号、total/processed/failed、
│                                        探活次数与最大延迟、中止时的 processed 值、库存前后值。
├── openspec/changes/archive/
│   ├── 2026-11-22-p4-wave-replenish/     [NEW] 归档产物，含 proposal/design/tasks
│   ├── 2026-11-22-p5-internal-tasking/   [NEW] 无 spec 增量
│   ├── 2026-11-22-p6-returns-actions/    [NEW] 无 spec 增量
│   └── 2026-11-22-split-owner-portal-entry/ [NEW] 带 specs/wms/owner-access 增量
└── openspec/specs/wms/owner-access/
    └── spec.md                          [MODIFY, 由归档写入] 合并门户拆分的增量需求
```

## Agent Extensions

### Skill

- **openspec-archive-change**
- Purpose: 归档 `p4-wave-replenish`、`p5-internal-tasking`、`p6-returns-actions`、`split-owner-portal-entry` 四个变更，处理 `changes/` 到 `archive/` 的搬移与 `split-owner-portal-entry` 的 spec 增量合并。
- Expected outcome: 四个变更出现在 `openspec/changes/archive/`，`openspec list` 只剩 `p0`、`p2`、`p3` 与三个未启动变更，`owner-access` 规格包含门户拆分后的约定。