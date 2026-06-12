#!/bin/bash
# edu-companion 启动脚本（后端 + 认证网关 + 前端 + Nginx 统一网关）
# 用法: ./startup.sh

set -e

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
NGINX_DIR="$PROJECT_DIR/nginx"
NGINX_BIN="${NGINX_BIN:-/usr/sbin/nginx}"

wait_for() {
  local url="$1" label="$2" timeout="${3:-15}"
  echo "🟡 等待 $label ($url)..."
  for i in $(seq 1 "$timeout"); do
    if curl -s -o /dev/null "$url" 2>/dev/null; then
      echo "✅ $label 已就绪"
      return 0
    fi
    sleep 1
  done
  echo "🔴 $label 超时"
  return 1
}

# 释放端口
for port in 8000 18001 3000 8080; do
  if lsof -ti:"$port" >/dev/null 2>&1; then
    echo "🟡 释放端口 $port..."
    fuser -k "$port/tcp" 2>/dev/null || true
    sleep 1
  fi
done

# 1. 后端
echo "🟡 启动后端 (uvicorn @ :8000)..."
cd "$PROJECT_DIR/backend"
nohup venv/bin/python -m uvicorn app.main:app \
  --host 0.0.0.0 --port 8000 \
  > /tmp/backend.log 2>&1 &
wait_for "http://127.0.0.1:8000/health" "后端"

# 2. 认证网关
echo "🟡 启动认证网关 (uvicorn @ :18001)..."
cd "$PROJECT_DIR/auth-gateway"
nohup ../backend/venv/bin/python -m uvicorn auth_app.main:app \
  --host 0.0.0.0 --port 18001 \
  > /tmp/auth_gateway.log 2>&1 &
wait_for "http://127.0.0.1:18001/health" "认证网关"

# 3. 前端
echo "🟡 启动前端 (Next.js @ :3000)..."
cd "$PROJECT_DIR/frontend"
nohup npx next start -p 3000 \
  > /tmp/frontend.log 2>&1 &
wait_for "http://127.0.0.1:3000/" "前端"

# 4. Nginx 统一网关
echo "🟡 启动 Nginx 统一网关 (:8080)..."
$NGINX_BIN -c "$NGINX_DIR/nginx.conf" -p "$NGINX_DIR" 2>/dev/null
wait_for "http://127.0.0.1:8080/health" "Nginx"

echo ""
echo "🎯 全部启动完成"
echo "   🌐 访问入口: http://<server-ip>:8080"
