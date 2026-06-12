#!/bin/bash
# edu-companion 关机脚本（后端 + 认证网关 + 前端 + Nginx）
# 用法: ./shutdown.sh

set -e

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
NGINX_DIR="$PROJECT_DIR/nginx"
NGINX_BIN="${NGINX_BIN:-/usr/sbin/nginx}"

# 停止 Nginx
stop_nginx() {
  if [ -f "$NGINX_DIR/nginx.pid" ]; then
    local npid
    npid=$(cat "$NGINX_DIR/nginx.pid" 2>/dev/null)
    if [ -n "$npid" ] && kill -0 "$npid" 2>/dev/null; then
      echo "🟡 停止 Nginx (pid: $npid)..."
      $NGINX_BIN -c "$NGINX_DIR/nginx.conf" -p "$NGINX_DIR" -s quit 2>/dev/null || kill "$npid" 2>/dev/null || true
      sleep 1
    fi
  fi
  fuser -k 8080/tcp 2>/dev/null || true
  echo "✅ Nginx 已关闭"
}

# 停止 uvicorn 进程
kill_uvicorn() {
  local port="$1" label="$2" pattern="$3"
  local pids
  pids=$(pgrep -f "$pattern" 2>/dev/null || true)
  if [ -z "$pids" ]; then
    pids=$(lsof -ti:"$port" 2>/dev/null || true)
  fi
  if [ -n "$pids" ]; then
    echo "🟡 停止 $label (pid: $(echo "$pids" | tr '\n' ' '))..."
    kill "$pids" 2>/dev/null || true
    sleep 1
    pids=$(pgrep -f "$pattern" 2>/dev/null || true)
    if [ -n "$pids" ]; then
      echo "🔴 $label 未响应 SIGTERM，强制关闭..."
      kill -9 "$pids" 2>/dev/null || true
    fi
  fi
  fuser -k "${port}/tcp" 2>/dev/null || true
  echo "✅ $label 已关闭"
}

stop_nginx
kill_uvicorn 8000  "后端"         "uvicorn app.main"
kill_uvicorn 18001 "认证网关"     "uvicorn auth_app.main"
kill_uvicorn 3000  "前端"         "next start"
kill_uvicorn 3001  "admin 前端"   "next.*3001"
kill_uvicorn 8001  "admin 后端"   "app_admin.main"

echo ""
echo "🎯 全部已关闭"
