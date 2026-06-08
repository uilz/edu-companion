# 数据规格：会话与消息

> 会话系统采用 `分区(Partition) → 领域(Domain) → 专题(Topic) → 对话(Conversation) → 消息(TreeNode)` 五级层级结构。
>
> 源码：[backend/app/schemas/conversation.py](../../backend/app/schemas/conversation.py)

---

## 层级结构

```
Partition（分区）
  └── Domain（领域）
        └── Topic（专题）
              └── Conversation（对话）
                    └── TreeNode（消息节点，树形结构）
                          ├── ContentBlock（内容块）
                          └── SubBranchRef（子支引用锚点）
```

## Partition 模型

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | UUID | 全局唯一 |
| `name` | str | 分区名称 |
| `subject` | str | 学科 |
| `direction` | str | 方向（默认 `"subject"`） |
| `emoji` | str | 图标 |
| `color` | str | 颜色（默认 `"#0066FF"`） |
| `root_id` | str | 虚拟根节点 ID |
| `context_summary` | str | 上下文摘要 |
| `tags` | list[str] | 标签 |
| `is_temp` | bool | 是否临时分区 |
| `domain_tags` | list[str] | 领域标签 |
| `domain_confidence` | float | 领域分类置信度 |

## Domain 模型

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | UUID | 全局唯一 |
| `partition_id` | str | 所属分区 ID |
| `name` | str | 领域名称 |
| `emoji` | str | 图标 |

## Topic 模型

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | UUID | 全局唯一 |
| `domain_id` | str | 所属领域 ID |
| `partition_id` | str | 所属分区 ID（跨级查找） |
| `name` | str | 专题名称 |
| `emoji` | str | 图标 |
| `active_conversation_id` | str | 当前活跃对话 ID |

## Conversation 模型

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | UUID | 全局唯一 |
| `parent_id` | str | 直接父级 ID |
| `parent_type` | str | partition / domain / topic |
| `type` | str | normal / tree_exploration / temporary |
| `partition_id` | str | 所属分区 ID |
| `domain_id` | str | 所属领域 ID |
| `topic_id` | str | 所属专题 ID（向下兼容） |
| `name` | str | 对话名称 |
| `path` | list[str] | 消息 ID 有序列表 |
| `is_active` | bool | 是否活跃 |
| `is_temporary` | bool | 临时会话标记 |
| `primary_node_id` | str\|null | 关联 CognitiveNode ID |
| `parent_conversation_id` | str | 父会话 ID（子支时非空） |
| `sub_branch_ids` | list[str] | 直接子支会话 ID 列表 |
| `depth` | int | 子支深度（0=顶层） |
| `metadata` | dict | 通用元数据 |

### 对话类型

| type | 场景 | 说明 |
|------|------|------|
| `normal` | 常规对话 | `/learn` 页面创建 |
| `tree_exploration` | 知识树探索 | 知识树节点触发，受作用域约束 |
| `temporary` | 临时对话 | 空状态自动创建，48h 清理 |

## TreeNode（消息节点）模型

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | UUID | 全局唯一 |
| `parent_id` | str | 父消息 ID（树形结构） |
| `children_ids` | list[str] | 子消息 ID（编辑时产生同级版本） |
| `partition_id` | str | 所属分区 |
| `conversation_id` | str | 所属对话 |
| `content_blocks` | list[ContentBlock] | 多模态内容块 |
| `text_summary` | str | 文本摘要 |
| `role` | str | user / assistant / system |
| `timestamp` | float | 时间戳 |
| `token_count` | int | Token 数 |
| `is_deleted` | bool | 是否删除 |
| `has_modified_version` | bool | 是否有编辑版本 |
| `discussed_skill_ids` | list[str] | 讨论的知识点 ID |
| `has_sub_branches` | bool | 是否有子支 |
| `sub_branch_ids` | list[str] | 子支会话 ID 列表 |
| `sub_branch_summaries` | list[dict] | 子支摘要列表 |
| `metadata` | dict | 元数据 |

## ContentBlock 类型

| type | 模型类 | 关键字段 |
|------|--------|----------|
| `text` | TextBlock | text |
| `image` | ImageBlock | file_id |
| `audio` | AudioBlock | file_id, duration_ms, transcription |
| `video` | VideoBlock | file_id, duration_ms, thumbnail_file_id, transcription |
| `document` | DocumentBlock | file_id, document_kind, page_count, text_content |
| `quote` | QuoteBlock | source_message_id, source_conversation_id, char_start, char_end, quoted_text |

## ResponseBlock（AI 响应块）

| 字段 | 类型 | 说明 |
|------|------|------|
| `type` | str | text / practice / video / image / audio / mindmap / document |
| `status` | str | pending / streaming / done / error |
| `content` | dict | 响应内容 |
| `order` | int | 排序 |
| `sources` | list[str] | 来源 |

## SubBranchRef（子支引用锚点）

| 字段 | 类型 | 说明 |
|------|------|------|
| `source_message_id` | str | 父会话中被引用的消息 ID |
| `char_start` / `char_end` | int | 选中文本偏移 |
| `quoted_text` | str | 引用原文 |
| `child_conversation_id` | str | 子支会话 ID |

### 子支核心规则

1. 子支引用通过 `QuoteBlock` 内容块实现
2. 子支摘要写回父消息 `sub_branch_summaries[]`
3. 父会话 LLM 自动感知子支讨论结果
4. 临时会话不支持创建子支
