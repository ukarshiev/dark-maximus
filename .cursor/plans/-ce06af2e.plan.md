<!-- ce06af2e-b060-4322-aabb-e25006dbb25b 6d0cc59c-347a-495f-bece-a61a03d3db30 -->
# Исправление проблемы с потерей сессий при ребилде

## Проблема

После ребилда контейнеров (`docker compose up -d --build`) сессии Flask ломаются во всех сервисах с авторизацией (bot, docs-proxy, allure-homepage), и пользователю приходится заново авторизовываться. Volume mapping для сессий уже настроен, FLASK_SECRET_KEY постоянный, но проблема все равно возникает.

## Корневая причина проблемы

**КРИТИЧНО**: В коде используется fallback, который генерирует новый случайный ключ, если `FLASK_SECRET_KEY` не найден в окружении:

```python
app.config['SECRET_KEY'] = os.getenv('FLASK_SECRET_KEY', secrets.token_hex(32))
```

При ребилде контейнера (`docker compose up -d --build`):

1. Старый контейнер останавливается и удаляется
2. Создается новый контейнер с новым ID
3. Если `FLASK_SECRET_KEY` не передается в контейнер правильно, генерируется новый случайный ключ
4. Новый ключ не может расшифровать старые сессии → сессии становятся невалидными
5. Дополнительно: директории сессий могут быть пересозданы с неправильными правами доступа

## Решение

### Шаг 1: Добавить проверку и логирование загрузки FLASK_SECRET_KEY

В `auth_utils.py` и `app.py` добавить проверку, что `FLASK_SECRET_KEY` загружается из окружения, а не генерируется случайно. Добавить логирование для диагностики.

### Шаг 2: Добавить предупреждение при использовании fallback

Если `FLASK_SECRET_KEY` не найден в окружении, вывести предупреждение в лог, чтобы было видно проблему.

### Шаг 3: Установить права доступа при создании директорий

В функции `init_flask_auth` и в коде webhook_server добавить установку прав доступа (755) при создании директории сессий.

### Шаг 4: Создать .gitkeep файлы

Создать `.gitkeep` файлы в директориях сессий, чтобы они сохранялись в git и не удалялись случайно.

## Файлы для изменения

1. **Обновить `src/shop_bot/webhook_server/auth_utils.py`**:

   - В функции `init_flask_auth` (строка 26) добавить проверку и логирование загрузки `FLASK_SECRET_KEY`
   - Добавить предупреждение, если ключ не найден и используется fallback
   - После `os.makedirs(session_dir, exist_ok=True)` (строка 43) добавить `os.chmod(session_dir, 0o755)`

2. **Обновить `src/shop_bot/webhook_server/app.py`**:

   - В строке 275 добавить проверку и логирование загрузки `FLASK_SECRET_KEY`
   - Добавить предупреждение, если ключ не найден и используется fallback
   - После строки 294 (`os.makedirs('/app/sessions', exist_ok=True)`) добавить `os.chmod('/app/sessions', 0o755)`

3. **Создать `.gitkeep` файлы**:

   - `sessions/.gitkeep`
   - `sessions-docs/.gitkeep`
   - `sessions-allure/.gitkeep`

## Детали реализации

### В `auth_utils.py` (строки 25-26, 43):

```python
# Безопасное получение секретного ключа из переменных окружения
import logging
logger = logging.getLogger(__name__)

secret_key = os.getenv('FLASK_SECRET_KEY')
if not secret_key:
    logger.warning("⚠️ FLASK_SECRET_KEY не найден в окружении! Генерируется новый случайный ключ. "
                   "Это приведет к потере всех существующих сессий!")
    secret_key = secrets.token_hex(32)
else:
    logger.info("✓ FLASK_SECRET_KEY успешно загружен из окружения")
app.config['SECRET_KEY'] = secret_key

# ... остальной код ...

# Создаем директорию для сессий, если её нет
os.makedirs(session_dir, exist_ok=True)
os.chmod(session_dir, 0o755)  # Установить права доступа 755
```

### В `app.py` (строки 274-275, 294):

```python
import secrets
secret_key = os.getenv('FLASK_SECRET_KEY')
if not secret_key:
    logger.warning("⚠️ FLASK_SECRET_KEY не найден в окружении! Генерируется новый случайный ключ. "
                   "Это приведет к потере всех существующих сессий!")
    secret_key = secrets.token_hex(32)
else:
    logger.info("✓ FLASK_SECRET_KEY успешно загружен из окружения")
flask_app.config['SECRET_KEY'] = secret_key

# ... остальной код ...

os.makedirs('/app/sessions', exist_ok=True)
os.chmod('/app/sessions', 0o755)  # Установить права доступа 755
```

## Проверка

После внесения изменений проверить:

1. В логах контейнеров видно сообщение "✓ FLASK_SECRET_KEY успешно загружен из окружения" (НЕ должно быть предупреждения о генерации нового ключа)
2. Директории сессий существуют на хосте и имеют правильные права доступа (755)
3. При ребилде контейнеров (`docker compose up -d --build`) сессии сохраняются
4. После ребилда авторизация работает без необходимости повторного входа во всех сервисах (bot, docs-proxy, allure-homepage)

## Диагностика

Если проблема сохраняется после внесения изменений:

1. Проверить логи контейнеров на наличие предупреждения о генерации нового ключа: `docker compose logs bot | grep FLASK_SECRET_KEY`
2. Проверить, что `FLASK_SECRET_KEY` действительно передается в контейнер: `docker compose exec bot env | grep FLASK_SECRET_KEY`
3. Проверить права доступа к директориям сессий на хосте: `ls -la sessions/ sessions-docs/ sessions-allure/`
4. Проверить, что файлы сессий существуют и не удаляются при ребилде