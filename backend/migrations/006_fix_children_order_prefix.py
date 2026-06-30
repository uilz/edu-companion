"""
#006: 修复 navigation_nodes.children_order ID 前缀不匹配

问题: 从旧版迁移时, children_order 中存储了 dir_xxx ID,
但新版 NavigationService 创建的节点 ID 使用 nav_xxx 前缀,
导致 list_children / build_tree 找不到子节点, 返回空树。

背景: 旧版 DirectoryNode 使用 dir_xxx 格式 ID, 
新版 v5 架构使用 nav_xxx 格式 (由 NavigationService.create_dir 生成)。
数据迁移 (005) 将旧节点导入了 navigation_nodes 表, 节点 ID 改为 nav_xxx,
但 children_order 未同步更新, 仍引用 dir_xxx。
"""
import json
import logging

logger = logging.getLogger(__name__)


def migrate(user_id: str) -> dict:
    """修复单个用户的导航节点 children_order prefix"""
    from app.infrastructure.db.database import get_db

    db = get_db()
    stats = {"fixed": 0, "skipped": 0, "removed_missing": 0}

    rows = db.fetchall(
        "SELECT id, name, children_order FROM navigation_nodes WHERE user_id = %s",
        (user_id,),
    )

    for row in rows:
        raw = row.get("children_order")
        order = json.loads(raw) if isinstance(raw, str) else (raw or [])
        if not order:
            stats["skipped"] += 1
            continue

        new_order: list[str] = []
        changed = False

        for oid in order:
            if oid.startswith("dir_"):
                nav_id = "nav_" + oid[4:]
                exists = db.fetchone(
                    "SELECT id FROM navigation_nodes WHERE id = %s", (nav_id,),
                )
                if exists:
                    new_order.append(nav_id)
                    changed = True
                    logger.debug("  fix %s → %s", oid, nav_id)
                else:
                    # 旧 ID 也不存在 → 移除
                    exists_old = db.fetchone(
                        "SELECT id FROM navigation_nodes WHERE id = %s", (oid,),
                    )
                    if not exists_old:
                        logger.warning("  drop missing child %s", oid)
                        stats["removed_missing"] += 1
                        changed = True
                        continue
                    new_order.append(oid)
            else:
                new_order.append(oid)

        if changed:
            db.execute(
                "UPDATE navigation_nodes SET children_order = %s, updated_at = NOW() WHERE id = %s",
                (json.dumps(new_order), row["id"]),
            )
            stats["fixed"] += 1
        else:
            stats["skipped"] += 1

    return stats


def migrate_all_users() -> dict:
    """修复所有用户的 children_order"""
    from app.infrastructure.db.database import get_db

    db = get_db()
    users = db.fetchall(
        "SELECT DISTINCT user_id FROM navigation_nodes ORDER BY user_id",
    )
    total = {"fixed": 0, "skipped": 0, "removed_missing": 0}
    for u in users:
        uid = u["user_id"]
        s = migrate(uid)
        for k in total:
            total[k] += s[k]
        if s["fixed"] > 0:
            logger.info("user %s: fixed %d", uid, s["fixed"])
    return total


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    result = migrate_all_users()
    print(f"Done: {result}")
