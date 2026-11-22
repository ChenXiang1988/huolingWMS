# Proposal

## Why

P0 为了省一次构建，把货主门户和管理后台做成了同一个 SPA、同一个登录页、同一个 base 路径，登录后按身份重定向。当时判断"界面分开就够了"，这个判断是错的。

实测出来的三个问题：

1. **货主账号在后台登录页能登录成功**——`/auth/login` 对任何合法账号发 token，只是前端随后把它重定向到门户。token 已经签发，边界等于没有。
2. **跨端是重定向不是拒绝**。真正的边界应该是"这个账号不属于这个入口，直接失败"。
3. **两套界面的产物、登录页、favicon 全绑在一份 `index.html` 上**。改门户要动后台的构建，门户的品牌也没法独立。

## What Changes

- **两个构建产物与两个入口**：`/admin/`（后台 + 作业端）与 `/owner/`（货主门户）。同一个工程，`vite build` 出两套，`base`、入口 HTML、产物目录各自独立。
- **两个登录页**：后台沿用 `views/login/index.vue`，门户新增 `views/login/owner.vue`，视觉与文案按货主方设计。
- **登录即判身份**：新增 `POST /wms-master-data/owner-login`，只接受绑定了货主的账号；后台 `/auth/login` 通过 `before_login` 钩子拒绝货主账号。两边互不通用。
- **后台不再有门户路由**：`/owner` 分支从后台路由表移除，后台守卫里那套"按身份重定向"的逻辑整个删掉。
- **门户守卫反向收紧**：非货主账号开门户，直接清 token 回门户登录页，不跳后台。

## Capabilities

### New Capabilities

无。

### Modified Capabilities

- `wms/owner-access`：新增「货主门户与后台是两个独立登录端」，明确入口、登录、会话三层的分离，以及跨端必须失败而不是重定向。

## Impact

- `frontend/vite.config.ts`：按 `mode` 切换 base 与产物目录；新增 `owner/index.html` 与 `src/main-owner.ts`、`src/router/owner.ts`、`src/OwnerApp.vue`、`src/views/login/owner.vue`。
- `frontend/src/router/index.ts`：删掉门户分支与 `ownerFlag` 逻辑。
- `backend/src/plugins/builtin/wms_master_data/`：新增货主登录接口；`before_login` 改为拒绝货主账号。
- `backend/src/main.py`：额外挂载 `/owner` 一份静态产物（本地验证用；生产由 nginx 各自分发）。
- `docker/nginx/default.conf` 与 `docker/frontend.Dockerfile`：两套产物分目录。
- 不新增任何依赖（用 `--mode` 而不是 `cross-env`）。
