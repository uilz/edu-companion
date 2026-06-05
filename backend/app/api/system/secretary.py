"""秘书系统 API 端点

提供: 秘书偏好管理、提案查询/采纳/拒绝/暂缓、快照获取、简报、LLM 提案生成
"""

from __future__ import annotations

import json
import logging
import os
import time
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException

from app.domain.secretary.secretary_service import SecretaryService
from app.domain.secretary.models import Proposal, ScopeSpec, SecretaryPrefs
from app.domain.secretary.proposal_store import ProposalStore
from shared.constants import DEFAULT_USER_ID

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/secretary", tags=["秘书系统"])

# ── 数据目录 ──

_DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
_PREFS_DIR = os.path.join(_DATA_DIR, "secretary_prefs")
_POLICY_DIR = os.path.join(_DATA_DIR, "policy_memory")


# ── 辅助函数 ──


def _load_prefs(user_id: str) -> dict:
    """加载用户偏好（简单 JSON 文件存储）"""
    os.makedirs(_PREFS_DIR, exist_ok=True)
    path = os.path.join(_PREFS_DIR, f"{user_id}.json")
    if os.path.exists(path):
        try:
            with open(path) as f:
                return json.load(f)
        except Exception as e:
            logger.warning("Failed to load user prefs for %s: %s", user_id, e)
    return {
        "enabled_extensions": [],
        "quiet_hours_start": "22:00",
        "quiet_hours_end": "08:00",
        "max_proactive_per_day": 5,
    }


def _save_prefs(user_id: str, prefs: dict) -> None:
    """保存用户偏好"""
    os.makedirs(_PREFS_DIR, exist_ok=True)
    with open(os.path.join(_PREFS_DIR, f"{user_id}.json"), "w") as f:
        json.dump(prefs, f, ensure_ascii=False, indent=2)


def _get_proposal_by_id(store: ProposalStore, proposal_id: str, user_id: str) -> Proposal | None:
    """通过 ID 获取提案对象"""
    try:
        db = store._get_db()
        row = db.fetchone(
            "SELECT * FROM secretary_proposals WHERE id = %s AND user_id = %s",
            (proposal_id, user_id),
        )
        if row:
            from ..domain.secretary.models import Proposal
            return Proposal(
                id=row["id"],
                emoji=row.get("emoji", "💡"),
                title=row["title"],
                description=row.get("description", ""),
                action_type=row["action_type"],
                payload=row.get("payload", {}),
                priority=row.get("priority", 3),
                generated_by=row.get("generated_by", ""),
                overrideable=row.get("overrideable", True),
                created_at=row.get("created_at", datetime.now(timezone.utc)),
                expires_at=row.get("expires_at"),
            )
    except Exception as e:
        logger.debug("获取提案失败: %s", e)
    return None


async def _ensure_db_schema(store: ProposalStore):
    """确保数据库表存在"""
    try:
        db = store._get_db()
        db.execute(
            "SELECT 1 FROM secretary_proposals LIMIT 1",
        )
    except Exception:
        logger.info("创建 secretary_proposals 表")
        db.execute("""
            CREATE TABLE IF NOT EXISTS secretary_proposals (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                session_id TEXT,
                emoji TEXT DEFAULT '💡',
                title TEXT NOT NULL,
                description TEXT DEFAULT '',
                action_type TEXT NOT NULL,
                payload JSONB DEFAULT '{}',
                priority INTEGER DEFAULT 3,
                generated_by TEXT DEFAULT '',
                overrideable BOOLEAN DEFAULT TRUE,
                status TEXT DEFAULT 'pending',
                metadata JSONB DEFAULT '{}',
                snoozed_until TIMESTAMP,
                created_at TIMESTAMP DEFAULT NOW(),
                expires_at TIMESTAMP,
                updated_at TIMESTAMP DEFAULT NOW()
            )
        """)


# ── 依赖 ──


def _get_service() -> SecretaryService:
    return SecretaryService()


