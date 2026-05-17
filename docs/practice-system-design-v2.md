# 练习系统设计 v2.0

> **核心理念**：不是"做题机器"，而是"认知教练"——通过练习诊断认知状态，通过交互引导深度理解，通过数据驱动个性化成长路径。

---

## 1. 设计哲学：为什么当前系统不够强

### 1.1 当前系统的缺陷

| 维度 | 当前状态 | 问题 |
|------|---------|------|
| 知识追踪 | 单维BKT (P(K)二值) | 只知道"会不会"，不知道"为什么不会" |
| 题目来源 | 硬编码5道题 | 无法扩展，无法个性化 |
| 难度调度 | 固定顺序 | 无自适应，无间隔重复 |
| 题型 | 仅选择题 | 认知层次浅，无法检测高阶思维 |
| 反馈 | 对/错+解析 | 无错因分析，无苏格拉底式引导 |
| 多模态 | 纯文本 | 无法处理图表题、计算题 |
| 情感 | 无 | 连续错题无安抚，无动机管理 |

### 1.2 强练习系统的标准（来自研究）

1. **认知诊断**：不止"会/不会"，要定位到具体认知缺陷（概念错误 vs 计算失误 vs 审题不清）
2. **自适应调度**：基于ZPD（最近发展区）理论，每道题都在"刚好够挑战"的甜蜜点
3. **间隔重复**：基于Ebbinghaus遗忘曲线 + SM-2算法，在即将遗忘时复习
4. **交错练习**：混合不同知识点/题型，增强迁移能力（Rohrer & Taylor, 2007）
5. **生成式学习**：不只是选择，要能解题、证明、画图、讲解
6. **苏格拉底引导**：错误时给提示而非直接答案，引导发现错误
7. **多模态**：数学公式、几何图形、物理示意图、代码片段
8. **情感伴随**：连续挫败时调整策略，成功时强化正反馈
9. **刻意练习+引导发现**：不只是"动手做"，要有结构化的引导发现（self-explanation、对比案例、个性化反馈），研究显示引导发现比纯动手练习效果好4倍，组合使用效果好10倍+（Chen et al., Active Learning is About More Than Hands-On）
10. **用户资料驱动**：支持上传自己的题库/资料，建立语义索引，从用户真实材料中生成练习题

---

## 2. 系统架构

```
┌─────────────────────────────────────────────────────────┐
│                    练习系统总架构                          │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │   题目引擎    │  │  调度引擎    │  │  诊断引擎    │  │
│  │              │  │              │  │              │  │
│  │ • 题目生成   │  │ • ZPD调度    │  │ • 错因分析   │  │
│  │ • 多模态解析 │  │ • 间隔重复   │  │ • 迷思概念   │  │
│  │ • 难度标注   │  │ • 交错混合   │  │ • 认知负荷   │  │
│  │ • 题目质量   │  │ • 遗忘曲线   │  │ • 能力画像   │  │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  │
│         │                 │                 │           │
│         ▼                 ▼                 ▼           │
│  ┌─────────────────────────────────────────────────┐    │
│  │              练习会话管理器                        │    │
│  │  • 会话状态机  • 实时评分  • 进度追踪             │    │
│  └─────────────────────────────────────────────────┘    │
│         │                 │                 │           │
│         ▼                 ▼                 ▼           │
│  ┌──────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ 交互层   │  │  反馈引擎    │  │  数据层      │      │
│  │          │  │              │  │              │      │
│  │ • 选择题 │  │ • 即时解析   │  │ • BKT/AKT   │      │
│  │ • 填空题 │  │ • 苏格拉底   │  │ • 遗忘曲线   │      │
│  │ • 解答题 │  │ • 提示系统   │  │ • 错题本     │      │
│  │ • 计算题 │  │ • 情感安抚   │  │ • 统计面板   │      │
│  │ • 语音   │  │ • 视频推荐   │  │ • 行为日志   │      │
│  └──────────┘  └──────────────┘  └──────────────┘      │
│                                                         │
│  ┌─────────────────────────────────────────────────┐    │
│  │        📚 用户资料索引引擎（NEW）                 │    │
│  │  • OCR/解析 → 分块 → Embedding → 向量存储        │    │
│  │  • 语义搜索 → 题目生成 → 知识点提取               │    │
│  └─────────────────────────────────────────────────┘    │
│                                                         │
└─────────────────────────────────────────────────────────┘
```
│         │                 │                 │           │
│         ▼                 ▼                 ▼           │
│  ┌──────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ 交互层   │  │  反馈引擎    │  │  数据层      │      │
│  │          │  │              │  │              │      │
│  │ • 选择题 │  │ • 即时解析   │  │ • BKT/AKT   │      │
│  │ • 填空题 │  │ • 苏格拉底   │  │ • 遗忘曲线   │      │
│  │ • 解答题 │  │ • 提示系统   │  │ • 错题本     │      │
│  │ • 计算题 │  │ • 情感安抚   │  │ • 统计面板   │      │
│  │ • 语音   │  │ • 视频推荐   │  │ • 行为日志   │      │
│  └──────────┘  └──────────────┘  └──────────────┘      │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

---

## 3. 核心模块详细设计

### 3.1 多维知识状态模型（升级版BKT）

**问题**：当前BKT只追踪一个标量P(K)，丢失了大量信息。

**解决方案**：Multi-Dimensional Knowledge State (MDKS)

```python
class KnowledgeDimension(BaseModel):
    """单个知识维度的状态"""
    dimension_id: str           # 维度ID: "concept" | "procedure" | "application" | "transfer"
    p_known: float              # 掌握概率
    p_learned: float            # 已学会概率
    last_practiced: datetime    # 最近练习时间
    attempt_count: int          # 练习次数
    correct_count: int          # 正确次数
    streak: int                 # 连续正确次数
    error_patterns: list[str]   # 常见错误模式

class KnowledgeState(BaseModel):
    """知识点的多维状态"""
    skill_id: str
    dimensions: dict[str, KnowledgeDimension] = {
        "concept": ...,       # 概念理解（定义、性质）
        "procedure": ...,     # 程序性知识（解题步骤）
        "application": ...,   # 应用能力（综合题）
        "transfer": ...,      # 迁移能力（跨领域）
    }
    prerequisite_states: dict[str, float]  # 前置知识点掌握度
    misconception_flags: list[str]          # 迷思概念标记
    confidence_level: float = 0.5           # 元认知：学生自评置信度
```

**为什么4个维度**：
- **概念理解**：能背出定义 ≠ 真正理解（Greeno, 1998）
- **程序性知识**：知道怎么做，但不一定知道为什么
- **应用能力**：在新情境中运用
- **迁移能力**：跨领域应用（最难得分）

### 3.2 智能题目生成系统

**问题**：5道硬编码题目无法覆盖学习需求。

**解决方案**：LLM + 模板 + 质量控制

#### 3.2.1 题目生成流水线

```
用户请求 → 意图分析 → 题目生成 → 质量过滤 → 难度校准 → 多模态渲染 → 交付
    │              │            │            │            │
    │         Bloom分类     多样性检查    IRT参数估计   KaTeX/SVG
    │         知识点定位     重复检测     历史校准      图表生成
    │         难度预设       难度验证
    ▼              ▼            ▼            ▼            ▼
```

#### 3.2.2 Bloom认知层次 × 题型矩阵

| Bloom层次 | 选择题 | 填空题 | 简答题 | 证明题 | 计算题 |
|-----------|--------|--------|--------|--------|--------|
| **记忆** | ✓ 定义识别 | ✓ 术语填写 | | | |
| **理解** | ✓ 概念辨析 | ✓ 公式填空 | ✓ 解释原理 | | |
| **应用** | ✓ 情境选择 | ✓ 步骤填写 | | | ✓ 计算应用 |
| **分析** | ✓ 关系判断 | | ✓ 结构分析 | ✓ 逻辑推导 | |
| **评价** | ✓ 方案选择 | | ✓ 论证评价 | | |
| **创造** | | | ✓ 方案设计 | ✓ 定理证明 | ✓ 建模求解 |

**关键原则**：每次练习覆盖至少2个Bloom层次，避免只做低阶重复。

#### 3.2.3 多模态题目支持

```python
class QuestionContent(BaseModel):
    """题目内容（支持多模态）"""
    text: str                           # 文本主体
    math_latex: list[str] = []          # LaTeX公式块
    images: list[ImageContent] = []      # 图片（几何图形、示意图）
    tables: list[TableContent] = []      # 数据表格
    code_blocks: list[CodeContent] = []  # 代码片段
    audio: list[str] = []               # 音频（语言听力题）
    
class ImageContent(BaseModel):
    """图片内容"""
    image_type: str  # "geometry" | "diagram" | "graph" | "photo" | "equation"
    svg_data: str | None = None    # SVG矢量图
    image_url: str | None = None   # 图片URL
    description: str = ""          # 无障碍描述
    interactive: bool = False      # 是否可交互（如拖拽点）
```

### 3.3 自适应调度引擎

**问题**：当前无难度自适应，无间隔重复。

**解决方案**：三层调度架构

#### 3.3.1 第一层：ZPD难度调度

```python
class ZPDScheduler:
    """
    基于最近发展区(Zone of Proximal Development)的难度调度
    
    核心思想：每道题都应该在学生"刚好能做对但需要努力"的区间
    
    难度区间：
    - 太简单 (P(correct) > 0.85): 浪费时间，无学习效果
    - 甜蜜点 (0.4 < P(correct) < 0.8): 最佳学习区
    - 太难 (P(correct) < 0.3): 产生挫败感，放弃
    
    算法：基于学生当前能力θ和题目难度b，选择|θ - b| ≈ 1.0的题目
    """
    
    def select_next_question(
        self, 
        student_ability: float,        # 学生当前能力估计
        question_pool: list[Question], # 可选题目
        recent_performance: list[bool], # 最近表现
        target_bloom_level: str,       # 目标Bloom层次
    ) -> Question:
        # 1. 过滤：只保留目标Bloom层次的题
        candidates = [q for q in question_pool if q.bloom_level == target_bloom_level]
        
        # 2. 计算每道题的"ZPD得分"
        for q in candidates:
            # 难度匹配度：越接近ZPD甜蜜点越高
            difficulty_gap = abs(student_ability - q.difficulty_value)
            zpd_score = 1.0 / (1.0 + difficulty_gap)
            
            # 时间衰减：最近做过的题降权
            time_decay = self._compute_time_decay(q, recent_performance)
            
            # 知识点覆盖：优先选未覆盖的知识点
            coverage_bonus = self._compute_coverage_bonus(q)
            
            q._zpd_score = zpd_score * time_decay * coverage_bonus
        
        # 3. 选择ZPD得分最高的题
        return max(candidates, key=lambda q: q._zpd_score)
```

#### 3.3.2 第二层：间隔重复调度

