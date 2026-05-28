# Edu-Companion Backend — Dead Code Audit Report

**Date:** 2026-05-28  
**Scope:** `backend/app/` directory (excluding tests/, venv/)  
**Method:** AST-based static analysis + manual verification of cross-file references

---

## 📋 状态更新 (2026-05-28)

本审计报告中的大部分问题已在 Phase R4-R6 重构中修复：

- ✅ **68 项 unused imports** — 已在 Phase R4 清理完成
- ✅ **3 deprecated files** — 已标记 DEPRECATED（`migrate_to_cognitive.py`、`migrate_materials.py`、`secretary_schema.sql`）
- ✅ **3 deprecated no-op functions** — `knowledge_trace.py` 已重写为 CognitiveNode 实现（Phase R5）
- ✅ **6 unused functions** — 已清理或标记
- ✅ **12 unused imports in cognitive/events.py** — 已清理
- ✅ **12 unused imports in api/practice.py** — 已清理

### 仍需关注
- ⚠️ **6 个 deprecated schema fields** — 保留但标记，后续版本移除
- ⚠️ **1 empty stub handler** — `AchievementEngine.__init__()`，无影响

## 1. Unused Imports (68 findings across 35 files)

| # | File | Line | Unused Import | Severity |
|---|------|------|---------------|----------|
| 1 | `app/main.py` | 14 | `asynccontextmanager` | Medium |
| 2 | `app/config.py` | 8 | `os` | Low |
| 3 | `app/config.py` | 10 | `Optional` | Low |
| 4 | `app/core/knowledge_trace.py` | 13 | `ErrorType` | Medium |
| 5 | `app/core/knowledge_trace.py` | 13 | `KnowledgeDimension` | Medium |
| 6 | `app/cognitive/events.py` | 14 | `calc_dynamic_load` | **High** |
| 7 | `app/cognitive/events.py` | 26 | `Composition` | **High** |
| 8 | `app/cognitive/events.py` | 26 | `DeepProcessing` | **High** |
| 9 | `app/cognitive/events.py` | 26 | `Diagnostic` | **High** |
| 10 | `app/cognitive/events.py` | 26 | `Engagement` | **High** |
| 11 | `app/cognitive/events.py` | 26 | `GoalAlignment` | **High** |
| 12 | `app/cognitive/events.py` | 26 | `Metacognition` | **High** |
| 13 | `app/cognitive/events.py` | 26 | `Prediction` | **High** |
| 14 | `app/cognitive/events.py` | 26 | `Scheduling` | **High** |
| 15 | `app/cognitive/events.py` | 26 | `Trend` | **High** |
| 16 | `app/cognitive/events.py` | 46 | `get_nodes_by_level` | **High** |
| 17 | `app/cognitive/events.py` | 46 | `search_nodes` | **High** |
| 18 | `app/cognitive/migrate_to_cognitive.py` | 28 | `datetime` | Low (deprecated file) |
| 19 | `app/cognitive/migrate_to_cognitive.py` | 28 | `timezone` | Low (deprecated file) |
| 20 | `app/cognitive/migrate_to_cognitive.py` | 30 | `Any` | Low (deprecated file) |
| 21 | `app/cognitive/migrate_to_cognitive.py` | 30 | `Optional` | Low (deprecated file) |
| 22 | `app/cognitive/migrate_to_cognitive.py` | 206 | `Associate` | Low (deprecated file) |
| 23 | `app/cognitive/migrate_to_cognitive.py` | 259 | `PracticeEvent` | Low (deprecated file) |
| 24 | `app/cognitive/migrate_to_cognitive.py` | 259 | `Associate` | Low (deprecated file) |
| 25 | `app/cognitive/models.py` | 9 | `datetime` | Low |
| 26 | `app/cognitive/storage.py` | 15 | `UserCognitiveState` | Medium |
| 27 | `app/cognitive/storage.py` | 22 | `Database` | Medium |
| 28 | `app/cognitive/link_storage.py` | 5 | `Optional` | Low |
| 29 | `app/cognitive/growth_engine.py` | 15 | `get_children` | Medium |
| 30 | `app/db/database.py` | 13 | `time` | Medium |
| 31 | `app/db/database.py` | 14 | `uuid` | Medium |
| 32 | `app/db/database.py` | 15 | `datetime` | Medium |
| 33 | `app/db/database.py` | 30 | `psycopg2` (duplicate) | **High** |
| 34 | `app/domain/secretary/analysis.py` | 19 | `Any` | Low |
| 35 | `app/domain/secretary/analysis.py` | 21 | `get_node` | Medium |
| 36 | `app/domain/secretary/analysis.py` | 21 | `get_nodes_by_level` | Medium |
| 37 | `app/domain/secretary/secretary_service.py` | 19 | `SecretaryPrefs` | Medium |
| 38 | `app/domain/secretary/secretary_service.py` | — | `json`, `os` | Low |
| 39 | `app/domain/secretary/proposal_store.py` | 17 | `SecretaryPrefs` | Medium |
| 40 | `app/domain/secretary/proposal_store.py` | — | `time` | Low |
| 41 | `app/domain/secretary/models.py` | 12 | `datetime` | Low |
| 42 | `app/domain/secretary/engines/proposal_generator.py` | 13 | `Any` | Low |
| 43 | `app/domain/secretary/engines/proposal_generator.py` | 16 | `ScoredInsight` | Medium |
| 44 | `app/domain/secretary/engines/proposal_generator.py` | 16 | `ScopeSpec` | Medium |
| 45 | `app/domain/secretary/engines/proposal_generator.py` | 22 | `find_weakness_clusters` | **High** |
| 46 | `app/domain/secretary/engines/proposal_generator.py` | 22 | `rank_forgetting_risk` | **High** |
| 47 | `app/domain/secretary/engines/proposal_generator.py` | 22 | `find_overdue_reviews` | **High** |
| 48 | `app/domain/secretary/engines/proposal_generator.py` | 22 | `analyze_error_patterns` | **High** |
| 49 | `app/domain/secretary/engines/module_registry.py` | 21 | `field` | Medium |
| 50 | `app/domain/secretary/engines/module_registry.py` | 24 | `ScoredInsight` | Medium |
| 51 | `app/domain/secretary/engines/builtin_lateral_expansion.py` | 9 | `Any` | Low |
| 52 | `app/domain/secretary/engines/builtin_daily_brief.py` | 21 | `ScoredInsight` | Medium |
| 53 | `app/domain/secretary/engines/builtin_daily_brief.py` | — | `asyncio` | Low |
| 54 | `app/domain/secretary/engines/builtin_fatigue_manager.py` | — | `Any`, `ScoredInsight`, `datetime`, `timezone` | Low |
| 55 | `app/domain/secretary/engines/builtin_review_reminder.py` | — | `Any`, `ScoredInsight`, `datetime`, `timezone` | Low |
| 56 | `app/domain/secretary/engines/context_engine.py` | — | `Any`, `ScopeSpec`, `time` | Low |
| 57 | `app/domain/secretary/engines/diagnosis.py` | — | `Proposal`, `SecretaryPrefs`, `analyze_error_patterns` | Medium |
| 58 | `app/domain/secretary/engines/exam_mode.py` | 17 | `timezone` | Low |
| 59 | `app/domain/secretary/engines/llm_proposal_generator.py` | — | `Any` | Low |
| 60 | `app/domain/secretary/engines/meta_cognitive_prompt.py` | — | `datetime`, `timezone` | Low |
| 61 | `app/domain/secretary/engines/proposal_action_handler.py` | — | `json`, `time` | Low |
| 62 | `app/domain/secretary/engines/active_checker.py` | — | `SessionContext`, `time` | Medium |
| 63 | `app/api/practice.py` | 16 | 12 unused schema imports (see note 1) | **High** |
| 64 | `app/api/progress.py` | — | `DEFAULT_USER_ID`, `HTTPException` | Medium |
| 65 | `app/api/achievements.py` | — | `HTTPException` | Low |
| 66 | `app/api/conversation.py` | — | `classifier`, `os` | Low |
| 67 | `app/services/conversation_llm.py` | — | `Conversation`, `Partition`, `SYSTEM_PROMPT` | Medium |
| 68 | `app/services/phase8_classifier.py` | — | `get_node` | Medium |

