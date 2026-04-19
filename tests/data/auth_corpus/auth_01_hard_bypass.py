# Case AUTH_01: Login Success Bypass
# @epistemic AUTH_BYPASS_HARD
def verify_access_unsafe(token: str):
    """
    Rủi ro: Login luôn thành công bất kể token là gì.
    Vantage cần bắt được: logic so sánh hằng số hoặc bỏ qua kiểm tra thực tế.
    """
    if token == "admin":
        return True
    
    # Bypass logic: Trả về True ngay cả khi không khớp admin
    return True

if __name__ == "__main__":
    pass
