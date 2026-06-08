# 对话模块 × 练习模块 互联互通设计文档

> 版本: v1.1  
> 最后更新: 2026-05-18  
> 状态: **核心集成点已全部实现**，见 [PROGRESS.md](./PROGRESS.md)

---

## 一、设计目标

两个模块不是独立孤岛。**对话是认知脚手架，练习是认知探测器**。互联互通的核心诉求：

| 方向 | 含义 | 核心价值 |
|------|------|---------|
| 对话 → 练习 | 对话触发练习、对话上下文指导选题 | 练得"准"——练正在学的 |
| 练习 → 对话 | 练习结果写回对话记忆、错误驱动深度讲解 | 聊得"透"——AI知道薄弱点 |
| 双向共享 | 统一知识状态、统一会话绑定 | 状态一致——不割裂 |

---

## 二、总架构：数据流全景

```
┌─────────────────────────────────────────────────────────────────────┐
│                        学生                                            │
│                  ┌──────┴──────┐                                     │
│                  │   前端UI     │                                     │
│                  └──────┬──────┘                                     │
│         ┌───────────────┼───────────────┐                            │
│         ▼                               ▼                            │
│  ┌──────────────┐                ┌──────────────┐                    │
│  │   对话模块    │                │   练习模块    │                    │
│  │              │                │              │                    │
│  │ • 树结构会话  │  ① 对话→练习   │ • 题目引擎    │                    │
│  │ • 多模态消息  │ ◄────────────► │ • 自适应调度  │                    │
│  │ • 智能分区    │  ② 练习→对话   │ • 认知诊断    │                    │
│  │ • 分支管理    │                │ • 苏格拉底反馈 │                    │
│  │ • LLM回复     │                │ • 错题本      │                    │
│  └──────┬───────┘                └──────┬───────┘                    │
│         │                               │                            │
│         └───────────┬───────────────────┘                            │
│                     │                                                │
│         ┌───────────┴───────────┐                                    │
│         │   共享数据层           │                                    │
│         │                       │                                    │
│         │ ③ SharedKnowledgeState │ ← 统一多维知识状态(MDKS)          │
│         │ ④ Branch.practice_*   │ ← 练习session挂载到对话branch      │
│         │ ⑤ Partition.context   │ ← 练习结果更新分区摘要             │
│         └───────────────────────┘                                    │
└─────────────────────────────────────────────────────────────────────┘
```

五大集成点：

| # | 集成点 | 数据方向 | 触发时机 |
|---|--------|---------|---------|
| ① | 对话→练习：上下文感知选题 | 对话context → 练习session | 用户说"出几道题" |
| ② | 练习→对话：结果写回记忆 | 练习结果 → branch节点+分区摘要 | session完成时 |
| ③ | 共享知识状态（MDKS） | 双向实时读写 | 每次答题 + 每次深度对话 |
| ④ | 内联练习（对话中做题） | 对话消息流嵌入练习块 | 用户触发/系统推荐 |
| ⑤ | 练习错误→深度对话推荐 | 错误分析 → 对话提示 | 连续错题/概念错误 |

---

## 三、③ 共享知识状态（SharedKnowledgeState）—— 核心枢纽

### 3.1 设计原则

**一个用户只有一个 MDKS 实例**。对话和练习不各自维护知识状态，共用同一份数据。

```
       共享 MDKS（PostgreSQL knowledge_states 表）
      ┌─────────────────────────────────────────────┐
      │  user_id + skill_id → {                      │
      │    p_known: 0.65,                            │
      │    dimensions: {                             │
      │      concept:     { p_known: 0.7  },          │
      │      procedure:   { p_known: 0.55 },          │
      │      application: { p_known: 0.45 },          │
      │      transfer:    { p_known: 0.30 },          │
      │    },                                        │
      │    misconception_flags: [...],                │
      │    pseudo_mastery_flags: [...],               │
      │    last_updated: "2026-05-17T14:30:00",       │
      │  }                                           │
      └──────┬──────────────────┬───────────────────┘
             │                  │
    ┌────────▼────────┐  ┌─────▼──────────┐
    │ 练习模块更新      │  │ 对话模块更新     │
    │                 │  │                 │
    │ update_from_    │  │ update_from_    │
    │ practice()     │  │ conversation()  │
    │                 │  │                 │
    │ • BKT更新       │  │ • 提问→p↑      │
    │ • 提示打折      │  │ • 自我解释→p↑   │
    │ • 解释评分调整   │  │ • 错误纠正→p↑   │
    │ • 疲劳感知      │  │ • 深度讨论→p↑   │
    └────────────────┘  └────────────────┘
```

