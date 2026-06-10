#!/bin/bash
# rebuild.sh — 关闭 → 构建前端 → 启动认证网关 → 重启前后端
# 用法: bash rebuild.sh

set -e

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
LOG_DIR="$PROJECT_DIR/logs"

mkdir -p "$LOG_DIR"

# ---------- 轮询等待函数（每1秒检查一次，最多等15秒）----------
wait_for_url() {
  local url="$1"
  local timeout="${2:-15}"   # 默认超时15秒
  local interval="${3:-1}"   # 默认间隔1秒
  local start_time
  start_time=$(date +%s)
  while true; do
    if curl -s -o /dev/null "$url" 2>/dev/null; then
      return 0
    fi
    if [ $(($(date +%s) - start_time)) -ge "$timeout" ]; then
      return 1
    fi
    sleep "$interval"
  done
}

echo "[$TIMESTAMP] 🛑 关闭旧进程..."
fuser -k 8000/tcp 2>/dev/null || true
fuser -k 8001/tcp 2>/dev/null || true
fuser -k 3000/tcp 2>/dev/null || true
fuser -k 3001/tcp 2>/dev/null || true
sleep 1
echo "[$TIMESTAMP] ✅ 端口已释放"

echo "[$TIMESTAMP] 🔍 检查后端语法..."
cd "$PROJECT_DIR/backend"
python3 -c "
import ast, os
errors = []
checked = 0
for root, dirs, files in os.walk('.'):
    for f in files:
        if f.endswith('.py') and '__pycache__' not in root and '.venv' not in root and 'venv' not in root:
            fp = os.path.join(root, f)
            try:
                ast.parse(open(fp, 'rb').read().decode('utf-8'))
                checked += 1
            except UnicodeDecodeError:
                continue
            except SyntaxError as e:
                errors.append(f'{fp}: {e}')
if errors:
    print('Syntax errors:')
    for e in errors[:5]:
        print(f'  {e}')
    exit(1)
print(f'Checked {checked} Python files, all OK')
" 2>&1 || { echo "[$TIMESTAMP] 🔴 后端语法检查失败"; exit 1; }
echo "[$TIMESTAMP] ✅ 后端语法检查通过"

echo "[$TIMESTAMP] 🔍 检查认证网关语法..."
cd "$PROJECT_DIR/auth-gateway"
python3 -c "
import ast, os
errors = []
checked = 0
for root, dirs, files in os.walk('.'):
    for f in files:
        if f.endswith('.py') and '__pycache__' not in root and 'venv' not in root:
            fp = os.path.join(root, f)
            try:
                ast.parse(open(fp, 'rb').read().decode('utf-8'))
                checked += 1
            except UnicodeDecodeError:
                continue
            except SyntaxError as e:
                errors.append(f'{fp}: {e}')
if errors:
    print('Syntax errors:')
    for e in errors[:5]:
        print(f'  {e}')
    exit(1)
print(f'Checked {checked} Python files, all OK')
" 2>&1 || { echo "[$TIMESTAMP] 🔴 认证网关语法检查失败"; exit 1; }
echo "[$TIMESTAMP] ✅ 认证网关语法检查通过"

echo "[$TIMESTAMP] 🔨 构建前端..."
cd "$PROJECT_DIR/frontend"
NODE_OPTIONS="--max-old-space-size=2048" \
NEXT_TELEMETRY_DISABLED=1 \
NODE_ENV=production \
  npx next build --no-lint 2>&1 | tail -20
echo "[$TIMESTAMP] ✅ 构建完成"

echo "[$TIMESTAMP] 🚀 启动认证网关 (uvicorn @ :18001)..."
cd "$PROJECT_DIR/auth-gateway"
BACKEND_VENV="$PROJECT_DIR/backend/venv"
if [ ! -d "$BACKEND_VENV" ]; then
    echo "[$TIMESTAMP] 🔴 后端 venv 不存在，请先运行后端初始化"
    exit 1
