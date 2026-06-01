# Phase 4 · 模块联动升级 — 架构重构 + 前端整合

> 版本: v2.0 (基于 2026-05-19 代码审计)  
> 最后更新: 2026-05-19  
> 状态: **✅ 全部实施完成** · Phase 4 闭环  
> 旧版: `docs/module-linkage-upgrade.md` (过时，已存档)

---

## 一、审计结论（13 项缺陷）

### 1.1 循环依赖（2 对）

```
🔴 循环 1: api ⇄ services
  api/practice.py
    → services.adaptive_planner   (API 调服务: 正常)
    → services.achievement_engine
    → services.knowledge_bridge
    → services.question_generator
    → services.behavior_analyzer
    → services.habit_formation
    → services.quality_analyzer
    → services.error_attribution
  
  services/conversation_llm.py:241
    → api.practice                (服务调 API: 倒挂!)

🔴 循环 2: core ⇄ services
  core/knowledge_trace.py:244,256,266 (3 处)
    → services.storage            (核心算法依赖基础设施)
  
  services/shared_ks.py:18
    → core.knowledge_trace        (服务依赖核心)
  services/adaptive_planner.py:19
    → core.knowledge_trace
```

### 1.2 全局单例（35 个，零依赖注入）

| 文件 | 单例 |
|------|------|
| `core/knowledge_trace.py` | `bkt_engine` |
| `core/learner_model.py` | `learner_engine` |
| `core/orchestrator.py` | `orchestrator` |
| `services/storage.py` | `storage` |
| `services/llm_service.py` | `llm_service` |
| `services/zpd_scheduler.py` | `zpd_scheduler`, `spacing_scheduler` |
| `services/achievement_engine.py` | `achievement_engine` |
| `services/behavior_analyzer.py` | `behavior_analyzer` |
| `services/habit_formation.py` | `habit_formation` |
| `services/adaptive_planner.py` | `adaptive_planner` |
| `services/quality_analyzer.py` | `quality_analyzer` |
| … 25 more | |

所有模块通过 `from app.xxx.yyy import singleton` 硬耦合。

### 1.3 API 层直接操作数据库

- `api/practice.py` — 大量 SQL (get_db, fetchone, upsert, execute)
- `api/study.py` — 直接 DB 查询
- `api/material.py` — 直接 DB 查询

### 1.4 submit_answer 同步长链（7 步串行）

```python
# api/practice.py submit_answer() — 当前实现
1. BKT update         (同步, 必需) ✓
2. DB attempt write   (同步, 必需) ✓
3. Error book write   (同步, 可异步)
4. Knowledge bridge   (同步, 可异步) ✗
5. Adaptive planner   (同步, 可异步) ✗
6. Achievement check  (同步, 可异步) ✗
7. Practice integrator(同步, 可异步) ✗
```

### 1.5 api/practice.py 上帝文件

单个文件 1025 行，承载 8 种职责：练习、错题、行为分析、习惯养成、题目质量、知识桥接、成就检测、错误归因。

### 1.6 前端碎片化

- 13 页，侧栏只露 7 个
- `/analytics`(1016行)、`/stats`、`/progress` 三页重叠
- `/errors`、`/calendar`、`/achievements`、`/quality` 用户找不到
- 模块间零上下文传递：跳转 `<Link href="/practice">` 不带任何参数

---

## 二、目标架构

### 2.1 分层模型（强制依赖规则）

```
┌──────────────────────────────────────────────────────────────┐
│                   presentation (api/)                         │
│  职责: HTTP/WS 路由、请求验证、响应序列化                       │
│  依赖: application 层接口 (UseCase)                           │
│  不得: 直接访问 DB、直接调用 services、持有业务逻辑             │
├──────────────────────────────────────────────────────────────┤
│                   application (use_cases/)                    │
│  职责: 编排业务用例、发布领域事件、事务边界                      │
│  依赖: domain 接口 (Protocol) + event_bus                    │
│  不得: 直接访问 DB、实现具体算法                               │
├──────────────────────────────────────────────────────────────┤
│                   domain (8 个模块)                            │
│  职责: 纯业务逻辑（BKT/ZPD/习惯/选题/对话编排）                  │
│  依赖: 只依赖 shared (schemas + protocols)                    │
│  不得: 直接访问 DB、调用外部服务、知道 presentation 层          │
├──────────────────────────────────────────────────────────────┤
│                   infrastructure (infra/)                     │
│  职责: DB 实现、LLM 客户端、文件存储、事件总线、熔断             │
│  依赖: domain 定义的接口 (Protocol)                           │
│  不得: 包含业务逻辑                                           │
├──────────────────────────────────────────────────────────────┤
│                   shared (schemas/ + events/ + protocols/)    │
│  职责: Pydantic 模型、事件定义、Protocol 接口                   │
│  依赖: 零外部依赖（只依赖 Python 标准库 + pydantic）            │
└──────────────────────────────────────────────────────────────┘
```

