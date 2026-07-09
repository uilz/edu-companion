"""CognitiveOperationRegistry — 认知操作注册/派发中心 测试"""

import sys
from pathlib import Path

# 确保 backend/ 在 sys.path
BACKEND = Path(__file__).resolve().parent.parent
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

import pytest

from app.domain.cognitive.operation_registry import CognitiveOperationRegistry


# ── Fixtures ──

@pytest.fixture
def reg():
    """每个测试独立的 CognitiveOperationRegistry 实例"""
    return CognitiveOperationRegistry()


@pytest.fixture
def ops_dir() -> str:
    """返回 app/domain/cognitive/operations/ 的绝对路径"""
    return str(
        Path(__file__).resolve().parent.parent
        / "app"
        / "domain"
        / "cognitive"
        / "operations"
    )


# ══════════════════════════════════════════════════════════════
#  Registry 核心功能
# ══════════════════════════════════════════════════════════════

class TestRegistryCore:
    """register / execute / get / list_operations / 未知操作"""

    def test_register_and_execute(self, reg):
        @reg.register("add", "加法运算", params_schema={"x": {"type": "number"}, "y": {"type": "number"}})
        def add(x: float, y: float) -> float:
            return x + y

        result = reg.execute("add", x=1.0, y=2.0)
        assert result == 3.0

    def test_get_returns_operation(self, reg):
        @reg.register("greet", "打招呼", params_schema={"name": {"type": "string"}})
        def greet(name: str) -> str:
            return f"Hello {name}"

        op = reg.get("greet")
        assert op is not None
        assert op.name == "greet"
        assert op.description == "打招呼"
        assert callable(op.handler)
        assert "name" in op.params_schema

    def test_get_nonexistent_returns_none(self, reg):
        op = reg.get("does_not_exist")
        assert op is None

    def test_list_operations(self, reg):
        @reg.register("op_a", "操作 A")
        def op_a():
            pass

        @reg.register("op_b", "操作 B")
        def op_b():
            pass

        ops = reg.list_operations()
        assert len(ops) == 2
        names = [o["name"] for o in ops]
        assert "op_a" in names
        assert "op_b" in names
        for o in ops:
            assert "description" in o
            assert "params_schema" in o

    def test_execute_unknown_raises_value_error(self, reg):
        with pytest.raises(ValueError, match="Unknown operation"):
            reg.execute("nonexistent")

    def test_register_uses_docstring_as_description(self, reg):
        @reg.register("doc_op")
        def doc_op():
            "文档字符串作为描述"
            return 42

        op = reg.get("doc_op")
        assert op is not None
        assert op.description == "文档字符串作为描述"
        assert reg.execute("doc_op") == 42


# ══════════════════════════════════════════════════════════════
#  BKT operations 测试
# ══════════════════════════════════════════════════════════════

class TestBKTOperations:
    """bkt_update / bkt_decay / aggregate_proficiency_to_parent"""

    @pytest.fixture
    def reg_with_bkt_ops(self, reg):
        from app.domain.cognitive.operations.bkt_operations import (
            bkt_update,
            bkt_decay,
            aggregate_proficiency_to_parent,
        )

        reg.register("bkt_update", "BKT 更新", params_schema={})(bkt_update)
        reg.register("bkt_decay", "BKT 衰减", params_schema={})(bkt_decay)
        reg.register("aggregate_proficiency_to_parent", "聚合掌握度", params_schema={})(
            aggregate_proficiency_to_parent
        )
        return reg

    def test_bkt_update_success(self, reg_with_bkt_ops):
        result = reg_with_bkt_ops.execute(
            "bkt_update",
            bkt_state={},
            success=True,
            difficulty=0.0,
            weight=1.0,
            now=1000.0,
        )
        assert result["subsystem"] == "bkt"
        assert result["bkt_after"]["bkt_proficiency"] > 0.3

    def test_bkt_update_failure_rises_less_than_success(self, reg_with_bkt_ops):
        failure = reg_with_bkt_ops.execute(
            "bkt_update",
            bkt_state={},
            success=False,
            difficulty=0.0,
            weight=1.0,
            now=1000.0,
        )
        success = reg_with_bkt_ops.execute(
            "bkt_update",
            bkt_state={},
            success=True,
            difficulty=0.0,
            weight=1.0,
            now=1000.0,
        )
        assert (
            failure["bkt_after"]["bkt_proficiency"]
            < success["bkt_after"]["bkt_proficiency"]
        )

    def test_bkt_decay_uninitialized(self, reg_with_bkt_ops):
        result = reg_with_bkt_ops.execute(
            "bkt_decay",
            bkt_state={"bkt_last_updated": 0.0},
            now=1000.0,
        )
        assert result["result_summary"] == "no decay (uninitialized)"

    def test_aggregate_proficiency(self, reg_with_bkt_ops):
        result = reg_with_bkt_ops.execute(
            "aggregate_proficiency_to_parent",
            child_proficiencies=[0.8, 0.6],
            child_weights=[1.0, 1.0],
        )
        assert result["mastery"] == pytest.approx(0.7, rel=1e-4)


# ══════════════════════════════════════════════════════════════
#  Activation operations 测试
# ══════════════════════════════════════════════════════════════

