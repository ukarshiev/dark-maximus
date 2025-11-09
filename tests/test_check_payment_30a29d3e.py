#!/usr/bin/env python3
"""
Быстрая диагностика платежа 30a29d3e-000f-5001-8000-18efc565b3c1
"""

import sys
import json
import sqlite3
from pathlib import Path

# Добавляем корневую директорию в PYTHONPATH
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / 'src'))

DB_FILE = project_root / "users.db"

def check_payment():
    payment_id = "30a29d3e-000f-5001-8000-18efc565b3c1"
    
    print(f"\n{'='*70}")
    print(f"Диагностика платежа: {payment_id}")
    print(f"{'='*70}\n")
    
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Проверяем транзакцию
            cursor.execute("""
                SELECT transaction_id, payment_id, user_id, status, amount_rub, 
                       payment_method, metadata, created_date 
                FROM transactions 
                WHERE payment_id = ?
            """, (payment_id,))
            
            row = cursor.fetchone()
            
            if row:
                print("[OK] Транзакция НАЙДЕНА в БД:\n")
                print(f"  Transaction ID: {row['transaction_id']}")
                print(f"  Payment ID:     {row['payment_id']}")
                print(f"  User ID:        {row['user_id']}")
                print(f"  Статус:         {row['status']}")
                print(f"  Сумма:          {row['amount_rub']} RUB")
                print(f"  Метод:          {row['payment_method']}")
                print(f"  Создано:        {row['created_date']}")
                
                # Парсим metadata
                metadata_str = row['metadata']
                if metadata_str:
                    try:
                        metadata = json.loads(metadata_str)
                        print(f"\n  Метаданные:")
                        print(f"    - user_id:        {metadata.get('user_id')}")
                        print(f"    - action:         {metadata.get('action')}")
                        print(f"    - host_name:      {metadata.get('host_name')}")
                        print(f"    - plan_id:        {metadata.get('plan_id')}")
                        print(f"    - months:         {metadata.get('months')}")
                        print(f"    - key_id:         {metadata.get('key_id')}")
                        print(f"    - price:          {metadata.get('price')}")
                        print(f"    - promo_code:     {metadata.get('promo_code')}")
                        print(f"    - customer_email: {metadata.get('customer_email')}")
                        
                        # Проверяем план
                        plan_id = metadata.get('plan_id')
                        if plan_id:
                            cursor.execute("SELECT * FROM plans WHERE plan_id = ?", (plan_id,))
                            plan = cursor.fetchone()
                            if plan:
                                print(f"\n  План (ID={plan_id}):")
                                print(f"    - Название:  {plan['plan_name']}")
                                print(f"    - Месяцев:   {plan['months']}")
                                print(f"    - Дней:      {plan['days']}")
                                print(f"    - Часов:     {plan['hours']}")
                                print(f"    - Цена:      {plan['price']} RUB")
                                print(f"    - Трафик:    {plan['traffic_gb']} GB")
                            else:
                                print(f"\n  [WARNING] План с ID={plan_id} НЕ НАЙДЕН в БД!")
                        
                    except json.JSONDecodeError as e:
                        print(f"\n  [WARNING] Ошибка парсинга metadata: {e}")
                
                # Проверяем пользователя
                user_id = row['user_id']
                cursor.execute("SELECT telegram_id, username, fullname FROM users WHERE telegram_id = ?", (user_id,))
                user = cursor.fetchone()
                if user:
                    print(f"\n  Пользователь (ID={user_id}):")
                    print(f"    - Username:  @{user['username']}")
                    print(f"    - Fullname:  {user['fullname']}")
                else:
                    print(f"\n  [WARNING] Пользователь с ID={user_id} НЕ НАЙДЕН в БД!")
                
            else:
                print(f"[ERROR] Транзакция с payment_id={payment_id} НЕ НАЙДЕНА в БД\n")
                print("Возможные причины:")
                print("  1. Платеж был создан, но не сохранен в БД")
                print("  2. Payment ID неверный")
                print("  3. Проблема с функцией create_pending_transaction()")
            
    except Exception as e:
        print(f"[ERROR] Ошибка при проверке: {e}")
        import traceback
        traceback.print_exc()
    
    print(f"\n{'='*70}\n")

if __name__ == "__main__":
    check_payment()

