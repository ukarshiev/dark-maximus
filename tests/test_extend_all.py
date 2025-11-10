#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Запуск всех тестов продления ключей с подпиской
"""

import sys
from pathlib import Path

# Добавляем путь к проекту
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))
sys.path.insert(0, str(project_root / "tests"))

from test_utils import safe_print, print_test_header, print_test_success, print_test_failure

def run_all_tests():
    """Запускает все тесты продления ключей"""
    print_test_header("ЗАПУСК ВСЕХ ТЕСТОВ ПРОДЛЕНИЯ КЛЮЧЕЙ")
    
    results = {}
    
    # Тесты клавиатуры
    safe_print("\n" + "="*60)
    safe_print("ТЕСТЫ КЛАВИАТУРЫ")
    safe_print("="*60 + "\n")
    try:
        from test_extend_keyboard import (
            test_keyboard_with_subscription_link,
            test_keyboard_without_subscription_link,
            test_keyboard_http_to_https_conversion
        )
        results['keyboard_subscription'] = test_keyboard_with_subscription_link()
        results['keyboard_no_subscription'] = test_keyboard_without_subscription_link()
        results['keyboard_http_https'] = test_keyboard_http_to_https_conversion()
    except Exception as e:
        safe_print(f"[FAIL] Ошибка при запуске тестов клавиатуры: {e}")
        results['keyboard_subscription'] = False
        results['keyboard_no_subscription'] = False
        results['keyboard_http_https'] = False
    
    # Тесты БД
    safe_print("\n" + "="*60)
    safe_print("ТЕСТЫ БАЗЫ ДАННЫХ")
    safe_print("="*60 + "\n")
    try:
        from test_extend_db_subscription_link import (
            test_update_key_info_with_subscription_link,
            test_update_key_info_without_subscription_link
        )
        results['db_with_subscription'] = test_update_key_info_with_subscription_link()
        results['db_without_subscription'] = test_update_key_info_without_subscription_link()
    except Exception as e:
        safe_print(f"[FAIL] Ошибка при запуске тестов БД: {e}")
        results['db_with_subscription'] = False
        results['db_without_subscription'] = False
    
    # Тесты provision_mode
    safe_print("\n" + "="*60)
    safe_print("ТЕСТЫ PROVISION_MODE")
    safe_print("="*60 + "\n")
    try:
        from test_extend_provision_mode import (
            test_get_purchase_success_text_key_mode,
            test_get_purchase_success_text_subscription_mode,
            test_get_purchase_success_text_both_mode
        )
        results['provision_key'] = test_get_purchase_success_text_key_mode()
        results['provision_subscription'] = test_get_purchase_success_text_subscription_mode()
        results['provision_both'] = test_get_purchase_success_text_both_mode()
    except Exception as e:
        safe_print(f"[FAIL] Ошибка при запуске тестов provision_mode: {e}")
        results['provision_key'] = False
        results['provision_subscription'] = False
        results['provision_both'] = False
    
    # Тесты логики YooKassa
    safe_print("\n" + "="*60)
    safe_print("ТЕСТЫ ЛОГИКИ YOOKASSA")
    safe_print("="*60 + "\n")
    try:
        from test_extend_yookassa_logic import (
            test_extend_logic_key_mode,
            test_extend_logic_subscription_mode,
            test_extend_logic_both_mode
        )
        results['yookassa_key'] = test_extend_logic_key_mode()
        results['yookassa_subscription'] = test_extend_logic_subscription_mode()
        results['yookassa_both'] = test_extend_logic_both_mode()
    except Exception as e:
        safe_print(f"[FAIL] Ошибка при запуске тестов логики YooKassa: {e}")
        results['yookassa_key'] = False
        results['yookassa_subscription'] = False
        results['yookassa_both'] = False
    
    # Тесты process_successful_payment
    safe_print("\n" + "="*60)
    safe_print("ТЕСТЫ PROCESS_SUCCESSFUL_PAYMENT")
    safe_print("="*60 + "\n")
    try:
        from test_extend_process_payment import (
            test_update_key_info_signature,
            test_process_payment_subscription_link_handling,
            test_provision_mode_from_plan
        )
        results['process_signature'] = test_update_key_info_signature()
        results['process_subscription'] = test_process_payment_subscription_link_handling()
        results['process_provision'] = test_provision_mode_from_plan()
    except Exception as e:
        safe_print(f"[FAIL] Ошибка при запуске тестов process_payment: {e}")
        results['process_signature'] = False
        results['process_subscription'] = False
        results['process_provision'] = False
    
    # Итоговая статистика
    safe_print("\n" + "="*60)
    safe_print("ИТОГОВАЯ СТАТИСТИКА")
    safe_print("="*60 + "\n")
    
    total = len(results)
    passed = sum(1 for v in results.values() if v)
    failed = total - passed
    
    safe_print(f"Всего тестов: {total}")
    safe_print(f"Пройдено: {passed}")
    safe_print(f"Провалено: {failed}")
    
    safe_print("\nДетализация:")
    for test_name, result in results.items():
        status = "[OK]" if result else "[FAIL]"
        safe_print(f"  {status} {test_name}")
    
    if failed == 0:
        print_test_success("ВСЕ ТЕСТЫ ПРОЙДЕНЫ УСПЕШНО!")
        return True
    else:
        print_test_failure(f"ПРОВАЛЕНО {failed} ИЗ {total} ТЕСТОВ")
        return False

if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)

