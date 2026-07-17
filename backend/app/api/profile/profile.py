"""Profile API — 学习者画像查询接口。

供 Profile 页面消费。回答「苹果果现在怎么看我？」
而非「数据库里存了什么」。

返回结构：
  - mirror_narrative: 带 highlight 标签的 HTML 镜像叙事
  - prefs: 4 条学习偏好键值对（学习方式 / 节奏 / 学科 / 次数）
"""

from fastapi import APIRouter, Depends, HTTPException

from app.domain.auth.dependencies import current_user_id
from app.domain.growth.service import GrowthService
from app.domain.profile.narrative import build_mirror_narrative, build_prefs
from app.application.di import get_growth_service

router = APIRouter(prefix="/api/profile", tags=["profile"])


@router.get("", response_model=dict)
async def get_profile(
    user_id: str = Depends(current_user_id),
    growth_service: GrowthService = Depends(get_growth_service),
):
    """获取学习者画像。

    返回镜像叙事 + 偏好网格，不含属于 Growth 页面的 goals / timeline。
    """
    if not user_id:
        raise HTTPException(status_code=401, detail="请先登录")

    profile = _get_learner_profile(user_id)
    growth_summary = await growth_service.get_growth_summary(user_id)

    mirror_narrative = build_mirror_narrative(profile, growth_summary)
    prefs = build_prefs(profile, growth_summary, first_record=growth_summary.get("first_record"))

    return {
        "mirror_narrative": mirror_narrative,
        "prefs": prefs,
    }


def _get_learner_profile(user_id: str) -> dict:
    """从 LearnerModelEngine 获取画像，补充默认值。"""
    try:
        from shared.learner_model import get_learner_model
        engine = get_learner_model()
        profile = engine.get_or_create_profile(user_id)
        return {
            "user_id": profile.user_id,
            "nickname": profile.nickname or "学习者",
            "subjects": profile.subjects or [],
            "learning_style": profile.learning_style.value
                if hasattr(profile.learning_style, "value") else str(profile.learning_style),
        }
    except Exception:
        return {
            "user_id": user_id,
            "nickname": "学习者",
            "subjects": [],
            "learning_style": "reading",
        }
