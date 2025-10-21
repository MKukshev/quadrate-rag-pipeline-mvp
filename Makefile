
SPACE ?= space_demo
MODEL ?= llama3.1:8b

.PHONY: up down build backend logs ingest ask pull-model health wait train-doctypes
.PHONY: up-vllm down-vllm logs-vllm switch-ollama switch-vllm

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
	docker compose -f docker-compose.vllm-mig.yml logs -f vllm

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
	@echo ""
	@echo "vLLM + MIG (GPU partitioning):"
	@echo "  make setup-mig       - Setup NVIDIA MIG instances"
	@echo "  make list-mig        - List MIG devices"
	@echo "  make up-vllm-mig     - Start with vLLM + MIG"
	@echo "  make down-vllm-mig   - Stop vLLM + MIG"
	@echo "  make logs-vllm-mig   - Show vLLM MIG logs"
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
	@echo ""
	@echo "Testing:"
	@echo "  make test-summarization - Test summarization feature"
	@echo "  make test-modes         - Test /ask modes (auto/normal/summarize/detailed)"
