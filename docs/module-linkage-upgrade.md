# 模块联动升级 — 架构重构设计

> 版本: v1.0  
> 最后更新: 2026-05-18  
> 状态: **设计阶段**，待逐步实施

---

## 一、现状诊断

### 1.1 依赖扫描结果

```
扫描范围: backend/app/ (50+ .py 文件)
分析方法: AST import 静态分析
```

**跨模块依赖矩阵**：

|  | agents | api | core | db | main | schemas | services |
|--|:--:|:--:|:--:|:--:|:--:|:--:|:--:|
| **agents** | — | · | · | · | · | 3 | 1 |
| **api** | · | — | 6 | 1 | · | 6 | **12** |
| **core** | 3 | · | — | · | · | 3 | **2** |
| **main** | · | 7 | 2 | 1 | — | · | · |
| **services** | · | **1** | **1** | · | · | 18 | — |

### 1.2 发现的架构缺陷

| # | 问题 | 严重度 | 涉及文件 |
|---|------|:--:|------|
| 1 | **`api ⇄ services` 循环** | 🔴 | conversation_llm → api.practice ← api.conversation |
| 2 | **`core ⇄ services` 循环** | 🔴 | knowledge_trace → storage ← shared_ks |
| 3 | **服务层倒挂 API 层** | 🔴 | conversation_llm.py: `from app.api.practice import router` |
| 4 | API 层直接操作 DB | 🟡 | practice.py: `db = get_db()` 直接 SQL |
| 5 | 全局单例满天飞 | 🟡 | bkt_engine, learner_engine, zpd_scheduler 等 10+ 全局变量 |
| 6 | 无依赖注入 | 🟡 | 所有模块通过 `import` 硬耦合 |
| 7 | 同步串行调用链过长 | 🟡 | submit → BKT → storage → conversation → analytics |
| 8 | 无契约治理 | 🟡 | 模块间传 dict，无版本化 Schema |
| 9 | 无超时/重试/熔断 | 🟡 | 跨模块调用无任何保护 |

### 1.3 循环依赖详解

```
🔴 循环 1: api ⇄ services
  api/conversation.py
    → services.conversation_llm   (正常: API 调用服务)
    → services.tree_ops
    → services.classifier
  
  services/conversation_llm.py
    → api.practice                (倒挂! 服务层不应知道 API 层)

🔴 循环 2: core ⇄ services
  core/knowledge_trace.py
    → services.storage            (核心依赖了基础设施)
  
  services/shared_ks.py
    → core.knowledge_trace        (服务依赖核心)
```

---

## 二、目标架构

### 2.1 分层模型

```
┌──────────────────────────────────────────────────────────────┐
│                   presentation (api/)                         │
│  职责: HTTP/WS 路由、请求验证、响应序列化                       │
│  依赖: application 层接口                                     │
│  不得: 直接访问 DB、直接调用 services、持有业务逻辑             │
├──────────────────────────────────────────────────────────────┤
│                   application (use_cases/)                    │
│  职责: 编排业务用例、发布领域事件、事务边界                      │
│  依赖: domain 接口 + event_bus                               │
│  不得: 直接访问 DB、实现具体算法                               │
├──────────────────────────────────────────────────────────────┤
│                   domain (modules/)                           │
│  职责: 纯业务逻辑（BKT/ZPD/习惯/选题）                          │
│  依赖: 只依赖 shared (schemas + protocols)                    │
│  不得: 直接访问 DB、调用外部服务、知道 presentation 层          │
├──────────────────────────────────────────────────────────────┤
│                   infrastructure (infra/)                     │
│  职责: DB 实现、LLM 客户端、文件存储、消息队列                  │
│  依赖: domain 定义的接口 (Protocol)                           │
│  不得: 包含业务逻辑                                           │
├──────────────────────────────────────────────────────────────┤
│                   shared (schemas/ + events/ + protocols/)    │
│  职责: Pydantic 模型、事件定义、Protocol 接口                   │
│  依赖: 零外部依赖（只依赖 Python 标准库 + pydantic）            │
└──────────────────────────────────────────────────────────────┘
```

### 2.2 依赖规则（强制）

```
✅ presentation → application  (通过接口)
✅ application → domain        (通过接口)
✅ domain → shared             (schemas + protocols)
✅ infrastructure → domain     (实现 domain 接口)

❌ domain → infrastructure     (违反依赖倒置)
❌ domain → presentation       (层次倒挂)
❌ presentation → domain       (绕过 application)
❌ presentation → infrastructure (绕过 application + domain)
❌ infrastructure → presentation (层次倒挂)
```

