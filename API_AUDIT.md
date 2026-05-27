# API Endpoint Audit — edu-companion

Generated: 2026-05-27

---

## 1. COMPLETE ENDPOINT INVENTORY

### 🔹 Chat Module (`backend/app/api/chat.py`)
No prefix — mounted directly

| # | Method | Full Path | Handler | Frontend Consumer |
|---|--------|-----------|---------|-------------------|
| 1 | WS | `/ws` | `ws_chat` | `ws.ts` → `/api/conversations/ws` (NOTE: mismatch, see issues) |
| 2 | POST | `/api/chat` | `http_chat` | ❌ None found |

### 🔹 Conversation Module (`backend/app/api/conversation.py`)
Prefix: `/api/conversations` (set in main.py)

| # | Method | Full Path | Handler | Frontend Consumer |
|---|--------|-----------|---------|-------------------|
| 3 | GET | `/api/conversations/tree/{level}` | `get_tree_nodes` | useConversation.ts, Phase8Sidebar.tsx |
| 4 | POST | `/api/conversations/tree/{level}` | `create_tree_node` | useConversation.ts, Phase8Sidebar.tsx |
| 5 | PATCH | `/api/conversations/tree/{level}/{node_id}` | `update_tree_node` | useConversation.ts, Phase8Sidebar.tsx |
| 6 | DELETE | `/api/conversations/tree/{level}/{node_id}` | `delete_tree_node` | useConversation.ts |
| 7 | GET | `/api/conversations/tree/conversation/{conv_id}/messages` | `get_conversation_messages` | useConversation.ts |
| 8 | GET | `/api/conversations/tree/conversation/{conv_id}/blocks` | `get_conversation_blocks` | useConversation.ts |
| 9 | POST | `/api/conversations/tree/conversation/{conv_id}/message` | `send_conversation_message` | useConversation.ts |
| 10 | POST | `/api/conversations/tree/conversation/{conv_id}/switch` | `switch_conversation` | ❌ None found |
| 11 | GET | `/api/conversations/tree/message/{message_id}` | `get_message` | useConversation.ts |
| 12 | PUT | `/api/conversations/tree/message/{message_id}` | `update_message` | useConversation.ts |
| 13 | DELETE | `/api/conversations/tree/message/{message_id}` | `delete_message` | useConversation.ts |
| 14 | GET | `/api/conversations/tree/message/{message_id}/blocks` | `get_message_blocks` | ❌ None found |
| 15 | GET | `/api/conversations/tree/response-block/{block_id}` | `get_response_block` | ❌ None found |
| 16 | GET | `/api/conversations/tree/stream/active/{conversation_id}` | `get_active_stream` | useConversation.ts |
| 17 | POST | `/api/conversations/tree/conversation/{conv_id}/message/persist` | `persist_message` | ❌ None found |
| 18 | WS | `/api/conversations/ws` | `ws_conversation` | ws.ts |
| 19 | GET | `/api/conversations/emotion/trend` | `get_emotion_trend` | ❌ None found |
| 20 | GET | `/api/conversations/jobs/{job_id}` | `get_job_status` | ❌ None found |
| 21 | POST | `/api/conversations/jobs/{job_id}/cancel` | `cancel_job` | ❌ None found |
| 22 | GET | `/api/conversations/jobs/{job_id}/block` | `get_job_block` | ❌ None found |
| 23 | GET | `/api/conversations/tree/conversations/{conv_id}/materials` | `get_conversation_materials` | ❌ None found |
| 24 | GET | `/api/conversations/tree/conversations/{conv_id}/practice-suggestions` | `get_practice_suggestions` | ❌ None found |
| 25 | POST | `/api/conversations/workspace/upload` | `workspace_upload` | ChatInput.tsx |
| 26 | GET | `/api/conversations/workspace/files` | `list_workspace_files` | ❌ None found |
| 27 | DELETE | `/api/conversations/workspace/files/{file_id}` | `delete_workspace_file` | ❌ None found |
| 28 | GET | `/api/conversations/workspace/download/{file_id}` | `download_workspace_file` | ❌ None found |

### 🔹 Study Module (`backend/app/api/study.py`)
Prefix: `/api/study`

