#!/bin/bash
# init.sh — 一键初始化开发环境
# 用法: bash init.sh [--force]
#
# 在全新克隆的仓库中运行，完成：
#   1. 环境依赖检查
#   2. Python 虚拟环境创建 + 依赖安装
#   3. 前端依赖安装
#   4. 环境配置文件初始化（从模板复制）
#   5. 数据库初始化（可选）
#   6. 打印启动说明

set -e

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
FORCE=false
[[ "$1" == "--force" ]] && FORCE=true

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

info()  { echo -e "${BLUE}[INFO]${NC}  $1"; }
ok()    { echo -e "${GREEN}[OK]${NC}    $1"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $1"; }
err()   { echo -e "${RED}[ERR]${NC}   $1"; }

# ========================================
# Step 0: 检查前置依赖
# ========================================
echo ""
echo "========================================"
echo "  苹果果 — 一键初始化"
echo "========================================"
echo ""

check_cmd() {
  if ! command -v "$1" &>/dev/null; then
    err "$1 未安装，请先安装 $1"
    return 1
  fi
  ok "$1 $(command -v "$1")"
}

info "检查前置依赖..."
check_cmd python3
check_cmd node
check_cmd npm
check_cmd psql || warn "psql 未安装，数据库初始化将跳过"
check_cmd fuser || warn "fuser 未安装（重启脚本需要）"
check_cmd curl || warn "curl 未安装（健康检查需要）"

PYTHON_OK=false
python3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)" && PYTHON_OK=true
$PYTHON_OK && ok "Python $(python3 --version 2>&1)" || warn "建议 Python 3.11+（当前: $(python3 --version 2>&1)）"

NODE_OK=false
node -e "process.exit(parseInt(process.version.slice(1)) >= 18 ? 0 : 1)" 2>/dev/null && NODE_OK=true
$NODE_OK && ok "Node $(node --version 2>&1)" || warn "建议 Node.js 18+（当前: $(node --version 2>&1)）"

echo ""

# ========================================
# Step 1: 初始化环境配置文件
# ========================================
info "检查环境配置文件..."

init_env() {
  local env_file="$1" example_file="$2" name="$3"
  if [ -f "$env_file" ]; then
    ok "$name 配置已存在: $env_file"
  elif [ -f "$example_file" ]; then
    cp "$example_file" "$env_file"
    ok "$name 配置已从模板创建: $env_file"
    warn "  请编辑 $env_file 填入实际值（API Key 等）"
  else
    warn "$name 模板文件不存在: $example_file"
  fi
}

init_env "$PROJECT_DIR/backend/config/.env" \
  "$PROJECT_DIR/backend/config/.env.example" "后端"

init_env "$PROJECT_DIR/auth-gateway/config/.env" \
  "$PROJECT_DIR/auth-gateway/config/.env.example" "认证网关"

init_env "$PROJECT_DIR/frontend/config/.env" \
  "$PROJECT_DIR/frontend/config/.env.example" "前端"

# 旧版兼容：根目录 .env（后端之前用）
if [ ! -f "$PROJECT_DIR/backend/.env" ] && [ -f "$PROJECT_DIR/backend/config/.env" ]; then
  ln -sf "config/.env" "$PROJECT_DIR/backend/.env" 2>/dev/null || true
fi

echo ""

# ========================================
# Step 2: 后端虚拟环境 + 依赖
# ========================================
info "初始化后端 (backend)..."
cd "$PROJECT_DIR/backend"

if [ ! -d "venv" ] || [ "$FORCE" = true ]; then
  if [ "$FORCE" = true ] && [ -d "venv" ]; then
    info "强制重建 venv..."
    rm -rf venv
  fi
  info "创建 Python 虚拟环境..."
  python3 -m venv venv
  ok "虚拟环境已创建: backend/venv"
else
  ok "虚拟环境已存在: backend/venv"
fi

info "安装后端 Python 依赖..."
./venv/bin/pip install --upgrade pip -q
./venv/bin/pip install -r requirements.txt -q
ok "后端依赖安装完成 ($(./venv/bin/pip list --format=columns 2>/dev/null | wc -l) 个包)"

echo ""

# ========================================
# Step 3: 认证网关依赖（复用后端 venv）
# ========================================
info "初始化认证网关 (auth-gateway)..."
cd "$PROJECT_DIR/auth-gateway"

# 复用后端 venv（符号链接），省 ~700MB 磁盘空间
if [ ! -L "venv" ] || [ ! -d "$(readlink venv 2>/dev/null)" ]; then
  if [ -d "$PROJECT_DIR/backend/venv" ]; then
    ln -sf "$PROJECT_DIR/backend/venv" "$PROJECT_DIR/auth-gateway/venv"
    ok "认证网关 venv → symlink 到 backend/venv"
  else
    warn "后端 venv 不存在，等后端初始化后再运行 init.sh"
  fi
else
  ok "认证网关 venv 已链接到 backend/venv"
fi

info "安装认证网关 Python 依赖..."
"$PROJECT_DIR/backend/venv/bin/pip" install -r requirements.txt -q 2>/dev/null || \
  warn "认证网关依赖安装跳过（后端 venv 可能已包含）"
ok "认证网关依赖检查完成"

echo ""

# ========================================
# Step 4: 前端依赖
# ========================================
info "初始化前端 (frontend)..."
cd "$PROJECT_DIR/frontend"

if [ -d "node_modules" ] && [ "$FORCE" != true ]; then
  ok "前端 node_modules 已存在"
  info "检查是否有更新..."
  npm install --no-audit --no-fund --prefer-offline 2>&1 | tail -3
