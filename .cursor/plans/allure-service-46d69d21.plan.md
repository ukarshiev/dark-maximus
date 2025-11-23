<!-- 46d69d21-69a0-47c6-87b1-9620583c4c70 a89d2a19-184a-4538-99aa-5364fa4c7ef5 -->
# Исправление прав доступа для Allure Service

## Найденная проблема

**100% подтвержденная проблема:** Контейнер `allure-service` не может генерировать отчеты из-за ошибок прав доступа (Permission denied).

### Детали проблемы:

1. **Контейнер работает от пользователя:** `uid=1000(allure) gid=1000(ubuntu)`
2. **Директории на хосте принадлежат:** `root:root` с правами `drwxr-xr-x` (755)
3. **Ошибки в логах:**

   - `mkdir: cannot create directory '/app/allure-docker-api/static/projects/default/results/history': Permission denied`
   - `/app/generateAllureReport.sh: line 57: /app/allure-docker-api/static/projects/default/results/executor.json: Permission denied`
   - `java.nio.file.AccessDeniedException: /app/allure-docker-api/static/projects/default/reports`

### Причина:

Контейнер не может создавать директории и файлы в смонтированных volumes, потому что они принадлежат root, а контейнер работает от пользователя с uid=1000.

## Решение

### Шаг 1: Изменить владельца директорий на сервере

На сервере `31.56.27.129` выполнить:

```bash
cd /opt/dark-maximus
chown -R 1000:1000 allure-results allure-report allure-reports
chmod -R 755 allure-results allure-report allure-reports
```

### Шаг 2: Перезапустить контейнер allure-service

```bash
docker compose restart allure-service
```

### Шаг 3: Проверить генерацию отчетов

```bash
# Подождать 30-60 секунд для генерации отчета
sleep 60

# Проверить логи на отсутствие ошибок Permission denied
docker compose logs --tail=50 allure-service | grep -i "permission\|denied" || echo "Ошибок прав доступа нет"

# Проверить наличие отчетов через API
curl -s http://localhost:50005/allure-docker-service/projects/default/reports | head -20
```

### Шаг 4: Обновить скрипт установки (опционально)

Если проблема повторяется после пересоздания контейнеров, добавить в `install-autotest.sh` автоматическую установку прав доступа:

```bash
# После создания директорий allure-results, allure-report, allure-reports
chown -R 1000:1000 allure-results allure-report allure-reports
chmod -R 755 allure-results allure-report allure-reports
```

## Ожидаемый результат

После исправления прав доступа:

- Allure Service сможет создавать директорию `history` в `allure-results/`
- Allure Service сможет создавать файл `executor.json`
- Allure Service сможет создавать директорию `reports` и генерировать HTML отчеты
- Отчеты будут доступны по адресу `https://allure.dark-maximus.com/allure-docker-service/projects/default/reports/latest/index.html`

## Файлы для изменения

- **На сервере:** `/opt/dark-maximus/allure-results`, `/opt/dark-maximus/allure-report`, `/opt/dark-maximus/allure-reports` (изменение владельца)
- **Опционально:** `install-autotest.sh` (добавление автоматической установки прав доступа)