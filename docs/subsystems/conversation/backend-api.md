# 对话系统 API 文档

> 层级：**分区(Partition) → 领域(Domain) → 专题(Topic) → 对话(Conversation) → 消息(Message)**
>
> 集成多模态响应块 (ResponseBlock) 和后台任务 (Background Job)
>
> MVP 单用户模式，用户 ID 固定为 `"default_user"`

---

## 请求模型 (Request Models)

| 模型 | 字段 | 类型 | 说明 |
|------|------|------|------|
| `SendMessageRequest` | `text` | `str` | 消息文本 |
| | `content_blocks` | `list[dict]` | 内容块列表（可选） |
| | `partition_id` | `str \| None` | 目标分区 ID（可选，自动分类） |
| `CreatePartitionRequest` | `name` | `str` | 分区名称 |
| | `subject` | `str` | 学科（默认 `""`） |
| | `direction` | `str` | 方向（默认 `"subject"`） |
| | `emoji` | `str` | 表情符号（默认 `"💬"`） |
| `CreateDomainRequest` | `partition_id` | `str` | 所属分区 ID |
| | `name` | `str` | 领域名称 |
| | `emoji` | `str` | 表情符号（默认 `"📚"`） |
| `CreateTopicRequest` | `domain_id` | `str` | 所属领域 ID |
| | `name` | `str` | 专题名称 |
| | `emoji` | `str` | 表情符号（默认 `"📝"`） |
| `CreateConversationRequest` | `topic_id` | `str` | 所属专题 ID |
| | `name` | `str` | 对话名称（可选） |
| `RenameRequest` | `name` | `str` | 新名称 |
| `ModifyMessageRequest` | `content_blocks` | `list[dict]` | 新内容块列表 |
| | `text_summary` | `str` | 文本摘要（可选） |
| `EmotionTrendRequest` | `window_hours` | `int` | 时间窗口（小时，默认 `72`） |

---

## 一、分区 (Partition)

### `GET /partitions`
- **用途**: 列出所有分区
- **请求参数**: 无
- **返回值**: `{"partitions": [Partition, ...]}`
- **响应头**: `ETag` + `Cache-Control: private, max-age=5`
- **逻辑**: 加载用户数据，返回所有 partition 的 JSON 列表。支持 ETag 304 缓存协商。

### `POST /partitions`
- **用途**: 创建新分区
- **请求体**: `CreatePartitionRequest`
- **返回值**: `{"partition": Partition}`
- **逻辑**: 调用 `tree_ops.create_partition(...)`，内部同时创建虚拟根节点 + 默认领域 + 默认对话。

### `PATCH /partitions/{partition_id}`
- **用途**: 重命名分区
- **路径参数**: `partition_id: str`
- **请求体**: `RenameRequest`
- **返回值**: `{"partition": Partition (model_dump)}`
- **逻辑**: 调用 `tree_ops.rename_partition(...)`。分区不存在返回 404。

### `DELETE /partitions/{partition_id}`
- **用途**: 删除分区及其下属所有领域/专题/对话/消息
- **路径参数**: `partition_id: str`
- **返回值**: `{"ok": True}`
- **逻辑**: 调用 `tree_ops.delete_partition(...)`。分区不存在返回 404。

---

## 二、领域 (Domain)

### `GET /partitions/{partition_id}/domains`
- **用途**: 列出指定分区下的所有领域
- **路径参数**: `partition_id: str`
- **返回值**: `{"domains": [Domain, ...]}`
- **响应头**: `ETag` + `Cache-Control: private, max-age=5`
- **逻辑**: 从 `data.domains` 中筛选 `partition_id` 匹配的领域列表。

### `POST /domains`
- **用途**: 在指定分区下创建新领域
- **请求体**: `CreateDomainRequest`
- **返回值**: `{"domain": Domain}`
- **逻辑**: 调用 `tree_ops.create_domain(...)`。分区不存在返回 404。

### `PATCH /domains/{domain_id}`
- **用途**: 重命名领域
- **路径参数**: `domain_id: str`
- **请求体**: `RenameRequest`
- **返回值**: `{"domain": Domain}`
- **逻辑**: 调用 `tree_ops.rename_domain(...)`。领域不存在返回 404。

