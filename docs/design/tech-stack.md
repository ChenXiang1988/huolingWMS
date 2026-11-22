# 技术栈

**层：详细设计** ｜ 蓝图见 [design.md](../../openspec/changes/archive/2026-11-21-define-wms-blueprint/design.md)。这份是定稿，照着可以直接建工程。

## 一、结论

基座已经把技术栈铺完了。全部需要新增的依赖是**后端 3 个、前端 3 个**：

| 新增 | 版本 | 用途 |
|---|---|---|
| `apscheduler` | 3.10+ | 定时任务 |
| `qrcode` | 7.4+ | 生成库位与单据二维码 |
| `openpyxl` | 3.1+ | 导出 Excel |
| `dayjs`（前端） | 1.11+ | 日期处理，显式声明避免依赖传递 |
| `vue-plugin-hiprint`（前端） | 最新 | 打印模板设计与渲染 |
| `socket.io-client`（前端） | 4.x | 连本地打印客户端 |

其余全部来自 `ApeAdmin-master` 已有的 `pyproject.toml` 与 `package.json`。

## 二、运行环境

| 项 | 要求 | 依据 |
|---|---|---|
| Python | 3.11+ | 基座 `requires-python` |
| Node | 20 LTS+ | Vite 6 |
| MySQL | 8.0+，`utf8mb4_0900_ai_ci`，时区 `+08:00` | T3 |
| Docker | 24+，含 Compose v2 | T3，本机与服务器均需 |
| 浏览器（后台与门户） | Chrome 110+ | Element Plus 2.14 |
| Android（作业端） | 14+，WebView 对应 Chrome 116+ | D19 |
| 服务器 | 单机 4C8G 起步 | 单仓量级，未实测 |

## 三、后端

| 层 | 选型 | 版本 | 来源 |
|---|---|---|---|
| 语言 | Python | 3.11+ | 基座 |
| 包管理 | pip + `pyproject.toml`（hatchling） | — | 基座 |
| Web 框架 | FastAPI | ≥0.141 | 基座 |
| ASGI | uvicorn[standard] | ≥0.52 | 基座 |
| 校验 | Pydantic | ≥2.13 | 基座 |
| 配置 | pydantic-settings | ≥2.15 | 基座 |
| ORM | SQLAlchemy[asyncio] | ≥2.0.52 | 基座 |
| 驱动 | aiomysql / aiosqlite | ≥0.3.2 / ≥0.22 | 基座 |
| 迁移 | Alembic（WMS 表走 patches，见 D10） | ≥1.19 | 基座 |
| JWT | python-jose[cryptography] | ≥3.5 | 基座 |
| 密码 | passlib[bcrypt] | ≥1.7.4 | 基座 |
| 日志 | loguru | ≥0.7.3 | 基座 |
| HTTP 客户端 | httpx | ≥0.28 | 基座 |
| JSON | orjson | ≥3.12 | 基座 |
| CLI | typer + rich | ≥0.27 / ≥15 | 基座 |
| MCP SDK | mcp | ≥2.0.0 | 基座，本项目不启用（T1） |
| Redis 客户端 | redis | ≥8.1.0 | 基座，本项目不部署（T6） |
| 定时任务 | **apscheduler** | 3.10+ | **新增**（T2） |
| 二维码 | **qrcode** | 7.4+ | **新增**（T7） |
| Excel | **openpyxl** | 3.1+ | **新增**（T7） |

不装的东西：`python-barcode`（一维码生成，T5 已排除）、`WeasyPrint` / `reportlab`（PDF，走浏览器打印）、`pandas`（聚合在 SQL 做）、`celery`（T2 已排除）。

## 四、前端

| 层 | 选型 | 版本 | 来源 |
|---|---|---|---|
| 框架 | Vue | 3.5.45 | 基座 |
| 语言 | TypeScript | 5.7 | 基座 |
| 构建 | Vite | 6.0 | 基座 |
| 类型检查 | vue-tsc（`build` 时跑 `--noEmit`） | 2.1 | 基座 |
| UI | Element Plus + Icons | 2.14.8 | 基座 |
| 路由 | vue-router | 4.5 | 基座 |
| 状态 | Pinia | 2.3 | 基座 |
| HTTP | axios | 1.21 | 基座 |
| 图表 | echarts + vue-echarts | 5.6 / 6.7 | 基座 |
| 国际化 | vue-i18n（本项目不用，T8） | 9.14 | 基座 |
| 富文本/渲染 | marked + dompurify + prismjs | — | 基座，AI 对话用 |
| 拖拽排序 | sortablejs | 1.15 | 基座 |
| 表单校验 | Element Plus 内置 `rules` | — | 不引 vee-validate |
| 日期 | **dayjs** | 1.11+ | **新增** |
| 打印 | **vue-plugin-hiprint** + **socket.io-client** | 最新 / 4.x | **新增**（T5） |
| 包管理 | npm | — | 基座 |
| 代码检查 | 不引 ESLint / Prettier | — | 见 T9 |

