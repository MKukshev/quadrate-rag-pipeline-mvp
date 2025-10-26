
ifneq (,$(wildcard .env))
include .env
export $(shell sed -n 's/^\([A-Za-z0-9_][A-Za-z0-9_]*\)=.*/\1/p' .env)
endif

SPACE ?= space_demo
DEFAULT_OLLAMA_MODEL := $(if $(strip $(LLM_MODEL)),$(LLM_MODEL),llama3.1:8b)
MODEL ?= $(DEFAULT_OLLAMA_MODEL)
DEFAULT_VLLM_MODEL := $(if $(strip $(VLLM_MODEL)),$(VLLM_MODEL),openai/gpt-oss-20b)
VLLM_MODEL ?= $(DEFAULT_VLLM_MODEL)
VLLM_COMPOSE ?= docker-compose.vllm-mig.yml

.PHONY: up down build backend logs ingest ask pull-model pull-model-vllm health wait train-doctypes
.PHONY: up-vllm down-vllm logs-vllm switch-ollama switch-vllm
.PHONY: up-dual-models down-dual-models logs-dual-models logs-medium logs-small test-medium test-small test-both-models restart-medium restart-small test-dual-models check-env

# ===== Ollama (default) =====
up:
	docker compose up -d qdrant ollama
	docker compose up -d --build backend

down:
	docker compose down

build:
	docker compose build backend

backend:
	docker compose up --build backend

logs:
	docker compose logs -f backend

pull-model:
	docker compose exec -T ollama ollama pull $(MODEL)

pull-model-vllm:
	@echo "Prefetching $(VLLM_MODEL) into vLLM cache..."
	docker compose -f $(VLLM_COMPOSE) exec -T vllm env HF_MODEL="$(VLLM_MODEL)" python -c "import os; from huggingface_hub import snapshot_download; model=os.environ['HF_MODEL']; cache_dir=os.environ.get('HF_HOME', '/root/.cache/huggingface'); print(f'Downloading {model} into cache {cache_dir} …', flush=True); snapshot_download(repo_id=model, cache_dir=cache_dir, resume_download=True, local_files_only=False); print('✓ Download complete.', flush=True)"

# ===== vLLM =====
up-vllm:
	@echo "Starting with vLLM (GPU required)..."
	docker compose -f docker-compose.vllm.yml up -d

down-vllm:
	docker compose -f docker-compose.vllm.yml down

logs-vllm:
	docker compose -f docker-compose.vllm.yml logs -f vllm

build-vllm:
	docker compose -f docker-compose.vllm.yml build

# Проверка GPU в контейнерах
check-gpu:
	@echo "Checking GPU availability in backend..."
	@docker compose -f docker-compose.vllm.yml exec backend python3 -c "import torch; print(f'CUDA available: {torch.cuda.is_available()}'); print(f'Device: {torch.cuda.get_device_name(0) if torch.cuda.is_available() else \"N/A\"}')" || echo "Backend container not running"

check-vllm-gpu:
	@echo "Checking GPU in vLLM..."
	@docker compose -f docker-compose.vllm.yml exec vllm python3 -c "import torch; print(f'CUDA available: {torch.cuda.is_available()}'); print(f'Device: {torch.cuda.get_device_name(0) if torch.cuda.is_available() else \"N/A\"}')" || echo "vLLM container not running"

# ===== Switching between Ollama and vLLM =====
switch-ollama:
	@echo "Switching to Ollama..."
	@docker compose -f docker-compose.vllm.yml down 2>/dev/null || true
	@cp .env.ollama .env || true
	@docker compose up -d
	@echo "✅ Switched to Ollama mode"

switch-vllm:
	@echo "Switching to vLLM..."
	@docker compose down 2>/dev/null || true
	@cp .env.vllm .env || true
	@docker compose -f docker-compose.vllm.yml up -d
	@echo "✅ Switched to vLLM mode (check logs: make logs-vllm)"

