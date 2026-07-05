"""LanguageRoom AI 角色服务

依据 docs/modules/language-room/overview.md §6 + ADR 0004 决策 5/6/7

核心设计：
- AI 角色**不直接复用** conversation-system 的 SSE pipeline
- AI 角色**共享** `app.infrastructure.llm.tool_repository` (tool registry)
- AI 角色不调用 LLM 做评判
- AI 纠错倾向 = 用户主动选择 (决策 6)
- 通过 Proposal 机制触发（与秘书系统一致）

支持两种角色：
  1. AI 同伴 (ai_companion) — 参与对话
  2. AI 辅助者 (ai_assistant) — 静默监听，被召唤时响应

侵入度 (invasiveness) 三档：
  - low: 仅用户召唤
  - medium: 检测卡顿时文字提示 (仅个人)
  - high: 主动提供建议 (仅个人)
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger(__name__)


# ── 纠错倾向常量 ──

CORRECTION_NONE = "none"               # 不纠错
CORRECTION_OCCASIONAL = "occasional"   # 偶尔纠错
CORRECTION_PROACTIVE = "proactive"     # 主动纠错 (用户主动选择)

# 侵入度
INVASION_LOW = "low"
INVASION_MEDIUM = "medium"
INVASION_HIGH = "high"


# ── Tool Registry 桥接 ──


def get_shared_tool_names() -> list[str]:
    """获取当前系统可用的共享 tool registry 名称列表

    AI 角色只能调用这些工具（通过 `app.infrastructure.llm.tool_repository`）

    返回的工具涵盖：
    - LLM 原生工具 (search_media, generate_practice, ...)
    - 知识树工具 (knowledge_search_nodes, knowledge_add_node, ...)
    - LanguageRoom 工具 (tool_vocabulary_capture, tool_error_mark, tool_knowledge_search, ...)
    """
    try:
        from app.infrastructure.llm.tool_repository import get_tool_repository
        repo = get_tool_repository()
        return repo.list_tools()
    except Exception as e:
        logger.warning("获取 tool registry 失败: %s", e)
        return []


def execute_shared_tool(tool_name: str, **params: Any) -> dict:
    """通过共享 tool registry 执行工具 (AI 角色入口)

    真正的实现路径：
    - 简单 tool (本模块的 liveroom_tools) → 走同步 handler (避免 async/sync 边界问题)
    - 复合 tool (knowledge_tree) → 走 tool_repository.execute() 异步
    - LLM 工具 (search_media 等) → 走 tool_executor.execute() 异步
    - 失败不抛异常，统一返回 dict (ok=False 表达失败)
    """
    try:
        # 路径 1: LanguageRoom 自己的工具 (liveroom_tools) — 同步 handler
        from app.infrastructure.llm.liveroom_tools import (
            SYNC_HANDLERS, execute_sync,
        )
        if tool_name in SYNC_HANDLERS:
            result = execute_sync(tool_name, dict(params))
            if result.get("ok"):
                return {"ok": True, "result": result, "via": "liveroom_sync_handler"}
            return {"ok": False, "error": result.get("error", "unknown")}

        # 路径 2: 知识树工具 + 其他 LLM 工具 — 走 tool_repository (async)
        from app.infrastructure.llm.tool_repository import get_tool_repository
        repo = get_tool_repository()
        tool = repo.get_tool(tool_name)
        if not tool:
            return {"ok": False, "error": f"tool {tool_name} not found"}

        import asyncio
        try:
            # 优先尝试获取 running loop (FastAPI async 上下文)
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        # 复合工具需要 action 参数
        action = params.get("action", "") if tool.is_composite else ""

        if loop and loop.is_running():
            # async 上下文 — fire-and-forget (tool_repository.execute 是 async)
            # 但 AI 角色是同步调用, 所以这里用 asyncio.run_coroutine_threadsafe
            import concurrent.futures
            future = asyncio.run_coroutine_threadsafe(
                repo.execute(tool_name, action, dict(params), user_id=params.get("user_id", "")),
                loop,
            )
            result = future.result(timeout=10)
        else:
            # sync 上下文 (e.g. 调度器线程) — 直接 run
            result = asyncio.run(repo.execute(
                tool_name, action, dict(params), user_id=params.get("user_id", ""),
            ))

        return {"ok": True, "result": result, "via": "tool_repository"}

    except Exception as e:
        logger.error("执行共享工具失败 [%s]: %s", tool_name, e)
        return {"ok": False, "error": str(e)}


# ── 数据类 ──


@dataclass
class AIPersona:
    """AI 角色配置"""
    id: str
    name: str
    target_language: str = "en"
    proficiency: str = "intermediate"   # beginner / intermediate / advanced / native
    speech_rate: str = "normal"         # slow / normal / fast
    accent: str = ""
    behavior: str = "balanced"          # talkative / balanced / concise
    correction_tendency: str = CORRECTION_NONE
    is_topic_lead: bool = False
    personality: str = ""
    background: str = ""
    is_system: bool = False

    @classmethod
    def from_row(cls, row: dict) -> "AIPersona":
        return cls(
            id=row.get("id", ""),
            name=row.get("name", ""),
            target_language=row.get("target_language", "en"),
            proficiency=row.get("proficiency", "intermediate"),
            speech_rate=row.get("speech_rate", "normal"),
            accent=row.get("accent", ""),
            behavior=row.get("behavior", "balanced"),
            correction_tendency=row.get("correction_tendency", CORRECTION_NONE),
            is_topic_lead=bool(row.get("is_topic_lead", False)),
            personality=row.get("personality", ""),
            background=row.get("background", ""),
            is_system=bool(row.get("is_system", False)),
        )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "target_language": self.target_language,
            "proficiency": self.proficiency,
            "speech_rate": self.speech_rate,
            "accent": self.accent,
            "behavior": self.behavior,
            "correction_tendency": self.correction_tendency,
            "is_topic_lead": self.is_topic_lead,
            "personality": self.personality,
            "background": self.background,
            "is_system": self.is_system,
        }


@dataclass
class InvasivenessConfig:
    """用户级侵入度配置"""
    user_id: str
    room_id: str
    invasiveness_level: str = INVASION_LOW
    helper_types: list[str] = field(default_factory=lambda: ["grammar", "vocabulary", "sentence_pattern"])
    correction_tendency: str = CORRECTION_NONE
    response_style: str = "concise"

    @classmethod
    def from_row(cls, row: dict) -> "InvasivenessConfig":
        helper_types = row.get("helper_types") or ["grammar", "vocabulary", "sentence_pattern"]
        if isinstance(helper_types, str):
            import json
            try:
                helper_types = json.loads(helper_types)
            except Exception:
                helper_types = ["grammar", "vocabulary", "sentence_pattern"]
        return cls(
            user_id=row.get("user_id", ""),
            room_id=row.get("room_id", ""),
            invasiveness_level=row.get("invasiveness_level", INVASION_LOW),
            helper_types=helper_types,
            correction_tendency=row.get("correction_tendency", CORRECTION_NONE),
            response_style=row.get("response_style", "concise"),
        )

    def upsert(self) -> "InvasivenessConfig":
        """持久化当前 config 到 ai_helper_invasiveness 表 (INSERT 或 UPDATE)

        依据 docs/modules/language-room/ai-helper.md §3 + ADR 0005
        调用方: liveroom.service.update_invasiveness / 测试 setup
        """
        import json
        from app.infrastructure.db.database import get_db
        # 确保表存在
        try:
            from app.api.liveroom.service import _ensure_tables
            _ensure_tables()
        except Exception:
            pass
        db = get_db()
        inv_id = f"INV_{self.user_id}_{self.room_id}"[:40]
        existing = db.fetchone(
            "SELECT id FROM ai_helper_invasiveness WHERE user_id = %s AND room_id = %s",
            (self.user_id, self.room_id),
        )
        if existing:
            db.execute(
                """UPDATE ai_helper_invasiveness
                   SET invasiveness_level = %s, helper_types = %s::jsonb,
                       correction_tendency = %s, response_style = %s,
                       updated_at = NOW()
                   WHERE user_id = %s AND room_id = %s""",
                (
                    self.invasiveness_level,
                    json.dumps(self.helper_types),
                    self.correction_tendency,
                    self.response_style,
                    self.user_id, self.room_id,
                ),
            )
        else:
            db.execute(
                """INSERT INTO ai_helper_invasiveness
                    (id, user_id, room_id, invasiveness_level, helper_types,
                     correction_tendency, response_style, show_to_room, created_at, updated_at)
                   VALUES (%s, %s, %s, %s, %s::jsonb, %s, %s, FALSE, NOW(), NOW())""",
                (
                    inv_id, self.user_id, self.room_id,
                    self.invasiveness_level,
                    json.dumps(self.helper_types),
                    self.correction_tendency,
                    self.response_style,
                ),
            )
        return self


# ── LLM 桥接（不调用做评判）──


def _call_llm_for_companion_response(
    persona: AIPersona,
    scenario_context: dict,
    recent_turns: list[dict],
) -> Optional[str]:
    """AI 同伴的对话生成

    关键约束:
    - **不**调用 LLM 做评判/纠错（纠错由用户主动标记）
    - 仅生成角色扮演的对话内容
    - 复用 conversation-system 的 LLM 调用入口
    """
    try:
        from app.config import settings
        from openai import OpenAI

        client = OpenAI(
            api_key=os.environ.get("OPENAI_API_KEY", ""),
            base_url=os.environ.get("OPENAI_API_BASE", ""),
        )

        # 构造系统提示
        sys_prompt = _build_companion_system_prompt(persona, scenario_context)
        messages = [{"role": "system", "content": sys_prompt}]
        for turn in recent_turns[-10:]:
            role = "assistant" if turn.get("speaker_id") == persona.id else "user"
            messages.append({
                "role": role,
                "content": turn.get("text", ""),
            })

        resp = client.chat.completions.create(
            model=settings.text_model,
            messages=messages,
            max_tokens=200,
            temperature=0.7,
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        logger.error("AI 同伴 LLM 调用失败: %s", e)
        return None


def _call_llm_for_helper_response(
    config: InvasivenessConfig,
    helper_type: str,
    query: str,
    context: dict,
    user_id: str = "",
) -> Optional[str]:
    """AI 辅助者响应（用户召唤时调用）

    关键改进 (Task #35):
    - 通过共享 tool registry 调用 `tool_knowledge_search` 搜索相关知识
    - 用搜索结果增强 LLM context, 给出更有依据的回答
    - 搜索失败时降级到原行为 (不破坏对话)

    helper_type: grammar / vocabulary / sentence_pattern
    """
    try:
        from app.config import settings
        from openai import OpenAI

        # ── 1. 通过 tool registry 搜索相关知识 (Task #35 核心改动) ──
        knowledge_ctx = ""
        if user_id and query:
            search_result = execute_shared_tool(
                "tool_knowledge_search",
                user_id=user_id,
                query=query,
                max_results=3,
            )
            if search_result.get("ok"):
                nodes = search_result.get("result", {}).get("results", [])
                if nodes:
                    lines = ["[相关知识上下文]"]
                    for n in nodes[:3]:
                        lines.append(
                            f"- {n.get('label', '')}: {n.get('brief', '')[:80]}"
                        )
                    knowledge_ctx = "\n".join(lines)

        client = OpenAI(
            api_key=os.environ.get("OPENAI_API_KEY", ""),
            base_url=os.environ.get("OPENAI_API_BASE", ""),
        )

        sys_prompt = _build_helper_system_prompt(helper_type, config)
        recent_text = context.get("recent_text", "")
        user_msg_parts = [f"问题: {query}"]
        if recent_text:
            user_msg_parts.append(f"\n上下文: {recent_text}")
        if knowledge_ctx:
            user_msg_parts.append(f"\n{knowledge_ctx}")
        user_msg = "\n".join(user_msg_parts)

        resp = client.chat.completions.create(
            model=settings.text_fast_model,
            messages=[
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": user_msg},
            ],
            max_tokens=200,
            temperature=0.3,
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        logger.error("AI 辅助者 LLM 调用失败: %s", e)
        return None


# ── 系统提示构造 ──


def _build_companion_system_prompt(persona: AIPersona, scenario: dict) -> str:
    """构造 AI 同伴系统提示（不评判、不纠错主导）"""
    parts = [
        f"你是一位 {persona.target_language} 语伴，名叫 {persona.name}。",
        f"熟练度: {persona.proficiency}",
        f"语速: {persona.speech_rate}",
        f"行为: {persona.behavior}",
    ]
    if scenario.get("prompt_text"):
        parts.append(f"当前场景: {scenario['prompt_text']}")
    if scenario.get("target_goals"):
        goals = scenario["target_goals"]
        if isinstance(goals, str):
            import json
            try:
                goals = json.loads(goals)
            except Exception:
                goals = []
        if goals:
            parts.append(f"场景目标: {'; '.join(goals)}")
    if persona.background:
        parts.append(f"角色背景: {persona.background}")
    if persona.personality:
        parts.append(f"性格: {persona.personality}")
    parts.append("重要: 你仅参与对话，不评判、不纠错、不主导对话流程。")
    parts.append("如果用户表达困难，自然地继续对话即可。")
    return "\n".join(parts)


def _build_helper_system_prompt(helper_type: str, config: InvasivenessConfig) -> str:
    """构造 AI 辅助者系统提示（仅响应，不主动评判）"""
    base = "你是语言学习辅助者。"
    if helper_type == "grammar":
        return base + "当用户召唤时，提供简洁的语法纠正。\n" + _style_prompt(config)
    if helper_type == "vocabulary":
        return base + "当用户召唤时，提供合适的词汇建议。\n" + _style_prompt(config)
    if helper_type == "sentence_pattern":
        return base + "当用户召唤时，提供句型模板建议。\n" + _style_prompt(config)
    return base + _style_prompt(config)


def _style_prompt(config: InvasivenessConfig) -> str:
    if config.response_style == "concise":
        return "回复风格: 简洁，不超过 30 字。"
    if config.response_style == "detailed":
        return "回复风格: 详细，提供例句。"
    return "回复风格: 平衡。"


# ── 调度器：决定 AI 同伴何时发言 ──


def should_ai_companion_respond(
    persona: AIPersona,
    recent_turns: list[dict],
    last_speaker: str,
) -> bool:
    """决定 AI 同伴是否应该发言

    关键约束: 不抢话 (decision 4)
    """
    # 1. AI 不连续发言
    if last_speaker == persona.id:
        return False
    # 2. 1v1 场景：每次用户发言后都应回应
    if not recent_turns:
        return True
    last_turn = recent_turns[-1]
    if last_turn.get("speaker_id") == persona.id:
        return False
    # 3. talkative 行为: 大部分时候都应回应
    if persona.behavior == "talkative":
        return True
    # 4. balanced: 70% 概率回应（让真人有思考空间）
    if persona.behavior == "balanced":
        return True
    # 5. concise: 仅在直接被提问时回应
    if persona.behavior == "concise":
        text = last_turn.get("text", "").lower()
        if any(q in text for q in ["what do you think", "你", "?", "？", "how about", "what about"]):
            return True
        return False
    return True


# ── 主要 API ──


def join_ai_companion(
    room_id: str,
    user_id: str,
    persona_id: str,
    role_label: str = "",
) -> dict:
    """AI 同伴加入房间

    1. 读取 ai_personas
    2. 创建 room_participants (type=ai_companion)
    3. 创建 ai_companion_configs
    4. 发布 LanguageRoomAIPersonaJoined 事件
    """
    from app.infrastructure.db.database import get_db
    from shared.events import LanguageRoomAIPersonaJoined
    from app.infrastructure.event_bus_utils import publish_event_safe
    import uuid

    db = get_db()
    persona_row = db.fetchone("SELECT * FROM ai_personas WHERE id = %s", (persona_id,))
    if not persona_row:
        return {"ok": False, "error": f"AI 角色 {persona_id} 不存在"}
    persona = AIPersona.from_row(persona_row)

    # 1. 写 participant
    participant_id = f"PART_{uuid.uuid4().hex[:12]}"
    db.execute(
        """INSERT INTO room_participants
            (id, room_id, user_id, participant_type, ai_role_id, role_label,
             language, joined_at, is_owner, created_at)
           VALUES (%s, %s, %s, 'ai_companion', %s, %s, %s, NOW(), FALSE, NOW())""",
        (participant_id, room_id, persona_id, persona_id, role_label or persona.name, persona.target_language),
    )

    # 2. 写 companion config
    config_id = f"ACC_{uuid.uuid4().hex[:12]}"
    db.execute(
        """INSERT INTO ai_companion_configs
            (id, room_id, participant_id, persona_id, user_id,
             correction_tendency, is_topic_lead, response_style, activated_at)
           VALUES (%s, %s, %s, %s, %s, %s, %s, 'balanced', NOW())""",
        (
            config_id, room_id, participant_id, persona_id, user_id,
            persona.correction_tendency, persona.is_topic_lead,
        ),
    )

    # 3. 发布事件
    publish_event_safe(LanguageRoomAIPersonaJoined(
        user_id=user_id,
        room_id=room_id,
        participant_id=participant_id,
        persona_id=persona_id,
        role_label=role_label or persona.name,
    ))

    return {
        "ok": True,
        "participant_id": participant_id,
        "persona": persona.to_dict(),
    }


def leave_ai_companion(room_id: str, participant_id: str, user_id: str = "") -> dict:
    """AI 同伴离开房间"""
    from app.infrastructure.db.database import get_db
    from shared.events import LanguageRoomAIPersonaLeft
    from app.infrastructure.event_bus_utils import publish_event_safe

    db = get_db()
    db.execute(
        "UPDATE room_participants SET left_at = NOW() WHERE id = %s",
        (participant_id,),
    )
    db.execute(
        "UPDATE ai_companion_configs SET deactivated_at = NOW() WHERE participant_id = %s",
        (participant_id,),
    )

    publish_event_safe(LanguageRoomAIPersonaLeft(
        user_id=user_id,
        room_id=room_id,
        participant_id=participant_id,
    ))

    return {"ok": True, "participant_id": participant_id}


def invoke_helper(
    user_id: str,
    room_id: str,
    helper_type: str,
    query: str,
    invasiveness: InvasivenessConfig,
    context: dict | None = None,
) -> dict:
    """用户召唤 AI 辅助者

    关键约束 (决策 6):
    - 用户主动召唤 = 主动行为
    - 不是 AI 主动评判
    - 输出仅在用户个人侧边区

    helper_type: grammar / vocabulary / sentence_pattern
    """
    from shared.events import LanguageRoomAIHelperInvoked
    from app.infrastructure.event_bus_utils import publish_event_safe

    if helper_type not in invasiveness.helper_types:
        return {
            "ok": False,
            "error": f"helper_type {helper_type} not enabled for this user",
        }

    response = _call_llm_for_helper_response(
        invasiveness, helper_type, query, context or {}, user_id=user_id,
    )
    if not response:
        return {"ok": False, "error": "AI 响应生成失败"}

    # 发布事件
    publish_event_safe(LanguageRoomAIHelperInvoked(
        user_id=user_id,
        room_id=room_id,
        helper_type=helper_type,
        query=query,
        response=response,
    ))

    return {
        "ok": True,
        "helper_type": helper_type,
        "response": response,
    }


def get_companion_response(
    room_id: str,
    persona: AIPersona,
    recent_turns: list[dict],
    last_speaker: str,
    scenario: dict | None = None,
) -> Optional[str]:
    """AI 同伴生成回复（不主动纠错/评判）"""
    if not should_ai_companion_respond(persona, recent_turns, last_speaker):
        return None
    return _call_llm_for_companion_response(
        persona, scenario or {}, recent_turns,
    )


# ── Proposal 模式：与秘书系统一致 ──


def submit_proposal_for_knowledge_link(
    user_id: str,
    transcript_id: str,
    node_id: str,
    confidence: float = 0.5,
) -> dict:
    """通过 Proposal 机制建议知识点关联（与秘书系统一致）

    不是强制关联，而是生成 Proposal 让用户确认
    """
    try:
        from app.infrastructure.db.proposal_store import ProposalStore
        import uuid
        store = ProposalStore()
        proposal_id = f"PROP_{uuid.uuid4().hex[:12]}"
        store.create(
            proposal_id=proposal_id,
            user_id=user_id,
            proposal_type="language_room_node_link",
            payload={
                "transcript_id": transcript_id,
                "node_id": node_id,
                "confidence": confidence,
            },
        )
        return {"ok": True, "proposal_id": proposal_id}
    except Exception as e:
        logger.warning("Proposal 提交失败: %s", e)
        return {"ok": False, "error": str(e)}


# ── 默认角色库（系统预置）──


DEFAULT_PERSONAS: list[dict] = [
    {
        "id": "PERSONA_BARISTA_EN",
        "name": "咖啡师 Lily",
        "target_language": "en",
        "proficiency": "native",
        "speech_rate": "normal",
        "behavior": "concise",
        "personality": "友好、耐心、简短回复",
        "background": "在咖啡馆工作 5 年，熟练服务用语",
        "is_system": True,
    },
    {
        "id": "PERSONA_INTERVIEWER_EN",
        "name": "面试官 Tom",
        "target_language": "en",
        "proficiency": "native",
        "speech_rate": "normal",
        "behavior": "talkative",
        "personality": "专业、引导式提问",
        "background": "科技公司高级工程师，常参与面试",
        "is_system": True,
    },
    {
        "id": "PERSONA_FRIEND_ZH",
        "name": "学伴小李",
        "target_language": "zh",
        "proficiency": "native",
        "speech_rate": "normal",
        "behavior": "balanced",
        "personality": "同龄人视角、平等交流",
        "background": "大学英语专业学生",
        "is_system": True,
    },
]


# ── 默认场景库（系统预置）──

DEFAULT_SCENARIOS: list[dict] = [
    {
        "id": "SCENARIO_CAFE_ORDER",
        "name": "咖啡馆点单",
        "description": "在咖啡馆向店员点单、询问推荐、调整口味",
        "category": "daily",
        "roles": [
            {"label": "咖啡师", "language": "en", "persona_id": "PERSONA_BARISTA_EN"},
            {"label": "顾客", "language": "en", "is_user": True},
        ],
        "target_goals": [
            "用三个新学的形容词描述口味",
            "询问今日推荐",
            "成功下单一杯咖啡",
        ],
        "prompt_text": "尝试在对话中使用至少 3 个新学的咖啡相关词汇。",
        "linked_node_ids": [],
        "cross_disciplinary": False,
    },
    {
        "id": "SCENARIO_JOB_INTERVIEW",
        "name": "工作面试",
        "description": "模拟英文工作面试，回答常见问题并介绍自己",
        "category": "business",
        "roles": [
            {"label": "面试官", "language": "en", "persona_id": "PERSONA_INTERVIEWER_EN"},
            {"label": "求职者", "language": "en", "is_user": True},
        ],
        "target_goals": [
            "自我介绍 1 分钟",
            "回答 3 个行为面试问题",
            "向面试官提问 1 个反向问题",
        ],
        "prompt_text": "用 STAR 法则 (情境-任务-行动-结果) 回答问题。",
        "linked_node_ids": [],
        "cross_disciplinary": False,
    },
    {
        "id": "SCENARIO_GROUP_DISCUSSION",
        "name": "小组作业讨论",
        "description": "和同学用中英混合讨论作业主题",
        "category": "academic",
        "roles": [
            {"label": "学伴 A", "language": "zh", "persona_id": "PERSONA_FRIEND_ZH"},
            {"label": "学伴 B", "language": "zh", "is_user": True},
        ],
        "target_goals": [
            "确定一个研究主题",
            "分工三个任务",
            "约下次会议时间",
        ],
        "prompt_text": "讨论中尽量使用本周学习的新短语。",
        "linked_node_ids": [],
        "cross_disciplinary": True,
    },
    {
        "id": "SCENARIO_DAILY_GREETING",
        "name": "日常问候",
        "description": "和 AI 同伴用目标语言互相问候、聊今天的事",
        "category": "daily",
        "roles": [
            {"label": "学伴", "language": "en", "is_user": True},
            {"label": "AI 同伴", "language": "en", "persona_id": "PERSONA_FRIEND_ZH"},
        ],
        "target_goals": [
            "完成 5 分钟的自由对话",
            "使用 3 个不同的问候/寒暄表达",
        ],
        "prompt_text": "无固定主题，自由聊天即可。",
        "linked_node_ids": [],
        "cross_disciplinary": False,
    },
]


def seed_default_scenarios() -> None:
    """初始化系统预置场景（幂等）

    依据: docs/modules/language-room/data-model.md §3.5
    """
    from app.infrastructure.db.database import get_db
    import json
    db = get_db()
    for s in DEFAULT_SCENARIOS:
        existing = db.fetchone("SELECT id FROM room_scenarios WHERE id = %s", (s["id"],))
        if existing:
            continue
        db.execute(
            """INSERT INTO room_scenarios
                (id, user_id, name, description, category, roles, target_goals,
                 prompt_text, linked_node_ids, cross_disciplinary, is_system,
                 created_at, updated_at)
               VALUES (%s, NULL, %s, %s, %s, %s::jsonb, %s::jsonb, %s, %s::jsonb, %s, TRUE, NOW(), NOW())""",
            (
                s["id"], s["name"], s["description"], s["category"],
                json.dumps(s["roles"], ensure_ascii=False),
                json.dumps(s["target_goals"], ensure_ascii=False),
                s["prompt_text"],
                json.dumps(s.get("linked_node_ids", []), ensure_ascii=False),
                s.get("cross_disciplinary", False),
            ),
        )
    logger.info("已种子化 %d 个系统预置场景", len(DEFAULT_SCENARIOS))


def seed_default_personas() -> None:
    """初始化系统预置 AI 角色（幂等）"""
    from app.infrastructure.db.database import get_db
    db = get_db()
    for p in DEFAULT_PERSONAS:
        existing = db.fetchone("SELECT id FROM ai_personas WHERE id = %s", (p["id"],))
        if existing:
            continue
        db.execute(
            """INSERT INTO ai_personas
                (id, user_id, name, gender_voice, personality, target_language,
                 proficiency, speech_rate, accent, behavior, correction_tendency,
                 is_topic_lead, is_system, background, created_at, updated_at)
               VALUES (%s, NULL, %s, %s, %s, %s, %s, %s, %s, %s, 'none', %s, TRUE, %s, NOW(), NOW())""",
            (
                p["id"], p["name"], "female", p.get("personality", ""),
                p["target_language"], p["proficiency"], p["speech_rate"],
                p.get("accent", ""), p["behavior"], p.get("is_topic_lead", False),
                p.get("background", ""),
            ),
        )
    logger.info("已种子化 %d 个系统预置 AI 角色", len(DEFAULT_PERSONAS))
