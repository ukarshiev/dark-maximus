#!/usr/bin/env python3
"""
Скрипт для ручной обработки платежа Yookassa
который не был обработан через webhook.

Использование:
    docker exec dark-maximus-bot python /app/tests/test_manual_yookassa_fix.py
"""

import asyncio
import sys
import os

# Добавляем путь к проекту
sys.path.insert(0, '/app/project')

from shop_bot.data_manager.database import get_setting
from shop_bot.bot import handlers
import requests
import logging

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ID платежа для обработки (можно переопределить через переменную окружения)
PAYMENT_ID = os.getenv("PAYMENT_ID", "30a03e8b-000f-5001-9000-1a3cbd78f7de")

def get_payment_from_yookassa(payment_id: str) -> dict:
    """Получает данные платежа из Yookassa API"""
    logger.info(f"Получение данных платежа {payment_id} из Yookassa API...")
    
    shop_id = get_setting("yookassa_shop_id")
    secret_key = get_setting("yookassa_secret_key")
    
    if not shop_id or not secret_key:
        raise ValueError("Yookassa credentials not configured!")
    
    response = requests.get(
        f"https://api.yookassa.ru/v3/payments/{payment_id}",
        auth=(shop_id, secret_key),
        headers={'Content-Type': 'application/json'}
    )
    
    if response.status_code != 200:
        raise Exception(f"Failed to get payment: {response.status_code} - {response.text}")
    
    payment_data = response.json()
    logger.info(f"Платеж получен. Статус: {payment_data.get('status')}")
    
    return payment_data

def prepare_metadata(payment_data: dict) -> dict:
    """Подготавливает metadata для обработчика"""
    metadata = payment_data.get("metadata", {})
    auth_details = payment_data.get("authorization_details", {})
    payment_method = payment_data.get("payment_method", {})
    
    # Добавляем дополнительные поля для process_successful_yookassa_payment
    metadata["yookassa_payment_id"] = payment_data["id"]
    metadata["rrn"] = auth_details.get("rrn")
    metadata["authorization_code"] = auth_details.get("auth_code")
    metadata["payment_type"] = payment_method.get("type")
    
    logger.info(f"Metadata подготовлена:")
    logger.info(f"  user_id: {metadata.get('user_id')}")
    logger.info(f"  plan_id: {metadata.get('plan_id')}")
    logger.info(f"  host_name: {metadata.get('host_name')}")
    logger.info(f"  price: {metadata.get('price')}")
    logger.info(f"  payment_method: {metadata.get('payment_method')}")
    
    return metadata

async def process_payment(metadata: dict):
    """Обрабатывает платеж"""
    logger.info("Создание bot instance...")
    
    from aiogram import Bot
    bot_token = get_setting("telegram_bot_token")
    
    if not bot_token:
        raise ValueError("Bot token not configured!")
    
    bot = Bot(token=bot_token)
    
    try:
        logger.info("Вызов process_successful_yookassa_payment...")
        await handlers.process_successful_yookassa_payment(bot, metadata)
        logger.info("✅ Платеж обработан успешно!")
        
    except Exception as e:
        logger.error(f"❌ Ошибка обработки платежа: {e}")
        import traceback
        traceback.print_exc()
        raise
        
    finally:
        await bot.session.close()
        logger.info("Bot session closed")

def main():
    """Главная функция"""
    try:
        logger.info("=" * 60)
        logger.info("Запуск ручной обработки платежа Yookassa")
        logger.info("=" * 60)
        
        # Получаем данные платежа
        payment_data = get_payment_from_yookassa(PAYMENT_ID)
        
        # Проверяем статус
        if payment_data.get('status') != 'succeeded':
            logger.warning(f"⚠️  Платеж не в статусе 'succeeded': {payment_data.get('status')}")
            user_input = input("Продолжить обработку? (y/n): ")
            if user_input.lower() != 'y':
                logger.info("Обработка отменена пользователем")
                return
        
        if not payment_data.get('paid'):
            logger.error("❌ Платеж не оплачен (paid=False)")
            return
        
        # Подготавливаем metadata
        metadata = prepare_metadata(payment_data)
        
        # Проверяем обязательные поля
        required_fields = ['user_id', 'plan_id', 'host_name', 'price']
        missing_fields = [f for f in required_fields if not metadata.get(f)]
        
        if missing_fields:
            logger.error(f"❌ Отсутствуют обязательные поля в metadata: {missing_fields}")
            return
        
        # Обрабатываем платеж
        asyncio.run(process_payment(metadata))
        
        logger.info("=" * 60)
        logger.info("✅ УСПЕШНО! Платеж обработан")
        logger.info("=" * 60)
        
    except Exception as e:
        logger.error(f"❌ ОШИБКА: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()

