#!/bin/bash
# Script to setup NVIDIA MIG on RTX 6000 Ada for vLLM
# Requires root/sudo access

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if running as root
if [[ $EUID -ne 0 ]]; then
   print_error "This script must be run as root (use sudo)"
   exit 1
fi

print_info "NVIDIA MIG Setup Script for RTX 6000 Ada"
echo ""

# Check if nvidia-smi is available
if ! command -v nvidia-smi &> /dev/null; then
    print_error "nvidia-smi not found. Install NVIDIA drivers first."
    exit 1
fi

# Detect GPU
print_info "Detecting NVIDIA GPUs..."
nvidia-smi -L

# Get MIG profile from environment or use default
MIG_PROFILE="${MIG_PROFILE:-3g.40gb}"
MIG_INSTANCE_COUNT="${MIG_INSTANCE_COUNT:-2}"
GPU_ID="${GPU_ID:-0}"

print_info "Configuration:"
echo "  GPU ID: ${GPU_ID}"
echo "  MIG Profile: ${MIG_PROFILE}"
echo "  Instance Count: ${MIG_INSTANCE_COUNT}"
echo ""

# Check MIG mode status
print_info "Checking current MIG mode..."
MIG_MODE=$(nvidia-smi -i ${GPU_ID} --query-gpu=mig.mode.current --format=csv,noheader)

if [ "$MIG_MODE" != "Enabled" ]; then
    print_warning "MIG mode is not enabled. Enabling MIG mode..."
    
    # Enable MIG mode
    nvidia-smi -i ${GPU_ID} -mig 1
    
    print_success "MIG mode enabled"
    print_warning "GPU reset required. Please reboot the system or run:"
    print_warning "  sudo nvidia-smi -i ${GPU_ID} -r"
    echo ""
    read -p "Press Enter to continue after GPU reset, or Ctrl+C to exit..."
else
    print_success "MIG mode is already enabled"
fi

# Destroy existing MIG devices
print_info "Destroying existing MIG devices (if any)..."
nvidia-smi mig -i ${GPU_ID} -dci || true
nvidia-smi mig -i ${GPU_ID} -dgi || true

# Create MIG GPU instances
print_info "Creating ${MIG_INSTANCE_COUNT} MIG GPU instance(s) with profile ${MIG_PROFILE}..."

for i in $(seq 1 ${MIG_INSTANCE_COUNT}); do
    print_info "Creating GPU instance ${i}/${MIG_INSTANCE_COUNT}..."
    
    # Create GPU instance
    GI_ID=$(nvidia-smi mig -i ${GPU_ID} -cgi ${MIG_PROFILE} -C | grep -oP 'GPU instance ID \K[0-9]+' | head -1)
    
    if [ -z "$GI_ID" ]; then
        print_error "Failed to create GPU instance"
        exit 1
    fi
    
    print_success "Created GPU instance with ID: ${GI_ID}"
    
    # Create compute instance for this GPU instance
    print_info "Creating compute instance for GPU instance ${GI_ID}..."
    CI_ID=$(nvidia-smi mig -i ${GPU_ID} -gi ${GI_ID} -cci | grep -oP 'Compute instance ID \K[0-9]+' | head -1)
    
    if [ -z "$CI_ID" ]; then
        print_error "Failed to create compute instance"
        exit 1
    fi
    
    print_success "Created compute instance with ID: ${CI_ID}"
    echo ""
done

# List created MIG devices
print_success "MIG setup complete!"
echo ""
print_info "Created MIG devices:"
nvidia-smi mig -lgi
echo ""

print_info "MIG device UUIDs:"
nvidia-smi -L | grep MIG
echo ""

# Get first MIG device UUID for configuration
FIRST_MIG_UUID=$(nvidia-smi -L | grep MIG | head -1 | grep -oP 'MIG-[a-f0-9-]+' || echo "0")

print_success "Setup complete! Next steps:"
echo ""
echo "1. Copy the MIG device UUID from above"
echo "2. Update .env.vllm-mig:"
echo "   MIG_DEVICE_UUID=${FIRST_MIG_UUID}"
echo ""
echo "3. Start vLLM with MIG:"
echo "   docker-compose -f docker-compose.vllm-mig.yml up -d"
echo ""
echo "To disable MIG and restore full GPU:"
echo "   sudo nvidia-smi -i ${GPU_ID} -mig 0"
echo "   sudo nvidia-smi -i ${GPU_ID} -r"

