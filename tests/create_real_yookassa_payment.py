# -*- coding: utf-8 -*-
"""
Создание РЕАЛЬНОГО тестового платежа YooKassa и проверка транзакций
"""

import sys
import os
import io
import uuid
import json
from datetime import datetime

# Настраиваем кодировку для Windows
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# Добавляем путь к проекту
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

from yookassa import Configuration, Payment
from shop_bot.data_manager.database import (
    get_setting, 
    create_pending_transaction,
    get_paginated_transactions,
    get_transaction_by_payment_id
)
from shop_bot.bot.handlers import _reconfigure_yookassa
import logging

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


def check_existing_transactions():
    """Проверяет существующие транзакции YooKassa"""
    print("\n" + "="*60)
    print("ПРОВЕРКА СУЩЕСТВУЮЩИХ ТРАНЗАКЦИЙ")
    print("="*60)
    
    transactions, total = get_paginated_transactions(page=1, per_page=10)
    
    yookassa_transactions = [tx for tx in transactions if tx.get('payment_method') == 'YooKassa']
    
    print(f"\nВсего транзакций: {total}")
    print(f"Транзакций YooKassa: {len(yookassa_transactions)}")
    
    if yookassa_transactions:
        print("\nПоследние транзакции YooKassa:")
        for tx in yookassa_transactions[:5]:
            print(f"  - ID: {tx.get('transaction_id')}, Payment ID: {tx.get('payment_id')}, "
                  f"Статус: {tx.get('status')}, Сумма: {tx.get('amount_rub')} RUB")
    else:
        print("\n[INFO] Транзакций YooKassa не найдено")
    
    return yookassa_transactions


def create_test_payment():
    """Создает реальный тестовый платеж через YooKassa API"""
    print("\n" + "="*60)
    print("СОЗДАНИЕ РЕАЛЬНОГО ТЕСТОВОГО ПЛАТЕЖА")
    print("="*60)
    
    # Проверяем настройки
    test_mode = get_setting("yookassa_test_mode") == "true"
    print(f"\nРежим: {'Тестовый' if test_mode else 'Боевой'}")
    
    # Переинициализируем Configuration
    print("\n[Шаг 1] Переинициализация Configuration...")
    result = _reconfigure_yookassa()
    if not result:
        print("[ERROR] Не удалось переинициализировать Configuration. Проверьте ключи в настройках.")
        return None
    
    print("[OK] Configuration переинициализирован")
    
    # Создаем платеж
    print("\n[Шаг 2] Создание платежа через YooKassa API...")
    
    payment_payload = {
        "amount": {
            "value": "5.00",
            "currency": "RUB"
        },
        "confirmation": {
            "type": "redirect",
            "return_url": "https://t.me/test_bot"
        },
        "capture": True,
        "description": "Тестовый платеж для проверки",
        "test": test_mode,
        "metadata": {
            "user_id": 999999999,  # Тестовый пользователь
            "months": 1,
            "price": 5.0,
            "action": "new",
            "key_id": 0,
            "host_name": "Тестовый хост",
            "plan_id": 1,
            "customer_email": "test@example.com",
            "payment_method": "YooKassa",
            "test_payment": True  # Маркер тестового платежа
        }
    }
    
    try:
        idempotence_key = str(uuid.uuid4())
        print(f"  Idempotence Key: {idempotence_key}")
        
        payment = Payment.create(payment_payload, idempotence_key)
        
        print(f"[OK] Платеж создан успешно!")
        print(f"  Payment ID: {payment.id}")
        print(f"  Status: {payment.status}")
        print(f"  Test: {payment.test}")
        print(f"  Confirmation URL: {payment.confirmation.confirmation_url}")
        
        # Создаем транзакцию в БД
        print("\n[Шаг 3] Создание транзакции в БД...")
        metadata = payment_payload["metadata"]
        transaction_id = create_pending_transaction(
            payment.id,
            999999999,  # Тестовый user_id
            5.0,
            metadata
        )
        
        if transaction_id:
            print(f"[OK] Транзакция создана в БД!")
            print(f"  Transaction ID: {transaction_id}")
            print(f"  Payment ID: {payment.id}")
        else:
            print("[ERROR] Не удалось создать транзакцию в БД")
            return None
        
        return {
            "payment": payment,
            "transaction_id": transaction_id,
            "payment_id": payment.id
        }
        
    except Exception as e:
        print(f"[ERROR] Ошибка при создании платежа: {e}")
        import traceback
        traceback.print_exc()
        return None


