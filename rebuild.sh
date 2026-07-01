#!/bin/bash
# rebuild.sh — 关闭 → 构建前端 → 启动所有服务 → 启动 Nginx
# 用法: bash rebuild.sh [--skip-build] [--skip-admin] [--sync-db]
# 要求：所有服务（包括 Nginx）必须在当前用户下运行，不能有 root 进程占用端口。
set -e

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
NGINX_DIR="$PROJECT_DIR/nginx"
NGINX_BIN="${NGINX_BIN:-/usr/sbin/nginx}"
LOG_DIR="$PROJECT_DIR/logs"
SKIP_BUILD=false
SKIP_ADMIN=false
SYNC_DB=false

for arg; do
  case $arg in
    --skip-build) SKIP_BUILD=true ;;
    --skip-admin) SKIP_ADMIN=true ;;
    --sync-db)    SYNC_DB=true ;;
  esac
done
mkdir -p "$LOG_DIR"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# ---------- 工具函数 ----------
log() { echo "[$(date +%Y%m%d_%H%M%S)] $*"; }

# ---------- 互斥锁 & 冷却间隔 ----------
LOCK_FILE="$PROJECT_DIR/.rebuild.lock"
LAST_RUN_FILE="$PROJECT_DIR/.rebuild.last_run"
COOLDOWN=30

# 阻塞获取排他锁（flock 是内核级文件锁，进程退出自动释放）
exec 9>"$LOCK_FILE"
log "🔒 等待 rebuild 锁（若有其他 rebuild 正在执行则排队）..."
flock 9 || { log "❌ 获取锁失败"; exit 1; }
log "🔒 已获取 rebuild 锁"

# 冷却间隔：距离上次 rebuild 完成至少间隔 COOLDOWN 秒
if [ -f "$LAST_RUN_FILE" ]; then
  last_run=$(cat "$LAST_RUN_FILE")
  now=$(date +%s)
  elapsed=$(( now - last_run ))
  if [ "$elapsed" -lt "$COOLDOWN" ]; then
    wait_time=$(( COOLDOWN - elapsed ))
    log "⏳ 距离上次 rebuild 仅 ${elapsed}s，等待 ${wait_time}s 冷却..."
    sleep "$wait_time"
  fi
fi

# 退出时记录完成时间并释放锁
_cleanup() {
  date +%s > "$LAST_RUN_FILE"
  flock -u 9 2>/dev/null || true
}
trap _cleanup EXIT

wait_for_url() {
  local url="$1" label="$2" timeout="${3:-20}" start end
  start=$(date +%s)
  while true; do
    if curl -s -o /dev/null -m 1 "$url" 2>/dev/null; then
      log "✅ $label 已就绪"
      return 0
    fi
    end=$(date +%s)
    if (( end - start >= timeout )); then
      log "🔴 $label 超时 (${timeout}s)"
      return 1
    fi
    sleep 1
  done
}

# 可靠地停止端口占用进程：fuser -k 杀全部 → 等待释放 → 验证
# 用 ss 替代 lsof 检测端口（lsof 间歇性漏检测）
_port_used() { ss -tlnp "sport = :$1" 2>/dev/null | grep -q ":$1"; }

stop_port() {
  local port=$1 timeout=${2:-5} waited=0

  if ! _port_used "$port"; then
    log "⏭️  端口 :$port 已空闲"
    return 0
  fi

  log "🛑 停止端口 :$port ..."

  # fuser -k 杀掉所有占用该端口的进程（含父子进程树）
  fuser -k "${port}/tcp" 2>/dev/null || true

  # 等待端口释放（最多 timeout 秒）
  while _port_used "$port" && [ $waited -lt $timeout ]; do
    sleep 1
    waited=$((waited + 1))
  done

  # 超时仍占用 → 补 SIGKILL
  if _port_used "$port"; then
    local leftover
    leftover=$(fuser "${port}/tcp" 2>/dev/null | awk '{print $NF}')
    log "⚡ 端口 :$port 残留进程，SIGKILL..."
    kill -KILL "$leftover" 2>/dev/null || true
    sleep 1
  fi

  # 验证
  if _port_used "$port"; then
    log "❌ 端口 :$port 仍被占用，可能需要手动处理"
    log "   执行: fuser -k ${port}/tcp"
    return 1
  fi
  log "✅ 端口 :$port 已释放"
}

# 检查端口是否被占用（ss 直接从内核 socket 表读取，比 lsof 可靠）
_port_in_use() { _port_used 8080; }

