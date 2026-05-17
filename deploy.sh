#!/bin/bash
# ========================================
# 智能伴学系统 - 一键更新部署脚本
# 在 edu-server 上运行此脚本即可拉取最新代码并重启服务
# ========================================

set -e

PROJECT_DIR="$HOME/edu-companion"
BRANCH="main"

echo "🔄 智能伴学系统 - 更新部署"
echo "================================"

# 1. 拉取最新代码
echo ""
echo "📥 拉取最新代码..."
cd "$PROJECT_DIR"
git fetch origin
LOCAL=$(git rev-parse HEAD)
REMOTE=$(git rev-parse origin/$BRANCH)

if [ "$LOCAL" = "$REMOTE" ]; then
    echo "   ✅ 已是最新版本"
else
    git pull origin "$BRANCH"
    echo "   ✅ 代码已更新"
fi

# 2. 后端依赖更新（如果 requirements.txt 有变化）
echo ""
echo "📦 检查后端依赖..."
cd "$PROJECT_DIR/backend"
source venv/bin/activate
pip install -r requirements.txt -q 2>/dev/null
echo "   ✅ 后端依赖就绪"

# 3. 前端依赖更新（如果 package.json 有变化）
echo ""
echo "📦 检查前端依赖..."
cd "$PROJECT_DIR/frontend"
npm install --silent 2>/dev/null
echo "   ✅ 前端依赖就绪"

# 4. 重启后端
echo ""
echo "🔄 重启后端..."
# 找到并杀掉旧的后端进程
pkill -f "uvicorn app.main:app" 2>/dev/null || true
sleep 1

cd "$PROJECT_DIR/backend"
source venv/bin/activate
nohup uvicorn app.main:app --host 0.0.0.0 --port 8000 > /tmp/edu-backend.log 2>&1 &
BACKEND_PID=$!
echo "   ✅ 后端已重启 (PID: $BACKEND_PID)"

# 5. 重启前端
echo ""
echo "🔄 重启前端..."
pkill -f "next dev" 2>/dev/null || true
sleep 1

cd "$PROJECT_DIR/frontend"
nohup npm run dev -- -p 3000 > /tmp/edu-frontend.log 2>&1 &
FRONTEND_PID=$!
echo "   ✅ 前端已重启 (PID: $FRONTEND_PID)"

# 6. 等待服务就绪
echo ""
echo "⏳ 等待服务启动..."
sleep 5

# 7. 健康检查
echo ""
echo "================================"
BACKEND_OK=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/ 2>/dev/null)
FRONTEND_OK=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:3000/ 2>/dev/null)

if [ "$BACKEND_OK" = "200" ]; then
    echo "✅ 后端正常  http://$(hostname -I | awk '{print $1}'):8000"
else
    echo "❌ 后端异常  HTTP $BACKEND_OK"
fi

if [ "$FRONTEND_OK" = "200" ]; then
    echo "✅ 前端正常  http://$(hostname -I | awk '{print $1}'):3000"
else
    echo "❌ 前端异常  HTTP $FRONTEND_OK"
fi

echo ""
echo "🎉 部署完成！"
