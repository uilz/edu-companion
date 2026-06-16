# ADR 0018: 文件系统对对话/练习系统的支持分析 (Round 3 Step 5)

> 生成日期: 2026-06-16 | 状态: Draft
> 前置: ADR 0014-0017
> 目标: 分析文件系统如何支撑对话系统(RAG) + 练习系统(出题/错题), 找出断裂点与扩展机会

---

## 1. 对话系统支持现状

### 1.1 RAG 资料注入 (核心功能)

#### context_builder.py (旧架构, L370-387)

```
用户输入 text
  → material_search.search_sync(user_id, query, top_k=3)
  → should_inject_rag(results)  → best_score < 0.35
  → format_rag_context(results) → "--- 资料: 文件名 []\n文本"
  → system_prompt 末尾追加:
    "📚 以下是你可引用的资料内容（来自用户的知识库）：\n{rag_ctx}\n请基于以上资料回答..."
  → 拼接消息: [system(含RAG)] + [history(8条)] + [user]
```

#### context_pipeline.py (新架构, TutorCapability, L602-623)

```
输入 input.user_text
  → material_search.search_sync(user_id, query, top_k=3)
  → should_inject_rag(results)  → best_score < 0.35
  → format_rag_context(results) → "--- 资料: 文件名 []\n文本"
  → ContextPayload(render="{parts拼接}", key="capability")
  → 最终合并到 system prompt
```

#### 两处 RAG 注入的代码完全相同 (复制粘贴), 新架构将其封装为 Provider

### 1.2 当前 RAG 注入的缺陷

| 问题 | 严重性 | 描述 |
|------|--------|------|
| R1. heading_path 恒空 | 中 | `search_sync()` 返回 heading_path="" → RAG 上下文格式为 `--- 资料: 文件名` → LLM 看不到标题层次 |
| R2. 回退返回 [] | 中 | embedding 失败时 `search_sync()` 回退返回 [] → `should_inject_rag()` false → 无 RAG |
| R3. 仅 top_k=3 | 低 | 固定3条, 小文件可能覆盖不全, 大文件仅覆盖3个chunk |
| R4. 无跳过逻辑 | 低 | 每次对话都做向量搜索, 即使问题与资料无关 |
| R5. 搜索结果不缓存 | 低 | 相同问题每次重新搜 |
| R6. 无 conversation/partition 过滤 | 低 | 搜索全库 library, 不限定当前学习节点 |
| R7. RAG prompt 有[heading]占位但恒空 | 中 | `format_rag_context()` 模板 `--- 资料：{material_name} [{heading_path}]` → heading_path 始终是 [] |

### 1.3 workspace 文件系统 — 完全隔离

```
对话工作空间: conversation_routes.py:773-870

WORKSPACE_BASE = ~/.companion/uploads/{user_id}/{conv_id}/
  ├── images/     ← 图片文件
  ├── audio/      ← 音频文件
  ├── video/      ← 视频文件
  └── documents/  ← 文档文件

存储: FileRecord → UserData.files (conversation_user_meta JSONB)
搜索: 不可搜索 (无 embedding, 无全文索引)
生命周期: 对话级, 随对话保留
```

| 问题 | 严重性 | 描述 |
|------|--------|------|
| W1. 两种文件系统隔离 | 高 | workspace 文件不可被 RAG 搜索, 用户上传到对话的文件无法被 AI 引用 |
| W2. workspace 文件无索引 | 中 | 无 MarkItDown 解析, 无 chunking, 无 embedding |
| W3. 无类型限制 | 低 | workspace 接受任意 mime 类型, 但只分了4类目录 |
| W4. 存储路径重复 | 低 | WORKSPACE_BASE 与 COMPANION_HOME 不同, 但都是 ~/.companion/ |

### 1.4 context_trigger.py — 间接媒体引用

```
context_trigger.py:
  生成 [Media: B站搜索"xxx"] 提示 → 对话卡片
  不直接调文件系统, 通过 media_search.py 生成搜索 URL
```

---

## 2. 练习系统支持现状

### 2.1 出题场景 (当前可用)

#### practice_question_gen.py — 基于素材出题

```python
get_material_context(user_id, material_ids=None, limit=5):
  if material_ids:
    SQL: SELECT mc.text, mc.material_id, m.file_name
         FROM material_chunks mc JOIN materials m
         WHERE mc.material_id IN ({material_ids})
         LIMIT 5
  else:
    SQL: SELECT mc.text, mc.material_id, m.file_name
         FROM material_chunks mc JOIN materials m
         WHERE mc.user_id=%s AND m.status='indexed'
         ORDER BY RANDOM() LIMIT 5
  → 拼接 context = "\n--- 资料: {file_name}\n{text[:2000]}"
  → 传给 LLM 出题 prompt
```

