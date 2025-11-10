#!/usr/bin/env python3
"""
Ручная обработка платежа ID 233 - создание ключа
"""
import sys
import os
import asyncio
from pathlib import Path

project_root = Path("/app/project") if os.path.exists("/app/project") else Path("/opt/dark-maximus")
sys.path.insert(0, str(project_root / "src"))

from shop_bot.data_manager.database import get_transaction_by_payment_id
from shop_bot.bot.handlers import process_successful_yookassa_payment
from shop_bot.bot_controller import BotController
import json

async def process_payment():
    payment_id = "30a48370-000f-5001-9000-16231fa0ad0c"
    
    print("="*80)
    print("Обработка платежа ID 233 - создание ключа")
    print("="*80)
    
    # Получаем транзакцию
    tx = get_transaction_by_payment_id(payment_id)
    if not tx:
        print("❌ Транзакция не найдена!")
        return False
    
    md = tx.get('metadata', {})
    if isinstance(md, str):
        md = json.loads(md)
    
    print(f"\nMetadata из транзакции:")
    print(f"  - user_id: {md.get('user_id')}")
    print(f"  - host_code: {md.get('host_code')}")
    print(f"  - host_name: {md.get('host_name')}")
    print(f"  - plan_id: {md.get('plan_id')}")
    print(f"  - action: {md.get('action')}")
    
    # Добавляем payment_id в metadata
    md['payment_id'] = payment_id
    
    # Получаем токен бота
    from shop_bot.data_manager.database import get_setting
    bot_token = get_setting('telegram_bot_token')
    if not bot_token:
        print("❌ Telegram bot token не найден в настройках!")
        return False
    
    # Создаем экземпляр бота
    from aiogram import Bot
    bot = Bot(token=bot_token)
    
    print(f"\n✅ Bot instance получен")
    print(f"Обрабатываем платеж...")
    
    try:
        await process_successful_yookassa_payment(bot, md)
        print(f"\n✅ Платеж обработан успешно!")
        return True
    except Exception as e:
        print(f"\n❌ Ошибка обработки: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    result = asyncio.run(process_payment())
    sys.exit(0 if result else 1)

