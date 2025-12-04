<!-- 8243dbdd-e3ae-466d-aaa0-d5121dcc0750 938e4870-31d8-455b-ae5d-23356b225a79 -->
# Исправление зависания бота при оплате через YooKassa

## Проблема

При выборе оплаты "Банковской картой" бот зависает и перестает отвечать. В логах видно:

- `Retrying (Retry(total=2, ...)) after connection broken by 'RemoteDisconnected(...)': /v3/payments`
- Синхронный вызов `Payment.create()` блокирует event loop при проблемах с сетью
- urllib3 пытается повторить запрос синхронно, что приводит к зависанию бота

## Решение

Обернуть синхронный вызов `Payment.create()` в `asyncio.to_thread()` с таймаутом через `asyncio.wait_for()`, чтобы не блокировать event loop.

**Важно:**

- `asyncio.to_thread()` доступен в Python 3.11 (используется в проекте)
- Импорт `asyncio` уже присутствует в файле (строка 14)
- Другие синхронные вызовы (`get_setting()`, `create_pending_transaction()`) - быстрые SQLite операции и не блокируют event loop

## Изменения

### 1. Исправление `create_yookassa_payment_handler()` в `src/shop_bot/bot/handlers.py`

**Текущий код (строка 5162):**

```python
payment = Payment.create(payment_payload, uuid.uuid4())
```

**Новый код:**

```python
import time
start_time = time.time()
try:
    payment = await asyncio.wait_for(
        asyncio.to_thread(Payment.create, payment_payload, uuid.uuid4()),
        timeout=30.0
    )
    elapsed_time = time.time() - start_time
    logger.info(f"[YOOKASSA_PAYMENT_PURCHASE] Payment created successfully in {elapsed_time:.2f}s, payment_id={payment.id}")
except asyncio.TimeoutError:
    elapsed_time = time.time() - start_time
    logger.error(f"[YOOKASSA_PAYMENT_PURCHASE] Timeout after {elapsed_time:.2f}s while creating payment for user_id={user_id}")
    await callback.message.answer(
        "❌ Не удалось создать ссылку на оплату. Пожалуйста, попробуйте снова или выберите другой способ оплаты. Если проблема повториться обратитесь в службу поддержки."
    )
    await state.clear()
    return
except Exception as e:
    elapsed_time = time.time() - start_time
    logger.error(f"[YOOKASSA_PAYMENT_PURCHASE] Failed to create payment after {elapsed_time:.2f}s: {e}", exc_info=True)
    # Общая обработка ошибок (уже есть в коде)
```

- Обернуть `Payment.create()` в `asyncio.to_thread()` для выполнения в отдельном потоке
- Добавить таймаут 30 секунд через `asyncio.wait_for()`
- Обработать ошибки таймаута (`asyncio.TimeoutError`) отдельно от общих исключений
- При таймауте отправлять пользователю понятное сообщение и завершать обработку (return)
- Логировать время выполнения для диагностики

### 2. Исправление `topup_pay_yookassa()` в `src/shop_bot/bot/handlers.py`

**Текущий код (строка 4460):**

```python
payment = Payment.create(payment_payload, uuid.uuid4())
```

**Новый код:**

- Применить те же изменения: обернуть в `asyncio.to_thread()` с таймаутом
- Обработать ошибки таймаута и соединения

### 3. Обработка ошибок

Добавить обработку следующих ошибок:

- `asyncio.TimeoutError` - таймаут при создании платежа
- `ConnectionError`, `RemoteDisconnected` - проблемы с сетью
- Общие исключения от YooKassa API

При ошибке отправлять пользователю сообщение:

```
❌ Не удалось создать ссылку на оплату. Пожалуйста, попробуйте снова или выберите другой способ оплаты. Если проблема повториться обратитесь в службу поддержки.
```

### 4. Логирование

Добавить логирование:

- Время выполнения создания платежа
- Ошибки таймаута и соединения
- Успешное создание платежа

## Файлы для изменения

1. `src/shop_bot/bot/handlers.py`:

   - Функция `create_yookassa_payment_handler()` (строка ~5162)
   - Функция `topup_pay_yookassa()` (строка ~4460)

## Тестирование

После исправления проверить:

1. Создание платежа при нормальной работе сети
2. Поведение при таймауте (имитация медленного соединения)
3. Поведение при обрыве соединения
4. Бот должен продолжать отвечать на другие запросы даже при проблемах с YooKassa

## Дополнительные улучшения (опционально)

1. Настройка таймаутов urllib3 для библиотеки yookassa (если поддерживается)
2. Добавление retry логики на уровне приложения с экспоненциальной задержкой
3. Мониторинг времени ответа YooKassa API

### To-dos

- [ ] Обернуть Payment.create() в create_yookassa_payment_handler() в asyncio.to_thread() с таймаутом 30 секунд
- [ ] Обернуть Payment.create() в topup_pay_yookassa() в asyncio.to_thread() с таймаутом 30 секунд
- [ ] Добавить обработку ошибок таймаута и соединения с понятными сообщениями пользователю
- [ ] Добавить логирование времени выполнения и ошибок при создании платежей YooKassa