"""
多维情绪分析服务

比关键词匹配更细粒度：用 LLM 分类情绪+强度，
缓存最近N条情绪，追踪趋势，生成洞察。
"""

from __future__ import annotations

import json
import logging
import re
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional

from app.infrastructure.llm.llm_service import llm_service

logger = logging.getLogger(__name__)

# ── 情绪分类体系 ──

EMOTION_CATEGORIES = {
    "frustration": {"label": "挫败", "emoji": "😤", "severity": "negative"},
    "anxiety": {"label": "焦虑", "emoji": "😰", "severity": "negative"},
    "confusion": {"label": "困惑", "emoji": "🤔", "severity": "neutral"},
    "boredom": {"label": "无聊", "emoji": "😴", "severity": "negative"},
    "overwhelm": {"label": "压力大", "emoji": "😵", "severity": "negative"},
    "procrastination": {"label": "拖延", "emoji": "🥱", "severity": "negative"},
    "motivated": {"label": "有动力", "emoji": "💪", "severity": "positive"},
    "achievement": {"label": "成就感", "emoji": "🎉", "severity": "positive"},
    "curious": {"label": "好奇", "emoji": "🔍", "severity": "positive"},
    "calm": {"label": "平静", "emoji": "😌", "severity": "positive"},
    "neutral": {"label": "中性", "emoji": "📝", "severity": "neutral"},
}

# ── 快速关键词检测（零 token 成本，先行过滤） ──

EMOTION_KEYWORDS: dict[str, list[str]] = {
    "frustration": ["好难", "太难了", "不会", "不懂", "搞不定", "放弃了", "崩溃",
                    "学不会", "做不对", "又错了", "我好菜", "废物", "完了", "挂了"],
    "anxiety": ["焦虑", "紧张", "害怕", "担心", "考不过", "来不及", "压力",
                "怎么办", "救救我", "好慌", "睡不着"],
    "confusion": ["不理解", "搞不懂", "什么意思", "为什么", "怎么回事",
                  "蒙了", "晕了", "懵", "没懂"],
    "boredom": ["无聊", "没意思", "不想学", "好困", "犯困", "没动力",
                "提不起劲", "乏味"],
    "overwhelm": ["太多了", "做不完", "赶不上", "忙不过来", "堆成山",
                  "喘不过气", "要死了", "疯了我"],
    "procrastination": ["拖延", "不想做", "明天再说", "以后再", "先不管",
                        "晚点", "懒得", "犯懒"],
    "motivated": ["加油", "冲", "今天要", "开始学", "努力", "坚持",
                  "一定可以", "搞起来", "卷"],
    "achievement": ["懂了", "明白了", "做对了", "通过了", "理解了",
                    "原来如此", "搞定", "完成了", "nice", "耶", "🎉", "💪"],
    "curious": ["为什么", "如何", "怎么实现", "原理是", "想了解",
                "深入", "然后呢", "再讲讲", "是什么", "什么是", "怎么推导"],
    "calm": ["好的", "嗯", "知道了", "了解", "谢谢", "ok", "行"],
}


@dataclass
class EmotionRecord:
    """单条情绪记录"""
    timestamp: datetime
    category: str
    intensity: float  # 0.0 ~ 1.0
    source_text: str  # 用户原话片段（截断）
    summary: str       # LLM 一句话总结

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp.isoformat(),
            "category": self.category,
            "intensity": self.intensity,
            "source_text": self.source_text[:100],
            "summary": self.summary,
        }


@dataclass
class EmotionTrend:
    """情绪趋势分析结果"""
    dominant_emotion: str
    dominant_count: int
    negative_ratio: float
    positive_ratio: float
    trend_direction: str  # "improving", "declining", "stable", "volatile"
    insight: str
    recent_records: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "dominant_emotion": self.dominant_emotion,
            "dominant_count": self.dominant_count,
            "negative_ratio": round(self.negative_ratio, 2),
            "positive_ratio": round(self.positive_ratio, 2),
            "trend_direction": self.trend_direction,
            "insight": self.insight,
            "recent_records": self.recent_records,
        }


# ── LLM 情绪分类 Prompt ──

