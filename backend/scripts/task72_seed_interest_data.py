"""
Task #72: InterestExplorer E2E 测试数据 seed 脚本

目的：
  - 为 e2e_admin 用户订阅一个启用的系统信息源（避免 trigger_push 候选为空）
  - 插入 N 条带 URL 的 interest_fetched_items（让 push_scheduler 有候选可采样）
  - 插入少量 interest_push_records（让反馈/跨模块导入流程可触发）

用法：
  cd /home/deploy/edu-companion/backend
  python3 -m scripts.task72_seed_interest_data [--reset] [--user-id u_xxx]

输出 (JSON to stdout):
  { "user_id": ..., "subscribed_source": ..., "fetched_count": N, "push_count": M }
"""
from __future__ import annotations

import argparse
import json
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from app.infrastructure.db.database import get_db  # noqa: E402
from app.services.interest import store  # noqa: E402


TEST_FETCHED_ITEMS: list[dict] = [
    {
        "title": "A Survey of Large Language Model Reasoning",
        "url": "https://arxiv.org/abs/2607.00001",
        "summary": "Comprehensive survey of reasoning techniques in LLMs including chain-of-thought, tree-of-thought, and self-consistency methods.",
        "author": "Test Author A",
    },
    {
        "title": "Efficient Neural Architecture Search Framework",
        "url": "https://arxiv.org/abs/2607.00002",
        "summary": "A novel framework for automated neural architecture search with reduced computational cost.",
        "author": "Test Author B",
    },
    {
        "title": "Machine Learning in Drug Discovery: A Review",
        "url": "https://arxiv.org/abs/2607.00003",
        "summary": "Recent advances in applying machine learning to drug discovery and design.",
        "author": "Test Author C",
    },
    {
        "title": "Breaking News: Latest AI Breakthroughs",
        "url": "https://example.com/news/2607-ai-breakthroughs",
        "summary": "News article about recent AI research advances.",
        "author": "News Reporter",
    },
    {
        "title": "Deep Learning Survey of Computer Vision",
        "url": "https://arxiv.org/abs/2607.00004",
        "summary": "Survey of deep learning methods in computer vision tasks.",
        "author": "Test Author D",
    },
]


def ensure_user_seed_tags(user_id: str) -> list[dict]:
    """为用户创建 level 2 标签，覆盖 seed 候选的关键词
    - 只在用户尚无该名标签时创建
    - 返回已创建/已存在的标签列表
    """
    SEED_L2_TAGS = [
        "Machine Learning",
        "Computer Vision",
        "AI",
    ]
    db = get_db()
    # 找到任意 L1 标签作父级（不存在则父级为空，最终落到 root）
    parent = db.fetchone(
        "SELECT id FROM interest_tags WHERE user_id = %s AND level = 0 LIMIT 1",
        (user_id,),
    )
    parent_id = parent["id"] if parent else None

    out: list[dict] = []
    for name in SEED_L2_TAGS:
        existing = db.fetchone(
            "SELECT * FROM interest_tags WHERE user_id = %s AND name = %s AND level = 2 LIMIT 1",
            (user_id, name),
        )
        if existing:
            out.append(dict(existing))
            continue
        tag_id = str(uuid.uuid4())
        db.execute(
            """
            INSERT INTO interest_tags
            (id, user_id, name, level, parent_id, weight, source, color, created_at)
            VALUES (%s, %s, %s, 2, %s, 1, 'manual', NULL, NOW())
            """,
            (tag_id, user_id, name, parent_id),
        )
        out.append({"id": tag_id, "user_id": user_id, "name": name, "level": 2, "parent_id": parent_id, "weight": 1})
    return out


def ensure_user_subscribed(user_id: str) -> dict:
    """为用户订阅一个启用的系统源，若未订阅则启用"""
    db = get_db()
    # 找一个启用的系统源
    src = db.fetchone(
        """
        SELECT id, name, type FROM interest_sources
        WHERE user_id IS NULL AND enabled = TRUE
        ORDER BY name
        LIMIT 1
        """
    )
    if not src:
        raise RuntimeError("No enabled system source found")
    # 订阅并启用
    db.execute(
        """
        INSERT INTO interest_source_subscriptions
        (id, user_id, source_id, enabled, created_at, updated_at)
        VALUES (%s, %s, %s, TRUE, NOW(), NOW())
        ON CONFLICT (user_id, source_id) DO UPDATE
        SET enabled = TRUE, updated_at = NOW()
        """,
        (str(uuid.uuid4()), user_id, src["id"]),
    )
    return {"id": src["id"], "name": src["name"], "type": src["type"]}


