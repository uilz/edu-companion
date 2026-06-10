"""秘书系统 API 端点

提供: 秘书偏好管理、提案查询/采纳/拒绝/暂缓、快照获取、简报、LLM 提案生成
"""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from app.domain.auth.dependencies import current_user_id
from app.domain.secretary.secretary_service import SecretaryService
from app.domain.secretary.models import Proposal, ScopeSpec, SecretaryPrefs
from app.domain.secretary.proposal_store import ProposalStore

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/secretary", tags=["秘书系统"])


# ── 辅助函数 ──


def _load_prefs(user_id: str) -> dict:
    """加载用户偏好（从 DataRepository 读取）"""
    from app.services.common import get_data_repo
    data = get_data_repo().load(user_id)
    return data.secretary_prefs or {
        "enabled_extensions": [],
        "quiet_hours_start": "22:00",
        "quiet_hours_end": "08:00",
        "max_proactive_per_day": 5,
    }


def _save_prefs(user_id: str, prefs: dict) -> None:
    """保存用户偏好（通过 DataRepository 持久化）"""
    from app.services.common import get_data_repo
    data = get_data_repo().load(user_id)
    data.secretary_prefs = prefs
    get_data_repo().save(user_id, data)


def _get_proposal_by_id(store: ProposalStore, proposal_id: str, user_id: str) -> Proposal | None:
    """通过 ID 获取提案对象"""
    try:
        db = store._get_db()
        row = db.fetchone(
            "SELECT * FROM secretary_proposals WHERE id = %s AND user_id = %s",
            (proposal_id, user_id),
        )
        if row:
            from app.domain.secretary.models import Proposal
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
    user_id: str = Depends(current_user_id),
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
    user_id: str = Depends(current_user_id),
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
    user_id: str = Depends(current_user_id),
    source_module: str | None = None,
    action_type: str | None = None,
    priority_min: int | None = None,
    priority_max: int | None = None,
    search: str | None = None,
    store: ProposalStore = Depends(_get_store),
) -> list[dict]:
    """获取待处理提案（支持筛选参数）"""
    await _ensure_db_schema(store)
    proposals = store.get_pending_proposals(
        user_id=user_id,
        source_module=source_module,
        action_type=action_type,
        priority_min=priority_min,
        priority_max=priority_max,
        search=search,
    )
    return [p.model_dump() for p in proposals]


@router.get("/proposals/history")
async def get_proposal_history(
    user_id: str = Depends(current_user_id),
    days: int = 7,
    source_module: str | None = None,
    action_type: str | None = None,
    page: int = 1,
    page_size: int = 50,
    store: ProposalStore = Depends(_get_store),
) -> list[dict]:
    """获取提案历史（支持筛选与分页）"""
    return store.get_history(
        user_id=user_id, days=days,
        source_module=source_module, action_type=action_type,
        page=page, page_size=page_size,
    )


@router.post("/proposals/{proposal_id}/accept")
async def accept_proposal(
    proposal_id: str,
    user_id: str = Depends(current_user_id),
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
                    payload=proposal.payload,
                )
            except Exception as e:
                logger.debug("ProposalAccepted 事件发射失败: %s", e)
        except Exception as e:
            logger.warning("提案动作/计划调整失败: %s", e)

    # 触发 WS 同步
    try:
        from app.api.conversation.ws_manager import manager as ws_manager
        await ws_manager.broadcast({
            "type": "secretary_proposal_update",
            "content": {"id": proposal_id, "status": "accepted"},
        })
    except Exception:
        pass

    return {
        "status": "accepted",
        "action_result": action_result,
        "plan_adjustment": plan_adjustment,
    }


@router.post("/proposals/{proposal_id}/dismiss")
async def dismiss_proposal(
    proposal_id: str,
    user_id: str = Depends(current_user_id),
    reason: str = "",
    store: ProposalStore = Depends(_get_store),
) -> dict:
    """忽略提案 — 更新状态 + 记录关系记忆"""
    store.update_status(proposal_id, "dismissed", user_id, {"action": "user_dismissed", "reason": reason})

    # 触发 WS 同步
    try:
        from app.api.conversation.ws_manager import manager as ws_manager
        await ws_manager.broadcast({
            "type": "secretary_proposal_update",
            "content": {"id": proposal_id, "status": "dismissed"},
        })
    except Exception:
        pass

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
# 新操作: 延后 / 删除 / 恢复 / 批量
# ═══════════════════════════════════════════


