# 学习数据联动 — 适配当前系统架构

> 基于现有认知模型（CognitiveNode → Belief/Activation/Scheduling/PracticeEvent）的精确适配方案。

---

## 4.1 现有可复用基础设施

### 4.1.1 CognitiveNode 的练习相关字段

现有 `CognitiveNode` 已包含全部所需子系统，无需新增字段：

```python
# backend/app/cognitive/models.py — 已有字段
class CognitiveNode(BaseModel):
    # ...
    belief: Belief              # Beta 分布 (alpha/beta → proficiency_mean)
    activation: Activation      # ACT-R 激活值 (base_level, retrieval_prob, latency_ms)
    scheduling: Scheduling      # 调度 (urgency, next_review, next_action_type)
    practice_events: list[PracticeEvent]   # 历史练习事件列表
    practice_summary: PracticeSummary       # 聚合摘要
    error_clusters: list[ErrorCluster]      # 错误聚类
    trend: Trend                # 学习趋势 (velocity_ewma, stagnation_days)
    prediction: Prediction      # 预测编码 (prediction_error)
    diagnostic: Diagnostic      # 诊断评估
```

关键子模型：

```python
class Belief(BaseModel):
    alpha: float = 2.0           # Beta 先验 α
    beta: float = 2.0            # Beta 先验 β
    proficiency_mean: float = 0.5   # α/(α+β) — 掌握度
    proficiency_precision: float = 4.0  # α+β — 置信度
    peak_proficiency: float = 0.5
    last_updated: float

class Activation(BaseModel):
    base_level: float = 0.0      # ACT-R 基础激活
    retrieval_prob: float = 0.5  # 提取概率
    latency_ms: float = 5000.0   # 提取延迟

class Scheduling(BaseModel):
    urgency: float = 0.0         # 紧迫度
    next_review: float = 0.0     # 下次复习时间戳
    next_action_type: str = "none"  # review | deep_processing | none

class PracticeEvent(BaseModel):
    timestamp: float
    success: bool
    latency_ms: float = 0
    weight: float = 1.0
    error_embedding: list[float] | None = None

class PracticeSummary(BaseModel):
    total_attempts: int = 0
    correct_attempts: int = 0
    total_time_spent: float = 0.0
    recent_success_rate_7d: float = 0.0
    mean_latency_7d: float = 0.0
    last_practiced: float | None = None
```

### 4.1.2 已有存储函数

```python
# backend/app/cognitive/storage.py
get_node(node_id, user_id)        # 获取 CognitiveNode
upsert_node(node, user_id)        # 保存 CognitiveNode（完整覆盖）
append_event(event)               # 追加认知事件
vector_search(query_embedding, ...)  # 向量检索（Python 余弦距离，无需 pgvector）
get_urgent_nodes(limit, user_id)  # 紧迫度最高的节点
```

### 4.1.3 已有事件系统

```python
class CognitiveEvent(BaseModel):
    event_id: str
    event_type: str               # 'practice.submitted', 'practice.correct', etc.
    user_id: str
    node_id: str | None
    timestamp: float
    payload: dict                 # 自定义负载
```

---

## 4.2 练习→认知模型更新（精确实现）

### 4.2.1 每题作答后的立即更新

