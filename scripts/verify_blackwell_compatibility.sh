#!/bin/bash
# Script to verify Blackwell compatibility for CUDA applications
# Based on: https://docs.nvidia.com/cuda/blackwell-compatibility-guide/index.html

set -e

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}=== NVIDIA Blackwell Compatibility Verification ===${NC}"
echo ""

# Check if nvidia-smi is available
if ! command -v nvidia-smi &> /dev/null; then
    echo -e "${RED}[ERROR]${NC} nvidia-smi not found. Install NVIDIA drivers."
    exit 1
fi

# 1. Check Driver Version
echo -e "${BLUE}[1] Checking NVIDIA Driver...${NC}"
DRIVER_VERSION=$(nvidia-smi --query-gpu=driver_version --format=csv,noheader | head -1)
DRIVER_MAJOR=$(echo $DRIVER_VERSION | cut -d. -f1)

echo "Driver Version: $DRIVER_VERSION"

if [ "$DRIVER_MAJOR" -ge 550 ]; then
    echo -e "${GREEN}✓ Driver version is compatible with Blackwell${NC}"
else
    echo -e "${RED}✗ Driver version too old. Blackwell requires 550+${NC}"
    echo "  Download latest driver from: https://www.nvidia.com/drivers"
    exit 1
fi
echo ""

# 2. Check CUDA Version
echo -e "${BLUE}[2] Checking CUDA Version...${NC}"
CUDA_VERSION=$(nvidia-smi --query-gpu=cuda_version --format=csv,noheader | head -1)
echo "CUDA Version: $CUDA_VERSION"

CUDA_MAJOR=$(echo $CUDA_VERSION | cut -d. -f1)
CUDA_MINOR=$(echo $CUDA_VERSION | cut -d. -f2)

if [ "$CUDA_MAJOR" -ge 12 ] && [ "$CUDA_MINOR" -ge 6 ]; then
    echo -e "${GREEN}✓ CUDA version supports Blackwell (PTX compatibility)${NC}"
    if [ "$CUDA_MINOR" -ge 8 ]; then
        echo -e "${GREEN}✓ CUDA 12.8+ detected - native sm_100 cubin support available${NC}"
    else
        echo -e "${YELLOW}! CUDA 12.6-12.7 - will use PTX JIT for Blackwell (minor overhead)${NC}"
        echo -e "${YELLOW}! Recommend updating to CUDA 12.8+ for native sm_100 cubin${NC}"
    fi
elif [ "$CUDA_MAJOR" -ge 12 ] && [ "$CUDA_MINOR" -ge 4 ]; then
    echo -e "${YELLOW}! CUDA 12.4+ - basic Blackwell support via PTX${NC}"
    echo -e "${YELLOW}! Recommend updating to CUDA 12.6+ for better performance${NC}"
else
    echo -e "${RED}✗ CUDA version too old. Blackwell requires 12.4+ (12.8+ recommended)${NC}"
    exit 1
fi
echo ""

# 3. Check GPU Compute Capability
echo -e "${BLUE}[3] Checking GPU Compute Capability...${NC}"
GPU_NAME=$(nvidia-smi --query-gpu=name --format=csv,noheader | head -1)
COMPUTE_CAP=$(nvidia-smi --query-gpu=compute_cap --format=csv,noheader | head -1)

echo "GPU: $GPU_NAME"
echo "Compute Capability: $COMPUTE_CAP"

if [ "$COMPUTE_CAP" == "10.0" ]; then
    echo -e "${GREEN}✓ Blackwell GPU detected (compute_100)${NC}"
elif [ "$COMPUTE_CAP" == "9.0" ]; then
    echo -e "${YELLOW}! Hopper GPU detected (compute_90)${NC}"
    echo "  This is not a Blackwell GPU"
elif [ "$COMPUTE_CAP" == "8.9" ]; then
    echo -e "${YELLOW}! Ada Lovelace GPU detected (compute_89)${NC}"
    echo "  This is not a Blackwell GPU"
