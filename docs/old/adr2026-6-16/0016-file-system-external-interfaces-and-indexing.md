# ADR 0016: 文件系统对外接口 + 内容识别索引全景 (Round 3 Step 3)

> 生成日期: 2026-06-16 | 状态: Draft
> 前置: ADR 0014 (全景), ADR 0015 (深层分析)
> 目标: 完整梳理文件系统暴露给外部的所有接口、全量内容识别及索引链路

---

## 1. 对外接口全景

### 1.1 HTTP API 层 — files_routes (20+ endpoint)

| 端点 | 方法 | 文件 | 行 | 功能 |
|------|------|------|----|------|
| `/api/files/upload` | POST | upload.py | 83 | 上传文件 + 自动索引 |
| `/api/files/{material_id}/reindex` | POST | upload.py | 189 | 手动重索引 |
| `/api/files/search` | POST | browse.py | — | 语义搜索 |
| `/api/files` | GET | browse.py | — | 文件列表(分页/过滤) |
| `/api/files/tags` | GET | browse.py | — | 所有标签 |
| `/api/files/trash` | GET | browse.py | — | 回收站列表 |
| `/api/files/folders` | GET | browse.py | — | 文件夹列表 |
| `/api/files/stats` | GET | browse.py | — | 文件统计 |
| `/api/files/{material_id}` | GET | browse.py | — | 文件详情 |
| `/api/files/{material_id}/download` | GET | browse.py | — | 下载 |
| `/api/files/{material_id}/toc` | GET | browse.py | — | 目录树 |
| `/api/files/{material_id}/chunks` | GET | browse.py | — | 分块列表 |
| `/api/files/{material_id}` | DELETE | manage.py | — | 硬删除 |
| `/api/files/{material_id}` | PATCH | manage.py | — | 更新元数据 |
| `/api/files/{material_id}/tags` | PUT | manage.py | — | 更新标签 |
| `/api/files/{material_id}/trash` | POST | manage.py | — | 软删除→回收站 |
| `/api/files/{material_id}/restore` | POST | manage.py | — | 恢复 |
| `/api/files/{material_id}/permanent` | DELETE | manage.py | — | 永久删除 |
| `/api/files/trash/empty` | POST | manage.py | — | 清空回收站 |
| `/api/files/cleanup` | POST | manage.py | — | 清理临时文件 |
| `/api/files/folder` | POST | manage.py | — | 创建文件夹 |
| `/api/files/folder/{folder_id}` | PATCH | manage.py | — | 更新文件夹 |
| `/api/files/folder/{folder_id}` | DELETE | manage.py | — | 删除文件夹 |
| `/api/files/generate-practice` | POST | manage.py | — | 基于文件出题 |
| `/api/files/batch` | POST | manage.py | — | 批量操作 |

### 1.2 管理后台 API — data_routes.py (1 endpoint)

| 端点 | 方法 | 行 | 功能 |
|------|------|----|------|
| `GET /api/data/materials` | GET | data_routes.py:186 | 管理员查看材料列表(直查 materials 表) |

### 1.3 Python 导入级接口

#### 1.3.1 基础设施层 (infrastructure/media/)

| 类/模块 | 导入路径 | 暴露方法 | 消费者 |
|---------|----------|----------|--------|
| `material_search.MaterialSearch` | `app.infrastructure.media.material_search` | `search()` async, `search_sync()`, `search_knowledge()`, `should_inject_rag()`, `format_rag_context()` | context_builder, context_pipeline, materials_stub |
| `material_indexer.MaterialIndexer` | `app.infrastructure.media.material_indexer` | `index_file()` async | upload.py (_index_background) |
| `material_parser.MaterialParser` | `app.infrastructure.media.material_parser` | `parse()`, `get_page_count()` | material_indexer |
| `material_toc_extractor` | `app.infrastructure.media.material_toc_extractor` | `extract_toc()`, `chunk_by_toc()`, `assign_chunk_ranges()` | material_indexer |
| `media_search.MediaSearchService` | `app.infrastructure.media.media_search` | `search()`, `search_multi_platform()` | LLM tool dispatch (间接) |
| `embedding_utils` | `app.infrastructure.embedding_utils` | `compute_embedding()`, `cosine_similarity()` | material_common → material_indexer/search |
| `material_common` | `app.infrastructure.media.material_common` | `get_pool()` (asyncpg), `compute_embedding()` (re-export) | — |

