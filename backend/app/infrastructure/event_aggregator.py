"""
EventHierarchyAggregator — 多维事件层次聚合引擎

三维聚合 (mixed/topic/type) × 六时间窗口 (5m/30m/1h/day/week/month)
每个 (dimension × window_minutes) 生成聚合事件, 多层聚合可层层折叠。

核心理念:
- 原始事件 → 聚合后默认隐藏 (有父可折叠)
- 聚合事件可再被更高层聚合 (有子可展开)
- 多父多子: 一条事件同时参与 mixed/topic/type 三条聚合链

用法:
    aggregator = EventHierarchyAggregator()
    await aggregator.scan()  # 定时扫描, 聚合所有用户
"""
from __future__ import annotations

import asyncio
import logging
import time
from collections import defaultdict
from typing import Optional
from uuid import uuid4

from app.infrastructure.event_store import EventRecord, get_event_store

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════
# 配置
# ═══════════════════════════════════════════

WINDOWS = [5, 30, 60, 1440, 10080, 43200]  # 5m, 30m, 1h, day, week, month
DIMENSIONS = ["mixed", "topic", "type"]
THRESHOLDS = {"mixed": 2, "topic": 1, "type": 2}
SCAN_INTERVAL = 60  # 扫描间隔 (秒)


# ═══════════════════════════════════════════
# 辅助
# ═══════════════════════════════════════════

def _make_id(prefix: str = "agg") -> str:
    return f"{prefix}_{uuid4().hex[:12]}"


def _now() -> float:
    return time.time()


# ═══════════════════════════════════════════
# EventHierarchyAggregator
# ═══════════════════════════════════════════

