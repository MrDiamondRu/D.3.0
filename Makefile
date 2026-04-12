# =============================================================================
# D3.0 CRM - Makefile
# =============================================================================

PROJECT_SLUG := d3_0
DC_DEV := docker compose -p $(PROJECT_SLUG) -f compose.dev.yml
DC_PROD := docker compose -p $(PROJECT_SLUG) -f compose.prod.yml
MANAGE := python manage.py

.DEFAULT_GOAL := help

.PHONY: help start start-dev stop stop-dev refresh refresh-nocache build-nocache logs logs-dev shell migrate makemigrations createsuperuser seed import-csv prod-up start-prod

# Colors for help menu
CYAN := \033[0;36m
GREEN := \033[0;32m
GRAY := \033[0;90m
BOLD := \033[1m
NC := \033[0m

# =============================================================================
# Help
# =============================================================================
help:
	@echo "$(CYAN)$(BOLD)━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━$(NC)"
	@echo "$(CYAN)$(BOLD)  D3.0 CRM - Команды управления проектом$(NC)"
	@echo "$(CYAN)$(BOLD)━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━$(NC)"
	@echo "▸ Запуск и остановка"
	@echo "  $(GREEN)make start$(NC)            Запустить dev-окружение (build + up)"
	@echo "  $(GREEN)make start-dev$(NC)        $(GRAY)(алиас для start)$(NC)"
	@echo "  $(GREEN)make stop$(NC)             Остановить dev-окружение"
	@echo "  $(GREEN)make stop-dev$(NC)         $(GRAY)(алиас для stop)$(NC)"
	@echo "  $(GREEN)make refresh$(NC)          Полный перезапуск dev + migrate"
	@echo "  $(GREEN)make refresh-nocache$(NC)  Как refresh, образ dev без кэша Docker"
	@echo "  $(GREEN)make build-nocache$(NC)    Только docker build --no-cache (dev)"
	@echo "▸ Логи и shell"
	@echo "  $(GREEN)make logs$(NC)             Логи сервиса web (follow)"
	@echo "  $(GREEN)make logs-dev$(NC)         $(GRAY)(алиас для logs)$(NC)"
	@echo "  $(GREEN)make shell$(NC)            Открыть shell в контейнере web"
	@echo "▸ Django management"
	@echo "  $(GREEN)make makemigrations$(NC)   Создать миграции"
	@echo "  $(GREEN)make migrate$(NC)          Применить миграции"
	@echo "  $(GREEN)make createsuperuser$(NC)  Создать суперпользователя"
	@echo "  $(GREEN)make seed$(NC)             Заполнить справочные данные"
	@echo "  $(GREEN)make import-csv$(NC)       Импортировать template/Михаил.csv"
	@echo "▸ Production"
	@echo "  $(GREEN)make prod-up$(NC)          Запустить production-стек (detached)"
	@echo "  $(GREEN)make start-prod$(NC)       $(GRAY)(алиас для prod-up)$(NC)"
	@echo "$(CYAN)$(BOLD)━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━$(NC)"

# =============================================================================
# Development commands
# =============================================================================
start: start-dev

start-dev:
	$(DC_DEV) up -d --build
	@echo "============================================================"
	@echo "  Project started successfully in development mode"
	@echo "============================================================"
	@echo ""
	@echo "App access:"
	@echo "  * Main page:     http://localhost:8000"
	@echo "  * Panel:         http://localhost:8000/panel/"
	@echo "  * Django Admin:  http://localhost:8000/admin/"
	@echo "  * API:           http://localhost:8000/api/"
	@echo ""
	@echo "! Tip: useful commands"
	@echo "  make logs"
	@echo "  make migrate"
	@echo "  make createsuperuser"
	@echo "  make stop"

stop: stop-dev

stop-dev:
	$(DC_DEV) down

refresh:
	$(DC_DEV) down
	$(DC_DEV) up -d --build
	$(DC_DEV) exec -T web $(MANAGE) migrate
	@echo "============================================================"
	@echo "  Refresh completed (dev restarted, migrations applied)"
	@echo "============================================================"

build-nocache:
	$(DC_DEV) build --no-cache

refresh-nocache:
	$(DC_DEV) down
	$(DC_DEV) build --no-cache
	$(DC_DEV) up -d
	$(DC_DEV) exec -T web $(MANAGE) migrate
	@echo "============================================================"
	@echo "  Refresh completed (no-cache rebuild, migrations applied)"
	@echo "============================================================"

logs: logs-dev

logs-dev:
	$(DC_DEV) logs -f web

shell:
	$(DC_DEV) run --rm web sh

# =============================================================================
# Django management commands
# =============================================================================
migrate:
	$(DC_DEV) run --rm web $(MANAGE) migrate

makemigrations:
	$(DC_DEV) run --rm web $(MANAGE) makemigrations

createsuperuser:
	$(DC_DEV) run --rm web $(MANAGE) createsuperuser

seed:
	$(DC_DEV) run --rm web $(MANAGE) seed_references

import-csv:
	$(DC_DEV) run --rm web $(MANAGE) import_mikhail_csv

# =============================================================================
# Production commands
# =============================================================================
prod-up:
	$(DC_PROD) up --build -d

start-prod: prod-up
