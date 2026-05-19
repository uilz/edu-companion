# S6 · 错题智能归因

> 子系统: 精准练习  
> 当前基础: 答题记录有 error_type（careless/concept/calculation），LLM 回答后记录  
> Phase 2 产出: LLM 深度分析错因 · 错因分类自动标签 · 针对性出题 · `/errors` 页增强

---

## 一、设计目标

当前错题本只记录「错了」。不够——需要知道「为什么错」。

| before | after |
|--------|-------|
| 错题列表 + error_type 标签 | 每题可展开 → LLM 分析文字 + 错因雷达 + 针对性推荐 |

---

## 二、错因分类体系

### 2.1 三层错因模型

```
Layer 1: 表象               Layer 2: 根因                  Layer 3: 干预策略
─────────                   ──────────                    ──────────
概念混淆 (concept)    →     前置知识缺失                    → 推荐前置知识点练习
                            概念边界模糊                    → 对比练习（A vs B）
                            知识点遗忘                      → 艾宾浩斯复习提醒

计算失误 (calculation) →   符号拿错                        → 相似符号对比题
                            步骤遗漏                        → 分步练习 + checklist
                            粗心（复查可发现）               → 降低速度要求

审题不清 (misreading)  →   关键条件忽略                    → 条件高亮题
                            问题理解偏差                    → 问题重述练习
                            歧义解读                        → 多角度理解题

方法错误 (method)      →   用了错误公式                    → 公式对比例题
                            不会分解问题                    → 子问题拆解练习
                            思维定势                        → 变式题（打破定势）
```

### 2.2 错因标签（给 LLM 的选项，单选）

```
concept_gap          → 前置知识缺失
concept_fuzzy        → 概念理解模糊
concept_forgotten    → 知识遗忘
calc_sign            → 符号/正负号错误
calc_skip            → 步骤遗漏
calc_careless        → 粗心（可自查发现）
read_ignore          → 忽略关键条件
read_misunderstand   → 理解偏差
method_wrong_formula → 用错公式
method_no_approach   → 不会入手
method_fixation      → 思维定势
```

---

## 三、数据流

```
用户答错
  → practice.py submit_answer()
    → feedback["error_analysis"] = LLM 生成 (已有)
    → 存入 ErrorBookEntry (已有)
  → ❌ 当前: 错因分析只有 type 字段，无详细分析文字
  → ✅ Phase 2: 新增 error_detail 字段 + 异步 LLM 深度分析

异步分析流程:
  answer submitted (is_correct=false)
    → background_jobs 触发 analyze_error(error_id)
    → LLM: "分析这道错题的深层原因，从11种错因中选择最匹配的1-2个"
    → 存入 error_book[error_id].attribution = {
        "primary": "concept_gap",
        "secondary": "calc_sign",
        "analysis": "用户混淆了导数和微分的概念...",
        "recommendation": "建议先复习极限定义，再做导数 vs 微分对比题"
      }
```

---

## 四、后端实现

### 4.1 增强存储

`ErrorBookEntry` 新增字段：

```python
attribution: Optional[dict] = None   # {"primary": "concept_gap", "analysis": "..."}
```

### 4.2 新增 LLM 分析

```python
# backend/app/services/error_attribution.py  ← 新建

async def analyze_error(question_text, user_answer, correct_answer, 
                        error_type, skill_id) -> dict:
    prompt = f"""
    分析以下错题的深层原因。

    题目: {question_text}
    学生答案: {user_answer}
    正确答案: {correct_answer}
    知识点: {skill_id}

    可选错因标签: concept_gap, concept_fuzzy, concept_forgotten,
    calc_sign, calc_skip, calc_careless, read_ignore, read_misunderstand,
    method_wrong_formula, method_no_approach, method_fixation

    返回 JSON: {{"primary": "...", "secondary": "...", "analysis": "...", 
    "recommendation": "..."}}
    """
    return await llm_call(prompt)
```

### 4.3 新增 API

| 端点 | 方法 | 用途 |
|------|:--:|------|
| `/api/practice/errors/{error_id}/analyze` | POST | 触发单个错题的深度分析 |
| `/api/practice/errors/stats` | GET | 错因分布统计（用于前端图表） |

---

## 五、前端增强

### 5.1 `/errors` 页面增强

现有错题列表 → 每题增加**展开按钮**：

```
┌────────────────────────────────────────────┐
│ ❌ 求 f(x)=x² 的导数                        │
│    你的答案: f'(x)=x                       │
│    正确答案: f'(x)=2x                      │
│    [展开分析 ▾]                             │
├────────────────────────────────────────────┤
│ 🔍 AI 错因分析                              │
│                                             │
│ 主要错因: 概念模糊 — 混淆了导数和原函数的关系  │
│                                             │
│ 分析: 你记得 x² 求导结果与 x 有关，但把     │
│ 次方系数搞反了。这是典型的「公式记反」错误。  │
│                                             │
│ 建议: 练习 3 道同类型题加深记忆              │
│                                              │
│ [练同类题] [看知识点讲解]                    │
└────────────────────────────────────────────┘
```

### 5.2 错因分布图表

`/errors` 页面顶部新增：

```
错因分布（最近 30 天）
──────────────────
概念混淆   ████████░░  40%
计算失误   ████░░░░░░  20%
审题不清   ███░░░░░░░  15%
方法错误   █████░░░░░  25%
```

---

## 六、验收检查

- [ ] 任一错题可点击展开 → 显示 LLM 分析文字
- [ ] 分析文字包含具体错因标签
- [ ] 分析文字包含改进建议
- [ ] 「练同类题」按钮可点击 → 生成相关题目
- [ ] 错因分布图表显示正确比例
- [ ] `/api/practice/errors/stats` 返回正确统计
