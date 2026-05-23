# 模型文件下载说明

本目录存放智能伴学系统运行所需的模型文件。出于仓库大小和 Git LFS 的考虑，模型文件**不纳入 Git 管理**，需手动下载到此处。

**后端推理模型**（Reranker、轻量嵌入等）也统一归入本说明，放置在 `backend/models/` 下。

---

## 下载方式

### 一键脚本（推荐）

```bash
bash scripts/download_models.sh
```

### 手动下载

各模型下载链接及放置路径见下表。

---

## 模型清单

### 前端/公共模型（`models/`）

| 模型 | 用途 | 下载来源 |
|------|------|----------|
| bge-small-zh-v1.5 | 文本嵌入（语义搜索/聚类） | [HuggingFace](https://huggingface.co/BAAI/bge-small-zh-v1.5) |
| bge-large-zh-v1.5 | 高精度文本嵌入 | [HuggingFace](https://huggingface.co/BAAI/bge-large-zh-v1.5) |
| whisper-small | 语音识别（ASR） | [HuggingFace](https://huggingface.co/openai/whisper-small) |
| CosyVoice-300M | 语音合成（TTS） | [ModelScope](https://modelscope.cn/models/iic/CosyVoice-300M) |
| Qwen2.5-7B-Instruct | 对话/答疑核心模型 | [HuggingFace](https://huggingface.co/Qwen/Qwen2.5-7B-Instruct) |

### 后端模型（`backend/models/`）

| 模型 | 用途 | 下载来源 |
|------|------|----------|
| bge-reranker-v2-m3 | 重排序（RAG 精排） | [HuggingFace](https://huggingface.co/BAAI/bge-reranker-v2-m3) |
| all-MiniLM-L6-v2 | 轻量句嵌入 | [HuggingFace](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2) |

> 模型列表会随系统迭代更新，以 `scripts/download_models.sh` 中的最新配置为准。

---

## 下载命令

```bash
# ── 前端/公共模型 ──
huggingface-cli download BAAI/bge-small-zh-v1.5 --local-dir models/bge-small-zh-v1.5
huggingface-cli download BAAI/bge-large-zh-v1.5 --local-dir models/bge-large-zh-v1.5
huggingface-cli download openai/whisper-small --local-dir models/whisper-small
huggingface-cli download Qwen/Qwen2.5-7B-Instruct --local-dir models/Qwen2.5-7B-Instruct

# ── 后端模型 ──
huggingface-cli download BAAI/bge-reranker-v2-m3 --local-dir backend/models/bge-reranker-v2-m3
huggingface-cli download sentence-transformers/all-MiniLM-L6-v2 --local-dir backend/models/all-MiniLM-L6-v2
```

### 国内镜像加速

```bash
HF_ENDPOINT=https://hf-mirror.com huggingface-cli download ...
```

---

## 存放规则

- **不要**把模型文件提交到 Git（`.gitignore` 已忽略 `models/*` 和 `backend/models/*`）
- 每个模型放在独立子目录，命名与 HuggingFace repo 名一致
- 下载完成后运行 `scripts/validate_models.sh` 校验完整性

---

## 配置说明

后端模型路径在 `backend/config/model_paths.py` 中配置，下载后确认路径正确指向 `backend/models/` 下的对应目录。
