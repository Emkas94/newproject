.PHONY: help dev test build compose-up compose-down lint clean install

help:
	@echo "Доступные команды:"
	@echo "  make install    - Установить зависимости"
	@echo "  make dev        - Запустить dev сервер"
	@echo "  make test       - Запустить тесты"
	@echo "  make lint       - Проверить код линтером"
	@echo "  make build      - Собрать Docker образ"
	@echo "  make compose-up - Запустить через Docker Compose"
	@echo "  make compose-down - Остановить Docker Compose"
	@echo "  make clean      - Очистить временные файлы"

install:
	pip install -r requirements.txt -c constraints.txt

dev:
	uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

test:
	pytest -v

lint:
	flake8 app/ videotext/ tests/
	mypy app/ videotext/ --ignore-missing-imports

build:
	docker build -t turboscribe:latest .

compose-up:
	docker-compose up -d

compose-down:
	docker-compose down

clean:
	find . -type d -name __pycache__ -exec rm -r {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	rm -rf .pytest_cache .mypy_cache