### `DELETE /domains/{domain_id}`
- **用途**: 删除领域及其下属所有专题/对话/消息
- **路径参数**: `domain_id: str`
- **返回值**: `{"ok": True}`
- **逻辑**: 调用 `tree_ops.delete_domain(...)`，归档所有下属 topic 和 conversation。领域不存在返回 404。

---

## 三、专题 (Topic)

### `GET /domains/{domain_id}/topics`
- **用途**: 列出指定领域下的所有专题
- **路径参数**: `domain_id: str`
- **返回值**: `{"topics": [Topic, ...]}`
- **响应头**: `ETag` + `Cache-Control: private, max-age=5`
- **逻辑**: 从 `data.topics` 中筛选 `domain_id` 匹配的专题列表。

### `POST /topics`
- **用途**: 在指定领域下创建新专题
- **请求体**: `CreateTopicRequest`
- **返回值**: `{"topic": Topic}`
- **逻辑**: 调用 `tree_ops.create_topic(...)`，同时自动创建首个默认对话。领域不存在返回 404。

### `PATCH /topics/{topic_id}`
- **用途**: 重命名专题
- **路径参数**: `topic_id: str`
- **请求体**: `RenameRequest`
- **返回值**: `{"topic": Topic}`
- **逻辑**: 调用 `tree_ops.rename_topic(...)`。专题不存在返回 404。

### `DELETE /topics/{topic_id}`
- **用途**: 删除专题及其下属所有对话和消息
- **路径参数**: `topic_id: str`
- **返回值**: `{"ok": True}`
- **逻辑**: 调用 `tree_ops.delete_topic(...)`，内部调用 `_archive_topic` 软删所有消息后从数据中移除专题。专题不存在返回 404。

---

## 四、对话 (Conversation)

### `GET /topics/{topic_id}/conversations`
- **用途**: 列出指定专题下的所有**未归档**对话
- **路径参数**: `topic_id: str`
- **返回值**: `{"conversations": [Conversation, ...]}`
- **响应头**: `ETag` + `Cache-Control: private, max-age=5`
- **逻辑**: 过滤 `conv.topic_id == topic_id and not conv.is_archived`。专题不存在返回 404。

### `POST /conversations`
- **用途**: 在专题下创建新对话
- **请求体**: `CreateConversationRequest`
- **返回值**: `{"conversation": Conversation}`
- **逻辑**: 调用 `tree_ops.create_conversation(...)`，停用旧活跃对话并设为新对话为活跃。专题不存在返回 404。

### `PATCH /conversations/{conv_id}`
- **用途**: 重命名对话
- **路径参数**: `conv_id: str`
- **请求体**: `RenameRequest`
- **返回值**: `{"conversation": Conversation}`
- **逻辑**: 调用 `tree_ops.rename_conversation(...)`。对话不存在返回 404。

### `DELETE /conversations/{conv_id}`
- **用途**: 删除对话（软删消息）
- **路径参数**: `conv_id: str`
- **返回值**: `{"ok": True}`
- **逻辑**: 调用 `tree_ops.delete_conversation(...)`，软删所有消息，从数据中移除对话记录。若为活跃对话则先取消活跃状态。对话不存在返回 400。

### `POST /conversations/{conv_id}/switch`
- **用途**: 切换专题的活跃对话
- **路径参数**: `conv_id: str`
- **查询参数**: `topic_id: str`
- **返回值**: `{"conversation": Conversation}`
- **逻辑**: 调用 `tree_ops.switch_conversation(...)`，将该专题下所有对话设为非活跃，仅目标对话设为活跃。专题或对话不存在返回 404。

---

## 五、消息 (Message)

### `GET /conversations/{conv_id}/messages`
- **用途**: 列出对话中的消息列表（分页，不含已删除消息）
- **路径参数**: `conv_id: str`
- **查询参数**: `limit: int = 50`，`offset: int = 0`
- **返回值**: `{"messages": [TreeNode, ...], "total": int}`
- **响应头**: `ETag` + `Cache-Control: private, max-age=3`
- **逻辑**: 按 `conv.path[offset:offset+limit]` 取消息，过滤 `is_deleted` 的消息。对话不存在返回 404。

