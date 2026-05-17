# 智能伴学系统 · 对话系统设计文档

> 最后更新: 2026-05-17
> 版本: v0.1-draft

---

## 一、设计总览

### 核心理念

对话系统采用**树结构会话（Tree-Structured Conversation）**模型，取代传统的线性对话列表。每个对话分区（Partition）是一棵独立的树，所有分区共享一个根记忆树（Root Memory Tree）。

### 核心特性

1. **树结构会话** — 消息是节点，支持分支、回溯、修改
2. **智能分区** — LLM + Embedding 自动分类对话到学科/方向分区
3. **跨分区关联** — 支持跨学科讨论，标记关联分区
4. **分层摘要** — 消息级摘要（索引）+ 分区级上下文摘要（给LLM）
5. **元消息历史** — 所有消息异步写入历史文件夹，删除只从活跃树移除
6. **手动编辑** — 用户可进入树的任意节点，从该点创建新分支
7. **虚拟根节点** — 所有修改操作在父节点下挂新节点，不原地修改

---

## 二、数据模型

### 2.1 树节点（TreeNode）

```typescript
interface TreeNode {
  id: string;                    // 唯一ID (UUID)
  parent_id: string | null;      // 父节点ID (null = 虚拟根节点)
  children_ids: string[];        // 子节点ID列表 (有序)
  
  // 消息内容
  role: "user" | "assistant";
  content: string;               // 原文（完整保留）
  summary?: string;              // 摘要（仅长消息生成）
  
  // 分区与分支
  partition_id: string;          // 所属分区
  branch_id: string;             // 所属分支ID
  
  // 跨分区
  cross_partition?: {
    is_cross: boolean;           // 是否跨分区消息
    primary_partition: string;   // 主分区
    linked_partitions: string[]; // 关联分区
  };
  
  // 元数据
  timestamp: number;
  token_count: number;
  is_deleted: boolean;           // 软删除标记
  is_archived: boolean;          // 归档标记（压缩后）
  is_modified: boolean;          // 是否有修改版本
  
  // 关联
  links_to?: string[];           // 跨分区引用的目标消息ID
  linked_from?: string[];        // 被哪些分区引用
}
```

### 2.2 虚拟根节点（Virtual Root）

每个分区有一个**虚拟根节点**，不可删除，所有分支从这里开始：

```typescript
interface VirtualRoot {
  id: string;                    // 分区ID即根节点ID
  type: "virtual_root";
  partition_id: string;
  children_ids: string[];        // 所有分支的第一条消息
  // 不可删除、不可修改
}
```

**修改操作的规则**：
- 不在原节点上修改内容
- 在原节点的**父节点**下挂一个新节点（新分支的起点）
- 原节点及其子树保持不变
- 新节点及其子树是"修改后的版本"

```
修改前:
  parent → msg_A → msg_B → msg_C
                    ↓ 修改msg_A
修改后:
  parent → msg_A → msg_B → msg_C    (原分支，保留)
         → msg_A' → msg_B' → ...    (新分支，从修改点开始)
```

### 2.3 分区（Partition）

```typescript
interface Partition {
  id: string;
  name: string;                  // "高等数学-极限与连续"
  subject: string;               // 学科
  direction: string;             // 扩展方向 (subject/skill/project/interest/life)
  emoji: string;                 // 视觉标识
  color: string;                 // 主题色
  
  // 树结构
  root_id: string;               // 虚拟根节点ID
  active_branch_id: string;      // 当前活跃分支ID
  
  // 摘要
  context_summary: string;       // 分区级上下文摘要（给LLM用）
  summary_branches: Record<string, string>; // branch_id → summary
  
  // 标签
  tags: string[];
  
  // 时间
  created_at: number;
  updated_at: number;
  last_active_at: number;
  
  // 统计
  message_count: number;
  total_tokens: number;
}
```

### 2.4 分支（Branch）

```typescript
interface Branch {
  id: string;
  partition_id: string;
  name?: string;                 // 分支名称（可选）
  fork_point_id?: string;        // 分叉点消息ID（如果是从某条消息分叉）
  
  // 路径
  path: string[];                // 从根到叶的消息ID有序列表
  
  // 状态
  is_active: boolean;            // 是否为当前活跃分支
  is_archived: boolean;          // 是否已归档
  
  // 摘要
  summary?: string;              // 该分支的摘要
  
  // 时间
  created_at: number;
  last_message_at: number;
}
```

### 2.5 元消息历史（Meta Message History）

