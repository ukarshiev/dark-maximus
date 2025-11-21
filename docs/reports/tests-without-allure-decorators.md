# Список тестов без декораторов Allure

**Дата создания:** 17.11.2025  
**Источник:** Allure отчет `http://localhost:50005/allure-docker-service/projects/default/reports/6/index.html#behaviors`

## Общая информация

Найдено **2 файла** с тестами без декораторов `@allure.epic` и `@allure.feature`:

- `tests/integration/test_timezone_integration.py` - 8 тестов
- `tests/unit/test_utils/test_timezone_utils.py` - 17 тестов

**Всего: 25 тестов**

### Причина отсутствия декораторов

Эти файлы используют `unittest.TestCase` вместо pytest, поэтому декораторы Allure не применяются. Согласно правилам из `testing-rules.mdc`, для `unittest.TestCase` декораторы не требуются, так как они используют другой подход к тестированию.

---

## 1. tests/integration/test_timezone_integration.py

### Тест 1: test_new_key_expiry_date_is_utc_naive

**Класс:** `TestKeyCreationStoresUTC`  
**Расположение:** строки 140-196

```python
def test_new_key_expiry_date_is_utc_naive(self):
    """
    Тест 1: Создание нового ключа сохраняет expiry_date в UTC без tzinfo
    """
    print("\n[TEST] Создание ключа -> проверка UTC в БД")
    
    # 1. Создаем тестового пользователя с ключом
    user_id = 12345
    username = "test_user"
    
    # Симулируем timestamp из API (срок через 30 дней)
    now_utc = datetime.now(UTC)
    future_utc = now_utc + timedelta(days=30)
    expiry_timestamp_ms = int(future_utc.timestamp() * 1000)
    
    # 2. Конвертируем timestamp в naive UTC (как это делает наш код)
    expiry_date = timestamp_to_utc_datetime(expiry_timestamp_ms)
    
    # 3. Сохраняем в БД
    from shop_bot.data_manager import database
    conn = sqlite3.connect(str(database.DB_FILE))
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO users (user_id, username, key, expiry_date, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        user_id,
        username,
        "test-key-12345",
        expiry_date.isoformat(),
        now_utc.isoformat(),
        now_utc.isoformat()
    ))
    conn.commit()
    conn.close()
    
    # 4. Читаем из БД и проверяем
    user = self._get_user_from_db(user_id)
    self.assertIsNotNone(user, "Пользователь должен быть создан")
    
    # Парсим expiry_date из БД
    expiry_str = user[3]  # expiry_date
    expiry_from_db = datetime.fromisoformat(expiry_str)
    
    # Проверяем, что дата naive (без tzinfo)
    self.assertIsNone(
        expiry_from_db.tzinfo,
        "expiry_date в БД должен быть naive (без tzinfo)"
    )
    
    # Проверяем, что дата правильная (±1 секунда)
    diff = abs((expiry_from_db - expiry_date).total_seconds())
    self.assertLess(diff, 1, "Дата должна совпадать с ожидаемой")
    
    print(f"[+] Дата сохранена в UTC (naive): {expiry_from_db.isoformat()}")
```

### Тест 2: test_notification_sent_at_correct_time

**Класс:** `TestNotificationTiming`  
**Расположение:** строки 202-259

```python
def test_notification_sent_at_correct_time(self):
    """
    Тест 2: Уведомление за 1 час должно прийти ровно за 1 час
    """
    print("\n[TEST] Уведомление -> проверка правильного времени")
    
    # 1. Создаем ключ с истечением через 1 час
    user_id = 12346
    now_utc = get_current_utc_naive()
    expiry_date = now_utc + timedelta(hours=1)
    
    from shop_bot.data_manager import database
    conn = sqlite3.connect(str(database.DB_FILE))
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO users (user_id, username, key, expiry_date, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        user_id,
        "test_user_notify",
        "test-key-notify",
        expiry_date.isoformat(),
        now_utc.isoformat(),
        now_utc.isoformat()
    ))
    conn.commit()
    conn.close()
    
    # 2. Вычисляем оставшееся время
    expiry_timestamp_ms = int(expiry_date.replace(tzinfo=UTC).timestamp() * 1000)
    remaining_seconds = calculate_remaining_seconds(expiry_timestamp_ms)
    
    # 3. Проверяем, что remaining_seconds примерно 3600 (1 час)
    expected_seconds = 3600
    diff = abs(remaining_seconds - expected_seconds)
    
    self.assertLess(
        diff,
        10,
        f"Оставшееся время должно быть ~3600 сек, получено: {remaining_seconds}"
    )
    
    print(f"[+] Оставшееся время: {remaining_seconds} сек (ожидалось: ~3600 сек)")
    
    # 4. Проверяем, что уведомление должно прийти примерно через 1 час
    notification_time = now_utc + timedelta(seconds=remaining_seconds) - timedelta(hours=1)
    time_diff = abs((notification_time - now_utc).total_seconds())
    
    self.assertLess(
        time_diff,
        10,
        "Уведомление должно отправиться примерно сейчас (за 1 час до истечения)"
    )
    
    print(f"[+] Уведомление будет отправлено в правильное время")
```

