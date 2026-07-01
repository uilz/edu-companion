#!/bin/bash
# ============================================================
# 用户管理运维脚本 — 一键化常用操作
# 用法: sudo -u deploy bash manage-users.sh
# ============================================================
set -euo pipefail

# ── 路径 ──
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
ENV_FILE="$PROJECT_DIR/backend/config/.env"

# ── 颜色 ──
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; NC='\033[0m'

log()  { echo -e "${GREEN}[✓]${NC} $1"; }
warn() { echo -e "${YELLOW}[!]${NC} $1"; }
err()  { echo -e "${RED}[✗]${NC} $1"; }
info() { echo -e "${CYAN}[i]${NC} $1"; }

# ── 加载环境变量 ──
load_env() {
  if [[ ! -f "$ENV_FILE" ]]; then
    err "未找到 $ENV_FILE"
    err "请确保脚本在项目目录内运行"
    exit 1
  fi
  set -a; source "$ENV_FILE"; set +a
  DB_USER="${DB_USER:-companion}"
  DB_HOST="${DB_HOST:-127.0.0.1}"
  DB_PORT="${DB_PORT:-5432}"
  DB_NAME="${DB_NAME:-edu_companion}"
}

# ── 获取数据库密码（从 .env） ──
get_db_password() {
  grep -oP '^DB_PASSWORD\s*=\s*\K.*' "$ENV_FILE" | head -1
}

# ── psql 快捷执行 ──
run_sql() {
  local pw
  pw=$(get_db_password)
  PGPASSWORD="$pw" PAGER=cat psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -Atc "$1"
}

run_sql_stdout() {
  local pw
  pw=$(get_db_password)
  PGPASSWORD="$pw" PAGER=cat psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -c "$1"
}

# ── 生成 bcrypt 哈希 ──
gen_hash() {
  python3 -c "import bcrypt; print(bcrypt.hashpw(b'$1', bcrypt.gensalt()).decode())"
}

# ── 列出所有用户 ──
list_users() {
  echo ""
  info "===== 用户列表 ====="
  run_sql_stdout "
    SELECT id, username, email, role, is_active,
           to_char(created_at, 'YYYY-MM-DD HH24:MI') AS created
    FROM users ORDER BY created_at DESC;
  "
  echo ""
}

# ── 搜索用户 ──
search_user() {
  read -r -p "输入用户名/邮箱关键词: " q
  echo ""
  run_sql_stdout "
    SELECT id, username, email, display_name, role, is_active,
           to_char(last_login, 'YYYY-MM-DD HH24:MI') AS last_login
    FROM users
    WHERE username ILIKE '%$q%' OR email ILIKE '%$q%' OR display_name ILIKE '%$q%'
    ORDER BY created_at DESC;
  "
}

# ── 创建用户 ──
create_user() {
  read -r -p "用户名: " username
  read -r -s -p "密码 (最少4位): " password; echo ""
  read -r -p "显示名 (可选): " display_name
  read -r -p "邮箱 (可选): " email
  echo ""
  info "角色选择:"
  echo "  1) user (普通用户)"
  echo "  2) analyst (分析员)"
  echo "  3) data_admin (数据管理员)"
  echo "  4) super_admin (超级管理员)"
  read -r -p "角色编号 [1]: " role_choice
  case "${role_choice:-1}" in
    2) role="analyst" ;;
    3) role="data_admin" ;;
    4) role="super_admin" ;;
    *) role="user" ;;
  esac

  # 生成 user_id
  local uid
  uid=$(python3 -c "
import hashlib, time
print('u_' + hashlib.md5(f'$username{time.time()}'.encode()).hexdigest()[:12])
")

  local hash
  hash=$(gen_hash "$password")
  display_name="${display_name:-$username}"

  run_sql "
    INSERT INTO users (id, username, email, password_hash, display_name, role, is_active)
    VALUES ('$uid', '$username', '${email:-}', '$hash', '$display_name', '$role', true);
  " 2>/dev/null && log "用户 $username ($uid) 创建成功，角色: $role" \
    || err "创建失败，用户名 $username 可能已存在"
}

