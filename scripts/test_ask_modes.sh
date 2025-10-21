#!/bin/bash
# Test script for /ask modes (auto, normal, summarize, detailed)

set -e

GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${BLUE}=== Testing /ask Modes ===${NC}"
echo ""

# Check backend
if ! curl -s http://localhost:8000/health > /dev/null 2>&1; then
    echo -e "${YELLOW}Backend not running. Please start with: make up${NC}"
    exit 1
fi

SPACE="space_demo"
QUESTION="Какие дедлайны прошли по проекту?"

echo -e "${BLUE}Question: ${QUESTION}${NC}"
echo -e "${BLUE}Space: ${SPACE}${NC}"
echo ""

# Test mode: auto
echo -e "${GREEN}[1] Testing mode: auto${NC}"
AUTO_RESPONSE=$(curl -s -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d "{
    \"q\": \"${QUESTION}\",
    \"space_id\": \"${SPACE}\",
    \"mode\": \"auto\",
    \"top_k\": 10
  }")

AUTO_MODE=$(echo $AUTO_RESPONSE | jq -r '.mode')
AUTO_SUMMARIZED=$(echo $AUTO_RESPONSE | jq -r '.summarized')
AUTO_CONTEXT=$(echo $AUTO_RESPONSE | jq -r '.context_tokens')

echo "  Mode: $AUTO_MODE"
echo "  Summarized: $AUTO_SUMMARIZED"
echo "  Context tokens: $AUTO_CONTEXT"
echo ""

# Test mode: normal
echo -e "${GREEN}[2] Testing mode: normal${NC}"
NORMAL_RESPONSE=$(curl -s -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d "{
    \"q\": \"${QUESTION}\",
    \"space_id\": \"${SPACE}\",
    \"mode\": \"normal\",
    \"top_k\": 10
  }")

NORMAL_MODE=$(echo $NORMAL_RESPONSE | jq -r '.mode')
NORMAL_SUMMARIZED=$(echo $NORMAL_RESPONSE | jq -r '.summarized')

echo "  Mode: $NORMAL_MODE"
echo "  Summarized: $NORMAL_SUMMARIZED (should be false)"
echo ""

# Test mode: summarize
echo -e "${GREEN}[3] Testing mode: summarize${NC}"
SUMMARIZE_RESPONSE=$(curl -s -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d "{
    \"q\": \"${QUESTION}\",
    \"space_id\": \"${SPACE}\",
    \"mode\": \"summarize\",
    \"top_k\": 10
  }")

SUMMARIZE_MODE=$(echo $SUMMARIZE_RESPONSE | jq -r '.mode')
SUMMARIZE_SUMMARIZED=$(echo $SUMMARIZE_RESPONSE | jq -r '.summarized')

echo "  Mode: $SUMMARIZE_MODE"
echo "  Summarized: $SUMMARIZE_SUMMARIZED (should be true)"
echo ""

# Test mode: detailed
echo -e "${GREEN}[4] Testing mode: detailed${NC}"
DETAILED_RESPONSE=$(curl -s -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d "{
    \"q\": \"${QUESTION}\",
    \"space_id\": \"${SPACE}\",
    \"mode\": \"detailed\",
    \"top_k\": 10
  }")

DETAILED_MODE=$(echo $DETAILED_RESPONSE | jq -r '.mode')
DETAILED_SUMMARIZED=$(echo $DETAILED_RESPONSE | jq -r '.summarized')

echo "  Mode: $DETAILED_MODE"
echo "  Summarized: $DETAILED_SUMMARIZED (should be false)"
echo ""

# Test invalid mode (graceful fallback)
echo -e "${GREEN}[5] Testing invalid mode (should fallback to 'auto')${NC}"
INVALID_RESPONSE=$(curl -s -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d "{
    \"q\": \"${QUESTION}\",
    \"space_id\": \"${SPACE}\",
    \"mode\": \"invalid_mode\",
    \"top_k\": 5
  }")

INVALID_MODE=$(echo $INVALID_RESPONSE | jq -r '.mode')

echo "  Mode returned: $INVALID_MODE (should be 'auto')"
echo ""

# Summary
echo -e "${BLUE}=== Test Summary ===${NC}"
echo ""
echo "Mode behavior:"
echo "  auto:      ${AUTO_MODE} (summarized: ${AUTO_SUMMARIZED})"
echo "  normal:    ${NORMAL_MODE} (summarized: ${NORMAL_SUMMARIZED})"
echo "  summarize: ${SUMMARIZE_MODE} (summarized: ${SUMMARIZE_SUMMARIZED})"
echo "  detailed:  ${DETAILED_MODE} (summarized: ${DETAILED_SUMMARIZED})"
echo "  invalid:   ${INVALID_MODE} (fallback to auto)"
echo ""

# Validation
if [ "$NORMAL_SUMMARIZED" == "false" ] && [ "$SUMMARIZE_SUMMARIZED" == "true" ]; then
    echo -e "${GREEN}✅ All mode tests passed!${NC}"
else
    echo -e "${YELLOW}⚠ Some unexpected behavior detected${NC}"
fi

echo ""
echo "Try modes yourself:"
echo "  curl -X POST http://localhost:8000/ask -d '{\"q\":\"test\",\"mode\":\"summarize\"}'"

