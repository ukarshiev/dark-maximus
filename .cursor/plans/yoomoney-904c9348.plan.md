<!-- 904c9348-46bd-4bdb-b034-589a7de51736 19a318f4-be76-468a-a53f-9c601fa6e7bb -->
# Исправление отображения данных платежей YooKassa

## Проблемы

1. **Username не отображается** - поле `username` в таблице `transactions` не заполняется
2. **План не отображается** - в metadata сохраняется только `plan_id`, но не `plan_name`
3. **Ключ не отображается** - `connection_string` не сохраняется в metadata транзакции
4. **Ссылка на оплату пустая** - `confirmation_url` не сохраняется в `payment_link`
5. **Нет полей API запрос/ответ** - отсутствуют поля для хранения JSON запроса и ответа от YooKassa
6. **Subscription Link не отображается в деталях ключа** - поле `subscription_link` не заполняется в функции `fillKeyDrawerData`
7. **Нет системы хранения webhook'ов** - webhook'и логируются, но не сохраняются структурированно для отображения в админке

## Решение по этапам

### Этап 1: Расширение структуры БД (Фундамент)

**Зависимости:** Нет
**Файлы:** `src/shop_bot/data_manager/database.py`

**Задачи:**

1. Добавить поля `api_request` и `api_response` (TEXT) в таблицу `transactions` через миграцию
2. Создать таблицу `webhooks` для гибридного хранения:

- `webhook_id` INTEGER PRIMARY KEY AUTOINCREMENT
- `webhook_type` TEXT NOT NULL (yookassa, heleket, ton)
- `event_type` TEXT (payment.succeeded, payment.waiting_for_capture и т.д.)
- `payment_id` TEXT
- `transaction_id` INTEGER (FK к transactions)
- `request_payload` TEXT (JSON)
- `response_payload` TEXT (JSON)
- `status` TEXT (received, processed, error)
- `created_date` TIMESTAMP DEFAULT CURRENT_TIMESTAMP
- Индексы: `payment_id`, `transaction_id`, `created_date`, `webhook_type`

3. Включить WAL mode для улучшения конкурентности (если еще не включен)
4. Обновить функцию `create_pending_transaction` для поддержки `payment_link`, `api_request`

**Критерии готовности:**

- Миграция выполнена успешно
- Таблица `webhooks` создана с индексами
- WAL mode активен
- Функция `create_pending_transaction` принимает новые параметры

---

### Этап 2: Сохранение данных при создании платежа

**Зависимости:** Этап 1
**Файлы:** `src/shop_bot/bot/handlers.py`, `src/shop_bot/data_manager/database.py`

**Задачи:**

1. В функции `create_yookassa_payment_handler`:

- Получать `plan_name` из `get_plan_by_id(plan_id)` и сохранять в metadata
- Сохранять `payment.confirmation.confirmation_url` в `payment_link`
- Сериализовать `payment_payload` в JSON и сохранять в `api_request`

2. Обновить вызов `create_pending_transaction` с новыми параметрами:

- `payment_link=payment.confirmation.confirmation_url`
- `api_request=json.dumps(payment_payload)`
- `metadata` с добавленным `plan_name`

**Критерии готовности:**

- При создании платежа сохраняются `plan_name`, `payment_link`, `api_request`
- Данные корректно записываются в БД

---

### Этап 3: Сохранение данных при получении webhook + система хранения webhook'ов

**Зависимости:** Этап 1, Этап 2
**Файлы:** `src/shop_bot/webhook_server/app.py`, `src/shop_bot/data_manager/database.py`

**Задачи:**

1. Создать функцию `save_webhook_to_db()` для сохранения webhook в таблицу `webhooks`:

- Асинхронная запись (через очередь или background task) для избежания блокировок БД
- Сохранение полного JSON payload в `request_payload`
- Связь с транзакцией через `transaction_id` или `payment_id`

2. В функции `yookassa_webhook_handler`:

- Вызывать `save_webhook_to_db()` для сохранения webhook (асинхронно)
- Сохранять JSON payload webhook в `api_response` при обновлении транзакции
- Сохранять `connection_string` в metadata при успешной обработке платежа
- Логировать webhook в файл (существующий механизм)

