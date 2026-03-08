import os

file_path = "pageindex/page_index.py"
with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

# Replace fragile dict accesses with .get()
replacements = [
    ("json_content['toc_detected']", "json_content.get('toc_detected', 'no')"),
    ("json_content['completed']", "json_content.get('completed', 'no')"),
    ("json_content['page_index_given_in_toc']", "json_content.get('page_index_given_in_toc', 'no')"),
    ("json_content['physical_index']", "json_content.get('physical_index', -1)")
]

for old, new in replacements:
    content = content.replace(old, new)

with open(file_path, "w", encoding="utf-8") as f:
    f.write(content)

print("Patch applied.")