### Тест 3: test_timezone_change_updates_display

**Класс:** `TestTimezoneDisplay`  
**Расположение:** строки 265-315

```python
def test_timezone_change_updates_display(self):
    """
    Тест 3: Смена timezone корректно изменяет отображаемое время
    """
    print("\n[TEST] Смена timezone -> проверка отображения")
    
    # 1. Создаем тестовую дату в UTC
    dt_utc = datetime(2025, 1, 1, 12, 0, 0)  # 12:00 UTC
    
    # 2. Включаем feature flag
    self._set_feature_flag(True)
    
    # 3. Проверяем отображение для Moscow (UTC+3)
    moscow_display = format_datetime_for_user(
        dt_utc,
        user_timezone="Europe/Moscow",
        feature_enabled=True
    )
    
    self.assertIn("01.01.2025", moscow_display)
    self.assertIn("15:00", moscow_display, "12:00 UTC = 15:00 MSK")
    self.assertIn("UTC", moscow_display)
    print(f"[+] Moscow: {moscow_display}")
    
    # 4. Проверяем отображение для Yekaterinburg (UTC+5)
    yekaterinburg_display = format_datetime_for_user(
        dt_utc,
        user_timezone="Asia/Yekaterinburg",
        feature_enabled=True
    )
    
    self.assertIn("01.01.2025", yekaterinburg_display)
    self.assertNotIn("12:00", yekaterinburg_display, "Время должно быть конвертировано")
    self.assertIn("UTC", yekaterinburg_display)
    print(f"[+] Yekaterinburg: {yekaterinburg_display}")
    
    # 5. Проверяем отображение для UTC
    utc_display = format_datetime_for_user(
        dt_utc,
        user_timezone="UTC",
        feature_enabled=True
    )
    
    self.assertIn("01.01.2025", utc_display)
    self.assertIn("2025", utc_display, "Дата должна быть правильной")
    self.assertIn("UTC", utc_display)
    print(f"[+] UTC: {utc_display}")
```

### Тест 4: test_feature_flag_disabled_uses_moscow

**Класс:** `TestTimezoneDisplay`  
**Расположение:** строки 317-335

```python
def test_feature_flag_disabled_uses_moscow(self):
    """
    Тест 4: При выключенном feature flag используется Moscow
    """
    print("\n[TEST] Feature flag выключен -> используется Moscow")
    
    dt_utc = datetime(2025, 1, 1, 12, 0, 0)
    
    # Feature flag выключен
    result = format_datetime_for_user(
        dt_utc,
        user_timezone="Asia/Tokyo",  # Указываем Tokyo
        feature_enabled=False  # Но flag выключен
    )
    
    # Должно использоваться Moscow, а не Tokyo
    self.assertIn("15:00", result, "При выключенном flag должно быть Moscow время")
    self.assertIn("UTC+3", result)
    print(f"[+] Используется Moscow: {result}")
```

### Тест 5: test_auto_renewal_triggers_at_correct_time

**Класс:** `TestAutoRenewalTiming`  
**Расположение:** строки 341-392