def check_transaction_in_db(payment_id: str):
    """Проверяет транзакцию в БД"""
    print("\n" + "="*60)
    print(f"ПРОВЕРКА ТРАНЗАКЦИИ В БД (Payment ID: {payment_id})")
    print("="*60)
    
    tx = get_transaction_by_payment_id(payment_id)
    
    if tx:
        print("\n[OK] Транзакция найдена в БД:")
        print(f"  Transaction ID: {tx.get('transaction_id')}")
        print(f"  Payment ID: {tx.get('payment_id')}")
        print(f"  User ID: {tx.get('user_id')}")
        print(f"  Status: {tx.get('status')}")
        print(f"  Amount: {tx.get('amount_rub')} RUB")
        print(f"  Payment Method: {tx.get('payment_method')}")
        print(f"  Created: {tx.get('created_date')}")
        
        metadata = tx.get('metadata')
        if metadata:
            if isinstance(metadata, str):
                metadata = json.loads(metadata)
            print(f"  Metadata: {json.dumps(metadata, ensure_ascii=False, indent=2)}")
        
        return tx
    else:
        print("\n[ERROR] Транзакция не найдена в БД!")
        return None


def simulate_webhook_processing(payment_id: str):
    """Симулирует обработку webhook для платежа"""
    print("\n" + "="*60)
    print("СИМУЛЯЦИЯ ОБРАБОТКИ WEBHOOK")
    print("="*60)
    
    # Получаем платеж из YooKassa API
    print("\n[Шаг 1] Получение статуса платежа из YooKassa API...")
    try:
        payment = Payment.find_one(payment_id)
        print(f"[OK] Платеж получен:")
        print(f"  Status: {payment.status}")
        print(f"  Paid: {payment.paid}")
        print(f"  Test: {payment.test}")
        
        # Симулируем webhook событие
        print("\n[Шаг 2] Симуляция webhook события...")
        
        if payment.status == "succeeded" and payment.paid:
            event_type = "payment.succeeded"
            print(f"  Event: {event_type}")
            print(f"  Paid: True")
            print(f"  [OK] Платеж будет обработан как успешный")
        elif payment.status == "waiting_for_capture" and payment.paid:
            event_type = "payment.waiting_for_capture"
            print(f"  Event: {event_type}")
            print(f"  Paid: True")
            print(f"  [OK] Платеж будет обработан как успешный (waiting_for_capture)")
        elif payment.status == "pending":
            print(f"  Status: pending")
            print(f"  [INFO] Платеж еще не оплачен, ожидание оплаты...")
            return False
        else:
            print(f"  Status: {payment.status}")
            print(f"  [INFO] Платеж в статусе {payment.status}")
            return False
        
        return True
        
    except Exception as e:
        print(f"[ERROR] Ошибка при получении платежа: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    print("="*60)
    print("СОЗДАНИЕ РЕАЛЬНОГО ТЕСТОВОГО ПЛАТЕЖА YOOKASSA")
    print("="*60)
    
    # Проверяем существующие транзакции
    existing = check_existing_transactions()
    
    # Создаем новый тестовый платеж
    result = create_test_payment()
    
    if not result:
        print("\n[ERROR] Не удалось создать платеж")
        return
    
    payment_id = result["payment_id"]
    transaction_id = result["transaction_id"]
    
    # Проверяем транзакцию в БД
    tx = check_transaction_in_db(payment_id)
    
    if tx:
        print("\n" + "="*60)
        print("РЕЗУЛЬТАТЫ")
        print("="*60)
        print(f"\n[OK] Транзакция создана и найдена в БД!")
        print(f"  Transaction ID: {transaction_id}")
        print(f"  Payment ID: {payment_id}")
        print(f"  Status: {tx.get('status')}")
        print(f"\nПроверьте транзакцию в веб-интерфейсе:")
        print(f"  http://localhost:50000/transactions")
        print(f"\nДля оплаты перейдите по ссылке:")
        print(f"  {result['payment'].confirmation.confirmation_url}")
        print(f"\nПосле оплаты запустите:")
        print(f"  python tests/simulate_yookassa_webhook.py {payment_id}")
    else:
        print("\n[ERROR] Транзакция не найдена в БД!")
    
    # Симулируем обработку webhook
    simulate_webhook_processing(payment_id)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n[INFO] Прервано пользователем")
    except Exception as e:
        print(f"\n[ERROR] Критическая ошибка: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

