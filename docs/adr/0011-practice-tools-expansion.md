# ADR 0011: 练习系统对外工具扩充计划

> 日期: 2026-06-15 | 状态: Proposed
> Round 2 Step 3 — 出题 + 秘书规划 + 题目分析 三大方向扩充

---

## 一、出题能力扩充 (7 项)

### Q1. 去学科模板, AI 自分析

**当前**: `QuestionGenerator.TEMPLATES` 硬编码 7 个学科知识模板 (calculus_limit/derivative/integral/linear_matrix/determinant/probability/physics_mechanics).

**决定**: 砍 TEMPLATES dict. `generate()` 中将 `subject + skill_id` 直接拼接为 LLM prompt "请输出关于{subject}中{skill_id}的知识要点", 让 LLM 自生成知识点说明.

影响范围: `question_generator.py` 的 `TEMPLATES` 删除 + `generate()` 的 `knowledge_ctx` 构建逻辑改为 LLM 动态生成.

### Q2. 题干变体引擎

**新增**: 基于已有题生成 N 个变体 (不改知识结构, 只换数值/情景/问法).

```python
async def generate_variants(
    question_id: str,
    user_id: str,
    count: int = 3,
    variation_axis: list[str] = ["number", "scenario", "complexity"],
) -> list[dict]:
    """生成变体: 沿指定维度变化"""
```

流程: 取原题 → LLM 按变化轴生成 → 保存到同题库 → 返回.

### Q3. 多步推理题

**新增**: 支持生成推理链题型 (子问题递进).

```python
async def generate_reasoning_chain(
    bank_id: str,
    user_id: str,
    skill_id: str,
    steps: int = 3,
    subject: str = "数学",
) -> dict:
    """生成多步推理链, 返回 {chain_id, steps: [{step, hint}, ...]}"""
```

每步一个题目, 前一步的答案作为后一步的前提. 链作为一个 group 保存.

### Q4. 组卷: 混合来源

**新增**: 组卷 API 支持从多种来源按比例选题.

```python
async def compose_exam(
    user_id: str,
    bank_id: str,
    total_count: int = 20,
    sources: list[dict] = [
        {"type": "bank", "ratio": 0.4},      # 题库已有题
        {"type": "error", "ratio": 0.2},     # 错题本
        {"type": "variant", "ratio": 0.2},   # 变体
        {"type": "new", "ratio": 0.2},       # AI 新生成
    ],
    knowledge_distribution: list[dict] = [],  # [{"skill_id": "...", "ratio": 0.3}, ...]
    difficulty: dict = {"easy": 0.3, "mid": 0.5, "hard": 0.2},
) -> dict:
    """按比例组卷"""
```

API 端点: `POST /api/v7/practice/exam/compose`

### Q5. 用户画像感知

**当前**: difficulty/bloom_level 固定传参.

**新增**: `generate_with_profile()` 自动查询用户历史正确率:

```python
async def generate_with_profile(
    user_id: str,
    bank_id: str,
    skill_id: str,
    count: int = 3,
) -> list[dict]:
    """根据用户画像自动调难度:
    - 该知识点历史正确率 < 40% → difficulty 0.4 (降难度打基础)
    - 历史正确率 > 80% → difficulty 0.7 (提难度保持挑战)
    - Bloom 层次也根据掌握度提升: remember→understand→apply→analyze
    """
```

### Q6. 结构化输出校验

**当前**: `_parse_llm_response()` 脆弱的三段降级 (直接解析→代码块→正则), 出错的题静默丢弃.

**新增**: Pydantic 校验链:

```python
from pydantic import BaseModel, Field, field_validator

class GeneratedQuestion(BaseModel):
    text: str = Field(..., min_length=5)
    options: list[GeneratedOption] = Field(..., min_length=2)
    explanation: str = Field(..., min_length=10)
    hints: list[str] = Field(default_factory=list, max_length=5)
    difficulty: float = Field(..., ge=0.1, le=1.0)
    bloom_level: str = Field(...)

    @field_validator("bloom_level")
    @classmethod
    def validate_bloom(cls, v):
        allowed = {"remember","understand","apply","analyze","evaluate","create"}
        if v.lower() not in allowed:
            raise ValueError(f"invalid bloom: {v}")
        return v.lower()

    @field_validator("options")
    @classmethod
    def has_correct(cls, v):
        if not any(o.is_correct for o in v):
            raise ValueError("no correct option")
        return v
```

