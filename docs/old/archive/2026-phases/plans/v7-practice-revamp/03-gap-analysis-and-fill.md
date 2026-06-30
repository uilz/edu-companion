# 缺口分析与补充设计

> 对比现有 practice API 与 v7.0 新方案，找出关键缺口并逐个填上。

---

## 1. 缺口分析

### 1.1 现有 vs 新方案对照

| 维度 | 现有系统 | v7.0 新方案 | 缺口 |
|------|---------|-------------|------|
| 题目存储 | 内存 `Question` 模型 + `question_id` UUID | `questions` 表（TEXT ID） | 数据迁移 + 双写策略 |
| 题库 | 无，基于 `skill_id` 直接出题 | `question_banks` 表分层管理 | 新增逻辑 |
| 练习会话 | 内存 `PracticeSession` 模型, 提交后丢弃 | `practice_sessions` 表持久化 | 需要兼容过渡 |
| 错题本 | `error_book` 表, 单表操作 | `practice_attempts` 带 `is_wrong`/`mastered` 状态机 | 状态扩展 |
| 认知更新 | `update_cognitive_after_practice()` 基于 BKT | `update_node_after_attempt()` 基于 CognitiveNode | 双轨并行 |
| 组题策略 | 无明确策略，由对话流触发 | `adaptive_select()` 三层比例 | 新增算法 |
| 考试模式 | 无 | 计时+答题卡+评分 | 全新功能 |
| 导入管道 | 无 | 多格式导入 + AI 匹配 | 全新功能 |

### 1.2 关键决策：双轨并行 vs 全线切换

```
选项 A: 双轨并行（推荐）
──────────────────────
对话流触发的练习 → 老路径（现有 practice.py）
独立题库页面练习 → 新路径（v7.0 new API）
                   ↘ 6个月后废弃老路径

选项 B: 全线切换
──────────────────────
所有练习 → 新路径，老 API 做适配壳

→ 选 A，因为：
  1. 现有对话流练习已稳定，不宜破坏
  2. 新题库功能逐步上线，给用户适应期
  3. 双轨期间可以对比数据，验证新方案
```

---

## 2. 练习会话状态机

### 2.1 状态流转

```
                     ┌──────────┐
                     │  CREATED  │  ← 组题完成，未开始
                     └────┬─────┘
                          │  start()
                          ▼
                     ┌──────────┐
              ┌──────│  ACTIVE  │──────┐
              │      └────┬─────┘      │
              │           │            │
         pause()     complete()    cancel()
              │           │            │
              ▼           ▼            ▼
       ┌──────────┐ ┌──────────┐ ┌──────────┐
       │  PAUSED  │ │COMPLETED │ │ CANCELLED│
       └────┬─────┘ └──────────┘ └──────────┘
            │
       resume()
            │
            ▼
       ┌──────────┐
       │  ACTIVE  │
       └──────────┘

特殊情况：超时（考试模式）
  ACTIVE + 倒计时归零 → 自动 COMPLETED
```

### 2.2 状态机实现