### 2.3 模块拆分（8 个业务域）

| 模块 | 目录 | 职责 | 暴露接口 |
|------|------|------|---------|
| **practice** | `domain/practice/` | 练习引擎(BKT+ZPD+出题+错题) | `PracticeService` Protocol |
| **conversation** | `domain/conversation/` | 对话引擎(树结构+LLM编排) | `ConversationService` Protocol |
| **planning** | `domain/planning/` | 学习规划(计划+目标+进度) | `PlanningService` Protocol |
| **materials** | `domain/materials/` | 资料管理(解析+索引+搜索) | `MaterialService` Protocol |
| **analytics** | `domain/analytics/` | 行为分析(streak+规律+疲劳) | `AnalyticsService` Protocol |
| **habits** | `domain/habits/` | 习惯养成(目标+微习惯+番茄钟) | `HabitService` Protocol |
| **media** | `domain/media/` | 媒体搜索(B站+百度+小红书) | `MediaService` Protocol |
| **knowledge** | `domain/knowledge/` | 知识图谱(节点+边+路径) | `KnowledgeGraphService` Protocol |

---

## 三、接口协议设计

### 3.1 Protocol 定义（每个模块一个）

```python
# shared/protocols/practice.py
from typing import Protocol, runtime_checkable
from shared.schemas.practice import (
    Question, PracticeSession, SubmitResult, KnowledgeState
)

@runtime_checkable
class PracticeService(Protocol):
    """练习模块对外契约 — 其他模块只能通过此接口调用"""

    async def generate_questions(
        self, subject: str, topic: str, level: str, count: int
    ) -> list[Question]: ...

    async def create_session(
        self, user_id: str, question_ids: list[str]
    ) -> PracticeSession: ...

    async def submit_answer(
        self, session_id: str, question_id: str, answer: str,
        time_spent: float = 0.0, hints_used: int = 0,
    ) -> SubmitResult: ...

    async def get_knowledge_state(
        self, user_id: str, skill_id: str
    ) -> KnowledgeState | None: ...

    async def get_errors(
        self, user_id: str, resolved: bool | None = None
    ) -> list[dict]: ...
```

```python
# shared/protocols/conversation.py
from typing import Protocol
from shared.schemas.conversation import Message, Branch, Partition

class ConversationService(Protocol):
    """对话模块对外契约"""

    async def send_message(
        self, partition_id: str, branch_id: str, content: str
    ) -> Message: ...

    async def create_branch(self, partition_id: str, name: str) -> Branch: ...

    async def inject_context(
        self, branch_id: str, context: dict
    ) -> None: ...
```

```python
# shared/protocols/planning.py
from typing import Protocol
from shared.schemas.learner import StudyPlan, DailyGoal

class PlanningService(Protocol):
    """学习规划模块对外契约"""

    async def generate_plan(self, user_id: str) -> StudyPlan: ...

    async def get_daily_goal(self, user_id: str) -> DailyGoal: ...

    async def mark_task_complete(
        self, user_id: str, task_id: str
    ) -> dict: ...
```

### 3.2 依赖注入容器

```python
# application/di.py
"""依赖注入容器 — 唯一的全局组装点"""

from domain.practice import PracticeServiceImpl
from domain.conversation import ConversationServiceImpl
from domain.planning import PlanningServiceImpl
from infra.database import PostgresPracticeRepo, PostgresSessionRepo
from infra.llm import DeepSeekClient
from infra.event_bus import InMemoryEventBus

class AppContainer:
    """应用容器 — 所有模块在此装配"""

    def __init__(self):
        # 基础设施
        self.event_bus = InMemoryEventBus()
        self.practice_repo = PostgresPracticeRepo()
        self.session_repo = PostgresSessionRepo()
        self.llm_client = DeepSeekClient()

        # 领域服务（注入接口实现）
        self.practice_service = PracticeServiceImpl(
            repo=self.practice_repo,
            session_repo=self.session_repo,
            event_bus=self.event_bus,
        )
        self.conversation_service = ConversationServiceImpl(
            llm=self.llm_client,
            event_bus=self.event_bus,
        )
        self.planning_service = PlanningServiceImpl(
            practice=self.practice_service,  # 通过 Protocol 依赖
            event_bus=self.event_bus,
        )

        # 事件订阅
        self._wire_events()

    def _wire_events(self):
        """注册领域事件处理器"""
        bus = self.event_bus
        # 答题 → 更新习惯养成
        bus.subscribe("practice.answer_submitted",
                       self.planning_service.on_answer_submitted)
        # 答题 → 更新知识图谱
        bus.subscribe("practice.answer_submitted",
                       self.knowledge_service.on_answer_submitted)
        # 知识状态更新 → 对话上下文
        bus.subscribe("knowledge.state_updated",
                       self.conversation_service.on_knowledge_updated)

# 全局单例（仅此一处）
container = AppContainer()
```

