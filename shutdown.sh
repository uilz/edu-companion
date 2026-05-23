#!/bin/bash
# edu-companion 前后端关机脚本
# 用法: ./shutdown.sh         # 默认: 关后端+前端
#       ./shutdown.sh backend  # 只关后端
#       ./shutdown.sh frontend # 只关前端

set -e

SHUTDOWN_TARGET="${1:-all}"

kill_python_backend() {
  local pids
  pids=$(pgrep -f "uvicorn app.main" 2>/dev/null || true)
  if [ -n "$pids" ]; then
    echo "🟡 关闭后端 (pid: $pids)..."
    kill "$pids" 2>/dev/null || true
    sleep 1
    # 确认已关闭
    pids=$(pgrep -f "uvicorn app.main" 2>/dev/null || true)
    if [ -n "$pids" ]; then
      echo "🔴 后端未响应 SIGTERM，强制关闭..."
      kill -9 "$pids" 2>/dev/null || true
    fi
  fi
  # 二次确认
  if pgrep -f "uvicorn app.main" >/dev/null 2>&1; then
    echo "🔴 后端仍活着!"
    return 1
  fi
  echo "✅ 后端已关闭"
}

kill_nextjs_frontend() {
  local pids
  pids=$(pgrep -f "next-server" 2>/dev/null || true)
  if [ -z "$pids" ]; then
    pids=$(pgrep -f "next start" 2>/dev/null || true)
  fi
  if [ -n "$pids" ]; then
    echo "🟡 关闭前端 (pid: $pids)..."
    kill "$pids" 2>/dev/null || true
    sleep 1
    pids=$(pgrep -f "next-server" 2>/dev/null || true)
    if [ -z "$pids" ]; then
      pids=$(pgrep -f "next start" 2>/dev/null || true)
    fi
    if [ -n "$pids" ]; then
      echo "🔴 前端未响应 SIGTERM，强制关闭..."
      kill -9 "$pids" 2>/dev/null || true
    fi
  fi
  if pgrep -f "next-server" >/dev/null 2>&1 || pgrep -f "next start" >/dev/null 2>&1; then
    echo "🔴 前端仍活着!"
    return 1
  fi
  echo "✅ 前端已关闭"
}

case "$SHUTDOWN_TARGET" in
  all)
    kill_python_backend
    kill_nextjs_frontend
    echo "🎯 前后端均已关闭"
    ;;
  backend)
    kill_python_backend
    echo "🎯 后端已关闭"
    ;;
  frontend)
    kill_nextjs_frontend
    echo "🎯 前端已关闭"
    ;;
  *)
    echo "用法: $0 {all|backend|frontend}"
    exit 1
    ;;
esac
