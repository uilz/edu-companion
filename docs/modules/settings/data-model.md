# Task #84 — Settings 模块 — 数据模型

> **任务**: Task #84 — 设置模块全面优化  
> **创建日期**: 2026-07-04

## 1. 核心表结构

### 1.1 `users` (用户表)

| 字段 | 类型 | 说明 |
|------|------|------|
| id | TEXT PRIMARY KEY | UUID |
| username | TEXT NOT NULL UNIQUE | 用户名 |
| email | TEXT | 邮箱 |
| password_hash | TEXT NOT NULL | bcrypt 加密密码 |
| display_name | TEXT | 显示名称 |
| role | TEXT DEFAULT 'user' | user / admin / super_admin |
| is_active | BOOLEAN DEFAULT TRUE | 是否激活 |
| token_version | INTEGER DEFAULT 0 | 用于踢出其他设备 |
| last_login | TIMESTAMP | 最后登录时间 |
| last_active_at | TIMESTAMP | 最后活跃时间（5 分钟节流） |
| created_at | TIMESTAMP NOT NULL DEFAULT NOW() | 创建时间 |
| updated_at | TIMESTAMP NOT NULL DEFAULT NOW() | 更新时间 |

### 1.2 `user_settings` (统一偏好表 — D16)

| 字段 | 类型 | 说明 |
|------|------|------|
| user_id | TEXT PRIMARY KEY | 关联 users.id |
| settings_jsonb | JSONB NOT NULL DEFAULT '{}' | 偏好字典 |
| updated_at | TIMESTAMPTZ DEFAULT NOW() | 更新时间 |

#### 1.2.1 顶层 Key 命名空间（Task #84 扩展）

```json
{
  "llm_config": {
    "api_base": "https://api.openai.com/v1",
    "api_key_encrypted": "gAAAAA...",  // Fernet 加密
    "model_name": "gpt-4o",
    "is_active": true
  },
  "llm_behavior": {
    "temperature": 0.7,
    "max_tokens": 2048,
    "system_prompt": ""
  },
  "ui": {
    "theme": "dark",
    "style": "professional"
  },
  "learning": {
    "socratic_mode": false,
    "socratic_follow_up_mode": false,
    "auto_scroll_on_load": true
  },
  "notification": {  // 预留
    "browser_push": true,
    "email_digest": false
  }
}
```

### 1.3 `login_events` (登录事件表)

| 字段 | 类型 | 说明 |
|------|------|------|
| id | SERIAL PRIMARY KEY | 自增 ID |
| user_id | TEXT NOT NULL | 关联 users.id |
| ip_address | TEXT | 客户端 IP |
| user_agent | TEXT | 浏览器 UA |
| country / region / city | TEXT | IP 归属地 |
| device_type | TEXT | desktop / mobile / tablet |
| browser / os | TEXT | 浏览器/操作系统 |
| is_current | BOOLEAN DEFAULT FALSE | 是否当前会话 |
| created_at | TIMESTAMP NOT NULL DEFAULT NOW() | 登录时间 |

## 2. 实体关系

```
┌──────────────┐  1:1   ┌─────────────────┐
│     users    │───────→│  user_settings  │
│  (id PK)     │        │  (user_id PK)   │
└──────┬───────┘        └─────────────────┘
       │ 1:N
       ↓
┌──────────────┐
│ login_events │
│ (id PK)      │
└──────────────┘
```

## 3. Pydantic 模型

### 3.1 请求模型

```python
class LlmConfigRequest(BaseModel):
    api_base: str = Field(default="", max_length=512)
    api_key: str = Field(default="", max_length=512)
    model_name: str = Field(default="", max_length=128)

class LlmBehaviorRequest(BaseModel):
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)
    max_tokens: int | None = Field(default=None, ge=64, le=8192)
    system_prompt: str | None = Field(default=None, max_length=4000)

class UiPrefsRequest(BaseModel):
    theme: str | None = Field(default=None)  # Pydantic validator: dark/light
    style: str | None = Field(default=None)  # Pydantic validator: 5 styles

class LearningPrefsRequest(BaseModel):
    socratic_mode: bool | None = None
    socratic_follow_up_mode: bool | None = None
    auto_scroll_on_load: bool | None = None

class UpdateProfileRequest(BaseModel):
    display_name: str | None = None
    email: str | None = None

class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str = Field(min_length=6, max_length=64)
```

### 3.2 响应模型