```python
class SpacedRepetitionScheduler:
    """
    基于SM-2算法的间隔重复调度
    
    与ZPD调度协同工作：
    - ZPD决定"做什么题"
    - 间隔重复决定"什么时候复习旧题"
    
    调度逻辑：
    - 新学的知识点：立即练习 + 1天后复习 + 3天后 + 7天后...
    - 忘记曲线：根据遗忘概率决定复习优先级
    - 掌握度高：延长间隔；掌握度低：缩短间隔
    """
    
    def compute_review_priority(
        self,
        knowledge_states: dict[str, KnowledgeState],
    ) -> list[ReviewTask]:
        """计算所有知识点的复习优先级"""
        now = datetime.now()
        tasks = []
        
        for skill_id, state in knowledge_states.items():
            # 计算遗忘概率（基于Ebbinghaus遗忘曲线的变体）
            days_since_practice = (now - state.last_practiced).days
            forgetting_prob = self._forgetting_curve(
                days_since_practice, 
                state.stability  # 知识稳定性
            )
            
            # 复习优先级 = 遗忘概率 × 掌握度重要性
            importance = 1.0 - state.p_known  # 越不掌握越重要
            priority = forgetting_prob * importance
            
            # 计算下次复习时间
            next_review = self._compute_next_interval(state)
            
            tasks.append(ReviewTask(
                skill_id=skill_id,
                priority=priority,
                next_review=next_review,
                forgetting_prob=forgetting_prob,
            ))
        
        # 按优先级排序
        tasks.sort(key=lambda t: t.priority, reverse=True)
        return tasks
    
    def _forgetting_curve(self, days: float, stability: float) -> float:
        """
        Ebbinghaus遗忘曲线：R = e^(-t/S)
        R: 记忆保留率
        t: 时间
        S: 知识稳定性（越大越不容易忘）
        """
        import math
        return math.exp(-days / max(stability, 0.1))
```

#### 3.3.3 第三层：交错练习调度

```python
class InterleavingScheduler:
    """
    交错练习(Interleaving)调度
    
    研究发现：混合练习不同类型的问题，比集中练习单种类型效果更好
    （Rohrer & Taylor, 2007; Kornell & Bjork, 2008）
    
    原则：
    1. 每次练习session包含2-3个不同知识点
    2. 不同Bloom层次混合（记忆+应用+分析）
    3. 不同题型混合（选择+填空+计算）
    4. 但不要太多（认知负荷理论）：一次不超过4个知识点
    """
    
    def plan_practice_session(
        self,
        student_profile: LearnerProfile,
        session_duration_minutes: int = 30,
        target_skills: list[str] | None = None,
    ) -> PracticeSessionPlan:
        """规划一次练习session"""
        
        # 1. 选择知识点（最多4个）
        if target_skills:
            skills = target_skills[:4]
        else:
            # 自动选择：ZPD + 间隔重复 + 交错
            zpd_skills = self.zpd.get_skills_in_zone(student_profile)
            review_skills = self.spacing.get_overdue_reviews(student_profile)
            skills = self._select_interleaved_skills(zpd_skills, review_skills, max=4)
        
        # 2. 规划题目序列
        questions = []
        for skill in skills:
            n_questions = self._questions_per_skill(session_duration_minutes, len(skills))
            for _ in range(n_questions):
                bloom = self._select_bloom_level(skill, student_profile)
                q = self.zpd.select_next_question(
                    student_profile.ability(skill),
                    self.question_pool.get(skill, bloom),
                    student_profile.recent_performance(skill),
                    bloom,
                )
                questions.append(q)
        
        # 3. 交错排列
        interleaved = self._interleave(questions)
        
        return PracticeSessionPlan(
            skills=skills,
            questions=interleaved,
            estimated_minutes=session_duration_minutes,
        )
```

### 3.4 认知诊断引擎

**问题**：当前只判断"对/错"，不知道"为什么错"。

**解决方案**：错因分析 + 迷思概念检测

#### 3.4.1 错因分类体系

```python
class ErrorType(str, Enum):
    """错误类型（基于认知科学分类）"""
    CONCEPTUAL = "conceptual"       # 概念错误：对定义/性质理解有误
    PROCEDURAL = "procedural"       # 程序错误：知道做什么但步骤错了
    COMPUTATION = "computation"     # 计算错误：会做但算错了
    READING = "reading"             # 审题错误：没看清题意
    TRANSFER = "transfer"           # 迁移错误：不会应用到新情境
    META_COGNITIVE = "meta"         # 元认知错误：不知道自己不会

class ErrorAnalysis(BaseModel):
    """单次答题的错因分析"""
    error_type: ErrorType
    error_subtype: str           # 更细粒度的分类
    misconception: str | None    # 迷思概念描述（如"认为负数没有平方根"）
    related_skills: list[str]    # 相关知识点
    severity: float              # 严重程度 0-1
    suggestion: str              # 针对性建议
```

#### 3.4.2 迷思概念检测

```python
class MisconceptionDetector:
    """
    迷思概念(Misconception)检测
    
    核心洞察：学生选错答案不是随机的，而是反映了他们脑中的错误概念。
    通过分析他们选择了哪个错误选项(distractor)，可以推断他们的迷思概念。
    
    例如：在三角函数题中
    - 选A：可能认为 sin²θ + cos²θ = 1 可以直接开方
    - 选B：可能混淆了 sin(A+B) 和 sinA + sinB
    - 选C：可能弧度制和角度制搞混了
    """
    
    DISTRACTOR_ANALYSIS = {
        "algebra_linear": {
            "distractor_1": {
                "pattern": "sign_error",
                "misconception": "移项时忘记变号",
                "remedy": "强调移项规则：过等号变号",
            },
            "distractor_2": {
                "pattern": "coefficient_error", 
                "misconception": "系数和常数项混淆",
                "remedy": "区分方程的系数和常数",
            },
        },
        # ... 更多知识点的错因映射
    }
    
    def analyze(
        self, 
        question: Question, 
        student_answer: str,
        student_profile: LearnerProfile,
    ) -> ErrorAnalysis:
        """分析错误原因"""
        # 1. 找到学生选的错误选项
        chosen_distractor = self._find_distractor(question, student_answer)
        
        # 2. 查找该干扰项对应的迷思概念
        misconception = self._lookup_misconception(
            question.skill_id, chosen_distractor
        )
        
        # 3. 结合历史错误模式分析
        historical_pattern = self._analyze_historical_pattern(
            student_profile.error_history(question.skill_id)
        )
        
        # 4. 综合判断
        return ErrorAnalysis(
            error_type=self._classify_error(misconception, historical_pattern),
            error_subtype=misconception.get("pattern", "unknown"),
            misconception=misconception.get("misconception"),
            related_skills=self._find_related_skills(question.skill_id),
            severity=self._compute_severity(misconception, historical_pattern),
            suggestion=misconception.get("remedy", "请重新复习该知识点"),
        )
```

### 3.5 苏格拉底式交互反馈

**问题**：当前反馈是"对/错+解析"，学生被动接受。

**解决方案**：渐进式提示 + 引导发现 + 元认知提示

#### 3.5.1 提示系统（3级渐进）

```python
class HintSystem:
    """
    渐进式提示系统
    
    灵感来源：认知学徒制(Cognitive Apprenticeship)中的"脚手架"(Scaffolding)
    
    策略：
    Level 0: 无提示（学生独立尝试）
    Level 1: 方向提示（"想想用什么方法"）
    Level 2: 步骤提示（"第一步应该做什么"）
    Level 3: 部分解法（"先算出这个值"）
    Level 4: 完整解析（最后手段）
    
    关键：每用一次提示，BKT的p_known更新要打折
    （因为提示相当于外部帮助，不代表真正掌握）
    """
    
    def get_hint(
        self, 
        question: Question, 
        hint_level: int,
        student_context: dict,
    ) -> Hint:
        if hint_level == 0:
            return Hint(
                level=0,
                text="试着自己想想看 💪",
                hint_type="encouragement",
            )
        elif hint_level == 1:
            return Hint(
                level=1,
                text=self._generate_direction_hint(question, student_context),
                hint_type="direction",
            )
        elif hint_level == 2:
            return Hint(
                level=2,
                text=self._generate_step_hint(question, student_context),
                hint_type="step",
            )
        elif hint_level == 3:
            return Hint(
                level=3,
                text=self._generate_partial_solution(question, student_context),
                hint_type="partial",
            )
        else:
            return Hint(
                level=4,
                text=question.full_explanation,
                hint_type="full",
            )
```

#### 3.5.2 情感感知反馈

```python
class EmotionalFeedback:
    """
    情感感知反馈系统
    
    研究发现（Pekrun, 2006）：
    - 焦虑降低认知表现
    - 无聊导致放弃
    - 自信增强学习效果
    
    策略：
    - 连续3题错：降低难度 + 鼓励
    - 连续5题对：适当挑战 + 肯定
    - 长时间无操作：提醒但不催促
    - 答题速度异常（太快）：可能在猜测，提醒认真
    """
    
    def generate_feedback(
        self,
        session_context: PracticeSession,
        latest_result: AttemptResult,
    ) -> str | None:
        """根据上下文生成情感反馈"""
        
        recent = session_context.last_n_results(5)
        consecutive_wrong = self._count_consecutive(recent, correct=False)
        consecutive_right = self._count_consecutive(recent, correct=True)
        
        if consecutive_wrong >= 3:
            return "别着急，困难的知识点需要多花时间。要不要先看看相关视频讲解？🎬"
        
        if consecutive_wrong >= 2:
            return "这个知识点确实有点难，我们一步步来 🤝"
        
        if consecutive_right >= 5:
            return "太厉害了！连续答对5题！要不要挑战更高难度？🌟"
        
        if consecutive_right >= 3:
            return "掌握得很好！继续保持 💪"
        
        if latest_result.time_spent < 5:
            return "这题做得很快，确认一下答案再提交哦 ✨"
        
        return None  # 不需要特殊反馈
```

### 3.6 多模态交互支持

#### 3.6.1 输入模态

| 模态 | 用途 | 实现方式 |
|------|------|---------|
| **文本选择/填空** | 基础交互 | 前端表单 |
| **手写识别** | 数学推导、草稿 | Canvas + 识别API |
| **语音输入** | 口述解题过程 | Whisper ASR |
| **图片上传** | 拍照题目、手写笔记 | Vision模型解析 |
| **公式编辑** | 复杂数学表达 | KaTeX + 自定义编辑器 |

#### 3.6.2 输出模态

| 模态 | 用途 | 实现方式 |
|------|------|---------|
| **文本解析** | 答案解释 | Markdown + KaTeX |
| **步骤动画** | 解题过程可视化 | CSS动画 / Lottie |
| **几何图形** | 数学几何题 | SVG生成 |
| **函数图像** | 数学函数题 | D3.js / Canvas |
| **视频讲解** | 知识点讲解 | B站搜索 + 嵌入 |
| **思维导图** | 知识结构 | Mermaid / D3树图 |

---

## 4. 数据模型设计

### 4.1 核心实体

