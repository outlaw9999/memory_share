# @epistemic SQL_DYNAMIC
# Case: SQL_09 - LIKE Injection
keyword = "admin' OR name LIKE '%"
query = f"SELECT * FROM users WHERE name LIKE '%{keyword}%'"
print(f"Executing: {query}")
