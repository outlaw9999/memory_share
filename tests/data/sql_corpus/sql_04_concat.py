# @epistemic SQL_DYNAMIC
# Case: SQL_04 - String Concatenation
user_id = "123 OR 1=1"
query = "SELECT * FROM users WHERE id=" + user_id
print(f"Executing: {query}")
