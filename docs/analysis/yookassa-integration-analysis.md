# Анализ интеграции YooKassa: Отчет по Best Practices

> **Дата анализа:** 08.11.2025  
> **Анализ выполнен согласно:** [План YooKassa Integration Fixes](../../.cursor/plans/yookassa-integration-fixes-54c2ae1c.plan.md)  
> **Linear Issue:** KAR-34

---

## 📋 Executive Summary

Проведен полный анализ текущей интеграции YooKassa на соответствие официальной документации и Best Practices. Выявлено **8 критических проблем** и **5 рекомендаций** для улучшения.

**Общая оценка:** ⚠️ **Требуется доработка**

---

## 1. Конфигурация и инициализация

### 1.1 ✅ Правильность использования Configuration.configure()

**Файл:** `src/shop_bot/bot_controller.py` (строки 118-157)

```python
Configuration.configure(
    account_id=yookassa_shop_id, 
    secret_key=yookassa_secret_key, 
    api_url=api_url, 
    verify=verify_ssl
)
```

**Статус:** ✅ **ХОРОШО**  
Используется правильный метод `Configuration.configure()` с всеми необходимыми параметрами.

---

### 1.2 ✅ Корректное различение тестового и боевого API URL

**Файл:** `src/shop_bot/bot_controller.py` (строки 118-136)

```python
if yookassa_test_mode:
    api_url = _safe_strip(database.get_setting("yookassa_test_api_url")) or \
              _safe_strip(database.get_setting("yookassa_api_url")) or \
              DEFAULT_YOOKASSA_API_URL
else:
    api_url = _safe_strip(database.get_setting("yookassa_api_url")) or DEFAULT_YOOKASSA_API_URL
```

**Статус:** ⚠️ **ПРОБЛЕМА**

**Проблемы:**
1. В тестовом режиме fallback к `DEFAULT_YOOKASSA_API_URL = "https://api.yookassa.ru/v3"` (боевой URL!)
2. Должно быть: `"https://api.test.yookassa.ru/v3"` для тестового режима
3. Нет явной проверки соответствия URL режиму

**Рекомендация:**
```python
DEFAULT_YOOKASSA_API_URL = "https://api.yookassa.ru/v3"
DEFAULT_YOOKASSA_TEST_API_URL = "https://api.test.yookassa.ru/v3"

if yookassa_test_mode:
    api_url = _safe_strip(database.get_setting("yookassa_test_api_url")) or DEFAULT_YOOKASSA_TEST_API_URL
else:
    api_url = _safe_strip(database.get_setting("yookassa_api_url")) or DEFAULT_YOOKASSA_API_URL
```

---

### 1.3 ⚠️ Fallback логика с test/production ключами

**Файл:** `src/shop_bot/bot_controller.py` (строки 125-136)

```python
if yookassa_test_mode:
    yookassa_shop_id = _safe_strip(database.get_setting("yookassa_test_shop_id")) or \
                       _safe_strip(database.get_setting("yookassa_shop_id"))  # ⚠️ ОПАСНО!
```

**Статус:** ❌ **КРИТИЧЕСКАЯ ПРОБЛЕМА**

**Проблемы:**
1. **Смешивание режимов:** Если тестовые ключи пустые, используются production ключи в тестовом режиме
2. **Риск потери денег:** Тестовые платежи могут создаваться с боевыми ключами
3. **Несогласованность:** БД говорит "test mode", но используются production credentials

**Влияние:**
- Пользователь думает, что работает в тестовом режиме
- Фактически создаются боевые платежи
- Реальные деньги списываются "в тесте"

**Рекомендация:**
```python
if yookassa_test_mode:
    yookassa_shop_id = _safe_strip(database.get_setting("yookassa_test_shop_id"))
    yookassa_secret_key = _safe_strip(database.get_setting("yookassa_test_secret_key"))
    
    # КРИТИЧНО: Не делаем fallback к production ключам
    if not yookassa_shop_id or not yookassa_secret_key:
        logger.error("[YOOKASSA] Test mode enabled but test credentials missing!")
        yookassa_enabled = False
        return
```

---

### 1.4 ✅ Проверка verify_ssl

**Файл:** `src/shop_bot/bot_controller.py` (строки 129, 135)

