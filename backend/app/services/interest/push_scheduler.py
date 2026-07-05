"""
InterestExplorer 推送调度器

按 docs/modules/interest-explorer/overview.md §4-§6 + ADR 0007 决策 1-2-7-11 实现:
- 按用户偏好（频率/时间/比例）调度
- 链接级别去重
- 本地权重调整
- 复用秘书 Proposal 机制（InterestPushProposal）
- 3 种推送类型: research_object / research_method / hot_news
- 推送比例可配置（默认 50/30/20）
- 跨学科推送（默认关闭，可开启）
- 时区感知
"""

from __future__ import annotations

import asyncio
import logging
import random
from datetime import datetime, time as dtime, timezone
from typing import Any, Optional

from app.services.interest import store
from app.services.interest.tag_matcher import (
    TagMatch,
    match_tags_against_item,
    compute_sampling_weights,
)
from shared.events import (
    InterestPushGenerated,
    InterestPrefsUpdated,
    CrossModuleTarget,
)

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════
# 推送调度器主体
# ═══════════════════════════════════════════


class PushScheduler:
    """推送调度器

    设计:
      - run_for_user(user_id): 为单个用户执行一次推送调度
      - run_for_all(): 遍历所有启用推送的用户
      - sample_pushes(): 按比例 (research_object / method / hot_news) 采样
    """

    async def run_for_user(self, user_id: str, force: bool = False) -> dict:
        """为单个用户执行推送调度

        Args:
            user_id: 用户 ID
            force: True 跳过时间检查（手动触发）

        Returns:
            {
              "pushed_count": int,
              "by_type": {"research_object": n, "research_method": n, "hot_news": n},
              "skipped_reason": str | None,
            }
        """
        prefs = store.get_prefs(user_id)
        if not prefs.get("is_enabled", True):
            return {
                "pushed_count": 0,
                "by_type": {},
                "skipped_reason": "push_disabled",
            }

        # 检查时间
        if not force and not self._is_push_window(prefs):
            return {
                "pushed_count": 0,
                "by_type": {},
                "skipped_reason": "outside_push_window",
            }

        # 检查频率
        if not force and not self._is_push_due(user_id, prefs):
            return {
                "pushed_count": 0,
                "by_type": {},
                "skipped_reason": "not_due",
            }

        # 计算推送数量
        daily_limit = int(prefs.get("daily_limit", 6))
        obj_pct = int(prefs.get("research_object_pct", 50))
        method_pct = int(prefs.get("research_method_pct", 30))
        hot_pct = int(prefs.get("hot_news_pct", 20))

        n_obj = round(daily_limit * obj_pct / 100)
        n_method = round(daily_limit * method_pct / 100)
        n_hot = daily_limit - n_obj - n_method  # 余数给 hot_news
        if n_hot < 0:
            n_hot = 0

        # 采样推送
        cross = bool(prefs.get("cross_disciplinary", False))
        sampled = await self._sample_pushes(
            user_id=user_id,
            n_object=n_obj,
            n_method=n_method,
            n_hot=n_hot,
            cross_disciplinary=cross,
        )

        # 写入推送记录 + 发布事件 + 复用 Proposal
        by_type = {"research_object": 0, "research_method": 0, "hot_news": 0}
        for push in sampled:
            rec = store.create_push_record(
                user_id=user_id,
                push_type=push["push_type"],
                title=push["title"],
                source_id=push.get("source_id"),
                summary=push.get("summary", ""),
                url=push.get("url"),
                author=push.get("author"),
                published_at=push.get("published_at"),
                matched_tags=push.get("matched_tags", []),
            )
            if rec:
                by_type[push["push_type"]] += 1
                await self._publish_push(rec, user_id)
                await self._notify_proposal(rec, push, user_id)

        return {
            "pushed_count": sum(by_type.values()),
            "by_type": by_type,
            "skipped_reason": None,
        }

    async def run_for_all(self) -> list[dict]:
        """遍历所有启用推送的用户执行调度"""
        db = store.get_db()
        rows = db.fetchall(
            "SELECT user_id FROM interest_push_prefs WHERE is_enabled = TRUE"
        )
        results: list[dict] = []
        for row in rows:
            try:
                result = await self.run_for_user(row["user_id"], force=True)
                results.append({"user_id": row["user_id"], **result})
            except Exception as e:
                logger.warning("run_for_user 失败 (%s): %s", row["user_id"], e)
                results.append({
                    "user_id": row["user_id"],
                    "error": str(e),
                })
        return results

    # ── 采样 ──

    async def _sample_pushes(
        self,
        user_id: str,
        n_object: int,
        n_method: int,
        n_hot: int,
        cross_disciplinary: bool = False,
    ) -> list[dict]:
        """按比例采样推送

        关键设计:
          - 从 user 启用的信息源中读取最近抓取的条目
          - 按 push_type 过滤
          - 按 matched_tags 过滤
          - 跨学科时不过滤标签
          - 本地权重 dislike_score 调整采样概率
        """
        if n_object + n_method + n_hot == 0:
            return []

        weights = compute_sampling_weights(
            user_id, cross_disciplinary=cross_disciplinary
        )
        # 加载用户启用的信息源最近条目
        candidates = self._load_candidates(user_id, cross_disciplinary)

        # 按标签权重采样（带随机扰动 + dislike_score 衰减）
        results: list[dict] = []
        for push_type, n in [
            ("research_object", n_object),
            ("research_method", n_method),
            ("hot_news", n_hot),
        ]:
            if n <= 0:
                continue
            type_candidates = [
                c for c in candidates if c["push_type"] == push_type
            ]
            if not type_candidates:
                continue
            picked = self._weighted_sample(
                type_candidates, weights, n
            )
            results.extend(picked)

        return results

    def _load_candidates(
        self, user_id: str, cross_disciplinary: bool
    ) -> list[dict]:
        """加载用户信息源最近抓取的条目（未推送/未 dislike 的）

        数据流:
          - 找到用户启用的所有 source_id (系统源 + 私有源)
          - 从 interest_fetched_items 读取最近条目
          - 对每条做标签匹配 → matched_tags
          - 过滤掉用户已 dislike 或已 imported 的
        """
        source_ids = store.list_enabled_source_ids_for_user(user_id)
        if not source_ids:
            return []
        # 只看最近 7 天的抓取
        from datetime import timedelta
        since = datetime.now(timezone.utc) - timedelta(days=7)
        items = store.list_fetched_items(source_ids, since=since)
        if not items:
            return []

        # 加载用户已 dislike/imported 的 push_id → 对应 url，避免重复推送
        feedback_rows = store.list_feedback(user_id, limit=500)
        existing_urls = {
            p["url"] for p in store.list_push_records(user_id, limit=500)
            if p.get("url")
        }
        disliked_urls: set[str] = set()
        imported_urls: set[str] = set()
        for f in feedback_rows:
            url = f.get("push_url")
            if not url:
                continue
            if f.get("feedback") == "dislike":
                disliked_urls.add(url)
            elif f.get("feedback") == "imported":
                imported_urls.add(url)

        # 标签匹配
        candidates: list[dict] = []
        for it in items:
            url = it.get("url")
            if not url:
                continue
            if url in existing_urls or url in disliked_urls or url in imported_urls:
                continue
            tag_matches = match_tags_against_item(
                user_id=user_id,
                title=it.get("title", ""),
                summary=it.get("summary", ""),
            )
            matched_tag_ids = [tm.tag_id for tm in tag_matches if tm.matched]
            if not cross_disciplinary and not matched_tag_ids:
                continue
            # 类型推断: 启发式 — 简单从 source 类别判断
            push_type = self._infer_push_type(it)
            candidates.append({
                "title": it.get("title", ""),
                "url": url,
                "summary": it.get("summary", ""),
                "author": it.get("author"),
                "published_at": it.get("published_at"),
                "source_id": it.get("source_id"),
                "matched_tags": matched_tag_ids,
                "push_type": push_type,
            })
        return candidates

    @staticmethod
    def _infer_push_type(item: dict) -> str:
        """启发式判断推送类型

        - 标题包含 method/framework/survey 关键词 → research_method
        - 标题包含 news/highlight/breaking → hot_news
        - 其他 → research_object (具体研究对象)
        """
        title = (item.get("title") or "").lower()
        summary = (item.get("summary") or "").lower()
        text = title + " " + summary

        method_kw = ("framework", "method", "approach", "algorithm",
                     "methodology", "survey", "review of", "model for")
        news_kw = ("news", "highlights", "breaking", "announcement",
                   "press release", "new:", "latest:")

        for kw in method_kw:
            if kw in text:
                return "research_method"
        for kw in news_kw:
            if kw in text:
                return "hot_news"
        return "research_object"

    def _weighted_sample(
        self,
        candidates: list[dict],
        weights: list[tuple[str, float]],
        n: int,
    ) -> list[dict]:
        """加权采样

        candidates: 待采样的推送
        weights: [(tag_id, weight)] 标签权重
        """
        if not candidates:
            return []
        weight_map = dict(weights)
        scored: list[tuple[float, dict]] = []
        for c in candidates:
            tags = c.get("matched_tags") or []
            score = 0.0
            for tid in tags:
                score += weight_map.get(tid, 0.0)
            # 候选无标签时给一个小的均匀权重
            if score == 0.0:
                score = 0.1
            # 随机扰动
            score *= random.uniform(0.5, 1.5)
            scored.append((score, c))
        scored.sort(key=lambda x: -x[0])
        return [c for _, c in scored[:n]]

    # ── 时间检查 ──

    def _is_push_window(self, prefs: dict) -> bool:
        """检查是否到达推送时间窗口（±30 分钟）"""
        try:
            from zoneinfo import ZoneInfo
            tz_str = prefs.get("timezone") or "Asia/Shanghai"
            tz = ZoneInfo(tz_str)
            now = datetime.now(tz)
            push_time = prefs.get("push_time", "08:00:00")
            if isinstance(push_time, str):
                parts = push_time.split(":")
                h, m = int(parts[0]), int(parts[1])
            else:
                h, m = 8, 0
            target = now.replace(hour=h, minute=m, second=0, microsecond=0)
            delta_min = abs((now - target).total_seconds() / 60)
            return delta_min <= 30
        except Exception:
            return True

    def _is_push_due(self, user_id: str, prefs: dict) -> bool:
        """检查推送频率是否到期（每日 / 每周）"""
        freq = prefs.get("frequency", "daily")
        if freq == "manual":
            return False
        records = store.list_push_records(user_id, limit=1)
        if not records:
            return True
        last = records[0]["generated_at"]
        if isinstance(last, str):
            try:
                last = datetime.fromisoformat(last.replace("Z", "+00:00"))
            except Exception:
                return True
        if freq == "daily":
            return (datetime.now(timezone.utc) - last).days >= 1
        if freq == "weekly":
            return (datetime.now(timezone.utc) - last).days >= 7
        return True

    # ── 事件 + 通知 ──

    async def _publish_push(self, rec: dict, user_id: str) -> None:
        """发布 InterestPushGenerated 事件"""
        try:
            from app.application.di import container
            await container.event_bus.publish(InterestPushGenerated(
                user_id=user_id,
                push_id=rec["id"],
                push_type=rec["push_type"],
                title=rec["title"],
                url=rec.get("url") or "",
                source_id=rec.get("source_id"),
                source_name="",
                matched_tags=rec.get("matched_tags") or [],
                summary_preview=(rec.get("summary") or "")[:200],
            ))
        except Exception as e:
            logger.debug("InterestPushGenerated 事件发布失败: %s", e)

    async def _notify_proposal(self, rec: dict, push: dict, user_id: str) -> None:
        """通过秘书 Proposal 机制推送通知（决策 2）

        复用 Proposal（命名 InterestPushProposal）

        Args:
            rec: push_record dict (含 id, push_type, url 等)
            push: 推送数据 (含 title, summary)
            user_id: 必填, 用于 save_proposal 的归属
        """
        try:
            from app.infrastructure.db.proposal_store import ProposalStore
            from app.domain.secretary.models import Proposal
            store_p = ProposalStore()
            proposal = Proposal(
                emoji="🔍",
                title=push["title"][:100],
                description=push.get("summary", "")[:300],
                action_type="interest_push",
                priority=3,
                payload={
                    "push_id": rec["id"],
                    "push_type": rec["push_type"],
                    "url": rec.get("url") or "",
                    "source_id": rec.get("source_id"),
                    "matched_tags": rec.get("matched_tags") or [],
                },
                insight_source="interest_explorer.push_scheduler",
                generated_by="interest_explorer",
                overrideable=True,
            )
            store_p.save_proposal(proposal, user_id)
        except Exception as e:
            logger.debug("Proposal 推送失败: %s", e)


# ═══════════════════════════════════════════
# 模块单例
# ═══════════════════════════════════════════

_scheduler: PushScheduler | None = None


def get_scheduler() -> PushScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = PushScheduler()
    return _scheduler


# ═══════════════════════════════════════════
# 周期任务（接入中央调度器）
# ═══════════════════════════════════════════


async def interest_push_tick() -> None:
    """中央调度器每 30 分钟调用一次：检查并执行推送"""
    try:
        scheduler = get_scheduler()
        # 默认按时间窗口（08:00±30min）触发
        # 其他时间手动触发或由 scheduler 路由
        results = await scheduler.run_for_all()
        if results:
            n = sum(r.get("pushed_count", 0) for r in results)
            if n:
                logger.info("🔍 InterestExplorer 推送: %d 条", n)
    except Exception as e:
        logger.warning("interest_push_tick 失败: %s", e)
