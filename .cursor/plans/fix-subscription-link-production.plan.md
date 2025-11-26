# План исправления проблемы subscription_link на боевом сервере

## 🎯 ПРОБЛЕМА НАЙДЕНА 100%

**Локация:** `src/shop_bot/bot/handlers.py`, строка 7059

**Суть проблемы:**

При создании нового ключа через YooKassa webhook функция `create_key_with_stats_atomic` вызывается **БЕЗ** параметра `subscription_link`, хотя:

1. `subscription_link` **генерируется** в `xui_api.create_or_update_key_on_host()` (строка 733-740)
2. `subscription_link` **возвращается** в `result` (строка 966)
3. Функция `create_key_with_stats_atomic` **принимает** параметр `subscription_link` (строка 6515)
4. Функция `create_key_with_stats_atomic` **сохраняет** `subscription_link` в БД (строка 6563)

**Но:** В вызове на строке 7059 параметр `subscription_link` **НЕ ПЕРЕДАЕТСЯ**!

## 📊 Доказательства из логов боевого сервера

```
2025-11-26 10:42:59,321 - [INFO] - shop_bot.modules.xui_api - Created subscription link: https://serv2.dark-maximus.com/subs/6044240344-k4rum_fwd
```

Ссылка **была создана**, но не сохранилась в БД, потому что не передана в `create_key_with_stats_atomic`.

## 🔧 РЕШЕНИЕ 100%

### Шаг 1: Исправить вызов create_key_with_stats_atomic

**Файл:** `src/shop_bot/bot/handlers.py`

**Строка:** 7059

**Текущий код:**

```python
key_id = create_key_with_stats_atomic(
    user_id=user_id,
    host_name=host_name,
    xui_client_uuid=result['client_uuid'],
    key_email=result['email'],
    expiry_timestamp_ms=result['expiry_timestamp_ms'],
    amount_spent=price,
    months_purchased=months,
    payment_id=payment_id,
    promo_usage_id=promo_usage_id,
    plan_id=plan_id,
    connection_string=result.get('connection_string') or "",
    plan_name=plan.get('plan_name') if plan else None,
    price=price,
    subscription=subscription,
    telegram_chat_id=telegram_chat_id,
    comment=f"Ключ для пользователя {fullname or username or user_id}"
)
```

**Исправленный код:**

```python
key_id = create_key_with_stats_atomic(
    user_id=user_id,
    host_name=host_name,
    xui_client_uuid=result['client_uuid'],
    key_email=result['email'],
    expiry_timestamp_ms=result['expiry_timestamp_ms'],
    amount_spent=price,
    months_purchased=months,
    payment_id=payment_id,
    promo_usage_id=promo_usage_id,
    plan_id=plan_id,
    connection_string=result.get('connection_string') or "",
    plan_name=plan.get('plan_name') if plan else None,
    price=price,
    subscription=subscription,
    subscription_link=result.get('subscription_link'),  # ← ДОБАВИТЬ ЭТУ СТРОКУ
    telegram_chat_id=telegram_chat_id,
    comment=f"Ключ для пользователя {fullname or username or user_id}"
)
```

### Шаг 2: Проверить другие вызовы create_key_with_stats_atomic

Найти все вызовы `create_key_with_stats_atomic` в проекте и убедиться, что везде передается `subscription_link`.

### Шаг 3: Проверить вызовы add_new_key

Найти все вызовы `add_new_key` и убедиться, что везде передается `subscription_link` из `result.get('subscription_link')`.

### Шаг 4: Обновить версию и CHANGELOG

- Обновить версию в `pyproject.toml` с 4.32.0 до 4.33.0 (минорный bump, т.к. это критичный фикс)
- Добавить запись в `CHANGELOG.md`

### Шаг 5: Создать миграцию для восстановления subscription_link

Создать скрипт для восстановления `subscription_link` для существующих ключей, у которых он `NULL`, но есть `subscription` (sub_id).

## ✅ Результат

После исправления:

1. Все новые ключи будут создаваться с `subscription_link` в БД
2. Личный кабинет будет отображать ссылку на подписку
3. Веб-панель будет отображать ссылку на подписку
4. Fallback логика (из предыдущих исправлений) будет работать для старых ключей

## 🚀 Тестирование

1. Создать тестовый платеж через YooKassa
2. Проверить, что `subscription_link` сохранился в БД
3. Проверить отображение в личном кабинете
4. Проверить отображение в веб-панели

## 📝 Примечания

- Это **критичный фикс** - без него все новые ключи создаются без `subscription_link`
- Проблема затрагивает **только создание новых ключей** через YooKassa webhook
- Продление существующих ключей может иметь ту же проблему - нужно проверить