EMOTION_CLASSIFY_PROMPT = """你是学习心理分析师。分析学生的学习状态，输出情绪标签和强度。

## 情绪标签（11类）
{emotion_list}

## 强度说明
- 0.1-0.3: 轻微（随手一提）
- 0.4-0.6: 中等（明显表露）
- 0.7-1.0: 强烈（核心关注点）

## 学生消息
{message}

## 输出 JSON 格式
{{
  "category": "frustration|anxiety|confusion|...",
  "intensity": 0.0-1.0,
  "summary": "一句话描述学生当前状态，10字以内"
}}"""

# ── 情绪趋势分析 Prompt ──

TREND_ANALYSIS_PROMPT = """你是学习心理分析师。根据学生最近的情绪记录，做趋势分析。

## 最近情绪记录
{records}

## 分析维度
1. **主导情绪**：出现最多的情绪类型
2. **方向**：improving(变好) / declining(变差) / stable(稳定) / volatile(波动)
3. **一句话洞察**：给学生本人的温暖反馈（第二人称，"你最近..."）

## 输出 JSON
{{
  "dominant_emotion": "emotion_category",
  "trend_direction": "improving|declining|stable|volatile",
  "insight": "一句话洞察，15字以内"
}}"""


class EmotionAnalyzer:
    """多维情绪分析引擎"""

    def __init__(self):
        # 内存缓存：user_id → list[EmotionRecord]（最近50条）
        self._cache: dict[str, list[EmotionRecord]] = defaultdict(list)
        self._max_cache = 50

    # ── 快速关键词检测 ──

    def quick_detect(self, text: str) -> Optional[str]:
        """零 token 成本：检测是否有明确情绪信号"""
        scores: dict[str, int] = {}
        for category, keywords in EMOTION_KEYWORDS.items():
            count = sum(1 for kw in keywords if kw in text)
            if count > 0:
                scores[category] = count

        if not scores:
            return None

        # 返回匹配最多的类别
        return max(scores, key=scores.get)

    # ── LLM 精确分类 ──

    async def classify(self, text: str, user_id: str) -> EmotionRecord:
        """用 LLM 精确分类情绪（仅在 quick_detect 有结果时调用）"""
        try:
            emotion_list = "\n".join(
                f"- {cat}: {info['label']} {info['emoji']}"
                for cat, info in EMOTION_CATEGORIES.items()
            )
            prompt = EMOTION_CLASSIFY_PROMPT.format(
                emotion_list=emotion_list,
                message=text[:500],
            )
            response = llm_service.chat(
                system_prompt="你是学习心理分析师。只输出JSON。",
                user_prompt=prompt,
            )

            # 解析 JSON
            json_match = re.search(r'\{[\s\S]*\}', response)
            if json_match:
                data = json.loads(json_match.group(0))
                record = EmotionRecord(
                    timestamp=datetime.now(),
                    category=data.get("category", "neutral"),
                    intensity=min(max(float(data.get("intensity", 0.3)), 0.0), 1.0),
                    source_text=text[:150],
                    summary=data.get("summary", ""),
                )
                self._cache[user_id].append(record)
                # 保持缓存大小
                if len(self._cache[user_id]) > self._max_cache:
                    self._cache[user_id] = self._cache[user_id][-self._max_cache:]
                return record

        except Exception as e:
            logger.warning(f"LLM 情绪分类失败: {e}")

        # Fallback: 用 quick_detect 结果
        category = self.quick_detect(text) or "neutral"
        record = EmotionRecord(
            timestamp=datetime.now(),
            category=category,
            intensity=0.3,
            source_text=text[:150],
            summary=f"关键词匹配: {category}",
        )
        self._cache[user_id].append(record)
        return record

    # ── 情绪趋势分析 ──

    async def analyze_trend(self, user_id: str, window_hours: int = 72) -> EmotionTrend:
        """分析最近 N 小时的情绪趋势"""
        records = self._cache.get(user_id, [])

        if not records:
            return EmotionTrend(
                dominant_emotion="neutral",
                dominant_count=0,
                negative_ratio=0.0,
                positive_ratio=0.0,
                trend_direction="stable",
                insight="还没有足够的情绪数据，继续聊天吧~",
            )

        # 时间窗口过滤
        cutoff = datetime.now() - timedelta(hours=window_hours)
        recent = [r for r in records if r.timestamp > cutoff]
        if not recent:
            recent = records[-10:]  # 兜底取最近10条

        # 统计
        category_counts: dict[str, int] = defaultdict(int)
        neg_count = 0
        pos_count = 0
        total = len(recent)

        for r in recent:
            category_counts[r.category] += 1
            severity = EMOTION_CATEGORIES.get(r.category, {}).get("severity", "neutral")
            if severity == "negative":
                neg_count += 1
            elif severity == "positive":
                pos_count += 1

        dominant = max(category_counts, key=category_counts.get)

        # 判断方向：比较前半段和后半段的情绪
        mid = total // 2
        first_half_neg = sum(
            1 for r in recent[:mid]
            if EMOTION_CATEGORIES.get(r.category, {}).get("severity") == "negative"
        )
        second_half_neg = sum(
            1 for r in recent[mid:]
            if EMOTION_CATEGORIES.get(r.category, {}).get("severity") == "negative"
        )

        if total < 3:
            direction = "stable"
        elif second_half_neg < first_half_neg:
            direction = "improving"
        elif second_half_neg > first_half_neg:
            direction = "declining"
        elif abs(pos_count - neg_count) <= 1:
            direction = "volatile"
        else:
            direction = "stable"

        # 生成洞察
        insight = await self._generate_insight(recent, dominant, direction)

        return EmotionTrend(
            dominant_emotion=dominant,
            dominant_count=category_counts[dominant],
            negative_ratio=neg_count / total if total > 0 else 0,
            positive_ratio=pos_count / total if total > 0 else 0,
            trend_direction=direction,
            insight=insight,
            recent_records=[r.to_dict() for r in recent[-5:]],
        )

    async def _generate_insight(
        self,
        records: list[EmotionRecord],
        dominant: str,
        direction: str,
    ) -> str:
        """用 LLM 生成人性化洞察"""
        try:
            records_text = "\n".join(
                f"- [{r.timestamp.strftime('%m/%d %H:%M')}] {r.category}({r.intensity:.1f}): {r.summary}"
                for r in records[-10:]
            )
            prompt = TREND_ANALYSIS_PROMPT.format(records=records_text)

            response = llm_service.chat(
                system_prompt="你是学习心理分析师。只输出JSON。",
                user_prompt=prompt,
            )

            json_match = re.search(r'\{[\s\S]*\}', response)
            if json_match:
                data = json.loads(json_match.group(0))
                return data.get("insight", self._fallback_insight(dominant, direction))
        except Exception as e:
            logger.warning(f"LLM 洞察生成失败: {e}")

        return self._fallback_insight(dominant, direction)

    def _fallback_insight(self, dominant: str, direction: str) -> str:
        """LLM 不可用时的兜底洞察"""
        insights = {
            ("frustration", "declining"): "你最近遇到了不少困难，这很正常，慢慢来 🌱",
            ("frustration", "improving"): "你在攻克难关，状态在变好 💪",
            ("anxiety", "declining"): "压力有点大，记得给自己喘息的时间 🫂",
            ("motivated", "improving"): "你正在进入状态，势头很好 🔥",
            ("achievement", "stable"): "你最近进步稳定，很棒 ✨",
            ("confusion", "stable"): "保持好奇心，困惑是理解的前奏 🔍",
            ("procrastination", "declining"): "拖延很正常，从小目标开始就好 📌",
        }
        key = (dominant, direction)
        return insights.get(key, f"你的学习状态{direction}，继续加油 💫")

    # ── 对话上下文注入 ──

    def build_emotion_context(self, user_id: str) -> str:
        """构建注入到 system prompt 的情绪上下文"""
        records = self._cache.get(user_id, [])
        if not records:
            return ""

        recent = records[-3:]
        lines = []
        for r in recent:
            emoji = EMOTION_CATEGORIES.get(r.category, {}).get("emoji", "")
            label = EMOTION_CATEGORIES.get(r.category, {}).get("label", r.category)
            lines.append(f"  最近: {emoji} {label} (强度 {r.intensity:.1f})")

        return (
            "\n\n## 学生当前情绪状态\n"
            + "\n".join(lines)
            + "\n请根据情绪调整回复语气和策略。"
        )


# ── 全局实例 ──

emotion_analyzer = EmotionAnalyzer()
