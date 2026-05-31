"""检查 knowledge_edges 和 cognitive_events 表结构"""
import asyncio
async def main():
    from app.db.database import get_db
    db = get_db()
    
    for table in ('knowledge_edges', 'cognitive_events', 'messages'):
        r = db.fetchall(
            "SELECT column_name, data_type, is_nullable FROM information_schema.columns "
            "WHERE table_name=%s ORDER BY ordinal_position",
            (table,)
        )
        print(f"\n=== {table} ===")
        for row in r:
            print(f"  {row['column_name']:25s} {row['data_type']:15s} nullable={row['is_nullable']}")
    
    # Check secretary_proposals
    r = db.fetchall(
        "SELECT column_name, data_type FROM information_schema.columns "
        "WHERE table_name='secretary_proposals' ORDER BY ordinal_position"
    )
    print(f"\n=== secretary_proposals ===")
    for row in r:
        print(f"  {row['column_name']:25s} {row['data_type']}")

    # Check vector_search function signature
    from app.cognitive.storage import vector_search
    import inspect
    print(f"\n=== vector_search signature ===")
    print(inspect.signature(vector_search))

asyncio.run(main())
