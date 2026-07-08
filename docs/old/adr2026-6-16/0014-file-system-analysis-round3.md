# ADR 0014: 文件系统全景分析 (Round 3 起点)

> 生成日期: 2026-06-16 | 状态: Draft — 第三轮重构前置摸底
> Round 1 完成: ADR 0001-0006 (认证/数据隔离/WS代理/事件表/目录节点/Store简化)
> Round 2 完成: ADR 0008-0013 (架构全景/练习重构/工具扩展/体验链优化)
> Round 3 目标: 文件系统重构
> Step 1 讨论完成: 2026-06-16, 见 §9 决策记录

---

## 1. 文件系统存储全景

### 1.1 PostgreSQL 表 (3+1 核心表)

#### materials — 文件元数据主表
```sql
PK: material_id
Fields:
  user_id, file_name, file_type, file_size, storage_path
  purpose        -- 'session' | 'library'
  status         -- 'uploading' | 'indexed' | 'index_failed'
  chunk_count    -- 分块数
  level          -- 'partition' | 'folder' (层级归属)
  parent_id      -- 父文件夹/分区 ID
  is_folder      -- 是否为文件夹
  tags_json      -- JSONB 标签数组
  skills_covered_json -- LLM 提取的知识点标签
  summary        -- LLM 生成的内容摘要(200字)
  is_deleted     -- 软删除标记(回收站)
  deleted_at     -- 删除时间
  created_at, indexed_at
```
索引: idx_materials_user(user_id)

#### material_chunks — 文件内容分块 + 向量
```sql
PK: chunk_id
Fields:
  user_id, material_id, text(最长8000), chunk_type('text')
  chunk_index, source_file, heading_path
  embedding      -- DOUBLE PRECISION[] (384维向量)
  indexing_status -- 'indexed' | 'pending'
  created_at
```
索引: idx_chunks_material(material_id)
向量搜索: 手工 PostgreSQL 余弦距离 (unnest + 手动计算, 无 pgvector)
回退: to_tsvector/plainto_tsquery 全文搜索

#### material_toc — 目录树 (仅大文件 + library 构建)
```sql
PK: toc_id
Fields:
  material_id, parent_toc_id
  level          -- 标题层级 (1=H1, 2=H2...)
  heading        -- 标题文本
  chunk_start, chunk_end  -- 关联的分块范围
  created_at
```
索引: idx_toc_material(material_id), idx_toc_parent(parent_toc_id)

#### events 表 (相关)
仅文件系统 `_index_background` 完成时发布 `CognitiveUpdateEvent` 写入 events 表,
但文件系统本身不直接写 events。由 MaterialsStub.on_indexed() 通过 EventBus 触发。

### 1.2 磁盘文件存储

```
COMPANION_HOME/uploads/{user_id}/{material_id}{ext}
  COMPANION_HOME = env COMPANION_HOME | ~/.companion
  物理文件命名: {material_id}.{ext} (如 a1b2c3d4.pdf)

COMPANION_HOME/uploads/materials_meta.json  (旧版元数据, 遗留)
  结构: {material_id: {partition_id, file_name, file_type, ...}}
  作用: MaterialsMetaStore 提供 JSON 文件级元数据管理(与 materials 表部分重叠)
```

### 1.3 工作空间文件 (与文件系统分离的另一路径)

```
~/.companion/uploads/{user_id}/{conversation_id}/{type}/{file_id}{ext}
  type: images | audio | video | documents
  用途: 对话内临时文件上传(workspace), 走 FileRecord 存入 conversation_user_meta
  与 materials 表无关, 独立管理
```

### 1.4 Embedding 模型

```
模型: granite-embedding-97m (384维)
推理: OpenVINO CPU (本地, 无需网络)
路径: backend/app/models/granite-embedding-97m/
  - openvino_model.xml
  - tokenizer.json
加载: 延迟加载, 全局单例
失败: 返回 None, 调用方回退全文搜索
```

### 1.5 阈值常数

