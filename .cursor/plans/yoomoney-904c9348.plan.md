<!-- 904c9348-46bd-4bdb-b034-589a7de51736 542e5381-931b-4cf1-b133-d353b4eba35b -->
# Исправление YooKassa webhook и host_code

## Критические проблемы

### 1. Webhook падает с ошибкой Flask async

**Ошибка**: `RuntimeError: Install Flask with the 'async' extra in order to use async views.`

**Причина**: Декоратор `@measure_performance` в `src/shop_bot/utils/performance_monitor.py` (строка 362) делает функцию async (`async def wrapper`), но Flask endpoint `yookassa_webhook_handler` синхронный. Flask 3.1.1 требует `flask[async]` для async views.

**Решение**: Создать синхронную версию декоратора `measure_performance` для Flask endpoints.

### 2. host_code содержит эмодзи

**Проблема**: В metadata передается `"host_code": "🇳🇱nederland1"` вместо `"nederland1"`.

**Причина**: Функция `_resolve_host_code` в `src/shop_bot/bot/handlers.py` (строка 97) в fallback не удаляет эмодзи из host_name перед созданием host_code.

**Последствия**:

- `get_host_by_code("🇳🇱nederland1")` не найдет хост в БД (там код без эмодзи)
- `_ensure_host_metadata` не сможет найти хост по host_code
- Платеж не обработается, ключ не создастся

### 3. Потенциальная проблема с поиском хоста

**Проблема**: Если host_code содержит эмодзи, `_ensure_host_metadata` не найдет хост даже через fallback по plan_id, если metadata уже содержит неправильный host_code.

## Решения

### 1. Исправление Flask async проблемы

**Файл**: `src/shop_bot/utils/performance_monitor.py`

Добавить синхронную версию декоратора для Flask endpoints после функции `measure_performance`:

```python
def measure_performance_sync(operation_name: str):
    """Синхронная версия декоратора для Flask endpoints"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            success = True
            error = None
            try:
                result = func(*args, **kwargs)
                return result
            except Exception as e:
                success = False
                error = str(e)
                raise
            finally:
                duration = time.time() - start_time
                # Записываем метрику асинхронно через event loop если доступен
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        monitor = get_performance_monitor()
                        asyncio.run_coroutine_threadsafe(
                            monitor.record_metric(
                                operation=operation_name,
                                duration=duration,
                                user_id=None,
                                success=success,
                                error=error
                            ),
                            loop
                        )
                except Exception:
                    pass  # Игнорируем ошибки мониторинга
        return wrapper
    return decorator
```

**Файл**: `src/shop_bot/webhook_server/app.py`

- Импортировать `measure_performance_sync` вместо `measure_performance`
- Заменить `@measure_performance("yookassa_webhook")` на `@measure_performance_sync("yookassa_webhook")` на строке 2635

### 2. Исправление host_code с эмодзи

**Файл**: `src/shop_bot/bot/handlers.py` (строка 87-97)

Исправить функцию `_resolve_host_code`:

```python
def _resolve_host_code(host_name: str | None) -> str:
    """Возвращает стабильный host_code без эмодзи"""
    if not host_name:
        return ""
    try:
        host_record = get_host(host_name)
        if host_record and host_record.get('host_code'):
            return str(host_record['host_code'])
    except Exception:
        pass
    # ИСПРАВЛЕНИЕ: Удаляем эмодзи и специальные символы из fallback
    import re
    # Удаляем все эмодзи (Unicode ranges для эмодзи) и оставляем только буквы, цифры, пробелы, дефисы
    cleaned = re.sub(r'[\U0001F300-\U0001F9FF\U00002600-\U000027BF\U0001F600-\U0001F64F\U0001F680-\U0001F6FF]', '', str(host_name))
    # Удаляем все остальные не-буквенно-цифровые символы кроме пробелов и дефисов
    cleaned = re.sub(r'[^\w\s-]', '', cleaned)
    return cleaned.replace(' ', '').lower()
```

### 3. Дополнительная защита в _ensure_host_metadata

**Файл**: `src/shop_bot/webhook_server/app.py` (строка 131-142)

Добавить очистку host_code от эмодзи перед поиском:

```python
# ИСПРАВЛЕНИЕ: Изменен приоритет - сначала ищем по host_code (более надежно)
if host_code:
    # Очищаем host_code от эмодзи перед поиском
    import re
    cleaned_host_code = re.sub(r'[\U0001F300-\U0001F9FF\U00002600-\U000027BF\U0001F600-\U0001F64F\U0001F680-\U0001F6FF]', '', str(host_code))
    cleaned_host_code = re.sub(r'[^\w\s-]', '', cleaned_host_code).replace(' ', '').lower()
    
    try:
        host_record = get_host_by_code(cleaned_host_code)
        if host_record:
            search_attempts.append(f"host_code={cleaned_host_code} (found)")
            metadata["host_name"] = host_record.get("host_name")
            metadata["host_code"] = host_record.get("host_code")  # Обновляем на правильный код
            logger.info(
                f"[YOOKASSA_WEBHOOK] Host found by host_code: {cleaned_host_code} -> {host_record.get('host_name')}"
            )
    except Exception as e:
        search_attempts.append(f"host_code={cleaned_host_code} (error: {e})")
        logger.warning(f"[YOOKASSA_WEBHOOK] Error searching by host_code {cleaned_host_code}: {e}")
```

### 4. Исправление существующей транзакции 234

После исправления кода проверить транзакцию 234 в БД и при необходимости обновить metadata с правильным host_code или обработать платеж вручную.

## Тестирование

1. Проверить что webhook endpoint доступен через GET запрос
2. Создать тестовый платеж и проверить что webhook обрабатывается без ошибок Flask async
3. Проверить что host_code в metadata не содержит эмодзи при создании платежа
4. Проверить что `_ensure_host_metadata` находит хост даже если host_code содержит эмодзи
5. Проверить что ключ создается после успешного платежа

## Файлы для изменения

- `src/shop_bot/utils/performance_monitor.py` - добавить `measure_performance_sync`
- `src/shop_bot/webhook_server/app.py` - заменить декоратор и добавить очистку host_code в `_ensure_host_metadata`
- `src/shop_bot/bot/handlers.py` - исправить `_resolve_host_code`