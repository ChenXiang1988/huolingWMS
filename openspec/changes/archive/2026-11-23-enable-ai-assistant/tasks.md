# Tasks

## 1. 配置与菜单恢复

- [x] 1.1 在配置中新增 `AI_ENABLED: bool = True`，验证 `Settings()` 读到默认值 true 且可用环境变量覆盖
- [x] 1.2 把 seed 里 AI 菜单的无条件隐藏改为受 `AI_ENABLED` 控制，验证开关为 false 时 AI 菜单 `status=0`、MCP 行为不变
- [x] 1.3 在 seed 中增加 AI 菜单恢复逻辑，验证已存在 `status=0` 的 AI 菜单在开关开启后恢复为 1，重复执行不产生重复记录
- [x] 1.4 补齐增量菜单列表中的 AI 顶级目录与两个页面，验证老环境升级后菜单树包含 AI 助手、AI 全能助手与模型密钥管理

## 2. 规格同步

- [x] 2.1 按 design.md 的固定顺序规划归档：本 change 在 `admin-navigation-restructure` 之后归档，并验证两份 delta 合并后的 `菜单基线只含货灵模块` 需求同时包含门户隔离与 AI 启用场景
- [x] 2.2 执行 `openspec validate enable-ai-assistant --strict`，验证四份产物齐全且严格校验通过

## 3. 集成验证

- [x] 3.1 启动服务并用超管登录，验证侧栏出现 AI 助手及其两个子页、侧栏推广按钮不再跳 404
- [x] 3.2 在未填真实密钥的环境发起对话，验证请求被拒绝并返回提示配置密钥，而非空结果或服务端异常

## Workflow follow-up

- 待 `admin-navigation-restructure` 归档后再归档本变更。
