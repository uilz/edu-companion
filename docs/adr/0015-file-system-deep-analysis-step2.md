# ADR 0015: 文件系统底层数据结构与核心技术深度分析 (Round 3 Step 2)

> 生成日期: 2026-06-16 | 状态: Draft
> 基于: ADR 0014 (文件系统全景)
> 目标: 详细分析3表关系/向量搜索/索引流水线/TOC提取/Embedding/搜索回退的全部实现细节

---

## 1. 三表数据结构深度分析

### 1.1 materials 表 — 文件主表

#### 完整列定义 (database.py:97-150)

```
material_id     TEXT PK              -- UUID v4, 如 "a1b2c3d4-..."
user_id         TEXT NOT NULL        -- 所有者
file_name       TEXT NOT NULL        -- 原始文件名, 含扩展名
file_type       TEXT DEFAULT ''      -- 'pdf'|'docx'|'pptx'|'xlsx'|'document'|'image'|'audio'|'other'
file_size       INTEGER DEFAULT 0    -- 字节
storage_path    TEXT DEFAULT ''      -- 磁盘路径: COMPANION_HOME/uploads/{uid}/{material_id}{ext}
purpose         TEXT DEFAULT 'session'  -- 'session'|'library'
status          TEXT DEFAULT 'uploading' -- 'uploading'|'indexed'|'index_failed'
chunk_count     INTEGER DEFAULT 0    -- 分块数
question_count  INTEGER DEFAULT 0    -- 练习题数 (预留, 目前未用)
skills_covered_json JSONB DEFAULT '[]'  -- LLM 提取知识点标签数组, ["标签1","标签2"]
summary         TEXT DEFAULT ''      -- LLM 生成摘要, ≤200字
level           TEXT DEFAULT 'partition' -- 'partition'|'folder', 层级归属
parent_id       TEXT DEFAULT ''      -- 父文件夹的 material_id
tags_json       JSONB DEFAULT '[]'   -- 用户标签数组
is_deleted      BOOLEAN DEFAULT FALSE -- 软删除标记
deleted_at      TIMESTAMP           -- 删除时间
is_folder       BOOLEAN DEFAULT FALSE -- 是否为文件夹
expires_at      TIMESTAMP           -- 过期时间 (session 文件)
created_at      TIMESTAMP DEFAULT NOW()
indexed_at      TIMESTAMP
```

#### 索引
```
idx_materials_user (user_id)  -- 按用户查询
```

#### 已知问题
- **列演化历史**: 约一半列通过 `ALTER TABLE ADD COLUMN IF NOT EXISTS` 动态追加 (summary, level, parent_id, tags_json, deleted_at, is_deleted, is_folder)
- **冗余列**: `question_count` 始终为0, 无代码更新
- **expires_at**: 仅有列定义, 无清理逻辑(manage.py cleanup 只清 session 文件, 不理 expires_at)
- **status 枚举**: 无 CHECK 约束, 靠代码保证
- **无外键**: material_chunks.material_id 无 FK → DELETE 依赖手动清理

### 1.2 material_chunks 表 — 分块内容 + 向量

#### 完整列定义 (database.py:153-177)

```
chunk_id          TEXT PK              -- 'chk_{material_id}_{index}', 如 "chk_a1b2_0"
user_id           TEXT NOT NULL
material_id       TEXT NOT NULL        -- → materials.material_id (隐式关联, 无FK)
text              TEXT DEFAULT ''      -- 分块文本, DB 截断到 8000 chars
image_urls_json   JSONB DEFAULT '[]'   -- 预留: 行内图片
chunk_type        TEXT DEFAULT 'text'  -- 当前仅 'text'
skill_ids_json    JSONB DEFAULT '[]'   -- 预留: 关联知识点ID
bloom_level       TEXT DEFAULT 'understand'  -- 预留: 布鲁姆分类
difficulty_estimate DOUBLE PRECISION DEFAULT 0.5  -- 预留: 难度系数
source_file       TEXT DEFAULT ''      -- 原始文件名
page_number       INTEGER              -- 预留: 页码
chunk_index       INTEGER DEFAULT 0    -- 分块序号, 0-based
created_at        TIMESTAMP DEFAULT NOW()
indexed_at        TIMESTAMP
indexing_status   TEXT DEFAULT 'pending'  -- 'pending'|'indexed'
heading_path      TEXT DEFAULT ''      -- breadcrumb: "H1标题 > H2标题 > H3标题"
embedding         DOUBLE PRECISION[]   -- 384维向量, NULLABLE
```

