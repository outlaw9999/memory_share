# AGENTS.md (v1.2.4 EXECUTION KERNEL)

## ⚖️ FLOW
recall → plan → execute → learn

## 🚫 RULES
- ALWAYS use kit/vantage first
- NO manual debugging if tool exists
- NO pytest for primary validation
- Kernel behavior = Source of Truth
- Tests = Verification only

## 🛠️ TOOLS
recall/search → context
doctor → system state
vantage → truth oracle
learn → persist decision

## 🆘 FAILURE ESCALATION
tool fails → doctor → vantage deep → only then reasoning

## 🏁 CONSTRAINT
zero-narrative mode