```python
def test_auto_renewal_triggers_at_correct_time(self):
    """
    Тест 5: Автопродление срабатывает в правильное время
    """
    print("\n[TEST] Автопродление -> проверка времени срабатывания")
    
    # 1. Создаем пользователя с балансом и включенным автопродлением
    user_id = 12347
    now_utc = get_current_utc_naive()
    expiry_date = now_utc + timedelta(hours=2)  # Истекает через 2 часа
    
    from shop_bot.data_manager import database
    conn = sqlite3.connect(str(database.DB_FILE))
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO users (user_id, username, key, expiry_date, balance, auto_renewal, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        user_id,
        "test_user_renewal",
        "test-key-renewal",
        expiry_date.isoformat(),
        100.0,  # Достаточно баланса
        1,  # Автопродление включено
        now_utc.isoformat(),
        now_utc.isoformat()
    ))
    conn.commit()
    conn.close()
    
    # 2. Вычисляем, когда должно сработать автопродление (за 1 час)
    expiry_timestamp_ms = int(expiry_date.replace(tzinfo=UTC).timestamp() * 1000)
    remaining_seconds = calculate_remaining_seconds(expiry_timestamp_ms)
    
    # Автопродление должно сработать за 1 час (3600 секунд) до истечения
    auto_renewal_delay = remaining_seconds - 3600
    
    # Проверяем, что это примерно через 1 час от текущего момента
    self.assertGreater(auto_renewal_delay, 3500, "Автопродление через ~1 час")
    self.assertLess(auto_renewal_delay, 3700, "Автопродление через ~1 час")
    
    print(f"[+] Автопродление сработает через: {auto_renewal_delay} сек (~1 час)")
    
    # 3. Проверяем, что время истечения в UTC
    user = self._get_user_from_db(user_id)
    expiry_str = user[3]
    expiry_from_db = datetime.fromisoformat(expiry_str)
    
    self.assertIsNone(expiry_from_db.tzinfo, "expiry_date должен быть в UTC (naive)")
    print(f"[+] expiry_date в UTC: {expiry_from_db.isoformat()}")
```

### Тест 6: test_existing_keys_work_correctly

**Класс:** `TestBackwardCompatibility`  
**Расположение:** строки 398-447

```python
def test_existing_keys_work_correctly(self):
    """
    Тест 6: Существующие ключи (без timezone) работают корректно
    """
    print("\n[TEST] Обратная совместимость -> старые ключи")
    
    # 1. Создаем "старый" ключ (до внедрения timezone)
    user_id = 12348
    now_utc = get_current_utc_naive()
    expiry_date = now_utc + timedelta(days=30)
    
    from shop_bot.data_manager import database
    conn = sqlite3.connect(str(database.DB_FILE))
    cursor = conn.cursor()
    
    # Вставляем БЕЗ timezone (старый формат)
    cursor.execute("""
        INSERT INTO users (user_id, username, key, expiry_date, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        user_id,
        "old_user",
        "old-key-12348",
        expiry_date.isoformat(),
        now_utc.isoformat(),
        now_utc.isoformat()
    ))
    conn.commit()
    conn.close()
    
    # 2. Читаем и проверяем, что дата читается корректно
    user = self._get_user_from_db(user_id)
    expiry_str = user[3]
    expiry_from_db = datetime.fromisoformat(expiry_str)
    
    # 3. Проверяем, что старый формат работает
    self.assertIsNone(expiry_from_db.tzinfo, "Старый формат без tzinfo")
    
    # 4. Проверяем, что форматирование работает (должен использоваться Moscow по умолчанию)
    formatted = format_datetime_for_user(
        expiry_from_db,
        user_timezone=None,  # Не указан timezone
        feature_enabled=True
    )
    
    self.assertIsNotNone(formatted, "Форматирование должно работать")
    self.assertIn("UTC", formatted)
    print(f"[+] Старый ключ работает: {formatted}")
```

### Тест 7: test_expired_key_returns_zero_remaining

**Класс:** `TestEdgeCases`  
**Расположение:** строки 453-467

```python
def test_expired_key_returns_zero_remaining(self):
    """
    Тест 7: Истекший ключ возвращает 0 оставшихся секунд
    """
    print("\n[TEST] Граничный случай -> истекший ключ")
    
    # Создаем ключ, который истек час назад
    now_utc = get_current_utc_naive()
    expired_date = now_utc - timedelta(hours=1)
    
    expiry_timestamp_ms = int(expired_date.replace(tzinfo=UTC).timestamp() * 1000)
    remaining_seconds = calculate_remaining_seconds(expiry_timestamp_ms)
    
    self.assertEqual(remaining_seconds, 0, "Для истекшего ключа должно быть 0 секунд")
    print(f"[+] Истекший ключ: {remaining_seconds} сек")
```

