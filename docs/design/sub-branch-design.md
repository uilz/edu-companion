# 子支（Sub-Branch）设计方案 v3.0

## 一、概念定义

### 层级关系
```
分区 → 领域 → 专题 → 会话(Conversation) → 消息(Message)
                                              ├─ 子支引用（文本锚点）
                                              └─ 子支会话(SubBranch Conv) → 消息链
                                                                              └─ 可递归子支
```

- **旁支（现有）**：会话级别，侧边栏切换
- **子支（新增）**：消息级别，由「引用」触发，锚定在某条消息的特定文本上，可递归

### 核心设计原则
1. **子支摘要回写父消息**：子支摘要写入父消息的 `metadata.sub_branch_summaries[]`
2. **父会话 LLM 天然感知**：父消息包含子支摘要 → LLM 自动看到子支讨论结果
3. **子支 LLM 上下文**：引用片段 + 子支内消息
4. **消息内联展示**：子支标识嵌入消息气泡内
5. **引用 = 内容块**：引用作为一种 ContentBlock，普通发送时也携带引用信息

---

## 二、数据模型

### 2.1 新增 QuoteBlock（引用内容块）

```python
class QuoteBlock(BaseModel):
    """引用内容块 — 类似文件附件，展示引用的原文"""
    type: Literal["quote"] = "quote"
    source_message_id: str           # 被引用消息 ID
    source_conversation_id: str      # 被引用消息所在会话 ID
    char_start: int                  # 选中文本起始偏移
    char_end: int                    # 选中文本结束偏移
    quoted_text: str                 # 引用的原文
```

**ContentBlock 联合类型扩展：**
```python
ContentBlock = TextBlock | ImageBlock | AudioBlock | VideoBlock | DocumentBlock | QuoteBlock
```

**消息内容示例：**
```json
{
    "content_blocks": [
        {"type": "quote", "source_message_id": "msg_123", "quoted_text": "第一类曲线积分 ∫_L f(x,y) ds", ...},
        {"type": "text", "text": "什么是第一类曲线积分？"}
    ]
}
```

### 2.2 SubBranchRef（子支引用锚点）

```python
class SubBranchRef(BaseModel):
    """子支引用锚点 — 记录子支是从哪条消息、哪个文本范围创建的"""
    id: str
    source_message_id: str
    char_start: int
    char_end: int
    quoted_text: str
    child_conversation_id: str
    created_at: float
```

### 2.3 Conversation 扩展

```python
class Conversation(BaseModel):
    # ... 现有字段 ...
    
    parent_conversation_id: str = ""           # 父会话 ID（空=顶层会话）
    parent_sub_branch_ref: SubBranchRef | None = None  # 作为子支时的引用锚点
    sub_branch_ids: list[str] = []             # 直接子支会话 ID 列表
    depth: int = 0                             # 子支深度（0=顶层，1=一级子支...）
```

### 2.4 TreeNode 扩展

```python
class TreeNode(BaseModel):
    # ... 现有字段 ...
    
    has_sub_branches: bool = False
    sub_branch_ids: list[str] = []
    sub_branch_summaries: list[dict] = []      # [{"conversation_id", "quoted_text", "summary"}]
```

---

## 三、两种发送模式

### 3.1 引用 + 普通发送（QuoteBlock 模式）

```
┌─────────────────────────────────────────┐
│ ChatInput：                             │
│ ┌─────────────────────────────────────┐ │
│ │ 📎「第一类曲线积分 ∫_L f(x,y) ds」│ │ ← 引用预览条（类文件附件栏）
│ │                              ✕      │ │
│ └─────────────────────────────────────┘ │
│ ┌─────────────────────────────────────┐ │
│ │ 什么是第一类曲线积分？               │ │
│ └─────────────────────────────────────┘ │
│                     [普通发送] [📎子支]  │
└─────────────────────────────────────────┘

发送后消息结构：
┌─────────────────────────────────────────┐
│ 👤                                     │
│ ┌─ 引用 ─────────────────────────────┐ │ ← QuoteBlock 渲染（类文件附件）
│ │ 📎 「第一类曲线积分 ∫_L f(x,y) ds」│ │    点击可跳转到原消息
│ │    —— 来自上文                     │ │
│ └────────────────────────────────────┘ │
│ 什么是第一类曲线积分？                   │ ← TextBlock 渲染
└─────────────────────────────────────────┘
```

**数据流：**
1. 用户选中文本 → 点击「引用」→ `pendingQuote` 设置
2. 用户输入问题
3. 点击「普通发送」
4. 前端构造消息：`content_blocks: [QuoteBlock(...), TextBlock(text)]`
5. 调用 `add_message` 发送到当前会话
6. 消息渲染时，QuoteBlock 显示为引用附件栏

### 3.2 引用 + 子支发送（SubBranch 模式）