#### manage.py POST /api/files/generate-practice

```python
SQL: SELECT text, material_id FROM material_chunks
     WHERE material_id IN ({material_ids}) LIMIT 30
→ context = "\n\n".join(text[:1000] for r in rows[:5])
→ LLM 生成 {count} 道题 (choice + short)
```

#### practice_question_bank.py — 题库关联资料

```python
SQL: SELECT DISTINCT m.material_id, m.file_name
     FROM materials m JOIN material_chunks mc
     WHERE m.user_id=%s AND m.status='indexed'
     AND ...(按知识点过滤)
```

### 2.2 断裂点 P0 (运行时崩溃)

| 问题 | 严重性 | 位置 | 影响 |
|------|--------|------|------|
| P1. `search_by_skill()` 不存在 | P0 | `practice_integrator.py:97` | 练习完成→总结带资料引用 → **崩溃 500** |
| P2. `material_meta` 表不存在 | P0 | `practice_error_book.py:282` | 错题本→推荐复习资料 → **崩溃 500** |

#### P1 详细: practice_integrator.py:92-107

```
练习结果写入后, 做"资料引用"后处理:
  for skill in session.struggling_skills[:3]:
    chunks = await ms.search_by_skill(user_id, skill, top_k=2)
             ^^^^^^^^^^^^^^^^^^ 方法不存在!
  → except 捕获, log warning
  → 不崩溃, 但资料引用永远为空
```

#### P2 详细: practice_error_book.py:278-296

```
错题推荐复习资料:
  SQL: SELECT m.id, m.filename FROM material_meta m WHERE ...
                               ^^^^^^^^^^^^ 表不存在!
  → except 捕获, pass
  → 推荐资料永远为空
```

### 2.3 功能缺失

| 问题 | 严重性 | 描述 |
|------|--------|------|
| Q1. 资料关联题库不可见 | 中 | file detail page 看不到"此文件生成了哪些题" |
| Q2. 无 material←→question 关联表 | 中 | manage.py 出题不记录关联, 不可追溯 |
| Q3. 出题 material_ids 只取5块 | 低 | 大文件只取前5 chunk, 可能遗漏重点 |
| Q4. 仅出题用chunks, 不出题用TOC | 低 | 有 TOC 结构但不利用来组织题目 |
| Q5. 错题→资料推荐缺语义搜索 | 中 | 当前用旧表 skill_covered && node_ids, 应改用向量搜索 |
| Q6. 无"错题生成新练习"的素材关联 | 低 | 错题→找相关文件→出相似题, 链路断裂 |

---

## 3. 对话系统改进方案

### 3.1 修复 (低风险)

| # | 改动 | 涉及 | 影响 |
|---|------|------|------|
| D1 | `material_search.search_sync()` 返回 heading_path | `material_search.py:263` 增加 heading_path 查询 | RAG 上下文展示 "资料: 文件名 [第一章>第二节]" |
| D2 | `material_search.search_sync()` 回退做全文搜索 | `material_search.py:263` 改用 fallback 同 async 版 | embedding 缺失时不丢 RAG |
| D3 | RAG 格式增强 heading_path | `format_rag_context.py:189` 已有模板 | 配合 D1 即可显示 |

#### D1 代码改动

```
material_search.py:263 → search_sync() SQL 增加 heading_path 列
  SELECT ... mc.heading_path  ← 当前 SELECT 不包含此列
```

### 3.2 增强 (中等)

| # | 改动 | 说明 |
|---|------|------|
| D4 | workspace 文件自动导入 materials | 上传 workspace 文件后, 异步调 `POST /api/files/upload` 或直接索引 |
| D5 | RAG 搜索限定当前 partition/node | `search_sync()` 增加 `cognitive_node_ids` 过滤 |
| D6 | RAG 结果缓存: LRU 缓存搜索结果 | 相同 query 在 N 秒内命中缓存 |
| D7 | 增加 skip-RAG 启发式 | 简短问题/打招呼跳过向量搜索 |
| D8 | context_pipeline 统一 RAG Provider | 消除 context_builder 中的重复代码 |

#### D5 代码示意

```
search_sync(user_id, query, top_k=3, node_ids=None):
  SQL: WHERE ... AND m.status='indexed'
       [AND m.skills_covered_json @> %s]   # node_ids 过滤
```

### 3.3 高价值 (高复杂度)

| # | 改动 | 说明 |
|---|------|------|
| D9 | 对话中"/search 关键词" 触发语义搜索返回结果卡片 | 类 CMD 模式 |
| D10 | 文件→分块→直接引用到对话 | 用户选中分块, 作为对话消息附件 |
| D11 | workspace + materials 统一存储 | 迁移 workspace 文件到 materials 体系 |