#### 1.3.2 服务桩层 (services/common/)

| 类 | 导入路径 | 暴露方法 | 消费者 |
|----|----------|----------|--------|
| `MaterialsStub` | `app.services.common.materials_stub` | `upload()`, `search()` async, `generate_questions()`, `on_indexed()` | **当前无活跃消费者** (原 domain/materials/service.py 不存在) |

#### 1.3.3 启动钩子

| 函数 | 位置 | 调用者 | 作用 |
|------|------|--------|------|
| `recover_stuck_files()` | `files_routes/__init__.py` | `main.py` 启动时 | 恢复 status='uploading' 的文件 |
| `materials_meta.ensure_indexed()` | `infrastructure/media/materials_meta.py` | `main.py` 启动时 | 扫描 uploads 目录, 注册未登记文件到 materials_meta.json |

### 1.4 数据库级接口 (直接 SQL)

#### 1.4.1 消费者直接查询 material_chunks

| 模块 | 文件 | 行 | SQL |
|------|------|-----|-----|
| 出题 | `practice_question_gen.py` | 135-146 | `SELECT mc.text, mc.material_id, m.file_name FROM material_chunks mc JOIN materials m WHERE mc.material_id IN ({ids})` |
| 批量出题 | `practice_question_gen.py` | 387-389 | 同上, 调用 get_material_context |
| 文件出题 | `manage.py` | (POST /generate-practice) | `SELECT text FROM material_chunks WHERE material_id IN ({ids}) LIMIT 30` |
| 题库关联 | `practice_question_bank.py` | 252-258 | `SELECT DISTINCT m.material_id, m.file_name FROM materials m JOIN material_chunks mc` |
| 后处理 | `materials_stub.py` | 80-84 | `SELECT text FROM material_chunks WHERE material_id = %s ORDER BY chunk_index LIMIT 3` |
| 后处理 | `materials_stub.py` | 32-36 | `SELECT text FROM material_chunks WHERE material_id = %s LIMIT 5` |
| RAG 搜索 | `material_search.py` | 66-85 | 向量余弦搜索 |
| RAG 搜索 | `material_search.py` | 132-141 | 全文搜索回退 |

#### 1.4.2 消费者直接查询 materials

| 模块 | 文件 | 行 | SQL |
|------|------|-----|-----|
| 题库关联 | `practice_question_bank.py` | 252-258 | `SELECT DISTINCT m.material_id, m.file_name ... WHERE m.user_id = %s AND m.status = 'indexed'` |
| 文件列表 | `browse.py` | — | `SELECT * FROM materials WHERE user_id = %s ...` |
| 统计 | `browse.py` | — | `SELECT ... FROM materials GROUP BY ...` |

#### 1.4.3 崩坏的数据库引用

| 模块 | 文件 | 行 | SQL | 问题 |
|------|------|-----|-----|------|
| `practice_error_book.py` | error_book.py | 281-285 | `SELECT m.id, m.filename FROM material_meta m WHERE ...` | **`material_meta` 表不存在** |
| `practice_error_book.py` | error_book.py | 300-304 | `SELECT ... FROM learning_memory WHERE ...` | **`learning_memory` 表不存在** |

### 1.5 LLM 工具定义 (通过 tool_repository)

文件系统不直接暴露 LLM 工具, 但以下工具有间接引用:

| 工具名 | 描述 | 文件系统关联 |
|--------|------|-------------|
| `search_media` | 多平台搜索(B站/YouTube/知乎等) | **无关** — 仅生成搜索链接, 不查 materials |
| `generate_practice` | 基于知识点出题 | **间接** — 参数可传 material_ids, 通过 manage.py API 获取分块内容 |

---

## 2. 全量内容识别链

### 2.1 文件类型探测

