import sys
from pathlib import Path
from kit.api import init_kernel, learn, recall, link_entities

def run_e2e_verification():
    print("🚀 [BOOT] Initializing .kit v1.0 engine...")
    db_path = Path("sam_v1.db")
    
    if db_path.exists():
        db_path.unlink()
        
    init_kernel(db_path)

    print("🧠 [LEARN] Ingesting knowledge into immutable ledger...")
    # Learn facts with default importance
    f1 = learn("AuthService", "Component", "Sử dụng JWT HS256 cho stateless authentication.")
    f2 = learn("Redis", "Storage", "Dùng để lưu trữ session và blacklist tokens.")
    
    # Supersede f1 with a more important fact
    f3 = learn("AuthService", "Component", "CẬP NHẬT: Chuyển sang RS256 để hỗ trợ Key Rotation.", importance=1.0, replaces_id=f1)

    print("🔗 [LINK] Establishing synaptic relations...")
    link_entities("AuthService", "Redis", "USES")

    print("🔍 [RECALL] Retrieving ranked context (1-Hop Expansion)...")
    # Should find updated AuthService fact and expanded Redis fact
    memories = recall(["AuthService"], limit=5)
    
    print("\n--- RETRIEVED CONTEXT ---")
    auth_found = False
    redis_expanded = False
    
    for m in memories:
        print(f"[{m.entity_uid}] (Score: {m.score:.2f}, Dist: {m.distance}) -> {m.content}")
        if m.entity_uid == "AuthService" and "RS256" in m.content:
            auth_found = True
        if m.entity_uid == "Redis":
            redis_expanded = True

    assert auth_found, "Latest AuthService fact not found or not ranked top"
    assert redis_expanded, "1-Hop expansion failed to pull Redis context"
    
    print("\n✅ [SUCCESS] v1.0.0 End-to-End Verification Passed!")

if __name__ == "__main__":
    try:
        run_e2e_verification()
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"❌ [FAILED] Verification error: {e}")
        sys.exit(1)
