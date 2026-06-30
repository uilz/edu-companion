# S3 · 遗忘曲线可视化

> 子系统: 学情深度  
> 当前基础: `/api/knowledge/retention` 后端已有，返回 Ebbinghaus 曲线数据  
> Phase 2 产出: 前端 `/analytics` 新增遗忘曲线面板 · CSS 手绘 SVG

---

## 一、设计目标

知识不复习会遗忘。让用户看到「如果我 7 天后不复习，这个知识点保留率只剩 40%」——驱动主动复习。

| before | after |
|--------|-------|
| `/api/knowledge/retention` 只有后端数据 | `/analytics` 里一个可视化面板 |

---

## 二、数据源

**已有，无需新 API。**

```http
GET /api/knowledge/retention?user_id=default_user
```

返回（每个练习过的技能）：

```json
{
  "skills": [{
    "skill_id": "calculus_limit",
    "label": "极限与连续",
    "mastery": 57.7,
    "curve": [
      {"day": 0, "retention": 100},
      {"day": 1, "retention": 90.2},
      {"day": 3, "retention": 82.1},
      {"day": 7, "retention": 70.5},
      {"day": 14, "retention": 55.3},
      {"day": 30, "retention": 35.1},
      {"day": 60, "retention": 18.7},
      {"day": 90, "retention": 9.4}
    ]
  }],
  "at_risk": [...]   // 7天保留率 <50% 的技能
}
```

---

## 三、视觉设计

### 3.1 面板布局

```
┌────────────────────────────────────────┐
│  🧠 遗忘曲线 · 知识保留率预估            │
│                                         │
│  学科筛选: [全部 ▾]                      │
│                                         │
│  ┌──────────────────────────────────┐  │
│  │ 100% ┤                            │  │
│  │  80% ┤╲                            │  │
│  │  60% ┤  ╲___                       │  │
│  │  40% ┤      ╲___                   │  │
│  │  20% ┤          ╲___               │  │
│  │   0% ┤              ╲___           │  │
│  │      └───┬───┬───┬───┬───┬───      │  │
│  │       0d  1d  3d  7d 14d 30d 60d 90d│  │
│  └──────────────────────────────────┘  │
│                                         │
│  🔴 高风险技能 (7天后<50%):               │
│  极限与连续 (35.1%) · 导数应用 (28.4%)    │
└────────────────────────────────────────┘
```

### 3.2 曲线样式

- **X 轴**: 天数（0d→90d，对数刻度等距标注）
- **Y 轴**: 保留率 0-100%
- **阈值线**: 50% 处红色虚线 + 标签「警戒线」
- **曲线**: 
  - 每个技能一条折线
  - 颜色 = masteryColor(skill.mastery)
  - hover 高亮 + 标签
- **默认显示**: mastery 最低的 5 条曲线（其余可切换）

---

## 四、组件实现

```
frontend/src/components/analytics/
└── ForgettingCurve.tsx    ← 新建（~150行）
    Props:
      retentionData: RetentionData   // API 返回体
      subject: string                // 学科筛选
```

### 核心逻辑

1. 接收 `retentionData.skills`
2. 按 `mastery` 排序，取前 5 条（最弱的）
3. 绘制 SVG:
   - 坐标变换：x = log(day+1) * scaleX, y = (100 - retention) * scaleY
   - `<polyline>` 渲染每条曲线
   - `<circle>` 标注数据点
4. 底部列出 `at_risk` 技能名

---

## 五、嵌入位置

`/analytics` 页面，在「每日趋势」面板下方新增「遗忘曲线」面板。

---

## 六、验收检查

- [ ] 有练习数据的知识点显示曲线（≥1 条）
- [ ] 没有练习数据的知识点不崩溃（显示「暂无数据，开始练习吧！」）
- [ ] 50% 警戒线可见
- [ ] 学科筛选生效（只显示该学科的技能曲线）
- [ ] hover 交互正常
