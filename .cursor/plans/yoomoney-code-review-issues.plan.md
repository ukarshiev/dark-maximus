# Обнаруженные проблемы в реализованном коде

**Дата анализа:** 11.11.2025

**Версия:** 1.0.0

## Критические проблемы

### 1. Ошибка в SQL запросе: ALTER TABLE RENAME TO с параметризацией

**Файл:** `src/shop_bot/data_manager/database.py:1369`

**Проблема:**

```python
cursor.execute("ALTER TABLE transactions RENAME TO ?", (backup_name,))
```

SQLite не поддерживает параметризацию для имен таблиц в DDL операциях. Это вызовет ошибку `sqlite3.OperationalError`.

**Решение:**

Использовать форматирование строки с валидацией имени таблицы:

```python
# Валидация имени таблицы (только буквы, цифры, подчеркивания)
if not re.match(r'^[a-zA-Z0-9_]+$', backup_name):
    raise ValueError(f"Invalid table name: {backup_name}")
cursor.execute(f"ALTER TABLE transactions RENAME TO {backup_name}")
```

**Приоритет:** Высокий

---

### 2. Ошибка в JavaScript: использование неопределенной переменной `event`

**Файл:** `src/shop_bot/webhook_server/static/js/script.js:1634, 1659`

**Проблема:**

```javascript
function copyJSON(elementId) {
    // ...
    const button = event.target.closest('button'); // event не определен!
}
```

Переменная `event` не определена как параметр функции. Это вызовет `ReferenceError: event is not defined` при выполнении.

**Решение:**

Вариант 1: Передавать event как параметр:

```javascript
function copyJSON(elementId, event) {
    // ...
    const button = event.target.closest('button');
}
```

Вариант 2: Найти кнопку через элемент:

```javascript
function copyJSON(elementId) {
    const element = document.getElementById(elementId);
    // Находим родительский контейнер с кнопкой
    const container = element.closest('.user-detail-item');
    const button = container?.querySelector('button');
    // ...
}
```

**Приоритет:** Высокий

---

## Средние проблемы

### 3. Неэффективное использование PRAGMA journal_mode=WAL

**Файлы:**

- `src/shop_bot/data_manager/database.py:4963, 5022, 4892, 4648`
- Множество других мест

**Проблема:**

```python
cursor.execute("PRAGMA journal_mode=WAL")
```

WAL mode устанавливается при каждом подключении к БД. Хотя это не вызывает ошибок, это неэффективно:

- WAL mode устанавливается один раз и сохраняется в файле БД
- Повторная установка при каждом подключении избыточна
- Может вызывать лишние операции записи в БД

**Решение:**

Установить WAL mode один раз в `run_migration()` или `initialize_db()`, а не при каждом подключении. Для проверки можно использовать:

```python
cursor.execute("PRAGMA journal_mode")
current_mode = cursor.fetchone()[0]
if current_mode != 'wal':
    cursor.execute("PRAGMA journal_mode=WAL")
```

**Приоритет:** Средний

---

### 4. Потенциальная проблема с json_extract на TEXT поле

**Файл:** `src/shop_bot/webhook_server/app.py:676, 681, 685, 688, 691`

**Проблема:**

```sql
json_extract(t.metadata, '$.plan_id')
```

`metadata` хранится как TEXT (JSON строка). SQLite поддерживает `json_extract` на строках, но:

- Если metadata содержит невалидный JSON, `json_extract` вернет NULL без ошибки
- Это может привести к неочевидным проблемам при JOIN'ах
- Нет явной обработки ошибок парсинга JSON

**Решение:**

Добавить проверку валидности JSON перед использованием `json_extract` или обработать NULL значения:

```sql
-- Вариант 1: Проверка валидности
CASE 
    WHEN json_valid(t.metadata) = 1 
    THEN json_extract(t.metadata, '$.plan_id')
    ELSE NULL
END

-- Вариант 2: Использовать COALESCE с явной обработкой NULL
COALESCE(
    CASE WHEN json_valid(t.metadata) = 1 
         THEN json_extract(t.metadata, '$.plan_name')
         ELSE NULL END,
    p.plan_name
) as plan_name
```

**Приоритет:** Средний

---

### 5. Проблема с проверкой переменной через locals()

**Файл:** `src/shop_bot/webhook_server/app.py:2850`

**Проблема:**

```python
if 'existing_transaction' not in locals():
    existing_transaction = get_transaction_by_payment_id(payment_id)
```

Использование `locals()` для проверки переменной может быть ненадежным:

- `locals()` возвращает локальные переменные текущего scope
- Если переменная была определена в другом scope, проверка может не сработать
- Код становится менее читаемым

**Решение:**

Инициализировать переменную явно:

```python
# В начале функции
existing_transaction = None

# Позже
if not existing_transaction:
    existing_transaction = get_transaction_by_payment_id(payment_id)
```

Или использовать более явную проверку:

```python
existing_transaction = get_transaction_by_payment_id(payment_id) if payment_id else None
```

**Приоритет:** Средний

---

## Низкие проблемы / Улучшения

### 6. Отсутствие валидации входных данных в API endpoint

