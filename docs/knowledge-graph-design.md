# 知识图谱系统设计

> 版本: v2.0  
> 最后更新: 2026-05-19  
> 状态: **分区级动态知识图谱已全面实现**

---

## 一、系统定位

知识图谱是伴学系统的「地图」——**按分区（学习领域）独立生成**，AI 根据领域名+分支细化方向自动构建节点和前置依赖边，叠加 BKT 引擎的实时掌握度，让学习者一眼看清「已征服的领土」和「待攀登的山峰」。

**核心价值**：
- 可视化知识结构，消除「盲学」焦虑
- 前置依赖 → 告诉你「先学什么才能学这个」
- 掌握度热力 → 实时反馈学习进展
- 学习路径推荐 → 自动按依赖层级排序

---

## 二、当前实现（v2.0 动态图谱）

### 2.1 架构概览

```
┌──────────────────────────────────────────────────────────────────┐
│                        前端 (Next.js 14)                          │
│                                                                   │
│  /graph?partition_id=xxx    ← 图谱专用页                          │
│  ├─ 分区选择器下拉框                                              │
│  ├─ SVG 画布（分层 DAG 布局）                                     │
│  ├─ 缩放（跟鼠标）+ 平移                                          │
│  ├─ 节点图例（从数据提取学科）                                    │
│  ├─ 学习路径推荐面板                                              │
│  └─ AI 生成按钮                                                   │
│                                                                   │
│  /learn (学习空间)                                                │
│  └─ 分区侧栏 GitGraph 图标  ← 跳转↓                               │
│                                                                   │
│  / (Dashboard)                                                    │
│  └─ 「知识图谱」快捷卡片  ← 跳转↓                                 │
│                                                                   │
│  /learn?panel=graph       ← 自动重定向到 /graph                   │
└───────────────────────┬──────────────────────────────────────────┘
                        │ HTTP
                        ▼
┌──────────────────────────────────────────────────────────────────┐
│                     后端 (FastAPI)                                │
│                                                                   │
│  router: /api/knowledge/graph                                    │
│  ├─ GET  /{partition_id}           查询图谱 + BKT 掌握度注入       │
│  ├─ POST /{partition_id}/generate  AI 生成/更新图谱               │
│  ├─ PUT  /{partition_id}/nodes     节点 CRUD                      │
│  └─ PUT  /{partition_id}/edges     边 CRUD                        │
│                                                                   │
│  异步 Hook: 分支自动命名 → generate_graph_logic() (fire-and-forget)│
│  会话集成: knowledge_graph → system prompt 注入已掌握/薄弱/建议    │
└───────────────────────┬──────────────────────────────────────────┘
                        │
                        ▼
┌──────────────────────────────────────────────────────────────────┐
│                     数据层                                        │
│                                                                   │
│  UserData.knowledge_graphs: Dict[partition_id, KnowledgeGraph]    │
│  ├─ nodes: Dict[node_id, KGNode]                                 │
│  │   └─ mastery / mastery_level  ← BKT 引擎实时查询               │
│  └─ edges: List[KGEdge]                                          │
│      └─ from_id → to_id (前置依赖)                               │
└──────────────────────────────────────────────────────────────────┘
```

### 2.2 数据模型

```python
class KGNode:
    id: str              # "calculus_limits"
    label: str           # "极限与连续"
    description: str     # "理解极限概念，掌握连续函数性质"
    priority: int        # 1-10 学习优先级
    mastery: float       # 0-100（BKT 实时注入，非持久化）
    mastery_level: str   # "已掌握"|"接近掌握"|"发展中"|"初学"|"未接触"
    created_by: str      # "ai" | "user"（用户创建的节点不会被 AI 覆盖）

class KGEdge:
    from_id: str         # 前置节点
    to_id: str           # 后置节点
    relation: str        # "prerequisite" | "extends" | "applies"
    label: str           # 可选标签

class KnowledgeGraph:
    id: str              # 格式 "kg_{partition_id}"
    partition_id: str
    name: str
    nodes: Dict[str, KGNode]
    edges: List[KGEdge]
    version: int         # 每次修改递增
    generated_by: str    # "ai" | "manual"
```

### 2.3 前端布局算法

**分层 DAG（中心辐射）**：

```
拓扑排序 → 按深度分层
  Layer 0: 入度为0的根节点（入口知识）
  Layer 1: 直接后继
  Layer N: 叶子节点

每层坐标:
  x = marginX + (index × nodeSpacing)  + 层内居中偏移
  y = marginY + (layerIndex × layerHeight)

动态间距:
  layerHeight = max(160, 800 / 层数)
  nodeSpacing = max(200, 1000 / 列数)
```

### 2.4 API 端点

| 方法 | 路径 | 功能 | 说明 |
|------|------|------|------|
| GET | `/api/knowledge/graph/{partition_id}` | 获取图谱 | 含 BKT 实时掌握度注入 |
| POST | `/api/knowledge/graph/{partition_id}/generate` | AI 生成 | depth 1-5 控制生成深度 |
| PUT | `/api/knowledge/graph/{partition_id}/nodes` | 节点编辑 | action: add/update/delete |
| PUT | `/api/knowledge/graph/{partition_id}/edges` | 边编辑 | action: add/delete |

### 2.5 AI 生成流程

```
POST /{partition_id}/generate?depth=3
  │
  ▼
generate_graph_logic()
  ├─ 收集上下文: 分区名、学科、domain_tags、现有分支名
  ├─ 若已有图谱 → 列出已有点，要求增量添加
  ├─ 调用 LLM（temperature=0.3, max_tokens=4096）
  │   └─ Prompt: 生成 depth 层，JSON 格式节点+边
  ├─ 解析 LLM 返回的 JSON
  ├─ 合并：保留 user 创建的节点（created_by="user"）
  ├─ 保存到 UserData.knowledge_graphs
  └─ 返回 {total_nodes, total_edges, version}
```