```python
# ─── 题目 ───
class Question(BaseModel):
    """练习题（增强版）"""
    question_id: str
    skill_id: str                           # 知识点ID
    subject: str                            # 学科
    
    # Bloom分类
    bloom_level: BloomLevel                 # 认知层次
    cognitive_skills: list[str]             # 认知技能标签
    
    # 内容
    content: QuestionContent                # 多模态内容
    options: list[QuestionOption] | None    # 选择题选项（非选择题为None）
    answer_type: AnswerType                 # "choice" | "fill" | "free_form" | "calculation"
    correct_answer: str                     # 标准答案
    answer_format: str                      # 答案格式要求
    
    # 难度与质量
    difficulty: float                       # IRT难度参数 b (0-1)
    discrimination: float                   # IRT区分度参数 a (0-2)
    guessing: float                         # IRT猜测参数 c (0-1)
    quality_score: float                    # 题目质量分 (0-1)
    
    # 元数据
    source: str                             # "llm" | "manual" | "imported"
    tags: list[str]                         # 标签
    explanation: str                        # 解析
    hints: list[Hint]                       # 提示列表
    video_url: str | None                   # 关联视频
    related_skills: list[str]               # 相关知识点
    
    # 验证
    verified: bool = False                  # 人工验证
    usage_count: int = 0                    # 使用次数
    avg_correct_rate: float = 0.0           # 平均正确率

class QuestionOption(BaseModel):
    """选择题选项"""
    letter: str                             # A/B/C/D
    text: str                               # 选项内容（多模态）
    is_correct: bool                        # 是否正确
    distractor_type: str | None             # 干扰项类型（用于错因分析）

# ─── 答题记录 ───
class AttemptRecord(BaseModel):
    """单次答题记录"""
    attempt_id: str
    user_id: str
    question_id: str
    session_id: str
    
    # 答题
    user_answer: str
    is_correct: bool
    time_spent_seconds: float
    
    # 认知诊断
    error_analysis: ErrorAnalysis | None    # 错因分析
    bloom_level_attempted: BloomLevel       # 实际考察的Bloom层次
    
    # 提示使用
    hints_used: int = 0                     # 使用了几个提示
    hint_levels: list[int] = []             # 每个提示的级别
    
    # 知识状态更新
    knowledge_before: dict[str, float]      # 答题前各知识点掌握度
    knowledge_after: dict[str, float]       # 答题后各知识点掌握度
    
    # 时间戳
    started_at: datetime
    submitted_at: datetime

# ─── 练习会话 ───
class PracticeSession(BaseModel):
    """一次练习会话"""
    session_id: str
    user_id: str
    
    # 规划
    planned_skills: list[str]               # 计划练习的知识点
    planned_bloom_levels: list[BloomLevel]  # 计划的Bloom层次
    estimated_minutes: int                  # 预计时长
    
    # 执行
    questions: list[str]                    # 题目ID列表
    current_index: int = 0                  # 当前做到第几题
    attempts: list[AttemptRecord] = []      # 答题记录
    
    # 统计
    correct_count: int = 0
    total_hints_used: int = 0
    avg_time_per_question: float = 0.0
    
    # 状态
    status: str = "active"                  # "active" | "paused" | "completed"
    started_at: datetime = Field(default_factory=datetime.now)
    completed_at: datetime | None = None
    
    # 情感状态
    frustration_level: float = 0.0          # 挫败感 (0-1)
    engagement_level: float = 0.5           # 参与度 (0-1)

# ─── 错题本 ───
class ErrorBookEntry(BaseModel):
    """错题本条目"""
    entry_id: str
    user_id: str
    question_id: str
    skill_id: str
    
    # 错误信息
    error_type: ErrorType
    misconception: str | None
    user_answer: str
    correct_answer: str
    
    # 复习
    review_count: int = 0                   # 已复习次数
    next_review: datetime                   # 下次复习时间
    mastery_after_review: float = 0.0       # 复习后掌握度
    
    # 状态
    is_resolved: bool = False               # 是否已解决
    created_at: datetime = Field(default_factory=datetime.now)

# ─── 统计面板 ───
class PracticeStats(BaseModel):
    """练习统计"""
    user_id: str
    
    # 总览
    total_questions: int = 0
    total_correct: int = 0
    overall_accuracy: float = 0.0
    
    # 按知识点
    skill_stats: dict[str, SkillStat] = {}
    
    # 按Bloom层次
    bloom_stats: dict[BloomLevel, BloomStat] = {}
    
    # 时间趋势
    daily_stats: list[DailyStat] = []
    
    # 错因分布
    error_distribution: dict[ErrorType, int] = {}
    
    # 学习建议
    recommendations: list[LearningRecommendation] = []
```

### 4.2 数据库表设计

```sql
-- 练习题表
CREATE TABLE practice_questions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    skill_id TEXT NOT NULL,
    subject TEXT NOT NULL,
    bloom_level TEXT NOT NULL,
    content JSONB NOT NULL,           -- 多模态内容
    options JSONB,                    -- 选择题选项
    answer_type TEXT NOT NULL,
    correct_answer TEXT NOT NULL,
    difficulty FLOAT DEFAULT 0.5,
    discrimination FLOAT DEFAULT 1.0,
    guessing FLOAT DEFAULT 0.25,
    quality_score FLOAT DEFAULT 0.5,
    source TEXT DEFAULT 'llm',
    tags TEXT[] DEFAULT '{}',
    explanation TEXT,
    hints JSONB DEFAULT '[]',
    verified BOOLEAN DEFAULT FALSE,
    usage_count INT DEFAULT 0,
    avg_correct_rate FLOAT DEFAULT 0.0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 答题记录表
CREATE TABLE attempt_records (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id TEXT NOT NULL,
    question_id UUID REFERENCES practice_questions(id),
    session_id UUID,
    user_answer TEXT NOT NULL,
    is_correct BOOLEAN NOT NULL,
    time_spent_seconds FLOAT DEFAULT 0,
    error_analysis JSONB,
    hints_used INT DEFAULT 0,
    knowledge_before JSONB DEFAULT '{}',
    knowledge_after JSONB DEFAULT '{}',
    started_at TIMESTAMPTZ NOT NULL,
    submitted_at TIMESTAMPTZ DEFAULT NOW()
);

-- 练习会话表
CREATE TABLE practice_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id TEXT NOT NULL,
    planned_skills TEXT[] DEFAULT '{}',
    planned_bloom_levels TEXT[] DEFAULT '{}',
    estimated_minutes INT DEFAULT 30,
    questions UUID[] DEFAULT '{}',
    current_index INT DEFAULT 0,
    correct_count INT DEFAULT 0,
    total_hints_used INT DEFAULT 0,
    status TEXT DEFAULT 'active',
    started_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    frustration_level FLOAT DEFAULT 0,
    engagement_level FLOAT DEFAULT 0.5
);

-- 错题本
CREATE TABLE error_book (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id TEXT NOT NULL,
    question_id UUID REFERENCES practice_questions(id),
    skill_id TEXT NOT NULL,
    error_type TEXT NOT NULL,
    misconception TEXT,
    user_answer TEXT,
    correct_answer TEXT,
    review_count INT DEFAULT 0,
    next_review TIMESTAMPTZ,
    mastery_after_review FLOAT DEFAULT 0,
    is_resolved BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 知识状态表
CREATE TABLE knowledge_states (
    user_id TEXT NOT NULL,
    skill_id TEXT NOT NULL,
    dimensions JSONB NOT NULL DEFAULT '{}',  -- 多维知识状态
    last_practiced TIMESTAMPTZ,
    streak INT DEFAULT 0,
    stability FLOAT DEFAULT 1.0,             -- 知识稳定性
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (user_id, skill_id)
);

-- 索引
CREATE INDEX idx_attempt_user ON attempt_records(user_id, submitted_at DESC);
CREATE INDEX idx_attempt_question ON attempt_records(question_id);
CREATE INDEX idx_error_book_user ON error_book(user_id, is_resolved, next_review);
CREATE INDEX idx_knowledge_user ON knowledge_states(user_id);
CREATE INDEX idx_question_skill ON practice_questions(skill_id, bloom_level);
```

---

## 5. API端点设计

### 5.1 题目管理

```yaml
POST /api/practice/questions/generate:
  description: "LLM生成题目"
  request:
    subject: string          # 学科
    skill_id: string         # 知识点
    bloom_level: BloomLevel  # 认知层次
    difficulty: float        # 目标难度 0-1
    count: int               # 生成数量 (1-10)
    content_type: "choice" | "fill" | "free_form" | "mixed"
    include_images: bool     # 是否包含图片
  response:
    questions: Question[]
    generation_cost: float   # token消耗

GET /api/practice/questions:
  description: "获取题目列表"
  params:
    subject: string?
    skill_id: string?
    bloom_level: BloomLevel?
    difficulty_min: float?
    difficulty_max: float?
    limit: int = 20
  response:
    questions: Question[]
    total: int

POST /api/practice/questions/verify:
  description: "验证题目质量（LLM评审）"
  request:
    question_id: string
  response:
    quality_score: float
    issues: list[str]
    suggestions: list[str]
```

### 5.2 练习会话

```yaml
POST /api/practice/sessions:
  description: "创建练习会话（自动规划）"
  request:
    subject: string?
    skill_ids: string[]?      # 指定知识点（可选）
    duration_minutes: int = 30
    mode: "adaptive" | "targeted" | "review" | "challenge"
    # adaptive: 自适应（系统自动选题）
    # targeted: 针对性（指定知识点）
    # review: 复习（间隔重复优先）
    # challenge: 挑战（高难度）
  response:
    session: PracticeSession
    planned_questions: Question[]

GET /api/practice/sessions/{session_id}:
  description: "获取会话详情"
  response:
    session: PracticeSession
    current_question: Question
    progress: SessionProgress

POST /api/practice/sessions/{session_id}/next:
  description: "获取下一题（自适应调度）"
  response:
    question: Question
    pre_context: string       # 前置提示/上下文

POST /api/practice/sessions/{session_id}/complete:
  description: "结束会话"
  response:
    summary: SessionSummary
```

### 5.3 答题与反馈

```yaml
POST /api/practice/submit:
  description: "提交答案"
  request:
    session_id: string
    question_id: string
    answer: string
    time_spent_seconds: float
    hints_used: int
    answer_content: QuestionContent?  # 多模态答案（如手写、语音）
  response:
    is_correct: bool
    correct_answer: string
    explanation: string
    error_analysis: ErrorAnalysis?
    knowledge_update: dict[str, KnowledgeUpdate]
    emotional_feedback: string?       # 情感反馈
    next_question_ready: bool
    xp_earned: int                    # 获得的经验值

POST /api/practice/hint:
  description: "获取提示"
  request:
    question_id: string
    current_level: int = 0
  response:
    hint: Hint
    next_level_available: bool
```

### 5.4 错题本与复习

```yaml
GET /api/practice/errors:
  description: "获取错题本"
  params:
    resolved: bool?              # true=已解决, false=未解决
    skill_id: string?
    error_type: ErrorType?
    sort_by: "created" | "next_review" | "frequency"
    limit: int = 20
  response:
    entries: ErrorBookEntry[]
    total: int
    unresolved_count: int

POST /api/practice/errors/{entry_id}/review:
  description: "复习错题"
  request:
    is_correct: bool
    time_spent_seconds: float
  response:
    updated_entry: ErrorBookEntry
    knowledge_update: dict

GET /api/practice/review/due:
  description: "获取待复习题目（间隔重复调度）"
  response:
    due_items: list[ReviewItem]
    overdue_count: int
    next_review_time: datetime
```

### 5.5 统计与分析

