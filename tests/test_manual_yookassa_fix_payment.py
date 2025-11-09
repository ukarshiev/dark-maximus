#!/usr/bin/env python3
"""
Скрипт для ручного исправления зависшего платежа YooKassa.
Проверяет транзакцию в БД, симулирует успешный webhook и выдает ключ пользователю.
"""

import sys
import os
import asyncio
import json
import sqlite3
from pathlib import Path
from datetime import datetime

# Добавляем корневую директорию в PYTHONPATH
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / 'src'))

from aiogram import Bot
from shop_bot.data_manager.database import get_transaction_by_payment_id, update_yookassa_transaction
from shop_bot.bot.handlers import process_successful_yookassa_payment


def check_transaction(payment_id: str):
    """Проверяет транзакцию в базе данных"""
    print(f"\n{'='*60}")
    print(f"Проверка транзакции: {payment_id}")
    print(f"{'='*60}\n")
    
    transaction = get_transaction_by_payment_id(payment_id)
    
    if not transaction:
        print(f"❌ Транзакция с payment_id={payment_id} не найдена в БД")
        return None
    
    print("✅ Транзакция найдена в БД:")
    print(f"  - ID: {transaction.get('transaction_id')}")
    print(f"  - User ID: {transaction.get('user_id')}")
    print(f"  - Статус: {transaction.get('status')}")
    print(f"  - Сумма: {transaction.get('amount_rub')} RUB")
    print(f"  - Метод: {transaction.get('payment_method')}")
    print(f"  - Создано: {transaction.get('created_date')}")
    
    # Парсим metadata
    metadata = transaction.get('metadata', {})
    if isinstance(metadata, str):
        try:
            metadata = json.loads(metadata)
        except:
            metadata = {}
    
    print(f"\n  Метаданные платежа:")
    print(f"    - Action: {metadata.get('action')}")
    print(f"    - Host: {metadata.get('host_name')}")
    print(f"    - Plan ID: {metadata.get('plan_id')}")
    print(f"    - Months: {metadata.get('months')}")
    print(f"    - Key ID: {metadata.get('key_id')}")
    print(f"    - Promo code: {metadata.get('promo_code')}")
    
    return transaction


async def fix_payment(payment_id: str, bot_token: str):
    """Выдает ключ для зависшего платежа"""
    print(f"\n{'='*60}")
    print(f"Исправление платежа: {payment_id}")
    print(f"{'='*60}\n")
    
    # Получаем транзакцию
    transaction = get_transaction_by_payment_id(payment_id)
    if not transaction:
        print(f"❌ Транзакция не найдена")
        return False
    
    # Проверяем статус
    if transaction.get('status') == 'paid':
        print(f"⚠️  Транзакция уже обработана (статус: paid)")
        user_input = input("Продолжить обработку? (yes/no): ")
        if user_input.lower() not in ['yes', 'y', 'да']:
            print("Отменено")
            return False
    
    # Парсим metadata
    metadata = transaction.get('metadata', {})
    if isinstance(metadata, str):
        try:
            metadata = json.loads(metadata)
        except Exception as e:
            print(f"❌ Ошибка парсинга метаданных: {e}")
            return False
    
    # Проверяем обязательные поля
    required_fields = ['user_id', 'action', 'host_name', 'plan_id', 'months']
    missing_fields = [f for f in required_fields if not metadata.get(f)]
    if missing_fields:
        print(f"❌ Отсутствуют обязательные поля в metadata: {missing_fields}")
        return False
    
    # Добавляем дополнительные данные YooKassa в metadata
    metadata['yookassa_payment_id'] = payment_id
    metadata['payment_type'] = 'manual_fix'
    metadata['price'] = transaction.get('amount_rub', 0.0)
    
    print(f"\n🔧 Запуск обработки платежа...")
    print(f"  - User ID: {metadata['user_id']}")
    print(f"  - Action: {metadata['action']}")
    print(f"  - Host: {metadata['host_name']}")
    print(f"  - Plan ID: {metadata['plan_id']}")
    
    # Создаем бот instance
    bot = Bot(token=bot_token)
    
    try:
        # Вызываем обработчик успешного платежа
        await process_successful_yookassa_payment(bot, metadata)
        
        print(f"\n✅ Платеж успешно обработан!")
        print(f"  - Ключ должен быть выдан пользователю {metadata['user_id']}")
        print(f"  - Статус транзакции обновлен на 'paid'")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Ошибка при обработке платежа: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        await bot.session.close()


async def main():
    """Основная функция"""
    # Payment ID для исправления
    PAYMENT_ID = "30a29d3e-000f-5001-8000-18efc565b3c1"
    
    # Получаем токен бота из настроек
    try:
        from shop_bot.data_manager.database import get_setting
        bot_token = get_setting('telegram_bot_token')
        if not bot_token:
            print("❌ Токен бота не найден в настройках")
            return
    except Exception as e:
        print(f"❌ Ошибка получения токена: {e}")
        return
    
    # 1. Проверяем транзакцию
    transaction = check_transaction(PAYMENT_ID)
    if not transaction:
        return
    
    # 2. Спрашиваем подтверждение
    print(f"\n{'='*60}")
    user_input = input(f"Выдать ключ для этого платежа? (yes/no): ")
    if user_input.lower() not in ['yes', 'y', 'да']:
        print("Отменено пользователем")
        return
    
    # 3. Исправляем платеж
    success = await fix_payment(PAYMENT_ID, bot_token)
    
    if success:
        print(f"\n{'='*60}")
        print(f"✅ ГОТОВО! Платеж успешно обработан.")
        print(f"{'='*60}")
    else:
        print(f"\n{'='*60}")
        print(f"❌ Не удалось обработать платеж. Проверьте логи выше.")
        print(f"{'='*60}")


if __name__ == "__main__":
    print(f"\n{'#'*60}")
    print(f"# Ручное исправление зависшего платежа YooKassa")
    print(f"# Дата: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}")
    print(f"{'#'*60}")
    
    asyncio.run(main())

