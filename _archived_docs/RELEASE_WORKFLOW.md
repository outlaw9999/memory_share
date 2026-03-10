# v1.0.0 Release Workflow

**Release Date**: March 9, 2026  
**Status**: Ready for GitHub Release & Announcement  

---

## 📋 Quick Reference Checklist

Before pushing code to the release branch:

```bash
# 1️⃣ Verify branch
git branch --show-current
# Expected output: main OR feature/kit-v1

# 2️⃣ Check git status
git status
# Ensure no uncommitted changes in .antigravity/, __pycache__, etc.

# 3️⃣ View staged changes
git diff --staged
# Verify only release artifacts are staged

# 4️⃣ Push to release branch
git push origin feature/kit-v1  # OR: git push origin main

# 5️⃣ Tag the release
git tag v1.0.0
git push origin v1.0.0
```

---

## 🚀 Complete Release Steps (5-10 minutes)

### Step 1: Final Verification (30 seconds)

```bash
# Confirm all release artifacts exist
ls -la V1_RELEASE_NOTES.md V1_RELEASE_CHECKLIST.md CHANGELOG.md
# All 3 files should exist

# Run verification suite one final time
python verify_kit.py
# Output should show: ✓ All 5 tests PASS
```

**Expected Output**:
```
test_01_environment: PASS
test_02_schema_integrity: PASS
test_03_logic_injection: PASS
test_04_graph_sanity: PASS
test_05_mobility: PASS
```

### Step 2: Check Current Branch (10 seconds)

```bash
git branch --show-current
```

**If you see `main` or `master`**:
- ⚠️ **DO NOT COMMIT**
- Checkout feature branch: `git checkout feature/kit-v1`

**If you see `feature/kit-v1` or similar**:
- ✅ **SAFE TO CONTINUE**

---

### Step 3: Stage Release Artifacts (20 seconds)

```bash
# Stage documentation only
git add V1_RELEASE_NOTES.md V1_RELEASE_CHECKLIST.md CHANGELOG.md README.md

# Verify what's staged
git diff --staged
```

**Expected changes**:
- ✅ README.md — v1.0.0 badge added
- ✅ V1_RELEASE_NOTES.md — user-facing docs
- ✅ V1_RELEASE_CHECKLIST.md — completion status
- ✅ CHANGELOG.md — v1.0.0 entry

**If you see unexpected files (e.g., `.db`, `__pycache__`)**:
```bash
git reset  # Unstage everything
git add V1_RELEASE_NOTES.md V1_RELEASE_CHECKLIST.md CHANGELOG.md README.md
```

---

### Step 4: Commit Release (20 seconds)

```bash
git commit -m "Release: v1.0.0 stable (11-stone spellbook, architecture frozen)"
```

**Standard commit message format**:
```
Release: v1.0.0 stable (11-stone spellbook, architecture frozen)

- Graph confidence metric (detects static analysis bias)
- Utility hub detection (separates utilities from orchestrators)
- Improved choke points heuristic (LN-based fan-out penalty)
- Query timeout support (scales to massive repos)
- Mobility test verified (execution from any subdirectory)
- Doctor enhanced with confidence + utility detection
- Gravity metric annotated (utility gravity well warning)
- Architecture frozen for backward compatibility
- 5-test verification guard active
- Performance baseline verified
```

---

### Step 5: Create Git Tag (10 seconds)

```bash
git tag -a v1.0.0 -m "Release v1.0.0: Stable, production-ready kit with frozen architecture"
```

**Verify tag**:
```bash
git tag -l v1.0.0
git show v1.0.0
```

---

### Step 6: Push to Remote (30 seconds)

```bash
# Push commits
git push origin feature/kit-v1   # OR: main (if merging directly)

# Push tag
git push origin v1.0.0
```

**Verify**:
```bash
git log --oneline -n 5
git tag -l
```

---

### Step 7: Create GitHub Release (Optional but Recommended)

Go to: `https://github.com/outlaw9999/memory_share/releases`