> **Note 1:** `app/api/practice.py` imports 12 schema types that are unused: `AttemptRecord`, `CoverageGap`, `DailyStat`, `ErrorAnalysis`, `ErrorBookEntry`, `ErrorType`, `Material`, `MaterialChunk`, `PracticeStats`, `QuestionOption`, `ReviewTask`, `SessionStatus`, `SkillStat`

---

## 2. Deprecated Files (Should Be Removed)

| # | File | Status | Notes |
|---|------|--------|-------|
| 1 | `app/cognitive/migrate_to_cognitive.py` | **DEPRECATED** | 530-line migration script. Migration completed in Phase 6. File explicitly says "请不要再执行". Never imported by any active code. |
| 2 | `app/db/migrate_materials.py` | **DEPRECATED** | 26-line no-op. Documented as replaced by `database.py _migrate()`. Never imported. |
| 3 | `app/db/secretary_schema.sql` | **DEPRECATED** | All SQL commented out. Not referenced by any Python code. Schema now lives inline in `app/api/secretary.py`. |

---

## 3. Deprecated Functions (Still Called But Are No-Ops)

| # | File:Line | Function | Status | Called From |
|---|-----------|----------|--------|-------------|
| 1 | `core/knowledge_trace.py:261` | `BKTEngine.save_state()` | **No-op (pass)** | `api/practice.py:363` |
| 2 | `core/knowledge_trace.py:265` | `BKTEngine.load_all_states()` | **Returns `{}`** | `api/study.py:173`, `api/practice.py:585,672`, `api/achievements.py:43` |
| 3 | `core/knowledge_trace.py:246` | `BKTEngine.load_or_create()` | **Creates fresh (no DB read)** | `api/study.py:201`, `api/practice.py:361`, `api/knowledge.py:60` |

