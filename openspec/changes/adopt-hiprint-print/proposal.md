# Proposal

## Why

原设计要自建一个打印代理：自己写 ZPL/TSPL 模板、自己维护工位与打印机的映射、自己起一个常驻服务。这套东西一旦照做，每改一次面单版式就要改代码发版，而且 ZPL 字符串只能在真机上调试。

`vue-plugin-hiprint` 把这两件事都包了：模板用拖拽设计器做，产物是 JSON；静默打印通过 `electron-hiprint` 本地客户端走 socket.io 下发，客户端调 Windows 打印驱动出纸。三万单/天的量级不需要自己造这套基建。

代价是引入一个第三方 Windows 桌面客户端作为生产依赖，这个风险必须显式承担而不是忽略。

## What Changes

- 打印通道从「自建 HTTP 代理 + ZPL 指令」改为「`vue-plugin-hiprint` 前端渲染 + `electron-hiprint` 客户端经 socket.io 下发」。
- 打印模板从代码迁移到后台管理：模板存 JSON，后台可视化编辑，改版式不发版。
- 新增打印任务记录：每张面单/标签的打印结果、失败原因、重打次数落库可查。
- 电子面单以图片形式嵌入模板打印——快递公司返回的是 PDF 或图片，不做解析重排。
- 明确吞吐前提：单台客户端约 0.3–1 秒/张，三万张必须多客户端并行，按打包工位分布。

## Capabilities

### New Capabilities

无。

### Modified Capabilities

- `wms/wave-picking`: 修改「面单与标签由本地代理打印」，把下发通道从自建代理换成 hiprint 客户端，并补上模板集中管理与打印任务留痕这两条既有规格没覆盖的行为。

## Impact

- `docs/design/tech-stack.md` 的 T5 要重写：不再是「自建 FastAPI 代理 + ZPL」。
- `docs/design/data-model.md` 增加打印模板与打印任务两张表。
- `docs/design/ui-map.md` 增加「打印模板」后台页。
- 前端新增依赖 `vue-plugin-hiprint` 与 `socket.io-client`；仓库本地需安装 `electron-hiprint` 客户端（Windows）。
- 不改任何后端接口；打印指令由前端直接下发给客户端。
