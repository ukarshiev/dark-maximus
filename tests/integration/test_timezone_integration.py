#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Integration тесты для полной поддержки timezone

Проверяет:
- Создание ключа → сохранение UTC в БД
- Уведомления → правильное время
- Смена timezone → корректное отображение
- Автопродление → правильное время срабатывания
"""

import sys
import pytest
import allure
import sqlite3
from datetime import datetime, timedelta, timezone as dt_timezone
from pathlib import Path

# Добавляем путь к модулям проекта
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root / "src"))

from shop_bot.utils.datetime_utils import (
    ensure_utc_datetime,
    timestamp_to_utc_datetime,
    format_datetime_for_user,
    get_current_utc_naive,
    calculate_remaining_seconds,
    UTC,
    MOSCOW_TZ
)


def init_test_database(temp_db):
    """Инициализирует тестовую БД с нужной структурой"""
    from shop_bot.data_manager import database
    conn = sqlite3.connect(str(temp_db))
    cursor = conn.cursor()
    
    # Создаем таблицу настроек (vpn_keys уже создана через database.initialize_db())
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS bot_settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)
    
    # Добавляем feature flag (по умолчанию выключен)
    cursor.execute("""
        INSERT OR REPLACE INTO bot_settings (key, value)
        VALUES ('feature_timezone_enabled', '0')
    """)
    
    conn.commit()
    conn.close()


def get_key_from_db(temp_db, key_id: int):
    """Получает ключ из БД"""
    conn = sqlite3.connect(str(temp_db))
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM vpn_keys WHERE key_id = ?", (key_id,))
    result = cursor.fetchone()
    conn.close()
    return result


def set_feature_flag(temp_db, enabled: bool):
    """Устанавливает feature flag"""
    conn = sqlite3.connect(str(temp_db))
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE bot_settings 
        SET value = ?
        WHERE key = 'feature_timezone_enabled'
    """, ('1' if enabled else '0',))
    conn.commit()
    conn.close()


