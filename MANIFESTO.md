# 📜 The .kit Manifesto: Against the Amnesia of Agents

The AI industry is living a lie. When an agent forgets, the reflex is to chunk the codebase, embed it, and perform a similarity search (RAG). 

**This is a fundamental architectural error.**

## 1. The Lie: "RAG gives agents memory."
Similarity is not Truth. When an agent asks "How do we handle auth?", a Vector DB returns 5 snippets that *conceptually* talk about auth—often including outdated, conflicting, or irrelevant noise. 

## 2. The Reality: RAG retrieves Noise.
RAG produces probabilistic relevance, not deterministic authority. 
- **The Cost:** Hallucinations, architectural drift, and multiple agents overwriting each other's work because they share no stable worldview.

## 3. The Principle: Memory must be Governed.
If 10 agents ask the same question, they must get the exact same ranked facts. Giving an agent more context without governance is just giving it more material to hallucinate with.

## 4. The Thesis: .kit is Deterministic Memory.
`.kit` rejects the "Good Enough" of RAG in favor of **Structural Integrity**:
1. **Deterministic Accuracy:** Using SQLite FTS5 and mathematical ranking (`materialized_score`), we provide authoritative recall, not "similar" results.
2. **Constitutional Guardrails:** `.kit` uses Git Hooks (`kit preflight`) and a Supreme Court Arbitrator to physically block commits that violate architectural invariants.
3. **Execution, not Search:** `.kit` is a protocol, not a tool. It is invisible, weightless, and enforces the laws of your repository with sub-50ms precision.

Stop treating your repository like a loose collection of text. Treat it like a **Cognitive OS**. 

---
*Memory is not a luxury. It is a prerequisite for disciplined engineering.* 🏛️
