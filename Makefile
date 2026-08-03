.PHONY: up down logs seed check
up:
	docker compose -f infra/docker/docker-compose.yml up --build -d
down:
	docker compose -f infra/docker/docker-compose.yml down
logs:
	docker compose -f infra/docker/docker-compose.yml logs -f
seed:
	bash scripts/seed_demo.sh
check:
	python3 -m compileall -q api core connectors worker
	python3 tests/test_logic.py
