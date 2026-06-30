# S2 · 成就激励系统

> 子系统: 游戏化激励  
> 当前基础: `behavior_analyzer` 有 streak / regularity / best_hours  
> Phase 2 产出: 徽章引擎 + 12 种成就 + 里程碑弹窗 + 成就墙页面

---

## 一、设计目标

学习是长跑。中间需要正反馈——不是排行榜，是「我比昨天更强了」。

| before | after |
|--------|-------|
| streak 数字藏在仪表板里 | 解锁成就时弹窗 + 🎉 动画 + 成就墙 |

---

## 二、成就分级

### 2.1 青铜成就（入门 · 一次性）

| ID | 名称 | 图标 | 触发条件 |
|----|------|:--:|---------|
| `first_practice` | 🥉 初出茅庐 | 🎯 | 完成第 1 次练习 |
| `first_correct` | ✅ 首战告捷 | ✨ | 第 1 次答对 |
| `first_session` | 📝 学习启程 | 🚀 | 创建第 1 个学习 session |
| `first_conversation` | 💬 初次对话 | 🗣️ | 发送第 1 条对话消息 |

### 2.2 白银成就（积累 · 可重复升级）

| ID | 名称 | 图标 | Lv1 | Lv2 | Lv3 |
|----|------|:--:|-----|-----|-----|
| `question_master` | 📚 题海勇士 | ⚔️ | 50 题 | 200 题 | 500 题 |
| `accuracy_champion` | 🎯 百发百中 | 💎 | 正确率 ≥70% (50题) | ≥80% (100题) | ≥90% (200题) |
| `streak_warrior` | 🔥 持之以恒 | 🔥 | 连续 3 天 | 连续 7 天 | 连续 30 天 |
| `knowledge_explorer` | 🧠 博学多才 | 📖 | 掌握 5 技能 | 掌握 15 技能 | 掌握 30 技能 |

### 2.3 黄金成就（里程碑 · 一次性）

| ID | 名称 | 图标 | 触发条件 |
|----|------|:--:|---------|
| `all_rounder` | 🌟 全能学者 | 🏆 | 至少 3 个学科各掌握 ≥1 个技能 |
| `speed_demon` | ⚡ 闪电思维 | ⚡ | 单题用时 <10s 且正确 (累计 10 次) |
| `perfectionist` | 💯 完美主义 | 👑 | 单次 session 10 题全对 |
| `comeback_kid` | 🔄 逆袭之王 | 🦅 | 同一技能从 mastery<20% → mastery≥80% |

---

## 三、触发机制

### 3.1 检测时机

```
答题 submit_answer
  → bkt_engine.update()
  → save_state()
  → AchievementEngine.check(user_id)  ← 新增
    → 遍历所有未解锁成就
    → 检测条件满足 → 解锁 + 记录 + 返回弹窗数据
  → 响应里附加 unlocked_achievements: [...]
```

### 3.2 去重存储

```
UserData.achievements = {
  "first_practice": {"unlocked_at": "2026-05-19T10:00:00", "level": 1},
  "question_master": {"unlocked_at": "2026-05-20T14:30:00", "level": 2},
  ...
}
```

- 已解锁的不再触发
- 升级类成就：每次答题后检查是否达到下一等级

---

## 四、后端实现

### 4.1 新增文件

```
backend/app/services/
└── achievement_engine.py    ← 新建（~200行）
```

### 4.2 AchievementEngine

```python
class AchievementEngine:
    ACHIEVEMENTS = {...}  # 12 种成就定义

    def check(self, user_id: str) -> list[dict]:
        """检测并返回新解锁的成就"""
        
    def get_all(self, user_id: str) -> dict:
        """获取所有成就（含进度）"""
```

### 4.3 检测逻辑示例

```python
def _check_question_master(user_id, achievement_def):
    total = db.count_questions(user_id)
    for level, threshold in achievement_def["thresholds"].items():
        if total >= threshold and not already_unlocked(level):
            return {"level": level, "name": f"题海勇士 Lv{level}"}
```

---

## 五、前端实现

### 5.1 弹窗组件

```
frontend/src/components/
└── achievements/
    └── AchievementUnlock.tsx   ← 新建
        Props:
          achievement: {name, icon, level, description}
          onClose: () => void
```

- 居中弹窗，半透明背景遮罩
- 图标放大动画（scale 0→1.2→1，0.5s）
- 标题 + 描述文字渐入
- 3 秒后自动消失，或点击关闭

### 5.2 成就墙页面

```
frontend/src/app/achievements/page.tsx   ← 新建（~200行）
```

布局：
- 3 列网格（桌面），1 列（移动端）
- 每张成就卡: 图标 + 名称 + 等级 + 解锁日期（或锁定🔒）
- 未解锁显示灰色 + 🔒
- 进度条显示（如：200/500 题 → 40%）

### 5.3 弹窗触发

答题/创建 session 后，API 响应中的 `unlocked_achievements` 非空 → 渲染弹窗。

---

## 六、API 端点

| 端点 | 方法 | 用途 |
|------|:--:|------|
| `/api/achievements/{user_id}` | GET | 获取所有成就状态（含进度） |
| `/api/achievements/{user_id}/recent` | GET | 最近解锁的成就（用于弹窗） |

**共 2 个新 API**。

---

## 七、验收检查

- [ ] 完成第 1 次答题 → 弹窗 「🎯 初出茅庐」
- [ ] 累计答对 50 题 → 弹窗 「⚔️ 题海勇士 Lv1」
- [ ] `/achievements` 页面展示 12 张成就卡（含锁定状态）
- [ ] 成就墙正确显示进度条
- [ ] 重复触发不弹重复弹窗（已解锁的 skip）
