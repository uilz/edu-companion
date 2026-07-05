# InterestExplorer 事件 schema

> InterestExplorer 模块产生和消费的事件定义。

**ADR**：[`docs/adr/0007-interest-exploration.md`](../../adr/0007-interest-exploration.md)

---

## 1. 事件清单

| 事件 | 触发时机 |
|------|---------|
| `InterestPushGenerated` | 推送内容已生成 |
| `InterestPushFeedback` | 用户对推送的反馈 |
| `InterestContentImported` | 用户将推送内容导入其他模块 |
| `InterestSourceAdded` | 用户添加信息源 |
| `InterestSourceRemoved` | 用户移除信息源 |
| `InterestSourceFetched` | 信息源抓取完成 |
| `InterestTagAdded` | 用户添加兴趣标签 |
| `InterestTagRemoved` | 用户移除兴趣标签 |
| `InterestWeightAdjusted` | 本地权重调整 |

---

## 2. 事件 Schema

### 2.1 推送生命周期

```python
class InterestPushGenerated(DomainEvent):
    """推送内容已生成"""
    user_id: str
    push_id: str
    push_type: Literal["research_object", "research_method", "hot_news"]
    title: str
    url: str
    matched_tags: list[str]
    source_id: str | None
    generated_at: datetime

class InterestPushFeedback(DomainEvent):
    """用户对推送的反馈"""
    user_id: str
    push_id: str
    feedback: Literal["read", "later", "dislike"]
    feedback_at: datetime
```

### 2.2 跨模块导入

```python
class InterestContentImported(DomainEvent):
    """用户将推送内容导入其他模块"""
    user_id: str
    push_id: str
    # target_module 必须为 CrossModuleTarget 枚举的合法值（来自 shared.events.CrossModuleTarget）
    #   - reading        : 导入到阅读模块
    #   - project        : 导入到项目模块
    #   - flashcard      : 导入到 FlashCard
    #   - cognitive_node : 导入到知识图谱
    #   - language_room  : 导入到语言房间
    target_module: CrossModuleTarget = CrossModuleTarget.READING
    target_ref_id: str
    imported_at: datetime
```

### 2.3 信息源

```python
class InterestSourceAdded(DomainEvent):
    user_id: str
    source_id: str
    name: str
    type: Literal["arxiv", "biorxiv", "rss", "atom", "opml"]
    config: dict
    added_at: datetime

class InterestSourceRemoved(DomainEvent):
    user_id: str
    source_id: str
    removed_at: datetime

class InterestSourceFetched(DomainEvent):
    """信息源抓取完成"""
    user_id: str | None
    source_id: str
    new_items_count: int
    error_message: str | None
    fetched_at: datetime
```

### 2.4 标签与权重

```python
class InterestTagAdded(DomainEvent):
    user_id: str
    tag_id: str
    name: str
    level: int
    parent_id: str | None
    # source: 本模块内部来源
    #   - manual : 用户手动添加
    #   - system : 系统推荐 / 自动归类
    # cross_module_source: 跨模块引用来源（与 source 互斥，二选一）
    #   - from_knowledge : 来自知识图谱已有点的标签同步
    #   - from_reading   : 来自阅读标注
    source: Literal["manual", "system"] = "manual"
    cross_module_source: Literal["from_knowledge", "from_reading"] | None = None
    added_at: datetime

class InterestTagRemoved(DomainEvent):
    user_id: str
    tag_id: str
    removed_at: datetime

class InterestWeightAdjusted(DomainEvent):
    """本地权重调整 - 不发送到服务端"""
    user_id: str
    tag_id: str
    old_score: float
    new_score: float
    adjustment_count: int
    adjusted_at: datetime
```

---

## 3. 事件消费者

### 3.1 本模块消费

- `InterestPushGenerated` → 写入 `interest_push_records` 表
- `InterestPushFeedback` → 写入 `interest_feedback` 表
- `InterestWeightAdjusted` → 写入 `interest_weight_adjustments` 表
- `CognitiveNodeLinked` → 当用户对兴趣标签创建/更新/删除知识点链接时同步 `interest_tags` 引用计数
- `CognitiveNodeMetadataChanged` → 当关联知识点的描述/标签变化时刷新兴趣面板展示

