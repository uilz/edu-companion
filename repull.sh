#!/usr/bin/env bash
# ===== edu-companion 一键部署脚本 =====
# 从 GitHub 拉取最新代码 → 构建前端 → 重启前后端
# 用法: ./repull.sh           # 构建前端+重启
#       ./repull.sh backend   # 只重启后端（前端不变）
#       ./repull.sh frontend  # 只构建前端+重启
#       ./repull.sh quick     # 只拉取代码（跳过构建）

set -euo pipefail
cd "$(dirname "$0")"

REPO_DIR="/home/deploy/edu-companion"
NODE="/home/deploy/.nvm/versions/node/v20.20.2/bin/node"
NPM="/home/deploy/.nvm/versions/node/v20.20.2/bin/npm"

log()  { echo -e "\e[36m[$1]\e[0m $2"; }
ok()   { echo -e "\e[32m  ✔\e[0m $1"; }
fail() { echo -e "\e[31m  ✘\e[0m $1"; }

target="${1:-all}"
cd "$REPO_DIR"

# ── 1. 拉取代码 ──
log "GIT" "拉取最新代码..."
git pull --ff-only 2>/dev/null || {
  git stash && git pull --ff-only && git stash pop
}
ok "代码已更新 ($(git log --oneline -1))"

[ "$target" = "quick" ] && { ok "快速部署完成"; exit 0; }

# ── 2. 构建前端 ──
if [ "$target" = "frontend" ] || [ "$target" = "all" ]; then
  log "BUILD" "构建前端..."
  cd "$REPO_DIR/frontend"
  export PATH="/home/deploy/.nvm/versions/node/v20.20.2/bin:$PATH"
  $NPM run build 2>&1 | tail -3
  ok "前端构建完成"

  log "RESTART" "重启前端..."
  systemctl --user restart edu-frontend.service || {
    # 处理旧进程卡住的情况
    pgrep -f "next-server" | xargs -r kill -9 2>/dev/null || true
    sleep 1
    systemctl --user reset-failed edu-frontend.service 2>/dev/null
    systemctl --user restart edu-frontend.service
  }
  ok "前端已重启"
fi

# ── 3. 重启后端 ──
if [ "$target" = "backend" ] || [ "$target" = "all" ]; then
  log "RESTART" "重启后端..."
  systemctl --user restart edu-backend.service
  sleep 2
  health=$(curl -s http://localhost:8000/health 2>/dev/null || echo "not ready")
  if echo "$health" | grep -q "healthy"; then
    ok "后端健康 ✅ $health"
  else
    fail "后端未就绪: $health"
    systemctl --user status edu-backend.service --no-pager -l | tail -5
  fi
fi

# ── 4. 验证 ──
if [ "$target" = "all" ]; then
  echo ""
  log "VERIFY" "全链路验证..."
  for i in {1..5}; do
    fe=$(curl -sL -o /dev/null -w '%{http_code}' http://localhost:3000/ 2>/dev/null || echo "000")
    be=$(curl -s http://localhost:8000/health 2>/dev/null || echo "not ready")
    [ "$fe" = "200" ] && ok "前端 HTTP 200" || fail "前端: HTTP $fe"
    echo "$be" | grep -q "healthy" && ok "后端健康" || fail "后端: $be"
    [ "$fe" = "200" ] && [ -n "$be" ] && break
    sleep 2
  done
  echo ""
  ok "部署完成 🚀"
fi
