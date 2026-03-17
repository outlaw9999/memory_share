#!/bin/bash
# .kit Infra-grade Pre-commit Verification

echo "🔍 Starting .kit Pre-commit Verification..."

# 1. Unit Tests
echo "🧪 Running formal test suite..."
pytest tests/
if [ $? -ne 0 ]; then
    echo "❌ Unit tests failed. Commit aborted."
    exit 1
fi

# 2. CLI End-to-End Verification
echo "🖥️ Verifying CLI runtime..."
python kit.py learn --uid test_node --content "Pre-commit verification fact" --importance 0.8
python kit.py recall test_node | grep -q "Pre-commit verification fact"
if [ $? -ne 0 ]; then
    echo "❌ CLI recall failed. Commit aborted."
    exit 1
fi

# 3. Context & AI Interface Verification
echo "🧠 Verifying AI manifests..."
python kit.py context
if [ ! -f "AGENTS.md" ]; then
    echo "❌ AGENTS.md missing. Commit aborted."
    exit 1
fi

# 4. DB Integrity
echo "🛡️ Checking SQLite integrity..."
sqlite3 cognitive.db "PRAGMA integrity_check;" | grep -q "ok"
if [ $? -ne 0 ]; then
    echo "❌ DB integrity check failed. Commit aborted."
    exit 1
fi

echo "✅ ALL SYSTEMS GO. Ready for commit."
exit 0
