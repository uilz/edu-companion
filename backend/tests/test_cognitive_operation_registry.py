"""CognitiveOperationRegistry — 认知操作注册/派发中心 测试"""

import sys
import time
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
#  belief_operations 测试
# ══════════════════════════════════════════════════════════════

class TestBeliefOperations:
    """update_belief_from_evidence / decay_belief"""

    @pytest.fixture
    def reg_with_belief_ops(self, reg):
        """将 belief_operations 中的函数注册到独立实例"""
        from app.domain.cognitive.operations.belief_operations import (
            update_belief_from_evidence,
            decay_belief,
        )

        reg.register(
            "update_belief_from_evidence",
            "贝叶斯证据融合: 基于答题正误更新 Beta(α,β) 信念分布",
            params_schema={
                "node_id": {"type": "string", "required": True},
                "user_id": {"type": "string", "required": True},
                "belief": {"type": "object", "required": True},
                "success": {"type": "boolean", "required": True},
                "weight": {"type": "number", "required": False, "default": 1.0},
                "now": {"type": "number", "required": False},
            },
        )(update_belief_from_evidence)

        reg.register(
            "decay_belief",
            "遗忘衰减: 基于时间差降低信念精度 (precision)",
            params_schema={
                "belief": {"type": "object", "required": True},
                "now": {"type": "number", "required": False},
            },
        )(decay_belief)

        return reg

    def test_update_belief_from_evidence_success(self, reg_with_belief_ops):
        """成功: α=2→3, mean=0.5→0.6"""
        belief = {
            "alpha": 2.0,
            "beta": 2.0,
            "proficiency_mean": 0.5,
            "proficiency_precision": 4.0,
            "peak_proficiency": 0.5,
            "last_updated": 1000.0,
        }
        result = reg_with_belief_ops.execute(
            "update_belief_from_evidence",
            node_id="n1",
            user_id="u1",
            belief=belief,
            success=True,
            weight=1.0,
            now=2000.0,
        )

        assert result["subsystem"] == "belief"
        assert result["method"] == "update_belief_from_evidence"

        ba = result["belief_after"]
        assert ba["alpha"] == pytest.approx(3.0, rel=1e-4)
        assert ba["beta"] == pytest.approx(2.0, rel=1e-4)
        assert ba["proficiency_mean"] == pytest.approx(0.6, rel=1e-4)  # 3/(3+2)
        assert ba["proficiency_precision"] == pytest.approx(5.0, rel=1e-4)
        assert ba["peak_proficiency"] == pytest.approx(0.6, rel=1e-4)
        assert ba["last_updated"] == 2000.0

    def test_update_belief_from_evidence_failure(self, reg_with_belief_ops):
        """失败: β=2→3, mean=0.5→0.4"""
        belief = {
            "alpha": 2.0,
            "beta": 2.0,
            "proficiency_mean": 0.5,
            "proficiency_precision": 4.0,
            "peak_proficiency": 0.5,
            "last_updated": 1000.0,
        }
        result = reg_with_belief_ops.execute(
            "update_belief_from_evidence",
            node_id="n1",
            user_id="u1",
            belief=belief,
            success=False,
            weight=1.0,
            now=2000.0,
        )

        assert result["subsystem"] == "belief"
        assert result["method"] == "update_belief_from_evidence"

        ba = result["belief_after"]
        assert ba["alpha"] == pytest.approx(2.0, rel=1e-4)
        assert ba["beta"] == pytest.approx(3.0, rel=1e-4)
        assert ba["proficiency_mean"] == pytest.approx(0.4, rel=1e-4)  # 2/(2+3)
        assert ba["proficiency_precision"] == pytest.approx(5.0, rel=1e-4)

    def test_decay_belief_no_time_diff(self, reg_with_belief_ops):
        """无时间差: elapsed_hours ≤ 0 → 不衰减"""
        now = 5000.0
        belief = {
            "alpha": 5.0,
            "beta": 3.0,
            "proficiency_mean": 5.0 / 8.0,
            "proficiency_precision": 8.0,
            "peak_proficiency": 0.7,
            "last_updated": now,
        }
        result = reg_with_belief_ops.execute(
            "decay_belief",
            belief=belief,
            now=now,
        )

        assert result["subsystem"] == "belief"
        assert result["method"] == "decay_belief"
        assert result["result_summary"] == "no decay (no time elapsed)"

        ba = result["belief_after"]
        assert ba["alpha"] == pytest.approx(5.0, rel=1e-4)
        assert ba["beta"] == pytest.approx(3.0, rel=1e-4)

    def test_decay_belief_long_time(self, reg_with_belief_ops):
        """长时间差: precision 从 ~8 衰减至接近保底值 4, mean 向 0.5 漂移"""
        now = 7 * 86400  # 7 天后
        belief = {
            "alpha": 5.0,
            "beta": 3.0,
            "proficiency_mean": 5.0 / 8.0,
            "proficiency_precision": 8.0,
            "peak_proficiency": 0.7,
            "last_updated": 0.0,
        }
        result = reg_with_belief_ops.execute(
            "decay_belief",
            belief=belief,
            now=now,
        )

        assert result["subsystem"] == "belief"

        ba = result["belief_after"]
        # 7 天 → precision 大幅衰减至接近保底值 4
        assert ba["proficiency_precision"] == pytest.approx(4.0, abs=0.5)
        # mean 从 0.625 向 0.5 漂移
        assert ba["proficiency_mean"] == pytest.approx(0.5, abs=0.02)
        assert ba["peak_proficiency"] == 0.7  # peak 不受衰减影响


