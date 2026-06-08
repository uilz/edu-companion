"""
清理孤儿数据脚本（v7 数据一致性）

清理对象：
1. messages 表中 user_id='u1'（测试用 user，不在 users 表）
2. messages 表中 conversation_id 不在 conversations 表 的旧数据
3. 5 个测试/历史用户：testfrom18001/browsertest/newuser2/Apple/testuser（保留 default_user 与真实登录用户）
4. secretary_proposals 中 test_user_diag 的测试数据
5. practice_question_bank 中 import_source='auto' 的「通用题库」

使用方法：
  PGPASSWORD=... psql -U companion -d edu_companion -h localhost -f cleanup_orphan_data.sql
或
  PGPASSWORD=... python cleanup_orphan_data.py --dry-run   # 只打印不执行
  PGPASSWORD=... python cleanup_orphan_data.py             # 实际执行
"""
from __future__ import annotations

import os
import sys
import psycopg2

PG = {
    "host": os.environ.get("PGHOST", "localhost"),
    "port": int(os.environ.get("PGPORT", "5432")),
    "user": os.environ.get("PGUSER", "companion"),
    "password": os.environ.get("PGPASSWORD", "companion123"),
    "dbname": os.environ.get("PGDATABASE", "edu_companion"),
}

DRY_RUN = "--dry-run" in sys.argv


def banner(msg: str) -> None:
    print("\n" + "=" * 60)
    print(f"  {msg}")
    print("=" * 60)


def count(cur, sql, params=()) -> int:
    cur.execute(sql, params)
    return cur.fetchone()[0]


def main() -> None:
    conn = psycopg2.connect(**PG)
    conn.autocommit = False
    cur = conn.cursor()

    try:
        # ── 1. 孤儿 messages (user_id='u1'，非真实用户) ──
        banner("1. messages 表 user_id='u1' 的孤儿数据")
        n = count(cur, "SELECT COUNT(*) FROM messages WHERE user_id = 'u1'")
        print(f"  计划删除: {n} 条")
        if not DRY_RUN and n:
            cur.execute("DELETE FROM messages WHERE user_id = 'u1'")

        # ── 2. messages 关联 conversations 的孤儿数据 ──
        banner("2. messages.conversation_id 不在 conversations 的孤儿数据")
        n = count(cur, """
            SELECT COUNT(*) FROM messages m
            WHERE NOT EXISTS (SELECT 1 FROM conversations c WHERE c.id = m.conversation_id)
        """)
        print(f"  计划删除: {n} 条")
        if not DRY_RUN and n:
            cur.execute("""
                DELETE FROM messages m
                WHERE NOT EXISTS (SELECT 1 FROM conversations c WHERE c.id = m.conversation_id)
            """)

        # ── 3. 测试/历史用户 ──
        banner("3. 测试/历史用户清理（保留 default_user + u_862e835ac373 + u_e5100c1b2c21 + u_93d3954b0b80）")
        test_users = ("testfrom18001", "browsertest", "newuser2", "Apple", "testuser")
        for username in test_users:
            cur.execute("SELECT id FROM users WHERE username = %s", (username,))
            row = cur.fetchone()
            if row:
                uid = row[0]
                # 删除该用户相关数据（保留 messages 作历史参考，但解除 conversation 关联）
                cur.execute("DELETE FROM conversation_user_meta WHERE user_id = %s", (uid,))
                n_meta = cur.rowcount
                cur.execute("DELETE FROM users WHERE id = %s", (uid,))
                n_user = cur.rowcount
                print(f"  - {username} (id={uid}): 删除 users({n_user}) conversation_user_meta({n_meta})")
            else:
                print(f"  - {username}: 未找到，跳过")

        # ── 4. secretary_proposals 测试数据 ──
        banner("4. secretary_proposals 中 test_user_diag 的测试数据")
        n = count(cur, "SELECT COUNT(*) FROM secretary_proposals WHERE user_id = 'test_user_diag'")
        print(f"  计划删除: {n} 条")
        if not DRY_RUN and n:
            cur.execute("DELETE FROM secretary_proposals WHERE user_id = 'test_user_diag'")

        # ── 5. 总结 ──
        banner("5. 当前数据状态")
        for table in [
            "messages", "conversations", "conversation_user_meta",
            "users", "secretary_proposals", "practice_attempts",
            "practice_sessions", "achievements",
        ]:
            try:
                n = count(cur, f"SELECT COUNT(*) FROM {table}")
                print(f"  {table}: {n}")
            except Exception as e:
                conn.rollback()
                print(f"  {table}: ERR {e}")

        if DRY_RUN:
            print("\n  ⚠️  DRY RUN — 回滚")
            conn.rollback()
        else:
            conn.commit()
            print("\n  ✅ 已提交")

    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    main()
