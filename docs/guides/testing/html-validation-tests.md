# Тесты для валидации HTML и обработки ошибок Telegram API

> **Дата последней редакции:** 17.11.2025 05:35

## Обзор

Документация описывает тесты для предотвращения проблем с невалидными HTML-тегами (например, `<br>`) и обработки ошибок Telegram Bot API при парсинге HTML-сущностей.

## Проблема

Telegram Bot API не поддерживает некоторые HTML-теги, включая `<br>`. При попытке отправить сообщение с невалидными тегами возникает ошибка:

```
Telegram server says - Bad Request: can't parse entities: Unsupported start tag "br" at byte offset 50
```

Это приводит к:
- Падению бота при отправке сообщений
- Потере информации для пользователей
- Нестабильности работы бота

## Решение

### 1. Автоматическая замена невалидных тегов

Функция `get_message_text()` автоматически заменяет все варианты `<br>` тегов на переносы строк (`\n`):

```python
# В src/shop_bot/config.py
text = re.sub(r'<br\s*/?>', '\n', text, flags=re.IGNORECASE)
```

**Поддерживаемые варианты:**
- `<br>` → `\n`
- `<br/>` → `\n`
- `<br />` → `\n`
- `<BR>` → `\n` (независимо от регистра)

### 2. Обработка ошибок парсинга HTML

Обработчики сообщений перехватывают ошибки `TelegramBadRequest` и отправляют сообщение без HTML-форматирования:

```python
# В src/shop_bot/bot/handlers.py
try:
    await callback.message.edit_text(text=final_text, parse_mode=ParseMode.HTML)
except TelegramBadRequest as e:
    if "can't parse entities" in error_msg or "unsupported start tag" in error_msg:
        # Удаляем HTML-теги и отправляем plain text
        plain_text = re.sub(r'<[^>]+>', '', final_text)
        await callback.message.edit_text(text=plain_text)
```

## Тесты

### Класс: TestHtmlTagReplacement

Тесты для проверки замены невалидных HTML-тегов.

#### test_br_tag_replacement_in_get_message_text

**Цель:** Проверяет, что функция `get_message_text` корректно заменяет все варианты `<br>` тегов на переносы строк.

**Предварительные условия:**
- Временная БД создана и инициализирована (temp_db фикстура)
- Таблица message_templates существует в БД
- Функция get_message_text доступна для импорта

**Шаги выполнения:**
1. Подготовка тестового шаблона с различными вариантами `<br>` тегов
2. Сохранение шаблона в БД
3. Вызов функции `get_message_text` с template_key из БД
4. Проверка замены всех вариантов `<br>` на `\n`
5. Валидация HTML-тегов после замены

**Ожидаемые результаты:**
- Все варианты `<br>` тегов заменены на `\n`
- В результате присутствуют переносы строк
- Текст после замены проходит валидацию HTML

**Критичность:** CRITICAL

**Теги:** `html`, `br-tag`, `validation`, `unit`, `critical`, `telegram-api`, `message-formatting`

#### test_br_tag_replacement_with_variables

**Цель:** Проверяет, что замена `<br>` тегов работает корректно после подстановки переменных в шаблоны.

**Предварительные условия:**
- Временная БД создана
- Шаблон с переменными и `<br>` тегами сохранен в БД

**Шаги выполнения:**
1. Подготовка шаблона с переменными и `<br>` тегами
2. Вызов `get_message_text` с переменными
3. Проверка замены `<br>` и подстановки переменных
4. Валидация итогового текста

**Ожидаемые результаты:**
- `<br>` теги заменены на `\n`
- Переменные подставлены корректно
- Итоговый текст валиден для Telegram

**Критичность:** CRITICAL

**Теги:** `html`, `br-tag`, `variables`, `unit`, `critical`

### Класс: TestTelegramBadRequestHandling

Тесты для проверки обработки ошибок TelegramBadRequest при парсинге HTML.

#### test_handle_parse_entities_error

**Цель:** Проверяет, что обработчик корректно обрабатывает ошибку "can't parse entities" и отправляет сообщение без форматирования.

**Предварительные условия:**
- Мок callback.message.edit_text настроен для симуляции ошибки
- TelegramBadRequest исключение доступно для импорта

**Шаги выполнения:**
1. Подготовка мока с ошибкой парсинга HTML
2. Симуляция обработки ошибки (как в handlers.py)
3. Проверка результата:
   - edit_text вызван дважды
   - Второй вызов без parse_mode
   - Plain text не содержит HTML-тегов

**Ожидаемые результаты:**
- Ошибка перехвачена и обработана
- Сообщение отправлено без HTML-форматирования
- HTML-теги удалены из текста
- Пользователь получает информацию даже при ошибке

