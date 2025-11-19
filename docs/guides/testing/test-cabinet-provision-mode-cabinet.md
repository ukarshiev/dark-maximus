# Тестирование личного кабинета с режимом предоставления "cabinet"

> **Дата последней редакции:** 16.11.2025 08:27

## Обзор

Документация описывает интеграционный тест `test_cabinet_provision_mode_flow`, который проверяет полный цикл работы личного кабинета при режиме предоставления "Личный кабинет" (`cabinet`). Этот режим является основной веткой, которую мы используем и тестируем.

## Описание теста

### `test_cabinet_provision_mode_flow`

Интеграционный тест, проверяющий полный цикл работы личного кабинета при режиме предоставления "Личный кабинет".

**Расположение:** `tests/integration/test_user_cabinet/test_cabinet_flow.py:616`

**Маркеры:**
- `@pytest.mark.integration` — интеграционный тест
- `@allure.epic("Личный кабинет")`
- `@allure.feature("Режим предоставления: Личный кабинет")`
- `@allure.story("Полный цикл покупки и работы кабинета")`
- `@allure.severity(allure.severity_level.CRITICAL)`

## Цель и область покрытия

### Цель теста

Проверить, что при режиме предоставления "Личный кабинет":
1. Тарифный план создается с правильным режимом предоставления
2. После покупки генерируется корректная ссылка на личный кабинет
3. Все три вкладки личного кабинета работают корректно:
   - **Инструкции** — отображается iframe с инструкциями по настройке VPN
   - **Подписка** — отображается секция подписки (если есть subscription_link)
   - **Проверка IP** — отображается функционал проверки IP-адреса
4. API `/api/ip-info` возвращает корректные данные

### Область покрытия

- Создание тарифного плана с `key_provision_mode='cabinet'`
- Симуляция покупки тарифа
- Генерация постоянного токена для личного кабинета
- Формирование URL личного кабинета
- Работа веб-интерфейса личного кабинета
- Проверка HTML структуры всех трех вкладок
- Тестирование API для проверки IP

## Структура теста

### Шаг 1: Создание тарифного плана с режимом 'cabinet'

**Что делается:**
- Создается пользователь через `register_user_if_not_exists`
- Создается хост через `create_host`
- Создается тарифный план с `key_provision_mode='cabinet'` через `create_plan`

**Параметры плана:**
- `host_name`: "test_host_cabinet"
- `plan_name`: "Test Cabinet Plan"
- `months`: 1
- `price`: 200.0
- `key_provision_mode`: 'cabinet'
- `display_mode`: 'all'

**Проверки:**
- План успешно создан в БД
- Режим предоставления установлен как 'cabinet'
- Название плана соответствует ожидаемому

### Шаг 2: Симуляция покупки тарифа

**Что делается:**
- Создается VPN ключ через `add_new_key` с параметрами тарифа
- Создается постоянный токен через `get_or_create_permanent_token`
- Получаются данные ключа из БД через `get_key_by_id`

**Параметры ключа:**
- `user_id`: 123500
- `host_name`: "test_host_cabinet"
- `expiry_ms`: текущая дата + 30 дней
- `plan_name`: "Test Cabinet Plan"
- `price`: 200.0

**Проверки:**
- `key_id` не `None`
- Токен успешно создан
- Данные ключа корректно сохранены в БД

### Шаг 3: Проверка ссылки на личный кабинет

**Что делается:**
- Получается домен личного кабинета через `get_user_cabinet_domain`
- Формируется URL: `{cabinet_domain}/auth/{token}`

**Проверки:**
- URL успешно сформирован
- URL содержит токен доступа

### Шаг 4: Тестирование веб-интерфейса

**Что делается:**
- Загружается Flask приложение через `_load_user_cabinet_app`
- Выполняется GET запрос к `/auth/{token}` с `follow_redirects=True`

**Проверки:**
- Статус ответа: 200 (OK)
- HTML страница успешно загружена

