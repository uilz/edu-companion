# 合并重构 + AI→题库自动映射

> 两个架构决策：
> 1. 不双轨，老 API 直接合并重构
> 2. 对话中 AI 生成题目自动存入当前专题题库

---

## 1. 合并策略

### 1.1 核心原则

```
旧路由前缀: /api/practice/*
新路由前缀: /api/practice/*  （同一前缀，替换实现）

不保留双前缀，不 redirect，不并行。
v7.0 部署后所有练习流量走新实现。
```

### 1.2 替换对照表

| 现有端点 | v7.0 实现方式 | 兼容处理 |
|---------|--------------|---------|
| `POST /api/practice/submit` | 新 `practice_attempts` 表 + `update_node_after_attempt()` | 签名微调 |
| `POST /api/practice/sessions/{id}/complete` | 新 `SessionMachine.transition()` | 内部逻辑替换 |
| `GET /api/practice/errors` | 新 `practice_attempts WHERE is_wrong=true` | 查询换表 |
| `POST /api/practice/errors/{id}/review` | 新 `review_submit()` | 内部替换 |
| `POST /api/practice/hint` | 复用 `get_hint_for_question()` | 不改 |
| `GET /api/practice/stats` | 新表聚合 | 查询换源 |
| `POST /api/practice/errors/{id}/analyze` | 复用 `analyze_error_entry()` | 不改 |
| `GET /api/practice/knowledge/state` | 共用 `CognitiveNode` | 不改 |

### 1.3 旧数据迁移

```python
# backend/app/services/practice_migration.py

"""
旧表 → 新表数据迁移（一次性脚本）。

旧表：questions (UUID PK, skill_id TEXT, 对话流创建)
新表：questions (TEXT PK, cognitive_node_ids[], bank_id)

迁移策略：
- 旧 questions 表里的每条记录 → 插入新 questions 表
- 根据 skill_id 查找对应的 CognitiveNode
- 创建 topic 级题库，旧题归入
- 旧 practice_sessions / attempt 记录 → 写入新表
"""

def migrate_legacy_data(user_id: str = DEFAULT_USER_ID) -> dict:
    """
    迁移单个用户的旧练习数据到新表。
    返回迁移统计。
    """
    from app.db.database import get_db
    db = get_db()
    stats = {"questions": 0, "sessions": 0, "attempts": 0, "errors": 0}

    # 1. 迁移旧题目 → 新 questions 表
    # 旧表: questions(UUID id, skill_id TEXT, subject TEXT, ...)
    # 新表: questions(TEXT id, bank_id TEXT, cognitive_node_ids TEXT[], ...)
    old_questions = db.fetchall("SELECT * FROM questions WHERE ...")
    for q in old_questions:
        # 找到对应的 cognitive_node
        node = _find_node_by_skill(q.get("skill_id", ""), user_id)
        # 找到或创建对应 topic 的题库
        bank_id = _ensure_bank_for_node(node.id if node else None, user_id, db)
        # 插入新表
        new_id = f"q_migrated_{q['question_id']}"
        db.execute(
            """INSERT INTO questions (id, bank_id, user_id, question_type, stem,
               options, answer, analysis, difficulty, cognitive_node_ids, source,
               status, created_at, updated_at)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
               ON CONFLICT (id) DO NOTHING""",
            (...)
        )
        stats["questions"] += 1

    logger.info("迁移完成: %s", stats)
    return stats


def _find_node_by_skill(skill_id: str, user_id: str):
    """
    根据老系统的 skill_id 查找对应的 CognitiveNode。
    skill_id 可能是 'calculus_derivative' 这种模板名，
    也可能是 CognitiveNode 的 id。
    """
    from app.cognitive.storage import get_node, search_nodes
    # 先当 node_id 查
    node = get_node(skill_id, user_id)
    if node:
        return node
    # 再按名称搜索
    results = search_nodes(skill_id, user_id, limit=1)
    return results[0] if results else None


def _ensure_bank_for_node(node_id: str | None, user_id: str, db) -> str:
    """
    确保某个 cognitive_node 有对应的题库。
    如果不存在则自动创建。

    bank_id 命名规则：
    - topic 级: `bnk_{node_id}`
    - 其他级: 自动创建或查找 topic 级祖先
    """
    if not node_id:
        # 无关联节点 → 默认通用题库
        bank_id = f"bnk_{user_id}_default"
        _ensure_bank_exists(db, bank_id, user_id, "通用题库")
        return bank_id

    bank_id = f"bnk_{node_id}"

    existing = db.fetchone(
        "SELECT id FROM question_banks WHERE id = %s",
        (bank_id,),
    )
    if existing:
        return bank_id

    # 获取节点信息用于命名
    from app.cognitive.storage import get_node
    node = get_node(node_id, user_id)
    label = node.label if node else node_id

    db.execute(
        """INSERT INTO question_banks
           (id, user_id, name, description, ref_node_id, metadata, created_at, updated_at)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
        (bank_id, user_id, f"{label}题库", f"自动为知识点「{label}」创建的题库",
         node_id, "{}", datetime.now().isoformat(), datetime.now().isoformat()),
    )
    return bank_id
```