```python
# backend/app/services/practice_session_manager.py

import time
from enum import Enum
from typing import Optional
from datetime import datetime


class SessionStatus(str, Enum):
    CREATED = "created"
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"


class SessionMachine:
    """
    练习会话状态机。
    每步状态变更都写入 practice_sessions 表 + 触发事件。
    """

    # 允许的状态转换
    TRANSITIONS = {
        SessionStatus.CREATED:    {SessionStatus.ACTIVE},
        SessionStatus.ACTIVE:     {SessionStatus.PAUSED, SessionStatus.COMPLETED,
                                   SessionStatus.CANCELLED, SessionStatus.TIMEOUT},
        SessionStatus.PAUSED:     {SessionStatus.ACTIVE, SessionStatus.CANCELLED},
        SessionStatus.COMPLETED:  set(),
        SessionStatus.CANCELLED:  set(),
        SessionStatus.TIMEOUT:    set(),
    }

    def __init__(self, db):
        self.db = db

    def transition(self, session_id: str, to_status: SessionStatus) -> dict:
        """执行状态转换"""
        row = self.db.fetchone(
            "SELECT * FROM practice_sessions WHERE id = %s",
            (session_id,),
        )
        if not row:
            raise ValueError(f"Session not found: {session_id}")

        current = SessionStatus(row["status"])
        if to_status not in self.TRANSITIONS[current]:
            raise ValueError(
                f"Invalid transition: {current.value} → {to_status.value}"
            )

        now = datetime.now().isoformat()
        updates = {"status": to_status.value}

        if to_status == SessionStatus.ACTIVE and current == SessionStatus.PAUSED:
            # 恢复：累计暂停时间
            paused_duration = self._accumulate_paused(row)
            updates["metadata"] = self._merge_metadata(
                row.get("metadata"), {"paused_duration_sec": paused_duration}
            )

        if to_status in (SessionStatus.COMPLETED, SessionStatus.TIMEOUT):
            updates["finished_at"] = now
            # 计算耗时
            started = row["started_at"]
            duration = (datetime.fromisoformat(now) - started).total_seconds()
            updates["duration_seconds"] = int(duration)

        # 更新数据库
        set_clause = ", ".join(f"{k} = %s" for k in updates)
        params = list(updates.values()) + [session_id]
        self.db.execute(
            f"UPDATE practice_sessions SET {set_clause} WHERE id = %s",
            tuple(params),
        )

        # 触发事件
        self._emit_event(session_id, current.value, to_status.value)

        return {**row, **updates}

    def _accumulate_paused(self, row: dict) -> int:
        """计算累计暂停时间"""
        meta = row.get("metadata") or {}
        return meta.get("paused_duration_sec", 0)

    def _merge_metadata(self, existing, new) -> str:
        import json
        meta = json.loads(existing) if isinstance(existing, str) else (existing or {})
        meta.update(new)
        return json.dumps(meta)

    def _emit_event(self, session_id: str, from_status: str, to_status: str) -> None:
        """发布状态变更事件（供认知引擎/秘书消费）"""
        from app.cognitive.storage import append_event
        from app.cognitive.models import CognitiveEvent
        append_event(CognitiveEvent(
            event_type=f"session.{to_status}",
            user_id="",
            node_id=None,
            payload={
                "session_id": session_id,
                "from_status": from_status,
                "to_status": to_status,
            },
        ))
```

---

## 3. 练习 API 路由设计（v7.0 新增）

### 3.1 路由总览

```
前缀: /api/v7/practice

┌── 题库管理
│   GET    /banks                    → 列表
│   POST   /banks                    → 创建
│   GET    /banks/{id}               → 详情（含题目统计）
│   PATCH  /banks/{id}               → 编辑
│   DELETE /banks/{id}               → 删除（软删除）
│
├── 题目管理
│   GET    /banks/{id}/questions     → 题库题目列表（分页+筛选）
│   POST   /banks/{id}/questions     → 手动添加单题
│   GET    /questions/{id}           → 题目详情
│   PATCH  /questions/{id}           → 编辑题目
│   DELETE /questions/{id}           → 删除
│   PATCH  /questions/{id}/slash     → 斩题/恢复
│   PATCH  /questions/{id}/favorite  → 收藏/取消
│
├── AI 出题
│   POST   /questions/generate               → AI 生成并存入
│   POST   /questions/generate-bulk           → 批量生成
│   POST   /questions/generate-from-material  → 资料衍生
│   POST   /questions/{id}/similar            → 同类变体
│   POST   /questions/{id}/explain            → AI 深入讲解
│
├── 练习会话
│   POST   /sessions                          → 创建（含组题）
│   GET    /sessions/{id}                     → 会话详情
│   PATCH  /sessions/{id}/start               → 开始
│   PATCH  /sessions/{id}/pause               → 暂停
│   PATCH  /sessions/{id}/resume              → 恢复
│   PATCH  /sessions/{id}/complete            → 完成
│   DELETE /sessions/{id}                     → 取消
│   GET    /sessions                          → 历史列表
│   POST   /sessions/{id}/submit              → 提交答案
│   GET    /sessions/{id}/result              → 成绩报告
│
├── 考试模式
│   POST   /exam                              → 创建考试
│   GET    /exam/{id}/time                    → 剩余时间
│   POST   /exam/{id}/submit-all              → 全部提交
│   GET    /exam/{id}/answer-sheet            → 答题卡
│
├── 错题本
│   GET    /errors                            → 错题列表
│   GET    /errors/review-due                 → 到期复习
│   POST   /errors/{id}/review                → 复习提交
│   GET    /errors/{id}/materials             → 关联资料推荐
│
├── 导入
│   POST   /import/upload                     → 上传文件
│   POST   /import/preview                    → 预览（含认知节点匹配）
│   POST   /import/confirm                    → 确认导入
│   GET    /import/history                    → 导入历史
│
├── 统计
│   GET    /stats/overview                    → 总览
│   GET    /stats/daily                       → 每日趋势
│   GET    /stats/weak-areas                  → 薄弱区域
│
└── 自适应组题（内部调用）
    POST   /adaptive/select                   → 按掌握度选题
```

