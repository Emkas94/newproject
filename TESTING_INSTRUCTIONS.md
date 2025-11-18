# Как запустить и протестировать чат локально

Эти шаги используют встроенный офлайн-стек (стабы FastAPI/TestClient и простой HTTPServer), поэтому не требуют установки пакетов. При желании вы можете установить зависимости из `requirements.txt` и запускать сервер через uvicorn, но базовый сценарий ниже работает «из коробки».

## 1. Требования
- Python 3.11+
- Доступ к файловой системе (загрузка вложений сохраняет их в папку `uploads/` рядом с репозиторием)

## 2. Поднять сервер
```bash
python serve.py
```
Вы увидите сообщение `Serving chat API on http://0.0.0.0:8000`. Сервер слушает HTTP на 8000 порту и сразу инициализирует SQLite-базу в файле `chat.db`.

## 3. Ручная проверка через веб-интерфейс
1. Откройте браузер на `http://localhost:8000/`.
2. В левом сайдбаре создайте пользователей (при необходимости включите флаг «Админ»).
3. Создайте приватный или групповой чат, выберите его и отправьте текст, эмодзи или вложение (файл).
4. Для проверки избранного нажмите ⭐ у чата или конкретного сообщения — элементы попадут в панель «Избранное».
5. Если пользователь — админ, в секции «Админ-панель» укажите его ID и ID чата, чтобы открыть логи и удалять сообщения.

## 4. Быстрые API-примеры (curl)
```bash
# создать двух пользователей
curl -X POST http://localhost:8000/users -H "Content-Type: application/json" -d '{"username":"alice"}'
curl -X POST http://localhost:8000/users -H "Content-Type: application/json" -d '{"username":"bob"}'

# создать приватный чат
curl -X POST http://localhost:8000/chats -H "Content-Type: application/json" -d '{"participant_ids":[1,2],"is_group":false}'

# отправить текст от alice
curl -X POST http://localhost:8000/chats/1/messages -F "sender_id=1" -F "content=Привет!"

# отправить файл (создаст уникальный префикс в uploads/)
curl -X POST http://localhost:8000/chats/1/messages -F "sender_id=1" -F "file=@README.md"

# отметить чат избранным
curl -X POST http://localhost:8000/favorites/chats -H "Content-Type: application/json" -d '{"user_id":1,"chat_id":1}'

# получить логи чата (требуется admin_id)
curl "http://localhost:8000/admin/chats/1/logs?admin_id=1"
```

## 5. Автоматические тесты
Тесты используют встроенный TestClient и локальную БД, поэтому никаких доп. пакетов не нужно.
```bash
pytest
```

## 6. Очистка окружения
После тестов при необходимости удалите артефакты:
```bash
rm -rf chat.db uploads/
```
