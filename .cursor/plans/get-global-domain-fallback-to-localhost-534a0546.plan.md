<!-- 534a0546-8d49-48f2-821b-ea36470de882 3ef4bf14-177d-44b5-834a-d185b440ab3a -->
# Исправление теста getglobaldomainfallbackto_localhost

## Проблема

Тест `test_get_global_domain_fallback_to_localhost_in_development` не проходит на боевом сервере, потому что:

1. Тест не очищает настройки `global_domain` и `domain` перед проверкой
2. Если на боевом сервере в production БД есть значения для этих настроек, они могут влиять на результат
3. Функция `get_global_domain()` может некорректно обрабатывать пустые строки (хотя пустая строка является falsy в Python)

## Решение

1. **Очистка настроек доменов в тесте**: Перед проверкой fallback на localhost необходимо явно удалить или установить в `None` настройки `global_domain` и `domain` в тестовой БД
2. **Улучшение функции `get_global_domain()`**: Добавить явную проверку на пустые строки, чтобы функция корректно обрабатывала случаи, когда в БД сохранена пустая строка вместо `None`
3. **Проверка работы на разных типах серверов**: Убедиться, что тест работает как на production, так и на development серверах

## Изменения

### 1. Исправление теста (`tests/unit/test_database/test_domain_settings.py`)

В тесте `test_get_global_domain_fallback_to_localhost_in_development`:

- Добавить явную очистку настроек `global_domain` и `domain` перед проверкой
- Убедиться, что настройки действительно отсутствуют (равны `None`)

### 2. Улучшение функции `get_global_domain()` (`src/shop_bot/data_manager/database.py`)

Добавить явную проверку на пустые строки:

- Если `global_domain` или `domain` являются пустыми строками, считать их отсутствующими
- Это обеспечит корректную работу fallback логики

## Тестирование

После исправления:

1. Запустить тест локально: `docker compose exec autotest pytest tests/unit/test_database/test_domain_settings.py::TestDomainSettings::test_get_global_domain_fallback_to_localhost_in_development -v`
2. Проверить отчет в Allure на боевом сервере
3. Убедиться, что тест проходит на обоих типах серверов (production и development)

### To-dos

- [ ] Добавить явную очистку настроек global_domain и domain в тесте test_get_global_domain_fallback_to_localhost_in_development перед проверкой fallback
- [ ] Улучшить функцию get_global_domain() для корректной обработки пустых строк (считать их отсутствующими)
- [ ] Запустить тест локально для проверки исправлений
- [ ] Проверить отчет Allure на боевом сервере после исправлений