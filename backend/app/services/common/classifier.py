"""
分类服务 v2：关键词 + LLM 智能分类
降级策略：embedding (可选) > LLM 关键词提取 > 静态关键词匹配
"""

from __future__ import annotations

import logging

from app.services.common.embedding_utils import compute_embedding, cosine_similarity
from app.services.common import get_data_repo
from app.services.common.classifier_keywords import (
    KEYWORD_WEIGHTS,
    DOMAIN_KEYWORDS,
    TOPIC_KEYWORDS,
    CONVERSATION_KEYWORDS,
)

logger = logging.getLogger(__name__)


def keyword_score(text: str, subject: str) -> float:
    """计算关键词匹配得分 (0-1)。最高匹配 + 多匹配奖励"""
    keywords = KEYWORD_WEIGHTS.get(subject, {})
    if not keywords:
        return 0.0
    matches = [(w, kw) for kw, w in keywords.items() if kw in text]
    if not matches:
        return 0.0
    best = max(w for w, _ in matches)
    bonus = min(0.3, 0.1 * (len(matches) - 1))
    return min(1.0, best * 0.7 + bonus)


class Classifier:
    """消息分类器 v3: 分区→领域→专题 三级分类，关键词为主"""

    def __init__(self) -> None:
        self._embeddings_cache: dict[str, list[float]] = {}

    def classify_partition(self, user_id: str, text: str) -> dict:
        """
        将文本分类到最合适的分区。
        优先关键词匹配，embedding 不可用时正常降级。
        """
        data = get_data_repo().load(user_id)

        if not data.partitions:
            return {
                "partition_id": None,
                "is_cross": False,
                "linked_partitions": [],
                "confidence": 0.0,
            }

        # 尝试获取 embedding（可能为 None）
        try:
            text_emb = compute_embedding(text)
        except Exception:
            logger.debug("文本 Embedding 计算失败", exc_info=True)
            text_emb = None

        scores: dict[str, float] = {}
        for pid, partition in data.partitions.items():
            # 关键词为主得分
            kw = keyword_score(text, partition.subject or "")
            kw_boost = keyword_score(text, partition.name)

            if text_emb is not None:
                # Embedding 可用：vec 60% + kw 40%
                target_text = f"{partition.name} {partition.subject or ''}"
                if pid not in self._embeddings_cache:
                    cached = compute_embedding(target_text)
                    if cached:
                        self._embeddings_cache[pid] = cached
                sim = cosine_similarity(text_emb, self._embeddings_cache.get(pid, text_emb))
                scores[pid] = sim * 0.5 + max(kw, kw_boost) * 0.5
            else:
                # 关键词为主：kw 70% + name match 30%
                scores[pid] = max(kw, 0.0) * 0.7 + kw_boost * 0.3

        # 按得分排序
        sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        best_pid, best_score = sorted_scores[0]

        # 确保最低匹配度
        if best_score < 0.15:
            return {
                "partition_id": None,  # 都不匹配 → 创建新分区
                "is_cross": False,
                "linked_partitions": [],
                "confidence": best_score,
            }

        return {
            "partition_id": best_pid,
            "is_cross": False,
            "linked_partitions": [],
            "confidence": best_score,
        }

    def decide_branch(
        self,
        user_id: str,
        partition_id: str,
        text: str,
        recent_messages: list[str],
    ) -> str:
        """决定继续/新建分支"""
        # 引用词 → 继续当前分支
        reference_words = ["刚才", "上面", "之前", "那个", "这个题", "那道题", "接着", "继续"]
        if any(w in text for w in reference_words):
            return "continue"

        # 问题型 + 新关键词 → 新分支
        question_patterns = ["什么是", "怎么", "为什么", "解释", "求", "如何", "区别", "对比"]
        if len(text) > 20 and any(kw in text for kw in question_patterns):
            return "new_branch"

        return "continue"


    def classify_full(
        self, user_id: str, text: str, current_partition_id: str = "",
    ) -> dict:
        """
        三级分类：分区 → 领域 → 专题。
        返回完整路由信息，含是否需要切换推荐。
        """
        data = get_data_repo().load(user_id)

        # Step 1: 分区分类（复用现有逻辑）
        partition_result = self.classify_partition(user_id, text)
        partition_id = partition_result.get("partition_id")
        confidence = partition_result.get("confidence", 0.0)

        if not partition_id and current_partition_id:
            # 无法归类但存在当前分区 → 留在当前
            partition_id = current_partition_id
            confidence = 0.3

        if not partition_id:
            # 完全无法归类 → 需创建新分区
            return {
                "partition_id": None,
                "domain_name": None,
                "topic_name": None,
                "is_switch": False,
                "confidence": 0.0,
            }

        partition = data.partitions.get(partition_id)
        partition_subject = (partition.subject or partition.name) if partition else ""

        # Step 2: 领域分类（关键词匹配）
        domain_name: str | None = None
        domain_score = 0.0
        domain_kws = DOMAIN_KEYWORDS.get(partition_subject, {})

        for dname, kws in domain_kws.items():
            score = keyword_score(text, "")  # reset
            # Manual score for domain keywords
            best = 0.0
            count = 0
            for kw, w in kws.items():
                if kw in text:
                    best = max(best, w)
                    count += 1
            s = best * 0.7 + min(0.3, 0.1 * (count - 1)) if count > 0 else 0.0
            if s > domain_score:
                domain_score = s
                domain_name = dname

        if domain_score < 0.3:
            # 低分不强制 fallback，设为 None 让上层决定
            domain_name = None
            domain_score = 0.0

        # Step 3: 专题分类
        topic_name: str | None = None
        topic_score = 0.0

        topic_kws = TOPIC_KEYWORDS.get(partition_subject, {}).get(domain_name or "", {})
        if topic_kws:
            for tname, kws in topic_kws.items():
                best = 0.0
                count = 0
                for kw, w in kws.items():
                    if kw in text:
                        best = max(best, w)
                        count += 1
                s = best * 0.7 + min(0.3, 0.1 * max(0, count - 1)) if count > 0 else 0.0
                if s > topic_score:
                    topic_score = s
                    topic_name = tname

        if topic_score < 0.3:
            topic_name = None  # 模糊匹配时不强制定专题

        # Step 3.5: 会话级分类（更细粒度）
        conv_name: str | None = None
        conv_score = 0.0
        if topic_name and domain_name:
            conv_kws = CONVERSATION_KEYWORDS.get(partition_subject, {}).get(domain_name, {}).get(topic_name, {})
            for cname, kws in conv_kws.items():
                best = 0.0
                count = 0
                for kw, w in kws.items():
                    if kw in text:
                        best = max(best, w)
                        count += 1
                s = best * 0.7 + min(0.3, 0.1 * max(0, count - 1)) if count > 0 else 0.0
                if s > conv_score:
                    conv_score = s
                    conv_name = cname

            if conv_score < 0.3:
                conv_name = None

        # Step 4: 判断是否需要推荐切换
        is_switch = False
        if current_partition_id and partition_id != current_partition_id:
            is_switch = True

        return {
            "partition_id": partition_id,
            "domain_name": domain_name,
            "topic_name": topic_name,
            "conv_name": conv_name,
            "is_switch": is_switch,
            "confidence": confidence,
        }

    def auto_resolve(
        self, user_id: str, text: str,
        current_partition_id: str = "", current_conversation_id: str = "",
    ) -> dict:
        """
        自动路由：分类检测 → 是否需要推荐切换。
        不再自动创建层级，消息始终存到当前会话。
        切换由用户确认后通过迁移 API 执行。
        """
        # 1. 分类
        full = self.classify_full(user_id, text, current_partition_id)
        target_partition_id = full["partition_id"]
        domain_name = full["domain_name"]
        topic_name = full["topic_name"]
        conv_name = full.get("conv_name")

        # 2. 如果无法归类 → 留在当前分区
        if not target_partition_id and current_partition_id:
            target_partition_id = current_partition_id

        # 3. 检测是否需要推荐切换
        should_recommend_switch = False
        switch_detail: dict = {}
        data = get_data_repo().load(user_id)
        current_topic_id = ""
        if current_conversation_id:
            conv = data.conversations.get(current_conversation_id)
            if conv:
                current_topic_id = conv.topic_id

        # 分区级切换
        if current_partition_id and target_partition_id and target_partition_id != current_partition_id:
            should_recommend_switch = True
            target_part = data.partitions.get(target_partition_id)
            switch_detail = {
                "type": "partition",
                "from_partition": current_partition_id,
                "to_partition": target_partition_id,
                "from_conversation": current_conversation_id,
                "reason": "消息内容更适合另一个分区",
                "to_partition_name": target_part.name if target_part else "",
            }

        # 同分区内专题级切换（目标分区存在）
        if not should_recommend_switch and domain_name and current_topic_id:
            # 查找目标专题
            data = get_data_repo().load(user_id)
            target_topic_id = None
            target_domain_id = None
            for d in data.domains.values():
                if d.partition_id == current_partition_id and d.name == domain_name:
                    target_domain_id = d.id
                    break
            if target_domain_id:
                for t in data.topics.values():
                    if t.domain_id == target_domain_id and (not topic_name or t.name == topic_name):
                        target_topic_id = t.id
                        break
            if target_topic_id and target_topic_id != current_topic_id:
                should_recommend_switch = True
                switch_detail = {
                    "type": "topic",
                    "from_partition": current_partition_id,
                    "to_partition": current_partition_id,
                    "from_conversation": current_conversation_id,
                    "domain_name": domain_name,
                    "topic_name": topic_name,
                    "reason": "消息内容属于不同专题",
                }

        # 4. 构建完整路径（用于前端展示）
        partition_name = ""
        partition_emoji = ""
        if target_partition_id:
            p = data.partitions.get(target_partition_id)
            if p:
                partition_name = p.name
                partition_emoji = p.emoji

        path_parts = []
        if partition_name:
            path_parts.append(f"{partition_emoji} {partition_name}" if partition_emoji else partition_name)
        if domain_name:
            path_parts.append(domain_name)
        if topic_name:
            path_parts.append(topic_name)
        if conv_name:
            path_parts.append(conv_name)
        full_path = " > ".join(path_parts)

        # 始终返回当前会话 — 消息留在原地
        return {
            "partition_id": current_partition_id or target_partition_id or "",
            "conversation_id": current_conversation_id or "",
            "target_partition_id": target_partition_id or "",
            "target_domain_name": domain_name or "",
            "target_topic_name": topic_name or "",
            "target_conv_name": conv_name or "",
            "partition_name": partition_name,
            "full_path": full_path,
            "should_recommend_switch": should_recommend_switch,
            "switch_detail": switch_detail,
            "confidence": full.get("confidence", 0.0),
        }

# 全局单例
classifier = Classifier()