| # | Method | Full Path | Handler | Frontend Consumer |
|---|--------|-----------|---------|-------------------|
| 29 | POST | `/api/study/plan/generate` | `generate_plan` | PlanTab.tsx, study/page.tsx |
| 30 | GET | `/api/study/plan/{user_id}` | `get_plan` | PlanTab.tsx, study/page.tsx |
| 31 | PUT | `/api/study/plan/{user_id}/{task_id}/complete` | `complete_task` | ❌ None found |
| 32 | GET | `/api/study/plan/{user_id}/progress` | `get_progress` | PlanTab.tsx, study/page.tsx |
| 33 | GET | `/api/study/plan/{user_id}/history` | `get_history` | PlanTab.tsx, study/page.tsx |
| 34 | POST | `/api/study/plan/refresh` | `refresh_plan` | ❌ None found |
| 35 | GET | `/api/study/suggestions` | `get_suggestions` | PlanTab.tsx, study/page.tsx |

### 🔹 Practice Module (`backend/app/api/practice.py`)
Prefix: `/api/practice`

| # | Method | Full Path | Handler | Frontend Consumer |
|---|--------|-----------|---------|-------------------|
| 36 | POST | `/api/practice/questions/generate` | `generate_questions` | ❌ None found |
| 37 | GET | `/api/practice/questions` | `get_questions` | ❌ None found |
| 38 | POST | `/api/practice/sessions` | `create_session` | practice/page.tsx |
| 39 | GET | `/api/practice/sessions` | `list_sessions` | ❌ None found |
| 40 | GET | `/api/practice/sessions/{session_id}` | `get_session` | ❌ None found |
| 41 | POST | `/api/practice/sessions/{session_id}/complete` | `complete_session` | ❌ None found |
| 42 | POST | `/api/practice/submit` | `submit_answer` | practice/page.tsx |
| 43 | POST | `/api/practice/hint` | `get_hint` | practice/page.tsx |
| 44 | POST | `/api/practice/inline/answer` | `submit_inline_answer` | InlinePracticeBlock.tsx |
| 45 | POST | `/api/practice/inline/hint` | `get_inline_hint` | InlinePracticeBlock.tsx |
| 46 | GET | `/api/practice/knowledge/state` | `get_knowledge_state` | stats/page.tsx |
| 47 | GET | `/api/practice/knowledge/skill/{skill_id}` | `get_skill_state` | ❌ None found |
| 48 | GET | `/api/practice/knowledge/weak` | `get_weak_knowledge` | ❌ None found |
| 49 | POST | `/api/practice/knowledge/evidence` | `submit_evidence` | ❌ None found |

### 🔹 Practice Errors Module (`backend/app/api/practice_errors.py`)
Prefix: `/api/practice`

| # | Method | Full Path | Handler | Frontend Consumer |
|---|--------|-----------|---------|-------------------|
| 50 | GET | `/api/practice/errors` | `get_errors` | ErrorsTab.tsx, errors/page.tsx |
| 51 | POST | `/api/practice/errors/{entry_id}/review` | `review_error` | ErrorsTab.tsx, errors/page.tsx |
| 52 | GET | `/api/practice/errors/due` | `get_due_errors` | ❌ None found |
| 53 | POST | `/api/practice/errors/{entry_id}/analyze` | `analyze_error` | ErrorsTab.tsx, errors/page.tsx |
| 54 | GET | `/api/practice/errors/stats` | `get_error_stats` | ErrorsTab.tsx, errors/page.tsx, progress/page.tsx |

### 🔹 Practice Analytics Module (`backend/app/api/practice_analytics.py`)
Prefix: `/api/practice`

| # | Method | Full Path | Handler | Frontend Consumer |
|---|--------|-----------|---------|-------------------|
| 55 | GET | `/api/practice/stats` | `get_stats` | AnalyticsTab.tsx, stats/page.tsx, progress/page.tsx, analytics/page.tsx |
| 56 | GET | `/api/practice/behavior` | `get_behavior` | AnalyticsTab.tsx, analytics/page.tsx |

### 🔹 Practice Quality Module (`backend/app/api/practice_quality.py`)
Prefix: `/api/practice`

