# Tasks

## 1. 表结构

- [x] 1.1 `wms_outbound` 追加 `wave_rule`、`wave`、`sort_cell`、`seed` 四张表；`order` 补 `wave_id` 列（走幂等补丁）
      —— 四表建成，`wms_outbound/patches.py` 补列成功；重启后 6 个插件全部启用
- [x] 1.2 新建 `wms_internal_ops` 插件包，首期只建 `replenish` 表；验证标准：插件依赖 `wms_inventory`，可独立启停
      —— 包已建，依赖 `master_data`/`inventory`/`outbound`；`wms_internal_ops_replenish` 表带 `lot_id`
- [x] 1.3 两个包补菜单：波次看板、分播作业、打印模板、补货建议
      —— 出库域新增 3 页（波次看板/分播作业/打印模板）+ 3 个按钮；库内作业域新增补货建议页 + 2 个按钮

## 2. 波次规则与异步生成

- [x] 2.1 波次规则 CRUD：截单时间、承运商、区域前缀、热度阈值、单波上限
      —— 列表、新建、编辑已实现；`TIME(created_at)` 判截单，`hot_only` 按订单行数在内存过滤
- [x] 2.2 `POST /waves`：按规则筛选 `confirmed` 订单，落 `pending` 记录并立即返回 id
      —— 订单在返回前就绑定 `wave_id`，避免两个波次抢同一批单
- [x] 2.3 后台 `asyncio.create_task` 生成：逐单调 `allocate_fefo` + `release_to_pick`，每 50 单 `await asyncio.sleep(0)`
      —— 实测 60 单全部生成；后台任务自己开 `SessionLocal`，不用请求 session
- [x] 2.4 进度落库：`processed / total / failed`，`GET /waves/{id}` 可轮询
      —— 每 10 单刷新一次进度，避免每单一次写
- [x] 2.5 状态机 `pending → generating → ready → picking → done`；单笔分配失败记入 `failed` 并继续下一单，不放整波失败
      —— 实测：60 单 `ready 60/60 failed 0`；另一次含一张指定批次不足的单，该单记入 `failed`，波次仍 `ready`
- [x] 2.6 `cancel`：任意阶段可中止；已生成的拣货单标记作废，不动已发运订单
      —— `cancel` 把 wave 置 cancelled、未发运 pick 置 cancelled、allocation 置 void、订单退回 confirmed；库存数量全程不变
- [x] 2.7 启动恢复：`generating` 超时未更新的波次标为 `interrupted`，不自动续跑
      —— 实测：造两条 generating，20 分钟前的标记后转 `interrupted` 且写 `finished_at`，
      1 分钟前的仍为 `generating`、`finished_at` 为空，返回 1；不误伤正在跑的波次

## 3. 播种墙分播

- [x] 3.1 格口管理：按播种墙生成 `sort_cell`，一个格口绑一个订单
      —— 实测 60 单生成 60 个格口；重复调用 `created=0`
- [x] 3.2 分播接口：扫商品条码 → 返回应放格口；扫错订单/格口不匹配时拒绝
      —— 实测扫错 `WRONG` 返回 422「应放 C001」；不传格口时系统返回 C001
- [x] 3.3 整单分播完成 → 订单进复核；B 端整箱走边拣边分，不进播种墙
      —— 格口 `full` 时订单自动转 `checked`；B 端入口按 `order_type` 区分，未做 UI
- [x] 3.4 分播结果可查：每个格口已放几件、还差几件
      —— `GET /waves/{id}/cells` 返回 `placed_qty` / `required_qty` / `status`

## 4. 整箱补货

- [x] 4.1 补货建议：筛 `location_type=picking` 且当前量低于 `replenish_min` 的商品
      —— 只读扫描；完全没有库存行的空库位属于首次铺货，系统不知道补哪个商品，留 P5
- [x] 4.2 建议量按 `qty_per_box` 向上整箱取整，上限 `replenish_max`
      —— **实现改为向下取整**：向上取整会超过 `replenish_max`，且拆箱会让拣选位出现散箱。实测 12 件（1 整箱）
- [x] 4.3 执行补货：从存储区扣、向拣选区加，同事务两条流水
      —— 实测存储位 15→3、拣选位 5→17，总量守恒 20→20；`post_stock` 带真实 `lot_id`
- [x] 4.4 存储区不足时拒绝并提示可用量，不部分补
      —— 执行时重新校验来源库存；建议阶段也会跳过"找不到足够整箱来源"的商品
- [x] 4.5 重复执行同一建议不重复补货（幂等键含建议 id）
      —— 实测：重复 `suggest` 返回 `created=0`；重复 `execute` 返回同一状态、库存不再变化

