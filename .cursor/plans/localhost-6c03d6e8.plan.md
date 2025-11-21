<!-- 6c03d6e8-e669-4875-bb06-7553360dc19e 510f49d4-2b08-4c03-a75d-1dd18a9d59eb -->
# Исправление ссылок на localhost в веб-панели

## Проблема

На боевом сайте https://panel.dark-maximus.com/ кнопки в header dashboard завязаны на hardcoded localhost, а должны использовать домены из глобальных параметров настроек.

## Решение

### 1. Добавление настройки "Домен Allure для тестирования"

**Файл:** `src/shop_bot/webhook_server/templates/settings.html`

Добавить новое поле в раздел "Глобальные параметры" после поля "Домен для личного кабинета" (после строки 337):

- Поле: "Домен Allure для тестирования"
- name: `allure_domain`
- placeholder: `https://tests.dark-maximus.com`
- Описание: "Если не указан, будет использоваться localhost:50005"

### 2. Обновление функции сохранения настроек

**Файл:** `src/shop_bot/webhook_server/app.py`

В функции `save_panel_settings()` (строка 1170) добавить `'allure_domain'` в список `panel_keys`:

```python
panel_keys = ['panel_login', 'global_domain', 'docs_domain', 'codex_docs_domain', 'user_cabinet_domain', 'allure_domain', 'admin_timezone', ...]
```

### 3. Формирование allure_url в get_common_template_data()

**Файл:** `src/shop_bot/webhook_server/app.py`

В функции `get_common_template_data()` (после строки 490) добавить логику формирования `allure_url` аналогично `wiki_url` и `knowledge_base_url`:

- Читать настройку `allure_domain` из БД
- Если указан - нормализовать (убрать слэш, добавить https:// если нет протокола)
- Если не указан - использовать fallback `http://localhost:50005`
- Добавить `allure_url` в возвращаемый словарь

### 4. Обновление dashboard.html

**Файл:** `src/shop_bot/webhook_server/templates/dashboard.html`

Заменить hardcoded ссылки на localhost на использование переменных из `common_data`:

- Строка 7: `http://localhost:50001` → `{{ wiki_url }}` (уже формируется в `get_common_template_data()`)
- Строка 11: `http://localhost:50002` → `{{ knowledge_base_url }}` (уже формируется в `get_common_template_data()`)
- Строка 15: `{{ latest_cabinet_link or 'http://localhost:50003' }}` → убрать fallback на localhost, использовать только `{{ latest_cabinet_link }}` (функция `get_latest_cabinet_link()` уже использует `get_user_cabinet_domain()` из настроек)
- Строка 19: `http://localhost:50005/allure-docker-service/` → `{{ allure_url }}/allure-docker-service/` (использовать новую переменную из настроек)

### 2. Проверка логики fallback

**Файл:** `src/shop_bot/webhook_server/app.py`

Убедиться, что:

- `get_common_template_data()` (строки 460-502) правильно формирует `wiki_url` и `knowledge_base_url` из настроек БД с fallback на localhost только если настройки не заданы
- `get_latest_cabinet_link()` (строки 509-560) использует `get_user_cabinet_domain()` из настроек БД

**Текущая логика корректна:** функции уже используют настройки из БД, но имеют fallback на localhost для локальной разработки.

### 3. Обновление title атрибутов

Обновить title атрибуты кнопок в dashboard.html, чтобы они не содержали hardcoded "localhost:5000X", а использовали динамические значения или общие описания.

## Файлы для изменения

1. `src/shop_bot/webhook_server/templates/dashboard.html` - замена hardcoded ссылок на переменные из шаблона

## Ожидаемый результат

На боевом сайте кнопки в header dashboard будут открывать ссылки, указанные в глобальных параметрах:

- Docs → `https://docs.dark-maximus.com` (из настройки `docs_domain`)
- Codex → `https://help.dark-maximus.com` (из настройки `codex_docs_domain`)
- Кабинет → домен из настройки `user_cabinet_domain`
- Тесты → останется localhost:50005 (настройка не предусмотрена)