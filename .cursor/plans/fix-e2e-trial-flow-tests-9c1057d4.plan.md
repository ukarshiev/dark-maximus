<!-- 9c1057d4-6912-44e6-83c4-b72fd65be694 c5e8fd9c-700b-4f79-8c3a-35da60133e09 -->
# Исправление E2E тестов для пробного периода

## Проблема

Два E2E теста требуют исправления:

1. `test_new_user_requests_trial_and_gets_key` - отсутствуют подробные Allure аннотации
2. `test_user_cannot_get_trial_with_active_trial_key` - отсутствуют подробные Allure аннотации

## Анализ

- Оба теста проходят при индивидуальном запуске
- В тестах отсутствуют обязательные Allure аннотации (@allure.title, @allure.description, @allure.severity, @allure.tag)
- Отсутствует структурирование шагов через allure.step()
- Нет прикрепления важных данных через allure.attach()

## Исправления

### 1. test_new_user_requests_trial_and_gets_key

- Добавить @allure.title с кратким описанием
- Добавить @allure.description с полной структурой (что проверяется, тестовые данные, ожидаемый результат)
- Добавить @allure.severity (CRITICAL - основной функционал)
- Добавить @allure.tag (trial, e2e, critical, trial_flow, new_user)
- Структурировать тест через allure.step() по паттерну Arrange-Act-Assert
- Добавить allure.attach() для важных данных (user_id, trial_info, keys, callback_text)

### 2. test_user_cannot_get_trial_with_active_trial_key

- Добавить @allure.title с кратким описанием
- Добавить @allure.description с полной структурой
- Добавить @allure.severity (CRITICAL - проверка ограничений)
- Добавить @allure.tag (trial, restriction, e2e, critical, trial_flow, active_key)
- Структурировать тест через allure.step()
- Добавить allure.attach() для важных данных
- Улучшить проверку сообщения об отказе

## Файлы для изменения

- `tests/e2e/test_user_scenarios/test_user_trial_flow.py` - добавление Allure аннотаций и структурирование тестов

## Проверка после исправления

- Запустить оба теста: `pytest tests/e2e/test_user_scenarios/test_user_trial_flow.py::TestUserTrialFlow::test_new_user_requests_trial_and_gets_key tests/e2e/test_user_scenarios/test_user_trial_flow.py::TestUserTrialFlow::test_user_cannot_get_trial_with_active_trial_key -v --alluredir=allure-results`
- Проверить отчет в Allure на наличие всех аннотаций и структурированных шагов
- Убедиться, что все данные правильно прикреплены к отчету

### To-dos

- [ ] Добавить подробные Allure аннотации к test_new_user_requests_trial_and_gets_key: @allure.title, @allure.description, @allure.severity, @allure.tag
- [ ] Структурировать test_new_user_requests_trial_and_gets_key через allure.step() по паттерну Arrange-Act-Assert
- [ ] Добавить allure.attach() для важных данных в test_new_user_requests_trial_and_gets_key (user_id, trial_info, keys, callback_text)
- [ ] Добавить подробные Allure аннотации к test_user_cannot_get_trial_with_active_trial_key: @allure.title, @allure.description, @allure.severity, @allure.tag
- [ ] Структурировать test_user_cannot_get_trial_with_active_trial_key через allure.step() по паттерну Arrange-Act-Assert
- [ ] Добавить allure.attach() для важных данных в test_user_cannot_get_trial_with_active_trial_key (user_id, trial_key, trial_info, callback_text)
- [ ] Запустить оба теста и проверить отчет в Allure на наличие всех аннотаций и структурированных шагов