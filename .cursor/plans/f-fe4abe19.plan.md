<!-- fe4abe19-35cc-4d30-bb57-7c9571db2dfd 9a3231c6-fbdc-4106-84bb-0db790b011a2 -->
# Исправление теста test_initialization_existing_users

## Проблема

Тест `test_initialization_existing_users` падает с ошибкой `NameError: name 'original_db_file' is not defined`. Переменная `original_db_file` определяется внутри блока `try` на строке 275, но если исключение произойдет до этой строки, переменная не будет определена, и при попытке восстановления на строке 346 возникнет NameError.

## Решение

### 1. Исправление NameError

**Файл:** `tests/unit/test_database/test_key_numbering.py`

**Изменения:**

- Инициализировать `original_db_file` до блока `try` (перед строкой 272)
- Добавить безопасное восстановление в блоке `finally` с проверкой существования переменной
- Использовать паттерн из `test_keys_count_migration` (строки 48-77) как эталон

**Конкретные изменения:**

- Переместить импорт `shop_bot.data_manager.database as db_module` и инициализацию `original_db_file = db_module.DB_FILE` до блока `try`
- В блоке `finally` добавить проверку `if 'original_db_file' in locals():` перед восстановлением
- Упростить логику очистки временной БД

### 2. Добавление Allure аннотаций

**Согласно правилам из `testing-rules.mdc`:**

**Обязательные аннотации:**

- `@allure.title` - краткое описание теста
- `@allure.description` - структурированное описание с разделами:
- Краткое описание (1-2 предложения)
- "Что проверяется" - список проверяемых аспектов
- "Тестовые данные" - входные параметры
- "Ожидаемый результат" - ожидаемое поведение
- `@allure.severity` - уровень важности (NORMAL для unit-теста)
- `@allure.tag` - теги для фильтрации: `"key_numbering"`, `"initialization"`, `"database"`, `"unit"`, `"migration"`

**Структурирование шагов:**

- Использовать `allure.step()` для структурирования по паттерну Arrange-Act-Assert:
- "Подготовка тестовых данных"
- "Создание БД и пользователя"
- "Создание ключей с разными номерами"
- "Инициализация счетчика"
- "Проверка результата"

**Прикрепление данных:**

- Использовать `allure.attach()` для:
- Пути к временной БД
- user_id
- Созданных ключей (email и номера)
- Максимального номера ключа
- Финального значения keys_count

### 3. Проверка и запуск теста

- Запустить тест через Docker: `docker compose exec monitoring pytest tests/unit/test_database/test_key_numbering.py::test_initialization_existing_users -v`
- Проверить отчет в Allure: `http://localhost:5050/allure-docker-service/projects/default/reports/latest/index.html`
- Убедиться, что:
- Тест проходит без ошибок
- Все Allure аннотации отображаются корректно
- Шаги структурированы правильно
- Прикрепленные данные доступны в отчете

## Файлы для изменения

1. `tests/unit/test_database/test_key_numbering.py` (строки 261-360)

- Исправление NameError (инициализация переменной до try)
- Добавление Allure аннотаций
- Структурирование шагов с allure.step()
- Прикрепление данных с allure.attach()

## Зависимости

- Используется существующая фикстура `temp_db` из `conftest.py` (но в этом тесте она не используется, создается своя временная БД)
- Импорты уже присутствуют в файле
- Allure уже настроен в проекте

### To-dos

- [ ] Исправить NameError: инициализировать original_db_file до блока try и добавить безопасное восстановление в finally
- [ ] Добавить полный набор Allure аннотаций: @allure.title, @allure.description, @allure.severity, @allure.tag
- [ ] Структурировать тест с помощью allure.step() по паттерну Arrange-Act-Assert
- [ ] Добавить allure.attach() для важных данных (user_id, ключи, счетчик)
- [ ] Запустить тест и проверить отчет в Allure на корректность отображения