### 3.2 核心请求/响应契约

**创建练习会话：**

```
POST /api/v7/practice/sessions
{
  "bank_id": "bnk_xxx",
  "mode": "adaptive",           // random | sequential | adaptive | exam
  "count": 10,
  "question_types": ["single", "multiple", "judge"],
  "node_ids": ["node_1", "node_2"],  // 可选，限定知识点
  "config": {
    "instant_feedback": true,
    "auto_next": true,
    "shuffle": true
  }
}

Response 201:
{
  "session_id": "ps_xxx",
  "status": "created",
  "questions": [
    {
      "id": "q_xxx",
      "question_type": "single",
      "stem": "...",
      "options": [
        {"label": "A", "content": "..."},
        {"label": "B", "content": "..."},
        {"label": "C", "content": "..."},
        {"label": "D", "content": "..."}
      ],
      "difficulty": 0.5,
      "cognitive_node_ids": ["node_1"],
      "index": 0
    }
    // ...
  ],
  "total": 10,
  "created_at": "2026-06-03T10:30:00"
}
```

**提交答案：**

```
POST /api/v7/practice/sessions/{id}/submit
{
  "question_id": "q_xxx",
  "user_answer": "A",             // 或 ["A","C"]（多选）或 "文本"（填空）
  "time_spent_seconds": 45.2,
  "hints_used": 0
}

Response 200:
{
  "is_correct": true,
  "correct_answer": "A",
  "explanation": "因为...所以选A",
  "knowledge_update": {
    "node_id": "node_1",
    "proficiency_before": 0.45,
    "proficiency_after": 0.52,
    "direction": "ascending"
  },
  "next_question_index": 2,
  "session_progress": {
    "answered": 3,
    "total": 10,
    "correct": 2,
    "wrong": 1
  }
}
```

### 3.3 创建会话（含组题）的精确实现

```python
# backend/app/api/v7_practice.py（示意）

@router.post("/sessions")
async def create_session(body: dict, user_id: str = DEFAULT_USER_ID):
    """
    创建练习会话 — 核心流程：
    1. 根据 mode 组题
    2. 写入 practice_sessions 表
    3. 写入 questions 的关联（session_questions 多对多）
    4. 返回题目（不含答案）
    """
    bank_id = body["bank_id"]
    mode = body.get("mode", "adaptive")
    count = body.get("count", 10)
    node_ids = body.get("node_ids")
    config = body.get("config", {})

    from datetime import datetime
    from app.db.database import get_db
    db = get_db()

    # 1. 组题
    if mode == "adaptive":
        questions = await adaptive_select_with_ai_fallback(
            bank_id, user_id, count, node_ids
        )
    elif mode == "random":
        questions = _random_select(db, bank_id, count, node_ids)
    elif mode == "sequential":
        questions = _sequential_select(db, bank_id, body.get("start_index", 0), count, node_ids)
    else:
        raise HTTPException(400, f"Unknown mode: {mode}")

    if not questions:
        raise HTTPException(400, "没有符合条件的题目")

    # 2. 创建 session
    session_id = f"ps_{user_id}_{int(datetime.now().timestamp())}"
    now = datetime.now().isoformat()

    # 收集涉及的认知节点
    all_node_ids = set()
    for q in questions:
        for nid in q.get("cognitive_node_ids") or []:
            all_node_ids.add(nid)

    db.execute(
        """INSERT INTO practice_sessions
           (id, user_id, bank_id, session_type, mode, config,
            total_count, cognitive_node_ids, status, started_at, created_at)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
        (
            session_id, user_id, bank_id,
            "practice", mode, json.dumps(config),
            len(questions), list(all_node_ids),
            "created", now, now,
        ),
    )

    # 3. 写入题目排序（session_questions 关联表）
    for i, q in enumerate(questions):
        sq_id = f"sq_{session_id}_{i}"
        db.execute(
            """INSERT INTO session_questions
               (id, session_id, question_id, sort_order)
               VALUES (%s, %s, %s, %s)""",
            (sq_id, session_id, q["id"], i),
        )

    # 4. 返回题目（不含答案）
    safe_questions = []
    for q in questions:
        safe_questions.append({
            "id": q["id"],
            "question_type": q.get("question_type", "single"),
            "stem": q.get("stem", ""),
            "options": q.get("options", []),
            "difficulty": q.get("difficulty", 0.5),
            "cognitive_node_ids": q.get("cognitive_node_ids", []),
            "index": safe_questions.__len__(),  # 注意：不准确，实际应该用 enumerate
        })
    # 修正 index
    for i, q in enumerate(safe_questions):
        q["index"] = i

    return {
        "session_id": session_id,
        "status": "created",
        "questions": safe_questions,
        "total": len(safe_questions),
        "created_at": now,
    }
```

