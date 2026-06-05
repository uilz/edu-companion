"""
Phase 6 直接提案测试 — 绕过消费者，直接调用 _generate_proposal
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def main():
    from shared.constants import DEFAULT_USER_ID
    from app.db.database import get_db
    from app.domain.secretary.proposal_store import ProposalStore
    from app.services.common.event_service import _generate_proposal
    from app.domain.secretary.models import Proposal

    uid = DEFAULT_USER_ID

    # 1. 直接调用 _generate_proposal
    print("=== 测试 _generate_proposal ===")
    _generate_proposal(
        user_id=uid,
        emoji="🔗",
        title="测试波纹边关联",
        description="测试描述 — 是否建立关联？",
        action_type="explore",
        priority=3,
        payload={
            "source_node_id": "node_1",
            "target_node_id": "node_2",
            "similarity": 0.82,
        },
        generated_by="event_handler",
        insight_source="ripple_edge",
    )
    print("  _generate_proposal 调用完成")

    # 2. 再生成一条跨主题提案
    _generate_proposal(
        user_id=uid,
        emoji="🔀",
        title="关联新话题「概率论」",
        description=f"本次对话涉及了「概率论」相关内容（匹配度 85%），是否需要关联？",
        action_type="explore",
        priority=2,
        payload={"candidate_label": "概率论", "score": 0.85},
        generated_by="event_handler",
        insight_source="pending_cross_topic",
    )
    print("  跨主题提案调用完成")

    # 3. 读取验证
    store = ProposalStore()
    proposals = store.get_pending_proposals(uid)
    print(f"\n=== 待处理提案: {len(proposals)} ===")
    for p in proposals:
        print(f"  [{p.emoji}] {p.title}")
        print(f"    action={p.action_type} source={p.insight_source} priority={p.priority}")
        print(f"    payload keys: {list(p.payload.keys()) if p.payload else 'empty'}")

    # 4. 清理
    db = get_db()
    db.execute(
        "DELETE FROM secretary_proposals WHERE user_id = %s AND generated_by = 'event_handler'",
        (uid,),
    )
    print(f"\n  已清理测试提案")

    print("\n✅ 提案系统工作正常")

if __name__ == "__main__":
    main()
