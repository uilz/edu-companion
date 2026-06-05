"""策略引擎 — 提案过滤、去重、优先级衰减、打扰预算管理

设计:
1. 勿扰时段：仅保留 priority=1 的紧急提案
2. 去重：相同 action_type + kp_id 合并
3. 每日上限：从用户设置读取（默认5条）
4. 关系记忆：连续3次忽略同类提案，优先级自动降一级
5. Orchestrator 否决权：标记"本轮跳过"

调用位置:
  - active_checker 生成提案后 → policy_engine.filter()
  - /accept / /dismiss 触发时 → policy_engine.record_interaction()
"""

from __future__ import annotations

from shared.constants import DEFAULT_USER_ID
import json
import logging
import os
import time
from datetime import datetime, timezone
from collections import defaultdict
from ..models import Proposal

logger = logging.getLogger(__name__)

_MEMORY_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "..", "data", "policy_memory")


# ═══════════════════════════════════════════
# 关系记忆存储
# ═══════════════════════════════════════════

class RelationMemory:
    """关系记忆 — 记录用户对各类提案的忽略/采纳历史"""

    def __init__(self) -> None:
        os.makedirs(_MEMORY_DIR, exist_ok=True)

    def _path(self, user_id: str) -> str:
        return os.path.join(_MEMORY_DIR, f"{user_id}.json")

    def _load(self, user_id: str) -> dict[str, Any]:
        path = self._path(user_id)
        if os.path.exists(path):
            try:
                with open(path) as f:
                    return json.load(f)
            except Exception as e:
                logger.warning("Failed to load policy memory from %s: %s", path, e)
        return {"ignore_counts": {}, "accept_counts": {}, "updated_at": time.time()}

    def _save(self, user_id: str, data: dict) -> None:
        data["updated_at"] = time.time()
        with open(self._path(user_id), "w") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def record_accept(self, user_id: str, action_type: str, kp_id: str) -> None:
        """记录采纳"""
        data = self._load(user_id)
        key = f"{action_type}:{kp_id}" if kp_id else action_type
        data["accept_counts"][key] = data["accept_counts"].get(key, 0) + 1
        # 采纳也重置忽略计数
        data["ignore_counts"][key] = 0
        self._save(user_id, data)

    def record_ignore(self, user_id: str, action_type: str, kp_id: str) -> None:
        """记录忽略，返回是否达到降级阈值（连续3次）"""
        data = self._load(user_id)
        key = f"{action_type}:{kp_id}" if kp_id else action_type
        data["ignore_counts"][key] = data["ignore_counts"].get(key, 0) + 1
        count = data["ignore_counts"][key]
        self._save(user_id, data)
        return count >= 3

    def get_priority_bias(self, user_id: str, action_type: str, kp_id: str) -> int:
        """获取优先级偏置（降级：-1，正常：0）"""
        data = self._load(user_id)
        key = f"{action_type}:{kp_id}" if kp_id else action_type
        ignore_count = data.get("ignore_counts", {}).get(key, 0)
        if ignore_count >= 5:
            return -2
        if ignore_count >= 3:
            return -1
        return 0


# ═══════════════════════════════════════════
# 策略引擎
# ═══════════════════════════════════════════

class PolicyEngine:
    """提案策略引擎 — 过滤/去重/限流/降级"""

    def __init__(self) -> None:
        self._memory = RelationMemory()
        self._session_veto: dict[str, set[str]] = defaultdict(set)  # session_id → set of proposal_ids

    async def filter(
        self,
        proposals: list[Proposal],
        user_id: str = DEFAULT_USER_ID,
        quiet_hours: bool = False,
        daily_used: int = 0,
        max_daily: int = 5,
        session_id: str | None = None,
    ) -> list[Proposal]:
        """对提案列表执行全部策略过滤

        返回过滤后的提案列表（按 priority 排序）
        """
        if not proposals:
            return []

        # 1. 勿扰时段过滤
        if quiet_hours:
            proposals = [p for p in proposals if p.priority <= 2]

        # 2. Orchestrator 否决
        if session_id:
            vetoed = self._session_veto.get(session_id, set())
            proposals = [p for p in proposals if p.id not in vetoed]

        # 3. 去重：相同 action_type + kp_id 合并（保留优先级高的）
        unique: dict[str, Proposal] = {}
        for p in proposals:
            kp_id = (p.payload or {}).get("kp_id", "")
            dedup_key = f"{p.action_type}:{kp_id}"
            if dedup_key in unique:
                existing = unique[dedup_key]
                if p.priority < existing.priority:
                    unique[dedup_key] = p
            else:
                unique[dedup_key] = p
        proposals = list(unique.values())

        # 4. 关系记忆降级
        for p in proposals:
            kp_id = (p.payload or {}).get("kp_id", "")
            bias = self._memory.get_priority_bias(user_id, p.action_type, kp_id)
            if bias < 0:
                p.priority = min(p.priority - bias, 5)
                logger.debug("提案降级: %s priority %d→%d (bias=%d)", p.id, p.priority + bias, p.priority, bias)

        # 5. 每日上限
        if daily_used >= max_daily:
            # 超过上限，只保留 priority=1 的紧急提案
            proposals = [p for p in proposals if p.priority <= 1]

        # 6. 按优先级排序
        proposals.sort(key=lambda p: p.priority)
        return proposals

    def record_interaction(
        self,
        user_id: str,
        proposal: Proposal,
        action: str,  # "accepted" | "dismissed"
    ) -> dict[str, Any]:
        """记录用户对提案的交互，返回额外处理结果"""
        kp_id = (proposal.payload or {}).get("kp_id", "")
        result = {"action": action, "downgraded": False}

        if action == "accepted":
            self._memory.record_accept(user_id, proposal.action_type, kp_id)
        elif action == "dismissed":
            downgraded = self._memory.record_ignore(user_id, proposal.action_type, kp_id)
            result["downgraded"] = downgraded
            if downgraded:
                logger.info("用户连续忽略同类提案: %s %s, 已自动降级", proposal.action_type, kp_id)
                result["message"] = "同类提案已自动降级，将减少此类建议频率"

        return result

    def mark_veto(self, session_id: str, proposal_id: str) -> None:
        """Orchestrator 标记提案为本轮跳过"""
        self._session_veto[session_id].add(proposal_id)

    async def get_daily_usage(self, user_id: str) -> int:
        """获取用户今日已使用的提案推送数"""
        try:
            from ..proposal_store import ProposalStore
            store = ProposalStore()
            today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            db = store._get_db()
            row = db.fetchone(
                """SELECT COUNT(*) as cnt FROM secretary_proposals
                   WHERE user_id = %s AND DATE(created_at) = %s
                   AND status IN ('pending', 'accepted')""",
                (user_id, today),
            )
            return row["cnt"] if row else 0
        except Exception as e:
            logger.debug("获取每日用量失败: %s", e)
            return 0


# ── 全局实例 ──
policy_engine = PolicyEngine()
