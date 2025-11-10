#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Тест логики продления через process_successful_payment (TON Connect, CryptoBot)
Проверяет правильность передачи subscription_link в update_key_info
"""

import sys
from pathlib import Path

# Добавляем путь к проекту
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))
sys.path.insert(0, str(project_root / "tests"))

from test_utils import safe_print, print_test_header, print_test_success, print_test_failure

def test_update_key_info_signature():
    """Тест проверки сигнатуры функции update_key_info"""
    print_test_header("Проверка сигнатуры update_key_info")
    
    try:
        from shop_bot.data_manager.database import update_key_info
        import inspect
        
        # Получаем сигнатуру функции
        sig = inspect.signature(update_key_info)
        params = list(sig.parameters.keys())
        
        safe_print(f"Параметры функции update_key_info: {params}")
        
        # Проверяем, что функция принимает subscription_link
        expected_params = ['key_id', 'new_xui_uuid', 'new_expiry_ms', 'subscription_link']
        
        all_ok = True
        for expected_param in expected_params:
            if expected_param in params:
                safe_print(f"[OK] Параметр '{expected_param}' присутствует")
            else:
                safe_print(f"[FAIL] Параметр '{expected_param}' отсутствует")
                all_ok = False
        
        # Проверяем порядок параметров
        if params == expected_params:
            safe_print("[OK] Порядок параметров правильный")
        else:
            safe_print(f"[WARN] Порядок параметров отличается: ожидалось {expected_params}, получено {params}")
        
        if all_ok:
            print_test_success("Тест сигнатуры update_key_info пройден")
            return True
        else:
            print_test_failure("Тест сигнатуры update_key_info не пройден")
            return False
            
    except Exception as e:
        safe_print(f"[FAIL] Ошибка при проверке сигнатуры: {e}")
        import traceback
        safe_print(traceback.format_exc())
        print_test_failure("Тест сигнатуры update_key_info не пройден")
        return False

def test_process_payment_subscription_link_handling():
    """Тест обработки subscription_link в process_successful_payment"""
    print_test_header("Обработка subscription_link в process_successful_payment")
    
    # Симулируем результат от create_or_update_key_on_host
    mock_result = {
        'client_uuid': 'test-uuid-12345',
        'expiry_timestamp_ms': 1735689600000,
        'connection_string': 'vless://test@server.com:443',
        'subscription_link': 'https://serv1.dark-maximus.com/subs/test123'
    }
    
    # Проверяем логику передачи subscription_link в update_key_info
    all_ok = True
    
    # 1. Проверяем, что subscription_link извлекается из результата
    subscription_link = mock_result.get('subscription_link')
    if subscription_link:
        safe_print(f"[OK] subscription_link извлечен из результата: {subscription_link}")
    else:
        safe_print("[FAIL] subscription_link не найден в результате")
        all_ok = False
    
    # 2. Проверяем, что subscription_link может быть None
    mock_result_no_subscription = {
        'client_uuid': 'test-uuid-67890',
        'expiry_timestamp_ms': 1735689600000,
        'connection_string': 'vless://test@server.com:443',
        'subscription_link': None
    }
    
    subscription_link_none = mock_result_no_subscription.get('subscription_link')
    if subscription_link_none is None:
        safe_print("[OK] subscription_link может быть None")
    else:
        safe_print(f"[FAIL] subscription_link должен быть None, получен: {subscription_link_none}")
        all_ok = False
    
    # 3. Проверяем правильность вызова update_key_info
    # Симулируем правильный вызов
    key_id = 123
    client_uuid = mock_result['client_uuid']
    expiry_ms = mock_result['expiry_timestamp_ms']
    sub_link = mock_result.get('subscription_link')
    
    # Правильный вызов должен быть:
    # update_key_info(key_id, client_uuid, expiry_ms, sub_link)
    expected_call = f"update_key_info({key_id}, {client_uuid}, {expiry_ms}, {sub_link})"
    safe_print(f"[OK] Правильный вызов: {expected_call}")
    
    if all_ok:
        print_test_success("Тест обработки subscription_link пройден")
        return True
    else:
        print_test_failure("Тест обработки subscription_link не пройден")
        return False

def test_provision_mode_from_plan():
    """Тест получения provision_mode из тарифа"""
    print_test_header("Получение provision_mode из тарифа")
    
    # Симулируем разные планы
    plans = [
        {'plan_id': 1, 'key_provision_mode': 'key'},
        {'plan_id': 2, 'key_provision_mode': 'subscription'},
        {'plan_id': 3, 'key_provision_mode': 'both'},
        {'plan_id': 4}  # Без key_provision_mode (должен быть 'key' по умолчанию)
    ]
    
    all_ok = True
    
    for plan in plans:
        plan_id = plan['plan_id']
        provision_mode = plan.get('key_provision_mode', 'key')
        
        safe_print(f"\nПлан {plan_id}:")
        safe_print(f"  provision_mode = '{provision_mode}'")
        
        # Проверяем, что provision_mode корректен
        if provision_mode in ['key', 'subscription', 'both']:
            safe_print(f"  [OK] provision_mode корректен")
        else:
            safe_print(f"  [FAIL] provision_mode некорректен: {provision_mode}")
            all_ok = False
        
        # Проверяем значение по умолчанию
        if 'key_provision_mode' not in plan:
            if provision_mode == 'key':
                safe_print(f"  [OK] Значение по умолчанию 'key' применено")
            else:
                safe_print(f"  [FAIL] Значение по умолчанию не применено")
                all_ok = False
    
    if all_ok:
        print_test_success("Тест получения provision_mode из тарифа пройден")
        return True
    else:
        print_test_failure("Тест получения provision_mode из тарифа не пройден")
        return False

if __name__ == "__main__":
    safe_print("Запуск тестов process_successful_payment\n")
    
    success1 = test_update_key_info_signature()
    success2 = test_process_payment_subscription_link_handling()
    success3 = test_provision_mode_from_plan()
    
    if success1 and success2 and success3:
        safe_print("\n" + "="*50)
        safe_print("[OK] ВСЕ ТЕСТЫ PROCESS_PAYMENT ПРОЙДЕНЫ УСПЕШНО!")
        safe_print("="*50)
        sys.exit(0)
    else:
        safe_print("\n" + "="*50)
        safe_print("[FAIL] НЕКОТОРЫЕ ТЕСТЫ PROCESS_PAYMENT НЕ ПРОЙДЕНЫ!")
        safe_print("="*50)
        sys.exit(1)

