<!-- a5783da0-cdbb-4412-9a06-f94154537969 c756c3fc-72f0-4e10-be4e-abb28de234ec -->
# Исправление теста testpromocodeapplicationvalidation

## Проблемы

1. **Неправильный параметр в вызове функции**: В строке 178 передается `promo_id` (число), но функция `can_user_use_promo_code` ожидает `promo_code` (строку) во втором параметре.
2. **Неправильная проверка результата**: В строке 179 проверяется `can_use is True`, но `can_use` - это dict, а не bool. Нужно проверять `can_use.get('can_use') is True`.
3. **Отсутствие Allure аннотаций**: Тест не имеет подробных Allure аннотаций согласно правилам проекта.

## Исправления

### 1. Исправить вызов функции can_user_use_promo_code

**Файл**: `tests/integration/test_vpn_purchase/test_promo_code_application.py`

**Строка 178**: Заменить `promo_id` на строку `'VALID'` (код промокода)

```python
# Было:
can_use = can_user_use_promo_code(test_setup['user_id'], promo_id, 'test_bot')

# Должно быть:
can_use = can_user_use_promo_code(test_setup['user_id'], 'VALID', 'test_bot')
```

### 2. Исправить проверку результата

**Строка 179**: Проверять значение из dict, а не сам dict

```python
# Было:
assert can_use is True, "Пользователь должен иметь возможность использовать промокод"

# Должно быть:
assert can_use.get('can_use') is True, "Пользователь должен иметь возможность использовать промокод"
```

### 3. Добавить Allure аннотации

Добавить следующие аннотации к тесту согласно правилам из `testing-rules.mdc`:

- `@allure.title` - краткое описание теста
- `@allure.description` - подробное структурированное описание с разделами:
  - Что проверяется
  - Тестовые данные
  - Шаги теста
  - Ожидаемый результат
- `@allure.severity` - уровень важности (NORMAL для интеграционного теста)
- `@allure.tag` - теги для фильтрации: `"promo_code"`, `"validation"`, `"integration"`, `"vpn_purchase"`
- `@allure.step` - структурирование шагов теста (опционально, для сложных тестов)

**Epic и Feature** уже установлены на уровне класса, поэтому их не нужно добавлять.

## Файлы для изменения

- `tests/integration/test_vpn_purchase/test_promo_code_application.py` (строки 145-180)

## Проверка после исправления

1. Запустить тест: `docker compose exec monitoring pytest tests/integration/test_vpn_purchase/test_promo_code_application.py::TestPromoCodeApplication::test_promo_code_application_validation -v`
2. Проверить отчет Allure: открыть `http://localhost:5050/allure-docker-service/projects/default/reports/latest/index.html` и убедиться, что:

   - Тест проходит успешно
   - Все Allure аннотации отображаются корректно
   - Описание теста читаемо и структурировано
   - Теги позволяют фильтровать тесты

### To-dos

- [ ] Исправить вызов can_user_use_promo_code: заменить promo_id на строку 'VALID'
- [ ] Исправить проверку результата: использовать can_use.get('can_use') вместо can_use
- [ ] Добавить Allure аннотации (@allure.title, @allure.description, @allure.severity, @allure.tag) к тесту
- [ ] Запустить тест и проверить, что он проходит
- [ ] Проверить отчет Allure и убедиться, что все аннотации отображаются корректно