<!-- c687654b-b6be-4c5a-9050-55983eace800 9f4d9bc6-1c16-4dbc-9373-018fb4183118 -->
# План исправления тестов install validation

## Проблема

Тесты `TestInstallValidation` падают, потому что файл `install.sh` не доступен в Docker контейнере `autotest`. Файл находится в корне проекта, но не маппируется в контейнер.

## Решение

### 1. Добавление маппинга install.sh в docker-compose.yml

- Добавить volume маппинг `./install.sh:/app/install.sh:ro` в секцию `autotest` в `docker-compose.yml`
- Это позволит тестам проверять файл `install.sh` в контейнере

### 2. Улучшение Allure аннотаций в тестах

Согласно правилам из `testing-rules.mdc`, нужно добавить:

- **@allure.story** для интеграционных тестов (опционально для unit-тестов)
- Улучшить **@allure.description** с полной структурой:
  - Краткое описание
  - Раздел "Что проверяется"
  - Раздел "Тестовые данные"
  - Раздел "Ожидаемый результат"
  - Раздел "Предусловия" (если нужно)
- Добавить **@allure.label("package", "...")** для группировки в Packages
- Улучшить использование **allure.step()** и **allure.attach()** для структурирования

### 3. Исправление теста test_port_consistency

- Тест не завершен (нет assert в конце)
- Нужно добавить проверку портов и завершающий assert

### 4. Запуск тестов и проверка в Allure

- Запустить тесты через `docker compose exec autotest pytest`
- Проверить результаты в Allure отчете
- Убедиться, что все тесты проходят и отчеты корректны

## Файлы для изменения

1. `docker-compose.yml` - добавление маппинга install.sh
2. `tests/scripts/test_install_validation.py` - улучшение Allure аннотаций и исправление теста test_port_consistency

## Детали изменений

### docker-compose.yml

Добавить в секцию `autotest` volumes:

```yaml
- ./install.sh:/app/install.sh:ro
```

### tests/scripts/test_install_validation.py

1. Улучшить все @allure.description с полной структурой
2. Добавить @allure.label("package", "tests.scripts") на уровне класса
3. Добавить allure.attach() для важных данных
4. Исправить test_port_consistency - добавить assert для проверки портов
5. Улучшить allure.step() для структурирования тестов

### To-dos

- [ ] Добавить маппинг install.sh в docker-compose.yml для контейнера autotest
- [ ] Улучшить Allure аннотации в test_install_script_exists: добавить полное описание, улучшить allure.step() и allure.attach()
- [ ] Улучшить Allure аннотации в test_required_directories_in_script: добавить полное описание, улучшить allure.step() и allure.attach()
- [ ] Улучшить Allure аннотации в test_docs_proxy_in_script: добавить полное описание, улучшить allure.step() и allure.attach()
- [ ] Исправить test_port_consistency: добавить assert для проверки портов и улучшить Allure аннотации
- [ ] Запустить тесты и проверить результаты в Allure отчете