```
依赖规则（强制）:
✅ presentation → application  (通过接口)
✅ application → domain        (通过 Protocol)
✅ domain → shared             (schemas + protocols)
✅ infrastructure → domain     (实现 domain 接口)

❌ domain → infrastructure     (违反依赖倒置)
❌ domain → presentation       (层次倒挂)
❌ presentation → domain       (绕过 application)
❌ presentation → infrastructure (绕过 application + domain)
❌ infrastructure → presentation (层次倒挂)
```

### 2.2 8 个领域模块

| 模块 | 目录 | 现状文件数 | 暴露接口 |
|------|------|:--:|------|
| **practice** | `domain/practice/` | BKT+ZPD+question_gen+error_book+quality | `PracticeService` Protocol |
| **conversation** | `domain/conversation/` | conversation_llm+tree_ops+classifier+emotion | `ConversationService` Protocol |
| **planning** | `domain/planning/` | adaptive_planner | `PlanningService` Protocol |
| **analytics** | `domain/analytics/` | behavior_analyzer+habit_formation | `AnalyticsService` Protocol |
| **knowledge** | `domain/knowledge/` | knowledge_trace+knowledge_bridge+shared_ks | `KnowledgeService` Protocol |
| **materials** | `domain/materials/` | material_parser+indexer+search+question_gen+meta | `MaterialService` Protocol |
| **media** | `domain/media/` | media_search | `MediaService` Protocol |
| **achievements** | `domain/achievements/` | achievement_engine | `AchievementService` Protocol |

---

## 三、关键改造：原子步骤

### Phase 4A: 基础设施层（1 天）

#### A1. 创建 shared 层

```python
# shared/protocols/practice.py
from typing import Protocol, runtime_checkable
from shared.schemas.practice import Question, PracticeSession, SubmitResult, KnowledgeState

@runtime_checkable
class PracticeService(Protocol):
    async def generate_questions(self, subject: str, topic: str, level: str, count: int) -> list[Question]: ...
    async def create_session(self, user_id: str, question_ids: list[str]) -> PracticeSession: ...
    async def submit_answer(self, session_id: str, question_id: str, answer: str,
                            time_spent: float = 0.0, hints_used: int = 0) -> SubmitResult: ...
    async def get_knowledge_state(self, user_id: str, skill_id: str) -> KnowledgeState | None: ...
    async def get_errors(self, user_id: str, resolved: bool | None = None) -> list[dict]: ...
```

```python
# shared/protocols/persistence.py
class KnowledgeStateRepository(Protocol):
    async def load(self, user_id: str, skill_id: str) -> dict | None: ...
    async def save(self, user_id: str, skill_id: str, state: dict) -> None: ...
    async def load_all(self, user_id: str) -> dict[str, dict]: ...

class AttemptRepository(Protocol):
    async def save_attempt(self, attempt: dict) -> None: ...
    async def get_session_attempts(self, session_id: str) -> list[dict]: ...
```

定义 8 个 Protocol + 3 个 Repository Protocol + 10 个领域事件。

#### A2. 创建事件总线

```python
# infra/event_bus.py
import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, Awaitable

EventHandler = Callable[['DomainEvent'], Awaitable[None]]

class EventBus:
    def __init__(self):
        self._handlers: dict[str, list[EventHandler]] = {}
    
    def subscribe(self, event_type: str, handler: EventHandler) -> None:
        self._handlers.setdefault(event_type, []).append(handler)
    
    async def publish(self, event: 'DomainEvent') -> None:
        handlers = self._handlers.get(type(event).__name__, [])
        tasks = [self._safe_invoke(h, event) for h in handlers]
        await asyncio.gather(*tasks, return_exceptions=True)
    
    async def _safe_invoke(self, handler, event, timeout=5.0):
        try:
            await asyncio.wait_for(handler(event), timeout=timeout)
        except Exception:
            logger.exception(f"Handler failed for {type(event).__name__}")
```