### 3.2 练习模块调用

```python
# 每次答题后调用
def update_from_practice(
    skill_id: str,
    is_correct: bool,
    hint_level: int,             # 提示等级 0-4
    error_analysis: ErrorAnalysis | None,
    explanation_score: float | None,   # 自我解释质量 0-1
) -> KnowledgeState:
    """
    更新逻辑（按优先级）：
    1. 基础BKT更新（答对/答错改变 p_known）
    2. 提示打折 —— hint_level越高，p_known提升幅度越小
       (hint=4 时更新幅度 ×0.05，几乎不增长)
    3. 解释评分调整：
       - 答对+解释好(>0.8) → 追加提升（真正掌握）
       - 答对+解释差(<0.5) → 标记伪掌握，不提升
       - 答错+解释好(>0.7) → p_known不降，增加p_slip（计算失误）
       - 答错+解释差(<0.5) → 大幅下降（真不理解）
    4. 四维度分别更新：选择题 → concept，计算题 → procedure，应用题 → application

    已实现状态：✅
    代码位置：backend/app/core/knowledge_trace.py → BKTEngine.update()
    """
```

### 3.3 对话模块调用

```python
# 每次有意义的对话交互后调用
def update_from_conversation(
    skill_id: str,
    interaction_type: str,  # "question_asked" | "explanation_given" |
                            # "concept_discussed" | "misconception_corrected"
    depth: int,             # 对话深度(对话轮次/解释复杂度)
) -> KnowledgeState:
    """
    对话改变知识状态的场景：
    
    | 交互类型                  | 更新行为                           | 幅度  |
    |--------------------------|-----------------------------------|-------|
    | question_asked           | concept.p_known 微增（在思考）    | +0.02 |
    | explanation_given (depth≥3)| application.p_known 提升        | +0.05 |
    | concept_discussed        | concept.p_known 提升              | +0.05 |
    | misconception_corrected  | concept.p_known 大幅提升          | +0.10 |
    
    原则：对话中纠正错误 > 自己解释 > 深度讨论 > 简单提问。
    对话更新幅度远小于练习更新（练习是直接检测）。

    已实现状态：⚠️ 设计完成，代码未实现
    """
```

### 3.4 MDKS 对两个模块的直接影响

| 模块 | 如何使用MDKS |
|------|-------------|
| 练习模块 | ZPD调度用 p_known 决定难度；间隔重复用 p_known + forgetting_curve 决定复习时间 |
| 对话模块 | LLM系统提示注入："已知：导数(70%), 积分(45%←薄弱)" |
| 前置卡控 | 前置不达标 → 练习降权、对话中不推荐进阶概念 |

---

## 四、① 对话→练习：上下文感知选题

### 4.1 为什么需要

用户说"出几道题"，如果不看对话上下文，可能随机出一道与当前讨论无关的题。这违背了"学习连贯性"。

### 4.2 设计方案

```python
class ContextAwarePracticeTrigger:
    """
    触发练习时，从对话上下文提取：
    1. 知识点标签 → 确定 skill_id 集合
    2. Bloom层次 → 确定考察深度
    3. 困惑信号 → 降低难度或切换题型
    """

    def trigger(self, branch: Branch, shared_ks: SharedKnowledgeState) -> PracticeSession:
        # Step 1: 从最近对话中提取知识主题
        #   方法：取branch最近5条消息的text_summary → Embedding搜索匹配skill_id
        inferred_skills = self._infer_skills(branch)

        # Step 2: 从对话中推断Bloom层次
        #   用户问"为什么" → concept
        #   用户问"怎么做" → procedure
        #   用户问"有什么应用" → application
        #   用户说"帮我讲讲" → concept (先理解)
        bloom_level = self._infer_bloom(branch)

        # Step 3: 查MDKS，选匹配的ZPD难度
        #   该skill的当前p_known → 映射到题目difficulty
        skill_p_known = shared_ks.get(inferred_skills[0]).p_known
        target_difficulty = self._zpd_difficulty(skill_p_known)

        # Step 4: 识别困惑信号
        #   检测对话中是否有 "不懂" "不太明白" "有点绕" 等
        #   有困惑 → 降低目标Bloom层次、增加hint配额
        confused = self._detect_confusion(branch)

        return PracticeSession(
            skill_ids=inferred_skills,
            bloom_level=bloom_level if not confused else "understand",
            difficulty=target_difficulty,
            mode="contextual",  # 标记来源：对话触发
        )
```

