#!/bin/bash
# init.sh — 苹果果学习助手 · 一键初始化
# 用法: bash init.sh [--force] [--skip-sudo]
# 功能: 在新机器上从零搭建完整开发/生产环境
#
# --force      : 强制重建 venv/node_modules
# --skip-sudo  : 跳过需要 sudo 的系统依赖安装（仅项目级初始化）

set -e

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
FORCE=false
SKIP_SUDO=false
for arg; do
  case $arg in
    --force) FORCE=true ;;
    --skip-sudo) SKIP_SUDO=true ;;
  esac
done

# ── 颜色 ──
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; CYAN='\033[0;36m'; NC='\033[0m'
info()  { echo -e "${BLUE}[INFO]${NC}  $1"; }
ok()    { echo -e "${GREEN}[OK]${NC}    $1"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $1"; }
err()   { echo -e "${RED}[ERR]${NC}   $1"; }
step()  { echo -e "\n${CYAN}══════════════════════════════════════${NC}"; echo -e "${CYAN}  $1${NC}"; echo -e "${CYAN}══════════════════════════════════════${NC}"; }

# ========================================
# 检测操作系统
# ========================================
step "🖥️  检测系统环境"

OS_ID=""
OS_VERSION=""
if [ -f /etc/os-release ]; then
  . /etc/os-release
  OS_ID=$ID
  OS_VERSION=$VERSION_ID
fi
info "系统: $PRETTY_NAME"
info "项目目录: $PROJECT_DIR"

# ========================================
# 系统依赖安装（需要 sudo）
# ========================================
install_system_deps() {
  step "📦 安装系统依赖"

  if [ "$SKIP_SUDO" = true ]; then
    warn "跳过系统依赖安装（--skip-sudo）"
    return
  fi

  info "更新软件源..."
  sudo apt update -qq || true

  info "安装基础工具..."
  sudo apt install -y -qq curl git psmisc nginx 2>&1 | tail -1

  # ── Node.js via nvm ──
  if [ ! -d "$HOME/.nvm" ]; then
    info "安装 nvm（Node.js 版本管理器）..."
    curl -fsSL https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.2/install.sh | bash
  else
    ok "nvm 已安装"
  fi

  # 加载 nvm
  export NVM_DIR="$HOME/.nvm"
  [ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh"

  info "安装 Node.js v22..."
  nvm install 22 2>&1 | tail -2
  nvm alias default 22
  ok "Node.js $(node --version) / npm $(npm --version)"

  # ── Python 3.11 via deadsnakes ──
  if ! python3.11 --version &>/dev/null; then
    info "安装 Python 3.11..."
    sudo add-apt-repository -y ppa:deadsnakes/ppa 2>&1 | tail -1
    sudo apt install -y -qq python3.11 python3.11-dev python3.11-venv 2>&1 | tail -1
  else
    ok "Python 3.11 已安装"
  fi
  ok "Python $(python3.11 --version)"

  # ── PostgreSQL 14 + pgvector ──
  if ! command -v psql &>/dev/null; then
    info "安装 PostgreSQL 14..."
    sudo apt install -y -qq postgresql-14 2>&1 | tail -1
    sudo systemctl enable postgresql 2>/dev/null || true
    sudo systemctl start postgresql 2>/dev/null || true
  else
    ok "PostgreSQL $(psql --version 2>&1 | head -1) 已安装"
  fi

  if ! dpkg -l postgresql-14-pgvector &>/dev/null; then
    info "安装 pgvector 扩展..."
    sudo apt install -y -qq postgresql-14-pgvector 2>&1 | tail -1
  else
    ok "pgvector 已安装"
  fi
}

install_system_deps

# ========================================
# 加载 nvm（确保后续可用）
# ========================================
export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh"

# ========================================
# 环境配置文件初始化
# ========================================
step "🔧 初始化环境配置"

init_env() {
  local env_file="$1" example_file="$2" name="$3"
  if [ -f "$env_file" ]; then
    ok "$name 配置已存在: $env_file"
  elif [ -f "$example_file" ]; then
    cp "$example_file" "$env_file"
    ok "$name 配置已从模板创建: $env_file"
  else
    warn "$name 模板不存在: $example_file（手动创建）"
    touch "$env_file"
  fi
}

# 确保 config 目录存在
mkdir -p "$PROJECT_DIR/backend/config"
mkdir -p "$PROJECT_DIR/auth-gateway/config"
mkdir -p "$PROJECT_DIR/frontend/config"

init_env "$PROJECT_DIR/backend/config/.env" \
  "$PROJECT_DIR/backend/config/.env.example" "后端"
init_env "$PROJECT_DIR/auth-gateway/config/.env" \
  "$PROJECT_DIR/auth-gateway/config/.env.example" "认证网关"
init_env "$PROJECT_DIR/frontend/config/.env" \
  "$PROJECT_DIR/frontend/config/.env.example" "前端"

# 兼容：backend/.env → config/.env 软链接
if [ -f "$PROJECT_DIR/backend/.env" ] && [ ! -L "$PROJECT_DIR/backend/.env" ]; then
  mkdir -p "$PROJECT_DIR/backend/config"
  cp "$PROJECT_DIR/backend/.env" "$PROJECT_DIR/backend/config/.env" 2>/dev/null || true
fi

# ========================================
# 后端 Python 虚拟环境
# ========================================
step "🐍 后端 Python 环境"

cd "$PROJECT_DIR/backend"

# 确定 python3.11 或 python3
PYTHON_BIN=""
for p in python3.11 python3; do
  if command -v "$p" &>/dev/null; then
    PYTHON_BIN="$p"
    break
  fi
done

if [ -z "$PYTHON_BIN" ]; then
  err "未找到 Python 3！请先安装 python3"
  exit 1
fi

if [ ! -d "venv" ] || [ "$FORCE" = true ]; then
  [ "$FORCE" = true ] && [ -d "venv" ] && rm -rf venv
  info "创建 Python 虚拟环境（$PYTHON_BIN）..."
  $PYTHON_BIN -m venv venv
  ok "虚拟环境已创建: backend/venv"
else
  ok "虚拟环境已存在: backend/venv"
fi

info "安装后端 Python 依赖..."
./venv/bin/pip install --upgrade pip -q
./venv/bin/pip install -r requirements.txt -q
ok "后端依赖安装完成"

cd "$PROJECT_DIR"

# ========================================
# 认证网关依赖
# ========================================
step "🔐 认证网关环境"

cd "$PROJECT_DIR/auth-gateway"

# 复用后端 venv（符号链接）
if [ ! -L "venv" ]; then
  if [ -d "$PROJECT_DIR/backend/venv" ]; then
    ln -sf "$PROJECT_DIR/backend/venv" .
    ok "认证网关 venv → symlink 到 backend/venv"
  fi
fi

info "安装认证网关 Python 依赖..."
"$PROJECT_DIR/backend/venv/bin/pip" install -r requirements.txt -q
ok "认证网关依赖安装完成"

cd "$PROJECT_DIR"

# ========================================
# 前端依赖
# ========================================
step "⚛️  前端依赖"

cd "$PROJECT_DIR/frontend"

if [ ! -d "node_modules" ] || [ "$FORCE" = true ]; then
  [ "$FORCE" = true ] && [ -d "node_modules" ] && rm -rf node_modules
  info "安装前端依赖..."
  npm install --no-audit --no-fund 2>&1 | tail -3
else
  ok "node_modules 已存在，检查更新..."
  npm install --no-audit --no-fund --prefer-offline 2>&1 | tail -1
fi
ok "前端依赖就绪"

cd "$PROJECT_DIR"

# ========================================
# Admin 前端依赖
# ========================================
if [ -d "$PROJECT_DIR/admin" ]; then
  step "📊 Admin 前端依赖"
  cd "$PROJECT_DIR/admin"
  if [ ! -d "node_modules" ] || [ "$FORCE" = true ]; then
    [ "$FORCE" = true ] && [ -d "node_modules" ] && rm -rf node_modules
    info "安装 admin 前端依赖..."
    npm install --no-audit --no-fund 2>&1 | tail -3
  else
    ok "node_modules 已存在"
  fi
  cd "$PROJECT_DIR"
fi

# ========================================
# PostgreSQL 数据库初始化
# ========================================
step "🗄️  数据库初始化"

DB_NAME="edu_companion"
DB_USER="companion"
DB_PASS="companion123"
DB_PORT="${DB_PORT:-5433}"

# 从 .env 读取配置
if [ -f "$PROJECT_DIR/backend/config/.env" ]; then
  DB_PASS=$(grep -oP '^DB_PASSWORD=\K.*' "$PROJECT_DIR/backend/config/.env" 2>/dev/null || echo "$DB_PASS")
  DB_PORT=$(grep -oP '^DB_PORT=\K.*' "$PROJECT_DIR/backend/config/.env" 2>/dev/null || echo "$DB_PORT")
fi

if command -v psql &>/dev/null; then
  # 使用系统 postgres 用户（免密码）
  if sudo -u postgres psql -c "SELECT 1" &>/dev/null; then
    ok "PostgreSQL 服务正常"

    # 创建用户
    if sudo -u postgres psql -tAc "SELECT 1 FROM pg_roles WHERE rolname='$DB_USER'" | grep -q 1; then
      ok "数据库用户 $DB_USER 已存在"
    else
      info "创建数据库用户 $DB_USER..."
      sudo -u postgres psql -c "CREATE USER $DB_USER WITH PASSWORD '$DB_PASS';"
      ok "数据库用户 $DB_USER 已创建"
    fi

    # 创建数据库
    if sudo -u postgres psql -tAc "SELECT 1 FROM pg_database WHERE datname='$DB_NAME'" | grep -q 1; then
      ok "数据库 $DB_NAME 已存在"
    else
      info "创建数据库 $DB_NAME..."
      sudo -u postgres psql -c "CREATE DATABASE $DB_NAME OWNER $DB_USER;"
      ok "数据库 $DB_NAME 已创建"
    fi

    # pgvector 扩展
    info "安装 pgvector 扩展..."
    sudo -u postgres psql -d "$DB_NAME" -c "CREATE EXTENSION IF NOT EXISTS vector;" 2>/dev/null
    ok "pgvector 扩展就绪"

    # 授权
    sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE $DB_NAME TO $DB_USER;" 2>/dev/null || true
    sudo -u postgres psql -d "$DB_NAME" -c "GRANT ALL ON SCHEMA public TO $DB_USER;" 2>/dev/null || true

    # 确保 DB_PORT 写入 .env
    PG_PORT=$(sudo -u postgres psql -tAc "SHOW port;" 2>/dev/null | tr -d ' ')
    if [ -n "$PG_PORT" ] && [ "$PG_PORT" != "5432" ]; then
      if ! grep -q "^DB_PORT=" "$PROJECT_DIR/backend/config/.env" 2>/dev/null; then
        echo "DB_PORT=$PG_PORT" >> "$PROJECT_DIR/backend/config/.env"
        info "DB_PORT=$PG_PORT 已写入 .env"
      fi
    fi
  else
    warn "无法通过 sudo -u postgres 连接，跳过数据库初始化"
    warn "  请手动执行: sudo -u postgres psql"
  fi
else
  warn "psql 未安装，跳过数据库初始化"
fi

# ========================================
# 创建日志目录
# ========================================
step "📁 创建日志目录"
mkdir -p "$PROJECT_DIR/logs"
mkdir -p "$PROJECT_DIR/nginx/client_body_temp"
ok "日志目录已创建: logs/"

# ========================================
# 完成！
# ========================================
step "🎉 初始化完成！"

echo ""
echo -e "  ${GREEN}✓${NC} 系统依赖    已安装"
echo -e "  ${GREEN}✓${NC} Python 环境  $($PROJECT_DIR/backend/venv/bin/python --version)"
echo -e "  ${GREEN}✓${NC} Node.js      $(node --version 2>/dev/null || echo '?')"
echo -e "  ${GREEN}✓${NC} 后端依赖     $(pip list --format=columns 2>/dev/null | wc -l) 个包"
echo -e "  ${GREEN}✓${NC} 前端依赖     已就绪"
echo ""

# 检查是否需要编辑 .env
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
echo -e "  ${CYAN}▶${NC} 构建并启动所有服务:"
echo "      bash rebuild.sh"
echo ""
echo -e "  ${CYAN}▶${NC} 跳过前端构建快速重启:"
echo "      bash rebuild.sh --skip-build"
echo ""
echo -e "  ${CYAN}▶${NC} 访问地址:"
echo "      前端:       http://localhost:3000"
echo "      后端 API:   http://localhost:8000/docs"
echo "      认证网关:   http://localhost:18001/docs"
echo "      Nginx 网关: http://localhost:8080"
echo ""
echo -e "  ${YELLOW}💡${NC} 如果数据库端口不是 5432（检查 /etc/postgresql/*/main/postgresql.conf），"
echo "      请在 backend/config/.env 中添加: DB_PORT=<实际端口>"
echo ""
