# 智能伴学系统 · 秘书系统 (Secretary) 最终设计实现方案

> **版本**: 2.0  
> **目标**: 构建一个独立、可扩展的“秘书系统”，承担学情诊断、协商提案、主动服务与模块化学习管理职责。通过与 Orchestrator、Tutor、Coach 松耦合协作，实现“懂克制、有温度”的伴学管家体验，并符合认知科学和学习科学原理。

---

## 目录

1. [设计总纲](#1-设计总纲)
2. [架构与模块](#2-架构与模块)
3. [领域模型](#3-领域模型)
4. [核心引擎设计](#4-核心引擎设计)
5. [扩展框架与内置模块](#5-扩展框架与内置模块)
6. [协作流程](#6-协作流程)
7. [API 设计](#7-api-设计)
8. [前端设计](#8-前端设计)
9. [认知科学合规与校准](#9-认知科学合规与校准)
10. [冷启动与数据稀疏处理](#10-冷启动与数据稀疏处理)
11. [隐私与伦理设计](#11-隐私与伦理设计)
12. [测试、监控与效果评估](#12-测试监控与效果评估)
13. [数据库设计](#13-数据库设计)
14. [实施路线图](#14-实施路线图)
15. [风险与对策](#15-风险与对策)
16. [附录：不足清单与改进记录](#16-附录不足清单与改进记录)

---

## 1. 设计总纲

### 1.1 定位

秘书系统是智能伴学平台的**数据洞察服务者、提案协商者与静默守护者**，不参与直接对话交互，所有用户可见内容经由 Orchestrator 委托 Tutor/Coach 呈现。

**四大铁律**:
1. **不直接发声** — 所有用户可见消息由 Tutor/Coach 转述。
2. **不替代决策** — 提供 2~3 个带理由的选项，由用户决定。
3. **不过度打扰** — 基于意图预测与打扰预算，仅在恰当窗口呈现。
4. **能力可插拔** — 统一扩展协议，用户自主启用/禁用功能模块。

### 1.2 核心价值

| 用户目标 | 秘书提供的支持 |
|---------|----------------|
| “我的学习状况怎么样？” | 薄弱点诊断、进步亮点、认知负荷提示 |
| “接下来该做什么？但我来决定” | 多选项提案、一键采纳、理由透明 |
| “在我没开口时，系统能做什么？” | 智能复习提醒、防疲劳建议、日简报 |
| “系统在后台悄悄为我做了什么？” | 错题预整理、关联知识预加载、自检清单 |
| “我如何掌控这个秘书？” | 模块开关、勿扰时段、每日上限、自定义规则 |

### 1.3 与现有系统关系

```text
用户 ↔ Orchestrator ↔ Tutor / Coach
            ↕
        秘书系统 (诊断+提案+主动服务)
            ↕
     分析洞察层 (analysis.py)    ← 替代"知识总线"
      → find_weakness_clusters / rank_forgetting_risk / assess_current_burden / ...
            ↕
     CognitiveNode / BKT / 知识图谱 / LearnerModel (原始数据层)
```

- 秘书通过**分析洞察层**访问学习数据，不直接耦合数据库实现。
- 分析层每个函数封装一个具体的教育洞察（find_weakness_clusters / rank_forgetting_risk 等），返回带归一化评分的统一结果。
- 通过**黑板 (Redis)** 与 Orchestrator 异步交换提案，不阻塞对话流。
- 通过**事件总线**感知学习行为，触发被动/主动分析。
- 通过**插件扩展**挂载学习管理能力，避免污染核心流程。

---

## 2. 架构与模块

### 2.1 新增文件结构

```backend/
├── app/core/
│   ├── blackboard.py             # Redis黑板
│   └── orchestrator.py           # 改造：增加秘书提案等待逻辑
├── domain/secretary/
│   ├── __init__.py
│   ├── secretary_service.py      # 主服务入口
│   ├── models.py                 # Pydantic模型 + ScoredInsight / AnalysisResult
│   ├── analysis.py               # 分析洞察层（18个分析函数，替代知识总线）
│   ├── proposal_store.py         # 提案持久化存储
│   ├── engines/
│   │   ├── module_registry.py            # 模块注册与生命周期管理
│   │   ├── active_checker.py             # 活跃检查与提案推送
│   │   ├── policy_engine.py              # 策略与规则引擎
│   │   ├── secretary_event_handler.py    # 事件处理（订阅事件总线）
│   │   ├── context_engine.py             # 情境与意图预测
│   │   ├── diagnosis.py                  # 诊断引擎（基于 analysis.py 结果）
│   │   ├── proposal_generator.py         # 提案生成 (LLM+模板)
│   │   ├── proposal_action_handler.py    # 提案采纳/忽略/暂缓处理
│   │   ├── secretary_plan_bridge.py      # 学习计划桥接
│   │   ├── llm_proposal_generator.py     # LLM 提案生成器
│   │   ├── builtin_review_reminder.py    # 复习提醒
│   │   ├── builtin_fatigue_manager.py    # 疲劳管理
│   │   ├── builtin_daily_brief.py        # 日简报生成
│   │   ├── exam_mode.py                  # 备考模式
│   │   ├── return_user_detection.py      # 回归用户检测
│   │   ├── meta_cognitive_prompt.py      # 元认知反思提示
│   │   └── silent_task.py                # 静默任务/后台记账
│   └── tasks.py                  # 定时主动检查
├── app/api/
│   └── secretary.py              # 秘书配置与提案API（含模块管理、数据导出等）
├── app/data/
│   └── secretary_prefs/          # 秘书偏好数据
└── app/services/
    └── context_builder.py        # 改造：增加secretary_proposals上下文层
```

### 2.2 核心交互组件

**分析洞察层** (`analysis.py`): 18 个分析函数，每个封装一个具体的教育洞察。直接调 `cognitive/storage.py`，不做抽象层包装。统一输入 `(user_id, ScopeSpec, AnalyzeOptions)`，统一返回 `AnalysisResult(ScoredInsight[])`。内部 SQL 层过滤 + 内存一次遍历聚合，无 N+1 查询。

**黑板** (`Blackboard`): 基于 Redis 的请求级共享上下文，键格式 `bb:secretary:{session_id}`，TTL 300 秒，用于传递提案和诊断摘要。

**事件总线** (已有): 秘书订阅 `UserMessageReceived`、`SessionEnded`、`ExerciseCompleted` 等事件，驱动诊断与情境更新。

**定时调度** (APScheduler): 每 10 分钟执行一次轻量主动检查，处理复习提醒、长期未练等低频事项，主要触发仍以事件驱动为主。

### 2.3 分析洞察层设计

分析层位于 `cognitive/storage.py`（原始数据）与秘书引擎之间，18 个函数每个封装一个具体的教育洞察。

**统一调用约定:**

```python
def analyze_xxx(
    user_id: str = "default_user",
    scope: ScopeSpec | None = None,
    options: AnalyzeOptions | None = None,
) -> AnalysisResult:
```

**ScopeSpec — 6 层范围控制:**

```python
class ScopeSpec(BaseModel):
    level: Literal["user", "partition", "domain", "topic", "concept", "atom"]
    node_id: str | None = None
```

**AnalyzeOptions — 统一参数:**

```python
class AnalyzeOptions(BaseModel):
    threshold: float = 0.6
    max_items: int = 10
    min_confidence: float = 0.0
    sort_by: Literal["urgency", "decline", "stagnation"] = "urgency"
    include_children: bool = False
    lookback_days: int = 7
    lookahead_hours: int = 24
```

**AnalysisResult — 统一返回:**

```python
class ScoredInsight(BaseModel):
    """带评分的洞察项"""
    node_id: str
    label: str
    level: str
    primary_value: float
    primary_label: str
    norm_urgency: float             # 归一化紧迫度 (0-1)
    norm_priority: float            # 归一化优先级 (0-1)
    confidence: float               # 置信度 (0-1)
    data_points: int                # 涉及数据点数量

class AnalysisResult(BaseModel):
    analysis_type: str
    meta: AnalysisMeta
    items: list[ScoredInsight]
    summary: str
    top_priority: str | None
```

**归一化映射:**

| 原始值类型 | 归一化逻辑 | 示例 |
|-----------|----------|:----:|
| proficiency | `1.0 - raw` | 掌握度 0.3 → 紧迫 0.7 |
| stagnation_days | `min(raw/14, 1.0)` | 停滞 7d → 0.5, 14d → 1.0 |
| forgetting_risk | `raw * 1.2` | 遗忘风险 0.7 → 0.84 |
| cognitive_load | `max(0, (raw-0.5)*2)` | 负荷 0.9 → 0.8 |
| error_frequency | `raw` | 直接映射 |

**完整分析函数清单 (18 个，覆盖率 89%):**

| 类别 | 函数名 | 产出 | 消费方 |
|:---:|--------|------|:------:|
| 薄弱诊断 | `find_weakness_clusters` | 薄弱概念簇 (parent+子节点聚合) | 诊断引擎 |
| | `detect_stagnant_topics` | 长期停滞知识点 | 诊断引擎 |
| | `trace_proficiency_regression` | 掌握度退步追踪 | 诊断引擎+简报 |
| 认知评估 | `assess_current_burden` | 当前认知负荷 | 疲劳管理 |
| | `predict_fatigue_risk` | 疲劳风险预测 | 疲劳管理 |
| 遗忘风险 | `rank_forgetting_risk` | 遗忘概率排序 | 复习提醒 |
| | `predict_optimal_review` | 最优复习时机 | 复习提醒+提案 |
| | `find_overdue_reviews` | 过期复习项 | 复习提醒 |
| 错误分析 | `analyze_error_patterns` | 错误模式聚类 | 诊断引擎 |
| 进展画像 | `compute_progress_delta` | 进步量化 (前后对比) | 简报 |
| | `profile_learning_rhythm` | 学习节奏画像 | 画像+简报 |
| 推荐排序 | `rank_recommendations` | 多因素融合推荐 | 提案生成器 |
| 跨域关联 | `find_cross_domain_bridges` | 薄弱→优势跨域连接 | 提案生成器 |
| 元认知 | `detect_calibration_mismatch` | 过度自信/不足检测 | 诊断引擎 |
| 目标对齐 | `assess_goal_distance` | 与目标差距评估 | 提案生成器 |
| 预测偏差 | `detect_prediction_divergence` | 预期vs实际偏差 | 诊断引擎 |
| 路径推荐 | `suggest_learning_path_step` | 下一步最优路径 | 提案生成器 |
| 对话上下文 | `extract_recent_context` | 近期讨论摘要 | 情境引擎 |

**内部实现原则:**
1. SQL 层优先过滤（`WHERE level='atom' AND belief->>'proficiency_mean' < 0.6`）
2. 内存一次遍历完成分组+聚合（不产生 N+1）
3. 空数据 / 冷启动时返回 `data_quality="cold_start"`，引擎降级

---

## 3. 领域模型

### 3.1 诊断报告

```python
class WeakPoint(BaseModel):
    knowledge_point_id: str
    name: str
    mastery: float                # 0-1, BKT概率
    error_pattern: str            # "公式混淆", "概念不清", "计算错误", "条件遗漏"
    trend: str                    # "下降", "稳定", "上升"

class DiagnosisReport(BaseModel):
    user_id: str
    snapshot_id: str
    generated_at: datetime
    weak_points: List[WeakPoint]
    cognitive_load: float
    highlight: str                # LLM生成的进步亮点描述
    summary: str                  # 整体诊断文本 (1-2句)
    positive_attribution: str     # 积极归因解释 (用于简报)
```

### 3.2 提案

```python
class Proposal(BaseModel):
    id: str
    emoji: str
    title: str
    description: str
    action_type: str              # review / practice / rest / explore / exam_prep
    payload: dict                 # { "kp_id":..., "num_questions":... }
    priority: int                 # 1-5, 1最高
    generated_by: str             # 来源模块名
    overrideable: bool = True     # Orchestrator是否可因用户意图跳过
    meta_reflection_prompt: Optional[str] = None  # 自我评估提示
    created_at: datetime
    expires_at: datetime
```

### 3.3 用户情境

```python
class UserContext(BaseModel):
    user_id: str
    current_session_active: bool
    last_active_at: datetime
    cognitive_load_estimate: float
    is_quiet_hours: bool
    predicted_intent: Optional[str]  # "submitting", "idle", "reviewing"
    interaction_preferences: dict    # 历史互动偏好 (语气/风格)
```

### 3.4 静默任务

```python
class SilentTask(BaseModel):
    id: str
    task_type: str                # prepare_review_list, fetch_related_video, pre_generate_quiz
    payload: dict
    ready_at: datetime
```

### 3.5 用户偏好设置

存储在 `user_data.secretary_prefs` (JSONB)：

```json
{
  "enabled_extensions": ["review_reminder", "fatigue_manager", "daily_brief"],
  "quiet_hours": {"start": "22:00", "end": "08:00"},
  "max_proactive_per_day": 5,
  "custom_rules": [
    {"trigger_nl": "当我连续3天不复习高数", "action": "提醒复习高数", "parsed": {...}}
  ],
  "privacy_settings": {
    "calendar_enabled": false,
    "device_activity_enabled": false
  }
}
```

---

## 4. 核心引擎设计

### 4.1 诊断引擎 (`DiagnosisEngine`)

- **输入**: 用户 ID + 可选 ScopeSpec
- **输出**: 综合诊断报告（基于分析层多个函数结果融合）
- **逻辑**:
  1. 调用 `find_weakness_clusters()` 获取薄弱知识点簇。
  2. 调用 `detect_stagnant_topics()` 获取停滞知识点。
  3. 调用 `trace_proficiency_regression()` 获取退步追踪。
  4. 调用 `assess_current_burden()` 获取认知负荷评估。
  5. 调用 `detect_calibration_mismatch()` 获取元认知偏差。
  6. 调用 `detect_prediction_divergence()` 获取预期偏差。
  7. 多结果融合：去重 + 优先级归一化排序（使用各函数返回的 `norm_urgency`）。
  8. 调用 LLM 生成 `highlight` (正面进步) 和 `summary` (整体诊断，含积极归因)。
- **认知科学校准**: 每个 `summary` 必须包含积极归因线索，例如"虽然极限部分有波动，但这属于正常学习曲线，上周你已经打下了基础"。

### 4.2 提案生成器 (`ProposalGenerator`)

- **核心策略**: **模板优先 + LLM 润色**，保证稳定性和低成本。
  1. 规则引擎先根据诊断生成结构化提案模板：`{emoji, title_template, description_template, action_type, payload}`。
  2. 对需要自然语言的部分（标题/描述），调用轻量 LLM 润色，注入协商语气。
  3. 如果 LLM 不可用或超时，直接使用模板，并标记为“自动生成”。
- **苏格拉底式选项**: 始终生成 2~3 个选项，每个附带简短理由。
- **自我评估注入**: 对于薄弱点相关提案，自动附加 `meta_reflection_prompt`： “你觉得这里最难的是什么？A.公式记不住 B.不知道该用哪个定理 C.计算易错”。

### 4.3 情境与意图引擎 (`ContextEngine`)

- **输入**: 用户 ID
- **输出**: `UserContext`
- **情境感知数据源** (全部 opt-in):
  - 日历事件 (未来考试、会议)
  - 设备当前活动状态 (仅判断活跃/闲置，不上传具体行为)
  - 当前时间与勿扰时段匹配
- **意图预测**: 基于最近 5 个行为事件进行简单模式匹配：
  - `[做题, 做题, 打开笔记]` → `submitting`
  - `[连续5分钟无操作]` → `idle`
  - 其它 → `learning`
- **互动偏好学习**: 记录用户对不同语气、不同类型提案的历史响应，存入 `interaction_preferences`，供提案生成时参考。

### 4.4 策略引擎 (`PolicyEngine`)

- **过滤规则**:
  - 勿扰时段内，仅保留 `priority=1` 的紧急提案。
  - 去重：相同 `action_type + kp_id` 合并。
  - 每日主动提醒上限（从用户设置读取，默认5）。
  - 提案按优先级和时间排序。
- **Orchestrator 否决权**: 若用户在对话中明确表达相反意图，Orchestrator 可标记对应提案为“本轮跳过”。
- **关系记忆**: 同一用户连续 3 次忽略同类提案，该类型提案优先级自动降一级。

---

## 5. 扩展框架与内置模块

### 5.1 扩展基类

```python
class SecretaryExtension(ABC):
    name: str
    description: str

    async def on_diagnosis(self, diag: DiagnosisReport, ctx: UserContext) -> None: pass
    async def on_proposals(self, diag: DiagnosisReport, ctx: UserContext) -> List[Proposal]: return []
    async def on_silent_task(self, ctx: UserContext) -> Optional[SilentTask]: return None
    async def on_proactive(self, ctx: UserContext) -> Optional[Proposal]: return None
```

所有内置模块均为无状态、无相互依赖。

### 5.2 内置模块

| 模块 | 触发 | 功能 |
|------|------|------|
| **复习提醒** | 诊断报告 + 遗忘概率 > 0.4 | 生成复习提案，解释时机合理性 |
| **疲劳管理** | 认知负荷 > 0.8 或连续学习 > 50min | 建议休息/换科 |
| **日简报** | 每日首次打开 | 生成昨日总结，含积极归因和自我解释提示 |
| **备考模式** | 日历中有考试事件 (需 opt-in) | 提升相关知识点优先级，生成冲刺清单 |
| **冷启动引导** | 新用户，数据不足 | 主动发起"学习风格初探"对话，生成初始策略包 |
| **回归用户检测** | 超过 5 天未登录 | 检测用户回归，生成欢迎回提案（基于文件跟踪 `data/secretary/last_active_{user_id}.json`） |
| **元认知反思** | 活跃会话（5min+ / 3+ 问题） | 生成 8 种元认知反思提示，引导学生自我评估学习策略 |
| **静默任务** | 定时周期 | 后台记账与内部状态维护，零提案产出（跟踪已用时间、检查次数） |

### 5.3 模块生命周期

- 通过用户设置 `secretary_prefs.enabled_extensions` 动态加载。
- 模块启用/禁用实时生效，无需重启。

---

## 6. 协作流程

### 6.1 对话回合中的被动提案

```
用户消息 → Orchestrator 接管
    ↘ 秘书异步: 情境获取 → 诊断 → 提案生成 → 策略过滤 → 写入黑板 (bb:secretary:{session_id})
Orchestrator 在回复前: 等待黑板数据 (超时 1s)
    → 若有提案，格式化后注入 LLM 系统上下文
    → Tutor 以协商口吻呈现提案，附加 contentBlock "secretary_suggestions"
```

### 6.2 主动检查流程

```
定时任务 (每10分钟):
  for 活跃用户:
    情境快照 → 各扩展 on_proactive
    → 生成提案 → 持久化 → WebSocket 推送红点
```

### 6.3 用户采纳提案

```
用户点击提案卡片 → POST /secretary/proposals/{id}/accept
  → 后端标记状态，返回 action payload (如跳转练习)
  → 前端执行对应跳转或启动对话指令
```

### 6.4 静默任务

基于意图预测触发，如预测用户即将提交练习：
- 秘书生成 `SilentTask(prepare_review_list, ...)`，后台整理错题集存入缓存。
- 检测到用户提交练习后，Coach 自然发起：“我顺便帮你整理了这次暴露的薄弱点，要看看吗？”

---

## 7. API 设计

所有端点需登录认证，从 JWT 中提取 `user_id`。

| 方法 | 路径 | 描述 |
|------|------|------|
| GET | `/secretary/preferences` | 获取当前用户秘书偏好 |
| PATCH | `/secretary/preferences` | 更新偏好 (勿扰/上限/扩展等) |
| GET | `/secretary/modules` | 获取所有模块列表及状态 |
| POST | `/secretary/modules/toggle` | 启用/禁用指定模块 |
| GET | `/secretary/proposals/pending` | 获取待处理提案列表 |
| POST | `/secretary/proposals/{id}/accept` | 采纳提案 |
| POST | `/secretary/proposals/{id}/dismiss` | 忽略提案 |
| POST | `/secretary/proposals/{id}/snooze` | 暂缓提案 (传入分钟数) |
| GET | `/secretary/proposals/history?days=7` | 近期提案历史 |
| GET | `/secretary/snapshot` | 当前学习快照摘要 (供面板) |
| GET | `/secretary/daily-brief` | 今日简报 |
| POST | `/secretary/generate-llm-proposals` | 手动触发 LLM 提案生成 |
| GET | `/secretary/onboarding` | 获取冷启动引导状态与内容 |
| POST | `/secretary/onboarding/dialogue` | 冷启动对话交互 |
| GET | `/secretary/data/export` | 导出所有秘书相关个人数据 |
| DELETE | `/secretary/data/delete` | 删除所有秘书相关个人数据 (遗忘权) |

---

## 8. 前端设计

### 8.1 秘书页面布局 (单列信息流)

```
┌─────────────────────────────────────┐
│ 问候 + 今日摘要卡片 (含积极归因)     │
├─────────────────────────────────────┤
│ 📋 待处理建议                        │
│ 卡片堆叠: 优先级色条 | emoji+标题 | 理由 | [执行][稍后][忽略] |
│ 空状态: "今天节奏很好，秘书保持静默"  │
├─────────────────────────────────────┤
│ 📊 学习状态速览 (可折叠)             │
│ 薄弱点 / 掌握度 / 趋势               │
│ [查看完整报告]                       │
├─────────────────────────────────────┤
│ 🕒 近期活动 (时间线 5条)             │
├─────────────────────────────────────┤
│ ⚙️ 秘书偏好 (折叠区)                │
│ 模块开关 / 勿扰 / 上限 / 自定义规则   │
│ 隐私设置 / 数据导出                  │
└─────────────────────────────────────┘
```

### 8.2 对话中的提案卡片

- `MessageList` 新增 `contentBlock: "secretary_suggestions"`，渲染为水平选项卡片。
- 点击卡片发送隐式指令 `/accept_proposal {id}`，直接跳转对应页面。

### 8.3 全局通知

- 导航栏铃铛图标仅显示红点，不弹窗，点击跳转秘书页。
- 新提案通过 WebSocket 推送轻量事件更新红点。

---

## 9. 认知科学合规与校准

| 认知原则 | 设计实现 | 状态 |
|---------|----------|:---:|
| 自我决定论 (自主感) | 多选项提案，用户决策 | ✅ |
| 自我效能感 | 进步亮点 + 具体正向反馈 | ✅ |
| 认知负荷理论 | 负荷感知 + 休息建议 | ✅ |
| 精细错误分析 | 错误模式归类 | ✅ |
| 成长型思维保护 | 日简报含积极归因，附自我解释提示 | ✅ |
| 间隔重复最优时机 | 复习提醒基于 BKT 遗忘概率而非固定天数 | ✅ |
| 必要难度 | 静默准备内容不直接呈现，先要求学生回忆 | ✅ |
| 元认知训练 | 提案附自我评估问题，引导学生反思 | ✅ |

---

## 10. 冷启动与数据稀疏处理

- **新用户引导**:
  1. 首次进入秘书页，显示数据收集进度条与预计生成首份诊断的时间。
  2. 主动发起“学习风格初探”对话 (Coach 驱动，秘书在后台记录偏好)。
  3. 基于年级/学科/目标提供初始通用学习策略包，标注“基于你的学习阶段推荐”。
- **间歇用户回归**:
  - 检测到超过 5 天未登录，秘书自动准备“回归总结”——空白期回顾与快速恢复路径。
  - 回归对话由 Coach 发起，秘书提供数据支持。

---

## 11. 隐私与伦理设计

- **数据采集**: 情境感知所有高级能力 (日历、设备活动) 均需用户显式 opt-in，默认关闭。
- **端侧处理**: 认知负荷等指标尽量在本地计算，仅上传脱敏后的聚合值。
- **数据权利**: 提供完整的数据导出和删除端点 (`/secretary/data/export`, `/delete`)。
- **学习自主权守护**: 若用户连续拒绝提案 (5次)，秘书切换策略：暂停推送，触发 Coach 发起纯关怀对话。
- **透明度**: 每条提案均可展开查看决策链日志 (数据源、规则触发、LLM原始输出)。

---

## 12. 测试、监控与效果评估

- **决策链日志**: 每个提案记录完整生成路径，支持调试面板 (`/admin/secretary/logs`)。
- **用户反馈闭环**: 每个提案卡片提供“不相关”按钮，反馈数据回流至日志。
- **A/B 测试框架**: 预留实验分组字段，可针对提案策略、语气、频率做对照实验。
- **关键指标**:
  - 过程: 提案采纳率、点击完成率、主动提醒响应率
  - 结果: 知识掌握度提升速度、学习时长一致性、用户留存率

---

## 13. 数据库设计

### 13.1 `secretary_proposals` 表

```sql
CREATE TABLE secretary_proposals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    proposal JSONB NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',   -- pending, accepted, dismissed, snoozed, expired
    decision_log JSONB,                              -- 完整决策链日志
    created_at TIMESTAMPTZ DEFAULT now(),
    accepted_at TIMESTAMPTZ,
    dismissed_at TIMESTAMPTZ,
    expires_at TIMESTAMPTZ
);
CREATE INDEX idx_sp_user_status ON secretary_proposals(user_id, status);
```

### 13.2 用户设置扩展

在 `user_data` (或等价表) 的 `metadata` JSONB 字段中增加 `secretary_prefs` (见前述模型)。

### 13.3 黑板数据 (Redis)

键前缀 `bb:secretary:{session_id}`，值：`{"status":"ready","proposals":[...]}`, TTL 300秒。

---

## 14. 实施路线图

| 阶段 | 内容 | 依赖 | 预计工作量 | 完成状态 |
|------|------|------|:---:|:---:|
| **Phase 7.1** | 分析层 (analysis.py) + 黑板 + 诊断引擎 + 模板提案 + Orchestrator 集成 + 前端提案卡片 | 依赖 CognitiveNode 存储 | 5-7天 | ✅ 已完成 |
| **Phase 7.2** | LLM 提案生成器 + 协商对话流程 + 秘书页基础 UI (列表+历史) | LLM Service | 5-7天 | ✅ 已完成 |
| **Phase 7.3** | 情境引擎 + 主动检查定时任务 + 提案持久化与 WebSocket 通知 | Redis, 事件总线 | 3-5天 | ✅ 已完成 |
| **Phase 7.4** | 扩展框架 + 内置模块 (复习提醒/疲劳/简报) + 秘书设置页 + 冷启动引导 | 前端设置组件 | 5-7天 | ✅ 已完成 |
| **Phase 7.5** | 自然语言自定义规则、静默任务、备考模式、决策链日志、A/B框架 | 规则解析LLM | 5-7天 | ⚠️ 部分完成（静默任务、备考模式 ✅；自然语言规则、决策链日志面板、A/B框架待补） |
| **Phase 7.6** | 认知科学微调 (自我评估提示、积极归因、必要难度保留) + 隐私/伦理完善 | 全栈 | 3-5天 | ⚠️ 部分完成（元认知提示 ✅；认知科学微调持续优化中） |

---

## 15. 风险与对策

| 风险 | 对策 |
|------|------|
| LLM 生成提案不稳定 | 模板回退，规则兜底，输出校验 |
| 主动提醒过频 | 每日上限 + 勿扰时段 + 一键关闭 |
| CognitiveNode 数据延迟 | 秘书软依赖，无数据时降级为通用鼓励 |
| 黑板超时/并发脏读 | Redis TTL + Orchestrator 超时跳过 |
| 用户隐私担忧 | 高级感知全 opt-in，端侧处理，数据可删除 |
| 新用户冷启动无建议 | 通用策略包 + 数据收集进度条 + 主动引导对话 |

---

## 16. 附录：不足清单与改进记录

以下为设计过程中识别出的全部不足及本方案的应对措施：

| # | 不足 | 严重度 | 解决方案 |
|---|------|:---:|------|
| 1 | 新用户冷启动支持缺失 | 高 | 冷启动引导模块、通用策略包、进度条 |
| 2 | 情境感知隐私授权不明确 | 高 | 全 opt-in，端侧处理，数据导出/删除 |
| 3 | 日简报缺少积极归因 | 高 | `positive_attribution` 字段，LLM生成 |
| 4 | 静默准备破坏必要难度 | 中 | 先提问再展示，生成式学习策略 |
| 5 | 复习提醒未用遗忘曲线 | 中 | 触发条件改为 BKT 遗忘概率 > 0.4 |
| 6 | 缺少元认知自我评估提示 | 中 | 提案附带 `meta_reflection_prompt` |
| 7 | 关系记忆缺失 | 中 | `interaction_preferences` 学习用户偏好 |
| 8 | 沉默不可解释 | 低 | 空状态显示判断依据 |
| 9 | 自主权守护缺失 | 中 | 连续拒绝5次切换关怀策略 |
| 10 | 秘书/Coach 角色冲突 | 中 | Orchestrator 协调规则，情感时段提案延迟 |
| 11 | Orchestrator 否决权规则 | 中 | `overrideable` 字段 + 意图匹配 |
| 12 | 调试与审计能力缺失 | 中 | 决策链日志 + 管理面板 |
| 13 | 效果评估/A/B 框架缺失 | 中 | 指标定义 + 实验分组预留 |
| 14 | 前端提案卡片未集成 (G4) | 低 | 已解决 — SecretarySuggestionsBlock + accepting API |
| 15 | 铃铛红点缺失 (G4) | 低 | 已解决 — SecretaryBellBadge 60s polling |
| 16 | 回归用户检测缺失 (G5) | 中 | 已解决 — return_user_detection module |
| 17 | 隐私数据导出/删除 (G3) | 中 | 已解决 — /data/export + /data/delete |

---

**文档状态**: 实现跟进 v2.0。核心架构与引擎已落地，内置模块持续扩展中。Phase 7.1-7.4 全部完成，7.5-7.6 部分完成，剩余项（自然语言规则、决策链日志面板、A/B框架、认知科学深度微调）持续迭代中。