def ensure_user_disabled_other_subs(user_id: str) -> int:
    """关闭用户其他订阅，避免被其他源干扰 push 抽样"""
    return get_db().execute_with_rowcount(
        """
        UPDATE interest_source_subscriptions
        SET enabled = FALSE, updated_at = NOW()
        WHERE user_id = %s
        """,
        (user_id,),
    )


def seed_fetched_items(source_id: str, reset: bool = False) -> int:
    """为 source 插入 fetched items（去重 by url）"""
    if reset:
        get_db().execute(
            "DELETE FROM interest_fetched_items WHERE source_id = %s",
            (source_id,),
        )
    now = datetime.now(timezone.utc)
    added = 0
    for i, it in enumerate(TEST_FETCHED_ITEMS):
        # 错开时间，避免冲突
        pub = now - timedelta(hours=i + 1)
        try:
            get_db().execute(
                """
                INSERT INTO interest_fetched_items
                (id, source_id, title, url, summary, author, published_at, fetched_at)
                SELECT %s, %s, %s, %s, %s, %s, %s, NOW()
                WHERE NOT EXISTS (
                    SELECT 1 FROM interest_fetched_items
                    WHERE source_id = %s AND url = %s
                )
                """,
                (
                    str(uuid.uuid4()),
                    source_id,
                    it["title"],
                    it["url"],
                    it["summary"],
                    it["author"],
                    pub,
                    source_id,
                    it["url"],
                ),
            )
            added += 1
        except Exception as e:
            print(f"  [warn] insert item {i} failed: {e}", file=sys.stderr)
    return added


def seed_push_records(
    user_id: str, source_id: str, reset: bool = False
) -> int:
    """为用户插入少量 push records（让反馈/导入流程能直接命中）"""
    if reset:
        get_db().execute(
            "DELETE FROM interest_push_records WHERE user_id = %s",
            (user_id,),
        )
    now = datetime.now(timezone.utc)
    samples = [
        ("research_object", TEST_FETCHED_ITEMS[0]),
        ("research_method", TEST_FETCHED_ITEMS[1]),
        ("hot_news", TEST_FETCHED_ITEMS[3]),
    ]
    added = 0
    for push_type, it in samples:
        try:
            rec = store.create_push_record(
                user_id=user_id,
                push_type=push_type,
                title=it["title"],
                source_id=source_id,
                summary=it["summary"],
                url=it["url"],
                author=it["author"],
                published_at=now - timedelta(minutes=30),
                matched_tags=[],
            )
            if rec:
                added += 1
        except Exception as e:
            print(f"  [warn] insert push record failed: {e}", file=sys.stderr)
    return added


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reset", action="store_true", help="清理后重写")
    parser.add_argument("--user-id", default=None, help="指定 user_id")
    parser.add_argument(
        "--username", default="e2e_admin", help="按 username 查找 user_id"
    )
    args = parser.parse_args()

    db = get_db()
    if args.user_id:
        user_id = args.user_id
    else:
        row = db.fetchone(
            "SELECT id FROM users WHERE username = %s", (args.username,)
        )
        if not row:
            print(
                json.dumps({"error": f"user {args.username} not found"}),
                file=sys.stderr,
            )
            return 1
        user_id = row["id"]

    print(f"==> Seeding for user_id={user_id} reset={args.reset}", file=sys.stderr)

    if args.reset:
        # 关闭所有订阅
        ensure_user_disabled_other_subs(user_id)
        # 清理已有数据
        get_db().execute(
            "DELETE FROM interest_push_records WHERE user_id = %s",
            (user_id,),
        )
        get_db().execute(
            "DELETE FROM interest_feedback WHERE user_id = %s",
            (user_id,),
        )
        get_db().execute(
            "DELETE FROM interest_weight_adjustments WHERE user_id = %s",
            (user_id,),
        )

    sub = ensure_user_subscribed(user_id)
    print(f"  subscribed: {sub['name']} ({sub['id'][:8]})", file=sys.stderr)

    tags = ensure_user_seed_tags(user_id)
    print(f"  seed_tags: {[t['name'] for t in tags]}", file=sys.stderr)

    fc = seed_fetched_items(sub["id"], reset=args.reset)
    print(f"  fetched_items: {fc}", file=sys.stderr)

    pc = seed_push_records(user_id, sub["id"], reset=False)
    print(f"  push_records: {pc}", file=sys.stderr)

    out = {
        "user_id": user_id,
        "subscribed_source": sub,
        "seed_tags": [t["name"] for t in tags],
        "fetched_count": fc,
        "push_count": pc,
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
