"""
Phase 1 Migration: user_meta JSONB → cognitive_nodes

Reads domains/topics from conversation_user_meta JSONB,
updates corresponding cognitive_nodes with emoji/color/sort_order.
Backs up JSONB data before cleanup.
"""
import psycopg2
import json
from datetime import datetime

DB_CONFIG = dict(dbname='edu_companion', user='companion', password='companion123', host='localhost')


def migrate():
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()

    # 1. Read all user_meta
    cur.execute("SELECT user_id, domains, topics FROM conversation_user_meta")
    rows = cur.fetchall()

    total_dom = 0
    total_top = 0

    for user_id, domains, topics in rows:
        domains = domains or {}
        topics = topics or {}

        # 2. Migrate domains → cognitive_nodes
        for dom_id, dom_data in domains.items():
            emoji = dom_data.get("emoji", "")
            name = dom_data.get("name", "")
            dir_id = dom_data.get("dir_id", "")

            cur.execute("""
                UPDATE cognitive_nodes
                SET emoji = %s, updated_at = NOW()
                WHERE id = %s AND user_id = %s
            """, (emoji, dom_id, user_id))
            if cur.rowcount == 0:
                # Create if not exists
                cur.execute("""
                    INSERT INTO cognitive_nodes (id, user_id, label, level, parent, emoji, node_type, is_visible, is_active)
                    VALUES (%s, %s, %s, 'domain', %s, %s, 'explicit', true, true)
                    ON CONFLICT (id) DO UPDATE SET emoji = %s
                """, (dom_id, user_id, name, dir_id, emoji, emoji))
            total_dom += 1
            print(f"  Domain: {dom_id} emoji={emoji} name={name}")

        # 3. Migrate topics → cognitive_nodes
        for top_id, top_data in topics.items():
            emoji = top_data.get("emoji", "")
            name = top_data.get("name", "")
            domain_id = top_data.get("domain_id", "")

            cur.execute("""
                UPDATE cognitive_nodes
                SET emoji = %s, updated_at = NOW()
                WHERE id = %s AND user_id = %s
            """, (emoji, top_id, user_id))
            if cur.rowcount == 0:
                cur.execute("""
                    INSERT INTO cognitive_nodes (id, user_id, label, level, parent, emoji, node_type, is_visible, is_active)
                    VALUES (%s, %s, %s, 'topic', %s, %s, 'explicit', true, true)
                    ON CONFLICT (id) DO UPDATE SET emoji = %s
                """, (top_id, user_id, name, domain_id, emoji, emoji))
            total_top += 1
            print(f"  Topic: {top_id} emoji={emoji} name={name}")

        # 4. Migrate partition emoji (from label prefix)
        cur.execute("""
            SELECT id, label, emoji FROM cognitive_nodes
            WHERE level = 'partition' AND user_id = %s
        """, (user_id,))
        for part_id, label, existing_emoji in cur.fetchall():
            if not existing_emoji and label:
                # Extract emoji from label (first char if it's an emoji)
                emoji = ""
                for ch in label:
                    if ord(ch) > 0x1F000:  # rough emoji detection
                        emoji = ch
                        break
                if emoji:
                    cur.execute("""
                        UPDATE cognitive_nodes SET emoji = %s WHERE id = %s
                    """, (emoji, part_id))
                    print(f"  Partition: {part_id} emoji={emoji}")

    conn.commit()

    # 5. Backup JSONB data (add backup columns)
    for col in ['domains', 'topics']:
        try:
            cur.execute(f"""
                ALTER TABLE conversation_user_meta
                ADD COLUMN IF NOT EXISTS {col}_backup JSONB
            """)
            cur.execute(f"""
                UPDATE conversation_user_meta
                SET {col}_backup = {col}
            """)
        except Exception as e:
            print(f"  Backup {col}: {e}")

    conn.commit()
    cur.close()
    conn.close()

    print(f"\nMigration complete: {total_dom} domains, {total_top} topics")
    print("Backup columns added: domains_backup, topics_backup")


if __name__ == "__main__":
    migrate()
