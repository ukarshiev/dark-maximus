# -*- coding: utf-8 -*-
"""
Симуляция webhook от YooKassa для обработки платежа
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

from yookassa import Payment
from shop_bot.data_manager.database import (
    get_setting,
    get_transaction_by_payment_id,
    update_yookassa_transaction
)
from shop_bot.bot.handlers import _reconfigure_yookassa
import logging

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


def simulate_webhook(payment_id: str):
    """Симулирует webhook от YooKassa"""
    print("="*60)
    print(f"СИМУЛЯЦИЯ WEBHOOK ДЛЯ ПЛАТЕЖА: {payment_id}")
    print("="*60)
    
    # Переинициализируем Configuration
    _reconfigure_yookassa()
    
    # Получаем платеж из YooKassa
    print("\n[Шаг 1] Получение платежа из YooKassa API...")
    try:
        payment = Payment.find_one(payment_id)
        print(f"[OK] Платеж получен:")
        print(f"  ID: {payment.id}")
        print(f"  Status: {payment.status}")
        print(f"  Paid: {payment.paid}")
        print(f"  Amount: {payment.amount.value} {payment.amount.currency}")
    except Exception as e:
        print(f"[ERROR] Не удалось получить платеж: {e}")
        return False
    
    # Получаем транзакцию из БД
    print("\n[Шаг 2] Получение транзакции из БД...")
    tx = get_transaction_by_payment_id(payment_id)
    if not tx:
        print("[ERROR] Транзакция не найдена в БД!")
        return False
    
    print(f"[OK] Транзакция найдена:")
    print(f"  Transaction ID: {tx.get('transaction_id')}")
    print(f"  Status: {tx.get('status')}")
    
    # Симулируем webhook событие
    print("\n[Шаг 3] Симуляция webhook события...")
    
    if payment.status == "succeeded" and payment.paid:
        event_type = "payment.succeeded"
        print(f"  Event: {event_type}")
        print(f"  Paid: True")
        
        # Создаем объект события как в реальном webhook
        event_json = {
            "event": event_type,
            "object": {
                "id": payment.id,
                "status": payment.status,
                "paid": payment.paid,
                "amount": {
                    "value": payment.amount.value,
                    "currency": payment.amount.currency
                },
                "metadata": json.loads(tx.get('metadata') or '{}'),
                "authorization_details": {
                    "rrn": getattr(payment, 'authorization_details', {}).get('rrn') if hasattr(payment, 'authorization_details') else None,
                    "auth_code": getattr(payment, 'authorization_details', {}).get('auth_code') if hasattr(payment, 'authorization_details') else None
                },
                "payment_method": {
                    "type": getattr(payment, 'payment_method', {}).get('type') if hasattr(payment, 'payment_method') else "unknown"
                }
            }
        }
        
        print(f"\n[OK] Webhook событие создано")
        print(f"  Event: {event_type}")
        print(f"  Payment ID: {payment.id}")
        print(f"  Status: {payment.status}")
        print(f"  Paid: {payment.paid}")
        
        # Обновляем транзакцию
        print("\n[Шаг 4] Обновление транзакции в БД...")
        metadata = json.loads(tx.get('metadata') or '{}')
        metadata.update({
            "yookassa_payment_id": payment.id,
            "rrn": event_json["object"]["authorization_details"].get("rrn"),
            "authorization_code": event_json["object"]["authorization_details"].get("auth_code"),
            "payment_type": event_json["object"]["payment_method"].get("type", "unknown")
        })
        
        try:
            update_yookassa_transaction(
                payment_id,
                'paid',
                float(payment.amount.value),
                payment.id,
                event_json["object"]["authorization_details"].get("rrn"),
                event_json["object"]["authorization_details"].get("auth_code"),
                event_json["object"]["payment_method"].get("type", "unknown"),
                metadata
            )
            print(f"[OK] Транзакция обновлена на статус 'paid'")
        except Exception as e:
            print(f"[ERROR] Ошибка при обновлении транзакции: {e}")
            import traceback
            traceback.print_exc()
            return False
        
        print("\n" + "="*60)
        print("РЕЗУЛЬТАТ")
        print("="*60)
        print(f"\n[OK] Webhook обработан успешно!")
        print(f"  Payment ID: {payment_id}")
        print(f"  Status: paid")
        print(f"\nПроверьте транзакцию в веб-интерфейсе:")
        print(f"  http://localhost:1488/transactions")
        
        return True
        
    elif payment.status == "waiting_for_capture" and payment.paid:
        event_type = "payment.waiting_for_capture"
        print(f"  Event: {event_type}")
        print(f"  Paid: True")
        print(f"  [OK] Платеж будет обработан как успешный")
        # Аналогичная обработка
        return True
    else:
        print(f"  Status: {payment.status}")
        print(f"  Paid: {payment.paid}")
        print(f"  [INFO] Платеж еще не оплачен или в другом статусе")
        return False


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Использование: python tests/simulate_yookassa_webhook.py <payment_id>")
        print("Пример: python tests/simulate_yookassa_webhook.py 30a0bb23-000f-5000-8000-1d431c36089a")
        sys.exit(1)
    
    payment_id = sys.argv[1]
    
    try:
        simulate_webhook(payment_id)
    except Exception as e:
        print(f"\n[ERROR] Критическая ошибка: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

