#!/usr/bin/env bash
# 认证网关启动脚本
# 复用后端 venv（symlink: venv → ../backend/venv），节省磁盘空间
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# 加载环境变量
if [ -f config/.env ]; then
    export $(grep -v '^#' config/.env | xargs)
fi

# 检查 venv（优先使用后端 venv）
if [ -L "venv" ] && [ -d "$(readlink venv)" ]; then
    VENV_DIR="$(readlink -f venv)"
    echo "ℹ️  复用后端 venv: $VENV_DIR"
elif [ -d "../backend/venv" ]; then
    echo "ℹ️  链接到后端 venv..."
    ln -sf ../backend/venv venv
    VENV_DIR="$(readlink -f venv)"
else
    echo "🔧 未找到后端 venv，创建独立虚拟环境..."
    python3 -m venv venv
    VENV_DIR="venv"
fi

# 确保依赖已安装
if ! "$VENV_DIR/bin/pip" list 2>/dev/null | grep -q "fastapi"; then
    echo "📦 安装认证网关依赖..."
    "$VENV_DIR/bin/pip" install -r requirements.txt -q
fi

# 创建日志目录
mkdir -p logs

# 启动服务
HOST="${AUTH_GATEWAY_HOST:-0.0.0.0}"
PORT="${AUTH_GATEWAY_PORT:-18001}"
echo "🚀 启动认证网关 ${HOST}:${PORT}..."
nohup "$VENV_DIR/bin/python" -m uvicorn auth_app.main:app \
    --host "$HOST" \
    --port "$PORT" \
    --workers "${AUTH_GATEWORKERS:-2}" \
    --log-level info \
    > logs/auth_gateway.log 2>&1 &

echo $! > logs/auth_gateway.pid
echo "✅ 认证网关已启动 (PID: $(cat logs/auth_gateway.pid))"
