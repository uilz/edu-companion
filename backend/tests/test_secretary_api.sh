#!/usr/bin/env bash
# 伴学系统 — API 级联动性测试脚本
# Phase 1 反馈循环: curl-based pass/fail 信号
#
# 用法:
#   bash tests/test_secretary_api.sh <base_url>
#   如: bash tests/test_secretary_api.sh http://localhost:8000

BASE="${1:-http://localhost:8000}"
USER_ID="${2:-default_user}"
PASS=0
FAIL=0

pass() { PASS=$((PASS+1)); echo "  ✅ PASS: $1"; }
fail() { FAIL=$((FAIL+1)); echo "  ❌ FAIL: $1 — $2"; }

echo "═══════════════════════════════════════════"
echo "伴学系统 API 联动性测试"
echo "Base URL: $BASE"
echo "User ID:  $USER_ID"
echo "═══════════════════════════════════════════"

# ── 1. 健康检查 ──
echo; echo "═══ 1. 健康检查 ═══"
STATUS=$(curl -s -o /dev/null -w "%{http_code}" "$BASE/health" 2>/dev/null || echo "000")
if [ "$STATUS" = "200" ]; then pass "API 可达 ($STATUS)"; else fail "API 不可达" "status=$STATUS"; fi

# ── 2. 获取 pending 提案 ──
echo; echo "═══ 2. GET /api/secretary/proposals/pending ═══"
RESP=$(curl -s "$BASE/api/secretary/proposals/pending?user_id=$USER_ID" 2>/dev/null)
if echo "$RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); assert isinstance(d, list)" 2>/dev/null; then
    COUNT=$(echo "$RESP" | python3 -c "import sys,json; print(len(json.load(sys.stdin)))")
    pass "提案列表返回 (count=$COUNT)"
else
    fail "提案列表异常" "${RESP:0:100}"
fi

# ── 3. 检查 checker 状态 ──
echo; echo "═══ 3. GET /api/secretary/checker/status ═══"
RESP=$(curl -s "$BASE/api/secretary/checker/status?user_id=$USER_ID" 2>/dev/null)
if echo "$RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); assert 'module_count' in d" 2>/dev/null; then
    COUNT=$(echo "$RESP" | python3 -c "import sys,json; print(json.load(sys.stdin)['module_count'])")
    INT=$(echo "$RESP" | python3 -c "import sys,json; print(json.load(sys.stdin).get('check_interval',0))")
    pass "状态返回 (modules=$COUNT, interval=${INT}s)"
else
    fail "状态接口异常" "${RESP:0:100}"
fi

# ── 4. 手动触发主动检查 ──
echo; echo "═══ 4. POST /api/secretary/checker/run ═══"
RESP=$(curl -s -X POST "$BASE/api/secretary/checker/run?user_id=$USER_ID" 2>/dev/null)
if echo "$RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); assert 'proposals_generated' in d or 'status' in d" 2>/dev/null; then
    GEN=$(echo "$RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('proposals_generated','?'))")
    pass "手动检查返回 (proposals_generated=$GEN)"
else
    fail "手动检查异常" "${RESP:0:100}"
fi

# ── 5. 获取 onboard 状态 ──
echo; echo "═══ 5. GET /api/secretary/onboarding ═══"
RESP=$(curl -s "$BASE/api/secretary/onboarding?user_id=$USER_ID" 2>/dev/null)
if echo "$RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); assert isinstance(d, dict)" 2>/dev/null; then
    pass "onboarding 返回"
else
    fail "onboarding 异常" "${RESP:0:100}"
fi

# ── 6. 模块列表 ──
echo; echo "═══ 6. GET /api/secretary/modules ═══"
RESP=$(curl -s "$BASE/api/secretary/modules?user_id=$USER_ID" 2>/dev/null)
if echo "$RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); assert isinstance(d, list)" 2>/dev/null; then
    MOD_NAMES=$(echo "$RESP" | python3 -c "import sys,json; print([m['name'] for m in json.load(sys.stdin) if 'name' in m])")
    pass "模块列表返回 ($MOD_NAMES)"
else
    fail "模块列表异常" "${RESP:0:100}"
fi

# ── 7. 提议生成 (LLM) ──
echo; echo "═══ 7. POST /api/secretary/generate-llm-proposals ═══"
RESP=$(curl -s -X POST "$BASE/api/secretary/generate-llm-proposals?user_id=$USER_ID" 2>/dev/null)
if echo "$RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); assert isinstance(d, list)" 2>/dev/null; then
    pass "LLM 生成返回 (count=$(echo "$RESP" | python3 -c "import sys,json; print(len(json.load(sys.stdin)))"))"
else
    fail "LLM 生成异常" "${RESP:0:100}"
fi

# ── 8. 通知偏好接口 ──
echo; echo "═══ 8. GET /api/secretary/preferences ═══"
RESP=$(curl -s "$BASE/api/secretary/preferences?user_id=$USER_ID" 2>/dev/null)
if echo "$RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); assert isinstance(d, dict)" 2>/dev/null; then
    pass "偏好设置返回"
else
    fail "偏好设置异常" "${RESP:0:100}"
fi

echo; echo "═══════════════════════════════════════════"
echo "API 测试结果: ✅ $PASS  |  ❌ $FAIL  |  总计 $((PASS+FAIL))"
echo "═══════════════════════════════════════════"
exit $((FAIL > 0 ? 1 : 0))