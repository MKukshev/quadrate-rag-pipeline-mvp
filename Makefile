
SPACE ?= space_demo
MODEL ?= llama3.1:8b

.PHONY: up down build backend logs ingest ask pull-model health wait train-doctypes
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