### Шаг 5: Проверка вкладки 'Инструкции'

**Что проверяется:**
- Наличие элемента `step-tab-setup` (кнопка вкладки)
- Наличие элемента `step-panel-setup` (панель вкладки)
- Вкладка активна по умолчанию (`is-active`)
- Наличие iframe для инструкций (`setup-iframe`)
- Наличие текста "Настройка VPN"

**HTML элементы:**
```html
<button id="step-tab-setup" class="steps-nav__item is-active">
  <span class="steps-nav__label">Настройка VPN</span>
</button>
<section id="step-panel-setup" class="step-pane step-pane--setup is-active">
  <iframe id="setup-iframe" class="step__iframe"></iframe>
</section>
```

### Шаг 6: Проверка вкладки 'Подписка'

**Что проверяется:**
- Наличие элемента `step-tab-subscription` (кнопка вкладки)
- Наличие элемента `step-panel-subscription` (панель вкладки)
- Наличие текста "Подключение"
- Наличие iframe для подписки (`subscription-iframe`) — если есть `subscription_link`

**HTML элементы:**
```html
<button id="step-tab-subscription" class="steps-nav__item">
  <span class="steps-nav__label">Подключение</span>
</button>
<section id="step-panel-subscription" class="step-pane step-pane--subscription">
  <iframe id="subscription-iframe" class="step__iframe"></iframe>
</section>
```

### Шаг 7: Проверка вкладки 'Проверка IP'

**Что проверяется:**
- Наличие элемента `step-tab-ip-check` (кнопка вкладки)
- Наличие элемента `step-panel-ip-check` (панель вкладки)
- Наличие текста "Проверка IP"
- Наличие кнопки "Обновить IP" (`ip-refresh`)
- Наличие функции `checkIP` в JavaScript

**HTML элементы:**
```html
<button id="step-tab-ip-check" class="steps-nav__item">
  <span class="steps-nav__label">Проверка IP</span>
</button>
<section id="step-panel-ip-check" class="step-pane step-pane--ip-check">
  <button class="ip-refresh" type="button" onclick="checkIP()">Обновить IP</button>
</section>
```

### Шаг 8: Тестирование API /api/ip-info

**Что делается:**
- Мокируется внешний API `requests.get` для возврата тестовых данных
- Выполняется GET запрос к `/api/ip-info`

**Мокируемые данные:**
```json
{
  "ip": "192.168.1.1",
  "country_name": "Russia",
  "city": "Moscow",
  "org": "Test ISP"
}
```

**Проверки:**
- Статус ответа: 200 (OK)
- Структура JSON ответа:
  - `status`: "ok"
  - `data`: объект с данными IP
- Поля в `data`:
  - `ip`: IP-адрес
  - `country`: страна
  - `city`: город
  - `provider`: провайдер

**Пример ответа API:**
```json
{
  "status": "ok",
  "data": {
    "ip": "192.168.1.1",
    "country": "Russia",
    "city": "Moscow",
    "provider": "Test ISP"
  }
}
```

## Проверяемые сценарии

### Основной сценарий (Happy Path)

1. ✅ Создание тарифного плана с режимом 'cabinet'
2. ✅ Симуляция покупки тарифа
3. ✅ Генерация ссылки на личный кабинет
4. ✅ Успешная авторизация по ссылке
5. ✅ Отображение всех трех вкладок
6. ✅ Работа API проверки IP

### Граничные случаи

- **Отсутствие subscription_link**: вкладка "Подписка" отображается, но iframe может отсутствовать
- **Отсутствие домена личного кабинета**: используется тестовый домен `http://localhost:50003`

## Примеры использования

### Запуск теста

