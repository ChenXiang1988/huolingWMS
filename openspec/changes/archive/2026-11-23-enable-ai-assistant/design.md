# Design

## Context

见 proposal.md 的 Why。当前 `_hide_vendor_menus` 无条件把 `/ai%` 与 `ai:%` 菜单置 `status=0`,且只做"非 0 改 0";MCP 则按 `MCP_ENABLED` 条件隐藏。AI 的后端路由、内置 agent、前端页面与动态注册机制都已就绪,没有总开关。另有一个未归档的 `admin-navigation-restructure` 也在修改 platform-bootstrap 的同一菜单需求。

## Goals / Non-Goals

**Goals:**

- AI 助手菜单默认可见,老环境升级后能从隐藏状态恢复。
- 配置开关与 MCP 同构,管理员可以关闭 AI 能力。
- 规格与文档中的"改状态即可恢复"有实际代码路径支撑。

**Non-Goals:**

- 不内置真实模型密钥,不调整 `AI_DAILY_LIMIT` 默认配额。
- 不改 AI 前端页面、对话逻辑与工具集。
- 不动 MCP 的现有开关行为。

## Decisions

**新增 `AI_ENABLED: bool = True`,比照 `MCP_ENABLED`。** 统一配置模型,管理员有明确的关闭入口;默认 true 才符合"放出来"。备选是直接删掉隐藏条件,因为没有关闭手段而否决。

**恢复逻辑放在 seed 里。** `AI_ENABLED=true` 时把 `path LIKE '/ai%'` 或 `permission LIKE 'ai:%'` 的菜单 `status` 恢复为 1。现有隐藏单向、老环境无法自愈,必须补这一步;让用户手工改数据库与文档承诺不符,否决。

**增量菜单列表补齐 AI 菜单树。** 老环境的 `missing_menus` 只有 `ai:chat:call` 按钮权限,没有顶级目录和页面记录。补建按 `name + parent_id` 去重,记录已存在时不会重复插入,恢复逻辑再把 `status` 置 1。

**前端不改。** 侧栏没有 AI 过滤,页面文件与按 `component` 动态注册路由的机制齐全;侧栏推广按钮指向 `/ai/chat`,菜单恢复后该路由自然注册,404 随之消失。

**规格 delta 写入合并后的全文。** `admin-navigation-restructure` 未归档且修改同一 requirement,本 change 的 delta 同时包含门户隔离场景与 AI 场景,避免两份 delta 归档时互相覆盖。归档顺序必须是 `admin-navigation-restructure` 先、本 change 后。

## Risks / Trade-offs

- [占位密钥] 默认供应商 key 是 `sk-placeholder`,菜单可见但对话会失败 → 页面提示管理员填写真实 key,规格已写明未配置时拒绝并提示。
- [归档顺序] 两个 change 改同一 requirement,顺序反了会丢 AI 场景 → design 固定顺序,归档时按此执行。
- [手工隐藏被覆盖] 管理员手动把 AI 菜单 `status=0` 但开关仍为 true,下次 seed 会恢复为 1 → 接受;正确关闭方式是把 `AI_ENABLED` 设为 false。

## Migration Plan

```mermaid
flowchart LR
    A[部署后端] --> B[seed 补建 AI 菜单树]
    B --> C[AI_ENABLED 开启时恢复 status]
    C --> D[管理员填写真实模型密钥]
    D --> E[侧栏可见 AI 助手并可对话]
```
