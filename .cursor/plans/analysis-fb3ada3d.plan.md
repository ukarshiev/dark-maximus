<!-- fb3ada3d-d94c-467f-9b4a-2909640ef0a8 1082f7bb-4e71-466b-bcea-bb36d00ba701 -->
# План реализации поддержки часовых поясов (PRODUCTION-SAFE)

## ⚠️ КРИТИЧЕСКИЕ ПРИНЦИПЫ БЕЗОПАСНОСТИ:

1. **Backward Compatibility** — старый код продолжает работать
2. **Feature Flags** — новая функциональность включается постепенно
3. **Rollback Ready** — можно откатить изменения без потери данных
4. **Zero Downtime** — система работает без остановки
5. **Testing First** — тесты перед каждым изменением

---

## Резюме задачи:

### Проблема

Система смешивает UTC и локальное время при записи `expiry_date`, что приводит к:

- Пропуску уведомлений за 24ч/1ч до истечения
- Задержкам автопродления на ~3 часа

### Решение

1. **Унифицировать хранение** — все даты в БД только в UTC
2. **Персонализировать отображение** — каждый пользователь видит время в своём часовом поясе
3. **Добавить настройку** — выбор часового пояса в профиле и админ-панели

### Ключевые находки из исследования:

- ✅ Использовать `zoneinfo` (встроен в Python 3.9+) вместо `pytz`
- ✅ SQLite `ALTER TABLE ADD COLUMN` безопасна в продакшене
- ✅ Хранить UTC, конвертировать при отображении
- ✅ Feature flag для постепенного включения

---

## ЭТАП 0: Подготовка и защита (КРИТИЧЕСКИЙ)

### 0.1. Создать резервную копию БД

**Скрипт:** `tests/backup_before_timezone_migration.py`

```python
import shutil
from datetime import datetime
shutil.copy('users.db', f'users_backup_{datetime.now().strftime("%Y%m%d_%H%M%S")}.db')
```

### 0.2. Добавить feature flag

**Файл:** `src/shop_bot/data_manager/database.py`

```python
def is_timezone_feature_enabled() -> bool:
    """Feature flag для постепенного включения timezone функциональности."""
    try:
        setting = get_setting('feature_timezone_enabled')
        return setting == '1' if setting else False
    except:
        return False
```

**В bot_settings добавить:**

```sql
INSERT INTO bot_settings (key, value) VALUES ('feature_timezone_enabled', '0');
```

### 0.3. Создать тестовую среду

Скопировать продакшн БД в тестовую среду для безопасного тестирования.

---

## ЭТАП 1: Исправление критических багов (ПРИОРИТЕТ: КРИТИЧЕСКИЙ)

### 1.1. Создать helper-модуль с backward compatibility

**Новый файл:** `src/shop_bot/utils/datetime_utils.py`

