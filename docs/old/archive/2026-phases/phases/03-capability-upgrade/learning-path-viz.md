# P2 · 学习路径可视化

> 打破孤岛: API↔前端（/knowledge/path 有数据无页面）

---

## 一、目标

当前 `/api/knowledge/path` 返回 JSON 路径，前端无渲染。做成交互式「登山路线图」：

```
     🏔️ 微分方程 [🔒]
         ↑
     微分应用 [⬜]
         ↑
     导数微分 [🔶 57%]
         ↑
     极限连续 [✅ 80%]
  
  🟢 = 已掌握  🟡 = 学习中  ⬜ = 未开始  🔒 = 前置卡控
```

---

## 二、数据源

**已有，无需新 API。**

```
GET /api/knowledge/path?user_id=default_user&target_skill=calculus_ode
```

返回：
```json
{
  "path": [
    {"skill_id": "calculus_limit", "status": "已掌握", "mastery": 80},
    {"skill_id": "calculus_derivative", "status": "待学习", "mastery": 57},
    ...
  ],
  "target": "calculus_ode"
}
```

---

## 三、前端实现

### 3.1 嵌入位置

`/graph` 页面新增「学习路径」Tab，或在知识图谱下方新增面板。

### 3.2 组件

```
frontend/src/components/knowledge/
└── LearningPath.tsx   ← 新建
```

- 目标技能下拉选择器
- 垂直节点链（每个节点：emoji状态 + 技能名 + mastery% + 颜色）
- 箭头连接线
- 点击节点 → 侧栏详情
- 如果「待学习」→ 按钮「去练习」

---

## 四、验收

- [ ] 选择目标技能 → 显示路径节点链
- [ ] 节点颜色正确（已掌握=绿，学习中=黄，待学习=白）
- [ ] 点击节点显示详情
- [ ] 「去练习」按钮跳转正确
