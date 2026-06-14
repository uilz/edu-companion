#!/bin/bash
# rebuild.sh — 关闭 → 构建前端 → 启动所有服务 → 启动 Nginx
# 用法: bash rebuild.sh [--skip-build] [--skip-admin]
#
# 环境配置文件约定（详见 README）:
#   backend/config/.env
#   auth-gateway/config/.env
#   frontend/config/.env

set -e

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
NGINX_DIR="$PROJECT_DIR/nginx"
NGINX_BIN="${NGINX_BIN:-/usr/sbin/nginx}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
LOG_DIR="$PROJECT_DIR/logs"
SKIP_BUILD=false
SKIP_ADMIN=false

for arg in "$@"; do
  case "$arg" in
    --skip-build) SKIP_BUILD=true ;;
    --skip-admin) SKIP_ADMIN=true ;;
  esac
done

mkdir -p "$LOG_DIR"

# ---------- 工具函数 ----------
wait_for_url() {
  local url="$1" label="$2" timeout="${3:-20}"
  local start_time
  start_time=$(date +%s)
  while true; do
    if curl -s -o /dev/null "$url" 2>/dev/null; then
      echo "[$TIMESTAMP] ✅ $label 已就绪"
      return 0
    fi
    if [ $(($(date +%s) - start_time)) -ge "$timeout" ]; then
      echo "[$TIMESTAMP] 🔴 $label 超时 ($timeout秒)"
      return 1
    fi
    sleep 1
  done
}

stop_nginx() {
  if [ -f "$NGINX_DIR/nginx.pid" ]; then
    local npid
    npid=$(cat "$NGINX_DIR/nginx.pid" 2>/dev/null)
    if [ -n "$npid" ] && kill -0 "$npid" 2>/dev/null; then
      echo "[$TIMESTAMP] 🛑 停止 Nginx (pid: $npid)..."
      $NGINX_BIN -c "$NGINX_DIR/nginx.conf" -p "$NGINX_DIR" -s quit 2>/dev/null || kill "$npid" 2>/dev/null || true
      sleep 1
    fi
  fi
}

start_nginx() {
  echo "[$TIMESTAMP] 🚀 启动 Nginx 统一网关 (:8080)..."
  stop_nginx
  # 确保 nginx 默认日志目录可写
  mkdir -p /var/log/nginx 2>/dev/null || true
  rm -f /var/log/nginx/error.log /var/log/nginx/access.log 2>/dev/null || true
  $NGINX_BIN -c "$NGINX_DIR/nginx.conf" -p "$NGINX_DIR" 2>&1
  wait_for_url "http://127.0.0.1:8080/health" "Nginx"
}

check_env_file() {
  local path="$1" name="$2"
  if [ ! -f "$path" ]; then
    local example="${path%.env}.env.example"
    if [ -f "$example" ]; then
      echo "[$TIMESTAMP] ⚠️  $name 未配置，复制模板..."
      cp "$example" "$path"
    else
      echo "[$TIMESTAMP] 🔴 $name 不存在 ($path)，请先配置"
      return 1
    fi
  fi
}

# ========================================
# 0. 检查环境配置文件
# ========================================
echo "[$TIMESTAMP] 🔍 检查环境配置文件..."
check_env_file "$PROJECT_DIR/backend/config/.env" "后端配置" || true
check_env_file "$PROJECT_DIR/auth-gateway/config/.env" "认证网关配置" || true
check_env_file "$PROJECT_DIR/frontend/config/.env" "前端配置" || true

# ========================================
# 1. 停止所有服务
# ========================================
echo "[$TIMESTAMP] 🛑 关闭所有服务..."
for port in 8000 8001 3000 3001 8080 18001; do
  fuser -k "${port}/tcp" 2>/dev/null || true
done
stop_nginx
sleep 1
echo "[$TIMESTAMP] ✅ 端口已释放"

# ========================================
# 2. 语法检查
# ========================================
echo "[$TIMESTAMP] 🔍 检查 Python 语法..."
for dir in "backend" "auth-gateway"; do
  cd "$PROJECT_DIR/$dir"
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
            except (UnicodeDecodeError, SyntaxError) as e:
                errors.append(f'{fp}: {e}')
if errors:
    print('Syntax errors in $dir:')
    for e in errors[:5]:
        print(f'  {e}')
    exit(1)
print(f'  $dir: {checked} files OK')
" 2>&1
done
echo "[$TIMESTAMP] ✅ Python 语法检查通过"