### `GET /partitions/{partition_id}/messages`
- **用途**: 列出分区活跃对话的消息（含 response_blocks）
- **路径参数**: `partition_id: str`
- **查询参数**: `limit: int = 50`，`offset: int = 0`
- **返回值**: `{"messages": [TreeNode, ...], "total": int, "response_blocks": [ResponseBlock, ...]}`
- **响应头**: `ETag` + `Cache-Control: private, max-age=3`
- **逻辑**: 遍历该分区下的 topics → domains 找到活跃对话，返回其消息及该分区所有 response_blocks。分区不存在返回 404。

### `POST /message`
- **用途**: 发送消息（自动分类路由 + LLM 回复）
- **请求体**: `SendMessageRequest`
- **返回值**:
  ```json
  {
    "user_message": TreeNode,
    "assistant_message": TreeNode,
    "partition_id": str,
    "conversation_id": str,
    "response_blocks": [dict, ...],
    "switch_recommendation": dict | null
  }
  ```
- **逻辑**:
  1. 使用 `classifier.auto_resolve()` 对用户文本进行自动分类和路由，确定目标分区
  2. 调用 `send_and_reply()` 发送消息并获取 LLM 回复
  3. 返回用户消息、助手回复、分区/对话 ID、响应块和切换推荐

### `PUT /messages/{message_id}`
- **用途**: 编辑消息（在当前对话内创建新版本，不另开对话）
- **路径参数**: `message_id: str`
- **请求体**: `ModifyMessageRequest`
- **返回值**: `{"node": TreeNode, "version_count": int}`
- **逻辑**: 调用 `tree_ops.modify_message(...)`，标记原消息 `has_modified_version`，创建新版本节点，用新版本替换 `conv.path` 中的位置。返回版本计数供前端使用。

### `DELETE /messages/{message_id}`
- **用途**: 软删除消息及其子树
- **路径参数**: `message_id: str`
- **返回值**: `{"ok": True}`
- **逻辑**: 调用 `tree_ops.delete_message(...)`，递归软删子树，重构父节点的 children_ids（提升子节点），从 conv.path 中移除。

### `GET /messages/{message_id}`
- **用途**: 获取单条消息（用于版本切换）
- **路径参数**: `message_id: str`
- **返回值**: `{"message": TreeNode, "versions": [str, ...], "version_count": int}`
- **逻辑**: 从 data.nodes 获取消息节点，从父节点 children_ids 中筛选同角色的版本 ID 列表。消息不存在返回 404。

---

## 六、ResponseBlock

### `GET /messages/{message_id}/blocks`
- **用途**: 获取消息关联的所有响应块
- **路径参数**: `message_id: str`
- **返回值**: `{"blocks": [ResponseBlock, ...]}`
- **逻辑**: 从 `data.response_blocks` 中筛选 `block.message_id == message_id` 的所有块。

### `GET /response-blocks/{block_id}`
- **用途**: 获取单个响应块
- **路径参数**: `block_id: str`
- **返回值**: `{"block": ResponseBlock}`
- **逻辑**: 直接从 `data.response_blocks` 取对应 block。未找到返回 404。

---

## 七、情绪 (Emotion)

### `GET /emotion/trend`
- **用途**: 获取用户情绪趋势分析
- **查询参数**: `window_hours: int = 72`
- **返回值**: `EmotionTrend.to_dict()`
- **逻辑**: 调用 `emotion_analyzer.analyze_trend(USER_ID, window_hours)` 返回情绪趋势分析结果。

---

## 八、后台任务 (Background Job)

### `GET /jobs/{job_id}`
- **用途**: 查询后台任务状态
- **路径参数**: `job_id: str`
- **返回值**: `{"job": Job}`
- **逻辑**: 调用 `job_manager.get_job(USER_ID, job_id)`。未找到返回 404。