| # | Method | Full Path | Handler | Frontend Consumer |
|---|--------|-----------|---------|-------------------|
| 57 | GET | `/api/practice/quality` | `get_quality` | QualityTab.tsx, quality/page.tsx |
| 58 | GET | `/api/practice/quality/worst` | `get_worst_quality` | ❌ None found |
| 59 | POST | `/api/practice/quality/apply` | `apply_quality_fixes` | QualityTab.tsx, quality/page.tsx |
| 60 | GET | `/api/practice/quality/detail/{question_id}` | `get_quality_detail` | QualityTab.tsx, quality/page.tsx |
| 61 | GET | `/api/practice/quality/{question_id}/distractors` | `get_distractors` | ❌ None found |

### 🔹 Progress Module (`backend/app/api/progress.py`)
Prefix: `/api/progress`

| # | Method | Full Path | Handler | Frontend Consumer |
|---|--------|-----------|---------|-------------------|
| 62 | GET | `/api/progress/{user_id}` | `get_progress` | progress/page.tsx |
| 63 | GET | `/api/progress/{user_id}/stats` | `get_stats` | progress/page.tsx |
| 64 | POST | `/api/progress/{user_id}/session/start` | `start_session` | ❌ None found |
| 65 | POST | `/api/progress/{user_id}/profile/update` | `update_profile` | ❌ None found |
| 66 | GET | `/api/progress/{user_id}/profile` | `get_profile` | ❌ None found |
| 67 | GET | `/api/progress/{user_id}/calendar` | `get_calendar` | CalendarTab.tsx, calendar/page.tsx |
| 68 | GET | `/api/progress/{user_id}/summary` | `get_daily_summary` | DailySummaryCard.tsx, analytics/page.tsx |

### 🔹 Content Module (`backend/app/api/content.py`)
Prefix: `/api/content`

| # | Method | Full Path | Handler | Frontend Consumer |
|---|--------|-----------|---------|-------------------|
| 69 | GET | `/api/content/search` | `search_content` | ❌ None found |
| 70 | GET | `/api/content/list` | `list_content` | ❌ None found |
| 71 | GET | `/api/content/{content_id}` | `get_content` | ❌ None found |
| 72 | GET | `/api/content/subjects/list` | `list_subjects` | ❌ None found |

### 🔹 Material Module (`backend/app/api/material.py`)
Prefix: `/api/materials`

| # | Method | Full Path | Handler | Frontend Consumer |
|---|--------|-----------|---------|-------------------|
| 73 | POST | `/api/materials/upload` | `upload_material` | MaterialPanel.tsx |
| 74 | GET | `/api/materials` | `list_materials` | MaterialPanel.tsx, MaterialPicker.tsx |
| 75 | PATCH | `/api/materials/{material_id}` | `update_material` | MaterialPanel.tsx |
| 76 | POST | `/api/materials/{material_id}/promote` | `promote_material` | MaterialPanel.tsx |
| 77 | GET | `/api/materials/promote-suggestions` | `get_promote_suggestions` | ❌ None found |
| 78 | POST | `/api/materials/search` | `search_materials` | ❌ None found |
| 79 | GET | `/api/materials/{material_id}/chunks` | `get_material_chunks` | ❌ None found |
| 80 | POST | `/api/materials/generate-questions` | `generate_questions` | ❌ None found |
| 81 | DELETE | `/api/materials/{material_id}` | `delete_material` | ❌ None found |
| 82 | POST | `/api/materials/cleanup-sessions` | `cleanup_sessions` | ❌ None found |

### 🔹 Knowledge Module (`backend/app/api/knowledge.py`)
Prefix: `/api/knowledge`

| # | Method | Full Path | Handler | Frontend Consumer |
|---|--------|-----------|---------|-------------------|
| 83 | GET | `/api/knowledge/graph` | `get_graph` | RadarChart.tsx, GraphSidePanel.tsx |
| 84 | GET | `/api/knowledge/prerequisites` | `get_prerequisites` | ❌ None found |
| 85 | POST | `/api/knowledge/check` | `check_prerequisites` | ❌ None found |
| 86 | GET | `/api/knowledge/blocked` | `get_blocked` | ❌ None found |
| 87 | GET | `/api/knowledge/ready` | `get_ready` | ❌ None found |
| 88 | GET | `/api/knowledge/path` | `get_path` | ❌ None found |
| 89 | GET | `/api/knowledge/retention` | `get_retention` | RetentionPanel.tsx, analytics/page.tsx |

