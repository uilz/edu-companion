# LanguageRoom 数据模型

> LanguageRoom 模块的数据结构（房间、参与者、转写、错误标记）。

**ADR**：[`docs/adr/0004-language-multiplayer.md`](../../adr/0004-language-multiplayer.md)

---

## 1. 设计原则

1. **数据归属 = 参与者各自存**（决策 1）
2. **房间可见性 = 邀请制**（无 `is_public` 字段，决策 2）
3. **场景与项目平行**（决策 9）
4. **录音可选**（决策 10）
5. **转写数据各自分开**（决策 11）
6. **词汇便签复用 FlashCard 数据卡**（`card_type='data'`，`source='language_room'`）
7. **错误标记复用 ErrorBookEntry**（不新建独立表）
8. **文字辅助复用 ExplainCard**（不新建独立表）
9. **AI 角色共享 conversation-system 的 tool registry**

---

## 2. 表清单（11 张）

| # | 表名 | 说明 |
|---|------|------|
| 1 | `language_rooms` | 房间主表 |
| 2 | `room_participants` | 参与者（真人 + AI 角色混合）|
| 3 | `room_sessions` | 参与者会话（每个用户各一份）|
| 4 | `room_transcripts` | 转写片段（按参与者各自存）|
| 5 | `room_scenarios` | 场景（系统预置 + 用户自建）|
| 6 | `ai_personas` | AI 角色（系统预置 + 用户自建）|
| 7 | `ai_companion_configs` | 房间级 AI 同伴行为配置 |
| 8 | `ai_helper_invasiveness` | 用户级 AI 辅助者侵入度配置 |
| 9 | `room_recordings` | 录音文件（可选）|
| 10 | `vocabulary_captures` | 词汇便签（软链接 FlashCard）|
| 11 | `room_invitations` | 邀请制 token |

> **命名约定**：模块内"房间子表"用 `room_` 前缀（与 `language_rooms` 主表区分）；AI 资源用 `ai_` 前缀。
> 所有表的主键用 `TEXT` 类型（统一为 `{prefix}_{uuid12}`）。

---

## 3. 详细表结构

### 3.1 房间主表 `language_rooms`

```sql
CREATE TABLE language_rooms (
    id                      TEXT PRIMARY KEY,
    owner_id                TEXT NOT NULL,                    -- 房主 user_id
    name                    TEXT NOT NULL,
    scenario_id             TEXT,                              -- 关联 room_scenarios
    room_type               VARCHAR(20) NOT NULL,             -- 1v1 / small / medium / large
    max_participants        INT DEFAULT 2,
    is_recording_enabled    BOOLEAN DEFAULT FALSE,
    is_transcript_enabled   BOOLEAN DEFAULT TRUE,
    ai_intrusion_level      VARCHAR(10) DEFAULT 'low',        -- low / medium / high
    status                  VARCHAR(20) DEFAULT 'active',     -- active / ended
    started_at              TIMESTAMP NOT NULL DEFAULT NOW(),
    ended_at                TIMESTAMP,
    settings                JSONB DEFAULT '{}'::jsonb,        -- 房间级设置 (Task #65: 含 4 字段)
    created_at              TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMP NOT NULL DEFAULT NOW()
);
```

