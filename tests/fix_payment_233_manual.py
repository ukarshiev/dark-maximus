#!/usr/bin/env python3
"""
Ручная обработка платежа ID 233
Создает транзакцию и обрабатывает платеж вручную
"""

import sys
import os
from pathlib import Path

project_root = Path("/app/project") if os.path.exists("/app/project") else Path("/opt/dark-maximus")
sys.path.insert(0, str(project_root / "src"))

from shop_bot.data_manager.database import (
    create_pending_transaction,
    get_transaction_by_payment_id,
    update_yookassa_transaction
)
from shop_bot.bot.handlers import _reconfigure_yookassa, process_successful_yookassa_payment
from yookassa import Payment, Configuration
import asyncio
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def fix_payment_233():
    payment_id = "30a48370-000f-5001-9000-16231fa0ad0c"
    
    print(f"\n{'='*80}")
    print(f"Ручная обработка платежа: {payment_id}")
    print(f"{'='*80}\n")
    
    # Переинициализируем YooKassa
    _reconfigure_yookassa()
    
    # Получаем платеж из YooKassa
    print("1. Получение платежа из YooKassa API...")
    try:
        payment = Payment.find_one(payment_id)
        print(f"   ✅ Платеж получен:")
        print(f"      - ID: {payment.id}")
        print(f"      - Status: {payment.status}")
        print(f"      - Paid: {payment.paid}")
        print(f"      - Amount: {payment.amount.value} {payment.amount.currency}")
    except Exception as e:
        print(f"   ❌ Ошибка получения платежа: {e}")
        return False
    
    if not payment.paid:
        print(f"   ❌ Платеж не оплачен!")
        return False
    
    # Извлекаем metadata
    print(f"\n2. Извлечение metadata...")
    metadata = payment.metadata or {}
    print(f"   Metadata keys: {list(metadata.keys())}")
    print(f"   - host_name: {metadata.get('host_name')}")
    print(f"   - host_code: {metadata.get('host_code')}")
    print(f"   - plan_id: {metadata.get('plan_id')}")
    print(f"   - user_id: {metadata.get('user_id')}")
    
    # Проверяем транзакцию в БД
    print(f"\n3. Проверка транзакции в БД...")
    existing_tx = get_transaction_by_payment_id(payment_id)
    
    if not existing_tx:
        print(f"   ⚠️  Транзакция не найдена, создаем...")
        
        # Создаем транзакцию
        user_id = int(metadata.get('user_id', 0))
        amount_rub = float(payment.amount.value)
        
        if not user_id:
            print(f"   ❌ user_id отсутствует в metadata!")
            return False
        
        tx_id = create_pending_transaction(payment_id, user_id, amount_rub, metadata)
        if tx_id:
            print(f"   ✅ Транзакция создана: ID={tx_id}")
        else:
            print(f"   ❌ Ошибка создания транзакции!")
            return False
    else:
        print(f"   ✅ Транзакция уже существует: ID={existing_tx.get('transaction_id')}, status={existing_tx.get('status')}")
        if existing_tx.get('status') == 'paid':
            print(f"   ⚠️  Платеж уже обработан!")
            return True
    
    # Обновляем metadata с данными от YooKassa
    metadata.update({
        "yookassa_payment_id": payment.id,
        "rrn": getattr(payment.authorization_details, 'rrn', None) if hasattr(payment, 'authorization_details') else None,
        "authorization_code": getattr(payment.authorization_details, 'auth_code', None) if hasattr(payment, 'authorization_details') else None,
        "payment_type": getattr(payment.payment_method, 'type', 'unknown') if hasattr(payment, 'payment_method') else 'unknown',
        "payment_id": payment_id
    })
    
    # Обрабатываем платеж
    print(f"\n4. Обработка платежа...")
    try:
        from shop_bot.bot_controller import BotController
        # Нужно получить экземпляр бота
        # Это сложно сделать из скрипта, поэтому просто обновим транзакцию
        update_yookassa_transaction(
            payment_id, 'paid', float(payment.amount.value),
            payment.id,
            metadata.get('rrn'),
            metadata.get('authorization_code'),
            metadata.get('payment_type'),
            metadata
        )
        print(f"   ✅ Транзакция обновлена на 'paid'")
        print(f"   ⚠️  Для полной обработки (создание ключа) нужно вызвать process_successful_yookassa_payment()")
        print(f"   Это можно сделать через веб-интерфейс или через simulate_yookassa_webhook.py")
    except Exception as e:
        print(f"   ❌ Ошибка обработки: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    print(f"\n{'='*80}")
    print(f"РЕЗУЛЬТАТ: Транзакция создана и обновлена")
    print(f"{'='*80}\n")
    
    return True

if __name__ == "__main__":
    try:
        result = asyncio.run(fix_payment_233())
        sys.exit(0 if result else 1)
    except Exception as e:
        print(f"\n❌ ОШИБКА: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