```yaml
GET /api/practice/stats:
  description: "获取练习统计"
  params:
    time_range: "week" | "month" | "semester" | "all"
  response:
    overview: PracticeStats
    skill_breakdown: list[SkillStat]
    bloom_breakdown: list[BloomStat]
    daily_trend: list[DailyStat]
    error_distribution: dict
    learning_velocity: float        # 学习速度（知识点掌握速率）
    study_streak: int               # 连续学习天数

GET /api/practice/stats/knowledge-map:
  description: "获取知识图谱掌握状态"
  response:
    nodes: list[KnowledgeNode]     # 知识点节点
    edges: list[PrerequisiteEdge]  # 前置关系边
    mastery_map: dict[str, float]  # 每个知识点的掌握度

GET /api/practice/recommendations:
  description: "获取个性化学习建议"
  response:
    immediate: list[Action]        # 立即要做的
    this_week: list[Action]        # 本周计划
    long_term: list[Action]        # 长期建议
    weak_points: list[WeakPoint]   # 薄弱点分析
    strength_points: list[str]     # 优势领域
```

---

## 6. 前端页面设计

### 6.1 练习主页（/practice）

```
┌─────────────────────────────────────────┐
│ 练习                              [设置] │
├─────────────────────────────────────────┤
│                                         │
│  ┌─────────────────────────────────┐    │
│  │  📊 今日概览                     │    │
│  │  已练 12 题 · 正确率 75%         │    │
│  │  连续学习 3 天 🔥                 │    │
│  │  [开始练习] [错题复习] [知识图谱] │    │
│  └─────────────────────────────────┘    │
│                                         │
│  ┌─────────────────────────────────┐    │
│  │  🎯 待复习（间隔重复）            │    │
│  │  极限的概念 · 3天前学的           │    │
│  │  导数的几何意义 · 昨天学的        │    │
│  │  [开始复习]                       │    │
│  └─────────────────────────────────┘    │
│                                         │
│  ┌─────────────────────────────────┐    │
│  │  📚 薄弱知识点                    │    │
│  │  ██████░░░░ 线性方程组 45%       │    │
│  │  ████░░░░░░ 概率论基础 32%       │    │
│  │  ███░░░░░░░ 积分应用 28%         │    │
│  │  [针对性练习]                     │    │
│  └─────────────────────────────────┘    │
│                                         │
│  ┌─────────────────────────────────┐    │
│  │  🏆 最近成就                     │    │
│  │  ⭐ 连续答对10题                  │    │
│  │  🧠 掌握"极限"知识点             │    │
│  │  📈 正确率提升到80%              │    │
│  └─────────────────────────────────┘    │
│                                         │
└─────────────────────────────────────────┘
```

### 6.2 练习进行中

```
┌─────────────────────────────────────────┐
│ ← 返回     练习进行中     ⏱ 12:34     │
├─────────────────────────────────────────┤
│                                         │
│  进度 ████████████░░░░ 6/10            │
│                                         │
│  ┌─────────────────────────────────┐    │
│  │ 高等数学 · 应用 · 难度:0.6       │    │
│  │                                 │    │
│  │ 求函数 f(x) = x³-3x²+2 在      │    │
│  │ [0,3] 上的最大值和最小值。       │    │
│  │                                 │    │
│  │ ○ A. 最大值2，最小值-2          │    │
│  │ ● B. 最大值2，最小值-4          │    │
│  │ ○ C. 最大值4，最小值-2          │    │
│  │ ○ D. 最大值4，最小值0           │    │
│  │                                 │    │
│  │ [💡 提示]  [跳过]  [提交答案]    │    │
│  └─────────────────────────────────┘    │
│                                         │
│  ┌─────────────────────────────────┐    │
│  │ 💡 提示 Level 1                 │    │
│  │ 想想：求最值需要找哪些特殊点？    │    │
│  │                          [下一级]│    │
│  └─────────────────────────────────┘    │
│                                         │
└─────────────────────────────────────────┘
```

### 6.3 答题反馈

```
┌─────────────────────────────────────────┐
│ ← 返回     练习进行中     ⏱ 15:22     │
├─────────────────────────────────────────┤
│                                         │
│  进度 ████████████░░░░ 6/10            │
│                                         │
│  ┌─────────────────────────────────┐    │
│  │ ❌ 回答错误                      │    │
│  │                                 │    │
│  │ 正确答案：A                      │    │
│  │ 你选的：B                        │    │
│  │                                 │    │
│  │ 📋 错因分析：                    │    │
│  │ 类型：计算错误                   │    │
│  │ 你可能在求f(2)时计算有误         │    │
│  │                                 │    │
│  │ 📝 解析：                        │    │
│  │ 求导 f'(x)=3x²-6x=3x(x-2)      │    │
│  │ 临界点 x=0, x=2                 │    │
│  │ f(0)=2, f(2)=-2, f(3)=2         │    │
│  │ 最大值2，最小值-2               │    │
│  │                                 │    │
│  │ 🎬 相关视频：极值求解详解        │    │
│  │                                 │    │
│  │ [📖 加入错题本]  [下一题 →]      │    │
│  └─────────────────────────────────┘    │
│                                         │
│  ┌─────────────────────────────────┐    │
│  │ 💪 别灰心，这个知识点确实有难度  │    │
│  │    已经学了不少了，继续加油！     │    │
│  └─────────────────────────────────┘    │
│                                         │
└─────────────────────────────────────────┘
```

---

## 7. 对话系统 × 练习系统 完整联动

> 现有设计只有"对话触发练习"（单向），需要完整的双向数据流。

### 7.1 联动全景图

```
对话 → 练习（已有）              练习 → 对话（缺失→补）
┌──────────────────┐            ┌──────────────────┐
│ "出几道极限的题"  │            │ 错误→推荐对话深度 │
│ → PracticeTool   │            │ "想聊聊这个吗？"  │
│ → ResponseBlock  │            │ → 深度讲解        │
└──────────────────┘            └──────────────────┘

对话 → 练习（缺失→补）          练习 → 对话（缺失→补）
┌──────────────────┐            ┌──────────────────┐
│ 对话上下文→选题   │            │ 练习数据→对话记忆 │
│ "刚聊到导数"     │            │ "你上次练了60%"   │
│ → 优先出导数题   │            │ → AI知道薄弱点    │
└──────────────────┘            └──────────────────┘

共享状态（缺失→补）
┌─────────────────────────────────────────────┐
│ 统一知识状态(MDKS) ← 对话和练习共同读写      │
│ 统一会话上下文 ← 练习session挂在对话branch上  │
└─────────────────────────────────────────────┘
```

### 7.2 共享知识状态（统一MDKS）

**问题**：对话系统和练习系统各自维护知识状态，数据不同步。

**方案**：一个用户只有一个MDKS实例，两个系统共同读写。

```python
class SharedKnowledgeState:
    """统一知识状态管理器"""
    
    def __init__(self, user_id: str, store: KnowledgeStateStore):
        self.user_id = user_id
        self.store = store  # PostgreSQL持久化
    
    # ── 练习系统调用 ──
    def update_from_practice(
        self, skill_id: str, is_correct: bool,
        hint_level: int, error_analysis: ErrorAnalysis | None,
        explanation_score: float | None,
    ) -> KnowledgeState:
        """练习答题后更新"""
        state = self.store.get(self.user_id, skill_id)
        # 根据提示等级打折 + BKT更新 + 解释评分调整
        # ... (见§13修复1和修复5)
        self.store.save(self.user_id, skill_id, state)
        return state
    
    # ── 对话系统调用 ──
    def update_from_conversation(
        self, skill_id: str, interaction_type: str, depth: int,
    ) -> KnowledgeState:
        """
        对话交互后更新
        
        interaction_type:
        - "question_asked": 学生主动提问（说明在思考）
        - "explanation_given": 学生尝试解释
        - "concept_discussed": 深度讨论了概念
        - "misconception_corrected": 对话中纠正了迷思概念
        """
        state = self.store.get(self.user_id, skill_id)
        
        if interaction_type == "misconception_corrected":
            state.dimensions["concept"].p_known = min(
                0.99, state.dimensions["concept"].p_known + 0.1
            )
        if interaction_type == "explanation_given" and depth >= 3:
            state.dimensions["application"].p_known = min(
                0.99, state.dimensions["application"].p_known + 0.05
            )
        
        self.store.save(self.user_id, skill_id, state)
        return state
```

### 7.3 对话上下文 → 练习选题

**问题**：从对话触发练习时，没有利用对话上下文。学生刚在聊导数，触发的练习却可能是随机题目。

```python
class ContextAwarePracticeTrigger:
    """利用对话上下文智能选题"""
    
    def infer_skills_from_context(
        self, conversation_branch: Branch, partition_context: str,
    ) -> list[str]:
        """从当前对话分支推断应该练习的知识点"""
        recent_texts = [
            node.text_summary 
            for node in conversation_branch.recent_messages(5)
        ]
        combined_text = " ".join(recent_texts)
        return self.skill_index.search(combined_text, top_k=3)
    
    def trigger_practice(
        self, conversation_context: dict, student_state: SharedKnowledgeState,
    ) -> PracticeSession:
        """基于对话上下文创建练习session"""
        # 1. 从对话推断知识点
        inferred_skills = self.infer_skills_from_context(
            conversation_context["branch"],
            conversation_context["partition_summary"],
        )
        
        # 2. 判断Bloom层次
        #    问"为什么" → 概念题
        #    问"怎么做" → 程序题
        #    问"有什么用" → 应用题
        bloom_level = self._infer_bloom_from_conversation(
            conversation_context["branch"]
        )
        
        return self.practice_engine.create_session(
            skill_ids=inferred_skills, bloom_level=bloom_level,
            mode="contextual",
        )
```

### 7.4 练习结果 → 对话记忆

**问题**：练习完成后，对话系统不知道学生的表现。下次对话时AI不了解练习情况。

```python
class PracticeResultIntegrator:
    """练习结果写入对话记忆"""
    
    def integrate_to_conversation(
        self, session: PracticeSession, branch: Branch, partition: Partition,
    ):
        # 1. 在branch上挂一条系统消息（元数据，不占token）
        system_node = TreeNode(
            role="system",
            content_blocks=[{
                "type": "text",
                "text": f"练习记录：{session.correct_count}/{len(session.questions)}正确，"
                        f"薄弱点：{', '.join(session.struggling_skills)}",
            }],
            metadata={
                "type": "practice_summary",
                "session_id": session.id,
                "accuracy": session.accuracy,
                "skills_tested": session.tested_skills,
                "error_patterns": session.error_patterns,
            }
        )
        branch.append(system_node)
        
        # 2. 更新分区摘要
        partition.context_summary += (
            f"\n练习记录({session.date}): {session.tested_skills} "
            f"正确率{session.accuracy:.0%}"
        )
        
        # 3. AI下次回复时注入：
        # [Practice] 最近练习: 极限(70%), 导数(40%←薄弱), 积分(85%)
        self._update_ai_context_injection(partition)
```

### 7.5 对话中的内联练习

**问题**：当前练习必须跳转到独立页面。对话中应该能直接做题不离开。