@router.post("/proposals/{proposal_id}/snooze")
async def snooze_proposal(
    proposal_id: str,
    user_id: str = Depends(current_user_id),
    store: ProposalStore = Depends(_get_store),
    until: float | None = None,
) -> dict:
    """延后提案 — 状态设为 snoozed，可选指定唤醒时间"""
    ok = store.snooze_proposal(proposal_id, user_id, until_timestamp=until)
    if not ok:
        raise HTTPException(404, "提案不存在")
    # 触发 WS 同步
    try:
        from app.api.conversation.ws_manager import manager as ws_manager
        await ws_manager.broadcast({
            "type": "secretary_proposal_update",
            "content": {"id": proposal_id, "status": "snoozed", "until": until},
        })
    except Exception:
        pass
    return {"status": "snoozed"}


@router.post("/proposals/{proposal_id}/delete")
async def delete_proposal(
    proposal_id: str,
    user_id: str = Depends(current_user_id),
    store: ProposalStore = Depends(_get_store),
) -> dict:
    """删除提案 — 状态设为 deleted"""
    ok = store.delete_proposal(proposal_id, user_id)
    if not ok:
        raise HTTPException(404, "提案不存在")
    # 触发 WS 同步
    try:
        from app.api.conversation.ws_manager import manager as ws_manager
        await ws_manager.broadcast({
            "type": "secretary_proposal_update",
            "content": {"id": proposal_id, "status": "deleted"},
        })
    except Exception:
        pass
    return {"status": "deleted"}


@router.post("/proposals/{proposal_id}/restore")
async def restore_proposal(
    proposal_id: str,
    user_id: str = Depends(current_user_id),
    store: ProposalStore = Depends(_get_store),
) -> dict:
    """恢复提案 — snoozed/deleted → pending"""
    ok = store.restore_proposal(proposal_id, user_id)
    if not ok:
        raise HTTPException(404, "提案不存在或状态不可恢复")
    # 触发 WS 同步
    try:
        from app.api.conversation.ws_manager import manager as ws_manager
        await ws_manager.broadcast({
            "type": "secretary_proposal_update",
            "content": {"id": proposal_id, "status": "restored"},
        })
    except Exception:
        pass
    return {"status": "restored"}


@router.post("/proposals/batch-accept")
async def batch_accept_proposals(
    ids: list[str],
    user_id: str = Depends(current_user_id),
    store: ProposalStore = Depends(_get_store),
) -> dict:
    """批量采纳提案"""
    count = store.batch_update_status(ids, "accepted", user_id)
    # 触发 WS 同步
    try:
        from app.api.conversation.ws_manager import manager as ws_manager
        for pid in ids:
            await ws_manager.broadcast({
                "type": "secretary_proposal_update",
                "content": {"id": pid, "status": "accepted"},
            })
    except Exception:
        pass
    return {"status": "ok", "count": count}


@router.post("/proposals/batch-dismiss")
async def batch_dismiss_proposals(
    ids: list[str],
    user_id: str = Depends(current_user_id),
    store: ProposalStore = Depends(_get_store),
) -> dict:
    """批量忽略提案"""
    count = store.batch_update_status(ids, "dismissed", user_id)
    # 触发 WS 同步
    try:
        from app.api.conversation.ws_manager import manager as ws_manager
        for pid in ids:
            await ws_manager.broadcast({
                "type": "secretary_proposal_update",
                "content": {"id": pid, "status": "dismissed"},
            })
    except Exception:
        pass
    return {"status": "ok", "count": count}


# ═══════════════════════════════════════════
# LLM 生成
# ═══════════════════════════════════════════


