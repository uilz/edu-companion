# InterestExplorer 数据模型

> InterestExplorer 模块的数据结构（兴趣标签、信息源、推送历史、反馈）。

**ADR**：[`docs/adr/0007-interest-exploration.md`](../../adr/0007-interest-exploration.md)

---

## 1. 兴趣标签表 `interest_tags`

```sql
CREATE TABLE interest_tags (
    id UUID PRIMARY KEY,
    user_id VARCHAR(64) NOT NULL,
    name VARCHAR(128) NOT NULL,
    level SMALLINT NOT NULL DEFAULT 0,         -- 0/1/2 三层
    parent_id UUID REFERENCES interest_tags(id) ON DELETE CASCADE,
    weight SMALLINT NOT NULL DEFAULT 1,         -- 1=主要, 2=次要
    source VARCHAR(20) NOT NULL,                -- manual / from_knowledge / from_reading
    source_ref_id VARCHAR(64),                  -- 关联的 CognitiveNode / Material
    color VARCHAR(7),
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),

    CHECK (level BETWEEN 0 AND 2),
    CHECK (weight IN (1, 2))
);

CREATE INDEX idx_tags_user_parent ON interest_tags(user_id, parent_id);
CREATE INDEX idx_tags_user_level ON interest_tags(user_id, level);
```

**关键决策**：兴趣标签**独立存储**（不与 CognitiveNode 耦合）。

---

## 2. 推送偏好表 `interest_push_prefs`

```sql
CREATE TABLE interest_push_prefs (
    user_id VARCHAR(64) PRIMARY KEY,
    frequency VARCHAR(20) NOT NULL DEFAULT 'daily',  -- daily / weekly / manual
    push_time TIME DEFAULT '08:00:00',
    timezone VARCHAR(64) DEFAULT 'Asia/Shanghai',
    daily_limit INT DEFAULT 6,
    research_object_pct SMALLINT DEFAULT 50,
    research_method_pct SMALLINT DEFAULT 30,
    hot_news_pct SMALLINT DEFAULT 20,
    cross_disciplinary BOOLEAN DEFAULT FALSE,
    retention_days INT DEFAULT 90,
    is_enabled BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);
```

---

## 3. 信息源表 `interest_sources`

```sql
CREATE TABLE interest_sources (
    id UUID PRIMARY KEY,
    user_id VARCHAR(64),                        -- NULL 表示系统内置
    name VARCHAR(128) NOT NULL,
    type VARCHAR(20) NOT NULL,                  -- arxiv / biorxiv / rss / atom / opml
    category VARCHAR(50),                       -- 预印本 / 新闻 / 数据集 / 博客 / 会议
    config JSONB NOT NULL,                       -- {"feed_url": "...", "category_filter": "cs.CL", ...}
    enabled BOOLEAN DEFAULT TRUE,
    is_system BOOLEAN DEFAULT FALSE,
    last_fetched_at TIMESTAMP,
    last_fetch_status VARCHAR(20),              -- success / error / rate_limited
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_sources_user ON interest_sources(user_id);
CREATE INDEX idx_sources_type ON interest_sources(type, enabled);
```

---

## 4. 推送历史表 `interest_push_records`

```sql
CREATE TABLE interest_push_records (
    id UUID PRIMARY KEY,
    user_id VARCHAR(64) NOT NULL,
    source_id UUID REFERENCES interest_sources(id) ON DELETE SET NULL,
    push_type VARCHAR(20) NOT NULL,             -- research_object / research_method / hot_news
    title TEXT NOT NULL,
    summary TEXT,                                -- 原文摘要
    url TEXT,                                    -- 唯一链接
    matched_tags JSONB DEFAULT '[]',             -- 匹配的标签 ID 列表
    generated_at TIMESTAMP NOT NULL DEFAULT NOW(),

    UNIQUE(user_id, url)                         -- 链接级别去重
);

CREATE INDEX idx_push_records_user_time ON interest_push_records(user_id, generated_at DESC);
CREATE INDEX idx_push_records_type ON interest_push_records(user_id, push_type);
CREATE INDEX idx_push_records_source ON interest_push_records(source_id);
```

---

## 5. 推送反馈表 `interest_feedback`

```sql
CREATE TABLE interest_feedback (
    push_id UUID PRIMARY KEY REFERENCES interest_push_records(id) ON DELETE CASCADE,
    user_id VARCHAR(64) NOT NULL,
    feedback VARCHAR(20) NOT NULL,               -- read / later / dislike / imported
    target_module VARCHAR(30),                  -- imported 时记录：reading / project / flashcard / knowledge_graph / language_room
    target_ref_id VARCHAR(64),                  -- 导入目标的引用 ID
    feedback_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_feedback_user_time ON interest_feedback(user_id, feedback_at DESC);
```

---

## 6. 本地权重调整表 `interest_weight_adjustments`

```sql
CREATE TABLE interest_weight_adjustments (
    id UUID PRIMARY KEY,
    user_id VARCHAR(64) NOT NULL,
    tag_id UUID REFERENCES interest_tags(id) ON DELETE CASCADE,
    dislike_score FLOAT NOT NULL DEFAULT 0,    -- 累计 0.0-1.0
    adjustment_count INT NOT NULL DEFAULT 0,    -- 调整次数
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),

    UNIQUE(user_id, tag_id)
);

CREATE INDEX idx_weight_adj_user ON interest_weight_adjustments(user_id);
```

**关键决策**：本地权重**不入服务端推荐模型**（与"不追踪"原则一致）。

---

## 7. 字段说明

### 7.1 标签层级 `level`

- `0` — 顶级（如"计算机科学"）
- `1` — 中间层（如"机器学习"）
- `2` — 叶子层（如"自然语言处理"）

### 7.2 标签权重 `weight`

- `1` — 主要兴趣（推送比例 1.0）
- `2` — 次要兴趣（推送比例 0.5）

### 7.3 推送类型 `push_type`

| 值 | 含义 |
|---|------|
| `research_object` | 研究对象（具体研究课题）|
| `research_method` | 研究方法（实验设计、理论框架）|
| `hot_news` | 研究热点日报（最近 N 天高频主题）|

### 7.4 反馈类型 `feedback`

| 值 | 含义 |
|---|------|
| `read` | 已读 |
| `later` | 稍后读（生成 `FlashCard`，`status='later'`）|
| `dislike` | 不感兴趣（本地权重调整）|
| `imported` | 已导入（具体看 `target_module`）|

### 7.5 推送比例

`research_object_pct` + `research_method_pct` + `hot_news_pct` = 100

---

## 8. 数据归属

| 归属模块 | 存储内容 |
|---------|---------|
| **本模块** | 兴趣标签、推送偏好、信息源、推送历史、反馈、本地权重 |
| `FlashCard` | 稍后读（`status='later'`, `source='interest_explorer'`）|
| `Material` | 导入的阅读材料（**已存在，调用**）|
| `CognitiveNode` | 创建的知识点（**已存在，调用**）|
| `Project` | 创建的项目（**已存在，调用**）|
| `LanguageRoom` | 分享的讨论话题（**已存在，调用**）|
| 秘书 `Proposal` | 推送通知（**已存在，调用**）|
| 全局事件流 | `InterestPushGenerated` / `InterestPushFeedback` / `InterestContentImported` |
