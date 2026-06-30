# Phase 7.0 智能题库系统设计方案

核心理念：题库不是孤立的数据集，而是认知诊断的传感器。每一次答题都在更新学生的认知模型，每一道错题都在触发秘书的精准干预，每一组练习都在丰富图谱的知识结构。

---

## 1. 设计目标与定位

### 1.1 与开源题库系统的关系

提供的开源题库系统（刷题与考试、错题本、多格式导入、AI核对等）是一个功能完备的独立刷题工具。7.0 的设计目标不是复制它，而是吸收其最佳实践，并深度整合到伴学系统的认知架构中。

### 1.2 核心差异化

| 维度 | 独立题库系统 | 7.0 智能题库 |
|------|-------------|-------------|
| 题目关联 | 题目归入题库分类 | 每道题精确锚定到 CognitiveNode（atom 级） |
| 练习记录 | 独立存储，统计分析 | 写入认知事件，更新 mastery/activation |
| 错题处理 | 错题本独立管理 | 触发秘书诊断，生成针对性复习提案 |
| 组题策略 | 随机/顺序 | 基于 BKT 掌握度的自适应出题 |
| 题目解析 | AI 生成或人工编写 | 与知识图谱关联，可回溯到对话中的讲解 |
| 学习数据 | 仅用于统计 | 联动秘书、图谱、对话，形成认知闭环 |

---

## 2. 数据模型设计

### 2.1 新增表

#### 2.1.1 题库表 question_banks

```sql
CREATE TABLE question_banks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    import_source VARCHAR(50),           -- 'docx' | 'xlsx' | 'json' | 'manual'
    metadata JSONB DEFAULT '{}',         -- 原始文件信息、导入配置等
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now(),
    deleted_at TIMESTAMPTZ
);
```

#### 2.1.2 题目表 questions

```sql
CREATE TABLE questions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    bank_id UUID NOT NULL REFERENCES question_banks(id),
    user_id UUID NOT NULL,
    
    -- 题目内容
    question_type VARCHAR(20) NOT NULL,   -- 'single' | 'multiple' | 'judge' | 'fill' | 'essay'
    stem TEXT NOT NULL,                    -- 题干
    options JSONB DEFAULT '[]',           -- 选项列表 [{"label":"A","content":"..."}]
    answer JSONB NOT NULL,                 -- 答案（格式按题型不同）
    analysis TEXT,                         -- 解析
    difficulty INT DEFAULT 3,              -- 难度 1~5
    
    -- 认知锚定（核心）
    cognitive_node_ids UUID[] DEFAULT '{}', -- 关联的 atom/concept 节点
    
    -- 状态管理
    is_favorite BOOLEAN DEFAULT false,     -- 收藏
    is_slashed BOOLEAN DEFAULT false,      -- 已斩题（移出普通练习池）
    status VARCHAR(20) DEFAULT 'active',   -- 'active' | 'draft' | 'archived'
    
    -- 导入元数据
    source_line INT,                       -- 原始文件行号
    import_errors JSONB DEFAULT '[]',      -- 导入时的异常标记
    
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now(),
    deleted_at TIMESTAMPTZ
);

CREATE INDEX idx_q_bank ON questions(bank_id) WHERE deleted_at IS NULL;
CREATE INDEX idx_q_cognitive ON questions USING GIN(cognitive_node_ids);
CREATE INDEX idx_q_type ON questions(question_type);
```

#### 2.1.3 练习记录表 practice_sessions

```sql
CREATE TABLE practice_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    bank_id UUID REFERENCES question_banks(id),
    
    session_type VARCHAR(20) NOT NULL,     -- 'practice' | 'exam' | 'review'
    mode VARCHAR(20) NOT NULL,             -- 'random' | 'sequential' | 'adaptive'
    config JSONB NOT NULL DEFAULT '{}',    -- 组题配置、考试设置等
    
    -- 统计
    total_count INT NOT NULL,
    correct_count INT DEFAULT 0,
    wrong_count INT DEFAULT 0,
    score FLOAT,                           -- 考试模式的分数
    
    -- 认知关联
    cognitive_node_ids UUID[] DEFAULT '{}', -- 涉及的认知节点
    
    started_at TIMESTAMPTZ DEFAULT now(),
    finished_at TIMESTAMPTZ,
    duration_seconds INT,
    
    created_at TIMESTAMPTZ DEFAULT now()
);
```

