"""内置模块: 回归用户检测 (ReturnUserDetection)

功能: 检测用户是否超过5天未登录，生成欢迎回归提案
触发条件:
  - 用户上次活跃时间距今 >= 5 天 (432000 秒)
  - 数据文件 data/secretary/last_active_{user_id}.json 中的 last_active 时间戳

使用简单文件存储每天记录一次最后活跃时间，无需数据库。
"""

from __future__ import annotations

import json
import logging
import os
import time
from datetime import datetime, timezone

from ..models import Proposal
from .context_engine import SessionContext
from .module_registry import SecretaryModule, ModuleMeta

logger = logging.getLogger(__name__)

# 数据存储根目录
_DATA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "data",
    "secretary",
)

_ABSENCE_THRESHOLD_SECONDS = 5 * 24 * 3600  # 5 天


def _ensure_data_dir() -> None:
    """确保数据目录存在"""
    os.makedirs(_DATA_DIR, exist_ok=True)


def _last_active_path(user_id: str) -> str:
    """获取用户最后活跃记录文件路径"""
    return os.path.join(_DATA_DIR, f"last_active_{user_id}.json")


def get_last_active(user_id: str) -> float | None:
    """读取用户最后活跃时间戳，不存在返回 None"""
    path = _last_active_path(user_id)
    try:
        if not os.path.isfile(path):
            return None
        with open(path, "r") as f:
            data = json.load(f)
        return data.get("last_active")
    except (json.JSONDecodeError, OSError) as e:
        logger.debug("读取用户活跃记录失败 %s: %s", user_id, e)
        return None


def touch_last_active(user_id: str) -> None:
    """记录用户当前活跃时间"""
    _ensure_data_dir()
    path = _last_active_path(user_id)
    try:
        now = time.time()
        with open(path, "w") as f:
            json.dump({"user_id": user_id, "last_active": now}, f)
    except OSError as e:
        logger.warning("写入用户活跃记录失败 %s: %s", user_id, e)


class ReturnUserDetectionModule(SecretaryModule):
    """回归用户检测模块"""

    @property
    def meta(self) -> ModuleMeta:
        return ModuleMeta(
            name="return_user_detection",
            display_name="回归用户检测",
            emoji="👋",
            description="检测超过5天未登录的用户，生成欢迎回归提案",
            default_enabled=True,
            run_interval_seconds=3600,  # 每小时检查一次
        )

    async def on_activate(self) -> None:
        """模块激活时确保数据目录存在"""
        _ensure_data_dir()

    async def run_check(
        self, user_id: str, ctx: SessionContext | None = None,
    ) -> list[Proposal]:
        """检测用户是否长时间未登录"""
        proposals: list[Proposal] = []

        last_active = get_last_active(user_id)
        now = time.time()

        # 首次使用，尚无记录 -> 记录此次活跃并跳过
        if last_active is None:
            touch_last_active(user_id)
            return proposals

        elapsed = now - last_active

        # 未超过阈值，正常记录活跃（保持文件为最新）
        if elapsed < _ABSENCE_THRESHOLD_SECONDS:
            # 每 24 小时更新一次文件，避免频繁 IO
            if elapsed >= 86400:
                touch_last_active(user_id)
            return proposals

        # 超过 5 天未登录 —— 生成欢迎回归提案
        days_absent = int(elapsed // 86400)
        last_active_dt = datetime.fromtimestamp(last_active, tz=timezone.utc)

        # 格式化时间
        local_dt = last_active_dt.astimezone()
        date_str = local_dt.strftime("%m月%d日")

        proposals.append(Proposal(
            emoji="👋",
            title=f"👋 欢迎回来！已经 {days_absent} 天没见了",
            description=(
                f"上次学习停留在 {date_str}，已经 {days_absent} 天过去了。"
                f"建议从上次学习的内容快速回顾开始，帮你重新找回节奏。"
            ),
            action_type="review",
            payload={
                "days_absent": days_absent,
                "last_active": last_active,
            },
            priority=2,  # 中等优先级，欢迎提示不具紧迫性
            generated_by="return_user_detection",
            overrideable=True,
        ))

        # 记录此次活跃，避免重复发送
        touch_last_active(user_id)

        return proposals
