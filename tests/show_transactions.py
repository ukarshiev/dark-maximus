# -*- coding: utf-8 -*-
"""
Показывает транзакции из БД и создает тестовую транзакцию для демонстрации
"""

import sys
import os
import io
import json
from datetime import datetime, timezone, timedelta

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
    update_yookassa_transaction,
    DB_FILE
)
import sqlite3


def show_all_transactions():
    """Показывает все транзакции"""
    print("="*60)
    print("ВСЕ ТРАНЗАКЦИИ ИЗ БД")
    print("="*60)
    
    transactions, total = get_paginated_transactions(page=1, per_page=100)
    
    print(f"\nВсего транзакций: {total}")
    
    if not transactions:
        print("\n[INFO] Транзакций не найдено")
        return
    
    # Группируем по payment_method
    by_method = {}
    for tx in transactions:
        method = tx.get('payment_method', 'Unknown')
        if method not in by_method:
            by_method[method] = []
        by_method[method].append(tx)
    
    print(f"\nТранзакций по методам оплаты:")
    for method, txs in by_method.items():
        print(f"  {method}: {len(txs)}")
    
    # Показываем транзакции YooKassa
    yookassa_txs = [tx for tx in transactions if tx.get('payment_method') == 'YooKassa']
    
    print(f"\n{'='*60}")
    print(f"ТРАНЗАКЦИИ YOOKASSA ({len(yookassa_txs)})")
    print("="*60)
    
    if yookassa_txs:
        for i, tx in enumerate(yookassa_txs[:10], 1):
            print(f"\n[{i}] Transaction ID: {tx.get('transaction_id')}")
            print(f"    Payment ID: {tx.get('payment_id')}")
            print(f"    User ID: {tx.get('user_id')}")
            print(f"    Status: {tx.get('status')}")
            print(f"    Amount: {tx.get('amount_rub')} RUB")
            print(f"    Created: {tx.get('created_date')}")
            
            metadata = tx.get('metadata')
            if metadata:
                if isinstance(metadata, str):
                    try:
                        metadata = json.loads(metadata)
                    except:
                        pass
                if isinstance(metadata, dict):
                    print(f"    Metadata:")
                    print(f"      - user_id: {metadata.get('user_id')}")
                    print(f"      - action: {metadata.get('action')}")
                    print(f"      - host_name: {metadata.get('host_name')}")
                    print(f"      - yookassa_payment_id: {metadata.get('yookassa_payment_id')}")
    else:
        print("\n[INFO] Транзакций YooKassa не найдено")
    
    return yookassa_txs


def create_demo_transaction():
    """Создает демонстрационную транзакцию YooKassa"""
    print("\n" + "="*60)
    print("СОЗДАНИЕ ДЕМОНСТРАЦИОННОЙ ТРАНЗАКЦИИ")
    print("="*60)
    
    # Создаем тестовый payment_id
    import uuid
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
    
    if transaction_id:
        print(f"[OK] Транзакция создана!")
        print(f"  Transaction ID: {transaction_id}")
        
        # Проверяем транзакцию
        print(f"\n[Шаг 2] Проверка транзакции в БД...")
        tx = get_transaction_by_payment_id(payment_id)
        if tx:
            print(f"[OK] Транзакция найдена в БД!")
            print(f"  Transaction ID: {tx.get('transaction_id')}")
            print(f"  Payment ID: {tx.get('payment_id')}")
            print(f"  Status: {tx.get('status')}")
            print(f"  Amount: {tx.get('amount_rub')} RUB")
            print(f"  Payment Method: {tx.get('payment_method')}")
            
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
            
            print(f"\n" + "="*60)
            print("РЕЗУЛЬТАТ")
            print("="*60)
            print(f"\n[OK] Демонстрационная транзакция создана и обработана!")
            print(f"  Transaction ID: {transaction_id}")
            print(f"  Payment ID: {payment_id}")
            print(f"  Status: paid")
            print(f"\nПроверьте транзакцию в веб-интерфейсе:")
            print(f"  http://localhost:1488/transactions")
            
            return transaction_id
        else:
            print(f"[ERROR] Транзакция не найдена после создания!")
            return None
    else:
        print(f"[ERROR] Не удалось создать транзакцию!")
        return None


def show_transaction_details(payment_id: str):
    """Показывает детали транзакции"""
    print(f"\n" + "="*60)
    print(f"ДЕТАЛИ ТРАНЗАКЦИИ: {payment_id}")
    print("="*60)
    
    tx = get_transaction_by_payment_id(payment_id)
    
    if not tx:
        print("\n[ERROR] Транзакция не найдена!")
        return
    
    print(f"\nОсновная информация:")
    print(f"  Transaction ID: {tx.get('transaction_id')}")
    print(f"  Payment ID: {tx.get('payment_id')}")
    print(f"  User ID: {tx.get('user_id')}")
    print(f"  Status: {tx.get('status')}")
    print(f"  Amount: {tx.get('amount_rub')} RUB")
    print(f"  Currency: {tx.get('currency_name')}")
    print(f"  Payment Method: {tx.get('payment_method')}")
    print(f"  Created: {tx.get('created_date')}")
    
    metadata = tx.get('metadata')
    if metadata:
        if isinstance(metadata, str):
            try:
                metadata = json.loads(metadata)
            except:
                pass
        
        if isinstance(metadata, dict):
            print(f"\nMetadata:")
            for key, value in metadata.items():
                print(f"  {key}: {value}")


if __name__ == "__main__":
    print("="*60)
    print("ПРОВЕРКА И СОЗДАНИЕ ТРАНЗАКЦИЙ YOOKASSA")
    print("="*60)
    
    # Показываем существующие транзакции
    yookassa_txs = show_all_transactions()
    
    # Создаем демонстрационную транзакцию
    print("\n" + "="*60)
    answer = input("\nСоздать демонстрационную транзакцию? (y/n): ")
    if answer.lower() == 'y':
        transaction_id = create_demo_transaction()
        
        if transaction_id:
            # Получаем payment_id из БД
            with sqlite3.connect(DB_FILE) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute("SELECT payment_id FROM transactions WHERE transaction_id = ?", (transaction_id,))
                row = cursor.fetchone()
                if row:
                    payment_id = row['payment_id']
                    show_transaction_details(payment_id)
    else:
        print("\n[INFO] Создание транзакции пропущено")
    
    print("\n" + "="*60)
    print("ЗАВЕРШЕНО")
    print("="*60)