### 1.4 部署切换步骤

```
1. 执行迁移脚本（逐用户迁移旧数据到新表）
2. 部署新 API 代码（/api/practice/* 实现已替换）
3. 旧 endpoints 返回 301 + 说明
4. 观察 1 周，确认无报错
5. 清理旧表（可选）
```

---

## 2. AI→题库自动映射

### 2.1 核心规则

```
对话中 AI 生成题目 → 自动存入当前对话所在专题的题库

                   ┌─────────────────┐
                   │ 当前对话        │
                   │ conversation_id │
                   └────────┬────────┘
                            │
                            ▼
                   ┌─────────────────┐
                   │ 查找 topic_id   │  ← conversation 已关联 topic
                   └────────┬────────┘
                            │
                            ▼
                   ┌────────────────────────┐
                   │ 查找/创建题库          │
                   │ bnk_{topic_id}         │
                   └────────┬───────────────┘
                            │
                            ▼
                   ┌─────────────────┐
                   │ AI 出题          │
                   │ generate_and_   │
                   │ save(bank_id)   │
                   └─────────────────┘
```

### 2.2 实现

```python
# backend/app/services/practice_ai_bank_resolver.py

"""
AI 生成题目时的题库解析器。
根据对话上下文自动确定题目归属的题库。
"""

from typing import Optional


def resolve_bank_for_conversation(
    conversation_id: str,
    user_id: str,
    db,
    user_specified_bank_id: Optional[str] = None,
) -> str:
    """
    根据对话上下文，解析题目应存入的题库 ID。

    优先级：
    1. 用户明确指定 → user_specified_bank_id
    2. 对话有关联 topic → bnk_{topic_id}
    3. 对话有关联 partition → bnk_{partition_id}
    4. 兜底 → 用户默认题库
    """
    if user_specified_bank_id:
        # 用户明确说了"生成到 xxx 题库"
        return user_specified_bank_id

    # 查找对话的 topic_id
    row = db.fetchone(
        "SELECT topic_id, partition_id FROM conversations WHERE id = %s",
        (conversation_id,),
    )
    if row and row.get("topic_id"):
        topic_id = row["topic_id"]
        bank_id = f"bnk_{topic_id}"
        _ensure_bank(db, bank_id, user_id, topic_id)
        return bank_id

    if row and row.get("partition_id"):
        partition_id = row["partition_id"]
        bank_id = f"bnk_{partition_id}"
        _ensure_bank(db, bank_id, user_id, partition_id)
        return bank_id

    # 兜底
    default_id = f"bnk_{user_id}_default"
    _ensure_default_bank(db, default_id, user_id)
    return default_id


def resolve_bank_for_node(
    node_id: str,
    user_id: str,
    db,
) -> str:
    """
    根据 cognitive_node 解析题库。
    - 如果是 topic 级 → 直接 bnk_{node_id}
    - 如果是 domain/partition → 查找下 topic 或创建本级
    """
    from app.cognitive.storage import get_node

    node = get_node(node_id, user_id)
    if not node:
        return f"bnk_{user_id}_default"

    # topic 级直接映射
    if node.level == "topic":
        bank_id = f"bnk_{node_id}"
        _ensure_bank(db, bank_id, user_id, node_id)
        return bank_id

    # concept/atom 级→找父节点 topic
    if node.level in ("concept", "atom"):
        parent_id = node.parent
        if parent_id:
            parent = get_node(parent_id, user_id)
            if parent and parent.level == "topic":
                bank_id = f"bnk_{parent_id}"
                _ensure_bank(db, bank_id, user_id, parent_id)
                return bank_id

    # domain/partition 级
    bank_id = f"bnk_{node_id}"
    _ensure_bank(db, bank_id, user_id, node_id)
    return bank_id


def _ensure_bank(db, bank_id: str, user_id: str, ref_node_id: str) -> None:
    """确保题库存在，不存在则自动创建"""
    existing = db.fetchone(
        "SELECT id FROM question_banks WHERE id = %s", (bank_id,)
    )
    if existing:
        return

    from app.cognitive.storage import get_node
    node = get_node(ref_node_id, user_id)
    label = node.label if node else ref_node_id
    level = node.level if node else ""

    db.execute(
        """INSERT INTO question_banks
           (id, user_id, name, description, ref_node_id, ref_node_level,
            metadata, created_at, updated_at)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
        (
            bank_id, user_id,
            f"{label}题库",
            f"自动为{level}「{label}」创建的题库",
            ref_node_id, level,
            "{}",
            datetime.now().isoformat(),
            datetime.now().isoformat(),
        ),
    )


def _ensure_default_bank(db, bank_id: str, user_id: str) -> None:
    db.execute(
        """INSERT INTO question_banks
           (id, user_id, name, description, metadata, created_at, updated_at)
           VALUES (%s, %s, %s, %s, %s, %s, %s)
           ON CONFLICT (id) DO NOTHING""",
        (bank_id, user_id, "通用题库", "未分类题目的默认题库",
         "{}", datetime.now().isoformat(), datetime.now().isoformat()),
    )
```