---

## 四、消除循环依赖

### 4.1 循环 1: api ⇄ services

**根因**: `services/conversation_llm.py` 第 82-89 行直接 import `api.practice` 来注入练习数据到 LLM 上下文。

**修复**: 依赖倒置

```python
# BEFORE (conversation_llm.py)
from app.api.practice import router  # ❌ 服务层倒挂 API 层
# ... 在 build_context 中直接调用 api.practice 的端点逻辑

# AFTER (domain/conversation/llm_engine.py)
from shared.protocols.practice import PracticeService  # ✅ 依赖抽象

class ConversationLLMEngine:
    def __init__(self, practice: PracticeService, llm: LLMClient):
        self._practice = practice  # 注入，不 import

    async def build_context(self, branch_id: str) -> dict:
        # 通过注入的接口获取练习上下文
        practice_summary = await self._practice.get_summary(branch_id)
        return {**base_context, "practice": practice_summary}
```

### 4.2 循环 2: core ⇄ services

**根因**: `core/knowledge_trace.py` 调用 `services/storage.py` 做持久化，而 `services/shared_ks.py` 又调用 `core/knowledge_trace.py` 的 BKT 算法。

**修复**: 接口倒置 + 仓储模式

```python
# BEFORE
# core/knowledge_trace.py
from app.services.storage import storage
state = storage.load(user_id)  # ❌ 核心算法依赖了基础设施

# AFTER
# shared/protocols/persistence.py
class KnowledgeStateRepository(Protocol):
    async def load(self, user_id: str, skill_id: str) -> dict | None: ...
    async def save(self, user_id: str, skill_id: str, state: dict) -> None: ...
    async def load_all(self, user_id: str) -> dict[str, dict]: ...

# domain/practice/bkt_engine.py
class BKTEngine:
    def __init__(self, repo: KnowledgeStateRepository):
        self._repo = repo  # ✅ 通过接口注入

    async def load_or_create(self, user_id: str, skill_id: str):
        data = await self._repo.load(user_id, skill_id)
        if data:
            return KnowledgeState(**data)
        return self.create_knowledge_state(skill_id)

# infra/database.py
class PostgresKnowledgeStateRepo(KnowledgeStateRepository):
    async def load(self, user_id, skill_id):
        return await self.db.fetchone(
            "SELECT * FROM knowledge_states WHERE user_id=%s AND skill_id=%s",
            (user_id, skill_id)
        )
```

### 4.3 结果: 零循环

```
修复前:
  core ⇄ services  (knowledge_trace ↔ storage)
  api  ⇄ services  (conversation ↔ practice)

修复后:
  core     → shared (Protocol)
  services → shared (Protocol)
  infra    → shared (Protocol)
  api      → shared (Protocol)
  ──────────────────────────
  所有循环消除，shared 层零外部依赖
```

---

## 五、事件驱动联动

### 5.1 领域事件定义

```python
# shared/events.py
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

@dataclass(frozen=True)
class DomainEvent:
    """领域事件基类"""
    event_id: str
    occurred_at: datetime = field(default_factory=datetime.now)

@dataclass(frozen=True)
class AnswerSubmitted(DomainEvent):
    """答题提交事件"""
    user_id: str
    session_id: str
    question_id: str
    skill_id: str
    is_correct: bool
    answer: str
    correct_answer: str
    time_spent: float
    p_known_before: float
    p_known_after: float

@dataclass(frozen=True)
class KnowledgeStateUpdated(DomainEvent):
    """知识状态变化事件"""
    user_id: str
    skill_id: str
    old_mastery: str
    new_mastery: str
    p_known_before: float
    p_known_after: float

@dataclass(frozen=True)
class SessionCompleted(DomainEvent):
    """练习会话完成事件"""
    user_id: str
    session_id: str
    total_questions: int
    correct_count: int
    accuracy: float
    duration_minutes: float

@dataclass(frozen=True)
class StudyPlanGenerated(DomainEvent):
    """学习计划生成事件"""
    user_id: str
    plan_items: int
    week_number: int

@dataclass(frozen=True)
class DailyGoalAchieved(DomainEvent):
    """每日目标达成事件"""
    user_id: str
    level: str
    streak_days: int
    questions_done: int
```