# 检测端口进程是否为 root 所有
_port_owned_by_root() {
  local port=$1 pid
  pid=$(ss -tlnp "sport = :$port" 2>/dev/null | grep -oP 'pid=\K[0-9]+' | head -1)
  [ -z "$pid" ] && return 1
  [ "$(stat -c %u "/proc/$pid" 2>/dev/null)" = "0" ]
}

# 停止 Nginx：尽可能清理，若端口被 root 占用则报错退出
stop_nginx() {
  local pid_file="$NGINX_DIR/nginx.pid"

  # 1. 优雅关闭
  if [ -x "$NGINX_BIN" ] && [ -f "$pid_file" ]; then
    log "🛑 优雅停止 Nginx (nginx -s quit)..."
    "$NGINX_BIN" -s quit -c "$NGINX_DIR/nginx.conf" -p "$NGINX_DIR" 2>/dev/null
    sleep 2
  fi

  # 2. 强制终止 PID 文件中记录的进程
  if [ -f "$pid_file" ]; then
    local npid=$(cat "$pid_file" 2>/dev/null)
    if [ -n "$npid" ] && [ -d "/proc/$npid" ]; then
      log "⚡ 强制终止 Nginx PID $npid (SIGTERM)..."
      kill -TERM "$npid" 2>/dev/null && sleep 1
      # 等不到就 SIGKILL
      [ -d "/proc/$npid" ] && kill -KILL "$npid" 2>/dev/null && sleep 1
    fi
    rm -f "$pid_file"
  fi

  # 3. 暴力清端口（fuser 杀所有占用 8080 的进程，无视 PID 文件）
  if _port_in_use; then
    log "⚡ 暴力释放 8080 端口 (fuser -k)..."
    fuser -k 8080/tcp 2>/dev/null || true
    sleep 1
  fi

  # 4. 最终确认
  if _port_in_use; then
    if _port_owned_by_root 8080; then
      log "❌ 端口 8080 被 root 进程占用，当前用户无权终止"
      log "   这是系统自带的 nginx 服务，请先执行:"
      log "     sudo systemctl disable nginx   # 禁止开机自启"
      log "     sudo systemctl stop nginx       # 立即停止"
      log "   然后再运行本脚本"
    else
      log "❌ 端口 8080 仍被占用，停止失败"
      log "   请手动执行: sudo fuser -k 8080/tcp"
    fi
    return 1
  else
    log "✅ Nginx 已停止"
    return 0
  fi
}

start_nginx() {
  log "🚀 启动 Nginx 统一网关 (:8080)..."

  # 若端口仍被占用则先停止（_stop_all_ports 已停过一次，但可能被其他进程抢占）
  if _port_in_use; then
    stop_nginx || return 1
  fi

  # 确保 Nginx 工作目录存在且可写（日志、pid）
  mkdir -p "$NGINX_DIR/logs"

  # 以当前用户启动（无需 root）；-g 覆盖默认错误日志路径
  # nginx 编译期默认 error_log /var/log/nginx/error.log 的 alert 无法消除（发生在 -g 解析前），
  # 重定向 stderr 到项目日志避免刷终端
  "$NGINX_BIN" -c "$NGINX_DIR/nginx.conf" -p "$NGINX_DIR" \
    -g "error_log $NGINX_DIR/logs/nginx_error.log;" \
    2>>"$NGINX_DIR/logs/nginx_stderr.log"
  sleep 1
  wait_for_url "http://127.0.0.1:8080/" "Nginx"
}

check_env_file() {
  local path="$1" name="$2"
  if [ ! -f "$path" ]; then
    local example="${path%.env}.env.example"
    if [ -f "$example" ]; then
      log "⚠️  $name 未配置，复制模板..."
      cp "$example" "$path"
    else
      log "🔴 $name 不存在 ($path)，请先配置"
      return 1
    fi
  fi
}

start_service() {
  local name="$1" dir="$2" cmd="$3" port="$4" health="$5" timeout="${6:-20}"
  local log_file="$LOG_DIR/${name}_${TIMESTAMP}.log"
  local pid_file="$LOG_DIR/${name}.pid"

  log "🚀 启动 $name (:${port})..."
  cd "$dir"
  nohup bash -c "exec 9>&-; $cmd" > "$log_file" 2>&1 &
  echo $! > "$pid_file"
  wait_for_url "http://127.0.0.1:${port}${health}" "$name" "$timeout"
}

