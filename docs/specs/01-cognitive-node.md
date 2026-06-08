# 数据规格：CognitiveNode

> 系统中所有知识点的统一表征。CognitiveNode 是**唯一数据源**，所有模块的认知状态以此为基准。
>
> 源码：[backend/app/cognitive/models.py](../../backend/app/cognitive/models.py)

---

## 身份与层级

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | str | 全局唯一（path_id 格式，如 `math.analysis.derivative`） |
| `label` | str | 节点名称 |
| `level` | str | 层级：partition / domain / topic / concept / atom |
| `parent` | str\|null | 父节点 ID |
| `children` | list[str] | 子节点 ID 列表 |
| `is_core` | bool | 是否核心节点 |
| `brief` | str | 节点简介（AI 或用户维护） |

## 图谱结构

| 字段 | 类型 | 说明 |
|------|------|------|
| `prerequisites` | list[Prerequisite] | 前置依赖（strict/suggested） |
| `unlocks` | list[Unlock] | 解锁门控（含 UnlockGate） |
| `associates` | list[Associate] | 关联节点（analogy/prerequisite/contrast） |

## 子系统状态（20 个）

| 子系统 | 模型类 | 关键字段 | 说明 |
|--------|--------|----------|------|
| ACT-R 激活 | `Activation` | base_level, retrieval_prob, latency_ms, spread_from_network | 记忆激活扩散 |
| 贝叶斯信念 | `Belief` | alpha, beta, proficiency_mean, proficiency_precision | Beta(α,β) 掌握分布 |
| 预测编码 | `Prediction` | top_down_mean, prediction_error, error_flag | 预测与误差信号 |
| 认知负荷 | `CognitiveLoad` | intrinsic, dynamic, aggregation_k | 内在+动态负荷 |
| 练习事件 | `list[PracticeEvent]` | timestamp, success, latency_ms, weight | 历史练习记录 |
| 练习摘要 | `PracticeSummary` | total_attempts, correct_attempts, recent_success_rate_7d | 练习统计 |
| 学习趋势 | `Trend` | velocity_ewma, stagnation_days, direction | ascending/descending/plateau/volatile |
| 错误诊断 | `list[ErrorCluster]` | cluster_id, count, last_seen, embedding | 错误聚类 |
| 统一调度 | `Scheduling` | urgency, next_review, next_action_type | review/deep_processing/none |
| 目标对齐 | `GoalAlignment` | toward_goal, distance, on_critical_path | 学习路径对齐 |
| 诊断评估 | `Diagnostic` | administered, score, inferred_proficiency | 诊断测试结果 |
| 深度思考 | `DeepProcessing` | task_templates, task_instances | 催化深度学习 |
| 深度连接 | `list[DeepLink]` | target, strength, source, type | 跨域知识连接 |
| 对话上下文 | `list[DialogueContext]` | session_id, context_type, relevance_score | upper/lower 上下文 |
| 元认知 | `Metacognition` | self_assessment, calibration_error, direction | overconfident/underconfident/accurate |
| 激励 | `Engagement` | xp, streak_current, effort_estimate | 游戏化激励 |
| 知识编译 | `Composition` | chunk_id, chunking_status, formation_tracker | none/forming/formed |

## Phase 8 扩展字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `path_id` | str | 不变路径标识（如 `大学物理.电磁学.静电场`） |
| `node_type` | str | explicit / auto_generated / user_created / suggested |
| `is_visible` | bool | 是否在侧边栏可见 |
| `subsystems` | dict | 扩展子系统数据 |
| `embedding` | list[float]\|null | 向量嵌入 |
| `is_active` | bool | 是否活跃 |
| `emoji` | str | 图标前缀 |
| `color` | str | 颜色标记 |
| `sort_order` | int | 排序权重 |

## 参数引用 (param_refs)

节点引用全局参数的映射表：

```python
param_refs = {
    "decay_factor": "student.decay_factor",
    "mastery_gate": "student.mastery_gate",
    "retrieval_sigma": "student.retrieval_sigma",
    "min_pseudo_count": "student.min_pseudo_count",
    "diagnostic_precision": "student.diagnostic_precision",
    "sched_retention_weight": "student.sched_retention_weight",
    "sched_mastery_push_weight": "student.sched_mastery_push_weight",
    "sched_interleaving_weight": "student.sched_interleaving_weight",
    "sched_core_boost": "student.sched_core_boost",
    "sched_stagnation_penalty": "student.sched_stagnation_penalty",
    "fatigue_decay_lambda": "student.fatigue_decay_lambda",
    "fatigue_increment_eta": "student.fatigue_increment_eta",
    "velocity_decay_lambda": "student.velocity_decay_lambda",
}
```

## 生命周期

```
创建（首次提及）→ 活跃（练习/对话）→ 巩固（间隔重复）→ 掌握（proficiency >= 0.85）
  ↘ 遗忘（长期未复习，activation 衰减）→ 重新激活
  ↘ 合并/拆分（知识树编辑）
```

## 核心规则

1. **唯一数据源**：所有模块对知识点的状态更新必须通过 CognitiveNode 同步
2. **事件驱动**：状态变更通过 `CognitiveNodeUpdated` 事件广播，模块异步消费
3. **持久化**：所有子系统状态持久化到 PostgreSQL JSONB（`cognitive_nodes` 表）
4. **访问原则**：读取不加锁，写入通过 `CognitiveNodeWriter` 和仓储协议接口
5. **幂等创建**：同一 parent + level + label 只创建一次
