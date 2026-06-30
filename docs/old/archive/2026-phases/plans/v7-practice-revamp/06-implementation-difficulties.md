# 实现难点分析

> 基于纯前端题库系统的功能清单，分析在伴学系统后端实现时的真实难点与方案。

---

## 难点 1：文档导入解析（docx/xlsx）

### 难度：⭐⭐⭐⭐⭐

**为什么难：**
- docx 本质是 ZIP 包里的 XML，没有标准"题目"标签
- xlsx 行列格式千奇百怪（题号可能在 A 列也可能在 C 列）
- 用户上传的格式不可能完全规范

**方案：分层解析 + 预览确认**

```python
# backend/app/services/import_parser.py

"""
解析分为三层：

Layer 1: 格式适配层
    docx → python-docx 提取段落
    xlsx → openpyxl 提取行列
    txt  → 按空行分段
    json → 直接映射

Layer 2: 结构推断层
    对提取的段落/行进行模式识别：
    - "1." / "（1）" / "①" → 题号
    - "A." / "B." / "C." / "D." → 选项
    - "答案：" / "【答案】" → 答案标记
    - "解析：" / "【解析】" → 解析标记

Layer 3: AI 纠错层
    对于推断置信度 < 0.8 的字段，
    调用 LLM 修正：
    "这段内容看起来像是题干还是选项？"
"""

import re
from typing import Optional

class ImportParser:
    """
    通用导入解析器。
    不依赖格式，核心是"模式识别 + AI 兜底"。
    """

    # 常见题号模式
    QUESTION_NUM_PATTERNS = [
        re.compile(r'^(\d+)[.、）\)]\s*(.*)'),       # 1. 1、1）1)
        re.compile(r'^（(\d+)）\s*(.*)'),              # （1）
        re.compile(r'^[①②③④⑤⑥⑦⑧⑨⑩]\s*(.*)'),    # ① ② ③
    ]

    # 选项模式
    OPTION_PATTERNS = [
        re.compile(r'^([A-Da-d])[.、）\)]\s*(.*)'),   # A. A、A）A)
        re.compile(r'^（([A-Da-d])）\s*(.*)'),          # （A）
    ]

    # 答案/解析标记
    ANSWER_MARKERS = ['答案', '正确答案', '【答案】', '参考答案']
    ANALYSIS_MARKERS = ['解析', '【解析】', '答案解析']

    def parse(self, file_path: str, file_type: str) -> list[dict]:
        """
        主入口：解析文件 → 题目列表。
        返回 [{ stem, options, answer, analysis, type, line_number }]
        """
        if file_type == 'docx':
            raw_blocks = self._parse_docx(file_path)
        elif file_type == 'xlsx':
            raw_blocks = self._parse_xlsx(file_path)
        elif file_type == 'json':
            return self._parse_json(file_path)
        else:
            raise ValueError(f"不支持的格式: {file_type}")

        return self._structure_blocks(raw_blocks)

    def _parse_docx(self, path: str) -> list[dict]:
        """docx → 段落列表"""
        from docx import Document
        doc = Document(path)
        blocks = []
        for para in doc.paragraphs:
            text = para.text.strip()
            if not text:
                continue
            blocks.append({
                "text": text,
                "style": para.style.name if para.style else "",
                "type": self._infer_block_type(text),
            })
        return blocks

    def _parse_xlsx(self, path: str) -> list[dict]:
        """xlsx → 行列表"""
        from openpyxl import load_workbook
        wb = load_workbook(path, read_only=True)
        ws = wb.active
        blocks = []
        for row in ws.iter_rows(values_only=True):
            text = "  ".join(str(c) for c in row if c is not None).strip()
            if not text:
                continue
            blocks.append({
                "text": text,
                "row_index": row[0] if row else 0,  # Excel 行号
                "type": self._infer_block_type(text),
            })
        return blocks

    def _infer_block_type(self, text: str) -> str:
        """推断段落类型：question | option | answer | analysis | unknown"""
        # 检查是否是答案行
        if any(marker in text for marker in self.ANSWER_MARKERS):
            return "answer"
        if any(marker in text for marker in self.ANALYSIS_MARKERS):
            return "analysis"
        # 检查是否是题号开头
        for pat in self.QUESTION_NUM_PATTERNS:
            if pat.match(text):
                return "question"
        # 检查是否是选项
        for pat in self.OPTION_PATTERNS:
            if pat.match(text):
                return "option"
        return "unknown"

    def _structure_blocks(self, blocks: list[dict]) -> list[dict]:
        """
        将段落列表结构化为一组题目。
        这是最复杂的部分——需要处理各种边界情况。
        """
        questions = []
        current = None

        for block in blocks:
            btype = block["type"]

            if btype == "question":
                # 新题开始
                if current:
                    questions.append(self._finalize_question(current))
                current = {
                    "stem": self._clean_stem(block["text"]),
                    "options": [],
                    "answer": "",
                    "analysis": "",
                    "source_line": block.get("row_index", 0),
                    "confidence": 0.7,
                }

            elif btype == "option" and current:
                opt = self._parse_option(block["text"])
                if opt:
                    current["options"].append(opt)

            elif btype == "answer" and current:
                current["answer"] = self._extract_answer_text(block["text"])

            elif btype == "analysis" and current:
                current["analysis"] = self._extract_analysis_text(block["text"])

            elif btype == "unknown" and current:
                # 无法识别的行——可能是题干续行或选项续行
                if not current["options"]:
                    # 还没出现选项，当作题干续行
                    current["stem"] += "\n" + block["text"]
                else:
                    # 已经出现选项，可能是杂项，跳过

                    pass

        if current:
            questions.append(self._finalize_question(current))

        # AI 兜底：对置信度低的题目进行修正
        for q in questions:
            if q["confidence"] < 0.8:
                q = self._ai_correct(q)

        return questions

    def _clean_stem(self, text: str) -> str:
        """去除题号前缀"""
        for pat in self.QUESTION_NUM_PATTERNS:
            m = pat.match(text)
            if m:
                return m.group(2).strip() if m.lastindex >= 2 else text
        return text

    def _parse_option(self, text: str) -> Optional[dict]:
        """解析选项行"""
        for pat in self.OPTION_PATTERNS:
            m = pat.match(text)
            if m:
                return {
                    "label": m.group(1).upper(),
                    "content": m.group(2).strip(),
                }
        return None

    def _extract_answer_text(self, text: str) -> str:
        """从答案行提取纯答案"""
        for marker in self.ANSWER_MARKERS:
            text = text.replace(marker, "")
        return text.strip()

    def _extract_analysis_text(self, text: str) -> str:
        for marker in self.ANALYSIS_MARKERS:
            text = text.replace(marker, "")
        return text.strip()

    def _finalize_question(self, q: dict) -> dict:
        """完成题目构建：推断题型、计算置信度"""
        # 推断题型
        opt_count = len(q.get("options") or [])
        if opt_count >= 2:
            correct = sum(1 for o in q["options"] if "正确" in o.get("content", ""))
            q["question_type"] = "single" if correct <= 1 else "multiple"
        elif not q["options"]:
            q["question_type"] = "fill"
        else:
            q["question_type"] = "single"

        # 置信度计算
        score = 0.7
        if q["answer"]:
            score += 0.15
        if q["analysis"]:
            score += 0.1
        if q["question_type"] in ("single", "multiple") and len(q["options"]) < 2:
            score -= 0.3  # 选择题选项不足
        q["confidence"] = min(1.0, max(0.1, score))

        return q

    def _ai_correct(self, q: dict) -> dict:
        """AI 修正低置信度的解析结果"""
        from app.services.llm_service import llm_service

        prompt = f"""以下是一道从文档中提取的题目，请修正可能的解析错误：

当前解析结果：
- 题干：{q['stem'][:200]}
- 选项：{q.get('options', [])}
- 答案：{q['answer']}
- 解析：{q['analysis'][:200]}

请检查：
1. 题型判断是否正确？
2. 题干是否完整？
3. 选项是否与题干匹配？
4. 答案是否正确提取？

以 JSON 格式返回修正后的完整题目。
"""
        try:
            result = llm_service.chat(
                system_prompt="你是一个文档解析专家，擅长从非结构化文档中提取练习题。",
                user_prompt=prompt,
            )
            # 解析 result 合并到 q
            # ...
            q["confidence"] = 0.95
        except Exception:
            pass  # AI 失败就用原始解析
        return q
```