### 4.3 Bloom层次推断规则

| 用户语言模式 | 推断Bloom层次 | 示例 |
|-------------|-------------|------|
| "是什么" "定义" | 记忆(remember) | "极限的定义是什么" |
| "为什么" "解释一下" | 理解(understand) | "为什么导数可以表示斜率" |
| "怎么做" "步骤" "解法" | 应用(apply) | "这道题怎么做" |
| "有什么区别" "对比" | 分析(analyze) | "不定积分和定积分有什么区别" |
| "证明" "推导" | 评价(evaluate) | "证明拉格朗日中值定理" |
| "设计" "构造" | 创造(create) | "设计一个算法来解决..." |

### 4.4 困惑信号的检测

```python
CONFUSION_PATTERNS = [
    r"不太?懂",
    r"不明白",
    r"有点绕",
    r"没听懂",
    r"再说一遍",
    r"什么是",
    r"还是不会",
]

# 检测到困惑 → 
#   - 降低Bloom层次（从apply降到understand）
#   - 增加内联练习题而非独立session
#   - AI先解释再出题，而非直接出题

已实现状态：✅ API 端点已实现 (`POST /api/practice/context-trigger`)；服务端 `context_trigger.py` 存在
```

---

## 五、② 练习→对话：结果写回记忆

### 5.1 设计目标

练习结束后，对话系统要知道：
1. 在这个话题下练过了
2. 练了多少题、正确率多少
3. 薄弱点是什么
4. 错了什么类型的题

### 5.2 三层写入

```
练习Session完成
    │
    ├── Layer 1: Branch节点写入 (元数据消息，不占LLM token)
    │   └── 在branch下追加一条 role="system" 的元数据节点
    │
    ├── Layer 2: Branch字段更新
    │   ├── branch.practice_sessions.append(session_id)
    │   └── branch.practice_summary = "已练12题,正确率70%,薄弱:导数概念"
    │
    └── Layer 3: Partition上下文更新
        └── partition.context_summary += "练习(05/17): 导数 正确率70%"
```

### 5.3 元数据节点格式

```python
TreeNode(
    role="system",
    content_blocks=[TextBlock(text="练习记录：3/4正确，用时8分钟，薄弱点：导数概念")],
    metadata={
        "type": "practice_summary",
        "session_id": "sess_abc123",
        "accuracy": 0.75,
        "skills_tested": ["calculus_derivative_concept"],
        "error_patterns": ["conceptual"],  # 错误类型
        "struggling_skills": ["calculus_derivative_concept"],
    }
)
# 此节点不发给LLM（通过 role="system" + metadata.type 过滤）
# 只给前端展示："你在这里练过一次，正确率75%"
```

### 5.4 LLM上下文注入

每次对话时，LLM系统提示中注入练习上下文：

```
[Practice]
- 导数讨论(05/17): 已练4题,正确率75%,薄弱:概念
- 极限讨论(05/15): 已练10题,正确率90%
```

这样AI在回复时自然知道：
- "你上次在导数概念上有点困惑，我们来聊聊" 
- "你的极限掌握得不错，可以试试更难的题"

```
已实现状态：✅ Layer 1+2+3 已实现
代码位置：backend/app/services/practice_integrator.py
注入逻辑：backend/app/services/conversation_llm.py → _build_context_messages() L82-89
```

---

## 六、④ 对话中的内联练习

### 6.1 设计目标

学生不需要跳转到独立练习页面。在对话流中就能：看到题 → 作答 → 获得反馈 → 继续聊。

### 6.2 交互模型

```
用户: "出几道极限的题考考我"
      ↓
AI回复:    "好的，来试试这道题：
           📝 求 lim(x→0) sin(x)/x = ?
           
           [A] 0   [B] 1   [C] ∞   [D] 不存在
           
           想好了就选一个字母～ 💡"
      ↓
[前端渲染为内联选择题，4个可点击按钮]
      ↓
用户: "B"
      ↓
AI回复:    "✅ 正确！lim(x→0) sin(x)/x = 1 是重要极限。
           能用自己的话解释一下为什么是1吗？"
      ↓
用户: "因为当x趋近于0时，sin(x)≈x，所以比值趋近于1"
      ↓
AI回复:    "很好的解释！这正是等价无穷小的核心思想。
           要不要再来一道？还是继续聊极限的其他性质？"
```

