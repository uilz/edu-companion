# Backend Codebase Audit Report

**Date**: 2026-05-26  
**Project**: edu-companion/backend (Python 3.11, FastAPI, PostgreSQL + pgvector)  
**Files scanned**: 176 Python files across app/, domain/, shared/, infra/, tests/

---

## 1. BROKEN IMPORTS

### HIGH: `shared.schemas.*` does not exist

| File | Line | Description |
|------|------|-------------|
| `shared/protocols/__init__.py` | 15 | `from shared.schemas.practice import Question, PracticeSession, SubmitResult, KnowledgeState` — no `shared/schemas/` directory exists |
| `shared/protocols/__init__.py` | 16 | `from shared.schemas.conversation import Message, Branch, Partition` |
| `shared/protocols/__init__.py` | 17 | `from shared.schemas.learner import StudyPlan, DailyGoal, LearnerProfile, ProgressSummary` |

**Impact**: These are inside `if TYPE_CHECKING:` guard, so they won't fail at runtime, but type checking/mypy will fail. The actual schemas live in `app/schemas/`.

---

### LOW: Domain namespace packages lack `__init__.py`

| File | Issue | Description |
|------|-------|-------------|
| `domain/knowledge/` | Missing `__init__.py` | Works via PEP 420 implicit namespaces but fragile |
| `domain/practice/` | Missing `__init__.py` | Same |
| `domain/conversation/` | Missing `__init__.py` | Same |
| `domain/materials/` | Missing `__init__.py` | Same |
| `domain/media/` | Missing `__init__.py` | Same |
| `domain/analytics/` | Missing `__init__.py` | Same |
| `domain/habits/` | Missing `__init__.py` | Same |
| `domain/planning/` | Missing `__init__.py` | Same |
| `app/domain/data/` | Missing `__init__.py` | Dead directory under app/domain/ |
| `app/domain/learning/` | Missing `__init__.py` | Likely dead — only `shared_knowledge.py` inside |

**Note**: Only `domain/multimedia/` and `app/domain/secretary/` have proper `__init__.py` files. All others rely on implicit namespace packages (PEP 420, Python 3.3+).

---

## 2. TODO / FIXME / HACK MARKERS

### MEDIUM: Unimplemented stubs in domain/practice/service.py

| File | Line | Severity | Description |
|------|------|----------|-------------|
| `domain/practice/service.py` | 202 | MEDIUM | `# TODO: 调用 LLM via question_generator` — question generation not implemented |
| `domain/practice/service.py` | 219 | MEDIUM | `# TODO: 从 attempts 表聚合` — stats aggregation from DB not done |
| `domain/practice/service.py` | 223 | MEDIUM | `# TODO: 调用 analytics service` — behavior report not connected |

### LOW: Future upgrade note

| File | Line | Severity | Description |
|------|------|----------|-------------|
| `infra/event_bus.py` | 9 | LOW | `- TODO: 后续可替换为 Redis Pub/Sub 或 Kafka` — in-memory event bus, planned upgrade |

---

## 3. DEPRECATED SCHEMAS

### MEDIUM: Duplicate `KnowledgeState` in app/schemas/

| File | Model | Description |
|------|-------|-------------|
| `app/schemas/practice.py:93` | `KnowledgeState` | V2 version — rich multi-dim with `dimensions`, `explanation_state`, BKT params |
| `app/schemas/learner.py:53` | `KnowledgeState` | Simpler BKT-only version — no dimensions, no explanation_state |

These two `KnowledgeState` models define different schemas for the same concept. The `practice.py` version is richer (multidimensional), while `learner.py` version is simpler (BKT only). If both are used as API response models, clients will get inconsistent structures depending on which endpoint they hit.

---

## 4. ORPHAN DB TABLES & SCHEMA ISSUES

### MEDIUM: Multiple competing `materials` table definitions