| 常数 | 值 | 位置 | 用途 |
|------|-----|------|------|
| MAX_FILE_SIZE | 50MB | upload.py | 单文件大小上限 |
| LARGE_FILE_PAGES | 15 | material_indexer.py | TOC 构建页数阈值 |
| LARGE_FILE_BYTES | 5MB | material_indexer.py | TOC 构建大小阈值 |
| HIT_THRESHOLD | 0.35 | material_search.py | RAG 注入余弦距离阈值 |
| EMBEDDING_DIM | 384 | material_search.py | 向量维度 |
| max_chunk_size | 1000 | material_toc_extractor.py | 单分块最大字符 |
| 临时文件清理 | 30天 | manage.py | session 文件过期 |
| 索引 chunk text | 8000 | material_indexer.py | 分块文本 DB 截断 |

---

## 2. 文件系统模块架构

### 2.1 API 路由层

```
api/system/files_routes/
  __init__.py     -- 聚合 upload/browse/manage 子路由, 暴露 recover_stuck_files
  upload.py       -- 上传 + 后台索引 + 重索引 + stuck 恢复
  browse.py       -- 列表/详情/下载/TOC/分块/搜索/标签/统计
  manage.py       -- 删除/更新/标签/回收站/文件夹/批量/清理/基于文件出题
```

#### upload.py - 13 个支持格式
```
ALLOWED_EXTENSIONS:
  .pdf, .docx, .pptx, .xlsx, .md, .txt, .html, .htm,
  .csv, .json, .xml,
  .jpg, .jpeg, .png, .gif, .bmp, .webp,
  .mp3, .wav, .m4a, .ogg,
  .zip

file_type() 映射:
  .pdf→pdf, .docx→docx, .pptx→pptx, .xlsx→xlsx
  .md/.txt→document
  .jpg/.jpeg/.png/.gif/.bmp/.webp→image
  .mp3/.wav/.m4a/.ogg→audio
  其他→other
```

#### browse.py - 暴露的 API
```
GET    /api/files                              -- 文件列表(分页/过滤/搜索)
GET    /api/files/tags                         -- 所有标签
GET    /api/files/trash                        -- 回收站列表
GET    /api/files/folders                      -- 文件夹列表
GET    /api/files/stats                        -- 文件统计
GET    /api/files/{material_id}                -- 文件详情
GET    /api/files/{material_id}/download       -- 下载文件
GET    /api/files/{material_id}/toc            -- 目录树
GET    /api/files/{material_id}/chunks         -- 分块列表
POST   /api/files/search                       -- 语义搜索(向量)
```

#### manage.py - 暴露的 API
```
DELETE /api/files/{material_id}                -- 硬删除
PATCH  /api/files/{material_id}                -- 更新元数据(level/parent_id/file_name)
PUT    /api/files/{material_id}/tags            -- 更新标签
POST   /api/files/{material_id}/trash          -- 软删除→回收站
POST   /api/files/{material_id}/restore        -- 从回收站恢复
DELETE /api/files/{material_id}/permanent      -- 永久删除
POST   /api/files/trash/empty                  -- 清空回收站
POST   /api/files/cleanup                      -- 清理过期临时文件(30天)
POST   /api/files/folder                       -- 创建文件夹
PATCH  /api/files/folder/{folder_id}           -- 更新文件夹
DELETE /api/files/folder/{folder_id}           -- 删除文件夹
POST   /api/files/generate-practice            -- 基于文件出题
POST   /api/files/batch                        -- 批量操作(delete/move/add_tags/remove_tags)
```

### 2.2 基础设施层 (infrastructure/media/)

#### MaterialParser 文件解析器
```
文件: material_parser.py
引擎: MarkItDown (Python 库)
职责: 统一解析入口, 所有格式→Markdown 文本
方法:
  parse(file_path, file_type) → str       -- 解析为 Markdown
  get_page_count(file_path) → int          -- PDF 页数(pymupdf)

支持格式: 同 ALLOWED_EXTENSIONS
实例: material_parser = MaterialParser()  (全局单例)
```

