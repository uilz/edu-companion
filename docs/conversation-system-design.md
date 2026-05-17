# 智能伴学系统 · 对话系统设计文档

> 最后更新: 2026-05-17
> 版本: v0.2-draft

---

## 一、设计总览

### 核心理念

对话系统采用**树结构会话（Tree-Structured Conversation）**模型，取代传统的线性对话列表。每个对话分区（Partition）是一棵独立的树，所有分区共享一个根记忆树（Root Memory Tree）。系统支持多模态输入（文字、图片、语音、视频）。

### 核心特性

1. **树结构会话** — 消息是节点，支持分支、回溯、修改
2. **多模态消息** — 单条消息可包含多段文字+图片+语音+视频
3. **智能分区** — LLM + Embedding 自动分类对话到学科/方向分区
4. **分支管理** — 分区内自动判断延续/新建分支
5. **跨分区关联** — 支持跨学科讨论，标记关联分区
6. **分层摘要** — 消息级摘要（索引）+ 分区级上下文摘要（给LLM）
7. **元消息历史** — 所有消息异步写入历史文件夹，删除只从活跃树移除
8. **手动编辑** — 用户可进入树的任意节点，从该点创建新分支
9. **虚拟根节点** — 所有修改操作在父节点下挂新节点，不原地修改
10. **多用户隔离** — 数据按用户隔离，为后续登录系统预留

---

## 二、核心概念：分区 vs 分支

### 分区（Partition）= 学科/话题领域

类比：**Git 仓库**。一个分区对应一个学科或扩展方向，包含多条对话分支。

- 分区数量**不限制**
- 每个分区有独立的虚拟根节点、上下文摘要、标签
- 分区可自由扩展方向：学科、技能、项目、兴趣、生活等

### 分支（Branch）= 一条对话线程

类比：**Git 分支**。一个分区内可以有多条对话线程，每条是独立的探索路径。

- 每个分支是一条从虚拟根到叶节点的**线性路径**
- 分支深度**不限制**
- 同一时刻每个分区只有一个**活跃分支**
- 用户可以切换活跃分支，或从任意节点创建新分支

### 关系

```
Partition "高等数学"
├── Virtual Root (不可删除)
│   ├── Branch A (活跃) → msg1 → msg2 → msg3 → msg4
│   ├── Branch B (归档) → msg1 → msg2' → msg5
│   └── Branch C (归档) → msg1 → msg6
```

---

## 三、数据模型

### 3.1 树节点（TreeNode）

```typescript
interface TreeNode {
  id: string;                    // 唯一ID (UUID)
  parent_id: string;             // 父节点ID (虚拟根节点的id = 分区id)
  children_ids: string[];        // 子节点ID列表 (有序)

  // 分区与分支
  partition_id: string;          // 所属分区
  branch_id: string;             // 所属分支ID (见3.6)

  // 多模态内容 (引用 MessagePayload)
  content_blocks: ContentBlock[]; // 多模态内容块 (任意数量任意类型)
  text_summary: string;          // 纯文本摘要（自动从text块+转文字生成）

  // 摘要
  summary?: string;              // 消息摘要（仅长消息生成）

  // 跨分区
  cross_partition?: CrossPartitionMark;

  // 元数据
  role: "user" | "assistant";
  timestamp: number;
  token_count: number;
  is_deleted: boolean;           // 软删除标记
  is_archived: boolean;          // 归档标记（压缩后）
  has_modified_version: boolean; // 是否有修改版本（原节点标记）

  // 关联
  links_to?: string[];           // 跨分区引用的目标消息ID
  linked_from?: string[];        // 被哪些分区引用
}
```

### 3.2 消息内容（MessageContent）

单条消息支持**任意数量、任意类型**的内容块组合。一条消息可以同时包含：2段文字 + 5张图片 + 1条语音 + 2个视频 + 1个Word + 1个PDF，完全自由组合。