3. Создать функцию `cleanup_old_webhooks()` для периодической очистки:

- Удалять записи старше 90 дней из таблицы `webhooks`
- Интегрировать в scheduler или вызывать периодически

**Критерии готовности:**

- Webhook'и сохраняются в БД и логируются в файл
- `api_response` обновляется при получении webhook
- `connection_string` сохраняется в metadata
- Механизм очистки старых записей работает

---

### Этап 4: Улучшение API endpoints

**Зависимости:** Этап 1, Этап 2, Этап 3
**Файлы:** `src/shop_bot/webhook_server/app.py`

**Задачи:**

1. Улучшить функцию `get_transaction_details`:

- Добавить LEFT JOIN с таблицей `users` для получения `username`
- Добавить LEFT JOIN с таблицей `plans` для получения `plan_name` (fallback если нет в metadata)
- Добавить LEFT JOIN с таблицей `vpn_keys` для получения `connection_string` (по `user_id` и `host_name` из metadata)
- Возвращать `api_request` и `api_response` в ответе
- Возвращать `username` и `plan_name` в ответе

2. Создать новый API endpoint `/api/webhooks`:

- GET `/api/webhooks?payment_id=...` - получить webhook'и по payment_id
- GET `/api/webhooks?transaction_id=...` - получить webhook'и по transaction_id
- GET `/api/webhooks?limit=100&offset=0` - список последних webhook'ов
- Возвращать структурированные данные с пагинацией

**Критерии готовности:**

- API возвращает полные данные транзакции (username, plan_name, connection_string)
- API возвращает `api_request` и `api_response`
- Новый endpoint для webhook'ов работает корректно

---

### Этап 5: Обновление фронтенда для транзакций

**Зависимости:** Этап 4
**Файлы:** `src/shop_bot/webhook_server/templates/base.html`, `src/shop_bot/webhook_server/static/js/script.js`

**Задачи:**

1. В `templates/base.html`:

- Добавить секцию "API Запрос" в детали платежа (после "Детали платежа")
- Добавить секцию "API Ответ" в детали платежа
- Использовать `<pre>` с форматированием JSON
- Добавить кнопку "Копировать" для каждого JSON блока

2. В `static/js/script.js`:

- Обновить функцию `populateTransactionDrawer`:
- Отображать `username` из ответа API
- Отображать `plan_name` из ответа API (fallback на metadata)
- Отображать `connection_string` из ответа API
- Отображать `api_request` и `api_response` с форматированием JSON
- Добавить функцию `formatJSON(jsonString)` для красивого отображения JSON
- Добавить функцию `copyJSON(elementId)` для копирования JSON

**Критерии готовности:**

- Все поля отображаются корректно в деталях транзакции
- JSON форматируется читаемо
- Кнопки копирования работают

---

### Этап 6: Исправление Subscription Link в деталях ключа

**Зависимости:** Нет (независимый)
**Файлы:** `src/shop_bot/webhook_server/static/js/script.js`

**Задачи:**

1. В функции `fillKeyDrawerData`:

- Добавить заполнение поля `keyDetailSubscriptionLink` значением `key.subscription_link`
- Обработать случай когда `subscription_link` равен `null` или пустой строке

**Критерии готовности:**

- Subscription Link отображается в деталях ключа
- Корректно обрабатываются пустые значения

---

## Файлы для изменения

1. `src/shop_bot/data_manager/database.py` - миграция БД, создание таблицы webhooks, обновление функций
2. `src/shop_bot/bot/handlers.py` - сохранение данных при создании платежа
3. `src/shop_bot/webhook_server/app.py` - сохранение webhook'ов, улучшение API endpoints
4. `src/shop_bot/webhook_server/templates/base.html` - добавление секций API запрос/ответ
5. `src/shop_bot/webhook_server/static/js/script.js` - обновление отображения данных транзакций и ключей

## Порядок выполнения

1. **Этап 1** → 2. **Этап 2** → 3. **Этап 3** → 4. **Этап 4** → 5. **Этап 5** → 6. **Этап 6**

**Примечание:** Этап 6 можно выполнять параллельно с этапами 4-5, так как он независим.