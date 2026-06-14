# ADR 0004: 通用事件记录表与认知操作注册中心

用通用 `events` 表取代 `cognitive_events` 表, 配合 `CognitiveOperationRegistry` 实现认知节点更新的可追溯、可复用。

## Status

Accepted

## Context

原 `cognitive_events` 表同时作为事件队列和历史记录, 结构过窄:
- 单 `node_id` 无法表达批量影响
- 无来源追溯, 不知道谁触发了更新
- 无操作明细, payload 散落各处

同时, 对话系统重构要求 TreeNode 与 CognitiveNode 解耦, 对话对认知的影响需要事件化记录, 并显示来源和理由。

events 表独立于 cognitive 模块, 由 EventsRepository 统一存取, 供所有模块共用。

## Decision

### 1. `events` 表 — 通用事件记录

```sql
CREATE TABLE events (
    id           TEXT PRIMARY KEY,
    user_id      TEXT NOT NULL,
    event_type   TEXT NOT NULL,           -- "cognitive_update" | 未来扩展
    source_type  TEXT NOT NULL,           -- "conversation" | "practice" | "secretary" | "manual" | "system"
    source_id    TEXT NOT NULL DEFAULT '',
    status       TEXT NOT NULL DEFAULT 'done',  -- pending | processing | done | failed
    status_msg   TEXT NOT NULL DEFAULT '',
    payload      JSONB NOT NULL DEFAULT '{}',
    created_at   TIMESTAMPTZ DEFAULT NOW(),
    updated_ats  TIMESTAMPTZ[] DEFAULT ARRAY[NOW()]  -- 状态变更时间戳链
);
```

- 通用字段在最顶层, 所有 event_type 共用
- 类型特有数据全在 `payload` (如 cognitive_update 的 reason/target_ids/operations)
- 默认写入即 `status='done'`; `status` 保留给未来异步模块
- 取代旧 `cognitive_events` 表

### 2. `EventsRepository` — 独立存储层

独立于 cognitive 模块的存储层 (`app/db/events_repository.py`)。提供:
- `insert(event)` / `get(event_id)` / `query(user_id, filters)` / `mark_done(event_id, operations_summary)`
- 多个模块 (cognitive/secretary/practice) 共用此仓库

### 3. `CognitiveOperationRegistry` — 认知操作注册中心

类 ToolRepository 模式, 应用启动时自动发现:

```python
@dataclass
class CognitiveOperation:
    name: str
    description: str
    params_schema: dict
    handler: Callable

class CognitiveOperationRegistry:
    def __init__(self):
        self._operations: dict[str, CognitiveOperation] = {}

    def register(self, name, description, params_schema=None):
        """装饰器注册"""
    def execute(self, name, **params) -> Any:
        """按名派发, 返回操作结果"""
    def list_operations(self) -> list[dict]:
        """列出所有可用操作"""
    def discover(self, source_dirs: list[str]):
        """应用启动时调用一次, 扫描目录下的 *\_operations.py"""
```

- 应用启动时 (main.py/DI 初始化) 调用 `discover()` 扫描 `cognitive/operations/`
- 运行时不变, 无热加载
- 操作名即方法名, 自由字符串但必须对应已注册方法
- 操作执行结果 → 由调用方写入 events.payload.operations[].result_summary

### 4. `cognitive_update` 事件 payload 结构

```json
{
    "reason": "用户在对话#conv_123中讨论了微积分基本定理",
    "target_ids": ["node_abc", "node_def"],
    "target_path": "数据科学.数据分析.统计学",
    "operations": [
        {
            "subsystem": "belief",
            "method": "update_belief_from_evidence",
            "params": {"success": true, "weight": 0.3},
            "result_summary": "proficiency_mean: 0.50→0.58"
        }
    ]
}
```

## Consequences

- **正面**: 事件完全可追溯 — 知道谁在什么时候因为什么更新了哪些节点的哪些子系统
- **正面**: 通用表 + EventsRepository 设计, 其他模块可直接复用
- **正面**: Operation 注册中心解耦调用方与实现方, 外部模块通过名称引用
- **正面**: 结果回写 (result_summary) 使事件表成为完整的审计链路
- **负面**: 旧 `cognitive_events` 表数据丢弃 (用户确认清库重建)
- **负面**: 增加一层间接调用 (name→handler), 但仅在事件写入路径, 非热点

### 实现文件清单

- 新建: `app/db/events_schema.sql` (events 表 DDL)
- 新建: `app/db/events_repository.py` (Event 模型 + EventsRepository)
- 新建: `app/cognitive/operation_registry.py` (CognitiveOperationRegistry)
- 新建: `app/cognitive/operations/__init__.py`
- 新建: `app/cognitive/operations/belief_operations.py`
- 新建: `app/cognitive/operations/trend_operations.py`
- 修改: `app/db/database.py` (迁移: 加入 events_schema.sql)
- 修改: `app/cognitive/models.py` (仅删除 CognitiveEvent, 不新增任何模型)
- 修改: `app/cognitive/storage.py` (删除旧 events CRUD 函数)
- 修改: `app/cognitive/pg_repository.py` (删除旧 events 代理方法)
- 修改: `app/cognitive/events.py` (重写: 处理器内调 CognitiveOperationRegistry)
- 修改: `app/cognitive/__init__.py` (导出 Registry)
- 修改: `app/db/cognitive_schema.sql` (删除 cognitive_events 建表语句)

## Considered Options

- **旧表加字段改造**: `cognitive_events` 加 source/target 字段。否决 — 表语义混杂 (队列+记录), 且不是通用设计。
- **无注册中心, 直接调函数**: 外部模块直接 import cognitive 函数。否决 — 破坏模块边界, 无法在 events 表中按名记录操作。
- **用现有 ToolRepository 注册**: 认知操作被设计为内部系统操作而非 LLM 工具, 语义不匹配, 故独立注册中心。
