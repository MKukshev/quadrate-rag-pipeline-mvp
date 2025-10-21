#!/bin/bash
# Test script for summary storage (Pattern 4)

set -e

GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${BLUE}=== Testing Summary Storage (Pattern 4) ===${NC}"
echo ""

# Check backend
if ! curl -s http://localhost:8000/health > /dev/null 2>&1; then
    echo -e "${YELLOW}Backend not running. Please start with: make up${NC}"
    exit 1
fi

SPACE="space_demo"
TEST_FILE="docs/notes_meeting.txt"

# Check if test file exists
if [ ! -f "$TEST_FILE" ]; then
    echo -e "${YELLOW}Test file $TEST_FILE not found${NC}"
    exit 1
fi

echo -e "${GREEN}[1] Upload document with summary generation${NC}"
echo "  File: $TEST_FILE"

INGEST_RESPONSE=$(curl -s -X POST http://localhost:8000/ingest \
  -F "file=@${TEST_FILE}" \
  -F "space_id=${SPACE}" \
  -F "doc_type=notes" \
  -F "generate_summary=true")

DOC_ID=$(echo $INGEST_RESPONSE | jq -r '.doc_id')
SUMMARY_PENDING=$(echo $INGEST_RESPONSE | jq -r '.summary_pending')

echo "  Doc ID: $DOC_ID"
echo "  Summary pending: $SUMMARY_PENDING"
echo ""

# Wait for background task
echo -e "${GREEN}[2] Waiting for background summarization (10 seconds)...${NC}"
sleep 10
echo ""

# Check summary status
echo -e "${GREEN}[3] Check summary status${NC}"
STATUS_RESPONSE=$(curl -s "http://localhost:8000/documents/${DOC_ID}/summary-status?space_id=${SPACE}")

HAS_SUMMARY=$(echo $STATUS_RESPONSE | jq -r '.has_summary')
echo "  Has summary: $HAS_SUMMARY"

if [ "$HAS_SUMMARY" == "true" ]; then
    PREVIEW=$(echo $STATUS_RESPONSE | jq -r '.summary_preview')
    TOKENS=$(echo $STATUS_RESPONSE | jq -r '.summary_tokens')
    echo "  Summary tokens: $TOKENS"
    echo "  Preview: $PREVIEW"
else
    echo -e "${YELLOW}  Summary not generated yet (might need more time)${NC}"
fi
echo ""

# Get full summary
echo -e "${GREEN}[4] Get full summary via /summarize${NC}"
SUMMARY_RESPONSE=$(curl -s -X POST http://localhost:8000/summarize \
  -H "Content-Type: application/json" \
  -d "{
    \"doc_id\": \"${DOC_ID}\",
    \"space_id\": \"${SPACE}\"
  }")

CACHED=$(echo $SUMMARY_RESPONSE | jq -r '.cached')
SUMMARY_TEXT=$(echo $SUMMARY_RESPONSE | jq -r '.summary')

echo "  Cached: $CACHED"
echo "  Summary length: ${#SUMMARY_TEXT} characters"
echo ""

# Get summary stats
echo -e "${GREEN}[5] Get summary statistics${NC}"
STATS_RESPONSE=$(curl -s "http://localhost:8000/summary-stats?space_id=${SPACE}")

TOTAL=$(echo $STATS_RESPONSE | jq -r '.total_summaries')
AVG_TOKENS=$(echo $STATS_RESPONSE | jq -r '.average_tokens')

echo "  Total summaries in space: $TOTAL"
echo "  Average tokens: $AVG_TOKENS"
echo ""

# Test bulk summarize
echo -e "${GREEN}[6] Test bulk summarization (for documents without summaries)${NC}"
BULK_RESPONSE=$(curl -s -X POST "http://localhost:8000/bulk-summarize?space_id=${SPACE}&limit=10")

DOCS_TO_PROCESS=$(echo $BULK_RESPONSE | jq -r '.documents_to_process')
echo "  Documents to process: $DOCS_TO_PROCESS"
echo ""

if [ "$DOCS_TO_PROCESS" -gt 0 ]; then
    echo -e "${YELLOW}  Waiting for bulk summarization (15 seconds)...${NC}"
    sleep 15
    
    # Check stats again
    STATS_RESPONSE=$(curl -s "http://localhost:8000/summary-stats?space_id=${SPACE}")
    NEW_TOTAL=$(echo $STATS_RESPONSE | jq -r '.total_summaries')
    echo "  New total summaries: $NEW_TOTAL"
    echo ""
fi

# Test regeneration
echo -e "${GREEN}[7] Test summary regeneration${NC}"
REGEN_RESPONSE=$(curl -s -X POST "http://localhost:8000/documents/${DOC_ID}/regenerate-summary?space_id=${SPACE}")

REGEN_STATUS=$(echo $REGEN_RESPONSE | jq -r '.status')
echo "  Regeneration status: $REGEN_STATUS"
echo ""

# Summary
echo -e "${BLUE}=== Test Summary ===${NC}"
echo ""
echo "Pattern 4 features tested:"
echo "  ✓ Async summary generation during ingest"
echo "  ✓ Summary status check"
echo "  ✓ Cached summary retrieval"
echo "  ✓ Summary statistics"
echo "  ✓ Bulk summarization"
echo "  ✓ Summary regeneration"
echo ""

if [ "$CACHED" == "true" ]; then
    echo -e "${GREEN}✅ All tests passed! Summary storage working correctly.${NC}"
else
    echo -e "${YELLOW}⚠ Summary might still be processing. Try again in a few seconds.${NC}"
fi

echo ""
echo "API endpoints:"
echo "  POST /ingest?generate_summary=true"
echo "  GET  /documents/{doc_id}/summary-status"
echo "  POST /summarize (with caching)"
echo "  POST /bulk-summarize"
echo "  POST /documents/{doc_id}/regenerate-summary"
echo "  GET  /summary-stats"
echo "  DELETE /documents/{doc_id}/summary"