else
  if [ "$FORCE" = true ] && [ -d "node_modules" ]; then
    info "强制重新安装前端依赖..."
    rm -rf node_modules
  fi
  info "安装前端依赖..."
  npm install --no-audit --no-fund 2>&1 | tail -5
fi
ok "前端依赖安装完成"

echo ""

# ========================================
# Step 4b: Admin 前端依赖（如果存在）
# ========================================
if [ -d "$PROJECT_DIR/admin" ]; then
  info "初始化 admin 前端..."
  cd "$PROJECT_DIR/admin"
  if [ -d "node_modules" ] && [ "$FORCE" != true ]; then
    ok "admin node_modules 已存在"
  else
    info "安装 admin 前端依赖..."
    npm install --no-audit --no-fund 2>&1 | tail -3
    ok "admin 前端依赖安装完成"
  fi
  echo ""
fi

# ========================================
# Step 5: 数据库初始化（可选）
# ========================================
echo ""
info "检查数据库..."

DB_NAME="${DB_NAME:-edu_companion}"

if command -v psql &>/dev/null; then
  # 尝试从配置读取密码
  if [ -f "$PROJECT_DIR/backend/config/.env" ]; then
    export DB_PASSWORD=$(grep -oP '^DB_PASSWORD=\K.*' "$PROJECT_DIR/backend/config/.env" 2>/dev/null || echo "")
    export DB_USER=$(grep -oP '^DB_USER=\K.*' "$PROJECT_DIR/backend/config/.env" 2>/dev/null || echo "companion")
    export DB_HOST=$(grep -oP '^DB_HOST=\K.*' "$PROJECT_DIR/backend/config/.env" 2>/dev/null || echo "127.0.0.1")
    export DB_PORT=$(grep -oP '^DB_PORT=\K.*' "$PROJECT_DIR/backend/config/.env" 2>/dev/null || echo "5432")
  fi

  # 尝试连接
  PGCONN="postgresql://${DB_USER:-companion}:${DB_PASSWORD}@${DB_HOST:-127.0.0.1}:${DB_PORT:-5432}/postgres"

  if psql "$PGCONN" -c "SELECT 1" &>/dev/null; then
    ok "PostgreSQL 连接成功"
    
    # 检查数据库是否存在
    DB_EXISTS=$(psql "$PGCONN" -tAc "SELECT 1 FROM pg_database WHERE datname='$DB_NAME'" 2>/dev/null || echo "0")
    if [ "$DB_EXISTS" != "1" ]; then
      info "创建数据库 $DB_NAME..."
      psql "$PGCONN" -c "CREATE DATABASE $DB_NAME" 2>/dev/null || warn "数据库创建失败（可能缺少权限）"
      
      # 尝试创建 pgvector 扩展
      DB_CONN="postgresql://${DB_USER:-companion}:${DB_PASSWORD}@${DB_HOST:-127.0.0.1}:${DB_PORT:-5432}/$DB_NAME"
      psql "$DB_CONN" -c "CREATE EXTENSION IF NOT EXISTS vector" 2>/dev/null || warn "pgvector 扩展创建失败（不影响核心功能）"
      ok "数据库 $DB_NAME 已就绪"
    else
      ok "数据库 $DB_NAME 已存在"
    fi
  else
    warn "无法连接 PostgreSQL（可稍后手动初始化）"
    warn "  连接字符串: $PGCONN"
  fi
else
  warn "psql 未安装，跳过数据库初始化"
fi

echo ""

# ========================================
# Step 6: 创建日志目录
# ========================================
mkdir -p "$PROJECT_DIR/logs"
ok "日志目录已创建: logs/"

# ========================================
# 完成
# ========================================
echo ""
echo "========================================"
echo -e "  ${GREEN}🎉 初始化完成${NC}"
echo "========================================"
echo ""
echo "📋 后续步骤:"
echo ""

# 检查哪些 .env 需要用户编辑
NEEDS_EDIT=false
if grep -q "sk-your" "$PROJECT_DIR/backend/config/.env" 2>/dev/null; then
  echo -e "  ${YELLOW}✎${NC} 编辑 backend/config/.env → 填入 OPENAI_API_KEY"
  NEEDS_EDIT=true
fi
if grep -q "your-strong-secret" "$PROJECT_DIR/auth-gateway/config/.env" 2>/dev/null; then
  echo -e "  ${YELLOW}✎${NC} 编辑 auth-gateway/config/.env → 修改 JWT_SECRET"
  NEEDS_EDIT=true
fi
if grep -q "your-db" "$PROJECT_DIR/backend/config/.env" 2>/dev/null; then
  echo -e "  ${YELLOW}✎${NC} 编辑 backend/config/.env → 填入 DB_PASSWORD"
  NEEDS_EDIT=true
fi
if ! $NEEDS_EDIT; then
  echo -e "  ${GREEN}✓${NC} 所有配置已就绪"
fi

echo ""
echo "  ▶ 启动开发环境:"
echo "      bash startup.sh"
echo ""
echo "  ▶ 构建 + 重启:"
echo "      bash rebuild.sh"
echo ""
echo "  ▶ 构建（跳过前端）:"
echo "      bash rebuild.sh --skip-build"
echo ""
echo "  ▶ 关闭所有服务:"
echo "      bash shutdown.sh"
echo ""
echo "  ▶ 查看服务状态:"
echo "      ps aux | grep -E 'uvicorn|next'"
echo ""
echo "📁 服务访问地址:"
echo "      前端:       http://localhost:3000"
echo "      后端 API:   http://localhost:8000/docs"
echo "      认证网关:   http://localhost:18001/docs"
echo "      Nginx 网关: http://localhost:8080"
echo "      Admin 后端: http://localhost:8001/admin/docs"
echo ""
