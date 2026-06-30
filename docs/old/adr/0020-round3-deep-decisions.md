# Round 3 第二轮决策 (Implement-level Deep Decisions)

> 生成日期: 2026-06-16 | 状态: **已定 — 全部 Accepted**
> 前置: ADR 0014-0019 已定决策
> 范围: 从"方向选择"进入"如何实现"的详细决策
> 审议结果: 2026-06-16 全部接受推荐方案

---

## R2-1: pgvector 迁移细节

### R2-1a: 迁移脚本策略
**背景**: 旧 `embedding DOUBLE PRECISION[]` 数据舍弃, 新建 `embedding_vec vector(384)` 列.

**推荐**: 两步迁移脚本:
1. `ALTER TABLE material_chunks ADD COLUMN embedding_vec vector(384);`
2. 后台逐一重索引所有 `status='indexed'` 文件 (调用已存在的 `reindex` 路径), 填充 `embedding_vec`
3. 旧 `embedding` 列待确认所有文件重索引完成后 DROP

**A**: 启动后批量重索引所有 indexed 文件 (一次性, 启动时) → **▸ 已定(A)**
**B**: 惰性重索引 — 用户打开文件时才索引 (碎片化, 体验差)
**C**: 保留旧列做 fallback, 新数据写新列 → 逐渐迁移后清理旧列

### R2-1b: HNSW 构建参数
**背景**: HNSW 索引需在 embedding_vec 填充后 BUILD.

```
CREATE INDEX idx_chunks_embedding_vec ON material_chunks
USING hnsw (embedding_vec vector_cosine_ops)
WITH (m=16, ef_construction=200);
```
默认 m=16, ef_construction=200. 是否需调整? 小数据集(<10K rows) 可接受. 数据集大时 (>100K rows) 可调 ef_construction=400.

**推荐**: 默认参数起步, 后续按数据规模调参 → **▸ 已定**

### R2-1c: 搜索 SQL 切换
**背景**: 当前手工余弦距离 → pgvector `<->` 操作符.

旧:
```sql
WITH qvec AS (SELECT %s::double precision[] AS v)
SELECT ... 1.0 - (sum(a*b)/...) AS score ...
```
新:
```sql
SELECT ... mc.embedding_vec <-> %s::vector AS score ...
ORDER BY score ASC LIMIT %s
```
**推荐**: 修改 3 处 SQL (search/search_sync/search_knowledge), 去掉旧列引用 → **▸ 已定**

---

## R2-2: infrastructure/files/ 精确文件边界

**背景**: 已定重构 infrastructure/media/ → infrastructure/files/, 但每个文件负责什么方法需要定义.

**推荐**: **

文件 | 职责 | 从哪来 | 方法签名
parser.py | MarkItDown解析 | material_parser.py + 新扩展名支持 | `parse(path, type) → str`, `get_page_count(path) → int`
chunker.py | TOC提取+分块 | material_toc_extractor.py + fence检测 | `extract_toc(text) → list[TOCNode]`, `chunk_by_toc(text, toc) → list[Chunk]`, `chunk_flat(text, max_size) → list[Chunk]`
indexer.py | 索引编排+事务+重试 | material_indexer.py + on_indexed内联 | `index_file(uid, mid, path, name, type, size, purpose) → IndexResult`
embedding.py | OpenVINO推理 | embedding_utils.py | `compute(text) → list[float]/None`, 全局单例
search.py | 向量+全文搜索 | material_search.py + heading_path + node_ids | `search(uid, query, ...) → list[dict]`, `search_sync(uid, query, ...) → list[dict]`, `search_knowledge(uid, query, ...) → list[dict]`
searcher.py | RAG判断+格式化 | material_search.py 的 should_inject_rag/format_rag_context | `should_inject(results) → bool`, `format_context(results) → str`, `search_rag(uid, query, ...) → str/None`
storage.py | DB操作 | material_common.py + 新 | `get_db()`, `ensure_extension()`

### R2-2a: 命名争议
`searcher.py` vs 直接放 search.py? `embedding.py` vs `vectorizer.py`?

**推荐**: search.py 包含搜索+格式化, 不拆 searcher.py. embedding.py 保持命名. → **▸ 已定**

### R2-2b: storage.py 是否需要独立文件?
**背景**: 当前 get_pool/get_db 散落在各文件.

**推荐 A**: storage.py 统一 DB 工具函数 (get_pool, get_db, ensure_extension) — 单点管理 → **▸ 已定(A)**
**B**: 不单独文件, 各文件自己 import database.py 的 get_db

---

## R2-3: 文件格式扩展清单

**背景**: 已定添加视频+代码文件.

**推荐**: 
```
视频: .mp4, .avi, .mov, .mkv, .webm  → file_type = 'video'
代码: .py, .js, .ts, .jsx, .tsx, .java, .cpp, .c, .h, .sql, .yaml, .yml, .toml, .ini → file_type = 'code'
ALLOWED_EXTENSIONS 从 24 → 44 种
```
MarkItDown 对视频返回空文本 (仅文件名+元数据), 对代码文件返回纯文本.

