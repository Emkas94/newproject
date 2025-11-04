# Системное проектирование: TurboScribe-подобный сервис транскрипции

## Архитектура

### Компоненты системы

```
┌─────────────┐      ┌──────────────┐      ┌─────────────┐
│   Web UI    │──────│   FastAPI     │──────│  PostgreSQL │
│  (HTMX)     │      │   (REST/SSE)  │      │  (Metadata) │
└─────────────┘      └──────────────┘      └─────────────┘
                            │                       │
                            │                       │
                     ┌──────▼──────┐      ┌────────▼────────┐
                     │   Redis/RQ   │      │   S3/MinIO      │
                     │   (Queue)    │      │  (Media/Art)   │
                     └──────┬──────┘      └─────────────────┘
                            │
                     ┌──────▼──────┐
                     │   Workers   │
                     │  (GPU/CPU)  │
                     └─────────────┘
```

### Основные слои

1. **API Layer (FastAPI)**
   - REST endpoints для управления задачами
   - SSE для прогресса в реальном времени
   - Web UI через Jinja2 + HTMX
   - Аутентификация (session/JWT + API keys)

2. **Queue Layer (Redis/RQ)**
   - Приоритетные очереди по планам пользователей
   - Retry механизм с экспоненциальной задержкой
   - Таймауты и обработка ошибок

3. **Worker Layer**
   - ASR Workers (faster-whisper + ctranslate2)
   - OCR Workers (Tesseract, опционально)
   - Диаризация (pyannote.audio)
   - Экспорт (SRT/VTT/TXT/DOCX/PDF/CSV/ZIP)

4. **Storage Layer**
   - PostgreSQL: метаданные, пользователи, биллинг
   - S3/MinIO: исходные файлы, артефакты, подписи
   - Redis: кэш, сессии, очереди

## Очереди и обработка задач

### Приоритеты очередей

- `high`: Pro/Team планы (обработка сразу)
- `normal`: Free план (стандартная очередь)
- `bulk`: Пакетные операции (низкий приоритет)

### Жизненный цикл задачи

```
CREATED → QUEUED → DOWNLOADING → PROCESSING → ASR → [DIARIZATION] → [OCR] → [TRANSLATION] → EXPORTING → COMPLETED
                                                                    ↓
                                                              FAILED (с retry)
```

### Обработка ошибок

- Максимум 3 повторных попытки на этап
- Экспоненциальная задержка: 1s, 5s, 30s
- Критические ошибки → FAILED без retry
- Таймауты: скачивание (10 мин), ASR (4× длительность), экспорт (5 мин)

## Хранилище данных

### PostgreSQL схемы

- `users`: аккаунты, планы, квоты
- `orgs`: организации, роли
- `jobs`: задачи, статусы, прогресс
- `artifacts`: ссылки на S3 объекты
- `api_keys`: ключи для публичного API
- `billing_events`: события Stripe
- `audit`: логи действий пользователей

### S3 структура

```
s3://bucket/
  uploads/{job_id}/original.{ext}        # Исходный файл
  artifacts/{job_id}/
    asr.srt                               # ASR результат
    ocr.srt                               # OCR результат (если включен)
    merged.srt                            # Объединенный
    merged.vtt                            # WebVTT
    output.json                           # Полный JSON
    asr.txt, ocr.txt, merged.txt          # Текстовые экспорты
    keywords.*                             # Фильтрованные по ключевым словам
    results.zip                           # Пакетный экспорт
```

### Индексы

- `jobs(org_id, status, created_at)` - фильтрация по организации
- `jobs(user_id, status)` - история пользователя
- `artifacts(job_id, type)` - быстрый поиск артефактов
- `api_keys(key_hash)` - валидация API ключей

## Масштабирование

### Горизонтальное масштабирование

- **API**: stateless, можно запускать несколько экземпляров за nginx
- **Workers**: пул воркеров с GPU/CPU нодами
- **PostgreSQL**: read replicas для тяжелых запросов
- **S3**: автоматически масштабируется

### Вертикальное масштабирование

- GPU nodes: T4/A10G для Accurate режима
- CPU nodes: для Fast/Balance режимов
- Распределение нагрузки по типу модели

### Производительность

- **Fast**: ≥ 0.25× RT (real-time)
- **Balance**: ≥ 0.5× RT
- **Accurate**: ≈ 1× RT

Target: обработка 50 файлов в пакете за 2-4 часа (зависит от режима).

## Режимы отказа и устойчивость

### Типичные сценарии отказа

1. **Worker crash**
   - Задача возвращается в очередь
   - Retry механизм
   - Alerting через Prometheus

2. **S3 недоступен**
   - Retry с экспоненциальной задержкой
   - Временное хранение в локальной файловой системе
   - Graceful degradation

3. **PostgreSQL недоступен**
   - Критично: API возвращает 503
   - Workers продолжают работу с кэшем в Redis
   - Автоматическое восстановление при доступности

4. **GPU OOM**
   - Fallback на CPU режим
   - Логирование для масштабирования
   - Предупреждение пользователю

5. **Превышение квоты**
   - Блокировка новых задач
   - Уведомление пользователя
   - Graceful handling в UI

### Мониторинг и observability

- **Prometheus**: метрики по задачам, времени обработки, ошибкам
- **JSON логи**: структурированные с job_id, run_id, trace_id
- **OpenTelemetry**: трейсинг между компонентами
- **Healthchecks**: `/health`, `/ready` endpoints

### Резервное копирование

- PostgreSQL: ежедневные snapshots
- S3: versioning включен
- Конфигурация: versioned в git

## Безопасность и приватность

- HTTPS только (TLS 1.3)
- S3 server-side encryption (SSE-S3)
- Signed URLs с TTL для артефактов
- Retention policies: автоматическое удаление через 90 дней (Free), 365 дней (Pro/Team)
- GDPR deletion: полное удаление по запросу
- Audit log: все действия пользователей логируются

## Оптимизации

- Batch processing для экспорта
- Streaming для больших файлов
- Кэширование моделей Whisper в памяти
- Lazy loading диаризации моделей
- Компрессия артефактов в ZIP