```typescript
interface MetaHistoryDir {
  path: string;                  // ~/.companion/history/
  structure: {
    "2026-05/": {
      "messages_001.jsonl": [],  // 分片文件，每片≤100MB
      "messages_002.jsonl": [],
    },
    "2026-04/": {
      "messages_001.jsonl": [],
    },
  }
}
```

每条消息（包括删除的）异步写入对应月份的子文件，智能分片：
- 当前活跃分片 < 100MB → 追加写入
- 当前活跃分片 ≥ 100MB → 新建 messages_XXX.jsonl
- 删除操作只修改活跃树，元历史不删

---

## 三、分区分类系统

### 3.1 分类策略：Embedding + LLM 两层

```
用户消息
  ↓
[Layer 1] Embedding 相似度匹配 ( <50ms )
  ├── 相似度 > 0.85 → 直接命中分区
  ├── 相似度 0.65~0.85 → 进入Layer 2
  └── 相似度 < 0.65 → 新分区候选，进入Layer 2
  ↓
[Layer 2] LLM 分类确认 ( 1-2s )
  ├── 返回单一分区 → 确认
  ├── 返回 ≥2 分区 → 跨分区处理
  └── 返回新建分区 → 创建
```

### 3.2 关键词权重阈值（非二值判断）

关键词检测使用**加权评分**而非直接匹配：

```python
keyword_weights = {
    "高等数学": ["极限", "导数", "积分", "微分", "泰勒", ...],  # 权重 0.8
    "线性代数": ["矩阵", "行列式", "特征值", "向量", ...],      # 权重 0.8
    "大学物理": ["电磁", "力学", "热力学", "量子", ...],        # 权重 0.7
    "英语": ["单词", "语法", "阅读", "听力", ...],              # 权重 0.6
    ...
}

# 计算方式：匹配关键词的权重之和 / 总权重 × 权重系数
# 得分 > 阈值(0.6) → 该分区候选
# 多个分区都 > 阈值 → 跨分区
```

### 3.3 分类触发条件

| 条件 | 行为 |
|------|------|
| 累计3条非短消息（>10字） | 触发分类判断 |
| 用户显式切换分区 | 清零计数器，新分区开始 |
| 消息包含高权重关键词 | 立即分类，不等3条 |
| 分区数 < 3 | 分类更积极（每2条触发） |
| 用户手动指定分区 | 跳过分类 |

### 3.4 分区上下文切换

| 情况 | 行为 |
|------|------|
| 当前分区 = 分类结果 | 直接继续 |
| 分类结果是当前分区的子话题 | 直接继续，不提示 |
| 分类结果是完全不同的分区 | 前端toast提示："这更像是[英语]的话题，要切换吗？" |
| 用户忽略提示继续打字 | 自动归入当前分区（尊重用户意图） |

---

## 四、跨分区关联处理

### 4.1 跨分区标记规则

```
用户消息 → 分类AI返回 ≥2 分区
  ↓
选择主分区（基于：当前所在分区 + 关联强度）
  ↓
标记为跨分区讨论：
  - 主分区：正常挂载消息节点
  - 关联分区：创建 LinkNode（引用主分区消息ID）
  ↓
后续消息 + 跨分区标签
  ↓
累计3条非短消息后重新分类
  ↓
如果分类AI返回不同结果 → 跨分区段结束
```

### 4.2 跨分区整理（空闲时 + 每日定时）

```
整理流程：
1. 找到所有跨分区消息组（相同 cross_partition 标记）
2. 判断"相同"的标准：
   - 同一用户消息产生的assistant回复 → 直接算相同
   - 不同用户消息但语义相似（embedding余弦 > 0.85）→ 也视为相同
3. 不合并的情况：
   - A+B 与 A+C → 不算相同类型
   - A+B 与 A+B+C → 不算相同类型（参与分区不同）
4. 整理结果：
   - 为每条消息在各关联分区生成 LinkNode
   - LinkNode 绑定 branch_id，指向原始消息
   - 更新各分区的 context_summary
```

### 4.3 LinkNode 结构

```typescript
interface LinkNode {
  id: string;
  type: "link";
  target_message_id: string;     // 原始消息ID
  target_partition_id: string;   // 原始分区
  target_branch_id: string;      // 原始分支
  source_partition_id: string;   // 当前分区
  source_branch_id: string;      // 当前分支
  
  // 摘要（可选，用于快速预览）
  preview_summary?: string;
  
  timestamp: number;
}
```

---

## 五、消息摘要与压缩

### 5.1 摘要分层

