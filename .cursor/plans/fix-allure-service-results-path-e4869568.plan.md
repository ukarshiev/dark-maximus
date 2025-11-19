<!-- e4869568-3e43-41cf-8178-84e50b974714 c0792e64-3361-41e9-88f0-dd201c5f7daa -->
# Исправление конфигурации Allure согласно официальной документации

## Проблема

Текущая конфигурация использует костыли (скрипт синхронизации) вместо правильной настройки volume mappings согласно официальной документации allure-docker-service.

## Решение согласно официальной документации

### 1. Правильная структура директорий для allure-docker-service

Согласно официальной документации:

- Результаты тестов сохраняются в `allure-results` (уже правильно настроено в pytest.ini)
- Allure-docker-service читает результаты из `/app/allure-docker-api/static/projects/{project_id}/results/`
- Для проекта "default": `/app/allure-docker-api/static/projects/default/results/`

### 2. Изменения в docker-compose.yml

**Удалить:**

- Volume mapping для sync-allure-results.sh
- Entrypoint с синхронизацией
- Все костыли

**Добавить правильный volume mapping:**

```yaml
volumes:
  - ./allure-results:/app/allure-docker-api/static/projects/default/results
  - ./allure-reports:/app/allure-docker-api/static/projects
```

### 3. Обновить pytest.ini

Изменить путь сохранения результатов, чтобы они сразу попадали в правильную директорию:

```ini
--alluredir=allure-reports/default/results
```

ИЛИ оставить как есть и использовать правильный volume mapping.

### 4. Удалить ненужные файлы

- Удалить sync-allure-results.sh (больше не нужен)

### 5. Обновить документацию

Обновить ссылки и инструкции в документации проекта.

## Файлы для изменения

1. `docker-compose.yml` - исправить volume mappings, убрать entrypoint
2. `tests/pytest.ini` - проверить/обновить путь allure-results
3. Удалить `sync-allure-results.sh`
4. Обновить документацию в `docs/guides/testing/allure-reporting.md` (если нужно)

## Проверка

1. Перезапустить allure-service
2. Запустить тесты
3. Проверить, что результаты видны в отчете
4. Убедиться, что statistic.total > 0

### To-dos

- [ ] Исправить docker-compose.yml: убрать entrypoint и sync-allure-results.sh, настроить правильный volume mapping для результатов
- [ ] Проверить и при необходимости обновить pytest.ini для правильного пути сохранения результатов
- [ ] Удалить sync-allure-results.sh - больше не нужен
- [ ] Обновить документацию allure-reporting.md с правильной конфигурацией
- [ ] Перезапустить allure-service, запустить тесты и проверить, что результаты отображаются в отчете