<!-- a1eceb91-9797-445b-99bc-54677272f13f 6c746c69-a680-426f-82b0-ca430ddee8c7 -->
# Исправление проблем с Allure Docker Service

## Проблемы

1. **Некорректные пути в графиках истории** - относительные пути типа `../45/index.html` не работают при использовании сервиса через `/allure-docker-service/`
2. **Отсутствие переменной `URL_PREFIX`** - необходима для корректной обработки путей к ресурсам
3. **Неправильная настройка `ALLURE_PUBLIC_URL`** - должна включать полный путь с префиксом

## Решение

### 1. Обновление docker-compose.yml

**Файл:** `docker-compose.yml`

**Изменения:**

- Добавить переменную окружения `URL_PREFIX=/allure-docker-service` для корректной обработки путей
- Обновить `ALLURE_PUBLIC_URL` на полный путь: `http://localhost:5050/allure-docker-service` (вместо `http://localhost:5050`)
- Добавить дополнительные настройки для лучшей работы с путями

**Пример конфигурации:**

```yaml
allure-service:
  image: frankescobar/allure-docker-service:latest
  container_name: dark-maximus-allure
  ports:
    - '127.0.0.1:5050:5050'
  volumes:
    - ./allure-results:/app/allure-results
    - ./allure-report:/app/allure-report
    - ./allure-categories.json:/app/allure-categories.json
  environment:
    - CHECK_RESULTS_EVERY_SECONDS=3
    - KEEP_HISTORY=1
    - ALLURE_PUBLIC_URL=http://localhost:5050/allure-docker-service
    - URL_PREFIX=/allure-docker-service
  networks:
    - dark-maximus-network
```

### 2. Проверка версии образа

**Действие:**

- Убедиться, что используется последняя стабильная версия `frankescobar/allure-docker-service:latest`
- Проверить, поддерживает ли версия переменную `URL_PREFIX` (доступна с версии 2.13.5+)

### 3. Обновление документации

**Файл:** `docs/guides/testing/allure-reporting.md`

**Изменения:**

- Обновить раздел конфигурации с новыми переменными окружения
- Добавить информацию о переменной `URL_PREFIX` и ее назначении
- Обновить примеры конфигурации docker-compose.yml

### 4. Тестирование исправлений

**Действия:**

1. Перезапустить контейнер allure-service: `docker compose restart allure-service`
2. Проверить доступность веб-интерфейса: `http://localhost:5050/allure-docker-service/`
3. Проверить работу графиков истории - кликнуть на график и убедиться, что переход работает корректно
4. Проверить загрузку всех ресурсов (CSS, JS, графики) через DevTools Network tab
5. Проверить отсутствие ошибок в консоли браузера

## Ожидаемый результат

После применения исправлений:

- Графики истории открываются корректно при клике
- Все пути к ресурсам (CSS, JS, графики) работают правильно
- Относительные пути в истории преобразуются в абсолютные с учетом `URL_PREFIX`
- Нет ошибок 404 при загрузке ресурсов
- Нет ошибок в консоли браузера

## Best Practices

1. **Использование `URL_PREFIX`** - обязательна при работе через обратный прокси или нестандартный путь
2. **Правильная настройка `ALLURE_PUBLIC_URL`** - должна включать полный путь с префиксом
3. **Мониторинг логов** - проверять логи контейнера на наличие ошибок
4. **Регулярные обновления** - использовать последние стабильные версии образа

### To-dos

- [ ] Обновить docker-compose.yml: добавить URL_PREFIX и исправить ALLURE_PUBLIC_URL
- [ ] Проверить версию образа allure-docker-service и поддержку URL_PREFIX
- [ ] Обновить документацию allure-reporting.md с новыми настройками
- [ ] Протестировать исправления: проверить графики, пути и ресурсы