### 6.3 技术实现

```python
class InlinePracticeHandler:
    """
    核心思想：练习题块是对话中的一种特殊 ContentBlock，
    不是独立页面，而是嵌入在对话消息流中。
    """

    def create_inline_question(
        self, branch: Branch, skill_id: str, bloom_level: str
    ) -> ResponseBlock:
        """生成一条内联练习题，作为助手回复的一部分"""
        question = self.question_generator.generate(skill_id, bloom_level)
        
        return ResponseBlock(
            type="practice",
            status="waiting_answer",
            content={
                "question_id": question.id,
                "stem": question.content.stem,
                "options": [o.model_dump() for o in question.options],
                "answer_type": question.answer_type,
            },
            # 关联到当前branch，用于后续知识状态更新
            metadata={
                "skill_id": skill_id,
                "branch_id": branch.id,
            }
        )

    def handle_answer(
        self, practice_block_id: str, student_answer: str,
        hint_level: int = 0,
    ) -> tuple[str, KnowledgeState]:
        """处理学生对内联练习题的回答"""
        question = self.store.get(practice_block_id)
        is_correct = self._check_answer(question, student_answer)

        # 更新共享知识状态
        state = shared_ks.update_from_practice(
            skill_id=question.skill_id,
            is_correct=is_correct,
            hint_level=hint_level,
        )

        # 生成对话回复（而非独立反馈页）
        if is_correct:
            reply = f"✅ 正确！{question.explanation[:100]}\n\n继续下一题还是聊聊这个知识点？"
        else:
            # 不是给完整解析，而是引导讨论
            reply = (
                f"❌ 不对哦。你的答案是{student_answer}。\n"
                f"提示：{question.hints[0] if question.hints else '再想想思路'}\n"
                f"试试看？或者想让我详细讲解？"
            )

        return reply, state
```

### 6.4 内联练习 vs 独立练习

| 维度 | 内联练习 | 独立练习 |
|------|---------|---------|
| 位置 | 对话消息流中 | /practice 页面 |
| 题量 | 1-3题 | 10-30题 |
| 目标 | 即时检测理解 | 系统训练 |
| 反馈 | 引导式回复（对话） | 完整解析+错因分析 |
| 知识更新 | ✅ 写入MDKS | ✅ 写入MDKS |
| 适用场景 | "出几道题考考我" | "我要做30分钟练习" |
| 数据记录 | 挂载到branch | 独立session + 挂载到branch |

```
已实现状态：✅ 后端 3 个端点已实现 (`POST /api/practice/inline/create|answer|hint`)；服务端 `inline_practice.py` 存在；前端组件 `InlinePracticeBlock.tsx` 存在
```

---

## 七、⑤ 练习错误→深度对话推荐

### 7.1 设计原理

研究（Chen et al.）表明：引导发现（guided discovery）比纯粹做题效果好4-10倍。当检测到概念性错误或连续错误时，系统应主动建议切换到对话模式进行深度讨论。

### 7.2 触发条件

```python
class PracticeToDialogueRecommendation:
    """
    什么时候推荐从练习切换到对话：
    """

    def should_recommend(self, session: PracticeSession) -> str | None:
        """
        返回推荐文案，或None（不推荐）
        """

        # 条件1: 同一知识点连续错 ≥2 次
        #   → "这个知识点连续错了两次，要不要在对话中详细讨论一下？💬"
        recent = session.last_n_attempts(3)
        same_skill_errors = self._count_same_skill_errors(recent)
        if same_skill_errors >= 2:
            return f"连续错了{same_skill_errors}次相同知识点，聊聊会更有效。要切换到对话吗？💬"

        # 条件2: 概念性错误（最严重的错误类型）
        #   → "这个是概念理解的问题，做题效果有限。聊聊会更深入"
        latest_error = session.latest_error_analysis
        if latest_error and latest_error.error_type == ErrorType.CONCEPTUAL:
            return f"检测到概念理解偏差：{latest_error.misconception[:30]}... 要做个深入讨论吗？💬"

        # 条件3: 迷思概念（带具体描述的错误）
        #   → "你对'切线斜率=函数值'的理解有偏差，聊聊？"
        if latest_error and latest_error.misconception:
            return f"你对'{latest_error.misconception[:30]}'的理解可能有偏差。聊聊这个问题？💬"

        # 条件4: 挫败感上升（连续错4题以上）
        #   → "做了挺多题，要不停下来聊聊思路？也许换个角度能豁然开朗"
        consecutive_wrong = self._count_consecutive_wrong(session)
        if consecutive_wrong >= 4:
            return "做了好几道都错了，是不是思路卡住了？停下来聊聊也许能豁然开朗 💬"

        return None
```

