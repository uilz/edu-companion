"""
成就服务 — v7 数据桥接

流程:
1. 每次 session 完成后触发 check_achievements()
2. 从 practice_attempts + cognitive_nodes 聚合 stats
3. 调用 AchievementEngine.check_all() 检测新成就
4. 新成就存入 achievements 表
5. 返回新解锁列表供前端弹窗
"""

import json
import logging
from datetime import datetime
from typing import Optional
from app.services.analytics.achievement_engine import achievement_engine, ACHIEVEMENTS

logger = logging.getLogger(__name__)


def _ensure_table():
    """确保 achievements 表存在"""
    from app.db.database import get_db
    db = get_db()
    db.execute("""
        CREATE TABLE IF NOT EXISTS achievements (
            id          TEXT PRIMARY KEY,
            user_id     TEXT NOT NULL,
            ach_id      TEXT NOT NULL,
            level       INT DEFAULT 1,
            name        VARCHAR(100),
            icon        VARCHAR(10),
            tier        VARCHAR(20),
            description TEXT,
            unlocked_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)
    db.execute("""
        CREATE INDEX IF NOT EXISTS idx_ach_user ON achievements(user_id)
    """)
    db.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_ach_user_ach
        ON achievements(user_id, ach_id, level)
    """)


def _build_stats(user_id: str) -> dict:
    """从 v7 数据构建 stats dict 供 achievement engine 使用"""
    from app.db.database import get_db
    db = get_db()

    # 练习总数
    total = db.fetchone(
        "SELECT COUNT(*) as cnt FROM practice_attempts WHERE user_id = %s",
        (user_id,),
    )
    practice_count = total["cnt"] if total else 0

    # 正确数
    correct = db.fetchone(
        "SELECT COUNT(*) as cnt FROM practice_attempts WHERE user_id = %s AND is_correct = true",
        (user_id,),
    )
    correct_count = correct["cnt"] if correct else 0

    # 正确率
    accuracy = correct_count / max(practice_count, 1)

    # 连续学习天数 — 从 practice_attempts 按日去重
    days = db.fetchall(
        """SELECT DISTINCT DATE(created_at) as day
           FROM practice_attempts
           WHERE user_id = %s
           ORDER BY day DESC""",
        (user_id,),
    )
    day_list = [r["day"] for r in days]
    streak = _calc_streak(day_list)

    # 会话数
    sessions = db.fetchone(
        "SELECT COUNT(*) as cnt FROM practice_sessions WHERE user_id = %s",
        (user_id,),
    )
    session_count = sessions["cnt"] if sessions else 0

    # 已掌握知识点数 (proficiency >= 0.8)
    from app.cognitive import get_repo
    atoms = get_repo().get_nodes_by_level("atom", user_id) or []
    mastered_skills = sum(1 for n in atoms if n.belief.proficiency_mean >= 0.8)

    # 对话数 (取 messages 表)
    convs = db.fetchone(
        "SELECT COUNT(DISTINCT conversation_id) as cnt FROM messages WHERE role = 'user' AND user_id = %s",
        (user_id,),
    )
    conversation_count = convs["cnt"] if convs else 0

    # 快速正确 (10s 内答对)
    fast = db.fetchone(
        "SELECT COUNT(*) as cnt FROM practice_attempts WHERE user_id = %s AND is_correct = true AND time_spent_seconds <= 10",
        (user_id,),
    )
    fast_correct = fast["cnt"] if fast else 0

    # 完全正确的 session 数
    perfect = db.fetchone(
        """SELECT COUNT(*) as cnt FROM practice_sessions
           WHERE user_id = %s AND status = 'completed'
           AND total_count > 0 AND correct_count = total_count""",
        (user_id,),
    )
    perfect_session = perfect["cnt"] if perfect else 0

    # 多学科 — 从 cognitive_nodes 的 label 或 metadata 获取
    subjects = set()
    for n in atoms:
        meta = n.meta
        if meta and meta.model_extra:
            subj = meta.model_extra.get("subject", "")
            if subj:
                subjects.add(subj)
    multi_subject_count = len(subjects)

    return {
        "practice_count": practice_count,
        "correct_count": correct_count,
        "accuracy": accuracy,
        "session_count": session_count,
        "conversation_count": conversation_count,
        "streak": streak,
        "mastered_skills": mastered_skills,
        "multi_subject_count": multi_subject_count,
        "fast_correct": fast_correct,
        "perfect_session": perfect_session,
        "comeback": 0,  # 暂不支持
    }


