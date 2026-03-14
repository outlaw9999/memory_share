# kit 🧠

**kit — remember things from your terminal.**

A tiny CLI tool for storing and recalling useful facts. Local-first, git-like memory for humans and AI agents.

## ⚡ 5-Second Demo

```bash
$ pip install kit-engine

$ kit learn bug "JWT refresh fails because of clock skew"
✅ Remembered.

$ kit recall bug
JWT refresh fails because of clock skew
```

## ❓ Why?

Developers forget things:
• Why a bug happened  
• Why an architecture decision was made  
• Which command fixed production  

`kit` keeps these facts in your terminal workflow, not hidden in Slack or Jira.

## 🎯 Pain vs. Solution

| Problem | Solution |
| --- | --- |
| Forget why code exists | `kit learn arch` |
| Lose track of bug fixes | `kit learn bug` |
| Search context for AI | `kit recall` |
| Fragmented knowledge | `kit compact` |

## 🧩 Composability

`kit` follows the Unix philosophy. It's built to be piped and combined.

```bash
# Search through memories with fuzzy-find
kit recall | fzf

# Search for specific tech notes
kit recall | grep "Postgres"

# View content with syntax highlighting
kit recall | bat
```

## 📂 Storage

All data is stored locally in a single, standard SQLite file:
`~/.kit/brain.db`

No cloud. No API. No vendor lock-in.

## 🏛️ Philosophy

Small tools that do one thing well last longer than frameworks. `kit` is a primitive, not a platform.

---
*Built for the era of Humans and Agents.*
⚔️🚀🛡️🧠🥂