#### 索引
```
idx_chunks_material (material_id)  -- 按文件查分块
```

#### 关键设计

**embedding 列** 是向量搜索的核心:
- 类型 `DOUBLE PRECISION[]` — PostgreSQL 原生数组, 非 pgvector
- 维度 384 (`EMBEDDING_DIM`)
- NULLABLE — 大量 chunk 可能 embedding=NULL (未配置模型时)
- 搜索时过滤: `mc.embedding IS NOT NULL AND array_length(mc.embedding, 1) = 384`

**text 列限制**:
- indexer 写入时截断 `ch["text"][:8000]`
- 搜索返回时再次截断 `r["text"][:2000]`
- 实际 chunk 文本可能因 flat 分块或 TOC 分块而远小于 8000

**预留列未使用**:
- `image_urls_json, skill_ids_json, bloom_level, difficulty_estimate, page_number` — 全是预留, 当前无写入逻辑

### 1.3 material_toc 表 — 目录树

#### 完整列定义 (database.py:180-192)

```
toc_id          TEXT PK           -- 'toc_{material_id}_{level}_{heading}', 如 "toc_a1b2_1_Introduction"
material_id     TEXT NOT NULL     -- → materials.material_id
parent_toc_id   TEXT              -- → material_toc.toc_id (自引用, NULL=根节点)
level           INTEGER DEFAULT 1 -- 1=H1, 2=H2, 3=H3 ...
heading         TEXT NOT NULL DEFAULT ''  -- 标题文本
chunk_start     INTEGER DEFAULT 0  -- 关联分块的起始索引
chunk_end       INTEGER DEFAULT 0  -- 关联分块的结束索引
page_start      INTEGER             -- 预留: 起始页码
created_at      TIMESTAMPTZ DEFAULT NOW()
```

#### 索引
```
idx_toc_material (material_id)
idx_toc_parent (parent_toc_id)
```

#### 自引用结构
```
material_toc (parent_toc_id → material_toc.toc_id)

示例:
  toc_id: "toc_m1_1_Overview"          level=1, parent_toc_id=NULL
    └─ toc_id: "toc_m1_2_Setup"        level=2, parent_toc_id=↑
         └─ toc_id: "toc_m1_3_Install" level=3, parent_toc_id=↑
```

#### TOC ID 生成 (indexer.py:107-114)

```python
toc_id = f"toc_{material_id}_{tn.level}_{_safe_heading(tn.heading)}"
_safe_heading: 取前30字符, 替换空格/斜杠为下划线

父节点匹配:
  parent_id = f"toc_{material_id}_{tn.parent.level}_{_safe_heading(tn.parent.heading)}"
  验证: parent_id in {同格式set of 已插入节点}
```

#### 已知问题
- **TOC ID 冲突风险**: `_safe_heading` 截取前30字符 → 两标题前30字符相同则冲突
- **父子验证逻辑脆弱**: indexer.py:114, set comprehension 嵌套在循环中, 可能导致误匹配
- **toc 仅对大 library 文件构建**: 小文件 + session 文件 → 0条 toc 记录
- **page_start**: 预留列, 始终 NULL

### 1.4 三表关系全景

```
materials (1) ────────── material_chunks (N)
    │                       ↑ 无 FK, 代码级关联
    │                       ↑ DELETE mater_id → 手动 DELETE chunks
    │
    └─────────── material_toc (N)
                        ↑ 无 FK, 代码级关联
                        ↑ 自引用 FK: parent_toc_id → toc_id

materials:chunks ≈ 1:20~300 (取决于文件大小)
materials:toc ≈ 0:0 (小文件) | 1:3~100 (大文件)
chunks:toc ≈ M:N (通过 chunk_start/chunk_end 关联, 非FK)
```

---

## 2. 向量搜索技术细节

### 2.1 余弦距离计算 (material_search.py:62-85)