### `POST /jobs/{job_id}/cancel`
- **用途**: 取消后台任务
- **路径参数**: `job_id: str`
- **返回值**: `{"ok": True, "job_id": str}`
- **逻辑**: 调用 `job_manager.cancel(USER_ID, job_id)`。取消失败（未找到或已完成）返回 404。

### `GET /jobs/{job_id}/block`
- **用途**: 获取任务关联的响应块
- **路径参数**: `job_id: str`
- **返回值**: `{"job": Job, "block": ResponseBlock}`
- **逻辑**: 获取任务对象后，根据 `job.block_id` 从 `data.response_blocks` 取对应块。任务或块未找到返回 404。

---

## 九、资料 (Materials)

### `GET /conversations/{conv_id}/materials`
- **用途**: 列出对话关联的学习资料
- **路径参数**: `conv_id: str`
- **返回值**: `{"materials": [Material, ...]}`
- **逻辑**: 根据 `conv.material_refs` 中的 ID 列表，通过 `materials_meta.get()` 获取材料元数据。对话不存在返回 404。

---

## 十、练习建议 (Practice Suggestions)

### `GET /conversations/{conv_id}/practice-suggestions`
- **用途**: 获取基于对话上下文的练习建议
- **路径参数**: `conv_id: str`
- **返回值**: `{"suggestions": [Suggestion, ...]}`
- **逻辑**: 取最近 10 条非删除消息，调用 `practice_integrator.get_suggestions(USER_ID, topic_id, messages)`。对话不存在返回 404。

---

## 十一、工作空间 (Workspace)

> 文件存储路径: `~/.companion/uploads/{user_id}/{conv_id}/{type}/`

| 类型 | 目录名 |
|------|--------|
| image | `images/` |
| audio | `audio/` |
| video | `video/` |
| document | `documents/` |

### `POST /workspace/upload`
- **用途**: 上传文件到对话工作空间
- **请求体**: `multipart/form-data`
  - `file: UploadFile` — 上传的文件
  - `conversation_id: str` — 目标对话 ID
- **返回值**: `{"file_id": str, "original_name": str, "file_type": str}`
- **逻辑**:
  1. 验证对话存在
  2. 根据 MIME 类型分类（image/audio/video/document）
  3. 生成唯一文件名 `{uuid}{ext}`，写入对应类型目录
  4. 创建 `FileRecord` 存入 `data.files`
  5. 保存数据

### `GET /workspace/files`
- **用途**: 列出工作空间中的文件
- **查询参数**: `conversation_id: str`
- **返回值**: `{"files": [{"name", "relative_path", "size", "modified"}, ...]}`
- **逻辑**: 递归扫描工作空间目录，返回所有文件元信息。对话不存在返回 404。

### `DELETE /workspace/files/{file_id}`
- **用途**: 删除工作空间中的文件
- **路径参数**: `file_id: str`
- **查询参数**: `conversation_id: str`
- **返回值**: `{"ok": True}`
- **逻辑**: 删除磁盘文件并从 `data.files` 中移除记录。文件不存在返回 404。

### `GET /workspace/download/{file_id}`
- **用途**: 下载工作空间中的文件
- **路径参数**: `file_id: str`
- **返回值**: `FileResponse`（流式文件下载）
- **逻辑**: 从 `data.files` 获取记录，用 `FileResponse` 返回文件内容。文件或磁盘文件不存在返回 404。

---

## 十二、WebSocket

### `WS /ws`
- **用途**: WebSocket 流式对话端点，支持逐 token 流式输出和上下文切换事件
- **协议**: JSON 文本帧（text frames）
- **客户端发送格式**:
  ```json
  {
    "text": "用户消息",
    "partition_id": "可选分区ID",
    "conversation_id": "可选对话ID",
    "request_id": "可选请求ID，用于追踪"
  }
  ```
- **服务端事件类型**:
  | 事件类型 | 说明 |
  |----------|------|
  | `status` | 状态通知（如 "正在思考..."） |
  | `token` | 逐 token 流式输出（`key`: `content`） |
  | `context_switch` | 上下文切换推荐（含 `partition_id`, `conversation_id`） |
  | `error` | 错误消息 |
