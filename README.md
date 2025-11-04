# TurboScribe - Сервис автоматической транскрипции

TurboScribe — это веб-сервис для автоматической транскрипции аудио и видео файлов с использованием Whisper (faster-whisper + ctranslate2). Поддерживает диаризацию спикеров, OCR, перевод, поиск и экспорт в различные форматы.

## Возможности

- 📝 **Транскрипция аудио/видео** с использованием Whisper (faster-whisper)
- 🎤 **Диаризация спикеров** (опционально)
- 📸 **OCR на кадрах** (опционально)
- 🌐 **Перевод** транскрипции на другие языки
- 🔍 **Поиск** и фильтрация по ключевым словам
- 📦 **Экспорт** в SRT, VTT, TXT, DOCX, PDF, CSV, ZIP
- 🌐 **Web UI** с поддержкой HTML5 видео и субтитров
- 🔌 **REST API** для интеграций

## Требования

- **Python 3.12** (рекомендуется)
- **Python 3.11+** (минимальная версия)
- **⚠️ Python 3.14**: ctranslate2 wheels могут быть недоступны. Используйте Docker или Python 3.12 venv.

## Быстрый старт

### 1. Установка зависимостей

```bash
# Создать виртуальное окружение
python3.12 -m venv venv
source venv/bin/activate  # Linux/Mac
# или
venv\Scripts\activate  # Windows

# Установить зависимости
pip install -r requirements.txt -c constraints.txt
```

### 2. Настройка окружения

```bash
# Скопировать пример конфигурации
cp .env.example .env

# Отредактировать .env при необходимости
```

### 3. Запуск приложения

```bash
# Development режим
make dev
# или
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Открыть в браузере
# http://localhost:8000
```

## Docker

### Сборка и запуск

```bash
# Собрать образ
make build

# Запустить через Docker Compose
make compose-up

# Остановить
make compose-down
```

### Прямой запуск Docker

```bash
docker build -t turboscribe:latest .
docker run -p 8000:8000 \
  -v $(pwd)/uploads:/app/uploads \
  -v $(pwd)/artifacts:/app/artifacts \
  --env-file .env \
  turboscribe:latest
```

## Структура проекта

```
.
├── app/
│   ├── main.py          # FastAPI приложение
│   ├── vtt.py           # VTT/SRT writer утилиты
│   ├── templates/       # Jinja2 шаблоны
│   └── static/          # Статические файлы
├── videotext/
│   ├── pipeline.py      # Основной pipeline обработки
│   ├── asr.py           # ASR модуль (faster-whisper)
│   ├── ocr.py           # OCR модуль (Tesseract)
│   └── utils.py         # Вспомогательные функции
├── tests/               # Тесты
├── docs/                # Документация
├── requirements.txt     # Зависимости
├── constraints.txt      # Закрепленные версии
├── Dockerfile           # Docker образ
├── docker-compose.yml   # Docker Compose конфигурация
└── README.md            # Этот файл
```

## API Endpoints

### Основные

- `POST /v1/jobs` - Создать задачу транскрипции
- `GET /v1/jobs/{job_id}` - Получить статус задачи
- `GET /v1/jobs/{job_id}/progress` - SSE поток прогресса
- `GET /v1/jobs/{job_id}/artifacts` - Список артефактов
- `DELETE /v1/jobs/{job_id}` - Отменить задачу
- `POST /v1/jobs/bulk` - Пакетная обработка
- `GET /health` - Health check

Полная документация OpenAPI доступна в `docs/openapi.yaml`.

## Использование

### Web UI

1. Откройте http://localhost:8000
2. Загрузите аудио или видео файл
3. Выберите параметры обработки:
   - Режим: Быстрый / Сбалансированный / Точный
   - Язык: автоопределение или конкретный
   - Диаризация спикеров
   - OCR на кадрах
   - Улучшение аудио
   - Перевод
   - Ключевые слова для фильтрации
4. Нажмите "Начать транскрипцию"
5. Дождитесь завершения и просмотрите результаты

### API

```bash
# Создать задачу
curl -X POST http://localhost:8000/v1/jobs \
  -F "source=@video.mp4" \
  -F "mode=balance" \
  -F "language=ru" \
  -F "diarization=true"

# Получить статус
curl http://localhost:8000/v1/jobs/{job_id}

# Получить прогресс (SSE)
curl http://localhost:8000/v1/jobs/{job_id}/progress
```

## Тестирование

