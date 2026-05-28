"""共享常量与工具函数"""

# 默认用户 ID — 单用户模式下使用的全局常量
DEFAULT_USER_ID = "default_user"


def get_user_id(user_id: str | None = None) -> str:
    """获取用户ID，None时回退默认"""
    return user_id or DEFAULT_USER_ID


# ── 掌握度判定（独立于 BKT 引擎）──

_MASTERY_THRESHOLD = 0.8  # 与 settings.bkt_mastery_threshold 默认值一致


def get_mastery_label(p_known: float, attempt_count: int = 0) -> str:
    """将掌握概率映射为中文掌握等级字符串。

    从 BKTEngine.get_mastery_level 提取的纯函数，无引擎依赖。
    """
    if attempt_count == 0:
        return "未接触"
    elif p_known < 0.3:
        return "初学"
    elif p_known < 0.6:
        return "发展中"
    elif p_known < _MASTERY_THRESHOLD:
        return "接近掌握"
    else:
        return "已掌握"


def recommend_practice_items(
    states: dict,
    top_n: int = 5,
) -> list[dict]:
    """推荐需要练习的知识点（独立于 BKT 引擎）。

    从 BKTEngine.recommend_practice 提取的纯函数。
    ``states`` 的值需提供 ``.p_known`` 和 ``.attempt_count`` 属性。
    """
    priority_map = {
        "接近掌握": 1.0,
        "发展中": 0.7,
        "初学": 0.5,
        "未接触": 0.3,
        "已掌握": 0.0,
    }
    recommendations: list[dict] = []
    for skill_id, state in states.items():
        level = get_mastery_label(state.p_known, state.attempt_count)
        priority = priority_map.get(level, 0.0)
        recommendations.append({
            "skill_id": skill_id,
            "level": level,
            "priority": priority,
            "p_known": state.p_known,
        })
    recommendations.sort(key=lambda x: x["priority"], reverse=True)
    return [r for r in recommendations if r["priority"] > 0][:top_n]
