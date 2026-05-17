# 练习系统设计文档

> 基于 conversation-system-design.md 的多模态回复架构
> 创建: 2026-05-17

---

## 一、设计目标

练习系统是学习平台的核心功能，需要实现：

1. **题库管理** — LLM生成 + 手动创建 + 导入
2. **智能推荐** — 基于BKT知识追踪，推荐薄弱知识点的题目
3. **即时批改** — 答案判断 + 错因分析 + 知识状态更新
4. **多模态题目** — 文字+图片+公式混合
5. **错题本** — 自动收集错题，定期复习
6. **学习统计** — 正确率、用时、知识点掌握度

---

## 二、与对话系统的关系

练习题可以通过两种方式触发：

```
方式1: 对话中触发
  用户："出几道极限的题"
  → predict_tools() 检测到 generate_practice
  → ToolExecutor 调用练习生成器
  → ResponseBlock(type="practice") 嵌入对话

方式2: 练习页面独立使用
  用户进入 /practice 页面
  → 调用 GET /api/practice/questions
  → 展示题库中的题目
```

两种方式共享同一个题库和BKT引擎。

---

## 三、数据模型

### 3.1 练习题 (PracticeQuestion)

```python
class PracticeQuestion(BaseModel):
    id: str                          # UUID
    subject: str                     # 学科
    skill_id: str                    # 知识点ID
    difficulty: str                  # easy/medium/hard
    question_type: str               # choice/fill/code/essay
    
    # 题目内容（多模态）
    content_blocks: list[ContentBlock]  # 文字+图片+公式
    question_text: str               # 纯文本版本（用于搜索/索引）
    
    # 选项（选择题）
    options: list[str] | None        # 选项列表
    correct_answer: str              # 正确答案
    
    # 解析
    explanation: str                 # 解析说明
    explanation_blocks: list[ContentBlock]  # 解析的多模态版本
    hints: list[str]                 # 提示列表
    
    # 元数据
    source: str                      # 来源(llm/manual/imported)
    created_at: float
    updated_at: float
```

### 3.2 答题记录 (AttemptRecord)

```python
class AttemptRecord(BaseModel):
    id: str
    user_id: str
    question_id: str
    answer: str                      # 用户答案
    is_correct: bool
    time_spent: float                # 用时(秒)
    
    # 错因分析
    error_type: str | None           # calculation/concept/reading/other
    error_analysis: str | None       # 详细错因
    
    # 知识状态更新
    skill_id: str
    p_known_before: float            # 答题前掌握度
    p_known_after: float             # 答题后掌握度
    
    created_at: float
```

### 3.3 练习会话 (PracticeSession)

```python
class PracticeSession(BaseModel):
    id: str
    user_id: str
    subject: str | None              # 学科筛选
    skill_ids: list[str] | None      # 知识点筛选
    difficulty: str | None           # 难度筛选
    
    # 状态
    question_ids: list[str]          # 本次练习的题目列表
    current_index: int               # 当前做到第几题
    answers: dict[str, str]          # question_id → 用户答案
    results: dict[str, bool]         # question_id → 是否正确
    
    # 统计
    total_questions: int
    correct_count: int
    total_time: float                # 总用时
    
    # 时间
    created_at: float
    completed_at: float | None
    
    # 来源
    source: str                      # "practice_page" | "conversation" | "review"
```

---

## 四、API设计

### 4.1 题目管理

```
GET    /api/practice/questions           — 获取题目列表(筛选)
GET    /api/practice/questions/{id}      — 获取单个题目
POST   /api/practice/questions/generate  — LLM生成题目 ⭐
```

### 4.2 答题流程

```
POST   /api/practice/sessions           — 创建练习会话
GET    /api/practice/sessions/{id}      — 获取会话状态
POST   /api/practice/sessions/{id}/next — 下一题
POST   /api/practice/submit             — 提交答案(即时批改)
```

### 4.3 统计与推荐

```
GET    /api/practice/recommend/{user_id} — 智能推荐题目
GET    /api/practice/errors/{user_id}    — 错题本
GET    /api/practice/stats/{user_id}     — 学习统计
```

---

## 五、LLM生成练习题

### 5.1 生成流程

