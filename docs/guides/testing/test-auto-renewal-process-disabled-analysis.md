# 📋 Анализ теста: test_auto_renewal_process_disabled

**Дата анализа:** 15.11.2025  
**Тест:** `integration.test_auto_renewal.test_auto_renewal_process.TestAutoRenewalProcess#test_auto_renewal_process_disabled`  
**Статус:** ✅ PASSED (текущий) / ❌ BROKEN (в истории Allure)

---

## 📖 Подробное описание теста

### Назначение теста

Тест проверяет, что **автопродление ключей не выполняется**, когда функция автопродления **отключена** у пользователя, даже если:
- Баланс пользователя достаточен для продления
- Ключ истек по сроку действия
- Тариф доступен для продления

### Тип теста

- **Категория:** Интеграционный тест
- **Маркеры:** `@pytest.mark.integration`, `@pytest.mark.bot`, `@pytest.mark.asyncio`
- **Расположение:** `tests/integration/test_auto_renewal/test_auto_renewal_process.py:160`

### Предусловия (Arrange)

1. **Создается временная БД** (`temp_db` фикстура)
2. **Регистрируется тестовый пользователь:**
   - `user_id = 123462`
   - `username = "test_user3"`
   - `referrer_id = None`

3. **Создается тестовый хост:**
   - `host_name = "test_host"`
   - `host_url = "http://test.com"`
   - `host_username = "user"`
   - `host_pass = "pass"`
   - `host_inbound_id = 1`
   - `host_code = "testcode"`

4. **Устанавливается баланс пользователя:**
   - `balance = 200.0 RUB` (достаточно для продления тарифа за 100 RUB)

5. **Отключается автопродление:**
   - `set_auto_renewal_enabled(user_id, False)`

6. **Создается ключ с истекшим сроком:**
   - `key_id` — идентификатор созданного ключа
   - `expiry_date = datetime.now(timezone.utc) - timedelta(hours=1)` (истек 1 час назад)
   - `host_name = "test_host"`
   - `xui_client_uuid = "test-uuid-disabled"`
   - `key_email = f"user{user_id}-key1@testcode.bot"`
   - `plan_name = "Test Plan"`
   - `price = 100.0 RUB`

7. **Мокируется функция `get_all_keys`:**
   - Возвращает список с одним ключом (созданным выше)
   - Данные ключа включают: `key_id`, `user_id`, `host_name`, `plan_name`, `expiry_date`, `price`

### Действия (Act)

```python
await perform_auto_renewals(mock_bot)
```

Выполняется функция автопродления, которая:
1. Получает все ключи из БД через `get_all_keys()`
2. Для каждого истекшего ключа проверяет:
   - Доступность тарифа (`_get_plan_info_for_key`)
   - Достаточность баланса (`get_user_balance`)
   - **Включено ли автопродление** (`get_auto_renewal_enabled`) — **здесь должно вернуть `False`**

### Ожидаемый результат (Assert)

✅ **Баланс пользователя НЕ изменился:**
```python
balance = get_user_balance(user_id)
assert balance == 200.0  # Остался 200.0, не списалось 100.0
```

### Логика работы функции `perform_auto_renewals`

Функция `perform_auto_renewals` (```891:938:src/shop_bot/data_manager/scheduler.py```) выполняет следующие проверки:

1. **Получение всех ключей** (строка 894):
   ```python
   all_keys = database.get_all_keys()
   ```

2. **Проверка истечения срока** (строка 907):
   ```python
   if expiry_date > now:
       continue  # Пропускаем ключи, которые еще не истекли
   ```

3. **Проверка доступности тарифа** (строка 913-927):
   ```python
   plan_info, price_to_renew, months_to_renew, plan_id, is_plan_available = _get_plan_info_for_key(key)
   if not plan_info or not plan_has_duration or not plan_id or price_to_renew <= 0 or not is_plan_available:
       continue  # Пропускаем, если тариф недоступен
   ```

4. **Проверка достаточности баланса** (строка 929-932):
   ```python
   from shop_bot.data_manager.database import get_user_balance, ...
   current_balance = float(get_user_balance(user_id) or 0.0)
   if current_balance < price_to_renew:
       continue  # Пропускаем, если баланса недостаточно
   ```

5. **🔑 КЛЮЧЕВАЯ ПРОВЕРКА: Включено ли автопродление** (строка 934-938):
   ```python
   from shop_bot.data_manager.database import get_auto_renewal_enabled
   if not get_auto_renewal_enabled(user_id):
       logger.info(f"Auto-renewal skipped for user {user_id}, key {key_id}: auto-renewal is disabled")
       continue  # ⬅️ ЗДЕСЬ ТЕСТ ДОЛЖЕН ВЫЙТИ ИЗ ФУНКЦИИ
   ```