### 2.6 异步图谱更新

分支自动命名时 fire-and-forget 触发：

```
用户多次对话 → 触发分支自动命名 → _trigger_graph_update()
                                        │
                           asyncio.create_task(_update())
                                        │
                           generate_graph_logic(
                               partition_id, branch_name, data)
                                        │
                           AI 增量更新图谱（不复写用户节点）
```

### 2.7 会话集成

每次对话时注入当前分区的知识图谱到 system prompt：

```
📊 知识图谱 (12个知识点):
   ✅ 已掌握: 极限与连续, 导数
   🔶 薄弱: 积分学, 多元函数
   ⬜ 未接触: 级数, 傅里叶变换
💡 建议下一步: 级数, 微分方程
```

### 2.8 交互功能

| 功能 | 实现 | 说明 |
|------|:--:|------|
| 分区选择器 | ✅ | 下拉列表切换分区，无需离开页面 |
| AI 生成 | ✅ | 一键调用 LLM 生成/更新图谱 |
| 缩放 | ✅ | 滚轮缩放 (0.3x~2x)，跟随鼠标位置 |
| 平移 | ✅ | 鼠标拖拽画布 |
| 页面防滚动 | ✅ | 滚轮在图谱区域不触发页面滚动 |
| 节点点击 | ✅ | 选中节点 → 侧边栏显示详情 |
| 掌握度环 | ✅ | `stroke-dasharray` 环形进度条 |
| 学科颜色 | ✅ | 从节点数据动态提取学科 |
| 前置知识 | ✅ | 侧边栏显示前置节点，可点击跳转 |
| 学习路径 | ✅ | 按拓扑层级分组展示推荐路径 |
| 图例 | ✅ | 动态从实际节点数据生成 |

---

## 三、入口路径

| 入口 | 路径 | 行为 |
|------|------|------|
| 侧栏图标 | 学习空间→分区右侧 `GitGraph` 按钮 | `router.push(/graph?partition_id=xxx)` |
| Dashboard | 首页「知识图谱」卡片 | `<Link href="/graph">` |
| 旧 URL | `/learn?partition_id=xxx&panel=graph` | `router.replace(/graph?partition_id=xxx)` |
| 图谱页 | 页面内「选择分区」下拉 | 切换分区重载图谱 |

---

## 四、跨模块互联

```
┌────────────────┐          ┌────────────────┐
│  BKT Engine    │  实时查询  │  Graph API     │
│  p_known × 100 │─────────▶│  GET /{pid}    │
│  mastery_level │  掌握度    │                │
└────────┬───────┘          └───────┬────────┘
         │                          │
         │                          │ nodes + edges
         ▼                          ▼
┌────────────────┐          ┌────────────────┐
│  Conversation  │  图谱注入  │  Graph Page    │
│  LLM           │◀─────────│  SVG 渲染      │
│  system prompt │  上下文    │  交互操作      │
└────────────────┘          └────────────────┘
         │                          │
         │ 分支命名                  │ GET/PUT
         ▼                          ▼
┌────────────────┐          ┌────────────────┐
│  Async Hook    │  fire &   │  UserData      │
│  _trigger_     │  forget   │  .knowledge_   │
│  graph_update  │─────────▶│  graphs[pid]   │
└────────────────┘          └────────────────┘
```

| # | 源模块 | 目标模块 | 数据 | 状态 |
|---|--------|---------|------|:--:|
| 1 | BKT Engine | Graph API | p_known → node.mastery | ✅ |
| 2 | Branch Naming | generate_graph_logic | 分支名 → 图谱增量 | ✅ |
| 3 | Conversation | System Prompt | 图谱 → 已掌握/薄弱/建议 | ✅ |
| 4 | Graph Page | Graph API | GET/POST/PUT | ✅ |
| 5 | Sidebar | Graph Page | router.push() | ✅ |
| 6 | Dashboard | Graph Page | `<Link>` | ✅ |
| 7 | Material System | Graph Node | 资料关联知识点 | 🔴 未实现 |
| 8 | Practice Scheduler | Graph Edge | 前置卡控选题 | 🟡 部分 |

---

## 五、与论文的对照

| 论文/理论 | 实现位置 | 状态 |
|----------|---------|:--:|
| 知识空间理论 (Doignon & Falmagne) | 前置依赖边 (KGEdge) | ✅ |
| 概念图 (Novak) | SVG 节点+边渲染 | ✅ |
| 掌握学习 (Bloom) | 掌握度环 + BKT 实时注入 | ✅ |
| 自适应超媒体 (Brusilovsky) | 分层拓扑路径推荐 | ✅ |
| 最近发展区 (Vygotsky) | System prompt 建议下一步 | ✅ |
| 学习路径推荐 (Chen et al.) | 拓扑排序 + priority 排序 | 🟡 基础实现 |

---

## 六、当前限制 & 未来规划

| 项目 | 当前状态 | 计划 |
|------|:--:|------|
| 数据表独立存储 | 🟡 UserData JSON 内嵌 | P2: 迁移到 PG `knowledge_graph_nodes/edges` |
| 图谱 → 资料关联 | 🔴 未实现 | P2: 知识点→搜索推荐资料 |
| 图谱 → 练习卡控 | 🟡 仅会话提示 | P2: ZPD 调度集成 |
| 图谱编辑 UI | 🔴 仅 API | P2: 图谱页可直接拖拽编辑 |
| 3D / VR 可视化 | 🔴 未实现 | P3 |
| 多用户图谱 | 🟡 仅 default_user | P3 |