### 🔹 Knowledge Graph Module (`backend/app/api/knowledge_graph.py`)
Prefix: `/api/knowledge/graph`

| # | Method | Full Path | Handler | Frontend Consumer |
|---|--------|-----------|---------|-------------------|
| 90 | GET | `/api/knowledge/graph/{partition_id}` | `get_partition_graph` | GraphTab.tsx (indirectly) |
| 91 | POST | `/api/knowledge/graph/{partition_id}/generate` | `generate_graph` | GraphTab.tsx |
| 92 | PUT | `/api/knowledge/graph/{partition_id}/nodes` | `update_nodes` | ❌ None found |
| 93 | PUT | `/api/knowledge/graph/{partition_id}/edges` | `update_edges` | ❌ None found |

### 🔹 Learning Events Module (`backend/app/api/learning_events.py`)
Prefix: `/api/learning-events`

| # | Method | Full Path | Handler | Frontend Consumer |
|---|--------|-----------|---------|-------------------|
| 94 | GET | `/api/learning-events/stats/{partition_id}` | `get_event_stats` | ❌ None found |
| 95 | GET | `/api/learning-events/daily/{partition_id}` | `get_daily_metrics` | ❌ None found |

### 🔹 Partition Progress Module (`backend/app/api/partition_progress.py`)
Prefix: `/api/partition-progress`

| # | Method | Full Path | Handler | Frontend Consumer |
|---|--------|-----------|---------|-------------------|
| 96 | GET | `/api/partition-progress/{partition_id}` | `get_partition_progress` | GraphTab.tsx |

### 🔹 Multimodal Module (`backend/app/api/multimodal.py`)
Prefix: `/api/multimodal`

| # | Method | Full Path | Handler | Frontend Consumer |
|---|--------|-----------|---------|-------------------|
| 97 | GET | `/api/multimodal/audio/{filename}` | `get_audio` | ❌ None found |
| 98 | GET | `/api/multimodal/images/{filename}` | `get_image` | ❌ None found |
| 99 | POST | `/api/multimodal/transcribe` | `transcribe_audio` | VoiceRecorder.tsx |

### 🔹 Achievements Module (`backend/app/api/achievements.py`)
Prefix: `/api/achievements`

| # | Method | Full Path | Handler | Frontend Consumer |
|---|--------|-----------|---------|-------------------|
| 100 | GET | `/api/achievements/{user_id}` | `get_achievements` | AchievementsTab.tsx, page.tsx, OverviewTab.tsx |
| 101 | POST | `/api/achievements/{user_id}/check` | `check_achievements` | ❌ None found |

### 🔹 Search Module (`backend/app/api/search.py`)
Prefix: `/api/search`

| # | Method | Full Path | Handler | Frontend Consumer |
|---|--------|-----------|---------|-------------------|
| 102 | GET | `/api/search` | `unified_search` | UnifiedSearch.tsx |

### 🔹 Secretary Module (`backend/app/api/secretary.py`)
Prefix: `/api/secretary`

| # | Method | Full Path | Handler | Frontend Consumer |
|---|--------|-----------|---------|-------------------|
| 103 | GET | `/api/secretary/preferences` | `get_preferences` | settings/page.tsx |
| 104 | PATCH | `/api/secretary/preferences` | `update_preferences` | ❌ None found |
| 105 | GET | `/api/secretary/snapshot` | `get_snapshot` | secretary/page.tsx |
| 106 | GET | `/api/secretary/daily-brief` | `get_daily_brief` | ❌ None found |
| 107 | POST | `/api/secretary/diagnose` | `diagnose` | ❌ None found |
| 108 | POST | `/api/secretary/suggest` | `suggest` | ❌ None found |
| 109 | GET | `/api/secretary/proposals/pending` | `get_pending_proposals` | secretary/page.tsx, SecretaryBellBadge.tsx |
| 110 | GET | `/api/secretary/proposals/history` | `get_proposals_history` | secretary/page.tsx |
| 111 | POST | `/api/secretary/proposals/{proposal_id}/accept` | `accept_proposal` | secretary/page.tsx |
| 112 | POST | `/api/secretary/proposals/{proposal_id}/dismiss` | `dismiss_proposal` | secretary/page.tsx |
| 113 | POST | `/api/secretary/proposals/{proposal_id}/snooze` | `snooze_proposal` | ❌ None found |
| 114 | POST | `/api/secretary/generate-llm-proposals` | `generate_llm_proposals` | secretary/page.tsx |
| 115 | POST | `/api/secretary/push-to-blackboard` | `push_to_blackboard` | ❌ None found |
| 116 | GET | `/api/secretary/modules` | `get_modules` | settings/page.tsx |
| 117 | POST | `/api/secretary/modules/toggle` | `toggle_module` | settings/page.tsx |
| 118 | GET | `/api/secretary/onboarding` | `get_onboarding` | settings/page.tsx |
| 119 | GET | `/api/secretary/data/export` | `export_data` | settings/page.tsx |
| 120 | DELETE | `/api/secretary/data/delete` | `delete_data` | settings/page.tsx |
| 121 | POST | `/api/secretary/onboarding/dialogue` | `onboarding_dialogue` | ❌ None found |