### 7.3 从错误到深度对话的闭环

```
练习中检测到错误
    ↓
分析错误类型和迷思概念
    ↓
推荐切换到对话
    ↓
学生选择"聊聊"
    ↓
对话系统接收上下文：
  - 错误题目
  - 学生的错误答案
  - 分析出的迷思概念
  - MDKS当前状态
    ↓
AI以"引导发现"模式回复：
  "你刚才做导数题时选了B，我猜你可能把切线斜率理解成函数值了。
   我们来看一个例子：f(x)=x² 在 x=1 处，函数值是1，切线斜率是多少？"
    ↓
学生回答 / 讨论
    ↓
SharedKnowledgeState.update_from_conversation(
    interaction_type="misconception_corrected"
)
    ↓
该知识点 p_known 提升
```

```
已实现状态：✅ API 端点已实现 (`POST /api/practice/dialogue-recommend`)；服务端 `dialogue_recommender.py` 存在
```

---

## 八、对话中的 "练习回顾"

### 8.1 场景

学生在对话中问：
- "我导数掌握得怎么样了？"
- "最近练习情况怎么样？"
- "我哪个知识点最薄弱？"

### 8.2 实现

```python
class PracticeRecallInConversation:
    """在对话中回答关于练习表现的问题"""

    def generate_recall(
        self, user_id: str, partition_id: str | None, time_range: str = "7d"
    ) -> str:
        # 查当前分区下所有branch的练习记录
        # 汇总统计
        # 生成自然语言回复

        stats = self._aggregate_practice_stats(user_id, partition_id, time_range)

        if stats.total == 0:
            return "你在这个话题下还没有做过练习哦，要不要现在来几道？📝"

        lines = [f"📊 过去一周你在{stats.subject}的练习情况："]
        lines.append(f"共 {stats.total} 题，正确率 {stats.accuracy:.0%}")

        if stats.weak_skills:
            lines.append(f"\n🔴 需要加强的：{'、'.join(stats.weak_skills)}")
        if stats.strong_skills:
            lines.append(f"🟢 掌握扎实的：{'、'.join(stats.strong_skills)}")

        if stats.trend == "improving":
            lines.append("\n📈 最近正确率在上升，继续保持！")
        elif stats.trend == "declining":
            lines.append("\n📉 最近正确率有点下降，是不是最近学的难度大了？")

        return "\n".join(lines)
```

```
已实现状态：✅ API 端点已实现 (`GET /api/practice/recall`)；服务端 `practice_recall.py` 存在
```

---

## 九、练习Session与对话Branch的绑定

### 9.1 数据模型

```python
class Branch:
    # ... 现有字段 ...
    practice_sessions: list[str] = []  # 关联的练习session_id列表
    practice_summary: str = ""         # 紧凑摘要："已练12题,正确率70%,薄弱:导数"
```

### 9.2 生命周期

```
创建branch
    ↓
... 对话进行中 ...
    ↓
用户说"出几道题"
    ↓
ContextAwarePracticeTrigger → 创建 PracticeSession
    ├── session 创建时记录 branch_id
    └── session 完成后 → integrate_practice_to_branch()
        ├── branch.practice_sessions.append(session_id)
        ├── branch.practice_summary 更新
        └── 元数据节点写入branch
    ↓
... 继续对话（AI能感知练习结果）...
    ↓
branch归档 → 练习记录作为元数据保留
```

### 9.3 前端展示

打开对话branch的侧边栏/信息面板时：

```
┌─ 分支信息 ────────────────────┐
│ 📝 导数概念讨论                │
│ 消息: 15条                     │
│ 创建: 05/15                    │
│                                │
│ 📊 练习记录                    │
│ 05/17: 4题, 正确率75%          │
│   薄弱: 导数概念                │
│ [查看错题]                     │
└────────────────────────────────┘
```

```
已实现状态：✅ 后端binding已实现，前端UI未实现
```

---

## 十、对话模块中的练习触发机制

### 10.1 三种触发方式

