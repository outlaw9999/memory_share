# @epistemic SQL_DYNAMIC
# Case: SQL_03 - Loop-based execute
dynamic_queries = [f"DELETE FROM logs WHERE id = {i}" for i in range(10)]
for q in dynamic_queries:
    # Logic risk: Dynamic queries formed in a list comprehension.
    # cursor.execute(q)
    print(f"Executing: {q}")