| File | Schema |
|------|--------|
| `app/db/database.py:152` | `materials` — TEXT PK, `skills_covered_json JSONB`, `purpose` defaults to `'session'` |
| `app/db/migrate_materials.py:16` | `materials` — UUID PK via `gen_random_uuid()`, `skills_covered TEXT[]`, `purpose` defaults to `'permanent'` |

The `database.py` runs first on startup, then `migrate_materials.py` would attempt to CREATE TABLE IF NOT EXISTS with a different schema (UUID vs TEXT PK). Since `database.py` runs first, the migrate_materials.py version will be skipped (table already exists) — but the migration script's schema expectations will never be met.

### LOW: `secretary_proposals` table defined twice

| File | Schema |
|------|--------|
| `app/db/secretary_schema.sql:7` | UUID PK, `proposal JSONB` — intended for migration |
| `app/api/secretary.py:97` | TEXT PK, flat columns — created on-demand at runtime |

The SQL migration file defines it one way, but the API code creates it inline with a completely different schema. The API inline version wins (tables created on first access), making the SQL file stale.

### Tables defined across the codebase:

| Table | Defined in | Also used in |
|-------|-----------|-------------|
| `knowledge_states` | `app/db/database.py:50` | N/A |
| `questions` | `app/db/database.py:69` | N/A |
| `practice_sessions` | `app/db/database.py:91` | N/A |
| `attempts` | `app/db/database.py:109` | N/A |
| `error_book` | `app/db/database.py:134` | N/A |
| `materials` | `app/db/database.py:152` + `app/db/migrate_materials.py:16` | **DUPLICATE** |
| `material_chunks` | `app/db/database.py:170` + `app/db/migrate_materials.py:34` | **DUPLICATE** |
| `conversation_partitions` | `app/db/conversation_schema.sql:5` | N/A |
| `conversation_branches` | `app/db/conversation_schema.sql:26` | N/A |
| `conversation_nodes` | `app/db/conversation_schema.sql:45` | N/A |
| `conversation_response_blocks` | `app/db/conversation_schema.sql:69` | N/A |
| `conversation_link_nodes` | `app/db/conversation_schema.sql:85` | N/A |
| `conversation_user_meta` | `app/db/conversation_schema.sql:97` | N/A |
| `cognitive_nodes` | `app/db/cognitive_schema.sql:9` | N/A |
| `cognitive_events` | `app/db/cognitive_schema.sql:69` | N/A |
| `knowledge_edges` | `app/scripts/migrate_phase8.sql:38` | N/A |
| `conversation_node_links` | `app/scripts/migrate_phase8.sql:61` | N/A |
| `chunk_review_queue` | `app/db/migrate_materials.py:65` | N/A |
| `plan_snapshots` | `app/services/adaptive_planner.py:167` | Inline CREATE |
| `secretary_proposals` | `app/api/secretary.py:97` + `app/db/secretary_schema.sql:7` | **DUPLICATE** (different schemas) |

---

## 5. HARDCODED `"default_user"` VALUES

### HIGH: Widespread hardcoded user_id="default_user"

**Scope**: ~40 occurrences across the codebase

| File | Lines | Description |
|------|-------|-------------|
| `app/api/chat.py` | 96 | `user_id = "default_user"` in WebSocket handler |
| `app/api/secretary.py` | 137 | `user_id: str = "default_user"` as default param |
| `domain/practice/service.py` | 123, 137, 156, 172, 183 | Hardcoded in KnowledgeState operations |
| `domain/knowledge/checker.py` | 57 | Hardcoded in test-like code path |
| `app/db/repository.py` | 122, 144, 173, 209, 234, 251 | Fallback to `"default_user"` in DB calls |
| `app/cognitive/*.py` | 30+ occurrences | Almost every function defaults to `"default_user"` |
| `app/domain/secretary/**/*.py` | 5+ occurrences | Various modules default to `"default_user"` |

