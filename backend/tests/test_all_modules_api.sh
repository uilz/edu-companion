#!/usr/bin/env bash
# 全模块 API 联动性测试
# 覆盖: 健康检查 | 对话/知识树 | 练习 | 学习进度 | 资料 | 成就 | 情绪 | 搜索 | 秘书
#
# 用法:
#   bash tests/test_all_modules_api.sh <base_url>
#   如: bash tests/test_all_modules_api.sh http://localhost:8000

BASE="${1:-http://localhost:8000}"
# ⚠️ 必须传入真实 user_id（不能再用 default_user）
USER_ID="${2:?用法: $0 [base_url] <user_id>}"
PASS=0
FAIL=0

pass() { PASS=$((PASS+1)); echo "  ✅ PASS: $1"; }
fail() { FAIL=$((FAIL+1)); echo "  ❌ FAIL: $1 — $2"; }

echo "═══════════════════════════════════════════"
echo "全模块 API 联动性测试"
echo "Base URL: $BASE"
echo "User ID:  $USER_ID"
echo "═══════════════════════════════════════════"

# ═══════════════════════════════════════════
# 1. 健康检查
# ═══════════════════════════════════════════
echo; echo "═══ 1. 健康检查 ═══"
STATUS=$(curl -s -o /dev/null -w "%{http_code}" "$BASE/health" 2>/dev/null || echo "000")
if [ "$STATUS" = "200" ]; then pass "API 可达 ($STATUS)"; else fail "API 不可达" "status=$STATUS"; fi

# ═══════════════════════════════════════════
# 2. 对话系统 — 分区列表
# ═══════════════════════════════════════════
echo; echo "═══ 2. GET /api/conversations/tree/partition ═══"
RESP=$(curl -s "$BASE/api/conversations/tree/partition" 2>/dev/null)
if echo "$RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); assert 'partitions' in d" 2>/dev/null; then
    COUNT=$(echo "$RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); print(len(d.get('partitions',[])))")
    pass "分区列表返回 (count=$COUNT)"
else
    fail "分区列表异常" "${RESP:0:100}"
fi

# 3. 创建临时对话
echo; echo "═══ 3. POST /api/conversations/tree/conversation/temporary ═══"
RESP=$(curl -s -X POST "$BASE/api/conversations/tree/conversation/temporary" 2>/dev/null)
if echo "$RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); assert 'conversation' in d" 2>/dev/null; then
    CONV_ID=$(echo "$RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['conversation']['id'])")
    pass "临时对话创建成功 (id=${CONV_ID:0:8}...)"
else
    CONV_ID=""
    fail "临时对话创建异常" "${RESP:0:100}"
fi

# 4. 对话 — 消息列表
echo; echo "═══ 4. GET /api/conversations/tree/conversation/{id}/messages ═══"
if [ -n "$CONV_ID" ]; then
    RESP=$(curl -s "$BASE/api/conversations/tree/conversation/$CONV_ID/messages?limit=5" 2>/dev/null)
    if echo "$RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); assert 'messages' in d" 2>/dev/null; then
        TOTAL=$(echo "$RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('total',0))")
        pass "消息列表返回 (total=$TOTAL)"
    else
        fail "消息列表异常" "${RESP:0:100}"
    fi
else
    fail "消息列表跳过" "无有效 conversation_id"
fi

# ═══════════════════════════════════════════
# 5. 情绪分析
# ═══════════════════════════════════════════
echo; echo "═══ 5. GET /api/conversations/emotion/stats ═══"
RESP=$(curl -s "$BASE/api/conversations/emotion/stats" 2>/dev/null)
if echo "$RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); assert 'status' in d" 2>/dev/null; then
    STATUS=$(echo "$RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['status'])")
    pass "情绪分析返回 (status=$STATUS)"
else
    fail "情绪分析异常" "${RESP:0:100}"
fi

# ═══════════════════════════════════════════
# 6. 知识树
# ═══════════════════════════════════════════
echo; echo "═══ 6. GET /api/knowledge ═══"
RESP=$(curl -s "$BASE/api/knowledge" 2>/dev/null)
if echo "$RESP" | python3 -c "import sys,json; d=json.load(sys.stdin)" 2>/dev/null; then
    pass "知识树端返回"
else
    fail "知识树异常" "${RESP:0:100}"
fi

# ═══════════════════════════════════════════
# 7. 学习进度
# ═══════════════════════════════════════════
echo; echo "═══ 7. GET /api/progress ═══"
RESP=$(curl -s "$BASE/api/progress?user_id=$USER_ID" 2>/dev/null)
if echo "$RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); assert d is not None" 2>/dev/null; then
    pass "学习进度返回"
else
    fail "学习进度异常" "${RESP:0:100}"
fi

# ═══════════════════════════════════════════
# 8. 练习系统
# ═══════════════════════════════════════════
echo; echo "═══ 8. GET /api/practice ═══"
RESP=$(curl -s "$BASE/api/practice?user_id=$USER_ID" 2>/dev/null)
if echo "$RESP" | python3 -c "import sys,json; d=json.load(sys.stdin)" 2>/dev/null; then
    pass "练习系统返回"
