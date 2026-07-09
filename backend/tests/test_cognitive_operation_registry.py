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
#  Belief operations 测试
# ══════════════════════════════════════════════════════════════

class TestBeliefOperations:
    """belief_update / belief_information_gain / shrinkage_prior_apply / belief_decay"""

    @pytest.fixture
    def reg_with_belief_ops(self, reg):
        from app.domain.cognitive.operations.belief_operations import (
            belief_update,
            belief_information_gain,
            shrinkage_prior_apply,
            belief_decay,
        )

        reg.register("belief_update", "Beta 更新", params_schema={})(belief_update)
        reg.register("belief_information_gain", "信息增益", params_schema={})(belief_information_gain)
        reg.register("shrinkage_prior_apply", "收缩先验", params_schema={})(shrinkage_prior_apply)
        reg.register("belief_decay", "Beta 衰减", params_schema={})(belief_decay)
        return reg

    def test_belief_update_success_increases_alpha(self, reg_with_belief_ops):
        result = reg_with_belief_ops.execute(
            "belief_update",
            belief_state={"belief_alpha": 2.0, "belief_beta": 2.0},
            success=True,
            difficulty=0.0,
            weight=1.0,
            now=1000.0,
        )
        after = result["belief_after"]
        assert after["belief_alpha"] > 2.0
        assert after["belief_beta"] >= 2.0
        assert after["belief_evidence_count"] == 1
        assert after["last_information_gain"] > 0

    def test_belief_update_failure_increases_beta(self, reg_with_belief_ops):
        result = reg_with_belief_ops.execute(
            "belief_update",
            belief_state={"belief_alpha": 2.0, "belief_beta": 2.0},
            success=False,
            difficulty=0.0,
            weight=1.0,
            now=1000.0,
        )
        after = result["belief_after"]
        assert after["belief_beta"] > 2.0
        assert after["belief_alpha"] >= 2.0

    def test_belief_update_harder_question_updates_less(self, reg_with_belief_ops):
        easy = reg_with_belief_ops.execute(
            "belief_update",
            belief_state={"belief_alpha": 2.0, "belief_beta": 2.0},
            success=True,
            difficulty=-1.0,
            weight=1.0,
            now=1000.0,
        )
        hard = reg_with_belief_ops.execute(
            "belief_update",
            belief_state={"belief_alpha": 2.0, "belief_beta": 2.0},
            success=True,
            difficulty=1.0,
            weight=1.0,
            now=1000.0,
        )
        # 根据设计文档简化版：难题 success 时 beta 增量更大（更谨慎）
        assert hard["belief_after"]["belief_beta"] > easy["belief_after"]["belief_beta"]

    def test_belief_information_gain_positive(self, reg_with_belief_ops):
        ig = reg_with_belief_ops.execute(
            "belief_information_gain",
            belief_state_before={"belief_alpha": 2.0, "belief_beta": 2.0},
            belief_state_after={"belief_alpha": 3.0, "belief_beta": 2.0},
        )
        assert ig["information_gain"] > 0

    def test_shrinkage_prior_sparse_data(self, reg_with_belief_ops):
        result = reg_with_belief_ops.execute(
            "shrinkage_prior_apply",
            child_belief_state={"belief_alpha": 1.0, "belief_beta": 1.0, "belief_evidence_count": 0},
            parent_belief_state={"belief_alpha": 8.0, "belief_beta": 2.0, "belief_evidence_count": 10},
            shrinkage_strength=5.0,
        )
        eff = result["effective_belief"]
        # 无证据时子节点完全向父节点 0.8 收缩
        assert eff["proficiency"] > 0.5
        assert abs(eff["proficiency"] - 0.8) < 0.01

    def test_shrinkage_prior_rich_data(self, reg_with_belief_ops):
        result = reg_with_belief_ops.execute(
            "shrinkage_prior_apply",
            child_belief_state={"belief_alpha": 8.0, "belief_beta": 2.0, "belief_evidence_count": 20},
            parent_belief_state={"belief_alpha": 2.0, "belief_beta": 8.0, "belief_evidence_count": 10},
            shrinkage_strength=5.0,
        )
        eff = result["effective_belief"]
        # 证据多时有效信念显著偏向子节点自身（子节点均值为 0.8）
        assert eff["proficiency"] > 0.6

    def test_belief_decay_over_time(self, reg_with_belief_ops):
        now = 86400.0 * 20
        result = reg_with_belief_ops.execute(
            "belief_decay",
            belief_state={
                "belief_alpha": 10.0,
                "belief_beta": 10.0,
                "belief_last_updated": 86400.0 * 10,
                "stability_factor": 0.5,
                "forgetting_rate": 0.1,
            },
            now=now,
        )
        after = result["belief_after"]
        # 精度应下降，但均值保持约 0.5
        assert after["belief_alpha"] < 10.0
        assert after["belief_beta"] < 10.0
        assert abs(after["belief_alpha"] - after["belief_beta"]) < 0.5


# ══════════════════════════════════════════════════════════════
#  Graph propagation 测试
# ══════════════════════════════════════════════════════════════