```sql
WITH qvec AS (
    SELECT %s::double precision[] AS v   -- 查询向量
)
SELECT mc.text, mc.chunk_index, mc.material_id,
       1.0 - (
           (SELECT sum(a*b) FROM unnest(mc.embedding, (SELECT v FROM qvec)) AS t(a,b))
           / NULLIF(
               sqrt((SELECT sum(a*a) FROM unnest(mc.embedding) AS t(a))) *
               sqrt((SELECT sum(b*b) FROM unnest((SELECT v FROM qvec)) AS t(b))),
               0
           )
       ) AS score
FROM material_chunks mc
JOIN materials m ON mc.material_id = m.material_id
WHERE mc.user_id = %s
  AND mc.embedding IS NOT NULL
  AND array_length(mc.embedding, 1) = 384
  AND m.status = 'indexed'
  [AND m.purpose = %s]
  [AND mc.material_id = ANY(%s)]
ORDER BY score ASC
LIMIT %s
```

#### 计算原理

```
cosine_distance = 1 - cosine_similarity
cosine_similarity = dot(A,B) / (||A|| * ||B||)
dot(A,B) = Σ(Ai * Bi)       -- unnest(A, B) → sum(a*b)
||A|| = sqrt(Σ(Ai²))        -- unnest(A) → sum(a*a)
||B|| = sqrt(Σ(Bi²))        -- unnest(B) → sum(b*b)

score = 1 - dot/(||A||*||B||)    — 范围 [0, 2]
score = 0 → 完美匹配 (同向量)
score = 1 → 正交 (无相关性)
score = 2 → 完全相反
```

#### 与 pgvector 对比

| 特性 | 当前实现 | pgvector 方案 |
|------|----------|---------------|
| 存储 | DOUBLE PRECISION[] | vector(384) |
| 索引 | 无(全表扫描) | IVFFlat / HNSW |
| 距离计算 | 手工 SQL unnest | 内建 `<=>` 运算符 |
| 性能 | O(n) 全表扫描, 每行 unnest 3次 | 索引加速 O(log n) |
| 维度硬编码 | 384 (代码常数) | schema 级定义 |
| NULL 处理 | 手动过滤 | 无 NULL |

### 2.2 搜索参数

| 参数 | 默认值 | 位置 |
|------|--------|------|
| top_k | 10 (async) / 5 (sync) | search() / search_sync() |
| HIT_THRESHOLD | 0.35 | should_inject_rag() |
| query 截断 | 前 2000 字符 | _compute_embedding(query[:2000]) |
| text 返回截断 | 前 2000 字符 | r["text"][:2000] |
| heading_path | 始终空字符串 | 搜索返回不携带 heading_path |

#### 已知问题

1. **全表扫描**: 无 pgvector 索引, 每次搜索扫描全部 embedding IS NOT NULL 的行
2. **两次向量序列化**: 查询向量 → PostgreSQL 字符串 `{0.1,0.2,...}` → 解析 → CAST 为向量, 384个 float 的字符串拼接
3. **search_sync 回退策略与 search 不一致**: async 版回退全文搜索; sync 版回退返回空列表
4. **heading_path 丢失**: `should_inject_rag()` 调 `format_rag_context()` 期望 heading_path, 但 search_sync 返回的 heading_path 始终是空字符串

### 2.3 全文搜索回退 (fallback)

```sql
SELECT mc.text, mc.chunk_index, mc.material_id,
       m.file_name as material_name,
       1.0 as score     -- 固定 1.0, 不影响 RAG 阈值判断
FROM material_chunks mc
JOIN materials m ON mc.material_id = m.material_id
WHERE mc.user_id = %s
  AND m.status = 'indexed'
  [AND m.purpose = %s]
  AND to_tsvector('simple', coalesce(mc.text, ''))
      @@ plainto_tsquery('simple', %s)
LIMIT %s
```

- `to_tsvector('simple', ...)`: 不进行词干化, 精确匹配
- `plainto_tsquery('simple', ...)`: 输入分词后 AND 连接
- 所有结果 score=1.0 → `should_inject_rag()` 返回 False → 不会注入 RAG

---

## 3. 索引流水线细节