```
上传 POST /api/files/upload
  → Path(file.filename).suffix.lower()  → 检查 ALLOWED_EXTENSIONS
  → file_type(ext)  → 返回类型字符串

ALLOWED_EXTENSIONS = 24种:
  .pdf .docx .pptx .xlsx              ← office 文档
  .md .txt .html .htm .csv .json .xml  ← 文本/标记
  .jpg .jpeg .png .gif .bmp .webp     ← 图片
  .mp3 .wav .m4a .ogg                  ← 音频
  .zip                                  ← 压缩包

file_type() 映射:
  .pdf        → "pdf"
  .docx       → "docx"
  .pptx       → "pptx"
  .xlsx       → "xlsx"
  .md/.txt    → "document"
  .jpg/...    → "image"
  .mp3/...    → "audio"
  其他        → "other"

不支持的类型:
  .mp4 .avi .mov .flv .mkv         ← 视频全部不支持
  .py .js .ts .java .cpp .go .rs   ← 代码文件全部不支持
  .epub .mobi                       ← 电子书
  .rtf .odt                         ← 其他文档
```

### 2.2 解析链路 (MarkItDown)

```
MaterialParser.parse(file_path, file_type) → markdown_text

内部:
  md = MarkItDown()                      ← markitdown 库
  result = md.convert(file_path)         ← 统一转换
  text = result.markdown                 ← Markdown 格式输出
  失败 → 返回空字符串

MarkItDown 实际支持:
  PDF        ← 文本提取(非OCR)
  DOCX       ← Word → Markdown
  PPTX       ← PowerPoint → Markdown
  XLSX       ← Excel 表格 → Markdown 表格
  MD/TXT     ← 直接读取
  HTML       ← HTML → Markdown
  CSV        ← 表格 → Markdown 表格
  JSON       ← JSON → 代码块
  XML        ← XML → 代码块
  图片(JPG/PNG等) ← 无OCR, 仅提取元数据, 返回空文本
  音频(MP3/WAV等) ← 无转写, 返回空文本
  ZIP         ← 解压后递归解析(仅扫描内部文件?
```

### 2.3 分块策略

#### 2.3.1 决策树

```
markdown_text → chunk_by_toc(text, toc_nodes)

                    ┌─ 大文件(>5MB或>15页) AND purpose='library'
                    │   → build_toc = TRUE
                    │   → extract_toc() → toc_nodes
                    │   → chunk_by_toc(text, toc_nodes)
                    │     → 按标题分割, breadcrumb heading_path
                    │     → 大chunk再分割(>1000字符)
                    │
                    └─ 小文件 OR purpose='session'
                        → build_toc = FALSE
                        → chunk_by_toc(text, [], max_chunk_size=1000)
                          → _chunk_flat(): 按空行段落, 累积到1000字符flush
```

#### 2.3.2 TOC 分块 (大文件)

```
正则: r"^(#{1,6})\s+(.+)$"

逐行扫描:
  遇到#标题 → 结束上一个chunk, 开始新chunk
  标题匹配TOC节点 → heading_path = breadcrumb(parent > ... > current)
  标题不匹配TOC → heading_path = 标题原文

分块粒度: 按标题切割, 每个标题=一个chunk
连锁分块: chunk.text > 1000 → _split_large_chunk()
  按段落(\n\n)再分割, 每段不超1000字符

heading_path 格式: "H1标题 > H2标题 > H3标题"
  → 存储到 DB heading_path 列
  → 嵌入 embedding 输入: f"{heading_path}\n{text}"[:2000]
  → **但搜索返回时 heading_path 硬编码为空字符串** (material_search.py:93/150/263)
```

#### 2.3.3 平铺分块 (小文件)

```
_chunk_flat(text, max_size=1000):
  paragraphs = text.split("\n\n")     ← 按空行分割
  每段累积, 超过max_size → flush
```

### 2.4 Embedding 计算

```
compute_embedding(text) → None | list[float] (384维)

模型: granite-embedding-97m
  引擎: OpenVINO CPU
  路径: backend/app/models/granite-embedding-97m/
  输入: tokenizer.encode(text), max_len=512 tokens
  输出: model([input_ids, attention_mask])[0, -1]
  维度: 384 float64

失败链:
  模型不存在 → return None  → chunk.embedding=NULL  → 搜索跳过
  text 空 → return None

性能: ~50-200ms/chunk (CPU)
```

### 2.5 索引写入