---

## 4. 错题复习调度算法

### 4.1 调度优先级计算

```python
# backend/app/services/practice_review_scheduler.py

import time
from datetime import datetime, timedelta
from app.cognitive.storage import get_node


def compute_review_priority(
    node_id: str,
    user_id: str,
    error_count: int,
    consecutive_correct: int,
    last_error_time: float,
) -> float:
    """
    计算错题复习优先级（0~1），用于排序"到期复习"列表。

    综合考量四个因子：
    1. 紧急度因子 — 基于 CognitiveNode.scheduling.urgency
    2. 遗忘因子 — 距离上次错误的时间
    3. 掌握置信度 — Beta 分布的总样本量
    4. 连续正确惩罚 — 连续正确次数越多，优先级越低
    """
    node = get_node(node_id, user_id)
    now = time.time()

    # 因子1：认知节点的 urgency
    urgency = node.scheduling.urgency if node else 0.0

    # 因子2：遗忘因子（距离上次错误越久，遗忘越多）
    days_since_error = (now - last_error_time) / 86400
    # 1天以内不着急，3天开始提升，7天以上高优先级
    forget_factor = min(1.0, max(0.0, (days_since_error - 1.0) / 6.0))

    # 因子3：置信度反比（样本少 → 需要更多验证）
    precision = node.belief.proficiency_precision if node else 4.0
    # precision < 6 → 置信度低，提高优先级
    confidence_factor = max(0.0, 1.0 - (precision - 4.0) / 10.0)

    # 因子4：连续正确惩罚
    # 连续正确 2 次 → 优先级降为 0（已掌握）
    if consecutive_correct >= 2:
        mastery_factor = 0.0
    else:
        mastery_factor = 1.0 - (consecutive_correct * 0.5)

    # 综合评分（加权）
    priority = (
        urgency * 0.35 +
        forget_factor * 0.30 +
        confidence_factor * 0.20 +
        mastery_factor * 0.15
    )

    return round(min(1.0, max(0.0, priority)), 4)


def get_review_queue(user_id: str, limit: int = 20) -> list[dict]:
    """
    获取用户待复习的错题队列（按优先级倒序）。

    从 practice_attempts 表筛选：
    - is_wrong = true
    - mastered = false
    - 按优先级排序，取前 limit
    """
    from app.db.database import get_db
    db = get_db()

    # 获取最近 100 条未掌握的错题
    rows = db.fetchall(
        """SELECT pa.*, q.stem, q.question_type, q.options, q.answer, q.analysis,
                  q.cognitive_node_ids, q.difficulty
           FROM practice_attempts pa
           JOIN questions q ON pa.question_id = q.id
           WHERE pa.user_id = %s
             AND pa.is_wrong = true
             AND pa.mastered = false
             AND pa.deleted_at IS NULL
           ORDER BY pa.created_at DESC
           LIMIT 100""",
        (user_id,),
    )

    scored = []
    for r in rows:
        # 取第一个 cognitive_node_id
        node_ids = r.get("cognitive_node_ids") or []
        node_id = node_ids[0] if node_ids else None

        # 计算该题累计的错题统计
        wrong_count = r.get("wrong_count", 1)
        consecutive_correct = r.get("consecutive_correct", 0)
        last_error = r["created_at"].timestamp() if hasattr(r["created_at"], "timestamp") else time.time()

        priority = compute_review_priority(
            node_id=node_id or "unknown",
            user_id=user_id,
            error_count=wrong_count,
            consecutive_correct=consecutive_correct,
            last_error_time=last_error,
        )

        if priority > 0.05:  # 低于阈值跳过
            scored.append({
                "attempt_id": r["id"],
                "question_id": r["question_id"],
                "stem": r["stem"],
                "question_type": r["question_type"],
                "options": r.get("options"),
                "correct_answer": r["answer"],
                "analysis": r.get("analysis", ""),
                "wrong_count": wrong_count,
                "consecutive_correct": consecutive_correct,
                "node_ids": node_ids,
                "priority": priority,
            })

    scored.sort(key=lambda x: -x["priority"])
    return scored[:limit]
```

