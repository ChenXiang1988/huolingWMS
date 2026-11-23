#!/usr/bin/env bash
# 开发数据库的唯一启动入口。
# 不要直接跑 docker compose up -d mysql：那走的是生产 compose（无 3307 映射），
# Recreate 后 backend/.env 指向的 127.0.0.1:3307 会失效。
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

NAME="huoling-mysql"
if docker ps -a --format '{{.Names}}' | grep -qx "$NAME"; then
  BINDINGS="$(docker inspect -f '{{range $p, $c := .HostConfig.PortBindings}}{{$p}} {{end}}' "$NAME" 2>/dev/null || true)"
  case "$BINDINGS" in
    *3307*) ;;
    *)
      echo "已有容器 $NAME 的端口映射不是 3307（当前：${BINDINGS:-无}），拒绝启动。" >&2
      echo "先确认这个容器的用途，处理后再跑本脚本。" >&2
      exit 1
      ;;
  esac
fi

docker compose -f docker-compose.dev.yml up -d "$@"
