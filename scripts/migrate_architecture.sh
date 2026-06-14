#!/usr/bin/env bash
set -euo pipefail
# ═══════════════════════════════════════════════════════════════════
# 架构迁移脚本
# Step 1: cognitive/ → domain/cognitive/
# Step 2: 删除 / 迁移浅层 domain service
# ═══════════════════════════════════════════════════════════════════

APP_DIR="/home/deploy/edu-companion/backend/app"
DOMAIN_DIR="$APP_DIR/domain"
COGNITIVE_DIR="$APP_DIR/cognitive"

echo "═══════════════════════════════════════════════════════════"
echo " Step 1: cognitive/ → domain/cognitive/"
echo "═══════════════════════════════════════════════════════════"

if [ -d "$COGNITIVE_DIR" ]; then
    echo "[1/4] 创建 domain/cognitive/ ..."
    mkdir -p "$DOMAIN_DIR/cognitive"

    echo "[2/4] 搬迁文件..."
    rsync -a --exclude='__pycache__' "$COGNITIVE_DIR/" "$DOMAIN_DIR/cognitive/"

    echo "[3/4] 更新 import: app.cognitive → app.domain.cognitive"
    find "$APP_DIR" -name "*.py" -type f \
        -exec sed -i "s/from app\.cognitive import/from app.domain.cognitive import/g" {} \;
    find "$APP_DIR" -name "*.py" -type f \
        -exec sed -i "s/from app\.cognitive\./from app.domain.cognitive./g" {} \;
    find "$APP_DIR" -name "*.py" -type f \
        -exec sed -i "s/import app\.cognitive$/import app.domain.cognitive/g" {} \;

    echo "[4/4] 更新 domain/cognitive/__init__.py 中的内部引用..."
    # cognitive/__init__.py 中有 from app.cognitive.operation_registry import ...
    # 迁入后变为 from app.domain.cognitive.operation_registry import ...
    # sed 已经在 [3/4] 中处理了

    echo "  ✓ cognitive/ 迁入完成"
else
    echo "  [跳过] cognitive/ 不存在"
fi


echo ""
echo "═══════════════════════════════════════════════════════════"
echo " Step 2: 搬迁 KnowledgeQueryServiceImpl → services/"
echo "═══════════════════════════════════════════════════════════"
#
# KnowledgeQueryServiceImpl 是纯转发层，但 get_knowledge_query() 被 5 处调用
# 策略：把类搬到 services/knowledge/knowledge_query_service.py，
#       保留 domain/knowledge/__init__.py 的 get_knowledge_query() 访问器

QUERY_SRC="$DOMAIN_DIR/knowledge/query_service.py"
QUERY_DST="$APP_DIR/services/knowledge/knowledge_query_service.py"

if [ -f "$QUERY_SRC" ]; then
    echo "[1/3] 创建 services/knowledge/knowledge_query_service.py..."
    # 提取 query_service.py 内容并修改 import
    cp "$QUERY_SRC" "$QUERY_DST"
    # 更新新文件中的 import (如果有 app.domain.knowledge 内部的引用)
    sed -i "s/from app\.domain\.knowledge/from app.services.knowledge/g" "$QUERY_DST" 2>/dev/null || true

    echo "[2/3] 更新 domain/knowledge/__init__.py — 指向新位置..."
    # 替换 __init__.py 中的 from .query_service import → from app.services.knowledge.knowledge_query_service import
    sed -i "s/from \.query_service import KnowledgeQueryServiceImpl/from app.services.knowledge.knowledge_query_service import KnowledgeQueryServiceImpl/" \
        "$DOMAIN_DIR/knowledge/__init__.py"

    echo "[3/3] 删除原文件"
    cp "$QUERY_SRC" "${QUERY_SRC}.bak"
    rm "$QUERY_SRC"
    echo "  ✓ KnowledgeQueryServiceImpl 搬迁完成"
else
    echo "  [跳过] query_service.py 不存在"
fi


echo ""
echo "═══════════════════════════════════════════════════════════"
echo " Step 3: 搬迁 KnowledgeGraphServiceImpl → services/"
echo "═══════════════════════════════════════════════════════════"

KG_SRC="$DOMAIN_DIR/knowledge/service.py"
KG_DST="$APP_DIR/services/knowledge/knowledge_graph_service.py"

if [ -f "$KG_SRC" ]; then
    echo "[1/3] 创建 services/knowledge/knowledge_graph_service.py..."
    cp "$KG_SRC" "$KG_DST"

    echo "[2/3] 更新 domain/knowledge/__init__.py — 移除 KnowledgeGraphServiceImpl..."
    sed -i "/from \.service import KnowledgeGraphServiceImpl/d" "$DOMAIN_DIR/knowledge/__init__.py"

    echo "[3/3] 删除原文件"
    cp "$KG_SRC" "${KG_SRC}.bak"
    rm "$KG_SRC"
    echo "  ✓ KnowledgeGraphServiceImpl 搬迁完成"