# ══════════════════════════════════════════════════════════════
#  trend_operations 测试
# ══════════════════════════════════════════════════════════════

class TestTrendOperations:
    """update_trend"""

    @pytest.fixture
    def reg_with_trend_ops(self, reg):
        """将 trend_operations 中的函数注册到独立实例"""
        from app.domain.cognitive.operations.trend_operations import update_trend

        reg.register(
            "update_trend",
            "更新趋势: 基于新 proficiency_mean 更新 velocity/stagnation/volatility/direction",
            params_schema={
                "trend": {"type": "object", "required": True},
                "new_mean": {"type": "number", "required": True},
                "now": {"type": "number", "required": False},
                "last_updated": {"type": "number", "required": False},
            },
        )(update_trend)

        return reg

    def test_update_trend_new_trend_plateau(self, reg_with_trend_ops):
        """新趋势: 空历史 + 单个采样点 → direction=plateau"""
        now = 1000.0
        result = reg_with_trend_ops.execute(
            "update_trend",
            trend={},
            new_mean=0.5,
            now=now,
            last_updated=now,
        )

        assert result["subsystem"] == "trend"
        assert result["method"] == "update_trend"

        ta = result["trend_after"]
        assert ta["direction"] == "plateau"
        assert ta["recent_proficiencies"] == [0.5]
        assert ta["velocity_ewma"] == pytest.approx(0.0, abs=1e-4)
        assert ta["volatility_std"] == pytest.approx(0.0, abs=1e-4)

    def test_update_trend_ascending(self, reg_with_trend_ops):
        """上行趋势: 持续增长 → ewma > 0.02 → direction=ascending"""
        now = 2000.0
        trend = {
            "recent_proficiencies": [0.3, 0.35, 0.4],
            "velocity_ewma": 0.0,
            "stagnation_days": 0.0,
        }
        result = reg_with_trend_ops.execute(
            "update_trend",
            trend=trend,
            new_mean=0.5,
            now=now,
            last_updated=now,
        )

        assert result["subsystem"] == "trend"

        ta = result["trend_after"]
        assert ta["direction"] == "ascending"
        assert len(ta["recent_proficiencies"]) == 4
        assert ta["recent_proficiencies"][-1] == 0.5
        assert ta["velocity_ewma"] > 0.02
        assert ta["volatility_std"] >= 0.0


# ══════════════════════════════════════════════════════════════
#  discover 发现机制
# ══════════════════════════════════════════════════════════════

class TestDiscover:
    """discover 自动扫描发现操作文件"""

    def test_discover_operations(self, ops_dir):
        """扫描 app/cognitive/operations/ → 发现 2 个操作文件 → 注册 3 个操作"""
        # 清除全局单例，确保测试独立性
        import app.domain.cognitive.operation_registry as reg_mod
        reg_mod._registry = None

        reg = CognitiveOperationRegistry()
        count = reg.discover([ops_dir])

        # discover 返回成功加载的 *_operations.py 文件数
        assert count == 2

        # 操作注册在全局单例上
        global_reg = reg_mod.get_registry()
        operation_names = {op.name for op in global_reg._operations.values()}
        for name in ("update_belief_from_evidence", "decay_belief", "update_trend"):
            assert name in operation_names, f"操作 {name} 应被注册"

        # 清理全局单例
        reg_mod._registry = None
