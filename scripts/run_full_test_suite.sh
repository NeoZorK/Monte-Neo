#!/bin/bash
# Comprehensive Test Suite Runner for Monte-Neo
# Version: v0.0.1

set -e

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}===============================================${NC}"
echo -e "${BLUE}   Monte-Neo Full Test & Verification Suite    ${NC}"
echo -e "${BLUE}===============================================${NC}"

# 1. Clean previous artifacts
echo -e "\n${BLUE}[1/7] Cleaning environment...${NC}"
rm -rf .pytest_cache coverage_html .coverage .mypy_cache .ruff_cache
mkdir -p coverage_html

# 2. Linting (Ruff)
echo -e "\n${BLUE}[2/7] Running Linter (Ruff)...${NC}"
if uv run ruff check .; then
    echo -e "${GREEN}✓ Linting Passed${NC}"
else
    echo -e "${RED}✗ Linting Failed${NC}"
    exit 1
fi

# 3. Type Checking (Optional/Informational)
echo -e "\n${BLUE}[3/7] Running Type Checker (Mypy)...${NC}"
if uv run mypy src/monte_neo; then
    echo -e "${GREEN}✓ Type Checking Passed${NC}"
else
    echo -e "${RED}⚠ Type Checking found issues, but continuing...${NC}"
fi

# 4. Unit Tests with Coverage
echo -e "\n${BLUE}[4/7] Running Unit Tests & Coverage...${NC}"
# Use a reasonable number of workers to avoid memory issues on some systems, or let it be auto
uv run pytest tests/unit/ -n auto -W ignore --cov=src/monte_neo --cov-report=html:coverage_html --cov-report=term --cov-config=.coveragerc
UNIT_STATUS=$?

if [ $UNIT_STATUS -eq 0 ]; then
    echo -e "${GREEN}✓ Unit Tests Passed${NC}"
else
    echo -e "${RED}✗ Unit Tests Failed${NC}"
    exit 1
fi

# 5. Integration Tests
echo -e "\n${BLUE}[5/7] Running Integration Tests...${NC}"
uv run pytest tests/integration/ -W ignore
INTEG_STATUS=$?

if [ $INTEG_STATUS -eq 0 ]; then
    echo -e "${GREEN}✓ Integration Tests Passed${NC}"
else
    echo -e "${RED}✗ Integration Tests Failed${NC}"
    exit 1
fi

# 6. Stress Tests
echo -e "\n${BLUE}[6/7] Running Stress & Performance Tests...${NC}"
uv run pytest tests/stress/ -W ignore
STRESS_STATUS=$?

if [ $STRESS_STATUS -eq 0 ]; then
    echo -e "${GREEN}✓ Stress Tests Passed${NC}"
else
    echo -e "${RED}✗ Stress Tests Failed${NC}"
    exit 1
fi

# 7. Docker Build Verification (if Docker is available)
if command -v docker &> /dev/null && docker info &> /dev/null; then
    echo -e "\n${BLUE}[7/7] Verifying Docker Build...${NC}"
    docker build -t monte-neo-test -f docker/Dockerfile .
    echo -e "${GREEN}✓ Docker Build Successfully${NC}"
else
    echo -e "\n${BLUE}[7/7] Docker daemon not running or not found, skipping build verification.${NC}"
fi

echo -e "\n${BLUE}===============================================${NC}"
echo -e "${GREEN}   All Verification Steps Completed Successfully!  ${NC}"
echo -e "${BLUE}   Coverage report: coverage_html/index.html   ${NC}"
echo -e "${BLUE}===============================================${NC}"
