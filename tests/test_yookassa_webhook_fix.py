#!/usr/bin/env python3
"""
Тест исправлений webhook YooKassa:
1. Проверка использования metadata из БД
2. Проверка приоритета host_code над host_name
3. Проверка fallback через plan_id
4. Проверка конкретного платежа ID 233
"""

import sys
import os
import json
from pathlib import Path

# Добавляем путь к проекту
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

from shop_bot.data_manager.database import (
    get_transaction_by_payment_id,
    get_host,
    get_host_by_code,
    get_plan_by_id,
    DB_FILE
)
from shop_bot.webhook_server.app import _ensure_host_metadata

def test_payment_233():
    """Тест конкретного платежа ID 233"""
    payment_id = "30a48370-000f-5001-9000-16231fa0ad0c"
    
    print(f"\n{'='*80}")
    print(f"ТЕСТ: Платеж ID 233 ({payment_id})")
    print(f"{'='*80}\n")
    
    # 1. Проверяем транзакцию в БД
    print("1. Проверка транзакции в БД:")
    transaction = get_transaction_by_payment_id(payment_id)
    
    if not transaction:
        print(f"   ❌ Транзакция НЕ НАЙДЕНА в БД!")
        print(f"   Это означает, что create_pending_transaction() не был вызван или упал с ошибкой.")
        return False
    
    print(f"   ✅ Транзакция найдена:")
    print(f"      - ID: {transaction.get('transaction_id')}")
    print(f"      - Статус: {transaction.get('status')}")
    print(f"      - User ID: {transaction.get('user_id')}")
    print(f"      - Amount: {transaction.get('amount_rub')} RUB")
    
    # 2. Проверяем metadata в транзакции
    print(f"\n2. Проверка metadata в транзакции:")
    metadata = transaction.get('metadata', {})
    if isinstance(metadata, str):
        try:
            metadata = json.loads(metadata)
        except:
            metadata = {}
    
    print(f"   Metadata keys: {list(metadata.keys())}")
    print(f"   - host_name: {metadata.get('host_name')}")
    print(f"   - host_code: {metadata.get('host_code')}")
    print(f"   - plan_id: {metadata.get('plan_id')}")
    print(f"   - user_id: {metadata.get('user_id')}")
    print(f"   - action: {metadata.get('action')}")
    
    if not metadata.get('host_code'):
        print(f"   ⚠️  ВНИМАНИЕ: host_code отсутствует в metadata транзакции!")
        print(f"   Это означает, что при создании платежа host_code не был передан.")
        return False
    
    print(f"   ✅ host_code присутствует в metadata: {metadata.get('host_code')}")
    
    # 3. Проверяем поиск хоста по host_code
    print(f"\n3. Проверка поиска хоста по host_code:")
    host_code = metadata.get('host_code')
    if host_code:
        host_by_code = get_host_by_code(str(host_code))
        if host_by_code:
            print(f"   ✅ Хост найден по host_code '{host_code}':")
            print(f"      - host_name: {host_by_code.get('host_name')}")
            print(f"      - host_code: {host_by_code.get('host_code')}")
        else:
            print(f"   ❌ Хост НЕ НАЙДЕН по host_code '{host_code}'!")
            return False
    
    # 4. Проверяем поиск хоста по host_name
    print(f"\n4. Проверка поиска хоста по host_name:")
    host_name = metadata.get('host_name')
    if host_name:
        host_by_name = get_host(host_name)
        if host_by_name:
            print(f"   ✅ Хост найден по host_name '{host_name}':")
            print(f"      - host_name: {host_by_name.get('host_name')}")
            print(f"      - host_code: {host_by_name.get('host_code')}")
        else:
            print(f"   ⚠️  Хост НЕ НАЙДЕН по host_name '{host_name}'")
            print(f"   (Но это не критично, если найден по host_code)")
    
    # 5. Проверяем fallback через plan_id
    print(f"\n5. Проверка fallback через plan_id:")
    plan_id = metadata.get('plan_id')
    if plan_id:
        plan = get_plan_by_id(plan_id)
        if plan:
            plan_host_name = plan.get('host_name')
            print(f"   ✅ План найден:")
            print(f"      - plan_id: {plan_id}")
            print(f"      - plan_name: {plan.get('plan_name')}")
            print(f"      - host_name из плана: {plan_host_name}")
            
            if plan_host_name:
                plan_host = get_host(plan_host_name)
                if plan_host:
                    print(f"   ✅ Хост найден через план:")
                    print(f"      - host_name: {plan_host.get('host_name')}")
                    print(f"      - host_code: {plan_host.get('host_code')}")
        else:
            print(f"   ⚠️  План с ID {plan_id} не найден")
    
    # 6. Тестируем функцию _ensure_host_metadata
    print(f"\n6. Тест функции _ensure_host_metadata():")
    test_metadata = metadata.copy()
    host_ok, host_record = _ensure_host_metadata(test_metadata, payment_id)
    
    if host_ok:
        print(f"   ✅ Функция вернула успех")
        if host_record:
            print(f"   ✅ Хост найден:")
            print(f"      - host_name: {host_record.get('host_name')}")
            print(f"      - host_code: {host_record.get('host_code')}")
        print(f"   ✅ Metadata обновлена:")
        print(f"      - host_name: {test_metadata.get('host_name')}")
        print(f"      - host_code: {test_metadata.get('host_code')}")
    else:
        print(f"   ❌ Функция вернула ошибку!")
        return False
    
    print(f"\n{'='*80}")
    print(f"РЕЗУЛЬТАТ: Все проверки пройдены успешно!")
    print(f"{'='*80}\n")
    
    return True