#### TOC 提取引擎
```
文件: material_toc_extractor.py
核心模型: TOCNode(level, heading, parent, children, chunk_start/end)
函数:
  extract_toc(markdown_text) → list[TOCNode]     -- 正则提取标题层次
  assign_chunk_ranges(toc_nodes, chunks) → [...]  -- heading 文本匹配→分块范围
  chunk_by_toc(text, toc_nodes) → list[dict]      -- 按标题分割分块
  _chunk_flat(text, max_size) → list[dict]         -- 平铺分块(无TOC)
  _split_large_chunk(text, heading, max_size) → [...] -- 大分块再分割

策略:
  大文件(library): TOC 树 + 按标题分块, breadcrumb heading_path
  小文件/非library: 按空行分段(平铺), max_chunk_size=1000
```

#### MaterialIndexer 索引流水线
```
文件: material_indexer.py

index_file(user_id, material_id, file_path, file_name, file_type, file_size, purpose)
  → {
      "material_id": str,
      "status": "indexed"|"parse_failed"|"no_content",
      "chunk_count": int,
      "toc_count": int
    }

流程:
  1. material_parser.parse() → Markdown
  2. 判定是否建 TOC: is_large && purpose=="library"
  3. 分块: chunk_by_toc() 或 _chunk_flat()
  4. 计算 embedding 并写入 material_chunks
  5. 写入 material_toc (如有)
  6. UPDATE materials SET status='indexed', chunk_count=N
  7. 回调 MaterialsStub.on_indexed() → LLM 提取 skills + summary

时间线: 异步(asyncio.ensure_future), 上传后立即返回"uploading"状态
```

#### MaterialSearch 语义搜索
```
文件: material_search.py

search(user_id, query, purpose?, material_ids?, top_k=10) → list[dict]
  [异步版]

search_sync(user_id, query, purpose?, top_k=5) → list[dict]
  [同步版, 供 context_builder 等非 async 上下文]

search_knowledge(user_id, query, top_k=5) → list[dict]
  [库文件专用, 固定 purpose='library']

should_inject_rag(results) → bool
  [条件: 有结果 && 最佳score < 0.35]

format_rag_context(results) → str
  [格式: "--- 资料：文件名\n文本" 拼接]

向量计算: PostgreSQL DOUBLE PRECISION[]
  余弦距离 = 1 - (dot(A,B) / (||A|| * ||B||))
  手工 unnest 数组, 无 pgvector

回退: to_tsvector('simple') @@ plainto_tsquery('simple')
```

#### media_search.py 媒体搜索
```
MediaSearchService — 多平台搜索链接生成
不调外部 API → AI 生成搜索词 + 返回搜索 URL
平台: B站/YouTube/知乎/百度文库/学习强国/知网/抖音/小红书/Bing/百度
```

#### materials_meta.py 遗留元数据
```
MaterialsMetaStore — JSON 文件级元数据
存储: COMPANION_HOME/uploads/materials_meta.json
与 materials 表功能重叠, 少量消费者(如 error_book.py 仍引用旧 material_meta 表)
```

### 2.3 服务桩层

```
services/common/materials_stub.py

MaterialsStub:
  upload(user_id, file_path) → dict              -- 桩, 返回 ok
  search(user_id, query, top_k) → list[dict]     -- 委托 material_search.search()
  generate_questions(user_id, material_id, count) → list[dict]  -- 基于分块+LLM出题
  on_indexed(event) → None                       -- 索引后处理:
    → 读前3个分块 → LLM 提取 skills + summary
    → UPDATE materials.skills_covered_json, summary
```

---

## 3. 外部模块依赖关系 (消费者)

### 3.1 对话系统 (conversation)

| 文件 | 消费方式 | 详细 |
|------|----------|------|
| `context_builder.py` | **RAG 资料注入** | `material_search.search_sync()` → `should_inject_rag()` → `format_rag_context()` → 拼入 system_prompt |
| `context_pipeline.py` | 间接 | TutorCapability Provider 通过工具提示间接引用 search_media |
| `conversation_routes.py` | **独立工作空间** | `POST /workspace/upload` → 独立 `~/.companion/uploads/{uid}/{conv_id}/` → FileRecord 存入 UserData.files, **不经过 materials 表** |

### 3.2 练习系统 (practice)

