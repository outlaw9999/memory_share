# @epistemic SQL_DYNAMIC
# Case: SQL_02 - SQLAlchemy text() interpolation
import sqlalchemy
user_id = 456
query = sqlalchemy.text(f"SELECT * FROM users WHERE id = {user_id}")
print(f"Executing SQLAlchemy text: {query}")
