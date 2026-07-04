# ADR 0008: Settings 模块 — 统一偏好存储 + 跨模块联动

## Status

Accepted

## 实现状态（截至 2026-07-04, Task #84）

### 已实现

- **决策 1 统一偏好存储**：所有用户级偏好合并到 `user_settings` JSONB 表（D16 已落地），新增 4 个命名空间（`llm_behavior` / `ui` / `learning` / `notification`）
- **决策 2 跨设备一致**：服务端为唯一来源，本地 localStorage 仅作防闪烁缓存；前端初始化时从 `/api/settings/{ui,learning}` 拉取最新值
- **决策 3 事件驱动**：新增 2 个用户域事件 `UserPreferencesUpdated` / `UserProfileUpdated`，覆盖所有偏好/资料变更点
- **决策 4 类型化接口**：`UserSettingsRepo` 提供 `get_llm_behavior` / `set_ui_prefs` / `set_learning_prefs` 等强类型接口
- **决策 5 Pydantic 严格校验**：`UiPrefsRequest` 通过 `field_validator` 限制 theme (dark/light) 和 style (5 种合法值)
- **决策 6 一键清除**：`DELETE /api/data/reset` 清空学习数据但保留 `user_settings` 用户偏好
- **决策 7 端到端测试**：53 个 E2E 测试覆盖 18 个设置/用户/数据端点

### 与原设计差异

- **关键差异 1（模块偏好自治）**：原设计期望所有偏好统一到 `user_settings`，实际 mood_stress / reading / interest 偏好仍保持模块自治表（设计妥协 — B6 未完全修复），通过事件统一联动
- **关键差异 2（LLM 配置拆分）**：原设计 `llm_config` 包含所有 LLM 字段，实际拆分为 `llm_config`（api_base/api_key/model_name）和 `llm_behavior`（temperature/max_tokens/system_prompt）两个命名空间，便于独立管理
- **关键差异 3（事件 source 字段）**：`UserPreferencesUpdated.source` 区分 `api`（后端 API 触发）/ `frontend_sync`（前端同步）/ `migration`（数据迁移），`UserProfileUpdated.change_type` 区分 `profile` / `password` / `deactivate` / `logout_others` / `avatar`
- **关键差异 4（删除 LLM 行为）**：原设计只有 `PUT /api/settings/llm` 没有 `DELETE`，Task #84 通过 `PUT llm-behavior {temperature: 0.7, max_tokens: 2048, system_prompt: ""}` 实现行为参数重置（不需要专门的 DELETE）

### 待修复 / 后续

- **待修复 1**：B6 完全迁移 — 将 mood_stress / reading / interest 偏好也迁到 `user_settings`（保持事件可联动）
- **待修复 2**：偏好版本控制 — 增加 `settings.version` 字段支持 schema 演进
- **待修复 3**：偏好导入/导出 — 用户可下载偏好 JSON 在新设备导入
- **待修复 4**：偏好模板 — "教师模式 / 学生模式"等预设模板

## Context

### 要解决的问题

用户在系统中有大量分散的偏好设置（主题、风格、LLM、布局、通知），这些偏好存在以下问题：

1. **存储散落** — 4 个 localStorage 键 + 5+ 个数据库表/字段
2. **跨设备失效** — localStorage 无法跨设备同步，换浏览器/换设备全部丢失
3. **缺少联动** — 没有 `UserPreferencesUpdated` 事件，偏好变更无法通知其他模块
4. **缺少验证** — Pydantic 模型不严格（如 theme 接受任意字符串）
5. **数据清除不彻底** — `/api/data/reset` 缺失或行为不一致

### 评估方案

#### 方案 A：完全统一（推荐）✅

所有用户级偏好合并到 `user_settings` JSONB 表，通过 Pydantic 严格校验 + 类型化仓储 + 事件发布实现跨设备一致。

**优势**:
- 单一来源 (SSOT)
- 跨设备自动一致
- 事件可观测性强
- 类型化接口易维护

**劣势**:
- 模块偏好（mood_stress/reading/interest）暂未迁移（妥协）

#### 方案 B：模块自治（已存在）

每个模块独立表，事件可联动但不统一存储。

**优势**:
- 模块解耦
- 不破坏现有数据

**劣势**:
- 存储散落
- 跨设备一致性差
- 需要为每个模块写独立同步逻辑

#### 方案 C：混合（实际采用）✅✅

核心用户级偏好（4 类）统一到 `user_settings`，模块偏好（5 个）保持独立表 + 事件联动。

**理由**: 平衡了"统一"和"自治"，先解决最影响用户体验的核心问题（主题/LLM/学习偏好跨设备失效），后续可渐进迁移模块偏好。

## Decision

采用 **方案 C — 混合**：

1. 核心 4 类偏好统一：`llm_config` / `llm_behavior` / `ui` / `learning`
2. 模块偏好保持独立：`secretary` / `mood_stress` / `reading` / `interest`
3. 通过 2 个用户域事件 `UserPreferencesUpdated` / `UserProfileUpdated` 跨模块联动
4. Pydantic 严格校验（field_validator 替代裸 str）
5. localStorage 仅作防闪烁缓存，不作为持久化来源
6. 一键清除保留 `user_settings`（用户偏好不丢）

## Consequences

### 正面

- 用户核心体验提升：主题/LLM/学习偏好跨设备一致
- 跨模块联动有了明确事件契约
- 端到端测试覆盖完整（53 个测试）
- 数据清除可保留用户偏好，避免误删

### 负面

- 模块偏好仍散落（B6 未完全修复）
- 前端双写（localStorage + 服务端）增加复杂度
- 需要为每个新模块添加 `UserPreferencesUpdated` 事件订阅点

### 中性

- 数据模型扩展性受限（JSONB 不易做复杂查询）

## References

- `docs/temp/task-84-settings-audit.md` — 完整摸底报告
- `docs/modules/settings/design.md` — 架构设计
- `docs/modules/settings/data-model.md` — 数据模型
- `docs/modules/settings/events.md` — 事件清单
- `backend/app/infrastructure/db/user_settings_repo.py` — 统一偏好仓储
- `backend/app/domain/auth/settings_api.py` — 设置 API
- `backend/shared/events.py:1698-1736` — UserPreferencesUpdated / UserProfileUpdated
- `backend/tests/test_settings_e2e_full.py` — 53 个 E2E 测试