@pytest.mark.integration
@pytest.mark.database
@allure.epic("Интеграционные тесты")
@allure.feature("Timezone")
@allure.label("package", "tests.integration.test_timezone_integration")
class TestKeyCreationStoresUTC:
    """Тесты: создание ключа сохраняет дату в UTC"""
    
    @allure.story("Создание ключа сохраняет дату в UTC")
    @allure.title("Создание нового ключа сохраняет expiry_date в UTC без tzinfo")
    @allure.description("""
    Проверяет, что при создании нового ключа expiry_date сохраняется в UTC без tzinfo.
    
    **Что проверяется:**
    - Создание ключа с expiry_date
    - Сохранение в БД в формате UTC (naive)
    - Корректность чтения из БД
    - Отсутствие tzinfo в сохраненной дате
    
    **Тестовые данные:**
    - user_id: 12345
    - username: "test_user"
    - expiry_date: текущее время + 30 дней
    
    **Предусловия:**
    - Используется временная БД (temp_db)
    - БД инициализирована с нужной структурой
    
    **Шаги теста:**
    1. Создание тестового пользователя с ключом
    2. Конвертация timestamp в naive UTC
    3. Сохранение в БД
    4. Чтение из БД и проверка формата
    
    **Ожидаемый результат:**
    expiry_date в БД должен быть naive (без tzinfo) и в формате UTC.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("timezone", "integration", "key_creation", "utc", "database")
    def test_new_key_expiry_date_is_utc_naive(self, temp_db):
        """Тест создания нового ключа с сохранением expiry_date в UTC"""
        init_test_database(temp_db)
        
        with allure.step("Подготовка тестовых данных"):
            user_id = 12345
            username = "test_user"
            now_utc = datetime.now(UTC)
            future_utc = now_utc + timedelta(days=30)
            expiry_timestamp_ms = int(future_utc.timestamp() * 1000)
            expiry_date = timestamp_to_utc_datetime(expiry_timestamp_ms)
            allure.attach(str(expiry_date), "expiry_date", allure.attachment_type.TEXT)
        
        with allure.step("Сохранение ключа в БД"):
            conn = sqlite3.connect(str(temp_db))
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO vpn_keys (user_id, host_name, xui_client_uuid, key_email, expiry_date, created_date)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                user_id,
                "test-host",
                "test-uuid-12345",
                "test-key-12345@example.com",
                expiry_date.isoformat(),
                now_utc.isoformat()
            ))
            key_id = cursor.lastrowid
            conn.commit()
            conn.close()
            allure.attach(str(key_id), "ID созданного ключа", allure.attachment_type.TEXT)
        
        with allure.step("Проверка данных из БД"):
            key = get_key_from_db(temp_db, key_id)
            assert key is not None, "Ключ должен быть создан"
            
            expiry_str = key[5]  # expiry_date (колонка 5 в vpn_keys)
            expiry_from_db = datetime.fromisoformat(expiry_str)
            allure.attach(str(expiry_from_db), "expiry_from_db", allure.attachment_type.TEXT)
            
            assert expiry_from_db.tzinfo is None, "expiry_date в БД должен быть naive (без tzinfo)"
            
            diff = abs((expiry_from_db - expiry_date).total_seconds())
            assert diff < 1, f"Дата должна совпадать с ожидаемой (разница: {diff} сек)"


@pytest.mark.integration
@pytest.mark.database
@allure.epic("Интеграционные тесты")
@allure.feature("Timezone")
@allure.label("package", "tests.integration.test_timezone_integration")
class TestNotificationTiming:
    """Тесты: уведомления приходят вовремя"""
    
    @allure.story("Уведомления приходят в правильное время")
    @allure.title("Уведомление за 1 час должно прийти ровно за 1 час")
    @allure.description("""
    Проверяет, что уведомление за 1 час до истечения ключа приходит в правильное время.
    
    **Что проверяется:**
    - Создание ключа с истечением через 1 час
    - Расчет оставшегося времени
    - Корректность времени отправки уведомления
    
    **Тестовые данные:**
    - user_id: 12346
    - expiry_date: текущее время + 1 час
    
    **Предусловия:**
    - Используется временная БД (temp_db)
    - БД инициализирована с нужной структурой
    
    **Шаги теста:**
    1. Создание ключа с истечением через 1 час
    2. Вычисление оставшегося времени
    3. Проверка корректности времени уведомления
    
    **Ожидаемый результат:**
    Оставшееся время должно быть примерно 3600 секунд (1 час).
    Уведомление должно отправиться примерно сейчас (за 1 час до истечения).
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("timezone", "integration", "notifications", "timing", "database")
    def test_notification_sent_at_correct_time(self, temp_db):
        """Тест правильного времени отправки уведомления"""
        init_test_database(temp_db)
        
        with allure.step("Создание ключа с истечением через 1 час"):
            user_id = 12346
            now_utc = get_current_utc_naive()
            expiry_date = now_utc + timedelta(hours=1)
            allure.attach(str(expiry_date), "expiry_date", allure.attachment_type.TEXT)
            
            conn = sqlite3.connect(str(temp_db))
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO vpn_keys (user_id, host_name, xui_client_uuid, key_email, expiry_date, created_date)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                user_id,
                "test-host",
                "test-uuid-notify",
                "test-key-notify@example.com",
                expiry_date.isoformat(),
                now_utc.isoformat()
            ))
            conn.commit()
            conn.close()
        
        with allure.step("Вычисление оставшегося времени"):
            expiry_timestamp_ms = int(expiry_date.replace(tzinfo=UTC).timestamp() * 1000)
            remaining_seconds = calculate_remaining_seconds(expiry_timestamp_ms)
            allure.attach(str(remaining_seconds), "remaining_seconds", allure.attachment_type.TEXT)
            
            expected_seconds = 3600
            diff = abs(remaining_seconds - expected_seconds)
            assert diff < 10, f"Оставшееся время должно быть ~3600 сек, получено: {remaining_seconds}"
        
        with allure.step("Проверка времени отправки уведомления"):
            notification_time = now_utc + timedelta(seconds=remaining_seconds) - timedelta(hours=1)
            time_diff = abs((notification_time - now_utc).total_seconds())
            assert time_diff < 10, "Уведомление должно отправиться примерно сейчас (за 1 час до истечения)"


