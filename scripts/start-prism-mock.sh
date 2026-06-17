#!/bin/bash

# ============================================================
# Script khởi động Prism Mock Server cho B6 Core Business API
# ============================================================

set -e

# Màu sắc cho terminal
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Cấu hình
OPENAPI_FILE="contracts/core-business.openapi.yaml"
PRISM_PORT=${PRISM_PORT:-4010}
PRISM_HOST="localhost"

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  B6 Core Business - Prism Mock Server  ${NC}"
echo -e "${GREEN}========================================${NC}"

# Kiểm tra file openapi.yaml tồn tại
if [ ! -f "$OPENAPI_FILE" ]; then
    echo -e "${RED}Error: File $OPENAPI_FILE not found!${NC}"
    echo -e "${YELLOW}Please ensure openapi.yaml is in the current directory.${NC}"
    exit 1
fi

# Kiểm tra Prism đã được cài đặt chưa
if ! command -v prism &> /dev/null; then
    echo -e "${YELLOW}Prism not found. Installing...${NC}"
    npm install -g @stoplight/prism-cli
fi

echo -e "${GREEN}Starting Prism mock server on port $PRISM_PORT...${NC}"
echo -e "${YELLOW}OpenAPI file: $OPENAPI_FILE${NC}"
echo -e "${YELLOW}Mock server will be available at: http://$PRISM_HOST:$PRISM_PORT${NC}"
echo ""
echo -e "${GREEN}Available endpoints:${NC}"
echo "  POST   http://$PRISM_HOST:$PRISM_PORT/access/check"
echo "  GET    http://$PRISM_HOST:$PRISM_PORT/policies/access/{policyId}"
echo "  GET    http://$PRISM_HOST:$PRISM_PORT/decisions/{decisionId}"
echo "  POST   http://$PRISM_HOST:$PRISM_PORT/cache/invalidate/{policyId}"
echo "  POST   http://$PRISM_HOST:$PRISM_PORT/internal/evaluate-sensor"
echo "  POST   http://$PRISM_HOST:$PRISM_PORT/evaluate-detection"
echo "  GET    http://$PRISM_HOST:$PRISM_PORT/internal/access-logs"
echo "  GET    http://$PRISM_HOST:$PRISM_PORT/internal/gates/{gateId}/status"
echo "  GET    http://$PRISM_HOST:$PRISM_PORT/health"
echo ""
echo -e "${YELLOW}Press Ctrl+C to stop the server${NC}"
echo ""

# Chạy Prism mock server
prism mock -p $PRISM_PORT $OPENAPI_FILE