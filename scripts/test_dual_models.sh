#!/bin/bash
# Test script for dual vLLM models (MEDIUM + SMALL)

set -e

GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

MEDIUM_URL="http://localhost:8001"
SMALL_URL="http://localhost:8002"

echo -e "${BLUE}╔═══════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║      Dual vLLM Models Test Suite                         ║${NC}"
echo -e "${BLUE}║      MEDIUM model (8001) + SMALL model (8002)            ║${NC}"
echo -e "${BLUE}╚═══════════════════════════════════════════════════════════╝${NC}"
echo ""

# Function to check model health
check_health() {
    local url=$1
    local name=$2
    
    echo -e "${YELLOW}Checking $name health...${NC}"
    if curl -sf "$url/health" > /dev/null; then
        echo -e "${GREEN}✓ $name is healthy${NC}"
        return 0
    else
        echo -e "${RED}✗ $name is not responding${NC}"
        return 1
    fi
}

# Function to test model
test_model() {
    local url=$1
    local model=$2
    local name=$3
    local prompt=$4
    
    echo -e "\n${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}Testing: $name${NC}"
    echo -e "${BLUE}Model: $model${NC}"
    echo -e "${BLUE}Prompt: $prompt${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    
    local start_time=$(date +%s%N)
    
    response=$(curl -s -X POST "$url/v1/chat/completions" \
        -H "Content-Type: application/json" \
        -d "{
            \"model\": \"$model\",
            \"messages\": [{\"role\": \"user\", \"content\": \"$prompt\"}],
            \"temperature\": 0.7,
            \"max_tokens\": 150
        }")
    
    local end_time=$(date +%s%N)
    local duration=$(( (end_time - start_time) / 1000000 ))
    
    if echo "$response" | jq -e '.choices[0].message.content' > /dev/null 2>&1; then
        echo -e "${GREEN}✓ Response received in ${duration}ms${NC}"
        echo -e "\n${YELLOW}Response:${NC}"
        echo "$response" | jq -r '.choices[0].message.content'
        
        # Extract usage stats if available
        if echo "$response" | jq -e '.usage' > /dev/null 2>&1; then
            echo -e "\n${YELLOW}Usage Stats:${NC}"
            echo "$response" | jq '.usage'
        fi
        
        return 0
    else
        echo -e "${RED}✗ Failed to get response${NC}"
        echo -e "${RED}Error: $response${NC}"
        return 1
    fi
}

# Function to compare models
compare_models() {
    local prompt=$1
    
    # Get actual model names from environment or use defaults
    MEDIUM_MODEL="${VLLM_MODEL_MEDIUM:-OpenGPT/gpt-oss-20b}"
    SMALL_MODEL="${VLLM_MODEL_SMALL:-mistralai/Mistral-7B-Instruct-v0.3}"
    
    echo -e "\n${BLUE}╔═══════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║      Comparing models on same prompt                      ║${NC}"
    echo -e "${BLUE}╚═══════════════════════════════════════════════════════════╝${NC}"
    
    test_model "$MEDIUM_URL" "$MEDIUM_MODEL" "MEDIUM model" "$prompt"
    test_model "$SMALL_URL" "$SMALL_MODEL" "SMALL model" "$prompt"
}

# Main test suite
main() {
    echo -e "${YELLOW}Step 1: Health checks${NC}"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    
    medium_healthy=0
    small_healthy=0
    
    check_health "$MEDIUM_URL" "MEDIUM model" && medium_healthy=1 || true
    check_health "$SMALL_URL" "SMALL model" && small_healthy=1 || true
    
    if [ $medium_healthy -eq 0 ] || [ $small_healthy -eq 0 ]; then
        echo -e "\n${RED}⚠️  Some models are not healthy. Exiting...${NC}"
        echo -e "${YELLOW}Tip: Check logs with 'make logs-dual-models'${NC}"
        exit 1
    fi
    
    echo -e "\n${YELLOW}Step 2: Check model endpoints${NC}"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    
    echo -e "${BLUE}MEDIUM model endpoint:${NC}"
    curl -s "$MEDIUM_URL/v1/models" | jq '.'
    
    echo -e "\n${BLUE}SMALL model endpoint:${NC}"
    curl -s "$SMALL_URL/v1/models" | jq '.'
    
    echo -e "\n${YELLOW}Step 3: Simple test${NC}"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    
    # Get actual model names from environment or use defaults
    MEDIUM_MODEL="${VLLM_MODEL_MEDIUM:-OpenGPT/gpt-oss-20b}"
    SMALL_MODEL="${VLLM_MODEL_SMALL:-mistralai/Mistral-7B-Instruct-v0.3}"
    
    test_model "$MEDIUM_URL" "$MEDIUM_MODEL" "MEDIUM model" "What is 2+2?"
    test_model "$SMALL_URL" "$SMALL_MODEL" "SMALL model" "What is 2+2?"
    
    echo -e "\n${YELLOW}Step 4: Coding test${NC}"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    
    compare_models "Write a Python function to calculate factorial."
    
    echo -e "\n${YELLOW}Step 5: Reasoning test${NC}"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    
    compare_models "Explain the difference between supervised and unsupervised learning."
    
    echo -e "\n${GREEN}╔═══════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║      All tests completed!                                 ║${NC}"
    echo -e "${GREEN}╚═══════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "${BLUE}Model Comparison Summary:${NC}"
    echo -e "  ${YELLOW}MEDIUM model (port 8001):${NC} Better for complex reasoning, longer contexts"
    echo -e "  ${YELLOW}SMALL model (port 8002):${NC} Faster, good for code and simple queries"
    echo ""
    echo -e "${BLUE}AnythingLLM Configuration:${NC}"
    echo -e "  For MEDIUM model: http://localhost:8001/v1"
    echo -e "  For SMALL model:  http://localhost:8002/v1"
}

# Run main function
main

