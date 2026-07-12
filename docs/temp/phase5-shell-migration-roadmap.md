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

## 二、各壳现状

| 壳 | 后端服务现状 | API 现状 | 文档现状 | 状态 |
|---|------------|---------|---------|------|
| **Reading 阅读** | `app/services/reading/` 已拆分 | `app/api/reading/routes.py` 较薄 | 已完成 | ✅ 已迁移 |
| **Planning 规划** | `app/services/planning/` 已拆分 8 个模块 | `app/api/planning/routes.py` 较薄 | overview + events + ADR 已完成 | ✅ 已迁移 |
| **Practice 练习** | `app/services/practice/` 已有 20+ 服务文件 | 路由层仍含业务逻辑 | `docs/modules/practice-system/` 存在但需按新架构重写 | 🔄 进行中 |
| **Secretary 秘书** | `app/domain/secretary/` + `app/services/secretary/` 已较成熟 | 路由归属可再整理 | 较完整 | ⏳ 待整理 |

---

## 三、Practice 壳服务下沉计划

### 3.1 现状差距

Practice 服务层已较完整，但 API 路由仍残留以下业务逻辑：

| 路由文件 | 残留业务逻辑 | 目标服务 | 状态 |
|---------|------------|---------|------|
| `banks.py` | 题库搜索过滤、题目预览组装、resolve 结果包装 | `practice_question_bank` | ✅ 已下沉 |
| `sessions.py` | 未完成的会话查询与组装、考试 config 包装 | `practice_session` / `practice_exam` | ✅ 已下沉 |
| `misc.py` | 秘书提案过滤、答题历史查询组装、独立答题提交、内联练习、遥测入口、自信度报告、自我解释评估 | 新建/复用 `proposals.py` `history.py` `standalone.py` `inline.py` `confidence.py` | ✅ 已下沉 |
| `references.py` | 搜索关键词生成 helper | `practice/references.py` service | ✅ 已下沉 |
| `import_routes.py` | 预览解析循环 | `practice_import/service.py` | ✅ 已下沉 |
| `errors.py` | 错题本/复习调度接口已直接委托服务层 | `practice_error_book` / `practice_scheduler` | ✅ 已较薄 |
| `stats.py` | 统计/成就接口已直接委托服务层 | `practice_stats` / `analytics.achievement_service` | ✅ 已较薄 |
| `generation.py` | 资料出题参数归一化、bank 解析、响应组装 | `practice_question_gen.py` | ✅ 已下沉 |
| `quality_routes.py` | 质量监控接口已直接委托 analyzer | `analytics.quality_analyzer` | ✅ 已较薄 |

### 3.2 切片

- **Slice 5.4**：题库与题目路由瘦身（banks.py）— ✅ 完成
- **Slice 5.5**：会话与考试路由瘦身（sessions.py）— ✅ 完成
- **Slice 5.6**： miscellaneous 路由瘦身（misc.py：历史、独立答题、内联、遥测、自信度、自我解释）— ✅ 完成
- **Slice 5.7**：错题/统计/出题/质量路由检查与补齐 — ✅ 完成（`generation.py` 资料出题逻辑下沉）
- **Slice 5.8**：文档重写（overview.md + events.md）+ ADR 0025 — ✅ 完成
- **Slice 5.9**：端到端验证（rebuild.sh + verify_practice_service_sink.py + pytest）

---

## 四、关键依赖与风险

| 风险点 | 影响 | 缓解措施 |
|-------|------|---------|
| Practice 壳体量大，一次性迁移易出回归 | 高 | 严格按子域切片，每片单独 rebuild + 测试 |
| 路由层残留的事件发布路径需保持 | 中 | 移动逻辑时保持 `publish_practice_events` 调用不变 |
| 当前仓库有大量无关未提交变更 | 中 | Practice 切片提交前确保不混入其他模块改动 |
| 会话系统正被其他 Agent 重构 | 高 | Phase 5 不碰 `backend/app/api/conversations/` 及相关 untracked 文件 |

---

## 五、下一步

启动 **Practice Slice 5.4：题库与题目路由瘦身**。
