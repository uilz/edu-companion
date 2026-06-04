#!/bin/bash
# rebuild.sh — 关闭 → 构建前端 → 重启前后端
# 用法: bash rebuild.sh

set -e

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "🛑 关闭旧进程..."
fuser -k 8000/tcp 2>/dev/null || true
fuser -k 3000/tcp 2>/dev/null || true
sleep 1
echo "✅ 端口已释放"

echo "🔨 构建前端..."
cd "$PROJECT_DIR/frontend"
npm run build 2>&1
echo "✅ 构建完成"

echo "🚀 启动后端 (uvicorn @ :8000)..."
cd "$PROJECT_DIR/backend"
nohup venv/bin/python -m uvicorn app.main:app \
  --host 0.0.0.0 --port 8000 \
  > /tmp/backend.log 2>&1 &
sleep 3
if curl -s -o /dev/null -w "" http://127.0.0.1:8000/docs 2>/dev/null; then
  echo "✅ 后端已就绪"
else
  echo "🔴 后端启动异常，检查 /tmp/backend.log"
  tail -5 /tmp/backend.log
fi

echo "🚀 启动前端 (Next.js @ :3000)..."
cd "$PROJECT_DIR/frontend"
nohup npx next start -p 3000 \
  > /tmp/frontend.log 2>&1 &
sleep 5
if curl -s -o /dev/null -w "" http://127.0.0.1:3000/learn 2>/dev/null; then
  echo "✅ 前端已就绪"
else
  echo "🔴 前端启动异常，检查 /tmp/frontend.log"
  tail -5 /tmp/frontend.log
fi

echo "🎯 全部完成"
