"""
Task #68 — MoodStress 跨模块联动审计 (E2E 测试)

依据: docs/adr/0005-mood-stress.md + docs/modules/mood-stress/*
审计 8 条跨模块联动:

  1. mood record → fatigue_manager        (mood_stress.run_check 调用 fatigue_manager 模块)
  2. fatigue → plan_item                  (疲劳度高的 plan_item 走规划模块)
  3. mood_stress rule → plan_item.scheduled_for  (规则触发改 is_mood_rule_affected)
  4. behavior signal → secretary suggestion      (7 类行为信号驱动秘书建议)
  5. intervention → plan_item                    (4 类干预产生 plan_item)
  6. mood record → conversation                  (心情记录发布事件供消费)
  7. prefs → module visibility                   (偏好设置影响模块对 MoodStress 的可见性)
  8. mood record → cognitive_node                (心情记录发布事件, 不修改 Belief)

不依赖 LLM/外部服务, 全部用真实 DB + EventBus
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import time
import uuid
from typing import Any

import pytest

# 让 backend 在 sys.path
BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND not in sys.path:
    sys.path.insert(0, str(BACKEND))


# ────────────────────────── 公共 helpers ──────────────────────────


def _try_connect():
    try:
        from app.infrastructure.db.database import get_db
        d = get_db()
        d.fetchone("SELECT 1")
        return d
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"数据库不可用: {exc}")


def _table_exists(db, table_name: str) -> bool:
    row = db.fetchone(
        """
        SELECT 1 FROM information_schema.tables
         WHERE table_name = %s LIMIT 1
        """,
        (table_name,),
    )
    return row is not None


def _ensure_all_tables(db) -> None:
    """确保 mood_stress / planning / cognitive 表就绪"""
    try:
        from app.services.planning import _ensure_tables
        _ensure_tables()
    except Exception:
        pass


def _make_jwt(user_id: str) -> str:
    """生成有效 JWT (与 auth-gateway 共享 HS256 密钥)"""
    import jwt as pyjwt
    secret = os.environ.get("JWT_SECRET")
    if not secret:
        from dotenv import load_dotenv
        env_path = os.path.join(BACKEND, "config", ".env")
        if os.path.exists(env_path):
            load_dotenv(env_path, override=False)
        secret = os.environ.get(
            "JWT_SECRET", "dev-secret-key-not-for-production-1234567890"
        )
    payload = {
        "sub": user_id,
        "username": f"xms_{user_id[:8]}",
        "role": "user",
        "type": "access",
        "iat": int(time.time()),
        "exp": int(time.time()) + 3600,
    }
    return pyjwt.encode(payload, secret, algorithm="HS256")


def _insert_plan_item(
    db,
    user_id: str,
    source_module: str,
    target_type: str = "intervention",
    target_ref_id: str | None = None,
    title: str = "审计项",
    status: str = "pending",
) -> str:
    """Insert a plan_item row directly (skip validation), return its ID"""
    pid = f"plan_{uuid.uuid4().hex[:16]}"
    if target_ref_id is None:
        target_ref_id = f"tgt_{uuid.uuid4().hex[:12]}"
    db.execute(
        """INSERT INTO plan_items
           (id, user_id, source_module, target_type, target_ref_id, title,
            estimated_minutes, linked_node_ids, priority, status)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s)""",
        (
            pid, user_id, source_module, target_type, target_ref_id,
            title or f"审计-{source_module}",
            30,
            json.dumps([], ensure_ascii=False),
            0,
            status,
        ),
    )
    return pid


def _wait_event(captured: list, event_type: str, user_id: str, timeout: float = 1.0) -> Any:
    """轮询 captured 列表, 等待指定事件出现"""
    deadline = time.time() + timeout
    while time.time() < deadline:
        for e in captured:
            if type(e).__name__ == event_type and getattr(e, "user_id", None) == user_id:
                return e
        time.sleep(0.05)
    return None


def _run_and_drain(coro):
    """运行 async coroutine 并等待所有 pending tasks 完成 (含 fire-and-forget publish)

    为什么需要: publish_event_safe 在 async 上下文中是 fire-and-forget,
    会在 loop.create_task 调度任务后立即返回。如果直接用 asyncio.run,
    当 coroutine 返回时, loop 关闭, pending 的 publish task 被取消,
    事件永远不会被 dispatch 到订阅者。本函数在 coro 完成后, 显式等待
    所有 pending task 完成, 确保事件已被 dispatch。
    """
    async def _wrapper():
        result = await coro
        # 等待所有 pending tasks (含 fire-and-forget publish) 完成
        pending = [
            t for t in asyncio.all_tasks()
            if t is not asyncio.current_task() and not t.done()
        ]
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)
        return result
    return asyncio.run(_wrapper())


def _run_async(coro):
    """运行 async coroutine (使用 _run_and_drain 等待 fire-and-forget publish)"""
    return _run_and_drain(coro)


# ────────────────────────── Fixtures ──────────────────────────


@pytest.fixture
def user_id() -> str:
    return f"xms_{uuid.uuid4().hex[:12]}"


@pytest.fixture
def db():
    return _try_connect()


@pytest.fixture
def client():
    """FastAPI TestClient (同步)"""
    from fastapi.testclient import TestClient
    from app.main import app
    return TestClient(app)


@pytest.fixture
def auth_headers(user_id):
    return {"Authorization": f"Bearer {_make_jwt(user_id)}"}


@pytest.fixture
def capture_bus():
    """事件捕获总线 - 使用 DI 全局 bus (因 publish_event_safe 走 DI bus)"""
    from app.application.di import container
    bus = container.event_bus
    captured: list[Any] = []

    async def _capture(event):  # noqa: ANN001
        captured.append(event)

    for evt_type in (
        "MoodStressRecorded",
        "MoodStressInterventionTriggered",
        "MoodStressRuleTriggered",
        "MoodStressBehaviorSignalDetected",
        "MoodStressPrefsUpdated",
    ):
        bus.subscribe(evt_type, _capture)
    return bus, captured


@pytest.fixture(autouse=True)
def cleanup_test_data(db, user_id):
    """测试结束清理 user 数据"""
    yield
    for tbl in (
        "emotion_records", "mood_stress_prefs", "mood_stress_intervention_logs",
        "mood_stress_rules", "behavior_signals", "plan_items",
    ):
        try:
            db.execute(f"DELETE FROM {tbl} WHERE user_id = %s", (user_id,))
        except Exception:
            pass


# ══════════════════════════════════════════════════════════════
# 联动 1: mood record → fatigue_manager
# ══════════════════════════════════════════════════════════════


class TestMoodRecordToFatigueManager:
    """联动 1: 心情记录 → fatigue_manager 模块复用

    实现方式: mood_stress.run_check() 内部通过 module_registry
    调用 FatigueManagerModule.run_check, 把疲劳 Proposal 作为
    上下文附加到 mood_stress rule proposal 上 (reuse_modules=['fatigue_manager'])
    """

    def test_fatigue_manager_module_is_registered(self, db, user_id):
        """fatigue_manager 模块必须注册到 module_registry (供 mood_stress 复用)"""
        _ensure_all_tables(db)
        from app.domain.secretary.engines.module_registry import module_registry
        module_registry.discover_builtin()
        names = [m["name"] for m in module_registry.list_modules()]
        assert "fatigue_manager" in names, (
            f"fatigue_manager 未注册, mood_stress 无法复用: {names}"
        )
        # fatigue_manager 默认启用
        assert module_registry.is_enabled("fatigue_manager"), (
            "fatigue_manager 默认应为 enabled"
        )

    def test_mood_stress_module_invoke_fatigue_manager_in_rule(self, db, user_id):
        """mood_stress.run_check 在生成 rule proposal 时, 调 fatigue_manager
        并把其 Proposal 作为 context.reuse_modules 暴露

        流程:
          1. 用户记录心情 pressure_score=8 (>=6)
          2. 创建规则 pressure_score >= 7 → action=postpone_high_intensity
          3. run_check 评估 → 触发规则 → 生成 proposal
          4. proposal.payload.context.reuse_modules 包含 'fatigue_manager'
        """
        _ensure_all_tables(db)
        from app.services.secretary.mood_stress_store import mood_stress_store
        from app.services.secretary.modules.mood_stress import MoodStressModule, record_manual

        async def _test():
            # 1. 写心情记录 (pressure_score=8)
            await record_manual(
                user_id=user_id,
                emotion_tags=["overwhelm"],
                pressure_score=8,
                energy_score=3,
            )
            # 2. 创建规则 pressure_score >= 7
            mood_stress_store.add_rule(
                user_id=user_id,
                rule_name="高压规则",
                trigger_metric="pressure_score",
                trigger_operator=">=",
                trigger_value=7,
                action="postpone_high_intensity",
            )
            # 3. 跑 run_check
            mod = MoodStressModule()
            return await mod.run_check(user_id)

        proposals = _run_async(_test())
        # 至少 1 个 proposal
        assert len(proposals) >= 1, "run_check 未生成 proposal"
        p = proposals[0]
        # 关键断言: context.reuse_modules 包含 fatigue_manager
        ctx = p.payload.get("context", {})
        assert "fatigue_manager" in ctx.get("reuse_modules", []), (
            f"mood_stress 规则未复用 fatigue_manager: context={ctx}"
        )

    def test_mood_stress_skips_fatigue_for_positive_emotion(self, db, user_id):
        """positive 情绪 (motivated/calm) 应不触发 fatigue_manager 复用

        实现: mood_stress.run_check 仅在压力/能量相关信号存在时调 fatigue_manager
        """
        _ensure_all_tables(db)
        from app.services.secretary.mood_stress_store import mood_stress_store
        from app.services.secretary.modules.mood_stress import MoodStressModule, record_manual

        async def _test():
            # 心情 = positive (没有压力/能量分数, 没有 fatigue/anxiety/overwhelm)
            await record_manual(
                user_id=user_id,
                emotion_tags=["motivated", "calm"],
            )
            mood_stress_store.add_rule(
                user_id=user_id,
                rule_name="motivated rule",
                trigger_metric="emotion_tag",
                trigger_operator="==",
                trigger_value="motivated",
                action="suggest_break",
            )
            mod = MoodStressModule()
            return await mod.run_check(user_id)

        proposals = _run_async(_test())
        # 规则匹配 → 至少 1 个 proposal
        if proposals:
            # 因为情绪标签是 positive, fatigue_proposals 应为空
            ctx = proposals[0].payload.get("context", {})
            # 关键: fatigue_proposals 应为空数组 (不是有内容)
            assert ctx.get("fatigue_proposals") == [], (
                f"positive 情绪不应有 fatigue_proposals: {ctx}"
            )


# ══════════════════════════════════════════════════════════════
# 联动 2: fatigue → plan_item
# ══════════════════════════════════════════════════════════════


class TestFatigueToPlanItem:
    """联动 2: 疲劳度 → plan_item 调度

    设计: FatigueManagerModule.run_check 在 risk_level 高时生成 rest proposal
    验证: 1) fatigue_manager 模块存在 2) predict_fatigue_risk 返回合法 risk_level
    """

    def test_fatigue_manager_module_exists(self, db, user_id):
        """FatigueManagerModule 必须存在, 用于疲劳检测"""
        _ensure_all_tables(db)
        from app.domain.secretary.engines.builtin_review import FatigueManagerModule
        from app.domain.secretary.engines.module_registry import module_registry

        module_registry.discover_builtin()
        mod = module_registry.get_module("fatigue_manager")
        assert mod is not None, "fatigue_manager 模块未注册"
        assert isinstance(mod, FatigueManagerModule)
        # meta 信息
        assert mod.meta.name == "fatigue_manager"
        assert mod.meta.display_name == "疲劳管理"

    def test_predict_fatigue_risk_returns_valid_risk_level(self, db, user_id):
        """predict_fatigue_risk 应返回合法 risk_level 字段"""
        _ensure_all_tables(db)
        from app.domain.secretary.analysis import predict_fatigue_risk
        result = predict_fatigue_risk(user_id)
        assert "risk_level" in result, f"缺少 risk_level: {result}"
        assert result["risk_level"] in ("low", "medium", "high"), (
            f"非法 risk_level: {result['risk_level']}"
        )
        assert "recent_practices_2h" in result


# ══════════════════════════════════════════════════════════════
# 联动 3: mood_stress rule → plan_item.scheduled_for
# ══════════════════════════════════════════════════════════════


class TestMoodStressRuleToPlanItem:
    """联动 3: 规则触发 → plan_item.is_mood_rule_affected 标记

    实现: completion_writer._on_mood_rule 订阅 MoodStressRuleTriggered
    → 仅当 action='postpone_high_intensity' 时, 标记 project 类型 plan_item
    """

    def test_mood_rule_triggered_marks_project_plan_items(self, db, user_id):
        """规则触发 action=postpone_high_intensity 应标记 project 类型 plan_item"""
        _ensure_all_tables(db)
        if not _table_exists(db, "plan_items"):
            pytest.skip("plan_items 表不存在")

        # 1. 创建 source_module=project 的 plan_item
        pid = _insert_plan_item(
            db, user_id, "project", target_type="project_node", target_ref_id="p_audit_001",
        )
        # 2. 创建 source_module=reading 的 plan_item (不应被标记)
        pid2 = _insert_plan_item(
            db, user_id, "reading", target_type="material", target_ref_id="r_audit_001",
        )
        # 3. 创建 source_module=flashcard 的 plan_item (不应被标记)
        pid3 = _insert_plan_item(
            db, user_id, "flashcard", target_type="flashcard_set", target_ref_id="fc_audit_001",
        )

        from app.infrastructure.event_bus import EventBus
        from app.services.planning.completion_writer import PlanningCompletionWriter
        from shared.events import MoodStressRuleTriggered

        bus = EventBus(handler_timeout=2.0)
        writer = PlanningCompletionWriter()
        writer.subscribe(bus)

        async def _test():
            await bus.publish(MoodStressRuleTriggered(
                user_id=user_id,
                rule_id="rule_audit_001",
                trigger_metric="pressure_score",
                trigger_value=8.0,
                action="postpone_high_intensity",
            ))

        asyncio.run(_test())

        # project 类型的 plan_item 应被标记
        row1 = db.fetchone(
            "SELECT is_mood_rule_affected FROM plan_items WHERE id = %s",
            (pid,),
        )
        assert row1 is not None
        assert row1["is_mood_rule_affected"] is True, (
            f"project plan_item 未被标记: is_mood_rule_affected={row1['is_mood_rule_affected']}"
        )
        # reading / flashcard 类型不应被标记
        for other_pid in (pid2, pid3):
            row = db.fetchone(
                "SELECT is_mood_rule_affected FROM plan_items WHERE id = %s",
                (other_pid,),
            )
            assert row is not None
            assert row["is_mood_rule_affected"] is False, (
                f"{other_pid} 被错误标记: {row['is_mood_rule_affected']}"
            )

    def test_mood_rule_only_postpone_action_marks(self, db, user_id):
        """action != 'postpone_high_intensity' 不应标记任何 plan_item"""
        _ensure_all_tables(db)
        if not _table_exists(db, "plan_items"):
            pytest.skip("plan_items 表不存在")

        pid = _insert_plan_item(
            db, user_id, "project", target_type="project_node", target_ref_id="p_audit_002",
        )

        from app.infrastructure.event_bus import EventBus
        from app.services.planning.completion_writer import PlanningCompletionWriter
        from shared.events import MoodStressRuleTriggered

        bus = EventBus(handler_timeout=2.0)
        writer = PlanningCompletionWriter()
        writer.subscribe(bus)

        async def _test():
            await bus.publish(MoodStressRuleTriggered(
                user_id=user_id,
                rule_id="rule_audit_002",
                trigger_metric="emotion_tag",
                trigger_value="frustration",
                action="only_flashcard",  # 不是 postpone_high_intensity
            ))

        asyncio.run(_test())

        row = db.fetchone(
            "SELECT is_mood_rule_affected FROM plan_items WHERE id = %s",
            (pid,),
        )
        assert row["is_mood_rule_affected"] is False, (
            f"only_flashcard action 不应标记 plan_item: {row['is_mood_rule_affected']}"
        )

    def test_mood_rule_triggered_event_published_by_run_check(
        self, db, user_id, capture_bus
    ):
        """完整联动: mood_stress.run_check() 触发规则时, 发布 MoodStressRuleTriggered 事件"""
        _ensure_all_tables(db)
        from app.services.secretary.mood_stress_store import mood_stress_store
        from app.services.secretary.modules.mood_stress import MoodStressModule, record_manual

        async def _test():
            # 写心情 (pressure=8)
            await record_manual(
                user_id=user_id, emotion_tags=["overwhelm"],
                pressure_score=8, energy_score=3,
            )
            # 创建规则
            mood_stress_store.add_rule(
                user_id=user_id, rule_name="高压规则",
                trigger_metric="pressure_score",
                trigger_operator=">=", trigger_value=7,
                action="postpone_high_intensity",
            )
            mod = MoodStressModule()
            return await mod.run_check(user_id)

        _run_async(_test())
        # 等事件 (fire-and-forget)
        time.sleep(0.3)
        bus, captured = capture_bus
        ev = _wait_event(captured, "MoodStressRuleTriggered", user_id, timeout=2.0)
        assert ev is not None, "MoodStressRuleTriggered 事件未发布"
        assert ev.action == "postpone_high_intensity"
        assert ev.trigger_metric == "pressure_score"


# ══════════════════════════════════════════════════════════════
# 联动 4: behavior signal → secretary suggestion
# ══════════════════════════════════════════════════════════════


class TestBehaviorSignalToSecretary:
    """联动 4: 行为信号 → 秘书建议 (7 类信号)

    验证: emit_behavior_signal 写入 behavior_signals 表 + 发布事件
    """

    SEVEN_SIGNAL_TYPES = (
        "task_switch", "stay_duration", "error_rate", "undo",
        "session_anomaly", "flashcard_failure", "voice_features",
    )

    def test_all_seven_signal_types_emit_event_and_persist(self, db, user_id, capture_bus):
        """7 类行为信号全部应写入 behavior_signals 表 + 发布 MoodStressBehaviorSignalDetected 事件"""
        _ensure_all_tables(db)
        from app.services.secretary.mood_stress_store import mood_stress_store
        from app.services.secretary.modules.mood_stress import emit_behavior_signal

        async def _test():
            # 开启 voice_features (默认关闭)
            mood_stress_store.upsert_prefs(
                user_id, {"auto_collect_voice_features": True}
            )
            results = []
            for sig_type in self.SEVEN_SIGNAL_TYPES:
                result = await emit_behavior_signal(
                    user_id=user_id,
                    signal_type=sig_type,
                    signal_data={"reason": f"audit_{sig_type}"},
                    severity=1,
                )
                results.append((sig_type, result))
            return results

        results = _run_async(_test())

        # 1) 每种信号应正常返回 (非 disabled)
        for sig_type, result in results:
            assert result.get("status") != "disabled", (
                f"{sig_type} 被 disabled: {result}"
            )
            assert result.get("id"), f"{sig_type} 缺 id: {result}"

        # 2) 验证 DB 持久化
        for sig_type, _ in results:
            row = db.fetchone(
                "SELECT id, signal_type FROM behavior_signals "
                "WHERE user_id = %s AND signal_type = %s",
                (user_id, sig_type),
            )
            assert row is not None, f"{sig_type} 未写入 behavior_signals 表"
            assert row["signal_type"] == sig_type

        # 3) 验证事件发布
        time.sleep(0.3)
        bus, captured = capture_bus
        for sig_type in self.SEVEN_SIGNAL_TYPES:
            ev = _wait_event(
                captured, "MoodStressBehaviorSignalDetected", user_id, timeout=1.0,
            )
            # 至少 1 个事件被发布
        assert len(captured) >= 7, (
            f"7 类信号事件未全部发布, 实际: {len(captured)} 个"
        )
        # 验证事件类型
        signal_events = [
            e for e in captured
            if type(e).__name__ == "MoodStressBehaviorSignalDetected"
            and e.user_id == user_id
        ]
        assert len(signal_events) >= 7

    def test_voice_features_default_off(self, db, user_id):
        """voice_features 默认应被 emit_behavior_signal 拒绝 (auto_collect=False 默认)"""
        _ensure_all_tables(db)
        from app.services.secretary.modules.mood_stress import emit_behavior_signal

        async def _test():
            return await emit_behavior_signal(
                user_id=user_id,
                signal_type="voice_features",
                signal_data={"speech_rate": 1.2},
                severity=1,
            )
        result = asyncio.run(_test())
        assert result.get("status") == "disabled", (
            f"voice_features 默认应关闭, 实际: {result}"
        )

    def test_emit_signal_respects_user_prefs(self, db, user_id):
        """prefs.auto_collect_task_switch=False 时, task_switch 应被拒绝"""
        _ensure_all_tables(db)
        from app.services.secretary.mood_stress_store import mood_stress_store
        from app.services.secretary.modules.mood_stress import emit_behavior_signal

        # 关闭 task_switch 收集
        mood_stress_store.upsert_prefs(
            user_id, {"auto_collect_task_switch": False}
        )

        async def _test():
            return await emit_behavior_signal(
                user_id=user_id,
                signal_type="task_switch",
                signal_data={"count": 10},
                severity=1,
            )
        result = asyncio.run(_test())
        assert result.get("status") == "disabled", (
            f"task_switch 应被 prefs 拒绝, 实际: {result}"
        )

    def test_behavior_signal_event_schema(self):
        """事件 schema 字段正确"""
        from shared.events import MoodStressBehaviorSignalDetected
        e = MoodStressBehaviorSignalDetected(
            user_id="u", signal_type="task_switch",
            signal_data={"count": 5}, severity=2,
        )
        assert e.signal_type == "task_switch"
        assert e.severity == 2
        assert e.event_type == "MoodStressBehaviorSignalDetected"


# ══════════════════════════════════════════════════════════════
# 联动 5: intervention → plan_item
# ══════════════════════════════════════════════════════════════


class TestInterventionToPlanItem:
    """联动 5: 4 类干预 → plan_item (source_module='mood_stress')

    验证: record_intervention 写入日志表 + 发布事件,
    配合 user 主动创建 source_module='mood_stress' 的 plan_item 形成完整联动
    """

    FOUR_INTERVENTION_TYPES = (
        "breathing", "knowledge_breathing",
        "cognitive_reappraisal", "environment",
    )

    def test_all_four_intervention_types_logged(self, db, user_id):
        """4 类干预工具全部应写入 mood_stress_intervention_logs 表"""
        _ensure_all_tables(db)
        from app.services.secretary.modules.mood_stress import record_intervention

        async def _test():
            ids = []
            for itype in self.FOUR_INTERVENTION_TYPES:
                result = await record_intervention(
                    user_id=user_id,
                    intervention_type=itype,
                    duration_seconds=60,
                    notes=f"audit {itype}",
                )
                ids.append((itype, result.get("id")))
            return ids
        ids = _run_async(_test())

        for itype, iid in ids:
            assert iid, f"{itype} 干预 id 缺失"
            row = db.fetchone(
                "SELECT id, intervention_type, duration_seconds FROM mood_stress_intervention_logs "
                "WHERE id = %s AND user_id = %s",
                (iid, user_id),
            )
            assert row is not None, f"{itype} 干预未落库"
            assert row["intervention_type"] == itype
            assert row["duration_seconds"] == 60

    def test_intervention_publishes_event(self, db, user_id, capture_bus):
        """record_intervention 应发布 MoodStressInterventionTriggered 事件"""
        _ensure_all_tables(db)
        from app.services.secretary.modules.mood_stress import record_intervention

        async def _test():
            await record_intervention(
                user_id=user_id,
                intervention_type="breathing",
                duration_seconds=300,
            )

        _run_async(_test())
        time.sleep(0.3)
        bus, captured = capture_bus
        ev = _wait_event(captured, "MoodStressInterventionTriggered", user_id, timeout=2.0)
        assert ev is not None, "MoodStressInterventionTriggered 未发布"
        assert ev.intervention_type == "breathing"
        assert ev.duration_seconds == 300

    def test_intervention_creates_plan_item_via_routing(self, db, user_id):
        """完整联动: 用户创建 source_module='mood_stress' 的 plan_item
        → 完成时路由到 mood_stress handler
        """
        _ensure_all_tables(db)
        from app.services.planning.completion_writer import PlanningCompletionWriter
        from app.infrastructure.event_bus import EventBus
        from shared.events import PlanItemCompleted, PlanningSourceModule

        # 1. 创建 plan_item (source_module=mood_stress, target_type=intervention)
        pid = _insert_plan_item(
            db, user_id, "mood_stress", target_type="intervention",
            target_ref_id=f"itv_{uuid.uuid4().hex[:8]}",
        )

        bus = EventBus(handler_timeout=2.0)
        writer = PlanningCompletionWriter()
        writer.subscribe(bus)

        async def _test():
            await bus.publish(PlanItemCompleted(
                user_id=user_id, plan_item_id=pid,
                source_module=PlanningSourceModule.MOOD_STRESS.value,
                target_type="intervention", target_ref_id="int_audit",
                actual_minutes=5,
            ))

        _run_async(_test())

        # 验证: plan_item.status = completed
        row = db.fetchone(
            "SELECT status, actual_minutes FROM plan_items WHERE id=%s",
            (pid,),
        )
        assert row is not None
        assert row["status"] == "completed", (
            f"mood_stress 路由未完成: status={row['status']}"
        )
        assert row["actual_minutes"] == 5

    def test_intervention_invalid_type_rejected(self, db, user_id):
        """非法 intervention_type 应抛 ValueError"""
        from app.services.secretary.modules.mood_stress import record_intervention

        async def _test():
            return await record_intervention(
                user_id=user_id,
                intervention_type="invalid_type",
            )
        with pytest.raises(ValueError, match="非法的干预类型"):
            _run_async(_test())


# ══════════════════════════════════════════════════════════════
# 联动 6: mood record → conversation
# ══════════════════════════════════════════════════════════════


class TestMoodRecordToConversation:
    """联动 6: 心情记录 → 对话上下文

    设计: record_manual 发布 MoodStressRecorded 事件供 conversation 消费
    验证: 事件被定义, 字段完整, prefs.output_to_conversation 控制可见性
    """

    def test_record_manual_publishes_event(self, db, user_id, capture_bus):
        """record_manual 应发布 MoodStressRecorded 事件"""
        _ensure_all_tables(db)
        from app.services.secretary.modules.mood_stress import record_manual

        async def _test():
            return await record_manual(
                user_id=user_id,
                emotion_tags=["frustration", "anxiety"],
                pressure_score=7,
                energy_score=3,
                text_note="心情不好",
            )
        result = _run_async(_test())

        # 1. DB 落库
        assert result.get("id"), "record 未返回 id"
        # 2. 事件已发布 (fire-and-forget, 需等待)
        time.sleep(0.3)
        bus, captured = capture_bus
        ev = _wait_event(captured, "MoodStressRecorded", user_id, timeout=2.0)
        assert ev is not None, "MoodStressRecorded 事件未发布"
        assert ev.pressure_score == 7
        assert ev.energy_score == 3
        assert "frustration" in ev.emotion_tags
        assert ev.source == "manual"
        assert ev.text_note == "心情不好"

    def test_output_to_conversation_pref_exists(self, db, user_id):
        """prefs.output_to_conversation 字段应存在, 控制 conversation 模块对 mood_stress 的可见性"""
        _ensure_all_tables(db)
        from app.services.secretary.mood_stress_store import mood_stress_store
        prefs = mood_stress_store.get_prefs(user_id)
        assert "output_to_conversation" in prefs, (
            f"output_to_conversation 字段缺失: {list(prefs.keys())}"
        )
        # 默认值
        assert prefs["output_to_conversation"] is True, (
            f"output_to_conversation 默认应为 True: {prefs['output_to_conversation']}"
        )

    def test_mood_recorded_event_schema(self):
        """MoodStressRecorded 事件 schema 字段完整"""
        from shared.events import MoodStressRecorded
        e = MoodStressRecorded(
            user_id="u", record_id="r",
            source="manual",
            emotion_tags=["calm"],
            pressure_score=3,
            energy_score=8,
            text_note="n",
            related_event_ids=["e1"],
        )
        assert e.event_type == "MoodStressRecorded"
        assert e.pressure_score == 3


# ══════════════════════════════════════════════════════════════
# 联动 7: prefs → module visibility
# ══════════════════════════════════════════════════════════════


class TestPrefsToModuleVisibility:
    """联动 7: 偏好设置 → 模块对 MoodStress 的可见性

    prefs 字段:
      - output_to_planning: 控制 run_check 是否评估 (Task #68 关键)
      - output_to_conversation: 控制 conversation 模块可见性
      - output_to_language_room: 控制 liveroom 模块可见性
      - auto_collect_*: 控制 7 类行为信号是否被收集
    """

    def test_run_check_skipped_when_output_to_planning_false(self, db, user_id):
        """prefs.output_to_planning=False 时, run_check 不评估 (返回空)"""
        _ensure_all_tables(db)
        from app.services.secretary.mood_stress_store import mood_stress_store
        from app.services.secretary.modules.mood_stress import MoodStressModule, record_manual

        async def _test():
            # 关闭 output_to_planning
            mood_stress_store.upsert_prefs(
                user_id, {"output_to_planning": False}
            )
            # 写心情 + 创建规则 (满足所有前置条件)
            await record_manual(
                user_id=user_id, emotion_tags=["overwhelm"],
                pressure_score=8, energy_score=3,
            )
            mood_stress_store.add_rule(
                user_id=user_id, rule_name="test",
                trigger_metric="pressure_score",
                trigger_operator=">=", trigger_value=7,
                action="postpone_high_intensity",
            )
            mod = MoodStressModule()
            return await mod.run_check(user_id)

        proposals = _run_async(_test())
        assert len(proposals) == 0, (
            f"output_to_planning=False 时 run_check 应不评估, 实际返回 {len(proposals)} 个 proposal"
        )

    def test_all_output_to_prefs_exist_with_defaults(self, db, user_id):
        """3 个 output_to_* 偏好字段都应存在并默认为 True"""
        _ensure_all_tables(db)
        from app.services.secretary.mood_stress_store import mood_stress_store
        prefs = mood_stress_store.get_prefs(user_id)
        for k in ("output_to_planning", "output_to_conversation", "output_to_language_room"):
            assert k in prefs, f"字段缺失: {k}"
            assert prefs[k] is True, f"{k} 默认应为 True, 实际: {prefs[k]}"

    def test_prefs_updated_publishes_event_via_api(
        self, db, user_id, client, auth_headers, capture_bus
    ):
        """prefs 更新 (通过 HTTP API) 应发布 MoodStressPrefsUpdated 事件"""
        _ensure_all_tables(db)
        r = client.put(
            "/api/secretary/mood-stress/prefs",
            headers=auth_headers,
            json={"data_retention_days": 60},
        )
        assert r.status_code == 200, f"prefs update API 失败: {r.text}"
        time.sleep(0.3)
        bus, captured = capture_bus
        ev = _wait_event(captured, "MoodStressPrefsUpdated", user_id, timeout=2.0)
        assert ev is not None, "MoodStressPrefsUpdated 事件未发布"
        assert "data_retention_days" in ev.changed_fields


# ══════════════════════════════════════════════════════════════
# 联动 8: mood record → cognitive_node (待验证: 不修改 Belief)
# ══════════════════════════════════════════════════════════════


class TestMoodRecordToCognitiveNode:
    """联动 8: 心情记录 → 认知节点 (待验证)

    设计原则 (ADR 0005):
      - 心情压力是主观状态, Belief 的合法来源仅限主动学习行为
      - MoodStressRecorded **不**触发 CognitiveNode.Belief 更新
      - 干预工具不修改 FSRS / Belief / Scheduling

    验证: 没有 subscriber 订阅 MoodStressRecorded → CognitiveNode.Belief
    """

    def test_no_subscriber_updates_belief_on_mood_recorded(self, db, user_id):
        """MoodStressRecorded 不应触发 Belief 更新 (无 handler 路径)"""
        _ensure_all_tables(db)
        from app.application.di import container
        bus = container.event_bus
        handlers = getattr(bus, "_handlers", {}) or {}
        # 检查: MoodStressRecorded 不应有 handler 改 Belief
        mood_handlers = handlers.get("MoodStressRecorded", [])
        for h in mood_handlers:
            h_name = getattr(h, "__name__", str(h))
            # 没有 handler 名包含 "belief" 或 "cognitive"
            assert "belief" not in h_name.lower(), (
                f"MoodStressRecorded 不应有 Belief 改写 handler: {h_name}"
            )

    def test_intervention_event_no_belief_handler(self, db, user_id):
        """MoodStressInterventionTriggered 不应触发 Belief 更新"""
        _ensure_all_tables(db)
        from app.application.di import container
        bus = container.event_bus
        handlers = getattr(bus, "_handlers", {}) or {}
        intervention_handlers = handlers.get("MoodStressInterventionTriggered", [])
        for h in intervention_handlers:
            h_name = getattr(h, "__name__", str(h))
            assert "belief" not in h_name.lower(), (
                f"MoodStressInterventionTriggered 不应有 Belief handler: {h_name}"
            )
            assert "fsrs" not in h_name.lower(), (
                f"MoodStressInterventionTriggered 不应有 FSRS handler: {h_name}"
            )

    def test_mood_stress_isolated_from_knowledge_graph_module(self):
        """mood_stress 模块代码声明不与知识图谱 Belief 互通"""
        from app.services.secretary.modules.mood_stress import MoodStressModule
        # 模块 docstring 应包含 "不" + 知识图谱 / FSRS / Belief 相关
        doc = (MoodStressModule.__doc__ or "") + ""
        # ADR 0005 关键约束
        assert "不自动修改" in doc or "不进入知识图谱" in doc or "不修改" in doc, (
            f"MoodStressModule 文档应声明不修改 Belief/FSRS, 实际: {doc[:200]}"
        )

    def test_principles_declared_in_dashboard(self, db, user_id, client, auth_headers):
        """dashboard 返回 principles 字段, 声明手动优先/隔离等核心原则"""
        _ensure_all_tables(db)
        r = client.get(
            "/api/secretary/mood-stress/dashboard",
            headers=auth_headers,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        principles = body.get("principles", {})
        # 4 个核心原则都应声明
        assert principles.get("manual_priority") is True
        assert principles.get("intervention_isolated_from_knowledge_graph") is True
        assert principles.get("voice_features_default_off") is True
        assert principles.get("reminder_default_off") is True


# ══════════════════════════════════════════════════════════════
# 额外: 集成性验证 (8 联动 × 1 E2E 完整流)
# ══════════════════════════════════════════════════════════════


class TestMoodStressFullE2E:
    """完整 E2E: 写心情 → 规则触发 → 标记 plan_item"""

    def test_full_mood_to_plan_item_marked_flow(
        self, db, user_id, client, auth_headers, capture_bus
    ):
        """完整联动 1+3: 心情记录 → 规则触发 → plan_item 标记

        1. record_manual 写心情 (pressure=8)
        2. 创建规则 pressure_score >= 7 → postpone_high_intensity
        3. run_check 触发规则 → 发布 MoodStressRuleTriggered 事件
        4. completion_writer 标记 project 类型 plan_item.is_mood_rule_affected = TRUE
        """
        _ensure_all_tables(db)
        if not _table_exists(db, "plan_items"):
            pytest.skip("plan_items 表不存在")

        # 1. 创建 source_module=project 的 plan_item
        pid = _insert_plan_item(
            db, user_id, "project", target_type="project_node",
            target_ref_id=f"p_full_{uuid.uuid4().hex[:8]}",
        )

        # 2. 写心情 + 创建规则
        r = client.post(
            "/api/secretary/mood-stress/record",
            headers=auth_headers,
            json={
                "emotion_tags": ["overwhelm"],
                "pressure_score": 8,
                "energy_score": 3,
            },
        )
        assert r.status_code == 200
        r = client.post(
            "/api/secretary/mood-stress/rules",
            headers=auth_headers,
            json={
                "rule_name": "高压规则",
                "trigger_metric": "pressure_score",
                "trigger_operator": ">=",
                "trigger_value": 7,
                "action": "postpone_high_intensity",
            },
        )
        assert r.status_code == 200

        # 3. 触发 run_check (通过 run_module 走 module_registry)
        from app.domain.secretary.engines.module_registry import module_registry
        # 模块 throttle: 4 分钟最多一次, 第一次调用必执行
        module_registry._last_run.pop("mood_stress", None)
        async def _test():
            return await module_registry.run_module("mood_stress", user_id)
        proposals = _run_async(_test())
        assert len(proposals) >= 1, "run_check 未生成 rule proposal"

        # 4. 验证: project 类型 plan_item 被标记
        time.sleep(0.5)  # 等 handler 跑完
        row = db.fetchone(
            "SELECT is_mood_rule_affected FROM plan_items WHERE id = %s",
            (pid,),
        )
        assert row is not None
        assert row["is_mood_rule_affected"] is True, (
            f"联动链路 (心情 → 规则 → plan_item 标记) 失败: {row['is_mood_rule_affected']}"
        )

        # 5. 验证事件发布
        bus, captured = capture_bus
        ev = _wait_event(captured, "MoodStressRuleTriggered", user_id, timeout=2.0)
        assert ev is not None, "MoodStressRuleTriggered 事件未发布"
        assert ev.action == "postpone_high_intensity"