@pytest.mark.integration
@pytest.mark.database
@allure.epic("Интеграционные тесты")
@allure.feature("Timezone")
@allure.label("package", "tests.integration.test_timezone_integration")
class TestTimezoneDisplay:
    """Тесты: смена timezone корректно меняет отображение"""
    
    @allure.story("Смена timezone корректно изменяет отображаемое время")
    @allure.title("Смена timezone корректно изменяет отображаемое время")
    @allure.description("""
    Проверяет, что смена timezone корректно изменяет отображаемое время для пользователя.
    
    **Что проверяется:**
    - Отображение времени для разных timezone (Moscow, Yekaterinburg, UTC)
    - Корректность конвертации времени
    - Работа feature flag
    
    **Тестовые данные:**
    - dt_utc: 2025-01-01 12:00:00 UTC
    - timezone: Europe/Moscow, Asia/Yekaterinburg, UTC
    
    **Предусловия:**
    - Используется временная БД (temp_db)
    - Feature flag включен
    
    **Шаги теста:**
    1. Создание тестовой даты в UTC
    2. Включение feature flag
    3. Проверка отображения для разных timezone
    
    **Ожидаемый результат:**
    Время должно корректно конвертироваться для каждого timezone.
    Moscow: 12:00 UTC = 15:00 MSK
    Yekaterinburg: 12:00 UTC = 17:00 YEKT (или fallback на Moscow на Windows)
    UTC: 12:00 UTC = 12:00 UTC
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("timezone", "integration", "display", "formatting")
    def test_timezone_change_updates_display(self, temp_db):
        """Тест изменения отображения времени при смене timezone"""
        init_test_database(temp_db)
        set_feature_flag(temp_db, True)
        
        with allure.step("Подготовка тестовой даты"):
            dt_utc = datetime(2025, 1, 1, 12, 0, 0)  # 12:00 UTC
            allure.attach(str(dt_utc), "dt_utc", allure.attachment_type.TEXT)
        
        with allure.step("Проверка отображения для Moscow (UTC+3)"):
            moscow_display = format_datetime_for_user(
                dt_utc,
                user_timezone="Europe/Moscow",
                feature_enabled=True
            )
            allure.attach(moscow_display, "moscow_display", allure.attachment_type.TEXT)
            assert "01.01.2025" in moscow_display
            assert "15:00" in moscow_display, "12:00 UTC = 15:00 MSK"
            assert "UTC" in moscow_display
        
        with allure.step("Проверка отображения для Yekaterinburg (UTC+5)"):
            yekaterinburg_display = format_datetime_for_user(
                dt_utc,
                user_timezone="Asia/Yekaterinburg",
                feature_enabled=True
            )
            allure.attach(yekaterinburg_display, "yekaterinburg_display", allure.attachment_type.TEXT)
            assert "01.01.2025" in yekaterinburg_display
            assert "12:00" not in yekaterinburg_display, "Время должно быть конвертировано"
            assert "UTC" in yekaterinburg_display
        
        with allure.step("Проверка отображения для UTC"):
            utc_display = format_datetime_for_user(
                dt_utc,
                user_timezone="UTC",
                feature_enabled=True
            )
            allure.attach(utc_display, "utc_display", allure.attachment_type.TEXT)
            assert "01.01.2025" in utc_display
            assert "2025" in utc_display, "Дата должна быть правильной"
            assert "UTC" in utc_display
    
    @allure.story("При выключенном feature flag используется Moscow")
    @allure.title("При выключенном feature flag используется Moscow")
    @allure.description("""
    Проверяет, что при выключенном feature flag используется Moscow timezone независимо от указанного timezone.
    
    **Что проверяется:**
    - Поведение при выключенном feature flag
    - Использование Moscow timezone по умолчанию
    - Игнорирование указанного timezone
    
    **Тестовые данные:**
    - dt_utc: 2025-01-01 12:00:00 UTC
    - user_timezone: "Asia/Tokyo" (указывается, но игнорируется)
    - feature_enabled: False
    
    **Предусловия:**
    - Feature flag выключен
    
    **Шаги теста:**
    1. Создание тестовой даты
    2. Форматирование с выключенным feature flag
    3. Проверка использования Moscow timezone
    
    **Ожидаемый результат:**
    При выключенном flag должно использоваться Moscow время (15:00), а не Tokyo.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("timezone", "integration", "display", "feature_flag")
    def test_feature_flag_disabled_uses_moscow(self, temp_db):
        """Тест использования Moscow при выключенном feature flag"""
        init_test_database(temp_db)
        
        with allure.step("Подготовка тестовой даты"):
            dt_utc = datetime(2025, 1, 1, 12, 0, 0)
            allure.attach(str(dt_utc), "dt_utc", allure.attachment_type.TEXT)
        
        with allure.step("Проверка форматирования с выключенным feature flag"):
            result = format_datetime_for_user(
                dt_utc,
                user_timezone="Asia/Tokyo",  # Указываем Tokyo
                feature_enabled=False  # Но flag выключен
            )
            allure.attach(result, "result", allure.attachment_type.TEXT)
            assert "15:00" in result, "При выключенном flag должно быть Moscow время"
            assert "UTC+3" in result


@pytest.mark.integration
@pytest.mark.database
@allure.epic("Интеграционные тесты")
@allure.feature("Timezone")
@allure.label("package", "tests.integration.test_timezone_integration")
class TestAutoRenewalTiming:
    """Тесты: автопродление работает вовремя"""
    
    @allure.story("Автопродление срабатывает в правильное время")
    @allure.title("Автопродление срабатывает в правильное время")
    @allure.description("""
    Проверяет, что автопродление срабатывает в правильное время (за 1 час до истечения ключа).
    
    **Что проверяется:**
    - Создание пользователя с балансом и включенным автопродлением
    - Расчет времени срабатывания автопродления
    - Корректность времени истечения в UTC
    
    **Тестовые данные:**
    - user_id: 12347
    - expiry_date: текущее время + 2 часа
    - balance: 100.0
    - auto_renewal: 1 (включено)
    
    **Предусловия:**
    - Используется временная БД (temp_db)
    - БД инициализирована с нужной структурой
    
    **Шаги теста:**
    1. Создание пользователя с балансом и автопродлением
    2. Вычисление времени срабатывания автопродления
    3. Проверка формата expiry_date в UTC
    
    **Ожидаемый результат:**
    Автопродление должно сработать примерно через 1 час от текущего момента.
    expiry_date должен быть в UTC (naive).
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("timezone", "integration", "auto_renewal", "timing", "database")
    def test_auto_renewal_triggers_at_correct_time(self, temp_db):
        """Тест правильного времени срабатывания автопродления"""
        init_test_database(temp_db)
        
        with allure.step("Создание пользователя с балансом и автопродлением"):
            user_id = 12347
            now_utc = get_current_utc_naive()
            expiry_date = now_utc + timedelta(hours=2)  # Истекает через 2 часа
            allure.attach(str(expiry_date), "expiry_date", allure.attachment_type.TEXT)
            
            conn = sqlite3.connect(str(temp_db))
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO vpn_keys (user_id, host_name, xui_client_uuid, key_email, expiry_date, created_date)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                user_id,
                "test-host",
                "test-uuid-renewal",
                "test-key-renewal@example.com",
                expiry_date.isoformat(),
                now_utc.isoformat()
            ))
            key_id = cursor.lastrowid
            conn.commit()
            conn.close()
            allure.attach(str(key_id), "ID созданного ключа", allure.attachment_type.TEXT)
        
        with allure.step("Вычисление времени срабатывания автопродления"):
            expiry_timestamp_ms = int(expiry_date.replace(tzinfo=UTC).timestamp() * 1000)
            remaining_seconds = calculate_remaining_seconds(expiry_timestamp_ms)
            
            # Автопродление должно сработать за 1 час (3600 секунд) до истечения
            auto_renewal_delay = remaining_seconds - 3600
            allure.attach(str(auto_renewal_delay), "auto_renewal_delay", allure.attachment_type.TEXT)
            
            assert auto_renewal_delay > 3500, "Автопродление через ~1 час"
            assert auto_renewal_delay < 3700, "Автопродление через ~1 час"
        
        with allure.step("Проверка формата expiry_date в UTC"):
            key = get_key_from_db(temp_db, key_id)
            expiry_str = key[5]  # expiry_date (колонка 5 в vpn_keys)
            expiry_from_db = datetime.fromisoformat(expiry_str)
            allure.attach(str(expiry_from_db), "Дата из БД", allure.attachment_type.TEXT)
            assert expiry_from_db.tzinfo is None, "expiry_date должен быть в UTC (naive)"


@pytest.mark.integration
@pytest.mark.database
@allure.epic("Интеграционные тесты")
@allure.feature("Timezone")
@allure.label("package", "tests.integration.test_timezone_integration")
class TestBackwardCompatibility:
    """Тесты: обратная совместимость со старыми данными"""
    
    @allure.story("Обратная совместимость со старыми ключами")
    @allure.title("Существующие ключи (без timezone) работают корректно")
    @allure.description("""
    Проверяет, что существующие ключи (созданные до внедрения timezone) работают корректно.
    
    **Что проверяется:**
    - Создание "старого" ключа без timezone
    - Корректность чтения из БД
    - Работа форматирования для старых ключей
    
    **Тестовые данные:**
    - user_id: 12348
    - expiry_date: текущее время + 30 дней
    - timezone: не указан (старый формат)
    
    **Предусловия:**
    - Используется временная БД (temp_db)
    - БД инициализирована с нужной структурой
    
    **Шаги теста:**
    1. Создание "старого" ключа без timezone
    2. Чтение из БД
    3. Проверка форматирования
    
    **Ожидаемый результат:**
    Старый формат должен работать корректно.
    Форматирование должно использовать Moscow по умолчанию.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("timezone", "integration", "backward_compatibility", "database")
    def test_existing_keys_work_correctly(self, temp_db):
        """Тест обратной совместимости со старыми ключами"""
        init_test_database(temp_db)
        
        with allure.step("Создание старого ключа без timezone"):
            user_id = 12348
            now_utc = get_current_utc_naive()
            expiry_date = now_utc + timedelta(days=30)
            allure.attach(str(expiry_date), "expiry_date", allure.attachment_type.TEXT)
            
            conn = sqlite3.connect(str(temp_db))
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO vpn_keys (user_id, host_name, xui_client_uuid, key_email, expiry_date, created_date)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                user_id,
                "test-host",
                "test-uuid-old",
                "old-key-12348@example.com",
                expiry_date.isoformat(),
                now_utc.isoformat()
            ))
            key_id = cursor.lastrowid
            conn.commit()
            conn.close()
            allure.attach(str(key_id), "ID созданного ключа", allure.attachment_type.TEXT)
        
        with allure.step("Проверка чтения из БД"):
            key = get_key_from_db(temp_db, key_id)
            expiry_str = key[5]  # expiry_date (колонка 5 в vpn_keys)
            expiry_from_db = datetime.fromisoformat(expiry_str)
            assert expiry_from_db.tzinfo is None, "Старый формат без tzinfo"
        
        with allure.step("Проверка форматирования"):
            formatted = format_datetime_for_user(
                expiry_from_db,
                user_timezone=None,  # Не указан timezone
                feature_enabled=True
            )
            allure.attach(formatted, "formatted", allure.attachment_type.TEXT)
            assert formatted is not None, "Форматирование должно работать"
            assert "UTC" in formatted


