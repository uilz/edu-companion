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

from app.domain.cognitive import get_repo

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

        # 1. 分层检索 (路径[A]: CognitiveNode)
        topic_candidates = self._search_topic(user_id, query_embedding)
        child_candidates = self._search_child(user_id, query_embedding, topic_candidates)

        # 2. 合并打分
        seeds = self._merge_score(topic_candidates, child_candidates)

        # 2b. 路径[B]: DirectoryNode 匹配 (文本匹配)
        if text:
            try:
                dir_candidates = self._search_directory_nodes(user_id, text)
                # 合并到种子列表
                existing_ids = {s["id"] for s in seeds}
                for dc in dir_candidates:
                    if dc["id"] not in existing_ids:
                        seeds.append(dc)
                        existing_ids.add(dc["id"])
                seeds.sort(key=lambda x: -x["score"])
            except Exception:
                logger.debug("DirectoryNode 匹配失败", exc_info=True)

        # 3. 模式决策（含沉浸感知）
        immersion_depth = self.get_immersion_depth(user_id, current_topic_id or "")
        result = self._decide_mode(seeds, current_topic_id, immersion_depth, user_id)

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

    # ─── 路径[B]: DirectoryNode 匹配 ────────────────────

    def _search_directory_nodes(
        self, user_id: str, text: str,
    ) -> list[dict]:
        """路径[B]: 按名称/summary_short 匹配用户目录树中的 DirectoryNode。

        返回与路径[A]兼容的候选列表，source="directory" 标记来源。
        """
        from app.services.common import get_data_repo
        data = get_data_repo().load(user_id)
        candidates: list[dict] = []
        words = [
            w for w in text
            .replace("?", "").replace("?", "").replace("，", " ")
            .replace(" ", " ").split()
            if len(w) >= 2
        ]
        if not words:
            return candidates

        for dn in data.directory_nodes.values():
            if dn.node_type != "dir":
                continue
            search_text = f"{dn.name} {dn.summary_short} {dn.display_name}"
            matched = sum(1 for w in words if w in search_text)
            if matched == 0:
                continue
            score = min(matched / len(words), 0.95)
            # 构建路径名称链
            path_names: list[str] = []
            pid = dn.parent_id
            while pid and pid in data.directory_nodes:
                p = data.directory_nodes[pid]
                path_names.insert(0, p.display_name)
                pid = p.parent_id
            candidates.append({
                "id": dn.id,
                "label": dn.display_name,
                "path_id": ".".join(path_names + [dn.display_name]),
                "score": score,
                "source": "directory",
            })

        candidates.sort(key=lambda x: -x["score"])
        return candidates[:5]

    def classify_by_text(
        self,
        user_id: str,
        text: str,
        current_topic_id: str | None = None,
    ) -> dict[str, Any]:
        """
        文本降级分类：ILIKE 检索 CognitiveNode + 名称匹配 DirectoryNode。

        当无 embedding 可用时使用。旧 keyword_weights 配置已删除。
        """
        candidates = []

        # 1. ILIKE 搜索 CognitiveNode (topic 级)
        if text:
            nodes = get_repo().search_by_text(text, user_id, limit=20)
            for n in nodes:
                if n.level == "topic":
                    candidates.append({
                        "id": n.id,
                        "label": n.label,
                        "path_id": n.path_id or "",
                        "score": 0.5,
                    })

        # 2. ILIKE 无结果 → 搜索 DirectoryNode 名称
        if not candidates and text:
            try:
                from app.services.common import get_data_repo
                data = get_data_repo().load(user_id)
                words = [w for w in text.replace("?", "").replace("，", " ").replace(" ", " ").split() if len(w) >= 2]
                for dn in data.directory_nodes.values():
                    if dn.node_type == "dir":
                        if any(w in dn.name for w in words):
                            candidates.append({
                                "id": dn.id,
                                "label": dn.name,
                                "path_id": dn.name,
                                "score": 0.5,
                            })
            except Exception:
                pass

        # 3. 去重 + 截断
        seen = set()
        unique = []
        for c in candidates:
            if c["id"] not in seen:
                seen.add(c["id"])
                unique.append(c)
        candidates = unique[:5]

        # 4. 模式决策
        immersion_depth = self.get_immersion_depth(user_id, current_topic_id or "")
        result = self._decide_mode(candidates, current_topic_id, immersion_depth, user_id)
        result["immersion_depth"] = immersion_depth
        result["immersion_suppressed"] = (
            immersion_depth >= _DEEP_IMMERSION_THRESHOLD
            and result["mode"] == 1
        )
        return result

    # ─── 分层向量检索 ──────────────────────────

    def _search_topic(
        self, user_id: str, query_embedding: list[float], limit: int = 5,
    ) -> list[dict]:
        """检索所有 topic 级节点"""
        return get_repo().vector_search(
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
            rows = get_repo().vector_search(
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
        user_id: str | None = None,
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
                    if user_id:
                        self._queue_pending_cross_topic(candidates, user_id)
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
    def _queue_pending_cross_topic(candidates: list[dict], user_id: str) -> None:
        """深度沉浸下将跨主题候选通过 EventBus 发布，供秘书延后处理"""
        try:
            from app.application.di import get_event_bus
            from shared.events import PendingCrossTopic
            import asyncio
            bus = get_event_bus()
            asyncio.ensure_future(bus.publish(PendingCrossTopic(
                user_id=user_id,
                candidates=[
                    {"id": c["id"], "label": c["label"], "score": c.get("score", 0)}
                    for c in candidates[:3]
                ],
                suppressed_at_depth=_DEEP_IMMERSION_THRESHOLD,
            )))
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
