# 学情仪表板设计 v1.0

> 不是数据堆砌，是"一眼看懂自己学得怎么样"。

---

## 一、设计原则

| 原则 | 说明 |
|------|------|
| **一眼看懂** | 打开页面 3 秒内能回答：我整体学得怎么样？哪里薄弱？ |
| **逐层深入** | 概览 → 知识点详情 → 单题分析，三层递进 |
| **对比有锚点** | 不能只看绝对数字，要有上周对比/目标线 |
| **行动导向** | 每个数据点要么能"点进去练"，要么能"点进去看错题" |
| **瑞士极简** | 不用图表库，纯 SVG/CSS 手绘，暗色主题 `#0a0a0a` |

---

## 二、面板布局

```
┌──────────────────────────────────────────────────────┐
│  📊 学情分析                    本周 | 本月 | 学期    │
├──────────┬──────────┬──────────┬──────────────────────┤
│ 总题数    │ 正确率    │ 学习天数  │ 学习时长              │
│  247     │  73%     │   18     │  12.5h               │
│ ↑12%     │ ↑3%     │  +2天    │  ↑2.3h               │
├──────────┴──────────┴──────────┴──────────────────────┤
│                                                        │
│  📈 学习趋势 (7日折线图)                               │
│  ▁▂▃▅▇█▆  ▁▃▄▆█▇▅  ...                               │
│                                                        │
├──────────────────────────┬─────────────────────────────┤
│  🔥 知识掌握热力图        │  📊 错因分布                 │
│  极限  ████████░░ 80%   │  概念  ██████ 35%            │
│  导数  ██████░░░░ 60%   │  计算  ████ 25%              │
│  积分  ████░░░░░░ 40%   │  审题  ███ 15%               │
│  矩阵  ████████░░ 85%   │  程序  ██ 12%                │
│  ...                     │  迁移  ██ 13%                │
├──────────────────────────┴─────────────────────────────┤
│  🎯 建议行动                                            │
│  • 积分是最大短板(40%)，建议今天重点练习                 │
│  • 导数概念错误偏多，去错题本看看 →                      │
│  • 连续3天没练了，今天来10道？                           │
└──────────────────────────────────────────────────────┘
```

### 面板清单（6 个）

| # | 面板 | 类型 | 数据来源 | 交互 |
|---|------|------|---------|------|
| 1 | 概览卡片 ×4 | 数字+环比 | stats API | 无 |
| 2 | 学习趋势图 | 7日折线 | stats.daily | 悬停详情 |
| 3 | 知识掌握热力条 | 横向进度条 | knowledge_states | 点击→针对性练习 |
| 4 | 错因分布 | 横向柱状 | stats.error_dist | 点击→错题本筛选 |
| 5 | 学习时段热力图 | 周×小时格子 | stats.hourly | 无 |
| 6 | 建议行动 | 文本列表 | 综合推断 | 可点击跳转 |

---

## 三、各面板详细设计

### 3.1 概览卡片

```
┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐
│ 总题数    │ │ 正确率    │ │ 学习天数  │ │ 学习时长  │
│  247     │ │  73%     │ │   18     │ │  12.5h   │
│ ↑12%     │ │ ↑3%     │ │  +2天    │ │  ↑2.3h   │
│ vs 上周   │ │ vs 上周   │ │ vs 上周   │ │ vs 上周   │
└──────────┘ └──────────┘ └──────────┘ └──────────┘
```

每个卡片显示：
- 主数字（大号字体）
- 环比变化（↑绿色/↓红色/→灰色）
- vs 上周/上月标签

### 3.2 学习趋势图

```
本周每日练习量 + 正确率双线：
   
   题数     正确率
   10┤        100%
   8 │    ●───●──80%
   6 │  ●       ●──60%
   4 │●    ●──────40%
   2 │             20%
   0 └──────────────0%
     一 二 三 四 五 六 日
```

纯 SVG 绘制，无外部依赖。悬停显示当日详情（x题，y%正确率）。

### 3.3 知识掌握热力条