### 5.2 关键联动链路改造

#### 链路 A: 答题 → 全系统反应

```
改造前 (同步串行, ~500ms):
  submit_answer()
    → bkt_engine.update()          # 50ms
    → storage.save_state()         # 20ms
    → practice_integrator.write()  # 80ms
    → behavior.analyze()           # 30ms
    → habit.check_daily_goal()     # 5ms
    → return feedback              # 总计 ~185ms 阻塞

改造后 (事件驱动, ~100ms 返回):
  submit_answer()
    → bkt_engine.update()                  # 50ms (同步,需要结果)
    → event_bus.publish(AnswerSubmitted)   # 1ms (fire-and-forget)
    → return feedback                      # 总计 ~51ms 阻塞

  ─── 以下异步消费 (不阻塞用户响应) ───

  [Analytics] on_answer_submitted()
    → 更新 daily_trend                  # 30ms
    → 更新 hourly_heatmap               # 20ms

  [Habits] on_answer_submitted()
    → 检查每日目标                       # 5ms
    → 如果达成 → publish(DailyGoalAchieved)

  [Planning] on_answer_submitted()
    → 更新计划进度                       # 10ms

  [Conversation] on_answer_submitted()
    → 写入 branch 记忆                  # 80ms

  [Knowledge] on_answer_submitted()
    → 检查掌握度变化                     # 5ms
    → 如果升级 → publish(KnowledgeStateUpdated)
```

#### 链路 B: 知识升级 → 计划重调

```
改造前 (无此联动):
  (不存在自动化)

改造后:
  [Knowledge] 检测到 mastery: 发展中 → 已掌握
    → publish(KnowledgeStateUpdated)
      → [Planning] on_knowledge_updated()
        → 重新生成学习计划（移除已掌握知识点，加入下一级）
        → publish(StudyPlanGenerated)
          → [Conversation] on_plan_generated()
            → 向用户推送: "你已掌握导数，建议开始学积分 🎉"
```

#### 链路 C: 会话完成 → 多模块联动

```
[Practice] session 完成
  → publish(SessionCompleted)
    → [Analytics] 更新 total_sessions, avg_duration
    → [Habits] 更新 streak, 检查番茄钟建议
    → [Planning] 标记对应 plan task 完成
    → [Conversation] 写入会话摘要到对话记忆
    → [Knowledge] 检查是否需要触发间隔复习提醒
```

### 5.3 事件总线实现

```python
# infra/event_bus.py
import asyncio
import logging
from typing import Callable, Awaitable

EventHandler = Callable[[DomainEvent], Awaitable[None]]

class EventBus:
    """轻量级内存事件总线（后续可替换为 Redis Pub/Sub 或 Kafka）"""

    def __init__(self):
        self._handlers: dict[str, list[EventHandler]] = {}
        self._logger = logging.getLogger("event_bus")

    def subscribe(self, event_type: str, handler: EventHandler) -> None:
        self._handlers.setdefault(event_type, []).append(handler)

    async def publish(self, event: DomainEvent) -> None:
        event_type = type(event).__name__
        handlers = self._handlers.get(event_type, [])
        if not handlers:
            return

        # 异步并行执行所有 handler，不阻塞发布者
        tasks = []
        for handler in handlers:
            tasks.append(self._safe_invoke(handler, event))
        await asyncio.gather(*tasks, return_exceptions=True)

    async def _safe_invoke(self, handler: EventHandler, event: DomainEvent):
        try:
            await asyncio.wait_for(handler(event), timeout=5.0)
        except asyncio.TimeoutError:
            self._logger.error(f"Handler timeout for {type(event).__name__}")
        except Exception:
            self._logger.exception(f"Handler error for {type(event).__name__}")
```

### 5.4 同步 vs 异步决策表

