# Tasks

本变更只产蓝图，不改 huolingWMS 仓库代码。验证全部在 `ApeAdmin-master` 参考副本上做——用它的原始代码证伪或确认 design.md 里的事实假设，比在纸上推演可靠。

## 1. 验证基座事实与 D1 命名约定

- [ ] 1.1 原样启动 `ApeAdmin-master`（SQLite + 安装向导），确认能登录且侧边栏出现 `dev_example` 的「插件示例」菜单；验证标准：`/api/v1/dev-example/notes` 能在前端页面正常列出数据
- [ ] 1.2 把 `dev_example` 顶级菜单的 `path` 改成 `/wms-inbound`、子菜单 `component` 改成 `dev_example/asn/index`、`permission` 改成 `dev_example:asn:list`，然后停用该插件；验证标准：整条菜单从侧边栏消失，且 `component` 与 `permission` 两种归属条件都能独立触发隐藏（分别只改一项各试一次）
- [ ] 1.3 在 `frontend/src/views/dev_example/asn/index.vue` 放一个最小页面，确认动态路由能解析 `dev_example/asn/index` 并渲染；验证标准：菜单可点击且页面出内容而非 404
- [ ] 1.4 把顶级菜单 `path` 分别写成 `/wms_inbound` 与 `/wms-inbound` 各试一次停用，确认两种写法都能被识别为同一插件所有；验证标准：两次停用都隐藏了整条菜单
- [ ] 1.5 给 `dev_example/plugin.json` 加 `"dependencies": ["wms_inventory"]`，确认在前置域不存在时启用被拒绝并给出缺失项；验证标准：接口返回缺失依赖提示，插件未进入 active
- [ ] 1.6 在 MySQL 与 SQLite 各执行一次 `ALTER TABLE ... ADD COLUMN` 幂等补丁，确认 D10 的补丁写法在两种引擎下都能重复执行不报错；验证标准：连跑两次补丁，第二次静默跳过。补丁要兼容 SQLite 只是因为基座安装向导会跑它，不意味着业务验收能跑 SQLite
- [ ] 1.7 读 `src/models/rbac.py` 与 `src/core/deps.py`，确认 `User` 上没有货主字段、`Role.data_scope` 的四个取值全是部门维度，确认 D5 的「用户-货主关联表 + 请求入口注入」不会与基座既有过滤冲突；验证标准：能指出货主维度在基座里零落点，只能由 WMS 新表承载
- [ ] 1.8 确认基座 `require_permission` 的权限判定只认 `role.menus` 上的 `permission` 字符串，不含数据范围，验证 `wms_owner_viewer` 只给 list 权限就能把子账号限制成只读；验证标准：用只绑 list 权限的账号调用任一 create 接口得到未授权
- [ ] 1.9 通读 `src/core/middleware.py` 与 `src/main.py`，确认拿 `X-API-Key` 的请求不会触发任何全局 JWT 解析（`HTTPBearer` 只在路由依赖里生效）；验证标准：带 `X-API-Key`、不带 `Authorization` 的请求能走到目标路由而不被拦在中间件
- [ ] 1.10 把 `dev_example` 顶级菜单的 `path` 改成 `/owner`、`permission` 改成 `dev_example:portal:view`（`path` 前缀已不匹配插件名，只剩 permission 能命中），再停用插件；验证标准：顶级目录 `status` 变为 0，整条门户菜单收起
- [ ] 1.11 读 `src/models/rbac.py` 的 `Role` 定义，确认 `code` 是全局唯一且角色不带货主维度，验证「货主侧只能用固定角色、不做自定义」这个限制来自表结构而不是偏好；验证标准：能说明若放开自定义角色，两个货主的同名角色如何串味
- [ ] 1.12 读 `src/core/deps.py` 的 `get_current_user`，确认每个请求都重新查 `User.status`；把某账号 `status` 置 0 后用其旧 token 请求，验证标准：立刻返回未授权，不需要等 token 过期。据此确认「切断访问靠停用、不靠改密码」这个决定的依据成立

## 2. 验证双凭证、菜单过滤与计费前提