- **逻辑**:
  1. 接受 WebSocket 连接
  2. 循环接收客户端 JSON 文本帧
  3. 调用 `send_and_reply_stream()` 进行流式 LLM 对话
  4. 将每个事件（含 `request_id`）转发给客户端
  5. 处理 `context_switch` 事件——更新 `partition_id`
  6. 流完成后异步发布 `AssistantReplied` 事件到 event bus

---

# TreeOpsService 服务方法文档

**文件**: `app/services/tree_ops.py`

**单例**: `tree_ops = TreeOpsService()`

---

## 分区方法

### `create_partition(user_id: str, name: str, subject: str = "", direction: str = "subject", emoji: str = "💬") -> Partition`
- **用途**: 创建新分区
- **数据修改**:
  - 创建虚拟根节点 `TreeNode`（`role="assistant"`, `text_summary="[virtual_root]"`）
  - 创建 `Partition` 对象
  - 创建默认 `Domain`（name 和 emoji 同分区）
  - 设置 `data.active_partition_id`
  - 保存到 `data.nodes`, `data.partitions`, `data.domains`

### `rename_partition(user_id: str, partition_id: str, name: str) -> Partition`
- **用途**: 重命名分区
- **数据修改**: 更新 `partition.name` 和 `partition.updated_at`
- **错误**: 分区不存在 → `ValueError`

### `delete_partition(user_id: str, partition_id: str) -> None`
- **用途**: 删除分区及其所有下属领域/专题/对话/消息
- **数据修改**:
  - 遍历所有下属领域 → 专题 → 调用 `_archive_topic` 软删消息
  - 从 `data.topics`, `data.domains`, `data.partitions` 移除
- **错误**: 分区不存在 → `ValueError`

### `get_partition_context(user_id: str, partition_id: str) -> dict`
- **用途**: 获取分区完整上下文（分区、活跃对话、消息列表、摘要）
- **返回值**: `{"partition", "conversation", "messages": [TreeNode], "context_summary"}`
- **错误**: 分区不存在 → `ValueError`

---

## 领域方法

### `create_domain(user_id: str, partition_id: str, name: str, emoji: str = "📚") -> Domain`
- **用途**: 在指定分区下创建新领域
- **数据修改**: 创建 `Domain`，存入 `data.domains`
- **错误**: 分区不存在 → `ValueError`

### `rename_domain(user_id: str, domain_id: str, name: str) -> Domain`
- **用途**: 重命名领域
- **数据修改**: 更新 `domain.name` 和 `domain.updated_at`
- **错误**: 领域不存在 → `ValueError`

### `delete_domain(user_id: str, domain_id: str) -> None`
- **用途**: 删除领域，同时归档所有下属专题和对话
- **数据修改**: 遍历下属 topic 调用 `_archive_topic`，从 `data.topics` 和 `data.domains` 移除
- **错误**: 领域不存在 → `ValueError`

---

## 专题方法

### `create_topic(user_id: str, domain_id: str, name: str, emoji: str = "📝") -> Topic`
- **用途**: 在指定领域下创建新专题，同时创建首个默认对话
- **数据修改**: 创建 `Topic` + `Conversation`（设为活跃对话），存入 `data.topics`, `data.conversations`
- **错误**: 领域不存在 → `ValueError`

### `rename_topic(user_id: str, topic_id: str, name: str) -> Topic`
- **用途**: 重命名专题
- **数据修改**: 更新 `topic.name` 和 `topic.updated_at`
- **错误**: 专题不存在 → `ValueError`

### `delete_topic(user_id: str, topic_id: str) -> None`
- **用途**: 删除专题，同时归档下属所有对话和消息
- **数据修改**: 调用 `_archive_topic` 软删消息并移除对话，从 `data.topics` 移除
- **错误**: 专题不存在 → `ValueError`

### `_archive_topic(data: UserData, topic_id: str) -> None` (私有)
- **用途**: 软删专题下所有对话和消息
- **数据修改**: 遍历下属对话，标记所有节点 `is_deleted=True`，从 `data.conversations` 移除对话