```python
class LlmConfigResponse(BaseModel):
    api_base: str = ""
    api_key: str = ""  # 脱敏: 前8位+****+后4位
    model_name: str = ""
    has_custom_config: bool = False

class LlmBehaviorResponse(BaseModel):
    temperature: float = 0.7
    max_tokens: int = 2048
    system_prompt: str = ""

class UiPrefsResponse(BaseModel):
    theme: str = "dark"
    style: str = "professional"

class LearningPrefsResponse(BaseModel):
    socratic_mode: bool = False
    socratic_follow_up_mode: bool = False
    auto_scroll_on_load: bool = True
```

## 4. 仓储接口

### 4.1 `UserSettingsRepo` (基础设施层)

```python
class UserSettingsRepo:
    # 全量读写
    def get_all(self, user_id: str) -> dict
    def set_all(self, user_id: str, settings: dict) -> None

    # 按 key 读写
    def get_key(self, user_id: str, key: str, default: Any = None) -> Any
    def set_key(self, user_id: str, key: str, value: Any) -> None
    def set_multiple(self, user_id: str, updates: dict) -> None
    def delete_key(self, user_id: str, key: str) -> None
    def delete(self, user_id: str) -> None

    # 类型化 (Task #84 新增)
    def get_llm_behavior(self, user_id: str) -> dict
    def set_llm_behavior(self, user_id: str, behavior: dict) -> dict
    def get_ui_prefs(self, user_id: str) -> dict
    def set_ui_prefs(self, user_id: str, prefs: dict) -> dict
    def get_learning_prefs(self, user_id: str) -> dict
    def set_learning_prefs(self, user_id: str, prefs: dict) -> dict
```

### 4.2 `UserLlmConfigRepo` (基础设施层)

```python
class UserLlmConfigRepo:
    def get(self, user_id: str) -> Optional[dict]:
        """获取 LLM 配置（解密 api_key）"""
    def set(self, user_id: str, api_base: str, api_key: str, model_name: str) -> None:
        """保存 LLM 配置（加密 api_key）"""
    def save(self, user_id: str, api_base: str, api_key: str, model_name: str) -> None:
        """save 是 set 的别名（兼容 settings_api.py）"""
    def delete(self, user_id: str) -> None:
        """删除 LLM 配置"""
```

### 4.3 `UserRepo` (基础设施层)

```python
class UserRepo:
    # 用户 CRUD
    def create_user(self, user_id: str, username: str, password_hash: str, ...) -> bool
    def find_by_id(self, user_id: str) -> Optional[dict]
    def find_by_username(self, username: str) -> Optional[dict]
    def update_password(self, user_id: str, password_hash: str) -> bool
    def update_last_login(self, user_id: str) -> None
    def touch_last_active(self, user_id: str, throttle_sec: int) -> None
    def update_display_name(self, user_id: str, display_name: str) -> None
    def update_profile(self, user_id: str, display_name: str | None, email: str | None) -> bool  # Task #84 新增
    def deactivate_user(self, user_id: str) -> None
    def deactivate_account(self, user_id: str, username: str) -> None
    def increment_token_version(self, user_id: str) -> None
```

## 5. 数据一致性保证

### 5.1 写入流程

1. **Pydantic 校验** → 拒绝非法值（如 temperature > 2.0）
2. **Repository 合并写** → `set_llm_behavior` 等合并现有值与新值
3. **范围二次校验** → Repository 内兜底（如 temperature 截断到 [0, 2]）
4. **DB 持久化** → `INSERT ... ON CONFLICT DO UPDATE`
5. **事件发布** → `publish_event_safe(UserPreferencesUpdated(...))`

### 5.2 读取流程

1. **localStorage 即时响应** → 防止页面刷新闪烁
2. **服务端异步拉取** → `/api/settings/ui` 等接口
3. **差异更新** → 仅当服务端值与本地不同时才更新 state
4. **触发 DOM 更新** → `root.setAttribute('data-theme', ...)`

## 6. 数据保留与清除

### 6.1 哪些保留

- `users` — 账号本身
- `user_settings` — **用户偏好**（Task #84: 数据清除时保留）

### 6.2 哪些清除（`/api/data/reset`）

- `directory_nodes` (DataRepository)
- `knowledge_graphs` (DataRepository)
- `practice_sessions`, `session_questions`, `questions`, `question_banks` (PG)
- `messages` (PG)
- `materials` (PG)
- `flashcards` (PG)
- `login_events` (PG)

> 注意: `users` / `user_settings` / `user_llm_configs` / `policies` 不动