---

## 4. 练习系统改进方案

### 4.1 P0 修复 (最高优先级)

| # | 改动 | 文件 | 行 |
|---|------|------|-----|
| E1 | 修复 `search_by_skill` → 改用 `search_sync` | `practice_integrator.py:97` | `chunks = await ms.search(user_id, query=skill, top_k=2)` |
| E2 | 修复 `material_meta` → 改用 `materials` 表 | `practice_error_book.py:280-285` | `SELECT material_id, file_name, file_type, file_size, created_at FROM materials WHERE user_id=%s AND skills_covered_json ?| array[...] LIMIT %s` |

#### E1 具体修复

```python
# practice_integrator.py:92-107 改为:
for skill in (session.struggling_skills or [])[:3]:
    # 用语义搜索替代不存在的 search_by_skill
    chunks = await ms.search(user_id, query=skill, top_k=2)
    for c in chunks:
        src = c.get("material_name", c.get("source_file", "未知"))
        pg = c.get("page_number")
        label = f"{src} p{pg}" if pg else src
        enriched.append(label)
```

#### E2 具体修复

```python
# practice_error_book.py:278-296 改为:
rows = db.fetchall(
    """SELECT m.material_id as id, m.file_name as filename,
              m.file_type, m.file_size, m.created_at
       FROM materials m
       WHERE m.user_id = %s AND m.status = 'indexed'
         AND m.skills_covered_json IS NOT NULL
         AND m.skills_covered_json != '[]'
         AND EXISTS (
           SELECT 1 FROM jsonb_array_elements_text(m.skills_covered_json) sk
           WHERE sk = ANY(%s)
         )
       ORDER BY m.created_at DESC LIMIT %s""",
    (user_id, node_ids, limit),
)
```

### 4.2 增强 (中等)

| # | 改动 | 说明 |
|---|------|------|
| E3 | 建立 `practice_from_material` 关联表 | `practice_question_gen.py` 出题后记录 material_id ↔ question_id 关联 |
| E4 | 出题时按 TOC 结构化组织 | 大文件按 TOC 章节依次出题, 覆盖所有章节 |
| E5 | 错题推荐改用向量搜索 | `practice_error_book.py` 错题 description / skill → `material_search.search()` |
| E6 | 文件详情页展示"关联题目" | 新 API `GET /api/files/{id}/related-questions` |

#### E3 关联表设计

```sql
CREATE TABLE IF NOT EXISTS practice_material_questions (
    id SERIAL PRIMARY KEY,
    material_id TEXT NOT NULL REFERENCES materials(material_id) ON DELETE CASCADE,
    question_id TEXT NOT NULL,
    chunk_index INTEGER,
    user_id TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(material_id, question_id)
);
```

### 4.3 高价值 (高复杂度)

| # | 改动 | 说明 |
|---|------|------|
| E7 | "错题→素材→类似题" 闭环 | 错题→提取 skill→向量搜索相关 chunk→LLM 生成相似题, 自动加入 practice_session |
| E8 | 基于素材自动生成题库 | 对一组文件 batch 调 generate-practice, 自动创建题库 |
| E9 | 素材掌握度追踪 | 从 practice_attempts 统计各 material 相关题目的正确率 |

---

## 5. 对话+练习统一改进路线图

### 5.1 优先级矩阵

| 优先级 | 对话系统 | 练习系统 | 共享 |
|--------|----------|----------|------|
| **P0 (崩坏)** | — | E1 search_by_skill, E2 material_meta | — |
| **P1 (质量)** | D1 heading_path, D2 全文回退, D3 格式修复 | E3 关联表, E4 TOC 出题 | 统一 RAG+出题素材 |
| **P2 (体验)** | D4 workspace 导入, D5 node 过滤 | E6 关联题目API | 知识图谱关联文件 |
| **P3 (进阶)** | D6 缓存, D7 skip-RAG, D8 Provider | E7 闭环, E8 自动题库 | 综合学习引擎 |

### 5.2 当前对话系统数据流 (修复后)

```
用户输入 text
  → material_search.search_sync(user_id, text, top_k=3, node_ids=current_node_ids)
  → compute_embedding(text[:2000])
  → 成功: PostgreSQL cosine 搜索 (含 heading_path)
  → 失败: to_tsvector @@ plainto_tsquery 全文搜索
  → should_inject_rag() → score < 0.35
  → format_rag_context() → "--- 资料: 文件名 [第一章>第二节]\n文本"
  → system_prompt 注入 → LLM 回复
```

### 5.3 当前练习系统数据流 (修复后)

