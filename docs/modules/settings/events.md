# Settings 模块 — 事件清单

> **任务**: Task #84 — 设置模块全面优化  
> **创建日期**: 2026-07-04

## 用户域事件（Task #84 新增）

### 1. UserPreferencesUpdated

**触发场景**: 用户级偏好统一存储变更（LLM / UI / Learning）

**Schema**:
```python
@dataclass(frozen=True)
class UserPreferencesUpdated(DomainEvent):
    user_id: str = ""
    changed_keys: list[str] = field(default_factory=list)
    source: Literal["api", "frontend_sync", "migration"] = "api"
    updated_at: datetime = field(default_factory=_now)
```

**changed_keys 取值**:
- `llm_config` — `PUT/DELETE /api/settings/llm`
- `llm_behavior` — `PUT /api/settings/llm-behavior`
- `ui` — `PUT /api/settings/ui`
- `learning` — `PUT /api/settings/learning`

**监听建议**:
- 秘书系统 — 重新评估对用户的响应策略
- 兴趣推送 — 重新校准推送频率
- 数据分析 — 记录用户偏好变更轨迹
- 跨设备同步 — 触发其他设备的设置刷新

### 2. UserProfileUpdated

**触发场景**: 用户资料（昵称/邮箱/密码/状态）变更

**Schema**:
```python
@dataclass(frozen=True)
class UserProfileUpdated(DomainEvent):
    user_id: str = ""
    changed_fields: list[str] = field(default_factory=list)
    change_type: Literal["profile", "password", "deactivate", "logout_others", "avatar"] = "profile"
    updated_at: datetime = field(default_factory=_now)
```

**change_type 取值**:
- `profile` — `PATCH /api/auth/me`（display_name / email）
- `password` — `POST /api/auth/change-password`
- `deactivate` — `POST /api/auth/deactivate`（账号注销）
- `logout_others` — `POST /api/auth/me/logout-other-devices`
- `avatar` — 预留（头像上传）

**监听建议**:
- 审计模块 — 记录敏感操作
- 安全模块 — 检测异常密码修改
- 通知模块 — 发送"密码已修改"邮件
- 设备管理 — 失效其他设备 token

## 事件发布点（端到端追踪）

| 事件 | 发布位置 | 端点 |
|------|----------|------|
| UserPreferencesUpdated(llm_config) | `settings_api.py:149` | PUT /api/settings/llm |
| UserPreferencesUpdated(llm_config, reset) | `settings_api.py:159` | DELETE /api/settings/llm |
| UserPreferencesUpdated(llm_behavior) | `settings_api.py:185` | PUT /api/settings/llm-behavior |
| UserPreferencesUpdated(ui) | `settings_api.py:211` | PUT /api/settings/ui |
| UserPreferencesUpdated(learning) | `settings_api.py:237` | PUT /api/settings/learning |
| UserProfileUpdated(profile) | `api.py:157` | PATCH /api/auth/me |
| UserProfileUpdated(password) | `api.py:181` | POST /api/auth/change-password |
| UserProfileUpdated(logout_others) | `api.py:252` | POST /api/auth/me/logout-other-devices |
| UserProfileUpdated(deactivate) | `api.py:275` | POST /api/auth/deactivate |

## 事件订阅建议

### 短期（v1.0）
- 暂无强制订阅方
- 事件作为系统可观测性的一部分，被审计/日志模块统一记录

### 中期（v1.x）
- 秘书系统订阅 UserPreferencesUpdated，根据学习偏好调整响应策略
- 跨设备同步订阅 UserPreferencesUpdated，触发其他设备的偏好拉取

### 长期（v2.0）
- 安全告警订阅 UserProfileUpdated(password)，异地密码修改触发二次验证
- 推荐系统订阅 UserPreferencesUpdated(ui)，根据主题偏好推荐合适的 UI