```python
# backend/app/services/practice_cognitive.py

import time
from app.cognitive.storage import get_node, upsert_node, append_event
from app.cognitive.models import (
    CognitiveNode, CognitiveEvent, PracticeEvent, PracticeSummary,
    ErrorCluster, Belief, Activation, Scheduling, Trend,
)

def update_node_after_attempt(
    node_id: str,
    user_id: str,
    is_correct: bool,
    time_spent_ms: float,
    error_embedding: list[float] | None = None,
) -> CognitiveNode:
    """
    单题作答后更新 CognitiveNode 的 belief / activation / scheduling / practice_events。
    同步调用，复用现有 psycopg2 连接池。
    """
    node = get_node(node_id, user_id)
    if node is None:
        raise ValueError(f"Node {node_id} not found")

    now = time.time()
    practice_event = PracticeEvent(
        timestamp=now,
        success=is_correct,
        latency_ms=time_spent_ms,
        weight=1.0,
        error_embedding=error_embedding,
    )

    # ── 1. 追加练习事件 ──
    node.practice_events.append(practice_event)
    # 保留最近 50 条
    if len(node.practice_events) > 50:
        node.practice_events = node.practice_events[-50:]

    # ── 2. 更新 PracticeSummary ──
    summary = node.practice_summary
    summary.total_attempts += 1
    summary.total_time_spent += time_spent_ms / 1000.0  # 秒
    if is_correct:
        summary.correct_attempts += 1
    summary.last_practiced = now

    # 计算近 7 天正确率
    seven_days_ago = now - 7 * 86400
    recent = [e for e in node.practice_events if e.timestamp > seven_days_ago]
    if recent:
        summary.recent_success_rate_7d = sum(1 for e in recent if e.success) / len(recent)
        summary.mean_latency_7d = sum(e.latency_ms for e in recent) / len(recent)

    node.practice_summary = summary

    # ── 3. 更新 Belief（Beta 分布） ──
    belief = node.belief
    if is_correct:
        belief.alpha += 1
    else:
        belief.beta += 1
    belief.proficiency_mean = belief.alpha / (belief.alpha + belief.beta)
    belief.proficiency_precision = belief.alpha + belief.beta
    if belief.proficiency_mean > belief.peak_proficiency:
        belief.peak_proficiency = belief.proficiency_mean
    belief.last_updated = now
    node.belief = belief

    # ── 4. 更新 Activation（ACT-R 基础激活） ──
    activation = node.activation
    # ACT-R: B = ln(Σ t_j^(-d))，简化版用指数衰减
    decay = 0.5  # 衰减参数
    activation.base_level = _update_actr_base_level(
        activation.base_level, now, time_spent_ms / 1000.0, decay
    )
    # 提取概率 = 1 / (1 + e^(-(base_level - threshold)/s))
    activation.retrieval_prob = 1.0 / (1.0 + 2.718 ** (-(activation.base_level - 0.5) / 0.3))
    # 提取延迟 = F * e^(-base_level)
    activation.latency_ms = 5000.0 * (2.718 ** (-activation.base_level))
    node.activation = activation

    # ── 5. 更新 Scheduling ──
    sched = node.scheduling
    if not is_correct:
        sched.urgency = min(1.0, sched.urgency + 0.15)
        sched.next_action_type = "review"
    else:
        sched.urgency = max(0.0, sched.urgency - 0.05)
        if sched.urgency < 0.1:
            sched.next_action_type = "none"
    # 下次复习时间：按遗忘曲线估算
    if sched.urgency > 0.3:
        # urgency 越高，复习间隔越短
        interval_hours = max(1, int(24 * (1.0 - sched.urgency)))
        sched.next_review = now + interval_hours * 3600
    node.scheduling = sched

    # ── 6. 错误聚类 ──
    if not is_correct and error_embedding:
        _update_error_clusters(node, error_embedding, now)

    # ── 7. 更新 Trend ──
    _update_trend(node, is_correct, now)

    # ── 8. 持久化 ──
    upsert_node(node, user_id)

    # ── 9. 追加认知事件 ──
    append_event(CognitiveEvent(
        event_type="practice.submitted",
        user_id=user_id,
        node_id=node_id,
        timestamp=now,
        payload={
            "is_correct": is_correct,
            "latency_ms": time_spent_ms,
            "proficiency_after": round(belief.proficiency_mean, 4),
        },
    ))

    return node


def _update_actr_base_level(
    current: float, now: float, time_spent_sec: float, decay: float = 0.5
) -> float:
    """
    简化 ACT-R base_level 更新。
    每次练习增加一次激活，按时间衰减累积。
    """
    # 新实践的效果：练习时间越长，激活增量越大（但呈对数）
    practice_boost = 0.3 * (1.0 - 2.718 ** (-time_spent_sec / 30.0))
    # 衰减当前值
    decayed = current * (2.718 ** (-decay * 0.01))  # 微小衰减
    return decayed + practice_boost


def _update_error_clusters(
    node: CognitiveNode, error_embedding: list[float], now: float
) -> None:
    """
    将错误嵌入添加到最匹配的 ErrorCluster 中。
    使用余弦距离与现有聚类匹配。
    """
    from app.cognitive.storage import _cosine_normalize, _cosine_similarity

    norm = _cosine_normalize(error_embedding)
    best_idx = -1
    best_sim = 0.3  # 最低匹配阈值

    for i, cluster in enumerate(node.error_clusters):
        if cluster.embedding:
            sim = _cosine_similarity(norm, cluster.embedding)
            if sim > best_sim:
                best_sim = sim
                best_idx = i

    if best_idx >= 0:
        # 归入现有聚类
        node.error_clusters[best_idx].count += 1
        node.error_clusters[best_idx].last_seen = now
        # 滑动平均更新聚类中心
        old = node.error_clusters[best_idx].embedding
        node.error_clusters[best_idx].embedding = [
            (a * 0.7 + b * 0.3) for a, b in zip(old, error_embedding)
        ]
    else:
        # 新建聚类
        cluster_id = f"ec_{node.id}_{int(now)}"
        node.error_clusters.append(ErrorCluster(
            cluster_id=cluster_id,
            count=1,
            last_seen=now,
            embedding=error_embedding,
        ))


def _update_trend(node: CognitiveNode, is_correct: bool, now: float) -> None:
    """更新学习趋势（滑动窗口正确率 + 速度）"""
    trend = node.trend
    # 记录近期 proficiency
    trend.recent_proficiencies.append(node.belief.proficiency_mean)
    if len(trend.recent_proficiencies) > 20:
        trend.recent_proficiencies = trend.recent_proficiencies[-20:]

    # EWMA 速度
    current_rate = 1.0 if is_correct else 0.0
    trend.velocity_ewma = 0.3 * current_rate + 0.7 * trend.velocity_ewma

    # 停滞检测：如果近 10 次记录 proficiency 变化 < 0.02
    if len(trend.recent_proficiencies) >= 10:
        recent = trend.recent_proficiencies[-10:]
        variation = max(recent) - min(recent)
        if variation < 0.02 and trend.velocity_ewma < 0.3:
            trend.stagnation_days += 1 / 24  # 每次练习约 1h
            trend.direction = "plateau"
        else:
            trend.stagnation_days = max(0, trend.stagnation_days - 0.5)
            if trend.velocity_ewma > 0.6:
                trend.direction = "ascending"
            elif trend.velocity_ewma < 0.3:
                trend.direction = "descending"
            else:
                trend.direction = "stable"

    node.trend = trend
```

