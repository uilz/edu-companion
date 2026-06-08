"""知识图谱领域服务 — 日志增强版"""

import logging

logger = logging.getLogger(__name__)


class KnowledgeGraphServiceImpl:
    def __init__(self, practice, event_bus):
        self._practice = practice
        self._bus = event_bus

    async def on_answer_submitted(self, event):
        """事件: 答题 → 同步 CognitiveNode belief + practice_summary"""
        user_id = getattr(event, "user_id", "?")
        skill_id = getattr(event, "skill_id", "?")
        is_correct = getattr(event, "is_correct", False)
        time_spent = getattr(event, "time_spent", 0.0)
        hints_used = getattr(event, "hints_used", 0)

        # 已经支持 CognitiveNode，通过 sync_from_practice_event 统一更新
        try:
            from app.cognitive import get_repo
            get_repo().sync_from_practice_event(
                user_id=user_id,
                skill_id=skill_id,
                is_correct=bool(is_correct),
                time_spent=time_spent,
                hints_used=hints_used,
            )
            logger.info(
                "Knowledge: synced practice to CognitiveNode user=%s skill=%s correct=%s",
                user_id, skill_id, is_correct,
            )
        except Exception as exc:
            logger.warning("Knowledge: failed to sync practice to CognitiveNode: %s", exc)

    async def on_error_recorded(self, event):
        """事件: 错误 → 标记薄弱知识点，更新 CognitiveNode 的 error_clusters"""
        user_id = getattr(event, "user_id", "?")
        skill_id = getattr(event, "skill_id", "?")
        error_type = getattr(event, "error_type", "unknown")

        logger.info(
            "Knowledge: error recorded user=%s skill=%s type=%s",
            user_id, skill_id, error_type,
        )

        # Update the CognitiveNode's error_clusters for this skill
        try:
            import time
            from app.cognitive import get_repo
            from app.cognitive.models import ErrorCluster

            node_id = f"{user_id}:{skill_id}"
            node = get_repo().get_node(node_id, user_id=user_id)

            if node is None:
                from app.cognitive.models import CognitiveNode
                node = CognitiveNode(id=node_id, label=skill_id)

            # Find existing cluster for this error type or create a new one
            cluster_id = f"{skill_id}:{error_type}"
            existing = [c for c in node.error_clusters if c.cluster_id == cluster_id]
            if existing:
                existing[0].count += 1
                existing[0].last_seen = time.time()
            else:
                node.error_clusters.append(
                    ErrorCluster(cluster_id=cluster_id, count=1, last_seen=time.time())
                )

            node.bump_version()
            get_repo().upsert_node(node, user_id=user_id)
            logger.info(
                "Knowledge: error cluster updated node=%s cluster=%s count=%d",
                node_id, cluster_id, 
                next(c.count for c in node.error_clusters if c.cluster_id == cluster_id),
            )
        except Exception as exc:
            logger.warning("Knowledge: failed to update error_clusters: %s", exc)

    async def get_graph(self, user_id):
        return {}

    async def can_practice(self, user_id, skill_id):
        return True, None

    async def find_learning_path(self, user_id, target_skill):
        return []
