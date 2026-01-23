#!/bin/bash
# Comprehensive Test Suite Runner for Monte-Neo
# Version: 0.0.1

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
echo -e "\n${BLUE}[1/5] Cleaning environment...${NC}"
rm -rf .pytest_cache coverage_html .coverage
mkdir -p coverage_html

# 2. Run Unit Tests with Coverage
echo -e "\n${BLUE}[2/5] Running Unit Tests & Coverage...${NC}"
PYTHONPATH=src pytest tests/unit/ --cov=src/monte_neo --cov-report=html:coverage_html --cov-report=term
UNIT_STATUS=$?

if [ $UNIT_STATUS -eq 0 ]; then
    echo -e "${GREEN}✓ Unit Tests Passed${NC}"
else
    echo -e "${RED}✗ Unit Tests Failed${NC}"
    exit 1
fi

# 3. Run Integration Tests
echo -e "\n${BLUE}[3/5] Running Integration Tests...${NC}"
PYTHONPATH=src pytest tests/integration/
INTEG_STATUS=$?

if [ $INTEG_STATUS -eq 0 ]; then
    echo -e "${GREEN}✓ Integration Tests Passed${NC}"
else
    echo -e "${RED}✗ Integration Tests Failed${NC}"
    exit 1
fi

# 4. Run Stress Tests
echo -e "\n${BLUE}[4/5] Running Stress & Performance Tests...${NC}"
PYTHONPATH=src pytest tests/stress/
STRESS_STATUS=$?

if [ $STRESS_STATUS -eq 0 ]; then
    echo -e "${GREEN}✓ Stress Tests Passed${NC}"
else
    echo -e "${RED}✗ Stress Tests Failed${NC}"
    exit 1
fi

# 5. Docker Build Verification (if Docker is available)
if command -v docker &> /dev/null; then
    echo -e "\n${BLUE}[5/5] Verifying Docker Build...${NC}"
    docker build -t monte-neo-test -f docker/Dockerfile .
    echo -e "${GREEN}✓ Docker Build Successfully${NC}"
else
    echo -e "\n${RED}[5/5] Docker not found, skipping build verification.${NC}"
fi

echo -e "\n${BLUE}===============================================${NC}"
echo -e "${GREEN}   All Verification Steps Completed Successfully!  ${NC}"
echo -e "${BLUE}   Coverage report: coverage_html/index.html   ${NC}"
echo -e "${BLUE}===============================================${NC}"