```python
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
from typing import Optional

# Константа для Moscow timezone (по умолчанию)
MOSCOW_TZ = ZoneInfo("Europe/Moscow")
DEFAULT_TIMEZONE = "Europe/Moscow"

def ensure_utc_datetime(dt: datetime) -> datetime:
    """
    Гарантирует, что datetime в UTC без tzinfo.
    БЕЗОПАСНО для существующих данных.
    """
    if dt is None:
        return None
    
    # Если уже есть tzinfo, конвертируем в UTC
    if dt.tzinfo is not None:
        return dt.astimezone(timezone.utc).replace(tzinfo=None)
    
    # Если tzinfo нет, предполагаем UTC (для обратной совместимости)
    return dt

def timestamp_to_utc_datetime(timestamp_ms: int) -> datetime:
    """Конвертирует timestamp в UTC datetime без tzinfo."""
    return datetime.fromtimestamp(timestamp_ms / 1000, tz=timezone.utc).replace(tzinfo=None)

def format_datetime_moscow(dt: datetime) -> str:
    """
    LEGACY функция для обратной совместимости.
    Форматирует datetime в Moscow time.
    """
    if dt is None:
        return ""
    
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    
    dt_moscow = dt.astimezone(MOSCOW_TZ)
    return dt_moscow.strftime('%d.%m.%Y в %H:%M')

def format_datetime_for_user(dt: datetime, user_id: int) -> str:
    """
    Форматирует datetime с учётом часового пояса пользователя.
    Использует feature flag для безопасного включения.
    """
    from shop_bot.data_manager.database import is_timezone_feature_enabled, get_user_timezone
    
    if dt is None:
        return ""
    
    # Если feature flag выключен, используем Moscow time
    if not is_timezone_feature_enabled():
        return format_datetime_moscow(dt)
    
    # Получаем timezone пользователя
    try:
        tz_name = get_user_timezone(user_id) or DEFAULT_TIMEZONE
        user_tz = ZoneInfo(tz_name)
    except:
        # Fallback на Moscow при ошибке
        user_tz = MOSCOW_TZ
    
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    
    dt_local = dt.astimezone(user_tz)
    
    # Показываем UTC offset для ясности
    offset = dt_local.strftime('%z')
    offset_formatted = f"UTC{offset[:3]}:{offset[3:]}"
    
    return f"{dt_local.strftime('%d.%m.%Y в %H:%M')} ({offset_formatted})"
```

### 1.2. Исправить запись expiry_date (с защитой)

**Файл:** `src/shop_bot/data_manager/database.py`

**Изменения в `update_key_info()`:**

```python
def update_key_info(key_id: int, new_xui_uuid: str, new_expiry_ms: int, subscription_link: str = None):
    try:
        from shop_bot.utils.datetime_utils import timestamp_to_utc_datetime
        
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            
            # ИСПРАВЛЕНО: используем UTC
            expiry_date = timestamp_to_utc_datetime(new_expiry_ms)
            
            # Остальной код без изменений...
```

**Аналогично исправить:**

- `update_key_status_from_server()` (строка ~5439)
- `add_new_key()` (строка ~5143)

### 1.3. Создать скрипт миграции существующих данных

**Файл:** `tests/migrate_expiry_dates_to_utc.py`

```python
#!/usr/bin/env python3
"""
Миграция существующих expiry_date в UTC.
БЕЗОПАСНО: не изменяет данные, только анализирует и исправляет некорректные.
"""
import sqlite3
from datetime import datetime, timezone, timedelta

DB_FILE = "users.db"

def analyze_and_fix_expiry_dates(dry_run=True):
    """
    Анализирует и исправляет expiry_date.
    dry_run=True: только анализ, без изменений
    dry_run=False: исправляет данные
    """
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # Получаем все ключи
    cursor.execute("SELECT key_id, expiry_date, created_date FROM vpn_keys")
    keys = cursor.fetchall()
    
    issues_found = 0
    fixed = 0
    
    for key_id, expiry_str, created_str in keys:
        try:
            expiry = datetime.fromisoformat(expiry_str)
            
            # Проверяем, есть ли timezone info
            if expiry.tzinfo is not None:
                # Если есть timezone, конвертируем в UTC
                expiry_utc = expiry.astimezone(timezone.utc).replace(tzinfo=None)
                
                if not dry_run:
                    cursor.execute(
                        "UPDATE vpn_keys SET expiry_date = ? WHERE key_id = ?",
                        (expiry_utc, key_id)
                    )
                    fixed += 1
                
                issues_found += 1
                print(f"Key {key_id}: {expiry_str} -> {expiry_utc}")
        
        except Exception as e:
            print(f"Error processing key {key_id}: {e}")
    
    if not dry_run:
        conn.commit()
    
    conn.close()
    
    print(f"\nAnalysis complete:")
    print(f"Issues found: {issues_found}")
    print(f"Fixed: {fixed}")
    print(f"Mode: {'DRY RUN' if dry_run else 'APPLIED'}")

if __name__ == "__main__":
    # Сначала анализ
    print("=== DRY RUN ===")
    analyze_and_fix_expiry_dates(dry_run=True)
    
    # Раскомментировать для применения
    # print("\n=== APPLYING FIXES ===")
    # analyze_and_fix_expiry_dates(dry_run=False)
```

