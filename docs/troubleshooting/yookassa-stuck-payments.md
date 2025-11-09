# Проблема зависших платежей YooKassa

**Дата создания:** 09.11.2025  
**Статус:** Решено

## Описание проблемы

Платежи YooKassa успешно проходят на стороне платежной системы, но ключи не выдаются пользователям, а транзакции остаются в статусе `pending` в админ-панели.

### Симптомы

1. Платеж успешно оплачен в YooKassa (статус `succeeded`)
2. В админ-панели транзакция висит в статусе `Ожидает` (pending)
3. Ключ не выдан пользователю
4. Пользователь не получил сообщение в Telegram

## Причины

### 1. Транзакция не создается в БД

**Проблема:**  
При создании платежа функция `create_pending_transaction()` не вызывается или падает с ошибкой.

**Файл:** `src/shop_bot/bot/handlers.py:4760`

**Решение:**  
- Добавлена проверка ошибок при создании транзакции
- Улучшено логирование в момент создания платежа

### 2. Webhook приходит, но не обрабатывается

**Проблема:**  
Webhook от YooKassa приходит, но:
- Event loop недоступен
- Bot instance не инициализирован
- Ошибка в обработчике `process_successful_yookassa_payment()`

**Файл:** `src/shop_bot/webhook_server/app.py:2440-2620`

**Решение:**
- Добавлено детальное логирование всех этапов webhook
- Добавлен fallback механизм при недоступном event loop
- Добавлено ожидание результата с таймаутом для отлова ошибок

### 3. Отсутствие инструментов для ручного исправления

**Проблема:**  
Нет способа вручную выдать ключ для зависшего платежа.

**Решение:**
- Создан endpoint `/transactions/retry/<payment_id>` для повторной обработки
- Добавлена кнопка "Повторить обработку" в админ-панель для pending платежей
- Созданы скрипты для ручной диагностики и исправления

## Исправления

### 1. Улучшенное логирование webhook

**Файл:** `src/shop_bot/webhook_server/app.py`

Добавлено логирование:
- Получения webhook с полной информацией о платеже
- Проверки наличия транзакции в БД
- Каждого этапа обработки платежа
- Результата обработки (успех/ошибка)

**Пример логов:**
```
[YOOKASSA_WEBHOOK] Received webhook: event=payment.succeeded, payment_id=30a29d3e-..., test=true, paid=True
[YOOKASSA_WEBHOOK] Transaction NOT FOUND in DB for payment_id=30a29d3e-...!
[YOOKASSA_WEBHOOK] Processing payment.succeeded: user_id=6044240344, action=new, plan_id=55
[YOOKASSA_WEBHOOK] Submitting payment processing to event loop for payment_id=30a29d3e-...
[YOOKASSA_WEBHOOK] Payment processing completed successfully for payment_id=30a29d3e-...
```

### 2. Fallback механизм

**Изменение:** Добавлен fallback при недоступном event loop

```python
if loop and loop.is_running():
    future = asyncio.run_coroutine_threadsafe(payment_processor(bot, metadata), loop)
    try:
        future.result(timeout=5)
        logger.info(f"[YOOKASSA_WEBHOOK] Payment processing completed")
    except Exception as e:
        logger.error(f"[YOOKASSA_WEBHOOK] Payment processing failed: {e}")
else:
    logger.error(f"[YOOKASSA_WEBHOOK] CRITICAL: Event loop not available!")
    logger.error(f"[YOOKASSA_WEBHOOK] FALLBACK DATA: payment_id={payment_id}, metadata={metadata}")
```

### 3. Кнопка "Повторить обработку" в админ-панели

**Расположение:** Страница "Платежи" → Меню транзакции (три точки) → "Повторить обработку"

**Условия отображения:**
- Статус транзакции: `pending`
- Метод оплаты: `YooKassa`
- Есть `payment_id`

**Действие:**  
Отправляет POST запрос на `/transactions/retry/<payment_id>`, который:
1. Проверяет транзакцию в БД
2. Валидирует метаданные
3. Вызывает `process_successful_yookassa_payment()` заново
4. Выдает ключ пользователю
5. Обновляет статус транзакции на `paid`

### 4. Скрипты для диагностики

**Созданы:**

1. **`tests/test_check_payment_30a29d3e.py`** — быстрая диагностика конкретного платежа
   - Проверяет наличие транзакции в БД
   - Показывает метаданные, план, пользователя
   
2. **`tests/test_fix_payment_30a29d3e.py`** — ручное исправление платежа
   - Создает транзакцию, если её нет
   - Вызывает обработчик успешного платежа
   - Выдает ключ пользователю

## Как исправить зависший платеж

### Вариант 1: Через админ-панель (рекомендуется)

1. Зайти в **Платежи**
2. Найти зависший платеж (статус "Ожидает", метод "YooKassa")
3. Открыть меню (три точки)
4. Нажать **"Повторить обработку"**
5. Подтвердить действие

Система автоматически:
- Проверит транзакцию
- Выдаст ключ пользователю
- Обновит статус на "Оплачено"
- Отправит сообщение в Telegram

### Вариант 2: Через скрипт

```bash
# Диагностика платежа
python tests/test_check_payment_30a29d3e.py

# Исправление платежа
python tests/test_fix_payment_30a29d3e.py
```

**Примечание:** В скриптах нужно изменить payment_id на актуальный.

### Вариант 3: Через API

```bash
curl -X POST \
  https://panel.dark-maximus.com/transactions/retry/30a29d3e-000f-5001-8000-18efc565b3c1 \
  -H "Cookie: session=<your_session_cookie>"
```

