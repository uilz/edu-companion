#!/usr/bin/env bash
set -euo pipefail
# ═══════════════════════════════════════════════════════════════════
# Phase 1: 合并 infrastructure
# 1. backend/infra/ → backend/app/infrastructure/
# 2. backend/app/db/ → backend/app/infrastructure/db/
# 3. 更新所有 import
# ═══════════════════════════════════════════════════════════════════

APP_DIR="/home/deploy/edu-companion/backend/app"
BACKEND_DIR="/home/deploy/edu-companion/backend"
INFRA_SRC="$BACKEND_DIR/infra"
DB_SRC="$APP_DIR/db"
INFRA_DST="$APP_DIR/infrastructure"

echo "═══════════════════════════════════════════════════════════"
echo " Phase 1: 合并基础设施目录"
echo "═══════════════════════════════════════════════════════════"

# ── Step 1: 复制文件到目标目录 ──

echo "[1/5] 复制 infra/ → app/infrastructure/ ..."
rsync -a --exclude='__pycache__' "$INFRA_SRC/" "$INFRA_DST/"

echo "[2/5] 复制 app/db/ → app/infrastructure/db/ ..."
mkdir -p "$INFRA_DST/db"
rsync -a --exclude='__pycache__' "$DB_SRC/" "$INFRA_DST/db/"

echo "[3/5] 更新所有 import 路径 ..."

# ── 替换 1: infra.xxx → app.infrastructure.xxx ──
find "$BACKEND_DIR" -name "*.py" -type f \
    -not -path "*/venv/*" -not -path "*/__pycache__/*" \
    -exec sed -i 's/from infra\./from app.infrastructure./g' {} \;

find "$BACKEND_DIR" -name "*.py" -type f \
    -not -path "*/venv/*" -not -path "*/__pycache__/*" \
    -exec sed -i 's/import infra\./import app.infrastructure./g' {} \;

# ── 替换 2: app.db.xxx → app.infrastructure.db.xxx ──
find "$BACKEND_DIR" -name "*.py" -type f \
    -not -path "*/venv/*" -not -path "*/__pycache__/*" \
    -exec sed -i 's/from app\.db\./from app.infrastructure.db./g' {} \;

find "$BACKEND_DIR" -name "*.py" -type f \
    -not -path "*/venv/*" -not -path "*/__pycache__/*" \
    -exec sed -i 's/import app\.db\./import app.infrastructure.db./g' {} \;

echo "[4/5] 删除旧目录 ..."

# 删除旧的 infra/ 目录（不在 app/ 下，是顶层）
if [ -d "$INFRA_SRC" ]; then
    rm -rf "$INFRA_SRC"
    echo "  已删除: $INFRA_SRC"
fi

# 删除旧的 app/db/ 目录
if [ -d "$DB_SRC" ]; then
    rm -rf "$DB_SRC"
    echo "  已删除: $DB_SRC"
fi

echo "[5/5] 清理 __pycache__ ..."
find "$APP_DIR" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true

echo ""
echo "═══════════════════════════════════════════════════════════"
echo " 验证残留"
echo "═══════════════════════════════════════════════════════════"

r1=$(find "$BACKEND_DIR" -name "*.py" -type f -not -path "*/venv/*" -not -path "*/__pycache__/*" | xargs grep -l "from infra\." 2>/dev/null | wc -l)
r2=$(find "$BACKEND_DIR" -name "*.py" -type f -not -path "*/venv/*" -not -path "*/__pycache__/*" | xargs grep -l "import infra\." 2>/dev/null | wc -l)
r3=$(find "$BACKEND_DIR" -name "*.py" -type f -not -path "*/venv/*" -not -path "*/__pycache__/*" | xargs grep -l "from app\.db\." 2>/dev/null | wc -l)
r4=$(find "$BACKEND_DIR" -name "*.py" -type f -not -path "*/venv/*" -not -path "*/__pycache__/*" | xargs grep -l "import app\.db\." 2>/dev/null | wc -l)

echo "  残留 from infra.:   $r1"
echo "  残留 import infra.: $r2"
echo "  残留 from app.db.:  $r3"
echo "  残留 import app.db.: $r4"

echo ""
echo "  ✅ Phase 1 完成"
echo ""
echo "  新的 infrastructure/:"
find "$INFRA_DST" -name "*.py" -not -path "*/__pycache__/*" | sort | while read f; do
    echo "    ${f#$INFRA_DST/}"
done