### 2.3 data model 变更

`question_banks` 表新增字段：

```sql
-- 原有字段
id              TEXT PRIMARY KEY,      -- bnk_{ref_node_id}
user_id         TEXT NOT NULL,
name            VARCHAR(255),
description     TEXT,
import_source   VARCHAR(50),
metadata        JSONB DEFAULT '{}',

-- 新增字段（v7.0 合并后）
ref_node_id     TEXT,                  -- 关联的 CognitiveNode ID
ref_node_level  VARCHAR(20),           -- topic | domain | partition | concept | atom
auto_created    BOOLEAN DEFAULT false, -- 是否自动创建
question_count  INT DEFAULT 0,        -- 题目数缓存

created_at      TIMESTAMPTZ DEFAULT now(),
updated_at      TIMESTAMPTZ DEFAULT now(),
deleted_at      TIMESTAMPTZ
```

### 2.4 AI 对话中出题的完整流程

```python
# 在 ConversationLLM（对话 AI）中集成

"""
用户在对话中说："帮我出 5 道导数的题"

处理流程：
1. 对话 AI 识别 intent = "generate_questions"
2. 解析参数：count=5, topic="导数"
3. 调用 practice_ai_bank_resolver 确定题库
4. 调用 generate_and_save()
5. 返回确认消息 + 题目预览
"""

# backend/app/services/conversation_llm.py 中的新增处理

async def handle_question_generation(
    user_id: str,
    conversation_id: str,
    params: dict,
) -> str:
    """
    处理"帮我出题"类意图的对话响应。
    params 可能包含:
    {
        "count": 5,
        "topic": "导数",          // 可选，AI 从对话中提取
        "bank_id": "bnk_xxx",    // 可选，用户指定
        "difficulty": 0.6,       // 可选
        "bloom_level": "apply",  // 可选
    }
    """
    from app.db.database import get_db
    from app.services.practice_ai_bank_resolver import resolve_bank_for_conversation
    from app.services.practice_ai_generator import generate_and_save

    db = get_db()

    # 1. 确定题库
    bank_id = params.get("bank_id") or resolve_bank_for_conversation(
        conversation_id, user_id, db, user_specified_bank_id=None,
    )

    # 2. 确定知识点（从参数或对话上下文）
    topic = params.get("topic", "")
    node_ids = None
    if topic:
        from app.cognitive.storage import search_nodes
        matches = search_nodes(topic, user_id, limit=3)
        if matches:
            node_ids = [m.id for m in matches]

    # 3. 生成并保存
    count = params.get("count", 3)
    saved = await generate_and_save(
        bank_id=bank_id,
        user_id=user_id,
        skill_id=node_ids[0] if node_ids else "",
        subject="",
        count=count,
        bloom_level=params.get("bloom_level", "apply"),
        difficulty=params.get("difficulty", 0.5),
    )

    # 4. 返回确认（用于 AI 回复）
    bank_name = db.fetchone(
        "SELECT name FROM question_banks WHERE id = %s", (bank_id,)
    )
    bank_label = bank_name["name"] if bank_name else "当前题库"

    preview_lines = []
    for i, q in enumerate(saved[:3]):
        preview_lines.append(f"{i+1}. {q['stem'][:60]}...")
    if len(saved) > 3:
        preview_lines.append(f"...还有 {len(saved)-3} 道")

    return (
        f"✅ 已为你生成 {len(saved)} 道题，存入「{bank_label}」\n\n"
        + "\n".join(preview_lines) + "\n\n"
        + "去练习 → /practice 或说「开始练习」"
    )
```

### 2.5 用户指定题库的 AI 指令解析

用户可以在对话中通过自然语言指定题库：

