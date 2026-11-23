# Proposal: 启用 AI 助手

## Why

AI 助手的后端路由、内置 agent、前端页面与默认供应商都已落地,但初始化 seed 无条件把 AI 菜单置为 `status=0`,侧栏看不到入口;侧栏推广按钮却直接指向 `/ai/chat`,点击落到 404。隐藏逻辑只做"非 0 改 0",即使填好模型密钥也没有恢复路径,文档里"改状态即可恢复"在代码上并不成立。

## What Changes

- 新增 `AI_ENABLED` 配置,默认开启;AI 菜单隐藏改为受该开关控制,不再无条件隐藏。
- seed 在开关开启时把已隐藏的 AI 菜单恢复为可见,补上文档承诺的恢复路径。
- 增量菜单列表补齐 AI 助手顶级目录与两个页面,老环境升级后能拿到菜单记录。
- 规格中"未启用的能力菜单"改为只描述 MCP;AI 助手默认启用。
- 默认供应商仍是占位密钥,菜单放出来后需管理员在「模型密钥管理」填真实 key 才能对话;本次不内置密钥,也不调整 `AI_DAILY_LIMIT` 默认配额。

## Capabilities

### New Capabilities

无。AI 属平台能力,domain-map 的十个业务域不含 AI,不另开能力。

### Modified Capabilities

- `wms/platform-bootstrap`:「未启用的能力菜单」与「菜单基线只含货灵模块」两条需求调整——AI 助手默认启用,MCP 仍按配置开关隐藏。

## Impact

- `backend/src/core/config.py`: 新增 `AI_ENABLED`。
- `backend/src/core/seed.py`: 隐藏条件受开关控制、增加恢复逻辑、补齐增量菜单。
- `frontend/`: 无需改动,侧栏没有 AI 过滤,页面与按菜单动态注册路由的机制齐全。
- 与 `admin-navigation-restructure` 都修改 platform-bootstrap 的菜单需求,归档顺序见 design.md。