---

## ЭТАП 2: База данных (ПРИОРИТЕТ: ВЫСОКИЙ, БЕЗОПАСНО)

### 2.1. Добавить колонку timezone в users (БЕЗОПАСНО)

**Миграция:** `tests/add_timezone_column.py`

```python
import sqlite3

DB_FILE = "users.db"

def add_timezone_column():
    """
    Добавляет колонку timezone в users.
    БЕЗОПАСНО: ALTER TABLE ADD COLUMN не блокирует таблицу в SQLite.
    """
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        # Проверяем, есть ли уже колонка
        cursor.execute("PRAGMA table_info(users)")
        columns = [row[1] for row in cursor.fetchall()]
        
        if 'timezone' not in columns:
            cursor.execute(
                "ALTER TABLE users ADD COLUMN timezone TEXT DEFAULT 'Europe/Moscow'"
            )
            conn.commit()
            print("✅ Column 'timezone' added successfully")
        else:
            print("ℹ️ Column 'timezone' already exists")
        
        conn.close()
        return True
    
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

if __name__ == "__main__":
    add_timezone_column()
```

### 2.2. Добавить настройки в bot_settings

```sql
-- Feature flag (по умолчанию выключен)
INSERT OR IGNORE INTO bot_settings (key, value) VALUES ('feature_timezone_enabled', '0');

-- Admin timezone
INSERT OR IGNORE INTO bot_settings (key, value) VALUES ('admin_timezone', 'Europe/Moscow');
```

### 2.3. Создать функции в database.py (с feature flag)

```python
def get_user_timezone(user_id: int) -> str:
    """Получает часовой пояс пользователя."""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT timezone FROM users WHERE telegram_id = ?", (user_id,))
            row = cursor.fetchone()
            return row[0] if row and row[0] else 'Europe/Moscow'
    except:
        return 'Europe/Moscow'

def set_user_timezone(user_id: int, timezone: str) -> bool:
    """Устанавливает часовой пояс пользователя."""
    try:
        # Валидация timezone
        from zoneinfo import ZoneInfo
        ZoneInfo(timezone)  # Проверяем валидность
        
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE users SET timezone = ? WHERE telegram_id = ?",
                (timezone, user_id)
            )
            conn.commit()
            return True
    except:
        return False
```

---

## ЭТАП 3: Telegram-бот — выбор часового пояса (ПРИОРИТЕТ: ВЫСОКИЙ)

### 3.1. Обновить "Мой профиль" (БЕЗ EMAIL)

**Файл:** `src/shop_bot/bot/handlers.py`

```python
# Текст профиля (ОБНОВЛЁННЫЙ):
profile_text = f"""
👤 Мой профиль

🔄 Автопродление с баланса: {'Включено' if auto_renewal else 'Выключено'}
🌍 Часовой пояс: {timezone_display}
💰 Баланс: {balance:.2f} RUB
"""

# Где timezone_display:
from shop_bot.utils.datetime_utils import get_timezone_display
timezone_display = get_timezone_display(user_id)  # "UTC+3 (Москва, Стамбул)"
```

### 3.2. Создать список часовых поясов

**Новый файл:** `src/shop_bot/data/timezones.py`