class EventHierarchyAggregator:
    """多维事件层次聚合引擎"""

    def __init__(self):
        self._running = False
        self._task: Optional[asyncio.Task] = None

    # ── 生命周期 ──

    async def start(self, interval: int = SCAN_INTERVAL) -> None:
        """启动后台扫描"""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._scan_loop(interval))
        logger.info("EventHierarchyAggregator 启动 (interval=%ds)", interval)

    async def stop(self) -> None:
        """停止后台扫描"""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("EventHierarchyAggregator 已停止")

    async def _scan_loop(self, interval: int) -> None:
        """保留兼容 — 轮询由客户端调度器（Web Worker）驱动"""
        pass

    # ── 主扫描 ──

    async def scan(self) -> dict:
        """扫描所有用户, 对所有维度×窗口执行聚合"""
        db = self._get_db()
        users = db.fetchall(
            "SELECT DISTINCT user_id FROM events ORDER BY user_id"
        )
        total = 0
        for row in users:
            user_id = row["user_id"]
            if not user_id:
                continue
            for window in WINDOWS:
                for dim in DIMENSIONS:
                    n = await self._aggregate(user_id, dim, window)
                    total += n
        if total:
            logger.info("聚合扫描完成: %d 个聚合事件", total)
        return {"aggregated": total}

    # ── 单维度×窗口聚合 ──

    async def _aggregate(
        self, user_id: str, dimension: str, window_minutes: int
    ) -> int:
        """对一个 (dimension × window) 执行聚合, 返回生成的事件数"""
        threshold = THRESHOLDS.get(dimension, 2)
        events = self._find_ungrouped(user_id, dimension, window_minutes)
        if len(events) < threshold:
            return 0

        # 分组
        groups = self._group_by_dimension(events, dimension, window_minutes)

        count = 0
        for group_key, group_events in groups.items():
            if len(group_events) < threshold:
                continue
            agg = await self._create_aggregate(
                group_events, user_id, dimension, window_minutes, group_key
            )
            if agg:
                self._write_aggregate(agg)
                self._write_relations(agg.id, [e["id"] for e in group_events])
                count += 1
        return count

    # ── 查找未聚合事件 ──

    def _find_ungrouped(
        self, user_id: str, dimension: str, window_minutes: int
    ) -> list[dict]:
        """查找某维度×窗口内无父节点的事件"""
        db = self._get_db()
        rows = db.fetchall(
            "SELECT e.* FROM events e "
            "WHERE e.user_id = %s "
            "  AND e.created_at >= NOW() - (%s || ' minutes')::INTERVAL "
            "  AND e.id NOT IN ("
            "    SELECT er.child_id FROM event_relations er "
            "    JOIN events p ON er.parent_id = p.id "
            "    WHERE p.payload->>'dimension' = %s "
            "      AND (p.payload->>'window_minutes')::int = %s"
            "  ) "
            "ORDER BY e.created_at ASC",
            (user_id, str(window_minutes), dimension, window_minutes),
        )
        return [dict(r) for r in rows]

    # ── 分组逻辑 ──

    def _group_by_dimension(
        self, events: list[dict], dimension: str, window_minutes: int
    ) -> dict[str, list[dict]]:
        """按维度分组"""
        groups: dict[str, list[dict]] = {}

        if dimension == "mixed":
            # 窗口内所有事件 → 1 组
            key = self._time_bucket_key(events, window_minutes)
            groups[key] = events

        elif dimension == "type":
            # 按 event_type 分组
            for e in events:
                key = e.get("event_type", "unknown")
                if key not in groups:
                    groups[key] = []
                groups[key].append(e)

        elif dimension == "topic":
            # 按 topic_label 分组
            for e in events:
                label = self._extract_topic(e)
                if label not in groups:
                    groups[label] = []
                groups[label].append(e)

        return groups

    def _time_bucket_key(self, events: list[dict], window_minutes: int) -> str:
        """生成时间桶标识"""
        if not events:
            return "unknown"
        ts = min(
            e.get("created_at", 0) for e in events
            if hasattr(e.get("created_at"), "timestamp")
        )
        if ts == 0:
            ts = time.time()
        elif hasattr(ts, "timestamp"):
            ts = ts.timestamp()
        from datetime import datetime, timezone
        dt = datetime.fromtimestamp(ts, tz=timezone.utc)
        if window_minutes >= 1440:
            return dt.strftime("%Y-%m-%d")
        if window_minutes >= 60:
            return dt.strftime("%Y-%m-%dT%H:00")
        return dt.strftime("%Y-%m-%dT%H:%M")

    # ── Topic 提取 ──

    def _extract_topic(self, event: dict) -> str:
        """从事件 payload 提取 topic_label

        策略: 字段映射优先 → 分类器匹配 → LLM fallback → 关键词兜底
        """
        payload = event.get("payload", {})
        if isinstance(payload, str):
            import json
            try:
                payload = json.loads(payload)
            except Exception:
                payload = {}

        # 1. 字段映射 (优先)
        for field in ("skill_id", "label", "topic_label", "domain"):
            v = payload.get(field)
            if v and isinstance(v, str) and len(v) > 0:
                return v

        # 2. 从 event_type 推断
        content = payload.get("content", "") or payload.get("question", "")
        summary = event.get("summary") or ""
        text = summary or content

        if text:
            # 3. 分类器匹配 (已有 topic 相似度)
            topic = self._classify_topic(text, event.get("event_type", ""))
            if topic and topic != "未分类":
                return topic

        # 4. 关键词兜底
        return self._keyword_topic(text) if text else "未分类"

    def _classify_topic(self, text: str, event_type: str) -> str:
        """分类器: 基于文本匹配已有知识节点

        先尝试 ClassifierService 文本匹配, 失败则用关键词规则。
        """
        # 尝试 ClassifierService 文本分类
        try:
            from app.services.common.classifier_service import classifier_service
            result = classifier_service.classify_by_text(
                user_id="",  # 分类器不需要 user_id, 用 ILIKE 匹配
                text=text,
                current_topic_id=None,
            )
            candidates = result.get("candidates", [])
            if candidates:
                best = candidates[0]
                score = best.get("score", 0)
                if score > 0.4:  # 相似度阈值
                    return best.get("label", "")
        except Exception:
            pass

        # 关键词规则 (快速匹配)
        return self._keyword_topic(text)

    def _keyword_topic(self, text: str) -> str:
        """关键词兜底匹配"""
        topic_map = {
            "三角": "三角函数",
            "函数": "函数",
            "方程": "方程",
            "几何": "几何",
            "概率": "概率与统计",
            "数列": "数列",
            "向量": "向量",
            "导数": "导数",
            "积分": "积分",
            "英语": "英语",
            "物理": "物理",
            "化学": "化学",
        }
        for kw, topic in topic_map.items():
            if kw in text:
                return topic
        return "未分类"

    # ── 创建聚合事件 ──

    async def _create_aggregate(
        self,
        children: list[dict],
        user_id: str,
        dimension: str,
        window_minutes: int,
        group_key: str,
    ) -> Optional[EventRecord]:
        """创建聚合事件"""
        if not children:
            return None

        event_type = {
            "mixed": "EpisodeDigest",
            "topic": "TopicDigest",
            "type": "TypeDigest",
        }.get(dimension, "EpisodeDigest")

        stream_type = "aggregate"
        stream_id = self._build_stream_id(dimension, group_key, window_minutes)

        # 时间范围
        timestamps = []
        for c in children:
            ts = c.get("created_at")
            if hasattr(ts, "timestamp"):
                timestamps.append(ts.timestamp())
            elif isinstance(ts, (int, float)):
                timestamps.append(ts)
        window_start = min(timestamps) if timestamps else _now()
        window_end = max(timestamps) if timestamps else _now()

        # 统计子事件类型
        type_counts: dict[str, int] = defaultdict(int)
        for c in children:
            type_counts[c.get("event_type", "unknown")] += 1

        # 计算准确性 (仅答题事件)
        accuracy = None
        answers = [c for c in children if c.get("event_type") == "AnswerSubmitted"]
        if answers:
            correct = sum(
                1 for a in answers
                if (a.get("payload", {}) or {}).get("is_correct")
            )
            accuracy = correct / len(answers) if answers else None

        # 构建 payload
        payload: dict = {
            "dimension": dimension,
            "window_minutes": window_minutes,
            "window_start": window_start,
            "window_end": window_end,
            "child_count": len(children),
            "child_type_counts": dict(type_counts),
        }
        if dimension == "topic":
            payload["topic_label"] = group_key
        if dimension == "type":
            payload["type_label"] = group_key
        if accuracy is not None:
            payload["accuracy"] = accuracy

        # 重要性 = 子事件平均重要性 + 聚合层级加成
        avg_importance = sum(
            float(c.get("importance", 0)) for c in children
        ) / len(children)
        importance = min(1.0, avg_importance + 0.1 * (window_minutes / 1440))

        # AI 摘要
        summary = await self._generate_summary(children, dimension, window_minutes, group_key)

        return EventRecord(
            id=_make_id("agg"),
            user_id=user_id,
            event_type=event_type,
            stream_type=stream_type,
            stream_id=stream_id,
            source_type="aggregator",
            payload=payload,
            summary=summary,
            importance=importance,
            created_at=_now(),
        )

    def _build_stream_id(
        self, dimension: str, group_key: str, window_minutes: int
    ) -> str:
        """构建 stream_id"""
        if dimension == "mixed":
            return f"episode:{group_key}"
        elif dimension == "topic":
            return f"topic:{group_key}:{window_minutes}m"
        else:
            return f"type:{group_key}:{window_minutes}m"

    # ── 写入 ──

    def _write_aggregate(self, event: EventRecord) -> None:
        """写入聚合事件到 events 表"""
        from app.infrastructure.db.events_repository import Event, get_events_repo
        repo = get_events_repo()
        db_event = Event(
            id=event.id,
            user_id=event.user_id,
            event_type=event.event_type,
            stream_type=event.stream_type,
            stream_id=event.stream_id,
            source_type=event.source_type,
            source_id="",
            status="done",
            payload=event.payload,
            summary=event.summary,
            importance=event.importance,
            created_at=event.created_at,
        )
        repo.insert(db_event)

    def _write_relations(self, parent_id: str, child_ids: list[str]) -> None:
        """写入 event_relations"""
        db = self._get_db()
        for cid in child_ids:
            rid = _make_id("rel")
            db.execute(
                "INSERT INTO event_relations (id, parent_id, child_id) "
                "VALUES (%s, %s, %s) ON CONFLICT (parent_id, child_id) DO NOTHING",
                (rid, parent_id, cid),
            )

    # ── AI 摘要生成 ──

    async def _generate_summary(
        self,
        children: list[dict],
        dimension: str,
        window_minutes: int,
        group_key: str,
    ) -> str:
        """生成聚合事件摘要"""
        # 先收集子事件摘要
        summaries = []
        for c in children:
            s = c.get("summary") or ""
            if s:
                summaries.append(s)
            else:
                payload = c.get("payload", {})
                if isinstance(payload, str):
                    try:
                        import json
                        payload = json.loads(payload)
                    except Exception:
                        payload = {}
                content = payload.get("content", "") or payload.get("question", "")
                if content:
                    summaries.append(content[:100])

        if not summaries:
            return "无内容"

        # 统计信息
        total = len(children)
        type_counts = defaultdict(int)
        for c in children:
            type_counts[c.get("event_type", "unknown")] += 1

        # 窗口名称
        window_names = {5: "5分钟", 30: "30分钟", 60: "1小时", 1440: "一天", 10080: "一周", 43200: "一个月"}
        window_name = window_names.get(window_minutes, f"{window_minutes}分钟")

        # 维度前缀
        dim_labels = {"mixed": "学习片段", "topic": group_key, "type": group_key}
        dim_label = dim_labels.get(dimension, dimension)

        # 基础摘要
        counts_str = ", ".join(f"{v}{k}" for k, v in sorted(type_counts.items()))
        base = f"{window_name}内的{dim_label}: {counts_str} (共{total}条)"

        # 尝试 LLM 生成更精炼的摘要
        if len(summaries) >= 2:
            try:
                return await self._llm_summarize(summaries, base)
            except Exception:
                pass

        return base

    async def _llm_summarize(
        self, summaries: list[str], base: str
    ) -> str:
        """LLM 生成精炼摘要"""
        text = " | ".join(s[:200] for s in summaries[:10])
        if len(text) < 50:
            return base
        try:
            from app.infrastructure.llm.llm_service import get_llm_service
            llm = get_llm_service()
            prompt = (
                "用一句话(不超过80字)总结以下学习活动片段,"
                "聚焦于知识点和学生的理解状态, 不需要复述统计数据:\n\n"
                f"{text[:2000]}"
            )
            result = await llm.chat(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=120,
            )
            return result.strip() or base
        except Exception:
            return base

    # ── DB 辅助 ──

    def _get_db(self):
        from app.infrastructure.db.database import get_db
        return get_db()


