<!-- fc0bd5fd-de8b-4cf8-a7f6-3c12291c635a 9932e612-1a74-44f8-89c3-ea532a045579 -->
# Исправление Flask сессий и авторизации

## Диагностика проблемы

По логам выявлено:

- Cookie отправляется браузером (`cookie_in_request=present`)
- Файл сессии не существует (`session_file_exists=no`)
- Сессия не читается (`logged_in=False`)

**Наиболее вероятная причина (80%)**: `SameSite=None` блокируется браузером Chrome 80+ на localhost, так как требует `Secure=True`, но для HTTP это не работает.

## Решение (приоритетный порядок)

### 1. КРИТИЧНО: Исправление настроек cookie для localhost

**Файл:** `src/shop_bot/webhook_server/auth_utils.py`

**Проблема**: `SameSite=None` требует `Secure=True` в Chrome 80+, но для localhost (HTTP) это невозможно. Браузер игнорирует cookie.

**Решение**: Использовать `SameSite=Lax` для localhost вместо `SameSite=None`

**Изменения:**

```python
# Для localhost (HTTP) - ИСПРАВЛЕНИЕ ПРИОРИТЕТНОЕ
app.config['SESSION_COOKIE_SECURE'] = False
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'  # Вместо 'None' - это ключевое исправление!

# Для production (HTTPS)
if os.getenv('FLASK_ENV') == 'production':
    app.config['SESSION_COOKIE_SECURE'] = True
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
```

**Почему это должно помочь**: `SameSite=Lax` работает с HTTP на localhost и позволяет cookie передаваться между запросами.

### 2. Обновление на CacheLibSessionInterface (если SameSite не поможет)

**Файл:** `src/shop_bot/webhook_server/auth_utils.py`

- Заменить устаревший `SESSION_FILE_DIR` на `SESSION_CACHELIB` с `FileSystemCache`
- Использовать современный API Flask-Session 0.8.0

**Изменения:**

```python
from cachelib import FileSystemCache

# Создаем cache для сессий
cache = FileSystemCache(
    cache_dir=session_dir,
    threshold=500,
    mode=0o600
)
app.config['SESSION_TYPE'] = 'cachelib'
app.config['SESSION_CACHELIB'] = cache
# Убрать app.config['SESSION_FILE_DIR'] = session_dir
```

**Примечание**: Это делаем только если исправление SameSite не решит проблему.

### 3. Упрощение кода авторизации

**Файл:** `src/shop_bot/webhook_server/app.py`

- Убрать избыточное логирование из маршрута `/login` (строки 406-480)
- Упростить логику установки сессии
- Убрать дублирование в `after_request_func` (строки 6467-6495)

**Изменения:**

- Оставить только критичное логирование (успешный/неуспешный login)
- Убрать детальные проверки Set-Cookie header
- Упростить after_request handler - убрать дублирование save_session

### 4. Упрощение login_required декоратора

**Файл:** `src/shop_bot/webhook_server/auth_utils.py`

- Убрать избыточное логирование и проверки файлов сессий (строки 96-108)
- Оставить только проверку `logged_in` в session
- Упростить логику до минимума

### 5. Установка срока жизни 30 дней

**Файл:** `src/shop_bot/webhook_server/auth_utils.py`

- Убедиться, что `PERMANENT_SESSION_LIFETIME = timedelta(days=30)` (уже установлено)
- Убедиться, что `SESSION_COOKIE_MAX_AGE = 30 * 24 * 60 * 60` (уже установлено)
- Убедиться, что `session.permanent = True` устанавливается при логине (уже установлено)

## Файлы для изменения

1. `src/shop_bot/webhook_server/auth_utils.py` - основная логика сессий (приоритет: SameSite)
2. `src/shop_bot/webhook_server/app.py` - маршрут login и after_request (упрощение)

## Тестирование

1. **Авторизация на http://localhost:50000/login** - проверить, что cookie устанавливается
2. **Проверка cookie в DevTools** - убедиться, что cookie присутствует с правильными атрибутами
3. **Редирект на /dashboard** - проверить, что сессия сохраняется и пользователь авторизован
4. **Переход на другие страницы** - проверить, что сессия работает
5. **Проверка cookie expiration** - убедиться, что Max-Age = 2592000 (30 дней)
6. **Проверка кнопки "Кабинет"** - убедиться, что работает после авторизации

## Зависимости

- Flask-Session 0.8.0 уже установлен
- `cachelib` нужно проверить/добавить в pyproject.toml (только если переходим на cachelib)

### To-dos

- [ ] КРИТИЧНО: Исправить SameSite=None на SameSite=Lax для localhost в auth_utils.py
- [ ] Упростить маршрут /login в app.py: убрать избыточное логирование (строки 406-480)
- [ ] Упростить login_required декоратор: убрать проверки файлов сессий (строки 96-108)
- [ ] Упростить after_request handler: убрать дублирование save_session
- [ ] Протестировать авторизацию через веб-интерфейс после исправления SameSite
- [ ] Если SameSite не помог: обновить на CacheLibSessionInterface с FileSystemCache
- [ ] Проверить/добавить cachelib в pyproject.toml (только если нужно)