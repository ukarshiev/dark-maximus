<!-- c5ddfbf4-061b-4166-b1cd-8286c460b6b9 bea12792-8021-4e9a-adc2-0bf3e0535a76 -->
# Документирование системы тестирования Dark Maximus

## Цель

Создать полную документацию по тестированию проекта, включая структуру тестов, инструкции по запуску, работу с Allure Framework и best practices для написания тестов.

## Структура документации

Согласно Diátaxis Framework и существующей структуре проекта, документация по тестированию будет разделена на несколько файлов в `docs/guides/testing/`:

### Файлы для создания

1. **docs/guides/testing/README.md** — главная страница раздела тестирования с навигацией
2. **docs/guides/testing/testing-structure.md** — структура тестов (unit/integration/e2e/ad-hoc)
3. **docs/guides/testing/running-tests.md** — инструкции по запуску тестов (локально, Docker, Nx)
4. **docs/guides/testing/allure-reporting.md** — работа с Allure Framework (отчеты, веб-интерфейс, интеграция)
5. **docs/guides/testing/best-practices.md** — best practices для написания тестов (pytest, фикстуры, моки, маркеры)

### Справочная документация

6. **docs/reference/testing-reference.md** — справочник по pytest и Allure (конфигурация, маркеры, фикстуры, API)

### Обновление существующих файлов

7. Обновить **docs/guides/README.md** — добавить раздел про тестирование
8. Обновить **docs/guides/development/README.md** — добавить ссылку на тестирование
9. Обновить **docs/guides/testing/allure-defects-management.md** — добавить ссылки на другие документы

## Содержание документов

### docs/guides/testing/README.md

- Обзор системы тестирования
- Навигация по документации
- Быстрый старт
- Ссылки на все документы

### docs/guides/testing/testing-structure.md

- Структура каталога `tests/`
- Описание типов тестов (unit/integration/e2e/ad-hoc)
- Организация тестов по модулям
- Связь тестов с исходным кодом
- Примеры структуры

### docs/guides/testing/running-tests.md

- Локальный запуск тестов (pip install, pytest)
- Запуск в Docker (docker compose exec monitoring)
- Запуск через Nx (npx nx test bot)
- Запуск конкретных тестов/категорий
- Параметры pytest
- Скрипты запуска (run_tests.sh, run_tests.ps1)

### docs/guides/testing/allure-reporting.md

- Установка мониторинга (install-monitoring.sh)
- Генерация отчетов Allure
- Веб-интерфейс Allure Service (localhost:5050)
- Работа с категориями дефектов
- Интеграция в CI/CD
- Внешний доступ через SSL (tests.dark-maximus.com)

### docs/guides/testing/best-practices.md

- Организация тестов (pytest conventions)
- Использование фикстур (temp_db, моки)
- Изоляция тестов
- Маркеры pytest
- Работа с временной БД
- Моки внешних сервисов (Telegram, 3X-UI, платежи)
- Именование тестов
- Структура тестов (AAA: Arrange, Act, Assert)

### docs/reference/testing-reference.md

- Конфигурация pytest.ini
- Все доступные маркеры
- Фикстуры из conftest.py
- Параметры Allure
- Справочник по Allure API
- Справочник по pytest CLI

## Источники для best practices

- Официальная документация pytest: https://docs.pytest.org/en/stable/explanation/goodpractices.html
- Официальная документация Allure: https://github.com/allure-framework/allure-python
- Текущая структура проекта (tests/, conftest.py, pytest.ini)
- Существующие тесты в проекте как примеры

## Файлы проекта для изучения

- `tests/conftest.py` — фикстуры
- `tests/pytest.ini` — конфигурация pytest
- `Dockerfile.tests` — Docker для тестов
- `install-monitoring.sh` — установка мониторинга
- `docker-compose.yml` — сервисы monitoring и allure-service
- Примеры тестов из `tests/unit/`, `tests/integration/`, `tests/e2e/`

## Формат документов

- Дата последней редакции в начале каждого файла
- Использование Markdown согласно стандартам проекта
- Примеры кода с комментариями на русском
- Ссылки между документами
- Соответствие Diátaxis Framework (How-to guides и Reference)

## Примечания

- Документация должна быть практической и ориентированной на задачи
- Все примеры должны быть проверены на работоспособность
- Ссылки должны указывать на актуальные пути в проекте
- Использовать русский язык для всех описаний и комментариев

### To-dos

- [ ] Создать docs/guides/testing/README.md — главную страницу раздела тестирования с навигацией
- [ ] Создать docs/guides/testing/testing-structure.md — описание структуры тестов
- [ ] Создать docs/guides/testing/running-tests.md — инструкции по запуску тестов
- [ ] Создать docs/guides/testing/allure-reporting.md — работа с Allure Framework
- [ ] Создать docs/guides/testing/best-practices.md — best practices для написания тестов
- [ ] Создать docs/reference/testing-reference.md — справочник по pytest и Allure
- [ ] Обновить docs/guides/README.md — добавить раздел про тестирование
- [ ] Обновить docs/guides/development/README.md — добавить ссылку на тестирование
- [ ] Обновить docs/guides/testing/allure-defects-management.md — добавить ссылки на другие документы