```python
class InlinePracticeHandler:
    """对话内联练习：不跳转页面，在对话流中完成"""
    
    def handle_inline_answer(
        self, branch: Branch, practice_block_id: str,
        student_answer: str, hint_level: int = 0,
    ) -> tuple[str, KnowledgeState]:
        """处理内联练习的答案"""
        question = self.question_store.get(practice_block_id)
        is_correct = student_answer.strip() == question.correct_answer.strip()
        
        state = self.shared_ks.update_from_practice(
            skill_id=question.skill_id, is_correct=is_correct,
            hint_level=hint_level, error_analysis=None,
            explanation_score=None,
        )
        
        if is_correct:
            reply = f"✅ 正确！{question.explanation}\n\n要继续下一题吗？"
        else:
            reply = (
                f"❌ 不对哦。你觉得哪里出了问题？\n"
                f"提示：{question.hints[0] if question.hints else '再想想'}\n"
                f"选 A/B/C/D 还是想让我详细讲解？"
            )
        
        branch.append(TreeNode(role="assistant", content_blocks=[{
            "type": "text", "text": reply
        }]))
        
        return reply, state
```

### 7.6 练习错误 → 推荐对话深度

```python
class PracticeToDialogueRecommendation:
    """练习后推荐深度对话"""
    
    def should_recommend_dialogue(
        self, session: PracticeSession, latest_error: ErrorAnalysis,
    ) -> str | None:
        skill = latest_error.related_skills[0] if latest_error.related_skills else None
        
        # 同一知识点连续错2次
        recent_errors = session.recent_errors_for_skill(skill, n=2)
        if len(recent_errors) >= 2:
            return "连续错了两次，要不要在对话中详细讨论一下？💬"
        
        # 概念性错误
        if latest_error.error_type == ErrorType.CONCEPTUAL:
            return "这个是概念理解的问题，聊聊会更有效。要切换到对话吗？💬"
        
        # 有未解决的迷思概念
        if latest_error.misconception:
            return f"检测到误解：{latest_error.misconception[:30]}... 要聊聊吗？💬"
        
        return None
```

### 7.7 对话中的"练习回顾"

```python
class PracticeRecallInConversation:
    """在对话中回答关于练习表现的问题"""
    
    def generate_recall(
        self, user_id: str, partition_id: str | None = None, time_range: str = "7d",
    ) -> str:
        stats = self.practice_stats.get(user_id, time_range)
        
        if not stats or stats.total_questions == 0:
            return "你还没有做过练习哦，要不要现在开始？📝"
        
        lines = [f"📊 过去{time_range}的练习情况："]
        lines.append(f"共练习 {stats.total_questions} 题，正确率 {stats.accuracy:.0%}\n")
        
        if stats.weak_skills:
            lines.append("🔴 薄弱点：" + "、".join(
                f"{s}({a:.0%})" for s, a in stats.weak_skills[:3]
            ))
        if stats.strong_skills:
            lines.append("🟢 掌握好的：" + "、".join(
                f"{s}({a:.0%})" for s, a in stats.strong_skills[:3]
            ))
        
        return "\n".join(lines)
```

### 7.8 练习Session挂载到对话Branch

```python
class Branch:
    # ... 现有字段 ...
    practice_sessions: list[str] = []  # 关联的session_id列表
    practice_summary: str = ""         # "已练12题,正确率70%,薄弱:导数"
```

**效果**：
- 打开对话branch时，侧边栏显示练习统计
- AI回复时注入："你在当前话题下已经练了10题，正确率60%"
- 学生问"这个话题我掌握了吗"，AI能基于练习数据回答

### 7.9 完整对话↔练习数据流

```
学生在对话中问"导数的几何意义是什么"
  ↓
AI回复解释（对话系统）
  ↓
学生说"出几道题考考我"
  ↓
┌──────────────────────────────────────────────┐
│ ContextAwarePracticeTrigger                   │
│ 1. 提取对话上下文："导数"、"几何意义"、"切线" │
│ 2. 匹配知识点：calculus_derivative_concept     │
│ 3. 查询MDKS：该知识点 p_known=0.45（发展中）  │
│ 4. 选择Bloom层次：概念+应用                     │
└──────────────────────────────────────────────┘
  ↓
练习在对话中内联进行（InlinePracticeHandler）
  ↓
学生答对3题、错1题（概念错误）
  ↓
┌──────────────────────────────────────────────┐
│ SharedKnowledgeState.update_from_practice     │
│ concept: 0.45→0.52  procedure: 0.45→0.60     │
└──────────────────────────────────────────────┘
  ↓
PracticeToDialogueRecommendation:
  概念性错误 + 迷思概念"切线斜率=函数值"
  → 推荐："要不要聊聊为什么切线斜率不是函数值？"
  ↓
学生选择继续对话
  ↓
AI回复（已注入练习上下文）：
  "你刚才做题时，我发现你对'切线斜率'的理解有点偏差..."
  ↓
┌──────────────────────────────────────────────┐
│ SharedKnowledgeState.update_from_conversation │
│ interaction_type="misconception_corrected"    │
│ concept: 0.52→0.62                           │
└──────────────────────────────────────────────┘
  ↓
PracticeResultIntegrator写入branch记忆：
  "练习记录：3/4正确，概念错误→已通过对话纠正"
  ↓
下次打开branch时AI能看到：
  "你在导数几何意义上练过一次，概念有偏差但已讨论纠正"
```

---

## 8. 刻意练习与引导发现（Deliberate Practice + Guided Discovery）

> 基于 Chen et al. "Active Learning is About More Than Hands-On" 的研究发现

### 8.1 核心发现

| 方法 | 效果 | 说明 |
|------|------|------|
| 纯动手练习（construction） | 基线 | 学生自由探索，无引导 |
| 引导发现（guided discovery） | **4倍**提升 | self-explanation + 对比案例 + 个性化反馈 |
| 引导发现 + 动手练习 | **10倍+**提升 | 组合使用效果最佳 |

**关键洞察**：单纯的"做题"（hands-on）不如"有引导的做题"（guided discovery）。系统不只是出题+判对错，而要主动引导学生思考。

### 8.2 三大引导机制

#### Self-Explanation（自我解释）

学生答完题后，**要求用自己的话解释为什么选这个答案**，而不是直接看解析。

```python
class SelfExplanationPrompt:
    """答完题后追问：用自己的话说说为什么选这个"""
    
    def generate_prompt(self, question: Question, student_answer: str) -> str:
        if student_answer == question.correct_answer:
            return "答对了！能用自己的话解释一下为什么是这个答案吗？"
        else:
            return "答错了。先别看解析，你觉得正确答案的逻辑是什么？试着推导一下。"
```

**效果**：强迫学生把"模糊的感觉"变成"清晰的逻辑"，暴露隐藏的迷思概念。

#### Contrasting Cases（对比案例）

展示两道**相似但关键点不同**的题目，让学生发现差异。

```python
class ContrastingCasesGenerator:
    """生成对比案例：两道看似相似但解法不同的题"""
    
    def generate_contrast(self, question: Question) -> dict:
        return {
            "case_a": question,  # 原题
            "case_b": self._modify_key_difference(question),  # 改变一个关键条件
            "prompt": "这两道题看起来很像，但解法完全不同。你能找出关键区别吗？",
        }
    
    def _modify_key_difference(self, q: Question) -> Question:
        """修改一个关键条件，生成对比题"""
        # 例：原题 f(x)=x² 在 [0,1] 求最值
        # 对比题 f(x)=x² 在 [-1,1] 求最值（多了负半轴）
        # 学生需要发现"区间不同→端点值不同"这个关键差异
        ...
```

#### Personalized Interactive Feedback（个性化交互反馈）

不是固定解析，而是根据学生的**具体错误**给出针对性反馈。

```python
class AdaptiveFeedback:
    """根据错误模式生成个性化反馈"""
    
    def generate(self, error_analysis: ErrorAnalysis, history: list) -> str:
        base = error_analysis.explanation
        
        if error_analysis.error_type == ErrorType.CONCEPTUAL:
            return f"你对{error_analysis.misconception}的理解有问题。\n" \
                   f"正确理解：{base}\n" \
                   f"💡 看看这个对比案例加深理解。"
        
        if error_analysis.error_type == ErrorType.PROCEDURAL:
            return f"你的方向对了，但第{error_analysis.error_subtype}步有问题。\n" \
                   f"正确步骤：{base}\n" \
                   f"🔍 对比一下你的步骤和正确步骤的差异。"
        
        if error_analysis.error_type == ErrorType.COMPUTATION:
            return f"思路完全正确！只是在{error_analysis.error_subtype}计算时出了点差错。\n" \
                   f"再算一遍这个步骤？"
```

### 8.3 引导发现 vs 直接解析

| 场景 | 直接解析 | 引导发现 |
|------|---------|---------|
| 首次做错 | 立即给完整解析 | 先追问"你为什么选这个？" → 再引导 |
| 同类错误≥2次 | 给对比案例 | 展示两道相似题，引导发现差异 |
| 概念性错误 | 给定义 | self-explanation + 对比案例 |
| 计算错误 | 给正确计算 | 指出具体步骤，让学生自己找到 |
| 连续对≥5题 | — | 挑战更高Bloom层次 |

---

## 9. 用户上传资料索引与题库构建

### 9.1 设计目标

用户可以上传自己的学习资料（PDF讲义、Word笔记、图片题目、习题集），系统自动：
1. **解析**：OCR/文本提取
2. **分块**：按知识点/题目切分
3. **索引**：Embedding向量化，存入pgvector
4. **生成**：基于用户资料生成练习题
5. **搜索**：语义搜索用户资料中的相关内容

### 9.2 支持的文件格式

| 格式 | 处理方式 | 输出 |
|------|---------|------|
| PDF | pymupdf提取文本+图片 | 结构化文本 + 图片块 |
| Word(.docx) | python-docx解析 | 结构化文本 |
| 图片(JPG/PNG) | Vision模型OCR | 文本 + 图片描述 |
| 手写笔记 | Vision模型OCR+手写识别 | 文本 |
| PPT | python-pptx提取 | 幻灯片文本+图片 |
| Markdown/TXT | 直接读取 | 文本 |

### 9.3 索引流水线

```
用户上传文件
  ↓
[Step 1] 格式解析
  ├── PDF → pymupdf → 文本块 + 图片
  ├── Word → python-docx → 文本块
  ├── 图片 → Vision模型OCR → 文本 + 图片描述
  └── 其他 → 对应解析器
  ↓
[Step 2] 智能分块
  ├── 按章节/标题分块（PDF目录/Word标题样式）
  ├── 按题目分块（识别"题目"、"解答"等标记）
  ├── 按知识点分块（LLM辅助识别）
  └── 固定长度分块（fallback，overlap 100字）
  ↓
[Step 3] 知识点标注
  ├── LLM提取每个chunk的知识点ID
  ├── 标注Bloom层次
  └── 标注难度估计
  ↓
[Step 4] Embedding向量化
  ├── 文本chunk → Granite Embedding → 向量
  ├── 图片 → CLIP embedding（可选）
  └── 存入pgvector
  ↓
[Step 5] 题目提取（可选）
  ├── 识别chunk中的题目（模式匹配+LLM）
  ├── 提取题干、选项、答案、解析
  ├── 标注难度、知识点、Bloom层次
  └── 存入practice_questions表
```