### 🔹 Phase 8 / V2 Module (`backend/app/api/phase8.py`)
Prefix: `/api/v2`

| # | Method | Full Path | Handler | Frontend Consumer |
|---|--------|-----------|---------|-------------------|
| 122 | POST | `/api/v2/classify` | `classify_message` | api.ts (fireClassify) |
| 123 | POST | `/api/v2/classify/select` | `classify_select` | ❌ None found |
| 124 | POST | `/api/v2/classify/custom` | `classify_custom` | ❌ None found |
| 125 | PUT | `/api/v2/conversations/{conv_id}/save` | `save_conversation` | ❌ None found |
| 126 | GET | `/api/v2/conversations/{conv_id}/links` | `get_links` | ❌ None found |
| 127 | POST | `/api/v2/conversations/{conv_id}/links` | `create_link` | ❌ None found |
| 128 | PATCH | `/api/v2/conversations/{conv_id}/links/{link_id}` | `update_link` | ❌ None found |
| 129 | DELETE | `/api/v2/conversations/{conv_id}/links/{link_id}` | `delete_link` | ❌ None found |
| 130 | GET | `/api/v2/graph/nodes` | `get_graph_nodes` | Phase8Sidebar.tsx |
| 131 | GET | `/api/v2/graph/search` | `search_graph` | ❌ None found |
| 132 | POST | `/api/v2/graph/nodes/{node_id}/expand` | `expand_node` | ❌ None found |
| 133 | POST | `/api/v2/graph/nodes` | `create_graph_node` | ❌ None found |
| 134 | PATCH | `/api/v2/graph/nodes/{node_id}` | `update_graph_node` | ❌ None found |
| 135 | DELETE | `/api/v2/graph/nodes/{node_id}` | `delete_graph_node` | Phase8Sidebar.tsx |
| 136 | GET | `/api/v2/graph/edges` | `get_graph_edges` | ❌ None found |
| 137 | POST | `/api/v2/graph/edges/{edge_id}/accept` | `accept_edge` | ❌ None found |
| 138 | POST | `/api/v2/graph/edges/{edge_id}/reject` | `reject_edge` | ❌ None found |
| 139 | DELETE | `/api/v2/graph/edges/{edge_id}` | `delete_edge` | ❌ None found |
| 140 | GET | `/api/v2/graph/export` | `export_graph` | ❌ None found |
| 141 | POST | `/api/v2/practice/queue` | `queue_practice` | ❌ None found |
| 142 | PATCH | `/api/v2/practice/scheduling` | `update_scheduling` | ❌ None found |
| 143 | GET | `/api/v2/dashboard/overview` | `get_overview` | OverviewTab.tsx |
| 144 | POST | `/api/v2/explain/for-error` | `explain_for_error` | ExplainPanel.tsx |
| 145 | POST | `/api/v2/explain/tts` | `explain_tts` | ExplainPanel.tsx |
| 146 | POST | `/api/v2/explain/card` | `explain_card` | ❌ None found |
| 147 | POST | `/api/v2/emotion/analyze` | `analyze_emotion` | ❌ None found |
| 148 | GET | `/api/v2/emotion/trend/{user_id}` | `get_emotion_trend` | EmotionCard.tsx |
| 149 | POST | `/api/v2/expand/knowledge` | `expand_knowledge` | ExpandPanel.tsx |
| 150 | POST | `/api/v2/expand/variant` | `expand_variant` | ExpandPanel.tsx |
| 151 | POST | `/api/v2/expand/discover` | `expand_discover` | ❌ None found |
| 152 | POST | `/api/v2/vision/ocr` | `vision_ocr` | ❌ None found |
| 153 | POST | `/api/v2/vision/understand-problem` | `vision_understand_problem` | ❌ None found |
| 154 | POST | `/api/v2/vision/analyze` | `vision_analyze` | ❌ None found |
| 155 | POST | `/api/v2/vision/chat-image` | `vision_chat_image` | ❌ None found |

