# Case AUTH_03: Empty Condition Bypass
# @epistemic AUTH_EMPTY_CHECK
def process_sensitive_data(auth_header: dict):
    """
    Rủi ro: Kiểm tra header rỗng hoặc không có auth nhưng vẫn tiếp tục xử lý.
    Vantage cần bắt được: If X then pass else execute.
    """
    if not auth_header:
        # Nhẽ ra phải raise error, nhưng ở đây chỉ print warning
        print("Warning: No auth header")
    
    # Tiếp tục xử lý dữ liệu nhạy cảm mà không có bảo vệ
    return "SENSITIVE_DATA_EXPOSED"

if __name__ == "__main__":
    pass