### 4.2.2 批量提交时的批量更新

```python
async def update_nodes_after_session(
    user_id: str,
    question_results: list[dict],
) -> list[dict]:
    """
    一次练习 session 结束后，批量更新所有涉及的认知节点。
    question_results: [
        {"node_ids": [...], "is_correct": bool, "time_spent_ms": int, "error_embedding": ...},
        ...
    ]
    返回每个 node 更新后的状态快照。
    """
    node_updates = {}  # node_id -> aggregated stats

    for qr in question_results:
        for node_id in qr["node_ids"]:
            if node_id not in node_updates:
                node_updates[node_id] = {
                    "total": 0, "correct": 0, "time_ms": 0,
                    "error_embeddings": [],
                }
            nu = node_updates[node_id]
            nu["total"] += 1
            if qr["is_correct"]:
                nu["correct"] += 1
            nu["time_ms"] += qr.get("time_spent_ms", 0)
            if not qr["is_correct"] and qr.get("error_embedding"):
                nu["error_embeddings"].append(qr["error_embedding"])

    results = []
    for node_id, nu in node_updates.items():
        # 取平均正确率作为本次的 is_correct
        avg_correct = nu["correct"] / nu["total"]
        node = update_node_after_attempt(
            node_id=node_id,
            user_id=user_id,
            is_correct=avg_correct > 0.5,
            time_spent_ms=nu["time_ms"] / nu["total"],
            error_embedding=nu["error_embeddings"][0] if nu["error_embeddings"] else None,
        )
        results.append({
            "node_id": node_id,
            "label": node.label,
            "proficiency_after": round(node.belief.proficiency_mean, 4),
            "precision_after": round(node.belief.proficiency_precision, 4),
            "urgency_after": round(node.scheduling.urgency, 4),
            "direction": node.trend.direction,
        })

    return results
```

---

## 4.3 错题→秘书提案（精确实现）