---

## 2. FRONTEND CALLS HITTING NON-EXISTENT BACKEND ENDPOINTS

| Frontend Call | File | Issue |
|---|---|---|
| `GET /api/conversations/partitions` | GraphTab.tsx:110 | ❌ **No such endpoint exists.** Backend has `/tree/{level}` (GET tree partitions = `/tree/partition`) but not `/partitions`. |
| `GET /api/progress/summary?user_id=default_user` | OverviewTab.tsx:93, page.tsx:88 | ⚠️ **Misrouted.** Matches `GET /api/progress/{user_id}` with user_id="summary" (not the intended user). Should be `/api/progress/default_user` or `/api/progress/default_user/summary`. The query param `user_id=default_user` is ignored by FastAPI. |

---

## 3. DUAL APIs (v1 vs v2 Serving Same Data)

| v1 Endpoint | v2 Endpoint | Overlap |
|---|---|---|
| `GET /api/conversations/emotion/trend` (conversation.py:535) | `GET /api/v2/emotion/trend/{user_id}` (phase8.py:807) | ⚠️ **Potential overlap.** Both serve emotion trend data. v2 adds user_id path param. |
| `GET /api/knowledge/graph/{partition_id}` (knowledge_graph.py:138) | `GET /api/v2/graph/nodes` (phase8.py:230) | ⚠️ **Potential overlap.** Both serve graph data, v2 has richer node management (expand, search, CRUD). |
| `POST /api/practice/...` (practice.py) | `POST /api/v2/practice/queue` + `PATCH /api/v2/practice/scheduling` (phase8.py) | ⚠️ **Partial overlap.** v2 adds queue-based practice scheduling on top of v1 session-based practice. |

---

## 4. ENDPOINTS WITH NO FRONTEND CONSUMER (43 endpoints)

Grouped by module:

### Chat (1)
- `POST /api/chat`

### Conversation (10)
- `POST /api/conversations/tree/conversation/{conv_id}/switch`
- `GET /api/conversations/tree/message/{message_id}/blocks`
- `GET /api/conversations/tree/response-block/{block_id}`
- `POST /api/conversations/tree/conversation/{conv_id}/message/persist`
- `GET /api/conversations/emotion/trend`
- `GET /api/conversations/jobs/{job_id}`
- `POST /api/conversations/jobs/{job_id}/cancel`
- `GET /api/conversations/jobs/{job_id}/block`
- `GET /api/conversations/tree/conversations/{conv_id}/materials`
- `GET /api/conversations/tree/conversations/{conv_id}/practice-suggestions`
- `GET /api/conversations/workspace/files`
- `DELETE /api/conversations/workspace/files/{file_id}`
- `GET /api/conversations/workspace/download/{file_id}`

### Study (2)
- `PUT /api/study/plan/{user_id}/{task_id}/complete`
- `POST /api/study/plan/refresh`

### Practice (7)
- `POST /api/practice/questions/generate`
- `GET /api/practice/questions`
- `GET /api/practice/sessions`
- `GET /api/practice/sessions/{session_id}`
- `POST /api/practice/sessions/{session_id}/complete`
- `GET /api/practice/knowledge/skill/{skill_id}`
- `GET /api/practice/knowledge/weak`
- `POST /api/practice/knowledge/evidence`

### Practice Errors (1)
- `GET /api/practice/errors/due`

### Practice Quality (2)
- `GET /api/practice/quality/worst`
- `GET /api/practice/quality/{question_id}/distractors`

### Progress (3)
- `POST /api/progress/{user_id}/session/start`
- `POST /api/progress/{user_id}/profile/update`
- `GET /api/progress/{user_id}/profile`

