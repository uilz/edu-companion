"""
InterestExplorer 兴趣标签匹配器

按 docs/modules/interest-explorer/overview.md §6 + events.md §6 实现:
- 关键词匹配（不调用 LLM/embedding）— 严格遵循决策 3
- 支持 3 层标签 (level 0/1/2)
- 主/次权重调整
- 本地权重 dislike_score 调整采样概率
- 跨学科推送（cross_disciplinary=True 时不限制范围）
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Optional

from app.services.interest import store

logger = logging.getLogger(__name__)


@dataclass
class TagMatch:
    tag_id: str
    tag_name: str
    level: int
    weight: int
    matched: bool
    dislike_score: float = 0.0
    effective_weight: float = 0.0  # 应用 dislike_score 后的实际采样权重


def match_tags_against_item(
    user_id: str,
    title: str,
    summary: str = "",
) -> list[TagMatch]:
    """对一条推送内容匹配用户兴趣标签

    算法:
      1. 加载用户所有 interest_tags + interest_weight_adjustments
      2. 关键词大小写不敏感匹配 (title + summary)
      3. 跨学科开关由调用方决定 (在 push_scheduler 中判断)
      4. effective_weight = base_weight * (1 - dislike_score)
         base_weight: weight=1 → 1.0, weight=2 → 0.5
    """
    tags = store.list_tags(user_id)
    if not tags:
        return []

    # 加载本地权重
    weight_map = {
        w["tag_id"]: w.get("dislike_score", 0.0)
        for w in store.list_weight_adjustments(user_id)
    }

    text = f"{title} {summary}".lower()
    matches: list[TagMatch] = []
    for tag in tags:
        tag_name = tag.get("name") or ""
        if not tag_name:
            continue
        # 关键词匹配（精确单词边界 + 子串）
        matched = _keyword_match(tag_name.lower(), text)
        base_weight = 1.0 if tag.get("weight", 1) == 1 else 0.5
        dislike = weight_map.get(tag["id"], 0.0)
        effective = base_weight * (1.0 - dislike)
        matches.append(TagMatch(
            tag_id=tag["id"],
            tag_name=tag_name,
            level=tag.get("level", 0),
            weight=tag.get("weight", 1),
            matched=matched,
            dislike_score=dislike,
            effective_weight=effective,
        ))
    return matches


def _keyword_match(keyword: str, text: str) -> bool:
    """关键词匹配

    - 单词边界匹配（避免 "ai" 误匹配 "main"）
    - 支持中英文（中文不做边界处理）
    - 多关键词（"机器学习"）按子串匹配
    """
    if not keyword or not text:
        return False
    # 含 ASCII 字符时使用单词边界
    if any(c.isascii() and c.isalnum() for c in keyword):
        pattern = r"\b" + re.escape(keyword) + r"\b"
        return bool(re.search(pattern, text, re.IGNORECASE))
    # 中文/日文/韩文 → 子串匹配
    return keyword in text


def compute_sampling_weights(
    user_id: str,
    cross_disciplinary: bool = False,
) -> list[tuple[str, float]]:
    """计算每个标签的采样权重

    返回 [(tag_id, weight)] 列表。
    - cross_disciplinary=False: 只包含 level=2 (叶子标签) + effective_weight > 0
    - cross_disciplinary=True: 包含所有标签（全局采样）
    """
    tags = store.list_tags(user_id)
    if not tags:
        return []
    weight_map = {
        w["tag_id"]: w.get("dislike_score", 0.0)
        for w in store.list_weight_adjustments(user_id)
    }
    results: list[tuple[str, float]] = []
    for tag in tags:
        if not cross_disciplinary and tag.get("level", 0) != 2:
            continue
        base_weight = 1.0 if tag.get("weight", 1) == 1 else 0.5
        dislike = weight_map.get(tag["id"], 0.0)
        eff = base_weight * (1.0 - dislike)
        if eff <= 0.01:
            continue
        results.append((tag["id"], eff))
    return results
