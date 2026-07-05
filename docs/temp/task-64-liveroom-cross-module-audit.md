# Task #64 — LanguageRoom 跨模块联动审计报告

> **日期**: 2026-07-03
> **测试文件**: `backend/tests/test_liveroom_cross_module.py` (21 测试, 全通过)
> **依据**: `docs/adr/0004-language-multiplayer.md` + `docs/modules/language-room/*`

## 1. 8 条跨模块联动审计矩阵

| # | 联动方向 | 实现状态 | ADR 差异 | 备注 |
|---|---------|---------|---------|------|
| 1 | Vocabulary → FlashCard | ⚠️ 部分 | 关键差异 6 (cross_module_source='language_room') | vocabulary_captures 表写入正常, flashcards 写入有降级 (try/except) |
| 2 | Error → ErrorBookEntry | ❌ 静默失败 | 关键差异 4 (grammar/vocabulary/pronunciation/coherence) | **B1+B3**: 双重 bug, 完全不可用 |
| 3 | Message → ExplainCard | ❌ 静默失败 | (D14 后 explain_cards 表已删) | **B2**: 写入已删除表, 静默失败 |
| 4 | AI Helper → KnowledgeGraph | ✅ 正常 | 关键差异 7 (3 类 helper_type) | tool_knowledge_search 路径通 |
| 5 | Transcript → voice_feature_stream | ❌ 断链 | 决策 8 (待修复 6) | liveroom 实际**未**推 voice_features 到 MoodStress |
| 6 | Room Completed → PlanItem | ✅ 正常 | (规划路由已实现) | completion_writer language_room 路由工作 |
| 7 | Scenario → Project | ❌ 未端到端 | 待修复 5 | 反向 (Project→LanguageRoom) 已通, 正向 (Scenario→Project) 未通 |
| 8 | AI Persona → Shared tool registry | ✅ 正常 | 决策 5 (4 类工具) | 4 个 liveroom 工具注册正常 |

## 2. 发现的真 bug (3 个)

### B1: `notes.create_error_entry` 写到不存在的表 (silent fail)
- **文件**: `backend/app/services/liveroom/notes.py:79`
- **现状**: `INSERT INTO practice_error_book (...)` — 该表**不存在**
- **真实表名**: `error_book` (`backend/app/infrastructure/db/practice_schema.sql:119`)
- **影响**: 错误标记的 ErrorBookEntry 实际未落库, `try/except` 静默吞掉, 只有 transcript.is_error 被更新
- **严重度**: 高 (用户主动行为数据丢失)

### B2: `notes.create_explain_card` 写入 D14 已删除表 (silent fail)
- **文件**: `backend/app/services/liveroom/notes.py:147`
- **现状**: `INSERT INTO explain_cards (...)` — 该表**已被 D14 删除** (数据应存 `messages.metadata.explain_cards` JSONB 数组)
- **影响**: 文字辅助消息 ID 返回, 但实际未落库
- **严重度**: 高 (会话补充内容丢失)

### B3: `notes.create_error_entry` SELECT 不存在的列 (硬错误)
- **文件**: `backend/app/services/liveroom/notes.py:69`
- **现状**: `SELECT text, user_text FROM room_transcripts` — `user_text` 列**不存在**
- **实际列**: 只有 `text`, `user_note` (无 `user_text`)
- **影响**: `create_error_entry` **每次必抛** `psycopg2.errors.UndefinedColumn: column "user_text" does not exist`
- **严重度**: 致命 (联动 2 完全不可用)

## 3. ADR 关键差异 1-9 实际状态

| 关键差异 | 描述 | 实际状态 |
|---------|------|---------|
| 1 | 路径 liveroom 而非 language_room | ✅ 已确认 (跨模块引用用 `CrossModuleTarget.LANGUAGE_ROOM = "language_room"`) |
| 2 | 事件 schema 实际 16 个 LanguageRoom* 事件 | ✅ 已确认 (`shared/events.py:1198-1458`) |
| 3 | `nodes_linked` → `linked_node_ids` 命名统一 | ✅ 已确认 (`LanguageRoomCompleted.linked_node_ids`) |
| 4 | 错误标记 → Belief 路径 (经 ErrorBookEntry 流程) | ❌ **B1+B3 阻断**: ErrorBookEntry 实际未落库 |
| 5 | `error_type` 4 类 (grammar/vocabulary/pronunciation/coherence) | ✅ 事件 schema 支持 4 类 |
| 6 | 词汇便签用 `cross_module_source='language_room'` | ⚠️ 部分: vocabulary_captures 落库正常, flashcards 落库有降级 |
| 7 | AI 辅助 helper_type 3 类 (grammar/vocabulary/sentence_pattern) | ✅ 已确认 (InvasivenessConfig.helper_types) |
| 8 | 转写片段事件粒度 (每个片段 1 个事件) | ✅ 已确认 (`LanguageRoomTranscriptSegmentAdded`) |
| 9 | AI 角色加入/离开独立事件 | ✅ 已确认 (`LanguageRoomAIPersonaJoined/Left`) |