```python
TIMEZONES = [
    {"offset": "-11", "cities": "Самоа", "iana": "Pacific/Samoa"},
    {"offset": "-10", "cities": "Гонолулу", "iana": "Pacific/Honolulu"},
    {"offset": "-9", "cities": "Анкоридж", "iana": "America/Anchorage"},
    {"offset": "-8", "cities": "Лос-Анджелес, Ванкувер", "iana": "America/Los_Angeles"},
    {"offset": "-7", "cities": "Денвер, Феникс", "iana": "America/Denver"},
    {"offset": "-6", "cities": "Чикаго, Мехико", "iana": "America/Chicago"},
    {"offset": "-5", "cities": "Нью-Йорк, Торонто", "iana": "America/New_York"},
    {"offset": "-4", "cities": "Каракас, Сантьяго", "iana": "America/Caracas"},
    {"offset": "-3", "cities": "Буэнос-Айрес, Сан-Паулу", "iana": "America/Argentina/Buenos_Aires"},
    {"offset": "-2", "cities": "Средняя Атлантика", "iana": "Atlantic/South_Georgia"},
    {"offset": "-1", "cities": "Азорские острова", "iana": "Atlantic/Azores"},
    {"offset": "+0", "cities": "Лондон, Дублин", "iana": "Europe/London"},
    {"offset": "+1", "cities": "Берлин, Париж", "iana": "Europe/Berlin"},
    {"offset": "+2", "cities": "Киев, Афины, Таллин", "iana": "Europe/Kiev"},
    {"offset": "+3", "cities": "Москва, Стамбул", "iana": "Europe/Moscow"},
    {"offset": "+4", "cities": "Дубай, Баку", "iana": "Asia/Dubai"},
    {"offset": "+5", "cities": "Екатеринбург, Карачи", "iana": "Asia/Yekaterinburg"},
    {"offset": "+6", "cities": "Алматы, Омск, Бишкек", "iana": "Asia/Almaty"},
    {"offset": "+7", "cities": "Бангкок, Джакарта, Новосиб.", "iana": "Asia/Novosibirsk"},
    {"offset": "+8", "cities": "Пекин, Сингапур, Иркутск", "iana": "Asia/Shanghai"},
    {"offset": "+9", "cities": "Токио, Сеул, Якутск", "iana": "Asia/Tokyo"},
    {"offset": "+10", "cities": "Владивосток, Сидней", "iana": "Australia/Sydney"},
    {"offset": "+11", "cities": "Магадан, Соломоновы о-ва", "iana": "Pacific/Guadalcanal"},
    {"offset": "+12", "cities": "Окленд, Фиджи", "iana": "Pacific/Auckland"},
]

TIMEZONES_PER_PAGE = 10

def get_timezone_page(page: int = 0):
    """Возвращает часовые пояса для страницы."""
    start = page * TIMEZONES_PER_PAGE
    end = start + TIMEZONES_PER_PAGE
    return TIMEZONES[start:end]

def get_total_pages():
    """Возвращает общее количество страниц."""
    return (len(TIMEZONES) + TIMEZONES_PER_PAGE - 1) // TIMEZONES_PER_PAGE
```

### 3.3. Реализовать пагинацию (10 на страницу)

**Файл:** `src/shop_bot/bot/keyboards.py`

```python
def create_timezone_selection_keyboard(page: int = 0):
    """Создаёт клавиатуру выбора часового пояса с пагинацией."""
    from shop_bot.data.timezones import get_timezone_page, get_total_pages, TIMEZONES_PER_PAGE
    
    builder = InlineKeyboardBuilder()
    
    timezones = get_timezone_page(page)
    total_pages = get_total_pages()
    
    # Кнопки часовых поясов
    for tz in timezones:
        button_text = f"UTC{tz['offset']}  | {tz['cities']}"
        callback_data = f"tz_select_{tz['iana']}"
        builder.button(text=button_text, callback_data=callback_data)
    
    builder.adjust(1)  # По одной кнопке в ряд
    
    # Навигация
    nav_buttons = []
    
    if page > 0:
        nav_buttons.append(("◀ Пред.", f"tz_page_{page-1}"))
    
    nav_buttons.append((f"Стр.{page+1}/{total_pages}", "tz_page_current"))
    
    if page < total_pages - 1:
        nav_buttons.append(("След ▶", f"tz_page_{page+1}"))
    
    for text, data in nav_buttons:
        builder.button(text=text, callback_data=data)
    
    builder.adjust(len(nav_buttons))
    
    # Кнопка отмены
    builder.button(text="❌ Отмена", callback_data="profile")
    
    return builder.as_markup()
```

