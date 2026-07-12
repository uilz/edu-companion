# Phase 5 壳迁移路线图

> 目标：将剩余学习场景壳层逐步迁移到「API 路由薄、领域服务独立、文档完整、事件边界清晰」的统一架构。
> 参考模式：Phase 4 知识树壳迁移（四实体解耦、/api/trees 统一入口、services 层独立、docs/modules 补齐）。

---

## 一、迁移原则

1. **不双轨运行**：当前处于开发阶段，直接替换旧实现，不保留两套逻辑/数据。
2. **服务下沉**：业务逻辑从 `app/api/<module>/` 下沉到 `app/services/<module>/` 或 `app/domain/<module>/`。
3. **文档同步**：每个壳补齐 `docs/modules/<module-name>/overview.md`，必要时补充 events.md / design.md。
4. **事件边界**：跨壳调用走事件总线，不直接引用其他壳内部服务。
5. **垂直切片**：每次只迁移一个壳的一个子域，2-4 小时内可完成、可验证、可提交。

---

## 二、各壳现状与差距

| 壳 | 后端服务现状 | API 现状 | 文档现状 | 迁移复杂度 | 备注 |
|---|------------|---------|---------|----------|------|
| **Reading 阅读** | `app/services/reading/` 已拆分 7 个服务，结构干净 | `app/api/reading/routes.py` 较薄 | 缺 `docs/modules/reading/` | 低 | 最接近完成，优先收尾 |
| **Planning 规划** | 仅 `app/services/planning/completion_writer.py` | 核心业务在 `app/api/planning/service.py` | 缺 `docs/modules/planning/` | 中 | 需把 service.py 下沉到 services/planning/ |
| **Practice 练习** | `app/services/practice/` 已有 20+ 服务文件 | 路由层 `app/api/practice/` 仍含业务逻辑 | `docs/modules/practice-system/` 已存在 | 高 | 需按子域（题库/会话/错题/出题/统计/导入）切片 |
| **Secretary 秘书** | `app/domain/secretary/` + `app/services/secretary/` 已较成熟 | `app/api/system/secretary.py` + `app/api/secretary/mood_stress.py` | `docs/modules/secretary-system/` 已完整 | 低-中 | 仅需整理路由归属，非核心迁移 |

---

## 三、推荐迁移顺序

按「依赖少 → 依赖多、风险低 → 风险高、收尾 → 大改」排序：

### 3.1 Reading 阅读壳（收尾，1-2 个切片）

- **Slice 5.1**：补齐 `docs/modules/reading/overview.md` + `events.md`；检查 `app/api/reading/routes.py` 是否仅做 HTTP 转换。
- **Slice 5.2**：前端 API 路径与类型对齐；运行 rebuild.sh + 阅读标注/笔记端到端验证。

### 3.2 Planning 规划壳（中等，3-4 个切片）

- **Slice 5.3**：将 `app/api/planning/service.py` 中的业务逻辑迁移到 `app/services/planning/`（拆分 `items.py`、`goals.py`、`reviews.py`、`layouts.py`）。
- **Slice 5.4**：更新 `app/api/planning/routes.py` 仅调用新 services；更新 `app/api/planning/event_handler.py`。
- **Slice 5.5**：补齐 `docs/modules/planning/overview.md` + `events.md`。
- **Slice 5.6**：端到端验证（日/周/知识视图、计划项 CRUD、完成回写）。

### 3.3 Practice 练习壳（大改，6-8 个切片）

- **Slice 5.7**：文档与现状盘点，确定每个路由文件对应的服务映射。
- **Slice 5.8-5.13**：按子域逐个迁移（banks、sessions、errors、generation、stats、import/quality）。
- **Slice 5.14**：移除 API 层残留业务逻辑，统一错误处理与事件发布。
- **Slice 5.15**：端到端验证（题库、组卷、练习会话、错题本、AI 出题、统计）。

### 3.4 Secretary 秘书壳（可选整理，1-2 个切片）

- **Slice 5.16**：评估 `mood_stress.py` 是否应并入 `app/api/system/secretary.py` 或保持独立；补齐缺失文档。
- **Slice 5.17**：验证 45 个端点 + 92 E2E 测试仍通过。

---

## 四、关键依赖与风险

| 风险点 | 影响 | 缓解措施 |
|-------|------|---------|
| Practice 壳体量大，一次性迁移易出回归 | 高 | 严格按子域切片，每片单独 rebuild + 测试 |
| Planning 完成回写事件链路复杂 | 中 | 迁移前后对比 `completion_writer.py` 调用路径 |
| Reading 与 file-management 耦合 | 低 | 保持只读/复用边界，不改 file-management |
| 当前仓库有大量无关未提交变更 | 中 | Phase 5 切片提交前确保不混入其他模块改动 |
| 会话系统正被其他 Agent 重构 | 高 | Phase 5 不碰 `backend/app/api/conversations/` 及相关 untracked 文件 |

---

## 五、下一步待确认

1. 是否按上述顺序启动 Phase 5？
2. 是否先从 **Reading Slice 5.1** 开始（最小收尾切片）？
3. Secretary 壳是否纳入 Phase 5，还是放到后续阶段？
4. Practice 壳是否需要先出一份更细的子域拆分方案再动手？