```
┌─────────────────────────────────────────┐
│ ChatInput：                             │
│ ┌─────────────────────────────────────┐ │
│ │ 📎「第一类曲线积分 ∫_L f(x,y) ds」│ │ ← 同样的引用预览条
│ │                              ✕      │ │
│ └─────────────────────────────────────┘ │
│ ┌─────────────────────────────────────┐ │
│ │ 什么是第一类曲线积分？               │ │
│ └─────────────────────────────────────┘ │
│                     [普通发送] [📎子支]  │
└─────────────────────────────────────────┘

点击 [📎子支] 后：
1. 创建子支会话（parent_conversation_id + parent_sub_branch_ref）
2. 切换到子支会话
3. 发送消息（content_blocks: [QuoteBlock(...), TextBlock(text)]）
4. 更新父消息的 has_sub_branches + sub_branch_ids
```

**子支内视图：**
```
┌─────────────────────────────────────────┐
│ ← 退出 │ 💬「第一类曲线积分」           │ ← 顶部横幅
├─────────────────────────────────────────┤
│ ┌─ 引用上下文 ─────────────────────┐   │
│ │ 曲线积分分为两类：               │   │ ← QuoteContextCard
│ │ ① 第一类曲线积分 ∫_L f(x,y) ds │   │    引用部分高亮
│ │   其中 ds 是弧长微元...          │   │
│ └──────────────────────────────────┘   │
│                                         │
│ 👤 什么是第一类曲线积分？               │ ← 用户消息（也带 QuoteBlock）
│                                         │
│ 🤖 第一类曲线积分（对弧长的曲线积分）  │
│    定义为...                            │
└─────────────────────────────────────────┘
```

### 3.3 QuoteBlock 渲染样式

**用户消息中的 QuoteBlock（附件栏样式）：**
```
┌─────────────────────────────────────────┐
│ ┌─────────────────────────────────────┐ │
│ │ 📎「第一类曲线积分 ∫_L f(x,y) ds」│ │  ← 圆角卡片，accent 边框
│ │    曲线积分分为两类：① 第一类...   │ │     显示引用原文截断
│ │    —— 来自「曲线积分」             │ │     来源会话名
│ └─────────────────────────────────────┘ │
│ 什么是第一类曲线积分？                   │
└─────────────────────────────────────────┘
```

**AI 消息不显示 QuoteBlock**（AI 不引用，只回复）

**渲染规则：**
- QuoteBlock 始终在 TextBlock 之前渲染
- 样式类似文件附件栏：圆角卡片 + 左侧 accent 边框 + 引用图标
- 点击 QuoteBlock → 跳转到原消息（父会话中滚动定位）
- 如果原消息在其他会话中 → 先切换会话再滚动

---

## 四、交互设计

### 4.1 文本选择

**选区规则：**
1. 单击 → 选句子（边界：`。！？!?\n`）
2. 双击 → 扩段（边界：`\n\n`）
3. 三击 → 全文
4. 已选中时单击 → 取消

**浮动工具栏：** 选区上方，`📎 引用` + `📋 复制`

**移动端：** 长按触发选择，逻辑一致

### 4.2 消息中的子支标识

```
┌─────────────────────────────────────────┐
│ 🤖 曲线积分分为两类：                   │
│ ① 第一类曲线积分 ∫_L f(x,y) ds        │
│   其中 ds 是弧长微元...                  │
│ ② 第二类曲线积分 ∫_L Pdx + Qdy        │
│   其中 L 有方向...                       │
│                                         │
│ ─────────────────────────────────────── │
│ 💬「第一类曲线积分」→ 3条  ▸            │ ← 内联子支条目
│ 💬「第二类曲线积分」→ 1条  ▸            │
└─────────────────────────────────────────┘
```

**交互：**
- 子支条目在消息气泡底部，与正文有分隔线
- 引用原文在正文中底色高亮，可点击跳转
- 多个子支 → 点击展开列表，选择进入
- 单个子支 → 点击直接进入
- 子支条目默认收起，显示 `▸ N个子支`

### 4.3 退出子支

- 顶部横幅 `← 退出` 按钮
- 退出时触发摘要生成（异步）
- 切换回父会话，滚动到引用消息位置

---

## 五、LLM 上下文策略

### 5.1 父会话 → LLM
- 父消息的 `sub_branch_summaries[]` 注入 system prompt：
  ```
  [子支讨论摘要]
  关于「第一类曲线积分」：用户询问了定义和计算方法，已掌握基本概念。
  ```

### 5.2 子支 → LLM
- 引用上下文注入 system prompt：
  ```
  [引用上下文]
  用户从以下内容中引用了「第一类曲线积分 ∫_L f(x,y) ds」：
  > 曲线积分分为两类：① 第一类曲线积分 ∫_L f(x,y) ds 其中 ds 是弧长微元...
  ```
- 子支内消息链
- 不需要父会话完整历史