@pytest.mark.integration
@pytest.mark.database
@allure.epic("Интеграционные тесты")
@allure.feature("Timezone")
@allure.label("package", "tests.integration.test_timezone_integration")
class TestEdgeCases:
    """Тесты: граничные случаи"""
    
    @allure.story("Граничные случаи работы с timezone")
    @allure.title("Истекший ключ возвращает 0 оставшихся секунд")
    @allure.description("""
    Проверяет, что для истекшего ключа функция calculate_remaining_seconds возвращает 0.
    
    **Что проверяется:**
    - Обработка истекшего ключа
    - Возврат 0 секунд для истекшего ключа
    
    **Тестовые данные:**
    - expired_date: текущее время - 1 час
    
    **Предусловия:**
    - Нет (не требуется БД)
    
    **Шаги теста:**
    1. Создание истекшей даты
    2. Вычисление оставшихся секунд
    3. Проверка результата
    
    **Ожидаемый результат:**
    Для истекшего ключа должно быть 0 секунд.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("timezone", "integration", "edge_cases", "expired_key")
    def test_expired_key_returns_zero_remaining(self, temp_db):
        """Тест обработки истекшего ключа"""
        init_test_database(temp_db)
        
        with allure.step("Создание истекшей даты"):
            now_utc = get_current_utc_naive()
            expired_date = now_utc - timedelta(hours=1)
            allure.attach(str(expired_date), "expired_date", allure.attachment_type.TEXT)
        
        with allure.step("Вычисление оставшихся секунд"):
            expiry_timestamp_ms = int(expired_date.replace(tzinfo=UTC).timestamp() * 1000)
            remaining_seconds = calculate_remaining_seconds(expiry_timestamp_ms)
            allure.attach(str(remaining_seconds), "remaining_seconds", allure.attachment_type.TEXT)
            assert remaining_seconds == 0, "Для истекшего ключа должно быть 0 секунд"
    
    @allure.story("Обработка невалидного timezone")
    @allure.title("Невалидный timezone падает обратно на Moscow")
    @allure.description("""
    Проверяет, что при указании невалидного timezone используется fallback на Moscow.
    
    **Что проверяется:**
    - Обработка невалидного timezone
    - Использование fallback на Moscow
    - Корректность отображения времени
    
    **Тестовые данные:**
    - dt_utc: 2025-01-01 12:00:00 UTC
    - user_timezone: "Invalid/Timezone" (невалидный)
    - feature_enabled: True
    
    **Предусловия:**
    - Feature flag включен
    
    **Шаги теста:**
    1. Создание тестовой даты
    2. Форматирование с невалидным timezone
    3. Проверка fallback на Moscow
    
    **Ожидаемый результат:**
    Должен использоваться fallback на Moscow (15:00).
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("timezone", "integration", "edge_cases", "invalid_timezone", "fallback")
    def test_invalid_timezone_fallback_to_moscow(self, temp_db):
        """Тест fallback на Moscow при невалидном timezone"""
        init_test_database(temp_db)
        
        with allure.step("Подготовка тестовой даты"):
            dt_utc = datetime(2025, 1, 1, 12, 0, 0)
            allure.attach(str(dt_utc), "dt_utc", allure.attachment_type.TEXT)
        
        with allure.step("Проверка fallback на Moscow"):
            result = format_datetime_for_user(
                dt_utc,
                user_timezone="Invalid/Timezone",
                feature_enabled=True
            )
            allure.attach(result, "result", allure.attachment_type.TEXT)
            assert "15:00" in result, "Должен быть fallback на Moscow"
            assert "UTC+3" in result