- [ ] 2.1 在 `dev_example/api.py` 加两条路由：一条沿用 `Depends(get_current_user)`，一条挂自定义 `X-API-Key` 依赖；确认两者在同一 app 内共存；验证标准：各自凭证访问各自接口成功，交叉使用两边都失败
- [ ] 2.2 核对 `sys_user` 与 `sys_role_menu` 的结构，确认后台登录态无法构造出调用对外路由的请求；验证标准：用后台 JWT 打对外路由得到未授权，且日志里没有把它当 API Key 解析
- [ ] 2.3 核对 `wms_inventory` 现有表结构能否回答「昨天某货主占了多少库位」；验证标准：确认库存表只存当前数量、无历史快照，从而证明 D16 的每日占用快照必须新建而不能靠回溯
- [ ] 2.4 给一个角色只分配门户菜单，请求 `/auth/userinfo` 对比超管返回的菜单树；验证标准：该角色只拿到门户分支，前端据此判断落地页的假设成立
- [ ] 2.5 确认基座同一份 `APIRouter` 或同一组 service 函数可以被两个不同前缀的 router 复用（`include_router` 两次是否会有路径冲突）；验证标准：两个前缀各自访问成功，且没有重复的 operationId
- [ ] 2.6 在 `ApeAdmin-master/frontend` 上把 Vite `build.target` 设为 `chrome116` 后构建，确认 Vue 3.5 与 Element Plus 2.14 不需要更高版本的 WebView 特性；验证标准：`npm run build` 通过，且 `npx browserslist` 显示目标不含超范围语法

## 3. 按实测结论修订制品

