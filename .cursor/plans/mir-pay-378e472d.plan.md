<!-- 378e472d-2c8e-4c90-a5a7-9379c120295b 0245cf7c-f151-40f7-af76-afb86fa43f02 -->
# Исправление ошибки 2005000007 при оплате через Mir Pay на мобильных устройствах

## Проблема

При оплате через Mir Pay на мобильных устройствах возникает ошибка 2005000007 "Извините, произошла внутренняя ошибка". Ошибка возникает всегда (100% попыток), при этом другие способы оплаты (банковская карта, СБП, SberPay) работают нормально.

## Анализ

1. **Текущая реализация**: В коде используется `return_url: f"https://t.me/{TELEGRAM_BOT_USERNAME}"` для всех платежей YooKassa
2. **Проблема**: Telegram deep link может не работать корректно для Mir Pay на мобильных устройствах, что вызывает ошибку 2005000007
3. **Решение**: Использовать универсальный return_url на домене проекта с редиректом на бота

## План исправления

### 1. Создание эндпоинта для редиректа после оплаты

**Файл**: `src/shop_bot/webhook_server/app.py`

Создать новый эндпоинт `/yookassa-return` который:

- Принимает параметры от YooKassa после оплаты
- Редиректит пользователя на Telegram бота через deep link
- Логирует информацию о редиректе для диагностики

### 2. Создание безопасной функции для получения return_url

**Файл**: `src/shop_bot/bot/handlers.py`

Создать функцию `get_yookassa_return_url()` с безопасным fallback механизмом:

```python
def get_yookassa_return_url() -> str:
    """
    Получить return_url для YooKassa с безопасным fallback на Telegram deep link.
    
    Согласно документации YooKassa, для мобильных платежей рекомендуется использовать
    валидный HTTP(S) URL вместо deep links. Если домен не настроен, используется
    fallback на Telegram deep link для обратной совместимости.
    
    Returns:
        str: URL для редиректа после оплаты
    """
    from shop_bot.data_manager.database import get_global_domain
    
    global_domain = get_global_domain()
    
    if global_domain:
        # Убираем trailing slash если есть
        domain = global_domain.rstrip('/')
        return_url = f"{domain}/yookassa-return"
        logger.info(
            f"[YOOKASSA_RETURN_URL] Using domain-based return_url: {return_url} "
            f"(domain: {domain})"
        )
        return return_url
    else:
        # Fallback на Telegram deep link если домен не настроен
        # Это сохраняет обратную совместимость и не ломает существующий функционал
        fallback_url = f"https://t.me/{TELEGRAM_BOT_USERNAME}"
        logger.warning(
            f"[YOOKASSA_RETURN_URL] global_domain not configured, "
            f"using fallback Telegram deep link: {fallback_url}. "
            f"Рекомендуется настроить global_domain в настройках панели для лучшей "
            f"совместимости с мобильными платежами (особенно Mir Pay)."
        )
        return fallback_url
```

### 3. Изменение return_url в создании платежа

**Файл**: `src/shop_bot/bot/handlers.py`

Изменить `return_url` в функциях:

- `create_yookassa_payment_handler()` (строка ~5042)
- `topup_pay_yookassa()` (строка ~4376)

**Было**:

```python
"return_url": f"https://t.me/{TELEGRAM_BOT_USERNAME}"
```

**Станет**:

```python
"return_url": get_yookassa_return_url()
```

**Важно**: Функция автоматически использует fallback на Telegram deep link, если домен не настроен, что гарантирует обратную совместимость.

### 4. Добавление логирования

Добавить логирование:

- Информация о создании платежа с return_url
- Информация о редиректе после оплаты
- Параметры, полученные от YooKassa

### 5. Обновление документации

**Файл**: `docs/integrations/yookassa.md`

Добавить информацию о:

- Настройке return_url для мобильных платежей
- Решении проблемы с Mir Pay
- Требованиях к домену проекта

## Файлы для изменения

1. `src/shop_bot/webhook_server/app.py` - добавление эндпоинта `/yookassa-return`
2. `src/shop_bot/bot/handlers.py` - изменение return_url в создании платежей
3. `docs/integrations/yookassa.md` - обновление документации

## Тестирование

1. Проверить создание платежа с новым return_url
2. Проверить редирект после оплаты через Mir Pay на мобильном устройстве
3. Проверить работу других способов оплаты (не должны сломаться)
4. Проверить логи для диагностики

## Риски

- Если домен проекта не настроен, потребуется fallback на Telegram deep link
- Необходимо убедиться, что домен доступен с мобильных устройств
- Редирект должен работать быстро, чтобы не терять пользователей