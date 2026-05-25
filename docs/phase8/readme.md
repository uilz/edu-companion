# Phase 8 完整设计实现方案：认知图驱动多路径分类与融合会话

> **版本**: Final  
> **目标**: 以 CognitiveNode 为统一权威数据源，融合对话、知识图谱与认知模型，实现语义驱动的多路径知识归属与融合会话管理。通过后台全量生长、前台渐进可见、动态边信任及秘书协同，构建高性能、长期陪伴的智能伴学基础设施。

---

## 目录

1. [设计理念与核心原则](#1-设计理念与核心原则)
2. [统一数据模型](#2-统一数据模型)
3. [存储与性能优化](#3-存储与性能优化)
4. [全方向自动生长引擎](#4-全方向自动生长引擎)
5. [渐进可见与预览机制](#5-渐进可见与预览机制)
6. [动态边信任与关系管理（惰性更新）](#6-动态边信任与关系管理惰性更新)
7. [分类引擎：三种用户意图模式（分层检索）](#7-分类引擎三种用户意图模式分层检索)
8. [临时会话模式](#8-临时会话模式)
9. [沉浸深度与跨主题抑制](#9-沉浸深度与跨主题抑制)
10. [秘书联动与元认知构建](#10-秘书联动与元认知构建)
11. [融合会话与多归属](#11-融合会话与多归属)
12. [多主题会话的新会话提示](#12-多主题会话的新会话提示)
13. [节点删除与递归清理](#13-节点删除与递归清理)
14. [API 设计](#14-api-设计)
15. [前端交互设计](#15-前端交互设计)
16. [实施路线图](#16-实施路线图)
17. [认知科学依据与行业对比](#17-认知科学依据与行业对比)
18. [风险与对策](#18-风险与对策)

---

## 1. 设计理念与核心原则

### 1.1 根本矛盾与解决方案

| 矛盾 | 解决方案 |
|------|---------|
| 系统需完整知识骨架做精准分类，但不能剥夺学生自主建构知识的权力 | **后台全量生长，前台按需渐进可见** |
| 自动化省心 vs 必要难度与自我建构 | **秘书协商式创建与展开，最终用户确认** |
| 个性化灵活 vs 教学逻辑严谨 | **LLM 推断结合置信度分层信任与动态信任调节** |
| 深度对话的沉浸感 vs 跨主题联想的打断风险 | **沉浸深度抑制 + 秘书延后处理** |
| 试探性提问不想“污染”知识库 | **临时会话模式，无节点创建，48h 自动清理** |

### 1.2 核心原则

- **统一权威源**：`cognitive_nodes` 是知识结构的唯一存储，废弃独立的 `partitions`、`domains`、`topics` 表。
- **全方向自动生长**：向上补全祖先、横向同级扩展（秘书驱动）、跨域波纹关联，不预建默认占位节点。
- **渐进可见**：节点可见性仅由真实学习行为触发，祖先级联可见且永不自动回退。提供临时预览，不影响可见性。
- **动态关系建模**：知识边采用连续信任度，**惰性更新**，仅在访问时计算衰减，无后台定时任务。
- **三模式分类**：依据用户意图呈现**跨主题讨论、切换会话主题、继续对话**三种交互，均支持自定义路径。采用**分层向量检索**提高精度。
- **沉浸深度抑制**：长对话抑制跨主题弹出，跨主题候选延后至会话结束由秘书确认。
- **临时会话模式**：无归属对话，不创建节点，48h 自动清理，可手动保存。
- **融合会话多归属**：一个会话可关联多个 topic，侧边栏多入口指向同一对话。
- **高性能与长期可用**：热冷分层、全量向量索引、智能压缩，数据永存。
- **用户绝对控制权**：可手动编辑所有层级节点、管理归属、删除节点（递归完全删除），控制秘书行为模式。

---

## 2. 统一数据模型

### 2.1 CognitiveNode 表

```sql
CREATE TABLE cognitive_nodes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    label VARCHAR(255) NOT NULL,           -- 显示名称，可重命名
    path_id VARCHAR(500) NOT NULL,         -- 不可变层级路径，如 "数学.微积分.导数"
    level VARCHAR(20) NOT NULL,            -- partition / domain / topic / concept / atom
    parent_id UUID REFERENCES cognitive_nodes(id),
    embedding VECTOR(1536),
    node_type VARCHAR(50) DEFAULT 'explicit',
        -- explicit | auto_generated | user_created | suggested
    created_by VARCHAR(50) DEFAULT 'system',
    is_visible BOOLEAN DEFAULT false,      -- 前端展示控制
    subsystems JSONB NOT NULL DEFAULT '{}',
    mastery FLOAT DEFAULT 0.0,
    retrieval_prob FLOAT DEFAULT 0.0,
    is_active BOOLEAN DEFAULT true,        -- 热冷分层标记
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now(),
    deleted_at TIMESTAMPTZ,
    UNIQUE(user_id, path_id)
);
```

- `path_id`：不可变结构标识。`label`：可重命名的显示名称。
- `is_visible`：`explicit`/`user_created` 创建即 `true`。`auto_generated` 祖先默认 `false`，当获得任意可见后代时自动 `true`，永不回退。`suggested` 仅在学习行为触及（对话归属、练习、秘书提案接受）时变 `true`。

### 2.2 对话系统

```sql
CREATE TABLE conversations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    title VARCHAR(500),
    primary_node_id UUID REFERENCES cognitive_nodes(id),
    is_temporary BOOLEAN DEFAULT false,    -- 临时会话标记
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now(),
    deleted_at TIMESTAMPTZ
);

CREATE TABLE conversation_node_links (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    node_id UUID NOT NULL REFERENCES cognitive_nodes(id),  -- topic 级
    added_by VARCHAR(50) DEFAULT 'system',
    is_primary BOOLEAN DEFAULT false,
    added_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(conversation_id, node_id)
);

CREATE TABLE messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    user_id UUID NOT NULL,
    role VARCHAR(20) NOT NULL,
    content TEXT NOT NULL,
    content_blocks JSONB DEFAULT '[]',
    cognitive_node_ids UUID[] DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT now()
);
```

### 2.3 图谱边表

```sql
CREATE TABLE knowledge_edges (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    source_node_id UUID NOT NULL REFERENCES cognitive_nodes(id),
    target_node_id UUID NOT NULL REFERENCES cognitive_nodes(id),
    edge_type VARCHAR(50) NOT NULL,        -- prerequisite / analogy / related_to / user_defined
    strength FLOAT DEFAULT 0.5,
    confidence FLOAT,
    trust_score FLOAT DEFAULT 0.5,         -- 动态信任度 [0,1]
    edge_status VARCHAR(30) DEFAULT 'suggested',
        -- auto_active | pending_confirm | suggested | user_rejected
    created_by VARCHAR(50) DEFAULT 'system',
    created_at TIMESTAMPTZ DEFAULT now(),
    last_evaluated_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(source_node_id, target_node_id, edge_type)
);
```

**分层信任与状态**：

| 状态 | 信任度区间 | 行为 |
|------|-----------|------|
| `auto_active` | > 0.7 | 参与分类扩展和秘书推荐，前端实线 |
| `pending_confirm` | (0.4, 0.7] | 参与分类扩展，秘书主动确认，前端橙色虚线 |
| `suggested` | ≤ 0.4 | 不主动参与计算，前端灰色虚线，用户手动激活 |
| `user_rejected` | 0.1（冻结） | 用户明确拒绝，可手动恢复 |

层级关系由 `parent_id` 与 `path_id` 推导，不建边表。

---

## 3. 存储与性能优化

### 3.1 热冷分层

```sql
CREATE TABLESPACE hot_storage LOCATION '/data/hot_ssd';
CREATE TABLESPACE cold_storage LOCATION '/data/cold_hdd';

CREATE TABLE cognitive_nodes (...) PARTITION BY LIST (is_active);
CREATE TABLE cognitive_nodes_active PARTITION OF cognitive_nodes
    FOR VALUES IN (true) TABLESPACE hot_storage;
CREATE TABLE cognitive_nodes_inactive PARTITION OF cognitive_nodes
    FOR VALUES IN (false) TABLESPACE cold_storage;
```

- **降冷**：30 天无写操作的节点 → `is_active=false`。
- **加热**：仅由写操作触发 `UPDATE SET is_active = true`，只读不触发。

### 3.2 向量索引

```sql
CREATE INDEX idx_cn_embedding_all ON cognitive_nodes
    USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 500) WHERE embedding IS NOT NULL;
```

分类检索全量节点。冷分区节点仅使用语义相似度，不融合动态认知信号。

### 3.3 数据压缩与常用索引

```sql
ALTER TABLE cognitive_nodes SET (compression = on);
ALTER TABLE cognitive_nodes ALTER COLUMN subsystems SET COMPRESSION lz4;

CREATE INDEX idx_cn_parent ON cognitive_nodes(user_id, parent_id) WHERE deleted_at IS NULL;
CREATE INDEX idx_cn_user_level ON cognitive_nodes(user_id, level) WHERE deleted_at IS NULL;
```

### 3.4 生命周期

- 数据永存，用户可软删除或导出。
- 临时会话 48 小时后自动物理删除。
- 节点支持递归完全删除。

---

## 4. 全方向自动生长引擎

### 4.1 向上补全祖先
创建节点时沿 `path_id` 逐级补全缺失的父节点（`auto_generated`，`is_visible=false`，`subsystems='{}'`）。

### 4.2 横向同级扩展（秘书驱动）
- 秘书监测父节点下可见子节点活动 ≥ 3 次且未扩展过。
- 提案：“要展开「微积分」更多专题吗？”
- 接受：LLM 生成 `suggested` 节点，**直接 `is_visible=true`**。
- 拒绝：冷却 30 天。

### 4.3 向下入口预填
父节点下无可见子节点时，侧边栏显示“+ 新建专题”，不创建默认节点。

### 4.4 波纹跨域关联
新节点创建后异步：
1. 语义检索高相似节点 → 按置信度创建边。
2. 沿高置信度边间接关联。
3. 同 partition 异 domain 的 topic，LLM 批量推断弱关联。

---

## 5. 渐进可见与预览机制

### 5.1 可见性触发

| 方式 | 效果 |
|------|------|
| 学习行为（对话归属、练习、秘书提案接受） | 节点永久可见，祖先级联可见 |
| 临时预览（点击“展开预览”） | 前端临时展示灰色虚线，不修改数据库，刷新消失 |

### 5.2 预览实现
- 前端维护 `previewParentIds` 状态。
- `GET /graph/nodes?parent_id=` 返回 `suggested_count`。
- 预览节点点击发起对话 → 后端自动设 `is_visible=true`，响应 `node_upgraded: true`。
- 秘书结构扩展提案接受 → 响应 `preview_cleared: true`，前端清除预览。

### 5.3 自定义路径冲突
路径已存在则复用升级（`explicit` + 初始化 `subsystems`），提示用户。

---

## 6. 动态边信任与关系管理（惰性更新）

### 6.1 惰性更新机制

**取消每日定时任务**。在读取边的 `trust_score` 时实时计算衰减并更新。

```python
def get_current_trust(edge: KnowledgeEdge) -> float:
    now = datetime.utcnow()
    days = (now - edge.last_evaluated_at).days
    if days > 0:
        decay = math.exp(-0.015 * days)
        new_score = edge.trust_score * decay
        db.execute(
            "UPDATE knowledge_edges SET trust_score = $1, last_evaluated_at = $2 WHERE id = $3",
            new_score, now, edge.id
        )
        return new_score
    return edge.trust_score
```

- 衰减公式：`trust_score *= exp(-0.015 * days)`
- 最小变化阈值：若新值与旧值差 < 0.01，可跳过写库以减少写入。

### 6.2 证据增强
当边的任一关联节点发生学习活动（mastery 变化 > 0.1，或有新对话/练习）：
```python
evidence = min(0.3, 0.05 * mastery_change + 0.1 * recent_activity_count)
trust_score += (1 - trust_score) * evidence
```

### 6.3 状态转换
信任度跨阈值时即时更新状态，无冷却期。

### 6.4 用户干预
知识图中可手动确认、拒绝或重置边。

---

## 7. 分类引擎：三种用户意图模式（分层检索）

### 7.1 分层向量检索

**第一步**：检索所有 `level = 'topic'` 的节点，取 top-5。
```sql
SELECT id, path_id, label, embedding,
       1 - (embedding <=> $1) AS similarity
FROM cognitive_nodes
WHERE user_id = $2 AND level = 'topic' AND deleted_at IS NULL
ORDER BY similarity DESC LIMIT 5
```

**第二步**：对每个 topic 候选，检索其下 `concept` 和 `atom` 级节点。
```sql
SELECT id, path_id, label, level, embedding,
       1 - (embedding <=> $1) AS similarity
FROM cognitive_nodes
WHERE user_id = $2
  AND path_id LIKE $3 || '.%'
  AND level IN ('concept', 'atom')
  AND deleted_at IS NULL
ORDER BY similarity DESC LIMIT 10
```

**第三步**：合并 topic 候选与子节点候选，按相似度重排序，过滤 `retrieval_prob < 0.1`，取最终 top-3 种子节点。

### 7.2 候选 Topic 生成与打分
- 种子节点的 topic 祖先（×1.0）
- `deep_links` 的 topic 祖先（×0.6）
- `auto_active`/`pending_confirm` 边的关联 topic 祖先（×0.5）

**软抑制**：同 domain 内非最高分 ×0.8；语义高相似（>0.85） topic 互相 ×0.85。

**近因惯性**：最近 5 轮内激活的 topic，指数衰减加成（1.3 * 0.9^轮次）。

### 7.3 三种模式决策

| 模式 | 触发条件 | 前端交互 | 用户操作 |
|------|---------|---------|---------|
| **模式1：跨主题讨论** | 多候选接近（无 >1.5×领先），受沉浸深度抑制调节 | 展示 1~3 路径，多选 + 可选“在新会话中讨论” | 勾选一个或多个归属，或在选择“在新会话中开启多主题讨论”。可自定义路径 |
| **模式2：切换会话主题** | 单一候选 > 第二名×1.5，且与当前主 topic 相似度 < 0.5。无主 topic 时单一高置信度也走此模式 | 展示新路径，单选 | 确认切换 / 修改后确认 / 发新消息自动拒绝 |
| **模式3：继续对话** | else | 静默 | 无需操作 |

---

## 8. 临时会话模式

### 8.1 触发方式
- 用户主动开启“临时会话”开关。
- 对于全新用户首次发言且无任何 CognitiveNode，可默认采用临时会话（可配置）。

### 8.2 行为约束
- **不创建任何 CognitiveNode**，不添加归属 link。
- 消息正常保存，会话标记 `is_temporary = true`。
- 侧边栏不展示临时会话，仅在独立“临时会话”区域可见（可选）。
- 用户可随时点击“保存”触发秘书协商创建节点，会话转为常规会话。

### 8.3 自动清理
每小时执行：`DELETE FROM conversations WHERE is_temporary = true AND updated_at < now() - INTERVAL '48 hours';`  
级联删除所有消息，不留下认知节点。

---

## 9. 沉浸深度与跨主题抑制

### 9.1 沉浸深度
```python
immersion_depth = 当前会话中连续归属于同一主 topic 的消息轮数
```

### 9.2 对模式1的抑制

| 沉浸深度 | 行为 |
|---------|------|
| 浅层（< 5 轮） | 正常弹出多选卡片 |
| 中度（5~15 轮） | 阈值提高 30%，弹出附带“你可能在关联讨论”提示 |
| 深度（16+ 轮） | **不弹出**。跨主题候选交秘书在**会话结束后**生成提案确认 |

### 9.3 模式2不受影响
明确的话题切换意图始终正常弹出。

---

## 10. 秘书联动与元认知构建

### 10.1 结构扩展建议
秘书扫描可扩展父节点，生成提案。接受后生成可见 `suggested` 节点，`preview_cleared: true`。

### 10.2 波纹边确认
`pending_confirm` 边在间隙询问，附带语义摘要。确认→ `auto_active`，拒绝→ `user_rejected`。

### 10.3 协商式节点创建
- **静默模式**：专注时自动创建，事后汇总提示。
- **协商模式**：间隙呈现建议层级确认。用户可切换。

### 10.4 深度沉浸跨主题延后处理
会话结束时秘书生成提案：“本次对话涉及了 X、Y 话题，要关联到知识树吗？” 用户确认后批量添加辅助归属。

### 10.5 新用户首次发言无节点
秘书直接协商：“你提到了「xxx」，建议路径：...。要加入知识库吗？”

---

## 11. 融合会话与多归属

- 会话通过 `conversation_node_links` 关联多个 topic。
- 侧边栏多入口指向同一对话。
- 详情页顶部标签展示所有关联路径，可增删改主。
- 话题漂移：每 10 轮重分类，自动添加辅助归属。
- 删除最后一条 link 即删除会话。

---

## 12. 多主题会话的新会话提示

模式1 多选卡片底部增加醒目选项：
```
🆕 在新会话中开启多主题讨论
```
用户勾选一个或多个 topic 后点击此选项，系统创建新会话，勾选的 topic 设为其归属（首个为主归属）。当前会话不变。

---

## 13. 节点删除与递归清理

### 13.1 递归完全删除

```python
async def delete_node_recursive(node_id: str, user_id: str):
    all_ids = await get_all_descendant_ids(node_id, user_id)
    
    # 统计关联对话
    linked = await db.fetch(
        "SELECT DISTINCT conversation_id FROM conversation_node_links WHERE node_id = ANY($1)",
        all_ids
    )
    
    if linked:
        return DeletionConfirmRequired(
            message=f"将删除 {len(all_ids)} 个节点和 {len(linked)} 个对话，不可恢复。确认？"
        )
    
    # 执行删除
    await db.execute("DELETE FROM conversation_node_links WHERE node_id = ANY($1)", all_ids)
    await db.execute("DELETE FROM conversations WHERE id IN (SELECT DISTINCT conversation_id FROM ...)", all_ids)
    await db.execute("DELETE FROM knowledge_edges WHERE source_node_id = ANY($1) OR target_node_id = ANY($1)", all_ids)
    await db.execute("DELETE FROM cognitive_nodes WHERE id = ANY($1)", all_ids)
```

### 13.2 前端强制确认弹窗
明确列出影响范围，用户输入确认短语方可执行。

---

## 14. API 设计

| 方法 | 端点 | 描述 |
|------|------|------|
| POST | `/classify` | 分类消息，返回模式/路径选项 |
| POST | `/classify/select` | 用户确认归属（支持多选 + 新会话选项） |
| POST | `/classify/custom` | 用户自定义路径 |
| PUT  | `/conversations/{id}/save` | 保存临时会话为常规会话 |
| GET  | `/conversations/{id}/links` | 获取会话关联 topic |
| POST | `/conversations/{id}/links` | 添加辅助归属 |
| DELETE | `/conversations/{id}/links/{link_id}` | 移除关联 |
| PATCH | `/conversations/{id}/links/{link_id}/primary` | 设为主归属 |
| GET  | `/graph/nodes?parent_id=` | 获取直接可见子节点（含 `suggested_count`） |
| PATCH | `/graph/nodes/{id}/move` | 移动节点 |
| POST | `/graph/nodes/merge` | 合并节点 |
| POST | `/graph/nodes/{id}/split` | 拆分节点 |
| DELETE | `/graph/nodes/{id}?recursive=true` | 递归完全删除节点 |
| GET  | `/graph/edges` | 获取边列表 |
| POST | `/graph/edges/{id}/accept` | 确认建议边 |
| POST | `/graph/edges/{id}/reset` | 重置边信任度 |
| DELETE | `/graph/edges/{id}` | 删除边 |
| GET  | `/graph/search?q=` | 全局搜索（不限可见性） |
| GET  | `/graph/export` | 导出图谱 |

---

## 15. 前端交互设计

### 15.1 侧边栏
- 逐层懒加载，`GET /graph/nodes?parent_id=`。
- “展开预览 (N)” 临时显示灰色虚线节点。
- 无子节点：“+ 新建专题”。
- 右键菜单含“删除”，触发递归删除确认弹窗。

### 15.2 分类交互
- **模式1**：多选卡片，最多 5 个，底部“在新会话中开启多主题讨论”。
- **模式2**：切换卡片 + 确认/修改。发新消息自动消失。
- **模式3**：无 UI 变化。

### 15.3 临时会话
- 工具栏“临时会话”开关。开启后侧边栏无归属，顶部提示“48h 后自动清理”。
- “保存”按钮触发秘书协商创建节点。

### 15.4 搜索
- 预生成节点右侧文字标签 `预生成`，点击加入后消失。

### 15.5 知识图
- 边按状态渲染实线/虚线，支持右键确认/忽略/重置。
- 节点右键编辑/删除。

---

## 16. 实施路线图

| 阶段 | 内容 | 工作量 |
|------|------|:---:|
| 8.1 | 统一数据模型、热冷分区、旧表迁移 | 3天 |
| 8.2 | 全方向生长引擎（补全祖先、秘书扩展、波纹关联） | 5天 |
| 8.3 | 渐进可见与预览、动态边信任惰性更新 | 4天 |
| 8.4 | 分层检索分类器 + 沉浸深度抑制 | 4天 |
| 8.5 | 融合会话多归属、秘书元认知、延后处理 | 5天 |
| 8.6 | 临时会话、多主题新会话、递归删除、前端适配 | 6天 |
| 8.7 | 集成测试与性能优化 | 4天 |

---

## 17. 认知科学依据与行业对比

- **图式理论**：知识网络动态生长。
- **扩散激活**：语义种子沿层级和跨域边激活，加入抑制与衰减。
- **必要难度**：骨架不直展，协商创建保留认知投入。
- **自我决定论**：可选归属、可编辑、可新开会话，维护自主感。
- **心流保护**：沉浸深度抑制 + 秘书延后处理。
- **试探学习保护**：临时会话隔离试探性提问。
- **对比 ALEKS/Khanmigo**：个人化动态图、多归属融合、用户控制、沉浸感知方面独特。

---

## 18. 风险与对策

| 风险 | 对策 |
|------|------|
| 惰性更新导致频繁写 | 最小变化阈值跳过微小更新 |
| 临时会话可能被滥用 | 48h 自动清理；转常规需主动保存 |
| 分层检索增加延迟 | 两次索引扫描，总 < 15ms |
| 深度沉浸遗漏跨域 | 秘书会话结束汇总确认 |
| 递归删除误操作 | 强制确认弹窗，标明不可恢复 |
| LLM 推断不准确 | 建议态、用户确认编辑、信任度衰减 |

---

此方案完整定义了 Phase 8 的架构、数据、算法、交互与实施路径，在系统智能与用户自主之间取得了最优平衡，为长期伴学奠定了坚实基础。可以进入开发。