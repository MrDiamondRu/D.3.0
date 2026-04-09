# D.3.0 CRM

## Dev запуск (Docker)

1. Убедитесь, что установлен Docker Desktop (с `docker compose`).
2. Выполните:
   - `make start` (сборка и запуск dev-контейнера)
   - `make migrate`
   - `make createsuperuser`
   - `make seed`
   - `make import-csv`
3. Админка доступна по адресу `http://127.0.0.1:8000/admin/`.
4. Остановить dev окружение: `make stop`.

## Make команды

- `make start` - запуск `compose.dev.yml` (dev docker compose)
- `make stop` - остановка dev окружения
- `make logs` - логи web-контейнера
- `make shell` - shell в dev-контейнере
- `make makemigrations` - генерация миграций в контейнере
- `make migrate` - применение миграций в контейнере
- `make createsuperuser` - создание администратора в контейнере
- `make seed` - заполнение справочников в контейнере
- `make import-csv` - импорт `template/Михаил.csv` в контейнере
- `make prod-up` - заготовка запуска `compose.prod.yml`

## Docker compose файлы

- `compose.dev.yml` - рабочая dev сборка (реализована)
- `compose.prod.yml` - prod заготовка (web + postgres + caddy)