#### A3. 领域事件定义

```python
# shared/events.py
@dataclass(frozen=True)
class AnswerSubmitted:
    event_id: str
    user_id: str
    session_id: str
    question_id: str
    skill_id: str
    is_correct: bool
    p_known_before: float
    p_known_after: float
    time_spent: float

@dataclass(frozen=True)
class KnowledgeStateUpdated:
    user_id: str
    skill_id: str
    old_mastery: str
    new_mastery: str
    p_known_before: float
    p_known_after: float

@dataclass(frozen=True)
class SessionCompleted:
    user_id: str
    session_id: str
    total_questions: int
    correct_count: int
    accuracy: float

@dataclass(frozen=True)
class AchievementUnlocked:
    user_id: str
    achievement_id: str
    level: int
    name: str

@dataclass(frozen=True)
class DailyGoalAchieved:
    user_id: str
    level: str
    streak_days: int

@dataclass(frozen=True)
class MaterialIndexed:
    user_id: str
    material_id: str
    chunk_count: int

@dataclass(frozen=True)
class WeaknessDetected:
    user_id: str
    skill_id: str
    error_count: int
    last_error_type: str
```

#### A4. 稳定性基础设施

```python
# infra/resilience.py
def with_timeout(seconds: float = 5.0): ...
def with_retry(max_attempts: int = 3, backoff: float = 0.5): ...

# infra/circuit_breaker.py
class CircuitBreaker:
    """熔断器 - 保护下游服务"""
    def __init__(self, name: str, failure_threshold: int = 5, recovery_timeout: float = 30.0): ...
    async def call(self, func, *args, **kwargs): ...

# infra/tracing.py
class TraceContext:
    """全链路追踪 - Trace ID 贯通"""
    @staticmethod
    def new() -> str: ...
    @staticmethod
    def current() -> str: ...
```

### Phase 4B: 消除循环依赖（2 天）

#### B1. 修复 api ⇄ services

**根因**: `services/conversation_llm.py:241` 导入 `api.practice`

```python
# 修复前
# services/conversation_llm.py:241
from app.api.practice import _sessions as _p_sessions

# 修复后
# domain/conversation/llm_engine.py
class ConversationLLMEngine:
    def __init__(self, practice: PracticeService):
        self._practice = practice  # 依赖注入，不 import
    
    async def build_context(self, branch_id: str) -> dict:
        practice_summary = await self._practice.get_summary(branch_id)
        return {**base_context, "practice": practice_summary}
```

#### B2. 修复 core ⇄ services

**根因**: `core/knowledge_trace.py` 直接调 `services/storage.py`

```python
# 修复前
# core/knowledge_trace.py:244
from app.services.storage import storage
data = storage.load(user_id)

# 修复后
# domain/knowledge/bkt_engine.py
class BKTEngine:
    def __init__(self, repo: KnowledgeStateRepository):
        self._repo = repo  # 通过接口注入
    
    async def load_or_create(self, user_id: str, skill_id: str):
        data = await self._repo.load(user_id, skill_id)
        if data:
            return KnowledgeState(**data)
        return self.create_knowledge_state(skill_id)

# infra/database.py
class PostgresKnowledgeStateRepo(KnowledgeStateRepository):
    async def load(self, user_id, skill_id): ...
    async def save(self, user_id, skill_id, state): ...
```

#### B3. 依赖注入容器（唯一的全局组装点）

