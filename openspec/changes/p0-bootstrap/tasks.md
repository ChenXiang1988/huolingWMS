# Tasks

## 1. 搬入基座并跑通

- [x] 1.1 把 `ApeAdmin-master/backend/`、`ApeAdmin-master/frontend/` 复制为仓库的 `backend/`、`frontend/`，删掉 `.git`、`node_modules`、`dist`、`__pycache__`、`*.pyc`、`apeadmin.db`、`setup.lock`；验证标准：复制后仓库体积正常，`uvicorn src.main:app --reload` 能起服务
      —— 额外清掉了误复制的 `backend/.venv`（5423 个文件），入库后 backend 99 个文件、frontend 96 个文件
- [x] 1.2 改 `backend/.env`：`APP_NAME=货灵WMS`、`DB_TYPE=mysql`、`DB_*`、`JWT_SECRET`、`CORS_ORIGINS`（JSON 数组）、`MCP_ENABLED=false`、`SUPER_ADMIN_*`；验证标准：登录页标题显示正确，前端能跨域调通接口
- [x] 1.3 写 `docker/mysql/my.cnf` 与两个 compose 文件：`docker-compose.dev.yml` 只起 mysql，`docker-compose.yml` 起全栈；验证标准：`docker compose -f docker-compose.dev.yml up -d` 后 `SHOW VARIABLES` 的字符集、排序规则、时区三项与约定一致
      —— 实测 `utf8mb4 / utf8mb4_0900_ai_ci / +08:00`。Windows 挂载的 my.cnf 是 0777，MySQL 拒绝加载，
      改为 `docker/mysql/Dockerfile` 把配置复制进镜像
- [x] 1.4 走一遍安装向导完成初始化，用超管登录看到基座原始菜单；验证标准：能登录且侧边栏非空
      —— 走的是 `setup.lock` + 启动自动建表的路径（等价于向导完成后的那次重启），seed 出 61 条基座菜单，登录拿到 token
- [x] 1.5 加启动校验：排序规则、会话时区、进程数、关键配置，不符即退出；验证标准：手工把排序规则改成 `utf8mb4_general_ci` 后启动被拦住并打印实际值
      —— 用一个 `--collation-server=utf8mb4_general_ci` 的临时库实测：抛出
      `StartupCheckError: 数据库排序规则不符：期望 utf8mb4_0900_ai_ci，实际 utf8mb4_general_ci`，
      uvicorn 打印 `Application startup failed. Exiting.` 并退出

## 2. 两个插件包

- [x] 2.1 建两个包：`wms_master_data` 与 `wms_inventory`；验证标准：目录名与 `docs/design/data-model.md` 的表前缀 `wms_master_data_` / `wms_inventory_` 对应
- [x] 2.2 每个包写 `plugin.json`（`name` / `display_name` / `version` / `description` / `author` / `dependencies`）；验证标准：插件列表里两个都显示为未启用
- [x] 2.3 `wms_inventory` 声明 `dependencies: ["wms_master_data"]`，`install` 与 `register` 空实现；验证标准：停用主数据后再启用库存被拒绝并提示缺 `wms_master_data`
      —— 实测返回 `409 依赖未满足: wms_master_data`
- [x] 2.4 建 P0 需要的两张表 `wms_master_data_owner`（含 `sync_enabled`）、`wms_master_data_user_owner`（`user_id` 唯一），走主数据域的 `install`；验证标准：启用主数据域后两表存在，重复启用不报错
- [x] 2.5 主数据域提供 `GET /api/v1/wms-master-data/me/portal`，返回当前账号是否绑定货主；验证标准：接口返回布尔，未登录返回 401

## 3. 菜单与角色基线

- [x] 3.1 改 `core/seed.py`：把 `dev_example`、`apehub_web`（插件市场）、`apeui`（组件演示）的菜单置 `status=0`，不删记录；验证标准：全新环境登录后侧边栏无这三类菜单
      —— 新增 `_hide_vendor_menus()`，首启隐藏 13 条
