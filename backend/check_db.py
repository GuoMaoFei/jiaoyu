import sqlite3

conn = sqlite3.connect(r"d:\project\python\jiaoyu_agent\backend\treeedu.db")
cur = conn.cursor()

print("=" * 60)
print("MATERIALS TABLE")
print("=" * 60)
cur.execute("SELECT id, title, grade, subject, version FROM materials")
rows = cur.fetchall()
for r in rows:
    print(f"  ID: {r[0]}")
    print(f"  Title: {r[1]}")
    print(f"  Grade: {r[2]}, Subject: {r[3]}, Version: {r[4]}")
    print()
print(f"Total materials: {len(rows)}")

print()
print("=" * 60)
print("KNOWLEDGE_NODES TABLE")
print("=" * 60)
cur.execute("SELECT COUNT(*) FROM knowledge_nodes")
total = cur.fetchone()[0]
print(f"Total nodes in DB: {total}")
print()

# Show tree structure grouped by material
cur.execute("SELECT DISTINCT material_id FROM knowledge_nodes")
mat_ids = [r[0] for r in cur.fetchall()]

for mat_id in mat_ids:
    print(f"--- Material: {mat_id} ---")
    cur.execute(
        "SELECT id, parent_id, title, level, seq_num, pageindex_ref, mapped_pi_nodes, content_md "
        "FROM knowledge_nodes WHERE material_id = ? ORDER BY level, seq_num",
        (mat_id,)
    )
    nodes = cur.fetchall()
    for n in nodes:
        node_id, parent_id, title, level, seq_num, pi_ref, mapped_pi, content_md = n
        indent = "  " * level
        content_preview = (content_md[:120] + "...") if content_md and len(content_md) > 120 else content_md
        mapped_preview = mapped_pi[:200] if mapped_pi else None
        print(f"{indent}[L{level}] #{seq_num} {title}")
        print(f"{indent}  id={node_id[:12]}.. parent={parent_id[:12] + '..' if parent_id else 'ROOT'}")
        print(f"{indent}  pi_ref={pi_ref} | mapped_pi={mapped_preview}")
        print(f"{indent}  content: {content_preview}")
        print()

conn.close()
