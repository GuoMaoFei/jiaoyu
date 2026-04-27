import sqlite3
import json

db_path = r'd:\project\python\jiaoyu_agent\backend\treeedu.db'
material_id = '54a7a39c-f27b-41f9-aebe-677afc5152a0'

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# 1. Check if material exists
cursor.execute("SELECT id, title FROM materials WHERE id = ?", (material_id,))
material = cursor.fetchone()
print("=== Material ===")
print(f"Material: {material}")

# 2. Count nodes by level
cursor.execute("""
    SELECT level, COUNT(*) as count 
    FROM knowledge_nodes 
    WHERE material_id = ? 
    GROUP BY level 
    ORDER BY level
""", (material_id,))
print("\n=== Nodes by Level ===")
for row in cursor.fetchall():
    print(f"Level {row[0]}: {row[1]} nodes")

# 3. Check parent_id distribution (to see tree structure)
cursor.execute("""
    SELECT 
        CASE WHEN parent_id IS NULL THEN 'ROOT' ELSE 'CHILD' END as type,
        COUNT(*) as count
    FROM knowledge_nodes
    WHERE material_id = ?
    GROUP BY type
""", (material_id,))
print("\n=== Root vs Child Nodes ===")
for row in cursor.fetchall():
    print(f"{row[0]}: {row[1]} nodes")

# 4. Sample nodes with parent_id (show tree structure)
cursor.execute("""
    SELECT id, title, level, seq_num, parent_id, pageindex_ref, mapped_pi_nodes
    FROM knowledge_nodes
    WHERE material_id = ?
    ORDER BY level, seq_num
    LIMIT 20
""", (material_id,))
print("\n=== Sample Nodes (first 20) ===")
for row in cursor.fetchall():
    node_id, title, level, seq_num, parent_id, pi_ref, mapped_pi = row
    print(f"Level {level} Seq {seq_num}: {title[:40]}...")
    print(f"  id={node_id[:8]}... parent_id={parent_id[:8] if parent_id else 'NULL'}")
    print(f"  pageindex_ref={pi_ref}, mapped_pi_nodes={mapped_pi}")

# 5. Check if there are any nodes with children (parent_id pointing to them)
cursor.execute("""
    SELECT parent.id, parent.title, COUNT(child.id) as child_count
    FROM knowledge_nodes parent
    JOIN knowledge_nodes child ON child.parent_id = parent.id
    WHERE parent.material_id = ?
    GROUP BY parent.id
    ORDER BY child_count DESC
    LIMIT 10
""", (material_id,))
print("\n=== Nodes with Children (top 10) ===")
for row in cursor.fetchall():
    print(f"{row[1][:40]}... has {row[2]} children")

# 6. Check pi_nodes_json field (this contains PageIndex structure)
cursor.execute("""
    SELECT id, title, pi_nodes_json
    FROM knowledge_nodes
    WHERE material_id = ? AND pi_nodes_json IS NOT NULL
    LIMIT 3
""", (material_id,))
print("\n=== Nodes with pi_nodes_json ===")
for row in cursor.fetchall():
    print(f"Node: {row[1][:40]}...")
    if row[2]:
        pi_json = json.loads(row[2]) if isinstance(row[2], str) else row[2]
        print(f"  pi_nodes_json type: {type(pi_json)}")
        if isinstance(pi_json, list) and len(pi_json) > 0:
            print(f"  First item keys: {list(pi_json[0].keys())[:10]}")

# 7. Check knowledge point mappings
cursor.execute("""
    SELECT COUNT(*) 
    FROM knowledge_point_mappings kpm
    JOIN knowledge_nodes kn ON kpm.knowledge_node_id = kn.id
    WHERE kn.material_id = ?
""", (material_id,))
kp_count = cursor.fetchone()[0]
print(f"\n=== Knowledge Point Mappings: {kp_count} ===")

conn.close()
