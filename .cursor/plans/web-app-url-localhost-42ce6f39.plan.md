<!-- 42ce6f39-eb98-4401-8ebe-7ee492916bae a4f4b283-e11c-49f6-a121-468da177c3d2 -->
# Добавление настройки server_environment для управления окружением

## Цель

Централизованное управление окружением сервера через единую настройку в БД, что упростит код и исключит множественные проверки на localhost в разных местах.

## Требования

1. Настройка `server_environment` со значениями: `"development"` / `"production"`
2. По умолчанию: `"production"` при первой установке
3. НЕ трогать YooKassa (оставить ручное управление `yookassa_test_mode`)
4. Development = использовать localhost, Production = использовать настройки доменов из БД
5. Fallback логика: сначала проверять настройки доменов, если они localhost - использовать их, иначе fallback на localhost
6. UI: выпадающий список с названием **"Тип сервера"** и значениями **"development"** / **"production"**

## Файлы для изменения (8 файлов, ~15 мест)

### 1. `src/shop_bot/data_manager/database.py`

- Добавить функцию `get_server_environment()` → `"development"` | `"production"`
- Добавить функцию `is_production_server()` → `bool`
- Добавить функцию `is_development_server()` → `bool`
- Добавить миграцию для создания настройки `server_environment` со значением по умолчанию `"production"`
- Обновить `get_global_domain()` (строка 2902) - заменить fallback на localhost проверкой окружения

### 2. `src/shop_bot/webhook_server/templates/settings.html`

- Добавить выпадающий список **"Тип сервера"** для `server_environment` в раздел "Глобальные параметры"
- Значения: "development" / "production" (без эмодзи и дополнительных текстов)

### 3. `src/shop_bot/webhook_server/app.py`

- Добавить `server_environment` в список `panel_keys` для сохранения (строка 1184)
- Обновить логику выбора доменов в `dashboard_page()` (строки 460-503):
  - `wiki_url` (строка 472)
  - `knowledge_base_url` (строка 490)
  - `allure_url` (строка 503)
- Обновить `get_latest_cabinet_link()` (строки 536-539) - fallback на localhost для `cabinet_domain`

### 4. `src/shop_bot/bot/keyboards.py`

- Обновить `create_key_info_keyboard()` (строки 562-582) для использования `is_production_server()` вместо проверки localhost

### 5. `src/shop_bot/bot/handlers.py` (7 мест)

- Строка 529: проверка domain для terms/privacy URL
- Строка 717: проверка domain для terms/privacy URL
- Строки 727-729: дополнительные проверки terms_url/privacy_url на localhost
- Строка 2042: проверка domain для terms/privacy URL
- Строка 2971: проверка domain для terms/privacy URL
- Строка 7760: проверка domain для terms/privacy URL
- Строка 7789: проверка domain для terms/privacy URL

### 6. `src/shop_bot/bot/support_handlers.py`

- Обновить проверку domain (строка 38) для terms/privacy URL

### 7. `src/shop_bot/bot/optimized_handlers.py`

- Обновить проверку domain (строка 251) для terms/privacy URL

### 8. `src/shop_bot/webhook_server/auth_utils.py`

- НЕ ТРОГАТЬ - техническая настройка для работы сессий между портами localhost

## Детали реализации

### 1. Функции в database.py

Добавить после функции `get_setting()`:

```python
def get_server_environment() -> str:
    """
    Получает текущее окружение сервера из настроек.
    
    Returns:
        "development" или "production" (по умолчанию "production")
    """
    env = get_setting("server_environment")
    if env in ("development", "production"):
        return env
    # По умолчанию production для безопасности
    return "production"

def is_production_server() -> bool:
    """
    Проверяет, запущен ли сервер в production окружении.
    
    Returns:
        True если окружение "production", False если "development"
    """
    return get_server_environment() == "production"

def is_development_server() -> bool:
    """
    Проверяет, запущен ли сервер в development окружении.
    
    Returns:
        True если окружение "development", False если "production"
    """
    return get_server_environment() == "development"
```

### 2. Миграция в database.py

Добавить в функцию `run_migration()` после существующих миграций:

```python
# Миграция: добавляем настройку server_environment
logging.info("The migration of the setting 'server_environment' ...")
try:
    existing_env = get_setting("server_environment")
    if existing_env is None:
        # Создаем настройку со значением по умолчанию "production"
        update_setting("server_environment", "production")
        logging.info(" -> The setting 'server_environment' is successfully added with default value 'production'.")
    else:
        logging.debug(" -> The setting 'server_environment' already exists.")
except Exception as e:
    logging.warning(f" -> Failed to add setting 'server_environment': {e}")
```

### 3. Обновление get_global_domain() в database.py

Заменить строки 2901-2902:

**Было:**

```python
# Fallback на localhost для разработки
return "https://localhost:8443"
```

**Станет:**

```python
# Fallback зависит от окружения
if is_development_server():
    return "https://localhost:8443"
else:
    # В production возвращаем None если домен не настроен
    return None
```

### 4. UI в settings.html