| 场景 | 选型 | 理由 |
|------|:--:|------|
| 提交答案 → BKT更新 | **同步** | 需要 p_known 结果返回给用户 |
| BKT更新 → 保存知识状态 | **同步** | 需确认持久化成功 |
| 提交答案 → 更新仪表板统计 | **异步** | 不影响用户当前响应 |
| 提交答案 → 更新对话记忆 | **异步** | 写对话是副作用 |
| 提交答案 → 检查每日目标 | **异步** | 不阻塞答题流 |
| 知识升级 → 重生成学习计划 | **异步** | 计划生成可能耗时长 |
| 生成计划 → 通知对话系统 | **异步** | 推送通知类场景 |
| 资料上传 → 触发索引 | **异步** | 索引耗时长(10-60s) |
| 资料索引完成 → 出题 | **异步** | 出题依赖 LLM(5-15s) |

---

## 六、契约治理

### 6.1 REST API 契约 (OpenAPI)

所有 REST 端点通过 FastAPI 自动生成 OpenAPI 3.1 schema：

```yaml
# openapi.yaml (由 FastAPI 自动生成, 版本化)
openapi: 3.1.0
info:
  title: EduCompanion API
  version: 1.0.0
paths:
  /api/practice/submit:
    post:
      summary: 提交练习答案
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/SubmitAnswerRequest'
      responses:
        '200':
          description: 答题结果
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/SubmitResult'
```

**版本策略**：
- URL 路径版本: `/api/v1/practice/submit`
- 向后兼容: 新增字段用 optional，不删除已有字段
- 废弃通知: `Deprecation: true` + `Sunset: <date>` header

### 6.2 领域事件契约 (JSON Schema)

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://edu-companion/schemas/events/answer-submitted-v1.json",
  "title": "AnswerSubmitted",
  "type": "object",
  "required": ["event_id", "user_id", "session_id", "question_id", "is_correct"],
  "properties": {
    "event_id": {"type": "string", "format": "uuid"},
    "event_type": {"const": "AnswerSubmitted"},
    "event_version": {"const": "1"},
    "occurred_at": {"type": "string", "format": "date-time"},
    "user_id": {"type": "string"},
    "session_id": {"type": "string", "format": "uuid"},
    "question_id": {"type": "string", "format": "uuid"},
    "skill_id": {"type": "string"},
    "is_correct": {"type": "boolean"},
    "answer": {"type": "string"},
    "correct_answer": {"type": "string"},
    "time_spent": {"type": "number", "minimum": 0},
    "p_known_before": {"type": "number", "minimum": 0, "maximum": 1},
    "p_known_after": {"type": "number", "minimum": 0, "maximum": 1}
  }
}
```

### 6.3 契约测试

```python
# tests/contracts/test_practice_contract.py
import pytest
from shared.protocols.practice import PracticeService

class TestPracticeContract:
    """PracticeService Protocol 契约测试 — 所有实现必须通过"""

    @pytest.fixture
    def service(self) -> PracticeService:
        from domain.practice import PracticeServiceImpl
        from infra.database import PostgresPracticeRepo
        return PracticeServiceImpl(repo=PostgresPracticeRepo())

    async def test_submit_answer_returns_correct_shape(self, service):
        result = await service.submit_answer(
            session_id="test-sid",
            question_id="test-qid",
            answer="A",
        )
        assert "is_correct" in result
        assert "feedback" in result
        assert "p_known_after" in result

class TestAnswerSubmittedEvent:
    """事件契约测试"""

    def test_event_schema_valid(self):
        event = AnswerSubmitted(
            event_id="evt-001",
            user_id="u1", session_id="s1",
            question_id="q1", skill_id="math",
            is_correct=True,
            answer="A", correct_answer="A",
            time_spent=15.0,
            p_known_before=0.5, p_known_after=0.7,
        )
        data = event.to_dict()
        # JSON Schema 验证
        validate(data, ANSWER_SUBMITTED_SCHEMA)
```

---

## 七、稳定性机制

### 7.1 超时与重试

```python
# infra/resilience.py
import asyncio
from functools import wraps

def with_timeout(seconds: float = 5.0):
    """同步跨模块调用超时保护"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                return await asyncio.wait_for(
                    func(*args, **kwargs), timeout=seconds
                )
            except asyncio.TimeoutError:
                raise ServiceTimeoutError(
                    f"{func.__name__} timed out after {seconds}s"
                )
        return wrapper
    return decorator

def with_retry(max_attempts: int = 3, backoff: float = 0.5):
    """指数退避重试"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            last_error = None
            for attempt in range(max_attempts):
                try:
                    return await func(*args, **kwargs)
                except RetryableError as e:
                    last_error = e
                    wait = backoff * (2 ** attempt)
                    await asyncio.sleep(wait)
            raise last_error
        return wrapper
    return decorator
