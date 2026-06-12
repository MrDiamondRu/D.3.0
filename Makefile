# =============================================================================
# D3.0 CRM - Makefile
# =============================================================================

PROJECT_SLUG := d3_0
SECRETS_DIR  := secrets
DEPLOY_ENV   := $(SECRETS_DIR)/deploy.env
ENV_PROD     := $(SECRETS_DIR)/env.prod
ENV_DEV      := $(SECRETS_DIR)/env.dev
DEV_DUMP     := $(SECRETS_DIR)/dev_dump.json

-include $(DEPLOY_ENV)
export

ifndef SSH_KEY
SSH_KEY := secrets/id_ed25519_deploy
endif

HOME_DIR       := $(if $(HOME),$(HOME),$(USERPROFILE))
SSH_KEY_SOURCE := $(SSH_KEY)
SSH_KEY_USE    := $(HOME_DIR)/.ssh/d3_0_deploy

DC_DEV  := docker compose -p $(PROJECT_SLUG) -f compose.dev.yml
DC_PROD := docker compose -p $(PROJECT_SLUG) -f compose.prod.yml --env-file $(DEPLOY_ENV)
MANAGE  := python manage.py

SSH_OPTS  := -i "$(SSH_KEY_USE)" -o StrictHostKeyChecking=accept-new -o IdentitiesOnly=yes
SSH       := ssh $(SSH_OPTS) $(DEPLOY_USER)@$(DEPLOY_HOST)
SCP       := scp $(SSH_OPTS)
RSYNC     := rsync -az --delete
RSYNC_EXCLUDES := \
	--exclude '.git' \
	--exclude '__pycache__' \
	--exclude '*.pyc' \
	--exclude 'db.sqlite3' \
	--exclude 'media' \
	--exclude '.env' \
	--exclude 'secrets/env.dev' \
	--exclude 'secrets/env.prod' \
	--exclude 'secrets/deploy.env' \
	--exclude 'secrets/id_ed25519_deploy' \
	--exclude 'secrets/dev_dump.json' \
	--exclude '.idea'

REMOTE_COMPOSE := docker compose -p $(PROJECT_SLUG) -f compose.prod.yml --env-file secrets/deploy.env
REMOTE_MIGRATE := sg docker -c "cd $(DEPLOY_PATH) && flock -w 120 /tmp/$(PROJECT_SLUG)_migrate.lock $(REMOTE_COMPOSE) run --rm web $(MANAGE) migrate --noinput"

.DEFAULT_GOAL := help

.PHONY: help start start-dev stop stop-dev refresh refresh-nocache build-nocache logs logs-dev shell \
	migrate makemigrations createsuperuser seed import-csv dev-rebuild-db prod-up start-prod \
	ssh-fix-key-perms ssh-setup ssh-test server-init deploy deploy-initial export-dev-db import-prod-db reset-prod-db

