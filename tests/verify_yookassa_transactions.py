# -*- coding: utf-8 -*-
"""
Проверяет транзакции YooKassa в БД и показывает их детали
"""

import sys
import os
import io
import json

# Настраиваем кодировку для Windows
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# Добавляем путь к проекту
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

from shop_bot.data_manager.database import get_paginated_transactions, get_transaction_by_payment_id


def verify_yookassa_transactions():
    """Проверяет транзакции YooKassa"""
    print("="*60)
    print("ПРОВЕРКА ТРАНЗАКЦИЙ YOOKASSA В БД")
    print("="*60)
    
    # Получаем все транзакции
    transactions, total = get_paginated_transactions(page=1, per_page=100)
    
    # Фильтруем транзакции YooKassa
    yookassa_txs = []
    for tx in transactions:
        payment_method = tx.get('payment_method')
        metadata = tx.get('metadata', {})
        if isinstance(metadata, str):
            try:
                metadata = json.loads(metadata)
            except:
                metadata = {}
        
        # Проверяем payment_method в колонке БД или в metadata
        if payment_method == 'YooKassa' or metadata.get('payment_method') == 'YooKassa':
            yookassa_txs.append(tx)
    
    print(f"\nВсего транзакций в БД: {total}")
    print(f"Транзакций YooKassa найдено: {len(yookassa_txs)}")
    
    if yookassa_txs:
        print("\n" + "="*60)
        print("ТРАНЗАКЦИИ YOOKASSA:")
        print("="*60)
        
        for i, tx in enumerate(yookassa_txs, 1):
            print(f"\n[{i}] Transaction ID: {tx.get('transaction_id')}")
            print(f"    Payment ID: {tx.get('payment_id')}")
            print(f"    User ID: {tx.get('user_id')}")
            print(f"    Status: {tx.get('status')}")
            print(f"    Amount: {tx.get('amount_rub')} RUB")
            print(f"    Payment Method: {tx.get('payment_method')}")
            print(f"    Created: {tx.get('created_date')}")
            
            metadata = tx.get('metadata', {})
            if isinstance(metadata, str):
                try:
                    metadata = json.loads(metadata)
                except:
                    pass
            
            if isinstance(metadata, dict):
                if metadata.get('yookassa_payment_id'):
                    print(f"    YooKassa Payment ID: {metadata.get('yookassa_payment_id')}")
                if metadata.get('rrn'):
                    print(f"    RRN: {metadata.get('rrn')}")
                if metadata.get('authorization_code'):
                    print(f"    Auth Code: {metadata.get('authorization_code')}")
        
        print("\n" + "="*60)
        print("РЕЗУЛЬТАТ")
        print("="*60)
        print(f"\n[OK] Найдено {len(yookassa_txs)} транзакций YooKassa!")
        print(f"\nЭти транзакции должны быть видны в веб-интерфейсе:")
        print(f"  http://localhost:50000/transactions")
        print(f"\nПроверьте:")
        print(f"  1. Транзакции отображаются в списке")
        print(f"  2. Payment Method = 'YooKassa'")
        print(f"  3. Статус корректный (paid/pending)")
        print(f"  4. Сумма отображается правильно")
        
        return True
    else:
        print("\n[WARN] Транзакций YooKassa не найдено!")
        print("\nВозможные причины:")
        print("  1. Транзакции еще не созданы")
        print("  2. Payment Method не установлен в БД")
        print("  3. Транзакции созданы с другим payment_method")
        
        return False


if __name__ == "__main__":
    verify_yookassa_transactions()

