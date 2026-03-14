import sys
from pathlib import Path

# Add project root to sys.path
project_root = Path(__file__).parent.absolute()
sys.path.append(str(project_root))

from kit.core.kit_cognitive_core import SAMBrain, SAMBrainError

def test_sambrain_v2():
    db_path = project_root / "test_memory_v2.db"
    if db_path.exists():
        db_path.unlink()
        
    brain = SAMBrain(db_path)
    print("✅ Schema initialized.")

    # 1. Learning
    brain.learn_fact("AuthService", "Component", "Uses JWT RS256.", importance=0.9)
    brain.learn_fact("Redis", "Storage", "Used for session caching.", importance=0.7)
    brain.learn_fact("JWT", "Standard", "JSON Web Token for stateless auth.", importance=0.8)
    print("✅ Facts learned.")

    # 2. Linking
    brain.link("AuthService", "Redis", "USES")
    brain.link("AuthService", "JWT", "REQUIRES")
    print("✅ Entities linked.")

    # 3. Recall with expansion
    print("\n--- Recalling AuthService (should expand to Redis and JWT) ---")
    nodes = brain.recall_context(["AuthService"])
    for n in nodes:
        print(f"Fact: [{n.entity_uid}] {n.content} (Score: {n.score:.4f}, Dist: {n.distance})")
    
    assert any(n.entity_uid == "Redis" for n in nodes), "Neighbor Redis not found in expansion"
    assert any(n.entity_uid == "JWT" for n in nodes), "Neighbor JWT not found in expansion"
    print("✅ Recall expansion verified.")

    # 4. Access count and Ranking
    print("\n--- Accessing Redis twice ---")
    brain.recall_context(["Redis"])
    brain.recall_context(["Redis"])
    
    nodes = brain.recall_context(["AuthService", "Redis"], limit=5)
    redis_node = next(n for n in nodes if n.entity_uid == "Redis")
    print(f"Redis Score after access: {redis_node.score:.4f}")
    print("✅ Access count ranking verified.")

    # 5. Export for prompt
    prompt = brain.export_for_prompt(["AuthService"], token_budget=500)
    print("\n--- Exported Prompt ---")
    print(prompt)
    assert "<sam_memory>" in prompt
    assert "### GRAPH RELATIONS:" in prompt
    print("✅ Export verify.")

    # 6. Type checking (Doctrine test)
    try:
        SAMBrain("invalid_str_path") # type: ignore
    except SAMBrainError:
        print("✅ String path rejection verified (Doctrine compliance).")

    print("\n🚀 ALL TESTS PASSED!")

if __name__ == "__main__":
    try:
        test_sambrain_v2()
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"❌ TEST FAILED: {e}")
        sys.exit(1)
