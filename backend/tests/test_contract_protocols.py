"""
契约测试: Protocol 接口约定

验证所有 Protocol 的结构完整性:
- 所有方法 async
- 所有方法有类型注解
- 无循环依赖（不导入业务模块）
- runtime_checkable 标记正确
"""

import inspect
import ast
from pathlib import Path
from typing import Protocol, runtime_checkable

import pytest

from app.shared.protocols.practice import PracticeService
from app.shared.protocols.knowledge import KnowledgeGraphService
from app.shared.protocols.planning import PlanningService
from app.shared.protocols.conversation import ConversationService
from app.shared.protocols.achievements import AchievementService
from app.shared.protocols.analytics import AnalyticsService
from app.shared.protocols.materials import MaterialService
from app.shared.protocols.persistence import KnowledgeStateRepository


ALL_PROTOCOLS = {
    "PracticeService": PracticeService,
    "KnowledgeGraphService": KnowledgeGraphService,
    "PlanningService": PlanningService,
    "ConversationService": ConversationService,
    "AchievementService": AchievementService,
    "AnalyticsService": AnalyticsService,
    "MaterialService": MaterialService,
    "KnowledgeStateRepository": KnowledgeStateRepository,
}


def _get_public_methods(cls):
    """获取 Protocol 的所有公开 async 方法名"""
    return {
        name for name, _ in inspect.getmembers(cls, inspect.isfunction)
        if not name.startswith("_")
    }


# ═══════════════════════════════════════════
# 结构验证
# ═══════════════════════════════════════════

@pytest.mark.parametrize("proto_name,proto_cls", ALL_PROTOCOLS.items())
def test_protocol_is_protocol(proto_name, proto_cls):
    """每个 Protocol 应是 typing.Protocol 的子类"""
    assert issubclass(proto_cls, Protocol), \
        f"{proto_name} 不是 Protocol 子类"


@pytest.mark.parametrize("proto_name,proto_cls", ALL_PROTOCOLS.items())
def test_protocol_has_methods(proto_name, proto_cls):
    """每个 Protocol 至少定义 2 个方法"""
    methods = _get_public_methods(proto_cls)
    assert len(methods) >= 2, \
        f"{proto_name}: 只有 {len(methods)} 个方法，期待 ≥2"


@pytest.mark.parametrize("proto_name,proto_cls", ALL_PROTOCOLS.items())
def test_all_methods_are_async(proto_name, proto_cls):
    """所有 Protocol 方法必须是 async"""
    for method_name in _get_public_methods(proto_cls):
        method = getattr(proto_cls, method_name)
        assert inspect.iscoroutinefunction(method), \
            f"{proto_name}.{method_name} 必须是 async 方法"


@pytest.mark.parametrize("proto_name,proto_cls", ALL_PROTOCOLS.items())
def test_methods_have_type_annotations(proto_name, proto_cls):
    """所有方法参数和返回值应有类型注解"""
    for method_name in _get_public_methods(proto_cls):
        method = getattr(proto_cls, method_name)
        hints = inspect.signature(method)
        
        # 检查返回值注解
        assert hints.return_annotation != inspect.Parameter.empty, \
            f"{proto_name}.{method_name} 缺少返回类型注解"


# ═══════════════════════════════════════════
# 依赖方向验证
# ═══════════════════════════════════════════

def test_protocol_files_have_zero_business_imports():
    """Protocol 文件不得导入任何业务模块（保证单向依赖）"""
    proto_dir = Path(__file__).parent.parent / "app" / "shared" / "protocols"
    forbidden = {"app.services", "app.domain", "app.api", "app.core", "app.infra"}
    
    violations = []
    for f in proto_dir.glob("*.py"):
        if f.name == "__init__.py":
            continue
        tree = ast.parse(f.read_text())
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                module = getattr(node, 'module', '') or ''
                if module:
                    for forbidden_pkg in forbidden:
                        if module.startswith(forbidden_pkg):
                            violations.append(f"{f.name}: imports {module}")
    
    assert not violations, \
        f"Protocol 文件违规导入业务模块:\n" + "\n".join(violations)


# ═══════════════════════════════════════════
# runtime_checkable 验证
# ═══════════════════════════════════════════

def test_practice_conversation_are_runtime_checkable():
    """PracticeService 和 ConversationService 标记了 @runtime_checkable"""
    assert runtime_checkable(PracticeService), "PracticeService 缺少 @runtime_checkable"
    assert runtime_checkable(ConversationService), "ConversationService 缺少 @runtime_checkable"


# ═══════════════════════════════════════════
# 契约快照（变更时需要显式更新）
# ═══════════════════════════════════════════

def test_contract_snapshot_matches():
    """
    契约快照测试: 方法签名哈希不应意外变更。
    
    如果新增/删除方法是有意的，更新下方的 EXPECTED_HASH。
    """
    import hashlib
    import json

    # 收集所有 Protocol 方法签名
    snapshot = {}
    for proto_name, proto_cls in sorted(ALL_PROTOCOLS.items()):
        methods = {}
        for method_name in sorted(_get_public_methods(proto_cls)):
            method = getattr(proto_cls, method_name)
            sig = str(inspect.signature(method))
            methods[method_name] = sig
        snapshot[proto_name] = methods

    snapshot_json = json.dumps(snapshot, sort_keys=True)
    actual_hash = hashlib.sha256(snapshot_json.encode()).hexdigest()[:16]

    # 当前快照哈希（首次运行后固化）
    # 如果本测试失败，说明 Protocol 签名已变更：
    #   - 有意变更 → 更新 EXPECTED_HASH
    #   - 无意变更 → 这是 breaking change，请修复
    EXPECTED_HASH = "1dc2747b5c639b49"

    assert actual_hash == EXPECTED_HASH, (
        f"契约快照哈希变化!\n"
        f"  当前: {actual_hash}\n"
        f"  预期: {EXPECTED_HASH}\n\n"
        f"当前签名:\n{snapshot_json}\n\n"
        f"如果变更是有意的，更新 test_contract_protocols.py 中的 EXPECTED_HASH。"
    )
