"""伴学系统 — 核心模块单元测试套件

按诊断流程：Phase 1 反馈循环 — 每个测试是独立可运行的 pass/fail 信号。

运行方式:
    cd backend && python3 -m pytest tests/test_secretary_modules.py -v 2>&1
    或直接: python3 tests/test_secretary_modules.py
"""

import sys
import os
import json
import time
import traceback

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

PASS = 0
FAIL = 0


def _check(name: str, condition: bool, detail: str = ""):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  ✅ PASS: {name}")
    else:
        FAIL += 1
        print(f"  ❌ FAIL: {name} — {detail}")


# ═══════════════════════════════════════════
# 1. Proposal Model 测试
# ═══════════════════════════════════════════
def test_proposal_model():
    print("\n═══ 1. ProposalModel ═══")
    from app.domain.secretary.models import Proposal

    p = Proposal(
        emoji="📖",
        title="测试提案",
        description="这是一个测试",
        action_type="review",
        priority=3,
        payload={"kp_id": "123"},
        insight_source="test",
    )
    _check("Proposal 创建", p.title == "测试提案")
    _check("action_type 默认", p.action_type == "review")
    _check("priority 范围", p.priority == 3)
    _check("payload 存储", p.payload.get("kp_id") == "123")
    _check("emoji", p.emoji == "📖")

    # 序列化 round-trip
    d = p.to_dict() if hasattr(p, "to_dict") else p.__dict__
    _check("Proposal 可序列化", isinstance(d, dict))


# ═══════════════════════════════════════════
# 2. ModuleRegistry 测试
# ═══════════════════════════════════════════
def test_module_registry():
    print("\n═══ 2. ModuleRegistry ═══")
    from app.domain.secretary.engines.module_registry import SecretaryModuleRegistry, ModuleMeta, SecretaryModule

    class DummyModule(SecretaryModule):
        @property
        def meta(self):
            return ModuleMeta(
                name="dummy", display_name="Dummy", emoji="🧪",
                description="test module", default_enabled=True,
            )
        async def run_check(self, user_id, ctx=None):
            return []

    registry = SecretaryModuleRegistry()
    registry.register(DummyModule())

    modules = registry.list_modules()
    _check("注册后模块数量 > 0", len(modules) > 0)
    
    dummy_found = any(m["name"] == "dummy" for m in modules)
    _check("Dummy 模块已注册", dummy_found)

    registry.enable("dummy")
    _check("启用 dummy", registry._enabled.get("dummy", False))

    registry.disable("dummy")
    _check("禁用 dummy", not registry._enabled.get("dummy", True))

    # 发现内置模块
    before = len(registry.list_modules())
    count = registry.discover_builtin()
    after = len(registry.list_modules())
    _check(f"内置模块发现完毕 ({after} 个)", after >= 10)
    names = [m["name"] for m in registry.list_modules()]
    _check("review_reminder 注册", "review_reminder" in names)
    _check("fatigue_manager 注册", "fatigue_manager" in names)
    _check("daily_brief 注册", "daily_brief" in names)
    _check("behavior_trigger 注册", "behavior_trigger" in names)

    # 重复发现不会增加模块数量
    before2 = len(registry.list_modules())
    count2 = registry.discover_builtin()
    after2 = len(registry.list_modules())
    _check("重复发现不增加模块数", after2 == before2)


# ═══════════════════════════════════════════
# 3. ProposalStore 测试
# ═══════════════════════════════════════════
def test_proposal_store():
    print("\n═══ 3. ProposalStore ═══")
    from app.infrastructure.db.proposal_store import ProposalStore
    from app.domain.secretary.models import Proposal

    store = ProposalStore()
    user_id = "test_user_diag"

    # 尝试清除旧测试数据
    try:
        db = store._get_db()
        db.execute("DELETE FROM secretary_proposals WHERE user_id = %s", (user_id,))
    except Exception as e:
        print(f"  ⚠ 清除数据失败 (可能是无数据库连接): {e}")

    p1 = Proposal(emoji="📖", title="测试1", description="desc1", action_type="review",
                   priority=3, payload={}, insight_source="test")
    p2 = Proposal(emoji="📖", title="测试2", description="desc2", action_type="practice",
                   priority=5, payload={}, insight_source="test")

    try:
        store.save_proposal(p1, user_id=user_id)
        _check("保存提案1", bool(p1.id))
        store.save_proposal(p2, user_id=user_id)
        _check("保存提案2", bool(p2.id))
        _check("ID 不同", p1.id != p2.id)

        pending = store.get_pending_proposals(user_id=user_id)
        _check("待处理列表非空", len(pending) > 0)

        # pending 返回的是 Proposal 对象（Pydantic），用 .title 访问
        _check("标题匹配", any(p.title == "测试1" for p in pending))

        # 验证 update_status
        try:
            store.update_status(p1.id, user_id, "accepted")
            # 用 get_pending 验证不再是 pending
            pending_after = store.get_pending_proposals(user_id=user_id)
            _check("接受后不再出现在待处理", all(p.id != p1.id for p in pending_after))
        except Exception as e:
            _check(f"更新状态异常: {e}", False)

    except Exception as e:
        _check(f"ProposalStore 测试异常 (DB 不可用?): {e}", False)
        print("  ⚠ 跳过数据库依赖的后续测试")