### 3.4. Добавить подтверждение выбора

**Файл:** `src/shop_bot/bot/handlers.py`

```python
@router.callback_query(F.data.startswith("tz_select_"))
async def timezone_select_handler(callback: CallbackQuery):
    """Обработчик выбора часового пояса."""
    from zoneinfo import ZoneInfo
    from datetime import datetime, timezone
    
    tz_name = callback.data.replace("tz_select_", "")
    
    try:
        # Получаем информацию о часовом поясе
        user_tz = ZoneInfo(tz_name)
        now_utc = datetime.now(timezone.utc)
        now_local = now_utc.astimezone(user_tz)
        
        # Форматируем offset
        offset = now_local.strftime('%z')
        offset_formatted = f"UTC{offset[:3]}:{offset[3:]}"
        
        # Находим название городов
        from shop_bot.data.timezones import TIMEZONES
        tz_info = next((tz for tz in TIMEZONES if tz['iana'] == tz_name), None)
        cities = tz_info['cities'] if tz_info else tz_name
        
        text = f"""
Вы выбрали: {offset_formatted} | {cities}

Текущее время там: {now_local.strftime('%H:%M')} ({offset_formatted})

Установить этот часовой пояс?
"""
        
        builder = InlineKeyboardBuilder()
        builder.button(text="✅ Подтвердить", callback_data=f"tz_confirm_{tz_name}")
        builder.button(text="❌ Отмена", callback_data="timezone_change")
        builder.adjust(2)
        
        await callback.message.edit_text(text, reply_markup=builder.as_markup())
        
    except Exception as e:
        await callback.answer("❌ Ошибка выбора часового пояса", show_alert=True)

@router.callback_query(F.data.startswith("tz_confirm_"))
async def timezone_confirm_handler(callback: CallbackQuery):
    """Подтверждение установки часового пояса."""
    from shop_bot.data_manager.database import set_user_timezone
    
    tz_name = callback.data.replace("tz_confirm_", "")
    user_id = callback.from_user.id
    
    if set_user_timezone(user_id, tz_name):
        await callback.answer("✅ Часовой пояс успешно изменён", show_alert=True)
        # Возвращаемся в профиль
        await show_profile(callback.message, user_id)
    else:
        await callback.answer("❌ Ошибка сохранения", show_alert=True)
```

---

## ЭТАП 4: Веб-интерфейс (ПРИОРИТЕТ: СРЕДНИЙ)

### 4.1. Добавить в настройки панели

**Файл:** `src/shop_bot/webhook_server/templates/settings.html`

```html
<div class="form-group">
  <label for="admin_timezone">Часовой пояс панели</label>
  <select name="admin_timezone" id="admin_timezone" class="form-control">
    <option value="Europe/London">UTC+0 (Лондон)</option>
    <option value="Europe/Berlin">UTC+1 (Берлин)</option>
    <option value="Europe/Kiev">UTC+2 (Киев)</option>
    <option value="Europe/Moscow" selected>UTC+3 (Москва)</option>
    <option value="Asia/Dubai">UTC+4 (Дубай)</option>
    <option value="Asia/Yekaterinburg">UTC+5 (Екатеринбург)</option>
    <option value="Asia/Almaty">UTC+6 (Алматы)</option>
    <option value="Asia/Novosibirsk">UTC+7 (Новосибирск)</option>
    <option value="Asia/Shanghai">UTC+8 (Пекин)</option>
    <option value="Asia/Tokyo">UTC+9 (Токио)</option>
    <option value="Australia/Sydney">UTC+10 (Сидней)</option>
  </select>
  <small class="form-text text-muted">
    Часовой пояс для отображения дат в админ-панели
  </small>
</div>
```