def _get_store() -> ProposalStore:
    return ProposalStore()


# ═══════════════════════════════════════════
# 偏好
# ═══════════════════════════════════════════


@router.get("/preferences")
async def get_preferences(
    user_id: str = DEFAULT_USER_ID,
) -> dict:
    """获取用户秘书偏好"""
    prefs = _load_prefs(user_id)
    return {
        "enabled_extensions": prefs.get("enabled_extensions", []),
        "quiet_hours_start": prefs.get("quiet_hours_start", "22:00"),
        "quiet_hours_end": prefs.get("quiet_hours_end", "08:00"),
        "max_proactive_per_day": prefs.get("max_proactive_per_day", 5),
    }


# ═══════════════════════════════════════════
# 诊断与快照
# ═══════════════════════════════════════════


@router.get("/snapshot")
async def get_snapshot(
    user_id: str = DEFAULT_USER_ID,
    service: SecretaryService = Depends(_get_service),
) -> dict:
    """获取当前学习状态快照"""
    assess = await service.quick_assess(user_id=user_id)
    return {
        "cognitive_load": assess.get("cognitive_load", 0),
        "weak_count": assess.get("weak_count", 0),
        "stagnant_count": assess.get("stagnant_count", 0),
        "streak_days": assess.get("streak_days", 0),
        "summary": assess.get("summary", ""),
    }


# ═══════════════════════════════════════════
# 提案 CRUD
# ═══════════════════════════════════════════


@router.get("/proposals/pending")
async def get_pending_proposals(
    user_id: str = DEFAULT_USER_ID,
    store: ProposalStore = Depends(_get_store),
) -> list[dict]:
    """获取待处理提案"""
    await _ensure_db_schema(store)
    proposals = store.get_pending_proposals(user_id=user_id)
    return [p.model_dump() for p in proposals]


@router.get("/proposals/history")
async def get_proposal_history(
    user_id: str = DEFAULT_USER_ID,
    days: int = 7,
    store: ProposalStore = Depends(_get_store),
) -> list[dict]:
    """获取提案历史"""
    return store.get_history(user_id=user_id, days=days)


@router.post("/proposals/{proposal_id}/accept")
async def accept_proposal(
    proposal_id: str,
    user_id: str = DEFAULT_USER_ID,
    store: ProposalStore = Depends(_get_store),
) -> dict:
    """采纳提案 — 更新状态 + 触发对应系统动作"""
    # 先获取提案详情
    try:
        proposal = _get_proposal_by_id(store, proposal_id, user_id)
        if not proposal:
            raise HTTPException(404, "提案不存在或已处理")
    except HTTPException:
        raise
    except Exception as e:
        logger.warning("获取提案详情失败: %s", e)
        proposal = None

    ok = store.update_status(proposal_id, "accepted", user_id, {"action": "user_accepted", "timestamp": time.time()})
    if not ok:
        raise HTTPException(404, "提案不存在或已处理")

    # 执行提案动作
    action_result = None
    plan_adjustment = None
    if proposal:
        from app.domain.secretary.engines.proposal_action_handler import action_handler
        from app.domain.secretary.engines.policy_engine import policy_engine
        try:
            action_result = await action_handler.execute(proposal, user_id)
            logger.info("提案动作执行: %s → %s", proposal.action_type, action_result.get("success"))

            # 记录策略交互
            policy_engine.record_interaction(user_id, proposal, "accepted")

            # 触发学习路径调整
            if action_result.get("success"):
                from app.domain.secretary.engines.secretary_plan_bridge import plan_bridge
                plan_adjustment = await plan_bridge.on_proposal_accepted(proposal, user_id)

            # v6: 发射 ProposalAccepted 事件，触发 mark_expanded 等后续动作
            try:
                from app.services.common.event_service import EventService
                target_node_id = (proposal.payload or {}).get("parent_id", "") or \
                                 (proposal.payload or {}).get("target_node_id", "")
                EventService.emit_proposal_accepted(
                    user_id=user_id,
                    proposal_id=proposal_id,
                    action_type=proposal.action_type,
                    target_node_id=target_node_id,
                )
            except Exception as e:
                logger.debug("ProposalAccepted 事件发射失败: %s", e)
        except Exception as e:
            logger.warning("提案动作/计划调整失败: %s", e)

    return {
        "status": "accepted",
        "action_result": action_result,
        "plan_adjustment": plan_adjustment,
    }