```python
verify_ssl = _setting_to_bool(database.get_setting("yookassa_test_verify_ssl"), True)
verify_ssl = _setting_to_bool(database.get_setting("yookassa_verify_ssl"), True)
```

**Статус:** ✅ **ХОРОШО**  
По умолчанию `True`, что правильно для production.

---

### 1.5 ⚠️ Configuration инициализируется только при старте

**Файл:** `src/shop_bot/bot_controller.py` (строка 156)

**Статус:** ❌ **КРИТИЧЕСКАЯ ПРОБЛЕМА**

**Проблемы:**
1. Configuration устанавливается ОДИН раз при запуске бота
2. Если администратор меняет режим в UI (test ↔ production), изменения **НЕ применяются**
3. Необходим перезапуск бота для применения изменений
4. Это не документировано и не очевидно для пользователя

**Текущее решение:** `_reconfigure_yookassa()` в handlers.py (строки 87-116)

```python
def _reconfigure_yookassa():
    """Переинициализирует Configuration с актуальными настройками из БД"""
    from yookassa import Configuration
    
    yookassa_test_mode = get_setting("yookassa_test_mode") == "true"
    # ... (логика переинициализации)
```

**Проблемы с текущим решением:**
- Вызывается перед **КАЖДЫМ** созданием платежа (overhead)
- Но **НЕ** вызывается при старте бота в handlers.py
- Нет логирования, что конфигурация изменилась
- Нет проверки, отличается ли новая конфигурация от текущей

**Статус использования `_reconfigure_yookassa()`:**
- ✅ Вызывается в `topup_pay_yookassa()` (строка 4086)
- ✅ Вызывается в `create_yookassa_payment_handler()` (строка 4688)

**Рекомендация:**
1. Добавить детальное логирование в `_reconfigure_yookassa()`
2. Добавить предупреждение в UI при несовпадении режимов
3. TODO: Добавить автоматический рестарт при изменении режима

---

## 2. Создание платежей

### 2.1 ✅ Наличие idempotency key

**Файлы:** 
- `handlers.py:4102` (topup)
- `handlers.py:4724` (purchase)

```python
payment = Payment.create(payment_payload, uuid.uuid4())
```

**Статус:** ✅ **ХОРОШО**  
Используется `uuid.uuid4()` для idempotency key в каждом запросе.

---

### 2.2 ✅ Формат idempotency key

**Статус:** ✅ **ХОРОШО**  
UUID v4 является стандартным и правильным форматом.

---

### 2.3 ✅ Правильное использование Payment.create()

**Статус:** ✅ **ХОРОШО**  
API используется корректно.

---

### 2.4 ✅ Параметры платежа

**Файл:** `handlers.py` (строки 4088-4100, 4708-4722)

```python
payment_payload = {
    "amount": {"value": price_str_for_api, "currency": "RUB"},
    "confirmation": {"type": "redirect", "return_url": f"https://t.me/{TELEGRAM_BOT_USERNAME}"},
    "capture": True,
    "description": "...",
    "test": yookassa_test_mode,  # ✅ ДОБАВЛЕНО!
    "metadata": {...}
}
```

**Статус:** ✅ **ОТЛИЧНО**

**Хорошие практики:**
- ✅ `amount.value` и `amount.currency` указаны
- ✅ `confirmation.type` и `confirmation.return_url` настроены
- ✅ `capture=True` для одностадийных платежей
- ✅ `metadata` передается для webhook
- ✅ `description` указан
- ✅ **`test` параметр явно указывается** (строки 4093, 4713)

**Особенность:**
Параметр `"test": yookassa_test_mode` передается явно в payload. Это **критически важно** для YooKassa API.

---

### 2.5 ⚠️ Логирование режима при создании платежа

**Файл:** `handlers.py` (строки 4684-4696)

```python
yookassa_test_mode = get_setting("yookassa_test_mode") == "true"
_reconfigure_yookassa()

current_shop_id = get_setting("yookassa_shop_id")
logger.info(f"Creating Yookassa payment: test_mode={yookassa_test_mode}, shop_id={current_shop_id}")
if yookassa_test_mode and current_shop_id:
    logger.warning(f"⚠️ ATTENTION: test_mode=true with shop_id={current_shop_id}. Ensure settings are synchronized!")
```