# ── 重置密码 ──
reset_password() {
  read -r -p "用户 ID 或 用户名: " uid_or_name
  read -r -s -p "新密码: " new_pwd; echo ""
  read -r -s -p "确认新密码: " confirm; echo ""

  if [[ "$new_pwd" != "$confirm" ]]; then
    err "两次密码不一致"; return 1
  fi

  # 检查用户是否存在
  local exists
  exists=$(PGPASSWORD="$(get_db_password)" PAGER=cat psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -Atc "SELECT COUNT(*) FROM users WHERE id='$uid_or_name' OR username='$uid_or_name';" 2>/dev/null)
  if [[ -z "$exists" || "$exists" -eq 0 ]]; then
    err "用户 $uid_or_name 不存在"; return 1
  fi

  local hash
  hash=$(gen_hash "$new_pwd")

  if [[ "$uid_or_name" =~ ^u_ ]]; then
    run_sql "UPDATE users SET password_hash='$hash', updated_at=NOW() WHERE id='$uid_or_name';"
  else
    run_sql "UPDATE users SET password_hash='$hash', updated_at=NOW() WHERE username='$uid_or_name';"
  fi
  log "密码已重置"
}

# ── 修改角色 ──
change_role() {
  read -r -p "用户 ID 或 用户名: " uid_or_name
  echo "角色: 1) user  2) analyst  3) data_admin  4) super_admin"
  read -r -p "新角色编号: " r
  local new_role
  case "$r" in
    1) new_role="user" ;; 2) new_role="analyst" ;; 3) new_role="data_admin" ;; 4) new_role="super_admin" ;;
    *) err "无效角色"; return 1 ;;
  esac
  if [[ "$uid_or_name" =~ ^u_ ]]; then
    run_sql "UPDATE users SET role='$new_role', updated_at=NOW() WHERE id='$uid_or_name';"
  else
    run_sql "UPDATE users SET role='$new_role', updated_at=NOW() WHERE username='$uid_or_name';"
  fi
  local rc=$?
  # 检查是否真的更新了行（UPDATE 返回 "UPDATE N"）
  local affected
  affected=$(PGPASSWORD="$(get_db_password)" PAGER=cat psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -Atc "SELECT COUNT(*) FROM users WHERE id='$uid_or_name' OR username='$uid_or_name';" 2>/dev/null)
  if [[ "$affected" -gt 0 ]]; then
    log "用户 $uid_or_name 角色已改为 $new_role"
  else
    err "用户 $uid_or_name 不存在"
  fi
}

# ── 封禁/解封 ──
toggle_ban() {
  read -r -p "用户 ID 或 用户名: " uid_or_name
  local field
  if [[ "$uid_or_name" =~ ^u_ ]]; then field="id"; else field="username"; fi
  local is_active
  is_active=$(run_sql "SELECT is_active FROM users WHERE $field='$uid_or_name';")
  if [[ "$is_active" == "t" ]]; then
    run_sql "UPDATE users SET is_active=false, updated_at=NOW() WHERE $field='$uid_or_name';"
    log "用户 $uid_or_name 已封禁"
  elif [[ "$is_active" == "f" ]]; then
    run_sql "UPDATE users SET is_active=true, updated_at=NOW() WHERE $field='$uid_or_name';"
    log "用户 $uid_or_name 已解封"
  else
    err "用户 $uid_or_name 不存在"
  fi
}

# ── 删除用户（带关联数据清理） ──
delete_user() {
  read -r -p "用户 ID 或 用户名: " uid_or_name
  local field
  if [[ "$uid_or_name" =~ ^u_ ]]; then field="id"; else field="username"; fi

  # 先检查用户是否存在
  local exists
  exists=$(run_sql "SELECT id FROM users WHERE $field='$uid_or_name';")
  if [[ -z "$exists" ]]; then
    err "用户 $uid_or_name 不存在"; return 1
  fi
  local uid="$exists"

  echo ""
  warn "警告: 删除用户不可恢复！将删除该用户的所有关联数据。"
  read -r -p "确认删除 $uid ($uid_or_name) ? (输入 yes 确认): " confirm
  if [[ "$confirm" != "yes" ]]; then
    warn "已取消"; return 1
  fi

  info "正在删除关联数据..."
  run_sql "DELETE FROM login_events          WHERE user_id='$uid';" 2>/dev/null || true
  run_sql "DELETE FROM practice_attempts     WHERE user_id='$uid';" 2>/dev/null || true
  run_sql "DELETE FROM practice_sessions     WHERE user_id='$uid';" 2>/dev/null || true
  run_sql "DELETE FROM conversation_user_meta WHERE user_id='$uid';" 2>/dev/null || true
  run_sql "DELETE FROM knowledge_nodes       WHERE user_id='$uid';" 2>/dev/null || true
  run_sql "DELETE FROM events                WHERE user_id='$uid';" 2>/dev/null || true
  run_sql "DELETE FROM users                 WHERE id='$uid';" 2>/dev/null || true
  log "用户 $uid ($uid_or_name) 已永久删除"
}