| 层级 | 内容 | 用途 | 触发条件 |
|------|------|------|----------|
| 原文 | 完整消息内容 | 存储、回溯、编辑 | 始终保留 |
| 消息摘要 | 单条消息的概要 | 分区索引、跨分区匹配 | 消息 > 50字时生成 |
| 分区上下文摘要 | 整个分区对话的压缩 | 给LLM作为上下文 | 定时更新 |
| 分支摘要 | 单条分支的压缩 | 分支列表预览 | 分支归档时生成 |

### 5.2 压缩策略

**时机**：
- 分区内消息数 > 50条
- 距离上次压缩 > 24小时
- 用户手动触发

**规则**：
- 只压缩**非活跃分支**（主分支最后N条不压缩）
- 压缩后的摘要保留：问题是什么、结论是什么、遗留问题
- 原始消息移到根记忆树，分区活跃记忆只剩摘要
- 摘要绑定 branch_id，分枝结构保持

```
压缩前:
  Branch A: [msg1, msg2, msg3, msg4, msg5]
                    ↓ 压缩前3条
压缩后:
  Branch A: [summary_1_2_3, msg4, msg5]
                         ↑ summary_1_2_3.bind_to = [msg1, msg2, msg3]
```

### 5.3 前端流式懒加载与虚拟滚动

**树结构的前端渲染挑战**：
- 可能有数千个节点，不能全部渲染
- 需要按需加载（用户滚动到才加载）
- 跨分区链接需要异步解析

**方案**：
- **虚拟列表**：只渲染可视区域内的节点（React Virtual / TanStack Virtual）
- **流式懒加载**：进入分区时只加载活跃分支的最后N条，向上滚动时加载更多
- **分支折叠**：非活跃分支默认折叠，展开时加载
- **链接异步解析**：LinkNode 先显示占位符，hover/click 时加载目标内容

---

## 六、消息删除与修改

### 6.1 删除操作

```
用户删除 msg3
  ↓
msg3 标记 is_deleted = true
  ↓
msg3 的子节点 (msg4, msg5) re-parent 到 msg3 的父节点 (msg2)
  ↓
msg3 如果是跨分区链接源 → 所有 LinkNode 标记 broken，提示用户
  ↓
该分支摘要标记 dirty，下次访问时重算
  ↓
msg3 已异步写入元消息历史文件夹 → 不会真正丢失
```

**删除规则**：
- 删除消息 = 删除该消息及其整棵子树
- 子树节点也标记 is_deleted = true
- 所有节点保留在元消息历史中
- 树结构中的指针关系断开（re-parent 或直接移除）

### 6.2 修改操作

```
用户修改 msg2 的内容
  ↓
在 msg2 的父节点 (msg1) 下挂新节点 msg2'
  ↓
msg2' 的 children 初始为空（用户从修改点重新对话）
  ↓
msg2 标记 is_modified = true（有修改版本）
  ↓
msg2 的原始子树 (msg3, msg4) 保持在 msg2 下
  ↓
新分支: parent → msg2' → (新对话...)
  ↓
原分支: parent → msg2 → msg3 → msg4 (完整保留)
  ↓
摘要重算：msg2' 所在分支
```

**修改规则**：
- 不原地修改，只创建新分支
- 旧版本标记 is_modified = true，保留在树中
- 新版本从父节点分叉，独立发展
- 类似 Git 的分支，不是 rebase

### 6.3 虚拟根节点的作用

每个分区有一个虚拟根节点（Virtual Root），不可删除、不可修改：
- 所有分支的第一条消息都是它的子节点
- 修改操作在虚拟根下挂新节点
- 删除操作不影响虚拟根
- 提供稳定的树根，方便遍历和序列化

---

## 七、元消息历史

### 7.1 存储结构

```
~/.companion/history/
├── 2026-05/
│   ├── messages_001.jsonl      # 分片1 (< 100MB)
│   ├── messages_002.jsonl      # 分片2 (< 100MB)
│   └── ...
├── 2026-04/
│   └── messages_001.jsonl
└── ...
```

### 7.2 写入规则

- 每次发送消息（user 或 assistant）都**异步**写入元历史
- 写入目标：当前月份子文件夹中最新的分片文件
- 如果当前分片 ≥ 100MB → 新建 messages_XXX.jsonl
- 删除操作**不写入元历史**（删除只修改活跃树的 is_deleted 标记）
- 但被删除的消息**之前已经写入过元历史**，所以不会丢失

### 7.3 数据格式（JSONL）