@router.post("/proposals/{proposal_id}/dismiss")
async def dismiss_proposal(
    proposal_id: str,
    user_id: str = DEFAULT_USER_ID,
    reason: str = "",
    store: ProposalStore = Depends(_get_store),
) -> dict:
    """忽略提案 — 更新状态 + 记录关系记忆"""
    store.update_status(proposal_id, "dismissed", user_id, {"action": "user_dismissed", "reason": reason})

    # 记录策略关系记忆
    try:
        proposal = _get_proposal_by_id(store, proposal_id, user_id)
        if proposal:
            from app.domain.secretary.engines.policy_engine import policy_engine
            result = policy_engine.record_interaction(user_id, proposal, "dismissed")
            return {"status": "dismissed", "policy": result}
    except Exception as e:
        logger.warning("Policy record_interaction failed on dismiss: %s", e)

    return {"status": "dismissed"}


# ═══════════════════════════════════════════
# LLM 生成
# ═══════════════════════════════════════════


@router.post("/generate-llm-proposals")
async def generate_llm_proposals(
    user_id: str = DEFAULT_USER_ID,
    service: SecretaryService = Depends(_get_service),
    store: ProposalStore = Depends(_get_store),
) -> list[dict]:
    """使用 LLM 生成润色提案"""
    report = await service.diagnose(user_id=user_id)

    from ..domain.secretary.engines.llm_proposal_generator import LLMProposalGenerator
    llm = None
    try:
        from app.services.llm.llm_service import llm_service
        llm = llm_service
    except Exception as e:
        logger.warning("LLM service unavailable, proceeding without LLM: %s", e)

    gen = LLMProposalGenerator(llm_service=llm)
    proposals = await gen.generate_suggestion(report, max_proposals=3)

    for p in proposals:
        store.save_proposal(p, user_id=user_id, session_id="api")

    return [p.model_dump() for p in proposals]


# ═══════════════════════════════════════════
# 模块管理
# ═══════════════════════════════════════════


@router.get("/modules")
async def list_modules(
    user_id: str = DEFAULT_USER_ID,
) -> list[dict]:
    """列出所有秘书模块及其状态"""
    from app.domain.secretary.engines.module_registry import module_registry
    if not module_registry._modules:
        module_registry.discover_builtin()
    modules = module_registry.list_modules()
    # 恢复用户偏好覆盖
    try:
        prefs = _load_prefs(user_id)
        if prefs.get("enabled_extensions"):
            module_registry.apply_prefs(prefs["enabled_extensions"])
            modules = module_registry.list_modules()
    except Exception as e:
        logger.warning("Failed to load/apply user prefs for %s: %s", user_id, e)
    return modules


@router.post("/modules/toggle")
async def toggle_module(
    name: str,
    enabled: bool,
    user_id: str = DEFAULT_USER_ID,
) -> dict:
    """启用/禁用指定模块"""
    from app.domain.secretary.engines.module_registry import module_registry
    if not module_registry._modules:
        module_registry.discover_builtin()

    if enabled:
        module_registry.enable(name)
    else:
        module_registry.disable(name)

    # 持久化偏好
    prefs = _load_prefs(user_id)
    prefs["enabled_extensions"] = module_registry.to_prefs_list()
    _save_prefs(user_id, prefs)

    return {
        "status": "ok",
        "module": name,
        "enabled": enabled,
    }


# ═══════════════════════════════════════════
# 冷启动引导
# ═══════════════════════════════════════════