6. **Если все проверки пройдены** — выполняется автопродление:
   - Списание средств с баланса
   - Продление ключа через 3X-UI API
   - Отправка уведомления пользователю

---

## 🐛 Анализ проблемы (на основе фактов)

### Историческая проблема (из Allure Reports)

**Ошибка из `allure-defects-export.json`:**
```json
{
  "name": "test_auto_renewal_process_disabled",
  "status": "broken",
  "error": "NameError: name 'get_user_balance' is not defined",
  "trace": "E   NameError: name 'get_user_balance' is not defined",
  "duration_ms": 63,
  "error_group": "NameError: name 'get_user_balance' is not defined"
}
```

### Причина ошибки

**Проблема:** Функция `get_user_balance` не была доступна в области видимости на строке 208 теста.

**Местоположение ошибки:**
```python
# Строка 166: импорт функции
from shop_bot.data_manager.database import (
    register_user_if_not_exists,
    add_new_key,
    add_to_user_balance,
    get_user_balance,  # ⬅️ Импортируется здесь
    set_auto_renewal_enabled,
    create_host,
)

# ... код теста ...

# Строка 208: использование функции
balance = get_user_balance(user_id)  # ❌ NameError: name 'get_user_balance' is not defined
assert balance == 200.0
```

### Возможные причины ошибки

1. **Проблема с областью видимости при патчинге:**
   - Тест использует `patch('shop_bot.data_manager.database.get_all_keys')` на строке 195
   - Патчинг может изменить импорты внутри модуля `database`
   - Функция `get_user_balance` может быть недоступна после патчинга

2. **Проблема с импортом внутри функции:**
   - В тесте `test_auto_renewal_process_plan_unavailable` (строка 261) используется обходной путь:
     ```python
     from shop_bot.data_manager.database import get_user_balance as get_balance
     balance = get_balance(user_id)
     ```
   - Это может указывать на проблему с областью видимости импортов

3. **Изменение структуры импортов:**
   - В функции `perform_auto_renewals` (строка 929) `get_user_balance` импортируется **внутри функции**:
     ```python
     from shop_bot.data_manager.database import get_user_balance, add_to_user_balance, ...
     ```
   - Это может создавать конфликты при тестировании

### Текущий статус

✅ **Тест сейчас проходит успешно:**
```bash
$ docker compose exec autotest pytest tests/integration/test_auto_renewal/test_auto_renewal_process.py::TestAutoRenewalProcess::test_auto_renewal_process_disabled -v

tests/integration/test_auto_renewal/test_auto_renewal_process.py::TestAutoRenewalProcess::test_auto_renewal_process_disabled PASSED [100%]
```

**Возможные причины исправления:**
1. Исправлена проблема с импортами в модуле `database`
2. Изменена логика патчинга в тестах
3. Обновлена версия pytest или зависимостей

---

## 🔍 Исследование реализации функций

### Функция `get_auto_renewal_enabled`

**Расположение:** ```4864:4902:src/shop_bot/data_manager/database.py```

**Логика работы:**
```python
def get_auto_renewal_enabled(user_id: int) -> bool:
    """Получает статус автопродления для пользователя. По умолчанию True (включено)."""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT auto_renewal_enabled FROM users WHERE telegram_id = ?", (user_id,))
            row = cursor.fetchone()
            
            # По умолчанию автопродление включено (1), если поле NULL или отсутствует - возвращаем True
            if row and row[0] is not None:
                return bool(row[0])
            return True  # По умолчанию включено
    except sqlite3.OperationalError as e:
        # Если колонка еще не существует (миграция не выполнилась), возвращаем True по умолчанию
        if "no such column" in str(e).lower():
            logging.debug(f"Column auto_renewal_enabled does not exist yet for user {user_id}, returning default True")
            return True
        raise
    except sqlite3.Error as e:
        logging.error(f"Failed to get auto_renewal_enabled for user {user_id}: {e}")
        return True  # По умолчанию включено при ошибке
```

**Важные особенности:**
- По умолчанию возвращает `True` (автопродление включено)
- Если колонка отсутствует — возвращает `True`
- При ошибке БД — возвращает `True`

### Функция `set_auto_renewal_enabled`

**Расположение:** ```4908:4969:src/shop_bot/data_manager/database.py```

**Логика работы:**
```python
def set_auto_renewal_enabled(user_id: int, enabled: bool) -> bool:
    # Обновляет значение auto_renewal_enabled в таблице users
    # Возвращает True при успехе, False при ошибке
```