```

### 7.2 熔断器

```python
# infra/circuit_breaker.py
from enum import Enum
from datetime import datetime, timedelta

class CircuitState(Enum):
    CLOSED = "closed"          # 正常
    OPEN = "open"              # 熔断
    HALF_OPEN = "half_open"    # 探测

class CircuitBreaker:
    """熔断器 — 保护下游服务"""

    def __init__(self, name: str, failure_threshold: int = 5,
                 recovery_timeout: float = 30.0):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failure_count = 0
        self.last_failure_time: datetime | None = None
        self.state = CircuitState.CLOSED

    async def call(self, func, *args, **kwargs):
        if self.state == CircuitState.OPEN:
            if self._should_attempt_recovery():
                self.state = CircuitState.HALF_OPEN
            else:
                raise CircuitBreakerOpenError(self.name)

        try:
            result = await func(*args, **kwargs)
            if self.state == CircuitState.HALF_OPEN:
                self.state = CircuitState.CLOSED
                self.failure_count = 0
            return result
        except Exception as e:
            self.failure_count += 1
            self.last_failure_time = datetime.now()
            if self.failure_count >= self.failure_threshold:
                self.state = CircuitState.OPEN
            raise e

    def _should_attempt_recovery(self) -> bool:
        if self.last_failure_time is None:
            return True
        elapsed = (datetime.now() - self.last_failure_time).total_seconds()
        return elapsed >= self.recovery_timeout

# 使用示例
llm_circuit = CircuitBreaker("llm_service", failure_threshold=3)
result = await llm_circuit.call(llm.generate, prompt="...")
```

### 7.3 全链路追踪

```python
# infra/tracing.py
import uuid
from contextvars import ContextVar
from datetime import datetime

trace_id: ContextVar[str] = ContextVar("trace_id", default="")

class TraceContext:
    """全链路追踪上下文"""

    @staticmethod
    def new() -> str:
        tid = str(uuid.uuid4())[:8]
        trace_id.set(tid)
        return tid

    @staticmethod
    def current() -> str:
        return trace_id.get()

    @staticmethod
    def propagate() -> dict:
        return {"x-trace-id": trace_id.get()}

# middleware.py — 自动注入每个 HTTP 请求
@app.middleware("http")
async def tracing_middleware(request, call_next):
    tid = request.headers.get("x-trace-id", TraceContext.new())
    trace_id.set(tid)
    response = await call_next(request)
    response.headers["x-trace-id"] = tid
    return response
```

### 7.4 稳定性全景

```
每个跨模块调用链:

  API Gateway
    │ x-trace-id 注入
    ▼
  UseCase 层
    │ @with_timeout(5s)
    ▼
  Domain Service
    │ CircuitBreaker
    ▼
  Infrastructure
    │ @with_retry(3, backoff=0.5)
    ▼
  外部服务 (DB / LLM / Redis)

日志格式:
  [trace_id=abc123] [span=submit_answer] [duration=52ms] OK
  [trace_id=abc123] [span=bkt_update] [duration=28ms] OK
  [trace_id=abc123] [span=event_publish] [event=AnswerSubmitted] OK
  [trace_id=def456] [span=llm_generate] [duration=3200ms] TIMEOUT → RETRY_1
