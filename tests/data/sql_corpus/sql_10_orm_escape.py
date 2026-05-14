# @epistemic SQL_DYNAMIC
# Case: SQL_10 - ORM Raw SQL Escape Hatch
from sqlalchemy import text

user_id = 999
# This is a very common SQLAlchemy mistake
query = text(f"SELECT * FROM users WHERE id={user_id}")
print(f"Executing SQLAlchemy text: {query}")