```
用户请求："出几道极限的题"
  ↓
构建提示词(学科+知识点+难度+数量)
  ↓
调用 LLM 生成题目(JSON格式)
  ↓
解析+验证格式
  ↓
存储到题库
  ↓
返回 ResponseBlock(type="practice")
```

### 5.2 提示词模板

```
你是一个出题专家。请为{subject}学科的{skill_id}知识点生成{count}道{difficulty}难度的练习题。

要求：
1. 题目类型：{question_type}
2. 每道题包含：题目、选项(选择题)、正确答案、解析、提示
3. 如果涉及数学公式，使用LaTeX格式
4. 难度说明：基础=概念理解，进阶=综合应用，挑战=拓展思考

请返回JSON格式：
[
  {
    "question_text": "...",
    "options": ["A...", "B...", "C...", "D..."],
    "correct_answer": "A",
    "explanation": "...",
    "hints": ["提示1", "提示2"]
  }
]
```

---

## 六、即时批改

### 6.1 批改流程

```
用户提交答案
  ↓
判断答案是否正确(精确匹配+模糊匹配)
  ↓
更新BKT知识状态
  ↓
如果错误：LLM分析错因
  ↓
返回批改结果
```

### 6.2 错因分类

| 错因 | 说明 | 示例 |
|------|------|------|
| calculation | 计算错误 | 2+3=6 |
| concept | 概念混淆 | 极限=导数 |
| reading | 审题不清 | 求最大值写成最小值 |
| method | 方法错误 | 用错公式 |
| other | 其他 | 猜错 |

---

## 七、前端设计

### 7.1 练习页面布局

```
┌─────────────────────────────────────┐
│  练习                    [难度筛选]  │
│                                      │
│  ┌─ 进度条 ─────────────────────┐  │
│  │ ████████░░░░░░ 3/5           │  │
│  └──────────────────────────────┘  │
│                                      │
│  ┌─ 题目卡片 ───────────────────┐  │
│  │ 📐 高等数学 · 进阶            │  │
│  │                               │  │
│  │ 求函数 f(x)=x³-3x²+2        │  │
│  │ 在区间 [0,3] 上的最值。       │  │
│  │                               │  │
│  │ ○ A. 最大值2，最小值-2       │  │
│  │ ● B. 最大值2，最小值-4       │  │
│  │ ○ C. 最大值4，最小值-2       │  │
│  │ ○ D. 最大值4，最小值0        │  │
│  │                               │  │
│  │ [提交答案]                    │  │
│  └──────────────────────────────┘  │
│                                      │
│  ┌─ 批改结果 ───────────────────┐  │
│  │ ✅ 回答正确！                  │  │
│  │ 解析：求导得 f'(x)=3x²-6x   │  │
│  │ ...                           │  │
│  │ [下一题] [查看错题本]         │  │
│  └──────────────────────────────┘  │
│                                      │
│  ┌─ 统计面板 ───────────────────┐  │
│  │ 正确率 80%  用时 12min       │  │
│  │ 连续答对 3 题 🔥             │  │
│  └──────────────────────────────┘  │
└─────────────────────────────────────┘
```

### 7.2 组件清单

| 组件 | 功能 |
|------|------|
| `PracticePage` | 练习主页面 |
| `QuestionCard` | 题目展示(含KaTeX) |
| `OptionSelector` | 选项选择 |
| `SubmissionResult` | 批改结果展示 |
| `ProgressBar` | 练习进度 |
| `StatsPanel` | 统计面板 |
| `ErrorBook` | 错题本 |

---

## 八、实施计划

### Step 1: 后端数据模型 + 题库API
- PracticeQuestion模型更新(多模态)
- 题库CRUD API
- 练习会话管理

### Step 2: LLM题目生成
- 生成提示词
- JSON解析+验证
- 存储到题库

### Step 3: 即时批改 + BKT更新
- 答案判断
- 错因分析(LLM)
- BKT状态更新

### Step 4: 前端练习界面
- 题目展示(KaTeX)
- 选项交互
- 批改结果
- 统计面板

### Step 5: 智能推荐 + 错题本
- 基于BKT的推荐
- 错题收集
- 定期复习提醒