# ===== Common commands =====
ingest:
	# индексируем примеры из /app/docs внутри контейнера
	docker compose exec -T backend python -m cli.index_cli --dir /app/docs --space $(SPACE)

ask:
	curl -s -X POST http://localhost:8000/ask -H "Content-Type: application/json" \
	  -d '{"q":"Какие дедлайны прошли по проекту?","space_id":"$(SPACE)","top_k":6}' | jq .

health:
	curl -sS http://localhost:8000/health | jq . || curl -sS http://localhost:8000/health

wait:
	@echo "Waiting for backend health..."; \
	until curl -fsS http://localhost:8000/health >/dev/null 2>&1; do \
	  sleep 2; printf "."; \
	done; \
	echo " ready";

train-doctypes:
	docker compose exec -T backend python -m backend.scripts.train_doc_type_classifier --docs /app/docs --output /app/backend/models/doc_type_classifier.joblib

# ===== MIG (Multi-Instance GPU) =====
up-vllm-mig:
	@echo "Starting with vLLM + MIG (requires MIG setup)..."
	docker compose -f docker-compose.vllm-mig.yml up -d

down-vllm-mig:
	docker compose -f docker-compose.vllm-mig.yml down

logs-vllm-mig:
	docker compose -f docker-compose.vllm-mig.yml logs -f vllm-medium

# ===== Dual Models (MEDIUM + SMALL) =====
up-dual-models:
	@echo "Starting dual vLLM models (MEDIUM + SMALL)..."
	@if [ ! -f .env ]; then \
		echo "⚠️  Warning: .env not found. Using default values from docker-compose."; \
		echo "💡 Tip: See ENV_SETUP_GUIDE.md for configuration examples."; \
	fi
	docker compose -f docker-compose.vllm-mig.yml up -d

down-dual-models:
	docker compose -f docker-compose.vllm-mig.yml down

logs-dual-models:
	docker compose -f docker-compose.vllm-mig.yml logs -f vllm-medium vllm-small

logs-medium:
	docker compose -f docker-compose.vllm-mig.yml logs -f vllm-medium

logs-small:
	docker compose -f docker-compose.vllm-mig.yml logs -f vllm-small

restart-medium:
	docker compose -f docker-compose.vllm-mig.yml restart vllm-medium

restart-small:
	docker compose -f docker-compose.vllm-mig.yml restart vllm-small

# Test individual models
test-medium:
	@echo "Testing MEDIUM model on port 8001..."
	@curl -s http://localhost:8001/health && echo "" || echo "❌ MEDIUM model not responding"
	@curl -s http://localhost:8001/v1/models | jq '.data[0].id' 2>/dev/null || echo "Models endpoint not available"

test-small:
	@echo "Testing SMALL model on port 8002..."
	@curl -s http://localhost:8002/health && echo "" || echo "❌ SMALL model not responding"
	@curl -s http://localhost:8002/v1/models | jq '.data[0].id' 2>/dev/null || echo "Models endpoint not available"

test-both-models:
	@echo "=== Testing both models ==="
	@make test-medium
	@echo ""
	@make test-small

setup-mig:
	@echo "Setting up NVIDIA MIG (requires sudo)..."
	@sudo ./scripts/setup_mig.sh

list-mig:
	@./scripts/list_mig_devices.sh

verify-blackwell:
	@./scripts/verify_blackwell_compatibility.sh

test-summarization:
	@./scripts/test_summarization.sh

test-modes:
	@./scripts/test_ask_modes.sh

test-summary-store:
	@./scripts/test_summary_store.sh

test-streaming:
	@./scripts/test_streaming.sh

test-dual-models:
	@./scripts/test_dual_models.sh

