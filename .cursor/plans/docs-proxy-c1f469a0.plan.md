<!-- c1f469a0-cd73-44eb-a203-687b0d026924 55892ab5-b9f5-4111-b666-ba4d2b94b37b -->
# Исправление ошибки авторизации в docs-proxy

## Проблема

После ребилда страницы авторизации выдают ошибку "Internal Server Error" при попытке входа:

- `http://localhost:50001/login` (docs-proxy)
- `http://localhost:50005/login` (allure-homepage)

**Ошибка в логах:**

```
AttributeError: 'NoneType' object has no attribute 'vary'
File "/app/src/shop_bot/webhook_server/auth_utils.py", line 108, in verify_and_login
    session_interface.save_session(current_app, session, None)
```

Оба сервиса используют общую функцию `verify_and_login` из `auth_utils.py`, поэтому исправление в одном месте решит проблему для обоих сервисов.

## Причина (подтверждено фактами)

**100% подтвержденная проблема** - проверено через логи, код и документацию:

1. **Факт из логов:** Ошибка `AttributeError: 'NoneType' object has no attribute 'vary'` происходит в `flask_session/base.py:290` при вызове `response.vary.add("Cookie")`, где `response` равен `None`.

2. **Факт из кода:** В функции `verify_and_login` в файле `src/shop_bot/webhook_server/auth_utils.py` на строке 108 происходит явный вызов `save_session` с параметром `None` вместо объекта Response:
   ```python
   session_interface.save_session(current_app, session, None)  # ← None вместо Response
   ```

3. **Факт из документации Flask-Session:** Метод `save_session(app, session, response)` требует объект Response в качестве третьего параметра. Внутри метода происходит обращение к `response.vary.add("Cookie")`, что вызывает ошибку при передаче `None`.

4. **Факт из использования:** В функции `verify_and_login` нет доступа к объекту Response, так как она вызывается из view-функции до создания Response.

5. **Факт из Flask-Session:** Flask-Session автоматически сохраняет сессию в конце запроса, если `session.modified = True` (что уже установлено в коде на строке 98). Явный вызов `save_session` не требуется и вызывает ошибку.

## Решение

Удалить явный вызов `save_session` из функции `verify_and_login` и полагаться на автоматическое сохранение сессии Flask-Session в конце запроса.

## Изменения

### Файл: `src/shop_bot/webhook_server/auth_utils.py`

**Строки 100-112:** Удалить блок с явным вызовом `save_session` и оставить только установку `session.modified = True`.

**Было:**

```python
# Явно сохраняем сессию на диск для предотвращения потери при перезапуске контейнера
# Flask-Session использует lazy saving, поэтому нужно явно вызвать сохранение
try:
    # Проверяем, что мы в контексте запроса Flask
    if hasattr(current_app, 'session_interface'):
        session_interface = current_app.session_interface
        if hasattr(session_interface, 'save_session'):
            # Сохраняем сессию немедленно
            session_interface.save_session(current_app, session, None)
except RuntimeError:
    # Если мы не в контексте запроса, session.modified = True достаточно
    # Flask-Session сохранит сессию в конце запроса
    pass
```

**Станет:**

```python
# Flask-Session автоматически сохранит сессию в конце запроса,
# так как session.modified = True установлено выше
# Явный вызов save_session не требуется и вызывает ошибку,
# так как требует объект Response, который недоступен в этой функции
```

## Сервисы с авторизацией

В проекте есть три сервиса с авторизацией:

1. **docs-proxy** (порт 50001) - использует `verify_and_login` из `auth_utils.py` ✅ **проблема**
2. **allure-homepage** (порт 50005) - использует `verify_and_login` из `auth_utils.py` ✅ **проблема**
3. **webhook_server** (порт 50000) - использует свою реализацию `login_page`, которая напрямую вызывает `verify_admin_credentials` и устанавливает сессию без использования `verify_and_login` ❌ **проблемы нет**

Исправление в `auth_utils.py` решит проблему для обоих затронутых сервисов (docs-proxy и allure-homepage).

