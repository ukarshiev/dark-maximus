#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Тест проверки обработки provision_mode при продлении ключа
"""

import sys
from pathlib import Path
from datetime import datetime, timezone, timedelta

# Добавляем путь к проекту
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))
sys.path.insert(0, str(project_root / "tests"))

from shop_bot.config import get_purchase_success_text
from test_utils import safe_print, print_test_header, print_test_success, print_test_failure

def test_get_purchase_success_text_key_mode():
    """Тест формирования сообщения для provision_mode='key'"""
    print_test_header("Формирование сообщения для provision_mode=key")
    
    key_number = 1
    expiry_date = datetime.now(timezone.utc) + timedelta(days=30)
    connection_string = "vless://test-uuid@server.com:443?type=tcp&security=reality"
    subscription_link = None
    provision_mode = 'key'
    
    text = get_purchase_success_text(
        action="продлен",
        key_number=key_number,
        expiry_date=expiry_date,
        connection_string=connection_string,
        subscription_link=subscription_link,
        provision_mode=provision_mode
    )
    
    # Проверяем, что текст содержит ключ
    if connection_string in text:
        safe_print("[OK] Сообщение содержит connection_string (ключ)")
    else:
        safe_print("[FAIL] Сообщение не содержит connection_string")
        print_test_failure("Тест формирования сообщения для key mode не пройден")
        return False
    
    # Проверяем, что текст НЕ содержит подписку
    if subscription_link is None or subscription_link not in text:
        safe_print("[OK] Сообщение не содержит subscription_link")
    else:
        safe_print("[FAIL] Сообщение содержит subscription_link, хотя не должно")
        print_test_failure("Тест формирования сообщения для key mode не пройден")
        return False
    
    # Проверяем наличие информации о продлении
    if "продлен" in text.lower():
        safe_print("[OK] Сообщение содержит информацию о продлении")
    else:
        safe_print("[FAIL] Сообщение не содержит информацию о продлении")
        print_test_failure("Тест формирования сообщения для key mode не пройден")
        return False
    
    print_test_success("Тест формирования сообщения для key mode пройден")
    return True

def test_get_purchase_success_text_subscription_mode():
    """Тест формирования сообщения для provision_mode='subscription'"""
    print_test_header("Формирование сообщения для provision_mode=subscription")
    
    key_number = 2
    expiry_date = datetime.now(timezone.utc) + timedelta(days=30)
    connection_string = None
    subscription_link = "https://serv1.dark-maximus.com/subs/test123"
    provision_mode = 'subscription'
    
    text = get_purchase_success_text(
        action="продлен",
        key_number=key_number,
        expiry_date=expiry_date,
        connection_string=connection_string,
        subscription_link=subscription_link,
        provision_mode=provision_mode
    )
    
    # Проверяем, что текст содержит подписку
    if subscription_link in text:
        safe_print("[OK] Сообщение содержит subscription_link")
    else:
        safe_print("[FAIL] Сообщение не содержит subscription_link")
        print_test_failure("Тест формирования сообщения для subscription mode не пройден")
        return False
    
    # Проверяем, что текст НЕ содержит ключ
    if connection_string is None or connection_string not in text:
        safe_print("[OK] Сообщение не содержит connection_string (ключ)")
    else:
        safe_print("[FAIL] Сообщение содержит connection_string, хотя не должно")
        print_test_failure("Тест формирования сообщения для subscription mode не пройден")
        return False
    
    # Проверяем наличие информации о продлении
    if "продлен" in text.lower():
        safe_print("[OK] Сообщение содержит информацию о продлении")
    else:
        safe_print("[FAIL] Сообщение не содержит информацию о продлении")
        print_test_failure("Тест формирования сообщения для subscription mode не пройден")
        return False
    
    print_test_success("Тест формирования сообщения для subscription mode пройден")
    return True

def test_get_purchase_success_text_both_mode():
    """Тест формирования сообщения для provision_mode='both'"""
    print_test_header("Формирование сообщения для provision_mode=both")
    
    key_number = 3
    expiry_date = datetime.now(timezone.utc) + timedelta(days=30)
    connection_string = "vless://test-uuid@server.com:443?type=tcp&security=reality"
    subscription_link = "https://serv1.dark-maximus.com/subs/test123"
    provision_mode = 'both'
    
    text = get_purchase_success_text(
        action="продлен",
        key_number=key_number,
        expiry_date=expiry_date,
        connection_string=connection_string,
        subscription_link=subscription_link,
        provision_mode=provision_mode
    )
    
    # Проверяем, что текст содержит и ключ, и подписку
    if connection_string in text:
        safe_print("[OK] Сообщение содержит connection_string (ключ)")
    else:
        safe_print("[FAIL] Сообщение не содержит connection_string")
        print_test_failure("Тест формирования сообщения для both mode не пройден")
        return False
    
    if subscription_link in text:
        safe_print("[OK] Сообщение содержит subscription_link")
    else:
        safe_print("[FAIL] Сообщение не содержит subscription_link")
        print_test_failure("Тест формирования сообщения для both mode не пройден")
        return False
    
    print_test_success("Тест формирования сообщения для both mode пройден")
    return True

if __name__ == "__main__":
    safe_print("Запуск тестов обработки provision_mode при продлении\n")
    
    success1 = test_get_purchase_success_text_key_mode()
    success2 = test_get_purchase_success_text_subscription_mode()
    success3 = test_get_purchase_success_text_both_mode()
    
    if success1 and success2 and success3:
        safe_print("\n" + "="*50)
        safe_print("[OK] ВСЕ ТЕСТЫ PROVISION_MODE ПРОЙДЕНЫ УСПЕШНО!")
        safe_print("="*50)
        sys.exit(0)
    else:
        safe_print("\n" + "="*50)
        safe_print("[FAIL] НЕКОТОРЫЕ ТЕСТЫ PROVISION_MODE НЕ ПРОЙДЕНЫ!")
        safe_print("="*50)
        sys.exit(1)