@router.post("/generate-llm-proposals")
async def generate_llm_proposals(
    user_id: str = Depends(current_user_id),
    service: SecretaryService = Depends(_get_service),
    store: ProposalStore = Depends(_get_store),
) -> list[dict]:
    """使用 LLM 生成润色提案"""
    report = await service.diagnose(user_id=user_id)

    from app.domain.secretary.engines.llm_proposal_generator import LLMProposalGenerator
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
    user_id: str = Depends(current_user_id),
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
    user_id: str = Depends(current_user_id),
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
# 主动检查器控制
# ═══════════════════════════════════════════


@router.post("/checker/run")
async def run_checker(
    user_id: str = Depends(current_user_id),
) -> dict:
    """手动触发一次主动检查"""
    from app.domain.secretary.engines.active_checker import active_checker
    try:
        findings = await active_checker.run_check()
        return {
            "status": "ok",
            "modules_run": findings.get("modules_run", 0),
            "proposals_generated": findings.get("proposals_generated", 0),
            "reasons": findings.get("reasons", []),
        }
    except Exception as e:
        logger.warning("主动检查执行失败: %s", e)
        return {"status": "error", "detail": str(e)}


@router.get("/checker/status")
async def get_checker_status(
    user_id: str = Depends(current_user_id),
) -> dict:
    """获取主动检查器状态"""
    from app.domain.secretary.engines.active_checker import active_checker
    from app.domain.secretary.engines.module_registry import module_registry

    modules = module_registry.list_modules()
    return {
        "running": active_checker._running if hasattr(active_checker, '_running') else False,
        "check_interval": active_checker._check_interval if hasattr(active_checker, '_check_interval') else 600,
        "modules": modules,
        "module_count": len(modules),
        "enabled_modules": [m["name"] for m in modules if m.get("enabled")],
    }


@router.post("/checker/configure")
async def configure_checker(
    body: dict,
    user_id: str = Depends(current_user_id),
) -> dict:
    """配置主动检查器

    Body:
        check_interval: int | None — 检查间隔（秒），默认 600
        enable_modules: list[str] | None — 启用模块列表
    """
    from app.domain.secretary.engines.active_checker import active_checker
    from app.domain.secretary.engines.module_registry import module_registry

    interval = body.get("check_interval")
    if interval and isinstance(interval, (int, float)) and 60 <= interval <= 3600:
        active_checker._check_interval = int(interval)
        logger.info("主动检查间隔已更新: %ds", interval)

    enable_modules = body.get("enable_modules")
    if enable_modules and isinstance(enable_modules, list):
        for name in module_registry._modules:
            enabled = name in enable_modules
            module_registry._enabled[name] = enabled

    return {
        "status": "ok",
        "check_interval": active_checker._check_interval,
        "enabled_modules": [n for n, e in module_registry._enabled.items() if e],
    }


# ═══════════════════════════════════════════
# 冷启动引导
# ═══════════════════════════════════════════


@router.get("/onboarding")
async def get_onboarding_status(
    user_id: str = Depends(current_user_id),
) -> dict:
    """获取冷启动状态与引导信息"""
    try:
        from app.cognitive import get_repo
        nodes = get_repo().list_all_nodes(user_id)
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
# 执行结果回传
# ═══════════════════════════════════════════


@router.post("/proposals/{proposal_id}/execution-result")
async def report_execution_result(
    proposal_id: str,
    body: dict,
    user_id: str = Depends(current_user_id),
    store: ProposalStore = Depends(_get_store),
) -> dict:
    """用户完成提案动作后回传执行结果

    Body:
        success: bool
        message: str
        details: str | None
        completed_at: int (epoch ms)
    """
    try:
        result_payload = {
            "success": body.get("success", True),
            "message": body.get("message", ""),
            "details": body.get("details"),
            "completed_at": body.get("completed_at", int(time.time() * 1000)),
        }
        # 直接更新 metadata 中的 execution_result（顶级字段）
        db = store._get_db()
        db.execute(
            "UPDATE secretary_proposals SET "
            "metadata = COALESCE(metadata, '{}'::jsonb) || %s::jsonb "
            "WHERE id = %s AND user_id = %s",
            (json.dumps({"execution_result": result_payload}), proposal_id, user_id),
        )
        logger.info(
            "提案执行结果回传: proposal=%s user=%s success=%s",
            proposal_id, user_id, result_payload["success"],
        )
        return {"status": "ok", "result": result_payload}
    except Exception as e:
        logger.warning("执行结果回传失败: %s", e)
        return {"status": "error", "detail": str(e)}


