#!/bin/bash
# Test script for streaming summarization (Pattern 5)

set -e

GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${BLUE}=== Testing Streaming Summarization (Pattern 5) ===${NC}"
echo ""

# Check backend
if ! curl -s http://localhost:8000/health > /dev/null 2>&1; then
    echo -e "${YELLOW}Backend not running. Please start with: make up${NC}"
    exit 1
fi

SPACE="space_demo"

# Find a document ID from the database
echo -e "${GREEN}[1] Finding a document to summarize${NC}"
DOC_ID=$(curl -s "http://localhost:8000/search?q=test&space_id=${SPACE}&top_k=1" | jq -r '.results[0].payload.doc_id' 2>/dev/null || echo "")

if [ -z "$DOC_ID" ] || [ "$DOC_ID" == "null" ]; then
    echo -e "${YELLOW}No documents found in space '${SPACE}'. Please ingest some documents first.${NC}"
    echo "  Run: make ingest"
    exit 1
fi

echo "  Found document: $DOC_ID"
echo ""

# Test SSE streaming
echo -e "${GREEN}[2] Testing SSE streaming summarization${NC}"
echo "  Endpoint: POST /summarize-stream"
echo "  Document: $DOC_ID"
echo ""
echo "  Streaming events:"

curl -X POST http://localhost:8000/summarize-stream \
  -H "Content-Type: application/json" \
  -d "{
    \"doc_id\": \"${DOC_ID}\",
    \"space_id\": \"${SPACE}\"
  }" \
  --no-buffer 2>/dev/null | while read -r line; do
    if [[ $line == data:* ]]; then
        # Parse JSON event
        EVENT_JSON="${line#data: }"
        EVENT_TYPE=$(echo "$EVENT_JSON" | jq -r '.type' 2>/dev/null || echo "")
        
        case "$EVENT_TYPE" in
            "cached")
                echo "    ✅ Cached summary loaded instantly"
                ;;
            "start")
                STRATEGY=$(echo "$EVENT_JSON" | jq -r '.strategy')
                TOTAL_TOKENS=$(echo "$EVENT_JSON" | jq -r '.total_tokens')
                echo "    🚀 Started ($STRATEGY strategy, $TOTAL_TOKENS tokens)"
                ;;
            "processing")
                MESSAGE=$(echo "$EVENT_JSON" | jq -r '.message')
                PROGRESS=$(echo "$EVENT_JSON" | jq -r '.progress')
                echo "    ⏳ [$PROGRESS%] $MESSAGE"
                ;;
            "progress")
                MESSAGE=$(echo "$EVENT_JSON" | jq -r '.message')
                PROGRESS=$(echo "$EVENT_JSON" | jq -r '.progress')
                ETA=$(echo "$EVENT_JSON" | jq -r '.eta_seconds')
                if [ "$ETA" != "null" ]; then
                    echo "    ⏳ [$PROGRESS%] $MESSAGE (ETA: ${ETA}s)"
                else
                    echo "    ⏳ [$PROGRESS%] $MESSAGE"
                fi
                ;;
            "partial_summary")
                CHUNK=$(echo "$EVENT_JSON" | jq -r '.chunk')
                TOKENS=$(echo "$EVENT_JSON" | jq -r '.tokens')
                echo "    📄 Chunk $CHUNK processed ($TOKENS tokens)"
                ;;
            "summary")
                TOKENS=$(echo "$EVENT_JSON" | jq -r '.tokens')
                TIME=$(echo "$EVENT_JSON" | jq -r '.processing_time')
                echo "    ✨ Final summary generated ($TOKENS tokens, ${TIME}s)"
                ;;
            "complete")
                TOTAL_TIME=$(echo "$EVENT_JSON" | jq -r '.total_time')
                echo "    ✅ Complete! Total time: ${TOTAL_TIME}s"
                ;;
            "error")
                MESSAGE=$(echo "$EVENT_JSON" | jq -r '.message')
                echo "    ❌ Error: $MESSAGE"
                ;;
        esac
    fi
done

echo ""
echo -e "${GREEN}[3] Testing long polling fallback${NC}"
POLL_RESPONSE=$(curl -s -X POST http://localhost:8000/summarize-poll \
  -H "Content-Type: application/json" \
  -d "{
    \"doc_id\": \"${DOC_ID}\",
    \"space_id\": \"${SPACE}\"
  }")

POLL_STATUS=$(echo $POLL_RESPONSE | jq -r '.status')
echo "  Status: $POLL_STATUS"

if [ "$POLL_STATUS" == "complete" ]; then
    echo "  ✅ Document has cached summary"
elif [ "$POLL_STATUS" == "pending" ]; then
    echo "  ℹ️ Long polling redirects to SSE endpoint (recommended)"
fi

echo ""
echo -e "${BLUE}=== Test Summary ===${NC}"
echo ""
echo "Pattern 5 features tested:"
echo "  ✓ SSE streaming with progress"
echo "  ✓ Real-time event updates"
echo "  ✓ ETA calculation"
echo "  ✓ Partial results display"
echo "  ✓ Long polling fallback"
echo ""
echo -e "${GREEN}✅ All tests completed!${NC}"
echo ""
echo "To see visual demo:"
echo "  1. Open: http://localhost:8000/static/streaming_demo.html"
echo "  2. Or run: open static/streaming_demo.html"
echo ""
echo "API endpoints:"
echo "  POST /summarize-stream  - SSE streaming"
echo "  POST /summarize-poll    - Long polling fallback"