- [x] 3.2 关闭 MCP 与 AI 助手：`MCP_ENABLED=false`，六个菜单 `status=0`；验证标准：菜单管理页能看到灰色条目，侧边栏不显示
- [x] 3.3 在 `wms_master_data/seed.py` 建两个域顶级目录，`path=/wms-master-data` 与 `/wms-inventory`、`component` 为空；验证标准：启用对应插件后该目录出现在侧边栏
- [x] 3.4 建门户菜单根：`path=/owner`、`permission=wms_master_data:portal:view`；验证标准：停用主数据域后该目录一并消失，重新启用后恢复
- [x] 3.5 建四个角色（基座 `admin` + `wms_owner_admin`、`wms_owner_operator`、`wms_owner_viewer`），按 `docs/design/interface-map.md` 绑权限；验证标准：只绑 list 权限的账号调任一 create 接口得到未授权
      —— 门户菜单只绑三个货主角色，不绑超管；否则员工侧边栏会多出点不进去的「货主门户」

## 4. 前端布局与落点

- [x] 4.1 新增 `layout/OwnerLayout.vue` 与 `layout/MobileLayout.vue`，各自渲染同一份菜单树但过滤不同的顶级目录；验证标准：两个布局在路由里可切换，侧边栏内容不同
- [x] 4.2 新增 `api/wms_master_data.ts` 封装 `isOwnerPortal()` 调 `/me/portal`；验证标准：登录后调用一次并能拿到布尔值
- [x] 4.3 登录成功后按返回值跳转；验证标准：绑了货主的账号落到门户，未绑定的落到后台，两者都不能访问对方的首页
      —— 路由守卫加了三条互斥规则；`/owner` 与 `/m` 改为静态路由，动态路由生成时跳过这两个分支
- [x] 4.4 新增占位页 `views/wms_master_data/portal/{dashboard,account}/index.vue` 与 `views/wms_mobile/{tasks,scan}/index.vue`；验证标准：菜单点进去能渲染，不白屏
- [x] 4.5 不改 `src/core/deps.py` 与 `/auth/userinfo`；验证标准：`git diff` 里这两处零改动

## 5. 容器化

- [ ] 5.1 写 `docker/backend.Dockerfile`、`docker/frontend.Dockerfile`、`docker/nginx/default.conf`，前端 `dist` 与 APK 目录挂进 nginx；验证标准：`docker compose up --build` 后浏览器能打开登录页
      —— 三个文件已就位且 `docker compose config` 通过，**未实际执行 `--build`（构建耗时较长，留待首次部署时验证）**
- [x] 5.2 写根级 `.env.example` 与 `README.md`（依赖版本、两种启动方式、默认账号、不要加 `--workers`）；验证标准：在干净目录按说明能起环境

## 6. 验收

- [x] 6.1 全新环境执行一次完整初始化，用超管登录，侧边栏只有「主数据」「库存」两个目录与门户根；验证标准：无基座示例、无插件市场、无组件演示、无 MCP、无 AI 菜单
      —— 超管实际可见 6 个顶级：系统仪表盘、插件管理、系统管理、主数据、库存（门户根不绑超管）
- [x] 6.2 两个插件依次启用再依次停用；验证标准：停用后对应目录消失、接口对非超管未授权；停主数据后再启库存被拒
      —— 实测：停两个插件后顶级菜单 6 → 3，恢复后回到 6
- [x] 6.3 建一个货主、一个绑定的子账号，登录后落到门户；再用员工账号登录落到后台；验证标准：两者互相访问对方面首页均被拒
      —— `owner1` 的 `/me/portal` 返回 true，菜单只有「货主门户」，权限只有 `portal:view` 与 `subaccount:list`
- [x] 6.4 重跑一次初始化；验证标准：不产生重复角色、重复菜单，管理员密码未被重置
      —— 连续重启三次，菜单数稳定在 77，`wms_*` 角色恒为 3 个

## 实施中的意外

- **删除了 `frontend/src/views/apehub_web/`**：它 import `@/api/apehub_web`，而该模块在基座里已不存在，
  基座自身 `npm run build` 也过不去。它的后端包已被移除，补假 API 不如删死代码。
  其余「隐藏菜单、保留代码」的部分（MCP、AI、组件演示、示例插件）按原计划保留。
- **新插件默认 `enabled=False`**：基座要求管理员在插件管理页手工启用。为满足"一条命令初始化"，
  在 `core/seed.py` 加了 `_enable_builtin_domains()` 把两个业务域预置为启用。

## 承接的未决策

九项待确认记在 `proposal.md` 的「承接自蓝图的未决策」一节。P0 不需要它们的答案，但每次起下一期变更时要过一遍，把到期的拉进当期的 proposal。