### 导入预览交互流程

```
用户上传文件 → 解析 → 返回 preview
                          │
               ┌──────────┼──────────┐
               ▼          ▼          ▼
        正确题目    需修正题目    无法解析的段落
        (绿色)      (黄色)       (红色标记)
               │          │
               ▼          ▼
        确认导入   用户手动修正 / AI 重新解析
                          │
                          ▼
                    确认导入
```

---

## 难点 2：选择题型渲染引擎

### 难度：⭐⭐⭐⭐

**为什么难：**
- 多种题型渲染逻辑不同（单选/多选/判断/填空）
- 题干支持 LaTeX 数学公式
- 需要自适应布局
- 选项要支持图文混排

### 方案：组件化渲染

```typescript
// frontend/src/components/practice/QuestionRenderer.tsx

/**
 * 题目渲染器 — 按题型分发到不同渲染组件。
 * 核心原则：每个题型一个独立组件，共享题干渲染。
 */

interface QuestionData {
  id: string;
  question_type: 'single' | 'multiple' | 'judge' | 'fill' | 'essay';
  stem: string;          // 题干（支持 Markdown + LaTeX）
  options?: {             // 选择题
    label: string;
    content: string;
  }[];
  // 其他元数据
}

function QuestionRenderer({ question, onAnswer, disabled }: Props) {
  return (
    <div className="space-y-4">
      {/* 题干渲染（所有题型共用） */}
      <StemRenderer stem={question.stem} />

      {/* 答题区域（题型分发） */}
      {question.question_type === 'single' && (
        <SingleChoice options={question.options!} onSelect={onAnswer} disabled={disabled} />
      )}
      {question.question_type === 'multiple' && (
        <MultipleChoice options={question.options!} onSelect={onAnswer} disabled={disabled} />
      )}
      {question.question_type === 'judge' && (
        <JudgeChoice onSelect={onAnswer} disabled={disabled} />
      )}
      {question.question_type === 'fill' && (
        <FillInput onSubmit={onAnswer} disabled={disabled} />
      )}
      {question.question_type === 'essay' && (
        <EssayInput onSubmit={onAnswer} disabled={disabled} />
      )}
    </div>
  );
}
```

