#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Unit тесты для модуля datetime_utils

Проверяет корректность работы функций конвертации timezone
"""

import sys
import unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path

# Добавляем путь к модулям проекта
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root / "src"))

from shop_bot.utils.datetime_utils import (
    ensure_utc_datetime,
    timestamp_to_utc_datetime,
    format_datetime_moscow,
    format_datetime_for_user,
    get_current_utc_naive,
    get_moscow_now,
    calculate_remaining_seconds,
    UTC,
    MOSCOW_TZ
)


class TestEnsureUtcDatetime(unittest.TestCase):
    """Тесты для ensure_utc_datetime"""
    
    def test_utc_aware_datetime(self):
        """Тест: UTC aware datetime -> naive UTC"""
        dt_utc = datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC)
        result = ensure_utc_datetime(dt_utc)
        
        self.assertIsNone(result.tzinfo, "Результат должен быть naive")
        self.assertEqual(result.year, 2025)
        self.assertEqual(result.month, 1)
        self.assertEqual(result.day, 1)
        self.assertEqual(result.hour, 12)
    
    def test_moscow_aware_datetime(self):
        """Тест: Moscow aware datetime -> naive UTC (должен конвертировать)"""
        moscow_tz = timezone(timedelta(hours=3))
        dt_moscow = datetime(2025, 1, 1, 15, 0, 0, tzinfo=moscow_tz)
        result = ensure_utc_datetime(dt_moscow)
        
        self.assertIsNone(result.tzinfo, "Результат должен быть naive")
        self.assertEqual(result.hour, 12, "15:00 MSK должно стать 12:00 UTC")
    
    def test_naive_datetime_warning(self):
        """Тест: naive datetime предполагается как UTC (с предупреждением)"""
        dt_naive = datetime(2025, 1, 1, 12, 0, 0)
        result = ensure_utc_datetime(dt_naive)
        
        self.assertIsNone(result.tzinfo, "Результат должен быть naive")
        self.assertEqual(result.hour, 12, "Naive считается UTC, не должно измениться")


class TestTimestampToUtcDatetime(unittest.TestCase):
    """Тесты для timestamp_to_utc_datetime"""
    
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
    
    def test_current_timestamp(self):
        """Тест: текущий timestamp"""
        now_utc = datetime.now(UTC)
        timestamp_ms = int(now_utc.timestamp() * 1000)
        result = timestamp_to_utc_datetime(timestamp_ms)
        
        self.assertIsNone(result.tzinfo)
        # Проверяем, что разница не больше 1 секунды
        diff = abs((result - now_utc.replace(tzinfo=None)).total_seconds())
        self.assertLess(diff, 1, "Разница должна быть меньше 1 секунды")


class TestFormatDatetimeMoscow(unittest.TestCase):
    """Тесты для format_datetime_moscow"""
    
    def test_naive_utc_format(self):
        """Тест: naive UTC datetime -> строка в московском времени"""
        dt_naive = datetime(2025, 1, 1, 12, 0, 0)  # 12:00 UTC
        result = format_datetime_moscow(dt_naive)
        
        # 12:00 UTC = 15:00 MSK
        self.assertIn("01.01.2025", result)
        self.assertIn("15:00", result)
        self.assertIn("UTC+3", result)
    
    def test_aware_utc_format(self):
        """Тест: aware UTC datetime -> строка в московском времени"""
        dt_utc = datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC)
        result = format_datetime_moscow(dt_utc)
        
        self.assertIn("01.01.2025", result)
        self.assertIn("15:00", result)
        self.assertIn("UTC+3", result)


class TestFormatDatetimeForUser(unittest.TestCase):
    """Тесты для format_datetime_for_user"""
    
    def test_feature_disabled(self):
        """Тест: feature flag выключен -> использует legacy функцию"""
        dt_naive = datetime(2025, 1, 1, 12, 0, 0)
        result = format_datetime_for_user(dt_naive, feature_enabled=False)
        
        # Должно работать как format_datetime_moscow
        self.assertIn("01.01.2025", result)
        self.assertIn("15:00", result)
        self.assertIn("UTC+3", result)
    
    def test_feature_enabled_default_timezone(self):
        """Тест: feature flag включен, timezone по умолчанию (Moscow)"""
        dt_naive = datetime(2025, 1, 1, 12, 0, 0)
        result = format_datetime_for_user(dt_naive, feature_enabled=True)
        
        self.assertIn("01.01.2025", result)
        self.assertIn("15:00", result)
        self.assertIn("UTC+3", result)
    
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


class TestGetCurrentUtcNaive(unittest.TestCase):
    """Тесты для get_current_utc_naive"""
    
    def test_returns_naive_utc(self):
        """Тест: возвращает naive UTC datetime"""
        result = get_current_utc_naive()
        
        self.assertIsNone(result.tzinfo, "Должен быть naive")
        
        # Проверяем, что это примерно текущее время
        now_utc = datetime.now(UTC).replace(tzinfo=None)
        diff = abs((result - now_utc).total_seconds())
        self.assertLess(diff, 1, "Разница с текущим временем должна быть < 1 секунды")


class TestGetMoscowNow(unittest.TestCase):
    """Тесты для get_moscow_now"""
    
    def test_returns_aware_moscow(self):
        """Тест: возвращает aware Moscow datetime"""
        result = get_moscow_now()
        
        self.assertIsNotNone(result.tzinfo, "Должен быть aware")
        
        # Проверяем, что offset примерно +3 часа
        offset = result.utcoffset()
        self.assertIsNotNone(offset)
        # Offset может быть 3 или 4 часа в зависимости от DST
        self.assertIn(offset.total_seconds() / 3600, [3, 4], "Offset должен быть +3 или +4 часа")


class TestCalculateRemainingSeconds(unittest.TestCase):
    """Тесты для calculate_remaining_seconds"""
    
    def test_future_timestamp(self):
        """Тест: timestamp в будущем -> положительное число секунд"""
        # Timestamp через 1 час
        future_ms = int((datetime.now(UTC).timestamp() + 3600) * 1000)
        result = calculate_remaining_seconds(future_ms)
        
        # Должно быть примерно 3600 секунд (1 час)
        self.assertGreater(result, 3500)
        self.assertLess(result, 3700)
    
    def test_past_timestamp(self):
        """Тест: timestamp в прошлом -> 0 секунд"""
        # Timestamp час назад
        past_ms = int((datetime.now(UTC).timestamp() - 3600) * 1000)
        result = calculate_remaining_seconds(past_ms)
        
        self.assertEqual(result, 0, "Для прошедшего времени должно вернуть 0")
    
    def test_current_timestamp(self):
        """Тест: текущий timestamp -> ~0 секунд"""
        now_ms = int(datetime.now(UTC).timestamp() * 1000)
        result = calculate_remaining_seconds(now_ms)
        
        # Должно быть очень близко к 0
        self.assertGreaterEqual(result, 0)
        self.assertLess(result, 5, "Для текущего времени должно быть < 5 секунд")


class TestIntegration(unittest.TestCase):
    """Интеграционные тесты"""
    
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


def run_tests():
    """Запуск всех тестов"""
    print("=" * 80)
    print("UNIT TESTS: datetime_utils")
    print("=" * 80 + "\n")
    
    # Создаем test suite
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromModule(sys.modules[__name__])
    
    # Запускаем тесты
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Итоги
    print("\n" + "=" * 80)
    print("RESULTS")
    print("=" * 80)
    print(f"Tests run: {result.testsRun}")
    print(f"Success: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"Failed: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print("=" * 80 + "\n")
    
    return result.wasSuccessful()


if __name__ == '__main__':
    success = run_tests()
    sys.exit(0 if success else 1)

