# Round 3 待决议题合集 (Steps 2-5)

> 生成日期: 2026-06-16 | 状态: **已定 — 全部 Accepted**
> Step 1 决策已记录于 ADR 0014 §9
> 以下议题按 Step 分组, 每条含背景 + 选项 + 推荐
> 审议结果: 2026-06-16 全部接受推荐方案

---

## Step 2: 底层数据结构 + 技术实现

### S2-Q1: TOC ID 生成冲突
**背景**: 当前 `toc_id = f"toc_{material_id}_{level}_{_safe_heading(heading)}"`, `_safe_heading` 取前30字符替换空格→下划线。两标题前30字符相同时 ID 冲突。

**推荐 A**: 用 UUID 作为 toc_id → 彻底去冲突, 但失去语义可读性
**B**: `_safe_heading` 取更长前缀(如100字符)
**C**: `hash(f"{material_id}_{level}_{heading}")` → 语义+唯一 → **▸ 已定(C)**

### S2-Q2: chunk text 8000 字符截断
**背景**: `material_chunks.text` 定义 TEXT, 但 indexer 写入时截断 `ch[:8000]`, 大 chunk 丢失尾部内容。

**推荐 方案 A**: 改列类型为 TEXT, 去掉代码中 `[:8000]` 截断, 信任 DB 存储 → **▸ 已定(A)**
**B**: 保持 8000, 超出部分拆成多个 chunk, 用 `chunk_index` 链接
**C**: 改 `text` 列不限长, 同时加 `text_truncated` 列标记是否截断

### S2-Q3: search_sync vs search 行为不一致
**背景**: `search_sync()` (供 context_builder RAG) 回退返回 `[]`; 而 `search()` (供 API) 回退做全文搜索。结果: embedding 失败时 RAG 完全缺失。

**推荐 方案 A**: `search_sync()` 用同一套回退逻辑 (全文搜索), 消除差异
**B**: `search_sync()` 调 `search()` 而不是重复实现 → **▸ 已定(B)**

### S2-Q4: search_sync 不返回 heading_path
**背景**: DB 行有 `heading_path` 列, search() 返回时硬编码 `"heading_path": ""`, search_sync 同理 → RAG 上下文 `format_rag_context()` 中 `[heading_path]` 始终空白。

**推荐 方案 A**: search_sync SQL 增加 `mc.heading_path` 返回 → **▸ 已定(A)**
**B**: 仅 `format_rag_context()` 查 DB 补 heading_path

### S2-Q5: MarkItDown 代码块中 `#` 误识别为标题
**背景**: `extract_toc()` 用正则 `r"^(#{1,6})\s+(.+)$"` 匹配标题。代码块中 `#` 开头行也被匹配, 导致 chunk 切割在代码块中间。