### 9.4 数据模型

```python
class MaterialChunk(BaseModel):
    """用户上传资料的一个分块"""
    chunk_id: str
    user_id: str
    material_id: str          # 所属资料
    
    # 内容
    text: str                 # 文本内容
    image_urls: list[str]     # 关联图片
    chunk_type: str           # "text" | "question" | "solution" | "diagram" | "formula"
    
    # 知识点
    skill_ids: list[str]      # 提取的知识点ID
    bloom_level: BloomLevel
    difficulty_estimate: float
    
    # 向量
    embedding: list[float]    # Embedding向量（存pgvector）
    
    # 来源
    source_file: str          # 原始文件名
    page_number: int | None   # 页码（PDF）
    chunk_index: int          # 在文件中的顺序
    
    # 元数据
    created_at: datetime
    indexed_at: datetime
    indexing_status: str      # "pending" | "processing" | "done" | "failed"

class Material(BaseModel):
    """用户上传的一份完整资料"""
    material_id: str
    user_id: str
    file_name: str
    file_type: str
    file_size: int
    
    # 状态
    status: str               # "uploading" | "processing" | "ready" | "failed"
    chunk_count: int = 0
    question_count: int = 0   # 提取出的题目数
    
    # 知识点覆盖
    skills_covered: list[str] = []
    
    created_at: datetime
    indexed_at: datetime | None
```

### 9.5 语义搜索API

```yaml
POST /api/materials/upload:
  description: "上传资料并触发索引"
  request:
    file: UploadFile
    auto_extract_questions: bool = true
  response:
    material: Material
    indexing_job_id: string

GET /api/materials:
  description: "获取用户资料列表"
  response:
    materials: list[Material]

GET /api/materials/{material_id}/chunks:
  description: "获取资料的分块列表"
  response:
    chunks: list[MaterialChunk]

POST /api/materials/search:
  description: "语义搜索用户资料"
  request:
    query: string
    material_ids: list[string]?
    skill_id: string?
    top_k: int = 10
  response:
    results: list[SearchResult]
    # 每个结果包含：chunk文本、相关度分数、来源文件、页码

POST /api/practice/generate-from-material:
  description: "基于用户资料生成练习题"
  request:
    material_ids: list[string]
    skill_id: string?
    count: int = 5
    bloom_level: BloomLevel?
    difficulty: float?
  response:
    questions: list[Question]
    source_chunks: list[MaterialChunk]  # 题目来源的资料片段
```

### 9.6 题目生成策略

从用户资料中生成题目的三种策略：

| 策略 | 说明 | 适用场景 |
|------|------|---------|
| **原题提取** | 直接识别资料中的题目 | 习题集、试卷 |
| **改题生成** | 改变原题的数字/条件 | 同类练习 |
| **知识点生成** | 根据资料中的知识点，LLM出新题 | 讲义、笔记 |

```python
class MaterialQuestionGenerator:
    """基于用户资料生成题目"""
    
    def generate(self, request: GenerateRequest) -> list[Question]:
        # 1. 语义搜索相关chunk
        chunks = self.vector_store.search(
            query=request.skill_id or request.query,
            material_ids=request.material_ids,
            top_k=20,
        )
        
        questions = []
        for chunk in chunks:
            if chunk.chunk_type == "question":
                # 策略1：原题提取
                q = self._extract_existing_question(chunk)
                if q: questions.append(q)
            
            # 策略2：改题生成
            q = self._modify_question(chunk, request.difficulty)
            if q: questions.append(q)
        
        # 策略3：知识点生成（用剩余chunk）
        knowledge_chunks = [c for c in chunks if c.chunk_type != "question"]
        new_questions = self._generate_from_knowledge(
            knowledge_chunks, request.count - len(questions)
        )
        questions.extend(new_questions)
        
        return questions[:request.count]
```

### 9.7 与练习系统的集成

```
用户上传PDF讲义
  ↓
系统解析 → 建立语义索引
  ↓
用户："根据我的讲义出几道极限的题"
  ↓
语义搜索 → 找到讲义中"极限"相关章节
  ↓
LLM基于讲义内容生成题目
  ↓
练习 → 答题 → 错因分析
  ↓
如果错误：推荐讲义中对应章节复习
```

**关键价值**：练习题不是凭空生成的，而是**基于用户自己的学习材料**，确保：
1. 题目内容与用户正在学的教材一致
2. 术语、符号、风格与教材匹配
3. 错误时能精确定位到教材的对应章节

---

## 10. 游戏化设计（谨慎使用）

### 10.1 设计原则

> **研究警告**：过度游戏化会削弱内在动机（Deci & Ryan, 2000）。  
> 我们的游戏化应该是**锦上添花**，不是**本末倒置**。

### 10.2 实现的游戏化元素

```python
class GamificationSystem:
    """轻量游戏化系统"""
    
    # ✅ 采用：基于掌握的成就
    ACHIEVEMENTS = {
        "concept_master": {
            "name": "概念大师",
            "description": "连续3个知识点达到'已掌握'",
            "icon": "🧠",
            "condition": lambda stats: stats.mastered_streak >= 3,
        },
        "error_slayer": {
            "name": "错题终结者",
            "description": "错题本清零",
            "icon": "⚔️",
            "condition": lambda stats: stats.error_book_count == 0,
        },
        "bloom_climber": {
            "name": "认知攀登者",
            "description": "在所有Bloom层次都有练习记录",
            "icon": "🧗",
            "condition": lambda stats: stats.bloom_levels_covered == 6,
        },
    }
    
    # ❌ 不采用：streak天数（研究显示会导致焦虑）
    # ❌ 不采用：排行榜（社会比较有害）
    # ❌ 不采用：虚拟货币（外在奖励削弱内在动机）
```

---

## 13. 模块联动闭环设计（修复断裂点）

> 各模块不应是孤岛，必须形成数据流动的闭环。

### 断裂点一览

| # | 断裂 | 问题 | 修复方案 |
|---|------|------|---------|
| 1 | Self-Explanation → 知识状态 | 解释质量没有反馈回BKT | 解释评分 → 调整BKT参数 |
| 2 | Contrasting Cases → 调度 | 对比案例何时插入不清楚 | 调度器感知"需要对比"的信号 |
| 3 | 错误分析 → 题目生成 | 发现迷思概念后没有针对性出题 | 错误驱动的题目生成 |
| 4 | 材料索引 → 间隔重复 | 材料chunk不参与复习调度 | 材料chunk = 知识点，纳入SM-2 |
| 5 | 提示使用 → BKT打折 | 提示了还答对≠真正掌握 | hint_weight打折p_known更新 |
| 6 | 疲劳 → ZPD调整 | session后半段难度应降低 | fatigue_factor动态调整ZPD |
| 7 | 错题本 → 材料索引 | 错题无法关联到用户笔记 | 错题→材料chunk反向索引 |

### 修复1：Self-Explanation 评分 → 知识状态反馈

```python
class SelfExplanationScorer:
    """
    评估学生的自我解释质量，反馈到知识状态
    
    评分维度：
    - 正确性：解释的核心逻辑是否正确
    - 完整性：是否覆盖了关键步骤
    - 一致性：解释是否与答案一致
    
    关键洞察：
    - 答对 + 解释正确 → 真正掌握（p_known大幅提升）
    - 答对 + 解释模糊 → 可能是猜对的（p_known小幅提升）
    - 答错 + 解释正确 → 可能是slip（计算失误），p_known不降
    - 答错 + 解释错误 → 真正的misconception（p_known大幅下降）
    """
    
    def score_and_update(
        self,
        attempt: AttemptRecord,
        explanation_text: str,
        knowledge_state: KnowledgeState,
    ) -> KnowledgeState:
        # LLM评估解释质量 (0-1)
        explanation_score = self._llm_score(explanation_text, attempt)
        
        if attempt.is_correct:
            if explanation_score > 0.8:
                # 真正掌握：大幅提升
                knowledge_state.p_known = min(0.99, knowledge_state.p_known + 0.15)
            elif explanation_score > 0.5:
                # 可能猜对：小幅提升
                knowledge_state.p_known = min(0.99, knowledge_state.p_known + 0.05)
            else:
                # 猜对但不理解：不提升，标记为"伪掌握"
                knowledge_state.pseudo_mastery_flags.append(attempt.skill_id)
        else:
            if explanation_score > 0.7:
                # 理解正确但计算失误(slip)：p_known不降，增加p_slip
                knowledge_state.p_slip = min(0.5, knowledge_state.p_slip + 0.05)
            else:
                # 真正不理解：大幅下降
                knowledge_state.p_known = max(0.0, knowledge_state.p_known - 0.1)
                knowledge_state.misconception_flags.append(
                    f"{attempt.skill_id}:{explanation_text[:50]}"
                )
        
        return knowledge_state
```

### 修复2：Contrasting Cases → 调度集成

```python
class InterleavingScheduler:
    """在调度中集成对比案例"""
    
    def plan_practice_session(self, student_profile, ...):
        questions = []
        
        for skill in skills:
            for _ in range(n_questions):
                q = self.zpd.select_next_question(...)
                
                # ★ 新增：判断是否需要插入对比案例
                if self._should_insert_contrast(skill, student_profile):
                    contrast_q = self._generate_contrasting_question(q)
                    # 对比案例紧挨着原题插入
                    questions.append(q)
                    questions.append(ContrastPair(
                        case_a=q, case_b=contrast_q,
                        prompt="这两道题看起来很像，但解法不同。找出关键区别！"
                    ))
                else:
                    questions.append(q)
        
        return PracticeSessionPlan(questions=self._interleave(questions))
    
    def _should_insert_contrast(self, skill_id: str, profile) -> bool:
        """
        什么时候插入对比案例：
        - 学生在同一知识点上犯过类似错误 → 需要对比来区分
        - 学生p_known在0.4-0.7之间（发展中）→ 对比有助于突破
        - 该知识点有常见的易混淆概念 → 对比能澄清
        """
        state = profile.knowledge_states.get(skill_id)
        if not state:
            return False
        
        # 发展中 + 有过错因记录 → 插入对比
        if 0.4 <= state.p_known <= 0.7 and state.attempt_count >= 3:
            return True
        
        # 有迷思概念标记 → 插入对比
        if state.misconception_flags:
            return True
        
        return False
```

### 修复3：错误驱动的题目生成

```python
class MisconceptionDrivenGenerator:
    """
    发现迷思概念后，自动生成针对性题目
    
    流程：
    错误分析 → 发现迷思概念 → 生成"反例题" → 让学生对比
    """
    
    def generate_for_misconception(
        self,
        misconception: str,
        skill_id: str,
        student_state: KnowledgeState,
    ) -> list[Question]:
        """
        例：学生错选了 sin(A+B) = sinA + sinB
        → 生成一道题：sin(30°+60°) 等于多少？
          A. sin30°+sin60° (错误选项，就是这个迷思)
          B. 1 (正确答案)
          C. sin30°·cos60°+cos30°·sin60° (展开式)
        → 让学生先做，再对比自己的错误思路
        """
        
        prompt = f"""
        学生在{skill_id}上有迷思概念：{misconception}
        请生成一道对比题，要求：
        1. 题目表面看起来支持学生的错误理解
        2. 但正确解法能揭示错误
        3. 选项中包含学生的迷思概念作为干扰项
        """
        
        return self.llm.generate(prompt, count=2)
```

