# 数据规格：秘书系统

> 诊断引擎 + 提案生成器 + 模块注册表 — 基于 CognitiveNode 状态和事件数据自动生成学习建议。
>
> 源码：[backend/app/domain/secretary/](../../backend/app/domain/secretary/)

---

## 核心架构

```
事件总线 → 事件消费者(SecretaryEventHandler)
               ↓
         诊断引擎(DiagnosisEngine) + 上下文引擎(ContextEngine) + 策略引擎(PolicyEngine)
               ↓
         提案生成器(ProposalGenerator) → 提案操作处理器(ProposalActionHandler)
               ↓
         模块注册表(SecretaryModuleRegistry) → 内置模块
               ↓
         前端展示
```

## 提案 (Proposal)

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | str | 全局唯一（12位 UUID） |
| `emoji` | str | 图标 |
| `title` | str | 提案标题 |
| `description` | str | 提案描述 |
| `action_type` | str | review / practice / rest / explore / exam_prep |
| `payload` | dict | 操作参数 |
| `priority` | int | 优先级 1-5（默认 3） |
| `generated_by` | str | 来源模块名 |
| `overrideable` | bool | 是否可覆盖（默认 true） |
| `meta_reflection_prompt` | str\|null | 元反思提示 |
| `insight_source` | str\|null | 关联的分析函数名 |
| `created_at` | float | 创建时间戳 |
| `expires_at` | float\|null | 过期时间戳 |

## 模块扩展契约

扩展模块必须继承 `SecretaryModule` 基类：

```python
class SecretaryModule(ABC):
    @property
    @abstractmethod
    def meta(self) -> ModuleMeta:
        """模块元数据"""
    
    async def on_activate(self) -> None:
        """模块激活时调用"""
    
    async def on_deactivate(self) -> None:
        """模块停用时调用"""
    
    @abstractmethod
    async def run_check(self, user_id: str, ctx: SessionContext | None = None) -> list[Proposal]:
        """执行一次模块检查，返回提案列表"""
    
    async def health_check(self) -> str:
        """模块健康状态"""
```

### ModuleMeta

| 字段 | 类型 | 说明 |
|------|------|------|
| `name` | str | 唯一标识名（如 `review_reminder`） |
| `display_name` | str | 显示名 |
| `emoji` | str | 图标 |
| `description` | str | 简短说明 |
| `default_enabled` | bool | 默认是否启用 |
| `run_interval_seconds` | int | 检查间隔（默认 600） |
| `version` | str | 版本号 |
| `author` | str | 作者 |

## 内置模块

| 模块 | name | 功能 | 检查条件 |
|------|------|------|----------|
| 复习提醒 | `review_reminder` | 检测遗忘曲线低谷节点 | 遗忘曲线 > 0.7 且 7天未复习 |
| 疲劳管理 | `fatigue_manager` | 检测疲劳风险 + 静默时段 | 连续学习 > 2h / 静默时段 / 高认知负荷 |
| 每日简报 | `daily_brief` | 每日学习摘要 | 每日触发 |

## 用户偏好 (SecretaryPrefs)

| 字段 | 类型 | 说明 |
|------|------|------|
| `enabled_extensions` | list[str] | 启用的模块列表（默认：review_reminder, fatigue_manager, daily_brief） |
| `quiet_hours_start` | str | 静默时段开始（默认 "22:00"） |
| `quiet_hours_end` | str | 静默时段结束（默认 "08:00"） |
| `max_proactive_per_day` | int | 每日最大主动推送数（默认 5） |
| `custom_rules` | list[dict] | 自定义规则 |
| `privacy_calendar_enabled` | bool | 日历隐私（默认 false） |
| `privacy_device_activity_enabled` | bool | 设备活动隐私（默认 false） |

## 诊断引擎 (DiagnosisEngine)

分析函数列表：

| 函数 | 产出 | 说明 |
|------|------|------|
| `find_weak_points` | WeakPoint[] | 薄弱点检测 |
| `predict_fatigue_risk` | FatigueRisk | 疲劳风险预测 |
| `analyze_learning_trend` | Trend | 学习趋势分析 |

## 事件消费列表

| 事件 | 消费者 | 产出 |
|------|--------|------|
| `AnswerSubmitted` | 疲劳管理 / 薄弱点发现 | 疲劳提醒 / 薄弱点提案 |
| `SessionCompleted` | 复习提醒 | 复习计划 |
| `CognitiveNodeUpdated` | 学习规划 | 路径建议 |
| `NodeCreated` | 波纹扩展 | 知识图谱扩展提案 |
| `ProposalAccepted` | 提案操作处理器 | 执行图谱操作 |

## 核心规则

1. 秘书系统通过事件总线异步消费领域事件，不阻塞主流程
2. 提案通过 `ProposalStore` 持久化，前端轮询获取
3. 模块注册表全局单例，支持动态启用/禁用
4. 疲劳检测使用 `predict_fatigue_risk()` 函数，结合 CognitiveNode 的 `cognitive_load` 和 `trend`