- [ ] 3.1 对照 1.1–2.5 的结果逐条核对 design.md 的 D1、D2、D5、D10、D17、D18，凡与实测不符的当场改写；验证标准：这六条决策均无"未验证"项
- [ ] 3.2 检查 design.md 的域职责表，确认十个域的「拥有的数据」两两不重叠、「不做什么」覆盖了所有易混边界；验证标准：任取一个能力（如"库位调整""账单冲抵""门户菜单"）能只靠该表定位到唯一域
- [ ] 3.3 复核货主相关条目：`domain-map` 的单仓多货主边界与四者一致校验、`stock-ledger` 的库存粒度与货主隔离、`owner-access` 的双入口与账号分级，确认 proposal、specs、design 三处口径一致且互不重复；验证标准：八份 spec 里搜「单货主」零命中（本条 tasks 自身除外），同一场景不出现在两份 spec 里
- [ ] 3.4 复核计费条目：`billing` spec 的六条 requirement 与 D16 的表清单、扫描节拍、幂等键对得上；验证标准：spec 里出现的每个概念（计费项、账期、快照、冲抵）在 design 里都有对应落点，反之亦然
- [ ] 3.5 检查 P0–P8 分期，确认每期的验收路径不依赖后续期；验证标准：逐期回答"关闭本期时，这一串操作能不能走完"，九期全部能走完
- [ ] 3.6 确认 Open Questions 各自标注了最晚解决时点，且不阻塞归档；验证标准：每条都写明在 P1 / P2 / P3 / P6 / P8 之前给出答案
- [ ] 3.7 确认「两个入口共用一套规则」在 design 里有唯一落点：建单校验只写在 `services.py`，`api.py` 与 `open_api.py` 只是薄壳；验证标准：能指出校验逻辑一行都不在路由文件里
- [ ] 3.8 确认主账号唯一性的实现方式是 `wms_master_data_owner.primary_user_id` 而不是唯一索引；验证标准：能说明 `(owner_id, is_primary)` 在 MySQL 下多条 false 会冲撞，因此选择字段指向
- [ ] 3.9 复核 `mobile-app` spec 的六条 requirement 与 D19 对得上；验证标准：spec 里的入口隔离、版本门槛、离线边界、客户端信任在 D19 都有对应段落，反之亦然
- [ ] 3.10 复核验货与留样的归属：验货落在入库域收货明细上且不建质检单；货主服务订单归入库域；留样记录归库内作业域且只存来源标识；留样靠 `location_type = sample` 表达而不是库存状态。验证标准：能说明留样记录为什么不反向依赖入库域（只存来源标识，不做外键与 join）、`ops → inbound` 为何不构成环，以及留样为何不能用库存状态表达（会被分配算法当成可发量）
- [ ] 3.11 复核留样的取值与处置：`fixed` 与 `ratio` 两种方式、比例向上取整并 cap 到实收数量、四条处置路径（报废/延期/邮寄/转回）各自落到哪个机制上。验证标准：四条路径里只有报废产生库存减量流水，延期不写流水，邮寄与转回各是移库加下游单据，D20 与 P4 验收路径对得上
- [ ] 3.12 复核三份详细设计互相咬合：`data-model.md` 的每张表都有明确归属域，`interface-map.md` 的每个权限标识都能对应到 `ui-map.md` 的一个菜单或按钮，跨域契约的参数名与 `data-model.md` 的字段名一致。验证标准：随机抽三张表、三个权限码、两个契约，都能在另外两份文件里找到对应；`data-model.md` 的枚举取值与 spec 里出现的取值不冲突
- [ ] 3.13 复核 `data-model.md` 的索引清单覆盖了所有幂等键与到期查询，且没有为"将来可能查"预建索引。验证标准：逐条对照 `interface-map.md` 的幂等键汇总表，每个键都有对应唯一索引；`wms_internal_ops_sample` 的 `(owner_id, status, retain_until)` 支撑到期清单
- [ ] 3.14 复核建模文档进系统的只有三条结论：坐标编码、空间域判定、选位优先级。验证标准：`仓库模拟建模.md` 里的 3,266 / 9,000 / 6,552 托位、分区比例、敏感性分析在 `data-model.md` 与 `location-policy` spec 里零出现；`floor_no` 与 `level` 在所有文档里都是两个字段
- [ ] 3.15 逐条核对 `tech-stack.md` 的"来源"列：标为基座的每一项都要能在 `ApeAdmin-master/backend/pyproject.toml` 或 `frontend/package.json` 里找到同名的包，标为新增的四项确实不在基座清单里。验证标准：抽后端五个、前端五个逐一比对；`Element Plus` 的版本号写的是 2.14.8 而不是 README 里过时的 2.9
- [ ] 3.16 确认十项选择的约束互不冲突：APScheduler 进程内不要求多 worker（D11）、不部署 Redis 则无组件依赖它（T2 已排除 Celery）、浏览器打印必须守住二维码与 100% 原尺寸（T5）、引入测试后项目规则的测试例外失效（T4）、不引 ESLint 则格式靠 review（T9）。验证标准：五条都能指出对应文档位置
- [ ] 3.17 确认新增依赖确为最小集：把 `apscheduler`、`qrcode`、`openpyxl`、`dayjs` 四个逐个问一遍"基座有没有能替代的"，`httpx` / `pytest` / `ruff` / `mypy` / `mcp` / `redis` 都不应出现"新增"字样。验证标准：`tech-stack.md` 第三节里标 `新增` 的行只有三行、第四节只有一行
- [ ] 3.18 确认 D11 改完之后全文没有残留"双引擎分叉"的说法：搜 `asyncio.Lock`、`SQLite 内存库`、`开发用 SQLite` 应零命中；`stock-ledger` spec 与 `data-model.md` 也不应出现"按引擎选锁"的描述。验证标准：全文只有一处说明 SQLite 的定位，且定位是"零配置预览，不用于并发与幂等验收"
- [ ] 3.19 复核货品档案的分工闭环：`domain-map` spec 的四条场景、`data-model.md` 的字段分组注释、`interface-map.md` 的 `sku:create/edit` 与 `sku:configure` 两个权限、`ui-map.md` 的门户「我的商品」页，四处指向同一套字段边界。验证标准：货主能改的字段与仓库能改的字段在三个文件里完全一致，无一个字段同时属于两组
- [ ] 3.20 复核温区只做软约束：`location-policy` spec 的三条场景、D23、`data-model.md` 的 `temp_zone` 枚举与 `putaway_line.temp_mismatch` 字段互相对得上。验证标准：全文没有"温区不符禁止上架"这类硬拦截表述；`temp_mismatch` 能回答"这批货放到了哪个非匹配温区"
- [ ] 3.21 复核 `inbound-walkthrough.md` 与蓝图一致：每一步写入的表与字段都能在 `data-model.md` 找到、每条库存变化都能对上 `stock-ledger` spec、五处系统感知点与 D7 的过账契约一致。验证标准：把推演里的四条 `post_stock` 逐条映射到契约参数，无参数在契约里不存在；七个阶段的状态推进都能在 `data-model.md` 的状态机表里找到
- [ ] 3.22 确认推演的"物理与系统不同步"结论没有被别处违反：全文不应出现"实时位置""货在哪"这类需要连续感知的能力承诺。验证标准：搜「实时」应只出现在明确否定的语境里
- [ ] 3.23 复核批次改动是否贯通：`lot-control` spec 五条要求、D24、`data-model.md` 的 `wms_inventory_lot` 与 stock/txn 的 `lot_id`、`interface-map.md` 的 `ensure_lot` 与 `pick_lots_fefo` 契约、`inbound-walkthrough.md` 的批次拆分数字，五处口径一致。验证标准：推演里 `20261015` 那批的 150 箱（147 好 + 3 破）在账面表里能对上；四者一致校验的表述在 `domain-map` spec 与推演里一致
- [ ] 3.24 确认批次改动没有留下"不分批次"的残留：搜「不采集批次」「不做批次」「批次粒度不拆分」应零命中；`stock-ledger` 里只剩"不采集序列号"这一条否定项。验证标准：`proposal.md` 的显式不做事只列序列号不列批次
- [ ] 3.25 确认数量口径唯一：全文搜「箱」只应出现在包装换算与拆箱动作的语境里，不该出现在任何 `qty` 字段的说明中；`data-model.md` 的通用约定已写明"一律以最小计量单位存储"。验证标准：`inbound-walkthrough.md` 的账面表与推演数字全部按件计，无一处把箱当库存单位
- [ ] 3.26 复核出库双模式与波次闭环：`wave-picking` spec 六条要求、D28、`data-model.md` 的 `order_type`/`wave_rule`/`wave`/`seed`/`sort_cell`、`interface-map.md` 的波次与分播路由、`ui-map.md` 的 P4 页面，四处口径一致。验证标准：抽一条波次规则能完整走到分播完成，中间每一层的状态与字段都能在 `data-model.md` 找到
- [ ] 3.27 确认三万单的量级假设被全文接受：搜「不做波次」「按单拣够用」应零命中；`tech-stack.md` 第八节的容量推算与 D28 的数字一致（6250 单/小时、7.5 万拣货行、5 行/秒）。验证标准：proposal、design、tech-stack 三处的规模描述不冲突
- [ ] 3.28 确认打印方案只有一套说法：搜「浏览器打印」应只在 A4 文档类的语境里出现，面单与标签一律提本地代理与热敏机。验证标准：T5 与 D29 的描述逐条一致，无一处仍把浏览器打印当作面单方案

## 4. 制品校验

- [ ] 4.1 运行 `openspec validate define-wms-blueprint --strict`，验证标准：退出码为 0，无告警
- [ ] 4.2 逐条检查八份 spec（`domain-map`、`stock-ledger`、`billing`、`owner-access`、`mobile-app`、`location-policy`、`lot-control`、`wave-picking`），确认每条 Requirement 至少有一个 Scenario 且 Scenario 可判定；验证标准：无"多分支却只有一个场景"、无写在 Requirement 正文里无法测试的形容词

## Workflow follow-up

- 蓝图评审通过后归档本变更，使八份 delta 成为 `openspec/specs/` 下的常驻约束。
- 按 P0–P8 依次独立起 change，每个 change 的 proposal 引用本蓝图并声明自己的域与 `plugin.json` 依赖。
- P0 起单时把 D1 的命名约定写进 tasks，并在 `wms_master_data` 上做一次端到端验证（菜单归属 + 前端页面解析 + 权限拦截）。