```python
# backend/app/services/practice_secretary.py

import time
from app.cognitive.storage import get_node
from app.services.secretary import add_proposal  # 假设的秘书 API


def check_and_propose(user_id: str, error_node_ids: list[str]) -> list[dict]:
    """
    练习结束后，检查各出错节点是否需要触发秘书提案。
    阈值：某知识点单次练习错误 >= 2 道 或 累计错误 >= 3 道。
    """
    proposals = []
    now = time.time()

    for node_id in set(error_node_ids):
        node = get_node(node_id, user_id)
        if not node:
            continue

        # 统计本次错误数
        error_count_this_session = error_node_ids.count(node_id)

        # 统计累计错误
        recent_errors = [
            e for e in node.practice_events[-20:]
            if not e.success
        ]
        total_errors = len(recent_errors)

        trigger = False
        proposal_type = None

        if error_count_this_session >= 2:
            trigger = True
            proposal_type = "mass_errors"
        elif total_errors >= 3:
            trigger = True
            proposal_type = "accumulated_errors"

        if trigger and node.belief.proficiency_mean < 0.5:
            proposal = _generate_proposal(node, proposal_type, error_count_this_session)
            proposals.append(proposal)
            # 写入秘书提案表
            add_proposal(user_id, proposal)

    return proposals


def _generate_proposal(node, error_type: str, error_count: int) -> dict:
    """生成秘书提案内容"""
    templates = {
        "mass_errors": (
            "你最近在「{label}」上错了 {count} 道题，"
            "主要集中在 {area}。要不要我帮你梳理一下核心公式？"
        ),
        "accumulated_errors": (
            "「{label}」的错题积累到了 {count} 道，"
            "建议针对性地练习一下，我可以给你出几道专项题。"
        ),
    }

    # 从 error_clusters 推断薄弱区域
    area = "基础知识"
    if node.error_clusters:
        # 取最大聚类作为薄弱区域描述
        top_cluster = max(node.error_clusters, key=lambda c: c.count)
        area = f"第 {top_cluster.cluster_id} 类错误模式"

    template = templates.get(error_type, templates["accumulated_errors"])
    message = template.format(
        label=node.label,
        count=error_count if error_type == "mass_errors" else len([
            e for e in node.practice_events[-20:] if not e.success
        ]),
        area=area,
    )

    return {
        "type": "practice_intervention",
        "node_id": node.id,
        "node_label": node.label,
        "priority": "high" if node.belief.proficiency_mean < 0.3 else "medium",
        "message": message,
        "suggested_actions": [
            {"type": "practice", "label": f"做 {node.label} 专项练习", "node_id": node.id},
            {"type": "explain", "label": f"让 AI 讲解 {node.label}", "node_id": node.id},
        ],
        "created_at": time.time(),
    }
```

---

## 4.4 自适应出题（精确实现）

```python
# backend/app/services/practice_adaptive.py

from app.cognitive.storage import get_node, list_all_nodes, vector_search


async def adaptive_select(
    bank_id: str,
    user_id: str,
    count: int,
    node_ids: list[str] | None = None,
    exclude_recent: bool = True,
) -> list[dict]:
    """
    基于现有 CognitiveNode.mastery 的自适应选题。
    复用现有 vector_search() 做题目↔节点匹配。

    选题比例：薄弱 : 巩固 : 保持 = 5 : 3 : 2
    （非硬编码 6:3:1，防止薄弱节点过多时学生疲劳）
    """
    # 1. 获取目标节点的掌握度
    if node_ids:
        nodes = []
        for nid in node_ids:
            node = get_node(nid, user_id)
            if node:
                nodes.append(node)
    else:
        nodes = list_all_nodes(user_id)
        # 只保留 atom 和 concept 级别
        nodes = [n for n in nodes if n.level in ("atom", "concept")]

    # 2. 按 mastery 分组
    weak = [n for n in nodes if n.belief.proficiency_mean < 0.4]
    medium = [n for n in nodes if 0.4 <= n.belief.proficiency_mean < 0.7]
    strong = [n for n in nodes if n.belief.proficiency_mean >= 0.7]

    # 3. 动态比例：如果薄弱节点少，减少薄弱比例
    weak_ratio = 0.5 if len(weak) >= 3 else 0.3
    medium_ratio = 0.3
    strong_ratio = 1.0 - weak_ratio - medium_ratio

    weak_target = max(1, int(count * weak_ratio))
    medium_target = max(1, int(count * medium_ratio))
    strong_target = count - weak_target - medium_target

    selected = []

    # 4. 从薄弱节点选题
    selected.extend(await _pick_questions_for_nodes(
        bank_id, weak, weak_target, exclude_recent
    ))

    # 5. 从巩固节点选题
    selected.extend(await _pick_questions_for_nodes(
        bank_id, medium, medium_target, exclude_recent
    ))

    # 6. 从已掌握节点选题（防止遗忘）
    selected.extend(await _pick_questions_for_nodes(
        bank_id, strong, strong_target, exclude_recent
    ))

    return selected


async def _pick_questions_for_nodes(
    bank_id: str,
    nodes: list,
    target_count: int,
    exclude_recent: bool,
) -> list[dict]:
    """
    为一组认知节点选题。
    遍历节点，对每个节点查询其关联题目。
    实际实现使用 SQL: 
    SELECT * FROM questions 
    WHERE bank_id = $1 
      AND cognitive_node_ids && $2 
      AND status = 'active'
      AND is_slashed = false
    ORDER BY random() LIMIT $3
    """
    if not nodes or target_count <= 0:
        return []

    node_ids = [n.id for n in nodes]
    from app.db.database import get_db
    db = get_db()

    rows = db.fetchall(
        """SELECT q.* FROM questions q
           WHERE q.bank_id = %s
             AND q.cognitive_node_ids && %s
             AND q.status = 'active'
             AND q.is_slashed = false
             AND q.deleted_at IS NULL
           ORDER BY random()
           LIMIT %s""",
        (bank_id, node_ids, target_count),
    )

    return [_row_to_question(r) for r in rows]


def _row_to_question(row: dict) -> dict:
    """数据库行 → API 输出"""
    return {
        "id": row["id"],
        "bank_id": row["bank_id"],
        "question_type": row["question_type"],
        "stem": row["stem"],
        "options": row.get("options") or [],
        "difficulty": row.get("difficulty", 3),
        "cognitive_node_ids": row.get("cognitive_node_ids") or [],
    }
```

