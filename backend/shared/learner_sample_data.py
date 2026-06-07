"""学习者数字孪生引擎 — 示例数据"""
from __future__ import annotations

from app.schemas.learner import ContentItem, PracticeQuestion


def get_sample_questions() -> dict[str, list[PracticeQuestion]]:
    """返回按科目分组的示例练习题"""
    sample_questions = [
        PracticeQuestion(
            question_id="math_001", subject="数学", skill_id="algebra_linear",
            difficulty="easy", question_text="求解方程：2x + 5 = 13",
            options=["x=3", "x=4", "x=5", "x=6"], correct_answer="x=4",
            explanation="2x + 5 = 13 → 2x = 8 → x = 4",
            hints=["先将5移到等号右边", "然后两边同时除以2"],
        ),
        PracticeQuestion(
            question_id="math_002", subject="数学", skill_id="algebra_linear",
            difficulty="medium", question_text="求解方程组：x + y = 10, x - y = 4",
            options=["x=7, y=3", "x=6, y=4", "x=8, y=2", "x=5, y=5"],
            correct_answer="x=7, y=3",
            explanation="将两式相加得 2x = 14, 所以 x = 7, y = 3",
            hints=["可以把两个方程相加", "消去y变量"],
        ),
        PracticeQuestion(
            question_id="math_003", subject="数学", skill_id="geometry_area",
            difficulty="easy", question_text="一个长方形的长为8cm，宽为5cm，求面积",
            options=["40 cm²", "26 cm²", "13 cm²", "45 cm²"], correct_answer="40 cm²",
            explanation="面积 = 长 × 宽 = 8 × 5 = 40 cm²",
            hints=["长方形面积公式是 长×宽"],
        ),
        PracticeQuestion(
            question_id="chinese_001", subject="语文", skill_id="reading_comprehension",
            difficulty="medium",
            question_text="下列哪个成语的使用是正确的？",
            options=["他的演讲真是画龙点睛", "这件事真是雪中送炭", "他的建议画蛇添足", "今天的天气秋高气爽"],
            correct_answer="他的建议画蛇添足",
            explanation="画蛇添足比喻做多余的事，反而弄巧成拙，适合形容多余的建议",
            hints=["画龙点睛指在关键处加精辟之笔", "雪中送炭指在困难时给予帮助", "秋高气爽形容秋天天气"],
        ),
        PracticeQuestion(
            question_id="english_001", subject="英语", skill_id="grammar_tense",
            difficulty="easy", question_text="She ___ (go) to school every day.",
            options=["go", "goes", "going", "went"], correct_answer="goes",
            explanation="第三人称单数（she）用 goes",
            hints=["注意主语是第三人称单数", "一般现在时的第三人称单数要加s"],
        ),
    ]

    bank: dict[str, list[PracticeQuestion]] = {}
    for q in sample_questions:
        bank.setdefault(q.subject, []).append(q)
    return bank


def get_sample_content() -> dict[str, list[ContentItem]]:
    """返回按科目分组的内容库"""
    items = [
        ContentItem(content_id="content_001", title="线性方程组入门教程", subject="数学",
                    content_type="article", description="从零开始学习如何解线性方程组",
                    difficulty=0.4, tags=["代数", "方程组", "入门"]),
        ContentItem(content_id="content_002", title="面积计算公式大全", subject="数学",
                    content_type="video", description="各种图形面积计算方法的视频讲解",
                    url="https://example.com/area-video", difficulty=0.3,
                    tags=["几何", "面积", "公式"]),
        ContentItem(content_id="content_003", title="成语辨析专项练习", subject="语文",
                    content_type="exercise", description="常见易混淆成语的辨析练习",
                    difficulty=0.5, tags=["成语", "辨析", "练习"]),
        ContentItem(content_id="content_004", title="英语时态总结", subject="英语",
                    content_type="article", description="英语12种时态的完整总结与例句",
                    difficulty=0.5, tags=["语法", "时态", "总结"]),
    ]

    store: dict[str, list[ContentItem]] = {}
    for c in items:
        store.setdefault(c.subject, []).append(c)
    return store
