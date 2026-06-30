# S1 · 知识点雷达图

> 子系统: 学情可视化  
> 当前基础: `/api/knowledge/graph` 已返回 mastery + mastery_level  
> Phase 2 产出: 前端 SVG 雷达图，嵌入 `/analytics` 页

---

## 一、设计目标

把「38 个知识点的 mastery 列表」变成「一眼看清强弱分布的蜘蛛网图」。

| before | after |
|--------|-------|
| 数字列表（57.7%、0.0%、0.0%、…） | 雷达图 + 颜色分区 + 点击跳练 |

---

## 二、数据源

**已有，无需新 API。**

```http
GET /api/knowledge/graph?user_id=default_user&subject=高等数学
```

返回每个节点：

```json
{
  "id": "calculus_limit",
  "label": "极限与连续",
  "mastery": 57.7,       // ← 雷达图半径
  "mastery_level": "发展中",
  "subject": "高等数学",
  "can_practice": true
}
```

---

## 三、雷达图规格

### 3.1 视觉设计

```
         极限(57%)  
            /\
           /  \
  微分(45%)/    \ 积分(30%)
         /      \
        /   🎯   \
       / 高等数学  \
  级数(10%)────应用(5%)
```

- **轴**: 每个知识点一条轴（最多 8 条，超过 8 个取 mastery 最低的 8 个 + 最高的 2 个）
- **刻度**: 3 圈（33% / 66% / 100%）
- **颜色分区**:
  - 0-33%: `#f97316`（薄弱）
  - 34-66%: `#f59e0b`（学习中）
  - 67-100%: `#22c55e`（已掌握）
- **填充**: 半透明多边形 (opacity=0.2)
- **交互**:
  - 点击节点 → 弹出 tooltip（知识点名 + mastery% + mastery_level + 跳转到练习按钮）
  - 学科下拉切换 → 重新拉数据

### 3.2 SVG 布局算法

```python
# 伪代码
angles = [i * 2π/n for i in range(n)]  # n 个知识点等分圆周
radius = mastery / 100 * MAX_R           # mastery 映射为半径
x = center_x + radius * cos(angle)
y = center_y + radius * sin(angle)
```

---

## 四、嵌入位置

修改 `/analytics` 页面（`frontend/src/app/analytics/page.tsx`）：

- 在「掌握度柱状图」面板下方新增「**知识雷达图**」面板
- 面板标题: `🎯 知识雷达图`
- 学科选择器（下拉）：全部 / 高等数学 / 大学物理 / 计算机 / 线性代数 / 概率论

---

## 五、组件拆解

```
frontend/src/components/
└── analytics/
    └── RadarChart.tsx      ← 新建
        Props:
          nodes: GraphNode[]      // 知识点列表（含 mastery）
          subject: string         // 当前学科
          onNodeClick: (id) => void // 点击跳转
```

### RadarChart.tsx 核心逻辑

1. 接收 `nodes: GraphNode[]`，按 mastery 排序
2. 取前 8 个（最多展示数），均匀分布角度
3. 绘制 3 个同心多边形（33%/66%/100%刻度）
4. 绘制 mastery 多边形
5. 绘制轴线 + 标签
6. 绘制节点圆点（颜色 = masteryColor）

---

## 六、API 调用

无新增。复用已有：

```
GET /api/knowledge/graph?user_id=default_user&subject={subject}
```

前端已有 `fetchGraph()` → 数据已经在 `nodes` 中 → 直接传给 RadarChart。

---

## 七、验收检查

- [ ] `/analytics` 页出现雷达图面板
- [ ] 按学科筛选后雷达图更新（高等数学 8 轴 → 大学物理 5 轴）
- [ ] mastery=0 的点显示在圆周最内圈（不是消失）
- [ ] 点击节点弹出 tooltip → **不**跳转（先只用 tooltip 展示）
- [ ] 移动端可用（雷达图宽度自适应，最小 300px）