| 文件 | 消费方式 | 详细 |
|------|----------|------|
| `practice_question_gen.py` | **出题材料** | `get_material_context()`: `SELECT text FROM material_chunks WHERE material_id IN (...)` |
| `practice_question_bank.py` | **关联资料** | `SELECT DISTINCT m.material_id, file_name FROM materials JOIN material_chunks` |
| `practice_integrator.py` | **错题资料引用** | `material_search.search_by_skill()` (该方法在 search.py 中不存在! 实际调用了不存在的接口) |
| `practice_error_book.py` | **推荐复习资料** | `get_error_materials()`: 查询旧 `material_meta` 表(可能不存在) + `learning_memory` |
| `manage.py` generate-practice | **基于文件出题** | `SELECT text FROM material_chunks WHERE material_id IN (...)` → LLM 生成题目 |

### 3.3 LLM 工具系统

| 工具名 | 消费方式 | 详细 |
|--------|----------|------|
| `search_media` | 平台搜索(不调文件系统) | `MediaSearchService` → AI 生成关键词 → 返回搜索链接 |
| `generate_practice` | 可引用文件分块 | 工具参数含 subject/knowledge_point, 实际文件内容从 manage.py API 获取 |
| `secretary_diagnose` | 不直接引用 | 间接使用 knowledge 模块获取认知状态 |

---

## 4. 运行时流程

### 4.1 上传索引流程

```
1. POST /api/files/upload
   → 验证: ext in ALLOWED_EXTENSIONS, size ≤ 50MB
   → 读 content = await file.read()  (全量内存!)
   → 生成 material_id = uuid4()
   → 判 purpose: auto→_classify_purpose (≥5MB→library, files_page→library, else→session)
   → 保存: COMPANION_HOME/uploads/{uid}/{material_id}{ext}
   → INSERT materials(status='uploading', chunk_count=0)
   → asyncio.ensure_future(_index_background(...))
   → 返回 {"status": "uploading"}

2. _index_background (异步)
   ├── material_parser.parse(file_path, file_type) → Markdown
   ├── is_large? (≥5MB 或 ≥15pages)
   ├── build_toc = is_large && purpose=='library'
   ├── 分块:
   │   ├── TOC路径: extract_toc() → chunk_by_toc() → assign_chunk_ranges()
   │   └── 平铺路径: _chunk_flat(max_size=1000)
   ├── 逐块:
   │   ├── 拼接 heading_path + text[:2000] → compute_embedding() → 384dim vector
   │   ├── text[:8000] 截断
   │   └── INSERT INTO material_chunks (embedding = DOUBLE PRECISION[])
   ├── INSERT INTO material_toc (如有)
   ├── UPDATE materials SET status='indexed', chunk_count=N
   └── 回调: MaterialsStub.on_indexed()
       → LLM 分析前3块 → 提取 skills(3-8个) + summary(≤100字)
       → UPDATE materials.skills_covered_json, summary

3. 失败处理
   → MarkItDown 返回空 → status='index_failed'
   → chunks 为空 → return no_content (不更新 status?)
   → LLM 后处理失败 → log warning, 不影响 status='indexed'
   → _index_background 异常 → status='index_failed'
```

### 4.2 语义搜索流程

```
POST /api/files/search {query, purpose?, material_ids?, top_k=10}
  → compute_embedding(query[:2000])
  → success:
      WITH qvec AS (SELECT %s::double precision[] AS v)
      SELECT mc.text, mc.chunk_index, mc.material_id,
             m.file_name as material_name,
             1.0 - (...) AS score
      FROM material_chunks mc JOIN materials m ...
      WHERE mc.user_id=%s AND mc.embedding IS NOT NULL
            AND array_length(mc.embedding,1)=384
            AND m.status='indexed'
            [AND m.purpose=%s] [AND mc.material_id=ANY(%s)]
      ORDER BY score ASC LIMIT %s
  → fail: 回退全文搜索 to_tsvector @@ plainto_tsquery
```

### 4.3 启动恢复流程

