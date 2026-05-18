# 知识图谱系统设计

> 版本: v1.0  
> 最后更新: 2026-05-18  
> 状态: **前端静态原型已实现**，后端+数据连接=待开发

---

## 一、系统定位

知识图谱是伴学系统的「地图」——可视化展示知识点之间的前置/后继/并行关系，叠加实时掌握度，让学习者一眼看清「已征服的领土」和「待攀登的山峰」。

**核心价值**：
- 可视化知识结构，消除「盲学」焦虑
- 前置依赖 → 告诉你「先学什么才能学这个」
- 掌握度热力 → 实时反馈学习进展
- 学习路径推荐 → 自动规划最优路线

---

## 二、当前实现（v0.1 静态原型）

### 2.1 前端 (`graph/page.tsx`)

**纯前端SVG图谱**，0个后端API调用。

```
┌─────────────────────────────────────────────┐
│  SVG 画布 (viewBox 700×620)                  │
│                                             │
│    ┌─────────┐                              │
│    │极限与连续 │──基础──▶┌──────────┐         │
│    │  90%    │          │导数与微分 │         │
│    └────┬────┘          │   78%    │         │
│         │基础           └────┬─────┘         │
│         ▼                   │工具            │
│    ┌──────────┐             ▼               │
│    │  积分学   │       ┌──────────┐          │
│    │   65%    │       │矩阵行列式 │          │
│    └────┬─────┘       │   72%    │          │
│         │应用          └────┬─────┘          │
│         ▼                   │扩展            │
│    ┌──────────┐             ▼               │
│    │向量空间解析│       ┌──────────┐         │
│    │   80%    │       │特征值向量 │         │
│    └────┬─────┘       │   55%    │         │
│         │理论           └──────────┘         │
│         ▼                                   │
│    ┌──────────┐                             │
│    │电磁场理论 │                             │
│    │   48%    │                             │
│    └──────────┘                             │
└─────────────────────────────────────────────┘
```

### 2.2 硬编码数据

**节点**（8个，纯静态）：

```typescript
interface GraphNode {
  id: string         // "calc-basics"
  label: string      // "极限与连续"
  x: number          // 400（绝对像素坐标）
  y: number          // 80
  subject: string    // "高等数学" | "线性代数" | "大学物理" | "概率论"
  mastery: number    // 0-100（硬编码值）
  description: string
}
```

**边**（8条，前置依赖关系）：

```typescript
interface GraphEdge {
  from: string   // "calc-basics"
  to: string     // "calc-deriv"
  label: string  // "基础" | "工具" | "应用" | "扩展" | "理论"
}
```

依赖链：
```
极限与连续 ──基础──▶ 导数与微分 ──工具──▶ 矩阵与行列式 ──扩展──▶ 特征值
     │基础
     └──▶ 积分学 ──应用──▶ 向量空间 ──理论──▶ 电磁场
              │基础              │工具
              └──▶ 概率 ◀───────┘
```

### 2.3 交互功能

| 功能 | 实现 | 说明 |
|------|:--:|------|
| 缩放 | ✅ | 滚轮缩放 (0.3x ~ 2x) + 按钮 |
| 平移 | ✅ | 鼠标拖拽画布 |
| 节点点击 | ✅ | 选中节点 → 侧边栏显示详情 |
| 掌握度环 | ✅ | 圆环 stroke-dasharray 表示进度 |
| 学科颜色 | ✅ | 高数蓝/线代绿/物理橙/概率紫 |
| 前置知识 | ✅ | 侧边栏显示指向当前节点的边 |
| 节点间跳转 | ✅ | 点击前置节点标签跳转 |
| 重置视图 | ✅ | 按钮恢复 1x 缩放 + 原点 |

---

## 三、待实现：动态知识图谱 v1.0

### 3.1 数据源对接

当前图谱与后端完全脱节。v1.0 改造：

```
当前:  graph/page.tsx ← 硬编码 nodes[] + edges[]
目标:  graph/page.tsx ← GET /api/knowledge/graph
                           ↓
                      后端服务层
                      ┌───┴────┐
                      │ 图谱   │  ← PostgreSQL: knowledge_graph 表
                      │ 引擎   │  ← BKT: knowledge_states (实时掌握度)
                      └────────┘
```

**新增数据表**：

```sql
CREATE TABLE knowledge_graph_nodes (
    node_id      TEXT PRIMARY KEY,
    label        TEXT NOT NULL,
    subject      TEXT,
    description  TEXT,
    bloom_level  TEXT DEFAULT 'understand',
    position_x   DOUBLE PRECISION DEFAULT 0,  -- 布局坐标（或自动计算）
    position_y   DOUBLE PRECISION DEFAULT 0,
    metadata     JSONB DEFAULT '{}'
);

CREATE TABLE knowledge_graph_edges (
    edge_id      TEXT PRIMARY KEY,
    from_node    TEXT NOT NULL REFERENCES knowledge_graph_nodes(node_id),
    to_node      TEXT NOT NULL REFERENCES knowledge_graph_nodes(node_id),
    relation     TEXT DEFAULT 'prerequisite',  -- prerequisite / extends / applies / parallel
    weight       DOUBLE PRECISION DEFAULT 1.0, -- 依赖强度
    description  TEXT DEFAULT '',
    UNIQUE(from_node, to_node)
);
```

