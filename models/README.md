# 本地模型文件

本目录存放智能伴学系统运行所需的本地模型文件。
模型文件**不纳入 Git 管理**（`.gitignore` 已忽略），需手动下载到此处。

---

## 模型清单

| 模型 | 用途 | 位置 | 维数 | 来源 |
|------|------|------|:----:|------|
| `granite-embedding-97m-multilingual-r2` | 文本嵌入（语义搜索、RAG、分类） | `models/granite-embedding-97m/` | 384 | [HuggingFace](https://huggingface.co/ibm-granite/granite-embedding-97m-multilingual-r2) |

其他模型（LLM、TTS、Whisper ASR 等）均通过 API 调用，无需本地下载。

---

## 🚀 新服务器部署指南

### 1. 下载模型

```bash
# 方式 A：huggingface-cli（推荐）
huggingface-cli download ibm-granite/granite-embedding-97m-multilingual-r2 \
  --local-dir models/granite-embedding-97m

# 方式 B：国内镜像加速
HF_ENDPOINT=https://hf-mirror.com huggingface-cli download \
  ibm-granite/granite-embedding-97m-multilingual-r2 \
  --local-dir models/granite-embedding-97m
```

### 2. 安装 Python 依赖

```bash
# 仅需两个轻量包（无需 PyTorch / sentence-transformers）
pip install openvino tokenizers numpy
```

| 包 | 大小 | 用途 |
|----|------|------|
| `openvino` | ~58MB | OpenVINO 推理引擎，加载 `.xml/.bin` 量化模型 |
| `tokenizers` | ~3MB | Rust BPE tokenizer，加载 `tokenizer.json` |
| `numpy` | ~10MB | 数组运算（通常已安装） |

> **不需要** PyTorch (~2GB)、sentence-transformers (~500MB)、transformers (~200MB)

### 3. 验证

```bash
cd backend
python3 -c "
from app.services.common.embedding_utils import compute_embedding, cosine_similarity
v = compute_embedding('测试文本')
print(f'✅ dim={len(v)}, self-sim={cosine_similarity(v,v):.4f}')
"
# 预期输出: ✅ dim=384, self-sim=1.0000
```

---

## 嵌入模型架构

### 技术栈

- **模型**: IBM Granite Embedding 97M (multilingual, R2, ModernBERT)
- **运行时**: OpenVINO 直接加载 `openvino_model.xml` + `openvino_model.bin`
- **维度**: 384（存入 `material_chunks.embedding DOUBLE PRECISION[]`）
- **加载位置**: `backend/app/services/classifier.py` → `compute_embedding()`
- **调用方**: `material_indexer.py`（索引时）、`material_search.py`（搜索时）、`context_builder.py`（RAG 注入时）

### 路径解析

```python
# classifier.py 路径逻辑（延迟加载、全局单例）
model_path = Path(__file__).resolve().parent.parent.parent.parent / "models" / "granite-embedding-97m"
# classifier.py → services/ → app/ → backend/ → 项目根 → models/granite-embedding-97m/
```

### 推理流程

```
文本 → BPE Tokenizer(180k vocab, 512截断) → input_ids + attention_mask
     → OpenVINO compiled_model → output (1,3,384)
     → 取最后一维 (normalized embedding) → 384-dim float list
```

### 在系统中的用途

- **文件索引**: 上传文件 → MarkItDown 解析 → 分块 → `compute_embedding()` → 存入 `material_chunks.embedding`
- **语义搜索**: 查询 → `compute_embedding()` → PostgreSQL 余弦相似度搜索
- **RAG 注入**: 对话 → 搜索资料 → 相似度阈值过滤 → 注入上下文
- **资料后处理**: 索引完成 → LLM 提取标签+摘要

---

## 存放规则

- **不要**把模型文件提交到 Git（`.gitignore` 已忽略 `models/*`）
- 每个模型放在独立子目录，命名与 HuggingFace repo 名一致
- 如需切换模型，更新 `classifier.py` 中的路径，并相应调整 `material_chunks.embedding` 维度

---

## 参考

- 模型详情: [models/granite-embedding-97m/README.md](granite-embedding-97m/README.md)
- 论文: [Granite Embedding Multilingual R2 (arXiv:2605.13521)](https://arxiv.org/abs/2605.13521)
