"""
临时对话清理脚本

每 48 小时清理一次：将超过 48 小时、无永久链接标记的临时对话软归档。
对数据库无破坏性操作（仅设置 is_archived = true）。
"""

from __future__ import annotations

import logging
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# ── 路径引导 ──
# 允许从任意位置直接执行 python3 scripts/cleanup_temp_convs.py
_HERE = Path(__file__).resolve().parent
_BACKEND = _HERE.parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from app.infrastructure.db.database import get_db

logger = logging.getLogger("cleanup_temp_convs")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S%z",
)

# ─────────────────────────────────────────────
# 常量
# ─────────────────────────────────────────────
TEMP_TTL_SECONDS = 48 * 3600  # 48 小时
BATCH_SIZE = 100  # 每批处理数（防止大事务锁表）


def ensure_columns(db) -> None:
    """幂等方式添加 is_temporary 等缺失列。"""
    conn = db.get_conn()
    try:
        cur = conn.cursor()
        # is_temporary (Conversation 模型 Phase 8 字段)
        cur.execute("""
            ALTER TABLE conversation_branches
            ADD COLUMN IF NOT EXISTS is_temporary BOOLEAN DEFAULT false
        """)
        # 索引加速查询
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_branches_temp_archived
            ON conversation_branches (is_temporary, is_archived, created_at)
        """)
        conn.commit()
        logger.info("表结构确认完毕")
    except Exception as e:
        conn.rollback()
        logger.error("迁移失败: %s", e)
        raise
    finally:
        cur.close()
        db.put_conn(conn)


def count_expired_temp_convs(db) -> int:
    """统计当前符合条件的待清理对话数。"""
    cutoff = time.time() - TEMP_TTL_SECONDS
    row = db.fetchone(
        """
        SELECT COUNT(*) AS cnt
        FROM conversation_branches b
        WHERE b.is_temporary = true
          AND b.is_archived = false
          AND b.created_at < %s
          AND NOT EXISTS (
              SELECT 1
              FROM conversation_link_nodes ln
              WHERE ln.target_branch_id = b.id
                 OR ln.source_branch_id = b.id
          )
        """,
        (cutoff,),
    )
    return row["cnt"] if row else 0


def archive_expired_temp_convs(db, dry_run: bool = False) -> dict:
    """
    执行归档操作。

    返回摘要:
        - total_candidates: 符合条件总数
        - archived: 实际归档数
        - dry_run: 是否是预演模式
    """
    cutoff = time.time() - TEMP_TTL_SECONDS

    # 1. 先数总数
    total = count_expired_temp_convs(db)
    logger.info("找到 %d 个待归档的临时对话", total)

    if total == 0:
        return {
            "total_candidates": 0,
            "archived": 0,
            "dry_run": dry_run,
        }

    if dry_run:
        logger.info("[DRY RUN] 跳过实际归档")
        return {
            "total_candidates": total,
            "archived": 0,
            "dry_run": True,
        }

    # 2. 分批归档
    archived_count = 0
    conn = db.get_conn()
    try:
        cur = conn.cursor()
        while True:
            cur.execute(
                """
                SELECT b.id, b.name
                FROM conversation_branches b
                WHERE b.is_temporary = true
                  AND b.is_archived = false
                  AND b.created_at < %s
                  AND NOT EXISTS (
                      SELECT 1
                      FROM conversation_link_nodes ln
                      WHERE ln.target_branch_id = b.id
                         OR ln.source_branch_id = b.id
                  )
                LIMIT %s
                FOR UPDATE SKIP LOCKED
                """,
                (cutoff, BATCH_SIZE),
            )
            rows = cur.fetchall()
            if not rows:
                break

            ids = [r[0] for r in rows]
            cur.execute(
                """
                UPDATE conversation_branches
                SET is_archived = true
                WHERE id = ANY(%s)
                """,
                (ids,),
            )
            conn.commit()
            archived_count += len(ids)
            logger.info(
                "已归档 %d 个对话（累计 %d）：%s",
                len(ids),
                archived_count,
                [r[1] or r[0][:8] for r in rows],
            )
    except Exception as e:
        conn.rollback()
        logger.error("归档过程中出错: %s", e)
        raise
    finally:
        cur.close()
        db.put_conn(conn)

    logger.info("归档完成: %d / %d", archived_count, total)
    return {
        "total_candidates": total,
        "archived": archived_count,
        "dry_run": False,
    }


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="清理 48h 以上无永久链接的临时对话（软归档）",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="预演模式，仅统计不执行归档",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="输出详细日志（DEBUG 级别）",
    )
    args = parser.parse_args()

    if args.verbose:
        logging.getLogger("cleanup_temp_convs").setLevel(logging.DEBUG)

    start = time.time()
    logger.info(
        "开始清理临时对话（dry_run=%s）",
        args.dry_run,
    )

    db = get_db()
    ensure_columns(db)
    result = archive_expired_temp_convs(db, dry_run=args.dry_run)

    elapsed = time.time() - start
    logger.info(
        "清理摘要: candidates=%d, archived=%d, dry_run=%s, elapsed=%.2fs",
        result["total_candidates"],
        result["archived"],
        result["dry_run"],
        elapsed,
    )

    # 以 JSON 形式输出供 cron 日志采集
    import json

    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["archived"] >= 0 else 1


if __name__ == "__main__":
    sys.exit(main())