### 3.2 掌握度动态注入

每个节点的 `mastery` 不再硬编码，而是**实时从 BKT 引擎读取**：

```
graph node "calc-deriv" → BKT knowledge_state["calculus_derivative"].p_known × 100
```

如果知识点没有知识状态（未接触），显示为灰色 + "未开始"。

### 3.3 学习路径推荐

基于图搜索算法，为用户推荐最优学习路径：

```
输入: 用户当前 knowledge_states + 目标节点
算法: Dijkstra变体 — 边权重 = 依赖强度 × (1 - 当前掌握度)
输出: 推荐路径 [A → B → C → 目标]
      + 每个节点的预计练习时长
```

**示例**：用户想学「特征值」，当前只掌握「极限与连续 90%」
```
路径: 极限 → 导数(78%) → 矩阵(72%) → 特征值(55%)
预估: 极限已掌握, 导数练10题, 矩阵练15题, 特征值练20题
```

### 3.4 前置知识卡控

图谱边定义前置依赖 → 练习调度时自动卡控：

```python
def can_practice(skill_id, user_knowledge_states, graph):
    """检查是否满足前置条件"""
    prerequisites = graph.get_prerequisites(skill_id)
    for prereq in prerequisites:
        state = user_knowledge_states.get(prereq)
        if not state or state.p_known < 0.7:  # 前置未达到70%
            return False, f"建议先掌握: {prereq}"
    return True, None
```

这是下一阶段「前置知识卡控」模块的核心依赖。

---

## 四、跨模块互联

```
┌────────────────┐          ┌────────────────┐
│  Knowledge     │  实时查询  │  Graph API     │
│  Trace (BKT)   │─────────▶│  /api/knowledge│
│  p_known × 100 │ 掌握度    │  /graph        │
└────────┬───────┘          └───────┬────────┘
         │                          │
         │ knowledge_states         │ nodes + edges
         ▼                          ▼
┌────────────────┐          ┌────────────────┐
│  Study Plan    │  前置检查  │  Graph Engine  │
│  Generator     │◀─────────│  can_practice() │
│                │ 卡控      │                │
└────────┬───────┘          └───────┬────────┘
         │                          │
         │ 路径推荐                   │ 依赖关系
         ▼                          ▼
┌────────────────┐          ┌────────────────┐
│  ZPD Scheduler │  难度参考  │  Prerequisites │
│                │◀─────────│  JSON/YAML     │
└────────────────┘          └────────────────┘
```

### 具体连接点

| # | 源模块 | 目标模块 | 数据 | 状态 |
|---|--------|---------|------|:--:|
| 1 | BKT | Graph(API) | p_known → node.mastery | ✅ 已实现 |
| 2 | Graph Edge | ZPD Scheduler | 前置依赖 → 卡控选题 | ✅ 已实现 |
| 3 | Graph Path | Study Plan | 推荐路径 → plan items | ✅ 已实现 |
| 4 | Practice Stats | Graph(前端) | 实时更新掌握度环 | 🔴 前端待对接 |
| 5 | Graph Node | Content Search | 知识点 → 推荐资料 | 🔴 未实现 |
| 6 | Graph | Conversation | 对话中引用知识图谱 | 🔴 未实现 |
| 7 | Graph | Analytics | 掌握热力图数据源 | 🟡 部分 |

---

## 五、与论文的对照

| 论文/理论 | 实现位置 | 状态 |
|----------|---------|:--:|
| 知识空间理论 (Doignon & Falmagne) | 前置依赖边 | 🟡 静态硬编码 |
| 概念图 (Novak) | SVG 节点+边 | ✅ 静态原型 |
| 学习路径推荐 (Chen et al.) | graph engine (待做) | 🔴 未实现 |
| 掌握学习 (Bloom) | 掌握度环+前置卡控 | 🟡 环已做/卡控待做 |
| 最近发展区 (Vygotsky) | ZPD + 前置依赖 | 🟡 ZPD已做/卡控待做 |
| 自适应超媒体 (Brusilovsky) | 学习路径推荐 | 🔴 未实现 |

---

## 六、实施路线

| 阶段 | 内容 | 复杂度 | 依赖 |
|------|------|:--:|------|
| P0 | 新增 `GET /api/knowledge/graph` 后端API | 🟡 | **✅ 已完成** |
| P0 | 创建 `knowledge_graph_nodes/edges` 表 | 🟢 | 🟡 YAML 定义替代 |
| P0 | 前置知识卡控引擎 (PrerequisiteChecker) | 🟡 | **✅ 已完成** |
| P0 | 集成到 create_session / ZPD 调度 | 🟡 | **✅ 已完成** |
| P0 | API 端点 (graph/prerequisites/check/blocked/ready/path) | 🟡 | **✅ 已完成 6个** |
| P1 | 前端从 API 读取（替换硬编码） | 🟢 | P0 |
| P1 | 掌握度实时注入（BKT → mastery） | 🟡 | P0 |
| P1 | 图自动布局（力导向算法） | 🔴 | P0 |
| P2 | 学习路径推荐（Dijkstra变体） | 🔴 | P1 |
| P2 | 前置知识卡控集成到ZPD调度 | 🟡 | P1 |
| P3 | 对话中嵌入知识图谱引用 | 🟡 | P2 |
| P3 | 知识图谱3D/VR可视化 | 🔴 | P2 |