---

## ЭТАП 5: Обновление отображения дат (ПРИОРИТЕТ: ВЫСОКИЙ)

### 5.1. Постепенная замена (с feature flag)

**Стратегия:**

1. Сначала заменить только в новых местах
2. Потом постепенно в существующих
3. Использовать feature flag для контроля

**Пример:**

```python
# СТАРЫЙ КОД (работает):
expiry_str = expiry_date.strftime('%d.%m.%Y в %H:%M')

# НОВЫЙ КОД (с feature flag):
from shop_bot.utils.datetime_utils import format_datetime_for_user
expiry_str = format_datetime_for_user(expiry_date, user_id)
# Если feature flag выключен, вернёт Moscow time (как раньше)
```

---

## ЭТАП 6: Тестирование (ПРИОРИТЕТ: КРИТИЧЕСКИЙ)

### 6.1. Unit тесты

**Файл:** `tests/test_timezone_utils.py`

```python
import unittest
from datetime import datetime, timezone
from shop_bot.utils.datetime_utils import (
    ensure_utc_datetime,
    timestamp_to_utc_datetime,
    format_datetime_moscow
)

class TestTimezoneUtils(unittest.TestCase):
    def test_ensure_utc_datetime(self):
        # Тест с UTC datetime
        dt_utc = datetime(2025, 11, 7, 12, 0, 0, tzinfo=timezone.utc)
        result = ensure_utc_datetime(dt_utc)
        self.assertIsNone(result.tzinfo)
        self.assertEqual(result.hour, 12)
        
        # Тест с naive datetime (предполагаем UTC)
        dt_naive = datetime(2025, 11, 7, 12, 0, 0)
        result = ensure_utc_datetime(dt_naive)
        self.assertEqual(result, dt_naive)
    
    def test_timestamp_to_utc_datetime(self):
        # 2025-11-07 12:00:00 UTC
        timestamp_ms = 1730980800000
        result = timestamp_to_utc_datetime(timestamp_ms)
        self.assertIsNone(result.tzinfo)
        self.assertEqual(result.year, 2025)
```

### 6.2. Integration тесты

**Файл:** `tests/test_timezone_integration.py`

Тестировать:

- Создание ключа → проверка UTC в БД
- Уведомление → проверка правильного времени
- Смена часового пояса → проверка отображения

### 6.3. Ручное тестирование

**Чеклист:**

- [ ] Создать тестовый ключ с истечением через 1 час
- [ ] Проверить, что в БД время в UTC
- [ ] Проверить уведомление за 1 час (должно прийти вовремя)
- [ ] Сменить часовой пояс на UTC+10
- [ ] Проверить, что время отображается правильно
- [ ] Проверить автопродление

---

## ЭТАП 7: Развёртывание (PRODUCTION-SAFE)

### 7.1. Pre-deployment чеклист

- [ ] Резервная копия БД создана
- [ ] Все тесты пройдены
- [ ] Feature flag = 0 (выключен)
- [ ] Rollback план готов

### 7.2. Развёртывание (поэтапное)

1. **День 1:** Деплой кода с feature flag = 0

   - Код работает в legacy режиме
   - Мониторинг ошибок

2. **День 2:** Добавить колонку timezone

   - Запустить миграцию
   - Проверить, что всё работает

3. **День 3:** Исправить запись expiry_date

   - Запустить скрипт миграции данных
   - Проверить корректность

4. **День 4:** Включить feature flag для тестовых пользователей

   - `feature_timezone_enabled = 1` только для админов
   - Тестировать функциональность