# ========================================
# 3. 构建前端
# ========================================
if [ "$SKIP_BUILD" = false ]; then
  echo "[$TIMESTAMP] 🔨 构建前端..."
  cd "$PROJECT_DIR/frontend"
  if [ ! -d "node_modules" ]; then
    echo "[$TIMESTAMP] 📦 安装前端依赖..."
    npm install --no-audit --no-fund --prefer-offline 2>&1
  fi
  NODE_OPTIONS="--max-old-space-size=2048" \
  NEXT_TELEMETRY_DISABLED=1 \
  NODE_ENV=production \
    npx next build --no-lint 2>&1 | tail -20
  echo "[$TIMESTAMP] ✅ 前端构建完成"
else
  echo "[$TIMESTAMP] ⏭️ 跳过前端构建"
fi

# ========================================
# 4. 启动认证网关 (:18001)
# ========================================
echo "[$TIMESTAMP] 🚀 启动认证网关 (uvicorn @ :18001)..."
cd "$PROJECT_DIR/auth-gateway"
nohup "$PROJECT_DIR/backend/venv/bin/python" -m uvicorn auth_app.main:app \
  --host 0.0.0.0 --port 18001 \
  > "$LOG_DIR/auth_gateway_$TIMESTAMP.log" 2>&1 &
echo $! > "$LOG_DIR/auth_gateway.pid"
wait_for_url "http://127.0.0.1:18001/health" "认证网关"

# ========================================
# 5. 启动后端 (:8000)
# ========================================
echo "[$TIMESTAMP] 🚀 启动后端 (uvicorn @ :8000)..."
cd "$PROJECT_DIR/backend"
# 导出 config/.env 到环境变量（供 os.getenv 读取，如 JWT_SECRET）
set -a
source "$PROJECT_DIR/backend/config/.env"
set +a
nohup venv/bin/python -m uvicorn app.main:app \
  --host 0.0.0.0 --port 8000 \
  > "$LOG_DIR/backend_$TIMESTAMP.log" 2>&1 &
echo $! > "$LOG_DIR/backend.pid"
wait_for_url "http://127.0.0.1:8000/docs" "后端"

# ========================================
# 6. 启动前端 (:3000)
# ========================================
echo "[$TIMESTAMP] 🚀 启动前端 (Next.js @ :3000)..."
cd "$PROJECT_DIR/frontend"
nohup npx next start -p 3000 \
  > "$LOG_DIR/frontend_$TIMESTAMP.log" 2>&1 &
echo $! > "$LOG_DIR/frontend.pid"
wait_for_url "http://127.0.0.1:3000/" "前端"

# ========================================
# 7. 启动 Nginx (:8080)
# ========================================
start_nginx

# ========================================
# 8. 启动 admin 后端 (:8001，可选)
# ========================================
if [ "$SKIP_ADMIN" = false ]; then
  echo "[$TIMESTAMP] 🚀 启动 admin 后端 (uvicorn @ :8001)..."
  cd "$PROJECT_DIR/backend"
  nohup venv/bin/python -m app_admin.main \
    > "$LOG_DIR/admin_backend_$TIMESTAMP.log" 2>&1 &
  echo $! > "$LOG_DIR/admin_backend.pid"
  wait_for_url "http://127.0.0.1:8001/admin/health" "admin 后端"

  # admin 前端 (:3001，如果存在)
  if [ -d "$PROJECT_DIR/admin" ]; then
    cd "$PROJECT_DIR/admin"
    if [ ! -d "node_modules" ]; then
      echo "[$TIMESTAMP] 📦 安装 admin 前端依赖..."
      npm install --no-audit --no-fund --prefer-offline > "$LOG_DIR/admin_frontend_$TIMESTAMP.log" 2>&1
    fi
    nohup npx next dev -p 3001 \
      > "$LOG_DIR/admin_frontend_$TIMESTAMP.log" 2>&1 &
    echo $! > "$LOG_DIR/admin_frontend.pid"
    wait_for_url "http://127.0.0.1:3001/" "admin 前端"
  fi
fi

# ========================================
# 9. 完成
# ========================================
echo ""
echo "[$TIMESTAMP] 🎯 全部完成"
echo "[$TIMESTAMP] 📊 服务状态:"
echo "  - Nginx 网关:     http://127.0.0.1:8080  (统一对外入口)"
echo "  - 认证网关:       http://127.0.0.1:18001"
echo "  - 后端 API:       http://127.0.0.1:8000"
echo "  - 前端:           http://127.0.0.1:3000"
echo "  - admin 后端:     http://127.0.0.1:8001"
if [ -d "$PROJECT_DIR/admin" ]; then
  echo "  - admin 前端:     http://127.0.0.1:3001"
fi
echo "[$TIMESTAMP] 📌 访问入口: http://<server-ip>:8080"
echo "[$TIMESTAMP] 📝 日志目录: $LOG_DIR"