class TestGraphPropagationOperations:
    """graph_propagate"""

    @pytest.fixture
    def reg_with_graph_ops(self, reg):
        from app.domain.cognitive.operations.graph_propagation_operations import graph_propagate

        reg.register("graph_propagate", "图传播", params_schema={})(graph_propagate)
        return reg

    def test_graph_propagate_to_direct_neighbor(self, reg_with_graph_ops):
        result = reg_with_graph_ops.execute(
            "graph_propagate",
            source_node_id="a",
            delta_alpha=1.0,
            delta_beta=0.0,
            edges=[
                {
                    "source_id": "a",
                    "target_id": "b",
                    "edge_type": "co_occurrence",
                    "edge_weight": 0.5,
                    "edge_distance_decay": 0.5,
                    "max_propagation_hops": 2,
                }
            ],
            neighbor_belief_states={"b": {"independent_evidence_weight": 1.0}},
        )
        updates = result["propagation_after"]["updates"]
        assert len(updates) == 1
        assert updates[0]["node_id"] == "b"
        assert updates[0]["distance"] == 1
        assert updates[0]["delta_alpha"] > 0

    def test_graph_propagate_prerequisite_direction(self, reg_with_graph_ops):
        # 前置 a -> b：从 a 传播到 b 应生效，反向不生效
        result = reg_with_graph_ops.execute(
            "graph_propagate",
            source_node_id="a",
            delta_alpha=1.0,
            delta_beta=0.0,
            edges=[
                {
                    "source_id": "a",
                    "target_id": "b",
                    "edge_type": "prerequisite",
                    "edge_weight": 0.6,
                    "edge_distance_decay": 0.5,
                    "max_propagation_hops": 2,
                }
            ],
            neighbor_belief_states={"b": {"independent_evidence_weight": 1.0}},
        )
        updates = {u["node_id"]: u for u in result["propagation_after"]["updates"]}
        assert "b" in updates

        reverse = reg_with_graph_ops.execute(
            "graph_propagate",
            source_node_id="b",
            delta_alpha=1.0,
            delta_beta=0.0,
            edges=[
                {
                    "source_id": "a",
                    "target_id": "b",
                    "edge_type": "prerequisite",
                    "edge_weight": 0.6,
                    "edge_distance_decay": 0.5,
                    "max_propagation_hops": 2,
                }
            ],
            neighbor_belief_states={"a": {"independent_evidence_weight": 1.0}},
        )
        assert len(reverse["propagation_after"]["updates"]) == 0

    def test_graph_propagate_distance_decay(self, reg_with_graph_ops):
        # a - b - c，d=2 的 c 应该比 d=1 的 b 更新量小
        result = reg_with_graph_ops.execute(
            "graph_propagate",
            source_node_id="a",
            delta_alpha=1.0,
            delta_beta=0.0,
            edges=[
                {
                    "source_id": "a",
                    "target_id": "b",
                    "edge_type": "co_occurrence",
                    "edge_weight": 0.8,
                    "edge_distance_decay": 0.5,
                    "max_propagation_hops": 2,
                },
                {
                    "source_id": "b",
                    "target_id": "c",
                    "edge_type": "co_occurrence",
                    "edge_weight": 0.8,
                    "edge_distance_decay": 0.5,
                    "max_propagation_hops": 2,
                },
            ],
            neighbor_belief_states={
                "b": {"independent_evidence_weight": 1.0},
                "c": {"independent_evidence_weight": 1.0},
            },
        )
        updates = {u["node_id"]: u for u in result["propagation_after"]["updates"]}
        assert updates["b"]["delta_alpha"] > updates["c"]["delta_alpha"]


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

    def test_update_scheduling_high_uncertainty_short_interval(self, reg_with_scheduling_ops):
        now = 1000.0
        result = reg_with_scheduling_ops.execute(
            "update_scheduling",
            scheduling_state={},
            belief_state={"belief_alpha": 1.0, "belief_beta": 1.0},
            last_practiced=now,
            stagnation_days=0.0,
            is_core=False,
            goal_distance=-1,
            now=now,
        )
        sched = result["scheduling_after"]
        # Beta(1,1) 不确定性高，间隔应较短
        assert sched["sched_interval_days"] < 2.0
        assert sched["sched_urgency"] > 0.0

    def test_update_scheduling_secretary_adjustment(self, reg_with_scheduling_ops):
        now = 1000.0
        base = reg_with_scheduling_ops.execute(
            "update_scheduling",
            scheduling_state={},
            belief_state={"belief_alpha": 5.0, "belief_beta": 5.0},
            last_practiced=now,
            adjustment_factor=1.0,
            now=now,
        )
        adjusted = reg_with_scheduling_ops.execute(
            "update_scheduling",
            scheduling_state={},
            belief_state={"belief_alpha": 5.0, "belief_beta": 5.0},
            last_practiced=now,
            adjustment_factor=2.0,
            now=now,
        )
        assert adjusted["scheduling_after"]["sched_interval_days"] > base["scheduling_after"]["sched_interval_days"]


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

        # discover 返回成功加载的 *_operations.py 文件数
        assert count >= 10

        # 操作注册在全局单例上
        global_reg = reg_mod.get_registry()
        operation_names = {op.name for op in global_reg._operations.values()}
        for name in (
            "belief_update",
            "belief_decay",
            "shrinkage_prior_apply",
            "graph_propagate",
            "update_scheduling",
            "activation_update",
            "update_trend",
            "update_goal_alignment",
            "shortest_path_to_goals",
        ):
            assert name in operation_names, f"操作 {name} 应被注册"

        # 清理全局单例
        reg_mod._registry = None