**`settings` JSONB 字段约定** (Task #65):

`language_rooms.settings` 存房间级偏好。前端 `/liveroom/create` 表单提交时打包的 4 字段:

| 字段 | 类型 | 默认 | 说明 |
|------|------|------|------|
| `stt_language` | `"en" \| "zh" \| "es"` | `"en"` | STT 转写语言 (ADR 待修复 2: 当前需用户主动配置每房间) |
| `error_correction_level` | `"none" \| "occasional" \| "proactive"` | `"none"` | AI 纠错倾向 (决策 6: 用户主动选择) |
| `ai_companion_persona_id` | `str` (UUID) | `""` | AI 同伴 persona ID, 房间创建时即把 persona 拉入 |
| `ai_assistant_persona_id` | `str` (UUID) | `""` | AI 辅助者 persona ID, 房间级助手 |

将来可升级为独立列 (独立 schema 字段), 不破坏现有数据。

**关键决策**：**不设公开房间**——`is_public` 字段**不存在**，房间**只**通过邀请 token 进入。

---

### 3.2 参与者表 `room_participants`

```sql
CREATE TABLE room_participants (
    id                      TEXT PRIMARY KEY,
    room_id                 TEXT NOT NULL REFERENCES language_rooms(id) ON DELETE CASCADE,
    user_id                 TEXT NOT NULL,                    -- 真人或 AI 角色 ID
    participant_type        VARCHAR(20) NOT NULL,             -- human / ai_companion / ai_assistant
    ai_role_id              TEXT,                              -- 关联 ai_personas (如果是 AI)
    role_label              VARCHAR(50),                       -- 场景中角色名 ("咖啡师")
    language                VARCHAR(20),                       -- 参与语种
    joined_at               TIMESTAMP NOT NULL DEFAULT NOW(),
    left_at                 TIMESTAMP,
    speaking_time_seconds   INT DEFAULT 0,
    is_muted                BOOLEAN DEFAULT FALSE,
    is_owner                BOOLEAN DEFAULT FALSE,
    created_at              TIMESTAMP NOT NULL DEFAULT NOW()
);
```

**关键决策**：每个参与者的数据**各自存储**，AI 同伴和真人在同一表。

---

### 3.3 参与者会话表 `room_sessions`

```sql
CREATE TABLE room_sessions (
    id                      TEXT PRIMARY KEY,
    room_id                 TEXT NOT NULL REFERENCES language_rooms(id) ON DELETE CASCADE,
    user_id                 TEXT NOT NULL,                    -- 该会话归属用户
    participant_id          TEXT NOT NULL,                    -- 关联 room_participants
    started_at              TIMESTAMP NOT NULL DEFAULT NOW(),
    ended_at                TIMESTAMP,
    duration_seconds        INT,
    transcript_count        INT DEFAULT 0,                    -- 该用户转写段数
    errors_marked           INT DEFAULT 0,                    -- 该用户标记错误数
    cards_generated         INT DEFAULT 0,                    -- 该用户生成卡片数
    ai_help_requests        INT DEFAULT 0,                    -- 该用户召唤 AI 辅助者次数
    vocabulary_captured     INT DEFAULT 0,                    -- 该用户词汇便签数
    messages_posted         INT DEFAULT 0,                    -- 该用户文字辅助区数
    linked_node_ids         JSONB DEFAULT '[]'::jsonb,         -- 关联知识点
    session_metadata        JSONB DEFAULT '{}'::jsonb,         -- 扩展元数据
    created_at              TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMP NOT NULL DEFAULT NOW()
);
```

**关键决策**：每个参与者各一份会话记录（用于"我的房间历史"视图与"距上次练习 N 天"提示）。

---

### 3.4 转写片段表 `room_transcripts`

```sql
CREATE TABLE room_transcripts (
    id                      TEXT PRIMARY KEY,
    room_id                 TEXT NOT NULL REFERENCES language_rooms(id) ON DELETE CASCADE,
    participant_id          TEXT NOT NULL REFERENCES room_participants(id) ON DELETE CASCADE,
    user_id                 TEXT NOT NULL,                    -- 转写归属用户
    segment_index           INT NOT NULL,
    text                    TEXT NOT NULL,
    language                VARCHAR(20),
    started_at              TIMESTAMP NOT NULL,
    ended_at                TIMESTAMP NOT NULL,
    confidence              DOUBLE PRECISION,
    speaker_id              TEXT,                              -- 实际说话者
    speaker_name            VARCHAR(100),
    is_user_marked          BOOLEAN DEFAULT FALSE,            -- 用户是否手动标记
    user_note               TEXT,
    is_error                BOOLEAN DEFAULT FALSE,            -- 标记为错误
    error_entry_id          TEXT,                              -- 关联 ErrorBookEntry.id
    created_at              TIMESTAMP NOT NULL DEFAULT NOW()
);
```

**关键决策**：转写**按参与者各自存储**（隐私）。同一句话在多个参与者的表中是**独立的行**。

---

### 3.5 场景表 `room_scenarios`

```sql
CREATE TABLE room_scenarios (
    id                      TEXT PRIMARY KEY,
    user_id                 TEXT,                              -- NULL = 系统预置
    name                    TEXT NOT NULL,
    description             TEXT,
    category                VARCHAR(50),                       -- 日常 / 学术 / 商务
    roles                   JSONB DEFAULT '[]'::jsonb,         -- 角色列表
    target_goals            JSONB DEFAULT '[]'::jsonb,         -- 目标任务列表
    prompt_text             TEXT,                              -- 浮动提示词
    linked_node_ids         JSONB DEFAULT '[]'::jsonb,         -- 关联 CognitiveNode
    cross_disciplinary      BOOLEAN DEFAULT FALSE,             -- 是否允许跨学科
    is_system               BOOLEAN DEFAULT FALSE,             -- 系统预置 / 用户自建
    created_at              TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMP NOT NULL DEFAULT NOW()
);
```

**关键决策**：场景与项目是**平行概念**——场景是短期对话脚手架，项目是长期任务。两者**不**互相引用。

---

### 3.6 AI 角色表 `ai_personas`

```sql
CREATE TABLE ai_personas (
    id                      TEXT PRIMARY KEY,
    user_id                 TEXT,                              -- NULL = 系统预置
    name                    TEXT NOT NULL,
    gender_voice            VARCHAR(20),
    personality             TEXT,                              -- 性格描述
    target_language         VARCHAR(20),
    proficiency             VARCHAR(20),                       -- beginner/intermediate/advanced/native
    speech_rate             VARCHAR(20),                       -- slow/normal/fast
    accent                  VARCHAR(50),
    behavior                VARCHAR(20),                       -- talkative/concise
    correction_tendency     VARCHAR(20) DEFAULT 'none',        -- none/occasional/proactive
    is_topic_lead           BOOLEAN DEFAULT FALSE,             -- 是否主动引导话题
    is_system               BOOLEAN DEFAULT FALSE,
    background              TEXT,                              -- 角色背景
    created_at              TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMP NOT NULL DEFAULT NOW()
);
```

**关键决策**：AI 角色**独立部署**（不是 OpenAI 助手），但**共享** conversation-system 的 tool registry。
**不**用 `ai_roles`（保留给其他模块的细粒度角色概念）。

---

### 3.7 AI 同伴配置表 `ai_companion_configs`

```sql
CREATE TABLE ai_companion_configs (
    id                      TEXT PRIMARY KEY,
    room_id                 TEXT NOT NULL REFERENCES language_rooms(id) ON DELETE CASCADE,
    participant_id          TEXT NOT NULL REFERENCES room_participants(id) ON DELETE CASCADE,
    persona_id              TEXT NOT NULL REFERENCES ai_personas(id) ON DELETE CASCADE,
    user_id                 TEXT NOT NULL,                    -- 该配置所属用户
    correction_tendency     VARCHAR(20) DEFAULT 'none',        -- 用户选择
    is_topic_lead           BOOLEAN DEFAULT FALSE,
    response_style          VARCHAR(20) DEFAULT 'balanced',    -- formal/balanced/casual
    max_response_length     INT DEFAULT 200,
    activated_at            TIMESTAMP NOT NULL DEFAULT NOW(),
    deactivated_at          TIMESTAMP
);
```

**关键决策**：AI 同伴行为**用户主动配置**（决策 6）；同一房间的不同用户对同一 AI 角色可有不同配置。

---

### 3.8 AI 辅助者侵入度配置表 `ai_helper_invasiveness`

```sql
CREATE TABLE ai_helper_invasiveness (
    id                      TEXT PRIMARY KEY,
    user_id                 TEXT NOT NULL,
    room_id                 TEXT NOT NULL REFERENCES language_rooms(id) ON DELETE CASCADE,
    invasiveness_level      VARCHAR(10) DEFAULT 'low',         -- low/medium/high
    helper_types            JSONB DEFAULT '["grammar","vocabulary","sentence_pattern"]'::jsonb,
    correction_tendency     VARCHAR(20) DEFAULT 'none',        -- 用户主动选择 (决策 6)
    response_style          VARCHAR(20) DEFAULT 'concise',
    show_to_room            BOOLEAN DEFAULT FALSE,             -- 始终仅个人侧边区可见
    created_at              TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX uq_ahi_user_room ON ai_helper_invasiveness(user_id, room_id);
```

**关键决策**：**房主无法为他人的 AI 行为做设置**——每个用户各自的侵入度。

---

### 3.9 录音文件表 `room_recordings`

```sql
CREATE TABLE room_recordings (
    id                      TEXT PRIMARY KEY,
    room_id                 TEXT NOT NULL REFERENCES language_rooms(id) ON DELETE CASCADE,
    user_id                 TEXT NOT NULL,                    -- 录音归属用户
    storage_path            TEXT NOT NULL,                    -- 文件路径
    file_size_bytes         BIGINT,
    duration_seconds        INT,
    started_at              TIMESTAMP NOT NULL,
    ended_at                TIMESTAMP NOT NULL,
    format                  VARCHAR(10) DEFAULT 'opus',       -- 音频格式
    is_deleted              BOOLEAN DEFAULT FALSE,
    created_at              TIMESTAMP NOT NULL DEFAULT NOW()
);
```

**关键决策**：录音**可选**（决策 10）；房主拥有，但参与者可访问/删除自己的发言部分。

---

### 3.10 词汇便签表 `vocabulary_captures`

```sql
CREATE TABLE vocabulary_captures (
    id                      TEXT PRIMARY KEY,
    user_id                 TEXT NOT NULL,                    -- 词汇归属用户
    room_id                 TEXT NOT NULL REFERENCES language_rooms(id) ON DELETE CASCADE,
    transcript_id           TEXT REFERENCES room_transcripts(id) ON DELETE SET NULL,
    card_id                 TEXT,                              -- 关联 FlashCard.id (类型=data)
    word                    TEXT NOT NULL,
    translation             TEXT,
    context_sentence        TEXT,
    language                VARCHAR(20),
    captured_at             TIMESTAMP NOT NULL DEFAULT NOW(),
    created_at              TIMESTAMP NOT NULL DEFAULT NOW()
);
```

**关键决策**：词汇便签**复用** FlashCard（`card_type='data'`, `source='language_room'`），本表只做**软链接 + 上下文**记录。

---

### 3.11 房间邀请表 `room_invitations`

```sql
CREATE TABLE room_invitations (
    id                      TEXT PRIMARY KEY,
    room_id                 TEXT NOT NULL REFERENCES language_rooms(id) ON DELETE CASCADE,
    inviter_id              TEXT NOT NULL,
    invitee_id              TEXT,                              -- NULL = 邀请链接
    invitation_token        TEXT NOT NULL,
    is_used                 BOOLEAN DEFAULT FALSE,
    expires_at              TIMESTAMP,
    created_at              TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX uq_ri_token ON room_invitations(invitation_token);
```

**关键决策**：邀请制（决策 2），不设公开房间；token 一次性使用。

---

## 4. 枚举值定义

### 4.1 参与者类型 `participant_type`

- `human` — 真人
- `ai_companion` — AI 同伴（参与对话）
- `ai_assistant` — AI 辅助者（静默监听）

### 4.2 AI 侵入度 `ai_intrusion_level`

| 值 | 行为 |
|---|------|
| `low` | 仅用户召唤 |
| `medium` | 检测卡顿/错误时提示（仅个人侧边区） |
| `high` | 主动提供建议（仅个人侧边区）|

### 4.3 AI 纠错倾向 `correction_tendency`

- `none` — 不纠错
- `occasional` — 偶尔纠错
- `proactive` — 主动纠错

### 4.4 房间类型 `room_type`

- `1v1` — 两人对话
- `small` — 3-5 人
- `medium` — 6-10 人
- `large` — 11+ 人

---

## 5. 数据归属总览

| 归属模块 | 存储内容 |
|---------|---------|
| **本模块** | 房间、参与者、会话、转写、场景、AI 角色/配置、录音、词汇便签、邀请 |
| `ErrorBookEntry`（复用）| 错误标记 |
| `FlashCard`（复用）| 转写生成的卡片、词汇便签 |
| `ExplainCard`（复用）| 文字辅助 |
| `CognitiveNode`（已存在）| 关联的知识点 |
| 全局事件流 | `LanguageRoomCompleted` 事件（按参与者维度）|
| 0005 MoodStress（可选）| 接收 `voice_feature_stream`（**接口已定义，实现解耦**）|