| 用户说 | 解析结果 |
|--------|---------|
| "帮我出 5 道导数的题" | `{count:5, topic:"导数", bank:auto}` |
| "生成 3 道微分方程的选择题，存入微积分题库" | `{count:3, topic:"微分方程", bank_name:"微积分题库"}` |
| "出 10 道题，我要考试" | `{count:10, mode:"exam"}` |
| "针对我上周错的知识点出 5 道题" | `{count:5, source:"error_book"}` |

在 conversation_llm 中的处理：

```python
# 在 tool_dispatch.py 或 conversation_llm.py 中

QUESTION_GENERATION_PROMPT = """用户说出了类似"帮我出题"的话。
请解析出题参数，以 JSON 格式返回：

{{
  "intent": "generate_questions",
  "count": <数字>,
  "topic": "<知识点名称或null>",
  "bank_name": "<用户指定的题库名或null>",
  "difficulty": <0-1或null>,
  "bloom_level": "<remember|understand|apply|analyze|evaluate|create|null>",
  "mode": "<practice|exam|null>",
  "source": "<error_book|null>"
}}

如果用户没有明确指定，全部设为 null。
"""
```

---

## 3. 知识图谱中的题库展示

### 3.1 FocusGraph 中的题库节点

每个 topic 级的 CognitiveNode，如果有关联题库，在 FocusGraph 中显示一个特殊图标：

```
┌─────────────┐
│  📈 导数     │  ← topic 节点（现有）
│  ├─ 💬 对话  │
│  └─ 📝 题库  │  ← 新增题库入口（N 道题）
└─────────────┘
```

点击"题库" → 跳转到 `/practice/banks/bnk_{topic_id}`

### 3.2 前端集成

```typescript
// focuspage.tsx 中图谱节点的扩展操作菜单

const nodeActions = [
  { label: "开始练习", icon: "✏️", action: () => startPractice(node.id) },
  { label: "查看题库", icon: "📝", action: () => router.push(`/practice/banks/bnk_${node.id}`) },
  { label: "AI 出题", icon: "🤖", action: () => aiGenerateForNode(node.id) },
];
```

---

## 4. question_banks 完整建表语句（最终版）

```sql
CREATE TABLE IF NOT EXISTS question_banks (
    id              TEXT PRIMARY KEY,           -- bnk_{ref_node_id}
    user_id         TEXT NOT NULL,
    name            VARCHAR(255) NOT NULL,
    description     TEXT DEFAULT '',
    import_source   VARCHAR(50) DEFAULT 'manual',
    
    -- 图谱关联（核心）
    ref_node_id     TEXT,                       -- 关联的 CognitiveNode ID
    ref_node_level  VARCHAR(20),                -- topic | domain | partition | concept | atom
    
    -- 状态
    auto_created    BOOLEAN DEFAULT false,      -- 是否自动创建
    question_count  INT DEFAULT 0,              -- 题目数缓存
    
    -- 用户偏好（该题库的练习配置）
    preferences     JSONB DEFAULT '{}',
    metadata        JSONB DEFAULT '{}',
    
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW(),
    deleted_at      TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_qb_user ON question_banks(user_id) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_qb_ref_node ON question_banks(ref_node_id) WHERE deleted_at IS NULL;
```

---

## 5. 对原方案的修改汇总

| 原方案内容 | 修改后 |
|-----------|--------|
| 双轨并行（新旧 API 共存） | ❌ 废弃 → **直接合并重构** |
| `question_banks` 无图谱关联 | ✅ 新增 `ref_node_id` + `ref_node_level` |
| AI 出题归属需手动指定 | ✅ **自动根据对话上下文映射到 topic 题库** |
| 需要迁移旧 data | ✅ 新增迁移脚本 |
| 图谱节点无题库入口 | ✅ FocusGraph 扩展开启题库/出题动作 |
| 无用户指定题库的 AI 指令 | ✅ AI 解析 `bank_name` 参数 |

---

## 6. 实施路线图（更新版）

| 阶段 | 内容 |
|------|------|
| **7.0.1a** | 建表（最终版）+ 旧数据迁移脚本 + `resolve_bank_for_conversation()` |
| **7.0.1b** | `generate_and_save()` + AI→题库自动映射 + `POST /api/practice/questions/generate` |
| **7.0.2a** | `QuestionGenerator` 适配新表 + `handle_question_generation()` 集成到对话 LLM |
| **7.0.2b** | 练习 session CRUD + SessionMachine + `POST /api/practice/sessions/*` |
| **7.0.3** | 逐题提交 + 认知更新 + 即时判题（替换现有 `/api/practice/submit`） |
| **7.0.4** | 错题本 + 斩题 + 复习调度 |
| **7.0.5** | 考试模式 |
| **7.0.6** | 图谱/对话/秘书全面联通 |
| **7.0.7** | 前端全面适配 + 旧 API 清理 |
