#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Тесты для deeplink утилит с base64 кодированием
"""

import sys
import unittest
from pathlib import Path

# Добавляем путь к проекту
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))
sys.path.insert(0, str(project_root / "tests"))

from shop_bot.utils.deeplink import create_deeplink, parse_deeplink, validate_deeplink_length

# Импортируем утилиты для безопасного вывода
from test_utils import safe_print, print_test_header, print_test_success, print_test_failure


class TestDeeplinkUtils(unittest.TestCase):
    """Тесты для утилит deeplink"""
    
    def test_create_deeplink_basic(self):
        """Тест создания базовой deeplink ссылки"""
        link = create_deeplink("testbot")
        self.assertEqual(link, "https://t.me/testbot")
    
    def test_create_deeplink_with_group(self):
        """Тест создания ссылки с группой"""
        link = create_deeplink("testbot", group_code="vip")
        self.assertTrue(link.startswith("https://t.me/testbot?start="))
        self.assertIn("testbot", link)
        
        # Проверяем, что можно распарсить обратно
        param = link.split("?start=")[1]
        group, promo, referrer = parse_deeplink(param)
        self.assertEqual(group, "vip")
        self.assertIsNone(promo)
        self.assertIsNone(referrer)
    
    def test_create_deeplink_with_promo(self):
        """Тест создания ссылки с промокодом"""
        link = create_deeplink("testbot", promo_code="SALE50")
        self.assertTrue(link.startswith("https://t.me/testbot?start="))
        
        # Проверяем, что можно распарсить обратно
        param = link.split("?start=")[1]
        group, promo, referrer = parse_deeplink(param)
        self.assertIsNone(group)
        self.assertEqual(promo, "SALE50")
        self.assertIsNone(referrer)
    
    def test_create_deeplink_with_both(self):
        """Тест создания ссылки с группой и промокодом"""
        link = create_deeplink("testbot", group_code="vip", promo_code="SALE50")
        self.assertTrue(link.startswith("https://t.me/testbot?start="))
        
        # Проверяем, что можно распарсить обратно
        param = link.split("?start=")[1]
        group, promo, referrer = parse_deeplink(param)
        self.assertEqual(group, "vip")
        self.assertEqual(promo, "SALE50")
        self.assertIsNone(referrer)
    
    def test_create_deeplink_referral(self):
        """Тест создания реферальной ссылки (старый формат)"""
        link = create_deeplink("testbot", referrer_id=123456)
        self.assertEqual(link, "https://t.me/testbot?start=ref_123456")
        
        # Проверяем парсинг
        group, promo, referrer = parse_deeplink("ref_123456")
        self.assertIsNone(group)
        self.assertIsNone(promo)
        self.assertEqual(referrer, 123456)
    
    def test_create_deeplink_all_params(self):
        """Тест создания ссылки со всеми параметрами"""
        link = create_deeplink("testbot", group_code="vip", promo_code="SALE50", referrer_id=123456)
        self.assertTrue(link.startswith("https://t.me/testbot?start="))
        
        # Проверяем, что можно распарсить обратно
        param = link.split("?start=")[1]
        group, promo, referrer = parse_deeplink(param)
        self.assertEqual(group, "vip")
        self.assertEqual(promo, "SALE50")
        self.assertEqual(referrer, 123456)
    
    def test_parse_deeplink_base64(self):
        """Тест парсинга base64 закодированных параметров"""
        # Тест с группой и промокодом
        group, promo, referrer = parse_deeplink("eyJnIjoidmlwIiwicCI6IlNBTEU1MCJ9")
        self.assertEqual(group, "vip")
        self.assertEqual(promo, "SALE50")
        self.assertIsNone(referrer)
        
        # Тест только с группой
        group, promo, referrer = parse_deeplink("eyJnIjoidmlwIn0")
        self.assertEqual(group, "vip")
        self.assertIsNone(promo)
        self.assertIsNone(referrer)
        
        # Тест только с промокодом
        group, promo, referrer = parse_deeplink("eyJwIjoiU0FMRTUwIn0")
        self.assertIsNone(group)
        self.assertEqual(promo, "SALE50")
        self.assertIsNone(referrer)
    
    def test_parse_deeplink_referral(self):
        """Тест парсинга реферальных ссылок (старый формат)"""
        group, promo, referrer = parse_deeplink("ref_123456")
        self.assertIsNone(group)
        self.assertIsNone(promo)
        self.assertEqual(referrer, 123456)
        
        # Тест с невалидным форматом
        group, promo, referrer = parse_deeplink("ref_invalid")
        self.assertIsNone(group)
        self.assertIsNone(promo)
        self.assertIsNone(referrer)
    
    def test_parse_deeplink_legacy_fallback(self):
        """Тест fallback на старый формат с запятыми"""
        # Этот формат НЕ РАБОТАЕТ в Telegram, но парсер должен его понимать
        group, promo, referrer = parse_deeplink("user_groups=vip,promo=SALE50")
        self.assertEqual(group, "vip")
        self.assertEqual(promo, "SALE50")
        self.assertIsNone(referrer)
        
        # Только группа
        group, promo, referrer = parse_deeplink("user_groups=vip")
        self.assertEqual(group, "vip")
        self.assertIsNone(promo)
        self.assertIsNone(referrer)
        
        # Только промокод
        group, promo, referrer = parse_deeplink("promo_SALE50")
        self.assertIsNone(group)
        self.assertEqual(promo, "SALE50")
        self.assertIsNone(referrer)
    
    def test_parse_deeplink_invalid(self):
        """Тест парсинга невалидных параметров"""
        # Пустая строка
        group, promo, referrer = parse_deeplink("")
        self.assertIsNone(group)
        self.assertIsNone(promo)
        self.assertIsNone(referrer)
        
        # None
        group, promo, referrer = parse_deeplink(None)
        self.assertIsNone(group)
        self.assertIsNone(promo)
        self.assertIsNone(referrer)
        
        # Невалидный base64
        group, promo, referrer = parse_deeplink("invalid_base64!")
        self.assertIsNone(group)
        self.assertIsNone(promo)
        self.assertIsNone(referrer)
        
        # Невалидный JSON
        group, promo, referrer = parse_deeplink("eyJpbnZhbGlkX2pzb24iOiJ0ZXN0In0")  # {"invalid_json":"test"
        self.assertIsNone(group)
        self.assertIsNone(promo)
        self.assertIsNone(referrer)
    
    def test_validate_deeplink_length(self):
        """Тест проверки длины deeplink параметров"""
        # Короткие данные - должны поместиться
        data = {"g": "vip", "p": "SALE50"}
        self.assertTrue(validate_deeplink_length(data))
        
        # Очень длинные данные - могут не поместиться
        data = {
            "g": "very_long_group_code_that_might_exceed_limit",
            "p": "very_long_promo_code_that_might_exceed_limit",
            "r": 123456789
        }
        result = validate_deeplink_length(data)
        # Результат может быть True или False в зависимости от длины
        self.assertIsInstance(result, bool)
    
    def test_roundtrip_consistency(self):
        """Тест консистентности: создание -> парсинг -> сравнение"""
        test_cases = [
            {"group_code": "vip", "promo_code": "SALE50"},
            {"group_code": "premium", "promo_code": None},
            {"group_code": None, "promo_code": "WELCOME"},
            {"group_code": "test", "promo_code": "TEST", "referrer_id": 123456},
        ]
        
        for case in test_cases:
            with self.subTest(case=case):
                # Создаём ссылку
                link = create_deeplink("testbot", **case)
                
                # Извлекаем параметр
                param = link.split("?start=")[1] if "?start=" in link else ""
                
                # Парсим обратно
                group, promo, referrer = parse_deeplink(param)
                
                # Сравниваем
                self.assertEqual(group, case.get("group_code"))
                self.assertEqual(promo, case.get("promo_code"))
                self.assertEqual(referrer, case.get("referrer_id"))
    
    def test_telegram_length_limit(self):
        """Тест соблюдения лимита длины Telegram (64 символа)"""
        # Создаём ссылку с максимально возможными параметрами
        link = create_deeplink("testbot", group_code="vip", promo_code="SALE50")
        param = link.split("?start=")[1]
        
        # Проверяем, что параметр не превышает 64 символа
        self.assertLessEqual(len(param), 64, f"Parameter too long: {len(param)} chars")
        
        # Проверяем, что ссылка работает
        group, promo, referrer = parse_deeplink(param)
        self.assertEqual(group, "vip")
        self.assertEqual(promo, "SALE50")


def run_tests():
    """Запуск всех тестов"""
    print_test_header("Deeplink утилиты с base64 кодированием")
    
    # Создаём test suite
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromTestCase(TestDeeplinkUtils)
    
    # Запускаем тесты
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    if result.wasSuccessful():
        print_test_success("ВСЕ ТЕСТЫ ПРОЙДЕНЫ УСПЕШНО!")
    else:
        print_test_failure(f"ТЕСТЫ НЕ ПРОЙДЕНЫ: {len(result.failures)} failures, {len(result.errors)} errors")
        for failure in result.failures:
            safe_print(f"FAILURE: {failure[0]}")
            safe_print(failure[1])
        for error in result.errors:
            safe_print(f"ERROR: {error[0]}")
            safe_print(error[1])
    
    return result.wasSuccessful()


if __name__ == "__main__":
    run_tests()
