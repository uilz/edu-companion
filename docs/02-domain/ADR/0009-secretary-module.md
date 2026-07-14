# ADR 0009: Secretary 模块 — 全模块优化 + 事件矩阵统一 + E2E 覆盖

## Status

Accepted

## 实现状态（截至 2026-07-04, Task #83）

### 已实现

- **决策 1 提案状态机**：5 个状态 (pending/accepted/dismissed/snoozed/deleted) + 状态切换审计日志 (B-4 rowcount 检查)
- **决策 2 Schema 统一入口**：`secretary_proposals` 表 DDL 统一在 `secretary_schema.sql`，所有路径通过 `ProposalStore._ensure_table()` 调用 (B-1/B-2 修复)
- **决策 3 跨用户隔离**：所有查询带 `user_id` 过滤，杜绝数据泄露
- **决策 4 错误处理一致性**：所有 async 调用包 try/except，LLM/DB 失败不阻塞主流程 (B-9/B-15/B-20/B-23)
- **决策 5 事件矩阵**：3 个发布事件 (ProposalAccepted / MoodStressPrefsUpdated / UserPreferencesUpdated) + 3 个订阅事件
- **决策 6 缓存策略**：`/api/secretary/snapshot` 30s 内存缓存 (B-18)
- **决策 7 偏好默认值**：`enabled_extensions` 默认 3 个核心模块 (B-22 与 Pydantic 模型一致)
- **决策 8 持久化**：`check_interval` 写入 `secretary_prefs`，重启不丢 (B-3)
- **决策 9 公开端点**：`/api/secretary/mood-stress/constants` 加入 `PUBLIC_PATHS` (Task #83)
- **决策 10 端到端测试**：92 个 E2E 测试覆盖 45 个端点

### 与原设计差异

- **关键差异 1（DB→API 时间戳转换）**：原设计 Proposal.created_at/expires_at 期望 DB 直接传值，Task #83 修复 DB datetime → float 时间戳转换 (NEW bug)
- **关键差异 2（dismiss 检查 rowcount）**：原设计 dismiss 永远返回 200，Task #83 加 `if not ok: raise 404` 修复
- **关键差异 3（preferences 返回 check_interval）**：原设计 GET preferences 不返回 check_interval，Task #83 补充
- **关键差异 4（agent/preferences 发事件）**：原设计 POST agent/preferences 不发事件，Task #83 B-6 修复加 `UserPreferencesUpdated` 事件

### 待修复 / 后续

- **待修复 1**：行为触发 (BehaviorTrigger) 与上下文引擎 (ContextEngine) 联动优化
- **待修复 2**：政策引擎 (PolicyEngine) 关系记忆的索引化
- **待修复 3**：提案去重逻辑优化 (跨模块 fingerprint 共享)
- **待修复 4**：Agent SSE 流式响应的事件注入 (实时工具调用反馈)

## Context

### 要解决的问题

秘书模块在 Task #83 全面摸底时发现 15+ 真实 bug，影响模块稳定性和可观测性：

1. **API 不一致** — `dismiss` 不检查 rowcount (永远 200) / `accept` 异常处理不彻底
2. **存储分裂** — `secretary_proposals` 表 schema 在 3 处定义 (proposal_store / secretary.py / practice_schema.sql)
3. **状态机不闭环** — `snooze` / `restore` 无审计日志 / `delete` 软删但不可恢复
4. **事件缺失** — `agent/preferences` POST 不发事件，跨模块无法联动
5. **冷启动判定不可靠** — 仅根据 `total_nodes < 5` 判定，漏掉 `tree_recommendation`
6. **性能浪费** — `/snapshot` 每次都重算，无缓存
7. **缺测试** — 45 个端点仅有 15 个测试覆盖

### 评估方案

#### 方案 A：补丁式修复 (不推荐) ❌

逐个 bug 修补，不改架构。短期快但累积技术债。

#### 方案 B：全模块优化 (推荐) ✅

按用户规则全面摸底 + 修所有真实 bug + 新增 92 E2E + 更新架构文档 + 浏览器实测。一次性解决问题，不留两套逻辑。

### 决策依据

- 用户规则 (2026-07-04) 明确禁止补丁式修改
- 模块端点已统一 (45 个稳定)，全量优化比部分优化 ROI 更高
- 92 E2E 测试可在 CI 中持续验证
- ADR 文档 + 架构图 (events.md / design.md) 让后续维护有据可循

## Consequences

### 正面

- 提案状态机闭环 (audit log + rowcount + restore)
- 跨用户隔离强制，无数据泄露
- 事件矩阵明确 (3 发布 + 3 订阅 + 4 跨模块联动)
- 92 E2E 测试 + 浏览器实测 0 错误，可信度大幅提升
- 架构文档完整 (overview / events / design)
- 性能优化 (snapshot 缓存)

### 负面

- 修复 `_get_proposal_by_id` 涉及 DB 类型转换，需前端配合 (返回 `float` 时间戳)
- `mood-stress/constants` 公开需评估信息泄露风险 (当前仅枚举值，无敏感信息)

## 实现

- 主文件: `backend/app/api/system/secretary.py` (24 端点)
- 子模块: `backend/app/api/secretary/mood_stress.py` (13 端点)
- 存储: `backend/app/infrastructure/db/secretary_schema.sql` + `secretary_schema.py`
- 仓储: `backend/app/infrastructure/db/proposal_store.py`
- 测试: `backend/tests/test_secretary_e2e_full.py` (92 E2E)
- 文档: `docs/modules/secretary-system/{overview,events,design}.md`
- 浏览器实测: `scripts/task83_verify.py`

## 验证

- `pytest tests/test_secretary_e2e_full.py` → 92/92 passed
- `pytest tests/test_secretary_modules.py tests/test_secretary_service.py` → 12/12 passed
- `bash rebuild.sh --skip-admin` → 前后端启动成功
- 浏览器实测: 5/5 通过, 0 console error, 0 page error, 0 network error
- 手动 API 调用: preferences / snapshot / proposals / modules / constants 全部 200