| 触发方式 | 触发条件 | 练习模式 |
|---------|---------|---------|
| 用户主动请求 | 关键词匹配："出题""练习""做题""测试""考我" | 内联练习 |
| AI主动建议 | 讨论深度≥3轮且MDKS显示p_known<0.5 | 内联练习 |
| 定时提醒 | 间隔重复调度器推荐复习 | 独立练习session |

### 10.2 关键词检测（对话系统现有）

```python
# backend/app/services/tool_executor.py 或类似位置
PRACTICE_KEYWORDS = {
    r"出题|练习|做题|测试|考我": "generate_practice",
}
```

### 10.3 AI主动建议的触发逻辑

```python
def should_suggest_practice(branch: Branch, shared_ks: SharedKnowledgeState) -> bool:
    """
    对话中AI应该主动建议练习的条件：
    1. 当前讨论深度 ≥ 3轮
    2. 主题知识点 p_known < 0.5（发展中/初学）
    3. 最近5条消息中没有练习
    """
    depth = len([n for n in branch.recent_messages(10) if n.role in ("user", "assistant")])
    if depth < 3:
        return False

    skill_ids = extract_skill_ids_from_branch(branch)
    for sid in skill_ids:
        if shared_ks.get(sid).p_known < 0.5:
            return True

    return False

# AI回复时注入建议：
# "...(正常回复)... 对了，这个知识点要不要出几道题练练手？📝"
```

```
已实现状态：⚠️ 设计完成，代码未实现（需要在 conversation_llm 系统提示中加入主动建议逻辑）
```

---

## 十一、实现状态总览

> **最后更新: 2026-05-18** — 学情仪表板设施阶段

| # | 集成点 | 设计 | 后端 | 前端 | 优先级 |
|---|--------|------|------|------|--------|
| ③ | 共享知识状态 MDKS | ✅ | ✅ BKT.update() + **load_or_create/save_state 持久化** | N/A | P0 ✅ |
| ② | 练习→对话 结果写回 | ✅ | ✅ practice_integrator.py | ⬜ branch侧边栏显示 | P0 ✅ |
| ② | LLM上下文注入 | ✅ | ✅ conversation_llm.py L82-89 | N/A | P1 ✅ |
| ⑨ | Session-Branch绑定 | ✅ | ✅ (branch_id字段) | ⬜ 前端展示 | P1 ✅ |
| ① | 对话→练习 上下文选题 | ✅ | ✅ /context-trigger API | N/A | P2 ✅ |
| ④ | 内联练习 | ✅ | ✅ /inline/* 3个端点 | ⬜ InlinePracticeBlock 前端组件 | P2 ⚠️ |
| ⑤ | 错误→对话推荐 | ✅ | ✅ /dialogue-recommend API | N/A | P2 ✅ |
| ③ | 对话→MDKS更新 | ✅ | ⬜ update_from_conversation | N/A | P2 |
| ⑧ | 练习回顾 | ✅ | ✅ /recall API | N/A | P3 ✅ |
| — | 知识状态持久化 | ✅ | ✅ bkt_engine.load_or_create/save_state | N/A | **新增** |
| — | 错因分布聚合 | ✅ | ✅ /stats error_distribution | N/A | **新增** |
| — | 历史环比对比 | ✅ | ✅ /stats prev_week | N/A | **新增** |
| — | 时段热力图 | ✅ | ✅ /stats hourly_heatmap | N/A | **新增** |
| — | 学情仪表板 API | ✅ | ✅ /stats 增强（mastery_bars） | ⬜ 仪表板前端页面 | **新增** |

### 关键变更说明

- **知识状态已持久化**: `UserData.knowledge_states` 字段 → `storage.load/save`，答题后自动写入磁盘
- **BKT 引擎新增 3 个持久化方法**: `load_or_create()`, `save_state()`, `load_all_states()`
- **/stats 端点大幅增强**: 新增 error_distribution、prev_week 环比、mastery_bars（读持久化 KnowledgeState）、hourly_heatmap、daily_trend
- **文档标记修正**: 原本标记为 ⬜ 的 P2 接口实际已实现（context-trigger/inline/dialogue-recommend/recall）

### 待完成

| 项目 | 状态 |
|------|------|
| 内联练习前端组件 | ⬜ InlinePracticeBlock.tsx 需验证/完善 |
| 前端 branch 侧边栏显示练习记录 | ⬜ |
| `update_from_conversation` 对话→BKT | ⬜ 设计完成，后端未实现 |
| 仪表板前端页面 (`analytics/page.tsx`) | ⬜ 需基于新 API 重写 |
| 建议行动规则引擎 | ⬜ 设计有伪代码，未实现 |
| 对话行为数据接入仪表板 | ⬜ 设计阶段 |