```python
# application/di.py
class AppContainer:
    """应用容器 — 唯一的全局组装点"""
    
    def __init__(self):
        # 基础设施
        self.event_bus = EventBus()
        self.llm_client = DeepSeekClient()
        self.knowledge_repo = PostgresKnowledgeStateRepo()
        self.attempt_repo = PostgresAttemptRepo()
        
        # 领域服务（通过 Protocol 接口互相注入）
        self.practice_service = PracticeServiceImpl(
            knowledge_repo=self.knowledge_repo,
            attempt_repo=self.attempt_repo,
            event_bus=self.event_bus,
        )
        self.conversation_service = ConversationServiceImpl(
            llm=self.llm_client,
            practice=self.practice_service,  # ← Protocol
            event_bus=self.event_bus,
        )
        self.knowledge_service = KnowledgeServiceImpl(
            knowledge_repo=self.knowledge_repo,
            event_bus=self.event_bus,
        )
        # ... 其余 5 个 domain service
        
        # 事件订阅
        self._wire_events()
    
    def _wire_events(self):
        bus = self.event_bus
        bus.subscribe("AnswerSubmitted", self.analytics_service.on_answer_submitted)
        bus.subscribe("AnswerSubmitted", self.planning_service.on_answer_submitted)
        bus.subscribe("AnswerSubmitted", self.conversation_service.on_answer_submitted)
        bus.subscribe("AnswerSubmitted", self.knowledge_service.on_answer_submitted)
        bus.subscribe("KnowledgeStateUpdated", self.planning_service.on_knowledge_updated)
        bus.subscribe("SessionCompleted", self.achievement_service.on_session_completed)
        bus.subscribe("DailyGoalAchieved", self.conversation_service.on_goal_achieved)
        bus.subscribe("MaterialIndexed", self.material_service.on_indexed)

container = AppContainer()  # 全局唯一单例
```

### Phase 4C: 事件驱动改造（2 天）

#### C1. submit_answer 拆分为同步核心 + 异步副作用

```
改造前 (api/practice.py, 同步串行 ~7 步):

  submit_answer()
    ├── BKT update           (50ms, 同步)
    ├── DB attempt write     (20ms, 同步)
    ├── Error book write     (10ms, 同步)
    ├── Knowledge bridge     (5ms, 同步)
    ├── Adaptive planner     (15ms, 同步)
    ├── Achievement check    (30ms, 同步)
    └── return feedback      总耗时 ~130ms

改造后 (use_cases/submit_answer.py, ~50ms 返回):

  submit_answer()
    ├── BKT update                  (50ms, 同步 — 结果必须返回用户)
    ├── DB attempt write            (20ms, 同步 — 必须持久化)
    ├── event_bus.publish(AnswerSubmitted) (1ms, fire-and-forget)
    └── return feedback             总耗时 ~71ms

  ─── 以下异步消费 (不阻塞用户) ───

  [Analytics] on_answer_submitted()
    ├── behavior_analyzer.update()    (30ms)
    └── habit_formation.check()       (5ms)

  [Knowledge] on_answer_submitted()
    ├── 检查 mastery 是否跨级别变化
    └── 如果变化 → publish(KnowledgeStateUpdated)

  [Planning] on_answer_submitted()
    └── 更新学习计划进度

  [Conversation] on_answer_submitted()
    └── practice_integrator 写分支记忆

  [Achievements] on_answer_submitted()
    └── achievement_engine.check_all()
```

#### C2. 知识点升级 → 自动重排计划

```
[Knowledge] 检测 mastery: 发展中 → 已掌握
  → publish(KnowledgeStateUpdated)
    → [Planning] on_knowledge_updated()
      → 重生成学习计划（移除已掌握，加入下一级）
      → [Conversation] 推送消息: "你已掌握导数，建议开始学积分 🎉"
```

#### C3. 资料上传 → 异步索引

```
POST /api/material/upload
  → 保存文件 (同步)
  → publish(MaterialIndexed)
    → [Materials] on_indexed()
      → 后台解析 + 向量索引 (10-60s, 不阻塞上传响应)
      → 索引完成 → 通知前端刷新资料列表
```

### Phase 4D: API 层精简（1 天）

#### D1. 拆分 api/practice.py 上帝文件

```
改造前:
  api/practice.py (1025 行, 8 种职责)

改造后:
  application/use_cases/
    ├── submit_answer.py       (~80行 — 核心答题编排)
    ├── create_session.py      (~50行)
    ├── generate_questions.py  (~60行)
    ├── get_hint.py            (~30行)
    ├── get_behavior.py        (~40行)
    └── get_quality.py         (~40行)

  api/practice.py → (~80行 — 纯路由, 只做参数验证+调用 use_case)
```

#### D2. API 层不得直接访问 DB

```python
# 修复前: api/practice.py
db = get_db()
session = db.fetchone("SELECT * FROM practice_sessions WHERE ...")

# 修复后: application/use_cases/submit_answer.py
async def execute(self, req: SubmitAnswerRequest) -> SubmitResult:
    session = await self.session_repo.get(req.session_id)
    question = await self.question_repo.get(req.question_id)
    # ... 业务逻辑
```

