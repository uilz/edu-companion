"""共享常量与工具函数"""

# ⚠️ 业务层 protocol/service 签名兼容默认参数（仅用于类型默认值；业务逻辑
# 必须由调用方显式传入真实 user_id）。新的中间件与前端代码不得再依赖此值。
# 详见 docs/CHANGELOG.md 中"default_user 移除"条目。
DEFAULT_USER_ID = "default_user"


def get_user_id(user_id: str | None = None) -> str | None:
    """获取用户ID，None时直接透传（由调用方决定是否拒绝）"""
    return user_id or None


def get_user_id_from_request(request) -> str | None:
    """从 FastAPI Request 对象提取当前用户 ID

    优先使用认证中间件注入的 request.state.user_id，
    其次回退到查询参数 user_id；取不到时返回 None。
    """
    # 1. 认证中间件注入
    state_uid = getattr(request.state, "user_id", None)
    if state_uid:
        return state_uid
    # 2. 查询参数兼容（业务层决定是否接受 query 传 user_id）
    try:
        q_uid = request.query_params.get("user_id")
        if q_uid:
            return q_uid
    except Exception:
        pass
    return None


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