### 4.2 复习提交逻辑

```python
def review_submit(
    attempt_id: str,
    user_id: str,
    is_correct: bool,
) -> dict:
    """
    错题复习提交：
    - 连续答对 2 次 → mastered = true
    - 答错 → consecutive_correct 归零
    - 每次更新 update_node_after_attempt()
    """
    from app.db.database import get_db
    db = get_db()

    attempt = db.fetchone(
        "SELECT * FROM practice_attempts WHERE id = %s AND user_id = %s",
        (attempt_id, user_id),
    )
    if not attempt:
        raise ValueError("Attempt not found")

    current_cc = attempt.get("consecutive_correct", 0)
    current_wc = attempt.get("wrong_count", 1)

    if is_correct:
        new_cc = current_cc + 1
        mastered = new_cc >= 2  # 连续 2 次正确 → 已掌握
        new_wc = current_wc
    else:
        new_cc = 0
        mastered = False
        new_wc = current_wc + 1  # 累计错误次数 +1

    db.execute(
        """UPDATE practice_attempts
           SET consecutive_correct = %s, wrong_count = %s, mastered = %s
           WHERE id = %s""",
        (new_cc, new_wc, mastered, attempt_id),
    )

    # 同步更新 CognitiveNode
    from app.services.practice_cognitive import update_node_after_attempt
    for nid in attempt.get("cognitive_node_ids") or []:
        update_node_after_attempt(
            node_id=nid,
            user_id=user_id,
            is_correct=is_correct,
            time_spent_ms=0,
        )

    return {
        "attempt_id": attempt_id,
        "mastered": mastered,
        "consecutive_correct": new_cc,
        "wrong_count": new_wc,
        "needs_more_review": not mastered,
    }
```

---

## 5. 考试模式的精确实现

### 5.1 考试创建

```python
@router.post("/api/v7/practice/exam")
async def create_exam(body: dict, user_id: str = DEFAULT_USER_ID):
    """
    创建考试模式的练习会话。

    body:
    {
        "bank_id": "...",
        "title": "期中模拟测试",
        "config": {
            "single_count": 15,
            "multiple_count": 5,
            "judge_count": 5,
            "duration_minutes": 60,
            "pass_score": 60,
            "shuffle_options": true
        },
        "node_ids": ["..."],  // 限定知识点范围（可选）
        "material_ids": ["..."]  // 基于资料组卷（可选）
    }
    """
    config = body["config"]
    bank_id = body.get("bank_id")
    material_ids = body.get("material_ids")

    # 1. 确定题型比例
    type_counts = {
        "single": config.get("single_count", 0),
        "multiple": config.get("multiple_count", 0),
        "judge": config.get("judge_count", 0),
        "fill": config.get("fill_count", 0),
    }
    total = sum(type_counts.values())
    if total == 0:
        raise HTTPException(400, "考试题目数量不能为 0")

    # 2. 基于资料组卷
    if material_ids:
        questions = await generate_exam_from_materials(
            bank_id, user_id, material_ids, type_counts
        )
        title = body.get("title", "基于资料的模拟考试")
    else:
        # 从题库按比例抽题
        questions = _select_exam_questions(
            db, bank_id, type_counts, body.get("node_ids")
        )
        title = body.get("title", "模拟考试")

    # 3. 创建 session（session_type = 'exam'）
    session_id = f"exam_{user_id}_{int(datetime.now().timestamp())}"
    now = datetime.now().isoformat()

    db.execute(
        """INSERT INTO practice_sessions
           (id, user_id, bank_id, session_type, mode, config,
            total_count, status, started_at, created_at)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
        (
            session_id, user_id, bank_id,
            "exam", "random",
            json.dumps({
                **config,
                "title": title,
                "started_at": now,
                "deadline": (datetime.now() + timedelta(minutes=config["duration_minutes"])).isoformat(),
            }),
            total, "active", now, now,
        ),
    )

    # 4. 写入 session_questions
    for i, q in enumerate(questions):
        # ...

    # 5. 返回（含剩余时间）
    return {
        "session_id": session_id,
        "title": title,
        "questions": safe_questions,
        "total": total,
        "duration_minutes": config["duration_minutes"],
        "deadline": deadline,
        "pass_score": config.get("pass_score", 60),
    }
```