class TestActivationOperations:
    """activation_update / activation_decay"""

    @pytest.fixture
    def reg_with_activation_ops(self, reg):
        from app.domain.cognitive.operations.activation_operations import (
            activation_update,
            activation_decay,
        )

        reg.register("activation_update", "激活更新", params_schema={})(activation_update)
        reg.register("activation_decay", "激活衰减", params_schema={})(activation_decay)
        return reg

    def test_activation_update(self, reg_with_activation_ops):
        result = reg_with_activation_ops.execute(
            "activation_update",
            activation_state={},
            event_timestamp=1000.0,
            now=1000.0,
        )
        assert result["subsystem"] == "activation"
        assert result["activation_after"]["act_base_level"] > 0.0

    def test_activation_decay(self, reg_with_activation_ops):
        result = reg_with_activation_ops.execute(
            "activation_decay",
            activation_state={"act_base_level": 1.0, "act_last_updated": 0.0},
            now=86400.0,
        )
        assert result["activation_after"]["act_base_level"] < 1.0


# ══════════════════════════════════════════════════════════════
#  Trend operations 测试
# ══════════════════════════════════════════════════════════════

class TestTrendOperations:
    """update_trend"""

    @pytest.fixture
    def reg_with_trend_ops(self, reg):
        from app.domain.cognitive.operations.trend_operations import update_trend

        reg.register("update_trend", "更新趋势", params_schema={})(update_trend)
        return reg

    def test_update_trend_new_trend_plateau(self, reg_with_trend_ops):
        now = 1000.0
        result = reg_with_trend_ops.execute(
            "update_trend",
            trend_state={},
            new_proficiency=0.5,
            now=now,
            last_practiced=now,
        )
        assert result["subsystem"] == "trend"
        ta = result["trend_after"]
        assert ta["trend_direction"] == "plateau"
        assert ta["_recent_proficiencies"] == [0.5]

    def test_update_trend_ascending(self, reg_with_trend_ops):
        now = 2000.0
        trend_state = {
            "_recent_proficiencies": [0.3, 0.35, 0.4],
            "trend_velocity": 0.0,
            "trend_stagnation_days": 0.0,
        }
        result = reg_with_trend_ops.execute(
            "update_trend",
            trend_state=trend_state,
            new_proficiency=0.5,
            now=now,
            last_practiced=now,
        )
        ta = result["trend_after"]
        assert ta["trend_direction"] == "ascending"
        assert ta["_recent_proficiencies"][-1] == 0.5


# ══════════════════════════════════════════════════════════════
#  Scheduling operations 测试
# ══════════════════════════════════════════════════════════════

class TestSchedulingOperations:
    """update_scheduling"""

    @pytest.fixture
    def reg_with_scheduling_ops(self, reg):
        from app.domain.cognitive.operations.scheduling_operations import update_scheduling

        reg.register("update_scheduling", "更新调度", params_schema={})(update_scheduling)
        return reg

    def test_update_scheduling_low_proficiency(self, reg_with_scheduling_ops):
        now = 1000.0
        result = reg_with_scheduling_ops.execute(
            "update_scheduling",
            scheduling_state={},
            proficiency=0.2,
            stability=0.5,
            stagnation_days=0.0,
            is_core=True,
            goal_distance=-1,
            last_practiced=now,
            successful_reviews=0,
            now=now,
        )
        assert result["subsystem"] == "scheduling"
        assert result["scheduling_after"]["sched_urgency"] > 0.0


# ══════════════════════════════════════════════════════════════
#  GoalAlignment operations 测试
# ══════════════════════════════════════════════════════════════

class TestGoalAlignmentOperations:
    """update_goal_alignment / shortest_path_to_goals"""

    @pytest.fixture
    def reg_with_goal_ops(self, reg):
        from app.domain.cognitive.operations.goal_alignment_operations import (
            update_goal_alignment,
            shortest_path_to_goals,
        )

        reg.register("update_goal_alignment", "目标对齐", params_schema={})(update_goal_alignment)
        reg.register("shortest_path_to_goals", "最短路径", params_schema={})(shortest_path_to_goals)
        return reg

    def test_shortest_path(self, reg_with_goal_ops):
        edges = [("a", "b"), ("b", "c")]
        result = reg_with_goal_ops.execute(
            "shortest_path_to_goals",
            start_node="a",
            goal_nodes=["c"],
            edges=edges,
        )
        assert result["min_distance"] == 2

    def test_update_goal_alignment(self, reg_with_goal_ops):
        result = reg_with_goal_ops.execute(
            "update_goal_alignment",
            goal_alignment_state={},
            goal_distances={"goal1": 1, "goal2": 3},
        )
        assert result["goal_alignment_after"]["goal_distance"] == 1


# ══════════════════════════════════════════════════════════════
#  discover 发现机制
# ══════════════════════════════════════════════════════════════

class TestDiscover:
    """discover 自动扫描发现操作文件"""

    def test_discover_operations(self, ops_dir):
        # 清除全局单例，确保测试独立性
        import app.domain.cognitive.operation_registry as reg_mod
        reg_mod._registry = None

        reg = CognitiveOperationRegistry()
        count = reg.discover([ops_dir])

        # discover 返回成功加载的 *_operations.py 文件数（当前包含 12 个文件）
        assert count >= 10

        # 操作注册在全局单例上
        global_reg = reg_mod.get_registry()
        operation_names = {op.name for op in global_reg._operations.values()}
        for name in (
            "bkt_update",
            "bkt_decay",
            "activation_update",
            "update_trend",
            "update_scheduling",
            "update_goal_alignment",
            "shortest_path_to_goals",
        ):
            assert name in operation_names, f"操作 {name} 应被注册"

        # 清理全局单例
        reg_mod._registry = None
