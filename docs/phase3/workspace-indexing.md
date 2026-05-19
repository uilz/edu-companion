# P6 · 工作空间文件索引

> 打破孤岛: 工作空间↔搜索↔知识图谱（当前只有上传/下载，无内容识别）

---

## 一、目标

分支工作空间当前功能：上传文件 → 存盘 → 列表/下载/删除。

Phase 3 升级：上传文件 → **自动提取文本内容 → 建立索引 → 全文搜索 → 关联知识图谱**。

---

## 二、完整链路

```
用户上传「lecture5-导数.pdf」到 branch workspace
  → 1. 存储文件 (已有)
  → 2. 内容提取: PDF → text (新增)
  → 3. 建立全文索引: text → inverted index (新增)
  → 4. LLM 知识点识别: text → [导数, 微分, 极限] (新增)
  → 5. 关联知识图谱: 对应节点 +📎 (新增, 见 P5)
  → 6. 接入全站搜索 (新增, 见 P1)
```

---

## 三、技术方案

### 3.1 内容提取

```python
# 新增: backend/app/services/workspace_indexer.py

def extract_text(file_path: str, file_type: str) -> str:
    """提取文件文本内容"""
    if file_type == "pdf":
        import pymupdf
        doc = pymupdf.open(file_path)
        return "\n".join(page.get_text() for page in doc)
    elif file_type in ("docx", "doc"):
        # python-docx
        ...
    elif file_type in ("txt", "md"):
        return open(file_path).read()
    elif file_type in ("py", "js", "ts", "tsx", "json", "yaml"):
        return open(file_path).read()  # 代码文件也索引
```

### 3.2 全文索引

```python
# 简单的内存倒排索引（MVP）
index: dict[str, set[str]] = {}  # word → {file_id, ...}

def index_file(file_id: str, text: str):
    words = tokenize(text)
    for word in words:
        if word not in index:
            index[word] = set()
        index[word].add(file_id)

def search(query: str) -> list[str]:
    words = tokenize(query)
    results = set()
    for word in words:
        results |= index.get(word, set())
    return list(results)
```

### 3.3 LLM 知识点识别

```python
async def identify_knowledge_points(text: str) -> list[str]:
    """从文本中识别涉及的知识点"""
    prompt = f"""
    这段文本涉及以下哪些知识点？
    可选: {list(ALL_PREREQUISITES.keys())}
    
    文本: {text[:2000]}
    
    返回 JSON: {{"skills": ["calculus_derivative", ...]}}
    """
    result = await llm_call(prompt)
    return result["skills"]
```

---

## 四、新增 API

| 端点 | 用途 |
|------|------|
| `POST /api/conversation/workspace/index/{file_id}` | 触发文件索引 |
| `GET /api/conversation/workspace/search?q=&branch_id=` | 搜索工作空间文件 |

### 修改现有 API

- `POST /api/conversation/workspace/upload` → 上传后自动触发索引（异步后台任务）

---

## 五、前端增强

### WorkspacePanel 升级

```
当前:
  WorkspacePanel
  └── 文件列表 (名称·大小·时间·删除按钮)

升级后:
  WorkspacePanel
  ├── 🔍 搜索框
  ├── 文件列表
  │   ├── lecture5.pdf  [已索引✅]
  │   ├── notes.txt      [已索引✅]
  │   └── photo.jpg      [未索引 — 图片不支持]
  └── 文件详情
      ├── 关联知识点: [导数] [极限]
      └── 内容预览 (前200字)
```

---

## 六、验收

- [ ] 上传 PDF → 自动索引 → 显示「已索引✅」
- [ ] 搜索工作空间 → 找到包含关键词的文件
- [ ] LLM 识别出文件涉及的知识点 → 关联到图谱
- [ ] 图片/二进制文件 → 「不支持索引」
- [ ] 索引失败 → 显示错误但不阻塞上传
