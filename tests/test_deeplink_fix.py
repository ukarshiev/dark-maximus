#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Тест исправления deeplink с промокодами
"""

import base64
import json
import sys
import os

# Добавляем корневую папку проекта в путь
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.shop_bot.utils.deeplink import create_deeplink, parse_deeplink

def test_deeplink_creation():
    """Тест создания deeplink с промокодом"""
    print("=== Тест создания deeplink ===")
    
    # Создаём deeplink с промокодом SKIDKA100RUB
    link = create_deeplink("darkmaxi_vpn_bot", promo_code="SKIDKA100RUB")
    print(f"Созданная ссылка: {link}")
    
    # Извлекаем параметр start
    start_param = link.split("start=")[1] if "start=" in link else None
    print(f"Параметр start: {start_param}")
    
    # Парсим параметр
    group_code, promo_code, referrer_id = parse_deeplink(start_param)
    print(f"Распарсенные данные: group={group_code}, promo={promo_code}, referrer={referrer_id}")
    
    # Проверяем, что промокод правильно извлекается
    assert promo_code == "SKIDKA100RUB", f"Ожидался SKIDKA100RUB, получен {promo_code}"
    print("[OK] Промокод правильно извлекается из deeplink")
    
    return link

def test_original_deeplink():
    """Тест оригинальной ссылки из проблемы"""
    print("\n=== Тест оригинальной ссылки ===")
    
    original_param = "eyJwIjoiU0tJREtBMTAwUlVCIn0"
    print(f"Оригинальный параметр: {original_param}")
    
    # Парсим оригинальный параметр
    group_code, promo_code, referrer_id = parse_deeplink(original_param)
    print(f"Распарсенные данные: group={group_code}, promo={promo_code}, referrer={referrer_id}")
    
    # Проверяем, что промокод правильно извлекается
    assert promo_code == "SKIDKA100RUB", f"Ожидался SKIDKA100RUB, получен {promo_code}"
    print("[OK] Оригинальная ссылка правильно парсится")
    
    return f"https://t.me/darkmaxi_vpn_bot?start={original_param}"

if __name__ == "__main__":
    print("Тестирование исправления deeplink с промокодами")
    print("=" * 50)
    
    try:
        # Тест создания новой ссылки
        new_link = test_deeplink_creation()
        
        # Тест оригинальной ссылки
        original_link = test_original_deeplink()
        
        print("\n=== Результаты ===")
        print(f"Новая ссылка: {new_link}")
        print(f"Оригинальная ссылка: {original_link}")
        print("\n[OK] Все тесты прошли успешно!")
        print("\nТеперь можно протестировать ссылки в реальном боте:")
        print(f"1. {original_link}")
        print(f"2. {new_link}")
        
    except Exception as e:
        print(f"[ERROR] Ошибка в тестах: {e}")
        import traceback
        traceback.print_exc()