# -*- coding: utf-8 -*-
"""
Создает РЕАЛЬНУЮ транзакцию YooKassa с правильным payment_method
"""

import sys
import os
import io
import json
import uuid
import sqlite3
from datetime import datetime, timezone, timedelta

# Настраиваем кодировку для Windows
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# Добавляем путь к проекту
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

from shop_bot.data_manager.database import DB_FILE, get_transaction_by_payment_id, update_yookassa_transaction


def create_yookassa_transaction():
    """Создает транзакцию YooKassa напрямую в БД с payment_method"""
    print("="*60)
    print("СОЗДАНИЕ РЕАЛЬНОЙ ТРАНЗАКЦИИ YOOKASSA")
    print("="*60)
    
    payment_id = f"yookassa-{uuid.uuid4()}"
    
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
        "test_payment": True
    }
    
    print(f"\n[Шаг 1] Создание транзакции в БД...")
    print(f"  Payment ID: {payment_id}")
    print(f"  Payment Method: YooKassa")
    print(f"  User ID: 999999999")
    print(f"  Amount: 5.00 RUB")
    print(f"  Status: pending")
    
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            
            local_tz = timezone(timedelta(hours=3))
            local_now = datetime.now(local_tz)
            
            # Создаем транзакцию с payment_method
            cursor.execute("""
                INSERT INTO transactions 
                (payment_id, user_id, status, amount_rub, payment_method, metadata, created_date) 
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                payment_id,
                999999999,
                'pending',
                5.0,
                'YooKassa',  # КРИТИЧЕСКИ ВАЖНО: payment_method в колонке БД
                json.dumps(metadata),
                local_now
            ))
            
            transaction_id = cursor.lastrowid
            conn.commit()
            
            print(f"[OK] Транзакция создана!")
            print(f"  Transaction ID: {transaction_id}")
            
            # Проверяем транзакцию
            print(f"\n[Шаг 2] Проверка транзакции в БД...")
            cursor.execute("SELECT * FROM transactions WHERE transaction_id = ?", (transaction_id,))
            row = cursor.fetchone()
            
            if row:
                print(f"[OK] Транзакция найдена!")
                print(f"  Transaction ID: {row[0]}")
                print(f"  Payment ID: {row[1]}")
                print(f"  Status: {row[3]}")
                print(f"  Payment Method: {row[6] if len(row) > 6 else 'N/A'}")
            
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
            print(f"\n[Шаг 4] Проверка обновленной транзакции...")
            tx = get_transaction_by_payment_id(payment_id)
            if tx:
                print(f"[OK] Транзакция обновлена!")
                print(f"  Transaction ID: {tx.get('transaction_id')}")
                print(f"  Payment ID: {tx.get('payment_id')}")
                print(f"  Status: {tx.get('status')}")
                print(f"  Payment Method: {tx.get('payment_method')}")
                print(f"  Amount: {tx.get('amount_rub')} RUB")
                
                print(f"\n" + "="*60)
                print("РЕЗУЛЬТАТ")
                print("="*60)
                print(f"\n[OK] Транзакция YooKassa создана и обработана!")
                print(f"  Transaction ID: {transaction_id}")
                print(f"  Payment ID: {payment_id}")
                print(f"  Status: paid")
                print(f"  Payment Method: YooKassa")
                print(f"\nПроверьте транзакцию в веб-интерфейсе:")
                print(f"  http://localhost:50000/transactions")
                print(f"\nТранзакция должна быть видна в списке!")
                
                return transaction_id
            else:
                print(f"[ERROR] Транзакция не найдена после обновления!")
                return None
                
    except Exception as e:
        print(f"[ERROR] Ошибка: {e}")
        import traceback
        traceback.print_exc()
        return None


if __name__ == "__main__":
    transaction_id = create_yookassa_transaction()
    
    if transaction_id:
        print("\n" + "="*60)
        print("УСПЕШНО ЗАВЕРШЕНО")
        print("="*60)
        print("\nТеперь откройте http://localhost:50000/transactions")
        print("и проверьте, что транзакция YooKassa видна в списке!")
    else:
        print("\n[ERROR] Не удалось создать транзакцию")

