<!-- eead2540-c6d4-4f27-a059-de4499133948 5efe1eb7-5373-42de-a860-1676e5b633ca -->
# Исправление тестов пробного периода и добавление Allure аннотаций

## Проблемы

1. **test_user_cannot_get_second_trial_without_reset** - тест проходит, но отсутствуют Allure аннотации
2. **test_trial_status_check** - тест падает, потому что `add_new_key` не устанавливает `trial_used = True` автоматически (это делает `process_trial_key_creation_callback`)

## Решение

### 1. Исправление test_trial_status_check

**Проблема:** В тесте создается триальный ключ через `add_new_key`, но эта функция не устанавливает `trial_used = True`. В реальном flow это делает `process_trial_key_creation_callback` через `set_trial_used(user_id)`.

**Решение:** Добавить вызов `set_trial_used(user_id)` и `set_trial_days_given(user_id, 7)` после создания ключа в тесте, чтобы имитировать реальное поведение.

**Файл:** `tests/integration/test_trial/test_trial_flow.py`

### 2. Добавление Allure аннотаций

Добавить полный набор Allure аннотаций для обоих тестов согласно правилам проекта:

- `@allure.epic` - "E2E тесты" / "Интеграционные тесты"
- `@allure.feature` - "Пользовательские сценарии" / "Пробный период"
- `@allure.title` - краткое описание теста
- `@allure.description` - структурированное описание с разделами
- `@allure.severity` - уровень важности
- `@allure.tag` - теги для фильтрации
- `allure.step()` - для структурирования шагов
- `allure.attach()` - для прикрепления важных данных

**Файлы:**

- `tests/e2e/test_user_scenarios/test_user_trial_flow.py`
- `tests/integration/test_trial/test_trial_flow.py`

## Шаги реализации

1. Исправить `test_trial_status_check` - добавить `set_trial_used` и `set_trial_days_given`
2. Добавить Allure аннотации в `test_user_cannot_get_second_trial_without_reset`
3. Добавить Allure аннотации в `test_trial_status_check`
4. Запустить тесты для проверки
5. Проверить отчеты в Allure

## Детали изменений

### test_trial_status_check

- Импортировать `set_trial_used`, `set_trial_days_given`
- После создания ключа вызвать `set_trial_used(user_id)` и `set_trial_days_given(user_id, 7)`
- Добавить Allure аннотации с описанием проверки статуса триала

### test_user_cannot_get_second_trial_without_reset

- Добавить полный набор Allure аннотаций
- Добавить `allure.step()` для структурирования шагов
- Добавить `allure.attach()` для прикрепления данных о состоянии триала

### To-dos

- [ ] Исправить test_trial_status_check - добавить set_trial_used и set_trial_days_given после создания ключа
- [ ] Добавить Allure аннотации в test_user_cannot_get_second_trial_without_reset
- [ ] Добавить Allure аннотации в test_trial_status_check
- [ ] Запустить оба теста для проверки исправлений
- [ ] Проверить отчеты в Allure на корректность отображения аннотаций