def _calc_streak(day_list: list) -> int:
    """计算连续学习天数"""
    if not day_list:
        return 0
    from datetime import date, timedelta
    today = date.today()
    streak = 0
    for i in range(365):
        check = today - timedelta(days=i)
        if any(d == check for d in day_list):
            streak += 1
        else:
            break
    return streak


def check_achievements(user_id: str) -> list[dict]:
    """
    检测成就 — 在 session 完成后调用。

    返回新解锁的成就列表。
    """
    _ensure_table()
    from app.db.database import get_db
    db = get_db()

    # 1. 构建 stats
    stats = _build_stats(user_id)

    # 2. 获取已有成就
    existing = db.fetchall(
        "SELECT ach_id, level, unlocked_at FROM achievements WHERE user_id = %s",
        (user_id,),
    )
    existing_map = {}
    for e in existing:
        aid = e["ach_id"]
        existing_map[aid] = {
            "level": e["level"],
            "unlocked_at": e.get("unlocked_at") and str(e["unlocked_at"]),
        }

    # 3. 检测
    newly = achievement_engine.check_all(user_id, stats, existing_map)

    # 4. 存储新成就
    now = datetime.now().isoformat()
    for ach in newly:
        aid = ach["id"]
        lv = ach.get("level", 1)
        uid = f"ach_{aid}_lv{lv}_{user_id[-8:]}"
        db.execute(
            """INSERT INTO achievements (id, user_id, ach_id, level, name, icon, tier, description, unlocked_at)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
               ON CONFLICT (id) DO NOTHING""",
            (uid, user_id, aid, lv, ach["name"], ach["icon"], ach["tier"], ach["description"], now),
        )

    logger.info("成就检测: user=%s, practice=%d, new=%d", user_id, stats["practice_count"], len(newly))
    return newly


def get_all_achievements(user_id: str) -> list[dict]:
    """
    获取所有成就及进度（成就墙展示）
    """
    _ensure_table()
    from app.db.database import get_db
    db = get_db()

    stats = _build_stats(user_id)

    existing = db.fetchall(
        "SELECT ach_id, level, unlocked_at FROM achievements WHERE user_id = %s",
        (user_id,),
    )
    existing_map = {}
    for e in existing:
        aid = e["ach_id"]
        existing_map[aid] = existing_map.get(aid, {})
        existing_map[aid]["level"] = max(existing_map[aid].get("level", 0), e["level"])
        existing_map[aid]["unlocked_at"] = str(e.get("unlocked_at", ""))

    return achievement_engine.get_all_with_progress(stats, existing_map)


def get_recent_unlocks(user_id: str, limit: int = 5) -> list[dict]:
    """最近解锁的成就"""
    _ensure_table()
    from app.db.database import get_db
    db = get_db()
    rows = db.fetchall(
        """SELECT * FROM achievements
           WHERE user_id = %s
           ORDER BY unlocked_at DESC LIMIT %s""",
        (user_id, limit),
    )
    return [
        {
            "ach_id": r["ach_id"],
            "name": r["name"],
            "icon": r["icon"],
            "tier": r["tier"],
            "level": r["level"],
            "description": r["description"],
            "unlocked_at": str(r.get("unlocked_at", "")),
        }
        for r in rows
    ]


def get_badge_stats(user_id: str) -> dict:
    """徽章统计"""
    _ensure_table()
    from app.db.database import get_db
    db = get_db()

    total = db.fetchone("SELECT COUNT(*) as cnt FROM achievements WHERE user_id = %s", (user_id,))
    total_unlocked = total["cnt"] if total else 0

    by_tier = db.fetchall(
        """SELECT tier, COUNT(*) as cnt FROM achievements
           WHERE user_id = %s GROUP BY tier""",
        (user_id,),
    )
    tier_counts = {r["tier"]: r["cnt"] for r in by_tier}

    return {
        "total_unlocked": total_unlocked,
        "total_possible": len(ACHIEVEMENTS),
        "bronze": tier_counts.get("bronze", 0),
        "silver": tier_counts.get("silver", 0),
        "gold": tier_counts.get("gold", 0),
    }