---

## 十二、关键设计决策

### 12.1 为什么是"非阻塞写入"而非"同步等待"

练习结果写入对话branch是**非阻塞回调**（session完成时触发），而不是同步等待。原因：
- 练习session是独立流程，对话系统不需要等待
- 写入fail不影响练习核心流程（降级处理）
- 异步写入避免增加练习API的响应延迟

### 12.2 为什么Branch.practice_summary是字符串而非结构化对象

```python
# 为什么不是：
practice_summary: dict = {"total": 12, "accuracy": 0.7, "weak": ["导数"]}

# 而是：
practice_summary: str = "已练12题,正确率70%,薄弱:导数"
```

原因：字符串格式直接注入LLM上下文，不需要额外解析；结构化数据需要转换步骤，且增加LLM token开销（JSON格式比紧凑文本多30-50%）。

### 12.3 对话更新MDKS幅度为何远小于练习更新

| 场景 | MDKS更新幅度 | 原因 |
|------|------------|------|
| 练习答对 | +0.1~0.2 | 直接检测 |
| 对话中解释正确 | +0.05 | 间接推断，证据弱 |
| 练习答错 | -0.1~0.2 | 直接检测 |
| 对话中被纠正 | +0.1 | 外部介入，值得信赖 |
| 对话中提问 | +0.02 | 微弱信号，仅表明在思考 |

原则：**只有直接的行为检测（做题）才能大幅改变知识状态估计**。对话中的信号是辅助性的。

---

## 十三、与外部系统的集成

### 13.1 与B站搜索的联动

```
练习错误 → 搜索B站视频 → 推荐给用户
    ↓
"这道题的正确率只有60%，检测到你对'导数极值'有困惑。
 🎬 推荐视频：3Blue1Brown - 导数的本质"
```

### 13.2 与用户资料索引的联动

```
练习错误 → 搜索用户上传的资料 → 精准引用
    ↓
"你的讲义《高等数学第三章》第12页有这个知识点的详细讲解"
```

---

## 附录A：数据流时序图

```
时间轴 →

T0: 学生在对话中说 "极限的定义是什么"
T1: AI回复解释
    └─ update_from_conversation("question_asked", depth=1)
       → MDKS: concept 微增

T2: 学生说 "出几道题考考我"
T3: ContextAwarePracticeTrigger
    ├─ 提取上下文: "极限", "定义"
    ├─ 匹配skill: calculus_limit_concept
    ├─ 查MDKS: p_known=0.45 → target_difficulty=0.5
    └─ 生成3道内联题

T4: 学生答题 (对,错,对)
T5: 每次答题 → update_from_practice()
    → MDKS 三次更新: concept 0.45→0.52→0.48→0.55

T6: Session完成 → integrate_practice_to_branch()
    ├─ branch.practice_sessions += [sess_001]
    ├─ branch.practice_summary = "已练3题,正确率67%,薄弱:极限概念"
    └─ 元数据节点写入branch

T7: 检测到错误类型=conceptual → 推荐深度对话

T8: 学生继续聊天，AI的LLM上下文自动注入：
    "[Practice] - 极限讨论: 已练3题,正确率67%,薄弱:概念"
    AI: "你刚才做题时对极限概念的理解还有点模糊，我们聊聊..."
    └─ 对话纠正 → update_from_conversation("misconception_corrected")
       → MDKS: concept 0.55→0.65

T9: 第二天，学生打开对话branch
    侧边栏显示: 📊 练习记录: 05/17 3题 67%
    AI看到上下文: "你昨天在极限概念上练过，正确率67%，现在理解更好了"
```

---

## 附录B：代码文件索引

