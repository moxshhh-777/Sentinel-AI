.PHONY: up down migrate test build logs

up:
	docker compose up -d --build

down:
	docker compose down

migrate:
	docker compose exec backend alembic upgrade head

test:
	docker compose exec -e PYTHONPATH=. backend pytest -v

build:
	docker compose build

logs:
	docker compose logs -f