```typescript
// ── 内容块类型 ──

type ContentBlock =
  | TextBlock
  | ImageBlock
  | AudioBlock
  | VideoBlock
  | DocumentBlock;

interface TextBlock {
  type: "text";
  text: string;
}

interface ImageBlock {
  type: "image";
  file_id: string;               // 文件ID（引用FileRecord）
}

interface AudioBlock {
  type: "audio";
  file_id: string;
  duration_ms?: number;
  transcription?: string;        // ASR转文字（异步生成）
}

interface VideoBlock {
  type: "video";
  file_id: string;
  duration_ms?: number;
  thumbnail_file_id?: string;    // 缩略图文件ID
  transcription?: string;        // 字幕/转文字（异步生成）
}

interface DocumentBlock {
  type: "document";
  file_id: string;
  document_kind: "word" | "pdf" | "ppt" | "excel" | "markdown" | "code" | "other";
  page_count?: number;           // 页数（PDF/Word/PPT）
  text_content?: string;         // 提取的纯文本（异步OCR/解析生成）
  preview_text?: string;         // 前N字预览
}

// ── 文件记录（独立存储） ──

interface FileRecord {
  id: string;                    // 文件唯一ID
  user_id: string;
  original_name: string;         // 原始文件名 "题目截图.png"
  storage_path: string;          // 存储路径
  mime_type: string;             // "image/png"
  file_size: number;             // bytes
  file_type: FileType;          // "image" | "audio" | "video" | "document"
  
  // 异步处理结果
  processing_status: "pending" | "processing" | "done" | "failed";
  transcription?: string;        // 语音/视频转文字
  text_content?: string;         // 文档提取文本
  thumbnail_path?: string;       // 缩略图
  ocr_text?: string;             // 图片OCR文字
  
  // 元数据
  width?: number;                // 图片/视频宽度
  height?: number;               // 图片/视频高度
  duration_ms?: number;          // 音频/视频时长
  page_count?: number;           // 文档页数
  
  created_at: number;
}

type FileType = "image" | "audio" | "video" | "document";

// ── 一条消息的完整结构 ──

interface MessagePayload {
  blocks: ContentBlock[];        // 任意数量、任意类型组合
  text_summary: string;          // 纯文本摘要（自动从text块+转文字结果生成）
}
```

**示例：一条包含7个内容块的消息**

```typescript
const msg: MessagePayload = {
  blocks: [
    { type: "text", text: "老师，这道题和上次的视频里讲的不太一样，我整理了笔记和截图" },
    { type: "image", file_id: "file_001" },   // 题目截图1
    { type: "image", file_id: "file_002" },   // 题目截图2
    { type: "image", file_id: "file_003" },   // 笔记照片1
    { type: "image", file_id: "file_004" },   // 笔记照片2
    { type: "image", file_id: "file_005" },   // 笔记照片3
    { type: "video", file_id: "file_006" },   // B站视频片段
    { type: "audio", file_id: "file_007" },   // 语音说明
    { type: "text", text: "重点看第3张笔记" },
    { type: "document", file_id: "file_008" }, // 老师发的PDF讲义
  ],
  text_summary: "用户问题目，附5张图片(题目+笔记)、1段视频、1段语音、1份PDF讲义",
};
```

**发给LLM时的压缩格式**：

```
[Media] 5张图片, 1段视频(3min), 1段语音(8s), 1份PDF(12页)
[Image 1] 题目截图（OCR: 求函数f(x)=x³-3x²+2在[0,3]上的最值）
[Image 3] 笔记（OCR: 极限定义...）
[Audio] 转文字："这道题和视频里讲的不太一样"
[Video] 转文字："今天我们讲..."
[Document] PDF前100字："第三章 极限与连续..."
```
```

### 3.3 虚拟根节点（Virtual Root）

每个分区有一个**虚拟根节点**，不可删除，所有分支从这里开始：

```typescript
interface VirtualRoot {
  id: string;                    // = 分区ID
  type: "virtual_root";
  partition_id: string;
  children_ids: string[];        // 所有分支的第一条消息
}
```

**修改操作规则**：在父节点下挂新节点，不原地修改。虚拟根节点是所有分支的共同父节点。

```
修改前:
  VRoot → msg_A → msg_B → msg_C
                   ↓ 用户修改msg_A
