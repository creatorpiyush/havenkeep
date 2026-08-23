---
name: havenkeep-test
description: >-
  Automated testing runbook for running unit tests, end-to-end REST API endpoint validation, and interactive CLI harness checks for Havenkeep.
---

# Havenkeep Automated Testing Skill 🧪

Use this skill when testing, validating, or debugging the **Havenkeep** multi-agent harness to verify that all REST APIs, state machine workflows, risk classifiers, and governance policies function properly.

---

## 🚀 One-Command Automated Test Suite Execution

### 1. Run Complete Automated Pre-Commit & Pytest Suite (19/19 Tests)
```bash
./scripts/precommit.sh
```

### 2. Run Complete End-to-End REST API Endpoint Suite (11/11 Endpoints)
```bash
TESTING=1 PYTHONPATH=backend ./venv/bin/python3 scripts/api_test_runner.py
```

### 3. Run Both Pre-Commit & REST API Suites Together
```bash
./scripts/precommit.sh && TESTING=1 PYTHONPATH=backend ./venv/bin/python3 scripts/api_test_runner.py
```

---

## 📋 What Gets Validated Automatically

| Test Command | Scope & Verified Features |
| :--- | :--- |
| **`./scripts/precommit.sh`** | Runs Python code compilation (`py_compile`), syntax linting, Pytest 19/19 unit & integration tests (`test_cost_tracker`, `test_policy_engine`, `test_supervisor`, `test_fast_lane`, `test_governed_lane`, `test_governance_layer`). |
| **`scripts/api_test_runner.py`** | Validates all 11 REST API endpoints documented in `docs/TESTING.md`: `/health`, `/api/config`, `/api/supervisor/classify`, `/api/workflow/execute` (Fast-Lane & Governed-Lane `interrupt()`), `/api/workflow/resume`, `/api/governance/models`, `/api/governance/policies` (GET/PUT), and `/api/governance/sweep`. |
| **`scripts/interactive_test.py`** | Terminal-based interactive testing harness for evaluating prompt routing and workflow responses. |

---

## 🛑 Documentation Invariant for `docs/TESTING.md`

Whenever adding a new API endpoint scenario to [docs/TESTING.md](docs/TESTING.md):
- [ ] Must include **`Swagger UI Endpoint`** label.
- [ ] Must include **`Swagger UI Payload (Copy & Paste)`** JSON block (if request body exists).
- [ ] Must include **`cURL Command`** block.
- [ ] Must include **`Expected Response JSON`** block.