**Статус:** ⚠️ **ЧАСТИЧНО ХОРОШО**

**Проблемы:**
1. Логирование только в `create_yookassa_payment_handler`, но не в `topup_pay_yookassa`
2. Не логируется `api_url`, который используется
3. Не логируется, какой именно shop_id применен после `_reconfigure_yookassa()`
4. Нет логирования значения `Configuration.account_id` для проверки

**Рекомендация:**
```python
from yookassa import Configuration

_reconfigure_yookassa()

logger.info(
    f"[YOOKASSA_PAYMENT] Creating payment: user_id={user_id}, amount={amount}, "
    f"test_mode={yookassa_test_mode}, "
    f"active_shop_id={Configuration.account_id[:4] if Configuration.account_id else 'None'}..., "
    f"api_url={Configuration.api_url if hasattr(Configuration, 'api_url') else 'default'}"
)
```

---

## 3. Обработка webhook уведомлений

### 3.1 ✅ Проверка типов событий

**Файл:** `app.py` (строки 2432, 2467, 2505)

```python
if event_type == "payment.succeeded":
    # ...
elif event_type == "payment.waiting_for_capture":
    # ...
elif event_type == "payment.canceled":
    # ...
else:
    logger.info(f"YooKassa webhook: unhandled event type={event_type}, payment_id={payment_object.get('id')}")
```

**Статус:** ✅ **ОТЛИЧНО**  
Обрабатываются все ключевые события YooKassa.

---

### 3.2 ✅ Проверка paid=true

**Файл:** `app.py` (строки 2434, 2470)

```python
if event_type == "payment.succeeded":
    if payment_object.get("paid") is True:
        # обработка успешного платежа
    else:
        logger.warning(f"YooKassa webhook: payment.succeeded but paid=false, payment_id={...}")
```

**Статус:** ✅ **ОТЛИЧНО**  
Явная проверка `paid=true` перед обработкой.

---

### 3.3 ✅ Извлечение metadata

**Файл:** `app.py` (строки 2435, 2473, 2508)

```python
metadata = payment_object.get("metadata", {})
```

**Статус:** ✅ **ХОРОШО**

---

### 3.4 ✅ Обработка authorization_details

**Файл:** `app.py` (строки 2438-2453)

```python
yookassa_payment_id = payment_object.get("id")
authorization_details = payment_object.get("authorization_details", {})
rrn = authorization_details.get("rrn")
auth_code = authorization_details.get("auth_code")
payment_method = payment_object.get("payment_method", {})
payment_type = payment_method.get("type", "unknown")

metadata.update({
    "yookassa_payment_id": yookassa_payment_id,
    "rrn": rrn,
    "authorization_code": auth_code,
    "payment_type": payment_type
})
```

**Статус:** ✅ **ОТЛИЧНО**  
Извлекаются и сохраняются все важные данные:
- RRN (Reference Retrieval Number)
- Authorization code
- Payment type (bank_card, sbp, apple_pay, google_pay и т.д.)

---

### 3.5 ✅ Логирование событий

**Файл:** `app.py` (строки 2429, 2465, 2471, 2503, 2511, 2526)

```python
logger.info(f"YooKassa webhook received: event={event_type}, payment_id={payment_object.get('id')}")
logger.warning(f"YooKassa webhook: payment.succeeded but paid=false, payment_id={...}")
logger.info(f"YooKassa webhook: payment.waiting_for_capture with paid=true, processing as succeeded, payment_id={...}")
# и т.д.
```

**Статус:** ✅ **ХОРОШО**  
Все ключевые события логируются.

---

### 3.6 ⚠️ Проверка на дублирование обработки

**Статус:** ⚠️ **НЕ РЕАЛИЗОВАНО**

**Проблема:**
- Нет проверки, обрабатывался ли уже этот `payment_id`
- Если webhook придет дважды (network retry, YooKassa retry), платеж обработается дважды
- Пользователь получит **2 ключа** вместо 1

**Текущая защита:**
- База данных использует `payment_id` как PRIMARY KEY в таблице `transactions`
- При повторной обработке вызов `update_yookassa_transaction()` обновит существующую запись
- **НО:** логика создания ключа (`process_successful_yookassa_payment`) выполнится дважды

