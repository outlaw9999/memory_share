# Case AUTH_02: Logic Inversion (Fail-Open)
# @epistemic AUTH_INVERSION
def check_permission_flawed(user_role: str):
    """
    Rủi rỏ: Logic bị đảo ngược khiến mọi user không phải guest đều có quyền admin.
    Vantage cần bắt được: If not X then Allow.
    """
    if not user_role == "guest":
        # Logic sai: nếu không phải guest thì cho phép (Lẽ ra phải kiểm tra admin)
        return "ALLOWED_ADMIN"

    return "DENIED"


if __name__ == "__main__":
    pass