### 3.1 触发链路

```
POST /api/files/upload
  → await file.read()           [全量内存, 最大50MB]
  → storage_path.write_bytes()  [写磁盘]
  → INSERT materials(status=uploading)
  → asyncio.ensure_future(_index_background(...))
  → return {status: "uploading"}
  
_index_background (异步, 与请求解耦)
  1. material_indexer.index_file(...)
  2. → return {material_id, status, chunk_count, toc_count}
  3. if chunk_count > 0:
       from domain.materials.service import MaterialServiceImpl  [❌ 模块不存在!]
       svc = MaterialServiceImpl(event_bus=_get_index_event_bus())
       await svc.on_indexed(_IndexEvent)  [❌ 总是异常 → log warning]
```

### 3.2 index_file 内部流水线

```
输入: user_id, material_id, file_path, file_name, file_type, file_size, purpose

Step 1: MarkItDown 解析
  material_parser.parse(file_path, file_type) → markdown_text (str)
  失败 → UPDATE status='index_failed', return parse_failed

Step 2: 判定是否建 TOC
  is_large = file_size > 5MB OR page_count > 15
  build_toc = is_large AND purpose == "library"

Step 3: 分块
  if build_toc:
    toc_nodes = extract_toc(markdown_text)    -- 正则解析标题
    chunks = chunk_by_toc(markdown_text, toc_nodes)  -- 按标题分割
    toc_nodes = assign_chunk_ranges(toc_nodes, chunks) -- 关联分块索引
  else:
    chunks = chunk_by_toc(markdown_text, [], max_chunk_size=1000)  -- 平铺

  空chunks → return no_content

Step 4: 写入 DB (无事务! 非原子)
  4a. DELETE FROM material_toc WHERE material_id = %s  (仅 build_toc)
  4b. DELETE FROM material_chunks WHERE material_id = %s
  4c. INSERT material_chunks (逐条, 含embedding)
      每条:
        chunk_id = f"chk_{material_id}_{index}"
        embed_text = f"{heading_path}\n{ch['text']}"[:2000]
        embedding = _compute_embedding(embed_text)  -- 可能为 NULL
        INSERT (chunk_id, user_id, material_id, text[:8000], ...)
  4d. INSERT material_toc (逐条, 含parent验证)
  4e. UPDATE materials SET chunk_count=N, status='indexed'

Step 5: 返回 result dict
```

### 3.3 原子性缺陷

整个索引流水线**无事务包裹**:
- 4a/4b DELETE 后, 若 4c INSERT 中途失败 → chunks 全丢, 文件状态仍 'uploading'
- 4c 已完成部分 chunk → index_file 异常 → status 不变 'uploading'
- recover_stuck_files 在下次启动时尝试重索引(仅 status='uploading' 的文件)
- 若 4e UPDATE 失败 → chunk/toc 已写入但 status='uploading'

### 3.4 后处理断裂 (重要bug)

`_index_background` 的 on_indexed 后处理:
```python
from domain.materials.service import MaterialServiceImpl  # ← 模块不存在!
class _IndexEvent:
    user_id = user_id
    material_id = material_id
    chunk_count = chunk_count

svc = MaterialServiceImpl(event_bus=_get_index_event_bus())
await svc.on_indexed(_IndexEvent)  # ← 始终抛出 ImportError
```

效果: **所有上传文件的后处理(LLM提取skills+summary)永远失败**. 
`services/common/materials_stub.py` 的 `MaterialsStub.on_indexed()` 实现了真正的逻辑但从未被调用.

此外 `_get_index_event_bus()` 每次调用创建一个新 EventBus (handler_timeout=30s), 若 EventBus 创建也失败则双层异常, 外层 catch log warning.

---

## 4. TOC 提取引擎细节

### 4.1 extract_toc() — 标题层次解析

```python
正则: r"^(#{1,6})\s+(.+)$"    # 行首 #~###### + 空格 + 标题文本

算法: 栈式维护父子关系
  lines = text.split("\n")
  stack = []  # 节点栈
  for each heading:
    while stack.top.level >= current_level: pop
    if stack: parent = stack.top
    push current
```

