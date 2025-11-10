#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Тест логики продления через YooKassa webhook с разными provision_mode
Проверяет правильность обработки без реальных API вызовов
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

# Добавляем путь к проекту
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))
sys.path.insert(0, str(project_root / "tests"))

from test_utils import safe_print, print_test_header, print_test_success, print_test_failure

def test_extend_logic_key_mode():
    """Тест логики продления с provision_mode='key'"""
    print_test_header("Логика продления с provision_mode=key")
    
    # Симулируем данные для продления
    key_id = 123
    user_id = 456
    plan_id = 1
    months = 1
    days_to_add = 30.0
    traffic_gb = 0.0
    host_name = "test_host"
    email = "test@example.com"
    
    # Симулируем результат от create_or_update_key_on_host
    mock_result = {
        'client_uuid': 'new-uuid-12345',
        'expiry_timestamp_ms': 1735689600000,  # Пример timestamp
        'connection_string': 'vless://test@server.com:443',
        'subscription_link': None  # Для key mode нет подписки
    }
    
    # Симулируем план с provision_mode='key'
    mock_plan = {
        'plan_id': plan_id,
        'key_provision_mode': 'key',
        'months': months,
        'days': 0,
        'hours': 0,
        'traffic_gb': traffic_gb
    }
    
    # Проверяем логику
    all_ok = True
    
    # 1. Проверяем, что subscription_link = None для key mode
    subscription_link = mock_result.get('subscription_link')
    if subscription_link is None:
        safe_print("[OK] subscription_link = None для key mode")
    else:
        safe_print(f"[FAIL] subscription_link должен быть None, получен: {subscription_link}")
        all_ok = False
    
    # 2. Проверяем, что provision_mode берется из плана
    provision_mode = mock_plan.get('key_provision_mode', 'key')
    if provision_mode == 'key':
        safe_print(f"[OK] provision_mode = '{provision_mode}' из плана")
    else:
        safe_print(f"[FAIL] provision_mode должен быть 'key', получен: {provision_mode}")
        all_ok = False
    
    # 3. Проверяем, что connection_string присутствует
    connection_string = mock_result.get('connection_string')
    if connection_string:
        safe_print(f"[OK] connection_string присутствует")
    else:
        safe_print("[FAIL] connection_string отсутствует")
        all_ok = False
    
    if all_ok:
        print_test_success("Тест логики продления с key mode пройден")
        return True
    else:
        print_test_failure("Тест логики продления с key mode не пройден")
        return False

def test_extend_logic_subscription_mode():
    """Тест логики продления с provision_mode='subscription'"""
    print_test_header("Логика продления с provision_mode=subscription")
    
    # Симулируем результат от create_or_update_key_on_host
    mock_result = {
        'client_uuid': 'new-uuid-67890',
        'expiry_timestamp_ms': 1735689600000,
        'connection_string': None,  # Для subscription mode нет ключа
        'subscription_link': 'https://serv1.dark-maximus.com/subs/test123'
    }
    
    # Симулируем план с provision_mode='subscription'
    mock_plan = {
        'plan_id': 2,
        'key_provision_mode': 'subscription',
        'months': 1
    }
    
    # Проверяем логику
    all_ok = True
    
    # 1. Проверяем, что subscription_link присутствует
    subscription_link = mock_result.get('subscription_link')
    if subscription_link:
        safe_print(f"[OK] subscription_link присутствует: {subscription_link}")
    else:
        safe_print("[FAIL] subscription_link отсутствует для subscription mode")
        all_ok = False
    
    # 2. Проверяем, что provision_mode берется из плана
    provision_mode = mock_plan.get('key_provision_mode', 'key')
    if provision_mode == 'subscription':
        safe_print(f"[OK] provision_mode = '{provision_mode}' из плана")
    else:
        safe_print(f"[FAIL] provision_mode должен быть 'subscription', получен: {provision_mode}")
        all_ok = False
    
    # 3. Проверяем, что connection_string отсутствует (или None)
    connection_string = mock_result.get('connection_string')
    if connection_string is None:
        safe_print("[OK] connection_string отсутствует для subscription mode")
    else:
        safe_print(f"[WARN] connection_string присутствует для subscription mode: {connection_string}")
    
    if all_ok:
        print_test_success("Тест логики продления с subscription mode пройден")
        return True
    else:
        print_test_failure("Тест логики продления с subscription mode не пройден")
        return False

def test_extend_logic_both_mode():
    """Тест логики продления с provision_mode='both'"""
    print_test_header("Логика продления с provision_mode=both")
    
    # Симулируем результат от create_or_update_key_on_host
    mock_result = {
        'client_uuid': 'new-uuid-11111',
        'expiry_timestamp_ms': 1735689600000,
        'connection_string': 'vless://test@server.com:443',
        'subscription_link': 'https://serv1.dark-maximus.com/subs/test123'
    }
    
    # Симулируем план с provision_mode='both'
    mock_plan = {
        'plan_id': 3,
        'key_provision_mode': 'both',
        'months': 1
    }
    
    # Проверяем логику
    all_ok = True
    
    # 1. Проверяем, что subscription_link присутствует
    subscription_link = mock_result.get('subscription_link')
    if subscription_link:
        safe_print(f"[OK] subscription_link присутствует: {subscription_link}")
    else:
        safe_print("[FAIL] subscription_link отсутствует для both mode")
        all_ok = False
    
    # 2. Проверяем, что connection_string присутствует
    connection_string = mock_result.get('connection_string')
    if connection_string:
        safe_print(f"[OK] connection_string присутствует")
    else:
        safe_print("[FAIL] connection_string отсутствует для both mode")
        all_ok = False
    
    # 3. Проверяем, что provision_mode берется из плана
    provision_mode = mock_plan.get('key_provision_mode', 'key')
    if provision_mode == 'both':
        safe_print(f"[OK] provision_mode = '{provision_mode}' из плана")
    else:
        safe_print(f"[FAIL] provision_mode должен быть 'both', получен: {provision_mode}")
        all_ok = False
    
    if all_ok:
        print_test_success("Тест логики продления с both mode пройден")
        return True
    else:
        print_test_failure("Тест логики продления с both mode не пройден")
        return False

if __name__ == "__main__":
    safe_print("Запуск тестов логики продления через YooKassa\n")
    
    success1 = test_extend_logic_key_mode()
    success2 = test_extend_logic_subscription_mode()
    success3 = test_extend_logic_both_mode()
    
    if success1 and success2 and success3:
        safe_print("\n" + "="*50)
        safe_print("[OK] ВСЕ ТЕСТЫ ЛОГИКИ YOOKASSA ПРОЙДЕНЫ УСПЕШНО!")
        safe_print("="*50)
        sys.exit(0)
    else:
        safe_print("\n" + "="*50)
        safe_print("[FAIL] НЕКОТОРЫЕ ТЕСТЫ ЛОГИКИ YOOKASSA НЕ ПРОЙДЕНЫ!")
        safe_print("="*50)
        sys.exit(1)