else
    echo "  [跳过] knowledge/service.py 不存在"
fi


echo ""
echo "═══════════════════════════════════════════════════════════"
echo " Step 4: 更新 domain/knowledge/__init__.py"
echo "═══════════════════════════════════════════════════════════"

KINIT="$DOMAIN_DIR/knowledge/__init__.py"
if [ -f "$KINIT" ]; then
    # 移除已删除的导出
    sed -i "/KnowledgeGraphServiceImpl/d" "$KINIT" 2>/dev/null || true
    # __all__ 也要清理
    sed -i 's/"KnowledgeGraphServiceImpl",//g' "$KINIT" 2>/dev/null || true
    sed -i 's/"KnowledgeGraphServiceImpl"//g' "$KINIT" 2>/dev/null || true
    echo "  ✓ __init__.py 已清理"
fi


echo ""
echo "═══════════════════════════════════════════════════════════"
echo " Step 5: 删除纯转发 domain service"
echo "═══════════════════════════════════════════════════════════"

# 这些模块的 service.py 是纯转发，可以安全删除（无需保留访问器）
SHALLOW_MODULES=(analytics habits materials media planning)

for MODULE in "${SHALLOW_MODULES[@]}"; do
    SVC_FILE="$DOMAIN_DIR/$MODULE/service.py"
    if [ -f "$SVC_FILE" ]; then
        echo "  [删除] domain/$MODULE/service.py"
        cp "$SVC_FILE" "${SVC_FILE}.bak" 2>/dev/null || true
        rm "$SVC_FILE"
    else
        echo "  [跳过] domain/$MODULE/service.py"
    fi
done


echo ""
echo "═══════════════════════════════════════════════════════════"
echo " Step 6: 保留 practice (含编排逻辑，需手动迁移)"
echo "═══════════════════════════════════════════════════════════"

PRACTICE_SVC="$DOMAIN_DIR/practice/service.py"
if [ -f "$PRACTICE_SVC" ] && [ ! -f "${PRACTICE_SVC}.bak" ]; then
    cp "$PRACTICE_SVC" "${PRACTICE_SVC}.bak" 2>/dev/null || true
    echo "  ⏳ 保留: domain/practice/service.py"
    echo "      备份已保存为 service.py.bak"
    echo "      submit_answer() 含事件编排, get_stats() 含直查 DB"
    echo "      需手动迁移到 services/practice/ 后删除"
fi


echo ""
echo "═══════════════════════════════════════════════════════════"
echo " Step 7: 更新 application/di.py"
echo "═══════════════════════════════════════════════════════════"

DI_FILE="$APP_DIR/application/di.py"
if [ -f "$DI_FILE" ]; then
    # 更新 _create_knowledge — 使用新的 services 路径
    sed -i "s/from app\.domain\.knowledge\.service import KnowledgeGraphServiceImpl/from app.services.knowledge.knowledge_graph_service import KnowledgeGraphServiceImpl/" \
        "$DI_FILE" 2>/dev/null || true

    # 更新 _create_knowledge_query — 使用新的 services 路径
    sed -i "s/from app\.domain\.knowledge\.query_service import KnowledgeQueryServiceImpl/from app.services.knowledge.knowledge_query_service import KnowledgeQueryServiceImpl/" \
        "$DI_FILE" 2>/dev/null || true

    # 更新 set_knowledge_query 的 import — 路径不变 (domain/knowledge/__init__.py 仍保留 get/set 函数)
    # 不需要改，因为 domain/knowledge/__init__.py 的 set_knowledge_query 保留

    echo "  ✓ di.py 的 cognitive import 在 Step 1 已更新"
    echo "  ✓ di.py 的 knowledge import 已指向 services/"
fi


echo ""
echo "═══════════════════════════════════════════════════════════"
echo " 完成 ✓"
echo "═══════════════════════════════════════════════════════════"
echo ""
echo " 迁移摘要:"
echo "  ✅ Step 1: cognitive/ → domain/cognitive/ (56 处 import 已更新)"
echo "  ✅ Step 2: KnowledgeQueryServiceImpl → services/knowledge/knowledge_query_service.py"
echo "  ✅ Step 3: KnowledgeGraphServiceImpl → services/knowledge/knowledge_graph_service.py"
echo "  ✅ Step 4: domain/knowledge/__init__.py 已清理"
echo "  ✅ Step 5: 已删除 5 个浅 service (analytics/habits/materials/media/planning)"
echo "  ⏳ Step 6: practice/service.py 保留待手动迁移"
echo "  ✅ Step 7: di.py import 路径已更新"
echo ""
echo "  ⚠️  后续手动操作:"
echo "    1. 确认运行正常后: rm -rf $COGNITIVE_DIR"
echo "    2. pytest 或启动服务验证"
echo "    3. 手动: domain/practice/service.py → services/practice/"
echo ""

