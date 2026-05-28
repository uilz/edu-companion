#!/bin/bash
# edu-companion 前后端启动脚本
# 用法: ./startup.sh         # 默认: 启动后端+前端
#       ./startup.sh backend  # 只启动后端
#       ./startup.sh frontend # 只启动前端（假设后端已运行）

set -e

START_TARGET="${1:-all}"
PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"

start_backend() {
  # 先释放端口，防 EADDRINUSE
  if lsof -ti:8000 >/dev/null 2>&1; then
    echo "🟡 端口 8000 被占用，先释放..."
    fuser -k 8000/tcp 2>/dev/null || true
    sleep 1
  fi
  echo "🟡 启动后端 (uvicorn @ :8000)..."
  cd "$PROJECT_DIR/backend"
  nohup venv/bin/python -m uvicorn app.main:app \
    --host 0.0.0.0 --port 8000 \
    > /tmp/backend.log 2>&1 &
  local pid=$!
  sleep 3
  if curl -s -o /dev/null -w "" http://127.0.0.1:8000/docs 2>/dev/null; then
    echo "✅ 后端已就绪 (pid: $pid)"
  else
    echo "🔴 后端启动可能有问题，检查 /tmp/backend.log"
    tail -5 /tmp/backend.log
    return 1
  fi
}

start_frontend() {
  # 先释放端口
  if lsof -ti:3000 >/dev/null 2>&1; then
    echo "🟡 端口 3000 被占用，先释放..."
    fuser -k 3000/tcp 2>/dev/null || true
    sleep 1
  fi
  echo "🟡 启动前端 (Next.js @ :3000)..."
  cd "$PROJECT_DIR/frontend"
  nohup npx next start -p 3000 \
    > /tmp/frontend.log 2>&1 &
  local pid=$!
  sleep 5
  if curl -s -o /dev/null -w "" http://127.0.0.1:3000/learn 2>/dev/null; then
    echo "✅ 前端已就绪 (pid: $pid)"
  else
    echo "🔴 前端启动可能有问题，检查 /tmp/frontend.log"
    tail -5 /tmp/frontend.log
    return 1
  fi
}

case "$START_TARGET" in
  all)
    start_backend
    start_frontend
    echo "🎯 前后端均已启动"
    ;;
  backend)
    start_backend
    echo "🎯 后端已启动"
    ;;
  frontend)
    start_frontend
    echo "🎯 前端已启动"
    ;;
  *)
    echo "用法: $0 {all|backend|frontend}"
    exit 1
    ;;
esac