### Content (4) — Entire module has no frontend consumers
- `GET /api/content/search`
- `GET /api/content/list`
- `GET /api/content/{content_id}`
- `GET /api/content/subjects/list`

### Material (5)
- `GET /api/materials/promote-suggestions`
- `POST /api/materials/search`
- `GET /api/materials/{material_id}/chunks`
- `POST /api/materials/generate-questions`
- `DELETE /api/materials/{material_id}`
- `POST /api/materials/cleanup-sessions`

### Knowledge (5)
- `GET /api/knowledge/prerequisites`
- `POST /api/knowledge/check`
- `GET /api/knowledge/blocked`
- `GET /api/knowledge/ready`
- `GET /api/knowledge/path`

### Knowledge Graph (2)
- `PUT /api/knowledge/graph/{partition_id}/nodes`
- `PUT /api/knowledge/graph/{partition_id}/edges`

### Learning Events (2) — Entire module has no frontend consumers
- `GET /api/learning-events/stats/{partition_id}`
- `GET /api/learning-events/daily/{partition_id}`

### Multimodal (2)
- `GET /api/multimodal/audio/{filename}`
- `GET /api/multimodal/images/{filename}`

### Achievements (1)
- `POST /api/achievements/{user_id}/check`

### Secretary (4)
- `PATCH /api/secretary/preferences`
- `GET /api/secretary/daily-brief`
- `POST /api/secretary/diagnose`
- `POST /api/secretary/suggest`
- `POST /api/secretary/proposals/{proposal_id}/snooze`
- `POST /api/secretary/push-to-blackboard`
- `POST /api/secretary/onboarding/dialogue`

### Phase 8 / V2 (19)
- `POST /api/v2/classify/select`
- `POST /api/v2/classify/custom`
- `PUT /api/v2/conversations/{conv_id}/save`
- `GET /api/v2/conversations/{conv_id}/links`
- `POST /api/v2/conversations/{conv_id}/links`
- `PATCH /api/v2/conversations/{conv_id}/links/{link_id}`
- `DELETE /api/v2/conversations/{conv_id}/links/{link_id}`
- `GET /api/v2/graph/search`
- `POST /api/v2/graph/nodes/{node_id}/expand`
- `POST /api/v2/graph/nodes`
- `PATCH /api/v2/graph/nodes/{node_id}`
- `GET /api/v2/graph/edges`
- `POST /api/v2/graph/edges/{edge_id}/accept`
- `POST /api/v2/graph/edges/{edge_id}/reject`
- `DELETE /api/v2/graph/edges/{edge_id}`
- `GET /api/v2/graph/export`
- `POST /api/v2/practice/queue`
- `PATCH /api/v2/practice/scheduling`
- `POST /api/v2/explain/card`
- `POST /api/v2/emotion/analyze`
- `POST /api/v2/expand/discover`
- `POST /api/v2/vision/ocr`
- `POST /api/v2/vision/understand-problem`
- `POST /api/v2/vision/analyze`
- `POST /api/v2/vision/chat-image`

---

## 5. SUMMARY STATISTICS

| Metric | Count |
|--------|-------|
| Total backend endpoints | **155** |
| Endpoints with frontend consumer | **~60** |
| Endpoints with NO frontend consumer | **~95** (61%) |
| Frontend calls to non-existent endpoints | **2** |
| Potential v1/v2 dual API overlaps | **3** |
| Entire modules with zero frontend consumption | **2** (content, learning-events) |

---

## 6. RECOMMENDED ACTIONS

1. **Fix GraphTab.tsx** — Change `/api/conversations/partitions` to `/api/conversations/tree/partition`
2. **Fix OverviewTab.tsx / page.tsx** — Change `/api/progress/summary?user_id=default_user` to `/api/progress/default_user` (or `/api/progress/default_user/summary` if daily summary was intended)
3. **Audit content module** — 4 endpoints, zero frontend consumers. Either wire up the frontend or remove dead code.
4. **Audit learning-events module** — 2 endpoints, zero frontend consumers.
5. **Review v1/v2 emotion trend overlap** — Decide on single source of truth.
6. **Review workspace endpoints** — Upload works but file listing/download/delete have no UI.
7. **Review vision endpoints** — 4 vision endpoints in v2, none consumed by frontend. Either implement vision UI or remove.