### 3.2 其他模块消费

| 事件 | 消费者 | 行为 |
|------|--------|------|
| `InterestPushGenerated` | 秘书系统 | 通过 `Proposal` 机制推送通知 |
| `InterestPushFeedback`（feedback='later'）| FlashCard 模块 | 创建 `FlashCard`（`status='later'`, `source='system'`, `cross_module_source='interest_explorer'`）|
| `InterestContentImported`（target_module='reading'）| 阅读模块 | 接收导入内容并创建 `Material` |
| `InterestContentImported`（target_module='project'）| 项目模块 | 接收导入内容并创建项目 |
| `InterestContentImported`（target_module='flashcard'）| FlashCard | 接收导入内容并创建卡片 |
| `InterestContentImported`（target_module='cognitive_node'）| 知识图谱 | 接收导入内容并创建 `CognitiveNode` |
| `InterestContentImported`（target_module='language_room'）| 语言房间 | 接收导入内容并创建话题 |

### 3.3 不更新的状态

**关键设计原则**：

- 所有 InterestExplorer 事件**不**更新 `CognitiveNode.Belief`
- 推送生成 / 反馈 / 导入**不**触发 Belief 更新
- Belief 的合法来源仅限主动学习行为

**理由**：

- InterestExplorer 是"信息发现工具"，**不**构成"学习行为"
- 用户对推送的反馈（read/later/dislike）**不**代表掌握度变化
- 跨模块导入时，由**目标模块**决定是否更新 Belief（如 FlashCard 复习时更新）

---

## 4. 事件粒度

### 4.1 推送 vs 反馈 vs 导入

| 粒度 | 事件 |
|------|------|
| **推送生成** | `InterestPushGenerated`（按推送内容）|
| **用户反馈** | `InterestPushFeedback`（按推送）|
| **跨模块导入** | `InterestContentImported`（按目标模块，每个目标一次事件）|

### 4.2 "稍后读"路径

```
InterestPushGenerated
    └─→ 用户点击"稍后读"
        └─→ InterestPushFeedback（feedback='later'）
            └─→ FlashCard 模块消费
                └─→ 创建 FlashCard（status='later', source='interest_explorer'）
                    └─→ 用户处理后
                        └─→ InterestContentImported（target_module='xxx'）
                            └─→ 标记 FlashCard.status='processed'
```

### 4.3 "不感兴趣"路径

```
InterestPushGenerated
    └─→ 用户点击"不感兴趣"
        └─→ InterestPushFeedback（feedback='dislike'）
            └─→ 本地写入 interest_feedback
            └─→ 更新 interest_weight_adjustments
            └─→ InterestWeightAdjusted（本地事件，不发送到服务端）
                └─→ 后续推送降低相似标签的采样概率
```

---

## 5. 信息源抓取调度

```python
# 定期抓取（非事件驱动）
async def fetch_sources():
    """infrastructure/scheduler 定期调用"""
    sources = await get_enabled_sources()
    for source in sources:
        try:
            items = await fetch_source(source)  # feedparser + httpx
            for item in items:
                if not await is_duplicate(user_id, item.url):
                    await create_push_record(user_id, source, item)
        except Exception as e:
            await record_fetch_error(source, e)
```

**关键设计**：

- 抓取是**定期调度**（不通过事件总线）
- `InterestSourceFetched` 事件记录抓取结果
- 新内容生成 `InterestPushGenerated` 事件

---

## 6. 不调用 LLM 的设计

**关键设计原则**：

- 推送内容**完全**来自 RSS/Atom 原文
- **不**调用 LLM 做摘要、分类、推荐
- 标签匹配基于**关键词匹配 + 用户兴趣标签**

**标签匹配算法**（伪代码）：

```python
def match_tags(item, user_tags):
    matched = []
    for tag in user_tags:
        if tag.name.lower() in item.title.lower() or \
           tag.name.lower() in item.summary.lower():
            matched.append(tag.id)
    return matched
```

**跨学科方法**（`cross_disciplinary=True`）：

- 不限制标签范围
- 从所有标签的**全局**采样
- 仍受本地权重调整影响
