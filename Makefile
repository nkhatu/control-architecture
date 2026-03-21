SHELL := /bin/zsh

infra-up:
	docker compose up -d postgres redis nats opa temporal temporal-ui

infra-down:
	docker compose down

infra-logs:
	docker compose logs -f

infra-ps:
	docker compose ps
