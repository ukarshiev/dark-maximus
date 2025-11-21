<!-- 0e84b641-91df-40ee-830a-68a2580606ac 72be0633-3b88-41fb-ac04-2bc680b007be -->
# Исправление пропуска теста testdockercompose_syntax

## Проблема

Тест `tests.scripts.test_docker_compose.TestDockerCompose#test_docker_compose_syntax` пропускается с сообщением "docker-compose.yml не найден в корне проекта".

## Причина

В `docker-compose.yml` для сервиса `autotest` отсутствует маппинг файла `docker-compose.yml` в контейнер. Тест использует фикстуру `project_root`, которая указывает на `/app` в контейнере, но файл `docker-compose.yml` не проброшен туда.

## Решение

### 1. Добавить маппинг docker-compose.yml в docker-compose.yml

- Файл: `docker-compose.yml`
- Добавить в volume-маппинги сервиса `autotest` (строка ~138):
  ```yaml
  - ./docker-compose.yml:/app/docker-compose.yml:ro
  ```


### 2. Проверить фикстуру project_root

- Файл: `tests/scripts/conftest.py`
- Фикстура `project_root` возвращает `Path(__file__).parent.parent.parent`
- Если `__file__` = `tests/scripts/conftest.py`, то:
        - `parent` = `tests/scripts/`
        - `parent.parent` = `tests/`
        - `parent.parent.parent` = корень проекта
- В контейнере это будет `/app`, что корректно

### 3. Запустить тест и проверить результат

- Запустить тест: `docker compose exec autotest pytest tests/scripts/test_docker_compose.py::TestDockerCompose::test_docker_compose_syntax -v`
- Проверить отчет в Allure: http://localhost:50005/allure-docker-service/projects/default/reports/latest/index.html

## Файлы для изменения

- `docker-compose.yml` - добавить маппинг docker-compose.yml для сервиса autotest

### To-dos

- [ ] Добавить маппинг docker-compose.yml в volume-маппинги сервиса autotest в docker-compose.yml
- [ ] Запустить тест test_docker_compose_syntax и проверить, что он проходит
- [ ] Проверить отчет в Allure и убедиться, что тест больше не пропускается