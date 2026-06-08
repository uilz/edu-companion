# 秘书系统 · 扩展模块

> 内置的秘书扩展模块列表及开发自定义模块的接口规范。
>
> 源码：[backend/app/domain/secretary/engines/](../../../backend/app/domain/secretary/engines/)

---

## 模块基类

所有扩展模块必须继承 `SecretaryModule` 基类：

```python
class SecretaryModule(ABC):
    @property
    @abstractmethod
    def meta(self) -> ModuleMeta:
        """模块元数据"""

    async def on_activate(self) -> None:
        """模块激活时调用（可选覆写）"""

    async def on_deactivate(self) -> None:
        """模块停用时调用（可选覆写）"""

    @abstractmethod
    async def run_check(self, user_id: str, ctx: SessionContext | None = None) -> list[Proposal]:
        """执行一次模块检查，返回提案列表（空列表=无事项）"""

    async def health_check(self) -> str:
        """模块健康状态（可选覆写）"""
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

### 1. 复习提醒模块

| 属性 | 值 |
|------|-----|
| name | `review_reminder` |
| 检查间隔 | 600 秒 |
| 触发条件 | 遗忘曲线 > 0.7 且 7 天未复习 |
| 产出 | 复习计划提案 |
| 源码 | `builtin_review_reminder.py` |

### 2. 疲劳管理模块

| 属性 | 值 |
|------|-----|
| name | `fatigue_manager` |
| 检查间隔 | 600 秒 |
| 触发条件 | 静默时段 / 高认知负荷 / 长时间会话 / predict_fatigue_risk 预测 |
| 产出 | 休息提醒提案 |
| 源码 | `builtin_fatigue_manager.py` |

疲劳管理模块有四种洞察来源：
- `fatigue_quiet_hours`：静默时段检测
- `fatigue_high_load`：高认知负荷
- `fatigue_long_session`：长时间会话
- `predict_fatigue_risk`：基于 CognitiveNode 的疲劳风险预测

### 3. 每日简报模块

| 属性 | 值 |
|------|-----|
| name | `daily_brief` |
| 检查间隔 | 每日触发 |
| 产出 | 每日学习摘要 |

## 注册表

`SecretaryModuleRegistry` 是全局单例，管理所有模块的注册、启用/禁用和运行：

```python
class SecretaryModuleRegistry:
    def register(self, module: SecretaryModule) -> None
    def unregister(self, name: str) -> None
    def apply_prefs(self, enabled_extensions: list[str]) -> None
    async def run_all(self, user_id: str, ctx: SessionContext | None = None) -> list[Proposal]
```

### 注册方式

```python
# 内置模块自动注册
registry = SecretaryModuleRegistry()
registry.register(ReviewReminderModule())
registry.register(FatigueManagerModule())

# 应用用户偏好
registry.apply_prefs(["review_reminder", "fatigue_manager", "daily_brief"])
```

## 提案优先级

| 优先级 | 含义 | 展示方式 |
|--------|------|----------|
| 1 | 最高优先 | 弹窗通知 |
| 2 | 高优先 | 秘书面板置顶 |
| 3 | 常规（默认） | 列表展示 |
| 4 | 低优先 | 折叠区域 |
| 5 | 最低 | 仅存档 |
