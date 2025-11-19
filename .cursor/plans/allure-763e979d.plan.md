<!-- 763e979d-0f2c-4b72-9b0a-431033cc2c47 5e86fff6-8189-4105-a6dc-5eb6d4f19c77 -->
# Исправление кликов в графиках Allure Reports

## Проблема

При нажатии на значения в графиках "Duration trend", "Retries trend" и "Categories trend" открывается страница с JSON-ответом API вместо корректного отображения данных.

JSON ответ содержит: `{"data":{"project":{"id":"default","reports":["http://localhost:5050/allure-docker-service/projects/default/reports/latest/index.html",...]}},"meta_data":{"message":"Project successfully obtained"}}`

## Причина

Allure Docker Service не знает правильный публичный URL и генерирует ссылки на API-эндпоинты с `localhost:5050` вместо корректных страниц отчетов. Это происходит потому, что сервис не настроен для работы за обратным прокси-сервером (nginx).

## Решение

### 1. Добавление переменной окружения ALLURE_DOCKER_PUBLIC_API_URL

- В секции `allure-service` в `docker-compose.yml` добавить переменную `ALLURE_DOCKER_PUBLIC_API_URL`
- Значение: `http://localhost:5050/allure-docker-service` (для локального доступа)
- Эта переменная сообщает Allure Docker Service правильный публичный URL для генерации ссылок в графиках

### 2. Безопасное решение с сохранением существующей конфигурации

- Добавить переменную окружения без изменения существующих настроек
- Сохранить существующие переменные: `CHECK_RESULTS_EVERY_SECONDS=3` и `KEEP_HISTORY=1`
- Не ломать существующую работу сервиса

### 3. Изменения в docker-compose.yml

- В секции `environment` для `allure-service` добавить:
- `ALLURE_DOCKER_PUBLIC_API_URL=http://localhost:5050/allure-docker-service`

## Файлы для изменения

- `docker-compose.yml` (строки 117-119) - добавить переменную окружения `ALLURE_DOCKER_PUBLIC_API_URL` в секцию `environment` для `allure-service`

## Тестирование

После изменений:

1. Перезапустить allure-service: `docker compose restart allure-service`
2. Дождаться перегенерации отчетов (CHECK_RESULTS_EVERY_SECONDS=3)
3. Проверить клики на графики в разделах Duration trend, Retries trend, Categories trend
4. Убедиться, что открываются корректные страницы с данными, а не JSON-ответы API