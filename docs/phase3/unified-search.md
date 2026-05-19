# P1 · 全站统一搜索

> 打破孤岛: 搜索×4（对话·资料·知识点·错题）

---

## 一、目标

首页一个搜索框，输入关键词 → 同时返回：

```
🔍 「导数」

📝 对话 (3条)
  · 「导数的定义是什么？」— calculus分区
  · 「怎么求x²的导数？」— calculus分区
  · 「导数应用题求最值」— calculus分区

📄 资料 (2份)
  · 高等数学笔记.pdf — 匹配度 87%
  · 习题集-ch3.pdf — 匹配度 72%

🧠 知识点 (2个)
  · 导数与微分 — 掌握57% 🔶
  · 极限与连续 — 掌握80% ✅

❌ 错题 (1道)
  · 求f(x)=x³的导数 — 概念模糊
```

---

## 二、实现方案

### 2.1 后端：聚合搜索 API

```
GET /api/search?q=导数&user_id=default_user
```

内部并行调用 4 个数据源：

```python
async def unified_search(q, user_id):
    results = await asyncio.gather(
        search_conversations(q, user_id),   # 对话内容模糊匹配
        search_materials(q, user_id),       # 资料语义搜索(已有API)
        search_knowledge(q),                # 知识点名称匹配(已有API)
        search_errors(q, user_id),          # 错题关键词匹配
    )
    return results
```

### 2.2 前端：首页搜索框

```
frontend/src/components/
└── search/
    └── UnifiedSearch.tsx   ← 新建
```

- 首页顶部居中搜索框
- 输入 3 字符后触发（防抖 300ms）
- 结果分 4 个 Tab 展示
- 点击跳转到对应页面

---

## 三、数据源映射

| 类型 | 数据源 | 匹配方式 | 已有 |
|------|--------|---------|:--:|
| 对话 | TreeNode.text_summary | SQL LIKE | ✅ |
| 资料 | material_indexer | 向量相似度 | ✅ |
| 知识点 | SKILL_TO_SUBJECT | 名称模糊匹配 | ✅ |
| 错题 | error_book.question_text | SQL LIKE | ✅ |

---

## 四、新增 API

| 端点 | 用途 |
|------|------|
| `GET /api/search?q=&user_id=` | 聚合搜索入口 |

## 五、验收

- [ ] 搜「导数」→ 4 类结果各 ≥1 条
- [ ] 无结果时显示「未找到相关内容」
- [ ] 点击结果项跳转到正确页面
- [ ] 输入 <3 字符 → 不触发搜索
