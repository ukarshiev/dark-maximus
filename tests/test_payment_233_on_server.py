#!/usr/bin/env python3
"""
Проверка платежа ID 233 на боевом сервере
Запускать на сервере: ssh root@31.56.27.129
"""

import sys
import os
import json
from pathlib import Path

# Добавляем путь к проекту
project_root = Path("/app/project") if os.path.exists("/app/project") else Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

from shop_bot.data_manager.database import (
    get_transaction_by_payment_id,
    get_host,
    get_host_by_code,
    get_plan_by_id,
    DB_FILE
)
from shop_bot.webhook_server.app import _ensure_host_metadata

def main():
    payment_id = "30a48370-000f-5001-9000-16231fa0ad0c"
    
    print("\n" + "="*80)
    print(f"ПРОВЕРКА ПЛАТЕЖА ID 233: {payment_id}")
    print("="*80 + "\n")
    
    # 1. Проверяем транзакцию в БД
    print("1. Проверка транзакции в БД:")
    print(f"   DB_FILE: {DB_FILE}")
    print(f"   Существует: {os.path.exists(DB_FILE)}")
    
    transaction = get_transaction_by_payment_id(payment_id)
    
    if not transaction:
        print(f"   ❌ ТРАНЗАКЦИЯ НЕ НАЙДЕНА в БД!")
        print(f"   Это означает проблему:")
        print(f"   - create_pending_transaction() не был вызван")
        print(f"   - Или платеж был создан до исправлений")
        return False
    
    print(f"   ✅ Транзакция найдена:")
    print(f"      - ID: {transaction.get('transaction_id')}")
    print(f"      - Статус: {transaction.get('status')}")
    print(f"      - User ID: {transaction.get('user_id')}")
    print(f"      - Amount: {transaction.get('amount_rub')} RUB")
    
    # 2. Проверяем metadata
    print(f"\n2. Проверка metadata в транзакции:")
    metadata = transaction.get('metadata', {})
    if isinstance(metadata, str):
        try:
            metadata = json.loads(metadata)
        except:
            metadata = {}
    
    print(f"   Ключи в metadata: {list(metadata.keys())}")
    print(f"   - host_name: {metadata.get('host_name')}")
    print(f"   - host_code: {metadata.get('host_code')}")
    print(f"   - plan_id: {metadata.get('plan_id')}")
    
    # 3. Тестируем функцию _ensure_host_metadata с metadata из БД
    print(f"\n3. Тест функции _ensure_host_metadata() с metadata из БД:")
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
        
        if transaction.get('status') == 'pending':
            print(f"\n   ⚠️  ВНИМАНИЕ: Транзакция в статусе 'pending'")
            print(f"   Это означает, что webhook не обработал платеж")
            print(f"   После применения исправлений webhook должен обработать платеж")
        elif transaction.get('status') == 'paid':
            print(f"\n   ✅ Транзакция уже обработана (status=paid)")
        elif transaction.get('status') == 'failed':
            print(f"\n   ❌ Транзакция помечена как failed")
            print(f"   Это означает, что хост не был найден при предыдущей обработке")
    else:
        print(f"   ❌ Функция вернула ошибку!")
        print(f"   Это означает, что хост не может быть найден даже с исправлениями")
        return False
    
    # 4. Проверяем логи webhook
    print(f"\n4. Рекомендации:")
    print(f"   - Проверьте логи: tail -100 /app/project/logs/application.log | grep '{payment_id}'")
    print(f"   - Ищите записи с [YOOKASSA_WEBHOOK]")
    print(f"   - Проверьте, что metadata_source='database' в логах")
    
    print("\n" + "="*80)
    print("ПРОВЕРКА ЗАВЕРШЕНА")
    print("="*80 + "\n")
    
    return True

if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ ОШИБКА: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

