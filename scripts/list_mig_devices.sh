#!/bin/bash
# Script to list available MIG devices and their UUIDs

set -e

# Colors
BLUE='\033[0;34m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${BLUE}=== NVIDIA MIG Device Information ===${NC}"
echo ""

# Check if nvidia-smi is available
if ! command -v nvidia-smi &> /dev/null; then
    echo -e "${YELLOW}nvidia-smi not found${NC}"
    exit 1
fi

# Check MIG mode
echo -e "${GREEN}MIG Mode Status:${NC}"
nvidia-smi --query-gpu=index,name,mig.mode.current --format=csv
echo ""

# List GPU instances
echo -e "${GREEN}GPU Instances:${NC}"
nvidia-smi mig -lgi 2>/dev/null || echo "No MIG instances found or MIG not enabled"
echo ""

# List compute instances
echo -e "${GREEN}Compute Instances:${NC}"
nvidia-smi mig -lci 2>/dev/null || echo "No compute instances found"
echo ""

# List MIG devices with UUIDs
echo -e "${GREEN}MIG Device UUIDs:${NC}"
nvidia-smi -L | grep MIG || echo "No MIG devices found"
echo ""

# Show detailed GPU info
echo -e "${GREEN}Detailed GPU Information:${NC}"
nvidia-smi --query-gpu=index,name,memory.total,mig.mode.current --format=csv
echo ""

# Available MIG profiles
echo -e "${GREEN}Available MIG Profiles for your GPU:${NC}"
echo ""
echo "Profile     | VRAM  | Instances | Use Case"
echo "------------|-------|-----------|----------------------------------"
echo "1g.12gb     | 12GB  | 7 max     | Small models (Llama-7B)"
echo "2g.24gb     | 24GB  | 3 max     | Medium models (Llama-13B)"
echo "3g.40gb     | 40GB  | 2 max     | Large models (Llama-70B with quant)"
echo "4g.48gb     | 48GB  | 1 max     | Very large models"
echo "7g.96gb     | 96GB  | 1 max     | Full GPU (no partitioning)"
echo ""

# Show which profile to use
echo -e "${YELLOW}Recommended profiles for common models:${NC}"
echo "  Llama-3.1-8B:  1g.12gb or 2g.24gb"
echo "  Llama-3.1-70B: 3g.40gb or 4g.48gb (with AWQ/GPTQ)"
echo "  Mixtral-8x7B:  3g.40gb or 7g.96gb"
echo ""

# Instructions
echo -e "${BLUE}To setup MIG:${NC}"
echo "  sudo ./scripts/setup_mig.sh"
echo ""
echo -e "${BLUE}To use a specific profile:${NC}"
echo "  export MIG_PROFILE=3g.40gb"
echo "  export MIG_INSTANCE_COUNT=2"
echo "  sudo ./scripts/setup_mig.sh"

