#!/usr/bin/env bash
# 认证网关启动脚本
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# 加载环境变量
if [ -f config/.env ]; then
    export $(grep -v '^#' config/.env | xargs)
fi

# 创建虚拟环境（如果不存在）
if [ ! -d "venv" ]; then
    echo "🔧 创建虚拟环境..."
    python3 -m venv venv
fi

# 安装依赖
echo "📦 安装依赖..."
./venv/bin/pip install -r requirements.txt -q

# 创建日志目录
mkdir -p logs

# 启动服务
echo "🚀 启动认证网关 ${AUTH_GATEWAY_HOST}:${AUTH_GATEWAY_PORT}..."
nohup ./venv/bin/uvicorn auth_app.main:app \
    --host "${AUTH_GATEWAY_HOST:-0.0.0.0}" \
    --port "${AUTH_GATEWAY_PORT:-8001}" \
    --workers "${AUTH_GATEWORKERS:-2}" \
    --log-level info \
    > logs/auth_gateway.log 2>&1 &

echo $! > logs/auth_gateway.pid
echo "✅ 认证网关已启动 (PID: $(cat logs/auth_gateway.pid))"
