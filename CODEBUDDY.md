# 货灵 WMS

单仓、多货主的三方仓储系统，管理一座物理仓四面墙内的作业：收货、上架、库存、波次拣货、分播、发运、留样、计费。B 端大货与 C 端电商混合作业，日单量三万级。

## 关键前提

- **单仓，不是多仓。** 仓型（平面仓 / 楼层仓 / 钢结构立库）是配置项，同一时刻只有一种生效。
- **多货主是第一维度。** 商品档案、库存、单据全部按货主归属；一个货主一个主账号，主账号可建子账号。
- **库位级管理。** 库存粒度是「货主 + 货品 + 批次 + 库位 + 状态」。留样是一种存储位置，不是库存状态。
- **批次按商品开关。** 启用的商品收发货必带批次、出库先到期先出、临期自动冻结；未启用的归入默认批次（`lot_id = 0`），界面不出现批次。
- **货品档案分工建。** 货主填「这是什么货」，仓库补「这货怎么存」，两组字段不重叠，不做事前审核，未建档拒收。
- **温区只做建议。** 有冷藏区，但温区不做硬拦截；放错温区要留痕，不留痕就查不出货损责任。
- **库存数量只有库存域能写。** 任何变动都在同一事务里写流水，流水只追加不修改，过账按来源单据幂等。
- **数量只存最小单位。** 所有 `qty` 都是件数，箱与托只存在于录入与展示两端，进库前换算（D27）。
- **只验货，不质检。** 到货核对是收货环节的一部分，不建质检单据。
- **货主两个入口，一套规则。** 系统对接走 API，人工操作走自助端（只做桌面），建单逻辑共用同一份实现。
- **出库分两模式。** B 端整箱走边拣边分，C 端拆零走波次加播种；波次规则可组合，生成异步。补货是拆零的前提。
- **复核称重拦截。** 打包后与理论重量比对，超差重检；面单与标签走本地打印代理，热敏机出纸。

行为约束以 `openspec/specs/wms/` 为准（已归档的八份规格），设计与选型见 `docs/design/`。

## 项目结构

```
backend/    FastAPI 后端，业务按域拆成插件（src/plugins/builtin/wms_*）
frontend/   Vue3 前端，后台 + 货主门户 /owner + 作业端路由组 /m
mobile/     Capacitor 容器工程，只打作业端 APK
openspec/   specs/ 常驻规格；changes/ 进行中的变更与归档
docs/design/ 详细设计：表结构、接口、页面、技术栈
```

`backend/`、`frontend/`、`mobile/` 尚未创建，由 P0 落地。

## 技术栈

Python 3.11 + FastAPI + SQLAlchemy 2.0 async + MySQL 8
Vue 3.5 + TypeScript + Vite 6 + Element Plus 2.14 + Pinia
管理基座：ApeAdmin（插件化 RBAC 框架，插件即业务域）

完整清单与关键选择的理由见 `docs/design/tech-stack.md`。

## 命令

以下命令在 P0 落地后可用。

```bash
# 开发环境：只有数据库进容器
docker compose up -d mysql
uvicorn src.main:app --reload     # backend/
npm run dev                       # frontend/

# 测试：必须连 MySQL，SQLite 只用于零配置看界面
docker compose run --rm backend pytest

# 全栈验证
docker compose up --build

# OpenSpec
openspec list
openspec status --change <name>
openspec validate <name> --strict
```

## 命名约定

| 对象 | 规则 | 示例 |
|---|---|---|
| 插件包 | `wms_<域>` | `wms_inbound` |
| 表名 | `wms_<域>_<实体>` | `wms_inbound_asn` |
| 路由 | `/api/v1/wms-<域>/<资源>` | `/api/v1/wms-inbound/asns` |
| 对外路由 | `/api/v1/open/v1/<资源>` | `/api/v1/open/v1/asns` |
| 权限标识 | `wms_<域>:<资源>:<动作>` | `wms_inbound:asn:create` |
| 菜单 component | `wms_<域>/<页面>/index` | `wms_inbound/asn/index` |

这些前缀不是风格偏好——基座靠它们判定菜单归属、清理插件元数据、解析前端页面。写错会让停用插件时菜单藏不掉。

## 文档

| 文档 | 层 | 内容 |
|---|---|---|
| `openspec/specs/wms/*/spec.md` | 规格 | 八份常驻能力规格：领域边界、库存台账、批次效期、计费、货主访问、移动端、库位策略、波次拣货 |
| `openspec/changes/archive/2026-11-21-define-wms-blueprint/` | 蓝图 | proposal、design（29 条决策）、tasks；归档后不再修改 |
| `docs/design/data-model.md` | 详细设计 | 表结构、枚举、状态机、单号规则 |
| `docs/design/interface-map.md` | 详细设计 | 权限清单、路由、对外接口、跨域契约、幂等键 |
| `docs/design/ui-map.md` | 详细设计 | 菜单树、页面清单、路由组 |
| `docs/design/tech-stack.md` | 详细设计 | 技术栈定稿、容量推算、部署 |
| `docs/design/inbound-walkthrough.md` | 详细设计 | 来货场景推演，兼作 P2 验收脚本 |
| `仓库模拟建模.md` | 规划参考 | 三类仓型的空间与容量推导（不进系统） |
| `仓内设备与调度模型.md` | 规划参考 | 搬运、分拣、调度资源建模（不进系统） |

规则见 `.codebuddy/rules/`：复杂度预算、文档输出规范。