### Phase 4E: 前端整并（2 天）

#### E1. 从 13 页 → 3 核心面板 + 1 设置

```
当前 13 页                             提案 3+1

/ (首页)         ┐
/analytics       │
/stats           ├→  📊 学习驾驶舱 /dashboard
/progress        │   Tab: 概览 | 学情深度 | 错题本 | 日历 | 成就 | 计划 | 质量
/calendar        │   入口: 侧栏第一位 (替代 /)
/achievements    │
/errors          │
/study           │
/quality         ┘

/learn           ┐
/graph           └→  💬 学习空间 /learn
                    主面板: 对话 (已有分区/分支/资料)
                    侧栏: 知识图谱 (可收起)
                    入口: 侧栏第二位

/practice        →  ✏️ 专注练习 /practice
                    保存专注模式
                    完成→自动跳回驾驶舱 (带结果)
                    入口: 侧栏第三位

/settings        →  ⚙️ 设置 /settings
                    入口: 侧栏底部
```

#### E2. 跨页上下文传递

```
驾驶舱 «薄弱点» → 点击 → /practice?skill=calculus&difficulty=medium
图谱节点 [未掌握] → 点击 → 选择 "练习" 或 "对话提问" → 带参数跳转
练习完成 → 结果页底部卡片:
  [📊 查看学情变化] → /dashboard?tab=analytics&highlight=calculus
  [📝 回顾错题]     → /dashboard?tab=errors&skill=calculus
  [💬 提问此题]     → /learn?action=chat&question_id=xxx
  [🎬 找视频讲解]   → 调起 media_search
```

#### E3. 驾驶舱统一入口

`/dashboard` 替代 `/` 成为新的首页：

```
┌─────────────────────────────────────────────────────┐
│  🔍 全站搜索                    👤 苹小果           │
├─────────────────────────────────────────────────────┤
│  [概览] [学情] [错题] [日历] [成就] [计划] [质量]     │
├─────────────────────────────────────────────────────┤
│                                                     │
│  ┌──────┬──────┬──────┬──────┐                      │
│  │ 128题 │ 72%  │ 5/38 │ 3🏆  │  ← 数据卡片          │
│  └──────┴──────┴──────┴──────┘                      │
│                                                     │
│  需要加强: calculus, algorithms, probability         │
│  → 针对性练习    → 找资料    → 问苹小果               │
│                                                     │
│  📊 今日摘要     🏆 最新成就     📅 热力图            │
│                                                     │
└─────────────────────────────────────────────────────┘
```

---

## 四、契约治理

### 4.1 REST API 版本化

```
/api/v1/practice/submit  →  FastAPI → OpenAPI 3.1 自动生成
向后兼容: 新增字段 default None, 不删除, 不重命名
废弃: Deprecation header + Sunset date
```

### 4.2 领域事件 Schema

每个事件定义 JSON Schema (draft 2020-12)，用于契约测试：

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "answer-submitted-v1",
  "type": "object",
  "required": ["event_id", "user_id", "session_id", "question_id", "is_correct"],
  "properties": {
    "event_id": {"type": "string", "format": "uuid"},
    "user_id": {"type": "string"},
    "skill_id": {"type": "string"},
    "is_correct": {"type": "boolean"},
    "p_known_before": {"type": "number", "minimum": 0, "maximum": 1}
  }
}
```

### 4.3 契约测试

每个 Protocol 实现 + 每个事件 Schema 都有独立契约测试，保证改变向下兼容。

---

## 五、稳定性全景

```
每个跨模块调用链:

  API Gateway
    │ x-trace-id 注入
    ▼
  UseCase 层
    │ @with_timeout(5s)
    ▼
  Domain Service
    │ CircuitBreaker(name="knowledge_service")
    ▼
  Infrastructure
    │ @with_retry(3, backoff=0.5)
    ▼
  外部服务 (DB / LLM / Redis)

日志格式:
  [trace_id=abc123] [span=submit_answer] [duration=71ms] OK
  [trace_id=abc123] [span=bkt_update] [duration=28ms] OK
  [trace_id=abc123] [span=event_publish] [event=AnswerSubmitted] OK
  [trace_id=def456] [span=achievement_check] [duration=45ms] OK (async)