# ═══════════════════════════════════════════
# 查询工具
# ═══════════════════════════════════════════

def _row_to_dict(row) -> dict:
    """将 DB 行转为 dict，统一 created_at 为 Unix 时间戳 float，处理 embedding 序列化"""
    d = dict(row)
    if "created_at" in d and hasattr(d["created_at"], "timestamp"):
        d["created_at"] = d["created_at"].timestamp()
    # pgvector 类型 → list
    if "embedding" in d and d["embedding"] is not None:
        emb = d["embedding"]
        if hasattr(emb, "tolist"):
            d["embedding"] = emb.tolist()
        elif not isinstance(emb, list):
            d["embedding"] = None
    return d


def get_top_level_events(user_id: str, limit: int = 50, stream_type: str = "") -> list[dict]:
    """获取顶层事件 (没有父节点的事件)，附带子事件计数"""
    db = _get_db_static()
    conditions = [
        "e.user_id = %s",
        "e.id NOT IN (SELECT child_id FROM event_relations)",
    ]
    params: list = [user_id]
    if stream_type:
        conditions.append("e.stream_type = %s")
        params.append(stream_type)
    where = " AND ".join(conditions)
    rows = db.fetchall(
        f"SELECT e.*, "
        f"  (SELECT COUNT(*) FROM event_relations WHERE parent_id = e.id) AS child_count "
        f"FROM events e "
        f"WHERE {where} "
        f"ORDER BY e.created_at DESC LIMIT %s",
        tuple(params + [limit]),
    )
    return [_row_to_dict(r) for r in rows]


