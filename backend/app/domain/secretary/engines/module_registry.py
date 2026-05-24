"""扩展框架 — 模块注册、生命周期管理、元数据统一

设计原则:
1. 每个模块是一个 SecretaryModule 子类，实现 run_check() 和元数据
2. 注册表全局单例，支持 enable/disable/toggle
3. 模块间互不依赖，各自独立运行
4. 冷启动模块自动感知数据量，不足时静默跳过

使用方式:
    registry = SecretaryModuleRegistry()
    registry.discover_builtin()
    for proposal in registry.run_checks("default_user", ctx):
        store.save_proposal(proposal)
"""

from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from ..models import Proposal, ScoredInsight, SessionContext

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════
# 模块基础类
# ═══════════════════════════════════════════

@dataclass
class ModuleMeta:
    """模块元数据"""
    name: str                        # 唯一标识名 (如 "review_reminder")
    display_name: str                # 显示名 (如 "复习提醒")
    emoji: str                       # 图标
    description: str                 # 简短说明
    default_enabled: bool = True     # 默认是否启用
    run_interval_seconds: int = 600  # 检查间隔
    version: str = "1.0.0"
    author: str = "系统内置"


class SecretaryModule(ABC):
    """所有秘书模块的基类"""

    @property
    @abstractmethod
    def meta(self) -> ModuleMeta:
        """模块元数据"""
        ...

    async def on_activate(self) -> None:
        """模块激活时调用（可选覆写）"""
        pass

    async def on_deactivate(self) -> None:
        """模块停用时调用（可选覆写）"""
        pass

    @abstractmethod
    async def run_check(self, user_id: str, ctx: SessionContext | None = None) -> list[Proposal]:
        """执行一次模块检查，返回生成的提案列表（空列表=无事项）"""
        ...

    async def health_check(self) -> str:
        """模块健康状态（可选覆写）"""
        return "ok"

    def __hash__(self) -> int:
        return hash(self.meta.name)


# ═══════════════════════════════════════════
# 注册表
# ═══════════════════════════════════════════

class SecretaryModuleRegistry:
    """模块注册表 — 全局单例"""

    def __init__(self) -> None:
        self._modules: dict[str, SecretaryModule] = {}
        self._enabled: dict[str, bool] = {}
        self._last_run: dict[str, float] = {}
        self._stats: dict[str, dict] = {}

    # ── 注册 ──

    def register(self, module: SecretaryModule) -> bool:
        """注册一个模块，重复注册覆盖旧模块"""
        name = module.meta.name
        self._modules[name] = module
        if name not in self._enabled:
            self._enabled[name] = module.meta.default_enabled
        self._stats.setdefault(name, {"total_runs": 0, "total_proposals": 0, "errors": 0})
        logger.info("秘书模块注册: %s %s %s", module.meta.emoji, module.meta.display_name, module.meta.version)
        return True

    def discover_builtin(self) -> int:
        """发现并注册所有内置模块"""
        from .builtin_review_reminder import ReviewReminderModule
        from .builtin_fatigue_manager import FatigueManagerModule
        from .builtin_daily_brief import DailyBriefModule

        for cls in [ReviewReminderModule, FatigueManagerModule, DailyBriefModule]:
            self.register(cls())
        return len(self._modules)

    def get_module(self, name: str) -> SecretaryModule | None:
        return self._modules.get(name)

    def list_modules(self) -> list[dict[str, Any]]:
        """列出所有已注册模块"""
        results = []
        for name, mod in self._modules.items():
            results.append({
                "name": name,
                **mod.meta.__dict__,
                "enabled": self._enabled.get(name, mod.meta.default_enabled),
                "last_run": self._last_run.get(name),
                "stats": self._stats.get(name, {}),
            })
        return results

    # ── 启停控制 ──

    def enable(self, name: str) -> bool:
        if name not in self._modules:
            return False
        self._enabled[name] = True
        return True

    def disable(self, name: str) -> bool:
        if name not in self._modules:
            return False
        self._enabled[name] = False
        return True

    def is_enabled(self, name: str) -> bool:
        return self._enabled.get(name, self._modules.get(name, object()).meta.default_enabled if name in self._modules else False)

    # ── 运行 ──

    async def run_module(self, name: str, user_id: str, ctx: SessionContext | None = None) -> list[Proposal]:
        """运行单个模块并返回提案"""
        mod = self._modules.get(name)
        if not mod or not self._enabled.get(name, False):
            return []

        try:
            proposals = await mod.run_check(user_id, ctx)
            self._stats[name]["total_runs"] += 1
            self._stats[name]["total_proposals"] += len(proposals)
            self._last_run[name] = time.time()

            # 给提案标记来源
            for p in proposals:
                if not p.generated_by:
                    p.generated_by = mod.meta.name

            return proposals
        except Exception as e:
            self._stats[name]["errors"] += 1
            logger.warning("模块 %s 检查失败: %s", name, e)
            return []

    async def run_enabled_checks(
        self, user_id: str, ctx: SessionContext | None = None,
    ) -> list[Proposal]:
        """运行所有已启用的模块"""
        all_proposals = []
        for name, enabled in list(self._enabled.items()):
            if enabled and name in self._modules:
                proposals = await self.run_module(name, user_id, ctx)
                all_proposals.extend(proposals)
        return all_proposals

    # ── 偏好同步 ──

    def apply_prefs(self, enabled_extensions: list[str]) -> None:
        """根据用户偏好同步模块启停"""
        for name in self._modules:
            self._enabled[name] = name in enabled_extensions

    def to_prefs_list(self) -> list[str]:
        """导出已启用模块列表"""
        return [name for name, en in self._enabled.items() if en]


# ── 全局实例 ──
module_registry = SecretaryModuleRegistry()
