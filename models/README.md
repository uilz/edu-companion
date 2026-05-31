# 本地模型文件

本目录存放智能伴学系统 v6 运行所需的本地模型文件。
模型文件**不纳入 Git 管理**（`.gitignore` 已忽略），需手动下载到此处。

---

## 模型清单

| 模型 | 用途 | 位置 | 维数 | 来源 |
|------|------|------|:----:|------|
| `granite-embedding-97m-multilingual-r2` | 文本嵌入（语义搜索、分类、波纹边检测） | `models/granite-embedding-97m/` | 384 | [HuggingFace](https://huggingface.co/ibm-granite/granite-embedding-97m-multilingual-r2) |

其他模型（Whisper ASR、TTS、LLM 等）均通过 API 调用，无需本地下载。

---

## 嵌入模型架构

### 技术栈

- **模型**: IBM Granite Embedding 97M (multilingual, R2)
- **运行时**: OpenVINO（已转换，无需 PyTorch/ONNX）
- **维度**: 384（`pgvector VECTOR(384)`）
- **引擎**: `backend/scripts/embedding_engine.py`

### 路径解析

`embedding_engine.py` 通过 `os.path.join(main_dir, "models", "granite-embedding-97m")` 自动定位，
`main_dir` 为 `backend/scripts/` 的父目录，即项目根 `/home/deploy/edu-companion/`。

```python
# embedding_engine.py 路径逻辑
main_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
model_path = os.path.join(main_dir, "models", "granite-embedding-97m")
```

### 在 v6 中的用途

- **Phase 3**: 消息写入时异步生成 embedding，存入 `messages.embedding`
- **Phase 5**: 分类器分层向量检索（`vector_search()`），topic→concept/atom 递归
- **Phase 6**: 波纹边检测（`_handle_NodeCreated` → 语义邻居检索 → `knowledge_edges`）

---

## 下载命令

```bash
huggingface-cli download ibm-granite/granite-embedding-97m-multilingual-r2 \
  --local-dir models/granite-embedding-97m
```

### 国内镜像加速

```bash
HF_ENDPOINT=https://hf-mirror.com huggingface-cli download \
  ibm-granite/granite-embedding-97m-multilingual-r2 \
  --local-dir models/granite-embedding-97m
```

---

## 存放规则

- **不要**把模型文件提交到 Git（`.gitignore` 已忽略 `models/*` 和 `backend/models/*`）
- 每个模型放在独立子目录，命名与 HuggingFace repo 名一致
- 如需切换模型，更新 `embedding_engine.py` 中的路径和 `cognitive_nodes` 的 `VECTOR(n)` 维度
