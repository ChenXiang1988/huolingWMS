"""导出货主侧接口的 OpenAPI 文档。

只保留两类路径：
- `/portal/`  货主自助端（建预报、建订单、查库存）
- `/open/v1/` 系统对接（推送预报与订单、回传库存）

后台作业接口不对外，进这份文档只会让对接方误以为可用。

业务路由挂在 lifespan 里注册，进程外拿不到 `app.openapi()`，
所以从运行中的服务取 `/openapi.json`。先起后端再跑本脚本：
`uvicorn src.main:app --port 8000`，然后 `python scripts/export_openapi_owner.py`。
"""

import json
import sys
from pathlib import Path

import httpx

BASE = "http://127.0.0.1:8000"
KEEP_MARKERS = ("/portal/", "/open/v1/")


def main() -> None:
    target = (
        Path(sys.argv[1])
        if len(sys.argv) > 1
        else Path(__file__).resolve().parents[2] / "docs" / "api" / "openapi-owner.json"
    )

    try:
        raw = httpx.get(f"{BASE}/openapi.json", timeout=30)
        raw.raise_for_status()
    except httpx.HTTPError as exc:
        raise SystemExit(f"取不到 {BASE}/openapi.json，先把后端跑起来：{exc}") from exc

    schema = raw.json()
    paths = {
        path: item
        for path, item in schema["paths"].items()
        if any(marker in path for marker in KEEP_MARKERS)
    }
    if not paths:
        raise SystemExit("没筛出任何货主侧路径，检查路由前缀是否变化")

    owner_schema = {
        "openapi": schema["openapi"],
        "info": {
            "title": "货灵 WMS 货主接口",
            "version": schema["info"]["version"],
            "description": "货主自助端与系统对接使用的接口。管理后台接口不在本文档范围内。",
        },
        "paths": dict(sorted(paths.items())),
        "components": schema.get("components", {}),
    }

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(owner_schema, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # 回读一次，结构不合法就别声称导出成功
    parsed = json.loads(target.read_text(encoding="utf-8"))
    ops = sum(len(item) for item in parsed["paths"].values())
    print(f"written: {target}")
    print(f"paths={len(parsed['paths'])} operations={ops}")
    for path in parsed["paths"]:
        print(f"  {path}")


if __name__ == "__main__":
    main()
