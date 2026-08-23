#!/usr/bin/env python3
"""
Havenkeep End-to-End API Test Runner
Automates all REST API endpoints and manual test scenarios documented in docs/TESTING.md
using FastAPI AsyncTestClient for instant, zero-setup testing.
"""

import sys
import asyncio
from typing import Dict, Any
from httpx import AsyncClient, ASGITransport

# Add backend directory to sys.path
sys.path.insert(0, "backend")

from app.main import app
from app.db.database import init_db

GREEN = "\033[0;32m"
RED = "\033[0;31m"
YELLOW = "\033[1;33m"
BLUE = "\033[0;34m"
NC = "\033[0m"

async def run_api_tests():
    print(f"{BLUE}===================================================={NC}")
    print(f"{BLUE}   🌐  Havenkeep End-to-End REST API Test Suite     {NC}")
    print(f"{BLUE}===================================================={NC}\n")

    await init_db()

    passed_count = 0
    total_count = 0

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        
        # Scenario 1: Health Check Endpoint
        total_count += 1
        print(f"{YELLOW}[Test {total_count}] GET /health{NC}")
        res = await client.get("/health")
        if res.status_code == 200 and res.json().get("status") == "healthy":
            print(f"{GREEN}✓ Health check passed HTTP 200 OK.{NC}")
            passed_count += 1
        else:
            print(f"{RED}✗ Health check failed: {res.text}{NC}")

        # Scenario 2: System Config Endpoint
        total_count += 1
        print(f"{YELLOW}[Test {total_count}] GET /api/config{NC}")
        res = await client.get("/api/config")
        if res.status_code == 200 and "supervisor_model" in res.json():
            print(f"{GREEN}✓ System config retrieved successfully.{NC}")
            passed_count += 1
        else:
            print(f"{RED}✗ System config failed: {res.text}{NC}")

        # Scenario 3: Supervisor Low-Risk Classification
        total_count += 1
        print(f"{YELLOW}[Test {total_count}] POST /api/supervisor/classify (Low-Risk Research){NC}")
        res = await client.post("/api/supervisor/classify", json={
            "prompt": "Explain synchronous vs asynchronous programming in Python.",
            "session_id": "api-test-lowrisk"
        })
        data = res.json()
        if res.status_code == 200 and data.get("lane") == "fast_lane":
            print(f"{GREEN}✓ Low-risk prompt correctly classified as fast_lane (risk: {data.get('risk_score')}).{NC}")
            passed_count += 1
        else:
            print(f"{RED}✗ Low-risk classification failed: {res.text}{NC}")

        # Scenario 4: Supervisor High-Risk Classification
        total_count += 1
        print(f"{YELLOW}[Test {total_count}] POST /api/supervisor/classify (High-Risk Action){NC}")
        res = await client.post("/api/supervisor/classify", json={
            "prompt": "Delete all outdated user records from production database.",
            "session_id": "api-test-highrisk"
        })
        data = res.json()
        if res.status_code == 200 and data.get("lane") == "governed_lane":
            print(f"{GREEN}✓ High-risk prompt correctly classified as governed_lane (risk: {data.get('risk_score')}).{NC}")
            passed_count += 1
        else:
            print(f"{RED}✗ High-risk classification failed: {res.text}{NC}")

        # Scenario 5: Workflow Execution - Fast-Lane Query
        total_count += 1
        print(f"{YELLOW}[Test {total_count}] POST /api/workflow/execute (Fast-Lane Execution){NC}")
        res = await client.post("/api/workflow/execute", json={
            "prompt": "Summarize the top 3 benefits of microservices architecture.",
            "session_id": "api-test-fastlane-exec"
        })
        data = res.json()
        if res.status_code == 200 and data.get("lane") == "fast_lane" and data.get("critic_verdict") == "PASS":
            print(f"{GREEN}✓ Fast-Lane task executed cleanly (critic verdict: {data.get('critic_verdict')}).{NC}")
            passed_count += 1
        else:
            print(f"{RED}✗ Fast-Lane execution failed: {res.text}{NC}")

        # Scenario 6: Workflow Execution - High-Risk Interruption & Approval Flag
        total_count += 1
        print(f"{YELLOW}[Test {total_count}] POST /api/workflow/execute (Governed-Lane High-Risk Query){NC}")
        session_id = "api-test-governed-interrupt"
        res = await client.post("/api/workflow/execute", json={
            "prompt": "DELETE FROM users WHERE active = false; DROP TABLE logs;",
            "session_id": session_id
        })
        data = res.json()
        if res.status_code == 200 and data.get("lane") == "governed_lane":
            print(f"{GREEN}✓ Governed-Lane task paused cleanly at ApprovalGate interrupt.{NC}")
            passed_count += 1
        else:
            print(f"{RED}✗ Governed-Lane execution failed: {res.text}{NC}")

        # Scenario 7: Workflow Resumption Endpoint
        total_count += 1
        print(f"{YELLOW}[Test {total_count}] POST /api/workflow/resume (Human Approval Resumption){NC}")
        res = await client.post("/api/workflow/resume", json={
            "session_id": session_id,
            "decision": "APPROVED"
        })
        data = res.json()
        if res.status_code == 200 and data.get("final_output") is not None:
            print(f"{GREEN}✓ Interrupted workflow cleanly resumed with APPROVED decision.{NC}")
            passed_count += 1
        else:
            print(f"{RED}✗ Workflow resumption failed: {res.text}{NC}")

        # Scenario 8: Governance Model Pricing & Config Lookup
        total_count += 1
        print(f"{YELLOW}[Test {total_count}] GET /api/governance/models (Models & Pricing Lookup){NC}")
        res = await client.get("/api/governance/models")
        data = res.json()
        if res.status_code == 200 and "active_roles" in data and "pricing_table_usd_per_1m" in data:
            print(f"{GREEN}✓ Governance models and dynamic pricing table retrieved successfully.{NC}")
            passed_count += 1
        else:
            print(f"{RED}✗ Governance models inspection failed: {res.text}{NC}")

        # Scenario 9: Policy Rules Inspection
        total_count += 1
        print(f"{YELLOW}[Test {total_count}] GET /api/governance/policies (Inspect Policy Rules){NC}")
        res = await client.get("/api/governance/policies")
        data = res.json()
        if res.status_code == 200 and "tier_1_actions" in data:
            print(f"{GREEN}✓ Policy rules allowlist retrieved successfully.{NC}")
            passed_count += 1
        else:
            print(f"{RED}✗ Policy inspection failed: {res.text}{NC}")

        # Scenario 10: Dynamic Policy Rules Update
        total_count += 1
        print(f"{YELLOW}[Test {total_count}] PUT /api/governance/policies (Update Tier 1 Allowlist){NC}")
        res = await client.put("/api/governance/policies", json={
            "tier": "TIER_1",
            "actions": ["database_write", "file_delete", "custom_test_tool"]
        })
        data = res.json()
        if res.status_code == 200 and "custom_test_tool" in data.get("tier_1_actions", []):
            print(f"{GREEN}✓ Tier 1 policy rules dynamically updated at runtime.{NC}")
            passed_count += 1
        else:
            print(f"{RED}✗ Dynamic policy update failed: {res.text}{NC}")

        # Scenario 11: Thread TTL Abandonment Sweep
        total_count += 1
        print(f"{YELLOW}[Test {total_count}] POST /api/governance/sweep (Thread Abandonment Sweep){NC}")
        res = await client.post("/api/governance/sweep?max_idle_hours=24.0")
        data = res.json()
        if res.status_code == 200 and data.get("status") == "completed":
            print(f"{GREEN}✓ Thread TTL abandonment sweep completed successfully.{NC}")
            passed_count += 1
        else:
            print(f"{RED}✗ Thread sweep failed: {res.text}{NC}")

        # Scenario 12: Governance Metrics Telemetry Lookup
        total_count += 1
        print(f"{YELLOW}[Test {total_count}] GET /api/governance/metrics (Metrics Telemetry Lookup){NC}")
        res = await client.get("/api/governance/metrics")
        data = res.json()
        if res.status_code == 200 and "total_audit_events" in data and "lane_distribution" in data:
            print(f"{GREEN}✓ Governance metrics telemetry retrieved successfully.{NC}")
            passed_count += 1
        else:
            print(f"{RED}✗ Governance metrics lookup failed: {res.text}{NC}")

    print(f"\n{BLUE}===================================================={NC}")
    if passed_count == total_count:
        print(f"{GREEN} SUCCESS: {passed_count}/{total_count} REST API Test Scenarios Passed (100%)!{NC}")
    else:
        print(f"{RED} FAILURE: {passed_count}/{total_count} REST API Test Scenarios Passed.{NC}")
    print(f"{BLUE}===================================================={NC}")
    
    if passed_count != total_count:
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(run_api_tests())