**过滤**:
- 忽略标题长度 > 200 的(视为误识别)
- 不区分代码块内/外的标题 (`#` 可能出现在代码中)

### 4.2 chunk_by_toc() — 按标题分割

```
输入: markdown_text, toc_nodes, max_chunk_size=1000

算法:
  1. 构建 heading→TOCNode 映射 (归一化: strip+lower)
  2. 面包屑路径构建: breadcrumb(node) = parent.heading > ... > node.heading
  3. 逐行扫描:
     - 遇到标题行 → 结束上一个 chunk, 开始新 chunk
     - 设置 current_heading = breadcrumb(node) [若匹配TOC] | 标题原文 [若不匹配]
  4. 最后的段落 → 最后一个 chunk
  5. 大chunk再分割: chunk.text > max_chunk_size → _split_large_chunk()
```

**问题**: 代码块中以 `#` 开头的行也会被识别为标题 → chunk 可能切割在代码块中间

### 4.3 assign_chunk_ranges() — TOC→chunk 关联

```
输入: toc_nodes, chunks
算法:
  1. 构建 heading→TOCNode 映射 (strip+lower)
  2. 对每个 chunk, 取其 heading_path 的最后一段
  3. 匹配 TOC 节点 → 设置 chunk_start/chunk_end
  4. 补漏: 未匹配的节点设 chunk_start=0, chunk_end=last_chunk

依赖: heading_path 格式 "H1 > H2 > H3"
```

### 4.4 _chunk_flat() — 无TOC平铺分块

```
输入: text, max_size=1000 (指定) | 1000 (固定)

算法:
  paragraphs = text.split("\n\n")  # 按空行分段
  buffer: 累积段落直到超过 max_size → flush 为一个 chunk
  → 最后一个 buffer → flush
```

### 4.5 embedding 输入构造

```
embed_text = f"{heading_path}\n{ch['text']}"[:2000]
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

大文件: 含 breadcrumb 路径 → 语义中包含上下文位置
小文件: heading_path="" → 仅 chunk 文本
```

---

## 5. Embedding 推理细节

### 5.1 模型加载 (embedding_utils.py:25-53)

```python
模型路径: backend/app/models/granite-embedding-97m/
  openvino_model.xml  -- OpenVINO IR 模型
  tokenizer.json      -- HuggingFace tokenizer

加载: 延迟加载, 全局单例 (_embedding_model, _tokenizer)
引擎: OpenVINO CPU
输入: tokenizer.encode(text) → input_ids (int64) + attention_mask (int64)
输出: output_key[0, -1] → 384维向量 (float64 → list[float])
截断: max_len=512 tokens
```

### 5.2 推理流程

```
compute_embedding(text: str) → list[float] | None
  1. text.strip() 为空 → return None
  2. _get_embedding_model():
     - 全局缓存命中 → return
     - 首次: Core.read_model() → compile_model("CPU") → Tokenizer.from_file()
  3. tokenizer.encode(text)
  4. len(ids) > 512 → truncate(512)
  5. np.array([ids]), np.array([mask])
  6. model([input_ids, attention_mask]) → output
  7. output = result[output_key][0, -1]  # 取最后隐层
  8. return vec.tolist()
```

### 5.3 失败链

```
compute_embedding fail → embedding=None
  → material_indexer._compute_embedding → returns None
    → material_chunks.embedding=NULL
    → vector_search WHERE embedding IS NOT NULL → 该 chunk 不被搜索

compute_embedding fail (query侧)
  → material_search._compute_embedding → returns None
    → search() 回退全文搜索
    → search_sync() 返回空列表 []  ← 不一致!
```

### 5.4 性能特征

- 单次推理: ~50-200ms (CPU, 取决于文本长度)
- 单文件索引: N chunks × 50-200ms = 数秒至数十秒
- 768维向量存储: 384 × 8bytes = 3072 bytes/chunk
- 1000 chunk 文件 → ~3MB 向量数据

---

## 6. RAG 注入机制

### 6.1 判断阈值 (material_search.py:170-179)

```python
def should_inject_rag(results) -> bool:
    if not results: return False
    best_score = results[0].get("score", 1.0)
    return best_score < HIT_THRESHOLD  # 0.35
    
# HIT_THRESHOLD=0.35 含义:
# cosine_similarity > 0.65 → 注入
# cosine_similarity ≤ 0.65 → 注入 (score < 0.35 即 cos > 0.65)
```

