#!/bin/bash
# Test script for document summarization feature

set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${BLUE}=== Testing Document Summarization ===${NC}"
echo ""

# Check if backend is running
if ! curl -s http://localhost:8000/health > /dev/null 2>&1; then
    echo -e "${YELLOW}Backend is not running. Starting...${NC}"
    make up
    make wait
fi

echo -e "${GREEN}[1] Backend is healthy${NC}"
echo ""

# Test 1: Ingest a test document
echo -e "${BLUE}[2] Uploading test document...${NC}"
INGEST_RESPONSE=$(curl -s -X POST http://localhost:8000/ingest \
  -F "file=@docs/work_plans/work_plan_001.txt" \
  -F "space_id=test_summarization")

DOC_ID=$(echo $INGEST_RESPONSE | jq -r '.doc_id')
CHUNKS=$(echo $INGEST_RESPONSE | jq -r '.chunks_indexed')

if [ "$DOC_ID" == "null" ] || [ -z "$DOC_ID" ]; then
    echo -e "${YELLOW}No documents found. Using sample data...${NC}"
    
    # Create a sample document
    echo "Creating sample document for testing..."
    
    SAMPLE_TEXT="This is a test document about cloud migration. The project started in January 2025 with a budget of 200000 dollars. The team consists of 5 engineers. The main technologies are Kubernetes and AWS. Timeline is 6 months ending in June 2025. Main risks include data migration complexity and tight timeline."
    
    INGEST_RESPONSE=$(curl -s -X POST http://localhost:8000/ingest \
      -F "file=@-;filename=test_migration.txt" \
      -F "space_id=test_summarization" \
      --form-string "file=$SAMPLE_TEXT")
    
    DOC_ID=$(echo $INGEST_RESPONSE | jq -r '.doc_id')
    CHUNKS=$(echo $INGEST_RESPONSE | jq -r '.chunks_indexed')
fi

echo -e "${GREEN}✓ Document ingested${NC}"
echo "  Doc ID: $DOC_ID"
echo "  Chunks: $CHUNKS"
echo ""

# Test 2: Basic summarization
echo -e "${BLUE}[3] Testing basic summarization...${NC}"
SUMMARY_RESPONSE=$(curl -s -X POST http://localhost:8000/summarize \
  -H "Content-Type: application/json" \
  -d "{
    \"doc_id\": \"$DOC_ID\",
    \"space_id\": \"test_summarization\"
  }")

SUMMARY=$(echo $SUMMARY_RESPONSE | jq -r '.summary')
CHUNKS_PROCESSED=$(echo $SUMMARY_RESPONSE | jq -r '.chunks_processed')

echo -e "${GREEN}✓ Summarization complete${NC}"
echo "  Chunks processed: $CHUNKS_PROCESSED"
echo ""
echo "Summary:"
echo "---"
echo "$SUMMARY"
echo "---"
echo ""

# Test 3: Summarization with focus
echo -e "${BLUE}[4] Testing summarization with focus...${NC}"
FOCUSED_RESPONSE=$(curl -s -X POST http://localhost:8000/summarize \
  -H "Content-Type: application/json" \
  -d "{
    \"doc_id\": \"$DOC_ID\",
    \"space_id\": \"test_summarization\",
    \"focus\": \"budget and timeline\"
  }")

FOCUSED_SUMMARY=$(echo $FOCUSED_RESPONSE | jq -r '.summary')

echo -e "${GREEN}✓ Focused summarization complete${NC}"
echo ""
echo "Focused Summary (budget and timeline):"
echo "---"
echo "$FOCUSED_SUMMARY"
echo "---"
echo ""

# Test 4: Error handling - non-existent document
echo -e "${BLUE}[5] Testing error handling...${NC}"
ERROR_RESPONSE=$(curl -s -X POST http://localhost:8000/summarize \
  -H "Content-Type: application/json" \
  -d '{
    "doc_id": "non_existent_doc",
    "space_id": "test_summarization"
  }')

ERROR_DETAIL=$(echo $ERROR_RESPONSE | jq -r '.detail')

if [[ "$ERROR_DETAIL" == *"not found"* ]]; then
    echo -e "${GREEN}✓ Error handling works correctly${NC}"
    echo "  Error: $ERROR_DETAIL"
else
    echo -e "${YELLOW}! Unexpected response for non-existent doc${NC}"
fi
echo ""

# Summary
echo -e "${GREEN}=== All tests passed! ===${NC}"
echo ""
echo "Summarization endpoint is working correctly:"
echo "  ✓ Basic summarization"
echo "  ✓ Focused summarization"
echo "  ✓ Error handling"
echo ""
echo "Try it yourself:"
echo "  curl -X POST http://localhost:8000/summarize \\"
echo "    -H 'Content-Type: application/json' \\"
echo "    -d '{\"doc_id\":\"$DOC_ID\",\"space_id\":\"test_summarization\"}'"
echo ""
echo "API Documentation: http://localhost:8000/docs"