---

## 对话方法

### `create_conversation(user_id: str, topic_id: str, name: str = "") -> Conversation`
- **用途**: 用户在专题下手动创建新对话
- **数据修改**:
  - 停用旧活跃对话（`is_active = False`）
  - 创建新 `Conversation`（默认名称 "新对话"）
  - 设为专题的活跃对话
  - 存入 `data.conversations`
- **错误**: 专题不存在 → `ValueError`

### `switch_conversation(user_id: str, topic_id: str, conversation_id: str) -> Conversation`
- **用途**: 切换专题的活跃对话
- **数据修改**: 该专题下所有对话 `is_active = False`，目标对话 `is_active = True`，更新 `topic.active_conversation_id`
- **错误**: 专题或对话不存在 → `ValueError`

### `rename_conversation(user_id: str, conv_id: str, name: str) -> Conversation`
- **用途**: 重命名对话
- **数据修改**: 更新 `conv.name`
- **错误**: 对话不存在 → `ValueError`

### `delete_conversation(user_id: str, conv_id: str) -> None`
- **用途**: 删除对话（软删消息）
- **数据修改**:
  - 若为活跃对话，取消活跃状态，清除专题的 `active_conversation_id`
  - 遍历 `conv.path` 中所有节点标记 `is_deleted=True`
  - 从 `data.conversations` 移除
- **错误**: 对话不存在 → `ValueError`

---

## 消息方法

### `add_message(user_id: str, partition_id: str, role: str, content_blocks: list[ContentBlock], text_summary: str = "", conversation_id: str = "") -> TreeNode`
- **用途**: 向活跃对话添加消息
- **数据修改**:
  - 查找分区下活跃 topic → 活跃 conversation（或指定 conversation_id）
  - 创建 `TreeNode`，父节点为对话路径末尾（或分区根节点）
  - 父节点 children_ids 添加新节点 ID
  - 追加到 `conv.path`
  - 更新 `conv.last_message_at`, `partition.message_count`, `partition.updated_at`, `partition.last_active_at`
- **错误**: 分区不存在 / 无活跃对话 / 对话不存在 → `ValueError`

### `modify_message(user_id: str, message_id: str, new_content_blocks: list[ContentBlock], new_text_summary: str = "") -> TreeNode`
- **用途**: 编辑消息（v4 内联版本：在同父节点下创建新版本）
- **数据修改**:
  - 标记原消息 `has_modified_version = True`
  - 创建新 `TreeNode`（同父、同角色、同对话）
  - 添加到父节点 `children_ids`
  - 迁移原消息（或路径中同父同角色的上一版本）的子节点到新版本
  - 用新版本替换 `conv.path` 中的位置
  - 标记 `conv.summary_dirty = True`
- **错误**: 消息不存在 → `ValueError`

### `delete_message(user_id: str, message_id: str) -> None`
- **用途**: 软删除消息及其子树
- **数据修改**:
  - 递归标记子树中所有节点 `is_deleted = True`
  - 从父节点 `children_ids` 中移除，并将子节点提升到父节点
  - 从 `conv.path` 中移除已删除的消息
  - 标记 `conv.summary_dirty = True`

---

## 统计摘要

| 类别 | 端点数 |
|------|--------|
| 分区 (Partition) | 4 |
| 领域 (Domain) | 4 |
| 专题 (Topic) | 4 |
| 对话 (Conversation) | 5 |
| 消息 (Message) | 5 |
| ResponseBlock | 2 |
| 情绪 (Emotion) | 1 |
| 后台任务 (Job) | 3 |
| 资料 (Material) | 1 |
| 练习建议 (Practice) | 1 |
| 工作空间 (Workspace) | 4 |
| WebSocket | 1 |
| **总计** | **35** |

| TreeOpsService 方法 | 数量 |
|---------------------|------|
| 分区方法 | 4 |
| 领域方法 | 3 |
| 专题方法 | 4 (含1私有) |
| 对话方法 | 4 |
| 消息方法 | 3 |
| **总计** | **18** (含1私有) |