### 5.2 考试自动判分

```python
def score_exam(session_id: str) -> dict:
    """
    考试自动判分。
    遍历 session_questions 中的每条 practice_attempt，按题型判分。

    评分规则：
    - 单选题：答对得满分，答错 0 分
    - 多选题：全对得满分，漏选得一半，多选/错选 0 分
    - 判断题：同单选题
    - 填空题：精确匹配得满分，部分匹配按比例
    """
    from app.db.database import get_db
    db = get_db()

    session = db.fetchone(
        "SELECT * FROM practice_sessions WHERE id = %s", (session_id,)
    )
    if not session:
        raise ValueError("Session not found")

    config = json.loads(session.get("config") or "{}")
    total_q = session["total_count"]

    # 获取该 session 的所有答题记录
    attempts = db.fetchall(
        """SELECT pa.*, q.question_type, q.answer as correct_answer
           FROM practice_attempts pa
           JOIN questions q ON pa.question_id = q.id
           WHERE pa.session_id = %s
           ORDER BY pa.created_at""",
        (session_id,),
    )

    # 各题型分值分配
    single_count = config.get("single_count", 0) or 1
    multiple_count = config.get("multiple_count", 0) or 1
    judge_count = config.get("judge_count", 0) or 1
    fill_count = config.get("fill_count", 0) or 1

    # 确保分母不为 0
    total_points = max(1,
        single_count + multiple_count * 2 + judge_count + fill_count * 1.5
    )

    score = 0.0
    detail = []

    for a in attempts:
        qtype = a["question_type"]
        user_ans = json.loads(a.get("user_answer") or "null")
        correct = json.loads(a.get("correct_answer") or "[]") if isinstance(a.get("correct_answer"), str) else a.get("correct_answer")
        is_correct = a["is_correct"]

        # 计算每题得分
        if qtype == "single":
            q_score = 100.0 / total_q if is_correct else 0
        elif qtype == "multiple":
            if is_correct:
                q_score = 2 * (100.0 / total_q)
            else:
                q_score = 0
        elif qtype == "judge":
            q_score = 100.0 / total_q if is_correct else 0
        elif qtype == "fill":
            q_score = 1.5 * (100.0 / total_q) if is_correct else 0
        else:
            q_score = 100.0 / total_q if is_correct else 0

        score += q_score
        detail.append({
            "question_id": a["question_id"],
            "question_type": qtype,
            "is_correct": is_correct,
            "score": round(q_score, 1),
        })

    final_score = round(score, 1)
    pass_score = config.get("pass_score", 60)
    passed = final_score >= pass_score

    return {
        "session_id": session_id,
        "total_questions": total_q,
        "answered": len(attempts),
        "correct": sum(1 for d in detail if d["is_correct"]),
        "score": final_score,
        "pass_score": pass_score,
        "passed": passed,
        "detail": detail,
    }
```

---

## 6. 前端页面架构

### 6.1 页面路由

```
/practice                  → 练习首页（题库列表 + 快速入口）
/practice/banks/{id}       → 题库详情（题目列表 + 导入 + 出题）
/practice/sessions/{id}    → 练习进行中
/practice/exam/{id}        → 考试模式
/practice/errors           → 错题本
/practice/stats            → 练习统计
```

