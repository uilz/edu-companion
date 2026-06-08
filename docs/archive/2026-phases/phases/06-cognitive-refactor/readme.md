```markdown
# AI 伴学系统中枢设计（对话联动完整版 v2.10）

**基于认知节点（CognitiveNode）的统一状态模型**

> **版本**：v2.10  
> **核心理念**：融合 Math Academy 的严格图谱与精熟路径、BKT 的贝叶斯知识追踪、ACT‑R 的激活与遗忘理论、ThoughtsMemo 的深度思考催化，以及树状多分支对话系统的上下文联动，以递归同构的认知节点实现“一处更新，全局一致”。  
> **状态**：所有模块均通过压力模拟，可直接作为核心引擎实现规范。

---

## 1. 概述

`CognitiveNode` 是 AI 伴学系统的核心数据结构。每个知识点（从学科分区到原子技能）对应一个结构完全相同的节点。所有子系统（练习、对话、图谱、资料）仅通过读写节点及其事件完成交互。节点内部封装了激活、信念、遗忘、错误诊断、调度、元认知、深度连接、激励、目标对齐、知识编译、学习趋势以及**对话上下文联动**的全部状态。

对话系统采用**分区‑领域‑专题**的树状会话管理，每个会话支持多分支及版本切换（上下文分为“上一条”与“下多条合并”）。节点不管理会话数据，但通过记录关联的会话标识，与对话系统协同实现精准的深度思考触发与概念连接更新。

---

## 2. 全局参数默认值

系统维护一份全局可学习参数表（每个学生一份），存储于独立文档或 Redis。参数通过 `param_refs` 引用，默认初始值如下：

| 参数名 | 默认值 | 说明 |
|--------|--------|------|
| `student.decay_factor` | 0.5 | 激活/信念衰减因子 |
| `student.mastery_gate` | 0.85 | 解锁后继的 proficiency 阈值 |
| `student.retrieval_sigma` | 0.3 | 激活噪声尺度 |
| `student.min_pseudo_count` | 1.0 | 信念遗忘下限伪计数 |
| `student.diagnostic_precision` | 10.0 | 诊断覆盖时的信念精度 |
| `student.sched_retention_weight` | 0.3 | 调度-遗忘紧迫权重 |
| `student.sched_mastery_push_weight` | 0.5 | 调度-推进掌握权重 |
| `student.sched_interleaving_weight` | 0.6 | 调度-交错收益权重 |
| `student.sched_core_boost` | 0.2 | 核心技能加成 |
| `student.sched_stagnation_penalty` | 0.15 | 调度-停滞惩罚系数 |
| `student.fatigue_decay_lambda` | 0.1 | 疲劳指数衰减率 |
| `student.fatigue_increment_eta` | 0.2 | 疲劳单次增量系数 |
| `student.velocity_decay_lambda` | 0.5 | 速度 EWMA 衰减率（per day） |

---

## 3. 节点数据结构（v2.10 对话联动版）

```jsonc
CognitiveNode {
  // ──────────── 身份与层级 ────────────
  "id": "math.calculus.derivative.chain_rule",       // 层级路径作为ID
  "label": "链式法则",
  "level": "atom",                    // partition|domain|topic|concept|atom
  "parent": "math.calculus.derivative",               // 父节点ID，根为null
  "children": [],                     // 子节点ID列表，原子为空
  "is_core": true,                    // 核心技能标记，调度加权

  // ──────────── 图谱结构 ────────────
  "prerequisites": [
    {
      "id": "math.calculus.derivative.power_rule",
      "type": "strict",
      "auto_required": false          // true则前置必须达到automatic
    }
  ],
  "unlocks": [
    {
      "id": "math.calculus.integral.substitution",
      "gate": {                       // 可学习阈值，带缓存TTL
        "ref": "student.mastery_gate",
        "value": 0.85,
        "cached_at": 1716000000,
        "ttl_seconds": 3600
      }
    }
  ],
  "associates": [                     // 灵活连接（扩散激活+思考催化）
    {
      "id": "math.calculus.derivative.product_rule",
      "strength": 0.6,
      "plasticity": { "hebbian": 0.01, "anti_hebbian": 0.005 },
      "label": "类似法则",
      "domain": "math",
      "type": "analogy"               // analogy|prerequisite|contrast
    }
  ],

  // ──────────── ACT‑R 激活状态 ────────────
  "activation": {
    "base_level": 2.3,
    "retrieval_prob": 0.92,           // 新节点初始0.5
    "latency_ms": 1850,               // 新节点初始5000
    "noise_sigma": { "ref": "student.retrieval_sigma", "value": 0.3 },
    "spread_from_network": 0.41       // 来自associates的扩散激活和，缓存
  },

  // ──────────── 贝叶斯信念（Beta分布） ────────────
  "belief": {
    "alpha": 22.0,                    // 新节点初始2.0
    "beta": 3.0,                      // 新节点初始2.0
    "proficiency_mean": 0.88,         // α/(α+β)
    "proficiency_precision": 25.0,    // α+β
    "peak_proficiency": 0.97,         // 历史最高proficiency_mean，新节点初始0.5
    "last_updated": 1716000000        // 初始为节点创建时间
  },

  // ──────────── 层级预测编码（仅用于异常检测） ────────────
  "prediction": {
    "top_down_mean": 0.85,
    "prediction_error": 0.02,
    "error_flag": false               // |error|>0.2 触发预警
  },

  // ──────────── 练习历史与压缩 ────────────
  "practice_events": [                // 最多50条
    { "timestamp": 1716000000, "success": true, "latency_ms": 2100 }
  ],
  "practice_summary": {
    "total_attempts": 45,
    "recent_success_rate_7d": 0.91,
    "mean_latency_7d": 1920,
    "decayed_event_count": 28.5,      // 递推维护
    "rapid_relearn_cooldown_until": 0 // Unix时间戳，0表示可用
  },

  // ──────────── 学习趋势（含历史序列） ────────────
  "trend": {
    "recent_proficiencies": [0.88, 0.86, 0.89, 0.91], // 最多保留7个
    "velocity_ewma": 0.005,
    "stagnation_days": 3,
    "volatility_std": 0.02,
    "direction": "plateau"            // ascending|descending|plateau|volatile
  },

  // ──────────── 错误诊断 ────────────
  "error_clusters": [
    {
      "cluster_id": "sign_mistake",
      "count": 3,
      "last_seen": 1716000000,
      "embedding": [0.2, -0.5, 0.8]
    }
  ],

  // ──────────── 认知负荷 ────────────
  "cognitive_load": {
    "intrinsic": 0.55,
    "dynamic": 0.42,                 // 基于前置掌握度实时计算（最终一致性）
    "aggregation_k": 1.0
  },

  // ──────────── 统一调度 ────────────
  "scheduling": {
    "urgency": 0.23,
    "next_review": 1717800000,
    "interleaving_group": "derivative_rules",
    "last_interleaved_with": [],
    "next_action_type": "review"      // review|deep_processing|none
  },

  // ──────────── 目标对齐 ────────────
  "goal_alignment": {
    "toward_goal": "algebraic_fraction_fluency",
    "distance": 0.6,
    "on_critical_path": true
  },

  // ──────────── 诊断评估持久化 ────────────
  "diagnostic": {
    "administered": true,
    "score": 0.92,
    "inferred_proficiency": 0.90,
    "overrides_activation": true,
    "timestamp": 1716000000
  },

  // ──────────── 深度思考催化 ────────────
  "deep_processing": {
    "task_templates": [
      {
        "id": "explain_relation",
        "template": "请解释 {skill_label} 与 {associate_label} 之间的关系。",
        "trigger": {
          "rules": [
            { "pointer": "/belief/proficiency_mean", "op": ">=", "value": 0.8 },
            { "pointer": "/error_clusters", "op": "array_length_gt", "value": 0 }
          ],
          "logic": "AND",
          "cooldown_days": 3,
          "require_dialogue_context": false
        },
        "plasticity_effects": {
          "links_to_strengthen": [
            { "target_variable": "associate_id", "delta": 0.05 }
          ]
        }
      },
      {
        "id": "reflect_on_discussion",
        "template": "回顾之前的讨论，{skill_label} 的关键点是什么？",
        "trigger": {
          "rules": [
            { "pointer": "/dialogue_contexts", "op": "non_empty" },
            { "pointer": "/belief/proficiency_mean", "op": ">=", "value": 0.7 }
          ],
          "logic": "AND",
          "cooldown_days": 1,
          "require_dialogue_context": true    // 必须有最近的对话记录
        },
        "plasticity_effects": {
          "links_to_strengthen": [
            { "target_variable": "self", "delta": 0.02, "reason": "meta_reflection" }
          ]
        }
      }
    ],
    "task_instances": []
  },

  // ──────────── 深度连接 ────────────
  "deep_links": [
    {
      "target": "math.calculus.derivative.implicit",
      "strength": 0.4,
      "source": "student_insight",
      "domain": "math",
      "type": "contrast"
    }
  ],

  // ──────────── 对话上下文联动（新增） ────────────
  "dialogue_contexts": [
    {
      "session_id": "sess_math_001",          // 对话会话ID（树状存储）
      "branch_id": "branch_derivative",       // 分支标识
      "version": 2,                           // 分支版本号
      "context_type": "upper",                // 上下文位置：upper(上一条) 或 lower(下多条合并)
      "last_discussed": 1716000000,           // 最近讨论时间戳
      "relevance_score": 0.85,                // 该技能在当前对话中的相关度 (0~1)
      "summary_text": "讨论了链式法则的直观理解"  // 对话系统生成的简短摘要（可选）
    }
  ],

  // ──────────── 元认知 ────────────
  "metacognition": {
    "self_assessment": 0.80,
    "calibration_error": 0.09,
    "direction": "overconfident"
  },

  // ──────────── 激励 ────────────
  "engagement": {
    "xp": 240,
    "streak_current": 5,              // 跨会话保留
    "effort_estimate": 0.73
  },

  // ──────────── 知识编译与 Chunk 演化 ────────────
  "composition": {
    "chunk_id": null,
    "chunking_status": "none",
    "formation_criteria": {
      "min_co_occurrence_sessions": 10,          // 绝对次数阈值
      "min_individual_auto_probability": 0.8,
      "consecutive_sessions": 5
    },
    "formation_tracker": {
      "co_occurrence_sessions": 12,
      "consecutive_sessions_met": 4,
      "last_session_id": "sess_xyz",
      "last_session_snapshot": {
        "skill_ids": ["math...power_rule", "math...product_rule"],
        "all_proficient": true
      }
    }
  },

  // ──────────── 外部参数引用 ────────────
  "param_refs": {
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
    "velocity_decay_lambda": "student.velocity_decay_lambda"
  },

  // ──────────── 元信息 ────────────
  "meta": {
    "created_at": 1716000000,
    "updated_at": 1716000000,
    "version": 3
  }
}
```

> **用户级全局状态**（独立文档或缓存）：
> ```jsonc
> {
>   "user_id": "u1",
>   "daily_practice_count": 12,
>   "fatigue_level": 0.6,
>   "current_session_id": "sess_math_001",
>   "session_start_time": 1716000000,
>   "last_activity_time": 1716000000,
>   "practice_count_this_session": 5
> }
> ```

---

## 4. 核心数学方程（v2.10）

### 4.1 激活更新（层级 ACT‑R）
\[
B_i = \ln\left( \sum_{e \in \text{events}} (t_{\text{now}} - t_e)^{-d} + \epsilon \right) + 0.1 \cdot \mu_{\text{parent}} + \sum_{j \in \text{associates}} w_{ij} \cdot R_j
\]
- \(d\)：衰减因子（引用 `student.decay_factor`），\(\epsilon = 10^{-6}\)
- 关联节点检索概率 \(R_j\) 缺失时取 0.5。
检索概率：\(P_{\text{recall}} = 1/(1 + e^{-B_i/\sigma})\)，\(\sigma\) 取自 `retrieval_sigma`
预期反应时：\(RT = 5000 \cdot e^{-B_i}\)

### 4.2 信念更新（稳健贝叶斯）
1. **遗忘衰减**（同比例，强制下限）
   \[
   \alpha_{\text{decay}} = \max(\alpha_{\text{last}} \cdot e^{-d\Delta t},\; \alpha_{\text{min}})
   \]
   \[
   \beta_{\text{decay}} = \max(\beta_{\text{last}} \cdot e^{-d\Delta t},\; \beta_{\text{min}})
   \]
   \(\alpha_{\text{min}} = \beta_{\text{min}}\) 取自全局参数 `min_pseudo_count`。
2. **快速重新学习**（冷却期控制）
   条件：
   - `peak_proficiency >= 0.95`
   - 当前 `proficiency_mean < 0.8`
   - 正确且 `latency_ms < max(3000, expected_latency_ms * 1.5)`
   - `rapid_relearn_cooldown_until <= now`
   满足时有效权重 \(w_{\text{eff}} = w \times 2.0\)，并**原子更新**冷却为 `now + 365*86400`。
3. **证据融合**
   \[
   \alpha_{\text{post}} = \alpha_{\text{decay}} + w_{\text{eff}} \cdot x
   \]
   \[
   \beta_{\text{post}} = \beta_{\text{decay}} + w_{\text{eff}} \cdot (1 - x)
   \]
   更新 `proficiency_mean`、`precision`、`peak_proficiency`、`last_updated`。

### 4.3 聚合（可视化）
\[
\mu_{\text{parent}} = \left( \frac{1}{N} \sum \mu_c^{-k} \right)^{-1/k}, \quad
\tau_{\text{parent}} = \frac{1}{\frac{1}{N}\sum \tau_c^{-1} + 0.01}
\]

### 4.4 压缩递推
\[
\text{decayed\_count}_{\text{new}} = \text{decayed\_count}_{\text{old}} \cdot e^{-d\Delta t} + 1
\]

### 4.5 学习趋势（含长期不活动处理）
在信念更新**之前**，先进行趋势预处理：
设距 `belief.last_updated` 的天数差 \(\Delta t\)（可为小数）。

1. **速度衰减**：\(v_{\text{decayed}} = v_{\text{old}} \cdot e^{-\lambda_{\text{vel}} \cdot \Delta t}\)，\(\lambda_{\text{vel}}\) 取自 `velocity_decay_lambda`（默认 0.5）。
2. **停滞天数基于时间累积**：若 \(\Delta t > 0\)，`stagnation_days += Δt`（实际实现时直接按天累积，在后续步骤中可能被清零）。
3. **历史序列清理**：若 \(\Delta t > 1\)，则清空 `recent_proficiencies`，避免用过期数据计算波动。

然后执行正常的信念更新，获取新的 \(\mu_t\)。之后：
4. 将 \(\mu_t\) 推入 `recent_proficiencies`（最多保留 7 个）。
5. 计算实际速度：\(v_{\text{new}} = 0.9 \cdot v_{\text{decayed}} + 0.1 \cdot (\mu_t - \mu_{t-1})\)（若历史为空则速度置 0）。
6. 若 `recent_proficiencies.length >= 2`，计算 `volatility_std`；否则为 0。
7. 若 `volatility_std > 0.05`，`direction = "volatile"`；
   否则，若 \(|v_{\text{new}}| < 0.005\)，保持或增加 `stagnation_days`（不清零）；
   若 \(v_{\text{new}} \ge 0.005\)，`direction = "ascending"`，`stagnation_days = 0`；
   若 \(v_{\text{new}} \le -0.005\)，`direction = "descending"`，`stagnation_days = 0`。
8. 更新 `velocity_ewma = v_new`。

### 4.6 疲劳模型
- 会话定义：最近 1 小时内有操作视为同一会话。`practice_count_this_session` 由用户状态服务幂等维护。
- \(L_{\text{session}} = \min(1.0, \text{practice\_count\_this\_session} / 30)\)
- \(\text{fatigue}_{\text{new}} = \text{fatigue}_{\text{old}} \cdot e^{-\lambda \cdot \Delta t} + \eta \cdot L_{\text{session}}\)

---

## 5. 事件协议

### 5.1 事件格式
```jsonc
{
  "event_id": "evt_abc123",
  "event_type": "practice_response",
  "user_id": "u1",
  "node_id": "math.calculus.derivative.chain_rule",
  "timestamp": 1716000000,
  "payload": {
    "success": true,
    "latency_ms": 2300,
    "weight": 1.0,
    "context": {
      "question_id": "q123",
      "secondary_nodes": ["math...product_rule"],
      "error_embedding": [0.1, -0.2, 0.3]
    }
  }
}
```
新增对话上下文更新事件：
```jsonc
{
  "event_id": "evt_dialogue_001",
  "event_type": "dialogue_context_update",
  "user_id": "u1",
  "node_id": "math.calculus.derivative.chain_rule",
  "timestamp": 1716000000,
  "payload": {
    "session_id": "sess_math_001",
    "branch_id": "branch_derivative",
    "version": 2,
    "context_type": "upper",
    "relevance_score": 0.85,
    "summary_text": "..."
  }
}
```

### 5.2 事件类型与默认权重
| 类型 | 权重 | 备注 |
|------|------|------|
| `practice_response` | 1.0 | 常规练习 |
| `diagnostic_result` | 1.5 | 诊断考试，覆盖激活和信念 |
| `conversation_assessment` | 0.4~0.6 | 对话评估 |
| `material_view` | 0.1 | 资料浏览 |
| `self_assessment` | — | 仅更新自评 |
| `deep_connection` | — | 建立概念连接 |
| `dialogue_context_update` | — | 更新对话上下文 |

---

## 6. 事件处理流程（v2.10 最终版）

### 6.1 处理 `practice_response` 事件

1. **加载节点与用户状态**：读取目标节点、关联节点缓存激活（缺失取 0.5）、用户全局状态。
2. **会话管理**：若 `last_activity_time` 距当前超 1 小时，生成新会话 ID，重置 `practice_count_this_session = 0`。更新 `last_activity_time`，`practice_count_this_session` 稍后由状态服务幂等递增。
3. **趋势预处理**：按 4.5 节进行速度衰减、停滞天数时间累积、历史序列清理。
4. **遗忘衰减**：按 4.2 节对信念执行时间衰减。
5. **快速恢复检查**：满足条件时原子更新冷却，加倍有效权重。
6. **信念更新**：融合证据，更新 α, β, proficiency_mean, precision, peak_proficiency, last_updated。
7. **更新学习趋势**：按 4.5 节剩余步骤计算 velocity, stagnation, volatility, direction。
8. **更新练习历史**：追加事件，裁剪至 50 条，递推 decayed_event_count，刷新 summary。
9. **重新计算激活**：利用事件列表和 decayed_count 计算 base_level；遍历 associates 加权求和得 spread；导出 retrieval_prob 和 latency_ms。
10. **更新动态认知负荷**：遍历 prerequisites，取每个前置的 proficiency_mean（缺失默认 0.5，容忍最终一致性），`dynamic = intrinsic * (1 - mean(mastery))`。
11. **预测误差检测**：与父节点预测值比较，超阈值标记 error_flag。
12. **异步通知父节点**：标记父节点 dirty，去抖聚合更新可视化数据，推送子节点 top_down_mean。
13. **更新激励**：正确+10xp，连续正确额外+5；错误无加分，streak 归零。
14. **更新错误簇**：若失败且包含 error_embedding，匹配或创建聚类。
15. **更新 Chunk 形成进度**：
    - 新会话时：用 `last_session_snapshot` 评估上一会话（快照空或不达标则重置连续计数；达标则 +1）。
    - 保存当前会话快照（若含 secondary_nodes 则记录参与技能及其 proficient 状态）。
    - 更新 `last_session_id`；若本事件含交错练习，`co_occurrence_sessions += 1`。
    - 若 `co_occurrence_sessions >= min_co_occurrence_sessions` 且 `consecutive_sessions_met >= consecutive_sessions`，发布 Chunk 创建事件。
16. **检查解锁**：gate 缓存过期则刷新，达标发布 `skill_unlocked`。
17. **统一调度决策**：
    - 若 `dialogue_contexts` 非空且最近讨论时间在 1 天内，可优先安排 `deep_processing` 类型的反思任务。
    - 计算优先级：
      ```
      score = w_ret * urgency + w_mast * (1-μ) + w_inter * interleaving_benefit
              + w_core * is_core + w_stag * (stagnation_days > 3) - fatigue_level
      ```
18. **保存节点**（乐观锁），发布 `node_updated` 事件，通知用户状态服务幂等增加 `practice_count_this_session` 并更新疲劳值。

### 6.2 处理 `diagnostic_result` 事件
1. 加载节点，清空练习历史（若覆盖激活），重置 decayed_event_count。
2. **重置趋势**：清空 recent_proficiencies，velocity_ewma、stagnation_days、volatility_std 归零。
3. **重置 Chunk 跟踪器**。
4. 从全局参数获取 `diagnostic_precision`，计算 α = inferred_proficiency * precision, β = (1 - inferred_proficiency) * precision。
5. 设置 `peak_proficiency = inferred_proficiency`，`last_updated = now`。
6. 根据 proficiency 计算 base_level 并缓存。
7. 标记 `diagnostic` 字段，保存节点。

### 6.3 处理 `dialogue_context_update` 事件
1. 加载节点。
2. 在 `dialogue_contexts` 数组中查找匹配 `session_id` + `branch_id` 的条目。
   - 若找到，更新 `version`, `context_type`, `relevance_score`, `summary_text`, `last_discussed`。
   - 若未找到，追加新条目。
3. 保持数组长度不超过 5 条，保留最近讨论的会话。
4. 保存节点（乐观锁）。

### 6.4 对话系统联动规则
- 对话系统在每轮对话后，可通过语义分析识别涉及的技能节点，发送 `dialogue_context_update` 事件。
- 当某技能节点的 `dialogue_contexts` 中包含最近活动会话，且 `proficiency_mean` 处于 0.7~0.95 时，调度服务可提升 `deep_processing` 任务的优先级。
- 深度思考任务完成后，对话系统可将学生的见解转化为新的 `deep_links` 或更新 `associates` 强度，通过 `deep_connection` 事件写入。

---

## 7. 并发与幂等
- **节点更新**：乐观锁 (`meta.version`)。
- **冷却期原子更新**：使用 MongoDB `findOneAndUpdate` 条件 `cooldown_until <= $currentTime` 或乐观锁重试。
- **练习计数**：用户状态服务接收事件 ID，去重后 `INCR`，保证幂等。
- **对话上下文更新**：基于 `session_id + branch_id` 幂等。

## 8. 触发规则操作符扩展
支持：`>=`, `>`, `<=`, `<`, `==`, `!=`, `array_length_gt`, `non_empty`。实现时注册扩展操作符。

## 9. 技术架构
- **数据库**：MongoDB（每用户一个集合，节点路径为文档 ID），索引 `parent`, `scheduling.next_review`
- **事件队列**：Kafka（分区键 user_id）
- **事件处理服务**：Go/Node.js 微服务，实现所有事件处理逻辑
- **用户状态服务**：Redis 管理会话、疲劳、练习计数
- **统一调度服务**：独立查询节点与用户状态，计算优先级，分流至练习/对话系统
- **离线参数学习**：Python + PyMC，定期更新全局参数
- **对话系统**：树状存储会话（分区-领域-专题），支持分支和版本切换，通过事件与中枢节点同步

## 10. 初始化默认值（全）
- `belief.alpha / beta` = 2.0 / 2.0 → μ=0.5, precision=4.0
- `peak_proficiency` = 0.5
- `retrieval_prob` = 0.5, `latency_ms` = 5000
- `decayed_event_count` = 0
- `rapid_relearn_cooldown_until` = 0
- `trend.recent_proficiencies` = [], `velocity_ewma` = 0, `stagnation_days` = 0, `volatility_std` = 0, `direction` = "stable"
- `engagement.xp / streak / effort` = 0 / 0 / 0.5
- `diagnostic.administered` = false
- `composition` 跟踪器全部归零或 null
- `dialogue_contexts` = []
- 用户状态 `fatigue_level` = 0, `practice_count_this_session` = 0

## 11. 对话联动优势
- **精准的深度思考触发**：利用树状对话的上下文位置（上/下）和版本，可生成针对性回顾问题。
- **概念网络自生长**：对话中的关联解释可自动强化 `associates` 权值。
- **元认知校准**：通过对比对话中的自我评价与系统 proficiency，更新 `calibration_error`。

---

**CognitiveNode v2.10 已原生支持多分支对话树联动，所有模块协同无冲突，可直接指导完整的 AI 伴学系统开发。**
```