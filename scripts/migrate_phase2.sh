#!/usr/bin/env bash
set -euo pipefail
# ═══════════════════════════════════════════════════════════════════
# Phase 2: services/llm/ + services/materials/ → infrastructure/
# ═══════════════════════════════════════════════════════════════════

APP_DIR="/home/deploy/edu-companion/backend/app"
BACKEND_DIR="/home/deploy/edu-companion/backend"

echo "═══════════════════════════════════════════════════════════"
echo " Phase 2: services/llm/ + services/materials/ → infrastructure/"
echo "═══════════════════════════════════════════════════════════"

# ── Step A: services/llm/ → infrastructure/llm/ ──

echo ""
echo "[A] services/llm/ → infrastructure/llm/"

if [ -d "$APP_DIR/services/llm" ]; then
    mkdir -p "$APP_DIR/infrastructure/llm"
    rsync -a --exclude='__pycache__' "$APP_DIR/services/llm/" "$APP_DIR/infrastructure/llm/"
    
    find "$BACKEND_DIR" -name "*.py" -type f \
        -not -path "*/venv/*" -not -path "*/__pycache__/*" \
        -exec sed -i 's/from app\.services\.llm\./from app.infrastructure.llm./g' {} \;
    find "$BACKEND_DIR" -name "*.py" -type f \
        -not -path "*/venv/*" -not -path "*/__pycache__/*" \
        -exec sed -i 's/import app\.services\.llm/import app.infrastructure.llm/g' {} \;
    
    # 删除旧目录
    rm -rf "$APP_DIR/services/llm"
    echo "   ✓ services/llm/ → infrastructure/llm/"
fi

# ── Step B: services/materials/ → infrastructure/media/ ──

echo ""
echo "[B] services/materials/ → infrastructure/media/"

if [ -d "$APP_DIR/services/materials" ]; then
    mkdir -p "$APP_DIR/infrastructure/media"
    rsync -a --exclude='__pycache__' "$APP_DIR/services/materials/" "$APP_DIR/infrastructure/media/"
    
    find "$BACKEND_DIR" -name "*.py" -type f \
        -not -path "*/venv/*" -not -path "*/__pycache__/*" \
        -exec sed -i 's/from app\.services\.materials\./from app.infrastructure.media./g' {} \;
    find "$BACKEND_DIR" -name "*.py" -type f \
        -not -path "*/venv/*" -not -path "*/__pycache__/*" \
        -exec sed -i 's/import app\.services\.materials/import app.infrastructure.media/g' {} \;
    
    rm -rf "$APP_DIR/services/materials"
    echo "   ✓ services/materials/ → infrastructure/media/"
fi

# ── Step C: embedding_utils → infrastructure/embedding_utils.py ──

echo ""
echo "[C] embedding_utils → infrastructure/embedding_utils.py"

if [ -f "$APP_DIR/services/common/embedding_utils.py" ]; then
    cp "$APP_DIR/services/common/embedding_utils.py" "$APP_DIR/infrastructure/embedding_utils.py"
    
    find "$BACKEND_DIR" -name "*.py" -type f \
        -not -path "*/venv/*" -not -path "*/__pycache__/*" \
        -exec sed -i 's/from app\.services\.common\.embedding_utils import/from app.infrastructure.embedding_utils import/g' {} \;
    
    rm "$APP_DIR/services/common/embedding_utils.py"
    echo "   ✓ embedding_utils.py → infrastructure/embedding_utils.py"
fi

# ── Step D: 更新 services/*/ 中对 llm/materials 的内部引用 ──
#   (例如 services/common/materials_stub.py 引用了 llm_service)
#   上面 sed 已经全量替换了，但需要确保 infrastructure/media/ 内部文件
#   引用 embedding_utils 的路径正确

echo ""
echo "[D] 修复 infrastructure/media/ 内部引用 embedding_utils"

if [ -f "$APP_DIR/infrastructure/media/material_common.py" ]; then
    sed -i 's/from app\.services\.common\.embedding_utils import/from app.infrastructure.embedding_utils import/g' \
        "$APP_DIR/infrastructure/media/material_common.py"
    echo "   ✓ material_common.py 更新"
fi

# ── Step E: 清理 pycache ──

echo ""
echo "[E] 清理 __pycache__"
find "$APP_DIR" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true

echo ""
echo "═══════════════════════════════════════════════════════════"
echo " 验证残留"
echo "═══════════════════════════════════════════════════════════"

r1=$(find "$BACKEND_DIR" -name "*.py" -type f -not -path "*/venv/*" -not -path "*/__pycache__/*" 2>/dev/null | xargs grep -l "from app\.services\.llm\." 2>/dev/null | wc -l)
r2=$(find "$BACKEND_DIR" -name "*.py" -type f -not -path "*/venv/*" -not -path "*/__pycache__/*" 2>/dev/null | xargs grep -l "from app\.services\.materials\." 2>/dev/null | wc -l)
r3=$(find "$BACKEND_DIR" -name "*.py" -type f -not -path "*/venv/*" -not -path "*/__pycache__/*" 2>/dev/null | xargs grep -l "from app\.services\.common\.embedding_utils import" 2>/dev/null | wc -l)

echo "  残留 from app.services.llm.:              $r1"
echo "  残留 from app.services.materials.:         $r2"
echo "  残留 from common.embedding_utils:          $r3"

echo ""
echo "═══════════════════════════════════════════════════════════"
echo " 新的 infrastructure/ 结构"
echo "═══════════════════════════════════════════════════════════"
find "$APP_DIR/infrastructure" -name "*.py" -not -path "*/__pycache__/*" | sort
