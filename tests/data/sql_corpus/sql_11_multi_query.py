# @epistemic SQL_DYNAMIC
# Case: SQL_11 - Multi Query Injection
# Injecting a semicolon to execute a second command.
user_id = "1; DELETE FROM users; --"
query = f"SELECT * FROM users WHERE id={user_id}"
print(f"Executing Multi-Query: {query}")
# Note: Python's sqlite3 execute() usually only allows one statement,
# but many other DB drivers (like psycopg2) allow multiple results.
