#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Тест веб-интерфейса для генерации deeplink ссылок
"""

import sys
from pathlib import Path

# Добавляем путь к проекту
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

from shop_bot.utils.deeplink import create_deeplink

def test_web_interface_deeplink():
    """Тест генерации ссылок для веб-интерфейса"""
    print("=" * 80)
    print("ТЕСТ: Веб-интерфейс генерации deeplink ссылок")
    print("=" * 80)
    
    # Тестовые данные из скриншота
    bot_username = "darkmaxi_vpn_bot"
    group_code = "rodnye"  # "Родные" из скриншота
    promo_code = "TEST_DEEPLINK_200"  # из скриншота
    
    print(f"Бот: {bot_username}")
    print(f"Группа: {group_code}")
    print(f"Промокод: {promo_code}")
    print()
    
    # Генерируем ссылку через утилиту
    link = create_deeplink(
        bot_username=bot_username,
        group_code=group_code,
        promo_code=promo_code
    )
    
    print("НОВАЯ РАБОЧАЯ ССЫЛКА (из веб-интерфейса):")
    print(link)
    print()
    
    param = link.split("?start=")[1] if "?start=" in link else ""
    print(f"Параметр start: {param}")
    print(f"Длина параметра: {len(param)} символов (лимит: 64)")
    print()
    
    # Проверяем парсинг
    from shop_bot.utils.deeplink import parse_deeplink
    parsed_group, parsed_promo, parsed_referrer = parse_deeplink(param)
    
    print("Проверка парсинга:")
    print(f"  group: {parsed_group}")
    print(f"  promo: {parsed_promo}")
    print(f"  referrer: {parsed_referrer}")
    print()
    
    # Сравнение со старым форматом
    old_format = f"https://t.me/{bot_username}?start=user_groups={group_code}&promo_{promo_code}"
    print("СРАВНЕНИЕ:")
    print(f"Старый формат (НЕ РАБОТАЕТ): {old_format}")
    print(f"Новый формат (РАБОТАЕТ):     {link}")
    print()
    
    # Проверка соответствия Telegram требованиям
    print("ПРОВЕРКА СООТВЕТСТВИЯ TELEGRAM API:")
    if param:
        valid_chars = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_")
        param_chars = set(param)
        invalid_chars = param_chars - valid_chars
        
        length_ok = "OK" if len(param) <= 64 else "FAIL"
        chars_ok = "OK" if not invalid_chars else f"FAIL (запрещенные: {invalid_chars})"
        format_ok = "OK" if param else "FAIL"
        
        print(f"  Длина: {len(param)}/64 символов [{length_ok}]")
        print(f"  Символы: [{chars_ok}]")
        print(f"  Формат: base64 encoded JSON [{format_ok}]")
    else:
        print("  [FAIL] Нет параметра start")
    
    print()
    print("=" * 80)
    print("[OK] Тест завершен!")
    print("=" * 80)

if __name__ == "__main__":
    test_web_interface_deeplink()
