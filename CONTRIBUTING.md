# 🏛️ Palace Etiquette (CONTRIBUTING.md)

Welcome, Contributor. You are entering a "Correctness-First" environment.

### ⚔️ The Code of Honor
- **Python 3.14+**: Mandatory. Use modern typing (e.g., `list[str]` instead of `List`).
- **No Side Effects**: The Memory Engine must be deterministic.
- **Documentation**: All logic changes MUST update the `ARCHITECTURE.md`. We no longer use scattered schema/api files.
- **Stability**: Every PR must pass the `Royal Guard` CI/CD check.

### 📜 Development Workflow
1. **Recall**: Check existing architecture in `ARCHITECTURE.md` and `STABILITY.md`.
2. **Implement**: Prioritize minimal, zero-dependency code.
3. **Verify**: Run `python examples/minimal_example.py` before submitting.