对于视频文件, chunk 内容如何组织?
- **A**: 不建 chunk, 仅插入 materials 元数据记录 (无索引内容)
- **B**: 建一个 chunk 存文件名+类型+描述 (可搜索"找到该视频") → **▸ 已定(B)**

---

## R2-4: practice_material_questions 关联表精确设计

**背景**: 已定新建关联表.

```
CREATE TABLE practice_material_questions (
    id SERIAL PRIMARY KEY,
    material_id TEXT NOT NULL REFERENCES materials(material_id) ON DELETE CASCADE,
    question_id TEXT NOT NULL,
    chunk_index INTEGER,         -- NULL = 无特定分块
    user_id TEXT NOT NULL,
    session_id TEXT,             -- practice session ID (可追溯上下文)
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(material_id, question_id)
);
```
索引: idx_pmq_material(material_id), idx_pmq_question(question_id)

写入时机: `practice_question_gen.py` 出题成功后 INSERT.

### R2-4a: 是否需要 `session_id` 列?
**A**: 保留 → 可追溯"哪次练习用了这个材料出题" → **▸ 已定(A)**
**B**: 去掉 → 保持简单, session 信息可从 questions 字典查询

---

## R2-5: workspace 废弃迁移方案

**背景**: 已定 workspace 废弃, 对话文件上传走 materials.

### 现有 workspace 文件如何处理?
```
现有路径: ~/.companion/uploads/{uid}/{conv_id}/{type}/{file_id}{ext}
目标路径: COMPANION_HOME/uploads/{uid}/{material_id}{ext}
```
**A**: 一次性迁移 — 启动时扫描 workspace 目录, 逐一 INSERT materials, 然后删除 workspace 记录 (√ 但可能长)
**B**: 惰性迁移 — 用户打开旧对话时, 按需迁移对应文件
**C**: 遗留处理 — 保留旧 workspace 只读, 新建文件走 materials; 不迁移旧数据 → **▸ 已定(C)**

### 对话路由改动:
**推荐**: 
- 删 `POST /api/workspace/upload` → 前端对话上传改调 `POST /api/files/upload?source=conversation&conv_id=xxx`
- `GET /api/workspace/files` → 保留兼容, 内部调 materials 查询
- `UserData.files` (JSONB) 仍记录引用 material_id → 兼容旧对话的 FileRecord

---

## R2-6: 统一 RAG Provider 迁移步骤

**背景**: 已定 context_pipeline TutorCapability → 唯一 RAG Provider, context_builder 废弃.

**迁移步骤**:
1. TutorCapability 增加 `search_sync()` + `should_inject_rag()` + `format_rag_context()` 封装
2. context_builder 中 import 改为调 TutorCapability (同一实例)
3. 确认无回归 → 删除 context_builder 中重复的 RAG 代码 (约30行)
4. 修改搜索方法: `search_sync` → 调 `search()` → 统一全文回退 + heading_path

**风险**: context_builder 和 context_pipeline 的 system_prompt 构建逻辑不同, 不能直接替换. 需保持 prompt 结构一致.

**A**: 先统一搜索方法 (search_sync 调 search), 再统一 RAG Provider (TutorCapability) → **▸ 已定(A)**
**B**: 直接删除 context_builder 的 RAG, 全由 TutorCapability 接管

---

## R2-7: node_ids 过滤实现

**背景**: 已定 search_sync 增加 node_ids 参数, JOIN cognitive_nodes 过滤.

### 实现方案:
```sql
-- 当前:
SELECT ... FROM material_chunks mc JOIN materials m ...

-- 过滤后:
SELECT DISTINCT mc.text, mc.heading_path, mc.chunk_index, ...
FROM material_chunks mc
JOIN materials m ON mc.material_id = m.material_id
JOIN cognitive_nodes cn ON cn.user_id = m.user_id
    AND cn.skills_covered_json ? m.skills_covered_json   -- 匹配 skill
WHERE ...
```

**问题**: `cognitive_nodes.skills_covered_json` 与 `materials.skills_covered_json` 都是 JSONB, 需要 overlap 检查 (`?|` 或 `@>`). 若 skills null → 匹配不到.

**A**: JSONB @> 操作符: `cn.skills_covered_json @> m.skills_covered_json` — 严格子集匹配
**B**: JSONB ?| 操作符: `cn.skills_covered_json ?| ARRAY(SELECT jsonb_array_elements_text(m.skills_covered_json))` — 任意 skill 重叠即匹配 → **▸ 已定(B)**
**C**: 不精确匹配 → 选每个 node 前5个 skill, 用来做语义搜索 query: `search(uid, query="|".join(skills), ...)`

---

## R2-8: 后处理 LLM 内联设计

**背景**: 已定后处理内联到 indexer.

### 后处理流程:
```
index_file() 成功后:
  1. SELECT text FROM material_chunks WHERE material_id=%s ORDER BY chunk_index LIMIT 3
  2. 前3 chunk 文本用 "\n---\n" 拼接
  3. LLM 调用: "分析以下内容, 提取3-8个知识点标签(中文) 和 100字摘要"
  4. 解析 LLM 返回 → skills list + summary str
  5. UPDATE materials SET skills_covered_json=%s, summary=%s WHERE material_id=%s
```