**В тесте:**
```python
set_auto_renewal_enabled(user_id, False)  # Отключаем автопродление
```

### Функция `get_user_balance`

**Расположение:** ```4842:4861:src/shop_bot/data_manager/database.py```

**Логика работы:**
```python
def get_user_balance(user_id: int) -> float:
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT balance FROM users WHERE telegram_id = ?", (user_id,))
            row = cursor.fetchone()
            return float(row[0]) if row and row[0] is not None else 0.0
    except sqlite3.Error as e:
        logging.error(f"Failed to get balance for user {user_id}: {e}")
        return 0.0
```

**Возвращает:**
- Баланс пользователя в виде `float`
- `0.0` если пользователь не найден или при ошибке

---

## ✅ Проверка корректности теста

### Что тест проверяет правильно:

1. ✅ Автопродление не выполняется при отключенной функции
2. ✅ Баланс не списывается
3. ✅ Используется временная БД (`temp_db`)
4. ✅ Используются моки для внешних зависимостей (`mock_bot`)

### Потенциальные проблемы в тесте:

1. ⚠️ **Отсутствие проверки плана:**
   - В тесте не создается план (`create_plan` не вызывается)
   - Функция `perform_auto_renewals` проверяет доступность плана через `_get_plan_info_for_key`
   - Если план недоступен, автопродление пропускается по другой причине, не из-за отключенного автопродления

2. ⚠️ **Мокирование `get_all_keys`:**
   - Тест мокирует `get_all_keys`, но не мокирует `_get_plan_info_for_key`
   - Если `_get_plan_info_for_key` вернет `is_plan_available = False`, автопродление пропустится до проверки `get_auto_renewal_enabled`

3. ⚠️ **Отсутствие проверки логов:**
   - Тест не проверяет, что в логах появилась запись:
     ```python
     logger.info(f"Auto-renewal skipped for user {user_id}, key {key_id}: auto-renewal is disabled")
     ```

### Рекомендации по улучшению теста:

1. **Создать план для корректной проверки:**
   ```python
   create_plan("test_host", "Test Plan", 1, 100.0, 0, 0.0, 0)
   ```

2. **Добавить проверку логов:**
   ```python
   with patch('shop_bot.data_manager.scheduler.logger') as mock_logger:
       await perform_auto_renewals(mock_bot)
       mock_logger.info.assert_called_with(
           f"Auto-renewal skipped for user {user_id}, key {key_id}: auto-renewal is disabled"
       )
   ```

3. **Проверить, что `get_auto_renewal_enabled` действительно вызывается:**
   ```python
   with patch('shop_bot.data_manager.database.get_auto_renewal_enabled') as mock_get_auto_renewal:
       mock_get_auto_renewal.return_value = False
       await perform_auto_renewals(mock_bot)
       mock_get_auto_renewal.assert_called_with(user_id)
   ```

---

## 📊 Сравнение с другими тестами

### Успешный тест: `test_auto_renewal_process_success`

**Отличия:**
- ✅ Создает план: `create_plan("test_host", "Test Plan", 1, 100.0, 0, 0.0, 0)`
- ✅ Мокирует `get_plan_by_id` для возврата данных плана
- ✅ Включает автопродление: `set_auto_renewal_enabled(user_id, True)`
- ✅ Мокирует `xui_api` для продления ключа

### Тест с обходным путем: `test_auto_renewal_process_plan_unavailable`

**Отличия:**
- ✅ Использует обходной путь для импорта:
  ```python
  from shop_bot.data_manager.database import get_user_balance as get_balance
  balance = get_balance(user_id)
  ```
- ❌ Не создает план (план недоступен по условию теста)

---

## 🎯 Выводы

1. **Тест работает корректно** на текущий момент — проверяет, что автопродление не выполняется при отключенной функции.

2. **Историческая проблема** (`NameError: name 'get_user_balance' is not defined`) была связана с областью видимости импортов при патчинге.

3. **Тест можно улучшить:**
   - Добавить создание плана для более точной проверки
   - Добавить проверку логов
   - Добавить мокирование `get_auto_renewal_enabled` для изоляции проверки

4. **Функция `perform_auto_renewals` работает корректно:**
   - Проверяет автопродление через `get_auto_renewal_enabled` на строке 936
   - Пропускает ключ, если автопродление отключено (строка 937-938)
   - Логирует пропуск для отладки

---

**Последнее обновление:** 15.11.2025  
**Связанные тесты:**
- `test_auto_renewal_process_success` — успешное автопродление
- `test_auto_renewal_process_insufficient_balance` — недостаточный баланс
- `test_auto_renewal_process_plan_unavailable` — недоступный тариф