## 五、移动端

| 层 | 选型 | 版本 |
|---|---|---|
| 容器（APK 形态） | Capacitor | 6.x |
| 目标平台 | Android | `minSdk 34` / `targetSdk 35` |
| 构建目标 | `chrome116` | — |
| 浏览器形态 | Chrome 110+ / Safari 16.4+ | — |
| 原生能力 | 广播扫码（PDA 型号确定后定插件）、蓝牙打印（若需要） | — |

**作业端两种形态，一份构建。** `dist` 既挂进 nginx 供浏览器访问 `/m/*`，也打进 Capacitor 壳给 PDA 安装。形态只影响版本门槛与原生能力，不影响功能边界——浏览器形态同样走打印代理，同样能扫码（广播拿不到就键盘模拟）。

只有作业端出 APK，货主端只做桌面（D18、D19）。

## 六、开发工具链

| 项 | 选择 | 来源 |
|---|---|---|
| 后端格式化 + lint | ruff（`target py311`、`line-length 120`、规则集 `E,W,F,I,N,UP,B,A,C4`） | 基座已配 lint，**补 `ruff format`** |
| 后端类型检查 | mypy `strict`（基座已配，但**不纳入发布 gate**） | 基座 |
| 前端格式化 | 无 | 见 T9 |
| 测试 | pytest + pytest-asyncio（`asyncio_mode = auto`）+ httpx | 基座 dev extras 已有 |
| 测试命令 | `docker compose run --rm backend pytest` | 因并发测试要 MySQL |
| CI | 不建 | 见 T10 |
| 版本标记 | git tag 按期（`p0`、`p1`…），不打语义化版本号 | 单体应用 |

## 七、数据与文件

| 项 | 约定 |
|---|---|
| 主键 | 自增 `bigint`，不用 UUID |
| 业务标识 | `code varchar(64)`，格式见 data-model 单号规则 |
| 金额与数量 | `Numeric(18,4)` + Python `Decimal`，禁止 float |
| 时间 | 标准库 `datetime` + `zoneinfo`，DB 存 `datetime`，统一 `+08:00` |
| 枚举 | Python `str Enum` ↔ DB `varchar`，不建枚举类型 |
| 分页 | `page` / `page_size`，与基座一致 |
| Excel 导出 | `StreamingResponse` 直接返回，不落盘、不走文件管理 |
| 二维码 | 后端 `qrcode` 生成 PNG，前端只做 `<img>`；编码规则单一来源 |
| 文件附件 | 沿用基座 `FILE_STORAGE_DIR`，本项目暂不使用 |

## 八、容量设计

日单量三万，作业时长按 12 小时算，峰值系数取 2.5。

| 指标 | 计算 | 结论 |
|---|---|---|
| 峰值订单 | 30000 × 2.5 ÷ 12 ≈ 6250 单/小时 | 1.7 单/秒 |
| 峰值拣货行 | 6250 × 2.5 行 ≈ 15600 行/小时 | 4.3 行/秒 |
| 每日拣货行 | 30000 × 2.5 ≈ 7.5 万行 | — |
| 峰值 PDA 扫码 | 30 人 × 每分钟 20 次 | 10 次/秒 |
| 总请求峰值 | 下单 + 扫码 + 后台查询 | 约 50 QPS |

**这些数字单机 MySQL 加单进程 FastAPI 完全吃得下。** 一次库存过账包含锁行、更新、写流水，约 5–10 ms，串行也就 100–200 次/秒。瓶颈不在吞吐。

真正需要设计的是三件事：

**波次生成。** 一次 300–500 单的分配，每单 10 ms，串起来 3–5 秒。必须异步，且不能占满事件循环——每处理 50 单让出一次，否则期间所有 PDA 扫码都会卡住。

**订单表增长。** 一年 1000 万行。查询默认带时间范围（近 7 天），跨月查询走归档表；归档策略是每月把 `shipped` 且超过 90 天的订单及其明细搬到 `_archive` 后缀的同构表，主表只留热数据。

**报表查询。** 三万单的日报聚合不能扫全表。报表走每日预聚合表，由定时任务在凌晨算好，页面只读结果。

**不做的事**：不加 Redis 缓存（T6）、不做分库分表、不上多 worker。这三样都是在这个量级用不上的复杂度，真到瓶颈时先做归档与索引优化。

## 九、部署

