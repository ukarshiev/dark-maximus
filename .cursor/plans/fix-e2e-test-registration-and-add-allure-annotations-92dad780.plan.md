<!-- 92dad780-f95f-4885-a7e6-31319e4f0996 c98b8364-726e-4b81-a835-404722af78bd -->
# Исправление E2E теста test_new_user_registers_and_buys_vpn

## Проблема

Тест падает с ошибкой `AssertionError: Пользователь должен быть зарегистрирован` потому что:

1. Локальная фикстура `temp_db` в тесте неправильно использует `base_temp_db.__wrapped__`
2. Фикстура из `conftest.py` правильно патчит `database.DB_FILE`, но локальная фикстура переопределяет это поведение
3. Функции `register_user_if_not_exists` и `get_user` используют неправильный путь к БД

## Решение

### 1. Удалить локальную фикстуру temp_db

- Удалить метод `temp_db` из класса `TestNewUserPurchase`
- Использовать фикстуру `temp_db` из `conftest.py` напрямую (как в других E2E тестах)

### 2. Добавить Allure аннотации

Согласно правилам из `testing-rules.mdc`, добавить:

- `@allure.title` - краткое описание теста
- `@allure.description` - структурированное описание с разделами:
- Краткое описание
- "Что проверяется"
- "Тестовые данные"
- "Ожидаемый результат"
- `@allure.severity` - уровень важности (CRITICAL для E2E тестов)
- `@allure.tag` - теги для фильтрации: `"e2e"`, `"user_registration"`, `"vpn_purchase"`, `"new_user"`

### 3. Улучшить тест

- Добавить проверку возвращаемого значения `register_user_if_not_exists`
- Добавить логирование через `allure.attach` для входных данных и результатов
- Использовать `allure.step` для структурирования теста

### 4. Запустить тест и проверить отчет

- Запустить тест через Docker: `docker compose exec monitoring pytest tests/e2e/test_user_scenarios/test_new_user_purchase.py::TestNewUserPurchase::test_new_user_registers_and_buys_vpn -v`
- Проверить отчет в Allure на `http://localhost:5050`
- Убедиться, что тест проходит и все аннотации отображаются корректно

## Файлы для изменения

- `tests/e2e/test_user_scenarios/test_new_user_purchase.py` - исправление фикстуры и добавление Allure аннотаций

### To-dos

- [ ] Удалить локальную фикстуру temp_db из класса TestNewUserPurchase
- [ ] Добавить Allure аннотации (@allure.title, @allure.description, @allure.severity, @allure.tag) к тесту test_new_user_registers_and_buys_vpn
- [ ] Добавить allure.attach для входных данных и результатов, использовать allure.step для структурирования
- [ ] Запустить тест и проверить отчет в Allure