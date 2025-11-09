# -*- coding: utf-8 -*-
"""
Создает демонстрационную транзакцию YooKassa в БД
"""

import sys
import os
import io
import json
import uuid

# Настраиваем кодировку для Windows
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# Добавляем путь к проекту
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

from shop_bot.data_manager.database import (
    get_paginated_transactions,
    get_transaction_by_payment_id,
    create_pending_transaction,
    update_yookassa_transaction
)


def create_demo_transaction():
    """Создает демонстрационную транзакцию YooKassa"""
    print("="*60)
    print("СОЗДАНИЕ ДЕМОНСТРАЦИОННОЙ ТРАНЗАКЦИИ YOOKASSA")
    print("="*60)
    
    # Создаем тестовый payment_id
    payment_id = f"test-{uuid.uuid4()}"
    
    metadata = {
        "user_id": 999999999,
        "months": 1,
        "price": 5.0,
        "action": "new",
        "key_id": 0,
        "host_name": "Тестовый хост",
        "plan_id": 1,
        "customer_email": "test@example.com",
        "payment_method": "YooKassa",
        "test_payment": True,
        "yookassa_payment_id": payment_id
    }
    
    print(f"\n[Шаг 1] Создание транзакции в БД...")
    print(f"  Payment ID: {payment_id}")
    print(f"  User ID: 999999999")
    print(f"  Amount: 5.00 RUB")
    print(f"  Status: pending")
    
    transaction_id = create_pending_transaction(
        payment_id,
        999999999,
        5.0,
        metadata
    )
    
    if not transaction_id:
        print(f"[ERROR] Не удалось создать транзакцию!")
        return None
    
    print(f"[OK] Транзакция создана!")
    print(f"  Transaction ID: {transaction_id}")
    
    # Проверяем транзакцию
    print(f"\n[Шаг 2] Проверка транзакции в БД...")
    tx = get_transaction_by_payment_id(payment_id)
    if not tx:
        print(f"[ERROR] Транзакция не найдена после создания!")
        return None
    
    print(f"[OK] Транзакция найдена в БД!")
    print(f"  Transaction ID: {tx.get('transaction_id')}")
    print(f"  Payment ID: {tx.get('payment_id')}")
    print(f"  Status: {tx.get('status')}")
    print(f"  Amount: {tx.get('amount_rub')} RUB")
    
    # Обновляем транзакцию на 'paid'
    print(f"\n[Шаг 3] Обновление транзакции на 'paid'...")
    metadata.update({
        "yookassa_payment_id": payment_id,
        "rrn": "123456789",
        "authorization_code": "000000",
        "payment_type": "bank_card"
    })
    
    update_yookassa_transaction(
        payment_id,
        'paid',
        5.0,
        payment_id,
        "123456789",
        "000000",
        "bank_card",
        metadata
    )
    
    # Проверяем обновленную транзакцию
    tx = get_transaction_by_payment_id(payment_id)
    if tx:
        print(f"[OK] Транзакция обновлена!")
        print(f"  Status: {tx.get('status')}")
        tx_metadata = tx.get('metadata')
        if isinstance(tx_metadata, str):
            tx_metadata = json.loads(tx_metadata)
        if isinstance(tx_metadata, dict):
            print(f"  YooKassa Payment ID: {tx_metadata.get('yookassa_payment_id')}")
            print(f"  RRN: {tx_metadata.get('rrn')}")
            print(f"  Authorization Code: {tx_metadata.get('authorization_code')}")
    
    print(f"\n" + "="*60)
    print("РЕЗУЛЬТАТ")
    print("="*60)
    print(f"\n[OK] Демонстрационная транзакция создана и обработана!")
    print(f"  Transaction ID: {transaction_id}")
    print(f"  Payment ID: {payment_id}")
    print(f"  Status: paid")
    print(f"\nПроверьте транзакцию в веб-интерфейсе:")
    print(f"  http://localhost:1488/transactions")
    print(f"\nТранзакция должна быть видна в списке с:")
    print(f"  - Payment Method: YooKassa")
    print(f"  - Status: paid")
    print(f"  - Amount: 5.00 RUB")
    
    return transaction_id


def show_yookassa_transactions():
    """Показывает все транзакции YooKassa"""
    print("\n" + "="*60)
    print("ТРАНЗАКЦИИ YOOKASSA В БД")
    print("="*60)
    
    transactions, total = get_paginated_transactions(page=1, per_page=100)
    
    yookassa_txs = [tx for tx in transactions if tx.get('payment_method') == 'YooKassa']
    
    print(f"\nВсего транзакций YooKassa: {len(yookassa_txs)}")
    
    if yookassa_txs:
        for i, tx in enumerate(yookassa_txs[:10], 1):
            print(f"\n[{i}] Transaction ID: {tx.get('transaction_id')}")
            print(f"    Payment ID: {tx.get('payment_id')}")
            print(f"    User ID: {tx.get('user_id')}")
            print(f"    Status: {tx.get('status')}")
            print(f"    Amount: {tx.get('amount_rub')} RUB")
            print(f"    Created: {tx.get('created_date')}")
    else:
        print("\n[INFO] Транзакций YooKassa не найдено")


if __name__ == "__main__":
    # Показываем существующие транзакции
    show_yookassa_transactions()
    
    # Создаем демонстрационную транзакцию
    print("\n")
    transaction_id = create_demo_transaction()
    
    # Показываем транзакции снова
    print("\n")
    show_yookassa_transactions()
    
    print("\n" + "="*60)
    print("ЗАВЕРШЕНО")
    print("="*60)