修改后:
  VRoot → msg_A → msg_B → msg_C    (原分支，保留)
         → msg_A' → (新对话...)    (新分支)
```

### 3.4 分区（Partition）

```typescript
interface Partition {
  id: string;
  name: string;                  // "高等数学-极限与连续"
  subject: string;               // 学科 (可自由扩展)
  direction: string;             // 方向 (subject/skill/project/interest/life/...)
  emoji: string;                 // 视觉标识
  color: string;                 // 主题色

  // 树结构
  root_id: string;               // 虚拟根节点ID
  active_branch_id: string;      // 当前活跃分支ID

  // 摘要
  context_summary: string;       // 分区级上下文摘要（给LLM用）
  summary_branches: Record<string, string>; // branch_id → 分支摘要

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

**分区数量不限制**，用户可自由创建。

### 3.5 跨分区标记

```typescript
interface CrossPartitionMark {
  is_cross: boolean;
  primary_partition: string;     // 主分区
  linked_partitions: string[];   // 关联分区
}
```

### 3.6 分支ID（branch_id）定义

**branch_id** 是分支的唯一标识，规则：

1. **创建时机**：以下操作会创建新分支并分配新 branch_id
   - 首次进入分区（自动创建第一个分支）
   - 用户从某条消息分叉（创建新分支）
   - 用户修改某条消息（在父节点下挂新节点 = 新分支）
   - 分类AI判断消息是新话题（自动创建新分支）

2. **归属规则**：每个 TreeNode 属于且仅属于一个 branch_id

3. **分支路径**：Branch 维护 `path: string[]`，从虚拟根到叶节点的消息ID有序列表

4. **分支命名**：
   - 自动命名：取分支第一条消息的前20字
   - 用户可手动修改

```typescript
interface Branch {
  id: string;                    // UUID
  partition_id: string;
  name: string;                  // "什么是极限？..." / 用户自定义名
  fork_point_id?: string;        // 分叉点消息ID（可选）
  path: string[];                // 从虚拟根到叶的消息ID有序列表
  is_active: boolean;            // 是否为当前活跃分支
  is_archived: boolean;          // 是否已归档
  summary?: string;              // 分支摘要
  created_at: number;
  last_message_at: number;
}
```

### 3.7 元消息历史（Meta Message History）

```typescript
// 存储位置：~/.companion/history/{user_id}/
// 结构：
// ~/.companion/history/{user_id}/
// ├── 2026-05/
// │   ├── messages_001.jsonl
// │   └── messages_002.jsonl
// └── 2026-04/
//     └── messages_001.jsonl
```

每条消息异步写入，智能分片（≤100MB/片）。**只存放，不做处理**。

---

## 四、分区分类系统

### 4.1 分类流程：先分区 → 再分支

```
用户消息
  ↓
[Step 1] 分区分类 (Embedding + LLM)
  ├── 命中已有分区 → 进入Step 2
  ├── 模糊匹配 → LLM确认 → 进入Step 2
  └── 无匹配 → 创建新分区 → 创建第一个分支
  ↓
[Step 2] 分支决策 (规则引擎 + LLM)
  ├── 消息是当前分支的自然延续 → 挂到活跃分支
  ├── 消息是新话题 → 创建新分支
  ├── 消息是对历史某条的追问/修改 → 从该节点分叉
  └── 跨分区消息 → 标记跨分区，走跨分区流程
```

### 4.2 分区分类：Embedding + LLM 两层

```
[Layer 1] Embedding 相似度匹配 ( <50ms )
  ├── 相似度 > 0.85 → 直接命中分区
  ├── 相似度 0.65~0.85 → 进入Layer 2
  └── 相似度 < 0.65 → 新分区候选，进入Layer 2
  ↓
[Layer 2] LLM 分类确认 ( 1-2s )
  ├── 返回单一分区 → 确认
  ├── 返回 ≥2 分区 → 跨分区处理（见第六节）
  └── 返回新建分区 → 创建
```

### 4.3 关键词权重阈值

关键词检测使用**加权评分**，非二值判断：

```python
# 权重得分 = Σ(匹配关键词权重) / Σ(该分区所有关键词权重)
# 得分 > 0.6 → 该分区候选
# 多个分区 > 0.6 → 跨分区
# 关键词权重由学科重要性决定，可配置

keyword_weights = {
    "高等数学": {"极限": 0.9, "导数": 0.9, "积分": 0.85, "微分": 0.85, "泰勒": 0.8, ...},
    "线性代数": {"矩阵": 0.9, "行列式": 0.9, "特征值": 0.85, "向量": 0.7, ...},
    "大学物理": {"电磁": 0.85, "力学": 0.8, "热力学": 0.8, "量子": 0.75, ...},
    "英语":     {"单词": 0.7, "语法": 0.7, "阅读": 0.6, "听力": 0.6, ...},
    ...
}
```

### 4.4 分支决策规则

| 条件 | 行为 |
|------|------|
| 消息与当前分支最后3条语义连贯 | 延续当前分支 |
| 消息包含"刚才"、"上面"等回指词 | 检查是否指向历史节点，是则分叉 |
| 消息是全新话题（与当前分支无关） | 创建新分支 |
| 消息明确引用某条历史消息 | 从该消息分叉 |

### 4.5 分类触发条件

| 条件 | 行为 |
|------|------|
| 累计3条非短消息（>10字） | 触发分区分类 |
| 用户显式切换分区 | 清零计数器，新分区开始 |
| 消息包含高权重关键词 | 立即分类，不等3条 |
| 分区数 < 3 | 分类更积极（每2条触发） |
| 用户手动指定分区 | 跳过分类 |

### 4.6 分区上下文切换

| 情况 | 行为 |
|------|------|
| 当前分区 = 分类结果 | 直接继续 |
| 分类结果是当前分区的子话题 | 直接继续，不提示 |
| 分类结果是完全不同的分区 | 前端toast："这更像是[英语]的话题，要切换吗？" |
| 用户忽略提示继续打字 | 自动归入当前分区 |

---

## 五、发给LLM的上下文格式

### 5.1 上下文构成

发给LLM的完整上下文 = 系统提示 + 分区摘要 + 分支历史 + 当前消息

### 5.2 省Token的结构化格式

**不用JSON，用紧凑文本格式**：

```
[System]
你是智能伴学助手"小智"。当前分区：高等数学-极限。

[Context]
分区摘要：用户正在学习极限与连续，已掌握ε-δ定义，对单侧极限还有困惑。
关联分区摘要：线性代数-矩阵（掌握度72%），大学物理-力学（掌握度80%）。

[History]
1. [U] 什么是极限？
2. [A] 极限是...（省略详细内容，只保留结论）
3. [U] ε-δ语言怎么理解？
4. [A] ε-δ是...（省略）

[Media]
用户发送了1张图片：/uploads/photo_001.jpg
用户发送了1段语音(5s)：转文字"这道题怎么做"

[Current]
用户：这道题怎么做？
```

### 5.3 Token压缩策略

| 数据 | 压缩方式 | 节省比例 |
|------|----------|----------|
| 分区摘要 | 原文保留，按摘要长度截断 | ~60% |
| 历史消息 | 只保留最近5条完整，更早的只保留role+前20字 | ~70% |
| 媒体内容 | 文字描述替代（"用户发送了1张图片"） | ~90% |
| 知识状态 | `数学-极限:0.85, 数学-积分:0.62` 一行格式 | ~80% |

### 5.4 多分区摘要合并

当涉及跨分区讨论时，LLM需要看到多个分区的摘要：

```
[Context]
主分区-高等数学-极限：用户正在学习极限...
关联分区-线性代数-矩阵：用户矩阵运算掌握度72%...
关联分区-大学物理-力学：用户牛顿定律掌握度80%...
```

一般不压缩，直接合并。如果总token超限，临时压缩各摘要到目标长度。

---

## 六、跨分区关联处理

### 6.1 跨分区标记规则

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

### 6.2 跨分区整理（空闲时 + 每日定时）

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

### 6.3 LinkNode 结构

```typescript
interface LinkNode {
  id: string;
  type: "link";
  target_message_id: string;     // 原始消息ID
  target_partition_id: string;   // 原始分区
  target_branch_id: string;      // 原始分支
  source_partition_id: string;   // 当前分区
  source_branch_id: string;      // 当前分支
  preview_summary?: string;      // 快速预览摘要
  timestamp: number;
}
```

---

## 七、消息摘要与压缩

### 7.1 摘要分层

| 层级 | 内容 | 用途 | 触发条件 |
|------|------|------|----------|
| 原文 | 完整消息内容（含媒体引用） | 存储、回溯、编辑 | 始终保留 |
| 消息摘要 | 单条消息的概要 | 分区索引、跨分区匹配 | 消息 > 50字时生成 |
| 分区上下文摘要 | 整个分区对话的压缩 | 给LLM作为上下文 | 定时更新 |
| 分支摘要 | 单条分支的压缩 | 分支列表预览 | 分支归档时生成 |

### 7.2 压缩策略

**时机**：消息数 > 50 或 距上次压缩 > 24h 或 手动触发

**规则**：
- 只压缩**非活跃分支**（主分支最后N条不压缩）
- 压缩后的摘要保留：问题是什么、结论是什么、遗留问题
- 原始消息移到根记忆树，分区活跃记忆只剩摘要
- 摘要绑定 branch_id

```
压缩前:
  Branch A: [msg1, msg2, msg3, msg4, msg5]
                    ↓ 压缩前3条
压缩后:
  Branch A: [summary_1_2_3, msg4, msg5]
                         ↑ summary_1_2_3.bind_to = [msg1, msg2, msg3]
```

### 7.3 前端流式懒加载与虚拟滚动

**方案**：
- **虚拟列表**：只渲染可视区域内的节点（TanStack Virtual）
- **流式懒加载**：进入分区时只加载活跃分支最后N条，向上滚动加载更多
- **分支折叠**：非活跃分支默认折叠，展开时加载
- **媒体懒加载**：图片/视频滚动到可视区域才加载
- **LinkNode占位符**：先显示摘要，click时加载目标内容

---

## 八、消息删除与修改

### 8.1 删除操作

```
用户删除 msg3
  ↓
msg3 标记 is_deleted = true
  ↓
msg3 的子树一起删除（子节点也标记 is_deleted）
  ↓
msg3 从父节点的 children_ids 中移除
  ↓
msg3 如果是跨分区链接源 → 所有 LinkNode 标记 broken
  ↓
该分支摘要标记 dirty，下次访问时重算
  ↓
msg3 已异步写入元消息历史文件夹 → 不会真正丢失
```

### 8.2 修改操作

```
用户修改 msg2 的内容
  ↓
在 msg2 的父节点 (msg1 或 VRoot) 下挂新节点 msg2'
  ↓
msg2' 的 branch_id = 新分支ID
msg2' 的 children_ids = []（从修改点重新对话）
  ↓
msg2 标记 has_modified_version = true
  ↓
原分支完整保留：VRoot → msg1 → msg2 → msg3 → msg4
新分支独立发展：VRoot → msg1 → msg2' → (新对话...)
```

**修改规则**：
- 不原地修改，只在父节点下挂新节点
- 旧版本标记 `has_modified_version = true`
- 类似 Git 分支，不是 rebase

### 8.3 虚拟根节点的兜底作用

- 所有分支的第一条消息都是 VRoot 的子节点
- 修改第一条消息时，VRoot 下同时挂着原分支起点和新分支起点
- 删除操作不影响 VRoot
- VRoot 不可删除、不可修改

---

## 九、元消息历史

### 9.1 存储结构

```
~/.companion/history/{user_id}/
├── 2026-05/
│   ├── messages_001.jsonl      # 分片1 (< 100MB)
│   ├── messages_002.jsonl      # 分片2 (< 100MB)
│   └── ...
└── 2026-04/
    └── messages_001.jsonl
```

### 9.2 写入规则

- 每次发送消息**异步**写入元历史
- 写入目标：当前月份最新分片，满100MB则新建
- **只存放，不做处理**（不做压缩、不做分析）
- 删除操作不写入，但之前已写入的保留

### 9.3 数据格式（JSONL）

```json
{
  "id": "msg_xxx",
  "partition_id": "part_xxx",
  "branch_id": "branch_xxx",
  "role": "user",
  "content_blocks": [
    {"type": "text", "text": "这道题怎么做？"},
    {"type": "image", "file_id": "file_001"},
    {"type": "document", "file_id": "file_002", "document_kind": "pdf"}
  ],
  "text_summary": "用户问题目，附1张图片和1份PDF",
  "timestamp": 1715980800000,
  "tree_metadata": {
    "parent_id": "msg_yyy",
    "children_ids": ["msg_zzz"],
    "is_deleted": false
  }
}
```

---

## 十、文件上传与异步处理

### 10.1 架构：Branch Workspace（分支工作空间）

文件**不直接绑定消息**，而是挂载到**分支工作空间**。消息通过 `file_id` 引用工作空间中的文件。

```
Branch Workspace (branch_id: "branch_abc")
├── files/
│   ├── file_001.jpg          # 用户上传的题目截图
│   ├── file_002.pdf          # 老师发的讲义
│   ├── file_003.mp3          # 用户的语音提问
│   └── ...
├── metadata.json             # FileRecord 列表
└── workspace.json            # 工作空间状态
```

**好处**：
- 同一分支内多条消息引用同一文件（"看第3页"、"刚才那个图"）
- 分支归档时，工作空间一起归档
- 分支删除时，文件移入"孤儿存储"（可通过元历史恢复）
- 跨分支引用文件时，只复制 file_id 引用，不复制文件本身

### 10.2 上传流程

```
用户选择文件（图片/音频/视频/文档）
  ↓
前端上传 → 后端保存到 branch workspace
  ↓
创建 FileRecord (processing_status = "pending")
  ↓
返回 file_id，前端插入消息的 ContentBlock
  ↓
消息发送成功（用户立即看到消息）
  ↓
后台异步处理：
  ├── 图片 → OCR → FileRecord.ocr_text
  ├── 音频 → ASR → FileRecord.transcription
  ├── 视频 → 截帧 + ASR → 对应字段
  └── 文档 → 提取文本 → FileRecord.text_content
  ↓
处理完成 → 前端通过 WebSocket 推送更新
```

### 10.3 文件存储结构

```
~/.companion/
├── uploads/{user_id}/
│   ├── {branch_id}/          # Branch Workspace
│   │   ├── images/
│   │   ├── audio/
│   │   ├── video/
│   │   ├── documents/
│   │   └── metadata.json
│   └── orphaned/              # 分支删除后的孤儿文件
│       ├── file_xxx.jpg
│       └── ...
└── history/{user_id}/
    └── ...
```

### 10.4 文件生命周期

```
文件上传 → 挂载到 Branch Workspace
  ↓
分支活跃期间 → 所有消息自由引用
  ↓
分支归档 → 工作空间一起归档，文件保留
  ↓
分支删除 → 文件移入 orphaned/，保留30天
  ↓
30天后 → 彻底删除（不可恢复）
```

### 10.5 跨分支文件引用

用户在分支B中想引用分支A上传的文件：
- 消息 ContentBlock 中的 `file_id` 指向分支A的工作空间
- 系统自动在分支B的工作空间创建一个**符号引用**（不复制文件）
- 被引用的文件不会因为分支A删除而丢失（已移入orphaned的文件仍可引用）

### 10.6 文件大小限制

| 类型 | 单文件上限 | 单分支工作空间上限 | 单用户总上限 |
|------|-----------|-------------------|-------------|
| 图片 | 20MB | 无限制 | 无限制 |
| 音频 | 50MB | 无限制 | 无限制 |
| 视频 | 500MB | 无限制 | 无限制 |
| 文档 | 100MB | 无限制 | 无限制 |

**不设上限**，按需扩展存储。

### 10.7 处理队列

异步处理使用任务队列（MVP用asyncio，后续可换Celery）：
- 图片OCR：PaddleOCR 或云端API
- 音频ASR：Whisper本地模型 或 云端API
- 视频：ffmpeg截帧 + ASR
- 文档：pymupdf(PDF) / python-docx(Word) 提取文本

---

## 十一、树结构存储挑战与解法

| 挑战 | 解法 |
|------|------|
| 上下文加载 O(depth) | 活跃路径缓存 active_branch_path，O(1) 读取 |
| 内存占用 | MVP JSON文件够用(10万条<50MB)，字符串池去重，跨分区用引用 |
| 摘要一致性 | 分支级 dirty 标记，lazy evaluation 重算，不级联更新 |
| 树的GC | archived > 30天且无引用 → 清理，元历史独立存储 |
| 并发安全 | 分支级锁，MVP单用户概率低 |
| 媒体文件管理 | 独立存储目录，消息只存引用(路径)，删除消息时软删媒体 |

---

## 十二、多用户隔离

### 11.1 数据隔离

```
~/.companion/
├── data/
│   ├── user_001/
│   │   ├── partitions.json
│   │   ├── branches.json
│   │   ├── nodes/
│   │   │   ├── part_xxx.json    # 每个分区一棵树
│   │   │   └── ...
│   │   └── cache/
│   │       └── embeddings.json  # 缓存的embedding向量
│   └── user_002/
│       └── ...
├── history/
│   ├── user_001/
│   │   └── 2026-05/
│   └── user_002/
│       └── 2026-05/
└── uploads/
    ├── user_001/
    │   ├── images/
    │   ├── audio/
    │   └── video/
    └── user_002/
        └── ...
```

### 11.2 登录系统预留

- MVP阶段：单用户模式，user_id = "default_user"
- 所有接口预留 user_id 参数
- 后续加登录：JWT token → 解析 user_id → 隔离数据
- 数据模型已支持多用户，无需重构

---

## 十三、前端设计要点

### 12.1 两种会话管理视图

**视图A：层级导航**
```
全部会话
├── 📐 高等数学-极限 (3条分支)
│   ├── 🌿 什么是极限？... (活跃, 4条消息)
│   ├── 🌿 ε-δ语言怎么理解 (归档, 3条消息)
│   └── 🌿 + 新建分支
├── 📖 英语-词汇 (1条分支)
└── 🔬 物理-电磁学 (2条分支)
```

**视图B：时间线**
```
今天
├── 14:30 [高等数学] 这道题怎么做？ (图片)
├── 14:25 [高等数学] 什么是极限？
├── 13:10 [英语] unit8单词怎么记
昨天
├── 22:00 [物理] 电磁场公式推导
```

### 12.2 多模态输入框

```
┌─────────────────────────────────────┐
│  输入消息...                         │
│                                      │
│  📷 🎤 🎬                    [发送] │
└─────────────────────────────────────┘
```

- 文字输入：主区域
- 图片：点击📷或拖拽上传
- 语音：点击🎤录制，自动转文字
- 视频：点击🎬上传或录制片段

### 12.3 分区对话界面

```
┌─────────────────────────────────────┐
│  📐 高等数学-极限     [切换分区] [···] │
│                                      │
│  ┌─ Branch: 什么是极限？ ──────────┐ │
│  │  [msg1] 什么是极限？            │ │
│  │  [msg2] 极限的定义是...         │ │
│  │  [msg3] 那epsilon-delta语言呢？ │ │
│  │  [msg4] 好问题！让我解释...     │ │
│  └────────────────────────────────┘ │
│                                      │
│  ┌─ Branch: ε-δ语言怎么理解 ──────┐ │
│  │  📎 从msg2分叉 (3条消息)        │ │
│  └────────────────────────────────┘ │
│                                      │
│  ┌─────────────────────────────────┐│
│  │  输入消息...       📷 🎤 🎬 [→] ││
│  └─────────────────────────────────┘│
└─────────────────────────────────────┘
```

---

## 十四、分区合并

### 14.1 触发条件

- 两个分区的 embedding 中心相似度 > 0.8
- 或者用户手动选择合并
- 系统建议但不自动执行

### 14.2 合并流程

```
用户确认合并 Partition A → Partition B
  ↓
1. Partition A 的所有 Branch 整体移入 Partition B
   - branch_id 不变（UUID无冲突）
   - 每个 Branch 的 partition_id 更新为 B
  ↓
2. 更新 Branch 路径缓存
   - 所有 Branch 的 active_branch_path 重新计算
  ↓
3. 重建 Partition B 的 context_summary
   - 合并 A 和 B 的所有分支摘要
   - 生成新的分区级上下文摘要
  ↓
4. 更新跨分区引用
   - 所有 LinkNode 中 target_partition_id = A 的 → 改为 B
   - 所有 LinkNode 中 source_partition_id = A 的 → 改为 B
   - 同一分区内出现重复 LinkNode → 去重
  ↓
5. 更新文件引用
   - Partition A 的 Branch Workspace 文件保留
   - 文件路径从 uploads/{user_id}/{branch_id_A}/ 保持不变
   - 只更新 metadata.json 中的 partition_id
  ↓
6. 删除 Partition A
   - 从 partitions.json 中移除
   - 虚拟根节点删除
   - 元历史保留（不删除任何记录）
```

### 14.3 合并后命名

- 默认名称：取两个分区名称的交集部分
- 例："高等数学-极限" + "高等数学-积分" → "高等数学"
- 用户可手动修改

### 14.4 不可合并的情况

- 两个分区的 subject 不同（如"高等数学"和"英语"）
- 合并后总分支数 > 100（建议先归档旧分支）

---

## 十五、分支自动命名

### 15.1 初始命名

分支创建时，根据第一条消息生成名称：
- 简单规则：取第一条消息的前20字
- 可选LLM增强：生成更精确的名称

### 15.2 重新命名（摘要驱动）

当分支对话达到一定轮次后，根据累计摘要重新命名：

| 条件 | 行为 |
|------|------|
| 分支对话 ≤ 5轮 | 保持初始名称 |
| 分支对话 > 5轮 | 用分支摘要 + LLM 生成新名称 |
| 分支对话 > 20轮 | 再次重新命名（反映最新进展） |

**重新命名的LLM提示词**：
```
根据以下对话摘要，为这条对话分支生成一个简短的名称（≤15字）。
摘要：{branch_summary}
当前名称：{current_name}
```

### 15.3 用户手动命名

用户可随时修改分支名称，修改后不再自动重命名。

---

## 十六、开放问题

1. **Embedding模型选择** — 待定，可用选项：bge-m3、text2vec-large-chinese、m3e-base
2. ~~分区自动合并~~ → 已设计（§十四）
3. ~~存储上限~~ → 不设上限
4. ~~分支自动命名~~ → 已设计（§十五）
5. **导出功能** — 未来扩展
6. **跨分区搜索** — 未来扩展