def get_children(parent_id: str) -> list[dict]:
    """获取聚合事件的子节点，附带子事件计数"""
    db = _get_db_static()
    rows = db.fetchall(
        "SELECT e.*, "
        "  (SELECT COUNT(*) FROM event_relations WHERE parent_id = e.id) AS child_count "
        "FROM events e "
        "JOIN event_relations er ON e.id = er.child_id "
        "WHERE er.parent_id = %s "
        "ORDER BY e.created_at ASC",
        (parent_id,),
    )
    return [_row_to_dict(r) for r in rows]


def get_ancestors(child_id: str) -> list[dict]:
    """获取事件的所有祖先 (CTE 递归)"""
    db = _get_db_static()
    rows = db.fetchall(
        "WITH RECURSIVE ancestors AS ("
        "  SELECT parent_id, child_id, 1 AS depth "
        "  FROM event_relations WHERE child_id = %s "
        "  UNION ALL "
        "  SELECT er.parent_id, er.child_id, a.depth + 1 "
        "  FROM event_relations er "
        "  JOIN ancestors a ON er.child_id = a.parent_id"
        ") "
        "SELECT e.*, a.depth FROM ancestors a "
        "JOIN events e ON e.id = a.parent_id "
        "ORDER BY a.depth DESC",
        (child_id,),
    )
    return [_row_to_dict(r) for r in rows]