### 修复4：材料Chunk → 间隔重复

```python
class MaterialReviewScheduler:
    """
    用户上传的资料chunk也纳入间隔重复
    
    原理：阅读资料 = 学习知识点 → 需要复习
    """
    
    def schedule_material_review(
        self,
        user_id: str,
        material_chunks: list[MaterialChunk],
    ) -> list[ReviewTask]:
        tasks = []
        now = datetime.now()
        
        for chunk in material_chunks:
            # 为每个chunk维护一个"阅读掌握度"
            read_state = self._get_read_state(user_id, chunk.chunk_id)
            
            # 基于遗忘曲线计算复习优先级
            days_since_read = (now - read_state.last_read).days
            forgetting_prob = math.exp(-days_since_read / max(read_state.stability, 0.1))
            
            if forgetting_prob > 0.3:  # 超过30%遗忘风险 → 需要复习
                tasks.append(ReviewTask(
                    type="material_review",
                    chunk_id=chunk.chunk_id,
                    priority=forgetting_prob,
                    skill_ids=chunk.skill_ids,
                ))
        
        return sorted(tasks, key=lambda t: t.priority, reverse=True)
```

### 修复5：提示使用 → BKT更新打折

```python
def update_with_hint_discount(
    self,
    state: KnowledgeState,
    is_correct: bool,
    hint_level: int,
) -> KnowledgeState:
    """
    提示等级越高，p_known更新幅度越小
    
    Level 0 (无提示): 更新幅度 = 100%
    Level 1 (方向):   更新幅度 = 70%
    Level 2 (步骤):   更新幅度 = 40%
    Level 3 (部分):   更新幅度 = 20%
    Level 4 (完整):   更新幅度 = 5%  (几乎不更新)
    """
    discount_factors = {0: 1.0, 1: 0.7, 2: 0.4, 3: 0.2, 4: 0.05}
    discount = discount_factors.get(hint_level, 0.05)
    
    # 原始更新
    original_update = self.bkt.update(state, is_correct)
    
    # 打折后的更新：只取discount比例的变化量
    delta = original_update.p_known - state.p_known
    state.p_known = state.p_known + delta * discount
    state.attempt_count += 1
    if is_correct:
        state.correct_count += 1
    
    return state
```

### 修复6：疲劳 → ZPD动态调整

```python
class FatigueAwareZPD:
    """
    疲劳感知的ZPD调度
    
    研究发现：认知疲劳导致有效ZPD下移
    - 开始时：θ+1.0 难度最合适
    - 30分钟后：θ+0.8 更合适
    - 60分钟后：θ+0.5 更合适
    """
    
    def adjusted_zpd_center(
        self,
        student_ability: float,
        session_elapsed_minutes: float,
        consecutive_wrong: int,
    ) -> float:
        # 基础ZPD偏移
        base_offset = 1.0
        
        # 时间衰减：每30分钟降低0.2
        time_decay = max(0.5, 1.0 - session_elapsed_minutes / 150)
        
        # 连续错误惩罚：每连续错1题降低0.15
        error_penalty = consecutive_wrong * 0.15
        
        # 最终ZPD中心
        adjusted = student_ability + max(0.0, base_offset * time_decay - error_penalty)
        
        return adjusted
```

### 修复7：错题本 → 材料反向索引

```python
class ErrorBookWithMaterialLink:
    """
    错题本与材料索引联动
    
    答错时：自动搜索用户资料中相关内容
    展示："你上传的讲义第X页有这个知识点"
    """
    
    def enrich_error_entry(
        self,
        error_entry: ErrorBookEntry,
        material_store: MaterialVectorStore,
    ) -> ErrorBookEntry:
        # 用错题的知识点搜索用户资料
        related_chunks = material_store.search(
            query=error_entry.misconception or error_entry.skill_id,
            user_id=error_entry.user_id,
            top_k=3,
        )
        
        if related_chunks:
            error_entry.referenced_materials = [
                {
                    "chunk_id": c.chunk_id,
                    "source_file": c.source_file,
                    "page_number": c.page_number,
                    "preview": c.text[:100],
                }
                for c in related_chunks
            ]
        
        return error_entry
```

### 完整数据流闭环图

```
                    ┌─────────────────────────────────────────────┐
                    │              用户上传资料                     │
                    └──────────────────┬──────────────────────────┘
                                       ↓
                    ┌─────────────────────────────────────────────┐
                    │        Material Indexing (§9)                │
                    │   OCR → 分块 → Embedding → pgvector         │
                    └──────────────────┬──────────────────────────┘
                                       ↓
                    ┌─────────────────────────────────────────────┐
                    │   Material Question Generator (§9.6)        │
                    │   原题提取 / 改题生成 / 知识点生成            │
                    └──────────────────┬──────────────────────────┘
                                       ↓
┌──────────────────────────────────────┼──────────────────────────────────────┐
│ 练习会话                              ↓                                      │
│  ┌─────────────────────────────────────────────────────────────────┐        │
│  │  Interleaving Scheduler (§3.3.3)                               │        │
│  │  ├── ZPD Scheduler → 选题难度                                   │        │
│  │  ├── Spaced Repetition → 复习调度                                │        │
│  │  ├── ★ FatigueAware → 疲劳降难度                                │        │
│  │  └── ★ ContrastInserter → 对比案例插入                          │        │
│  └─────────────────────────────────────────────────────────────────┘        │
│         ↓                                                                  │
│  ┌─────────────────────────────────────────────────────────────────┐        │
│  │  学生答题                                                       │        │
│  └─────────────────────────────────────────────────────────────────┘        │
│         ↓                                                                  │
│  ┌─────────────────────────────────────────────────────────────────┐        │
│  │  诊断引擎 (§3.4)                                                │        │
│  │  ├── ErrorAnalysis → 错因分类                                    │        │
│  │  ├── MisconceptionDetector → 迷思概念检测                        │        │
│  │  └── ★ SelfExplanationScorer → 解释质量评分                      │        │
│  └─────────────────────────────────────────────────────────────────┘        │
│         ↓                                                                  │
│  ┌─────────────────────────────────────────────────────────────────┐        │
│  │  反馈引擎 (§3.5 + §8)                                          │        │
│  │  ├── HintSystem → 渐进提示                                       │        │
│  │  ├── ★ HintDiscount → 提示打折(BKT)                             │        │
│  │  ├── AdaptiveFeedback → 个性化解析                                │        │
│  │  ├── ★ MisconceptionDriven → 错误驱动出题                        │        │
│  │  ├── ★ ContrastingCases → 对比案例                               │        │
│  │  └── EmotionalFeedback → 情感安抚                                 │        │
│  └─────────────────────────────────────────────────────────────────┘        │
│         ↓                                                                  │
│  ┌─────────────────────────────────────────────────────────────────┐        │
│  │  知识状态更新 (§3.1)                                             │        │
│  │  MDKS.update() ← 接收: is_correct + hint_level + explanation_score│       │
│  │  → 更新 concept/procedure/application/transfer 四维度            │        │
│  │  → 更新 misconception_flags                                      │        │
│  │  → 更新 pseudo_mastery_flags (答对但不会解释)                     │        │
│  └─────────────────────────────────────────────────────────────────┘        │
│         ↓                                                                  │
│  ┌─────────────────────────────────────────────────────────────────┐        │
│  │  间隔重复调度 (§3.3.2)                                          │        │
│  │  ← 接收: 更新后的knowledge_state                                │        │
│  │  → 计算下次复习时间                                               │        │
│  │  → 同时调度: 知识点复习 + ★材料chunk复习                         │        │
│  └─────────────────────────────────────────────────────────────────┘        │
│         ↓                                                                  │
│  ┌─────────────────────────────────────────────────────────────────┐        │
│  │  错题本 (§4.2)                                                   │        │
│  │  ← 记录: 错因 + 迷思概念                                         │        │
│  │  → ★ 反向搜索用户材料: "你讲义第X页有这个知识点"                  │        │
│  └─────────────────────────────────────────────────────────────────┘        │
│         ↓                                                                  │
│  ┌─────────────────────────────────────────────────────────────────┐        │
│  │  统计面板 (§5.5)                                                 │        │
│  │  ← 汇总: 掌握度 + 错因分布 + 学习速度 + 疲劳曲线               │        │
│  │  → 输出: 推荐 + 知识图谱 + 材料薄弱章节                          │        │
│  └─────────────────────────────────────────────────────────────────┘        │
└─────────────────────────────────────────────────────────────────────────────┘

★ = 新增的联动修复
```

---

## 14. 第二轮遗漏修复（6个深层机制）

### 14.1 题目质量反馈闭环

**问题**：LLM生成的题如果100%答对/0%答对，说明题目有问题。

```python
class QuestionQualityMonitor:
    """
    题目质量监控
    
    自动降权/淘汰的条件：
    - 正确率 > 95%：太简单，降权
    - 正确率 < 10%：可能有歧义或太难，标记人工审核
    - 区分度 < 0.2：不能区分高低能力学生，降权
    - 答题时间 < 3秒：可能是猜测，题目质量存疑
    """
    
    def evaluate(self, question_id: str, attempts: list[AttemptRecord]) -> float:
        if len(attempts) < 5:
            return question.quality_score  # 样本不够，不调整
        
        correct_rate = sum(a.is_correct for a in attempts) / len(attempts)
        avg_time = sum(a.time_spent_seconds for a in attempts) / len(attempts)
        
        # 计算区分度（高能力组 vs 低能力组的正确率差）
        discrimination = self._compute_discrimination(attempts)
        
        # 质量分 = 区分度 × 难度适中度
        difficulty_fit = 1.0 - abs(correct_rate - 0.6)  # 60%正确率最优
        quality = discrimination * difficulty_fit
        
        # 自动降权
        if correct_rate > 0.95:
            quality *= 0.3  # 太简单
        elif correct_rate < 0.10:
            quality *= 0.5  # 可能有歧义
            self._flag_for_review(question_id, "正确率过低")
        
        if avg_time < 3:
            quality *= 0.7  # 答题太快
        
        return quality
```

### 14.2 前置知识点卡控

**问题**：MDKS有prerequisite_states但调度没用它。