**问题**: LLM 调用失败/超时怎么办?

**A**: 失败 → log warning, 不影响 indexed 状态, 之后触发 retry (同 S3-Q3 的定时重试) → **▸ 已定(A)**
**B**: 失败 → 标记 index_failed, 强制用户手动重试
**C**: 失败 → log warning, skills+summary 为空, 降级检索

---

## R2-9: 文件命名策略

**背景**: 当前 `COMPANION_HOME/uploads/{uid}/{material_id}{ext}`.

**分析**: 磁盘文件以 material_id 命名, 无法直观看出哪个文件. 但文件系统只通过 storage_path 引用, 无需可读性.

**A**: 保持现状 `{material_id}{ext}` — 简单, 无冲突 → **▸ 已定(A)**
**B**: `{file_name}` — 可读但可能有特殊字符/冲突
**C**: `{material_id}_{file_name}` — 兼顾

---

## 附录: UX 变动影响链

| 决策 | 涉及文件 (后端) | 涉及文件 (前端) | 估计行 |
|------|-----------------|-----------------|--------|
| R2-1 pgvector | material_search.py | — | ~50 |
| R2-2 infra 重构 | 8个文件新建/移动 | — | ~200 |
| R2-3 格式扩展 | upload.py | 上传组件 | ~20 |
| R2-4 关联表 | practice_question_gen.py | 文件详情页 | ~30 |
| R2-5 workspace 废弃 | conversation_routes.py | 对话上传组件 | ~60 |
| R2-6 RAG 统一 | context_builder.py, context_pipeline.py | — | ~40 |
| R2-7 node_ids | context_builder.py, material_search.py | — | ~30 |
| R2-8 后处理内联 | material_indexer.py | — | ~30 |
| R2-9 命名 | upload.py | — | ~2 |

---

## 实施状态 (2026-06-16 本轮已完成)

### ✅ 已完成 — 后端 (15项)

| 项 | 文件 | 关键变更 |
|----|------|---------|
| R2-1 pgvector | `database.py`, `indexer.py`, `search.py` | embedding_vec 列 + HNSW + <-> 操作符 + 批量迁移 |
| R2-2 infra 重构 | `infrastructure/files/` (7文件) | 旧 media/ deprecated 包装器已删除 |
| R2-3 格式扩展 | `upload.py`, `parser.py` | ALLOWED_EXTENSIONS 24→55, file_type 增加 video/code |
| R2-4 关联表 | `database.py`, `practice_question_gen.py` | practice_material_questions 表 + 出题后自动记录 |
| R2-5 workspace 废弃 | `conversation_routes.py`, `upload.py` | 提取 _do_upload(), workspace 委托到 /api/files/upload |
| R2-6 RAG 统一 | `context_builder.py` | 移除重复 RAG 代码 (约15行), TutorCapability 唯一 Provider |
| R2-7 node_ids | `search.py` | search/search_sync/_search 统一新增 node_ids 参数 |
| R2-8 后处理内联 | `indexer.py` | _post_process 方法内联, LLM 失败降级 |
| R2-9 命名 | `upload.py` | 保持 {material_id}{ext}, 不做改动 |
| S2-Q1 TOC hash | `indexer.py` | hashlib.sha256 hexdigest[:12] 替代 _safe_heading |
| S2-Q2 截断 | `indexer.py` | 去掉 ch["text"][:8000] |
| S2-Q3+Q4 search_sync | `search.py` | 提取 _search() 共享内核, 返回 heading_path |
| S2-Q5 fence 检测 | `chunker.py` | _is_in_fence() 跳过代码块内 # |
| S3-Q2 搜索 API | `browse.py` | 新增 3 个搜索端点 |
| S3-Q3 事务+重试 | `indexer.py`, `main.py` | execute_batch 单事务 + _retry_index_failed 启动重试 |

### ✅ 已完成 — 前端 (4项)

| 项 | 文件 | 关键变更 |
|----|------|---------|
| S4-Q1 skills+summary | `[material_id]/page.tsx` | 接口新增 skills/summary, 展示 amber 色标签 + 摘要卡片 |
| S4-Q2 分块全文展开 | `[material_id]/page.tsx` | 调用 /chunks/{index}/full API, 展开/收起按钮 (>300字显示) |
| S4-Q3 音视频预览 | `[material_id]/page.tsx`, `resources/page.tsx` | audio/video 标签播放器, 详情页 + 预览弹窗均支持 |
| S4-Q4 TOC 跳转+高亮 | `[material_id]/page.tsx` | IntersectionObserver + scrollIntoView + 自动展开 + sticky 侧边栏 |

### 📊 进度总结

| 维度 | 总计 | 完成 | 待做 |
|------|------|------|------|
| 后端核心 | 17 | 17 | 0 |
| 前端展示 | 4 | 4 | 0 |
| admin 管理面板 | — | — | 可启动 |
| 文档 | 1 | 1 | 本 ADR 已更新 |

> 下一阶段建议: 部署验证 → 或启动 admin/ 端管理面板