### 5.3 子支摘要生成
- 参考现有 `branch_summarizer.py` 机制
- `summary_dirty = True` → 需要时生成
- 退出子支时触发，或父会话加载时检查 dirty
- 写入父消息 `sub_branch_summaries[]`

---

## 六、API 设计

### 6.1 创建子支
```
POST /api/conversations/sub-branch
{
    "source_conversation_id", "source_message_id",
    "char_start", "char_end", "quoted_text",
    "initial_message": "什么是第一类曲线积分？"
}
→ { "conversation": {...}, "sub_branch_ref": {...} }
```

### 6.2 获取消息的子支列表
```
GET /api/conversations/messages/{message_id}/sub-branches
→ { "sub_branches": [{ "conversation_id", "quoted_text", "message_count", "summary" }] }
```

### 6.3 退出子支
```
GET /api/conversations/sub-branch/{conv_id}/parent
→ { "parent_conversation_id", "source_message_id", "char_start", "char_end" }
```

### 6.4 生成子支摘要
```
POST /api/conversations/sub-branch/{conv_id}/summarize
→ { "summary", "parent_message_id" }
```

### 6.5 删除子支
```
DELETE /api/conversations/sub-branch/{conv_id}
→ { "ok": true, "parent_message_id", "remaining_count" }
```

---

## 七、前端状态设计

### 7.1 Store 新增

```typescript
interface SubBranchState {
    pendingQuote: {
        sourceMessageId: string;
        sourceConversationId: string;
        charStart: number;
        charEnd: number;
        quotedText: string;
    } | null;
    
    isInSubBranch: boolean;
    subBranchParentConvId: string | null;
    subBranchSourceMsgId: string | null;
    
    subBranchCache: Record<string, SubBranchInfo[]>;
}
```

### 7.2 Store Actions

```typescript
setPendingQuote: (quote) => void;
clearPendingQuote: () => void;
createSubBranch: (sourceConvId, sourceMsgId, charStart, charEnd, quotedText, initialMsg) => Promise<string>;
enterSubBranch: (subBranchConvId) => void;
exitSubBranch: () => Promise<void>;
loadSubBranches: (messageId) => Promise<void>;
deleteSubBranch: (subBranchConvId) => Promise<void>;
```

---

## 八、组件设计

### 8.1 新增组件

| 组件 | 文件 | 职责 |
|------|------|------|
| `TextSelectionToolbar` | `TextSelectionToolbar.tsx` | 浮动工具栏（引用+复制） |
| `SubBranchBanner` | `SubBranchBanner.tsx` | 子支顶部横幅（退出+标题） |
| `QuotePreview` | `QuotePreview.tsx` | ChatInput 引用预览条 |
| `QuoteBlockRenderer` | `QuoteBlockRenderer.tsx` | QuoteBlock 渲染（附件栏样式） |
| `SubBranchInline` | `SubBranchInline.tsx` | 消息内联子支条目 |
| `QuoteContextCard` | `QuoteContextCard.tsx` | 子支内引用上下文卡片 |

### 8.2 修改组件

| 组件 | 修改内容 |
|------|----------|
| `MessageList.tsx` | 文本选择事件、引用高亮、SubBranchInline 嵌入 |
| `MessageBubble.tsx` | QuoteBlock 渲染（在 TextBlock 之前） |
| `ChatInput.tsx` | 双按钮模式、QuotePreview |
| `ConversationPanel.tsx` | SubBranchBanner 区域 |
| `conversation-store.ts` | SubBranchState + actions |

---

## 九、实现分期

### Phase 1：数据层 + API（后端）
1. QuoteBlock schema（ContentBlock 扩展）
2. SubBranchRef schema
3. Conversation 扩展字段
4. TreeNode 扩展字段
5. POST /sub-branch
6. GET /messages/{id}/sub-branches
7. GET /sub-branch/{id}/parent
8. POST /sub-branch/{id}/summarize
9. DELETE /sub-branch/{id}
10. tree_ops.py 子支操作

### Phase 2：文本选择 + 引用（前端）
1. MessageList 文本选择事件
2. 句子/段落/全文选择算法
3. TextSelectionToolbar
4. Store pendingQuote 状态
5. QuotePreview 组件

### Phase 3：QuoteBlock 渲染 + 发送（前后端）
1. QuoteBlockRenderer 组件
2. MessageBubble 集成 QuoteBlock
3. ChatInput 双按钮模式
4. 普通发送携带 QuoteBlock
5. createSubBranch action
6. 子支切换 + 消息发送

### Phase 4：子支展示 + 导航（前端）
1. SubBranchBanner
2. exitSubBranch + 滚动定位
3. SubBranchInline 消息内联
4. 引用原文高亮 + 点击跳转
5. QuoteContextCard

### Phase 5：递归 + 摘要（前后端）
1. 递归子支（depth 限制）
2. 子支摘要 LLM 生成
3. 摘要回写父消息
4. 父会话 system prompt 注入摘要
5. deleteSubBranch + 引用清理