# ═══════════════════════════════════════════
# 数据导出/删除 (遗忘权)
# ═══════════════════════════════════════════


@router.get("/data/export")
async def export_secretary_data(user_id: str = Depends(current_user_id)) -> dict:
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
        from app.domain.secretary.proposal_store import ProposalStore
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
    try:
        from app.services.common import get_data_repo
        user_data = get_data_repo().load(user_id)
        data["policy_memory"] = user_data.policy_memory
    except Exception as e:
        data["policy_memory_error"] = str(e)

    return data


@router.delete("/data/delete")
async def delete_secretary_data(user_id: str = Depends(current_user_id)) -> dict:
    """删除所有秘书相关个人数据 (遗忘权)"""
    deleted = {"proposals": False, "prefs": False, "policy_memory": False}

    # 删除提案
    try:
        from app.domain.secretary.proposal_store import ProposalStore
        store = ProposalStore()
        store._get_db().execute("DELETE FROM secretary_proposals WHERE user_id = %s", (user_id,))
        deleted["proposals"] = True
    except Exception as e:
        logger.error("Failed to delete proposals for user %s: %s", user_id, e)

    # 清空偏好 + 关系记忆（通过 DataRepository）
    try:
        from app.services.common import get_data_repo
        user_data = get_data_repo().load(user_id)
        user_data.secretary_prefs = {}
        user_data.policy_memory = {}
        get_data_repo().save(user_id, user_data)
        deleted["prefs"] = True
        deleted["policy_memory"] = True
    except Exception as e:
        logger.error("Failed to clear secretary data via storage: %s", e)

    return {"status": "deleted", "details": deleted}


# ══════════════════════════════════════════════════════════════
#  Agent 助手 — 意图路由 + 对话
# ══════════════════════════════════════════════════════════════

from pydantic import BaseModel, Field


class AgentChatRequest(BaseModel):
    message: str = Field(..., min_length=1)
    current_page: str = "/"
    conversation_id: str | None = None