**Рекомендация:**
```python
@flask_app.route('/yookassa-webhook', methods=['POST'])
def yookassa_webhook_handler():
    try:
        event_json = request.json
        payment_id = event_json.get("object", {}).get("id")
        
        # Проверка на дублирование
        from shop_bot.data_manager.database import get_transaction_by_payment_id
        existing_transaction = get_transaction_by_payment_id(payment_id)
        
        if existing_transaction and existing_transaction['status'] == 'paid':
            logger.info(f"YooKassa webhook: payment {payment_id} already processed, skipping")
            return 'OK', 200
        
        # ... остальная обработка
```

---

## 4. Поле `test` в Payment Object

### 4.1 ❌ Проверка поля test в webhook

**Файл:** `app.py` (webhook handler)

**Статус:** ❌ **КРИТИЧЕСКАЯ ПРОБЛЕМА**

**Что отсутствует:**
1. Нет извлечения поля `payment_object.get("test")`
2. Нет логирования, тестовый ли это платеж
3. Нет проверки соответствия с настройкой `yookassa_test_mode` из БД
4. Нет предупреждения, если пришел тестовый платеж в боевом режиме (или наоборот)

**Риски:**
- Невозможно отследить смешивание тестовых/боевых платежей
- Сложно отлаживать проблемы с режимами
- Нет защиты от обработки тестового платежа как боевого

**Рекомендация:**
```python
@flask_app.route('/yookassa-webhook', methods=['POST'])
def yookassa_webhook_handler():
    try:
        event_json = request.json
        payment_object = event_json.get("object", {})
        
        # НОВОЕ: Извлекаем и логируем поле test
        is_test_payment = payment_object.get("test", False)
        payment_id = payment_object.get("id")
        
        logger.info(
            f"[YOOKASSA_WEBHOOK] event={event_type}, payment_id={payment_id}, "
            f"test={is_test_payment}, paid={payment_object.get('paid')}"
        )
        
        # Проверяем соответствие режимов
        db_test_mode = get_setting("yookassa_test_mode") == "true"
        if is_test_payment != db_test_mode:
            logger.warning(
                f"[YOOKASSA_WEBHOOK] Mode mismatch! webhook test={is_test_payment}, "
                f"db test_mode={db_test_mode}, payment_id={payment_id}"
            )
        
        # ... остальная обработка ...
```

---

## 5. Безопасность

### 5.1 ✅ HTTPS для webhook endpoint

**Статус:** ✅ **ПРЕДПОЛАГАЕТСЯ**  
Webhook URL: `/yookassa-webhook`  
Предполагается использование HTTPS через reverse proxy (nginx).

**Рекомендация:** Проверить, что в production используется HTTPS.

---

### 5.2 ⚠️ Проверка IP адресов YooKassa

**Статус:** ❌ **НЕ РЕАЛИЗОВАНО**

**Проблема:**
- Webhook endpoint не проверяет, что запрос пришел от YooKassa
- Любой может отправить POST на `/yookassa-webhook`
- Возможна подделка webhook уведомлений

**Рекомендация (опционально):**
```python
YOOKASSA_IP_RANGES = [
    "185.71.76.0/27",
    "185.71.77.0/27",
    "77.75.153.0/25",
    "77.75.156.11",
    "77.75.156.35",
    "77.75.154.128/25",
    "2a02:5180::/32"
]

def is_yookassa_ip(ip: str) -> bool:
    import ipaddress
    client_ip = ipaddress.ip_address(ip)
    for ip_range in YOOKASSA_IP_RANGES:
        if client_ip in ipaddress.ip_network(ip_range):
            return True
    return False

@flask_app.route('/yookassa-webhook', methods=['POST'])
def yookassa_webhook_handler():
    client_ip = request.remote_addr
    if not is_yookassa_ip(client_ip):
        logger.warning(f"YooKassa webhook from unauthorized IP: {client_ip}")
        return 'Forbidden', 403
    # ...
```

---

### 5.3 ⚠️ Защита от replay attacks

**Статус:** ⚠️ **ЧАСТИЧНАЯ**