```bash
# Запуск конкретного теста
docker compose exec autotest pytest tests/integration/test_user_cabinet/test_cabinet_flow.py::TestCabinetFlow::test_cabinet_provision_mode_flow -v

# Запуск с подробным выводом
docker compose exec autotest pytest tests/integration/test_user_cabinet/test_cabinet_flow.py::TestCabinetFlow::test_cabinet_provision_mode_flow -v --tb=long

# Запуск с Allure отчетами
docker compose exec autotest pytest tests/integration/test_user_cabinet/test_cabinet_flow.py::TestCabinetFlow::test_cabinet_provision_mode_flow --alluredir=allure-results
```

### Просмотр результатов в Allure

После запуска теста результаты доступны в Allure отчетах:

1. Откройте веб-интерфейс: `http://localhost:50005/allure-docker-service/projects/default/reports/latest/index.html`
2. Найдите тест `test_cabinet_provision_mode_flow`
3. Просмотрите детальные шаги и вложения:
   - Созданный тарифный план (JSON)
   - Созданный ключ и токен (JSON)
   - URL личного кабинета (TEXT)
   - HTML ответ главной страницы (HTML)
   - Результаты проверки каждой вкладки (TEXT)
   - Ответ API /api/ip-info (JSON)
   - Данные IP из API (TEXT)

## Связь с другими тестами

### Похожие тесты

- **`test_full_cabinet_flow`** — базовый тест полного flow кабинета
- **`test_cabinet_key_data_display`** — тест отображения данных ключа
- **`test_cabinet_with_subscription_link`** — тест кабинета с подпиской
- **`test_valid_cabinet_link_accessible`** — тест доступности ссылок кабинета

### Отличия

- **`test_cabinet_provision_mode_flow`** — единственный тест, который:
  - Создает тарифный план с режимом 'cabinet'
  - Проверяет все три вкладки личного кабинета
  - Тестирует API `/api/ip-info` с моками

## Технические детали

### Используемые функции

- `create_plan()` — создание тарифного плана
- `add_new_key()` — создание VPN ключа
- `get_or_create_permanent_token()` — генерация токена для кабинета
- `get_user_cabinet_domain()` — получение домена личного кабинета
- `_load_user_cabinet_app()` — загрузка Flask приложения

### Используемые моки

- `unittest.mock.patch('requests.get')` — мок для внешних API проверки IP

### Фикстуры

- `temp_db` — временная БД для изоляции теста

## Best Practices

### Изоляция теста

- Используется временная БД через фикстуру `temp_db`
- `DB_FILE` патчится для использования временной БД
- Восстановление оригинального `DB_FILE` в блоке `finally`

### Детальное логирование

- Все шаги обернуты в `allure.step()` для детального отчета
- Используются `allure.attach()` для сохранения промежуточных данных
- Подробные сообщения в assert для легкой отладки

### Мокирование внешних зависимостей

- Внешние API мокируются для стабильности теста
- Моки возвращают предсказуемые данные для проверки

## Возможные проблемы и решения

### Проблема: Тест падает на проверке API /api/ip-info

**Причина:** Мок не применяется к правильному модулю

**Решение:** Убедитесь, что `requests.get` мокируется до загрузки приложения или используйте правильный путь для патча

### Проблема: Вкладка "Подписка" не содержит iframe

**Причина:** У ключа нет `subscription_link`

**Решение:** Это нормальное поведение — iframe отображается только при наличии `subscription_link`

### Проблема: Домен личного кабинета не настроен

**Решение:** Тест использует тестовый домен `http://localhost:50003` если `get_user_cabinet_domain()` возвращает `None`

## См. также

- [Структура тестов](testing-structure.md) — организация тестов
- [Best Practices](best-practices.md) — рекомендации по написанию тестов
- [Allure отчеты](allure-reporting.md) — работа с Allure Framework
- [Режимы предоставления](../../reference/features-subscriptions.md) — документация по режимам предоставления

---

**Версия:** 1.0  
**Последнее обновление:** 16.11.2025 08:27  
**Автор:** Dark Maximus Team