### 6.2 练习进行中 — 组件树

```
PracticeSessionPage
├── SessionHeader
│   ├── ProgressBar        ← 已答/总数 + 正确/错误
│   ├── Timer              ← 仅考试模式
│   └── ExitButton
│
├── QuestionCard           ← 当前题目
│   ├── QuestionStem       ← 题干（支持 Markdown/LaTeX）
│   ├── QuestionTypeBadge  ← 题型标签
│   ├── OptionsArea        ← 选择/填空/判断
│   │   ├── SingleChoiceOption
│   │   ├── MultipleChoiceOption
│   │   ├── JudgeOption
│   │   └── FillInput
│   └── QuestionMeta
│       ├── DifficultyBadge
│       └── CognitiveNodeTags  ← 关联知识点标签，点击跳转图谱
│
├── FeedbackArea           ← 提交后显示
│   ├── CorrectIndicator   ← ✅ / ❌
│   ├── Explanation        ← 解析
│   ├── KnowledgeUpdate    ← 掌握度变化动画
│   ├── SimilarQuestionBtn ← "再做一道同类题"
│   └── AskAIBtn           ← "请教 AI" → 触发对话
│
├── ActionBar
│   ├── HintButton         ← 提示（支持渐进 3 级）
│   ├── FavoriteButton     ← 收藏
│   ├── PreviousButton     ← 上一题
│   └── NextButton         ← 下一题/提交
│
└── AnswerSheet            ← 答题卡（考试模式）
    └── AnswerGrid         ← 格子列表（绿/红/灰/白）
```

### 6.3 状态管理（Zustand store）

```typescript
// frontend/src/store/practice-store.ts

interface PracticeSessionState {
  // 当前会话
  sessionId: string | null;
  status: 'idle' | 'loading' | 'active' | 'paused' | 'completed';
  questions: PracticeQuestion[];
  currentIndex: number;
  
  // 答题记录（本地缓存）
  answers: Record<string, {
    answer: string;
    isCorrect?: boolean;
    timeSpent: number;
    hintsUsed: number;
  }>;
  
  // 统计
  progress: { answered: number; total: number; correct: number; wrong: number };
  
  // 考试模式
  examMode: boolean;
  deadline: string | null;
  remainingSeconds: number;
  
  // 反馈状态
  showFeedback: boolean;
  currentFeedback: {
    isCorrect: boolean;
    explanation: string;
    knowledgeUpdate?: { nodeId: string; before: number; after: number };
  } | null;
  
  // 操作
  createSession: (config: CreateSessionConfig) => Promise<void>;
  submitAnswer: (questionId: string, answer: string) => Promise<void>;
  nextQuestion: () => void;
  prevQuestion: () => void;
  pauseSession: () => Promise<void>;
  resumeSession: () => Promise<void>;
  completeSession: () => Promise<void>;
  getHint: (questionId: string, level: number) => Promise<string>;
}
```

---

## 7. 集成矩阵：每个触点精确实现

### 7.1 练习 ↔ 对话

| 触点 | 触发条件 | 实现方式 |
|------|---------|---------|
| "请教 AI" | 用户在练习反馈区点击 | 从 `question.cognitive_node_ids` 取第一个节点 → 创建对话并注入 `context = {question_stem, user_answer, explanation}` |
| 对话中出题 | 秘书提案"要做题吗" | 用户确认 → 调用 `create_session({mode:'adaptive', node_ids:[...], count:5})` → 跳转 `/practice/sessions/{id}` |
| 练习后反思 | session 完成后 | 秘书收到 `session.completed` 事件 → 生成反思提案：如"你这次练习准确率 70%，其中「导数」错了2道，想深入看看吗？" |

### 7.2 练习 ↔ 图谱

| 触点 | 触发条件 | 实现方式 |
|------|---------|---------|
| 图谱节点→练习 | 点击节点→"开始练习" | `create_session({mode:'adaptive', node_ids:[nodeId], count:10})` |
| 练习→图谱更新 | 每题提交后 | `update_node_after_attempt()` → 前端重新 `fetchGraphData()` |
| 薄弱区域高亮 | 图谱渲染时 | 查询 `get_urgent_nodes()` → 这些节点在 FocusGraph 中加红色边框 |

### 7.3 练习 ↔ 秘书