## 4. ADR 7 项待修复实际状态

| 待修复 | 描述 | 实际状态 |
|-------|------|---------|
| 1 | AI 同伴语言熟练度单独建表 | ❌ 未实现 (按当前简化参数透传) |
| 2 | 跨语种 STT 多语种自动切换 | ❌ 未实现 (需用户主动配置每房间 STT 语言) |
| 3 | LiveKit 自部署 vs Cloud 自动检测 | ❌ 未实现 (依赖环境变量) |
| 4 | 录音文件 30 天后清理定时任务 | ❌ 未实现 (存储层仅做标记) |
| 5 | 场景与项目联动 (项目节点关联场景) | ❌ **未端到端**: 反向 (Project→LanguageRoom) 已通, 正向未通 |
| 6 | `voice_feature_stream` 实时流 0005 MoodStress 订阅 | ❌ **断链**: liveroom 实际未推 voice_features, MoodStress 默认 auto_collect=False |
| 7 | AI 角色纠错"仅在用户个人侧边区显示"前端 UI 差异化 | ❌ 后端已保证, 前端 UI 未差异化 |

## 5. AI 角色 tool 共享完整度

| 工具类 | 工具名 | 共享状态 | 调用路径 |
|-------|-------|---------|---------|
| 词汇捕获 | `tool_vocabulary_capture` | ✅ 注册 | liveroom_sync_handler |
| 错误标记 | `tool_error_mark` | ✅ 注册 | liveroom_sync_handler |
| 文字辅助 | `tool_message_post` | ✅ 注册 | liveroom_sync_handler |
| AI 辅助 | `tool_knowledge_search` | ✅ 注册 | liveroom_sync_handler |
| 知识图谱 (其他模块) | `knowledge_search_nodes` 等 | ✅ 通过 `tool_repository` | composite tool |

完整度: **4/4 liveroom 工具已注册到共享 tool_repository** (测试通过 `ai_persona.get_shared_tool_names()` 验证)

## 6. 命名规范 `linked_node_ids` 一致性

| 位置 | 字段名 | 一致性 |
|------|-------|-------|
| `LanguageRoomCompleted` (events.py:1255) | `linked_node_ids` | ✅ |
| `LanguageRoomErrorMarked` (events.py:1435) | `linked_node_ids` | ✅ |
| `room_sessions` (liveroom_schema.sql:85) | `linked_node_ids` | ✅ |
| `room_scenarios` (liveroom_schema.sql:146) | `linked_node_ids` | ✅ |
| `notes.create_vocabulary_capture` (notes.py:226) | `linked_node_ids` JSONB | ✅ |
| `notes.create_error_entry` (notes.py:88) | `linked_node_ids` JSONB | ✅ |

**结论**: 命名一致, 已统一为 `linked_node_ids`, 无 `nodes_linked` 旧命名残留

## 7. 测试统计

- **新增文件**: `backend/tests/test_liveroom_cross_module.py`
- **测试数**: 21 (8 联动类别全覆盖, 部分联动含子测试)
- **结果**: **21 passed, 0 failed**
- **pytest 终态**:
  - 原基线: 903 passed
  - 新基线: 998 passed (+95, 包含我新增 21)
  - 11 pre-existing failures in `test_liveroom_e2e_full.py` (untracked, 与本任务无关)
  - 3 errors in `test_agent_chat.py` (pre-existing storage 路径问题)

## 8. 建议修复优先级 (供后续任务)

1. **P0**: 修复 B3 (notes.create_error_entry SELECT user_text) — 联动 2 致命阻断
2. **P0**: 修复 B1 (notes.create_error_entry INSERT practice_error_book → error_book) — 联动 2 阻断
3. **P0**: 修复 B2 (notes.create_explain_card 迁移到 messages.metadata.explain_cards) — 联动 3 阻断
4. **P1**: 实现待修复 6 (liveroom 推送 voice_features 到 MoodStress)
5. **P1**: 实现待修复 5 (场景被项目节点关联)
6. **P2**: 推进其他 5 项待修复