**Impact:** These deprecated functions are called from live API endpoints, meaning:
- `save_state()` silently discards BKT updates
- `load_all_states()` always returns empty, so study recommendations and achievement checks get no data
- `load_or_create()` always creates fresh state, losing any prior BKT estimates

---

## 4. Unused Functions/Methods

| # | File:Line | Function | Notes |
|---|-----------|----------|-------|
| 1 | `core/knowledge_trace.py:236` | `BKTEngine.compute_forgetting_prob()` | Never called anywhere in the codebase |
| 2 | `core/knowledge_trace.py:188` | `BKTEngine.predict_correct_prob()` | Never called anywhere in the codebase |
| 3 | `core/knowledge_trace.py:50` | `BKTEngine._get_storage()` | Never called anywhere in the codebase |
| 4 | `db/database.py:328` | `Database.insert_returning()` | Never called anywhere in the codebase |
| 5 | `db/database.py:378` | `Database._deserialize()` | Never called anywhere in the codebase |
| 6 | `shared/protocols/achievements.py:10` | `AchievementService` protocol | Defined but never referenced |

---

## 5. Duplicate/Redundant Code

| # | File | Lines | Issue |
|---|------|-------|-------|
| 1 | `app/db/database.py` | 22-23 vs 30-32 | **Duplicate imports**: `from psycopg2 import pool` and `from psycopg2.extras import RealDictCursor` appear twice |
| 2 | `app/db/database.py` | 28 vs 34 | **Duplicate logger**: `logger = logging.getLogger(__name__)` defined twice |
| 3 | `app/db/database.py` | 30 | **Duplicate `import psycopg2`**: already imported via `from psycopg2 import pool` on line 22 |

---

## 6. Empty/Stub Handlers

| # | File:Line | Function | Notes |
|---|-----------|----------|-------|
| 1 | `app/services/achievement_engine.py:128` | `AchievementEngine.__init__()` | Empty `pass` — class has no state to initialize, could use `__init_subclass__` or remove |

---

## 7. Deprecated Schema Fields (Still Present)

| # | File:Line | Field | Notes |
|---|-----------|-------|-------|
| 1 | `schemas/conversation.py:286` | `Conversation.knowledge_states` | Marked DEPRECATED, still in schema |
| 2 | `schemas/conversation.py:287` | `Conversation.practice_sessions` | Marked DEPRECATED (Phase A2) |
| 3 | `schemas/conversation.py:289` | `Conversation.error_book` | Marked DEPRECATED (Phase A2) |
| 4 | `schemas/learner.py:69` | `LearnerProfile.knowledge_states` | Marked DEPRECATED, still in schema |
| 5 | `schemas/learner.py:77` | `LearnerProfile.knowledge_states` | Marked DEPRECATED (Phase A1) |
| 6 | `shared/protocols/practice.py:72` | `PracticeService.get_all_knowledge_states()` | Marked DEPRECATED |

---

## 8. Priority Recommendations

### Immediate (High Impact)
1. **Remove deprecated no-op functions** from `knowledge_trace.py` or implement them against CognitiveNode
2. **Remove unused imports** in `cognitive/events.py` (12 unused imports) and `api/practice.py` (12 unused imports)
3. **Delete duplicate imports** in `db/database.py`
4. **Delete the 3 deprecated files** (`migrate_to_cognitive.py`, `migrate_materials.py`, `secretary_schema.sql`)

### Short-Term (Code Quality)
5. Clean up all unused imports across the 35 affected files
6. Remove `compute_forgetting_prob()`, `predict_correct_prob()`, `_get_storage()` from `BKTEngine`
7. Remove unused `insert_returning()` and `_deserialize()` from `Database`
8. Remove or implement the `AchievementService` protocol

### Long-Term (Architecture)
9. Evaluate whether deprecated schema fields can be removed
10. Audit the `knowledge_states` parameter threading through `zpd_scheduler.py`