```bash
# Запустить все тесты
make test
# или
pytest -v

# Запустить конкретный тест
pytest tests/test_vtt.py -v
```

## Режимы обработки

- **fast**: Маленькая модель, int8 квантование — максимальная скорость (≥ 0.25× RT)
- **balance**: Средняя модель — баланс скорости и точности (≥ 0.5× RT)
- **accurate**: Большая модель (large-v3) — максимальная точность (≈ 1× RT), рекомендуется GPU

## Форматы файлов

### Поддерживаемые входные форматы

- **Аудио**: MP3, WAV, M4A, OGG, FLAC, AAC
- **Видео**: MP4, MOV, MKV, WEBM, AVI, M4V

### Форматы экспорта

- **SRT** - Стандартные субтитры
- **VTT** - WebVTT для HTML5 видео
- **TXT** - Простой текст
- **JSON** - Полная структура данных
- **DOCX** - Microsoft Word (TODO)
- **PDF** - PDF документ (TODO)
- **CSV** - Таблица с временными метками (TODO)
- **ZIP** - Пакетный экспорт всех артефактов

## Переменные окружения

См. `.env.example` для полного списка переменных окружения.

Основные:
- `DATABASE_URL` - PostgreSQL connection string
- `REDIS_URL` - Redis connection string
- `S3_ENDPOINT_URL` - S3/MinIO endpoint
- `UPLOAD_DIR` - Директория для загрузок
- `ARTIFACTS_DIR` - Директория для артефактов

## Troubleshooting

### Python 3.14: ctranslate2 не устанавливается

**Проблема**: При установке на Python 3.14 возникает ошибка с ctranslate2.

**Решение**:
1. Используйте Docker (рекомендуется):
   ```bash
   docker build -t turboscribe .
   docker run -p 8000:8000 turboscribe
   ```

2. Или создайте Python 3.12 venv:
   ```bash
   python3.12 -m venv venv312
   source venv312/bin/activate
   pip install -r requirements.txt -c constraints.txt
   ```

### faster-whisper не найден

**Проблема**: Модуль faster-whisper не импортируется.

**Решение**:
```bash
pip install faster-whisper ctranslate2
```

Для GPU поддержки убедитесь, что установлены CUDA 12.x драйверы и cuDNN.

### OCR не работает

**Проблема**: OCR возвращает ошибки.

**Решение**:
1. Установите Tesseract:
   ```bash
   # Ubuntu/Debian
   sudo apt-get install tesseract-ocr tesseract-ocr-rus
   
   # macOS
   brew install tesseract tesseract-lang
   ```

2. Установите opencv-python:
   ```bash
   pip install opencv-python pytesseract
   ```

### Порты заняты

**Проблема**: Порты 8000 или 80 уже заняты.

**Решение**: Измените порты в `docker-compose.yml` или используйте переменные окружения.

### Ошибки с базой данных

**Проблема**: Приложение не может подключиться к PostgreSQL.

**Решение**:
1. Убедитесь, что PostgreSQL запущен
2. Проверьте `DATABASE_URL` в `.env`
3. Создайте базу данных:
   ```sql
   CREATE DATABASE turboscribe;
   ```

## Разработка

### Настройка окружения разработки

```bash
# Установить зависимости
make install

# Запустить линтер
make lint

# Запустить тесты
make test

# Запустить dev сервер
make dev
```

### Структура кода

- `app/main.py` - FastAPI application с маршрутами
- `videotext/pipeline.py` - Основной pipeline обработки
- `videotext/asr.py` - ASR транскрипция (stub реализация)
- `videotext/ocr.py` - OCR извлечение (stub реализация)
- `app/vtt.py` - Утилиты для записи VTT/SRT

### Добавление новых функций

1. Создайте feature branch
2. Реализуйте функциональность
3. Добавьте тесты
4. Обновите документацию
5. Создайте Pull Request

## Производительность

Целевые показатели производительности (на GPU T4/A10G):
- **Fast**: ≥ 0.25× RT (real-time)
- **Balance**: ≥ 0.5× RT
- **Accurate**: ≈ 1× RT

Для достижения лучшей производительности:
- Используйте GPU для Accurate режима
- Настройте worker pool для параллельной обработки
- Используйте Redis queue для распределения нагрузки

## Безопасность

- Все API endpoints требуют аутентификации (TODO: реализовать)
- Загруженные файлы проверяются на тип и размер
- S3 объекты используют signed URLs с TTL
- Аудит логирование всех действий пользователей

## Лицензия

[Указать лицензию]

## Контакты

[Указать контакты]