```
DELETE material_chunks WHERE material_id = %s   ← 删除旧索引
DELETE material_toc WHERE material_id = %s      ← (仅build_toc)

逐条 INSERT material_chunks:
  chunk_id = 'chk_{material_id}_{index}'
  text = ch['text'][:8000]           ← DB截断8000字符
  heading_path = breadcrumb_path
  embedding = compute_embedding(...) ← 可能为NULL

逐条 INSERT material_toc (仅build_toc):
  toc_id = 'toc_{material_id}_{level}_{heading[:30]}'
  parent_toc_id = toc_id of parent (验证存在)
  chunk_start/end = assign_chunk_ranges 结果

UPDATE materials SET chunk_count=N, status='indexed'
```

**原子性问题**: 全部操作无事务包裹. DELETE 后 INSERT 中途失败 → 数据丢失

### 2.6 后处理 (on_indexed)

```
意图: MaterialsStub.on_indexed()
  1. SELECT 前3 chunk text
  2. LLM 提取: skills (3-8个), summary (≤100字)
  3. UPDATE materials.skills_covered_json, summary

实际: **永远不执行**
  upload.py:163 → from domain.materials.service import MaterialServiceImpl
  → 模块不存在 → ImportError → log warning → 后处理跳过
```

---

## 3. 文件系统各类消费者全景

### 3.1 对话系统 (conversation)

| 消费者 | 位置 | 集成方式 | 数据流 | 状态 |
|--------|------|----------|--------|------|
| `context_builder.py` (旧) | L386-402 | `material_search.search_sync()` + `should_inject_rag()` + `format_rag_context()` | 用户问题→向量搜索→前3结果→RAG→system_prompt | ✅ 但 heading_path 恒空 |
| `context_pipeline.py` TutorCapability (新) | L617-631 | 同上, 新 Provider 架构 | 同上 | ✅ 同上问题 |
| `conversation_routes.py` workspace | L752-855 | 独立文件系统 `~/.companion/uploads/{uid}/{conv_id}/` | FileRecord 存入 UserData.files | ✅ 但与 materials 隔离 |
| `context_trigger.py` | L1-259 | 间接, 生成 [Media] 提示 | 不直接查文件系统 | ✅ |

### 3.2 练习系统 (practice)

| 消费者 | 位置 | 集成方式 | 数据流 | 状态 |
|--------|------|----------|--------|------|
| `practice_question_gen.py` | L117-157 | 直查 material_chunks 表 | material_ids → SQL → 拼接资料上下文 → LLM出题 | ✅ |
| `practice_question_bank.py` | L246-267 | 直查 materials + material_chunks | 按知识点匹配关联资料 | ✅ (结果用不到 node_ids 过滤) |
| `manage.py` (generate-practice) | manage.py | 直查 material_chunks | 文件出题 endpoint | ✅ |
| `practice_integrator.py` | L92-107 | **调不存在方法** `ms.search_by_skill()` | 练习后→按skill查资料→关联引用 | ❌ 运行时崩溃 |
| `practice_error_book.py` | L278-316 | **查不存在表** `material_meta` + `learning_memory` | 错题→推荐复习资料 | ❌ 运行时崩溃 |
| `materials_stub.py` | L28-69 | 直查 material_chunks + LLM | 出题/后处理 | ❌ 后处理永不执行 |

### 3.3 LLM 工具系统

| 消费者 | 位置 | 集成方式 | 状态 |
|--------|------|----------|------|
| `tool_repository.py` | 全局 | search_media 工具(不查文件系统) | ✅ 无关 |
| `tool_dispatch.py` | 工具派发 | 间接路由 | ✅ |

### 3.4 启动系统

| 消费者 | 位置 | 集成方式 | 状态 |
|--------|------|----------|------|
| `main.py` | L297-345 | `app.include_router(files_router)` | ✅ |
| `main.py` 启动 | post-start | `recover_stuck_files()` (恢复uploading文件) | ✅ |
| `main.py` 启动 | post-start | `materials_meta.ensure_indexed()` (JSON元数据扫描) | ⚠️ 重叠存储 |

---

## 4. 消费者调用模式的5种类型

### 类型A: HTTP API 调用 (前端 → 后端)
```
前端页面 → POST/GET /api/files/*
  最常用: 文件上传、列表、搜索、下载
```