#### 2.1.4 答题记录表 practice_attempts

```sql
CREATE TABLE practice_attempts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID NOT NULL REFERENCES practice_sessions(id),
    question_id UUID NOT NULL REFERENCES questions(id),
    user_id UUID NOT NULL,
    
    user_answer JSONB,                     -- 学生答案
    is_correct BOOLEAN,
    time_spent_seconds INT,                -- 本题耗时
    
    -- 错题管理
    is_wrong BOOLEAN DEFAULT false,        -- 是否加入错题本
    wrong_count INT DEFAULT 0,             -- 累计错误次数
    consecutive_correct INT DEFAULT 0,     -- 连续答对次数
    mastered BOOLEAN DEFAULT false,        -- 是否已掌握（错题复习用）
    
    -- 认知标注
    cognitive_node_ids UUID[] DEFAULT '{}', -- 本题关联的认知节点
    error_pattern VARCHAR(50),             -- 错因分类（如有）
    
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_pa_session ON practice_attempts(session_id);
CREATE INDEX idx_pa_user_question ON practice_attempts(user_id, question_id);
CREATE INDEX idx_pa_wrong ON practice_attempts(user_id, is_wrong) WHERE is_wrong = true;
```

#### 2.1.5 收藏表 question_favorites

```sql
CREATE TABLE question_favorites (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    question_id UUID NOT NULL REFERENCES questions(id),
    created_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(user_id, question_id)
);
```

#### 2.1.6 斩题记录表 slashed_questions

```sql
CREATE TABLE slashed_questions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    question_id UUID NOT NULL REFERENCES questions(id),
    slashed_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(user_id, question_id)
);
```

---

## 3. 核心功能设计

### 3.1 组题策略

#### 3.1.1 随机抽题

- 从指定题库中随机选取 N 道题，可设定题型比例。
- 偏好（题库、题型、数量）自动记忆到 practice_sessions.config。

#### 3.1.2 顺序练习

- 按题库内题目原始顺序逐题练习。
- 进度记忆：退出时保存 last_question_index，下次继续。

#### 3.1.3 自适应出题（与认知模型联动）

这是 7.0 的核心差异化能力：

```python
async def adaptive_select(bank_id, user_id, count, node_ids=None):
    """
    基于认知节点掌握度自适应选题。
    """
    # 1. 获取目标认知节点的 mastery
    if node_ids:
        nodes = await db.get_nodes(node_ids)
    else:
        nodes = await db.get_all_atom_nodes(user_id)
    
    # 2. 按 mastery 分组
    weak_nodes = [n for n in nodes if n['mastery'] < 0.4]      # 薄弱
    medium_nodes = [n for n in nodes if 0.4 <= n['mastery'] < 0.7]  # 巩固
    strong_nodes = [n for n in nodes if n['mastery'] >= 0.7]   # 保持
    
    # 3. 按比例选题（薄弱:巩固:保持 = 6:3:1）
    weak_count = int(count * 0.6)
    medium_count = int(count * 0.3)
    strong_count = count - weak_count - medium_count
    
    questions = []
    questions.extend(await select_questions_by_nodes(bank_id, weak_nodes, weak_count))
    questions.extend(await select_questions_by_nodes(bank_id, medium_nodes, medium_count))
    questions.extend(await select_questions_by_nodes(bank_id, strong_nodes, strong_count))
    
    return questions
```

秘书提案触发：当某节点 mastery 持续 < 0.3 时，秘书生成"加强练习"提案；当 mastery > 0.9 时，秘书建议"减少该知识点练习"。

### 3.2 练习模式

#### 3.2.1 即时判题模式

- 每题选择/输入后立即判断正误，显示正确答案和解析。
- 答对自动下一题（可配置）。

#### 3.2.2 批量练习模式

- 全部题目完成后统一提交判题。
- 提交后展示总结：正确率、错题数、逐题明细。

#### 3.2.3 背题模式

- 直接显示答案与解析。
- 不计入正确率统计，不生成普通练习记录。
- 单独记录为 session_type='review'。

### 3.3 考试模式