### 6.2 上下文格式化 (material_search.py:181-196)

```python
format_rag_context(results: list[dict]) → str:

"--- 资料：{material_name} [{heading_path}]
{text[:2000]}"

拼接前5个结果, 间隔 \n\n
```

### 6.3 context_builder 消费链路

```python
context_builder.py:
  material_search.search_sync(user_id, query, top_k=5) → results
  → should_inject_rag(results) → True
  → format_rag_context(results) → rag_context
  → system_prompt += rag_context  ← 拼接到 tutor system prompt 末尾
```

**问题**: 
- `search_sync` 不返回 `heading_path` (永远是空字符串) → RAG 上下文丢失"资料:文件名 []"中的 heading
- `search_sync` 回退返回空列表 → `should_inject_rag()` 返回 False → 无 RAG 注入
- **同步版 vs 异步版行为不一致**: sync 回退→[], async 回退→全文搜索

---

## 7. 分类目的自动判定 (upload.py:53-59)

```python
_classify_purpose(file_size, upload_source):
  if file_size > 5MB:         → "library"
  if upload_source == 'files_page': → "library"
  else:                       → "session"
```

| 条件 | purpose | 建TOC | 搜索范围 |
|------|---------|-------|----------|
| >5MB | library | √ | general + knowledge |
| <5MB + files_page | library | ×(不满足is_large) | general + knowledge |
| <5MB + 对话页 | session | × | general 仅 |

---

## 8. 启动恢复机制

```python
recover_stuck_files() — 由 main.py 启动时调用

SELECT * FROM materials WHERE status = 'uploading'

对每个stuck文件:
  storage_path 存在 → asyncio.ensure_future(_index_background(...))
  storage_path 丢失 → UPDATE status='index_failed'
```

**问题**: 仅恢复 `status='uploading'`, 不恢复 `status='index_failed'`

---

## 9. 已识别技术债务汇总 (结合ADR 0014 + 本分析)

### 9.1 严重 (运行时错误)

| # | 问题 | 严重性 | 涉及代码 |
|---|------|--------|----------|
| S1 | `domain/materials/service.py` 不存在, on_indexed 后处理永远失败 | **功能丢失** | upload.py:163 |
| S2 | `practice_integrator.py:97` 调 `search_by_skill()` 不存在 | **运行时崩溃** | integrator.py:97 |
| S3 | `practice_error_book.py` 查 `material_meta` 表不存在 | **运行时崩溃** | error_book.py:282 |

### 9.2 中 (设计缺陷)

| # | 问题 | 涉及代码 |
|---|------|----------|
| M1 | 索引流水线无事务 → 部分失败时数据不一致 | material_indexer.py:82-132 |
| M2 | search_sync 回退返回 [] vs search 回退全文搜索 | material_search.py:205-272 |
| M3 | heading_path 在搜索返回中恒为空 → RAG 上下文缺失 | material_search.py:93 |
| M4 | TOC ID 生成冲突: 前30字符相同标题 | material_indexer.py:107 |
| M5 | 代码块中 # 被误识别为标题 | material_toc_extractor.py:48 |
| M6 | upload.py 每个 upload 创建新 EventBus | upload.py:28-34 |
| M7 | 无 pgvector → 全表扫描 | material_search.py:62-85 |

### 9.3 低 (代码质量)

| # | 问题 |
|---|------|
| L1 | 多次 `from app.infrastructure.db.database import get_db` 内联 import |
| L2 | materials 表列通过 ALTER TABLE 演化 → schema 与代码脱节 |
| L3 | DB 连接用 psycopg2 ThreadedConnectionPool + asyncpg 两套 |
| L4 | upload.py 全量 file.read() 占用大内存 |
| L5 | chunk text 长度限制 8000 可能丢失内容 |

---

## 10. 核心数据流图