5. **День 5+:** Постепенное включение для всех

   - Включить для 10% пользователей
   - Мониторинг
   - Включить для всех

### 7.3. Rollback план

**Если что-то пошло не так:**

```sql
-- 1. Выключить feature flag
UPDATE bot_settings SET value = '0' WHERE key = 'feature_timezone_enabled';

-- 2. Восстановить БД из бэкапа (если критично)
-- cp users_backup_YYYYMMDD_HHMMSS.db users.db

-- 3. Откатить код (git)
-- git revert <commit_hash>
```

---

## ЭТАП 8: Мониторинг и оптимизация

### 8.1. Метрики для отслеживания

- Количество пропущенных уведомлений (должно = 0)
- Время отправки уведомлений (должно быть точным)
- Ошибки конвертации часовых поясов
- Производительность БД

### 8.2. Логирование

Добавить логи:

- При смене часового пояса пользователем
- При конвертации времени (если ошибка)
- При отправке уведомлений (с указанием timezone)

---

## Зависимости:

```toml
# pyproject.toml
dependencies = [
    # zoneinfo встроен в Python 3.9+
    # Для Python 3.8 добавить:
    # "backports.zoneinfo>=0.2.1; python_version<'3.9'",
]
```

---

## Порядок выполнения (БЕЗОПАСНЫЙ):

1. ✅ **Этап 0** — Подготовка (бэкапы, feature flags)
2. ✅ **Этап 6.1** — Создать unit тесты
3. ✅ **Этап 1** — Исправить критические баги (с backward compatibility)
4. ✅ **Этап 2** — Добавить БД структуру (безопасно)
5. ✅ **Этап 6.2** — Integration тесты
6. ✅ **Этап 7.1-7.2** — Развёртывание (поэтапное)
7. ✅ **Этап 3** — Telegram-бот (после включения feature flag)
8. ✅ **Этап 5** — Обновить отображение (постепенно)
9. ✅ **Этап 4** — Веб-интерфейс
10. ✅ **Этап 6.3** — Ручное тестирование
11. ✅ **Этап 8** — Мониторинг

---

## Что могли забыть (обновлено):

### ❓ Вопросы для уточнения:

1. **Python версия:** Какая версия Python используется? (для выбора zoneinfo/backports.zoneinfo)

2. **Уведомления в канале:** Если бот отправляет уведомления в канал администратора, использовать `admin_timezone`?

3. **API/webhook:** Если есть внешние интеграции, в каком формате отдавать даты? (Рекомендую: UTC + ISO 8601)

4. **Логи:** В каком часовом поясе писать логи? (Рекомендую: UTC с возможностью конвертации)

5. **Старые уведомления в БД:** Мигрировать `created_date` в таблице `notifications`?

6. **Автоопределение timezone:** Определять часовой пояс по IP при регистрации? (Опционально, можно добавить позже)

### To-dos

- [ ] Исправить запись expiry_date в UTC во всех функциях database.py и handlers.py
- [ ] Создать timezone_helper.py с функциями ensure_utc_datetime и format_datetime_for_user
- [ ] Создать скрипт миграции существующих expiry_date в UTC
- [ ] Добавить колонку timezone в users и настройку admin_timezone в bot_settings
- [ ] Реализовать get/set функции для работы с часовыми поясами в database.py
- [ ] Создать timezones.py со списком всех часовых поясов
- [ ] Обновить текст профиля с отображением часового пояса
- [ ] Создать клавиатуру выбора часового пояса с пагинацией
- [ ] Реализовать обработчики выбора и подтверждения часового пояса
- [ ] Добавить выпадающий список часовых поясов в настройки веб-панели
- [ ] Заменить все прямые форматирования дат на format_datetime_for_user
- [ ] Создать тесты для проверки корректности работы с часовыми поясами
- [ ] Провести ручное тестирование уведомлений и автопродления
- [ ] Обновить пользовательскую и техническую документацию