- 自定义题型、数量、分值、时长。
- 实时倒计时，到时自动交卷。
- 答题卡快速跳题，未答题提醒。
- 不受斩题和背题模式影响。

### 3.4 错题本

#### 3.4.1 自动收录

- 练习/考试中答错的题自动进入错题本，记录首次出错时间和累计错误次数。

#### 3.4.2 掌握状态管理

- 连续答对 2 次 → 自动标记为"已掌握"。
- 再次答错 → 清空连续答对次数，回到"未掌握"。
- 支持手动标记/取消掌握。

#### 3.4.3 智能复习模式（与秘书联动）

- 秘书根据错题的遗忘曲线 scheduling.urgency 安排到期复习。
- 首页同步待复习数量，点击进入错题复习。

### 3.5 斩题功能

- 一眼就会的题可"斩"出普通练习池。
- 斩题与错题掌握互相独立：斩题用于普通练习过滤，错题掌握用于错题复习状态。
- 题库详情中可集中管理和恢复。

---

## 4. 与学习数据的联动

### 4.1 练习→认知模型更新

练习提交后写入 practice.submitted 事件，认知引擎消费：

```python
async def handle_practice_submitted(user_id, payload):
    for attempt in payload['attempts']:
        node_ids = attempt['cognitive_node_ids']
        is_correct = attempt['is_correct']
        time_spent = attempt['time_spent_seconds']
        
        for node_id in node_ids:
            # 1. 更新贝塔分布参数
            belief = await get_belief(node_id)
            if is_correct:
                belief['alpha'] += 1
            else:
                belief['beta'] += 1
            mastery = belief['alpha'] / (belief['alpha'] + belief['beta'])
            
            # 2. 更新激活值（ACT-R）
            activation = await get_activation(node_id)
            activation['base_level'] = update_base_level(
                activation['base_level'], 
                time_spent, 
                is_correct
            )
            
            # 3. 更新调度紧迫度
            scheduling = await get_scheduling(node_id)
            if not is_correct:
                scheduling['urgency'] += 0.1  # 错题提升紧迫度
            else:
                scheduling['urgency'] = max(0, scheduling['urgency'] - 0.05)
            
            await save_node_subsystems(node_id, belief, activation, scheduling)
```

### 4.2 错题→秘书提案

当错题本中某知识点的错题积累到阈值（如 3 道），秘书生成：

"你最近在「导数」上错了 3 道题，主要集中在公式混淆。要不要我帮你梳理一下导数的核心公式？"

### 4.3 练习→对话联动

- 学生在练习中遇到某道错题，可直接点击"请教 AI"按钮，开启一个以该知识点为核心的对话。
- 对话中 Tutor 可引用这道错题的具体内容，进行针对性讲解。

### 4.4 练习→图谱更新

- 练习结束后，涉及的认知节点 mastery 更新，图谱中节点颜色/大小实时变化。
- 新增的薄弱节点在思维导图中高亮显示。

---

## 5. 与对话/图谱/秘书模块的联通

### 5.1 与对话系统的联通

| 场景 | 联动行为 |
|------|---------|
| 练习中遇到错题 | 点击"请教 AI" → 创建以错题知识点为中心的对话，Tutor 引用错题内容 |
| 对话中秘书推荐练习 | 秘书诊断薄弱点 → 提案："要针对「导数」做 5 道练习吗？" → 一键进入练习 |
| 练习后对话反思 | 秘书在练习结束后引导："你觉得这次练习中哪道题最难？为什么？" |

### 5.2 与知识图谱的联通

| 场景 | 联动行为 |
|------|---------|
| 图谱节点→练习 | 点击图谱中某节点 → 展开知识卡片 → "开始练习"按钮 → 按该知识点自适应出题 |
| 练习→图谱更新 | 练习后 mastery 变化 → 图谱节点颜色/大小实时更新 |
| 薄弱区域可视化 | 力导向图中，薄弱节点自动聚拢并高亮，形成"需要关注的区域" |
| 错题关联图谱 | 错题详情页显示该题关联的认知节点及其在图谱中的位置 |

### 5.3 与秘书系统的联通