@router.post("/agent/chat")
async def agent_chat(body: AgentChatRequest, user_id: str = Depends(current_user_id)):
    """Agent 助手对话 — SSE 流式返回

    流程: 用户输入 → 加载工具 schema → LLM 分析意图 → 流式返回 token + tool_call 事件
    """
    from app.domain.secretary.tools.tool_registry import ToolRegistry
    from app.services.common import get_data_repo
    from app.services.knowledge.tree_ops import tree_ops
    from app.schemas.conversation import Conversation
    import uuid

    # ── 创建/复用 secretary 类型会话 ──
    conv_id = body.conversation_id
    if not conv_id:
        data = get_data_repo().load(user_id)
        # 创建临时分区下的 secretary 会话
        temp_partition = None
        for pid, p in data.partitions.items():
            if getattr(p, "is_temp", False):
                temp_partition = p
                break

        if not temp_partition:
            temp_partition, _ = tree_ops._ensure_temp_partition(user_id, data)

        conv = Conversation(
            id=str(uuid.uuid4()),
            parent_id=temp_partition.id,
            parent_type="partition",
            type="secretary",
            name="AI 秘书对话",
        )
        conv.partition_id = temp_partition.id
        conv.is_temporary = True
        data.conversations[conv.id] = conv
        get_data_repo().save(user_id, data)
        conv_id = conv.id

    # ── 加载 tools schema ──
    registry = ToolRegistry()
    tools_dir = Path(__file__).resolve().parent.parent.parent.parent / "app" / "domain" / "secretary" / "tools"
    registry.discover(str(tools_dir))
    tool_schemas = registry.get_schema()

    async def event_stream():
        # 返回 conversation_id 事件
        yield f"event: conversation\ndata: {json.dumps({'conversation_id': conv_id})}\n\n"

        # ── 调用 Agent LLM 进行意图分析 ──
        try:
            from app.domain.secretary.agent_llm import agent_generate_stream

            async for event in agent_generate_stream(
                user_message=body.message,
                current_page=body.current_page,
                tool_schemas=tool_schemas,
                user_id=user_id,
            ):
                if event["type"] == "token":
                    yield f"event: token\ndata: {json.dumps({'delta': event['delta']})}\n\n"
                elif event["type"] == "tool_call":
                    tc = event["tool_call"]
                    if not isinstance(tc, dict):
                        tc = {"name": str(tc), "arguments": {}}
                    tool_name = tc.get("name", "")
                    tool_args = tc.get("arguments", {})

                    # 执行工具获取真实结果（confirmation_text + route）
                    tool_def = registry.get_tool(tool_name)
                    route = tool_def.route if tool_def else None
                    confirmation_text = f'即将执行 {tool_name}'
                    require_confirmation = tool_def.require_confirmation if tool_def else True
                    tool_result_data = None

                    if tool_def:
                        try:
                            tool_result = await registry.execute(tool_name, tool_args)
                            # 使用工具执行结果中的实际值
                            confirmation_text = tool_result.confirmation_text or confirmation_text
                            if tool_result.route_target:
                                route = {
                                    "target": tool_result.route_target,
                                    "params": tool_result.route_params or {},
                                }
                            tool_result_data = tool_result.data
                        except Exception:
                            pass  # 执行失败时使用默认值

                    tool_data = {
                        'name': tool_name,
                        'arguments': tool_args,
                        'confidence': tc.get('confidence', 0.8),
                        'require_confirmation': require_confirmation,
                        'route': route,
                        'confirmation_text': confirmation_text,
                    }
                    yield f"event: tool_call\ndata: {json.dumps(tool_data)}\n\n"

                    # 基于工具结果让 LLM 生成后续回复
                    if tool_result_data is not None:
                        try:
                            from app.domain.secretary.agent_llm import agent_generate_followup
                            async for followup_event in agent_generate_followup(
                                user_message=body.message,
                                tool_name=tool_name,
                                tool_result=tool_result_data,
                                user_id=user_id,
                            ):
                                if followup_event["type"] == "token":
                                    yield f"event: token\ndata: {json.dumps({'delta': followup_event['delta']})}\n\n"
                        except Exception:
                            pass  # 后续回复失败不影响主流程
                elif event["type"] == "done":
                    pass  # 最后统一发送 done

        except Exception as e:
            logger = __import__("logging").getLogger(__name__)
            logger.error("Agent LLM 调用失败: %s", e)
            yield f"event: token\ndata: {json.dumps({'delta': '抱歉，AI 服务暂时不可用，请稍后重试。'})}\n\n"

        yield "event: done\ndata: {}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ══════════════════════════════════════════════════════════════
#  Agent 偏好
# ══════════════════════════════════════════════════════════════

class AgentPreferencesRequest(BaseModel):
    confirm_mode: str = "smart"
    auto_jump_threshold: float = 0.85


@router.get("/agent/preferences")
async def get_agent_preferences(user_id: str = Depends(current_user_id)):
    """获取 Agent 助手偏好"""
    from app.services.common import get_data_repo
    data = get_data_repo().load(user_id)
    prefs = data.secretary_prefs.get("agent", {})
    return {
        "confirm_mode": prefs.get("confirm_mode", "smart"),
        "auto_jump_threshold": prefs.get("auto_jump_threshold", 0.85),
    }


@router.post("/agent/preferences")
async def set_agent_preferences(
    body: AgentPreferencesRequest,
    user_id: str = Depends(current_user_id),
):
    """设置 Agent 助手偏好"""
    valid_modes = {"smart", "always", "never"}
    if body.confirm_mode not in valid_modes:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid confirm_mode. Must be one of: {valid_modes}",
        )

    from app.services.common import get_data_repo
    data = get_data_repo().load(user_id)
    if "agent" not in data.secretary_prefs:
        data.secretary_prefs["agent"] = {}
    data.secretary_prefs["agent"]["confirm_mode"] = body.confirm_mode
    data.secretary_prefs["agent"]["auto_jump_threshold"] = body.auto_jump_threshold
    get_data_repo().save(user_id, data)

    return {
        "confirm_mode": body.confirm_mode,
        "auto_jump_threshold": body.auto_jump_threshold,
    }