**推荐 方案 A**: 解析前用 fence 检测跳过代码块区域 (跟踪 ``` 开/关) → **▸ 已定(A)**
**B**: 解析后过滤无效标题 (用已识别 TOC 的 heading 做白名单)

---

## Step 3: 外部工具 + 内容索引

### S3-Q1: 文件格式扩展
**背景**: 不支持视频(.mp4 .avi .mov)和代码(.py .js .ts), MarkItDown 能解析但文件类型映射缺失。

**推荐 方案 A**: 添加视频扩展名(ALLOWED_EXTENSIONS + file_type), MarkItDown parse 会返回空文本但至少文件能上传
**B**: 同时添加视频 + 代码文件(代码文件→document 类型, MarkItDown 按纯文本读) → **▸ 已定(B)**
**C**: 暂不扩展, 等明确需求

### S3-Q2: content-type 分页/搜索增强
**背景**: `/api/files/search` 仅语义搜索; 无全文搜索端点、无文件内搜索、无单 chunk 全文获取 API。

**推荐 方案 A**: 新增 3 个 API (文件内搜索、单 chunk 全文、相似分块) → **▸ 已定(A)**
**B**: 增强现有 `/search` 支持 `mode=fulltext|semantic` 参数

### S3-Q3: 批量 reindex 策略
**背景**: reindex 时 DELETE + INSERT 无事务包裹, 单个 chunk embedding 失败后其他 chunk 已写入。当前仅 recover_stuck_files 可恢复, 且仅恢复 status='uploading'。

**推荐 方案 A**: 重索引用事务包裹(失败回滚), 失败后 status='index_failed', 用户可手动点"重试"
**B**: 后台定时扫描 index_failed 自动重试
**C**: 两者都要 → **▸ 已定(C)**

---

## Step 4: 浏览体验

### S4-Q1: 前端现有数据不展示 (skills/summary/heading_path)
**背景**: 后端 `/api/files` 和 `/api/files/{id}` 已返回 skills/summary, `/api/files/{id}/chunks` 已返回 heading_path — 但前端均未渲染。

**推荐 方案 A**: 纯前端改动 — 在文件列表/详情页加技能标签、摘要行、分块面包屑 → **▸ 已定(A)**
**B**: 后端先归一化数据格式再前端渲染

### S4-Q2: 分块全文展开
**背景**: browse.py 返回 chunk.text[:1000], 分块卡片 line-clamp-4。

**推荐 方案 A**: 新增 `/api/files/{id}/chunks/{index}` 返回全文, 前端点击"展开"调用 → **▸ 已定(A)**
**B**: 修改 `/api/files/{id}/chunks` 加 `full_text=true` 参数

### S4-Q3: 文件预览增强
**背景**: 仅图片+PDF可预览。音频无播放器、Markdown 无渲染、其他只能下载。

**推荐 方案 A**: 分步增强 — 先加音频 `<audio>`, 再加 Markdown `react-markdown`, 最后视频支持 → **▸ 已定(A)**
**B**: 一次性实现统一 FilePreviewModal 组件, 接管所有类型

### S4-Q4: TOC 交互增强
**背景**: TOC 可展开但不能点击跳转到对应分块, 无当前阅读位置高亮。

**推荐 方案 A**: `scrollIntoView()` + 高亮当前 visible chunk 的 TOC 节点 → **▸ 已定(A)**
**B**: 点击 TOC 节点→调 chunks API 按 chunk_start/end 过滤→只渲染该节分块

---

## Step 5: 对话/练习系统支持

### S5-Q1: practice_integrator.py search_by_skill 修复
**背景**: `ms.search_by_skill(user_id, skill, top_k=2)` 方法不存在。详见 ADR 0015 §9.1 S2。

**推荐 方案 A**: 改为 `ms.search(user_id, query=skill, top_k=2)`, 用语义搜索代替 skill 名称匹配 → **▸ 已定(A)**
**B**: 新建 `search_by_skill()` 方法 — 调 skills_covered_json 做 JSONB 过滤

### S5-Q2: practice_error_book.py material_meta 修复
**背景**: `SELECT m.id, m.filename FROM material_meta m WHERE ...` — material_meta 表不存在。详见 ADR 0015 §9.1 S3。

**推荐 方案 A**: 改为 `SELECT material_id as id, file_name as filename FROM materials WHERE skills_covered_json @> ...` → **▸ 已定(A)**
**B**: 改为 `search()` 语义搜索

### S5-Q3: 出题关联记录
**背景**: practice_question_gen.py 出题后不记录 material_id ↔ question_id 关联, 无法追溯"此文件生成了哪些题"。

**推荐 方案 A**: 新建 `practice_material_questions` 关联表, 出题后写入 → **▸ 已定(A)**
**B**: 不建表, 在 question JSON 中嵌入 material_id 引用

### S5-Q4: RAG 注入限定当前 partition/node
**背景**: context_builder.py + context_pipeline.py 的 RAG 搜索全库, 不限定当前学习树节点。用户学"微积分"时可能搜到"历史"资料。

**推荐 方案 A**: search_sync 增加 `node_ids` 参数, JOIN cognitive_nodes 过滤 skills_covered_json → **▸ 已定(A)**
**B**: 用户上传文件时关联 partition, 搜索按 partition 过滤

### S5-Q5: RAG 回退策略统一
**背景**: 两处 RAG (context_builder 旧 / context_pipeline 新) 代码完全重复。search_sync 回退返回 [] 与 search() 回退做全文搜索不一致。

**推荐 方案 A**: 统一调用路径 — context_pipeline 的 TutorCapability 成为唯一 RAG Provider, context_builder 废弃 → **▸ 已定(A)**
**B**: search_sync 内部调 search() 消除实现差异

---

## 附录: 已定决策索引 (Step 1)

| 决策 | 结论 | 所在文档 |
|------|------|----------|
| D1. 预留列清理 | 清理 | ADR 0014 §9 |
| D2. JSON遗留废弃 | 废弃 | ADR 0014 §9 |
| D3. A/B职责分离 | 分开 | ADR 0014 §9 |
| D4. workspace废弃 | 统一materials | ADR 0014 §9 |
| D5. 路由拆分 | ingest/query/mutate/serve/derive | ADR 0014 §9 |
| D6. infra分层 | files/{parser,chunker,indexer,embedding,search,storage} | ADR 0014 §9 |
| D7. 后处理修复 | 内联到indexer | ADR 0014 §9 |
| D8. 索引事务 | 事务+重试3次 | ADR 0014 §9 |
| D9. pgvector | HNSW, 新建列, 旧数据舍弃 | ADR 0014 §9 |
| D10. 后处理内联 | index_file成功后直做 | ADR 0014 §9 |