### 类型B: Python 导入调用 (后端模块 → 后端模块)
```
context_builder.py:
  from app.infrastructure.media.material_search import material_search
  material_search.search_sync(...)

materials_stub.py:
  from app.infrastructure.media.material_search import material_search
  await material_search.search(...)
```

### 类型C: 直查 DB (无中间层)
```
practice_question_gen.py:
  from app.infrastructure.db.database import get_db
  db = get_db()
  db.fetchall("SELECT ... FROM material_chunks ...")

此模式绕过所有 services/infrastructure 层, 直接访问 DB
```

### 类型D: 磁盘文件读取
```
material_indexer.py:
  material_parser.parse(file_path)  → MarkItDown 读取磁盘文件

conversation_routes.py workspace:
  storage_path.write_bytes(content)
  → UserData.files 记录 FileRecord
```

### 类型E: 启动钩子
```
main.py startup:
  recover_stuck_files()      → 重新索引 stuck 文件
  materials_meta.ensure_indexed() → JSON 扫描
```

---

## 5. 内容索引全链示意

```
┌─ 上传 ─────────────────────────────────────┐
│ [用户] POST /api/files/upload              │
│  → ALLOWED_EXTENSIONS 校验 (24种扩展名)    │
│  → MAX_FILE_SIZE 校验 (50MB)               │
│  → file.read() (全量内存)                  │
│  → 磁盘: {COMPANION_HOME}/uploads/{uid}/   │
│  → INSERT materials(status=uploading)       │
│  → asyncio.ensure_future(_index_background) │
│  → return {status: "uploading"}             │
└─────────────────────────────────────────────┘
                                                   
┌─ 后台索引 (异步) ───────────────────────────┐
│ _index_background                            │
│                                               │
│ 1. MarkItDown.parse() → markdown_text        │
│    [PDF/DOCX/PPTX/XLSX/MD/TXT/HTML/CSV/...]  │
│    空文本 → status=index_failed              │
│                                               │
│ 2. 判定: build_toc?                          │
│    is_large = size>5MB OR pages>15           │
│    build_toc = is_large AND purpose=library  │
│                                               │
│ 3a. TOC路径:                                 │
│    extract_toc() → 正则解析 #标题层次        │
│    chunk_by_toc() → 按标题分割               │
│    assign_chunk_ranges() → chunk↔toc关联     │
│                                               │
│ 3b. 平铺路径:                                │
│    chunk_by_toc(text, []) → _chunk_flat()    │
│    按\n\n分段, 每段≤1000字符                 │
│                                               │
│ 4. 逐chunk:                                  │
│    embed_text = f"{heading}\n{text}"[:2000]  │
│    compute_embedding() → 384-dim             │
│    失败 → embedding=NULL                     │
│                                               │
│ 5. 写入 (无事务!):                           │
│    DELETE old chunks+toc                     │
│    INSERT chunks (含embedding)               │
│    INSERT toc nodes (if build)               │
│    UPDATE materials SET status='indexed'     │
│                                               │
│ 6. 后处理 [❌ 永远失败]:                    │
│    from domain.materials.service... ❌       │
└─────────────────────────────────────────────┘
                                                   
┌─ 搜索链路 ──────────────────────────────────┐
│ POST /api/files/search {query}               │
│  → compute_embedding(query[:2000])           │
│  → 成功: PostgreSQL 余弦距离                │
│    WITH qvec AS (...) SELECT ... ORDER BY     │
│    unnest(A,B) → sum(a*b) → cosine distance  │
│  → 失败: to_tsvector @@ plainto_tsquery      │
│  → 返回 results[{text, score, material_id}]  │
│                                               │
│ RAG注入链路:                                  │
│  context_builder.py:                          │
│    search_sync(query, top_k=3)               │
│    should_inject_rag(results) → score<0.35   │
│    format_rag_context(results)               │
│      → system_prompt 末尾追加                │
│      **heading_path 恒空, 丢失标题信息**     │
└─────────────────────────────────────────────┘
```

---

## 6. 问题重排 (基于消费者视角)

### 6.1 关键断裂点 (影响用户功能)