```
极限   ████████████████████░░░░░░░░  80%  已掌握 ✅
导数   ██████████████░░░░░░░░░░░░░░  60%  发展中 🔶
积分   ██████████░░░░░░░░░░░░░░░░░░  40%  薄弱 🔴
矩阵   ████████████████████░░░░░░░░  85%  已掌握 ✅
```

每行：
- 知识点名称
- 进度条（宽度=掌握度%，颜色=绿/黄/红）
- 百分比数字
- 状态标签
- 点击跳转到该知识点的针对性练习

颜色阈值：
- ≥80%: `#22c55e` 绿 — 已掌握
- 50-80%: `#f59e0b` 黄 — 发展中
- <50%: `#ef4444` 红 — 薄弱

### 3.4 错因分布

```
概念错误  ██████████████████████  35%  12次
计算错误  ██████████████          25%  8次
审题错误  ████████                15%  5次
程序错误  ██████                  12%  4次
迁移错误  ██████                  13%  4次
```

纯 CSS 柱状图。每个柱：
- 标签
- 宽度=占比%
- 次数
- 点击→错题本按错误类型筛选

### 3.5 学习时段热力图

```
      周一  周二  周三  周四  周五  周六  周日
8:00   ░     ░     ░     ░     ░     ▒     ▓
10:00  ▒     ▓     ░     ▒     ▓     ░     ░
14:00  ▓     ▒     ▓     ░     ░     ▒     ░
16:00  ░     ░     ▒     ▓     ▒     ░     ░
20:00  ▒     ▒     ░     ░     ░     ▓     ▒
22:00  ▓     ░     ░     ▒     ░     ░     ░

░=0题 ▒=1-5题 ▓=6-10题 █=10+题
```

### 3.6 建议行动

基于所有数据推断的 3-5 条行动建议：

```
🎯 建议行动
• 积分(40%)是你当前最大短板，建议今天用15分钟针对性练习 →
• 你的概念错误占35%(偏高)，去做概念专题 →
• 周六是你效率最高的学习日，建议安排重难点 →
• 连续3天没练了，现在来一组保持手感？💪
```

---

## 四、API 设计

### 现有：`GET /api/practice/stats?time_range=week`

返回：total_questions, accuracy, study_minutes, weak_skills, strong_skills

### 新增：`GET /api/practice/analytics?time_range=week`

```json
{
  "overview": {
    "total_questions": 247,
    "accuracy": 0.73,
    "study_days": 18,
    "study_minutes": 750,
    "prev_week_total": 220,
    "prev_week_accuracy": 0.70,
    "prev_week_days": 16,
    "prev_week_minutes": 612
  },
  "daily_trend": [
    {"date": "05-12", "questions": 12, "correct": 9},
    {"date": "05-13", "questions": 8, "correct": 6},
    ...
  ],
  "mastery_bars": [
    {"skill_id": "calculus_limit", "label": "极限", "p_known": 0.80},
    {"skill_id": "calculus_derivative", "label": "导数", "p_known": 0.60},
    ...
  ],
  "error_distribution": [
    {"type": "conceptual", "label": "概念错误", "count": 12, "pct": 0.35},
    {"type": "computation", "label": "计算错误", "count": 8, "pct": 0.25},
    ...
  ],
  "hourly_heatmap": [
    {"day": 1, "hour": 8, "questions": 3},
    {"day": 1, "hour": 10, "questions": 5},
    ...
  ],
  "suggestions": [
    {"text": "积分是最大短板(40%)，建议重点练习", "action": "practice", "skill": "calculus_integral"},
    {"text": "概念错误偏高(35%)，做概念专题", "action": "errors", "filter": "conceptual"},
    ...
  ]
}
```

---

## 五、建议行动生成规则

