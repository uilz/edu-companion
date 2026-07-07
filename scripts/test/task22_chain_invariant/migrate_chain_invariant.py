"""
迁移脚本：修复违反链路不变量的对话。

链路不变量：conv_message_ids 链上，每个 user 消息的 parent_id 必须指向一个
            assistant 消息（除首条 user 消息可 parent_id=None）。

历史 bug：InitStage 因 tree_ops 导入错误崩溃，assistant shell 缺失；前端把
        user 消息当 parent 发送给 add_message，add_message 未校验角色直接
        接受 → 多条 user 串成 user→user→user... 链。

修复策略：在 user→user 断裂处插入"assistant 无回复"占位消息，把后续 user
         消息的 parent 接到这个新占位上，恢复线性链。

用法：
    cd /home/deploy/edu-companion/backend
    venv/bin/python ../scripts/test/task22_chain_invariant/migrate_chain_invariant.py [--user USER_ID] [--dry-run]
"""
from __future__ import annotations

import argparse
import sys
import time
from uuid import uuid4

# 把 backend 路径加入 sys.path
sys.path.insert(0, "/home/deploy/edu-companion/backend")

from app.services.common import get_data_repo
from app.schemas.directory_node import MessageNode


def _make_no_reply_assistant(conv_id: str, user_msg_id: str) -> MessageNode:
    """创建一条 assistant "无回复"占位消息，parent = 给定的 user 消息"""
    return MessageNode(
        directory_id=conv_id,
        parent_id=user_msg_id,
        role="assistant",
        content="",
        text_summary="(no-reply placeholder · 链路修复)",
        content_blocks=[],
        agent_label="tutor",
        status="done",
        stream_started_at=None,
        is_deleted=False,
        is_archived=False,
    )


def fix_one_conv(user_id: str, conv_id: str, dry_run: bool) -> dict:
    """修复一个 conv 的链路。返回修复统计。

    修复策略：对每条 user 消息，如果它的 parent 是另一条 user 消息（user→user
    违反不变量），则在它前面插入一条 assistant "no-reply" 占位。
    占位的 parent = 链上前一条 user 消息；该 user 消息的 parent 改为新占位。

    例（修复前）：user_A → user_B (parent=user_A) → user_C (parent=user_A)
    修复后：user_A → placeholder_1 (parent=user_A) → user_B (parent=placeholder_1)
            → placeholder_2 (parent=user_B) → user_C (parent=placeholder_2)
    """
    data = get_data_repo().load(user_id)
    conv = data.directory_nodes.get(conv_id)
    if not conv or conv.node_type != "conv":
        return {"conv": conv_id, "skipped": "not found or not conv"}

    stats = {"conv": conv_id, "inserted": 0, "scanned": 0, "actions": []}

    # 第一步：扫描，收集所有需要插入占位的 (insert_before_user_id, prev_user_id) 元组
    conv_msgs = list(conv.conv_message_ids)
    print(f"  [{conv_id[:12]}] 扫描 {len(conv_msgs)} 条消息", flush=True)

    plan = []  # (insert_before_user_id, prev_user_id_in_chain)
    last_user_id = ""  # 链上最后遇到的 user 消息 id
    for i, mid in enumerate(conv_msgs):
        node = data.nodes.get(mid)
        if not node or node.is_deleted:
            continue
        if node.role != "user":
            continue
        stats["scanned"] += 1
        if not node.parent_id:
            # 根 user 消息：parent_id=None 是合法的（无前置消息）
            last_user_id = mid
            continue
        parent = data.nodes.get(node.parent_id)
        if parent and parent.role == "assistant":
            # 合规
            last_user_id = mid
            continue
        # 违规：parent 是 user（且非根）
        prev_user_id = last_user_id or ""
        plan.append((mid, prev_user_id))

    print(f"  [{conv_id[:12]}] 发现 {len(plan)} 处 user→user 违规", flush=True)

    if not plan:
        return stats

    # 第二步：插入占位并修改 parent
    # 按 user 在链中位置倒序处理（避免插入时索引错位）
    plan_by_pos = []
    for user_mid, prev_user_mid in plan:
        # 找到 user_mid 在当前 conv.conv_message_ids 中的位置
        try:
            pos = conv.conv_message_ids.index(user_mid)
        except ValueError:
            continue
        plan_by_pos.append((pos, user_mid, prev_user_mid))
    plan_by_pos.sort(key=lambda x: x[0], reverse=True)

    for pos, user_mid, prev_user_mid in plan_by_pos:
        # 占位的 parent：链上前一条 user 消息（prev_user_mid）
        # 若 prev_user_mid 为空（首条 user 就违规），用 conv 的根目录
        parent_for_placeholder = prev_user_mid or ""
        placeholder = MessageNode(
            directory_id=conv_id,
            parent_id=parent_for_placeholder,
            role="assistant",
            content="",
            text_summary="(no-reply placeholder · 链路修复)",
            content_blocks=[],
            agent_label="tutor",
            status="done",
            stream_started_at=None,
            is_deleted=False,
            is_archived=False,
        )
        # 在 user_mid 之前插入占位
        conv.conv_message_ids.insert(pos, placeholder.id)
        data.nodes[placeholder.id] = placeholder
        # 修改 user_mid 的 parent 指向新占位
        user_node = data.nodes.get(user_mid)
        old_parent = user_node.parent_id
        user_node.parent_id = placeholder.id
        stats["inserted"] += 1
        stats["actions"].append(
            f"insert placeholder {placeholder.id[:12]} before user {user_mid[:12]} (prev_user={parent_for_placeholder[:12] if parent_for_placeholder else 'None'}, old_parent={old_parent[:12] if old_parent else 'None'})"
        )

    if not dry_run:
        conv.updated_at = time.time()
        get_data_repo().save(user_id, data)

    return stats


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--user", default="u_f65eb04e5c6b", help="用户 ID")
    parser.add_argument("--dry-run", action="store_true", help="只扫描，不保存")
    parser.add_argument("--conv", default="", help="只处理指定 conv（默认全部 conv）")
    args = parser.parse_args()

    data = get_data_repo().load(args.user)
    targets = []
    if args.conv:
        targets = [args.conv]
    else:
        targets = [dn.id for dn in data.directory_nodes.values() if dn.node_type == "conv"]

    print(f"扫描用户 {args.user}，共 {len(targets)} 个 conv\n")
    total_inserted = 0
    total_reparented = 0
    for cid in targets:        stats = fix_one_conv(args.user, cid, dry_run=args.dry_run)
        if "skipped" in stats:
            print(f"  {cid[:16]}... SKIP: {stats['skipped']}")
            continue
        if stats["inserted"]:
            print(f"  {cid[:16]}... inserted={stats['inserted']}, scanned={stats['scanned']}")
            for a in stats["actions"][:10]:
                print(f"      - {a}")
            if len(stats["actions"]) > 10:
                print(f"      ... ({len(stats['actions'])-10} more)")
            total_inserted += stats["inserted"]

    print(f"\n总计: inserted={total_inserted}, reparented={total_reparented}, dry_run={args.dry_run}")


if __name__ == "__main__":
    main()