## Тестирование

После исправления проверить:

1. Авторизация на `http://localhost:50001/login` (docs-proxy) работает без ошибок
2. Авторизация на `http://localhost:50005/login` (allure-homepage) работает без ошибок
3. Сессия сохраняется и работает между запросами на обоих сервисах
4. Логи не содержат ошибок AttributeError

## Создание тестов для предотвращения подобных проблем

### Цель

Создать интеграционные тесты, которые проверяют реальную авторизацию на всех сервисах с авторизацией, чтобы предотвратить подобные проблемы в будущем.

### Тесты для создания

#### 1. Интеграционный тест авторизации для всех сервисов

**Файл:** `tests/integration/test_auth_all_services/test_login_integration.py`

**Что проверять:**

- Успешная авторизация на всех сервисах (docs-proxy, allure-homepage, webhook_server)
- Отсутствие ошибок AttributeError при авторизации
- Корректное сохранение сессии после авторизации
- Работа сессии между запросами
- Обработка неверных учетных данных

**Структура теста:**

```python
@pytest.mark.integration
@allure.epic("Интеграционные тесты")
@allure.feature("Авторизация на всех сервисах")
class TestAuthAllServices:
    """Тесты авторизации для всех сервисов проекта"""
    
    @pytest.mark.parametrize("service_name,port,base_url", [
        ("docs-proxy", 50001, "http://localhost:50001"),
        ("allure-homepage", 50005, "http://localhost:50005"),
        ("webhook_server", 50000, "http://localhost:50000"),
    ])
    def test_login_success_no_errors(self, service_name, port, base_url, admin_credentials):
        """Проверяет успешную авторизацию без ошибок AttributeError"""
        # Тест авторизации через реальные HTTP запросы
        
    def test_login_failure_no_errors(self, ...):
        """Проверяет обработку неверных данных без ошибок"""
        
    def test_session_persistence(self, ...):
        """Проверяет сохранение сессии между запросами"""
```

#### 2. Тест проверки отсутствия ошибок в логах

**Файл:** `tests/integration/test_auth_all_services/test_auth_error_detection.py`

**Что проверять:**

- При авторизации не должно быть ошибок AttributeError в логах
- При авторизации не должно быть ошибок, связанных с session_interface.save_session
- Проверка через анализ логов контейнеров или перехват исключений

#### 3. Обновление существующих unit-тестов

**Файлы:**

- `tests/unit/test_docs_proxy/test_auth.py` - уже существует
- `tests/unit/test_allure_homepage/test_auth.py` - уже существует

**Что добавить:**

- Явную проверку отсутствия ошибок AttributeError при вызове `verify_and_login`
- Проверку, что сессия сохраняется корректно без явного вызова `save_session`

### Структура директорий

```
tests/
├── integration/
│   └── test_auth_all_services/
│       ├── __init__.py
│       ├── test_login_integration.py      # Основные интеграционные тесты
│       ├── test_auth_error_detection.py    # Проверка отсутствия ошибок
│       └── conftest.py                     # Фикстуры для всех сервисов
```

### Фикстуры для тестов

**Файл:** `tests/integration/test_auth_all_services/conftest.py`

Создать фикстуры:

- `admin_credentials` - учетные данные для авторизации
- `service_client(service_name, port)` - клиент для каждого сервиса
- `check_service_available(port)` - проверка доступности сервиса

### Интеграция в CI/CD

Добавить запуск этих тестов в CI/CD pipeline:

- После каждого ребилда контейнеров
- Перед деплоем на production
- При изменении кода авторизации

## Дополнительные проверки

- ✅ Проверить, что аналогичная проблема не существует в других местах использования `verify_and_login` (allure-homepage, docs-proxy) - **проверено, проблема только в auth_utils.py**
- ✅ Убедиться, что тесты в `tests/unit/test_docs_proxy/test_auth.py` проходят
- ✅ Убедиться, что тесты в `tests/unit/test_allure_homepage/test_auth.py` проходят