每行一条消息：
```json
{
  "id": "msg_xxx",
  "partition_id": "part_xxx",
  "branch_id": "branch_xxx",
  "role": "user",
  "content": "什么是极限？",
  "summary": "用户询问极限的定义",
  "timestamp": 1715980800000,
  "token_count": 12,
  "tree_metadata": {
    "parent_id": "msg_yyy",
    "children_ids": ["msg_zzz"],
    "is_deleted": false,
    "is_archived": false
  }
}
```

---

## 八、树结构存储挑战与解法

### 8.1 上下文加载效率

**问题**：加载分区上下文需要从根遍历到活跃叶节点，O(depth) 复杂度。

**解法**：
- 每个分区维护**活跃路径缓存**（active_branch_path）：有序消息ID列表
- 加载时直接读缓存，O(1)
- 缓存失效条件：分支切换、消息增删

### 8.2 内存占用

**问题**：树结构每个节点需要 parent_id、children_ids、branch_id 等元数据。

**解法**：
- MVP阶段 JSON 文件完全够用（10万条消息 < 50MB）
- 消息内容用字符串池（相同内容不重复存储）
- 跨分区用引用（8字节指针 vs 1KB消息内容）
- 元数据占总存储的 ~15-20%，可接受

### 8.3 摘要一致性

**问题**：消息删除/修改后，分支摘要需要重算，级联更新成本高。

**解法**：
- 摘要只绑到分支级别，不是消息级别
- 删除/修改后，标记该分支摘要为 dirty
- 下次访问时重算（lazy evaluation）
- 不级联更新 — 摘要本身就是近似的

### 8.4 树的 GC（垃圾回收）

**问题**：大量 archived/deleted 节点占内存。

**解法**：
- 定期清理：archived 超过 30 天且无子节点引用 → 彻底删除
- 根记忆树保留压缩摘要，不保留原文
- 元消息历史文件夹独立存储，不影响树大小

### 8.5 并发安全

**问题**：用户编辑消息时，摘要生成器可能正在读取同一分支。

**解法**：
- 分支级锁（branch-level lock）：修改分支时，阻塞该分支的摘要生成
- 其他分支不受影响
- MVP单用户场景下，实际并发概率低

---

## 九、前端设计要点

### 9.1 对话管理界面

```
┌─────────────────────────────────────┐
│  📚 全部对话                         │
│  ├─ 📐 高等数学-极限     [3条消息]   │
│  ├─ 📐 高等数学-积分     [12条消息]  │
│  ├─ 📖 英语-词汇         [8条消息]   │
│  ├─ 🔬 物理-电磁学       [5条消息]   │
│  └─ 💡 创意项目          [2条消息]   │
│                                      │
│  ┌─────────────────────────────────┐│
│  │  主输入框（智能分类）            ││
│  │  输入消息...                     ││
│  └─────────────────────────────────┘│
└─────────────────────────────────────┘
```

### 9.2 分区对话界面

```
┌─────────────────────────────────────┐
│  📐 高等数学-极限          [切换分区] │
│                                      │
│  ┌─ Branch A (活跃) ──────────────┐ │
│  │  [msg1] 什么是极限？           │ │
│  │  [msg2] 极限的定义是...        │ │
│  │  [msg3] 那epsilon-delta语言呢？│ │
│  │  [msg4] 好问题！让我解释...    │ │
│  └────────────────────────────────┘ │
│                                      │
│  ┌─ Branch B (归档) ──────────────┐ │
│  │  📎 从msg2分叉 (3条消息)       │ │
│  └────────────────────────────────┘ │
│                                      │
│  ┌─────────────────────────────────┐│
│  │  输入消息...          [发送]    ││
│  └─────────────────────────────────┘│
└─────────────────────────────────────┘
```

### 9.3 虚拟滚动实现

- 使用 TanStack Virtual 或 react-window
- 只渲染可视区域 ± buffer 的节点
- 向上滚动时动态加载更多历史消息
- LinkNode 使用 Skeleton 占位符，hover 时异步加载

---

## 十、待确认/开放问题

1. **分区最大数量限制** — 是否限制分区数？还是完全自由扩展？
2. **跨分区消息的LLM上下文** — 跨分区讨论时，LLM是否能同时看到多个分区的摘要？
3. **消息内容的最大长度** — 单条消息的token上限？
4. **分支的最大深度** — 是否限制分支深度防止无限分叉？
5. **元历史的检索** — 是否需要对元历史做全文检索？还是只按时间浏览？
6. **多用户支持** — 当前设计为单用户，后续多用户时分区是否隔离？

---

## 附录：相关文档

- [架构总设计](./01-architecture-overview.md)
- [技术栈选型](./02-tech-stack.md)
- [API设计](./03-api-design.md)
- [前端设计规范](./04-frontend-design.md)