### Тест 8: test_invalid_timezone_fallback_to_moscow

**Класс:** `TestEdgeCases`  
**Расположение:** строки 469-487

```python
def test_invalid_timezone_fallback_to_moscow(self):
    """
    Тест 8: Невалидный timezone падает обратно на Moscow
    """
    print("\n[TEST] Граничный случай -> невалидный timezone")
    
    dt_utc = datetime(2025, 1, 1, 12, 0, 0)
    
    # Указываем несуществующий timezone
    result = format_datetime_for_user(
        dt_utc,
        user_timezone="Invalid/Timezone",
        feature_enabled=True
    )
    
    # Должен использоваться fallback на Moscow (15:00)
    self.assertIn("15:00", result, "Должен быть fallback на Moscow")
    self.assertIn("UTC+3", result)
    print(f"[+] Fallback на Moscow: {result}")
```

---

## 2. tests/unit/test_utils/test_timezone_utils.py

### Тест 9: test_utc_aware_datetime

**Класс:** `TestEnsureUtcDatetime`  
**Расположение:** строки 34-43

```python
def test_utc_aware_datetime(self):
    """Тест: UTC aware datetime -> naive UTC"""
    dt_utc = datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC)
    result = ensure_utc_datetime(dt_utc)
    
    self.assertIsNone(result.tzinfo, "Результат должен быть naive")
    self.assertEqual(result.year, 2025)
    self.assertEqual(result.month, 1)
    self.assertEqual(result.day, 1)
    self.assertEqual(result.hour, 12)
```

### Тест 10: test_moscow_aware_datetime

**Класс:** `TestEnsureUtcDatetime`  
**Расположение:** строки 45-52

```python
def test_moscow_aware_datetime(self):
    """Тест: Moscow aware datetime -> naive UTC (должен конвертировать)"""
    moscow_tz = timezone(timedelta(hours=3))
    dt_moscow = datetime(2025, 1, 1, 15, 0, 0, tzinfo=moscow_tz)
    result = ensure_utc_datetime(dt_moscow)
    
    self.assertIsNone(result.tzinfo, "Результат должен быть naive")
    self.assertEqual(result.hour, 12, "15:00 MSK должно стать 12:00 UTC")
```

### Тест 11: test_naive_datetime_warning

**Класс:** `TestEnsureUtcDatetime`  
**Расположение:** строки 54-60

```python
def test_naive_datetime_warning(self):
    """Тест: naive datetime предполагается как UTC (с предупреждением)"""
    dt_naive = datetime(2025, 1, 1, 12, 0, 0)
    result = ensure_utc_datetime(dt_naive)
    
    self.assertIsNone(result.tzinfo, "Результат должен быть naive")
    self.assertEqual(result.hour, 12, "Naive считается UTC, не должно измениться")
```

### Тест 12: test_timestamp_conversion

**Класс:** `TestTimestampToUtcDatetime`  
**Расположение:** строки 66-76

```python
def test_timestamp_conversion(self):
    """Тест: timestamp -> naive UTC datetime"""
    # 2025-01-01 12:00:00 UTC = 1735732800000 ms
    timestamp_ms = 1735732800000
    result = timestamp_to_utc_datetime(timestamp_ms)
    
    self.assertIsNone(result.tzinfo, "Результат должен быть naive")
    self.assertEqual(result.year, 2025)
    self.assertEqual(result.month, 1)
    self.assertEqual(result.day, 1)
    self.assertEqual(result.hour, 12)
```

### Тест 13: test_current_timestamp

**Класс:** `TestTimestampToUtcDatetime`  
**Расположение:** строки 78-87

```python
def test_current_timestamp(self):
    """Тест: текущий timestamp"""
    now_utc = datetime.now(UTC)
    timestamp_ms = int(now_utc.timestamp() * 1000)
    result = timestamp_to_utc_datetime(timestamp_ms)
    
    self.assertIsNone(result.tzinfo)
    # Проверяем, что разница не больше 1 секунды
    diff = abs((result - now_utc.replace(tzinfo=None)).total_seconds())
    self.assertLess(diff, 1, "Разница должна быть меньше 1 секунды")
```

### Тест 14: test_naive_utc_format