**Файл:** `src/shop_bot/webhook_server/app.py:747-755`

**Проблема:**

```python
payment_id = request.args.get('payment_id')
transaction_id = request.args.get('transaction_id', type=int)
limit = request.args.get('limit', default=100, type=int)
offset = request.args.get('offset', default=0, type=int)
```

Нет валидации:

- `limit` может быть отрицательным
- `offset` может быть отрицательным
- `payment_id` не проверяется на формат

**Решение:**

Добавить валидацию:

```python
if limit < 0:
    return jsonify({'status': 'error', 'message': 'Limit must be >= 0'}), 400
if offset < 0:
    return jsonify({'status': 'error', 'message': 'Offset must be >= 0'}), 400
```

**Приоритет:** Низкий

---

### 7. Потенциальная проблема с конкурентным доступом к webhook'ам

**Файл:** `src/shop_bot/webhook_server/app.py:2676-2694`

**Проблема:**

Webhook'и сохраняются в отдельном потоке через `threading.Thread`, но:

- Нет проверки успешного завершения потока
- Нет обработки исключений в потоке (только внутри функции)
- Нет ограничения на количество параллельных потоков

**Решение:**

Использовать очередь задач или пул потоков:

```python
from queue import Queue
import threading

webhook_queue = Queue(maxsize=100)

def webhook_worker():
    while True:
        webhook_data = webhook_queue.get()
        if webhook_data is None:
            break
        try:
            save_webhook_to_db(**webhook_data)
        except Exception as e:
            logger.error(f"Failed to save webhook: {e}")
        finally:
            webhook_queue.task_done()

# Запустить worker thread один раз при старте приложения
worker_thread = threading.Thread(target=webhook_worker, daemon=True)
worker_thread.start()

# В webhook handler:
webhook_queue.put({
    'webhook_type': 'yookassa',
    'event_type': event_type,
    # ...
})
```

**Приоритет:** Низкий

---

### 8. Потенциальная проблема с ORDER BY/LIMIT в UPDATE запросе

**Файл:** `src/shop_bot/webhook_server/app.py:2995, 3017, 3192, 3214`

**Проблема:**

```sql
UPDATE webhooks 
SET status = 'processed' 
WHERE payment_id = ? AND webhook_type = 'yookassa' AND event_type = ?
ORDER BY created_date DESC LIMIT 1
```

SQLite поддерживает `ORDER BY` и `LIMIT` в `UPDATE` запросах только если скомпилирован с опцией `SQLITE_ENABLE_UPDATE_DELETE_LIMIT`. Стандартная сборка Python sqlite3 может не иметь этой опции, что вызовет ошибку `sqlite3.OperationalError: near "ORDER"`.

**Решение:**

Использовать подзапрос для совместимости со всеми версиями SQLite:

```sql
UPDATE webhooks 
SET status = 'processed' 
WHERE webhook_id = (
    SELECT webhook_id 
    FROM webhooks 
    WHERE payment_id = ? AND webhook_type = 'yookassa' AND event_type = ?
    ORDER BY created_date DESC 
    LIMIT 1
)
```

**Приоритет:** Высокий

---

### 9. Потенциальная проблема с JOIN по json_extract в LEFT JOIN

**Файл:** `src/shop_bot/webhook_server/app.py:688-693`

**Проблема:**

```sql
LEFT JOIN plans p ON json_extract(t.metadata, '$.plan_id') = p.plan_id
```

Если `json_extract` возвращает строку, а `plan_id` - INTEGER, сравнение может не сработать корректно. SQLite может автоматически преобразовать типы, но это не гарантировано.

**Решение:**

Явное преобразование типов:

```sql
LEFT JOIN plans p ON CAST(json_extract(t.metadata, '$.plan_id') AS INTEGER) = p.plan_id
```

Или обработка NULL:

```sql
LEFT JOIN plans p ON 
    json_extract(t.metadata, '$.plan_id') IS NOT NULL 
    AND CAST(json_extract(t.metadata, '$.plan_id') AS INTEGER) = p.plan_id
```

**Приоритет:** Низкий

---

## Резюме

**Критические проблемы:** 3

**Средние проблемы:** 3

**Низкие проблемы:** 3

**Рекомендации:**

1. **Исправить критические проблемы немедленно** (ошибки выполнения):

   - Проблема #1: ALTER TABLE RENAME TO с параметризацией (SQLite не поддерживает)
   - Проблема #2: Использование неопределенной переменной `event` в JavaScript
   - Проблема #8: ORDER BY/LIMIT в UPDATE запросе (SQLite не поддерживает напрямую)

2. **Исправить средние проблемы в ближайшее время** (потенциальные проблемы):

   - Проблема #3: Неэффективное использование PRAGMA journal_mode=WAL
   - Проблема #4: Потенциальная проблема с json_extract на TEXT поле
   - Проблема #5: Проблема с проверкой переменной через locals()

3. **Улучшения можно отложить**, но желательно реализовать для стабильности:

   - Проблема #6: Отсутствие валидации входных данных в API endpoint
   - Проблема #7: Потенциальная проблема с конкурентным доступом к webhook'ам
   - Проблема #9: Потенциальная проблема с JOIN по json_extract