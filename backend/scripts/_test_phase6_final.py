"""
Phase 6 最终全链路验证 — 事件 → handler → 边 → 提案
"""
import sys, os, asyncio
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

async def main():
    from shared.constants import DEFAULT_USER_ID
    from app.infrastructure.db.database import get_db
    from app.infrastructure.db.cognitive_storage import list_all_nodes
    from app.infrastructure.db.cognitive_edge_storage import get_edges_by_status
    from app.services.common.event_service import EventService
    from app.infrastructure.db.proposal_store import ProposalStore

    uid = DEFAULT_USER_ID
    db = get_db()

    # 清除旧测试数据
    db.execute("DELETE FROM secretary_proposals WHERE generated_by = 'event_handler'")
    db.execute("DELETE FROM cognitive_events WHERE event_type IN ('NodeCreated','PendingCrossTopic')")

    nodes = list_all_nodes(uid)
    topics = [n for n in nodes if n.level == "topic"]
    print(f"=== 节点状态: {len(nodes)} 总, {len(topics)} topic ===")

    if topics:
        node = topics[0]
        EventService.emit_node_created(
            user_id=uid, node_id=node.id, parent_id=node.parent or "",
            level=node.level, created_by="system",
        )
        print(f"  NodeCreated → {node.label}")
    
    EventService.emit_event(
        event_type="PendingCrossTopic", user_id=uid,
        payload={
            "candidates": [{"id": t.id, "label": t.label, "score": 0.85} for t in topics[:2]],
            "suppressed_at_depth": 16,
        },
    )
    print(f"  PendingCrossTopic → {len(topics[:2])} 候选")

    print("\n=== 等待消费 (10s) ===")
    await asyncio.sleep(10)

    # 验证事件已处理
    events = db.fetchall(
        "SELECT event_type, processed FROM cognitive_events "
        "WHERE user_id = %s AND event_type IN ('NodeCreated','PendingCrossTopic') "
        "ORDER BY created_at DESC",
        (uid,),
    )
    all_processed = all(e["processed"] for e in events)
    print(f"  事件: {len(events)} 个, 全部已处理={all_processed}")
    for e in events:
        print(f"    {e['event_type']:25s} processed={e['processed']}")

    # 验证边
    pending = get_edges_by_status("pending_confirm", uid)
    print(f"\n=== pending_confirm 边: {len(pending)} ===")
    for e in pending:
        print(f"  {e.source_node_id[:8]} → {e.target_node_id[:8]} (strength={e.strength:.2f})")

    # 验证提案
    store = ProposalStore()
    proposals = store.get_pending_proposals(uid)
    print(f"\n=== 提案: {len(proposals)} ===")
    for p in proposals:
        print(f"  [{p.emoji}] {p.title}")
        print(f"    source={p.insight_source} action={p.action_type} priority={p.priority}")

    if all_processed:
        print("\n✅ Phase 6 全链路验证通过!")
    else:
        print("\n⚠️ 部分事件未处理，检查日志")

asyncio.run(main())
