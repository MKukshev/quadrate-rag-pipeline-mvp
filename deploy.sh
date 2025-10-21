#!/bin/bash

# AI Assistant MVP - Cloud Deployment Script
# Usage: ./deploy.sh [--production]

set -e

PRODUCTION_MODE=false
if [[ "$1" == "--production" ]]; then
    PRODUCTION_MODE=true
fi

echo "🚀 Starting AI Assistant MVP deployment..."

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if running as root
if [[ $EUID -eq 0 ]]; then
   print_error "This script should not be run as root for security reasons"
   exit 1
fi

# Check system requirements
print_status "Checking system requirements..."

# Check available memory
TOTAL_MEM=$(free -g | awk '/^Mem:/{print $2}')
if [ "$TOTAL_MEM" -lt 8 ]; then
    print_warning "System has ${TOTAL_MEM}GB RAM. Recommended: 16GB+ for optimal performance"
fi

# Check available disk space
AVAILABLE_SPACE=$(df -BG . | tail -1 | awk '{print $4}' | sed 's/G//')
if [ "$AVAILABLE_SPACE" -lt 30 ]; then
    print_error "Insufficient disk space. Available: ${AVAILABLE_SPACE}GB, Required: 30GB+"
    exit 1
fi

# Check if Docker is installed and accessible
if ! command -v docker &> /dev/null; then
    print_error "Docker is not installed or not in PATH"
    exit 1
fi

if ! docker ps &> /dev/null; then
    print_error "Cannot connect to Docker daemon. Make sure user is in docker group"
    exit 1
fi

# Check if Docker Compose is available
if ! command -v docker-compose &> /dev/null; then
    print_error "Docker Compose is not installed"
    exit 1
fi

print_status "System requirements check passed ✅"

# Setup environment
if [ "$PRODUCTION_MODE" = true ]; then
    print_status "Setting up production environment..."
    cp .env.production .env
else
    print_status "Setting up development environment..."
    if [ ! -f .env ]; then
        print_warning "No .env file found, creating default configuration..."
        cp .env.production .env
    fi
fi

# Create necessary directories
print_status "Creating data directories..."
mkdir -p backend/models
mkdir -p data/qdrant
mkdir -p data/whoosh

# Set proper permissions
chmod 755 backend/models
chmod 755 data

# Pull required Docker images
print_status "Pulling Docker images..."
docker-compose pull qdrant ollama

# Build application
print_status "Building application..."
docker-compose build backend

# Start services
print_status "Starting services..."

# Start infrastructure services first
print_status "Starting Qdrant and Ollama..."
docker-compose up -d qdrant ollama

# Wait for services to be ready
print_status "Waiting for services to initialize..."
sleep 10

# Check Qdrant health
print_status "Checking Qdrant connectivity..."
max_attempts=30
attempt=0
while [ $attempt -lt $max_attempts ]; do
    if curl -s http://localhost:6333/collections > /dev/null 2>&1; then
        print_status "Qdrant is ready ✅"
        break
    fi
    attempt=$((attempt + 1))
    echo -n "."
    sleep 2
done

if [ $attempt -eq $max_attempts ]; then
    print_error "Qdrant failed to start within expected time"
    exit 1
fi

# Start backend
print_status "Starting backend service..."
docker-compose up -d backend

# Wait for backend health
print_status "Waiting for backend to be ready..."
max_attempts=60
attempt=0
while [ $attempt -lt $max_attempts ]; do
    if curl -s http://localhost:8000/health > /dev/null 2>&1; then
        print_status "Backend is ready ✅"
        break
    fi
    attempt=$((attempt + 1))
    echo -n "."
    sleep 2
done

if [ $attempt -eq $max_attempts ]; then
    print_error "Backend failed to start within expected time"
    print_status "Checking logs..."
    docker-compose logs backend
    exit 1
fi

# Download LLM model
print_status "Downloading LLM model (this may take several minutes)..."
MODEL=${LLM_MODEL:-"llama3.1:8b"}
docker-compose exec -T ollama ollama pull $MODEL

# Index sample documents if they exist
if [ -d "docs" ] && [ "$(ls -A docs)" ]; then
    print_status "Indexing sample documents..."
    docker-compose exec -T backend python -m cli.index_cli --dir /app/docs --space demo_space
else
    print_warning "No documents found in ./docs directory to index"
fi

# Final health check
print_status "Performing final health check..."
HEALTH_RESPONSE=$(curl -s http://localhost:8000/health)
STATUS=$(echo $HEALTH_RESPONSE | jq -r '.status' 2>/dev/null || echo "unknown")

if [ "$STATUS" = "ok" ]; then
    print_status "✅ Deployment successful!"
    echo ""
    echo "🎉 AI Assistant MVP is now running!"
    echo ""
    echo "📊 Service URLs:"
    echo "  • API Documentation: http://$(hostname -I | awk '{print $1}'):8000/docs"
    echo "  • Health Check: http://$(hostname -I | awk '{print $1}'):8000/health"
    echo "  • Metrics: http://$(hostname -I | awk '{print $1}'):8000/metrics"
    echo ""
    echo "🔧 Management Commands:"
    echo "  • View logs: docker-compose logs -f backend"
    echo "  • Stop services: docker-compose down"
    echo "  • Restart: docker-compose restart"
    echo ""
    
    # Test query
    print_status "Testing with sample query..."
    TEST_RESPONSE=$(curl -s -X POST http://localhost:8000/ask \
        -H "Content-Type: application/json" \
        -d '{"q":"Hello, how are you?","space_id":"demo_space","top_k":3}' | jq -r '.answer' 2>/dev/null || echo "Test failed")
    
    if [ "$TEST_RESPONSE" != "Test failed" ] && [ "$TEST_RESPONSE" != "null" ]; then
        print_status "✅ Sample query test passed"
    else
        print_warning "Sample query test failed - service may need more time to initialize"
    fi
    
else
    print_error "Deployment completed but health check failed"
    echo "Health response: $HEALTH_RESPONSE"
    print_status "Check logs with: docker-compose logs backend"
    exit 1
fi

print_status "🎯 Next steps:"
echo "  1. Upload documents via API: POST /ingest"
echo "  2. Search documents: GET /search?q=your_query"
echo "  3. Ask questions: POST /ask"
echo "  4. Monitor with: curl http://localhost:8000/metrics"

if [ "$PRODUCTION_MODE" = true ]; then
    echo ""
    print_warning "🔐 Production Security Reminders:"
    echo "  • Configure firewall rules"
    echo "  • Set up SSL/TLS termination"
    echo "  • Configure log rotation"
    echo "  • Set up monitoring and alerting"
    echo "  • Regular backup of data volumes"
fi
