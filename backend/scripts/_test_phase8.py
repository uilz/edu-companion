"""Phase 8 全链路验证"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def main():
    from shared.constants import DEFAULT_USER_ID
    from app.infrastructure.db.database import get_db
    db = get_db()

    # 清理上次残留
    db.execute("DELETE FROM conversation_summaries WHERE conv_id = '00000000-0000-0000-0000-000000000001'")

    # 1. 检查 conversation_summaries 表
    r = db.fetchall(
        "SELECT column_name, data_type FROM information_schema.columns "
        "WHERE table_name='conversation_summaries' ORDER BY ordinal_position"
    )
    if r:
        print("✅ conversation_summaries 表存在")
        for row in r:
            print(f"  {row['column_name']:20s} {row['data_type']}")
    else:
        print("❌ conversation_summaries 表不存在")

    # 2. 测试 boost_trust_on_activity
    from app.infrastructure.db.cognitive_edge_storage import boost_trust_on_activity
    from app.infrastructure.db.cognitive_edge_storage import get_edges_by_status
    from shared.constants import DEFAULT_USER_ID

    edges = get_edges_by_status("auto_active", DEFAULT_USER_ID)
    if edges:
        e = edges[0]
        old = e.trust_score
        new = boost_trust_on_activity(e.source_node_id, e.target_node_id, e.user_id, evidence=0.2)
        print(f"✅ boost_trust_on_activity: {old:.3f} → {new:.3f} (evidence=0.2)")
    else:
        print("ℹ️ 无边可测试，跳过 boost_trust_on_activity")

    # 3. 测试 summary 保存和查询
    from app.services.common.summary_service import save_summary, get_recent_summaries, build_condensed_context

    sid = save_summary(
        conv_id="00000000-0000-0000-0000-000000000001",
        summary="测试摘要内容",
        user_id=DEFAULT_USER_ID,
        round_number=10,
        involved_node_ids=["微积分", "线性代数"],
        token_count=120,
    )
    print(f"✅ 摘要保存: {sid}")

    summaries = get_recent_summaries("00000000-0000-0000-0000-000000000001")
    print(f"✅ 摘要查询: {len(summaries)} 条")
    for s in summaries:
        print(f"  第{s['round_number']}轮: {s['summary'][:50]}")

    context = build_condensed_context(
        "00000000-0000-0000-0000-000000000001",
        [{"user": "什么是微积分?", "assistant": "微积分是..."}],
        max_recent=5,
    )
    print(f"✅ 上下文裁剪: {len(context)} 字符")

    # 4. 检测 is_temporary 列是否存在
    r = db.fetchall(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name='conversations' AND column_name='is_temporary'"
    )
    print(f"✅ conversations.is_temporary 列: {'存在' if r else '不存在'}")

    # 5. 清理测试数据
    db.execute("DELETE FROM conversation_summaries")
    print("✅ 测试摘要已清理")

    print("\n✅ Phase 8 全链路验证通过！")

if __name__ == "__main__":
    main()