| 项 | 选型 |
|---|---|
| 编排 | Docker Compose v2：`backend` + `mysql` + `nginx` |
| MySQL 配置 | `my.cnf` 写死 `utf8mb4` / `utf8mb4_0900_ai_ci` / `+08:00` |
| 反向代理 | Nginx，同时挂 APK 与前端 `dist` |
| 备份 | `mysqldump` 容器 + 每日快照留存 7 天 |
| 日志 | 容器 stdout，loguru 输出 JSON，由 Docker 的日志驱动轮转 |

### 本地开发

| 步骤 | 命令 | 说明 |
|---|---|---|
| 起数据库 | `docker compose up -d mysql` | 只有 MySQL 在容器里 |
| 后端 | `uvicorn src.main:app --reload` | 宿主直跑，改代码即生效 |
| 前端 | `npm run dev` | 宿主直跑，Vite HMR |
| 测试 | `docker compose run --rm backend pytest` | 连同一个 MySQL，用独立测试库 |
| 全栈验证 | `docker compose up --build` | 仅发布前与演示用 |

后端与前端在宿主跑、只有数据库进容器，是改代码最快的组合。全栈容器化留给发布前验证——每次改一行就 rebuild 镜像没人受得了。

**SQLite 仍可用**（`DB_TYPE=sqlite` 直接起后端），但只用于"把界面打开看看"，不用于并发、幂等、计费相关的验证（D11）。

## 十、关键选择的理由

### T1 MCP 与 AI 助手：保留代码，默认关闭

`MCP_ENABLED=false`，6 个菜单留在 `sys_menu` 里但 `status=0`。

`mcp>=2.0.0` 已经在基座依赖里，保留不增加任何安装成本。剥离则要改基座，以后升级必冲突。摆到作业员面前则要有人维护模型密钥。

将来启用改配置与菜单状态，不动代码。

### T2 定时任务：APScheduler 进程内

`AsyncIOScheduler` 挂在 FastAPI `lifespan` 上。四类任务：推送重试（P7）、计费扫描、占用快照、账单生成（P8）。

四件事都天然幂等——计费靠 `(charge_item, ref_type, ref_id, period)`、快照靠 `(owner_id, day, location_type)`、推送靠 `sync_log` 状态机、账单靠 `(owner_id, period)`。多 worker 跑多份等于白跑。

Celery 要 Redis 加第二个进程，与 T6 冲突；cron 调 CLI 拿不到应用内连接池。

代价：多一个依赖；任务异常必须捕获，不能拖崩主循环；启停顺序要串好。

**长任务与定时任务分开。** 波次生成要跑 3–5 秒甚至更久，还会被中止。它不适合塞进 APScheduler——定时器的语义是"到点触发、跑完就算"，而长任务需要进度、中止、失败回滚。

做法是同一进程内另起一个执行器：任务落 `wms_outbound_wave` 的状态字段，`asyncio.create_task` 启动，处理过程中定期提交进度，中止时置标志位让循环自己退出。**不用外部队列**，因为只有一个长任务类型，且单进程前提下内存队列就够。

### T3 部署：全栈 Docker Compose

**理由不是流行，是唯一索引。** 这套设计的幂等全靠唯一约束，而唯一索引行为受排序规则影响：`utf8mb4_general_ci` 下 `ASN001` 与 `asn001` 同值，会挡掉本该新建的单；字符集不一致时索引前缀还可能静默截断。这类问题不报错，只表现为"偶尔建不出单"或"同一笔流水记两遍"。

容器化把字符集、排序规则、时区写死在 `my.cnf`，开发与生产同一份。

**代价**：服务器上运维要会 `docker compose`。开发机已有 Docker，本地零额外成本。

### T4 测试：pytest，只覆盖五处

测 `post_stock` 的增减/负库存/幂等、`transfer_status` 的总量守恒、`OwnerScope` 的越权、`create_asn` 两入口一致、计费幂等与冲抵。

这五处错了不报警：库存扣错只是账不平，幂等键错一个字就多记一笔，隔离开个口子就是数据泄露，计费重复就是账单多钱。

**统一跑 MySQL 容器，不分裂成两种引擎。** 幂等的正确性依赖唯一索引，而唯一索引行为受排序规则影响——SQLite 上通过的测试证明不了 MySQL 上成立。开发机已有 Docker，起一个测试库的成本已经付过。

连带影响：项目规则里"无测试目录故不要求先写复现测试"的例外失效。

### T5 打印：hiprint 模板 + electron 客户端

原方案是自建 FastAPI 代理、手写 ZPL 模板、直发 9100 端口。改成 `vue-plugin-hiprint`：模板拖拽设计存 JSON，静默打印经 socket.io 下发给 `electron-hiprint` 本地客户端，客户端调 Windows 驱动出纸。

| 打印机 | 尺寸 | 打什么 |
|---|---|---|
| 面单机 | 100×150 | 快递面单 |
| 标签机 | 60×40 / 40×30 | 库位、商品、托盘、包裹、格口标签 |
| A4 机 | A4 | 拣货单、装箱单、盘点表 |