**Impact**: MVP single-user assumption. Cannot support multi-user without audit.

---

## 6. OVERLAPPING API ROUTES

### MEDIUM: Four routers share prefix `/api/practice`

| File | Router Prefix | Sample Routes |
|------|--------------|---------------|
| `app/api/practice.py` | `/api/practice` | `/questions`, `/sessions`, `/submit` |
| `app/api/practice_errors.py` | `/api/practice` | `/errors`, `/errors/{id}/review` |
| `app/api/practice_analytics.py` | `/api/practice` | `/stats`, `/behavior` |
| `app/api/practice_quality.py` | `/api/practice` | `/quality`, `/quality/worst` |

FastAPI merges these without error, but route conflicts are possible if path patterns overlap.

### LOW: conversation.py has zero-prefix router, mounted at runtime

| File | Router Prefix | Mounted At | Notes |
|------|--------------|------------|-------|
| `app/api/conversation.py` | `(none)` | `app.include_router(conversation_router, prefix="/api/conversations")` | All routes defined as `/tree/...`, `/workspace/...` etc. with no prefix in router |

---

## 7. DEAD / ORPHAN CODE

### MEDIUM: Orphan agent classes

| File | Class | Status |
|------|-------|--------|
| `app/agents/base.py:19` | `BaseAgent` | Defined but never imported by any other module |
| `app/agents/coach.py:22` | `CoachAgent` | Defined but never imported |
| `app/agents/tutor.py:22` | `TutorAgent` | Defined but never imported |

These agent classes exist in `app/agents/` but the actual orchestration uses `app/core/orchestrator.py` instead.

### LOW: Dead cognitive migration script

| File | Description |
|------|-------------|
| `app/cognitive/migrate_to_cognitive.py` | 500+ line migration script, only runnable via `python -m app.cognitive.migrate_to_cognitive --user default_user`, not integrated into startup flow |

### LOW: Potentially unused schemas

| File | Description |
|------|-------------|
| `app/schemas/chat.py` | Chat-specific schemas — may be used but no cross-references found in API code |
| `app/schemas/learning_event.py` | Learning event schemas |
| `app/schemas/learning_profile.py` | Learning profile schemas |

---

## 8. SYNTAX ERRORS

**None found.** All 176 Python files parse successfully.

---

## Summary

| Category | HIGH | MEDIUM | LOW | Total |
|----------|------|--------|-----|-------|
| Broken imports | 1 | 0 | 1 | 2 |
| TODO/FIXME markers | 0 | 3 | 1 | 4 |
| Deprecated/duplicate schemas | 0 | 2 | 0 | 2 |
| Schema/table duplication | 0 | 2 | 2 | 4 |
| Hardcoded values | 1 | 0 | 0 | 1 |
| Overlapping routes | 0 | 1 | 1 | 2 |
| Dead code | 0 | 1 | 2 | 3 |
| Syntax errors | 0 | 0 | 0 | 0 |
| **Total** | **2** | **9** | **7** | **18** |

### Top 3 Action Items

1. ~~**HIGH** — Remove hardcoded `"default_user"` (40 occurrences). Add proper auth/user resolution to all endpoints.~~ **✅ 已修复 (Phase 16 S6)** — 全部替换为 `DEFAULT_USER_ID` 常量。
2. ~~**MEDIUM** — Fix `shared/schemas/*` imports in `shared/protocols/__init__.py` by creating the schemas or re-pointing to `app/schemas/`.~~ **✅ 已修复 (Phase 16 S10)** — 指向 `app.schemas.*`。
3. ~~**MEDIUM** — Reconcile duplicate `materials` and `material_chunks` table schemas between `database.py` and `migrate_materials.py`. Same for `secretary_proposals`.~~ **✅ 已修复 (Phase 16 S11-S12)** — `migrate_materials.py` 标记为 deprecated；`secretary_schema.sql` 同步更新。
