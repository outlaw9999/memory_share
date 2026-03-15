
import os

path = r"e:\DEV\opensource_contrib\memory_share\kit\core\kit_cognitive_core.py"
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

target = """                results.append(Memory(
                    id=row["id"],
                    node_uid=row["node_uid"],
                    content=row["content"],
                    score=row["score"],
                    brain_source=source,
                    layer=row["layer"],
                    namespace=row["namespace"]
                ))"""

replacement = """                results.append(Memory(
                    id=row["id"],
                    node_uid=row["node_uid"],
                    content=row["content"],
                    score=row["score"],
                    brain_source=source,
                    layer=row["layer"],
                    namespace=row["namespace"],
                    created_at=row["created_at"],
                    importance=row["importance"]
                ))"""

new_content = content.replace(target, replacement)

with open(path, "w", encoding="utf-8", newline="\n") as f:
    f.write(new_content)
print("Updated successfully")