# ========================================
# 主流程
# ========================================

log "🔍 检查环境配置文件..."
check_env_file "$PROJECT_DIR/backend/config/.env" "后端配置" || true
check_env_file "$PROJECT_DIR/auth-gateway/config/.env" "认证网关配置" || true
check_env_file "$PROJECT_DIR/frontend/config/.env" "前端配置" || true

_stop_all_ports() {
  local failed=0
  for port in 8000 8001 3000 3001 18001; do
    stop_port "$port" 5 || failed=1
  done
  # 8080 用 stop_nginx 替代 stop_port（更可靠的检测方式）
  stop_nginx || failed=1
  return $failed
}

log "🛑 关闭所有服务..."
_stop_all_ports || log "⚠️  部分端口释放失败，可能仍有残留进程"
# 此时若 8080 被 root 进程占用，允许继续，但在 start_nginx 时会严肃处理
sleep 1
log "✅ 端口已释放"

log "🔍 检查 Python 语法..."
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
                errors.append(fp + ': ' + str(e))
if errors:
    print('Syntax errors in $dir:')
    for e in errors[:5]:
        print(e)
    exit(1)
print('  $dir: ' + str(checked) + ' files OK')
" 2>&1
done
log "✅ Python 语法检查通过"

# ---------- 构建前端 ----------
if [ "$SKIP_BUILD" = false ]; then
  log "🔨 构建前端..."
  cd "$PROJECT_DIR/frontend"
  [ ! -d "node_modules" ] && log "📦 安装前端依赖..." && npm install --no-audit --no-fund --prefer-offline 2>&1
  NODE_OPTIONS="--max-old-space-size=2048" \
  NEXT_TELEMETRY_DISABLED=1 \
  NODE_ENV=production \
    npx next build --no-lint 2>&1 | tail -20
  log "✅ 前端构建完成"
else
  log "⏭️ 跳过前端构建"
fi

# ---------- 启动服务 ----------
start_service "auth-gateway" "$PROJECT_DIR/auth-gateway" \
  "\"$PROJECT_DIR/backend/venv/bin/python\" -m uvicorn auth_app.main:app --host 0.0.0.0 --port 18001" \
  18001 "/health"

log "📥 加载后端环境变量..."
set -a
source "$PROJECT_DIR/backend/config/.env"
set +a

start_service "backend" "$PROJECT_DIR/backend" \
  "venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8000" \
  8000 "/health" 180

if [ "$SYNC_DB" = true ]; then
  log "🗄️  同步数据库表结构..."
  cd "$PROJECT_DIR"
  source backend/venv/bin/activate
  DB_PASSWORD="$DB_PASSWORD" DB_HOST="$DB_HOST" DB_PORT="$DB_PORT" DB_USER="$DB_USER" DB_NAME="$DB_NAME" \
    python3 scripts/ensure_all_tables.py --import 2>&1 || log "⚠️  同步有非致命警告（可忽略）"
fi

start_service "frontend" "$PROJECT_DIR/frontend" \
  "npx next start -p 3000" \
  3000 "/"

# Nginx 启动（如果端口被 root 占用会直接提示并退出）
start_nginx || { log "❌ Nginx 启动失败，请先释放 8080 端口"; exit 1; }

if [ "$SKIP_ADMIN" = false ]; then
  start_service "admin-backend" "$PROJECT_DIR/backend" \
    "venv/bin/python -m app_admin.main" \
    8001 "/admin/health"

  if [ -d "$PROJECT_DIR/admin" ]; then
    cd "$PROJECT_DIR/admin"
    [ ! -d "node_modules" ] && log "📦 安装 admin 前端依赖..." && npm install --no-audit --no-fund --prefer-offline 2>&1
    start_service "admin-frontend" "$PROJECT_DIR/admin" \
      "npx next dev -p 3001" \
      3001 "/"
  fi
fi

echo ""
log "🎯 全部完成"
log "📊 服务状态:"
echo "  - Nginx 网关:     http://127.0.0.1:8080"
echo "  - 认证网关:       http://127.0.0.1:18001"
echo "  - 后端 API:       http://127.0.0.1:8000"
echo "  - 前端:           http://127.0.0.1:3000"
echo "  - admin 后端:     http://127.0.0.1:8001"
[ -d "$PROJECT_DIR/admin" ] && echo "  - admin 前端:     http://127.0.0.1:3001"
log "📌 访问入口: http://<server-ip>:8080"
log "📝 日志目录: $LOG_DIR"