```
出题请求 (material_ids)
  → SELECT chunks WHERE material_id IN (...) LIMIT 30
  → 按 TOC 组织: 每章选前3块 → LLM 每章出1-2题
  → INSERT question + INSERT practice_material_questions(material_id, question_id)
  → 返回题目

错题推荐:
  → 错题 skill → material_search.search(user_id, query=skill, top_k=3)
  → 过滤 status='indexed'
  → 返回 related materials → 用户可选"以此素材出练习题"

练习总结:
  → struggling_skills → material_search.search (语义搜索)
  → enrich practice_summary with material references
```

---

## 6. 对话系统 + 练习系统 当前集成全景图

```
┌────────────────────────────────────────────────────────────────────┐
│                        文件系统 (materials)                        │
│  ┌──────────┐  ┌───────────────┐  ┌─────────────────────────┐    │
│  │ materials │  │material_chunks│  │ material_toc            │    │
│  │ 元数据    │  │ 分块+embedding │  │ 目录树                  │    │
│  └────┬─────┘  └───────┬───────┘  └────────┬────────────────┘    │
│       │                │                   │                     │
└───────┼────────────────┼───────────────────┼─────────────────────┘
        │                │                   │
  ┌─────┴─────┐   ┌──────┴────────┐   ┌─────┴──────────┐
  │对话系统    │   │练习系统       │   │独立 workspace   │
  │RAG注入     │   │出题           │   │(对话文件)       │
  │search_sync│   │SELECT chunks  │   │FileRecord       │
  │top_k=3    │   │LIMIT 5-30     │   │→ UserData.files │
  │threshold  │   │→ LLM生成题   │   │❌ 不可搜索      │
  │0.35       │   │               │   │❌ 无索引        │
  │→ system   │   │错题→推荐资料  │   │                │
  │  prompt   │   │❌ search_by_  │   │                │
  │           │   │   skill 崩溃  │   │                │
  │           │   │❌ material_   │   │                │
  │           │   │   meta 表崩溃 │   │                │
  │           │   │               │   │                │
  │           │   │关联题目(缺)    │   │                │
  └───────────┘   └───────────────┘   └────────────────┘
```

---

## 7. 改动总结

### 7.1 对话系统: 3修复 + 4增强 + 2进阶

| 编号 | 改动 | 估计行 | 风险 | 优先级 |
|------|------|--------|------|--------|
| D1 | search_sync 返回 heading_path | ~5行 | 低 | P1 |
| D2 | search_sync 回退全文搜索 | ~30行 | 低 | P1 |
| D3 | RAG 格式修复 | ~2行 | 低 | P1 |
| D4 | workspace→materials 导入 | ~40行 | 中 | P2 |
| D5 | node_ids 过滤 | ~15行 | 低 | P2 |
| D6 | LRU 缓存 | ~20行 | 低 | P3 |
| D7 | skip-RAG 启发式 | ~10行 | 低 | P3 |
| D8 | 统一 RAG Provider | ~30行 | 中 | P3 |

### 7.2 练习系统: 2修复 + 4增强 + 3进阶

| 编号 | 改动 | 估计行 | 风险 | 优先级 |
|------|------|--------|------|--------|
| E1 | search_by_skill→search | ~5行 | 低 | **P0** |
| E2 | material_meta→materials | ~10行 | 低 | **P0** |
| E3 | 关联表 + 写入 | ~30行 | 低 | P1 |
| E4 | TOC 组织出题 | ~40行 | 中 | P1 |
| E5 | 错题向量搜索 | ~20行 | 低 | P2 |
| E6 | API: 关联题目 | ~30行 | 低 | P2 |
| E7 | 闭环: 错题→素材→类似题 | ~60行 | 高 | P3 |
| E8 | 自动生成题库 | ~40行 | 中 | P3 |
| E9 | 素材掌握度追踪 | ~50行 | 中 | P3 |

---

## 8. Step 5 决策记录 (2026-06-16 讨论确认)

| 决策 | 结论 | 参考 |
|------|------|------|
| S5-Q1. search_by_skill 修复 | 改为 `ms.search(user_id, query=skill, top_k=2)` 语义搜索 | ADR 0019 |
| S5-Q2. material_meta 修复 | 改为 `SELECT material_id, file_name FROM materials WHERE skills_covered_json @>` | ADR 0019 |
| S5-Q3. 出题关联记录 | 新建 `practice_material_questions` 关联表 (material_id, question_id, user_id) | ADR 0019 |
| S5-Q4. RAG 限定 node_ids | search_sync 增加 `node_ids` 参数, JOIN cognitive_nodes 过滤 | ADR 0019 |
| S5-Q5. RAG 回退统一 | context_pipeline TutorCapability 成为唯一 RAG Provider, context_builder 废弃 | ADR 0019 |