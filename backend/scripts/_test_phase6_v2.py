"""
Phase 6 全链路验证脚本 v2 — 使用 DEFAULT_USER_ID
"""
import asyncio
import json
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

async def main():
    from shared.constants import DEFAULT_USER_ID
    from app.db.database import get_db
    from app.cognitive.storage import get_node, get_children, list_all_nodes
    from app.cognitive.edge_storage import get_edges_for_node, get_edges_by_status
    from app.services.common.event_service import EventService

    db = get_db()
    uid = DEFAULT_USER_ID  # 注意：DEFAULT_USER_ID 仅作签名兼容，新代码不再依赖

    nodes = list_all_nodes(uid)
    topics = [n for n in nodes if n.level == "topic"]

    # ── 1. 写 NodeCreated 事件（用正确 user_id）──
    print("=== 写 NodeCreated 事件 ===")
    if topics:
        node = topics[0]
        evt_id = EventService.emit_node_created(
            user_id=uid,
            node_id=node.id,
            parent_id=node.parent or "",
            level=node.level or "atom",
            created_by="system",
        )
        print(f"  NodeCreated: {evt_id} (user={uid})")

    # ── 2. 写 PendingCrossTopic 事件 ──
    print("\n=== 写 PendingCrossTopic 事件 ===")
    evt_id = EventService.emit_v6_event(
        event_type="PendingCrossTopic",
        user_id=uid,
        payload={
            "candidates": [
                {"id": t.id, "label": t.label, "score": 0.85}
                for t in topics[:2]
            ],
            "suppressed_at_depth": 16,
        },
    )
    print(f"  PendingCrossTopic: {evt_id} (user={uid})")

    # ── 3. 等待消费 ──
    print("\n=== 等待消费 (10s) ===")
    await asyncio.sleep(10)

    # ── 4. 验证消费结果 ──
    events = db.fetchall(
        "SELECT event_type, processed FROM cognitive_events "
        "WHERE user_id = %s ORDER BY created_at DESC LIMIT 3",
        (uid,),
    )
    print("\n=== 消费验证 ===")
    for e in events:
        print(f"  {e['event_type']:30s} processed={e['processed']}")

    # ── 5. 检查提案 ──
    from app.domain.secretary.proposal_store import ProposalStore
    store = ProposalStore()
    proposals = store.get_pending_proposals(uid)
    print(f"\n=== 待处理提案: {len(proposals)} ===")
    for p in proposals[:5]:
        print(f"  [{p.emoji}] {p.title}")
        print(f"    action={p.action_type} source={p.insight_source}")

    # ── 6. 检查 pending_confirm 边 ──
    pending = get_edges_by_status("pending_confirm", uid)
    print(f"\n=== pending_confirm 边: {len(pending)} ===")
    for e in pending[:3]:
        print(f"  {e.source_node_id[:8]} → {e.target_node_id[:8]} ({e.strength:.2f})")

    print("\n✅ 验证完成")

asyncio.run(main())
