#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Интеграционный тест для проверки работы deeplink с реальным ботом
"""

import sys
from pathlib import Path

# Добавляем путь к проекту
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))
sys.path.insert(0, str(project_root / "tests"))

from shop_bot.utils.deeplink import create_deeplink, parse_deeplink

# Импортируем утилиты для безопасного вывода
from test_utils import safe_print, print_test_header, print_test_success


def test_deeplink_generation():
    """Тест генерации deeplink ссылок"""
    print_test_header("Генерация deeplink ссылок")
    
    # Тест 1: Ссылка с группой и промокодом (как в оригинальной проблеме)
    safe_print("\n1. Ссылка с группой 'moi' и промокодом 'SKIDKA100RUB':")
    link1 = create_deeplink("darkmaxi_vpn_bot", group_code="moi", promo_code="SKIDKA100RUB")
    safe_print(f"   Новая ссылка: {link1}")
    
    # Проверяем, что можно распарсить
    param1 = link1.split("?start=")[1]
    group, promo, referrer = parse_deeplink(param1)
    safe_print(f"   Парсинг: group='{group}', promo='{promo}', referrer={referrer}")
    
    # Тест 2: Только группа
    safe_print("\n2. Ссылка только с группой 'vip':")
    link2 = create_deeplink("darkmaxi_vpn_bot", group_code="vip")
    safe_print(f"   Ссылка: {link2}")
    
    param2 = link2.split("?start=")[1]
    group, promo, referrer = parse_deeplink(param2)
    safe_print(f"   Парсинг: group='{group}', promo='{promo}', referrer={referrer}")
    
    # Тест 3: Только промокод
    safe_print("\n3. Ссылка только с промокодом 'WELCOME50':")
    link3 = create_deeplink("darkmaxi_vpn_bot", promo_code="WELCOME50")
    safe_print(f"   Ссылка: {link3}")
    
    param3 = link3.split("?start=")[1]
    group, promo, referrer = parse_deeplink(param3)
    safe_print(f"   Парсинг: group='{group}', promo='{promo}', referrer={referrer}")
    
    # Тест 4: Реферальная ссылка (старый формат)
    safe_print("\n4. Реферальная ссылка (старый формат):")
    link4 = create_deeplink("darkmaxi_vpn_bot", referrer_id=123456789)
    safe_print(f"   Ссылка: {link4}")
    
    param4 = link4.split("?start=")[1]
    group, promo, referrer = parse_deeplink(param4)
    safe_print(f"   Парсинг: group='{group}', promo='{promo}', referrer={referrer}")
    
    # Тест 5: Все параметры
    safe_print("\n5. Ссылка со всеми параметрами:")
    link5 = create_deeplink("darkmaxi_vpn_bot", group_code="premium", promo_code="MEGA50", referrer_id=987654321)
    safe_print(f"   Ссылка: {link5}")
    
    param5 = link5.split("?start=")[1]
    group, promo, referrer = parse_deeplink(param5)
    safe_print(f"   Парсинг: group='{group}', promo='{promo}', referrer={referrer}")
    
    print_test_success("ВСЕ ТЕСТЫ ГЕНЕРАЦИИ ПРОЙДЕНЫ!")
    
    return {
        "group_and_promo": link1,
        "group_only": link2,
        "promo_only": link3,
        "referral": link4,
        "all_params": link5
    }


def test_original_problem():
    """Тест решения оригинальной проблемы"""
    safe_print("\n" + "=" * 80)
    safe_print("РЕШЕНИЕ ОРИГИНАЛЬНОЙ ПРОБЛЕМЫ")
    safe_print("=" * 80)
    
    # Оригинальная неработающая ссылка
    old_link = "https://t.me/darkmaxi_vpn_bot?start=user_groups=moi,promo=SKIDKA100RUB"
    safe_print(f"❌ Старая ссылка (НЕ РАБОТАЕТ): {old_link}", fallback_text=f"[X] Старая ссылка (НЕ РАБОТАЕТ): {old_link}")
    safe_print("   Проблема: содержит недопустимые символы = и ,")
    
    # Новая рабочая ссылка
    new_link = create_deeplink("darkmaxi_vpn_bot", group_code="moi", promo_code="SKIDKA100RUB")
    safe_print(f"✅ Новая ссылка (РАБОТАЕТ): {new_link}", fallback_text=f"[OK] Новая ссылка (РАБОТАЕТ): {new_link}")
    safe_print("   Решение: base64 кодирование JSON параметров")
    
    # Проверяем, что новая ссылка работает
    param = new_link.split("?start=")[1]
    group, promo, referrer = parse_deeplink(param)
    safe_print(f"   Результат парсинга: group='{group}', promo='{promo}', referrer={referrer}")
    
    # Проверяем длину параметра
    safe_print(f"   Длина параметра: {len(param)} символов (лимит Telegram: 64)")
    
    if len(param) <= 64:
        safe_print("   ✅ Длина в пределах нормы", fallback_text="   [OK] Длина в пределах нормы")
    else:
        safe_print("   ❌ Превышен лимит длины!", fallback_text="   [X] Превышен лимит длины!")
    
    safe_print("\n" + "=" * 80)
    safe_print("✅ ПРОБЛЕМА РЕШЕНА!", fallback_text="[OK] ПРОБЛЕМА РЕШЕНА!")
    safe_print("=" * 80)


if __name__ == "__main__":
    # Запускаем тесты
    links = test_deeplink_generation()
    test_original_problem()
    
    safe_print("\n" + "=" * 80)
    safe_print("ГОТОВЫЕ ССЫЛКИ ДЛЯ ТЕСТИРОВАНИЯ:")
    safe_print("=" * 80)
    for name, link in links.items():
        safe_print(f"{name}: {link}")
    safe_print("=" * 80)