校验失败 → 自动重试 1 次 (temperature=0.3). 重试仍失败 → 记录日志, 不返回.

### Q7. 错题→相似题变体

**当前**: `generate_similar()` 只传原题文本, 不传错因.

**新增**: 错题变体入口:

```python
async def generate_similar_from_error(
    attempt_id: str,
    user_id: str,
    count: int = 3,
) -> list[dict]:
    """取 practice_attempts 的错因分析 → 定向生成:
    - error_type="概念混淆" → 生成概念辨析题
    - error_type="计算失误" → 生成同类计算但简单数值
    - error_type="审题不清" → 生成更清晰分步题
    """
```

---

## 二、秘书规划扩充 (6 项)

### S1. 练习计划提案

**新增**: 周/月级别计划进度追踪.

```python
def check_plan_progress(user_id: str) -> Optional[Proposal]:
    """检查用户练习计划执行情况:
    - 本周目标: 30 题 → 已完成 12 题 → 进度 40%
    - 如果进度 < 60% 且 本周过了一半 → 发提醒
    """
```

action_type: `practice_plan_progress`

### S2. 薄弱点定向推荐

**当前**: 秘书只说"你错了 N 题", 不主动推练习.

**新增**:

```python
def check_weak_point_recommendation(user_id: str) -> Optional[Proposal]:
    """识别薄弱知识点 → 推荐专项练:
    - 查 cognitive_links 列出所有 skill + 正确率
    - 排序取最差的 1-2 个
    - 提案含直达链接: "去练 '{skill}' (5道)"
    """
```

action_type: `practice_weak_recommend`

### S3. 跨会话趋势分析

```python
def check_trend_analysis(user_id: str) -> Optional[Proposal]:
    """过去 7 天:
    - 各知识点正确率趋势 (上升/下降/平稳)
    - 用时趋势 (越来越慢? 越来越快?)
    - 如果某个知识点 7 天内正确率从 60% 降到 30% → 预警
    """
```

action_type: `practice_trend_alert`

### S4. 学习节奏顾问

```python
def check_pacing_advice(user_id: str) -> Optional[Proposal]:
    """分析:
    - 平均每日练习量 vs 目标
    - 练习间隔 > 3 天 → "好久没练了"
    - 一天内连续练 > 2 小时 → "休息一下, 间隔学习效果更好"
    """
```

action_type: `practice_pacing_advice`

### S5. 错因模式识别

```python
def check_error_pattern(user_id: str) -> Optional[Proposal]:
    """分析最近 20 道错题的 error_type 分布:
    - 如果某类错因占比 > 40% → "你在{错因类型}上比较集中"
    - 附带具体建议:
      "计算失误" → "建议放慢速度, 每步检查"
      "概念混淆" → "建议先复习再做题"
    """
```

action_type: `practice_error_pattern`

### S6. 考前冲刺规划

```python
def check_exam_prep(user_id: str, exam_date: str, skill_ids: list[str]) -> Proposal:
    """考试倒计时:
    - 距考试 N 天
    - 规划每天练 |skill|/|days_remaining| 道题
    - 按 Bloom 层次: 先覆盖 remember/understand, 最后练 apply/analyze
    """
```

action_type: `practice_exam_prep`

---

## 三、题目分析扩充 (10 项)

### A1. 选项级错因标记

**当前**: `QuestionOption.distractor_type` 存在于 Pydantic, 但不用于判题.

**新增**: 提交答案时, 如果答错且选了含 `distractor_type` 的选项, 直接记录到 `practice_attempts.error_analysis`:

```python
def record_distractor_analysis(attempt: dict, selected_option: dict):
    if selected_option.get("distractor_type"):
        attempt["error_analysis"]["distractor_type"] = selected_option["distractor_type"]
```

