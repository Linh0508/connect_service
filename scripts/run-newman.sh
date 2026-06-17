#!/bin/bash

# ============================================================
# Script chạy Newman test cho B6 Core Business API
# ============================================================

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Cấu hình - ĐÃ SỬA ĐƯỜNG DẪN ĐÚNG
COLLECTION_FILE="postman/collections/core-business.postman_collection.json"
ENVIRONMENT_FILE="postman/environments/environment_local.json"
REPORT_DIR="reports"
BASE_URL=${BASE_URL:-"http://localhost:8000"}

mkdir -p $REPORT_DIR

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}     B6 API - Newman Test Runner       ${NC}"
echo -e "${GREEN}========================================${NC}"

if ! command -v newman &> /dev/null; then
    echo -e "${YELLOW}Newman not found. Installing...${NC}"
    npm install -g newman newman-reporter-junit newman-reporter-htmlextra
fi

if [ ! -f "$COLLECTION_FILE" ]; then
    echo -e "${RED}Error: Collection file $COLLECTION_FILE not found!${NC}"
    exit 1
fi

if [ ! -f "$ENVIRONMENT_FILE" ]; then
    echo -e "${YELLOW}Warning: Environment file $ENVIRONMENT_FILE not found.${NC}"
    ENV_PARAM=""
else
    ENV_PARAM="-e $ENVIRONMENT_FILE"
fi

echo -e "${GREEN}Base URL: $BASE_URL${NC}"
echo -e "${GREEN}Collection: $COLLECTION_FILE${NC}"
echo ""

echo -e "${YELLOW}Running tests...${NC}"

newman run "$COLLECTION_FILE" \
    $ENV_PARAM \
    --global-var "baseUrl=$BASE_URL" \
    --reporters junit,htmlextra,cli \
    --reporter-junit-export "$REPORT_DIR/newman-report-local.xml" \
    --reporter-htmlextra-export "$REPORT_DIR/newman-report-local.html" \
    --timeout-request 5000 \
    --timeout-script 2000

if [ $? -eq 0 ]; then
    echo ""
    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}✓ All tests passed!${NC}"
    echo -e "${GREEN}Reports saved to: $REPORT_DIR/${NC}"
    echo -e "${GREEN}========================================${NC}"
else
    echo ""
    echo -e "${RED}========================================${NC}"
    echo -e "${RED}✗ Some tests failed!${NC}"
    echo -e "${RED}Check reports in: $REPORT_DIR/${NC}"
    echo -e "${RED}========================================${NC}"
    exit 1
fi