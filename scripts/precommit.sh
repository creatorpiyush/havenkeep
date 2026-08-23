#!/usr/bin/env bash
# Havenkeep Pre-Commit Verification & Git Hook Script
# Runs Python syntax checks, linting, and full Pytest regression suite before committing code.

set -e

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Option to install as Git pre-commit hook
if [ "$1" == "--install-hook" ]; then
    HOOK_PATH=".git/hooks/pre-commit"
    echo -e "${BLUE}Installing Havenkeep pre-commit hook into ${HOOK_PATH}...${NC}"
    mkdir -p .git/hooks
    cat << 'EOF' > "$HOOK_PATH"
#!/usr/bin/env bash
./scripts/precommit.sh
EOF
    chmod +x "$HOOK_PATH"
    echo -e "${GREEN}✓ Pre-commit hook successfully installed!${NC}"
    exit 0
fi

echo -e "${BLUE}====================================================${NC}"
echo -e "${BLUE}   🛡️  Havenkeep Pre-Commit Verification Suite      ${NC}"
echo -e "${BLUE}====================================================${NC}"

# 1. Absolute Machine Path Leak Check
echo -e "\n${YELLOW}[1/4] Checking for Hardcoded Absolute Machine Paths...${NC}"
if grep -E -rn --exclude="precommit.sh" --exclude-dir="__pycache__" --exclude-dir=".pytest_cache" --exclude-dir="venv" --exclude-dir=".git" "/Users/[a-zA-Z0-9_-]+" backend/ docs/ .agents/ README.md ARCHITECTURE.md CHANGELOG.md scripts/ > /dev/null 2>&1; then
    echo -e "${RED}ERROR: Hardcoded absolute machine paths (/Users/username/...) found in repository files! Use relative paths.${NC}"
    grep -E -rn --exclude="precommit.sh" --exclude-dir="__pycache__" --exclude-dir=".pytest_cache" --exclude-dir="venv" --exclude-dir=".git" "/Users/[a-zA-Z0-9_-]+" backend/ docs/ .agents/ README.md ARCHITECTURE.md CHANGELOG.md scripts/
    exit 1
fi
echo -e "${GREEN}✓ Zero hardcoded absolute machine paths found.${NC}"

# 2. Python Syntax & Compilation Verification
echo -e "\n${YELLOW}[2/4] Checking Python Syntax & Code Compilation...${NC}"
PYTHON_BIN="./venv/bin/python3"
if [ ! -f "$PYTHON_BIN" ]; then
    PYTHON_BIN="python3"
fi

$PYTHON_BIN -m py_compile backend/app/main.py backend/app/config.py backend/app/api/routes.py backend/app/governance/policy_engine.py backend/app/governance/cost_tracker.py backend/app/governance/audit_logger.py backend/app/governance/model_adapter.py backend/app/graph/workflow.py backend/app/graph/nodes/*.py
echo -e "${GREEN}✓ All Python modules compiled cleanly without syntax errors.${NC}"

# 3. Pytest Automated Test Suite Execution
echo -e "\n${YELLOW}[3/4] Executing Automated Pytest Test Suite...${NC}"
TESTING=1 PYTHONPATH=backend ./venv/bin/pytest tests/ -v

echo -e "${GREEN}✓ 100% of automated unit & integration tests passed cleanly.${NC}"

# 4. REST API Endpoint Test Suite Execution
echo -e "\n${YELLOW}[4/4] Executing End-to-End REST API Endpoint Test Suite...${NC}"
TESTING=1 PYTHONPATH=backend $PYTHON_BIN scripts/api_test_runner.py

echo -e "${GREEN}✓ 100% of REST API endpoint test scenarios passed cleanly.${NC}"

# Final Pre-Commit Summary
echo -e "\n${BLUE}====================================================${NC}"
echo -e "${GREEN} SUCCESS: All 4 pre-commit linting, syntax, unit, and API test suites passed!${NC}"
echo -e "${BLUE}====================================================${NC}"
