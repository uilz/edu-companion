"""
Data Migration: JSONB (UserData) → PG Tables (v5)

将旧的 UserData JSONB 数据迁移到新的四实体 PG 表:
- knowledge_nodes (从 knowledge_graphs + cognitive_nodes)
- navigation_nodes (从 directory_nodes)
- conversations (从 directory_nodes 中的 conv 节点)
- messages (从 nodes)
"""
from __future__ import annotations
import json
import logging
import time
from uuid import uuid4

from app.infrastructure.db.database import get_db
from app.services.common import get_data_repo

logger = logging.getLogger(__name__)


def migrate(user_id: str) -> dict:
    """迁移单个用户的所有数据"""
    result = {
        "knowledge_nodes": 0,
        "navigation_nodes": 0,
        "conversations": 0,
        "messages": 0,
        "errors": [],
    }
    try:
        data = get_data_repo().load(user_id)
        db = get_db()
        conn = db.get_conn()
        cur = conn.cursor()

        # ── 1. 迁移 KnowledgeGraph → knowledge_nodes ──
        try:
            for kg_id, kg in data.knowledge_graphs.items():
                for node_id, kg_node in kg.nodes.items():
                    # 检查是否已存在
                    cur.execute(
                        "SELECT id FROM knowledge_nodes WHERE id = %s AND user_id = %s",
                        (node_id, user_id),
                    )
                    if cur.fetchone():
                        # 更新已有节点
                        cur.execute(
                            """UPDATE knowledge_nodes SET
                               label = %s, tags = %s, created_by = %s, is_visible = true, brief = %s,
                               updated_at = NOW()
                               WHERE id = %s AND user_id = %s""",
                            (kg_node.label, json.dumps(kg_node.tags or []),
                             kg_node.created_by, kg_node.description or "",
                             node_id, user_id),
                        )
                    else:
                        # 插入新节点
                        cur.execute(
                            """INSERT INTO knowledge_nodes (id, user_id, label, level, brief,
                               tags, created_by, is_visible, node_type, path_id, children_order)
                               VALUES (%s, %s, %s, 'topic', %s, %s, %s, true, 'explicit', %s, %s)
                               ON CONFLICT (id) DO NOTHING""",
                            (node_id, user_id, kg_node.label,
                             kg_node.description or "",
                             json.dumps(kg_node.tags or []),
                             kg_node.created_by,
                             f"kg.{kg_node.label}",
                             json.dumps([])),
                        )
                    result["knowledge_nodes"] += 1
        except Exception as e:
            logger.warning("迁移 knowledge_graphs 失败: %s", e)
            result["errors"].append(f"knowledge_graphs: {e}")

        # ── 2. 迁移 DirectoryNode → NavigationNode + Conversation ──
        try:
            for dn_id, dn in data.directory_nodes.items():
                if dn.node_type == "conv":
                    # 创建 Conversation
                    conv_id = f"conv_{dn_id.replace('dir_', '').replace('conv_', '')}"
                    msg_ids = getattr(dn, "conv_message_ids", [])
                    cur.execute(
                        """INSERT INTO conversations (id, user_id, message_ids, summary_short,
                           summary_dirty, created_at, updated_at)
                           VALUES (%s, %s, %s, %s, %s, to_timestamp(%s), to_timestamp(%s))
                           ON CONFLICT (id) DO NOTHING""",
                        (conv_id, user_id, json.dumps(msg_ids),
                         getattr(dn, "summary_short", "") or "",
                         getattr(dn, "summary_dirty", False),
                         getattr(dn, "created_at", time.time()),
                         getattr(dn, "updated_at", time.time())),
                    )
                    result["conversations"] += 1

                    # 创建 NavigationNode (conv ref)
                    nav_id = f"nav_{dn_id.replace('dir_', '')}"
                    cur.execute(
                        """INSERT INTO navigation_nodes (id, user_id, parent_id, node_type, kind,
                           name, user_name, ai_name, conv_id, path, children_order,
                           created_at, updated_at)
                           VALUES (%s, %s, %s, 'conv', %s, %s, %s, %s, %s, %s, %s,
                                   to_timestamp(%s), to_timestamp(%s))
                           ON CONFLICT (id) DO NOTHING""",
                        (nav_id, user_id, dn.parent_id, getattr(dn, "kind", "general"),
                         getattr(dn, "name", "新对话"),
                         getattr(dn, "user_name", None),
                         getattr(dn, "ai_name", ""),
                         conv_id,
                         json.dumps(getattr(dn, "path", [])),
                         json.dumps(getattr(dn, "children_order", [])),
                         getattr(dn, "created_at", time.time()),
                         getattr(dn, "updated_at", time.time())),
                    )
                    result["navigation_nodes"] += 1
                else:
                    # dir 节点 → NavigationNode
                    nav_id = f"nav_{dn_id.replace('dir_', '')}"
                    cur.execute(
                        """INSERT INTO navigation_nodes (id, user_id, parent_id, node_type, kind,
                           name, user_name, ai_name, children_order, path,
                           created_at, updated_at)
                           VALUES (%s, %s, %s, 'dir', %s, %s, %s, %s, %s, %s,
                                   to_timestamp(%s), to_timestamp(%s))
                           ON CONFLICT (id) DO NOTHING""",
                        (nav_id, user_id, dn.parent_id, getattr(dn, "kind", "general"),
                         getattr(dn, "name", "新节点"),
                         getattr(dn, "user_name", None),
                         getattr(dn, "ai_name", ""),
                         json.dumps(getattr(dn, "children_order", [])),
                         json.dumps(getattr(dn, "path", [])),
                         getattr(dn, "created_at", time.time()),
                         getattr(dn, "updated_at", time.time())),
                    )
                    result["navigation_nodes"] += 1
        except Exception as e:
            logger.warning("迁移 directory_nodes 失败: %s", e)
            result["errors"].append(f"directory_nodes: {e}")

        # ── 3. 迁移 TreeNode (MessageNode) → Message ──
        try:
            for node_id, node in data.nodes.items():
                msg_id = node_id.replace("tree_", "msg_")
                # 获取 conv_id - 优先 directory_id，其次 conv_id，最后 dir_id
                conv_id = (getattr(node, "directory_id", "") or
                          getattr(node, "conv_id", "") or
                          getattr(node, "dir_id", ""))
                cur.execute(
                    """INSERT INTO messages (id, user_id, conv_id, role, content,
                       content_blocks, text_summary, parent_id, children_ids,
                       has_sub_branches, sub_branch_ids, sub_branch_summaries,
                       version, is_deleted, timestamp, token_count, agent_label)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                               to_timestamp(%s), %s, %s)
                       ON CONFLICT (id) DO NOTHING""",
                    (msg_id, user_id,
                     conv_id,
                     getattr(node, "role", "user"),
                     getattr(node, "content", "") or "",
                     json.dumps(getattr(node, "content_blocks", []) or []),
                     getattr(node, "text_summary", "") or "",
                     getattr(node, "parent_id", None),
                     json.dumps(getattr(node, "children_ids", []) or []),
                     getattr(node, "has_sub_branches", False),
                     json.dumps(getattr(node, "sub_branch_ids", []) or []),
                     json.dumps(getattr(node, "sub_branch_summaries", []) or []),
                     getattr(node, "version", 1),
                     getattr(node, "is_deleted", False),
                     getattr(node, "timestamp", time.time()),
                     getattr(node, "token_count", 0),
                     getattr(node, "agent_label", "") or ""),
                )
                result["messages"] += 1
        except Exception as e:
            logger.warning("迁移 messages 失败: %s", e)
            result["errors"].append(f"messages: {e}")

        conn.commit()
        cur.close()
        db.put_conn(conn)
        logger.info("迁移完成: user=%s result=%s", user_id, result)
    except Exception as e:
        logger.exception("迁移用户 %s 失败", user_id)
        result["errors"].append(str(e))
    return result


def migrate_all_users() -> dict:
    """迁移所有用户"""
    # 获取所有用户 ID — 从 conversation_user_meta 表中获取
    from app.infrastructure.db.database import get_db
    db = get_db()
    rows = db.fetchall("SELECT user_id FROM conversation_user_meta")
    user_ids = [row["user_id"] for row in rows if row["user_id"]]
    logger.info("找到 %d 个用户需要迁移", len(user_ids))

    all_results = {}
    for user_id in user_ids:
        all_results[user_id] = migrate(user_id)
    return all_results


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    if len(sys.argv) > 1:
        user_id = sys.argv[1]
        result = migrate(user_id)
    else:
        result = migrate_all_users()
    print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
