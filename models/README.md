# 模型文件下载说明

本目录存放智能伴学系统运行所需的模型文件。出于仓库大小和 Git LFS 的考虑，模型文件**不纳入 Git 管理**，需手动下载到此处。

---

## 模型清单

| 模型 | 用途 | 位置 | 来源 |
|------|------|------|------|
| granite-embedding-97m-multilingual-r2 | 文本嵌入（语义搜索/分类） | `backend/models/granite-embedding-97m/` | [HuggingFace](https://huggingface.co/ibm-granite/granite-embedding-97m-multilingual-r2) |

其他模型（Whisper ASR、TTS、LLM 等）均通过 API 调用，无需本地下载。

---

## 下载命令

```bash
# embedding 模型
huggingface-cli download ibm-granite/granite-embedding-97m-multilingual-r2 \
  --local-dir backend/models/granite-embedding-97m
```

### 国内镜像加速

```bash
HF_ENDPOINT=https://hf-mirror.com huggingface-cli download ...
```

---

## 存放规则

- **不要**把模型文件提交到 Git（`.gitignore` 已忽略 `models/*` 和 `backend/models/*`）
- 每个模型放在独立子目录，命名与 HuggingFace repo 名一致
