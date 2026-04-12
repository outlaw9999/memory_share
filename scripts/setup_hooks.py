import os
import stat
from pathlib import Path


def main():
    git_dir = Path(".git")
    if not git_dir.exists():
        print("Error: .git directory not found. Must run from repository root.")
        return

    hooks_dir = git_dir / "hooks"
    hooks_dir.mkdir(exist_ok=True)

    pre_commit_path = hooks_dir / "pre-commit"
    
    # Path detection for robustness in varied Windows/GitBash environments
    import sys
    python_bin = sys.executable
    kit_path = (Path(__file__).resolve().parents[1] / "kit.py").absolute()

    hook_content = f"""#!/usr/bin/env bash
# ==========================================================
# AMSB v1.2.3 - The Autonomic Cognitive Governance Hook
# ==========================================================

# 🛡️ 1. CỜ THOÁT HIỂM (EMERGENCY BYPASS)
if [ "$SKIP_KIT" = "1" ]; then
    echo "⏭️  [AMSB] Bypassing Cognitive Preflight..."
    exit 0
fi

# ⚡ 2. LỌC RÁC TỐI ĐA (ANTI-LAG FILTER)
# Only analyze staged code changes (Added, Copied, Modified)
STAGED_DIFF=$(git diff --cached --diff-filter=ACM -- '*.py' '*.rs' '*.ts' '*.go' '*.js' 2>/dev/null)

if [ -z "$STAGED_DIFF" ]; then
    exit 0
fi

echo "🧠 [AMSB] Cognitive Preflight..."

# ⏱️ 3. KỶ LUẬT THÉP OS-LEVEL (THE 1-SECOND GUILLOTINE)
# Uses OS-level timeout to guarantee the IDE never hangs more than 1 second.
# Passes diff via STDIN for zero-leak security.
timeout 1s "{python_bin}" "{kit_path}" preflight <<< "$STAGED_DIFF"
EXIT_CODE=$?

# ⚖️ 4. TÒA ÁN PHÁN QUYẾT
if [ $EXIT_CODE -eq 124 ]; then
    echo "⏱️ [AMSB] Timeout 1s! Bỏ qua kiểm duyệt để bảo vệ tốc độ IDE."
    exit 0 
elif [ $EXIT_CODE -ne 0 ]; then
    echo "❌ [AMSB] ỦY BAN KIẾN TRÚC PHỦ QUYẾT: Vi phạm luật (Invariant)!"
    echo "💡 Sửa code, hoặc dùng SKIP_KIT=1 git commit... nếu muốn ép lưu."
    exit 1 
fi

exit 0
"""
    
    with open(pre_commit_path, "w", encoding="utf-8", newline='\n') as f:
        f.write(hook_content)
        
    # Make executable
    st = os.stat(pre_commit_path)
    os.chmod(pre_commit_path, st.st_mode | stat.S_IEXEC)
        
    print(f"✅ Successfully installed AMSB v1.2.3 hook at {pre_commit_path}")


if __name__ == "__main__":
    main()
