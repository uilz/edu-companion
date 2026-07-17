"""Profile Domain — 镜像叙事生成器。

Profile 是 Growth + LearnerModel 的 Projection，不持有独立存储。
本模块只负责将现有数据转化为「苹果果眼中」的叙事文案。
"""

from app.domain.profile.narrative import build_mirror_narrative, build_prefs

__all__ = [
    "build_mirror_narrative",
    "build_prefs",
]
