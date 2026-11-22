# Design

## Context

P0 交付了两个空插件：`wms_master_data` 只有 owner / user_owner 两张表和 `/me/portal`，`wms_inventory` 什么都没有。

`docs/design/data-model.md` 已经把表结构与约束写到字段级，`docs/design/interface-map.md` 已经把 `post_stock` 的签名逐参数定死。本期是照着做，不是重新设计。

## Decisions

### M1 表结构严格对齐 data-model，不做"先简化后补"

理由：P2 入库、P3 出库都要往这些表里写数据。字段少一个，后面就是 `patches.py` 幂等 ALTER 补丁；字段名不一致，就是接口层写转换代码。两种返工都比一次做对贵。

主数据域 11 张表：`warehouse`、`owner`、`user_owner`、`zone`、`location`、`sku`、`barcode`、`partner`、`apikey`、`unit`、`sequence`。

库存域 4 张表：`lot`、`stock`、`txn`，加上库存状态枚举常量。

### M2 post_stock 的四道闸

这一个函数是整个系统最热、也最不能出错的地方。四件事必须同时成立：

```mermaid
flowchart TD
  call["post_stock(sku, lot, location, status, delta, ref...)"]
  call --> lock["1 锁行<br/>SELECT ... FOR UPDATE"]
  lock --> idem["2 幂等<br/>先插流水，唯一键冲突即返回已有结果"]
  idem --> neg["3 非负<br/>qty + delta >= 0，否则拒绝"]
  neg --> upd["4 更新数量 + 写流水<br/>同一事务"]
```

**先插流水再改数量**，不是反过来。流水表上 `(ref_type, ref_id, sku_id, lot_id, location_id, action)` 唯一，重复调用会在这里撞键；捕获冲突后直接返回成功，数量不动。这样幂等由数据库保证，不靠应用层判断"我上次是不是做过"。

**锁行的顺序固定**：sku → lot → location。多个过账并发时按同一顺序取锁，避免死锁。

**负库存直接拒绝**，不做"允许负库存后对账"。WMS 的负库存等于账已经错了，让它写进去只会掩盖问题。

### M3 transfer_status 只写一条流水

库位内的状态转换（available ↔ frozen ↔ damaged）不是两次过账，是一条带前后状态的记录：扣源状态、加目标状态，总量守恒。

流水表加 `from_status` / `to_status` 两列，`post_stock` 时为空，`transfer_status` 时必填。

### M4 两套编码，各生成各的

| 编码 | 生成 | 规则 |
|---|---|---|
| 仓库货品编码 `sku.code` | 新建时自动取号 | `SKU` + 6 位序号，走 `sequence` 表 |
| 货主货品编码 `sku.owner_sku_code` | 货主或上游提供 | `(owner_id, owner_sku_code)` 唯一 |

`sequence` 表按 `(prefix, period)` 取号，用 `SELECT ... FOR UPDATE` 保证不重号；`period` 为空表示全局序列（SKU 用它），有值表示按日重置（单号用它）。

### M5 字段分组靠 schema 表达

货主能改的字段和仓库能改的字段不重叠，这个边界落在两个 Pydantic 模型上：`SkuBaseIn`（货主组）与 `SkuStorageIn`（仓库组），分别对应 `PUT /skus/{id}` 与 `PUT /skus/{id}/storage`。

不用字段级动态校验——那会让"这个字段到底谁能改"变成运行时才知道的事。

### M6 菜单由插件 seed，按 `ui-map.md` 逐期补

本期补主数据 6 页与库存 3 页，加上按钮级权限。角色绑定沿用 P0 的 `_bind`，只增不减。

### M7 前端先做"能用"不做"好看"

六个主数据页面 + 三个库存页面，统一用 Element Plus 的表格 + 抽屉表单。库存查询默认按「商品」聚合，展开才看批次——三万单量级下逐行铺开批次会直接卡死。

## Risks / Trade-offs

- **11 张表一次建完，`install()` 失败会留下半套表** → 建表放在同一个 `engine.begin()` 里，DDL 不可回滚但至少顺序固定；seed 失败只影响菜单，可以重跑。
- **`FOR UPDATE` 在 SQLite 上无效** → 与 D11 一致：开发与验收一律 MySQL，SQLite 只用于看看界面。
- **库存查询按商品聚合会掩盖批次差异** → 聚合行上显示"3 个批次、最早到期 XX"，点开看明细。
- **前端九个页面工作量大** → 先做列表 + 基础表单，导出、批量操作留到后续期次。
