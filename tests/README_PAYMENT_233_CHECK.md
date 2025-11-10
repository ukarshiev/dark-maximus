# Проверка исправлений для платежа ID 233

## Что было исправлено

1. **Использование metadata из БД**: Webhook теперь использует metadata из транзакции в БД как основу, что гарантирует наличие `host_code`
2. **Приоритет host_code**: Поиск хоста сначала по `host_code`, потом по `host_name`
3. **Fallback через план**: Если хост не найден, система пытается найти его через `plan_id`

## Как проверить на боевом сервере

### Вариант 1: Проверка через SSH

```bash
# Подключиться к серверу
ssh root@31.56.27.129

# Перейти в директорию проекта
cd /app/project  # или где находится проект

# Запустить проверку транзакции
python3 tests/test_payment_233_on_server.py

# Проверить логи
bash tests/check_webhook_logs.sh
```

### Вариант 2: Проверка логов вручную

```bash
ssh root@31.56.27.129

# Проверить транзакцию в БД
sqlite3 /app/project/users.db "SELECT * FROM transactions WHERE payment_id = '30a48370-000f-5001-9000-16231fa0ad0c';"

# Проверить логи webhook
tail -200 /app/project/logs/application.log | grep "30a48370-000f-5001-9000-16231fa0ad0c"

# Проверить использование metadata из БД
tail -200 /app/project/logs/application.log | grep "Using metadata from DB transaction"

# Проверить поиск хоста
tail -200 /app/project/logs/application.log | grep "Host found by host_code"
```

### Вариант 3: Симуляция webhook для проверки

```bash
ssh root@31.56.27.129
cd /app/project
python3 tests/simulate_yookassa_webhook.py 30a48370-000f-5001-9000-16231fa0ad0c
```

## Что должно быть в логах после исправлений

1. **При получении webhook**:
   ```
   [YOOKASSA_WEBHOOK] Transaction found in DB: id=..., status=pending
   [YOOKASSA_WEBHOOK] Using metadata from DB transaction for payment_id=30a48370-000f-5001-9000-16231fa0ad0c
   ```

2. **При поиске хоста**:
   ```
   [YOOKASSA_WEBHOOK] Host found by host_code: finland1 -> 🇫🇮 Финляндия 1
   ```

3. **При обработке платежа**:
   ```
   [YOOKASSA_WEBHOOK] Processing payment.succeeded: metadata_source=database+webhook, host_code=finland1, ...
   [YOOKASSA_WEBHOOK] Payment processing completed successfully
   ```

## Если платеж все еще в pending

1. Проверьте, что код обновлен на сервере
2. Проверьте, что бот перезапущен после обновления
3. Проверьте логи на наличие ошибок
4. Если нужно, обработайте платеж вручную через `tests/test_manual_yookassa_fix_payment.py`