---

## 4.5 题目↔认知节点关联（精确实现）

```python
# backend/app/services/practice_import_matcher.py

from app.cognitive.storage import vector_search, get_embedding


def match_question_to_nodes(
    question_stem: str,
    user_id: str,
    top_k: int = 3,
    min_similarity: float = 0.35,
) -> list[dict]:
    """
    题目导入时自动匹配 CognitiveNode。
    使用已有 embedding pipeline 和 vector_search()。

    步骤：
    1. 对题目内容生成 embedding（复用 save_message 的 embedding 管道）
    2. 用 vector_search() 检索最相似的 atom/concept 节点
    3. 返回建议关联列表供用户确认
    """
    from app.services.embedding import get_embedding  # 假设的 embedding 服务

    # 1. 生成 embedding
    embedding = get_embedding(question_stem)
    if not embedding:
        return []

    # 2. 向量检索 atom 级节点
    results = vector_search(
        query_embedding=embedding,
        user_id=user_id,
        level="atom",
        limit=top_k,
        min_similarity=min_similarity,
    )

    # 3. 也检索 concept 级
    concept_results = vector_search(
        query_embedding=embedding,
        user_id=user_id,
        level="concept",
        limit=top_k,
        min_similarity=min_similarity - 0.1,
    )

    return results + concept_results
```

---

## 4.6 事件驱动联动（异步处理管道）

```python
# backend/app/services/practice_event_handler.py

"""
整体处理流程（同步调用的协程编排）：

    practice/submit (API)
         │
         ▼
    update_nodes_after_session()      ← 更新 belief/activation/scheduling
         │
         ├──▶ check_and_propose()     ← 检查是否需要秘书提案
         │
         └──▶ 返回节点状态快照到前端     ← 图谱更新、前端展示

     事件写入：
    append_event('practice.submitted')  ← 认知事件流
"""
```

---

## 4.7 现有基础设施复用清单

| 功能 | 复用组件 | 注意事项 |
|------|---------|---------|
| 认知节点读写 | `cognitive/storage.py` → `get_node()`, `upsert_node()` | 同步调用，直接可用 |
| 事件写入 | `cognitive/storage.py` → `append_event()` | 事件类型统一用 `'practice.submitted'` |
| embedding 生成 | `services/embedding.py`（或 `save_message` 同管道） | 384 维，OpenVINO 模型 |
| 向量检索 | `cognitive/storage.py` → `vector_search()` | Python 余弦距离，无需 pgvector |
| 紧迫节点查询 | `cognitive/storage.py` → `get_urgent_nodes()` | 用于复习调度 |
| session 管理 | `services/practice_service.py` | 已有错题本、提醒、统计 |
| 秘书提案 | `services/secretary.py` | 等待确认实际 API 签名 |
| 图谱更新 | 前端 FocusGraph + ForceGraph | 重新 fetchGraphData() 即可 |

---

## 4.8 数据流转总图

```
     题目导入
        │
        ▼
  match_question_to_nodes() ──→ 建议认知节点关联
        │
        ▼
  questions.cognitive_node_ids ← 持久化关联

     练习组题
        │
        ▼
  adaptive_select() ──→ 按掌握度选择题目
        │
        ▼
  student 作答 → 提交

     提交处理
        │
        ▼
  update_node_after_attempt()  ←─ 逐题更新(n times)
        │
        ├── belief.alpha/beta 更新
        ├── activation.base_level 更新
        ├── scheduling.urgency 更新
        ├── practice_events 追加
        ├── practice_summary 更新
        ├── error_clusters 更新
        ├── trend 更新
        ├── upsert_node() 持久化
        └── append_event() 写入事件流
        │
        ▼
  check_and_propose()  ←── 检查错题阈值
        │
        └── add_proposal() → 秘书提案
        │
        ▼
  返回 node 快照 → 前端图谱更新 / 对话联动
```
