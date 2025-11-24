<!-- 6e3350fd-62f9-40b2-9567-634b2583e1c5 d30ff196-35fa-4e02-8e1c-323593756c61 -->
# Исправление теста testgetglobaldomainfallbacktolocalhostindevelopment

## Проблема

Тест `test_get_global_domain_fallback_to_localhost_in_development` может падать из-за:

1. Прямого импорта `DB_FILE` вместо использования `temp_db` фикстуры
2. Возможной проблемы с сохранением настройки `server_environment` в БД
3. Необходимости убедиться, что тест работает как на production, так и на development серверах

## Анализ кода

- Тест находится в `tests/unit/test_database/test_domain_settings.py:115`
- Функция `get_global_domain()` в `src/shop_bot/data_manager/database.py:2939`
- Функция `is_development_server()` в `src/shop_bot/data_manager/database.py:2930`
- Функция `get_server_environment()` в `src/shop_bot/data_manager/database.py:2908`

## План исправления

1. **Исправить использование DB_FILE в тесте**

- Заменить прямой импорт `DB_FILE` на использование `temp_db` фикстуры
- Использовать `temp_db` напрямую для подключения к БД

2. **Добавить проверку сохранения настройки**

- После установки `server_environment` проверить, что она действительно сохранилась
- Добавить проверку через `get_server_environment()` перед вызовом `get_global_domain()`

3. **Улучшить диагностику теста**

- Добавить больше allure.attach для отладки
- Добавить проверки промежуточных значений

4. **Проверить работу на разных серверах**

- Убедиться, что тест работает независимо от типа сервера (production/development)
- Тест должен устанавливать окружение явно через `update_setting()`

## Файлы для изменения

- `tests/unit/test_database/test_domain_settings.py` - исправление теста