**Класс:** `TestFormatDatetimeMoscow`  
**Расположение:** строки 93-101

```python
def test_naive_utc_format(self):
    """Тест: naive UTC datetime -> строка в московском времени"""
    dt_naive = datetime(2025, 1, 1, 12, 0, 0)  # 12:00 UTC
    result = format_datetime_moscow(dt_naive)
    
    # 12:00 UTC = 15:00 MSK
    self.assertIn("01.01.2025", result)
    self.assertIn("15:00", result)
    self.assertIn("UTC+3", result)
```

### Тест 15: test_aware_utc_format

**Класс:** `TestFormatDatetimeMoscow`  
**Расположение:** строки 103-110

```python
def test_aware_utc_format(self):
    """Тест: aware UTC datetime -> строка в московском времени"""
    dt_utc = datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC)
    result = format_datetime_moscow(dt_utc)
    
    self.assertIn("01.01.2025", result)
    self.assertIn("15:00", result)
    self.assertIn("UTC+3", result)
```

### Тест 16: test_feature_disabled

**Класс:** `TestFormatDatetimeForUser`  
**Расположение:** строки 116-124

```python
def test_feature_disabled(self):
    """Тест: feature flag выключен -> использует legacy функцию"""
    dt_naive = datetime(2025, 1, 1, 12, 0, 0)
    result = format_datetime_for_user(dt_naive, feature_enabled=False)
    
    # Должно работать как format_datetime_moscow
    self.assertIn("01.01.2025", result)
    self.assertIn("15:00", result)
    self.assertIn("UTC+3", result)
```

### Тест 17: test_feature_enabled_default_timezone

**Класс:** `TestFormatDatetimeForUser`  
**Расположение:** строки 126-133

```python
def test_feature_enabled_default_timezone(self):
    """Тест: feature flag включен, timezone по умолчанию (Moscow)"""
    dt_naive = datetime(2025, 1, 1, 12, 0, 0)
    result = format_datetime_for_user(dt_naive, feature_enabled=True)
    
    self.assertIn("01.01.2025", result)
    self.assertIn("15:00", result)
    self.assertIn("UTC+3", result)
```

### Тест 18: test_feature_enabled_custom_timezone

**Класс:** `TestFormatDatetimeForUser`  
**Расположение:** строки 135-145

```python
def test_feature_enabled_custom_timezone(self):
    """Тест: feature flag включен, custom timezone"""
    dt_naive = datetime(2025, 1, 1, 12, 0, 0)
    # UTC+5 (например, Yekaterinburg)
    result = format_datetime_for_user(dt_naive, user_timezone="Asia/Yekaterinburg", feature_enabled=True)
    
    self.assertIn("01.01.2025", result)
    # На Windows без tzdata будет fallback на Moscow (15:00), на Unix - 17:00
    # Проверяем, что время изменилось (не 12:00)
    self.assertNotIn("12:00", result)  # Должно быть конвертировано
    self.assertIn("UTC", result)
```

### Тест 19: test_returns_naive_utc

**Класс:** `TestGetCurrentUtcNaive`  
**Расположение:** строки 151-160

```python
def test_returns_naive_utc(self):
    """Тест: возвращает naive UTC datetime"""
    result = get_current_utc_naive()
    
    self.assertIsNone(result.tzinfo, "Должен быть naive")
    
    # Проверяем, что это примерно текущее время
    now_utc = datetime.now(UTC).replace(tzinfo=None)
    diff = abs((result - now_utc).total_seconds())
    self.assertLess(diff, 1, "Разница с текущим временем должна быть < 1 секунды")
```

### Тест 20: test_returns_aware_moscow

**Класс:** `TestGetMoscowNow`  
**Расположение:** строки 166-176

```python
def test_returns_aware_moscow(self):
    """Тест: возвращает aware Moscow datetime"""
    result = get_moscow_now()
    
    self.assertIsNotNone(result.tzinfo, "Должен быть aware")
    
    # Проверяем, что offset примерно +3 часа
    offset = result.utcoffset()
    self.assertIsNotNone(offset)
    # Offset может быть 3 или 4 часа в зависимости от DST
    self.assertIn(offset.total_seconds() / 3600, [3, 4], "Offset должен быть +3 или +4 часа")
```

### Тест 21: test_future_timestamp

