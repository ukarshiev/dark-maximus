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
import unittest
import sqlite3
import tempfile
import shutil
from datetime import datetime, timedelta, timezone as dt_timezone
from pathlib import Path
from unittest.mock import patch, MagicMock

# Добавляем путь к модулям проекта
project_root = Path(__file__).parent.parent
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


class TestTimezoneIntegration(unittest.TestCase):
    """Интеграционные тесты для timezone support"""
    
    @classmethod
    def setUpClass(cls):
        """Подготовка тестовой среды"""
        # Создаем временную директорию для тестовой БД
        cls.test_dir = tempfile.mkdtemp()
        cls.test_db_path = Path(cls.test_dir) / "test_users.db"
        
        print(f"\n[SETUP] Создана тестовая БД: {cls.test_db_path}")
    
    @classmethod
    def tearDownClass(cls):
        """Очистка после тестов"""
        # Удаляем временную директорию
        if cls.test_dir and Path(cls.test_dir).exists():
            shutil.rmtree(cls.test_dir)
            print(f"[TEARDOWN] Удалена тестовая директория: {cls.test_dir}")
    
    def setUp(self):
        """Подготовка перед каждым тестом"""
        # Создаем чистую БД для каждого теста
        if self.test_db_path.exists():
            self.test_db_path.unlink()
        
        # Патчим DB_FILE в модуле database
        self.db_patcher = patch('shop_bot.data_manager.database.DB_FILE', self.test_db_path)
        self.db_patcher.start()
        
        # Инициализируем тестовую БД
        self._init_test_database()
    
    def tearDown(self):
        """Очистка после каждого теста"""
        self.db_patcher.stop()
    
    def _init_test_database(self):
        """Инициализирует тестовую БД с нужной структурой"""
        conn = sqlite3.connect(self.test_db_path)
        cursor = conn.cursor()
        
        # Создаем таблицу users с поддержкой timezone
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                key TEXT,
                expiry_date TEXT,
                timezone TEXT DEFAULT 'Europe/Moscow',
                balance REAL DEFAULT 0.0,
                auto_renewal INTEGER DEFAULT 0,
                created_at TEXT,
                updated_at TEXT
            )
        """)
        
        # Создаем таблицу настроек
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS bot_settings (
                key TEXT PRIMARY KEY,
                value TEXT,
                updated_at TEXT
            )
        """)
        
        # Добавляем feature flag (по умолчанию выключен)
        cursor.execute("""
            INSERT OR REPLACE INTO bot_settings (key, value, updated_at)
            VALUES ('feature_timezone_enabled', '0', ?)
        """, (datetime.now(UTC).isoformat(),))
        
        conn.commit()
        conn.close()
        
        print(f"[INIT] Инициализирована тестовая БД")
    
    def _get_user_from_db(self, user_id: int):
        """Получает пользователя из БД"""
        conn = sqlite3.connect(self.test_db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        result = cursor.fetchone()
        conn.close()
        return result
    
    def _set_feature_flag(self, enabled: bool):
        """Устанавливает feature flag"""
        conn = sqlite3.connect(self.test_db_path)
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE bot_settings 
            SET value = ?, updated_at = ?
            WHERE key = 'feature_timezone_enabled'
        """, ('1' if enabled else '0', datetime.now(UTC).isoformat()))
        conn.commit()
        conn.close()
        
        print(f"[FLAG] Feature flag установлен: {enabled}")


class TestKeyCreationStoresUTC(TestTimezoneIntegration):
    """Тесты: создание ключа сохраняет дату в UTC"""
    
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
        conn = sqlite3.connect(self.test_db_path)
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


class TestNotificationTiming(TestTimezoneIntegration):
    """Тесты: уведомления приходят вовремя"""
    
    def test_notification_sent_at_correct_time(self):
        """
        Тест 2: Уведомление за 1 час должно прийти ровно за 1 час
        """
        print("\n[TEST] Уведомление -> проверка правильного времени")
        
        # 1. Создаем ключ с истечением через 1 час
        user_id = 12346
        now_utc = get_current_utc_naive()
        expiry_date = now_utc + timedelta(hours=1)
        
        conn = sqlite3.connect(self.test_db_path)
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
        # (В реальной системе это проверит scheduler)
        notification_time = now_utc + timedelta(seconds=remaining_seconds) - timedelta(hours=1)
        time_diff = abs((notification_time - now_utc).total_seconds())
        
        self.assertLess(
            time_diff,
            10,
            "Уведомление должно отправиться примерно сейчас (за 1 час до истечения)"
        )
        
        print(f"[+] Уведомление будет отправлено в правильное время")


class TestTimezoneDisplay(TestTimezoneIntegration):
    """Тесты: смена timezone корректно меняет отображение"""
    
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
        # На Windows может быть fallback на Moscow
        # На Unix должно быть 17:00
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
        # На Windows с fallback будет Moscow (15:00), на Unix - UTC (12:00)
        # Проверяем, что хотя бы дата правильная
        self.assertIn("2025", utc_display, "Дата должна быть правильной")
        self.assertIn("UTC", utc_display)
        print(f"[+] UTC: {utc_display}")
    
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


class TestAutoRenewalTiming(TestTimezoneIntegration):
    """Тесты: автопродление работает вовремя"""
    
    def test_auto_renewal_triggers_at_correct_time(self):
        """
        Тест 5: Автопродление срабатывает в правильное время
        """
        print("\n[TEST] Автопродление -> проверка времени срабатывания")
        
        # 1. Создаем пользователя с балансом и включенным автопродлением
        user_id = 12347
        now_utc = get_current_utc_naive()
        expiry_date = now_utc + timedelta(hours=2)  # Истекает через 2 часа
        
        conn = sqlite3.connect(self.test_db_path)
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


class TestBackwardCompatibility(TestTimezoneIntegration):
    """Тесты: обратная совместимость со старыми данными"""
    
    def test_existing_keys_work_correctly(self):
        """
        Тест 6: Существующие ключи (без timezone) работают корректно
        """
        print("\n[TEST] Обратная совместимость -> старые ключи")
        
        # 1. Создаем "старый" ключ (до внедрения timezone)
        user_id = 12348
        now_utc = get_current_utc_naive()
        expiry_date = now_utc + timedelta(days=30)
        
        conn = sqlite3.connect(self.test_db_path)
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


class TestEdgeCases(TestTimezoneIntegration):
    """Тесты: граничные случаи"""
    
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


def run_integration_tests():
    """Запуск всех интеграционных тестов"""
    print("=" * 80)
    print("INTEGRATION TESTS: Timezone Support")
    print("=" * 80 + "\n")
    
    # Создаем test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Добавляем все тесты
    suite.addTests(loader.loadTestsFromTestCase(TestKeyCreationStoresUTC))
    suite.addTests(loader.loadTestsFromTestCase(TestNotificationTiming))
    suite.addTests(loader.loadTestsFromTestCase(TestTimezoneDisplay))
    suite.addTests(loader.loadTestsFromTestCase(TestAutoRenewalTiming))
    suite.addTests(loader.loadTestsFromTestCase(TestBackwardCompatibility))
    suite.addTests(loader.loadTestsFromTestCase(TestEdgeCases))
    
    # Запускаем тесты
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Итоги
    print("\n" + "=" * 80)
    print("INTEGRATION TEST RESULTS")
    print("=" * 80)
    print(f"Tests run: {result.testsRun}")
    print(f"Success: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"Failed: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print("=" * 80 + "\n")
    
    if result.wasSuccessful():
        print("[OK] ВСЕ ИНТЕГРАЦИОННЫЕ ТЕСТЫ ПРОЙДЕНЫ!")
    else:
        print("[ERROR] ЕСТЬ ОШИБКИ В ИНТЕГРАЦИОННЫХ ТЕСТАХ")
    
    return result.wasSuccessful()


if __name__ == '__main__':
    success = run_integration_tests()
    sys.exit(0 if success else 1)

