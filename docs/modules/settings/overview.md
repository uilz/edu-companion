# Settings 模块 — 概览

> **任务**: Task #84 — 设置模块全面优化  
> **创建日期**: 2026-07-04

## 模块定位

Settings 是整个教育助手的"用户偏好中心"，负责管理所有用户级的配置和偏好。

## 文档清单

| 文档 | 内容 |
|------|------|
| [overview.md](./overview.md) | 模块总览（本文） |
| [design.md](./design.md) | 架构设计、端点表、事件 |
| [data-model.md](./data-model.md) | 数据库表、模型、仓储 |
| [events.md](./events.md) | 事件清单、发布点、订阅建议 |

## 核心职责

1. **用户资料管理** — 昵称、邮箱、密码、头像
2. **设备管理** — 活跃会话、踢出其他设备
3. **LLM 配置** — 自定义 API/Key/Model/行为参数
4. **UI 偏好** — 主题、设计风格
5. **学习偏好** — 苏格拉底模式、追问模式、自动滚动
6. **数据管理** — 学习数据概览、导出、清除
7. **跨模块联动** — 通过 UserPreferencesUpdated / UserProfileUpdated 事件

## 关键设计原则

1. **统一存储** — 用户级偏好统一到 `user_settings` JSONB 表
2. **跨设备一致** — 服务端为唯一来源，本地 localStorage 仅作防闪烁缓存
3. **事件驱动** — 偏好变更通过事件发布，跨模块联动无需直接耦合
4. **类型化接口** — Pydantic 严格校验，Repository 二次兜底
5. **安全优先** — API Key Fernet 加密、密码 bcrypt、token_version 踢设备

## 验收状态（Task #84）

| 项目 | 状态 |
|------|------|
| 全面摸底（Part A） | ✅ 完成 (`docs/temp/task-84-settings-audit.md`) |
| 修复 8 个 Bug（Part B） | ✅ B1-B5 + B7 完成，B6 设计妥协 |
| E2E 测试 ≥ 20（Part C） | ✅ **53 个测试** (`test_settings_e2e_full.py`) |
| 端到端验收（Part D） | ✅ pytest 1286 passed, 0 failure (related) |
| 设计文档（Part E） | ✅ 完成 (`docs/modules/settings/*.md`) |
| Git 提交（Part F） | ⏳ 待提交 |

## 端点速查

- 用户/认证 10 端点
- 设置 9 端点
- 数据管理 12 端点
- **合计 31 端点**（与基线 154+ 端点一致，未删任何端点）

## 相关文件

- `backend/app/domain/auth/api.py` — 用户/认证 API
- `backend/app/domain/auth/settings_api.py` — 设置 API
- `backend/app/infrastructure/db/user_settings_repo.py` — 统一偏好仓储
- `backend/app/infrastructure/db/auth_repository.py` — 用户仓储
- `backend/app/api/system/data_routes.py` — 数据管理 API
- `frontend/src/app/settings/page.tsx` — 前端设置页面
- `frontend/src/contexts/ThemeContext.tsx` — 主题/风格上下文
- `backend/shared/events.py` — UserPreferencesUpdated / UserProfileUpdated 事件