---

## 难点 3：考试计时器同步

### 难度：⭐⭐⭐⭐

**为什么难：**
- 前端倒计时与服务器时间不一致
- 用户可能开多个 tab
- 到时间必须强制交卷（不能依赖前端）

### 方案：双轨计时 + 服务端强校验

```python
# backend/app/services/exam_timer.py

"""
考试计时策略：

1. 前端：WebSocket 实时推送剩余时间（倒计时体验）
2. 后端：每次 submit 时校验 deadline
3. 到时间：服务端自动 COMPLETED，拒绝后续 submit
"""

from datetime import datetime, timedelta


def validate_exam_time(session_id: str, db) -> dict:
    """
    校验考试是否仍在有效时间内。
    返回: { "valid": bool, "remaining_seconds": int, "auto_submitted": bool }
    """
    session = db.fetchone(
        "SELECT * FROM practice_sessions WHERE id = %s AND session_type = 'exam'",
        (session_id,),
    )
    if not session:
        return {"valid": False, "remaining_seconds": 0, "auto_submitted": False}

    config = session.get("config") or {}
    if isinstance(config, str):
        import json
        config = json.loads(config)

    deadline_str = config.get("deadline")
    if not deadline_str:
        return {"valid": True, "remaining_seconds": 99999, "auto_submitted": False}

    deadline = datetime.fromisoformat(deadline_str)
    now = datetime.now()

    remaining = (deadline - now).total_seconds()

    if remaining <= 0:
        # 时间到 → 自动交卷
        if session["status"] == "active":
            _auto_submit_exam(session_id, db)
        return {"valid": False, "remaining_seconds": 0, "auto_submitted": True}

    return {"valid": True, "remaining_seconds": int(remaining), "auto_submitted": False}


def _auto_submit_exam(session_id: str, db) -> None:
    """
    自动交卷：将所有未答标记为错误，完成会话。
    """
    now = datetime.now().isoformat()
    db.execute(
        """UPDATE practice_sessions
           SET status = 'timeout', finished_at = %s
           WHERE id = %s AND status = 'active'""",
        (now, session_id),
    )
    # 未答的题自动记错
    unanswered = db.fetchall(
        """SELECT sq.id, sq.question_id
           FROM session_questions sq
           WHERE sq.session_id = %s AND sq.is_correct IS NULL""",
        (session_id,),
    )
    for uq in unanswered:
        db.execute(
            """UPDATE session_questions
               SET is_correct = false, time_spent_seconds = 0
               WHERE id = %s""",
            (uq["id"],),
        )
```

### 防作弊检测

```typescript
// frontend/src/hooks/useExamGuard.ts

/**
 * 考试模式下的防作弊检测。
 * 不搞复杂的摄像头/屏幕监控，只做基本的 tab 切换检测。
 */

function useExamGuard(sessionId: string) {
  const [violations, setViolations] = useState(0);
  const MAX_VIOLATIONS = 3;

  useEffect(() => {
    const handleVisibility = () => {
      if (document.hidden) {
        setViolations(v => {
          const next = v + 1;
          if (next >= MAX_VIOLATIONS) {
            // 自动交卷
            api.examAutoSubmit(sessionId, reason: 'tab_switch');
          }
          return next;
        });
      }
    };

    const handleBlur = () => {
      // 窗口失去焦点也算一次（但不累加太快）
    };

    document.addEventListener('visibilitychange', handleVisibility);
    window.addEventListener('blur', handleBlur);

    return () => {
      document.removeEventListener('visibilitychange', handleVisibility);
      window.removeEventListener('blur', handleBlur);
    };
  }, [sessionId]);

  return { violations, isDisqualified: violations >= MAX_VIOLATIONS };
}
```