```
recover_stuck_files() (由 app 启动时调用)
  → SELECT * FROM materials WHERE status='uploading'
  → 逐个: 文件存在→asyncio.ensure_future(_index_background(...))
  → 文件丢失→UPDATE status='index_failed'
```

---

## 5. 已识别问题 (Round 3 重构信号)

### 5.1 数据层

1. **双重元数据**: materials 表 (main) + materials_meta.json (legacy) — 数据重叠, materials_meta.json 可能过时
2. **无 pgvector**: 手工 cosine 相似度 (unnest + 数组运算) — 性能瓶颈, 大数据集时慢
3. **embedding 列 NULLABLE**: 大量 chunk 可能 embedding IS NULL, 搜索时 skipped
4. **text 截断**: material_chunks.text 最长 8000 chars, 大块可能丢失
5. **chunk 重复索引**: reindex 时 DELETE + INSERT, 但无事务包裹

### 5.2 架构层

6. **工作空间分离**: conversation_routes.py 的 workspace 文件系统独立于 materials 体系 — FileRecord vs materials 表, 使用两套存储, 互相不可见
7. **MaterialsStub 名存实亡**: 几乎所有逻辑直接委托给 material_search/material_indexer, stub 层多余
8. **upload.py import 模式**: 每个函数内 import get_db 而非模块顶部 — 循环引用?
9. **index_event_bus 模块级**: 上传文件 create EventBus — 应该共享主 EventBus

### 5.3 API 层

10. **全量内存读取**: upload_file  await file.read()  — 50MB 上限, 但仍占内存
11. **无流式上传**: 不支持大文件分片
12. **无预览 API**: 图片/音频/视频 inline preview 缺失
13. **chunk text 返回截断**: browse.py 返回 chunk text[:1000], 前端看不到完整内容
14. **文件类型少**: 无 .mp4/.avi/.mov 视频, 无 .py/.js/.ts 代码

### 5.4 消费者问题

15. **practice_integrator.py 调不存在方法**: `material_search.search_by_skill()` — 该方法不存在, 应调 search() 或 search_sync()
16. **practice_error_book.py 引用过期表**: 查 `material_meta` 和 `learning_memory` 表 — 可能已不存在
17. **context_builder.py RAG 注入未分 conversation**: 全局搜索, 无 conversation/partition 限定

### 5.5 其他

18. **TOC parent_id 验证**: material_indexer.py `{f"toc_{material_id}_{t.level}_{_safe_heading(t.heading)}" for t in toc_nodes[:len([x for x in toc_nodes if x.level < tn.level])]}` — fragil, 可能漏 match
19. **index_event_bus.create**: 每个 upload 文件重新 create EventBus, 应复用系统 EventBus
20. **无文件版本/history**: overwrite 行为 undefined

---

## 6. 暴露给其他模块的工具/接口

### 6.1 HTTP API (所有模块共用)
参见 2.1 节,  ~20 个 endpoint

### 6.2  Python 导入级接口

| 模块 | 导入 | 调用 |
|------|------|------|
| conversation/context_builder | `material_search` | `search_sync()` `should_inject_rag()` `format_rag_context()` |
| practice/practice_question_gen | `material_chunks` 表 | `SELECT ... WHERE material_id IN (...)` |
| practice/practice_question_bank | `materials` + `material_chunks` 表 | `SELECT DISTINCT ... JOIN material_chunks` |
| practice/manage.py | `material_chunks` 表 | `SELECT text ... LIMIT 30` (出题) |
| common/materials_stub | `material_search` | `search()` |
| common/materials_stub | `material_chunks` 表 | `SELECT text ... LIMIT 5` (LLM出题) |
| common/materials_stub | `material_chunks` 表 | `SELECT text ... LIMIT 3` (on_indexed) |

### 6.3 启动暴露

| 函数 | 位置 | 调用者 |
|------|------|--------|
| `recover_stuck_files()` | `files_routes/__init__.py` | app 启动模块 |

---

## 7. 技术栈汇总