## 5. 打印 —— 已移交 `adopt-hiprint-print`

原 5.1–5.6、6.4、7.4 共九条移交 `adopt-hiprint-print`（16 条），与那边的 1.1–1.4、2.1–2.4、4.x
一一对应，本变更加入范围不含打印，不在此重复列条目。表名以该变更为准。

当前「打印模板」菜单指向一个说明页，点得到但打不出纸，这一点要如实告知使用者。

## 6. 前端

- [x] 6.1 波次看板：四个数字块 + 波次表格 + 进度条 + 中止按钮
      —— 有 pending/generating 的波次时自动 1.5 秒轮询，跑完停止；生成与中止都二次确认
- [x] 6.2 分播作业页：扫商品即显示应放格口
      —— 选波次自动生成格口；扫完高亮结果并聚焦回输入框；格口卡片按 empty/filling/full 三态着色
- [x] 6.3 补货建议页：当前量/下限/建议整箱数 + 执行按钮
      —— 列表带状态筛选，「扫描并生成建议」与逐行「执行补货」

## 当前批次范围

打印移交后本变更只剩 2.7、7.1、7.2 三条。2.7 已实测通过，7.1 已实测通过，
**7.2 未通过**：中止后仍有在途订单停在 `picking`，阻塞归档。

## 7. 验收

- [x] 7.1 一次波次装 200 单，后台生成期间登录接口仍可响应
      —— 实测波次 `WAV000006`：`total=200`、`processed=200`、`failed=0`、终态 `ready`。
      生成窗口 18:08:32–18:08:46（约 14 秒）内串行探活登录 34 次，**全部 200**，
      平均 265.0 ms、最大 317.1 ms（登录本身走 bcrypt，265 ms 是基线量级而非阻塞）
- [ ] 7.2 生成到一半中止：已生成拣货单全部作废，库存数量不变
      —— **未通过，可复现**。两轮结果：
      · 第一轮 `WAV000007`：`processed=10` 时中止，HTTP 200，波次转 `cancelled`；
        12 单被正确作废（pick `cancelled`、allocation `void`、订单退回 `confirmed` 并解绑 `wave_id`），
        但**另有 3 单在中止提交后仍被继续处理**，停在 `picking`、pick 为 `pending`、
        allocation 为 `active`，`wave_id` 仍指向已取消的波次
      · 第二轮 `WAV000008`：同样复现，残留 2 单
      · 两轮库存总量均前后一致（sku1 349 → 349、sku2 80 → 80），"库存不变"这一半成立
      —— 根因见实施记录「中止与生成存在竞态」
- [x] 7.3 补货 1 托：存储区减、拣选区加，总量守恒
      —— 实测 15→3 / 5→17，20→20
- [x] 7.5 停用 `wms_internal_ops` 后补货接口与菜单同时消失
      —— 插件 `uninstall()` 按 `wms_internal_ops:%` 与 `/wms-internal-ops%` 双前缀清菜单，机制与 P0 已验一致

## 实施记录

- **修了两个 async SQLAlchemy 坑**：`commit()` 后对象被 expire，再读 `wave.operator_id` 会 `MissingGreenlet`；单笔失败 `rollback()` 后同理。后台任务里把 id / code / operator_id 提前取成普通值，循环只用普通值。
- **`recover_interrupted` 不能挂在列表查询上**：波次生成是后台任务，前端一轮询就会把正在跑的波次误判为中断。改为只在进程启动调用一次，且带 10 分钟超时阈值。
- **打印模板菜单权限统一用 `wms_outbound:` 前缀**：表在主数据域，但页面入口归出库作业；否则停用出库插件时这个菜单删不掉。
- **中止与生成存在竞态（7.2 暴露，未修）**：`cancel_wave` 用 `with_for_update()` 锁波次行，
  但 `generate_wave` 每单开头读 `wave.status` 是快照读，读不到未提交的 `cancelled`；
  `cancel_wave` 又在事务里对每张订单单独查一次状态（200 次 N+1），事务被拖长，
  窗口进一步放大。结果是：中止提交时正在处理的那 1–3 单在提交后才 `commit`，
  沿用了中止前的状态判断，落成 `picking` + `pick pending` + `allocation active`，
  且 `wave_id` 仍指向已取消波次——这些单既拣不动也回不到可分配池。
  库存不受影响（分配只记账不动 `stock.qty`）。
  修法方向（未实施）：中止后由生成任务在下次 `commit` 前复核一次波次状态；
  或把 `cancel_wave` 的逐单状态查询改成一条 `UPDATE ... WHERE order_id IN (...)`。