**通道：socket.io 客户端直连 `localhost:17521`，不做中继。** `node-hiprint-transit` 只在跨网段时需要，仓库里浏览器与客户端同机，多一层中继只是多一个故障点。每台打包工位装一个客户端，只连本机，不跨机打印。

**模板存后端不存 localStorage。** `wms_print_template` 表 + 后台编辑页。存本地的话改一次版式要跑遍所有机器。

**打印任务落库。** `wms_print_task` 记录模板版本、目标打印机、客户端、成败与原因。重打时旧任务作废、新任务生效，面单号不变。

**电子面单整图贴入。** 快递公司返回 PDF/图片，转图后铺满模板，不解析字段重排——面单版式由快递方定义且会变，解析等于自找麻烦。

**吞吐按工位算。** 单张约 0.3–1 秒（走系统驱动），三万张必须多客户端并行。按打包工位数配客户端，实测后再定数量。不做集中排队——集中排队会把"某台卡纸"放大成整线停摆。

**浏览器打印降为应急**：客户端离线时，A4 文档类仍可走 `window.print()`；面单不可用浏览器打。

**代价**：多一个 Windows 桌面客户端作为生产依赖，崩溃或被安全软件拦截都会停一个工位。缓解是开机自启、前端常驻连接状态提示、每工位留一条 A4 应急通道。

### T6 缓存：不部署 Redis

核过基座 `get_current_user`——每请求都查一次用户连带 `roles`、`menus`（`selectin` 预加载），**这条热路径上没有缓存**。装 Redis 对最热的那条路径帮不上忙，而 Celery 已排除，没有 broker 需求。

`redis>=8.1.0` 仍留在依赖里（基座带的），不装服务端即可，无害。

将来开多 worker 时进程内缓存会各存一份，届时加 `REDIS_URL` 重启，不改代码。

### T7 依赖：qrcode + openpyxl

系统只**生成**二维码，不生成一维码——商品上的 EAN-13 / Code128 是厂商印好的，识别由扫码枪完成，系统只收字符串。

不装 `WeasyPrint` / `reportlab`（浏览器打印不经过 PDF，省掉 cairo、pango 系统依赖）、不装 `pandas`（聚合在 SQL 做）。

### T8 国际化：不做

中文硬编码，`i18n_key` 留空。`vue-i18n` 已在基座依赖里，不用它不影响结构。

i18n 的成本不在翻译，在每个新增文案都要同步 key、每个页面都要走 `t()`，是持续的税。而使用者全是中文。

注意：不做 i18n 不等于可以随便写文案。"货主/客户"、"库位/货位"混用是最容易积累的债，控制方式是遵守 `data-model.md` 的枚举名与表名用词。

### T9 前端不引 ESLint / Prettier

基座前端只有 `vue-tsc --noEmit` 这一道检查（`npm run build` 时跑）。没有 ESLint，也没有 Prettier 配置。

**理由**：引入 ESLint 要选配置集（`eslint:recommended` 还是 `plugin:vue/vue3-recommended`）、处理 Element Plus 的规则冲突、给 40 多个页面文件补第一遍。收益是抓到未使用变量与 `v-for` 缺 key 这类问题，而 `vue-tsc` 已经覆盖了类型层面的错误。

**代价**：格式不统一靠人工 review。缓解方式是沿用基座的缩进与引号风格，不在同一个文件里混用。

**复查点**：如果贡献者超过两人，或者出现反复的同类 review 意见，再引 ESLint。

### T10 不建 CI

**理由**：只有一个人提交代码。CI 的价值在拦住别人合入的坏代码，一个人写一个人合，本地跑通就等于过了。环境不是障碍——`services: mysql` 是现成写法，随时能加。

**替代**：一条命令覆盖——`docker compose run --rm backend pytest`。本地跑通即可，发布前必跑。

**复查点**：出现第二个人提交代码，或开始多环境部署时，把这条命令搬进 GitHub Actions / GitLab CI，几分钟的事，不改代码。

## 十一、换基座的代价

| 部分 | 是否受影响 |
|---|---|
| 十个域的划分与职责 | 不受影响 |
| 多货主的库存粒度与隔离 | 不受影响 |
| 库存记账的幂等与流水约束 | 不受影响 |
| 计费的费用派生与账单锁定 | 不受影响 |
| 库位坐标与选位规则 | 不受影响 |
| 插件拓扑（一域一包） | 重画 |
| 菜单归属靠字符串前缀 | 重画 |
| 表名前缀与元数据清理联动 | 重画 |
| 前端 `import.meta.glob` 解析 component | 重画 |
| 权限标识与 `require_permission` | 重写 |
| `install()` 建表与补丁模式 | 重写 |

业务蓝图可移植，落地形态不可移植。

## 十二、待确认

无。