| 优先级 | 问题 | 影响 | 积分 |
|--------|------|------|------|
| P0 | `practice_integrator.py:97` → `search_by_skill()` 不存在 | 练习完成后关联资料**崩溃** | ⚠️ 运行时 500 |
| P0 | `practice_error_book.py:282` → `material_meta` 表不存在 | 错题推荐资料**崩溃** | ⚠️ 运行时 500 |
| P0 | `upload.py:163` → `domain.materials.service` 不存在 | 所有文件后处理**静默丢失** | ⚠️ skills/summary 始终为空 |
| P1 | `material_search.py:93` heading_path 恒空 | RAG 上下文丢失标题层次 | 影响 AI 质量 |
| P1 | `search_sync` 回退返回 [] | 无 embedding 时 RAG 完全缺失 | 影响 AI 质量 |
| P1 | 索引无事务 | 索引中途失败 → 数据丢失 | 可靠性 |

### 6.2 可扩性限制 (影响功能拓展)

| 优先级 | 问题 | 限制 |
|--------|------|------|
| P2 | 无 pgvector | 全表扫描, 大数据集搜索慢 |
| P2 | workspace vs materials 分离 | 对话文件不可用于搜索/出题 |
| P2 | 不支持视频/代码文件 | 用户无法上传学习视频/代码作业 |
| P2 | 全量 file.read() | 大文件内存占用高 |
| P3 | materials_meta.json 遗留 | 元数据双写, 不一致风险 |
| P3 | 8列预留未用 | schema 膨胀, 维护成本 |
| P3 | TOC ID 冲突 | 标题前30字符相同→ID冲突 |
| P3 | 代码块中 # 误识别为标题 | 代码文件 TOC 错误 |

---

## 7. 接口版本总结

| 层 | 接口形式 | 数量 | 消费者数 | 稳定性 |
|----|----------|------|----------|--------|
| API | HTTP REST | 25 | 1(前端) | 稳定 |
| Python | 类方法调用 | 12 | 3(practice/conversation/common) | ⚠️ search_by_skill 不存在 |
| DB | 直接 SQL | 8 | 4(question_gen, bank, stub, manage) | ❌ material_meta 不存在 |
| 启动 | 函数钩子 | 2 | main.py | ✅ |
| 工具 | LLM tool def | 2 | tool_repository | ✅ (间接) |

---

## 附录: 文件系统全量关联文件清单

```
# 核心文件系统 (13 files, ~1.2K 行)
backend/app/api/system/files_routes/
  __init__.py     — 聚合 + recover_stuck_files
  upload.py       — 上传 + 索引
  browse.py       — 浏览 + 搜索
  manage.py       — 管理 + 批量

backend/app/infrastructure/media/
  material_parser.py         — MarkItDown 封装
  material_toc_extractor.py  — TOC 提取
  material_indexer.py        — 索引流水线
  material_search.py         — 向量/全文搜索
  material_common.py         — 公共
  materials_meta.py          — 遗留 JSON 元数据
  media_search.py            — 多平台搜索(独立)

backend/app/infrastructure/
  embedding_utils.py         — OpenVINO embedding

backend/app/services/common/
  materials_stub.py          — 服务桩

# 消费者 (7 files)
backend/app/services/conversation/
  context_builder.py         — RAG 注入(旧)
  context_pipeline.py        — RAG 注入(新)

backend/app/services/practice/
  practice_question_gen.py   — 出题用资料
  practice_question_bank.py  — 题库关联资料
  practice_integrator.py     — ❌ 崩坏
  practice_error_book.py     — ❌ 崩坏
  practice_recall.py         — 间接

backend/app/api/conversation/
  conversation_routes.py     — workspace 独立文件系统

backend/app/api/system/
  data_routes.py             — 管理后台

backend/app/
  main.py                    — 启动注册

---

## 8. Step 3 决策记录 (2026-06-16 讨论确认)

| 决策 | 结论 | 参考 |
|------|------|------|
| S3-Q1. 文件格式扩展 | 同时添加视频(.mp4 .avi .mov .mkv) + 代码(.py .js .ts .java), 代码→document 类型 | ADR 0019 |
| S3-Q2. 搜索增强 | 新增 3 个 API: 文件内搜索、单 chunk 全文、相似分块 | ADR 0019 |
| S3-Q3. 批量 reindex | 事务回滚 + 后台定时(如间隔 5 分钟)自动重试 index_failed 文件 | ADR 0019 |