| 触点 | 触发条件 | 实现方式 |
|------|---------|---------|
| 错题诊断提案 | 某知识点错题达 3 道 | `check_and_propose()` → 写入 secretary 表 |
| 考前冲刺 | 日历检测到考试 | 秘书事件 listener → 查找今日考试 → 生成 exam session |
| 复习提醒 | 每日首次打开 | 查询 `get_review_queue()` → 待复习 > 5 条则显示 badge |

### 7.4 练习 ↔ 解释卡片

| 触点 | 触发条件 | 实现方式 |
|------|---------|---------|
| 解析/讲解 | 练习反馈区 | 直接显示 `analysis` 字段（非解释卡片，不需要浮动） |
| 深入讲解 | 用户点击"讲解知识点" | 调用 `generate_explanation()` → 结果存入 `explain_cards` 表 → 作为解释卡片展示 |

---

## 8. 需要创建的数据库迁移（汇总）

```sql
-- 7.0.1 基础表
CREATE TABLE IF NOT EXISTS question_banks ( ... );
CREATE TABLE IF NOT EXISTS questions ( ... );
CREATE TABLE IF NOT EXISTS practice_sessions ( ... );
CREATE TABLE IF NOT EXISTS practice_attempts ( ... );
CREATE TABLE IF NOT EXISTS session_questions (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    question_id TEXT NOT NULL,
    sort_order INT NOT NULL DEFAULT 0,
    user_answer JSONB,
    is_correct BOOLEAN,
    time_spent_seconds INT DEFAULT 0,
    hints_used INT DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS question_favorites ( ... );
CREATE TABLE IF NOT EXISTS slashed_questions ( ... );

-- 7.0.4 错题复习补充字段（在 practice_attempts 上）
-- 这些字段已包含在 practice_attempts 建表语句中

-- 7.0.5 索引
CREATE INDEX IF NOT EXISTS idx_sq_session ON session_questions(session_id);
CREATE INDEX IF NOT EXISTS idx_sq_question ON session_questions(question_id);
```

---

## 9. 关键数据流总结

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│  导入/出题    │     │  自适应组题   │     │  练习进行中   │
│              │     │              │     │              │
│ file → parse │────▶│ adaptive_    │────▶│ 逐题作答      │
│ AI → generate│     │ select()     │     │ 即时判题      │
│ match → node │     │ AI fallback  │     │ 显示反馈      │
└──────────────┘     └──────────────┘     └──────┬───────┘
                                                 │
                                                 ▼
                                        ┌──────────────┐
                                        │  提交处理     │
                                        │              │
                                        │ practice_    │
                                        │ attempts 写入 │
                                        │              │
                                        ├──▶ cognitive/ │
                                        │   update_node │
                                        ├──▶ check_and_ │
                                        │   propose()   │
                                        └──────┬───────┘
                                               │
                          ┌────────────────────┼────────────────────┐
                          ▼                    ▼                    ▼
                   ┌────────────┐      ┌────────────┐      ┌────────────┐
                   │ 错题复习    │      │ 秘书提案    │      │ 图谱更新    │
                   │            │      │            │      │            │
                   │ review_    │      │ 生成诊断    │      │ fetchGraph │
                   │ submit()   │      │ 写入提案    │      │ Data()     │
                   │ mastered?  │      │ 推送通知    │      │ 节点变色    │
                   └────────────┘      └────────────┘      └────────────┘
```

---

## 10. 与现有系统的兼容策略

| 现有 API | v7.0 新 API | 兼容方式 |
|---------|-------------|---------|
| `POST /api/practice/submit` | `POST /api/v7/practice/sessions/{id}/submit` | 并行运行，数据不同源 |
| `GET /api/practice/errors` | `GET /api/v7/practice/errors` | 错题数据来自不同表 |
| `GET /api/practice/stats` | `GET /api/v7/practice/stats/overview` | 新统计聚合新表数据 |
| `GET /api/practice/knowledge/state` | — | 共用 `CognitiveNode`，无需改 |
| `POST /api/practice/hint` | — | 复用 `get_hint_for_question()` |

> 双轨策略：对话流触发的练习走老 API（不动），独立题库页面走新 API（全功能）。
> 6 个月后评估老 API 用量，决定是否迁移。
