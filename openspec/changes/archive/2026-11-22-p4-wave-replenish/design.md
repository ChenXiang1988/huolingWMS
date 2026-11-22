# Design

## Context

P3 的 `allocate_fefo` 是单订单级：一条 `IN` 查询取候选库存、内存按到期日排序、写 `allocation`，库存数量到 `ship()` 才动。这个形状在 1.7 单/秒下够用，但逐单操作本身是瓶颈。

P4 不重写分配，只在它外面套一层批量编排。

## Decisions

### W1 波次是真异步，不是同步长请求

```mermaid
flowchart LR
  post["POST /waves<br/>落 pending 返回 id"] --> task["asyncio.create_task<br/>后台生成"]
  task --> loop["分页拉订单<br/>每 50 单 sleep(0)"]
  loop --> alloc["allocate_fefo<br/>复用 P3 契约"]
  alloc --> pick["release_to_pick<br/>复用 P3 契约"]
  pick --> ready["wave ready"]
  ready --> cancel["任意阶段可 cancel<br/>已生成拣货单标记作废"]
```

同步跑三万单会把 HTTP 连接挂住，超时后前端不知道该重试还是放弃。落一条 `pending` 记录立刻返回 id，前端轮询 `GET /waves/{id}` 看 `processed/total` 与状态，是最简单也最可恢复的形态。

**每 50 单 `await asyncio.sleep(0)`**：单进程部署下，后台任务不让出事件循环会把整个 FastAPI 卡住，登录和查询都会变慢。

### W2 中止不回滚，只标记作废

波次生成到一半时，前面的订单已经有 `allocation` 和 `pick`。回滚这些数据要么删记录、要么反向补库存，两条都容易出错。

所以 `cancel` 只做两件事：把 wave 置 `cancelled`、把该波次已生成但还没发运的 pick 置 `cancelled`。已经发出去的货不动——它本来就该发。

### W3 分配仍不改库存数量

波次批量调用 `allocate_fefo`，依然只写 `allocation`。这一点不能因为"批量"就变：否则波次中止时会留下半扣的库存。

### W4 播种墙：格口即订单

`sort_cell` 记录格口编号与当前绑定的订单；`seed` 记录"扫到某商品，应放到哪个格口"。B 端整箱不走分播，走边拣边分，直接在拣货行上标记。

### W5 补货按整箱取整

拣选区当前量低于 `replenish_min` 时，建议量 = `ceil((replenish_max − 当前量) / qty_per_box) × qty_per_box`。不按零头补，否则拆零库位里会出现散箱，作业员没法整箱搬。

补货落库时走 `post_stock` 两次（扣存储区、加拣选区），同事务、两条流水。

### W6 打印沿用 hiprint 既定方案

模板存 `wms_master_data_print_template`（已在 P1 设计里定过），前端 `vue-plugin-hiprint` 渲染，经 socket.io 连本机 `electron-hiprint:17521`，由 Windows 驱动出纸。

**不自建 ZPL 代理**。代价是引入一个 Windows 客户端依赖，靠开机自启 + 前端常驻连接状态提示兜底。二维码扫读质量必须在 P4 真机验收，不合格才回退 ZPL。

### W7 定时任务用 asyncio

基座 `pyproject.toml` 里没有 APScheduler。单进程部署下，进程内 `asyncio.create_task` + 计算下次执行时刻就够；多进程才需要外部调度，而这套系统明确单进程。

## Risks / Trade-offs

- **后台任务与请求共用事件循环** → 每 50 单让出一次；如果实测仍影响登录响应，降到每 20 单。
- **进程重启会丢掉进行中的波次** → `wave.status=generating` 且长时间未更新时，下次启动标记为 `interrupted`，由人工重新发起，不自动续跑（自动续跑最容易重复分配）。
- **打印客户端是生产依赖** → 客户端挂掉只影响该工位，但要显式提示；不做静默失败。
- **补货建议可能超存储区可用量** → 生成建议时只读，执行时才校验库存并拒绝部分不足。
