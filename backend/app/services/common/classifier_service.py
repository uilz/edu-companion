"""
ClassifierService — 认知图驱动的多路径分类器

替换旧的 classifier.py 中的 classify_partition / classify_full / auto_resolve。

流程：
1. 分层向量检索（先 topic 级再 concept/atom 级）
2. 候选 topic 生成与打分
3. 三种模式决策（跨主题/切换/继续）
4. 沉浸抑制（>16轮深度沉浸不弹出模式1）
"""
from __future__ import annotations

import logging
from typing import Any

from app.cognitive.storage import vector_search

logger = logging.getLogger(__name__)

# 沉浸深度阈值
_DEEP_IMMERSION_THRESHOLD = 16


class ClassifierService:
    """认知图驱动的多路径分类器，支持沉浸追踪"""

    def __init__(self):
        # 沉浸深度：{(user_id, topic_id): consecutive_rounds}
        self._immersion: dict[tuple[str, str], int] = {}

    # ─── 沉浸追踪 ──────────────────────────────

    def get_immersion_depth(self, user_id: str, topic_id: str) -> int:
        """获取当前 topic 的沉浸深度（连续轮数）"""
        return self._immersion.get((user_id, topic_id), 0)

    def increment_immersion(self, user_id: str, topic_id: str) -> int:
        """增加沉浸深度，返回新值"""
        key = (user_id, topic_id)
        depth = self._immersion.get(key, 0) + 1
        self._immersion[key] = depth
        return depth

    def reset_immersion(self, user_id: str, topic_id: str | None = None) -> None:
        """重置指定 topic 的沉浸（切换主题时），topic_id=None 清空全部"""
        if topic_id:
            self._immersion.pop((user_id, topic_id), None)
        else:
            # 清空该用户所有沉浸
            keys = [k for k in self._immersion if k[0] == user_id]
            for k in keys:
                self._immersion.pop(k, None)

    # ─── 主入口 ────────────────────────────────

    def classify(
        self,
        user_id: str,
        query_embedding: list[float],
        current_topic_id: str | None = None,
        text: str = "",  # 用于向量检索无结果时的对话树回退
    ) -> dict[str, Any]:
        """
        主入口：对用户消息 embedding 进行分类

        参数：
            query_embedding: 用户消息的 embedding 向量
            current_topic_id: 当前会话的主 topic node id（可选）

        返回：
        {
            "mode": 1 | 2 | 3,
            "candidates": [...],
            "should_switch": bool,
            "switch_detail": {...} | None,
            "immersion_depth": int,
            "immersion_suppressed": bool,
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

        # 3. 模式决策（含沉浸感知）
        immersion_depth = self.get_immersion_depth(user_id, current_topic_id or "")
        result = self._decide_mode(seeds, current_topic_id, immersion_depth)

        # 4. 沉浸抑制标记
        is_suppressed = (
            immersion_depth >= _DEEP_IMMERSION_THRESHOLD
            and result["mode"] == 1
        )
        result["immersion_suppressed"] = is_suppressed

        # 5. 补充 switch_detail
        if result["should_switch"] and result["candidates"]:
            result["switch_detail"] = {
                "domain_name": self._get_domain_label(result["candidates"][0]),
                "topic_name": result["candidates"][0]["label"],
                "path_id": result["candidates"][0].get("path_id", ""),
            }

        # 6. 沉浸抑制下隐藏候选（不泄露给前端）
        if is_suppressed:
            result["candidates"] = []

        # 7. 向量检索无候选 → 回退到对话树文本分类
        if not result["candidates"] and text:
            tree_result = self.classify_by_text(user_id, text, current_topic_id)
            if tree_result.get("candidates"):
                result["candidates"] = tree_result["candidates"]
                result["mode"] = tree_result["mode"]
                result["should_switch"] = tree_result["should_switch"]

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

        # 3.5 ILIKE 也无结果 → 搜索对话树中的 domain/topic 名称
        if not candidates and text:
            try:
                from app.cognitive.storage import storage
                data = storage.load(user_id)
                words = [w for w in text.replace("?", "").replace("?", "").replace("，", " ").replace(" ", " ").split() if len(w) >= 2]
                # 按名称搜索 domain
                for d in data.domains.values():
                    if any(w in d.name for w in words):
                        candidates.append({
                            "id": d.id,
                            "label": d.name,
                            "path_id": d.name,
                            "score": 0.5,
                        })
                # 按名称搜索 topic
                for t in data.topics.values():
                    if any(w in t.name for w in words):
                        candidates.append({
                            "id": t.id,
                            "label": t.name,
                            "path_id": t.name,
                            "score": 0.5,
                        })
            except Exception:
                pass

        # 3.75 仍无候选 & 有关键词匹配 → 自动创建新节点
        if not candidates and text:
            try:
                matched_keywords = self._keyword_score(text)
                if matched_keywords:
                    top = matched_keywords[0]
                    partition_name = top["partition"]
                    score = top["score"]
                    from app.services.knowledge.tree_ops import tree_ops
                    from app.services.common.storage import storage
                    data = storage.load(user_id)
                    # 找或创建 partition
                    pid = None
                    for p in data.partitions.values():
                        if p.name == partition_name:
                            pid = p.id
                            break
                    if not pid:
                        p = tree_ops.create_partition(user_id, partition_name, subject=partition_name, emoji="📖")
                        pid = p.id
                    # 创建 domain（从关键词提取，取第一个关键词作为 domain 名）
                    words = [w for w in partition_name.replace(" ", "").split() if len(w) >= 2]
                    domain_name = f"{partition_name}入门" if not words else partition_name
                    d = tree_ops.create_domain(user_id, pid, domain_name)
                    # 创建 topic（取消息的前几个字）
                    topic_name = text[:12] + ("..." if len(text) > 12 else "")
                    t = tree_ops.create_topic(user_id, d.id, topic_name)
                    candidates.append({
                        "id": t.id,
                        "label": topic_name,
                        "path_id": f"{partition_name}.{domain_name}.{topic_name}",
                        "score": score,
                    })
            except Exception:
                logger.debug("自动创建节点失败", exc_info=True)

        # 4. 去重 + 截断
        seen = set()
        unique = []
        for c in candidates:
            if c["id"] not in seen:
                seen.add(c["id"])
                unique.append(c)
        candidates = unique[:5]

        # 5. 用相同的模式决策逻辑
        immersion_depth = self.get_immersion_depth(user_id, current_topic_id or "")
        result = self._decide_mode(candidates, current_topic_id, immersion_depth)
        result["immersion_depth"] = immersion_depth
        result["immersion_suppressed"] = (
            immersion_depth >= _DEEP_IMMERSION_THRESHOLD
            and result["mode"] == 1
        )
        return result

    # ─── 关键词匹配 ────────────────────────────

    @staticmethod
    def _keyword_score(text: str) -> list[dict]:
        """关键词匹配，复用 classifier.py 的 KEYWORD_WEIGHTS 表"""
        try:
            from app.services.common.classifier import KEYWORD_WEIGHTS
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

    # ─── 分层向量检索 ──────────────────────────

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
            rows = vector_search(
                query_embedding, user_id,
                level=None, limit=limit, min_similarity=0.05,
            )
            for r in rows:
                rp = r.get("path_id", "")
                if rp.startswith(path_prefix + ".") and r["level"] in ("concept", "atom"):
                    results.append({
                        "id": t["id"],
                        "label": t["label"],
                        "path_id": t["path_id"],
                        "score": r["similarity"] * 0.9,
                        "source": t.get("similarity", 0) * 0.1 + r["similarity"] * 0.9,
                    })
        return results

    # ─── 合并打分 ────────────────────────────

    def _merge_score(
        self, topic_candidates: list[dict], child_candidates: list[dict],
    ) -> list[dict]:
        """合并 topic 候选与子节点候选，按相似度重排序，过滤低分"""
        scores: dict[str, dict] = {}

        for t in topic_candidates:
            scores[t["id"]] = {
                "id": t["id"],
                "label": t["label"],
                "path_id": t.get("path_id", ""),
                "score": t.get("similarity", 0) * 1.0,
            }

        for c in child_candidates:
            tid = c["id"]
            if tid in scores:
                scores[tid]["score"] = max(
                    scores[tid]["score"],
                    c.get("score", 0),
                )

        result = [s for s in scores.values() if s["score"] > 0.1]
        result.sort(key=lambda x: -x["score"])
        return result

    # ─── 三模式决策（含沉浸抑制）───────────────

    def _decide_mode(
        self,
        candidates: list[dict],
        current_topic_id: str | None = None,
        immersion_depth: int = 0,
    ) -> dict[str, Any]:
        """
        模式决策：
        - 模式1（跨主题）：多候选接近，无 >1.5× 领先
        - 模式2（切换）：单一候选 > 第二名×1.5，且与当前不同
        - 模式3（继续）：else

        沉浸抑制：depth > 16 时模式1不弹出，降级为模式3。
        """
        if not candidates:
            return {"mode": 3, "candidates": [], "should_switch": False}

        top = candidates[0]

        # 候选数量 >= 2 且前两名分数接近 → 模式1（跨主题）
        if len(candidates) >= 2:
            second = candidates[1]
            if second["score"] * 1.5 > top["score"]:
                # 深度沉浸抑制
                if immersion_depth >= _DEEP_IMMERSION_THRESHOLD:
                    # 不弹出，但记录到 cognitive_events 供秘书延后处理
                    self._queue_pending_cross_topic(candidates)
                    return {
                        "mode": 3,
                        "candidates": [top],
                        "should_switch": False,
                        "_suppressed_candidates": candidates[:3],
                    }
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

    # ─── 待处理跨主题队列 ──────────────────────

    @staticmethod
    def _queue_pending_cross_topic(candidates: list[dict]) -> None:
        """深度沉浸下将跨主题候选写入 cognitive_events，供秘书延后处理"""
        try:
            from app.services.common.event_service import event_service
            from shared.constants import DEFAULT_USER_ID
            event_service.emit_v6_event(
                event_type="PendingCrossTopic",
                user_id=DEFAULT_USER_ID,
                payload={
                    "candidates": [
                        {"id": c["id"], "label": c["label"], "score": c.get("score", 0)}
                        for c in candidates[:3]
                    ],
                    "suppressed_at_depth": _DEEP_IMMERSION_THRESHOLD,
                },
            )
        except Exception:
            logger.debug("PendingCrossTopic 事件写入失败", exc_info=True)

    # ─── 辅助 ────────────────────────────────

    @staticmethod
    def _get_domain_label(candidate: dict) -> str:
        """从 path_id 提取 domain 层级标签"""
        path = candidate.get("path_id", "")
        segments = path.split(".")
        if len(segments) >= 2:
            return segments[1]
        return segments[0] if segments else ""


# 全局实例
classifier_service = ClassifierService()