def get_top_level_by_dimension(
    user_id: str, dimension: str, limit: int = 50, stream_type: str = ""
) -> list[dict]:
    """按维度过滤顶层事件，附带子事件计数

    仅排除同维度父节点下的子事件，允许跨维度多父层级。
    """
    db = _get_db_static()
    conditions = [
        "e.user_id = %s",
        "e.payload->>'dimension' = %s",
        # 只排除同维度聚合链中的子节点, 跨维度不排除
        "e.id NOT IN ("
        "  SELECT er.child_id FROM event_relations er"
        "  JOIN events p ON er.parent_id = p.id"
        "  WHERE p.payload->>'dimension' = %s"
        ")",
    ]
    params: list = [user_id, dimension, dimension]
    if stream_type:
        conditions.append("e.stream_type = %s")
        params.append(stream_type)
    where = " AND ".join(conditions)
    rows = db.fetchall(
        f"SELECT e.*, "
        f"  (SELECT COUNT(*) FROM event_relations WHERE parent_id = e.id) AS child_count "
        f"FROM events e "
        f"WHERE {where} "
        f"ORDER BY e.created_at DESC LIMIT %s",
        tuple(params + [limit]),
    )
    return [_row_to_dict(r) for r in rows]


def _get_db_static():
    from app.infrastructure.db.database import get_db
    return get_db()


# ── 全局单例 ──

_aggregator: Optional[EventHierarchyAggregator] = None


def get_event_aggregator() -> EventHierarchyAggregator:
    global _aggregator
    if _aggregator is None:
        _aggregator = EventHierarchyAggregator()
    return _aggregator