---

## 难点 4：自适应出题算法稳定性

### 难度：⭐⭐⭐⭐

**为什么难：**
- 初期用户练习数据少 → master 分布不可靠
- 薄弱节点太多时 → 题目集中在少数节点
- 题库覆盖不全 → 某些节点无题可出

### 方案：冷启动 + 兜底 + 去重

```python
# 在 adaptive_select 中增加的保护逻辑

def _get_safe_distribution(nodes: list, count: int) -> dict:
    """
    安全的分组比例计算。
    考虑冷启动和数据稀疏的情况。
    """
    weak = [n for n in nodes if n.belief.proficiency_mean < 0.4]
    medium = [n for n in nodes if 0.4 <= n.belief.proficiency_mean < 0.7]
    strong = [n for n in nodes if n.belief.proficiency_mean >= 0.7]

    total = len(nodes)

    # 冷启动：数据太少时全部随机
    if total < 5:
        return {"weak": count, "medium": 0, "strong": 0}

    # 薄弱节点太少 → 降低薄弱比例
    weak_ratio = min(0.6, max(0.2, len(weak) / max(total, 1)))

    # 按比例计算，确保每个分组至少有 1 道题（如果有节点的话）
    weak_target = max(0 if len(weak) == 0 else 1, int(count * weak_ratio))
    medium_target = max(0 if len(medium) == 0 else 1, int(count * 0.3))
    strong_target = count - weak_target - medium_target

    # 不能有负数
    if strong_target < 0:
        strong_target = 0
        medium_target = max(0, count - weak_target)

    return {"weak": weak_target, "medium": medium_target, "strong": strong_target}
```

---

## 难点 5：认知节点匹配（题目↔知识点）

### 难度：⭐⭐⭐

**为什么难：**
- 导入时自动匹配 → 需要语义理解
- 知识点层级关系复杂 → 匹配完需要上提下推
- 用户可能手动修改匹配 → 需要记录 override

### 方案：embedding 匹配 + 层级推断 + 用户确认

```python
# 在 match_question_to_nodes 中增加层级推断

def _infer_proper_level(matches: list[dict]) -> list[str]:
    """
    从 embedding 匹配结果中推断最合适的关联层级。
    
    匹配结果可能返回多个层级的节点（atom、concept、topic）。
    规则：
    - 优先匹配 atom（最精确）
    - 如果所有匹配的 atom 都属于同一个 topic → 关联 topic
    - 如果匹配的 topic 只有一个 → 关联 topic
    - 如果匹配分散 → 关联得分最高的 2 个 atom
    """
    from collections import Counter
    
    if not matches:
        return []
    
    # 按层级分组
    atoms = [m for m in matches if m.get("level") == "atom"]
    topics = [m for m in matches if m.get("level") == "topic"]
    
    # 只有 atom 匹配
    if atoms and not topics:
        # 查这些 atom 的共同父级
        parent_ids = Counter()
        for a in atoms:
            node = get_node(a["id"], DEFAULT_USER_ID)
            if node and node.parent:
                parent_ids[node.parent] += 1
        # 如果 80% 以上的 atom 同属一个父节点，关联父节点
        if parent_ids:
            top_parent, count = parent_ids.most_common(1)[0]
            if count / len(atoms) >= 0.8:
                return [top_parent]
        return [a["id"] for a in atoms[:2]]
    
    # 有 topic 匹配
    if topics:
        return [topics[0]["id"]]
    
    # 兜底
    return [matches[0]["id"]]
```

---

## 难点总结

| 难点 | 核心挑战 | 方案核心 |
|------|---------|---------|
| 文档解析 | 格式不统一，模式多变 | 分层解析（格式适配→结构推断→AI 纠错）+ 预览确认 |
| 题型渲染 | 多题型 + LaTeX + 自适应 | 组件化分发，共用题干渲染 |
| 考试计时 | 前后端时间不同步 | 前端倒计时体验 + 后端 deadline 强校验 |
| 自适应算法 | 冷启动 + 稀疏数据 | 安全比例 + AI 补题 + 去重 |
| 认知匹配 | 语义理解 + 层级推断 | embedding + 共同父级推断 + 用户可覆盖 |

这些难点中，**文档解析**和**考试计时器同步**是最容易出 bug 的——前者格式变体太多，后者涉及并发边界条件。