else
    fail "练习系统异常" "${RESP:0:100}"
fi

# ═══════════════════════════════════════════
# 9. 资料管理
# ═══════════════════════════════════════════
echo; echo "═══ 9. GET /api/files ═══"
RESP=$(curl -s "$BASE/api/files?user_id=$USER_ID" 2>/dev/null)
if echo "$RESP" | python3 -c "import sys,json; d=json.load(sys.stdin)" 2>/dev/null; then
    pass "资料列表返回"
else
    fail "资料列表异常" "${RESP:0:100}"
fi

# ═══════════════════════════════════════════
# 10. 成就系统
# ═══════════════════════════════════════════
echo; echo "═══ 10. GET /api/achievements ═══"
RESP=$(curl -s "$BASE/api/achievements?user_id=$USER_ID" 2>/dev/null)
if echo "$RESP" | python3 -c "import sys,json; d=json.load(sys.stdin)" 2>/dev/null; then
    pass "成就列表返回"
else
    fail "成就列表异常" "${RESP:0:100}"
fi

# ═══════════════════════════════════════════
# 11. 统一搜索
# ═══════════════════════════════════════════
echo; echo "═══ 11. GET /api/search?q=test ═══"
RESP=$(curl -s "$BASE/api/search?q=test" 2>/dev/null)
if echo "$RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); assert 'query' in d" 2>/dev/null; then
    pass "搜索接口返回"
else
    fail "搜索接口异常" "${RESP:0:100}"
fi

# ═══════════════════════════════════════════
# 12. 秘书系统（快速复查）
# ═══════════════════════════════════════════
echo; echo "═══ 12. 秘书系统复查 ═══"
TOTAL_CHECK=0
PASS_CHECK=0

# 12a. 提案列表
RESP=$(curl -s "$BASE/api/secretary/proposals/pending?user_id=$USER_ID" 2>/dev/null)
TOTAL_CHECK=$((TOTAL_CHECK+1))
if echo "$RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); assert isinstance(d, list)" 2>/dev/null; then
    PASS_CHECK=$((PASS_CHECK+1))
    pass "提案列表 (count=$(echo "$RESP" | python3 -c "import sys,json; print(len(json.load(sys.stdin)))"))"
else
    fail "提案列表异常" "${RESP:0:80}"
fi

# 12b. 检查器状态
RESP=$(curl -s "$BASE/api/secretary/checker/status" 2>/dev/null)
TOTAL_CHECK=$((TOTAL_CHECK+1))
if echo "$RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); assert 'modules' in d" 2>/dev/null; then
    PASS_CHECK=$((PASS_CHECK+1))
    pass "检查器状态 (modules=$(echo "$RESP" | python3 -c "import sys,json; print(d['module_count'])"))"
else
    fail "检查器状态异常" "${RESP:0:80}"
fi

# 12c. 模块列表
RESP=$(curl -s "$BASE/api/secretary/modules" 2>/dev/null)
TOTAL_CHECK=$((TOTAL_CHECK+1))
if echo "$RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); assert isinstance(d, list) and len(d) > 0" 2>/dev/null; then
    PASS_CHECK=$((PASS_CHECK+1))
    pass "模块列表 (count=$(echo "$RESP" | python3 -c "import sys,json; print(len(json.load(sys.stdin)))"))"
else
    fail "模块列表异常" "${RESP:0:80}"
fi

# 12d. 偏好设置
RESP=$(curl -s "$BASE/api/secretary/preferences?user_id=$USER_ID" 2>/dev/null)
TOTAL_CHECK=$((TOTAL_CHECK+1))
if echo "$RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); assert isinstance(d, dict)" 2>/dev/null; then
    PASS_CHECK=$((PASS_CHECK+1))
    pass "偏好设置返回"
else
    fail "偏好设置异常" "${RESP:0:80}"
fi

# 12e. 手动检查
RESP=$(curl -s -X POST "$BASE/api/secretary/checker/run?user_id=$USER_ID" 2>/dev/null)
TOTAL_CHECK=$((TOTAL_CHECK+1))
if echo "$RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); assert 'proposals_generated' in d or 'status' in d" 2>/dev/null; then
    PASS_CHECK=$((PASS_CHECK+1))
    pass "手动检查 (generated=$(echo "$RESP" | python3 -c "import sys,json; print(d.get('proposals_generated','?'))"))"
else
    fail "手动检查异常" "${RESP:0:80}"
fi

echo "  秘书复查: $PASS_CHECK/$TOTAL_CHECK"

# ═══════════════════════════════════════════
# 汇总
# ═══════════════════════════════════════════
echo
echo "═══════════════════════════════════════════"
echo "API 测试结果: ✅ $PASS  |  ❌ $FAIL  |  总计 $((PASS+FAIL))"
echo "═══════════════════════════════════════════"