import sys
from pathlib import Path
from kit.api import init_kernel, learn, recall, link

def run_e2e_verification():
    print("🚀 [BOOT] Initializing .kit v2.0.0 engine...")
    db_path = Path("sam_v2.db")
    
    if db_path.exists():
        db_path.unlink()
        
    init_kernel(db_path)

    print("🧠 [LEARN] Ingesting knowledge into immutable ledger...")
    # Learn facts with default importance
    f1 = learn("AuthService", "Sử dụng JWT HS256 cho stateless authentication.", kind="Component")
    f2 = learn("Redis", "Dùng để lưu trữ session và blacklist tokens.", kind="Storage")
    
    # Supersede f1 with a more important fact
    f3 = learn("AuthService", "CẬP NHẬT: Chuyển sang RS256 để hỗ trợ Key Rotation.", kind="Component", importance=1.0, supersede_id=f1)

    print("🔗 [LINK] Establishing synaptic relations...")
    link("AuthService", "Redis", "USES")

    print("🔍 [RECALL] Retrieving ranked context...")
    # Should find updated AuthService fact
    memories = recall(["AuthService"], limit=5)
    
    print("\n--- RETRIEVED CONTEXT ---")
    auth_found = False
    
    for m in memories:
        print(f"[{m.node_uid}] (Score: {m.score:.2f}) -> {m.content}")
        if m.node_uid == "authservice" and "RS256" in m.content:
            auth_found = True

    assert auth_found, "Latest AuthService fact not found or not ranked top"
    
    print("\n✅ [SUCCESS] v2.0.0 End-to-End Verification Passed!")

if __name__ == "__main__":
    try:
        run_e2e_verification()
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"❌ [FAILED] Verification error: {e}")
        sys.exit(1)
