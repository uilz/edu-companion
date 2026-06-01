# 📁 文件管理系统 · 设计文档

> 子系统：文件上传 / 解析 / 索引 / TOC / RAG / 练习生成
> 状态：v1 设计 | 实施中
> 对应阶段：Phase 10.7+

---

## 一、核心概念

### 1.1 双区设计：知识库 + 临时文件

```
工作空间 /files
├── 📁 知识库 (library)
│   ├── 永久保留
│   ├── 全局显示在文件列表「知识库」tab
│   ├── 大文件建 TOC 层次索引
│   └── AI 优先检索来源
│
└── 📋 临时文件 (session)
    ├── 生命周期跟随对话（最后活跃 +7 天）
    ├── 只显示在「最近使用」+ 所属对话中
    ├── 小文件不建 TOC，直接按段落分块
    └── 可手动转存到知识库
```

### 1.2 purpose 自动判定

不依赖用户手动选择，按客观规则归类：

```python
def classify_purpose(file, upload_source):
    # 大文件自动归知识库
    if file.size > 5_000_000 or file.page_count > 15:
        return 'library'
    # 从 /files 页面上传
    if upload_source == 'files_page':
        return 'library'
    # 从对话上传
    if upload_source == 'chat':
        return 'session'
    # 用户仍可手动覆盖
```

### 1.3 索引深度由文件大小决定

| 文件规模 | TOC | 分块策略 |
|----------|:---:|---------|
| > 15 页 / > 5MB | ✅ 提取完整目录树 | 按标题层级分块 |
| 3-15 页 | ❌ 不建 TOC | 按段落分块（~300字） |
| < 3 页 | ❌ 不建 TOC | 整文件一个 chunk |

---

## 二、数据库

### 2.1 materials 表（已有）

```sql
-- purpose: 'session' | 'library'  (默认 'session')
-- 已包含：material_id, user_id, file_name, file_type, file_size,
--         storage_path, status, chunk_count, skills_covered_json
```

### 2.2 material_chunks 表（已有，增强）

```sql
-- 新增字段：
--   toc_id         TEXT        -- 关联的目录节点 ID
--   heading_path   TEXT        -- 面包屑 "第1章 > 1.2 > 数列极限"
--   page_number    INTEGER     -- 起始页码（MarkItDown 可提取）
```

### 2.3 material_toc 表（新增）

```sql
CREATE TABLE IF NOT EXISTS material_toc (
    toc_id          TEXT PRIMARY KEY,
    material_id     TEXT NOT NULL REFERENCES materials(material_id) ON DELETE CASCADE,
    parent_toc_id   TEXT,                    -- 父节点 ID，根节点为 NULL
    level           INTEGER NOT NULL,         -- 1=H1, 2=H2, 3=H3
    heading         TEXT NOT NULL,            -- 标题文本
    heading_md      TEXT,                     -- 原始 Markdown 标题
    chunk_start     INTEGER,                  -- 首个 chunk 序号
    chunk_end       INTEGER,                  -- 末个 chunk 序号
    page_start      INTEGER,                  -- 起始页码
    embedding       vector(1536),             -- heading + 首段内容的 embedding
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_toc_material ON material_toc(material_id);
CREATE INDEX idx_toc_parent ON material_toc(parent_toc_id);
CREATE INDEX idx_toc_embedding ON material_toc USING ivfflat (embedding vector_cosine_ops);
```

---

## 三、索引流水线

### 3.1 完整流程

```
上传文件
  │
  ├─ 1. 保存到磁盘
  │     ~/.companion/uploads/{user_id}/{material_id}.ext
  │
  ├─ 2. 后台异步解析 (asyncio.create_task)
  │
  ├─ 3. MarkItDown 转换
  │     md = MarkItDown()
  │     result = md.convert(path)
  │     raw_md = result.markdown
  │
  ├─ 4. 按文件规模分流
  │     ├─ 大文件 → TOC 提取 + 按标题分块
  │     └─ 小文件 → 按段落分块
  │
  ├─ 5. Embedding
  │     ├─ chunk.text → embedding → material_chunks
  │     └─ heading + 首段 → embedding → material_toc
  │
  └─ 6. 更新 materials.status = 'indexed'
```

### 3.2 TOC 提取算法

```python
def extract_toc(markdown_text: str) -> list[TOCNode]:
    """
    解析 Markdown 标题层级生成目录树。
    注意：不使用 LLM 生成摘要，直接拿 heading + 首段内容 embedding。
    """
    nodes = []
    stack = []
    for line in markdown_text.split('\n'):
        m = re.match(r'^(#{1,6})\s+(.+)$', line)
        if m:
            level = len(m.group(1))
            heading = m.group(2).strip()
            node = TOCNode(level=level, heading=heading)
            # 维护父子关系
            while stack and stack[-1].level >= level:
                stack.pop()
            node.parent = stack[-1] if stack else None
            stack.append(node)
            nodes.append(node)
    return nodes
```

### 3.3 分块策略

```python
def chunk_markdown(md_text: str, toc_nodes: list[TOCNode]) -> list[Chunk]:
    """
    按标题分块。每个 ### 及其正文为一个 chunk。
    超过 1000 字的 chunk 内再按空行分割。
    每个 chunk 记录 heading_path。

    小文件/无 TOC 文件：按空行+段落分块。
    """
```

### 3.4 Embedding 策略

