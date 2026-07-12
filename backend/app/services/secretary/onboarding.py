"""秘书冷启动引导服务 (Task #168)

将 onboarding 判定逻辑从 API 路由下沉到服务层，便于测试与复用。
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


async def get_onboarding_status(user_id: str) -> dict[str, Any]:
    """获取用户冷启动状态与引导步骤。"""
    try:
        from app.domain.cognitive import get_repo
        nodes = get_repo().list_all_nodes(user_id)
        real_nodes = [n for n in nodes if not (n.level == "partition" and n.created_by == "system")]
        total_nodes = len(real_nodes) if real_nodes else 0
        learned_nodes = sum(
            1 for n in real_nodes
            if n.belief and n.belief.alpha + n.belief.beta > 4
        )
    except Exception:
        total_nodes = 0
        learned_nodes = 0

    is_cold_start = total_nodes < 5 or learned_nodes == 0
    has_suggestions = total_nodes > 0

    guide_steps = [
        {"step": 1, "title": "开始学习", "description": "打开任意分区开始你的第一次学习对话", "link": "/", "done": has_suggestions},
        {"step": 2, "title": "完成练习", "description": "做几道练习题，秘书系统会根据错题生成个性化建议", "link": "/practice", "done": learned_nodes > 0},
        {"step": 3, "title": "查看秘书建议", "description": "回到秘书页面，查看系统为你生成的个性化学习建议", "link": "/secretary", "done": learned_nodes > 2},
        {"step": 4, "title": "个性化配置", "description": "关闭不需要的模块，设置安静时段，定制秘书行为", "link": "/secretary/settings", "done": False},
    ]

    return {
        "is_cold_start": is_cold_start,
        "total_nodes": total_nodes,
        "learned_nodes": learned_nodes,
        "guide_steps": guide_steps,
        "current_step": 1 if total_nodes == 0 else 2 if learned_nodes == 0 else 3 if learned_nodes < 3 else 4,
        "message": "你好！我是你的学习秘书，欢迎开始学习之旅 🎉" if is_cold_start else "感谢继续使用！你的学习数据正在丰富中 📈",
    }
