# @epistemic SQL_DYNAMIC_LOOP
def batch_delete_unsafe(cursor, ids):
    """
    Case SQL_12: Đây là nơi Regex thất bại hoàn toàn.
    Chúng ta cần Vantage nhìn thấy Loop + Execute + Variable.
    """
    for uid in ids:
        # Nhát dao structural risk:
        query = "DELETE FROM users WHERE id=%s" % uid
        cursor.execute(query)

if __name__ == "__main__":
    # Mock call for local test
    pass
