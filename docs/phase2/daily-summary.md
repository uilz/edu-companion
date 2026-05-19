# S7 · 智能每日摘要

> 子系统: 持续反馈  
> 当前基础: 无  
> Phase 2 产出: 每天定时推送 · 昨日学习总结 · 今日推荐 · 鼓励卡片 · 零 token 脚本模式

---

## 一、设计目标

用户不打开应用也能感知学习进展——每天一条消息，像朋友一样关心。

| before | after |
|--------|-------|
| 需要主动打开 app 才能看到进度 | 每天固定时间收到一条总结推送 |

---

## 二、推送内容设计

### 2.1 卡片结构

```
┌────────────────────────────────────┐
│         早安，你的学习日报 📊         │
│                                    │
│  5月18日 星期二                      │
│                                    │
│  📝 答题 15 题    较昨日 ↑3         │
│  ✅ 正确 12 题    正确率 80%         │
│  ⏱  学习 32 分钟                   │
│  🔥 连续学习 5 天！                  │
│                                    │
│  📈 进步的知识点                     │
│  · 极限与连续  +12% → 已掌握         │
│  · 导数定义    +8%  → 发展中         │
│                                    │
│  🎯 今日推荐                        │
│  练习「导数应用」· 5 题 · 约15分钟    │
│  复习「极限与连续」· 防止遗忘         │
│                                    │
│  [开始练习]                         │
└────────────────────────────────────┘
```

### 2.2 推送时间

- **早上 7:30** — 早安问候 + 昨日总结 + 今日推荐
- **不推送的情况**：昨天没有任何学习活动 → 沉默（不打扰）

---

## 三、实现方案

### 3.1 Cron Job（零 token 脚本模式）

```
cron: 30 7 * * *
script: ~/.hermes/profiles/weixin2/scripts/daily-summary.py
no_agent: true
```

脚本直接计算数据 + 输出要发送的文字，不走 LLM。

### 3.2 脚本逻辑

```python
# daily-summary.py

# 1. 查询昨日学习数据
yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
daily = get_daily_stats(user_id, yesterday)

# 2. 如果昨天没有学习 → 沉默退出
if daily["total"] == 0:
    sys.exit(0)

# 3. 查询本周 trend（环比）
this_week = get_week_stats(user_id)
prev_day = get_daily_stats(user_id, day_before_yesterday)

# 4. 查询 BKT 进步（今天 vs 昨天 mastery 变化的技能）
progress_skills = get_mastery_changes(user_id, yesterday)

# 5. 生成今日推荐（最弱的 3 个可练习技能）
recommendations = get_today_recommendations(user_id)

# 6. 组装输出
print(f"""
早安 ☀️ 你的学习日报

{yesterday_str} · 星期{weekday}

📝 答题 {daily['total']} 题  {trend_arrow(daily['total'], prev_day.get('total', 0))}
✅ 正确 {daily['correct']} 题 · 正确率 {daily['accuracy']:.0%}
⏱  学习 {daily['minutes']} 分钟
🔥 连续学习 {streak} 天

{'📈 进步的知识点' if progress_skills else '💤 昨天没有进步的知识点'}
{format_skills(progress_skills)}

🎯 今日推荐
{format_recommendations(recommendations)}
""")
```

### 3.3 静默逻辑

```python
if daily["total"] == 0:
    sys.exit(0)  # 空输出 → 不推送
```

---

## 四、数据查询函数

需要新增的辅助函数（放在脚本内或共享模块）：

| 函数 | 数据源 | 说明 |
|------|--------|------|
| `get_daily_stats(uid, date)` | `/progress/{uid}/stats` daily | 昨日数据 |
| `get_week_stats(uid)` | 同上 | 本周累计 |
| `get_mastery_changes(uid, date)` | BKT state snapshots | 需要前一天快照对比 |
| `get_today_recommendations(uid)` | `/api/knowledge/ready` | 可练习 + 最弱的 3 个 |

### BKT 快照

`get_mastery_changes` 需要昨天的 mastery。如果 BKT 没有历史快照，简化处理：

```python
# 简化版：展示当前 mastery 最高提升的技能
def get_mastery_changes(user_id):
    states = bkt_engine.load_all_states(user_id)
    # 按 p_known 排序，取前 3（作为「已经不错的」）
    top = sorted(states.values(), key=lambda s: s.p_known, reverse=True)[:3]
    return [{"skill_id": s.skill_id, "mastery": s.p_known * 100} for s in top]
```

---

## 五、鼓励语库

避免每天同样的文案。从文案池随机取：

```
morning_greetings = [
    "早安 ☀️ 新的一天，新的进步",
    "早上好 🌅 昨天的努力都算数",
    "醒来就是战斗力 💪",
    ...
]

encourage_lines = [
    "坚持下去，复利效应正在发生 📈",
    "每一个知识点都是未来的砖瓦 🧱",
    "今天比昨天多会一点，就是胜利 ✨",
    ...
]
```

---

## 六、验收检查

- [ ] 早上 7:30 收到推送（昨天有学习时）
- [ ] 昨天没学习 → 不推送
- [ ] 答题数环比正确（↑3 或 ↓2）
- [ ] 今日推荐包含 ≥1 个可练习知识点
- [ ] 连续 2 天推送，用语不同（文案池随机）
- [ ] 脚本静默退出时无推送、无错误日志