```

---

## 六、实施路线（7 天）

| 阶段 | 天 | 内容 | 交付 |
|------|:--:|------|------|
| **4A 基础设施** | 1 | shared/protocols(8) + shared/events(10) + infra/event_bus + infra/resilience + infra/tracing | 零业务影响，纯新增文件 |
| **4B 消除循环** | 2 | BKT → Repository 模式 · conversation_llm → 依赖注入 · application/di.py · main.py 接入 DI | `api ⇄ services` + `core ⇄ services` 全部消除 |
| **4C 事件驱动** | 2 | submit_answer 拆分同步/异步 · AnswerSubmitted 事件串联 5 个消费者 · 资料索引异步化 | submit_answer 耗时减半，新模块零侵入接入 |
| **4D API 精简** | 1 | 拆分 api/practice.py 上帝文件 · API 层移除 DB 直连 · 8 个 use_case 文件 | api/practice.py 从 1025→80 行 |
| **4E 前端整并** | 1 | 13→3+1 面板 · /dashboard 统一驾驶舱 · 跨页上下文传递 · 侧栏更新 | 用户找得到所有功能 |
| **4F 契约测试** | 1 | Protocol 契约测试 · 事件 Schema 验证 · 熔断器集成测试 | 全量回归通过 |

---

## 七、前后对比

| 维度 | 改造前 | 改造后 |
|------|--------|--------|
| 循环依赖 | 2 对 (api⇄services, core⇄services) | **0** |
| 全局单例 | 35 个，零 DI | **1 个** (AppContainer) |
| API 直连 DB | 3 个文件 | **0** |
| api/practice.py 行数 | 1025 (8 职责) | **~80 (纯路由)** |
| submit_answer 耗时 | ~130ms | **~71ms** (核心路径) |
| 前端页面 | 13 (侧栏 7) | **4** (侧栏 4，全可见) |
| 跨页联动 | `<Link href="/practice">` | **带上下文参数跳转** |
| 新模块接入 | 修改现有代码 | **订阅事件，零侵入** |
| 契约 | 无 (传 dict) | **OpenAPI + JSON Schema + 契约测试** |
|| 稳定性 | 无超时/重试/熔断 | **3 层保护 + Trace ID** |

---

## 八、Phase 5 · 多模态生成 + Tool Calling（2026-05-19 完成）

### 8.1 架构扩展

Phase 4 分层架构零改动，Phase 5 以「新增文件 + 事件订阅」方式接入：

```
presentation (api/)
  └── multimodal.py (音频/图片静态文件服务)

application/ (di.py)
  └── 新增: multimedia_service 工厂 + AssistantReplied 事件订阅

domain/
  ├── conversation/service.py (新增: on_audio/image WS 推送)
  └── multimedia/service.py 🆕 (多媒体编排)

infra/
  ├── tts_client.py 🆕 (Edge TTS)
  └── svg_renderer.py 🆕 (matplotlib SVG)

shared/
  ├── events.py (新增: AssistantReplied/AudioSynthesized/ImageRendered)
  └── protocols/multimedia.py 🆕 (AudioSynthesizer/ImageRenderer)
```

### 8.2 事件流

```
AssistantReplied
  ├── MultimediaService.on_assistant_replied()
  │     ├── EdgeTTSClient.synthesize() → AudioSynthesized
  │     └── SVGRenderer.render_for_knowledge() → ImageRendered
  ├── ConversationService.on_audio_synthesized() → WS push AudioBlock
  └── ConversationService.on_image_rendered() → WS push ImageBlock
```

### 8.3 Tool Call Loop (新增能力)

```
用户消息 → LLM(含 tools: [search_media, generate_practice, ...])
  → LLM 自主决策调 tool → ToolExecutor 执行
    → 结果注入 messages → LLM 综合回复 → 流式
```

| 改动 | 文件 |
|------|------|
| `generate()` 增加 `tools`+`tool_choice` | `app/services/llm_service.py` |
| `_run_with_tools()` loop + `_stream_with_tools()` | `app/agents/base.py` |
| Tutor/Coach 配置 5 工具 | `app/agents/tutor.py` `app/agents/coach.py` |
| 5 个 handler 升级真实现 | `app/services/tool_executor.py` |
