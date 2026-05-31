"""
自适应学习计划引擎

触发条件:
1. 知识状态升级 → 自动重调计划
2. 手动刷新 → API 触发

核心策略:
- 技能升级时: 移除已掌握，加入下一级前置满足的技能
- 全局难度调整: 根据近7日正确率微调题目难度
- 时间预算: 根据 habit level 分配每日任务量
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta

from app.cognitive.storage import list_all_nodes, find_node_by_label
from domain.knowledge.checker import PrerequisiteChecker
from domain.knowledge.prerequisites import (
    ALL_PREREQUISITES,
    SKILL_TO_SUBJECT,
)
from app.db.database import get_db

logger = logging.getLogger("adaptive_planner")

# ── 掌握度阈值（与 BKT get_mastery_level 保持一致）──
_MASTERY_THRESHOLD = 0.8


def _proficiency_to_level(p: float) -> str:
    """CognitiveNode proficiency_mean → 掌握等级字符串"""
    if p < 0.3:
        return "初学"
    elif p < 0.6:
        return "发展中"
    elif p < _MASTERY_THRESHOLD:
        return "接近掌握"
    else:
        return "已掌握"


class AdaptivePlanGenerator:

    def __init__(self):
        # PrerequisiteChecker 需要一个 PracticeService-like adapter
        # 现在从 CognitiveNode 读取 proficiency_mean
        planner_self = self  # capture for closure

        from app.services.knowledge_state import get_knowledge_state as _canonical_get_ks

        class _CognitiveAdapter:
            async def get_knowledge_state(self, uid, sid):
                return await _canonical_get_ks(uid, sid)

        self._checker = PrerequisiteChecker(_CognitiveAdapter())

    async def generate(
        self, user_id: str, reason: str = "manual",
        subject: str | None = None,
    ) -> dict:
        # ── 从 CognitiveNode 读取所有节点 ──
        all_nodes = list_all_nodes(user_id)

        # 按 proficiency_mean 降序排列，生成推荐列表
        # 模拟原来 BKT recommend_practice 的输出格式
        recommendations = self._build_recommendations(all_nodes, top_n=10)

        ready_skills, blocked_skills = [], []
        for rec in recommendations:
            sid = rec["skill_id"]
            result = await self._checker.can_practice(user_id, sid)
            if result.can_practice:
                ready_skills.append(rec)
            else:
                blocked_skills.append({
                    "skill_id": sid, "level": rec["level"],
                    "p_known": rec["p_known"], "blocked_by": result.blocked,
                })

        if len(ready_skills) < 3:
            entry = self._find_entry_skills(all_nodes, user_id, subject)
            for sid in entry:
                if sid not in [r["skill_id"] for r in ready_skills]:
                    node = find_node_by_label(sid, user_id)
                    p = node.belief.proficiency_mean if node else 0.0
                    lv = _proficiency_to_level(p) if node else "未接触"
                    ready_skills.append({"skill_id": sid, "level": lv, "p_known": p, "priority": 3})

        target = ready_skills[:5]
        recent_acc = self._get_recent_accuracy(user_id)
        diff_bias = self._compute_difficulty_bias(recent_acc)
        habit_lv = self._get_habit_level(user_id)
        time_budget = {"beginner": 5, "regular": 10, "intensive": 20}.get(habit_lv, 5)

        items = []
        for i, rec in enumerate(target):
            sid, lv, pk = rec["skill_id"], rec.get("level", "发展中"), rec.get("p_known", 0.3)
            if lv == "未接触":
                est, diff = 30, max(0.2, 0.3 + diff_bias)
            elif lv == "初学":
                est, diff = 25, max(0.2, 0.4 + diff_bias)
            elif lv == "发展中":
                est, diff = 20, max(0.3, 0.5 + diff_bias)
            else:
                est, diff = 15, max(0.4, 0.7 + diff_bias)

            # 利用 CognitiveNode 的 trend/scheduling 信息增强优先级
            node = find_node_by_label(sid, user_id)
            priority = 10 - i
            if node:
                # 停滞 7 天以上 → 提升优先级
                if node.trend.stagnation_days >= 7:
                    priority += 2
                # 下降趋势 → 提升优先级
                if node.trend.direction == "descending":
                    priority += 1
                # urgency 字段（已由 scheduling 引擎计算）
                if node.scheduling.urgency > 0.7:
                    priority += 1

            items.append({
                "task_id": f"plan_{user_id}_{i}_{int(datetime.now().timestamp())}",
                "skill_id": sid, "title": f"练习: {self._checker._skill_display_name(sid)}",
                "description": f"当前水平: {lv}，建议难度 {diff:.1f}",
                "subject": SKILL_TO_SUBJECT.get(sid, "通用"),
                "estimated_minutes": est, "difficulty": round(diff, 2),
                "priority": priority, "daily_questions": time_budget,
                "completed": False, "level": lv,
            })

        old = self._get_last_plan(user_id)
        changes = self._diff_plan(old, items)
        self._save_snapshot(user_id, items, reason, changes)

        return {
            "user_id": user_id,
            "plan": {
                "items": items, "total_items": len(items),
                "estimated_total_minutes": sum(it["estimated_minutes"] for it in items),
                "daily_questions": time_budget, "habit_level": habit_lv,
                "difficulty_bias": round(diff_bias, 2),
                "recent_accuracy": round(recent_acc, 2),
                "week_number": datetime.now().isocalendar()[1],
            },
            "changes": changes, "reason": reason,
            "blocked_skills": blocked_skills[:5],
        }

    def _build_recommendations(self, nodes, top_n: int = 10) -> list[dict]:
        """从 CognitiveNode 列表构建推荐列表（替代 BKT recommend_practice）"""
        recs = []
        for node in nodes:
            p = node.belief.proficiency_mean
            level = _proficiency_to_level(p)

            # 已掌握的不推荐
            if level == "已掌握":
                continue

            # 基于 urgency + stagnation 计算推荐优先级
            urgency = node.scheduling.urgency
            stagnation = node.trend.stagnation_days
            # 停滞越久 + urgency 越高 → 优先级越高
            priority = urgency * 0.6 + min(stagnation / 14.0, 1.0) * 0.4

            # 未接触的优先级稍低（先让用户接触已开始的技能）
            if p == 0.0:
                priority -= 0.1

            recs.append({
                "skill_id": node.id,
                "level": level,
                "p_known": p,
                "priority": priority,
            })

        recs.sort(key=lambda r: -r["priority"])
        return recs[:top_n]

    async def on_knowledge_updated(self, event) -> dict | None:
        """处理 CognitiveNodeUpdated 事件"""
        from shared.events import CognitiveNodeUpdated
        if not isinstance(event, CognitiveNodeUpdated):
            return None

        # 显著提升阈值：proficiency 提升超过 0.15 才触发重调
        delta = event.proficiency_after - event.proficiency_before
        if delta < 0.15:
            return None

        old_level = _proficiency_to_level(event.proficiency_before)
        new_level = _proficiency_to_level(event.proficiency_after)
        if old_level == new_level:
            return None

        return await self.generate(
            event.user_id,
            reason=(
                f"knowledge_upgrade:{event.node_id}:{event.label}"
                f":{old_level}→{new_level}"
                f"(Δ{delta:+.2f})"
            ),
        )

    def _find_entry_skills(self, nodes, user_id: str, subject=None):
        """找到所有前置条件已满足的入口技能"""
        node_map = {n.id: n for n in nodes}
        entry = []
        for sid, prereqs in ALL_PREREQUISITES.items():
            if subject and SKILL_TO_SUBJECT.get(sid) != subject:
                continue
            node = node_map.get(sid)
            p = node.belief.proficiency_mean if node else 0.0
            if p >= 0.7:
                continue
            if all(
                (node_map.get(prereq) and node_map[prereq].belief.proficiency_mean >= 0.7)
                for prereq in prereqs
            ):
                entry.append(sid)
        return entry[:5]

    def _get_recent_accuracy(self, user_id):
        db = get_db()
        w = (datetime.now() - timedelta(days=7)).isoformat()
        r = db.fetchone(
            "SELECT COUNT(*) as t, SUM(CASE WHEN is_correct THEN 1 ELSE 0 END) as c "
            "FROM attempts WHERE user_id=%s AND submitted_at>%s", (user_id, w))
        return r["c"] / r["t"] if r and r["t"] else 0.5

    def _compute_difficulty_bias(self, acc):
        if acc > 0.85: return 0.2
        if acc > 0.7: return 0.1
        if acc < 0.3: return -0.2
        if acc < 0.5: return -0.1
        return 0.0

    def _get_habit_level(self, user_id):
        r = get_db().fetchone(
            "SELECT COUNT(DISTINCT DATE(submitted_at)) as d FROM attempts WHERE user_id=%s", (user_id,))
        d = r["d"] if r else 0
        return "intensive" if d >= 7 else "regular" if d >= 3 else "beginner"

    def _ensure_table(self):
        try:
            get_db().execute(
                """CREATE TABLE IF NOT EXISTS plan_snapshots (
                    id SERIAL PRIMARY KEY, user_id TEXT NOT NULL,
                    plan_json JSONB DEFAULT '{}', changes_json JSONB DEFAULT '{}',
                    reason TEXT DEFAULT '', created_at TIMESTAMP DEFAULT NOW()
                )""", ())
        except Exception:
            logger.debug("plan_snapshots 表创建跳过（可能已存在）", exc_info=True)

    def _get_last_plan(self, user_id):
        import json
        self._ensure_table()
        r = get_db().fetchone(
            "SELECT plan_json FROM plan_snapshots WHERE user_id=%s ORDER BY created_at DESC LIMIT 1",
            (user_id,))
        if r and r.get("plan_json"):
            p = json.loads(r["plan_json"]) if isinstance(r["plan_json"], str) else r["plan_json"]
            return [it.get("skill_id","") for it in p.get("items",[])]
        return []

    def _diff_plan(self, old, new):
        new_skills = [it["skill_id"] for it in new]
        a = [s for s in new_skills if s not in old]
        r = [s for s in old if s not in new_skills]
        return {"added": a, "removed": r, "has_changes": len(a)+len(r) > 0, "change_count": len(a)+len(r)}

    def _save_snapshot(self, uid, items, reason, changes):
        import json
        self._ensure_table()
        try:
            get_db().execute(
                "INSERT INTO plan_snapshots (user_id,plan_json,changes_json,reason) VALUES (%s,%s,%s,%s)",
                (uid, json.dumps({"items": items}), json.dumps(changes), reason))
        except Exception as e:
            logger.warning("保存快照失败: %s", e)


# Phase 4: 延迟构造（DI 容器未就绪时回退到默认构造）
_adaptive_planner = None


def _get_adaptive_planner():
    global _adaptive_planner
    if _adaptive_planner is None:
        _adaptive_planner = AdaptivePlanGenerator()
    return _adaptive_planner


# 模块级属性，import 时触发延迟构造
adaptive_planner = _get_adaptive_planner()
