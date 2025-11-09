#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Ручное исправление платежа 30a29d3e-000f-5001-8000-18efc565b3c1
1. Создаем транзакцию в БД
2. Обрабатываем как успешный платеж
3. Выдаем ключ пользователю
"""

import sys
import json
import asyncio
from pathlib import Path
from datetime import datetime, timezone, timedelta

# Добавляем корневую директорию в PYTHONPATH
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / 'src'))

from aiogram import Bot
from shop_bot.data_manager.database import get_setting, create_pending_transaction, get_transaction_by_payment_id
from shop_bot.bot.handlers import process_successful_yookassa_payment


async def fix_payment():
    """Исправляет зависший платеж"""
    
    # Данные платежа из YooKassa
    payment_id = "30a29d3e-000f-5001-8000-18efc565b3c1"
    user_id = 6044240344
    amount_rub = 1.0
    
    metadata = {
        "user_id": user_id,
        "months": 0,  # По данным из YooKassa
        "price": 1.0,
        "action": "new",
        "key_id": 0,
        "host_name": "🇪🇪 Эстония",
        "plan_id": 55,
        "customer_email": "ukarshiev+bot1@yandex.ru",
        "payment_method": "YooKassa",
        "promo_code": None
    }
    
    print("\n" + "="*70)
    print("Исправление платежа 30a29d3e-000f-5001-8000-18efc565b3c1")
    print("="*70 + "\n")
    
    # Шаг 1: Проверяем, есть ли транзакция в БД
    print("[Шаг 1] Проверка транзакции в БД...")
    existing_tx = get_transaction_by_payment_id(payment_id)
    
    if existing_tx:
        print(f"[OK] Транзакция найдена (ID: {existing_tx.get('transaction_id')})")
        print(f"  Статус: {existing_tx.get('status')}")
    else:
        print("[WARNING] Транзакция НЕ найдена. Создаю вручную...")
        
        # Создаем pending транзакцию
        tx_id = create_pending_transaction(payment_id, user_id, amount_rub, metadata)
        
        if tx_id:
            print(f"[OK] Транзакция создана (ID: {tx_id})")
        else:
            print("[ERROR] Не удалось создать транзакцию!")
            return False
    
    # Шаг 2: Получаем токен бота
    print("\n[Шаг 2] Получение токена бота...")
    bot_token = get_setting('telegram_bot_token')
    if not bot_token:
        print("[ERROR] Токен бота не найден в настройках!")
        return False
    print("[OK] Токен получен")
    
    # Шаг 3: Создаем бот instance и обрабатываем платеж
    print("\n[Шаг 3] Обработка успешного платежа...")
    print(f"  User ID: {user_id}")
    print(f"  Plan ID: {metadata['plan_id']}")
    print(f"  Host: {metadata['host_name']}")
    print(f"  Action: {metadata['action']}")
    
    bot = Bot(token=bot_token)
    
    try:
        # Добавляем дополнительные данные YooKassa
        metadata['yookassa_payment_id'] = payment_id
        metadata['payment_type'] = 'manual_fix'
        
        # Вызываем обработчик успешного платежа
        await process_successful_yookassa_payment(bot, metadata)
        
        print("\n[OK] Платеж успешно обработан!")
        print(f"  - Ключ должен быть выдан пользователю {user_id}")
        print(f"  - Статус транзакции обновлен на 'paid'")
        print(f"  - Сообщение отправлено в Telegram")
        
        return True
        
    except Exception as e:
        print(f"\n[ERROR] Ошибка при обработке платежа: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        await bot.session.close()


async def main():
    """Основная функция"""
    success = await fix_payment()
    
    print("\n" + "="*70)
    if success:
        print("[SUCCESS] Платеж успешно исправлен!")
    else:
        print("[FAILED] Не удалось исправить платеж")
    print("="*70 + "\n")
    
    return success


if __name__ == "__main__":
    result = asyncio.run(main())
    sys.exit(0 if result else 1)