@router.get("/onboarding")
async def get_onboarding_status(
    user_id: str = DEFAULT_USER_ID,
) -> dict:
    """获取冷启动状态与引导信息"""
    try:
        from app.cognitive.storage import list_all_nodes
        nodes = list_all_nodes(user_id)
        total_nodes = len(nodes) if nodes else 0
    except Exception:
        total_nodes = 0

    is_cold_start = total_nodes < 5
    has_suggestions = total_nodes > 0

    guide_steps = [
        {"step": 1, "title": "开始学习", "description": "打开任意分区开始你的第一次学习对话", "link": "/", "done": has_suggestions},
        {"step": 2, "title": "完成练习", "description": "做几道练习题，秘书系统会根据错题生成个性化建议", "link": "/practice", "done": total_nodes > 3},
        {"step": 3, "title": "查看秘书建议", "description": "回到秘书页面，查看系统为你生成的个性化学习建议", "link": "/secretary", "done": False},
        {"step": 4, "title": "个性化配置", "description": "关闭不需要的模块，设置安静时段，定制秘书行为", "link": "/secretary/settings", "done": False},
    ]

    return {
        "is_cold_start": is_cold_start,
        "total_nodes": total_nodes,
        "guide_steps": guide_steps,
        "current_step": 1 if total_nodes == 0 else 2 if total_nodes < 3 else 3 if total_nodes < 5 else 4,
        "message": "你好！我是你的学习秘书，欢迎开始学习之旅 🎉" if is_cold_start else "感谢继续使用！你的学习数据正在丰富中 📈",
    }


# ═══════════════════════════════════════════
# 数据导出/删除 (遗忘权)
# ═══════════════════════════════════════════


@router.get("/data/export")
async def export_secretary_data(user_id: str = DEFAULT_USER_ID) -> dict:
    """导出所有秘书相关个人数据"""
    data = {
        "user_id": user_id,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "preferences": _load_prefs(user_id),
        "proposals": [],
        "policy_memory": {},
    }

    # 提案历史
    try:
        from ..domain.secretary.proposal_store import ProposalStore
        store = ProposalStore()
        db = store._get_db()
        rows = db.fetchall(
            "SELECT id, title, action_type, priority, status, created_at FROM secretary_proposals WHERE user_id = %s ORDER BY created_at DESC LIMIT 200",
            (user_id,),
        )
        if rows:
            data["proposals"] = [
                {"id": r["id"], "title": r["title"], "action_type": r["action_type"],
                 "priority": r["priority"], "status": r["status"],
                 "created_at": str(r["created_at"]) if r["created_at"] else None}
                for r in rows
            ]
    except Exception as e:
        data["proposal_error"] = str(e)

    # 关系记忆
    os.makedirs(_POLICY_DIR, exist_ok=True)
    policy_path = os.path.join(_POLICY_DIR, f"{user_id}.json")
    if os.path.exists(policy_path):
        with open(policy_path) as f:
            data["policy_memory"] = json.load(f)

    return data


@router.delete("/data/delete")
async def delete_secretary_data(user_id: str = DEFAULT_USER_ID) -> dict:
    """删除所有秘书相关个人数据 (遗忘权)"""
    deleted = {"proposals": False, "prefs_file": False, "policy_memory": False}

    # 删除提案
    try:
        from ..domain.secretary.proposal_store import ProposalStore
        store = ProposalStore()
        store._get_db().execute("DELETE FROM secretary_proposals WHERE user_id = %s", (user_id,))
        deleted["proposals"] = True
    except Exception as e:
        logger.error("Failed to delete proposals for user %s: %s", user_id, e)

    # 删除偏好
    prefs_path = os.path.join(_PREFS_DIR, f"{user_id}.json")
    if os.path.exists(prefs_path):
        os.remove(prefs_path)
        deleted["prefs_file"] = True

    # 删除关系记忆
    policy_path = os.path.join(_POLICY_DIR, f"{user_id}.json")
    if os.path.exists(policy_path):
        os.remove(policy_path)
        deleted["policy_memory"] = True

    return {"status": "deleted", "details": deleted}