```
┌──────────────┐     ┌─────────────┐     ┌──────────────────┐
│  上传请求     │     │ 磁盘文件     │     │ PostgreSQL DB     │
│ POST /upload  │────>│ {uid}/{mid}{ext}│ │                   │
│ file.read()   │     └─────────────┘     │ materials(mid,...)│
│ → uuid4       │                         │   status=uploading│
│ → INSERT      │                         └────────┬─────────┘
│ → ensure_future│                                  │
└──────┬───────┘                                    │
       │ 异步                                       │
       ▼                                            │
┌──────────────┐                                    │
│ _index_background                                 │
│  ┌──────────┐                                    │
│  │MarkItDown│ → markdown_text                     │
│  └──────────┘                                    │
│       │                                           │
│       ▼                                           │
│  ┌──────────┐                                    │
│  │extract_toc│ → toc_nodes (if large+library)     │
│  └──────────┘                                    │
│       │                                           │
│       ▼                                           │
│  ┌───────────┐                                   │
│  │chunk_by_toc│ → chunks [{text,heading_path}]    │
│  └───────────┘                                   │
│       │                                           │
│       ▼                                           │
│  ┌────────────────┐                              │
│  │compute_embedding│ → 384-dim vector / None      │
│  │OpenVINO CPU     │                              │
│  └────────────────┘                              │
│       │                                           │
│       ▼                                           │
│  DELETE chunks (reindex case)                    │
│  INSERT chunk(text[:8000], embedding) ───────────>│ material_chunks
│  INSERT toc (if build) ──────────────────────────>│ material_toc
│  UPDATE status=indexed ─────────────────────────>│ materials
└──────────────────────────────────────────────────┘

搜索链路:
┌────────────┐   ┌──────────────┐   ┌───────────────┐
│ 查询文本    │──>│ compute_      │──>│ PostgreSQL     │
│ "什么是XX"  │   │ embedding()   │   │ cosine相似度   │
└────────────┘   └──────────────┘   │ unnest(A,B)    │
                                    │ ORDER BY score  │
                                    └───────┬───────┘
                                            │
                                            ▼
                                    ┌───────────────┐
                                    │ should_inject_ │
                                    │ rag(score<0.35)│
                                    └───────┬───────┘
                                            │
                                    ┌───────▼───────┐
                                    │ format_rag_    │
                                    │ context()      │
                                    │ → system_prompt│
                                    └───────────────┘
```

---

## 附录: 引用代码文件清单

| 文件 | 行数 | 角色 |
|------|------|------|
| `backend/app/infrastructure/db/database.py` | L96-200 | 三表 DDL |
| `backend/app/infrastructure/media/material_search.py` | 276L | 向量搜索引擎 |
| `backend/app/infrastructure/media/material_indexer.py` | 171L | 索引流水线 |
| `backend/app/infrastructure/media/material_toc_extractor.py` | 259L | TOC 提取引擎 |
| `backend/app/infrastructure/media/material_parser.py` | 92L | MarkItDown 封装 |
| `backend/app/infrastructure/media/material_common.py` | 31L | 公共模块(embedding re-export) |
| `backend/app/infrastructure/embedding_utils.py` | 98L | OpenVINO 推理 |
| `backend/app/api/system/files_routes/upload.py` | 249L | 上传 + 索引触发 |
| `backend/app/services/common/materials_stub.py` | 122L | 后处理(未使用) |
| `backend/app/services/practice/practice_integrator.py` | L97 | 崩坏调用点 |
| `backend/app/services/practice/practice_error_book.py` | L282 | 崩坏调用点 |

---

## 11. Step 2 决策记录 (2026-06-16 讨论确认)

| 决策 | 结论 | 参考 |
|------|------|------|
| S2-Q1. TOC ID 冲突 | 改用 `hash(f"{material_id}_{level}_{heading}")` | ADR 0019 |
| S2-Q2. chunk text 截断 | 改 TEXT 列, 去掉 `[:8000]` 截断 | ADR 0019 |
| S2-Q3. search_sync 行为不一致 | `search_sync()` 内部调 `search()`, 复用全文回退 | ADR 0019 |
| S2-Q4. heading_path 恒空 | search_sync SQL 增加 `mc.heading_path` 返回 | ADR 0019 |
| S2-Q5. 代码块 # 误识别 | 解析前用 fence 检测跳过代码块区域 | ADR 0019 |