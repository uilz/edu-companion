# Phase 8 实施文档

> 版本: v1.0  
> 基于 `docs/phase8/readme.md` 设计 + 代码审计后的实现修正

---

## 目录

- [0. 核心决策清单](#0-核心决策清单)
- [1. 数据模型变更（增量，不破坏现有表）](#1-数据模型变更增量不破坏现有表)
- [2. 新引擎：GrowthEngine](#2-新引擎growthengine)
- [3. 分类引擎重写（classifier.py）](#3-分类引擎重写classifierpy)
- [4. 新 API 端点](#4-新-api-端点)
- [5. 现有文件改动清单](#5-现有文件改动清单)
- [6. 新文件清单](#6-新文件清单)
- [7. 前端改动](#7-前端改动)
- [8. 实施顺序](#8-实施顺序)
- [9. 风险与回避策略](#9-风险与回避策略)

---

## 0. 核心决策清单

| 维度 | 方案 | 理由 |
|:-----|:-----|:------|
| 异步/同步 | **同步**（与现有后端一致） | `cognitive/storage.py` 全同步，不宜混用 |
| `subsystems` | **只存 Phase 8 元数据**，现有 30+ 字段保持 | 零迁移成本，Phase 7 兼容 |
| `retrieval_prob` | **删除该列**，用 embedding 相似度 > 0.1 替代 | 新节点无模型数据，相似度天然适合 |
| 消息存储 | **不动** `conversations`/`messages`（UserData 内） | 大幅缩小改动面 |
| 分类器 | **重写** `classifier.py`，替换 keyword → vector | 核心升级 |
| 48h 清理 | **Secretary 模块**，复用 `ActiveChecker` | 零外部依赖，随进程生命周期 |
| 10轮重分类 | `add_message` 时 `len(path) % 10 == 0` 触发 | 无定时扫描开销 |
| 边信任 | **惰性更新**（读时算衰减） | 取消定时任务 |

---

## 1. 数据模型变更（增量，不破坏现有表）

### 1.1 `cognitive_nodes` 表 — 加列，不动旧列

```sql
-- Phase 8 新增列
ALTER TABLE cognitive_nodes ADD COLUMN IF NOT EXISTS path_id VARCHAR(500);
ALTER TABLE cognitive_nodes ADD COLUMN IF NOT EXISTS node_type VARCHAR(50) DEFAULT 'explicit';
    -- explicit | auto_generated | user_created | suggested
ALTER TABLE cognitive_nodes ADD COLUMN IF NOT EXISTS is_visible BOOLEAN DEFAULT false;
ALTER TABLE cognitive_nodes ADD COLUMN IF NOT EXISTS subsystems JSONB DEFAULT '{}';
    -- Phase 8 专属元数据：growth_state, preview_count 等
ALTER TABLE cognitive_nodes ADD COLUMN IF NOT EXISTS embedding VECTOR(1536);
ALTER TABLE cognitive_nodes ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT true;

CREATE UNIQUE INDEX IF NOT EXISTS idx_cn_path_id ON cognitive_nodes(user_id, path_id)
    WHERE path_id IS NOT NULL AND deleted_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_cn_embedding ON cognitive_nodes
    USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100) WHERE embedding IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_cn_parent ON cognitive_nodes(user_id, parent)
    WHERE deleted_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_cn_level ON cognitive_nodes(user_id, level)
    WHERE deleted_at IS NULL;
```

> `subsystems` JSONB 结构（只存 Phase 8 专属数据）：
> ```json
> {
>   "growth": {
>     "state": "initial",        // initial | expanded | stale
>     "ancestor_completed": true,
>     "last_expansion_at": null
>   },
>   "preview": {
>     "suggested_count": 0,
>     "last_viewed_at": null
>   }
> }
> ```

### 1.2 新表：`knowledge_edges`

```sql
CREATE TABLE IF NOT EXISTS knowledge_edges (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id VARCHAR(255) NOT NULL,
    source_node_id UUID NOT NULL REFERENCES cognitive_nodes(id),
    target_node_id UUID NOT NULL REFERENCES cognitive_nodes(id),
    edge_type VARCHAR(50) NOT NULL,        -- prerequisite / analogy / related_to / user_defined
    strength FLOAT DEFAULT 0.5,
    confidence FLOAT,
    trust_score FLOAT DEFAULT 0.5,
    edge_status VARCHAR(30) DEFAULT 'suggested',
        -- auto_active | pending_confirm | suggested | user_rejected
    created_by VARCHAR(50) DEFAULT 'system',
    created_at TIMESTAMPTZ DEFAULT now(),
    last_evaluated_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(source_node_id, target_node_id, edge_type)
);
CREATE INDEX IF NOT EXISTS idx_ke_source ON knowledge_edges(source_node_id);
CREATE INDEX IF NOT EXISTS idx_ke_target ON knowledge_edges(target_node_id);
```

### 1.3 新表：`conversation_node_links`

```sql
CREATE TABLE IF NOT EXISTS conversation_node_links (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id VARCHAR(255) NOT NULL,   -- 引用 UserData.conversations[id]
    node_id UUID NOT NULL REFERENCES cognitive_nodes(id),
    added_by VARCHAR(50) DEFAULT 'system',
    is_primary BOOLEAN DEFAULT false,
    added_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(conversation_id, node_id)
);
CREATE INDEX IF NOT EXISTS idx_cnl_conv ON conversation_node_links(conversation_id);
CREATE INDEX IF NOT EXISTS idx_cnl_node ON conversation_node_links(node_id);
```

### 1.4 conversations 表（UserData 内） — 加字段

在 `conversation.py` 的 `Conversation` 模型中加：

```python
class Conversation(BaseModel):
    # ... 现有字段
    primary_node_id: str | None = None  # 关联 cognitive_nodes.id
    is_temporary: bool = False
```

### 1.5 CognitiveNode Python 模型加字段

在 `cognitive/models.py` 的 `CognitiveNode` 中加：

```python
class CognitiveNode(BaseModel):
    # ... 现有字段
    path_id: str = ""        # 不变路径标识，如 "大学物理.电磁学.静电场"
    node_type: str = "explicit"
    is_visible: bool = False
    subsystems: dict = Field(default_factory=dict)
    embedding: list[float] | None = None
    is_active: bool = True
```

### 1.6 新 Python 模型

`backend/app/cognitive/edge_models.py`:

```python
class KnowledgeEdge(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    user_id: str
    source_node_id: str
    target_node_id: str
    edge_type: str  # prerequisite | analogy | related_to | user_defined
    strength: float = 0.5
    confidence: float | None = None
    trust_score: float = 0.5
    edge_status: str = "suggested"
    created_by: str = "system"
    created_at: float = Field(default_factory=time.time)
    last_evaluated_at: float = Field(default_factory=time.time)
```

---

## 2. 新引擎：GrowthEngine

`backend/app/cognitive/growth_engine.py`

```python
"""
全方向自动生长引擎

职责：
1. 向上补全祖先（创建节点时沿 path_id 逐级补全）
2. 横向同级扩展（秘书驱动提案）
3. 波纹跨域关联（语义检索 + 建边）
"""

class GrowthEngine:
    def ensure_ancestors(self, user_id: str, path_id: str, level: str, path_labels: dict[str, str]) -> list[str]:
        """
        沿 path_id 逐级检查缺失的父节点，补全为 auto_generated。
        path_labels: { "大学物理": "partition", "电磁学": "domain", ... }
        返回创建的节点 ID 列表（以便后续建边的回调）
        """
        segments = path_id.split(".")
        created = []
        parent_id = None
        current_path = ""
        for i, seg in enumerate(segments):
            current_path = seg if i == 0 else current_path + "." + seg
            seg_level = ["partition", "domain", "topic", "concept", "atom"][i]
            existing = find_node_by_path(user_id, current_path)
            if not existing:
                node = upsert_node(CognitiveNode(
                    id=str(uuid4()),
                    label=path_labels.get(seg, seg),
                    path_id=current_path,
                    level=seg_level,
                    parent=parent_id,
                    node_type="auto_generated",
                    is_visible=(seg_level == "partition"),  # 分区本身可见
                ), user_id)
                created.append(node.id)
                parent_id = node.id
            else:
                parent_id = existing.id
        return created

    def suggest_lateral_expansion(self, user_id: str, parent_node_id: str) -> list[dict]:
        """
        扫描父节点下已激活的子节点数 ≥ 3 且未扩展过
        返回秘书提案数据
        """
        children = get_children(parent_node_id, user_id)
        visible = [c for c in children if c.is_visible]
        if len(visible) < 3:
            return []
        # 检查该 parent 的 subsystems 是否记录过已扩展
        parent = get_node(parent_node_id, user_id)
        if not parent:
            return []
        growth = parent.subsystems.get("growth", {})
        if growth.get("state") == "expanded":
            return []
        return [{
            "type": "lateral_expansion",
            "parent_id": parent_node_id,
            "parent_label": parent.label,
            "visible_count": len(visible),
        }]

    def ripple_cross_domain(self, user_id: str, node_id: str):
        """
        新节点创建后异步：
        1. 语义检索高相似节点 → 按置信度建边
        2. 沿高置信度边间接关联
        """
        # 异步任务（在 API 层用 asyncio.create_task 或直接推队列）
        from app.cognitive.storage import get_node
        node = get_node(node_id, user_id)
        if not node or not node.embedding:
            return
        similar = vector_search(node.embedding, exclude_id=node_id, limit=5)
        for sim in similar:
            if sim.similarity > 0.85:
                create_edge(KnowledgeEdge(
                    user_id=user_id,
                    source_node_id=node_id,
                    target_node_id=sim.id,
                    edge_type="related_to",
                    strength=sim.similarity,
                    confidence=sim.similarity,
                    trust_score=sim.similarity * 0.8,
                    edge_status="auto_active" if sim.similarity > 0.9 else "pending_confirm",
                ))
```

---

## 3. 分类引擎重写（classifier.py）

### 3.1 放弃旧 `classify_partition` / `classify_full` / `auto_resolve`

这三个函数全部废弃，替换为新的一套。

### 3.2 新分类器架构

`backend/app/services/phase8_classifier.py`（新文件）

```python
class Phase8Classifier:
    """
    认知图驱动的多路径分类器

    流程：
    1. 分层向量检索（先 topic 级再 concept/atom 级）
    2. 候选 topic 生成与打分
    3. 三种模式决策（跨主题/切换/继续）
    """

    def __init__(self):
        self.embedder = EmbeddingService()  # 复用现有 embedding

    def classify(self, user_id: str, text: str, current_topic_id: str | None = None) -> dict:
        """
        主入口：返回分类结果
        {
            "mode": 1|2|3,
            "candidates": [...],
            "should_switch": bool,
            "switch_detail": {...}
        }
        """
        # 1. 用户消息 embedding
        query_emb = self.embedder.embed(text)

        # 2. 分层检索
        topic_candidates = self._search_topic_level(user_id, query_emb)
        child_candidates = self._search_child_level(user_id, query_emb, topic_candidates)

        # 3. 候选合并 + 打分
        seeds = self._merge_and_score(topic_candidates, child_candidates)

        # 4. 模式决策
        return self._decide_mode(seeds, current_topic_id)

    def _search_topic_level(self, user_id, query_emb) -> list[dict]:
        """检索所有 topic 级节点，取 top-5"""
        rows = db.fetchall("""
            SELECT id, path_id, label,
                   1 - (embedding <=> %s) AS similarity
            FROM cognitive_nodes
            WHERE user_id = %s AND level = 'topic'
              AND deleted_at IS NULL AND embedding IS NOT NULL
            ORDER BY similarity DESC LIMIT 5
        """, (query_emb, user_id))
        return [{"id": r["id"], "label": r["label"],
                 "path_id": r["path_id"], "sim": r["similarity"]}
                for r in rows]

    def _search_child_level(self, user_id, query_emb, topics) -> list[dict]:
        """对每个 topic 候选，检索其下 concept/atom 节点"""
        results = []
        for t in topics[:3]:  # 只前 3 个 topic 深入
            rows = db.fetchall("""
                SELECT id, path_id, label, level,
                       1 - (embedding <=> %s) AS similarity
                FROM cognitive_nodes
                WHERE user_id = %s
                  AND path_id LIKE %s || '.%%'
                  AND level IN ('concept', 'atom')
                  AND deleted_at IS NULL AND embedding IS NOT NULL
                ORDER BY similarity DESC LIMIT 10
            """, (query_emb, user_id, t["path_id"]))
            for r in rows:
                results.append(r)
        return results

    def _merge_and_score(self, topics, children) -> list[dict]:
        """合并 topic 候选与子节点候选，按相似度重排序，过滤低分"""
        # topic 祖先权重 ×1.0
        # deep_links 的 topic 祖先 ×0.6
        # auto_active/pending_confirm 边的关联 topic 祖先 ×0.5
        scores = {}
        for t in topics:
            scores[t["id"]] = max(scores.get(t["id"], 0), t["sim"] * 1.0)
        # 同 domain 内非最高分 ×0.8（软抑制）
        # 近因惯性（最近 5 轮激活 topic 加分）
        return sorted(
            [{"id": k, "score": v} for k, v in scores.items() if v > 0.1],
            key=lambda x: -x["score"]
        )

    def _decide_mode(self, candidates, current_topic_id) -> dict:
        """
        模式决策：
        - 模式1（跨主题）：多候选接近，无 >1.5× 领先
        - 模式2（切换）：单一候选 > 第二名×1.5
        - 模式3（继续）：else
        """
        if not candidates:
            return {"mode": 3, "candidates": [], "should_switch": False}

        top = candidates[0]
        if len(candidates) > 1 and candidates[1]["score"] * 1.5 > top["score"]:
            return {"mode": 1, "candidates": candidates[:3],
                    "should_switch": True}
        if current_topic_id and top["id"] != current_topic_id:
            return {"mode": 2, "candidates": [top],
                    "should_switch": True}
        return {"mode": 3, "candidates": [top],
                "should_switch": False}

    def confirm_switch(self, user_id: str, node_id: str, conversation_id: str):
        """
        用户确认切换 → 建立 conversation_node_links
        """
        db.execute("""
            INSERT INTO conversation_node_links
                (conversation_id, node_id, is_primary, added_by)
            VALUES (%s, %s, true, 'user_selection')
            ON CONFLICT (conversation_id, node_id) DO NOTHING
        """, (conversation_id, node_id))
```

### 3.3 `conversation_llm.py` 的改动最小

只改一处：将 `classifier.auto_resolve(...)` 替换为 `Phase8Classifier().classify(...)`，判断 `should_switch` 后决定是否发 `context_switch` 事件。

```python
# 旧代码
from app.services.classifier import classifier
result = classifier.auto_resolve(user_id, text, current_partition_id, conv_id)

# 新代码
from app.services.phase8_classifier import Phase8Classifier
result = Phase8Classifier().classify(user_id, text, current_topic_id)
if result["mode"] in (1, 2) and result["should_switch"]:
    # 发 context_switch 事件（格式兼容现有前端）
    ...
```

---

## 4. 新 API 端点

全部加在 `backend/app/api/phase8.py`（新文件），使用 `/api/v2/` 前缀避免与现有 API 冲突。

| 方法 | 端点 | 功能 | 备注 |
|:----|:-----|:-----|:-----|
| POST | `/api/v2/classify` | 分类单条消息 | 返回 mode + candidates |
| POST | `/api/v2/classify/select` | 用户确认归属 | 支持多选 + 新会话 |
| POST | `/api/v2/classify/custom` | 用户自定义路径 | LLM 补全 |
| PUT | `/api/v2/conversations/{id}/save` | 保存临时会话 | 触发 LLM hierarchy 生成 |
| GET | `/api/v2/conversations/{id}/links` | 获取会话关联 topic | |
| POST | `/api/v2/conversations/{id}/links` | 添加辅助归属 | |
| PATCH | `/api/v2/conversations/{id}/links/{link_id}` | 设为主归属 | |
| DELETE | `/api/v2/conversations/{id}/links/{link_id}` | 移除关联 | |
| GET | `/api/v2/graph/nodes` | 获取可见子节点 | 参数 `parent_id` |
| GET | `/api/v2/graph/search` | 全局搜索 | 参数 `q` |
| POST | `/api/v2/graph/nodes/{id}/expand` | 创建子节点 | |
| POST | `/api/v2/graph/edges/{id}/accept` | 确认建议边 | |
| POST | `/api/v2/graph/edges/{id}/reject` | 拒绝边 | |
| PATCH | `/api/v2/graph/edges/{id}` | 修改边 | |
| GET | `/api/v2/graph/export` | 导出全量图谱 | |

### 返回值示例

**POST /api/v2/classify**
```json
{
    "mode": 1,
    "candidates": [
        {"id": "xxx", "label": "电磁学", "path_id": "大学物理.电磁学",
         "score": 0.89, "from_level": "topic"}
    ],
    "immersion_depth": 3,
    "should_switch": true
}
```

---

## 5. 现有文件改动清单

| 文件 | 改动类型 | 改动内容 |
|:-----|:---------|:---------|
| `cognitive/models.py` | 加字段 | CognitiveNode 加 path_id, node_type, is_visible, subsystems, embedding, is_active |
| `cognitive/storage.py` | 加方法 | `find_node_by_path()`, `vector_search()`, 读写新字段 |
| `cognitive/storage.py` | 加方法 | `upsert_edge()`, `get_edges()` |
| `services/classifier.py` | 标记废弃 | 保留旧函数供回退，主入口改为 Phase8Classifier |
| `services/conversation_llm.py` | 小改 | 替换 auto_resolve → Phase8Classifier.classify |
| `services/tree_ops.py` | 小改 | create_partition/domain/topic 时同步创建 CognitiveNode |
| `schemas/conversation.py` | 加字段 | Conversation 加 primary_node_id, is_temporary |
| `main.py` | 加注册 | 注册 phase8 API 路由 |
| 前端 `PartitionSidebar.tsx` | 大改 | 数据源从 UserData.partitions 改为 `/api/v2/graph/nodes` |
| 前端 `ConversationPanel.tsx` | 小改 | 分类交互卡片（模式1/2 UI） |
| 前端 `useConversation.ts` | 小改 | 支持临时会话、融合会话 |

---

## 6. 新文件清单

| 文件 | 内容 |
|:-----|:-----|
| `cognitive/growth_engine.py` | 全方向生长引擎（补全祖先/横向扩展/波纹关联） |
| `cognitive/edge_models.py` | KnowledgeEdge Python 模型 |
| `cognitive/edge_storage.py` | knowledge_edges 表的 CRUD |
| `cognitive/link_storage.py` | conversation_node_links 表的 CRUD |
| `services/phase8_classifier.py` | 新分类器（分层向量检索 + 模式决策） |
| `api/phase8.py` | Phase 8 所有新 API 端点 |
| `domain/secretary/engines/builtin_temp_conv_cleanup.py` | 临时会话 48h 清理模块 |
| `domain/secretary/engines/builtin_lateral_expansion.py` | 横向扩展提案模块（秘书驱动） |

---

## 7. 前端改动

### 7.1 侧边栏数据源切换

`PartitionSidebar.tsx` 的 `useEffect` 从：
```typescript
// 旧：读 UserData.partitions
const partitions = Object.values(data.partitions);
```
改为：
```typescript
// 新：读 Phase 8 Graph API
const response = await fetch(`/api/v2/graph/nodes?parent_id=${parentId}`);
const nodes = await response.json();
```

### 7.2 可见性控制

- 自动生成的节点（`auto_generated`、`suggested`）不显示，除非 `is_visible=true`
- 侧边栏每个父节点下显示 "展开预览 (N)" 按钮
- 预览节点用灰色虚线渲染

### 7.3 分类交互卡片

- 模式1：多选卡片，底部「在新会话中开启多主题讨论」
- 模式2：单选切换卡片 + 确认/修改按钮
- 模式3：静默，无 UI 变化

### 7.4 临时会话

- 工具栏开关
- 开启后顶部提示「48h 后自动清理」
- 「保存」按钮触发 `PUT /api/v2/conversations/{id}/save`

---

## 8. 实施顺序

### 第 1 步：数据层（2 天）

```
1.1 cognitive_nodes 加列 + 索引（已确认不破坏现有数据）
1.2 建新表 knowledge_edges / conversation_node_links
1.3 CognitiveNode Python 模型加字段
1.4 新增 edge_models.py / edge_storage.py / link_storage.py
1.5 测试：创建节点、向量检索、建边读写
```

### 第 2 步：引擎层（2 天）

```
2.1 GrowthEngine — ensure_ancestors（向上补全）
2.2 分类器 — Phase8Classifier（向量检索 + 模式决策）
2.3 验证：用真实消息测试分类准确率
```

### 第 3 步：API 层（2 天）

```
3.1 phase8.py — classify / classify/select / classify/custom
3.2 graph API — 节点 CRUD + 搜索
3.3 edges API — 确认/拒绝/修改
3.4 conversation_llm.py 集成
```

### 第 4 步：Secretary 模块（1 天）

```
4.1 builtin_temp_conv_cleanup.py
4.2 builtin_lateral_expansion.py（秘书驱动横向扩展提案）
4.3 延迟步骤：波纹跨域关联 + 沉浸深度跨主题延后处理
```

### 第 5 步：前端 + 集成测试（2 天）

```
5.1 侧边栏数据源切换
5.2 分类交互卡片（模式1/2）
5.3 临时会话 UI
5.4 端到端测试
```

---

## 9. 风险与回避策略

| 风险 | 概率 | 影响 | 回避策略 |
|:-----|:----|:-----|:---------|
| embedding 向量维度与模型不匹配 | 中 | 高 | 先在认知节点插入时硬编码一个测试向量测试索引 |
| `conversation_node_links` 引用 UserData 内 conversation.id 是 UUID，与前端路由可能不同步 | 中 | 中 | 前端侧边栏改成统一从 graph API 取，不要混用两套 ID |
| 旧 classifier 被多处引用（conversation_llm.py 之外还可能有用）| 低 | 高 | 保留旧 classifier 函数不变，Phase8Classifier 是新增的，旧的不删除 |
| 生长引擎递归创建大量 `auto_generated` 节点，冷热分层可能预热大量节点 | 低 | 低 | `auto_generated` 默认 `is_visible=false, is_active=false`，不参与热分区 |
|| 分类器在无 cognitive_nodes（新用户）时退化 | 中 | 中 | 新用户首次消息走秘书协商，不走分类 |

---

## 10. 用户确认决策

| 维度 | 决策 | 含义 |
|:-----|:-----|:------|
| 老用户数据迁移 | **A** — 一次性迁移脚本 | 写脚本将旧 UserData 中所有 partition/domain/topic 转为 CognitiveNode，迁移后废弃旧数据源 |
| 新用户首次消息 | **秘书协商** | 协商创建路径，用户拒绝则留在临时会话（48h 清理） |
| 前端过渡 | **直接重构，做好再开** | 不搞两套兼容，一次性替换侧边栏、分类UI、临时会话，测试通过后再上线 |

---

## 11. 迁移脚本设计

### 11.1 迁移脚本位置

`backend/app/scripts/migrate_to_phase8.py`

### 11.2 迁移逻辑

```python
def migrate_user(user_id: str):
    """
    将 UserData 中的 partitions/domains/topics 转为 cognitive_nodes

    转换规则：
    - partition → CognitiveNode(level="partition", label=name, node_type="explicit", is_visible=True)
    - domain    → CognitiveNode(level="domain", label=name, node_type="explicit", is_visible=True)
    - topic     → CognitiveNode(level="topic", label=name, node_type="explicit", is_visible=True)
    - path_id = partition.name + "." + domain.name + "." + topic.name
    - parent/children 关系通过 path_id 推导
    - conversation_node_links: 每个 topic 的 active_conversation_id → link
    """
    data = storage.load(user_id)

    for pid, partition in data.partitions.items():
        partition_node = upsert_node(CognitiveNode(
            id=pid,
            label=partition.name,
            level="partition",
            node_type="explicit",
            is_visible=True,
            path_id=partition.name,
        ), user_id)

        for did, domain in data.domains.items():
            if domain.partition_id != pid:
                continue
            path_id = f"{partition.name}.{domain.name}"
            domain_node = upsert_node(CognitiveNode(
                id=did,
                label=domain.name,
                level="domain",
                parent=pid,
                node_type="explicit",
                is_visible=True,
                path_id=path_id,
            ), user_id)

            for tid, topic in data.topics.items():
                if topic.domain_id != did:
                    continue
                    topic_path = f"{path_id}.{topic.name}"
                    topic_node = upsert_node(CognitiveNode(
                        id=tid,
                        label=topic.name,
                        level="topic",
                        parent=did,
                        node_type="explicit",
                        is_visible=True,
                        path_id=topic_path,
                    ), user_id)

                    # 建立 conversation_node_links
                    if topic.active_conversation_id:
                        upsert_link(
                            conversation_id=topic.active_conversation_id,
                            node_id=tid,
                            is_primary=True,
                        )

    logger.info(f"迁移完成: user={user_id}, partitions={len(data.partitions)}")
```

### 11.3 回退方案

迁移后保留旧 UserData 不动，仅新增 cognitive_nodes 表。
如果 Phase 8 有问题，切换回`USE_PHASE8=false`环境变量即可回退到旧分类器。

---

## 12. 新用户首次消息流程

```
用户发第1条消息
  → 分类器检索 cognitive_nodes → 空
  → 秘书调用 LLM 生成 path_labels（deepseek 模型）
  → 秘书发起协商："你提到了「xxx」，建议路径是 大学物理/电磁学，要加入知识库吗？"
    → 用户确认 → 创建 CognitiveNode 层级（explicit + is_visible=true）
    → 用户拒绝或忽略 → 留在临时会话（is_temporary=true, 48h 清理）
```

---

## 13. 前端重构策略

不搞两套兼容，一次性替换：

| 组件 | 旧实现 | 新实现 |
|:-----|:-------|:-------|
| `PartitionSidebar.tsx` | 读 `data.partitions` | 读 `/api/v2/graph/nodes?parent_id=`，支持懒加载 + 预览 + 可见性 |
| `ConversationPanel.tsx` | `switchBanner` 判断 | 模式1/2/3 分类卡片 |
| 临时会话 | 无 | 顶部提示 + 保存按钮 |
| 知识图页面 | 无 | 边状态渲染、节点编辑删除 |

**开发流程**：本地新分支开发全部完成 → 单元测试 → 端到端测试 → 数据迁移 → 切换前端路由 → 部署

不做渐进式上线，避免新旧两套数据打架。

