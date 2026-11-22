# Tasks

## 1. 两个构建入口

- [x] 1.1 `vite.config.ts` 按 `--mode owner` 切换 base、入口与产物目录；验证标准：`npm run build` 同时产出 `dist/admin` 与 `dist/owner`
- [x] 1.2 新增 `owner/index.html` 与 `src/main-owner.ts`、`src/OwnerApp.vue`；验证标准：门户产物引用 `/owner/assets/*`
- [x] 1.3 补 `scripts/fix-owner-dist.mjs` 把入口拷到 `dist/owner/index.html`；验证标准：构建末尾打印拷贝结果
- [x] 1.4 `package.json` 增加 `dev:owner`、`build:admin`、`build:owner`；验证标准：不引入 `cross-env`

## 2. 两个登录页

- [x] 2.1 新增 `views/login/owner.vue`：货主方视觉、错误就地显示、成功后进 `/dashboard`；验证标准：门户登录页不出现后台元素
- [x] 2.2 后台登录页保持原样，不再承担"判断该去哪个界面"的职责；验证标准：登录后固定进 `/dashboard-monitor`

## 3. 登录即判身份

- [x] 3.1 新增 `POST /wms-master-data/owner-login`：只接受绑定货主且状态启用的账号，返回与基座登录同结构的 token
- [x] 3.2 `before_login` 钩子改为拒绝所有绑定货主的账号，提示走门户
- [x] 3.3 不存在账号与密码错误返回同一提示；验证标准：两种情况的响应体一致

## 4. 路由与守卫

- [x] 4.1 后台路由删除 `/owner` 分支与 `ownerFlag` 重定向逻辑；验证标准：后台守卫里不再有"按身份跳转"
- [x] 4.2 新增 `router/owner.ts`：独立 base `/owner/`，只注册门户页面；验证标准：员工 token 开门户被清会话回登录页
- [x] 4.3 `OwnerLayout` 适配新路径（`/dashboard`、`/account`）；验证标准：侧边栏点击与高亮正确

## 5. 部署与本地验证

- [x] 5.1 `main.py` 把 `frontend_dist_owner` 挂到 `/owner`；验证标准：本地 8000 端口两个入口都能打开
- [x] 5.2 nginx 按 `/admin/` 与 `/owner/` 分别回退到各自 index；验证标准：两条路径都不串
- [x] 5.3 `frontend.Dockerfile` 把两套产物分目录拷入；验证标准：镜像内 `html/admin` 与 `html/owner` 并存

## 6. 验收

- [x] 6.1 货主账号调后台登录接口 → 401 且不签发 token；实测「该账号属于货主方，请从货主门户登录」
- [x] 6.2 员工账号调门户登录接口 → 422；实测「该账号不是货主方账号，请从管理后台登录」
- [x] 6.3 货主账号调门户登录接口 → 200，返回 owner_name 与 is_primary
- [x] 6.4 密码错误与账号不存在返回同一句提示
- [x] 6.5 `/admin/` 与 `/owner/` 分别返回各自入口文件（1163B / 468B）
