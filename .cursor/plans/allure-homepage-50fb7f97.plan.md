<!-- 50fb7f97-3487-49db-a632-a9de1a3db8bc cea61790-d511-4641-a505-61fbb07d99b8 -->
# План: Добавление главной страницы для Allure Docker Service

## Цель

Создать главную страницу на пути `/allure-docker-service/`, которая будет отображать ссылки на отчеты Allure и API документацию (Swagger UI) вместо пустого Swagger UI интерфейса.

## Текущая ситуация

- На `http://localhost:5050/allure-docker-service/` отображается Swagger UI (API документация)
- Отчеты доступны по пути `/allure-docker-service/projects/default/reports/latest/index.html`
- Allure Docker Service работает на порту 5050 напрямую

## Решение

Создать отдельный простой веб-сервер (Python Flask) для главной страницы, который будет:

1. Отображать главную страницу на корневом пути `/allure-docker-service/`
2. Проксировать все остальные пути на allure-service (который будет работать на внутреннем порту 5051)

## Шаги реализации

### 1. Создание структуры для главной страницы

- Создать директорию `apps/allure-homepage/`
- Создать `apps/allure-homepage/app.py` - Flask приложение с главной страницей
- Создать `apps/allure-homepage/templates/index.html` - HTML шаблон главной страницы
- Создать `apps/allure-homepage/requirements.txt` - зависимости Python
- Создать `apps/allure-homepage/Dockerfile` - Docker образ для главной страницы

### 2. Обновление docker-compose.yml

- Изменить порт allure-service с 5050 на 5051 (внутренний порт)
- Добавить новый сервис `allure-homepage` на порту 5050
- Настроить проксирование запросов от allure-homepage к allure-service

### 3. Создание HTML шаблона

- Создать красивую главную страницу в стиле проекта (темная тема, зеленый акцент #008771)
- Добавить ссылки на:
- Последний отчет Allure: `/allure-docker-service/projects/default/reports/latest/index.html`
- API документацию (Swagger UI): `/allure-docker-service/swagger-ui/` или `/allure-docker-service/`
- Список проектов: `/allure-docker-service/projects`
- Добавить информацию о сервисе и статистику

### 4. Обновление документации

- Обновить `docs/guides/testing/allure-reporting.md` с информацией о главной странице
- Обновить CHANGELOG.md

## Файлы для создания/изменения

### Новые файлы:

- `apps/allure-homepage/app.py`
- `apps/allure-homepage/templates/index.html`
- `apps/allure-homepage/requirements.txt`
- `apps/allure-homepage/Dockerfile`

### Изменяемые файлы:

- `docker-compose.yml` - добавить сервис allure-homepage, изменить порт allure-service
- `docs/guides/testing/allure-reporting.md` - обновить информацию о главной странице
- `CHANGELOG.md` - добавить запись о новом функционале

## Технические детали

### Flask приложение

- Использует Flask для отображения главной страницы
- Проксирует запросы к allure-service через `requests` или `httpx`
- Обрабатывает корневой путь `/allure-docker-service/` для главной страницы
- Проксирует все остальные пути на allure-service

### Docker конфигурация

- allure-service: внутренний порт 5051 (не публикуется наружу)
- allure-homepage: публичный порт 5050, проксирует запросы на allure-service:5051

### Стилизация

- Использовать темную тему проекта
- Зеленый акцентный цвет #008771
- Адаптивный дизайн для мобильных устройств
- Современный и чистый интерфейс

### To-dos

- [ ] Создать структуру директорий и файлов для allure-homepage (app.py, templates/index.html, requirements.txt, Dockerfile)
- [ ] Реализовать Flask приложение с главной страницей и проксированием запросов к allure-service
- [ ] Создать HTML шаблон главной страницы со ссылками на отчеты и API в стиле проекта
- [ ] Обновить docker-compose.yml: добавить сервис allure-homepage, изменить порт allure-service на 5051
- [ ] Обновить документацию allure-reporting.md и CHANGELOG.md с информацией о главной странице