# ═══════════════════════════════════════════
# 4. SecretaryEventHandler 测试
# ═══════════════════════════════════════════
def test_event_handler():
    print("\n═══ 4. SecretaryEventHandler ═══")
    from app.domain.secretary.engines.secretary_event_handler import SecretaryEventHandler
    from app.infrastructure.event_bus import EventBus

    handler = SecretaryEventHandler()
    _check("Handler 创建", handler is not None)
    _check("初始未订阅", not handler._subscribed)

    # 使用真正的 EventBus 实例
    bus = EventBus()
    handler.subscribe(bus)
    _check("订阅后已注册", handler._subscribed)
    
    # EventBus 的 _handlers 是 dict[type_str, list[callable]]
    _check("SessionCompleted 已订阅", "SessionCompleted" in bus._handlers)
    _check("CognitiveNodeUpdated 已订阅", "CognitiveNodeUpdated" in bus._handlers)
    _check("PracticeSubmitted 已订阅", "PracticeSubmitted" in bus._handlers)

    handler.unsubscribe()
    _check("取消订阅", not handler._subscribed)
    # EventBus.unsubscribe 只移除 handler 不删除键，检查列表为空
    _check("SessionCompleted handler 已移除", len(bus._handlers.get("SessionCompleted", [])) == 0)
    _check("PracticeSubmitted handler 已移除", len(bus._handlers.get("PracticeSubmitted", [])) == 0)


# ═══════════════════════════════════════════
# 5. BehaviorTrigger 测试
# ═══════════════════════════════════════════
def test_behavior_trigger():
    print("\n═══ 5. BehaviorTrigger ═══")
    from app.domain.secretary.engines.behavior_trigger import (
        BehaviorTriggerModule,
        on_practice_submitted,
        on_session_completed,
        _find_struggling_topics,
        _find_stale_topics,
        _find_ready_for_expansion,
    )

    # 5a — 模块注册元数据
    mod = BehaviorTriggerModule()
    _check("模块名称", mod.meta.name == "behavior_trigger")
    _check("默认启用", mod.meta.default_enabled)
    _check("间隔 == 300", mod.meta.run_interval_seconds == 300)

    # 5b — on_practice_submitted (低正确率)
    import asyncio
    low_correctness_result = asyncio.run(on_practice_submitted(
        user_id="test_user",
        atom_node_ids=["node_1"],
        correctness=0.3,
    ))
    _check("低正确率生成提案", low_correctness_result is not None)
    if low_correctness_result:
        _check("action_type == review", low_correctness_result.action_type == "review")
        _check("insight_source 含 practice_feedback",
             "practice_feedback" in low_correctness_result.insight_source)
        _check("priority >= 3", low_correctness_result.priority >= 3)

    # 5c — on_practice_submitted (高正确率 => 不生成)
    high_correctness_result = asyncio.run(on_practice_submitted(
        user_id="test_user",
        atom_node_ids=["node_2"],
        correctness=0.8,
    ))
    _check("高正确率不生成提案", high_correctness_result is None)

    # 5d — on_session_completed (高正确率 + 长时长)
    session_result = asyncio.run(on_session_completed(
        user_id="test_user", accuracy=0.9, duration_minutes=30,
    ))
    _check("会话完成生成反思提案", session_result is not None)
    if session_result:
        _check("action_type == review", session_result.action_type == "review")

    # 5e — 辅助函数 (空列表)
    _check("find_struggling_topics(空)", len(_find_struggling_topics([])) == 0)
    _check("find_stale_topics(空)", len(_find_stale_topics([])) == 0)
    _check("find_ready_for_expansion(空)", len(_find_ready_for_expansion([])) == 0)


# ═══════════════════════════════════════════
# 6. ActiveChecker 测试
# ═══════════════════════════════════════════
def test_active_checker():
    print("\n═══ 6. ActiveChecker ═══")
    from app.domain.secretary.engines.active_checker import ActiveChecker
    from app.domain.secretary.engines.module_registry import module_registry

    checker = ActiveChecker(user_id="test_user_diag")
    _check("Checker 创建成功", checker is not None)
    _check("默认间隔", hasattr(checker, "_check_interval"))

    # 确保模块已注册
    module_registry.discover_builtin()
    modules = module_registry.list_modules()
    _check(f"已注册模块数 >= 5 ({len(modules)})", len(modules) >= 5)


# ═══════════════════════════════════════════
# 7. Notification Store (Frontend) 逻辑验证
# ═══════════════════════════════════════════
def test_notification_store():
    print("\n═══ 7. NotificationStore (类型定义验证) ═══")
    try:
        from app.domain.secretary.models import Proposal
        p = Proposal(emoji="📖", title="test", description="test",
                     action_type="review", priority=3, payload={},
                     insight_source="test", generated_by="behavior_trigger")
        _check("Proposal 支持 generated_by", p.generated_by == "behavior_trigger")
        
        # 支持 payload (等效于 metadata)
        p.payload["execution_result"] = {"success": True, "message": "done"}
        _check("Proposal payload 支持任意数据", p.payload.get("execution_result", {}).get("success") is True)
    except Exception as e:
        _check(f"Proposal 模型检查异常: {e}", False)
        traceback.print_exc()


# ═══════════════════════════════════════════
# 主入口
# ═══════════════════════════════════════════
if __name__ == "__main__":
    print("=" * 60)
    print("伴学系统模块单元测试")
    print("=" * 60)

    test_proposal_model()
    test_module_registry()
    test_proposal_store()
    test_event_handler()
    test_behavior_trigger()
    test_active_checker()
    test_notification_store()

    print("\n" + "=" * 60)
    print(f"总计: {PASS + FAIL}  |  ✅ PASS: {PASS}  |  ❌ FAIL: {FAIL}")
    print("=" * 60)
    sys.exit(0 if FAIL == 0 else 1)