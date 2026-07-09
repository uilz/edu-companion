"""
Phase 3.4 — 语义记忆检索：为 messages 表所有消息生成 embedding

用法：python scripts/backfill_embeddings.py [--force]
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def backfill(force: bool = False):
    from app.infrastructure.db.database import get_db
    from shared.constants import DEFAULT_USER_ID

    user_id = DEFAULT_USER_ID
    db = get_db()

    # 找需要 embedding 的消息
    if force:
        rows = db.fetchall(
            "SELECT id, content, role FROM messages WHERE user_id = %s AND content != '' ORDER BY created_at",
            (user_id,),
        )
    else:
        rows = db.fetchall(
            "SELECT id, content, role FROM messages WHERE user_id = %s AND embedding IS NULL AND content != '' ORDER BY created_at",
            (user_id,),
        )

    if not rows:
        logger.info("No messages need embedding")
        return 0

    from app.infrastructure.llm.embedding_engine import compute_embedding

    total = len(rows)
    done = 0

    for r in rows:
        text = r["content"]
        if not text or len(text.strip()) < 5:
            db.execute("UPDATE messages SET embedding = '{}' WHERE id = %s", (r["id"],))
            done += 1
            continue

        emb = compute_embedding(text[:2000])
        if emb:
            db.execute(
                "UPDATE messages SET embedding = %s::vector WHERE id = %s",
                (emb, r["id"]),
            )
            done += 1
            if done % 5 == 0:
                logger.info(f"  {done}/{total}")
        else:
            logger.warning(f"  Embedding failed for {r['id'][:20]}...")

    logger.info(f"Embedding 生成完成: {done}/{total}")
    return done


if __name__ == "__main__":
    force = "--force" in sys.argv
    done = backfill(force=force)
    print(f"\n✅ 完成: {done} 条 embedding")
