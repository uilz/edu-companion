"""Phase 8 数据迁移：旧 partition/branch → CognitiveNode

将 conversation_partitions 映射为 partition 级节点，
conversation_branches 映射为 topic 级节点，
并创建默认 domain → topic → concept 骨架。
"""

import logging
import uuid
import sys
import os
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))
os.environ.setdefault("APP_DEBUG", "true")

from app.db.database import get_db
from app.cognitive.models import CognitiveNode
from app.cognitive.storage import upsert_node

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("migrate_old_data")


def migrate():
    db = get_db()

    # 1. 读取旧分区数据
    partitions = db.fetchall(
        "SELECT id, name, created_at FROM conversation_partitions"
    )
    branches = db.fetchall(
        "SELECT id, name, partition_id, created_at FROM conversation_branches"
    )

    user_id = "o9cq800rjtrGooSMfmHEQ6uTW6wE@im.wechat"
    created_nodes = 0

    for p in partitions:
        pid = p["id"]
        pname = p.get("name", "默认分区")
        pkey = f"partition.{pid}"

        # 检查是否已存在
        existing = db.fetchone(
            "SELECT id FROM cognitive_nodes WHERE path_id = %s AND user_id = %s",
            (pkey, user_id),
        )
        if existing:
            logger.info(f"  partition '{pname}' already exists as {existing['id']}")
            continue

        node = CognitiveNode(
            id=str(uuid.uuid4()),
            label=pname,
            level="partition",
            parent=None,
            path_id=pkey,
            node_type="explicit",
            is_visible=True,
        )
        upsert_node(node, user_id)
        logger.info(f"  created partition node: {node.label} ({pkey})")
        created_nodes += 1

        # 为此分区下每个 branch 创建 topic 级节点
        partition_branches = [b for b in branches if b["partition_id"] == pid]
        if partition_branches:
            # 创建默认 domain
            domain_key = f"{pkey}.default"
            did = str(uuid.uuid4())
            dnode = CognitiveNode(
                id=did,
                label="默认领域",
                level="domain",
                parent=node.id,
                path_id=domain_key,
                node_type="auto_generated",
                is_visible=True,
            )
            upsert_node(dnode, user_id)
            # 更新 partition 的 children
            partition_node = db.fetchone(
                "SELECT children FROM cognitive_nodes WHERE id = %s", (node.id,)
            )
            children = partition_node.get("children", []) if partition_node else []
            if isinstance(children, str):
                pass  # json already imported at top
                children = json.loads(children)
            if did not in children:
                from datetime import datetime, timezone
                new_children = children + [did]
                db.execute(
                    "UPDATE cognitive_nodes SET children = %s, updated_at = %s WHERE id = %s",
                    (json.dumps(new_children), datetime.now(timezone.utc).isoformat(), node.id),
                )
            logger.info(f"    created domain node: {dnode.label} ({domain_key})")
            created_nodes += 1

            for b in partition_branches:
                tkey = f"{domain_key}.{b['id']}"
                existing_topic = db.fetchone(
                    "SELECT id FROM cognitive_nodes WHERE path_id = %s AND user_id = %s",
                    (tkey, user_id),
                )
                if existing_topic:
                    continue

                tname = b.get("name", "未命名")
                t_node = CognitiveNode(
                    id=str(uuid.uuid4()),
                    label=f"{tname}",
                    level="topic",
                    parent=did,
                    path_id=tkey,
                    node_type="explicit",
                    is_visible=True,
                )
                upsert_node(t_node, user_id)
                logger.info(f"      created topic node: {t_node.label} ({tkey})")
                created_nodes += 1

    logger.info(f"=== 迁移完成，共创建 {created_nodes} 个节点 ===")
    return created_nodes


if __name__ == "__main__":
    migrate()