```

---

## 八、实施路线

### Phase 1: 契约先行（1天）

| 步骤 | 内容 |
|------|------|
| 1.1 | 创建 `shared/protocols/` — 8 个 Protocol 定义 |
| 1.2 | 创建 `shared/events.py` — 10 个领域事件定义 |
| 1.3 | 创建 `infra/event_bus.py` — 异步事件总线 |
| 1.4 | 创建 `infra/resilience.py` — 超时/重试/熔断 |
| 1.5 | 创建 `infra/tracing.py` — Trace ID 传播 |

### Phase 2: 核心模块改造（3天）

| 步骤 | 内容 |
|------|------|
| 2.1 | 重构 `practice` 为 `domain/practice/` — BKT 接口化 |
| 2.2 | 重构 `conversation` — 解耦 api.practice 依赖 |
| 2.3 | 重构 KnowledgeState 持久化为 Repository 模式 |
| 2.4 | `submit_answer` 改为事件驱动（不阻塞返回） |

### Phase 3: 联动改造（2天）

| 步骤 | 内容 |
|------|------|
| 3.1 | 会话完成 → 事件驱动 analytics + habits + conversation |
| 3.2 | 知识升级 → 事件驱动 planning 重生成 |
| 3.3 | 资料上传 → 异步索引（事件驱动） |
| 3.4 | 每日目标达成 → 事件通知对话系统推送 |

### Phase 4: 契约测试 + 稳定化（1天）

| 步骤 | 内容 |
|------|------|
| 4.1 | 每个 Protocol 实现契约测试 |
| 4.2 | 事件 Schema 契约测试 |
| 4.3 | 熔断器集成测试 |
| 4.4 | 全链路追踪验证 |

---

## 九、前后对比

| 维度 | 改造前 | 改造后 |
|------|--------|--------|
| 循环依赖 | 2 个 (api⇄services, core⇄services) | **0** |
| 模块耦合 | 直接 import 具体实现 | **通过 Protocol 依赖抽象** |
| 联动方式 | 同步串行调用链 (5步) | **事件驱动并行 (1发布+N消费)** |
| 用户响应延迟 | ~185ms (含所有副作用) | **~51ms (仅核心路径)** |
| 契约 | 无 (传 dict) | **OpenAPI + JSON Schema + 契约测试** |
| 稳定性 | 无超时/重试/熔断 | **3层保护 + Trace ID 全链路** |
| 新模块接入 | 修改现有代码 | **订阅事件即可，零侵入** |
| 可测试性 | 需要真实 DB/LLM | **接口可 Mock，独立测试** |

---

## 附录: 文件结构

```
backend/
├── shared/
│   ├── protocols/
│   │   ├── __init__.py
│   │   ├── practice.py       # PracticeService Protocol
│   │   ├── conversation.py   # ConversationService Protocol
│   │   ├── planning.py       # PlanningService Protocol
│   │   ├── materials.py      # MaterialService Protocol
│   │   ├── analytics.py      # AnalyticsService Protocol
│   │   ├── habits.py         # HabitService Protocol
│   │   ├── media.py          # MediaService Protocol
│   │   ├── knowledge.py      # KnowledgeGraphService Protocol
│   │   └── persistence.py    # Repository Protocols
│   ├── events.py             # 所有领域事件定义
│   └── schemas/              # (已有) Pydantic 模型
│       ├── practice.py
│       ├── conversation.py
│       ├── learner.py
│       └── chat.py
│
├── domain/
│   ├── practice/
│   │   ├── __init__.py        # 导出 PracticeServiceImpl
│   │   ├── bkt_engine.py      # BKT 算法（纯逻辑）
│   │   ├── zpd_scheduler.py   # ZPD 调度
│   │   ├── question_gen.py    # 题目生成
│   │   └── error_book.py      # 错题管理
│   ├── conversation/
│   │   ├── __init__.py
│   │   ├── llm_engine.py      # LLM 编排
│   │   ├── tree_ops.py        # 树操作
│   │   └── classifier.py      # 分类
│   ├── planning/
│   │   ├── __init__.py
│   │   ├── plan_generator.py
│   │   └── goal_tracker.py
│   ├── analytics/
│   │   ├── __init__.py
│   │   ├── behavior_analyzer.py
│   │   └── stats_engine.py
│   ├── habits/
│   │   ├── __init__.py
│   │   └── habit_engine.py
│   ├── materials/
│   ├── media/
│   └── knowledge/
│
├── application/
│   ├── di.py                  # 依赖注入容器
│   └── use_cases/
│       ├── submit_answer.py   # 答题用例
│       ├── create_session.py
│       └── generate_plan.py
│
├── infra/
│   ├── database.py            # PostgreSQL 实现
│   ├── storage.py             # JSON 文件存储
│   ├── llm.py                 # LiteLLM 客户端
│   ├── event_bus.py           # 内存事件总线
│   ├── circuit_breaker.py     # 熔断器
│   ├── resilience.py          # 超时/重试
│   └── tracing.py             # 全链路追踪
│
├── api/                       # (保持) FastAPI 路由
│   ├── practice.py            # 精简为薄层
│   ├── conversation.py
│   ├── study.py
│   └── ...
│
└── tests/
    └── contracts/
        ├── test_practice.py
        ├── test_events.py
        └── test_resilience.py
```