## Профилактика

### 1. Мониторинг логов

Следите за логами webhook:

```bash
npx nx logs bot --tail=200 2>&1 | Select-String -Pattern "YOOKASSA_WEBHOOK" -Context 2,2
```

Критичные сообщения:
- `Transaction NOT FOUND in DB` — транзакция не создалась
- `Event loop is not available` — бот не инициализирован
- `Payment processing failed` — ошибка при выдаче ключа

### 2. Регулярная проверка pending платежей

Проверяйте платежи в статусе `pending` старше 10 минут:

```sql
SELECT payment_id, user_id, created_date, payment_method 
FROM transactions 
WHERE status = 'pending' 
  AND payment_method = 'YooKassa'
  AND created_date < datetime('now', '-10 minutes')
ORDER BY created_date DESC;
```

### 3. Настройка webhook в YooKassa

Убедитесь, что webhook настроен правильно:
- **URL:** `https://panel.dark-maximus.com/yookassa-webhook`
- **События:** `payment.succeeded`, `payment.waiting_for_capture`, `payment.canceled`
- **Формат:** JSON
- **Версия API:** v3

## Дополнительные ресурсы

- [Документация YooKassa по webhook](https://yookassa.ru/developers/api#notification)
- [Анализ интеграции YooKassa](../analysis/yookassa-integration-analysis.md)
- [Настройка webhook YooKassa](../integrations/yookassa-webhook-setup.md)

## Дополнительная проблема: months=0

### Описание
Обнаружено, что при создании платежей для планов, содержащих только дни/часы (без месяцев), в metadata передавался только параметр `months=0`, но не `days` и `hours`. Это приводило к созданию ключей с неверным сроком действия.

### Затронутые планы
- Plan 58: M:0 D:1 H:0 = 1 день
- Plan 60: M:0 D:3 H:1 = 3.04 дня  
- Plan 61: M:0 D:2 H:1 = 2.04 дня
- Plan 62: M:0 D:0 H:1 = 1 час

### Исправления (09.11.2025 15:54)

#### 1. YooKassa
- ✅ Добавлены `days` и `hours` в metadata при создании платежа (`handlers.py:4737`)
- ✅ Добавлены `days` и `hours` в transaction metadata (`handlers.py:4752`)
- ✅ Обработка использует days/hours из metadata с fallback на план (`handlers.py:6378-6394`)

#### 2. Stars
- ✅ Добавлены `days` и `hours` в metadata (`handlers.py:5225-5226`)
- ✅ Добавлены в stars_metadata (`handlers.py:5259-5260`)

#### 3. TON Connect
- ✅ Добавлены `days` и `hours` в metadata (`handlers.py:5120`)

#### 4. Универсальная обработка
- ✅ Добавлен парсинг `days` и `hours` из metadata (`handlers.py:6532-6533`)
- ✅ Обработка использует значения из metadata с fallback (`handlers.py:6595-6596`)

### Логика работы

**При создании платежа:**
```python
months = plan['months']
days = int(plan.get('days') or 0)
hours = int(plan.get('hours') or 0)

metadata = {
    "months": months,
    "days": days,      # ← Теперь передается!
    "hours": hours,    # ← Теперь передается!
    ...
}
```

**При обработке платежа:**
```python
# Берем из metadata (то, что пользователь оплатил)
months = _to_int(metadata.get('months'))
days = _to_int(metadata.get('days', 0))
hours = _to_int(metadata.get('hours', 0))

# Используем с fallback на текущий план (для старых платежей)
extra_days = days if days > 0 else (int(plan.get('days') or 0) if plan else 0)
extra_hours = hours if hours > 0 else (int(plan.get('hours') or 0) if plan else 0)

days_to_add = months * 30 + extra_days + (extra_hours / 24)
```

## Дополнительные исправления (09.11.2025 16:15)

После первого исправления были обнаружены еще 3 метода оплаты без поддержки days/hours:

### CryptoBot
- ✅ `handlers.py:4823-4825` - добавлены days/hours при создании платежа
- ✅ `handlers.py:4844` - payload теперь содержит days/hours
- ✅ `app.py:2749-2786` - webhook поддерживает старый (9 частей) и новый (11 частей) форматы
- ✅ Обратная совместимость: старые платежи обрабатываются с days=0, hours=0

### Heleket
- ✅ `handlers.py:4900-4902` - добавлены days/hours при создании платежа
- ✅ `handlers.py:6171` - обновлена сигнатура `_create_heleket_payment_request`
- ✅ `handlers.py:6186` - metadata содержит days/hours
- ✅ Обратная совместимость: JSON metadata автоматически поддерживает fallback

### Balance (покупка из баланса)
- ✅ `handlers.py:5430-5433` - извлечение days/hours из плана
- ✅ `handlers.py:5458-5459` - metadata содержит days/hours

## История изменений

| Дата       | Изменение                                    |
|------------|----------------------------------------------|
| 09.11.2025 | Добавлено детальное логирование webhook      |
| 09.11.2025 | Добавлен fallback механизм для event loop    |
| 09.11.2025 | Добавлена кнопка "Повторить обработку"      |
| 09.11.2025 | Созданы скрипты для диагностики и исправления |
| 09.11.2025 15:54 | Исправлена передача days/hours для YooKassa, Stars, TON |
| 09.11.2025 16:15 | Исправлена передача days/hours для CryptoBot, Heleket, Balance |

