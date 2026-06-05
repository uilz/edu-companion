"""共享常量与工具函数"""

# 默认用户 ID — 单用户模式下使用的全局常量
DEFAULT_USER_ID = "default_user"


def get_user_id(user_id: str | None = None) -> str:
    """获取用户ID，None时回退默认"""
    return user_id or DEFAULT_USER_ID


def get_user_id_from_request(request) -> str:
    """从 FastAPI Request 对象提取当前用户 ID

    优先使用认证中间件注入的 request.state.user_id，
    回退到查询参数 user_id，最终回退到 DEFAULT_USER_ID。
    """
    # 1. 认证中间件注入
    state_uid = getattr(request.state, "user_id", None)
    if state_uid:
        return state_uid
    # 2. 查询参数兼容
    try:
        q_uid = request.query_params.get("user_id")
        if q_uid:
            return q_uid
    except Exception:
        pass
    return DEFAULT_USER_ID


# ── 掌握度判定 ──

_MASTERY_THRESHOLD = 0.8


def get_mastery_label(p_known: float, attempt_count: int = 0) -> str:
    """将掌握概率映射为中文掌握等级字符串。

    纯函数：根据 proficiency 和 attempt_count 判定掌握等级。
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
    """推荐需要练习的知识点。

    纯函数：按掌握度和优先级排序。
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