Добавить в раздел "Глобальные параметры" (после `admin_timezone`, перед закрывающим `</section>`):

```html
<div class="form-group">
    <label for="server_environment">Тип сервера:</label>
    <select
        id="server_environment"
        name="server_environment"
        title="Определяет режим работы сервера: development использует localhost, production использует настроенные домены"
    >
        <option value="production" {% if settings.server_environment != 'development' %}selected{% endif %}>
            production
        </option>
        <option value="development" {% if settings.server_environment == 'development' %}selected{% endif %}>
            development
        </option>
    </select>
    <small class="text-muted">
        <strong>production:</strong> используются настроенные домены из полей ниже.<br>
        <strong>development:</strong> используются localhost адреса для всех сервисов.
    </small>
</div>
```

### 5. Обновление app.py для сохранения настройки

В функции `save_panel_settings()` добавить `server_environment` в список `panel_keys` (строка 1184):

```python
panel_keys = ['panel_login', 'global_domain', 'docs_domain', 'codex_docs_domain', 
              'user_cabinet_domain', 'allure_domain', 'admin_timezone', 
              'server_environment',  # Добавить эту строку
              'monitoring_max_metrics', 'monitoring_slow_threshold', 'monitoring_cleanup_hours']
```

### 6. Обновление логики выбора доменов в app.py

Заменить логику в функции `dashboard_page()` (строки 460-503):

**Было:**

```python
if docs_domain:
    wiki_url = docs_domain
else:
    wiki_url = 'http://localhost:50001'
```

**Станет:**

```python
from shop_bot.data_manager.database import is_development_server

if is_development_server():
    wiki_url = 'http://localhost:50001'
elif docs_domain:
    wiki_url = docs_domain
else:
    wiki_url = 'http://localhost:50001'  # Fallback
```

Аналогично для `knowledge_base_url` (строка 490) и `allure_url` (строка 503).

### 7. Обновление get_latest_cabinet_link() в app.py

Заменить строки 537-539:

**Было:**

```python
if not cabinet_domain:
    cabinet_domain = "http://localhost:50003"
```

**Станет:**

```python
from shop_bot.data_manager.database import is_development_server

if not cabinet_domain:
    if is_development_server():
        cabinet_domain = "http://localhost:50003"
    else:
        # В production возвращаем None если домен не настроен
        return None
```

### 8. Обновление keyboards.py

В функции `create_key_info_keyboard()` заменить строки 562-582:

**Было:**

```python
if codex_docs_domain and not _is_local_address(codex_docs_domain):
    setup_url = normalize_web_app_url(f"{codex_docs_domain}/setup")
    if _is_local_address(setup_url):
        setup_url = "https://help.dark-maximus.com/setup"
else:
    setup_url = "https://help.dark-maximus.com/setup"
```

**Станет:**

```python
from shop_bot.data_manager.database import is_production_server

if is_production_server() and codex_docs_domain and not _is_local_address(codex_docs_domain):
    setup_url = normalize_web_app_url(f"{codex_docs_domain}/setup")
    if _is_local_address(setup_url):
        logger.warning(f"Local address detected in setup_url: {setup_url}. Using fallback URL.")
        setup_url = "https://help.dark-maximus.com/setup"
elif is_development_server():
    # В development всегда используем fallback (localhost не поддерживается в Web App)
    setup_url = "https://help.dark-maximus.com/setup"
else:
    # Fallback для production если настройка не заполнена
    setup_url = "https://help.dark-maximus.com/setup"
```

### 9. Обновление handlers.py (7 мест)

Заменить все проверки вида:

```python
if domain and not domain.startswith("http://localhost") and not domain.startswith("https://localhost"):
```

На:

```python
from shop_bot.data_manager.database import is_production_server
from shop_bot.bot.keyboards import _is_local_address

if is_production_server() and domain and not _is_local_address(domain):
```

Также удалить дополнительные проверки на localhost (строки 727-729), так как они будут избыточны.

### 10. Обновление support_handlers.py

Заменить строку 38 аналогично handlers.py.

### 11. Обновление optimized_handlers.py

Заменить строку 251 аналогично handlers.py.

## Лучшие практики (из Context7)

1. **Типизация**: Использовать строгие типы (`"development"` | `"production"`) с валидацией
2. **Безопасность по умолчанию**: Значение по умолчанию `"production"` для предотвращения случайного использования тестовых настроек
3. **Консистентность**: Единые функции-хелперы для проверки окружения во всем коде
4. **Валидация**: Проверка допустимых значений при сохранении настройки
5. **Документация**: Понятные docstrings для всех новых функций
6. **Миграции**: Безопасное добавление настройки с проверкой существования

## Тестирование

После реализации проверить:

1. Переключение окружения в панели настроек работает корректно
2. В development режиме используются localhost адреса
3. В production режиме используются настройки доменов из БД
4. Fallback логика работает правильно
5. YooKassa настройки не затронуты (остаются ручными)
6. Миграция создает настройку со значением "production" по умолчанию
7. Все места, где проверялся localhost, теперь используют новые функции