# =============================================================================
# UI helpers
# =============================================================================
CYAN    := \033[0;36m
GREEN   := \033[0;32m
YELLOW  := \033[0;33m
RED     := \033[0;31m
BLUE    := \033[0;34m
MAGENTA := \033[0;35m
GRAY    := \033[0;90m
BOLD    := \033[1m
DIM     := \033[2m
NC      := \033[0m

define log_banner
	@echo ""
	@echo "$(CYAN)$(BOLD)━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━$(NC)"
	@echo "$(CYAN)$(BOLD)  $(1)$(NC)"
	@echo "$(CYAN)$(BOLD)━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━$(NC)"
endef

define log_section
	@echo ""
	@echo "$(MAGENTA)$(BOLD)▸ $(1)$(NC)"
endef

define log_step
	@echo "$(BLUE)$(BOLD)[$(1)/$(2)]$(NC) $(3)"
endef

define log_cmd
	@echo "$(DIM)    $$ $(1)$(NC)"
endef

define log_ok
	@echo "$(GREEN)$(BOLD)  ✓$(NC) $(1)"
endef

define log_warn
	@echo "$(YELLOW)$(BOLD)  !$(NC) $(1)"
endef

define log_info
	@echo "$(GRAY)    $(1)$(NC)"
endef

define log_done
	@echo ""
	@echo "$(GREEN)$(BOLD)━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━$(NC)"
	@echo "$(GREEN)$(BOLD)  ✓ $(1)$(NC)"
	@echo "$(GREEN)$(BOLD)━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━$(NC)"
	@echo ""
endef

define log_fail
	@echo ""
	@echo "$(RED)$(BOLD)━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━$(NC)"
	@echo "$(RED)$(BOLD)  ✗ $(1)$(NC)"
	@echo "$(RED)$(BOLD)━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━$(NC)"
	@echo ""
endef

# =============================================================================
# Help
# =============================================================================
help:
	$(call log_banner,D3.0 CRM — команды управления)
	@echo ""
	@echo "$(BOLD)Запуск и остановка$(NC)"
	@echo "  $(GREEN)make start$(NC)            $(GRAY)dev-окружение (build + up)$(NC)"
	@echo "  $(GREEN)make stop$(NC)             $(GRAY)остановить dev$(NC)"
	@echo "  $(GREEN)make refresh$(NC)          $(GRAY)перезапуск dev + migrate$(NC)"
	@echo "  $(GREEN)make refresh-nocache$(NC)  $(GRAY)как refresh, без кэша Docker$(NC)"
	@echo ""
	@echo "$(BOLD)Логи и shell$(NC)"
	@echo "  $(GREEN)make logs$(NC)             $(GRAY)логи web (follow)$(NC)"
	@echo "  $(GREEN)make shell$(NC)            $(GRAY)shell в контейнере web$(NC)"
	@echo ""
	@echo "$(BOLD)Django$(NC)"
	@echo "  $(GREEN)make migrate$(NC)          $(GRAY)применить миграции$(NC)"
	@echo "  $(GREEN)make makemigrations$(NC)   $(GRAY)создать миграции$(NC)"
	@echo "  $(GREEN)make createsuperuser$(NC)  $(GRAY)суперпользователь$(NC)"
	@echo "  $(GREEN)make seed$(NC)             $(GRAY)справочники$(NC)"
	@echo "  $(GREEN)make import-csv$(NC)       $(GRAY)импорт Михаил.csv$(NC)"
	@echo "  $(GREEN)make dev-rebuild-db$(NC)   $(GRAY)пересоздать SQLite из дампа$(NC)"
	@echo ""
	@echo "$(BOLD)Production (локально)$(NC)"
	@echo "  $(GREEN)make prod-up$(NC)          $(GRAY)запуск prod-стека$(NC)"
	@echo ""
	@echo "$(BOLD)Deploy (удалённый сервер)$(NC)"
	@echo "  $(GREEN)make ssh-setup$(NC)        $(GRAY)SSH-ключ на сервер$(NC)"
	@echo "  $(GREEN)make ssh-test$(NC)         $(GRAY)проверка SSH без пароля$(NC)"
	@echo "  $(GREEN)make server-init$(NC)      $(GRAY)каталог + группа docker$(NC)"
	@echo "  $(GREEN)make deploy$(NC)             $(GRAY)rsync + compose prod$(NC)"
	@echo "  $(GREEN)make deploy IMPORT_DB=1$(NC) $(GRAY)деплой + перенос БД$(NC)"
	@echo "  $(GREEN)make deploy-initial$(NC)   $(GRAY)export + deploy + import$(NC)"
	@echo "  $(GREEN)make export-dev-db$(NC)    $(GRAY)дамп SQLite → JSON$(NC)"
	@echo "  $(GREEN)make import-prod-db$(NC)   $(GRAY)импорт JSON → PostgreSQL$(NC)"
	@echo "  $(GREEN)make reset-prod-db$(NC)    $(GRAY)сброс PostgreSQL на сервере$(NC)"
	@echo ""

# =============================================================================
# Development
# =============================================================================
start: start-dev

start-dev:
	$(call log_banner,Запуск development)
	$(call log_step,1,2,Сборка и старт контейнеров)
	$(call log_cmd,$(DC_DEV) up -d --build)
	@$(DC_DEV) up -d --build
	$(call log_step,2,2,Проверка статуса)
	@$(DC_DEV) ps --format "table {{.Name}}\t{{.Status}}\t{{.Ports}}" 2>/dev/null || $(DC_DEV) ps
	$(call log_done,Development запущен)
	@echo "$(BOLD)Доступ:$(NC)"
	@echo "  $(CYAN)http://localhost:8000/panel/$(NC)"
	@echo "  $(CYAN)http://localhost:8000/admin/$(NC)"
	@echo ""
	@echo "$(GRAY)Полезно: make logs | make migrate | make stop$(NC)"

stop: stop-dev

stop-dev:
	$(call log_banner,Остановка development)
	$(call log_cmd,$(DC_DEV) down)
	@$(DC_DEV) down
	$(call log_done,Development остановлен)

refresh:
	$(call log_banner,Refresh development)
	$(call log_step,1,3,Остановка)
	@$(DC_DEV) down
	$(call log_step,2,3,Сборка и старт)
	@$(DC_DEV) up -d --build
	$(call log_step,3,3,Миграции)
	@$(DC_DEV) exec -T web $(MANAGE) migrate
	$(call log_done,Refresh завершён)

build-nocache:
	$(call log_banner,Build без кэша)
	$(call log_cmd,$(DC_DEV) build --no-cache)
	@$(DC_DEV) build --no-cache
	$(call log_done,Образ пересобран)

refresh-nocache:
	$(call log_banner,Refresh без кэша)
	$(call log_step,1,4,Остановка)
	@$(DC_DEV) down
	$(call log_step,2,4,Сборка без кэша)
	@$(DC_DEV) build --no-cache
	$(call log_step,3,4,Старт)
	@$(DC_DEV) up -d
	$(call log_step,4,4,Миграции)
	@$(DC_DEV) exec -T web $(MANAGE) migrate
	$(call log_done,Refresh без кэша завершён)

logs: logs-dev

logs-dev:
	$(call log_section,Логи web — Ctrl+C для выхода)
	@$(DC_DEV) logs -f web

shell:
	$(call log_section,Shell в контейнере web)
	@$(DC_DEV) run --rm web sh

# =============================================================================
# Django management
# =============================================================================
migrate:
	$(call log_banner,Миграции)
	$(call log_cmd,$(DC_DEV) run --rm web $(MANAGE) migrate)
	@$(DC_DEV) run --rm web $(MANAGE) migrate
	$(call log_done,Миграции применены)

makemigrations:
	$(call log_banner,Создание миграций)
	$(call log_cmd,$(DC_DEV) run --rm web $(MANAGE) makemigrations)
	@$(DC_DEV) run --rm web $(MANAGE) makemigrations
	$(call log_done,Готово)

createsuperuser:
	$(call log_section,Создание суперпользователя)
	@$(DC_DEV) run --rm web $(MANAGE) createsuperuser

seed:
	$(call log_banner,Справочные данные)
	@$(DC_DEV) run --rm web $(MANAGE) seed_references
	$(call log_done,Справочники загружены)

import-csv:
	$(call log_banner,Импорт CSV)
	@$(DC_DEV) run --rm web $(MANAGE) import_mikhail_csv
	$(call log_done,Импорт завершён)

dev-rebuild-db: export-dev-db
	$(call log_banner,Пересборка dev SQLite)
	$(call log_warn,db.sqlite3 будет удалён, данные восстановятся из дампа)
	@rm -f db.sqlite3
	$(call log_step,1,2,Миграции)
	@$(DC_DEV) run --rm web $(MANAGE) migrate --noinput
	$(call log_step,2,2,Загрузка loaddata)
	@$(DC_DEV) run --rm -v "$(CURDIR)/$(SECRETS_DIR):/secrets" web $(MANAGE) loaddata /secrets/dev_dump.json
	$(call log_done,Dev БД пересобрана)

# =============================================================================
# Production (local)
# =============================================================================
prod-up:
	@test -f $(ENV_PROD) || (echo "$(RED)Создайте $(ENV_PROD) из env.prod.example$(NC)" && exit 1)
	@test -f $(DEPLOY_ENV) || (echo "$(RED)Создайте $(DEPLOY_ENV) из deploy.env.example$(NC)" && exit 1)
	$(call log_banner,Запуск production (локально))
	$(call log_cmd,$(DC_PROD) up --build -d)
	@$(DC_PROD) up --build -d
	@$(DC_PROD) ps --format "table {{.Name}}\t{{.Status}}\t{{.Ports}}" 2>/dev/null || $(DC_PROD) ps
	$(call log_done,Production запущен локально)

start-prod: prod-up

# =============================================================================
# Deploy (remote)
# =============================================================================
ssh-fix-key-perms:
	@if [ ! -f "$(SSH_KEY_SOURCE)" ]; then \
		echo "$(RED)$(BOLD)  ✗$(NC) Нет ключа $(SSH_KEY_SOURCE). Сначала: $(GREEN)make ssh-setup$(NC)"; \
		exit 1; \
	fi
	@mkdir -p "$(HOME_DIR)/.ssh"
	@cp -f "$(SSH_KEY_SOURCE)" "$(SSH_KEY_USE)"
	@cp -f "$(SSH_KEY_SOURCE).pub" "$(SSH_KEY_USE).pub"
	@chmod 700 "$(HOME_DIR)/.ssh" 2>/dev/null || true
	@chmod 600 "$(SSH_KEY_USE)" 2>/dev/null || true
	@chmod 644 "$(SSH_KEY_USE).pub" 2>/dev/null || true
	@if command -v icacls >/dev/null 2>&1; then \
		WIN_KEY=$$(cygpath -w "$(SSH_KEY_USE)" 2>/dev/null || echo "$(SSH_KEY_USE)"); \
		WIN_SSH=$$(cygpath -w "$(HOME_DIR)/.ssh" 2>/dev/null || echo "$(HOME_DIR)/.ssh"); \
		icacls "$$WIN_SSH" /inheritance:r >/dev/null 2>&1; \
		icacls "$$WIN_SSH" /grant:r "$$USERNAME:(OI)(CI)F" >/dev/null 2>&1; \
		icacls "$$WIN_KEY" /inheritance:r >/dev/null 2>&1; \
		icacls "$$WIN_KEY" /grant:r "$$USERNAME:(R)" >/dev/null 2>&1; \
		icacls "$$WIN_KEY" /remove:g "Authenticated Users" "BUILTIN\Users" "Everyone" 2>/dev/null || true; \
	fi

ssh-setup:
	@test -f $(DEPLOY_ENV) || (echo "$(RED)Создайте $(DEPLOY_ENV) из deploy.env.example$(NC)" && exit 1)
	$(call log_banner,Настройка SSH)
	$(call log_step,1,3,Генерация ключа)
	@test -f "$(SSH_KEY_SOURCE)" || ssh-keygen -t ed25519 -f "$(SSH_KEY_SOURCE)" -N "" -C "d3_0-deploy"
	@$(MAKE) --no-print-directory ssh-fix-key-perms
	$(call log_ok,Ключ: $(SSH_KEY_USE))
	$(call log_step,2,3,Каталог ~/.ssh на сервере $(DEPLOY_HOST))
	$(call log_warn,Потребуется пароль)
	@ssh -o StrictHostKeyChecking=accept-new -o PreferredAuthentications=password -o PubkeyAuthentication=no \
		$(DEPLOY_USER)@$(DEPLOY_HOST) \
		'mkdir -p ~/.ssh && chmod 700 ~/.ssh && touch ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys'
	$(call log_step,3,3,Копирование публичного ключа)
	@PUBKEY=$$(cat "$(SSH_KEY_SOURCE).pub"); \
	ssh -o StrictHostKeyChecking=accept-new -o PreferredAuthentications=password -o PubkeyAuthentication=no \
		$(DEPLOY_USER)@$(DEPLOY_HOST) \
		"grep -qxF \"$$PUBKEY\" ~/.ssh/authorized_keys || echo \"$$PUBKEY\" >> ~/.ssh/authorized_keys"
	$(call log_done,SSH настроен — проверка: make ssh-test)

ssh-test: ssh-fix-key-perms
	@test -f $(DEPLOY_ENV) || (echo "$(RED)Создайте $(DEPLOY_ENV)$(NC)" && exit 1)
	$(call log_banner,Проверка SSH)
	$(call log_info,Хост: $(DEPLOY_USER)@$(DEPLOY_HOST))
	@$(SSH) -o BatchMode=yes 'echo "OK: $$(hostname) — $$(whoami)"' || \
		(echo "$(RED)$(BOLD)  ✗$(NC) SSH не работает. Запустите: $(GREEN)make ssh-setup$(NC)" && exit 1)
	$(call log_done,SSH без пароля работает)

server-init: ssh-fix-key-perms
	@test -f $(DEPLOY_ENV) || (echo "$(RED)Создайте $(DEPLOY_ENV)$(NC)" && exit 1)
	$(call log_banner,Инициализация сервера)
	$(call log_info,Путь: $(DEPLOY_PATH))
	$(call log_warn,Может потребоваться sudo-пароль)
	@$(SSH) -t '\
		if ! command -v docker >/dev/null 2>&1; then \
			echo "Ошибка: Docker не установлен"; exit 1; \
		fi; \
		if mkdir -p "$(DEPLOY_PATH)/secrets" 2>/dev/null; then \
			echo "Каталог готов: $(DEPLOY_PATH)"; \
		else \
			echo "Нужен sudo для $(DEPLOY_PATH)..."; \
			sudo mkdir -p "$(DEPLOY_PATH)/secrets" && sudo chown -R "$$USER:$$USER" "$(DEPLOY_PATH)"; \
		fi; \
		if ! id -nG "$$USER" | tr " " "\n" | grep -qx docker; then \
			echo "Добавляем $$USER в группу docker..."; \
			sudo usermod -aG docker "$$USER"; \
			echo "Группа docker добавлена"; \
		else \
			echo "Группа docker: OK"; \
		fi'
	$(call log_done,Сервер готов)

export-dev-db:
	$(call log_banner,Экспорт dev БД)
	@mkdir -p $(SECRETS_DIR)
	$(call log_step,1,1,dumpdata из SQLite)
	$(call log_info,Экспорт: auth.user + crm (без admin-логов и contenttypes))
	@$(DC_DEV) run --rm -v "$(CURDIR)/$(SECRETS_DIR):/secrets" web $(MANAGE) dumpdata \
		auth.user crm \
		--natural-foreign --natural-primary \
		--indent 2 -o /secrets/dev_dump.json
	$(call log_ok,Файл: $(DEV_DUMP))
	@ls -lh "$(DEV_DUMP)" 2>/dev/null || true
	$(call log_done,Экспорт завершён)

import-prod-db: ssh-fix-key-perms
	@test -f $(DEV_DUMP) || (echo "$(RED)Нет $(DEV_DUMP). Сначала: make export-dev-db$(NC)" && exit 1)
	@test -f $(DEPLOY_ENV) || (echo "$(RED)Нет $(DEPLOY_ENV)$(NC)" && exit 1)
	$(call log_banner,Импорт БД на production)
	$(call log_step,1,4,Копирование дампа на сервер)
	$(call log_info,$(DEV_DUMP) → $(DEPLOY_HOST):$(DEPLOY_PATH)/dev_dump.json)
	@$(SCP) $(DEV_DUMP) $(DEPLOY_USER)@$(DEPLOY_HOST):$(DEPLOY_PATH)/dev_dump.json
	$(call log_ok,Дамп скопирован)
	$(call log_step,2,4,Применение миграций PostgreSQL)
	@$(SSH) '$(REMOTE_MIGRATE)'
	$(call log_ok,Миграции применены)
	$(call log_step,3,4,Загрузка данных loaddata)
	@$(SSH) 'sg docker -c "cd $(DEPLOY_PATH) && $(REMOTE_COMPOSE) run --rm \
		-v $(DEPLOY_PATH)/dev_dump.json:/app/dev_dump.json:ro \
		web $(MANAGE) loaddata dev_dump.json"'
	$(call log_ok,Данные загружены)
	$(call log_step,4,4,Перезапуск web-контейнера)
	@$(SSH) 'sg docker -c "cd $(DEPLOY_PATH) && $(REMOTE_COMPOSE) up -d web"'
	$(call log_done,Импорт завершён — https://$(DEPLOY_DOMAIN))

reset-prod-db: ssh-fix-key-perms
	@test -f $(DEPLOY_ENV) || (echo "$(RED)Нет $(DEPLOY_ENV)$(NC)" && exit 1)
	$(call log_banner,Сброс PostgreSQL на сервере)
	$(call log_warn,Все данные prod БД будут удалены!)
	$(call log_step,1,1,docker compose down -v)
	@$(SSH) 'sg docker -c "cd $(DEPLOY_PATH) && $(REMOTE_COMPOSE) down -v"'
	$(call log_done,БД сброшена. Далее: make deploy && make import-prod-db)

deploy: server-init
	@test -f $(ENV_PROD) || (echo "$(RED)Создайте $(ENV_PROD) из env.prod.example$(NC)" && exit 1)
	@test -f $(DEPLOY_ENV) || (echo "$(RED)Создайте $(DEPLOY_ENV) из deploy.env.example$(NC)" && exit 1)
	$(call log_banner,Деплой на $(DEPLOY_HOST))
	$(call log_step,1,5,Синхронизация файлов rsync)
	$(call log_info,→ $(DEPLOY_PATH))
	@$(RSYNC) $(RSYNC_EXCLUDES) -e "ssh $(SSH_OPTS)" ./ $(DEPLOY_USER)@$(DEPLOY_HOST):$(DEPLOY_PATH)/
	$(call log_ok,Код синхронизирован)
	$(call log_step,2,5,Копирование secrets)
	@$(SCP) $(ENV_PROD) $(DEPLOY_USER)@$(DEPLOY_HOST):$(DEPLOY_PATH)/secrets/env.prod
	@$(SCP) $(DEPLOY_ENV) $(DEPLOY_USER)@$(DEPLOY_HOST):$(DEPLOY_PATH)/secrets/deploy.env
	$(call log_ok,env.prod + deploy.env)
	$(call log_step,3,5,Сборка и запуск Docker)
	@$(SSH) 'sg docker -c "cd $(DEPLOY_PATH) && $(REMOTE_COMPOSE) up -d --build"'
	$(call log_ok,Контейнеры запущены)
	$(call log_step,4,5,Миграции PostgreSQL)
	@$(SSH) '$(REMOTE_MIGRATE)'
	$(call log_ok,Миграции применены)
	$(call log_step,5,5,Статус сервисов)
	@$(SSH) 'sg docker -c "cd $(DEPLOY_PATH) && $(REMOTE_COMPOSE) ps"' 2>/dev/null || true
	$(call log_done,Деплой завершён — https://$(DEPLOY_DOMAIN))
ifdef IMPORT_DB
	@$(MAKE) --no-print-directory import-prod-db
endif

deploy-initial:
	$(call log_banner,Первый деплой)
	$(call log_info,export → reset-prod-db → deploy → import-prod-db)
	@$(MAKE) --no-print-directory export-dev-db
	@$(MAKE) --no-print-directory reset-prod-db
	@$(MAKE) --no-print-directory deploy
	@$(MAKE) --no-print-directory import-prod-db