fi
"$BACKEND_VENV/bin/python" -m uvicorn auth_app.main:app \
  --host 0.0.0.0 --port 18001 \
  >> "$LOG_DIR/auth_gateway_$TIMESTAMP.log" 2>&1 &
disown

if wait_for_url "http://127.0.0.1:18001/health"; then
  echo "[$TIMESTAMP] ✅ 认证网关已就绪"
else
  echo "[$TIMESTAMP] 🔴 认证网关启动异常，最近日志:"
  tail -10 "$LOG_DIR/auth_gateway_$TIMESTAMP.log"
fi

echo "[$TIMESTAMP] 🚀 启动后端 (uvicorn @ :8000)..."
cd "$PROJECT_DIR/backend"
venv/bin/python -m uvicorn app.main:app \
  --host 0.0.0.0 --port 8000 \
  >> "$LOG_DIR/backend_$TIMESTAMP.log" 2>&1 &
disown

if wait_for_url "http://127.0.0.1:8000/docs"; then
  echo "[$TIMESTAMP] ✅ 后端已就绪"
else
  echo "[$TIMESTAMP] 🔴 后端启动异常，最近日志:"
  tail -5 "$LOG_DIR/backend_$TIMESTAMP.log"
fi

echo "[$TIMESTAMP] 🚀 启动前端 (Next.js @ :3000)..."
cd "$PROJECT_DIR/frontend"
npx next start -p 3000 \
  > "$LOG_DIR/frontend_$TIMESTAMP.log" 2>&1 &
disown

if wait_for_url "http://127.0.0.1:3000/"; then
  echo "[$TIMESTAMP] ✅ 前端已就绪"
else
  echo "[$TIMESTAMP] 🔴 前端启动异常，最近日志:"
  tail -5 "$LOG_DIR/frontend_$TIMESTAMP.log"
fi

# ---------- admin 后端 (uvicorn @ :8001) ----------
echo "[$TIMESTAMP] 🚀 启动 admin 后端 (uvicorn @ :8001)..."
cd "$PROJECT_DIR/backend"
venv/bin/python -m app_admin.main \
  >> "$LOG_DIR/admin_backend_$TIMESTAMP.log" 2>&1 &
disown

if wait_for_url "http://127.0.0.1:8001/admin/health"; then
  echo "[$TIMESTAMP] ✅ admin 后端已就绪"
else
  echo "[$TIMESTAMP] 🔴 admin 后端启动异常，最近日志:"
  tail -5 "$LOG_DIR/admin_backend_$TIMESTAMP.log"
fi

# ---------- admin 前端 (Next.js @ :3001) ----------
echo "[$TIMESTAMP] 🚀 启动 admin 前端 (Next.js @ :3001)..."
cd "$PROJECT_DIR/admin"
if [ ! -d "node_modules" ]; then
  echo "[$TIMESTAMP] 📦 安装 admin 前端依赖..."
  npm install --no-audit --no-fund --prefer-offline >> "$LOG_DIR/admin_frontend_$TIMESTAMP.log" 2>&1
fi
npx next dev -p 3001 \
  > "$LOG_DIR/admin_frontend_$TIMESTAMP.log" 2>&1 &
disown

if wait_for_url "http://127.0.0.1:3001/"; then
  echo "[$TIMESTAMP] ✅ admin 前端已就绪"
else
  echo "[$TIMESTAMP] 🔴 admin 前端启动异常，最近日志:"
  tail -5 "$LOG_DIR/admin_frontend_$TIMESTAMP.log"
fi

echo "[$TIMESTAMP] 🎯 全部完成"
echo "[$TIMESTAMP] 📊 服务状态:"
echo "  - 认证网关:    http://127.0.0.1:18001  (统一对外入口)"
echo "  - 后端 API:    http://127.0.0.1:8000   (内网，通过网关代理)"
echo "  - 前端:        http://127.0.0.1:3000"
echo "  - admin 后端:  http://127.0.0.1:8001   (仅内网)"
echo "  - admin 前端:  http://127.0.0.1:3001   (仅内网/本机)"