### A2. LLM 错因分析

**当前**: `classify_error()` 仅基于 question_type/difficulty 做 if-else.

**新增**: 答错时异步调 LLM 分析:

```python
async def llm_error_analysis(question: dict, user_answer: list, correct_answer: list) -> dict:
    """LLM 分析: 为什么错? 缺什么知识? 建议什么?
    返回: {
        "error_type": "concept_confusion",
        "misconception": "混淆了导数和极限的定义",
        "suggestion": "建议回顾极限的 ε-δ 定义",
        "related_knowledge": ["..."]
    }
    """
```

不需要阻塞答题流程, 异步写入 `practice_attempts.error_analysis`.

### A3. 错因模式聚类

```python
def cluster_error_patterns(user_id: str) -> dict[str, float]:
    """统计该用户所有错题的 error_type 占比:
    {"概念混淆": 0.4, "计算失误": 0.3, "审题不清": 0.2, "粗心大意": 0.1}
    """
```

供秘书提案 S5 消费.

### A4. 技能×错因热图

```python
def get_error_heatmap(user_id: str) -> list[dict]:
    """返回 [{skill, skill_label, error_type, count, ratio}]
    前端可渲染为热力图矩阵: 行=知识点, 列=错因类型
    """
```

### A5. 审题时间异常检测

```python
def detect_time_anomaly(attempt: dict, user_stats: dict) -> Optional[str]:
    """对比该题用户用时 vs 用户平均用时:
    - 用时 > 2x avg BUT 答错 → "卡住了 / 缺少思路"
    - 用时 < 0.5x avg BUT 答错 → "粗心 / 审题不清"
    - 正常 BUT 答错 → "概念问题"
    """
```

### A6. 知识点关联分析

```python
def analyze_prerequisite_weakness(user_id: str) -> list[dict]:
    """通过 cognitive_links(link_type='prerequisite') 检测:
    - 如果"极限"掌握度低 → "导数"也低 → 根源在极限
    - 建议先补前置知识点
    """
```

### A7. 练习趋势 + 意图推断

```python
def infer_practice_intent(user_id: str) -> dict:
    """分析最近 7 天的练习行为:
    - 集中在某几个技能? → 可能在学某章
    - 最近开始大量练题? → 可能在备考
    - 正确率突然下降? → 内容难度跳跃
    """
```

### A8. 题目质量分析

```python
def analyze_question_quality(question_id: str) -> dict:
    """分析该题被答了 N 次后的指标:
    - 正确率 (过高 >90% → 太简单, 过低 <20% → 太难)
    - 区分度 (高分组正确率 - 低分组正确率, <0.2 说明题不好)
    - 选项分析 (是否有选项无人选 = 干扰项无效)
    """
```

### A9. 文件引用级分析

```python
def get_error_material_context(attempt: dict) -> Optional[str]:
    """从 cognitive_links 找到题目关联的 material_chunk:
    - "这道题来自你上传的《高等数学》第三章, 建议重看第 3.2 节"
    - 在秘书提案中嵌入
    """
```

### A10. 文件参照灵活度

**新增概念**: 练习各工具 (出题/判题/分析) 增加 `file_ref_mode` 参数:

| 模式 | 语义 | 用途 |
|------|------|------|
| `inspiration` | 灵感参考 | AI 根据文件风格出题, 但不要求严格一致 |
| `general` | 一般参考 | 出题知识点对齐文件, 但题目情景可换 |
| `strict` | 严格参照 | 题目必须基于文件内容, 答案来自文件原文 |

```python
# 示例: 出题时
file_ref_mode = "strict"
material_context = await get_material_context(ids, user_id)
# strict 模式: material_context 注入温度 0.3, prompt 强调"请基于以上资料内容出题"
# inspiration 模式: 温度 0.7, prompt 强调"参考以上资料风格, 适当发挥"
```

影响: `generate_and_save()` / `handle_question_generation()` 增加 `file_ref_mode` 参数.

---

## 实现优先级建议

