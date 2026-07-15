"""GrowthRepository — GrowthRecord 持久化。

V1 使用内存存储 + JSON 文件备份。未来可迁移到 SQL。
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.domain.growth.models import GrowthRecord

# 文件存储路径
_STORAGE_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", ".data", "growth")
os.makedirs(_STORAGE_DIR, exist_ok=True)


class GrowthRepository:
    """GrowthRecord 仓储。"""

    def __init__(self):
        self._store: dict[str, GrowthRecord] = {}
        self._by_learner: dict[str, list[str]] = {}  # learner_id → [record_id, ...]
        self._load_all()

    def _load_all(self):
        """从文件备份加载所有 GrowthRecord。"""
        from app.domain.growth.models import GrowthRecord, SkillGain

        if not os.path.isdir(_STORAGE_DIR):
            return
        for filename in os.listdir(_STORAGE_DIR):
            if not filename.endswith(".json"):
                continue
            path = os.path.join(_STORAGE_DIR, filename)
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except (json.JSONDecodeError, OSError):
                continue
            if not isinstance(data, list):
                continue
            for item in data:
                try:
                    record = GrowthRecord(
                        id=item["id"],
                        learner_id=item["learner_id"],
                        session_id=item["session_id"],
                        session_title=item.get("session_title", ""),
                        session_started_at=item.get("session_started_at", 0.0),
                        session_finished_at=item.get("session_finished_at"),
                        created_at=item.get("created_at", 0.0),
                        summary=item.get("summary", ""),
                        reflection_snippet=item.get("reflection_snippet", ""),
                        key_takeaways=item.get("key_takeaways", []),
                        next_steps=item.get("next_steps", []),
                        skill_gains=[
                            SkillGain(
                                skill=g.get("skill", ""),
                                before=g.get("before", 0.0),
                                after=g.get("after", 0.0),
                                evidence=g.get("evidence", ""),
                                category=g.get("category", "knowledge"),
                            )
                            for g in item.get("skill_gains", [])
                        ],
                    )
                    self._store[record.id] = record
                    ids = self._by_learner.setdefault(record.learner_id, [])
                    if record.id not in ids:
                        ids.append(record.id)
                except (KeyError, TypeError):
                    continue

    def save(self, record: GrowthRecord) -> None:
        """保存 GrowthRecord。"""
        self._store[record.id] = record
        ids = self._by_learner.setdefault(record.learner_id, [])
        if record.id not in ids:
            ids.append(record.id)

        # 异步写入文件备份
        self._write_file(record.learner_id)

    def get(self, record_id: str) -> GrowthRecord | None:
        """按 ID 获取。"""
        return self._store.get(record_id)

    def list_by_learner(
        self, learner_id: str, limit: int = 30
    ) -> list[GrowthRecord]:
        """按 Learner 获取最近的 GrowthRecord。"""
        ids = self._by_learner.get(learner_id, [])
        records = [self._store[rid] for rid in reversed(ids) if rid in self._store]
        return records[:limit]

    def list_by_session(self, session_id: str) -> list[GrowthRecord]:
        """按 Session 获取（通常 1 个）。"""
        return [
            r for r in self._store.values()
            if r.session_id == session_id
        ]

    def get_latest(self, learner_id: str) -> GrowthRecord | None:
        """获取最新的 GrowthRecord。"""
        ids = self._by_learner.get(learner_id, [])
        if not ids:
            return None
        return self._store.get(ids[-1])

    def count(self, learner_id: str) -> int:
        """Learner 的 GrowthRecord 总数。"""
        return len(self._by_learner.get(learner_id, []))

    def total_gain_sum(self, learner_id: str) -> float:
        """Learner 的所有成长增益总和。"""
        return round(sum(
            r.total_gain for r in self.list_by_learner(learner_id, limit=999
        )), 2)

    def _write_file(self, learner_id: str):
        """写入 JSON 备份文件。"""
        try:
            records = self.list_by_learner(learner_id, limit=9999)
            data = []
            for r in records:
                data.append({
                    "id": r.id,
                    "learner_id": r.learner_id,
                    "session_id": r.session_id,
                    "session_title": r.session_title,
                    "session_started_at": r.session_started_at,
                    "session_finished_at": r.session_finished_at,
                    "created_at": r.created_at,
                    "skill_gains": [
                        {
                            "skill": g.skill,
                            "before": g.before,
                            "after": g.after,
                            "evidence": g.evidence,
                            "category": g.category,
                        }
                        for g in r.skill_gains
                    ],
                    "summary": r.summary,
                    "reflection_snippet": r.reflection_snippet,
                    "key_takeaways": r.key_takeaways,
                    "next_steps": r.next_steps,
                })
            dest = os.path.join(_STORAGE_DIR, f"{learner_id}.json")
            with open(dest, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass  # 文件写入失败不阻塞主流程


# 模块级单例
_growth_repo: GrowthRepository | None = None


def get_growth_repo() -> GrowthRepository:
    global _growth_repo
    if _growth_repo is None:
        _growth_repo = GrowthRepository()
    return _growth_repo
