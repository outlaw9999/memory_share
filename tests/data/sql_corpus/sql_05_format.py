# @epistemic SQL_DYNAMIC
# Case: SQL_05 - Format String Injection
user_id = "456; DROP TABLE users"
query = f"SELECT * FROM users WHERE id={user_id}"
print(f"Executing: {query}")
