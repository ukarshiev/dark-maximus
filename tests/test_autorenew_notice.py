"""
Скрипт для тестирования уведомления о списании при автопродлении.
Имитирует автопродление для пользователя 1588069616 с данными платежа 223 и ключа 119.
"""

import asyncio
import sys
import os
import json
import sqlite3

# Настройка кодировки для Windows
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# Добавляем корневую директорию проекта в путь
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from aiogram import Bot
from shop_bot.data_manager.database import get_key_by_id, get_setting, DB_FILE
from shop_bot.data_manager.scheduler import send_balance_deduction_notice


async def test_autorenew_notice():
    """Тестирует отправку уведомления о списании при автопродлении"""
    
    # Параметры для теста
    user_id = 1588069616
    transaction_id = 223
    key_id = 119
    
    print(f"🔍 Получаю данные ключа {key_id}...")
    
    # Получаем данные ключа
    key_data = get_key_by_id(key_id)
    
    if not key_data:
        print(f"❌ Ключ {key_id} не найден в базе данных")
        return
    
    print(f"✅ Ключ найден:")
    print(f"   - Host: {key_data.get('host_name', 'N/A')}")
    print(f"   - Plan: {key_data.get('plan_name', 'N/A')}")
    print(f"   - User ID: {key_data.get('user_id', 'N/A')}")
    print(f"   - Price: {key_data.get('price', 'N/A')} RUB")
    
    # Проверяем, что ключ принадлежит нужному пользователю
    if key_data.get('user_id') != user_id:
        print(f"⚠️  Внимание: Ключ принадлежит пользователю {key_data.get('user_id')}, а не {user_id}")
        response = input("Продолжить? (y/n): ")
        if response.lower() != 'y':
            return
    
    # Пытаемся получить данные транзакции 223, если не найдена - используем цену из ключа
    amount = float(key_data.get('price', 0))
    plan_name = key_data.get('plan_name', 'Неизвестный тариф')
    host_name = key_data.get('host_name', 'Неизвестный сервер')
    
    print(f"\n🔍 Пытаюсь получить данные транзакции {transaction_id}...")
    
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT 
                    transaction_id,
                    amount_rub,
                    payment_method,
                    metadata
                FROM transactions
                WHERE transaction_id = ?
            """, (transaction_id,))
            
            row = cursor.fetchone()
            
            if row:
                transaction = dict(row)
                # Используем сумму из транзакции, если она найдена
                if transaction.get('amount_rub'):
                    amount = float(transaction['amount_rub'])
                print(f"✅ Транзакция найдена, используем сумму: {amount:.2f} RUB")
            else:
                print(f"⚠️  Транзакция {transaction_id} не найдена, используем цену из ключа: {amount:.2f} RUB")
            
    except Exception as e:
        print(f"⚠️  Ошибка при получении транзакции: {e}, используем цену из ключа: {amount:.2f} RUB")
    
    print(f"\n📤 Отправляю уведомление о списании...")
    print(f"   - Пользователь: {user_id}")
    print(f"   - Ключ: {key_id}")
    print(f"   - Сумма: {amount:.2f} RUB")
    print(f"   - Тариф: {plan_name}")
    print(f"   - Сервер: {host_name}")
    
    # Получаем токен бота из настроек
    bot_token = get_setting("telegram_bot_token")
    
    if not bot_token:
        print(f"❌ Токен бота не найден в настройках")
        return
    
    # Создаем экземпляр бота
    bot = Bot(token=bot_token)
    
    try:
        # Отправляем уведомление
        await send_balance_deduction_notice(
            bot=bot,
            user_id=user_id,
            key_id=key_id,
            amount=amount,
            plan_name=plan_name,
            host_name=host_name
        )
        
        print(f"\n✅ Уведомление успешно отправлено!")
        
    except Exception as e:
        print(f"\n❌ Ошибка при отправке уведомления: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await bot.session.close()


if __name__ == "__main__":
    print("=" * 60)
    print("Тест уведомления о списании при автопродлении")
    print("=" * 60)
    print()
    
    asyncio.run(test_autorenew_notice())
    
    print("\n" + "=" * 60)
    print("Тест завершен")
    print("=" * 60)

