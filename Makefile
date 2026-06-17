.PHONY: help build up down logs test clean

GREEN := \033[0;32m
RED := \033[0;31m
NC := \033[0m

help:
	@echo "Available commands:"
	@echo "  make build      - Build all Docker images"
	@echo "  make up         - Start all services"
	@echo "  make down       - Stop all services"
	@echo "  make logs       - Show logs"
	@echo "  make test       - Run Newman tests"
	@echo "  make clean      - Remove everything"

build:
	@echo "$(GREEN)Building images...$(NC)"
	docker compose build

up:
	@echo "$(GREEN)Starting services...$(NC)"
	docker compose up -d
	sleep 10
	@echo "$(GREEN)Services started:$(NC)"
	docker compose ps

down:
	@echo "$(GREEN)Stopping services...$(NC)"
	docker compose down

logs:
	docker compose logs -f

test:
	@echo "$(GREEN)Running Newman tests...$(NC)"
	bash scripts/run-newman.sh

clean:
	@echo "$(RED)Removing containers, volumes, images...$(NC)"
	docker compose down -v --rmi all
	@echo "$(GREEN)Cleanup complete$(NC)"