| 技术 | 用途 | 备注 |
|------|------|------|
| MarkItDown (Python) | 文件→Markdown 解析 | 支持 20+ 格式 |
| OpenVINO (CPU) | Embedding 推理 | granite-embedding-97m, 384-dim |
| PostgreSQL DOUBLE PRECISION[] | 向量列 | 无 pgvector |
| psycopg2 ThreadedConnectionPool | DB 连接 | min=2, max=10 |
| Alembic (fallback: raw SQL) | 迁移 | phase8_schema.sql |
| FastAPI FileResponse | 文件下载 | |
| Python pathlib/uuid/asyncio | OS 级 | ensure_future 做后台 |

---

## 8. 文件组织

```
backend/
  app/api/system/files_routes/
    __init__.py     [16L] 聚合路由 + recover_stuck_files
    upload.py       [249L] 上传 + 索引 + stuck
    browse.py       [430L] 浏览/搜索/下载/TOC
    manage.py       [460L] 管理 CRUD + 文件夹 + 批量 + 练习

  app/infrastructure/media/
    material_parser.py         [92L]  MarkItDown 封装
    material_toc_extractor.py  [259L] TOC 提取引擎
    material_indexer.py        [172L] 索引流水线
    material_search.py         [276L] 向量 + 全文搜索
    material_common.py         [31L]  公共(embedding re-export)
    materials_meta.py          [169L] 遗留 JSON 元数据
    media_search.py            [231L] 多平台搜索(无关)
    __init__.py                [0L]   empty

  app/services/common/
    materials_stub.py          [122L] 服务桩 + post-index handlers
    storage.py                 [14L]  对话存储(无关)
    pg_storage.py              [302L] PG 对话存储(无关)

  app/infrastructure/
    embedding_utils.py         [98L]  OpenVINO embedding
    db/database.py             [467L] DB 连接池 + SCHEMA_SQL 含 materials 建表
    db/learning_schema.sql     [87L]  material_toc 建表(learning_schema)

  app/config.py               COMPANION_HOME 定义

docs/archive/2026-phases/subsystems/file-management/README.md  [320L 设计文档]
docs/archive/2026-phases/phases/02-full-supplement/material-system-design.md  [252L 物料系统设计]
docs/archive/2026-phases/phases/03-capability-upgrade/material-graph-link.md  [163L P5 资料→分区→分支引用]
docs/archive/2026-phases/plans/v7-practice-revamp/02-ai-and-material.md  [808L AI+物料]

---

## 9. Step 1 决策记录 (2026-06-16 讨论确认)

| 决策 | 结论 | 影响范围 |
|------|------|----------|
| D1. 预留列清理 | material_chunks 的 image_urls_json, skill_ids_json, bloom_level, difficulty_estimate, page_number + materials.question_count — 全部清理 | schema, 代码 |
| D2. JSON 遗留废弃 | materials_meta.json 完全废弃, ensure_indexed() 移除 | materials_meta.py, main.py |
| D3. A/B 职责分离 | PG(materials表)管元数据+索引+搜索, 磁盘管原始文件 | storage_path 留在 PG |
| D4. workspace 废弃 | 对话文件上传走 /api/files/upload → materials 统一管理, 删除 conversation_routes.py workspace 路由 | conversation_routes.py, 前端对话页 |
| D5. 路由拆分 | 按数据流向拆分: ingest/ query/ mutate/ serve/ derive/ | files_routes/ 目录重构 |
| D6. infra 分层 | infrastructure/files/{parser, chunker, indexer, embedding, search, storage}, 废弃 materials_stub.py + material_common.py | infrastructure/media/ → files/ |
| D7. 后处理修复 | 内联到 indexer (方案 A): index_file 完成直接 LLM 提取 skills+summary, 删 upload.py import | material_indexer.py, upload.py |
| D8. 索引事务 | 事务包裹 + 重试3次 → 失败标记 index_failed | material_indexer.py |
| D9. pgvector 引入 | 新建 embedding_vec vector(384) 列, HNSW 索引(m=16, ef_construction=200), 旧 embedding 数据舍弃 | material_chunks schema, material_search.py SQL |
| D10. 后处理内联 | index_file 成功后直接读前3 chunk → LLM → UPDATE skills_covered_json + summary | material_indexer.py |