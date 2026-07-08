# 苹果果 - 个人知识体系

> AI 驱动的个人学习助手，提供自主学习规划、精准答疑、多模态交互、知识追踪与个性化陪伴。

**技术栈**：Next.js 14 + React 18 + FastAPI + PostgreSQL + pgvector
**核心定位**：以认知引擎为大脑、对话系统为交互枢纽，通过练习、阅读、卡片复习、项目探索等多维学习方式，结合知识图谱构建个人知识体系，辅以秘书系统、规划系统、情绪系统提供个性化学习陪伴。

---

## 快速开始

```bash
# 一键启动（前后端 + Nginx + 认证网关）
bash rebuild.sh
# 访问 http://localhost:8080

# 前端开发（:3000）
cd frontend && npm run dev

# 后端开发（:8000）
cd backend && uvicorn main:app --reload
```

| 服务 | 端口 | 说明 |
|------|------|------|
| Nginx 统一入口 | 8080 | 路由分发、SSE 代理 |
| Next.js 前端 | 3000 | App Router、SSR/CSR 混合 |
| FastAPI 后端 | 8000 | 业务 API、LLM 调用 |
| Auth Gateway | 18001 | 认证、JWT 管理 |
| Admin 管理后台 | 3001 | 用户管理、数据监控 |

---

## 文档导航

### 架构总览
[architecture/overview.md](architecture/overview.md) — 系统分层架构、前后端通信、数据流、所有模块清单与依赖关系。

### 架构专题
| 文档 | 内容 |
|------|------|
| [architecture/message-tree.md](architecture/message-tree.md) | 对话消息树结构与操作 |
| [architecture/event-hierarchy.md](architecture/event-hierarchy.md) | 领域事件分类体系 |
| [architecture/event-system-v2.md](architecture/event-system-v2.md) | 事件系统 v2 设计 |
| [architecture/tool-architecture.md](architecture/tool-architecture.md) | AI Tool 调用架构 |

### 架构决策记录（ADR）
[adr/readme.md](adr/readme.md) — 12 份 ADR，覆盖项目探索、记忆卡、阅读、语言房间、心情压力、规划、兴趣探索、设置、秘书、认知引擎、情绪系统、多视图架构等关键决策。

### 模块文档

#### 核心模块
| 模块 | 文档 |
|------|------|
| 认知引擎 | [modules/cognitive-engine/overview.md](modules/cognitive-engine/overview.md) |
| 对话系统 | [modules/conversation-system/overview.md](modules/conversation-system/overview.md) |

#### 学习模块
| 模块 | 文档 |
|------|------|
| 练习系统 | [modules/practice-system/overview.md](modules/practice-system/overview.md) |
| 卡片复习 | [modules/flashcard/overview.md](modules/flashcard/overview.md) |
| 阅读系统 | [modules/reading/overview.md](modules/reading/overview.md) |
| 考试模式 | [modules/exam/overview.md](modules/exam/overview.md) |

#### 知识模块
| 模块 | 文档 |
|------|------|
| 知识图谱 | [modules/knowledge-graph/overview.md](modules/knowledge-graph/overview.md) |
| 项目管理 | [modules/project-based-exploration/overview.md](modules/project-based-exploration/overview.md) |

#### 辅助模块
| 模块 | 文档 |
|------|------|
| 秘书系统 | [modules/secretary-system/overview.md](modules/secretary-system/overview.md) |
| 规划系统 | [modules/planning/overview.md](modules/planning/overview.md) |
| 情绪系统 | [modules/emotion-system/overview.md](modules/emotion-system/overview.md) |
| 心情压力 | [modules/mood-stress/overview.md](modules/mood-stress/overview.md) |
| 专注模式 | [modules/focus/overview.md](modules/focus/overview.md) |

#### 发现模块
| 模块 | 文档 |
|------|------|
| 兴趣探索 | [modules/interest-explorer/overview.md](modules/interest-explorer/overview.md) |
| 语言房间 | [modules/language-room/overview.md](modules/language-room/overview.md) |
| 多模态 | [modules/multimodal/overview.md](modules/multimodal/overview.md) |

#### 基础设施
| 模块 | 文档 |
|------|------|
| 文件管理 | [modules/file-management/overview.md](modules/file-management/overview.md) |
| 设置 | [modules/settings/overview.md](modules/settings/overview.md) |
| 驾驶舱 | [modules/dashboard/overview.md](modules/dashboard/overview.md) |
| 学情分析 | [modules/analytics/overview.md](modules/analytics/overview.md) |
| 资源管理 | [modules/resources/overview.md](modules/resources/overview.md) |
| 质量分析 | [modules/quality/overview.md](modules/quality/overview.md) |
| 数据导入 | [modules/import/overview.md](modules/import/overview.md) |

### 设计规范
| 文档 | 内容 |
|------|------|
| [design-language.md](design-language.md) | UI 设计语言规范（颜色、字体、组件） |
| [design/sub-branch-design.md](design/sub-branch-design.md) | 子分支设计规范 |

### 部署运维
| 文档 | 内容 |
|------|------|
| [deploy/cloudflare-deploy.md](deploy/cloudflare-deploy.md) | Cloudflare 部署指南 |
| [deploy/user-management.md](deploy/user-management.md) | 用户管理运维 |

### AI 代理工作流
| 文档 | 内容 |
|------|------|
| [agents/domain.md](agents/domain.md) | 领域模型与开发约定 |
| [agents/triage-labels.md](agents/triage-labels.md) | Issue 分类标签规范 |
| [agents/issue-tracker.md](agents/issue-tracker.md) | Issue 跟踪流程 |

### 历史归档
[old/](old/) — 早期架构设计、Roadmap、Phase 规划、历史审计报告、旧版 Specs 等。

---

## 新人阅读路线

```
第 1 步: docs/architecture/overview.md    — 了解系统全貌、分层架构、模块清单
第 2 步: docs/adr/readme.md  — 理解关键架构决策的背景与取舍
第 3 步: docs/modules/ 中选感兴趣模块    — 深入具体模块的设计与实现
第 4 步: 阅读源码 frontend/src/ backend/ — 开始编码
```

---

## 项目结构速览

```
edu-companion/
├── frontend/              # Next.js 14 前端（App Router + Zustand + Tailwind）
├── backend/               # FastAPI 后端（分层架构：api/domain/services/infra）
├── auth-gateway/          # 独立认证网关（FastAPI :18001）
├── admin/                 # 管理后台（Next.js 14 :3001）
├── docs/                  # 项目文档（本目录）
│   ├── architecture/      # 架构文档
│   ├── modules/           # 23 个模块文档
│   ├── design-language.md # 设计规范
│   ├── design/            # 设计专题
│   ├── deploy/            # 部署文档
│   ├── agents/            # AI 代理工作流
│   └── old/               # 历史归档（ADR、Specs、Roadmap、Phase）
├── scripts/               # 工具脚本
└── rebuild.sh             # 一键重启（前后端 + Nginx + 认证网关）
```

---

## 文档维护约定

- **新模块**：必须在 `docs/modules/<module-name>/` 创建 `overview.md`，描述模块定位、数据模型、API 接口、事件定义。
- **重大架构变更**：需在 `docs/adr/` 创建 ADR 文档，记录决策背景、方案对比、最终选择。
- **历史文档归档**：过期或废弃的文档移动到 `docs/old/` 对应子目录，不在主文档区保留旧版本。
- **架构文档更新**：模块新增或重构后，同步更新 `docs/architecture/overview.md` 中的模块清单和依赖关系图。
- **设计变更**：UI 层面的重大变更需同步更新 `docs/design-language.md`。