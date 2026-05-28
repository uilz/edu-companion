"""
Phase8Classifier — 认知图驱动的多路径分类器

替换旧的 classifier.py 中的 classify_partition / classify_full / auto_resolve。

流程：
1. 分层向量检索（先 topic 级再 concept/atom 级）
2. 候选 topic 生成与打分
3. 三种模式决策（跨主题/切换/继续）
"""
from __future__ import annotations

import logging
from typing import Any

from app.cognitive.storage import vector_search

logger = logging.getLogger(__name__)


class Phase8Classifier:
    """认知图驱动的多路径分类器"""

    def classify(
        self,
        user_id: str,
        query_embedding: list[float],
        current_topic_id: str | None = None,
    ) -> dict[str, Any]:
        """
        主入口：对用户消息 embedding 进行分类

        参数：
            query_embedding: 用户消息的 embedding 向量
            current_topic_id: 当前会话的主 topic node id（可选）

        返回：
        {
            "mode": 1 | 2 | 3,
            "candidates": [{ "id": str, "label": str, "path_id": str, "score": float }, ...],
            "should_switch": bool,
            "switch_detail": { ... } | None,
        }
        """
        if not query_embedding:
            # 无 embedding → 降级到 keyword + ILIKE
            return self.classify_by_text(user_id, "", current_topic_id)

        # 1. 分层检索
        topic_candidates = self._search_topic(user_id, query_embedding)
        child_candidates = self._search_child(user_id, query_embedding, topic_candidates)

        # 2. 合并打分
        seeds = self._merge_score(topic_candidates, child_candidates)

        # 3. 模式决策
        result = self._decide_mode(seeds, current_topic_id)

        # 4. 补充 switch_detail
        if result["should_switch"] and result["candidates"]:
            result["switch_detail"] = {
                "domain_name": self._get_domain_label(result["candidates"][0]),
                "topic_name": result["candidates"][0]["label"],
                "path_id": result["candidates"][0].get("path_id", ""),
            }
        return result

    def classify_by_text(
        self,
        user_id: str,
        text: str,
        current_topic_id: str | None = None,
    ) -> dict[str, Any]:
        """
        文本降级分类：keyword + ILIKE 检索，返回与 classify() 相同格式。

        当无 embedding 可用时使用。
        """
        candidates = []

        if text:
            # 1. 关键词匹配 → partition 得分
            matched_keywords = self._keyword_score(text)
            if matched_keywords:
                # 2. 对得分最高的 partition，用 ILIKE 找 topic 级节点
                top_partition = matched_keywords[0]["partition"]
                from app.cognitive.storage import search_nodes
                nodes = search_nodes(top_partition, user_id, limit=10)
                for n in nodes:
                    if n.level == "topic":
                        candidates.append({
                            "id": n.id,
                            "label": n.label,
                            "path_id": n.path_id or "",
                            "score": matched_keywords[0]["score"],
                        })
                        break

            # 3. 如果关键词没匹配到，直接 ILIKE 搜索全部节点
            if not candidates:
                from app.cognitive.storage import search_nodes
                nodes = search_nodes(text, user_id, limit=20)
                for n in nodes:
                    if n.level == "topic":
                        candidates.append({
                            "id": n.id,
                            "label": n.label,
                            "path_id": n.path_id or "",
                            "score": 0.5,
                        })

        # 4. 去重 + 截断
        seen = set()
        unique = []
        for c in candidates:
            if c["id"] not in seen:
                seen.add(c["id"])
                unique.append(c)
        candidates = unique[:5]

        # 5. 用相同的模式决策逻辑
        return self._decide_mode(candidates, current_topic_id)

    @staticmethod
    def _keyword_score(text: str) -> list[dict]:
        """关键词匹配，复用 classifier.py 的 KEYWORD_WEIGHTS 表"""
        try:
            from app.services.classifier import KEYWORD_WEIGHTS
        except ImportError:
            return []

        scores: list[dict] = []
        for partition, keywords in KEYWORD_WEIGHTS.items():
            total = 0.0
            for keyword, weight in keywords.items():
                if keyword in text:
                    total += weight
            if total > 0:
                scores.append({
                    "partition": partition,
                    "score": min(total / 2.0, 0.95),
                })
        scores.sort(key=lambda x: -x["score"])
        return scores

    def _search_topic(
        self, user_id: str, query_embedding: list[float], limit: int = 5,
    ) -> list[dict]:
        """检索所有 topic 级节点"""
        return vector_search(
            query_embedding, user_id,
            level="topic", limit=limit, min_similarity=0.1,
        )

    def _search_child(
        self, user_id: str, query_embedding: list[float],
        topics: list[dict], limit: int = 10,
    ) -> list[dict]:
        """对每个 topic 候选，检索其下 concept/atom 节点"""
        results = []
        for t in topics[:3]:
            path_prefix = t.get("path_id", "")
            if not path_prefix:
                continue
            # 用 path_id 前缀过滤
            rows = vector_search(
                query_embedding, user_id,
                level=None, limit=limit, min_similarity=0.05,
            )
            for r in rows:
                rp = r.get("path_id", "")
                if rp.startswith(path_prefix + ".") and r["level"] in ("concept", "atom"):
                    # 将这个子节点映射回它的 topic 祖先
                    results.append({
                        "id": t["id"],
                        "label": t["label"],
                        "path_id": t["path_id"],
                        "score": r["similarity"] * 0.9,
                        "source": t.get("similarity", 0) * 0.1 + r["similarity"] * 0.9,
                    })
        return results

    def _merge_score(
        self, topic_candidates: list[dict], child_candidates: list[dict],
    ) -> list[dict]:
        """合并 topic 候选与子节点候选，按相似度重排序，过滤低分"""
        scores: dict[str, dict] = {}

        # 每个 topic 候选得分 = 自身相似度 × 1.0
        for t in topic_candidates:
            scores[t["id"]] = {
                "id": t["id"],
                "label": t["label"],
                "path_id": t.get("path_id", ""),
                "score": t.get("similarity", 0) * 1.0,
            }

        # child candidate 映射回 topic 祖先的加分
        for c in child_candidates:
            tid = c["id"]
            if tid in scores:
                scores[tid]["score"] = max(
                    scores[tid]["score"],
                    c.get("score", 0),
                )

        # 过滤低分 (< 0.1)
        result = [s for s in scores.values() if s["score"] > 0.1]

        # 按分数降序
        result.sort(key=lambda x: -x["score"])
        return result

    def _decide_mode(
        self, candidates: list[dict], current_topic_id: str | None = None,
    ) -> dict[str, Any]:
        """
        模式决策：
        - 模式1（跨主题）：多候选接近，无 >1.5× 领先
        - 模式2（切换）：单一候选 > 第二名×1.5，且与当前不同
        - 模式3（继续）：else
        """
        if not candidates:
            return {"mode": 3, "candidates": [], "should_switch": False}

        top = candidates[0]
        # 候选数量 >= 2 且前两名分数接近
        if len(candidates) >= 2:
            second = candidates[1]
            if second["score"] * 1.5 > top["score"]:
                return {
                    "mode": 1,
                    "candidates": candidates[:3],
                    "should_switch": True,
                }

        # 单一高分候选，与当前 topic 不同 → 切换
        if current_topic_id and top["id"] != current_topic_id:
            return {
                "mode": 2,
                "candidates": [top],
                "should_switch": True,
            }

        # 其他情况：继续
        return {
            "mode": 3,
            "candidates": [top],
            "should_switch": False,
        }

    def _get_domain_label(self, candidate: dict) -> str:
        """从 path_id 提取 domain 层级标签"""
        path = candidate.get("path_id", "")
        segments = path.split(".")
        if len(segments) >= 2:
            return segments[1]
        return segments[0] if segments else ""


# 全局实例
phase8_classifier = Phase8Classifier()
