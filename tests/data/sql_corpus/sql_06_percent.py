# @epistemic SQL_DYNAMIC
# Case: SQL_06 - Percent Formatting
user_id = "789 OR 1=1"
query = "SELECT * FROM users WHERE id=%s" % user_id
print(f"Executing: {query}")