| 场景 | 联动行为 |
|------|---------|
| 错题积累触发诊断 | 某知识点错题达 3 道 → 秘书自动分析错因 → 生成针对性提案 |
| 掌握度停滞触发干预 | 某知识点练习多次但 mastery 无提升 → 秘书建议："要不要换个方式学？我可以讲解、出题、或者帮你梳理知识结构" |
| 考前冲刺提案 | 秘书检测日历中有考试 → 自动生成"考前冲刺"练习计划 |
| 练习后深度反思引导 | 完成一组练习 → 秘书不直接显示分数 → 先引导反思："你觉得自己这次表现怎么样？哪道题最有把握？" |

---

## 6. 题库导入与AI辅助

### 6.1 多格式导入（复用开源系统）

- 支持 docx、xlsx、txt、json 等格式。
- 自动识别题号、题干、选项、答案、解析、题型。
- 预览与手动修正。

### 6.2 AI 核对与解析（增强）

- 导入后 AI 自动校验题型和答案正确性。
- AI 自动生成解析（可调用 LLM）。
- 关键增强：AI 解析生成后，自动尝试匹配到 cognitive_nodes（通过语义检索），并在导入预览中显示建议的认知节点关联，人工可调整。

### 6.3 题目↔认知节点关联

- 每道题导入时，通过其内容 embedding 检索最匹配的 atom 级 CognitiveNode。
- 建议关联显示在导入预览中，用户可确认或修改。
- 这一关联是所有后续联动的基础。

---

## 7. 用户偏好记忆

```sql
-- 在 user_data 中增加练习偏好
"practice_preferences": {
    "default_bank_id": "...",
    "group_mode": "random",        -- 'random' | 'sequential' | 'adaptive'
    "instant_feedback": true,      -- 即时判题
    "auto_next": true,             -- 答对自动下一题
    "font_size_stem": 16,          -- 题干字号
    "font_size_options": 14,       -- 选项字号
    "compact_options": false,      -- 紧凑选项模式
    "exam_defaults": {
        "single_count": 20,
        "multiple_count": 10,
        "judge_count": 10,
        "duration_minutes": 60
    }
}
```

---

## 8. 实施路线图

| 阶段 | 内容 | 工作量 |
|------|------|--------|
| 7.0.1 | 数据库建表、基础 CRUD API、题库导入（含 AI 解析和认知节点匹配） | 5天 |
| 7.0.2 | 练习模式核心（随机/顺序/自适应出题、即时判题、批量练习、背题模式） | 5天 |
| 7.0.3 | 考试模式（组题配置、倒计时、答题卡、成绩报告） | 3天 |
| 7.0.4 | 错题本与斩题（收录、掌握状态、智能复习、斩题管理） | 4天 |
| 7.0.5 | 认知模型联动（练习→mastery/activation更新、错题→秘书诊断、自适应出题） | 5天 |
| 7.0.6 | 图谱/对话/秘书模块联通（节点→练习、练习→图谱更新、秘书考前冲刺、反思引导） | 5天 |
| 7.0.7 | 前端适配、偏好记忆、全量测试 | 5天 |
| **总计** | | **32天** |

---

## 9. 与开源题库系统的对比总结

| 功能 | 开源系统 | 7.0 智能题库 |
|------|---------|-------------|
| 多题型支持 | ✅ | ✅ |
| 多格式导入 | ✅ | ✅ + 认知节点自动匹配 |
| AI 核对/解析 | ✅ | ✅ + 解析与知识图谱关联 |
| 练习/考试/背题模式 | ✅ | ✅ + 自适应出题 |
| 错题本/斩题 | ✅ | ✅ + 秘书智能复习 |
| 偏好记忆 | ✅ | ✅ |
| 认知节点锚定 | ❌ | ✅ **核心差异化** |
| 掌握度驱动出题 | ❌ | ✅ BKT 自适应 |
| 秘书联动诊断 | ❌ | ✅ 错题→诊断→提案 |
| 图谱联动可视化 | ❌ | ✅ 练习→图谱实时更新 |
| 对话联动讲解 | ❌ | ✅ 错题一键请教AI |
| 反思引导 | ❌ | ✅ 练习后元认知提示 |

---

> 7.0 的题库系统不是孤立的功能模块，而是整个伴学生态的认知数据采集器和秘书干预执行器。每一次答题都在让系统更懂学生，每一道错题都在触发精准的教学干预。
