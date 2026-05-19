#!/bin/bash
# 智能学习伴侣 — 一键部署脚本
# 用法: ./repull.sh

set -e
PROJECT_DIR="/home/deploy/edu-companion"
cd "$PROJECT_DIR"

echo "📦 拉取最新代码..."
git pull origin main

echo ""
echo "🔧 安装后端依赖..."
cd "$PROJECT_DIR/backend"
source venv/bin/activate 2>/dev/null || true
pip install -r requirements.txt -q

echo ""
echo "🧪 运行后端测试..."
python -m pytest tests/ -x -q --tb=short

echo ""
echo "📦 构建前端..."
cd "$PROJECT_DIR/frontend"
npm install --silent
npm run build

echo ""
echo "🔄 重启服务..."
# 停止旧进程
pkill -f "uvicorn app.main:app" 2>/dev/null || true
pkill -f "node .next/standalone/server.js" 2>/dev/null || true
sleep 1

# 启动后端
cd "$PROJECT_DIR/backend"
nohup python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 > /tmp/edu-backend.log 2>&1 &

# 启动前端 (standalone mode)
cd "$PROJECT_DIR/frontend"
nohup node .next/standalone/server.js > /tmp/edu-frontend.log 2>&1 &

sleep 2

echo ""
echo "🏥 健康检查..."
sleep 2
BACKEND=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/api/conversations/partitions 2>/dev/null || echo "000")
FRONTEND=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:3000/dashboard 2>/dev/null || echo "000")

echo "  后端: HTTP $BACKEND"
echo "  前端: HTTP $FRONTEND"

if [ "$BACKEND" = "200" ] && [ "$FRONTEND" = "200" ]; then
    echo ""
    echo "✅ 部署成功！"
else
    echo ""
    echo "⚠️ 部分服务异常"
fi
