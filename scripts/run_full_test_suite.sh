#!/bin/bash
# Comprehensive Test Suite Runner for Monte-Neo
# Version: v0.0.5

set -e

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}===============================================${NC}"
echo -e "${BLUE}   Monte-Neo Full Test & Verification Suite    ${NC}"
echo -e "${BLUE}===============================================${NC}"

# 1. Phase 1: Environment & System Check
echo -e "\n${BLUE}[1/10] Phase 1: Environment & System Check...${NC}"
uv run scripts/check_system.py

# 2. Phase 2: Cleaning environment
echo -e "\n${BLUE}[2/10] Phase 2: Cleaning environment...${NC}"
rm -rf .pytest_cache coverage_html .coverage .mypy_cache .ruff_cache *.png
mkdir -p coverage_html

# 3. Phase 3: Static Analysis
echo -e "\n${BLUE}[3/10] Phase 3: Static Analysis...${NC}"
echo -e "${BLUE}Running Linter (Ruff)...${NC}"
if uv run ruff check . --fix; then
    echo -e "${GREEN}✓ Linting Passed${NC}"
else
    echo -e "${RED}✗ Linting Failed${NC}"
    exit 1
fi

echo -e "\n${BLUE}Running Type Checker (Mypy)...${NC}"
if uv run mypy src/monte_neo --ignore-missing-imports; then
    echo -e "${GREEN}✓ Type Checking Passed${NC}"
else
    echo -e "${RED}⚠ Type Checking found issues, but continuing...${NC}"
fi

# 4. Phase 4: Core Tests
echo -e "\n${BLUE}[4/10] Phase 4: Core Tests...${NC}"
echo -e "${BLUE}Running Unit Tests & Coverage...${NC}"
uv run pytest tests/unit/ -n auto -W ignore --cov=src/monte_neo --cov-report=html:coverage_html --cov-report=term --cov-config=.coveragerc --dist loadscope

echo -e "\n${BLUE}Running Integration Tests...${NC}"
uv run pytest tests/integration/ -W ignore

echo -e "\n${BLUE}Running Stress & Performance Tests...${NC}"
uv run pytest tests/stress/ -W ignore

# 5. Phase 5: Hardware Specific Tests (Metal/GPU)
echo -e "\n${BLUE}[5/10] Phase 5: Hardware Specific Tests...${NC}"
echo -e "${BLUE}Testing Metal Pipeline...${NC}"
uv run scripts/test_metal_pipeline.py
echo -e "${BLUE}Testing BB Metal...${NC}"
uv run scripts/test_bb_metal.py
echo -e "${BLUE}Testing Advanced Metal...${NC}"
uv run scripts/test_advanced_metal.py

# 6. Phase 6: Benchmarks
echo -e "\n${BLUE}[6/10] Phase 6: Benchmarks...${NC}"
echo -e "${BLUE}Benchmark Suite...${NC}"
uv run scripts/benchmark_suite.py
echo -e "${BLUE}Benchmark Drivers...${NC}"
uv run scripts/benchmark_drivers.py
echo -e "${BLUE}Benchmark Dynamic...${NC}"
uv run scripts/benchmark_dynamic.py
echo -e "${BLUE}Benchmark GPU...${NC}"
uv run scripts/benchmark_gpu.py
echo -e "${BLUE}Benchmark MC...${NC}"
uv run scripts/benchmark_mc.py

# 7. Phase 7: Verification & Metrics
echo -e "\n${BLUE}[7/10] Phase 7: Verification & Metrics...${NC}"
uv run scripts/verify_metrics.py

# 8. Phase 8: Visualization
echo -e "\n${BLUE}[8/10] Phase 8: Visualization...${NC}"
uv run scripts/visualize_stress_tests.py

# 9. Phase 9: Production Pipeline
echo -e "\n${BLUE}[9/10] Phase 9: Production Pipeline...${NC}"
uv run scripts/production_pipeline.py

# 10. Phase 10: Docker Build Verification
echo -e "\n${BLUE}[10/10] Phase 10: Docker Build Verification...${NC}"
if command -v docker &> /dev/null && docker info &> /dev/null; then
    docker build -t monte-neo-test -f docker/Dockerfile .
    echo -e "${GREEN}✓ Docker Build Successfully${NC}"
else
    echo -e "${BLUE}Docker daemon not running or not found, skipping build verification.${NC}"
fi

echo -e "\n${BLUE}===============================================${NC}"
echo -e "${GREEN}   All Verification Steps Completed Successfully!  ${NC}"
echo -e "${BLUE}   Coverage report: coverage_html/index.html   ${NC}"
echo -e "${BLUE}===============================================${NC}"