```python
def generate_suggestions(stats: AnalyticsData) -> list[Suggestion]:
    suggestions = []
    
    # 规则1: 最弱知识点 → 建议练习
    weakest = min(stats.mastery_bars, key=lambda x: x["p_known"])
    if weakest["p_known"] < 0.5:
        suggestions.append({
            "text": f"{weakest['label']}({weakest['p_known']:.0%})是最大短板，建议重点练习",
            "action": "practice",
            "skill": weakest["skill_id"],
        })
    
    # 规则2: 最常见错误类型 → 建议错题本
    top_error = max(stats.error_distribution, key=lambda x: x["count"])
    if top_error["pct"] > 0.25:
        suggestions.append({
            "text": f"{top_error['label']}偏高({top_error['pct']:.0%})，去错题本看看",
            "action": "errors",
            "filter": top_error["type"],
        })
    
    # 规则3: 连续3天未练习 → 提醒
    if stats.study_days < 3:
        suggestions.append({
            "text": "最近练习偏少，来一组保持手感？💪",
            "action": "practice",
            "skill": None,
        })
    
    # 规则4: 正确率上升 → 鼓励
    if stats.overview["accuracy"] - stats.overview["prev_week_accuracy"] > 0.05:
        suggestions.append({
            "text": f"正确率上升{...}%！继续保持势头 🔥",
            "action": None,
            "skill": None,
        })
    
    return suggestions[:5]
```

---

## 六、前端实现策略

| 元素 | 实现方式 | 理由 |
|------|---------|------|
| 概览卡片 | CSS Grid + 纯文本 | 简单直接 |
| 趋势折线 | SVG `<polyline>` | 无外部依赖，暗色主题友好 |
| 热力条 | CSS `width: X%` + 渐变 | 简单精确 |
| 柱状图 | CSS `width: X%` | 不需要坐标轴 |
| 热力图 | CSS Grid + 透明度 | 7×6 格子，CSS 足够 |
| 建议列表 | 纯文本 + Link | 最简单的交互 |

**不引入任何图表库**（recharts/chart.js/echarts），全部手写 SVG+CSS。节省 80KB+ bundle，风格完全可控。

---

## 七、实施计划

| 步骤 | 内容 | 文件 | 状态 |
|------|------|------|------|
| 1 | 知识状态持久化 | `knowledge_trace.py` + `conversation.py` | ✅ 已完成 |
| 2 | BKT 引擎 load_or_create / save_state | `knowledge_trace.py` | ✅ 已完成 |
| 3 | submit_answer 使用持久化状态 | `api/practice.py` L310-316 | ✅ 已完成 |
| 4 | /stats 端点增强（错因+环比+知识掌握+热力） | `api/practice.py` L470-603 | ✅ 已完成 |
| 5 | /analytics 独立端点（含建议行动） | `api/practice.py` | ⬜ 待实施 |
| 6 | 重写仪表板页面 | `frontend/src/app/analytics/page.tsx` | ⬜ 待实施 |
| 7 | 首页/练习页跳转 | 练习结果→仪表板链接 | ⬜ 待实施 |

### 步骤 1-4 已完成的改动

1. **UserData 扩展** (`schemas/conversation.py`): 新增 `knowledge_states`、`practice_sessions`、`error_book` 持久化字段
2. **BKT 引擎持久化** (`core/knowledge_trace.py`): 新增 `load_or_create(user_id, skill_id)`, `save_state(user_id, state)`, `load_all_states(user_id)` 三个方法
3. **答题流程改造** (`api/practice.py submit_answer`): `create_knowledge_state` → `load_or_create` + 答题后 `save_state`
4. **统计端点增强** (`api/practice.py /stats`):
   - `error_distribution`: 从 AttemptRecord.error_analysis.error_type 聚合
   - `overview.prev_week`: 上一周期的环比对比数据
   - `mastery_bars`: 从持久化 KnowledgeState 读取 p_known
   - `hourly_heatmap`: 周×小时 7×6 网格聚合
   - `daily_trend`: 7日每日题量+正确率

### 数据流确认

```
答题 submit_answer
  → bkt_engine.load_or_create(user_id, skill_id)  # 加载持久化状态
  → bkt_engine.update(state, is_correct, ...)       # BKT 更新
  → bkt_engine.save_state(user_id, updated_state)   # 写回 UserData
  → storage.save(user_id, data)                      # 持久化到磁盘

仪表板 GET /stats
  → overview: 当期 session 聚合 + 上一周期环比
  → mastery_bars: bkt_engine.load_all_states(user_id) → p_known
  → error_distribution: 遍历 attempts → error_type 聚合
  → hourly_heatmap: 遍历 attempts → day×hour 聚合
  → daily_trend: 按日期分桶
```
