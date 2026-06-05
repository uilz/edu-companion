#!/usr/bin/env bash
# 认证网关停止脚本
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

PID_FILE="logs/auth_gateway.pid"

if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE")
    if kill -0 "$PID" 2>/dev/null; then
        echo "🛑 停止认证网关 (PID: $PID)..."
        kill "$PID"
        rm -f "$PID_FILE"
        echo "✅ 认证网关已停止"
    else
        echo "⚠️  进程 $PID 不存在，清理 PID 文件"
        rm -f "$PID_FILE"
    fi
else
    echo "ℹ️  未找到运行中的认证网关"
fi