**Критичность:** CRITICAL

**Теги:** `telegram`, `error-handling`, `html-parsing`, `unit`, `critical`, `telegram-api`, `exception-handling`

#### test_handle_unsupported_tag_error

**Цель:** Проверяет обработку ошибки "unsupported start tag" при отправке сообщения.

**Предварительные условия:**
- Мок callback настроен для симуляции ошибки unsupported start tag

**Шаги выполнения:**
1. Подготовка мока с ошибкой unsupported start tag
2. Симуляция обработки ошибки
3. Проверка результата

**Ожидаемые результаты:**
- Ошибка обработана корректно
- Сообщение отправлено без HTML-форматирования
- Пользователь получает информацию

**Критичность:** CRITICAL

**Теги:** `telegram`, `error-handling`, `html-parsing`, `unit`, `critical`

## Запуск тестов

### Все тесты HTML-валидации

```bash
docker compose exec autotest pytest tests/unit/test_utils/test_message_templates.py::TestHtmlTagReplacement -v
```

### Все тесты обработки ошибок

```bash
docker compose exec autotest pytest tests/unit/test_utils/test_message_templates.py::TestTelegramBadRequestHandling -v
```

### Конкретный тест

```bash
docker compose exec autotest pytest tests/unit/test_utils/test_message_templates.py::TestHtmlTagReplacement::test_br_tag_replacement_in_get_message_text -v
```

## Просмотр отчетов Allure

После запуска тестов отчеты доступны по адресу:

- **Последний отчет:** `http://localhost:50005/allure-docker-service/projects/default/reports/latest/index.html`
- **Главная страница:** `http://localhost:50005/allure-docker-service/`

### Фильтрация тестов

В Allure отчете можно фильтровать тесты по:
- **Тегам:** `html`, `br-tag`, `validation`, `critical`, `telegram-api`, `error-handling`
- **Severity:** CRITICAL
- **Компонентам:** `config`, `bot-handlers`
- **Story:** `html-tag-replacement`, `error-handling`

## Структура тестов в Allure

### Epic: Форматирование сообщений

Все тесты находятся в epic "Форматирование сообщений".

### Features

- **Обработка невалидных HTML-тегов** — тесты замены `<br>` тегов
- **Обработка ошибок Telegram API** — тесты обработки TelegramBadRequest

### Labels

- **owner:** qa-team
- **component:** config, bot-handlers
- **story:** html-tag-replacement, error-handling

## Детали тестов в Allure

Каждый тест содержит:

1. **Подробное описание** с:
   - Целью теста
   - Предварительными условиями
   - Шагами выполнения
   - Ожидаемыми результатами
   - Проверяемыми аспектами
   - Важностью теста

2. **Шаги выполнения** (`allure.step`):
   - Подготовка данных
   - Вызов функций
   - Проверка результатов

3. **Вложения (attachments):**
   - Тестовые шаблоны (JSON)
   - Результаты обработки (HTML)
   - Детали валидации (JSON)
   - Статистика (TEXT)

4. **Метки и теги:**
   - Severity (CRITICAL)
   - Теги для фильтрации
   - Labels (owner, component, story)

## Проверка отчетов

После выполнения тестов проверьте:

1. **Статус тестов:** Все тесты должны пройти (passed)
2. **Шаги выполнения:** Все шаги должны быть выполнены успешно
3. **Вложения:** Все вложения должны быть прикреплены
4. **Описания:** Описания должны быть полными и понятными
5. **Теги и метки:** Теги и метки должны быть корректными

## Известные проблемы

### Проблема с отображением названий тестов

В некоторых версиях Allure Report могут отображаться пробелы в названиях тестов вместо точек. Это визуальная проблема, не влияющая на функциональность.

**Решение:** Используйте `@allure.title()` для читаемых названий тестов.

## Рекомендации

1. **Регулярно запускайте тесты:** Проверяйте результаты после каждого изменения кода
2. **Проверяйте отчеты Allure:** Убедитесь, что все тесты прошли успешно
3. **Используйте фильтры:** Фильтруйте тесты по тегам и severity для быстрого поиска
4. **Обновляйте описания:** Поддерживайте описания тестов в актуальном состоянии

## Связанные документы

- [Allure Reporting](allure-reporting.md) — общая информация об Allure Framework
- [Allure Test Description Template](allure-test-description-template.md) — шаблон описания тестов
- [Testing Structure](testing-structure.md) — структура тестов в проекте
- [Running Tests](running-tests.md) — инструкции по запуску тестов

---

**Версия:** 1.0  
**Последнее обновление:** 16.11.2025  
**Автор:** Dark Maximus Team

