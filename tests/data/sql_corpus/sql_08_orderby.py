# @epistemic SQL_DYNAMIC
# Case: SQL_08 - ORDER BY Injection
sort_column = "id; DROP TABLE users"
query = f"SELECT * FROM users ORDER BY {sort_column}"
print(f"Executing: {query}")