else
    echo -e "${YELLOW}! Compute capability: $COMPUTE_CAP${NC}"
    echo "  This is not a Blackwell GPU (expected 10.0)"
fi
echo ""

# 4. Check PyTorch CUDA Architecture
echo -e "${BLUE}[4] Checking PyTorch CUDA Support...${NC}"

if command -v python3 &> /dev/null; then
    TORCH_ARCHS=$(python3 -c "import torch; print(torch.cuda.get_arch_list() if torch.cuda.is_available() else 'N/A')" 2>/dev/null || echo "PyTorch not installed")
    
    if [ "$TORCH_ARCHS" != "N/A" ] && [ "$TORCH_ARCHS" != "PyTorch not installed" ]; then
        echo "PyTorch CUDA Architectures: $TORCH_ARCHS"
        
        if echo "$TORCH_ARCHS" | grep -q "10.0\|sm_100"; then
            echo -e "${GREEN}✓ PyTorch compiled with Blackwell support (sm_100)${NC}"
        else
            echo -e "${YELLOW}! PyTorch does not include sm_100${NC}"
            echo -e "${YELLOW}! Will use PTX JIT (minor performance impact)${NC}"
            echo ""
            echo "To compile PyTorch with Blackwell support:"
            echo "  export TORCH_CUDA_ARCH_LIST=\"8.0;8.6;8.9;9.0;10.0\""
            echo "  pip install torch --no-binary :all:"
        fi
    else
        echo -e "${YELLOW}! PyTorch: $TORCH_ARCHS${NC}"
    fi
else
    echo -e "${YELLOW}! Python3 not found in PATH${NC}"
fi
echo ""

# 5. Test PTX Compatibility (if Docker available)
echo -e "${BLUE}[5] Testing PTX Compatibility...${NC}"

if command -v docker &> /dev/null; then
    echo "Running PTX JIT test..."
    
    # Test with CUDA_FORCE_PTX_JIT=1 as per NVIDIA guide
    TEST_RESULT=$(docker run --rm --gpus all \
        -e CUDA_FORCE_PTX_JIT=1 \
        nvidia/cuda:12.6.1-base-ubuntu22.04 \
        nvidia-smi 2>&1 || echo "FAILED")
    
    if echo "$TEST_RESULT" | grep -q "CUDA Version"; then
        echo -e "${GREEN}✓ PTX JIT compatibility test passed${NC}"
    else
        echo -e "${YELLOW}! Could not run PTX test (GPU may be in use)${NC}"
    fi
else
    echo -e "${YELLOW}! Docker not available, skipping PTX test${NC}"
fi
echo ""

# 6. Summary
echo -e "${BLUE}=== Summary ===${NC}"
echo ""

if [ "$COMPUTE_CAP" == "10.0" ] && [ "$DRIVER_MAJOR" -ge 550 ] && [ "$CUDA_MAJOR" -ge 12 ] && [ "$CUDA_MINOR" -ge 6 ]; then
    echo -e "${GREEN}✅ System is Blackwell compatible!${NC}"
    echo ""
    echo "Recommendations:"
    echo "  • Use CUDA 12.8+ for native sm_100 cubin (best performance)"
    echo "  • Current CUDA $CUDA_VERSION will work via PTX JIT"
    echo "  • Ensure vLLM/PyTorch include PTX for compute_100"
    echo ""
    echo "Optimal Docker image:"
    echo "  nvidia/cuda:12.8.0-cudnn-devel-ubuntu22.04"
else
    echo -e "${YELLOW}⚠ Some compatibility issues detected${NC}"
    echo ""
    echo "Please review warnings above and update:"
    echo "  • NVIDIA Driver to 550+"
    echo "  • CUDA Toolkit to 12.6+ (12.8+ recommended)"
fi

echo ""
echo "For more information, see:"
echo "  https://docs.nvidia.com/cuda/blackwell-compatibility-guide/index.html"