# ── 强制踢下线 ──
force_logout() {
  read -r -p "用户 ID 或 用户名: " uid_or_name
  local field
  if [[ "$uid_or_name" =~ ^u_ ]]; then field="id"; else field="username"; fi
  run_sql "UPDATE users SET token_version=token_version+1, updated_at=NOW() WHERE $field='$uid_or_name';"
  log "用户 $uid_or_name 的 token_version 已递增，所有设备需重新登录"
}

# ── 创建或重置第一个超级管理员 ──
bootstrap_admin() {
  echo ""
  info "===== 创建/重置超级管理员 ====="
  warn "如果 admin 用户已存在，会重置其密码。如果不存在，会创建。"
  echo ""
  read -r -p "用户名 [admin]: " username
  username="${username:-admin}"
  read -r -s -p "密码 (最少8位): " password; echo ""
  read -r -s -p "确认密码: " confirm; echo ""

  if [[ "$password" != "$confirm" ]]; then
    err "两次密码不一致"; return 1
  fi
  if [[ ${#password} -lt 8 ]]; then
    err "密码最少8位"; return 1
  fi

  local hash
  hash=$(gen_hash "$password")

  # 检查用户是否存在
  local exists
  exists=$(run_sql "SELECT id FROM users WHERE username='$username';")

  if [[ -z "$exists" ]]; then
    # 创建新用户
    local uid
    uid=$(python3 -c "
import hashlib, time
print('u_' + hashlib.md5(f'$username{time.time()}'.encode()).hexdigest()[:12])
")
    run_sql "
      INSERT INTO users (id, username, email, password_hash, display_name, role, is_active)
      VALUES ('$uid', '$username', '', '$hash', '超级管理员', 'super_admin', true);
    " && log "超级管理员 $username ($uid) 创建成功"
  else
    # 重置密码+提升角色
    run_sql "
      UPDATE users SET password_hash='$hash', role='super_admin', is_active=true, updated_at=NOW()
      WHERE username='$username';
    " && log "超级管理员 $username 密码已重置，角色已提升为 super_admin"
  fi

  echo ""
  info "你现在可以用以下命令获取 JWT:"
  echo "  curl -s -X POST http://localhost:18001/api/auth/login \\"
  echo "    -H \"Content-Type: application/json\" \\"
  echo "    -d '{\"username\":\"$username\",\"password\":\"$password\"}'"
}

# ── 菜单 ──
menu() {
  while true; do
    echo ""
    echo "=========================================="
    echo "         用户管理运维脚本"
    echo "=========================================="
    echo "  1)  列出所有用户"
    echo "  2)  搜索用户"
    echo "  3)  创建新用户"
    echo "  4)  重置密码"
    echo "  5)  修改角色"
    echo "  6)  封禁 / 解封"
    echo "  7)  强制踢下线"
    echo "  8)  删除用户（不可恢复）"
    echo "  ---------------------------------------"
    echo "  9)  创建/重置超级管理员 (bootstrap)"
    echo "  ---------------------------------------"
    echo "  q)  退出"
    echo "=========================================="
    read -r -p "选择操作: " choice
    echo ""
    case "$choice" in
      1) list_users ;;
      2) search_user ;;
      3) create_user ;;
      4) reset_password ;;
      5) change_role ;;
      6) toggle_ban ;;
      7) force_logout ;;
      8) delete_user ;;
      9) bootstrap_admin ;;
      q|Q) log "再见"; exit 0 ;;
      *) warn "无效选择" ;;
    esac
    echo ""
    read -r -p "按回车继续..."
  done
}

# ── 入口 ──
load_env

# 检查 psql
if ! command -v psql &>/dev/null; then
  err "未找到 psql，请安装 postgresql-client"
  exit 1
fi

# 检查 python3 + bcrypt
if ! python3 -c "import bcrypt" 2>/dev/null; then
  err "未安装 bcrypt: pip3 install bcrypt"
  exit 1
fi

clear
echo ""
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${CYAN}    用户管理运维工具                ${NC}"
echo -e "${CYAN}    项目: edu-companion             ${NC}"
echo -e "${CYAN}    数据库: $DB_HOST:$DB_PORT/$DB_NAME${NC}"
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

# 检测 admin 服务可用性
if curl -s -o /dev/null -w "%{http_code}" http://localhost:8001/admin/health 2>/dev/null | grep -q 200; then
  info "admin-backend 服务正常 (8001)"
else
  warn "admin-backend 不可用，所有操作将直接操作数据库"
fi

menu
