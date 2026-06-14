"""
Phase 3.3 — 数据迁移：将旧树节点消息批量写入 messages 表

用法：python scripts/migrate_messages.py

幂等：跳过已存在的 message_id
"""
import json
import logging
import sys
import os

# 允许独立运行
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def migrate():
    from app.infrastructure.db.cognitive_storage import get_db
    from shared.constants import DEFAULT_USER_ID
    from app.services.common.storage import storage

    user_id = DEFAULT_USER_ID
    data = storage.load(user_id)
    db = get_db()

    # 收集已存在的 message_id
    existing = set()
    rows = db.fetchall("SELECT id FROM messages")
    for r in rows:
        existing.add(r["id"])

    migrated = 0
    skipped = 0

    for conv_id, conv in data.conversations.items():
        for nid in conv.path:
            node = data.nodes.get(nid)
            if not node or node.is_deleted:
                continue

            if nid in existing:
                skipped += 1
                continue

            # 序列化 content_blocks
            blocks = node.content_blocks or []
            if blocks and hasattr(blocks[0], "model_dump"):
                blocks_json = json.dumps([b.model_dump(mode="json") for b in blocks])
            elif blocks and hasattr(blocks[0], "dict"):
                blocks_json = json.dumps([b.dict() for b in blocks])
            else:
                blocks_json = json.dumps(blocks)

            content = ""
            for b in blocks:
                if hasattr(b, "text") and b.text:
                    content = b.text
                    break

            db.execute(
                """INSERT INTO messages (id, conversation_id, user_id, role, content, content_blocks, summary, token_count, created_at)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, to_timestamp(%s))
                   ON CONFLICT (id) DO NOTHING""",
                (
                    nid,
                    conv_id,
                    user_id,
                    node.role,
                    content,
                    blocks_json,
                    node.text_summary or "",
                    node.token_count or 0,
                    node.timestamp / 1000 if node.timestamp else None,
                ),
            )
            migrated += 1
            logger.info(f"  [{node.role}] {nid[:20]}... → {content[:40]}")

    logger.info(f"迁移完成: {migrated} 条写入, {skipped} 条跳过")
    return migrated, skipped


if __name__ == "__main__":
    migrated, skipped = migrate()
    print(f"\n✅ 迁移完成: {migrated} 写入, {skipped} 跳过")