| 文件 | 内容 | 状态 |
|------|------|------|
| `backend/app/core/knowledge_trace.py` | BKT引擎 + **load_or_create/save_state 持久化** | ✅ 已实现 |
| `backend/app/services/practice_integrator.py` | 练习→对话结果写入 | ✅ 已实现 |
| `backend/app/services/conversation_llm.py` | LLM上下文注入(L82-89) | ✅ 已实现 |
| `backend/app/api/practice.py` | 练习API + **/stats 增强（错因/环比/热力/掌握度）** | ✅ 已实现 |
| `backend/app/schemas/practice.py` | 练习数据模型 | ✅ 已实现 |
| `backend/app/schemas/conversation.py` | Branch.practice_* + **UserData.knowledge_states/practice_sessions** | ✅ 已实现 |
| `backend/app/services/zpd_scheduler.py` | ZPD调度（使用MDKS） | ✅ 已实现 |
| `backend/app/services/question_generator.py` | LLM题目生成 | ✅ 已实现 |
| `docs/practice-system-design-v2.md` (§7) | 对话×练习联动设计 | ✅ 已写 |
| `docs/study-planning-design.md` | 学习规划系统设计 | ✅ 新文档 |
| `docs/knowledge-graph-design.md` | 知识图谱系统设计 | ✅ 新文档 |

---

## 附录C：全系统模块互联矩阵

> 更新: 2026-05-18 — 加入学习规划+知识图谱

### C.1 互联总览

```
                          ┌──────────────┐
                          │  知识图谱     │
                          │  (Graph)     │
                          └──┬───┬───┬──┘
                 前置依赖    │   │   │  掌握度
               ┌────────────┘   │   └────────────┐
               ▼                │                ▼
┌──────────┐  选题    ┌─────────┴────────┐  推荐  ┌──────────┐
│  练习系统 │◀────────│    学习规划       │──────▶│  BKT引擎  │
│ Practice │────────▶│   StudyPlan      │◀──────│ k_trace  │
└────┬─────┘ 答题记录 └────────┬─────────┘ 知识推荐└──────────┘
     │                        │
     │ stats/behavior         │ plan items
     ▼                        ▼
┌──────────┐            ┌──────────┐
│ 行为分析  │───────────▶│ 习惯养成  │
│ Behavior │ 疲劳/规律   │ Habits   │
└──────────┘            └──────────┘
     │
     │ daily_trend + heatmap
     ▼
┌──────────┐            ┌──────────┐
│ 学情仪表  │◀──────────│ 对话系统  │
│ Analytics│ 练习上下文  │Conversat │
└──────────┘            └──────────┘
```

### C.2 全量连接矩阵

| # | 从 | 到 | 数据 | 触发 | 状态 |
|---|----|----|------|------|:--:|
| 1 | BKT | StudyPlan | recommend_practice() → plan items | 生成计划 | ✅ |
| 2 | BKT | Graph | p_known → node.mastery | 实时查询 | 🔴 |
| 3 | BKT | Practice | 知识状态 → 选题难度 | 创建session | ✅ |
| 4 | ZPD | Practice | 能力估计 → ZPD选题 | 创建session | ✅ |
| 5 | ZPD | StudyPlan | 难度调整 → 计划时长 | 生成计划 | 🟡 |
| 6 | Practice | StudyPlan | session完成 → task标记完成 | 手动触发 | ✅ |
| 7 | Practice | Behavior | daily_trend + hourly_heatmap | 查询stats | ✅ |
| 8 | Practice | ErrorBook | is_correct=F → error_book | 提交答案 | ✅ |
| 9 | Practice | Conversation | session结果 → branch summary | session完成 | 🟡 |
| 10 | Behavior | HabitFormation | streak/fatigue → goal/pomodoro | 查询behavior | ✅ |
| 11 | Behavior | Analytics | 全部指标 → 6面板 | 页面加载 | ✅ |
| 12 | HabitFormation | Analytics | daily_goal → 进度环 | 页面加载 | ✅ |
| 13 | Graph | ZPD | 前置依赖 → can_practice() | 选题时 | 🔴 |
| 14 | Graph | StudyPlan | 学习路径 → plan items | 生成计划 | 🔴 |
| 15 | Graph | Conversation | 图谱引用 → 对话上下文 | 对话触发 | 🔴 |
| 16 | Content | Graph | 知识点 → 推荐资料 | 搜索时 | 🔴 |
| 17 | Content | StudyPlan | 资料匹配 → plan resources | 生成计划 | 🟡 |
| 18 | Conversation | Practice | 对话上下文 → 选题 | 对话触发出题 | 🟡 |
| 19 | Conversation | StudyPlan | 对话意图 → 计划调整 | coach agent | 🔴 |

**图例**：✅=已实现 🟡=部分/有代码但未全链路 🔴=未实现
| `docs/conversation-system-design.md` | 对话系统设计 | ✅ 已写 |
| `docs/dialogue-practice-integration.md` | **本文档** | ✅ |