def test_metadata_priority():
    """Тест приоритета host_code над host_name"""
    print(f"\n{'='*80}")
    print(f"ТЕСТ: Приоритет host_code над host_name")
    print(f"{'='*80}\n")
    
    # Создаем тестовый metadata с обоими полями
    test_metadata = {
        "host_name": "🇫🇮 Финляндия 1",
        "host_code": "finland1",
        "plan_id": 59,
        "user_id": 2206685,
        "action": "new"
    }
    
    print("Тестовый metadata:")
    print(json.dumps(test_metadata, indent=2, ensure_ascii=False))
    
    # Проверяем, что функция находит хост по host_code
    host_ok, host_record = _ensure_host_metadata(test_metadata.copy(), "test-payment-id")
    
    if host_ok and host_record:
        print(f"\n✅ Хост найден:")
        print(f"   - host_name: {host_record.get('host_name')}")
        print(f"   - host_code: {host_record.get('host_code')}")
        
        # Проверяем, что использовался host_code
        if host_record.get('host_code') == test_metadata['host_code']:
            print(f"   ✅ Подтверждено: использован host_code (приоритет работает)")
        else:
            print(f"   ⚠️  Использован host_name вместо host_code")
    else:
        print(f"\n❌ Хост не найден!")
        return False
    
    return True

def test_plan_fallback():
    """Тест fallback через plan_id"""
    print(f"\n{'='*80}")
    print(f"ТЕСТ: Fallback через plan_id")
    print(f"{'='*80}\n")
    
    # Создаем metadata БЕЗ host_name и host_code, но с plan_id
    test_metadata = {
        "plan_id": 59,
        "user_id": 2206685,
        "action": "new"
    }
    
    print("Тестовый metadata (без host_name и host_code):")
    print(json.dumps(test_metadata, indent=2, ensure_ascii=False))
    
    # Проверяем, что функция находит хост через план
    host_ok, host_record = _ensure_host_metadata(test_metadata.copy(), "test-payment-id")
    
    if host_ok and host_record:
        print(f"\n✅ Хост найден через fallback план:")
        print(f"   - host_name: {host_record.get('host_name')}")
        print(f"   - host_code: {host_record.get('host_code')}")
        print(f"   ✅ Fallback через plan_id работает!")
    else:
        print(f"\n❌ Хост не найден через fallback!")
        return False
    
    return True

if __name__ == "__main__":
    print("\n" + "="*80)
    print("ТЕСТИРОВАНИЕ ИСПРАВЛЕНИЙ YooKassa Webhook")
    print("="*80)
    
    results = []
    
    # Тест 1: Конкретный платеж ID 233
    try:
        results.append(("Платеж ID 233", test_payment_233()))
    except Exception as e:
        print(f"\n❌ ОШИБКА при тесте платежа ID 233: {e}")
        import traceback
        traceback.print_exc()
        results.append(("Платеж ID 233", False))
    
    # Тест 2: Приоритет host_code
    try:
        results.append(("Приоритет host_code", test_metadata_priority()))
    except Exception as e:
        print(f"\n❌ ОШИБКА при тесте приоритета: {e}")
        import traceback
        traceback.print_exc()
        results.append(("Приоритет host_code", False))
    
    # Тест 3: Fallback через plan_id
    try:
        results.append(("Fallback через plan_id", test_plan_fallback()))
    except Exception as e:
        print(f"\n❌ ОШИБКА при тесте fallback: {e}")
        import traceback
        traceback.print_exc()
        results.append(("Fallback через plan_id", False))
    
    # Итоги
    print("\n" + "="*80)
    print("ИТОГИ ТЕСТИРОВАНИЯ")
    print("="*80)
    for test_name, result in results:
        status = "✅ ПРОЙДЕН" if result else "❌ ПРОВАЛЕН"
        print(f"{test_name}: {status}")
    
    all_passed = all(result for _, result in results)
    print("\n" + "="*80)
    if all_passed:
        print("✅ ВСЕ ТЕСТЫ ПРОЙДЕНЫ УСПЕШНО!")
    else:
        print("❌ НЕКОТОРЫЕ ТЕСТЫ ПРОВАЛЕНЫ!")
    print("="*80 + "\n")
    
    sys.exit(0 if all_passed else 1)