**Текущая защита:**
- Используется БД для хранения транзакций с `payment_id` как PRIMARY KEY
- Повторная обработка того же `payment_id` перезапишет запись

**Проблема:**
- Логика создания ключа выполнится дважды (см. 3.6)

**Рекомендация:** См. раздел 3.6

---

### 5.4 ✅ Валидация входящих данных

**Файл:** `app.py`, `handlers.py`

**Статус:** ✅ **ХОРОШО**

Используются функции:
- `_to_int(val, default=0)` (handlers.py:6257)
- `_to_float(val, default=0.0)` (handlers.py:6268)
- Проверка `payment_object.get("paid") is True`

---

## 📊 Итоговая таблица проблем

| # | Проблема | Критичность | Файл | Строка |
|---|----------|-------------|------|--------|
| 1 | Fallback к production URL в test mode | ❌ КРИТИЧЕСКАЯ | `bot_controller.py` | 128 |
| 2 | Fallback к production credentials в test mode | ❌ КРИТИЧЕСКАЯ | `bot_controller.py` | 126-127 |
| 3 | Configuration не обновляется при смене режима в UI | ❌ КРИТИЧЕСКАЯ | `bot_controller.py` | 156 |
| 4 | Отсутствует проверка поля `test` в webhook | ❌ КРИТИЧЕСКАЯ | `app.py` | 2423 |
| 5 | Нет защиты от дублирования обработки webhook | ⚠️ ВЫСОКАЯ | `app.py` | 2423 |
| 6 | Неполное логирование режима при создании платежа | ⚠️ СРЕДНЯЯ | `handlers.py` | 4086 |
| 7 | Нет индикатора активного режима в UI | ⚠️ СРЕДНЯЯ | `settings.html` | - |
| 8 | Отсутствует проверка IP адресов YooKassa | ⚠️ НИЗКАЯ | `app.py` | 2421 |

---

## ✅ Что работает хорошо

1. ✅ Использование `Configuration.configure()` с правильными параметрами
2. ✅ Idempotency key в каждом запросе (`uuid.uuid4()`)
3. ✅ Параметр `"test": yookassa_test_mode` передается в payload
4. ✅ Обработка всех типов событий webhook (`payment.succeeded`, `payment.waiting_for_capture`, `payment.canceled`)
5. ✅ Проверка `paid=true` перед обработкой
6. ✅ Извлечение и сохранение `authorization_details` (RRN, auth_code)
7. ✅ Извлечение `payment_type` (bank_card, sbp, и т.д.)
8. ✅ Логирование событий webhook
9. ✅ Функция `_reconfigure_yookassa()` вызывается перед созданием платежа
10. ✅ Валидация входящих данных

---

## 🔧 Рекомендации по приоритетам

### Критические (необходимо исправить немедленно)

1. **Убрать fallback к production credentials в test mode** (bot_controller.py, handlers.py)
2. **Исправить fallback к production URL в test mode** (bot_controller.py)
3. **Добавить проверку поля `test` в webhook** (app.py)
4. **Добавить защиту от дублирования обработки webhook** (app.py)

### Высокие (желательно исправить в ближайшее время)

5. **Улучшить логирование режима при создании платежа** (handlers.py)
6. **Добавить индикатор активного режима в UI** (settings.html, app.py)
7. **Добавить предупреждение о необходимости рестарта** (settings.html)

### Средние (можно отложить)

8. **Добавить проверку IP адресов YooKassa** (app.py) - опционально
9. **Добавить документацию по работе с режимами** (docs/)

---

## 📝 Следующие шаги

1. ✅ **Этап 1 завершен:** Анализ выполнен
2. ⏭️ **Этап 2:** Реализация исправлений согласно плану
3. ⏭️ **Этап 3:** Docker Management UI
4. ⏭️ **Этап 4:** Тестирование и документация

---

## 📚 Ссылки

- [YooKassa API Documentation](https://yookassa.ru/developers/api)
- [YooKassa Best Practices](https://yookassa.ru/developers/using-api/webhooks)
- [План исправлений](../../.cursor/plans/yookassa-integration-fixes-54c2ae1c.plan.md)

---

**Анализ выполнил:** AI Assistant  
**Дата:** 08.11.2025  
**Версия документа:** 1.0

