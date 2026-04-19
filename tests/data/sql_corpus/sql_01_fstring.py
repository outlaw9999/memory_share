# @epistemic SQL_DYNAMIC
# Case: SQL_01 - Raw f-string interpolation
user_id = 123
query = f"SELECT * FROM users WHERE id = {user_id}"
print(f"Executing: {query}")