1. Click **"Draft a new release"**
2. Select tag: `v1.0.0`
3. Title: `v1.0.0 — Production Ready`
4. Description: Copy from [V1_RELEASE_NOTES.md](V1_RELEASE_NOTES.md)
5. Attachments: (optional) Attach compiled `.kit` artifacts
6. Click **"Publish release"**

---

### Step 8: Pin in README (Already Done ✅)

The README now includes:
```markdown
[![Release: v1.0.0](https://img.shields.io/badge/release-v1.0.0-green)](...)
```

---

## ⚠️ Common Mistakes (How to Avoid)

### Mistake #1: Committing to `main` instead of feature branch

**Prevention**:
```bash
# BEFORE every commit, run:
git branch --show-current

# If output is 'main', STOP:
git checkout feature/kit-v1
```

### Mistake #2: Staging wrong files (`.db`, `__pycache__`)

**Prevention**:
```bash
# BEFORE commit, inspect staged files:
git diff --staged

# If .db or __pycache__ appears:
git reset
git add V1_RELEASE_NOTES.md V1_RELEASE_CHECKLIST.md CHANGELOG.md README.md
```

### Mistake #3: Tagging wrong commit

**Prevention**:
```bash
# Verify HEAD is correct
git log --oneline -n 1

# Before tagging, check:
git tag -l | grep v1.0.0  # Should be empty

# After tagging, verify:
git show v1.0.0 --stat
```

---

## 🔧 Pro Tips for Maintainers

### Tip #1: Display Branch in Terminal Prompt

Add to your `.bashrc` or `.zshrc` (or PowerShell profile):

```bash
# Bash example
PS1="$(pwd) ($branch) $ "  # Shows: /path/to/kit (feature/kit-v1) $
```

This makes it **impossible** to forget which branch you're on.

### Tip #2: Git Hooks (Prevent Commits to main)

Create `.git/hooks/pre-commit`:

```bash
#!/bin/bash
BRANCH=$(git rev-parse --abbrev-ref HEAD)
if [ "$BRANCH" == "main" ] || [ "$BRANCH" == "master" ]; then
  echo "❌ Cannot commit directly to $BRANCH"
  echo "✅ Use: git checkout feature/kit-v1"
  exit 1
fi
```

Then:
```bash
chmod +x .git/hooks/pre-commit
```

### Tip #3: Protected Branches (GitHub)

1. Go to **Settings > Branches**
2. Add rule for `main`:
   - ✅ Require pull request reviews before merging
   - ✅ Require status checks to pass
3. Now direct commits to `main` are **impossible**

---

## 📝 Post-Release Tasks

After tagging and pushing:

- [ ] Create GitHub Release (attach C documentation)
- [ ] Update project announcements channel
- [ ] Pin v1.0.0 in README (✅ Done)
- [ ] Begin planning v1.1 (incremental indexing)
- [ ] Monitor for early adoption feedback

---

## 🎯 Release Summary

| Component | Status | Location |
|-----------|--------|----------|
| Release Notes | ✅ Complete | [V1_RELEASE_NOTES.md](V1_RELEASE_NOTES.md) |
| Checklist | ✅ Verified | [V1_RELEASE_CHECKLIST.md](V1_RELEASE_CHECKLIST.md) |
| Changelog | ✅ Updated | [CHANGELOG.md](CHANGELOG.md) |
| Architecture Freeze | ✅ Locked | [docs/ARCHITECTURE_FREEZE.md](docs/ARCHITECTURE_FREEZE.md) |
| README Badge | ✅ Pinned | [README.md](README.md) [L1-L4](README.md#L1-L4) |
| Verification Tests | ✅ Passing | [verify_kit.py](verify_kit.py) |

---

## 🚀 You're Ready to Release!

Everything is prepared. Follow the **5-step workflow** above and you'll ship v1.0.0 with confidence.

The **honesty layer** (graph confidence + utility detection + timeout safety) separates this release from naive graph tools.

**Status: PRODUCTION READY** ✅
