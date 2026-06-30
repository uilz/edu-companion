"""
Phase 6 全链路验证脚本
- 测试1: classify endpoint → MessageClassified → 可见性级联
- 测试2: 创建节点 → NodeCreated → 波纹边检测
- 测试3: 抽取 PendingCrossTopic 事件 → 提案存储
"""
import asyncio
import json
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

async def main():
    from app.infrastructure.db.database import get_db
    from app.infrastructure.db.cognitive_storage import get_node, get_children, list_all_nodes
    from app.infrastructure.db.cognitive_edge_storage import get_edges_for_node, get_edges_by_status
    
    db = get_db()

    # ── Test 1: 检查 cognitive_events 表是否有 MessageClassified 事件 ──
    events = db.fetchall(
        "SELECT event_type, payload, processed FROM cognitive_events "
        "ORDER BY created_at DESC LIMIT 10"
    )
    print("=== 最近事件 ===")
    for evt in events:
        pl = json.dumps(evt["payload"], ensure_ascii=False)[:100]
        print(f"  {evt['event_type']:30s} processed={evt['processed']} {pl}")

    # ── Test 2: 检查是否有知识图谱节点 ──
    nodes = list_all_nodes()
    print(f"\n=== 节点总数: {len(nodes)} ===")
    topics = [n for n in nodes if n.level == "topic"]
    print(f"Topic 节点: {len(topics)}")
    for t in topics[:5]:
        children = get_children(t.id)
        visible = [c for c in children if c.is_visible]
        print(f"  {t.label} ({t.id[:8]}...) → {len(children)} 子节点, {len(visible)} 可见")

    from shared.constants import DEFAULT_USER_ID

    # ── Test 3: 检查是否有 pending_confirm 的边 ──
    pending_edges = get_edges_by_status("pending_confirm", DEFAULT_USER_ID)
    print(f"\n=== pending_confirm 边: {len(pending_edges)} ===")
    for e in pending_edges[:3]:
        print(f"  {e.source_node_id[:8]} → {e.target_node_id[:8]} (strength={e.strength:.2f})")

    # ── Test 4: 检查 proposal_store 中 pending 提案 ──
    from app.infrastructure.db.proposal_store import ProposalStore
    store = ProposalStore()
    proposals = store.get_pending_proposals("")
    print(f"\n=== 待处理提案: {len(proposals)} ===")
    for p in proposals[:5]:
        print(f"  [{p.emoji}] {p.title} (action={p.action_type}, priority={p.priority})")
        print(f"    source={p.insight_source}")

    # ── Test 5: 手动触发 NodeCreated 事件 ──
    print("\n=== 写 NodeCreated 事件 ===")
    from app.services.common.event_service import EventService
    
    # 找一个有 embedding 的节点
    nodes_with_emb = [n for n in nodes if n.embedding][:1]
    if nodes_with_emb:
        node = nodes_with_emb[0]
        evt_id = EventService.emit_node_created(
            user_id="",
            node_id=node.id,
            parent_id=node.parent or "",
            level=node.level or "atom",
            created_by="system",
        )
        print(f"  NodeCreated 事件已写入: {evt_id}")

    # ── Test 6: 手动写 PendingCrossTopic 事件 ──
    print("\n=== 写 PendingCrossTopic 事件 ===")
    evt_id = EventService.emit_event(
        event_type="PendingCrossTopic",
        payload={
            "candidates": [
                {"id": t.id, "label": t.label, "score": 0.85}
                for t in topics[:2]
            ],
            "suppressed_at_depth": 16,
        },
    )
    print(f"  PendingCrossTopic 事件已写入: {evt_id}")

    # ── Test 7: 验证消费者处理 ──
    await asyncio.sleep(7)  # 等待一个消费周期
    events = db.fetchall(
        "SELECT event_type, processed, created_at FROM cognitive_events "
        "ORDER BY created_at DESC LIMIT 5"
    )
    print("\n=== 消费验证 ===")
    for evt in events:
        print(f"  {evt['event_type']:30s} processed={evt['processed']} at={evt['created_at']}")

    print("\n✅ Phase 6 全链路验证完成")

asyncio.run(main())
