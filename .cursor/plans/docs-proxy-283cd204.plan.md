<!-- 283cd204-2811-4bf9-90f5-682960415cf6 e7a92bcc-7f23-40cb-9a2e-f03a7f554d4c -->
# План исправления тестов docs-proxy авторизации

## Проблема

Тесты падают из-за:

1. **Мокирование `verify_and_login`** не устанавливает сессию - когда мы мокируем функцию с `return_value=True`, реальная функция не вызывается, и `session['logged_in'] = True` не устанавливается
2. **Flask-Session filesystem sessions** могут иметь проблемы с `session_transaction()` в тестах
3. **Проверка сессии** через `session_transaction()` может не работать корректно с filesystem sessions

## Решение

### 1. Изменить способ мокирования в тестах

Вместо мокирования `verify_and_login`, нужно мокировать `verify_admin_credentials` внутри функции, чтобы реальная функция `verify_and_login` вызывалась и устанавливала сессию.

**Файл:** `tests/unit/test_docs_proxy/test_auth.py`

**Изменения:**

- Заменить `patch.object(docs_proxy_app, 'verify_and_login', return_value=True)` на `patch('shop_bot.data_manager.database.verify_admin_credentials', return_value=True)`
- Это позволит реальной функции `verify_and_login` выполниться и установить сессию

### 2. Исправить проверку сессии в тестах

Для тестов с Flask-Session filesystem sessions нужно использовать альтернативный способ проверки сессии:

- Использовать `session_transaction()` только для установки сессии
- Для проверки использовать запросы к защищенным страницам и проверку статус-кодов

### 3. Исправить тест `test_session_persistence`

Проблема: проверка `sess.get('_permanent', False)` может не работать с filesystem sessions. Нужно проверять через поведение (доступ к защищенным страницам).

### 4. Исправить тест `test_proxy_headers`

Проблема: мокирование `requests` может быть неправильным. Нужно проверить, что мок правильно настроен.

## Файлы для изменения

1. `tests/unit/test_docs_proxy/test_auth.py` - основной файл с тестами

- Исправить все тесты, которые используют мокирование `verify_and_login`
- Изменить способ проверки сессии
- Исправить тест `test_session_persistence`
- Исправить тест `test_proxy_headers`

## Шаги выполнения

1. Проанализировать текущие ошибки в тестах (если есть доступ к логам)
2. Изменить мокирование с `verify_and_login` на `verify_admin_credentials`
3. Исправить проверку сессии в тестах
4. Исправить тест `test_session_persistence`
5. Исправить тест `test_proxy_headers`
6. Запустить тесты и проверить результаты
7. Проверить отчет в Allure
8. При необходимости повторить исправления на основе ошибок из отчета

### To-dos

- [ ] Изменить мокирование с verify_and_login на verify_admin_credentials во всех тестах в test_auth.py
- [ ] Исправить проверку сессии в тестах - использовать альтернативный способ для filesystem sessions
- [ ] Исправить тест test_session_persistence - изменить способ проверки permanent сессии
- [ ] Исправить тест test_proxy_headers - проверить правильность мокирования requests
- [ ] Запустить тесты и проверить результаты
- [ ] Проверить отчет в Allure и исправить оставшиеся ошибки