```python
class PrerequisiteGate:
    """
    前置知识点卡控
    
    知识点前置关系示例：
    - 极限 → 连续 → 导数 → 积分
    - 集合 → 函数 → 极限
    - 向量 → 矩阵 → 特征值
    
    规则：
    - 前置知识点p_known < 0.5 → 不推荐后续知识点的新题
    - 前置知识点p_known < 0.7 → 后续知识点的高阶题降权
    - 前置知识点p_known ≥ 0.8 → 正常开放后续知识点
    """
    
    PREREQUISITES = {
        "calculus_continuity": ["calculus_limit"],
        "calculus_derivative": ["calculus_continuity"],
        "calculus_integral": ["calculus_derivative"],
        "linear_eigenvalue": ["linear_matrix"],
        "linear_matrix": ["linear_vector"],
    }
    
    def can_practice(
        self, skill_id: str, knowledge_states: dict[str, KnowledgeState],
    ) -> tuple[bool, str]:
        """检查是否可以练习某个知识点"""
        prereqs = self.PREREQUISITES.get(skill_id, [])
        
        for prereq in prereqs:
            state = knowledge_states.get(prereq)
            if not state or state.p_known < 0.5:
                return False, f"需要先掌握前置知识：{prereq}"
        
        return True, ""
    
    def adjust_difficulty(
        self, skill_id: str, target_difficulty: float,
        knowledge_states: dict[str, KnowledgeState],
    ) -> float:
        """根据前置掌握度调整难度上限"""
        prereqs = self.PREREQUISITES.get(skill_id, [])
        
        if not prereqs:
            return target_difficulty
        
        min_prereq_mastery = min(
            knowledge_states.get(p, KnowledgeState(skill_id=p)).p_known
            for p in prereqs
        )
        
        # 前置掌握度低 → 难度上限降低
        max_difficulty = 0.3 + min_prereq_mastery * 0.7  # 0.3~1.0
        return min(target_difficulty, max_difficulty)
```

### 14.3 自适应Session时长

**问题**：当前固定30分钟，但心流时不该打断，疲劳时不该硬撑。

```python
class AdaptiveSessionLength:
    """
    基于Flow理论的自适应session管理
    
    Csikszentmihalyi的心流通道：
    - 挑战 > 能力 → 焦虑
    - 挑战 < 能力 → 无聊
    - 挑战 ≈ 能力 → 心流（最佳学习状态）
    
    策略：
    - 检测到心流（连续正确+答题速度快）→ 延长session
    - 检测到疲劳（正确率下降+答题变慢）→ 建议结束
    - 检测到焦虑（连续错误+长时间停顿）→ 降低难度或建议休息
    """
    
    def should_continue(
        self, session: PracticeSession, elapsed_minutes: float,
    ) -> tuple[bool, str]:
        recent = session.last_n_results(5)
        
        if len(recent) < 3:
            return True, ""  # 数据不够，继续
        
        # 心流检测
        accuracy = sum(r.is_correct for r in recent) / len(recent)
        avg_time = sum(r.time_spent for r in recent) / len(recent)
        
        if accuracy >= 0.8 and avg_time < 30:
            # 心流状态：建议延长
            if elapsed_minutes < 60:
                return True, "🔥 状态很好，要不要继续？"
            else:
                return True, "已经练了1小时了，状态不错但记得休息哦"
        
        # 疲劳检测
        if accuracy < 0.4 or avg_time > 120:
            return False, "看起来有点累了，要不要先休息一下？休息后效果会更好 💤"
        
        # 焦虑检测
        consecutive_wrong = self._count_consecutive(recent, correct=False)
        if consecutive_wrong >= 4:
            return False, "这个知识点确实有难度，先看看讲解视频再来？🎬"
        
        return True, ""
```

### 14.4 题目覆盖度检测

**问题**：用户有100个知识点但只有20个有题→80个知识死角。

```python
class CoverageDetector:
    """检测知识点的题目覆盖度"""
    
    def detect_gaps(
        self, user_id: str, knowledge_states: dict[str, KnowledgeState],
        question_bank: dict[str, list[Question]],
    ) -> list[CoverageGap]:
        gaps = []
        
        for skill_id, state in knowledge_states.items():
            available_questions = question_bank.get(skill_id, [])
            
            if len(available_questions) == 0:
                gaps.append(CoverageGap(
                    skill_id=skill_id,
                    gap_type="no_questions",
                    severity="critical",
                    suggestion=f"知识点'{skill_id}'没有任何题目，需要生成",
                ))
            elif len(available_questions) < 3:
                gaps.append(CoverageGap(
                    skill_id=skill_id,
                    gap_type="insufficient_questions",
                    severity="warning",
                    suggestion=f"知识点'{skill_id}'只有{len(available_questions)}道题，建议补充",
                ))
            
            # 检查Bloom层次覆盖
            covered_blooms = set(q.bloom_level for q in available_questions)
            all_blooms = {BloomLevel.REMEMBER, BloomLevel.UNDERSTAND, BloomLevel.APPLY}
            missing_blooms = all_blooms - covered_blooms
            
            if missing_blooms and state.p_known > 0.3:
                gaps.append(CoverageGap(
                    skill_id=skill_id,
                    gap_type="missing_bloom_levels",
                    severity="info",
                    suggestion=f"缺少{missing_blooms}层次的题目",
                ))
        
        return gaps
```

### 14.5 学习行为分析 + 习惯养成

**问题**：原始需求有"学习行为分析心理陪伴学习习惯养成"，当前只做了游戏化的皮。

```python
class LearningBehaviorAnalyzer:
    """
    学习行为分析
    
    追踪维度：
    - 时间模式：什么时间段学习、每次学多久
    - 效率模式：不同时间段的正确率差异
    - 习惯形成：连续学习天数、固定学习时间
    - 疲劳曲线：session内正确率随时间的变化
    """
    
    def analyze_patterns(self, user_id: str) -> BehaviorReport:
        sessions = self.session_store.get_all(user_id)
        
        # 时间模式分析
        hourly_accuracy = defaultdict(list)
        for s in sessions:
            hour = s.started_at.hour
            hourly_accuracy[hour].append(s.accuracy)
        
        # 找出最佳学习时段
        best_hours = sorted(
            hourly_accuracy.items(),
            key=lambda x: sum(x[1]) / len(x[1]),
            reverse=True,
        )[:3]
        
        # 习惯形成度
        streak = self._compute_streak(sessions)
        regularity = self._compute_regularity(sessions)  # 时间规律性
        
        # 疲劳曲线
        fatigue_curve = self._compute_fatigue_curve(sessions)
        
        return BehaviorReport(
            best_study_hours=[h for h, _ in best_hours],
            current_streak=streak,
            regularity_score=regularity,
            fatigue_curve=fatigue_curve,
            recommendations=self._generate_recommendations(best_hours, streak, fatigue_curve),
        )
    
    def _generate_recommendations(self, best_hours, streak, fatigue_curve):
        recs = []
        
        if best_hours:
            best_h = best_hours[0][0]
            recs.append(f"你在{best_h}:00左右效率最高，建议安排重点学习")
        
        if streak < 3:
            recs.append("试着每天固定时间学习10分钟，养成习惯比一次学很久更重要")
        
        if fatigue_curve.get("drop_at_minutes", 999) < 20:
            recs.append("你的专注力在20分钟左右会下降，建议用番茄钟：学20分钟休息5分钟")
        
        return recs


class HabitFormation:
    """
    习惯养成系统
    
    基于BJ Fogg的Tiny Habits方法：
    1. 从小开始（每天2题就行）
    2. 锚定时间（每天同一时间提醒）
    3. 庆祝成功（答对后给正反馈）
    """
    
    DAILY_TARGETS = {
        "beginner": {"questions": 5, "minutes": 10},
        "regular": {"questions": 10, "minutes": 20},
        "intensive": {"questions": 20, "minutes": 40},
    }
    
    def check_daily_goal(self, user_id: str, today_stats: DailyStat) -> str:
        level = self._get_user_level(user_id)
        target = self.DAILY_TARGETS[level]
        
        if today_stats.questions_done >= target["questions"]:
            return f"✅ 今日目标已完成！已练{today_stats.questions_done}题"
        else:
            remaining = target["questions"] - today_stats.questions_done
            return f"今天还差{remaining}题就完成目标了，要现在做吗？🎯"
```

### 14.6 间隔重复扩展到Self-Explanation

**问题**：不仅复习"会不会"，还要复习"能不能解释出来"。

```python
class ExplanationReviewScheduler:
    """
    解释能力的间隔重复
    
    原理：学生能做对题 ≠ 能解释清楚
    解释能力也会遗忘
    
    调度：
    - 刚学会解释 → 1天后复习
    - 能稳定解释 → 3天后复习
    - 解释能力退化 → 立即复习
    """
    
    def schedule_explanation_reviews(
        self, user_id: str, knowledge_states: dict[str, KnowledgeState],
    ) -> list[ReviewTask]:
        tasks = []
        
        for skill_id, state in knowledge_states.items():
            # 只对"已掌握"的知识点做解释复习
            if state.p_known < 0.7:
                continue
            
            explanation_state = state.explanation_state  # 新增字段
            if not explanation_state:
                continue
            
            days_since = (datetime.now() - explanation_state.last_explained).days
            forgetting = math.exp(-days_since / max(explanation_state.stability, 0.1))
            
            if forgetting > 0.4:  # 解释能力遗忘风险
                tasks.append(ReviewTask(
                    type="explanation_review",
                    skill_id=skill_id,
                    priority=forgetting * 0.8,  # 略低于做题复习
                    instruction="请用自己的话解释这个知识点",
                ))
        
        return sorted(tasks, key=lambda t: t.priority, reverse=True)
```

---

## 11. 实施路线图

### Phase 1: MVP（2-3周）

| 任务 | 优先级 | 依赖 |
|------|--------|------|
| 数据模型迁移（内存→PostgreSQL） | P0 | DB |
| 题目生成API（LLM） | P0 | — |
| 基础ZPD调度 | P0 | DB |
| 前端练习界面（对接后端） | P0 | API |
| 答题+即时反馈 | P0 | API |
| 错题本基础功能 | P1 | DB |

### Phase 2: 增强（2-3周）

| 任务 | 优先级 | 依赖 |
|------|--------|------|
| 多维知识状态模型 | P0 | Phase 1 |
| 间隔重复调度 | P1 | Phase 1 |
| 交错练习 | P1 | Phase 1 |
| 苏格拉底提示系统 | P1 | Phase 1 |
| 错因分析 | P1 | Phase 1 |
| 前端增强（进度条、错题本页面） | P1 | API |

### Phase 3: 高级（3-4周）

| 任务 | 优先级 | 依赖 |
|------|--------|------|
| 多模态题目（图片、公式） | P0 | Phase 1 |
| 手写识别输入 | P1 | 外部API |
| 语音输入（Whisper） | P1 | 外部API |
| 视频讲解推荐 | P1 | B站API |
| 情感感知反馈 | P2 | Phase 2 |
| 轻量游戏化 | P2 | Phase 2 |
| 知识图谱可视化 | P2 | Phase 1 |

---

## 12. 技术决策记录

| 决策 | 选择 | 理由 |
|------|------|------|
| 知识追踪 | 增强BKT + 多维 | MVP用BKT够用，后续可换AKT/DKT |
| 题目生成 | LLM + 质量过滤 | 灵活，可扩展，质量由LLM评审控制 |
| 难度调度 | ZPD + IRT | ZPD理论基础扎实，IRT参数可从数据中估计 |
| 间隔重复 | SM-2变体 | 成熟算法，已被Anki等验证 |
| 错因分析 | 预定义模式 + LLM | 预定义覆盖常见错因，LLM处理复杂情况 |
| 数据库 | PostgreSQL + JSONB | 结构化+半结构化混合，JSONB存多模态内容 |
| 前端 | shadcn/ui + Tailwind | 与现有系统一致 |
