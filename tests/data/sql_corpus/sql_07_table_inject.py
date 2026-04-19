# @epistemic SQL_DYNAMIC
# Case: SQL_07 - Table/Column Injection
table_name = "users; DROP TABLE sessions"
query = f"SELECT * FROM {table_name}"
print(f"Executing: {query}")
