import pytest
from kit.core.kit_cognitive_core import SAMBrain

@pytest.fixture
def brain(tmp_path):
    db_path = tmp_path / "fts_test.db"
    return SAMBrain(db_path)

def test_fts_keyword_search(brain):
    brain.learn("node", "The authentication system uses JWT tokens")
    brain.learn("node", "Database is using Postgres")
    
    # 1. Direct match
    results = brain.search("JWT")
    assert len(results) == 1
    assert "authentication" in results[0].content

    # 2. Case insensitive
    results = brain.search("jwt")
    assert len(results) == 1

def test_porter_stemming(brain):
    # Porter stemmer should map 'connecting', 'connection', 'connect' to same root
    brain.learn("node", "Establishing a persistent connection to the server")
    
    # Search for 'connecting' should find 'connection'
    results = brain.search("connecting")
    assert len(results) == 1
    assert "connection" in results[0].content

def test_fts_trigger_sync(brain):
    # Insert
    fact_id = brain.learn("node", "Initial content")
    assert len(brain.search("Initial")) == 1
    
    # Update content (via supersede or manual update to test trigger)
    with brain._get_connection() as conn:
        conn.execute("UPDATE observations SET content = 'Updated content' WHERE id = ?", (fact_id,))
    
    # Search for old content should fail, new should succeed
    assert len(brain.search("Initial")) == 0
    assert len(brain.search("Updated")) == 1
