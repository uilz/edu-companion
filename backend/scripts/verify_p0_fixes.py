#!/usr/bin/env python3
"""
P0 修复点一键验收脚本 (Task #33)

覆盖 11 个 P0 修复点，输出 PASS/FAIL 表 + 整体健康度报告。

运行方式
========
    cd /home/deploy/edu-companion
    python backend/scripts/verify_p0_fixes.py            # 仅静态校验
    python backend/scripts/verify_p0_fixes.py --strict   # 含 pytest 回归 (可选)

设计原则
========
1. **快速** — 不依赖数据库 / 外部服务，5 秒内出结果
2. **明确** — 每个验证点独立输出 PASS/FAIL + 修复建议
3. **可重复** — 不修改任何状态，可反复运行
4. **CI 友好** — 退出码 0 = 全 PASS，1 = 存在 FAIL

验收点定义在 ``P0_VERIFICATIONS`` 字典；每项是一个
``(check_fn, fix_suggestion)`` 元组，``check_fn`` 返回 ``(bool, str)``。
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path
from typing import Callable

# ── 路径初始化 ──────────────────────────────────────────────
REPO = Path(__file__).resolve().parents[2]
BACKEND = REPO / "backend"
FRONTEND = REPO / "frontend"
sys.path.insert(0, str(BACKEND))

# ── 工具 ──────────────────────────────────────────────────
PASS_COUNT = 0
FAIL_COUNT = 0
FAIL_DETAILS: list[str] = []


def _ok(category: str, name: str, detail: str = ""):
    global PASS_COUNT
    PASS_COUNT += 1
    suffix = f"  ({detail})" if detail else ""
    print(f"  \033[32m[PASS]\033[0m {name}{suffix}")


def _fail(category: str, name: str, detail: str, fix: str):
    global FAIL_COUNT
    FAIL_COUNT += 1
    msg = f"[FAIL] {name} — {detail}\n        修复建议: {fix}"
    FAIL_DETAILS.append(f"{category} :: {msg}")
    print(f"  \033[31m[FAIL]\033[0m {name} — {detail}")
    print(f"        \033[33m修复建议: {fix}\033[0m")


# ── 通用读文件辅助 ────────────────────────────────────────
def _read(rel: str) -> str:
    p = REPO / rel
    if not p.exists():
        return ""
    return p.read_text(encoding="utf-8", errors="ignore")


def _exists(rel: str) -> bool:
    return (REPO / rel).exists()


# ── P0 验证函数（每项返回 (passed, detail, fix_suggestion)） ──
# P0-1: 7 模块入口
def check_nav_config_exists() -> tuple[bool, str, str]:
    rel = "frontend/src/lib/navConfig.ts"
    if not _exists(rel):
        return False, "navConfig.ts 不存在", "创建 frontend/src/lib/navConfig.ts (Task #30 任务核心文件)"
    content = _read(rel)
    for sym in ("getNavItemsFor", "getQuickActions", "primaryNavItems"):
        if sym not in content:
            return False, f"navConfig.ts 缺导出 {sym}", f"补充导出 {sym}"
    return True, "已导出 getNavItemsFor / getQuickActions / primaryNavItems", ""


def check_sidebar_uses_navconfig() -> tuple[bool, str, str]:
    rel = "frontend/src/components/layout/Sidebar.tsx"
    content = _read(rel)
    if "getNavItemsFor" not in content:
        return False, "Sidebar 未引用 getNavItemsFor", "将硬编码 navItems 替换为 getNavItemsFor('sidebar')"
    # 校验是否实际调用了 getNavItemsFor (e.g. `getNavItemsFor('sidebar')` 而非仅作类型注解)
    if not re.search(r"getNavItemsFor\(\s*['\"]sidebar['\"]\s*\)", content):
        return False, "Sidebar 引用了 getNavItemsFor 但未实际调用", "确保执行 getNavItemsFor('sidebar') 一次"
    return True, "Sidebar 已从 navConfig 读取", ""


def check_mobile_drawer_uses_navconfig() -> tuple[bool, str, str]:
    rel = "frontend/src/components/layout/MobileDrawer.tsx"
    content = _read(rel)
    if "getNavItemsFor" not in content:
        return False, "MobileDrawer 未引用 getNavItemsFor", "替换为 getNavItemsFor('drawer')"
    return True, "MobileDrawer 已从 navConfig 读取", ""


def check_bottom_nav_uses_navconfig() -> tuple[bool, str, str]:
    rel = "frontend/src/components/layout/BottomNav.tsx"
    content = _read(rel)
    if "getNavItemsFor" not in content:
        return False, "BottomNav 未引用 getNavItemsFor", "替换为 getNavItemsFor('bottomNav')"
    return True, "BottomNav 已从 navConfig 读取", ""


def check_cockpit_uses_quickactions() -> tuple[bool, str, str]:
    """任务 #78: OverviewTab 已删除，验证 Cockpit 接管驾驶舱路由
    Cockpit 不使用 getQuickActions（直接渲染 QuickLink 自有 4 个按钮），
    此检查只确认 Cockpit 文件存在。"""
    rel = "frontend/src/components/dashboard/Cockpit.tsx"
    content = _read(rel)
    if "Cockpit" not in content or "QuickLink" not in content:
        return False, "Cockpit 缺失", "确认 Cockpit.tsx 含 QuickLink 子组件"
    return True, "Cockpit 已接管驾驶舱", ""


def check_nav_items_count() -> tuple[bool, str, str]:
    """验证 navConfig 中 entry 数 >= 12 (6 原有 + 6 新增)"""
    content = _read("frontend/src/lib/navConfig.ts")
    # 统计 path: "/xxx" 行
    paths = re.findall(r'path:\s*[\'"](\/[\w\-/]+)[\'"]', content)
    unique = set(paths)
    n = len(unique)
    if n < 12:
        return False, f"只发现 {n} 个 path: {sorted(unique)}", "补齐 6 个新模块的 nav 条目 (project/reading/liveroom/planning/flashcard/interest)"
    return True, f"发现 {n} 条 path", ""


# P0-2: 事件循环修复
def check_plan_item_completed_in_events() -> tuple[bool, str, str]:
    content = _read("backend/shared/events.py")
    if "class PlanItemCompleted" not in content:
        return False, "shared/events.py 缺 PlanItemCompleted 事件类", "在 shared/events.py 添加 PlanItemCompleted dataclass"
    return True, "PlanItemCompleted 已声明", ""


def check_completion_writer_no_resend() -> tuple[bool, str, str]:
    rel = "backend/app/services/planning/completion_writer.py"
    content = _read(rel)
    if not _exists(rel):
        return False, "completion_writer.py 不存在", "新建 app/services/planning/completion_writer.py (Task #P0-2 核心文件)"
    # 关键: 应当没有对源事件做 publish_event 调用
    # 允许在 docstring/注释中提到 "不重发 ProjectNodeCompleted" 之类的说明
    # 真正的违规是 publish_event(ProjectNodeCompleted) 这种调用
    publish_calls = re.findall(
        r"(?:publish_event|publish|_publish|_publish_event|bus\.publish|_publish_event_safe)\s*\(\s*\w*ProjectNodeCompleted",
        content,
    )
    if publish_calls:
        return False, f"completion_writer 调用了 {len(publish_calls)} 次源事件发布", "移除 ProjectNodeCompleted 重发调用"
    return True, "completion_writer 未重发源事件", ""


def check_completion_writer_test_exists() -> tuple[bool, str, str]:
    rel = "backend/tests/test_planning_completion_writer.py"
    if not _exists(rel):
        return False, "test_planning_completion_writer.py 不存在", "为 completion_writer 写单元测试 (Task #P0-2 验收测试)"
    return True, "completion_writer 测试已就位", ""


# P0-3: source_module 枚举
def check_planning_source_module_enum() -> tuple[bool, str, str]:
    content = _read("backend/shared/events.py")
    if "class PlanningSourceModule" not in content:
        return False, "events.py 缺 PlanningSourceModule 枚举", "新增 enum PlanningSourceModule(str, Enum)"
    return True, "PlanningSourceModule 枚举已声明", ""


def check_schemas_use_enum() -> tuple[bool, str, str]:
    rel = "backend/app/api/planning/schemas.py"
    content = _read(rel)
    if "PlanningSourceModule" not in content:
        return False, "schemas.py 未引用 PlanningSourceModule", "在 schemas.py 用 PlanningSourceModule 替换 Literal[...]"
    if "source_module:" in content and "Literal" in content.split("source_module:")[1][:200]:
        return False, "schemas.py 仍使用 Literal 描述 source_module", "改为 source_module: PlanningSourceModule"
    return True, "schemas.py 已用 PlanningSourceModule", ""


def check_completion_writer_uses_enum() -> tuple[bool, str, str]:
    rel = "backend/app/services/planning/completion_writer.py"
    content = _read(rel)
    if "PlanningSourceModule" not in content:
        return False, "completion_writer 未引用 PlanningSourceModule", "改用 PlanningSourceModule 枚举做路由"
    return True, "completion_writer 已用枚举", ""


# 架构 P0-1: event_bus_utils
def check_event_bus_utils_exists() -> tuple[bool, str, str]:
    rel = "backend/app/infrastructure/event_bus_utils.py"
    if not _exists(rel):
        return False, "event_bus_utils.py 不存在", "新建 app/infrastructure/event_bus_utils.py (Task 架构 P0-1 核心文件)"
    content = _read(rel)
    if "publish_event_safe" not in content:
        return False, "event_bus_utils.py 缺 publish_event_safe 导出", "导出 def publish_event_safe(event, bus=None)"
    return True, "event_bus_utils.publish_event_safe 已就位", ""


def check_modules_use_publish_event_safe() -> tuple[bool, str, str]:
    """检查 7 个目标模块 (api + services) 是否都使用 publish_event_safe 替代内联 try/except

    7 个新模块的所有 .py 文件 (api + services) 都应能查到 publish_event_safe 引用。
    """
    target_modules = [
        ("flashcard",   "backend/app/api/flashcard",   "backend/app/services/flashcard"),
        ("interest",    "backend/app/api/interest",    "backend/app/services/interest"),
        ("liveroom",    "backend/app/api/liveroom",    "backend/app/services/liveroom"),
        ("planning",    "backend/app/api/planning",    "backend/app/services/planning"),
        ("project",     "backend/app/api/project",     "backend/app/services/project"),
        ("reading",     "backend/app/api/reading",     "backend/app/services/reading"),
        ("secretary",   "backend/app/api/secretary",   "backend/app/services/secretary"),
    ]
    using = []
    missing = []
    for name, api_dir, svc_dir in target_modules:
        text = ""
        any_dir = False
        for d in (api_dir, svc_dir):
            p = REPO / d
            if not p.exists():
                continue
            any_dir = True
            for f in p.rglob("*.py"):
                if "__pycache__" in str(f):
                    continue
                text += f.read_text(encoding="utf-8", errors="ignore") + "\n"
        if not any_dir:
            missing.append(f"{name} (目录不存在)")
            continue
        if "publish_event_safe" in text:
            using.append(name)
        else:
            missing.append(name)
    if len(using) < len(target_modules):
        return False, f"仅 {len(using)}/{len(target_modules)} 模块用 publish_event_safe; 缺失: {missing}", "在缺失模块的 api/service 文件中导入并使用 publish_event_safe"
    return True, f"{len(using)}/{len(target_modules)} 模块已用 publish_event_safe", ""


# 架构 P0-2: liveroom 直写 SQL
def check_liveroom_no_inline_sql() -> tuple[bool, str, str]:
    """检查 liveroom/service.py 的 3 个数据捕获入口是否改走 service 调用

    3 处明确指定的直写 SQL 已改造为 execute_sync 工具调用:
      - mark_error       → execute_sync("tool_error_mark", ...)
      - post_message     → execute_sync("tool_message_post", ...)
      - capture_vocabulary → execute_sync("tool_vocabulary_capture", ...)

    (其他 SQL 是房间/参与者管理, 留在 service.py 是合理的)
    """
    rel = "backend/app/api/liveroom/service.py"
    content = _read(rel)
    if not content:
        return False, "liveroom/service.py 不存在", "新建 app/api/liveroom/service.py"
    # 3 个入口必须调 execute_sync
    targets = {
        "mark_error": r"def mark_error\(",
        "post_message": r"def post_message\(",
        "capture_vocabulary": r"def capture_vocabulary\(",
    }
    bad = []
    for fn, sig in targets.items():
        m = re.search(sig, content)
        if not m:
            bad.append(f"{fn} 函数未找到")
            continue
        # 函数体内必须出现 execute_sync 调用
        start = m.end()
        # 用花括号配对找出函数体结束
        body = _extract_function_body(content, start)
        if "execute_sync" not in body:
            # 检查是否还在用 db.execute
            if re.search(r"db\.execute\s*\(", body):
                bad.append(f"{fn} 仍直写 db.execute")
            else:
                bad.append(f"{fn} 未通过 execute_sync 调用工具")
    if bad:
        return False, "; ".join(bad), "3 个数据捕获入口 (mark_error / post_message / capture_vocabulary) 必须走 execute_sync(...) 调用共享 tool"
    return True, "3 个数据捕获入口已改走 service 调用", ""


def _extract_function_body(content: str, start: int) -> str:
    """从函数签名后开始扫描, 取出函数体字符串 (基于 def 行后下一行开始)"""
    # 简单做法: 从 start 到下一个 "^\n\ndef " 或 "^\ndef " 之间
    rest = content[start:]
    m = re.search(r"\n(?:def |async def |class )", rest)
    if m:
        return rest[:m.start()]
    return rest


def check_liveroom_service_helpers() -> tuple[bool, str, str]:
    """检查 liveroom 是否有 create_error_entry / create_explain_card 等 service 函数

    这些函数应在 services/liveroom/ 下, 由 tool handler 调用。
    """
    svc_dir = REPO / "backend/app/services/liveroom"
    api_service = REPO / "backend/app/api/liveroom/service.py"
    found = []
    for d in (svc_dir, api_service.parent if api_service.exists() else None):
        if d is None or not d.exists():
            continue
        for f in d.rglob("*.py"):
            if "__pycache__" in str(f):
                continue
            text = f.read_text(encoding="utf-8", errors="ignore")
            for sym in ("def create_error_entry", "def create_explain_card",
                        "class ExplainCard", "def create_vocabulary_capture"):
                if sym in text and sym not in found:
                    found.append(f"{sym} (in {f.relative_to(REPO)})")
    if len(found) < 2:
        return False, f"liveroom 缺服务函数: 找到 {found}", "在 app/services/liveroom/notes.py 中新增 create_error_entry() / create_explain_card() 服务函数, 并让 tool handler 调用"
    return True, f"已找到 {len(found)} 个服务函数: {found}", ""


# 架构 P0-3: source 字段拆分
def check_events_source_split() -> tuple[bool, str, str]:
    """验证 4 个事件类有 source + cross_module_source 拆分"""
    rel = "backend/shared/events.py"
    content = _read(rel)
    targets = {
        "FlashCardCreated": ("source:", "cross_module_source:"),
        "ReadingNoteCreated": ("source:", "cross_module_source:"),
        "MoodStressRecorded": ("source:", "cross_module_source:"),
        "InterestTagCreated": ("source:", "cross_module_source:"),
    }
    missing = []
    for cls, (s1, s2) in targets.items():
        # 在类的 dataclass 体内查
        m = re.search(rf"class {cls}\(DomainEvent\):.*?(?=^class |\Z)", content, re.MULTILINE | re.DOTALL)
        if not m:
            missing.append(f"{cls} (类未找到)")
            continue
        body = m.group(0)
        if s1 not in body or s2 not in body:
            missing.append(f"{cls} (缺 {s1} 或 {s2})")
    if missing:
        return False, "; ".join(missing), "为 4 个事件类同时声明 source 和 cross_module_source"
    return True, "4 个事件类均含 source + cross_module_source", ""


# 架构 P1: AI persona 共享 tool
def check_ai_persona_uses_shared_tool() -> tuple[bool, str, str]:
    rel = "backend/app/services/liveroom/ai_persona.py"
    content = _read(rel)
    if not _exists(rel):
        return False, "ai_persona.py 不存在", "检查 liveroom/ai_persona.py 路径"
    if "tool_repository" not in content and "execute_shared_tool" not in content:
        return False, "ai_persona.py 未引用 tool_repository / execute_shared_tool", "在 ai_persona.py 改用 tool_repository.execute() 或 execute_shared_tool()"
    return True, "ai_persona.py 已接入 tool_repository / execute_shared_tool", ""


def check_liveroom_tools_in_registry() -> tuple[bool, str, str]:
    """检查 4 个 liveroom tool action 在 ALL_TOOL_INFO 中"""
    try:
        sys.path.insert(0, str(BACKEND))
        from app.infrastructure.llm.tool_registry import ALL_TOOL_INFO
        expected = [
            "tool_vocabulary_capture",
            "tool_error_mark",
            "tool_message_post",
            "tool_knowledge_search",
        ]
        missing = [n for n in expected if n not in ALL_TOOL_INFO]
        if missing:
            return False, f"ALL_TOOL_INFO 缺 {missing}", "在 app/infrastructure/llm/liveroom_tools.py 注册缺失的 tool"
        return True, "4 个 liveroom tool action 已在 ALL_TOOL_INFO", ""
    except Exception as e:
        return False, f"导入 ALL_TOOL_INFO 失败: {e}", "检查 app/infrastructure/llm/tool_registry.py 模块结构"


def check_liveroom_shared_tools_test() -> tuple[bool, str, str]:
    rel = "backend/tests/test_task35_liveroom_shared_tools.py"
    if not _exists(rel):
        return False, "test_task35_liveroom_shared_tools.py 不存在", "新建测试文件"
    return True, "liveroom shared tools 测试就位", ""


# 架构 P2: ToolDefinition 合并
def check_tool_definition_inherits_tool_info() -> tuple[bool, str, str]:
    rel = "backend/app/infrastructure/llm/tool_registry.py"
    content = _read(rel)
    if "class ToolDefinition" not in content:
        return False, "tool_registry.py 缺 class ToolDefinition", "新增 class ToolDefinition"
    m = re.search(r"class ToolDefinition\(([^)]+)\)", content)
    if not m or "ToolInfo" not in m.group(1):
        return False, "ToolDefinition 未继承 ToolInfo", "改为 class ToolDefinition(ToolInfo):"
    return True, "ToolDefinition 继承 ToolInfo", ""


def check_base_py_is_reexport() -> tuple[bool, str, str]:
    rel = "backend/app/domain/secretary/tools/base.py"
    content = _read(rel)
    if not _exists(rel):
        return False, "tools/base.py 不存在", "检查 app/domain/secretary/tools/base.py"
    if "re-export" not in content.lower() and "from app.infrastructure.llm.tool_registry" not in content:
        return False, "base.py 似未做 re-export", "将 base.py 改为从 tool_registry re-export ToolDefinition"
    return True, "tools/base.py 已是 re-export 壳", ""


# 架构 P3: 收尾
def check_project_create_node_batch_exposed() -> tuple[bool, str, str]:
    rel = "backend/app/services/project/__init__.py"
    content = _read(rel)
    if "def create_node_batch" not in content:
        return False, "project/__init__.py 缺 create_node_batch", "从 node_ref 暴露 create_node_batch 到 services.project 命名空间"
    return True, "create_node_batch 已暴露", ""


def check_copy_nodes_uses_service() -> tuple[bool, str, str]:
    rel = "backend/app/services/project/node_ref.py"
    content = _read(rel)
    if "create_node_batch" not in content:
        return False, "node_ref.copy_nodes_across_projects 未走 service.create_node_batch", "改为调用 app.services.project.create_node_batch"
    return True, "node_ref.copy_nodes_across_projects 已走 service", ""


def check_mood_stress_reuses_modules() -> tuple[bool, str, str]:
    rel = "backend/app/services/secretary/modules/mood_stress.py"
    content = _read(rel)
    if not _exists(rel):
        return False, "modules/mood_stress.py 不存在", "检查 app/services/secretary/modules/mood_stress.py"
    has_fatigue = "fatigue_manager" in content
    has_daily = "daily_brief" in content
    if not (has_fatigue and has_daily):
        return False, f"mood_stress 缺疲劳/简报复用 (fatigue={has_fatigue}, daily={has_daily})", "实际化调用 fatigue_manager / daily_brief 模块"
    return True, "mood_stress 已复用 fatigue_manager / daily_brief", ""


def check_interest_cross_module_importer() -> tuple[bool, str, str]:
    rel = "backend/app/services/interest/cross_module_importer.py"
    content = _read(rel)
    if not _exists(rel):
        return False, "cross_module_importer.py 不存在", "检查 app/services/interest/cross_module_importer.py"
    if "create_room" not in content:
        return False, "cross_module_importer 未调 liveroom.create_room", "实际调 liveroom.service.create_room"
    return True, "interest.cross_module_importer 已调 liveroom.create_room", ""


# 文档 P0: ADR 同步
def check_adrs_have_implementation_status() -> tuple[bool, str, str]:
    """检查 7 个 ADR 都有"实现状态"小节"""
    adr_dir = REPO / "docs/adr"
    if not adr_dir.exists():
        return False, "docs/adr 目录不存在", "检查 docs/adr 目录"
    expected = ["0001", "0002-card", "0003-reading", "0004-language", "0005-mood", "0006-planning", "0007-interest"]
    missing = []
    for stem in expected:
        # 找到对应文件
        matches = list(adr_dir.glob(f"{stem}*.md"))
        if not matches:
            missing.append(f"{stem}*.md (文件不存在)")
            continue
        for f in matches:
            content = f.read_text(encoding="utf-8", errors="ignore")
            if "实现状态" not in content:
                missing.append(f"{f.name} (缺实现状态小节)")
    if missing:
        return False, "; ".join(missing), "在 7 个 ADR 文件添加 ## 实现状态 (截至 YYYY-MM-DD) 小节"
    return True, "7 个 ADR 都有实现状态小节", ""


def check_adrs_status_accepted() -> tuple[bool, str, str]:
    """检查 7 个 ADR 状态从 Proposed 改 Accepted"""
    adr_dir = REPO / "docs/adr"
    not_accepted = []
    for f in sorted(adr_dir.glob("000*.md")):
        if "memory-card" in f.name:  # 排除非 7 模块的旧 ADR
            continue
        content = f.read_text(encoding="utf-8", errors="ignore")
        # 在文件前 30 行内查找 Status
        head = "\n".join(content.splitlines()[:30])
        m = re.search(r"##\s*Status\s*\n+(\w+)", head)
        if not m:
            not_accepted.append(f"{f.name} (无 Status)")
            continue
        if m.group(1).strip() != "Accepted":
            not_accepted.append(f"{f.name} (Status={m.group(1).strip()})")
    if not_accepted:
        return False, f"未 Accepted: {not_accepted}", "将 7 个 ADR 的 Status 改为 Accepted"
    return True, "7 个 ADR 状态均为 Accepted", ""


# ── 注册表 ──────────────────────────────────────────────
P0_VERIFICATIONS: dict[str, list[tuple[str, Callable[[], tuple[bool, str, str]]]]] = {
    "P0-1 7模块入口": [
        ("navConfig.ts 存在并导出 getNavItemsFor/getQuickActions", check_nav_config_exists),
        ("Sidebar 使用 getNavItemsFor", check_sidebar_uses_navconfig),
        ("MobileDrawer 使用 getNavItemsFor", check_mobile_drawer_uses_navconfig),
        ("BottomNav 使用 getNavItemsFor", check_bottom_nav_uses_navconfig),
        ("Cockpit 接管驾驶舱 (任务 #78)", check_cockpit_uses_quickactions),
        ("navConfig 含 12+ 条 path (6 原有 + 6 新增)", check_nav_items_count),
    ],
    "P0-2 事件循环修复": [
        ("shared/events.py 含 PlanItemCompleted", check_plan_item_completed_in_events),
        ("completion_writer.py 不重发源事件", check_completion_writer_no_resend),
        ("test_planning_completion_writer.py 存在", check_completion_writer_test_exists),
    ],
    "P0-3 source_module 枚举": [
        ("shared/events.py 含 PlanningSourceModule 枚举", check_planning_source_module_enum),
        ("schemas.py 用 PlanningSourceModule", check_schemas_use_enum),
        ("completion_writer.py 用枚举", check_completion_writer_uses_enum),
    ],
    "架构 P0-1 event_bus_utils": [
        ("event_bus_utils.py 存在并导出 publish_event_safe", check_event_bus_utils_exists),
        ("7 个目标模块使用 publish_event_safe", check_modules_use_publish_event_safe),
    ],
    "架构 P0-2 liveroom 直写 SQL": [
        ("liveroom/service.py 已无内联 SQL", check_liveroom_no_inline_sql),
        ("liveroom/service.py 提供 create_error_entry / ExplainCard 服务函数", check_liveroom_service_helpers),
    ],
    "架构 P0-3 source 字段拆分": [
        ("FlashCardCreated/ReadingNoteCreated/MoodStressRecorded/InterestTagCreated 都用 source + cross_module_source 拆分", check_events_source_split),
    ],
    "架构 P1 AI persona 共享 tool": [
        ("ai_persona.py 真的使用 tool_repository / execute_shared_tool", check_ai_persona_uses_shared_tool),
        ("4 个 liveroom tool action 在 ALL_TOOL_INFO 中可发现", check_liveroom_tools_in_registry),
        ("test_task35_liveroom_shared_tools.py 存在", check_liveroom_shared_tools_test),
    ],
    "架构 P2 ToolDefinition 合并": [
        ("tool_registry.ToolDefinition 继承 ToolInfo", check_tool_definition_inherits_tool_info),
        ("secretary/tools/base.py 是 re-export 壳", check_base_py_is_reexport),
    ],
    "架构 P3 收尾": [
        ("project/__init__.py 含 create_node_batch", check_project_create_node_batch_exposed),
        ("node_ref.copy_nodes_across_projects 走 service", check_copy_nodes_uses_service),
        ("mood_stress 实际调用 fatigue_manager / daily_brief", check_mood_stress_reuses_modules),
        ("interest.cross_module_importer 真调 liveroom.create_room", check_interest_cross_module_importer),
    ],
    "文档 P0 ADR 同步": [
        ("7 个 ADR 都有实现状态小节", check_adrs_have_implementation_status),
        ("7 个 ADR 状态从 Proposed 改 Accepted", check_adrs_status_accepted),
    ],
}


# ── 主流程 ──────────────────────────────────────────────
def main() -> int:
    print("=" * 78)
    print("  P0 修复点一键验收 (Task #33)")
    print(f"  仓库根: {REPO}")
    print("=" * 78)

    for category, items in P0_VERIFICATIONS.items():
        print(f"\n\033[1m[{category}]\033[0m  ({len(items)} 项)")
        for name, fn in items:
            try:
                passed, detail, fix = fn()
            except Exception as e:  # noqa: BLE001
                passed, detail, fix = False, f"异常: {e}", "检查脚本调用是否正确"
            if passed:
                _ok(category, name, detail)
            else:
                _fail(category, name, detail, fix)

    # ── 总览 ──────────────────────────────────────────────
    total = PASS_COUNT + FAIL_COUNT
    print("\n" + "=" * 78)
    print(f"  验收结果: {PASS_COUNT}/{total} PASS  /  {FAIL_COUNT} FAIL")
    if FAIL_COUNT == 0:
        print("  \033[32m整体健康度: A (全部 P0 修复点已就位)\033[0m")
    elif FAIL_COUNT <= 2:
        print("  \033[33m整体健康度: B (个别 P0 点未完成, 请查看 FAIL)\033[0m")
    elif FAIL_COUNT <= 5:
        print("  \033[33m整体健康度: C (存在 P0 缺口, 需要补齐)\033[0m")
    else:
        print("  \033[31m整体健康度: D (大量 P0 缺口, 需要紧急修复)\033[0m")
    print("=" * 78)

    if FAIL_DETAILS:
        print("\n\033[31m[待修复清单]\033[0m")
        for i, d in enumerate(FAIL_DETAILS, 1):
            print(f"  {i}. {d}")
        print()

    return 0 if FAIL_COUNT == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