| 优先级 | 方向 | 项 | 依赖 |
|--------|------|----|------|
| P0 | 出题 Q6 | 结构化输出校验 | 无, 改 `question_generator.py` |
| P0 | 分析 A2 | LLM 错因分析 | 无 |
| P0 | 分析 A5 | 时间异常检测 | 无 |
| P1 | 出题 Q1 | 去学科模板 | Q6 完成后 |
| P1 | 出题 Q7 | 错题→相似变体 | A2 (需要错因分析输出) |
| P1 | 秘书 S5 | 错因模式识别 | A3 (需要聚类) |
| P1 | 分析 A1 | 选项级错因标记 | 无 |
| P2 | 出题 Q2/Q5 | 变体引擎 + 画像感知 | 认知节点稳定后 |
| P2 | 秘书 S1/S2/S4 | 计划/推荐/节奏 | P0-1 完成后 |
| P2 | 分析 A4/A6 | 热图 + 关联分析 | P0-1 完成后 |
| P3 | 出题 Q3/Q4 | 多步推理 + 组卷 | 基础设施稳定后 |
| P3 | 秘书 S3/S6 | 趋势/考前 | 需更多数据积累 |
| P3 | 分析 A7/A8 | 意图推断 + 题目质量 | 需足够答题量 |
| P3 | 分析 A9/A10 | 文件引用 + 参照模式 | 文件系统就绪后 |

---

## 对接现有接口

### 新增 Protocol 方法

```python
# 出题
async generate_variants(question_id, user_id, count, variation_axis) → list[dict]
async generate_reasoning_chain(bank_id, user_id, skill_id, steps) → dict
async compose_exam(user_id, bank_id, total_count, sources) → dict
async generate_with_profile(user_id, bank_id, skill_id, count) → list[dict]
async generate_similar_from_error(attempt_id, user_id, count) → list[dict]
```

```python
# 秘书
async check_plan_progress(user_id) → Optional[Proposal]
async check_weak_point_recommendation(user_id) → Optional[Proposal]
async check_trend_analysis(user_id) → Optional[Proposal]
async check_pacing_advice(user_id) → Optional[Proposal]
async check_error_pattern(user_id) → Optional[Proposal]
async check_exam_prep(user_id, exam_date, skill_ids) → Proposal
```

```python
# 分析
async llm_error_analysis(question, user_answer, correct_answer) → dict
def cluster_error_patterns(user_id) → dict[str, float]
def get_error_heatmap(user_id) → list[dict]
def detect_time_anomaly(attempt, user_stats) → Optional[str]
def analyze_prerequisite_weakness(user_id) → list[dict]
def infer_practice_intent(user_id) → dict
def analyze_question_quality(question_id) → dict
def get_error_material_context(attempt) → Optional[str]
```

### 新增 API 端点

| 方法 | 路径 | 对应的扩充 |
|------|------|-----------|
| POST | `/api/v7/practice/generate/variants` | Q2 变体 |
| POST | `/api/v7/practice/generate/chain` | Q3 多步推理 |
| POST | `/api/v7/practice/exam/compose` | Q4 组卷 |
| POST | `/api/v7/practice/generate/profile` | Q5 画像感知 |
| POST | `/api/v7/practice/generate/similar-from-error` | Q7 错题变体 |
| GET | `/api/v7/practice/analysis/error-patterns` | A3 错因聚类 |
| GET | `/api/v7/practice/analysis/heatmap` | A4 热图 |
| GET | `/api/v7/practice/analysis/question-quality/{id}` | A8 题目质量 |
| GET | `/api/v7/practice/analysis/prerequisites` | A6 关联分析 |
| GET | `/api/v7/practice/secretary/plans` | S1 计划 |
| POST | `/api/v7/practice/secretary/exam-prep` | S6 考前 |

### 秘书提案类型扩展

| action_type | 对应 |
|-------------|------|
| `practice_plan_progress` | S1 |
| `practice_weak_recommend` | S2 |
| `practice_trend_alert` | S3 |
| `practice_pacing_advice` | S4 |
| `practice_error_pattern` | S5 |
| `practice_exam_prep` | S6 |
