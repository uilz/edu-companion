# P5 · 资料→知识图谱联动

> 打破孤岛: 资料↔图谱（上传讲义不关联图谱节点）

---

## 一、目标

上传一份「高等数学笔记.pdf」→ AI 自动识别覆盖了哪些知识点 → 知识图谱对应节点打上 📎 资料标记。

```
知识图谱 — 导数节点
┌─────────────────┐
│ 📎 高等数学笔记   │  ← 点击跳转到资料对应页码
│    · 第23-28页    │
│ 📎 习题集-ch3    │
│    · 第5-10页     │
└─────────────────┘
```

---

## 二、实现方案

### 2.1 后端：LLM 知识点匹配

资料上传后（已有 `material_parser` → `material_indexer` 流程），新增异步步骤：

```python
# 资料→图谱匹配
async def match_to_graph(material_id, chunks):
    # 1. 提取资料的关键概念
    concepts = extract_key_concepts(chunks)  # LLM调用
    
    # 2. 匹配到知识图谱节点
    matched_skills = []
    for concept in concepts:
        skill = fuzzy_match(concept, ALL_PREREQUISITES)  # 名称模糊匹配
        if skill:
            matched_skills.append(skill)
    
    # 3. 存储关联
    save_material_skill_links(material_id, matched_skills)
```

### 2.2 API 增强

| 端点 | 变更 |
|------|------|
| `POST /api/material/upload` | 上传完成后异步触发图谱匹配 |
| `GET /api/knowledge/graph` | 节点返回关联资料列表 |

### 2.3 前端

`/graph` 页面 — 点击节点时已有详情面板 → 新增「📎 关联资料」区域。

---

## 三、数据存储

```
material_skill_links 表:
  material_id → [skill_id, ...]
  
知识图谱节点返回:
  { ..., "materials": [{"name": "高等数学笔记.pdf", "pages": "23-28"}] }
```

---

## 四、验收

- [ ] 上传一份包含「导数」内容的 PDF
- [ ] 导数节点详情中显示该资料
- [ ] 点击资料跳转到 /materials 对应条目
- [ ] 无匹配的资料不显示关联