```python
# TOC 节点：heading + 首段前 200 字
toc_embedding = compute_embedding(f"{heading}\n{first_chunk_text[:200]}")

# 内容 chunk：heading_path + 正文
chunk_embedding = compute_embedding(f"{heading_path}\n{chunk_text}")
```

**关键设计**：搜索永远一层，把路径信息拍平到 chunk 内。TOC 是给「人」看的导航，不是给「机器」搜的索引。

---

## 四、搜索与 RAG

### 4.1 搜索 API

```python
POST /api/files/search
{
    "query": "夹逼定理",
    "purpose": "library",          # 过滤知识库
    "material_ids": [...],         # 限定文件（可选）
    "top_k": 10,
}
→ [
    {
        "text": "...",
        "heading_path": "第1章 > 1.2 > 数列极限",
        "material_id": "...",
        "material_name": "高等数学.pdf",
        "toc_id": "...",
        "page": 28,
        "score": 0.87,
    }
]
```

### 4.2 RAG 注入条件

```python
# 搜索结果为 top-5 chunks
# 注入条件：top-1.score < 0.35（余弦距离）
# 满足 → 注入 system prompt，要求 AI 标注来源
# 不满足 → 不注入，AI 按自身知识回答

SYSTEM_PROMPT = """以下是你可引用的资料内容：

--- 资料：{material_name} ---
[{heading_path}]
{chunk_text}

---

请基于以上资料回答用户问题。引用具体内容时标注「[来源：章节名]」。
如果资料中没有足够信息，直接说「资料中未找到相关信息」，不要编造。
"""
```

---

## 五、API 端点

### 5.1 文件 CRUD

| 方法 | 端点 | 用途 |
|------|------|------|
| POST | `/api/files/upload` | 上传文件，自动分类 purpose |
| GET | `/api/files` | 文件列表（分页，按 purpose/status/类型过滤） |
| GET | `/api/files/{id}` | 文件详情 + 索引状态 |
| DELETE | `/api/files/{id}` | 删除文件 + 级联删除 chunks + toc |
| PATCH | `/api/files/{id}` | 修改 purpose / 文件名 |

### 5.2 文件内容

| 方法 | 端点 | 用途 |
|------|------|------|
| GET | `/api/files/{id}/toc` | 返回目录树 |
| GET | `/api/files/{id}/chunks` | 分块列表（按 toc_id 过滤） |

### 5.3 搜索与生成

| 方法 | 端点 | 用途 |
|------|------|------|
| POST | `/api/files/search` | 语义搜索（全文 + 向量混合） |
| POST | `/api/files/generate-practice` | 基于文件分块生成练习题 |

### 5.4 清理

| 方法 | 端点 | 用途 |
|------|------|------|
| POST | `/api/files/cleanup` | 清理过期 session 文件 |

---

## 六、前端页面

### 6.1 页面路由

```
/files                   → 文件管理首页（双 tab）
/files/{material_id}     → 文件详情页（目录树 + 分块预览）
```

### 6.2 页面布局

```
/files:
┌──────────────────────────────────────────────┐
│ 📁 资料库              [+ Upload]  🔍 Search │
├──────────────────────────────────────────────┤
│ [📁 知识库] [📋 临时文件]  [全部] [PDF] [DOC] │
├──────────────────────────────────────────────┤
│ ┌─ 📄 高等数学.pdf ────────────────────────┐ │
│ │  12MB · 42分块 · 15章 · 已索引 ✅       │ │
│ │  2026-06-27  [查看] [生成练习] [✕]      │ │
│ └────────────────────────────────────────┘ │
│ ┌─ 📄 笔记.docx ──────────────────────────┐ │
│ │  2MB · 5分块 · 已索引 ✅               │ │
│ └────────────────────────────────────────┘ │
└──────────────────────────────────────────────┘

/files/{id}:
┌──────────────────────────────────────────────┐
│ 📄 高等数学.pdf          [📁 知识库] 已索引  │
│ 12MB · 15章 · 42分块                        │
├──────────────────────────────────────────────┤
│ 📖 目录                       🔍 搜索本文件  │
│                                          │
│  ─┬─ 第1章 函数与极限                      │
│   ├── 1.1 映射与函数          3个分块       │
│   ├── 1.2 数列的极限          2个分块       │
│   └── 1.3 函数的极限          2个分块       │
│  ─┬─ 第2章 导数与微分                      │
│  ─┬─ 第3章 微分中值定理                    │
├──────────────────────────────────────────────┤
│ [从文件生成练习] [关联到知识图谱] [删除文件]  │
└──────────────────────────────────────────────┘
```

---

## 七、实施路线

| # | 任务 | 文件 | 依赖 |
|:-:|------|------|:----:|
| 1 | MarkItDown 替换 parser | `material_parser.py` | — |
| 2 | 建 material_toc 表 | `learning_schema.sql` | — |
| 3 | TOC 提取引擎 | **新** `material_toc_extractor.py` | 1 |
| 4 | 重写索引器 | `material_indexer.py` | 1,2,3 |
| 5 | 重写搜索器 | `material_search.py` | 1,2,3,4 |
| 6 | `/api/files/*` API | **新** `files_api.py` | 4,5 |
| 7 | 前端 `/files` 页面 | 4 个新文件 | 6 |
| 8 | RAG 注入对话 | `conversation_llm.py` | 5 |
| 9 | 路由注册 | `main.py` | 6 |