# Check environment configuration
check-env:
	@echo "=== Environment Configuration Check ==="
	@echo ""
	@if [ -f .env ]; then \
		echo "✅ .env file found"; \
		echo ""; \
		echo "MEDIUM Model:"; \
		grep "VLLM_MODEL_MEDIUM" .env || echo "  ⚠️  VLLM_MODEL_MEDIUM not set"; \
		grep "MIG_MEDIUM" .env || echo "  ⚠️  MIG_MEDIUM not set"; \
		echo ""; \
		echo "SMALL Model:"; \
		grep "VLLM_MODEL_SMALL" .env || echo "  ⚠️  VLLM_MODEL_SMALL not set"; \
		grep "MIG_SMALL" .env || echo "  ⚠️  MIG_SMALL not set"; \
		echo ""; \
		echo "Backend:"; \
		grep "MIG_1G_24GB" .env || echo "  ⚠️  MIG_1G_24GB not set"; \
	else \
		echo "❌ .env file not found"; \
		echo ""; \
		echo "💡 Create .env file with required variables."; \
		echo "   See ENV_SETUP_GUIDE.md for examples."; \
	fi
	@echo ""
	@echo "=== Docker Compose Config Preview ==="
	@docker compose -f docker-compose.vllm-mig.yml config 2>&1 | grep -A 2 "VLLM_MODEL" || echo "Could not preview config"

# ===== Help =====
help:
	@echo "Available targets:"
	@echo ""
	@echo "Basic:"
	@echo "  make up              - Start with Ollama (default)"
	@echo "  make down            - Stop Ollama setup"
	@echo "  make logs            - Show logs"
	@echo ""
	@echo "vLLM (GPU):"
	@echo "  make up-vllm         - Start with vLLM (single GPU)"
	@echo "  make down-vllm       - Stop vLLM setup"
	@echo "  make logs-vllm       - Show vLLM logs"
	@echo "  make pull-model-vllm - Prefetch HF model into vLLM cache"
	@echo ""
	@echo "vLLM + MIG (GPU partitioning):"
	@echo "  make setup-mig       - Setup NVIDIA MIG instances"
	@echo "  make list-mig        - List MIG devices"
	@echo "  make up-vllm-mig     - Start with vLLM + MIG (single model)"
	@echo "  make down-vllm-mig   - Stop vLLM + MIG"
	@echo "  make logs-vllm-mig   - Show vLLM MIG logs"
	@echo ""
	@echo "Dual Models (MEDIUM + SMALL):"
	@echo "  make up-dual-models  - Start both models simultaneously"
	@echo "  make down-dual-models- Stop dual models setup"
	@echo "  make logs-dual-models- Show logs for both models"
	@echo "  make logs-medium     - Show logs for MEDIUM model only"
	@echo "  make logs-small      - Show logs for SMALL model only"
	@echo "  make test-medium     - Test MEDIUM model (port 8001)"
	@echo "  make test-small      - Test SMALL model (port 8002)"
	@echo "  make test-both-models- Test both models"
	@echo "  make restart-medium  - Restart MEDIUM model container"
	@echo "  make restart-small   - Restart SMALL model container"
	@echo ""
	@echo "Blackwell Verification:"
	@echo "  make verify-blackwell - Verify Blackwell compatibility"
	@echo ""
	@echo "Switching:"
	@echo "  make switch-ollama   - Switch to Ollama mode"
	@echo "  make switch-vllm     - Switch to vLLM mode"
	@echo ""
	@echo "Operations:"
	@echo "  make ingest          - Index documents"
	@echo "  make ask             - Test RAG query"
	@echo "  make health          - Check system health"
	@echo "  make check-env       - Check .env configuration for dual models"
	@echo ""
	@echo "Testing:"
	@echo "  make test-summarization - Test summarization feature"
	@echo "  make test-modes         - Test /ask modes (auto/normal/summarize/detailed)"
	@echo "  make test-summary-store - Test summary storage (pattern 4)"
	@echo "  make test-streaming     - Test streaming summarization (pattern 5)"
	@echo "  make test-dual-models   - Test both MEDIUM and SMALL models"