**Класс:** `TestCalculateRemainingSeconds`  
**Расположение:** строки 182-190

```python
def test_future_timestamp(self):
    """Тест: timestamp в будущем -> положительное число секунд"""
    # Timestamp через 1 час
    future_ms = int((datetime.now(UTC).timestamp() + 3600) * 1000)
    result = calculate_remaining_seconds(future_ms)
    
    # Должно быть примерно 3600 секунд (1 час)
    self.assertGreater(result, 3500)
    self.assertLess(result, 3700)
```

### Тест 22: test_past_timestamp

**Класс:** `TestCalculateRemainingSeconds`  
**Расположение:** строки 192-198

```python
def test_past_timestamp(self):
    """Тест: timestamp в прошлом -> 0 секунд"""
    # Timestamp час назад
    past_ms = int((datetime.now(UTC).timestamp() - 3600) * 1000)
    result = calculate_remaining_seconds(past_ms)
    
    self.assertEqual(result, 0, "Для прошедшего времени должно вернуть 0")
```

### Тест 23: test_current_timestamp

**Класс:** `TestCalculateRemainingSeconds`  
**Расположение:** строки 200-207

```python
def test_current_timestamp(self):
    """Тест: текущий timestamp -> ~0 секунд"""
    now_ms = int(datetime.now(UTC).timestamp() * 1000)
    result = calculate_remaining_seconds(now_ms)
    
    # Должно быть очень близко к 0
    self.assertGreaterEqual(result, 0)
    self.assertLess(result, 5, "Для текущего времени должно быть < 5 секунд")
```

### Тест 24: test_full_workflow_new_key

**Класс:** `TestIntegration`  
**Расположение:** строки 213-239

```python
def test_full_workflow_new_key(self):
    """Тест: полный цикл работы с датой нового ключа"""
    # 1. Получаем timestamp из API (например, expiry через 30 дней)
    now_utc = datetime.now(UTC)
    future_utc = now_utc + timedelta(days=30)
    expiry_timestamp_ms = int(future_utc.timestamp() * 1000)
    
    # 2. Конвертируем timestamp в naive UTC для записи в БД
    expiry_date = timestamp_to_utc_datetime(expiry_timestamp_ms)
    
    # Проверяем, что дата naive
    self.assertIsNone(expiry_date.tzinfo)
    
    # 3. Вычисляем remaining_seconds
    remaining_seconds = calculate_remaining_seconds(expiry_timestamp_ms)
    
    # Должно быть примерно 30 дней в секундах
    expected_seconds = 30 * 24 * 3600
    self.assertGreater(remaining_seconds, expected_seconds - 100)
    self.assertLess(remaining_seconds, expected_seconds + 100)
    
    # 4. Форматируем для отображения пользователю
    formatted = format_datetime_moscow(expiry_date)
    
    # Проверяем формат
    self.assertIn("в", formatted)
    self.assertIn(".", formatted)
```

### Тест 25: test_backward_compatibility

**Класс:** `TestIntegration`  
**Расположение:** строки 241-254

```python
def test_backward_compatibility(self):
    """Тест: обратная совместимость со старым кодом"""
    # Старый код мог создавать naive datetime напрямую
    old_style_date = datetime(2025, 6, 1, 12, 0, 0)  # naive
    
    # Новая утилита должна его принять (с предупреждением)
    result = ensure_utc_datetime(old_style_date)
    
    # Результат не должен измениться
    self.assertEqual(result, old_style_date)
    
    # Форматирование тоже должно работать
    formatted = format_datetime_moscow(old_style_date)
    self.assertIn("01.06.2025", formatted)
```

---

## Итоговая статистика

- **Всего файлов:** 2
- **Всего тестов:** 25
- **Интеграционные тесты:** 8 (test_timezone_integration.py)
- **Unit тесты:** 17 (test_timezone_utils.py)

## Примечание

Все эти тесты используют `unittest.TestCase`, поэтому декораторы Allure (`@allure.epic`, `@allure.feature`) не применяются. Согласно правилам из `testing-rules.mdc`, для `unittest.TestCase` декораторы не требуются, так как они используют другой подход к тестированию.

---

**Связанные документы:**
- [Правила тестирования](../../guides/testing/testing-rules.mdc)
- [Allure отчеты](../../guides/testing/allure-reporting.md)




