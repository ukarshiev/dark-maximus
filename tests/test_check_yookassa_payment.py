#!/usr/bin/env python3
"""
Скрипт для проверки и обработки платежа YooKassa
который не был обработан через webhook.

Использование:
    docker exec dark-maximus-bot python /app/tests/test_check_yookassa_payment.py
    или
    PAYMENT_ID=30a29228-000f-5000-b000-1091368acfc8 docker exec dark-maximus-bot python /app/tests/test_check_yookassa_payment.py
"""

import asyncio
import sys
import os

# Добавляем путь к проекту
sys.path.insert(0, '/app/project')

from shop_bot.data_manager.database import get_setting, get_transaction_by_payment_id
from shop_bot.bot import handlers
import requests
import logging
from yookassa import Configuration, Payment

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ID платежа для обработки
PAYMENT_ID = os.getenv("PAYMENT_ID", "30a29228-000f-5000-b000-1091368acfc8")

def reconfigure_yookassa():
    """Переинициализирует конфигурацию YooKassa"""
    try:
        from shop_bot.data_manager.database import get_setting
        
        yookassa_test_mode = get_setting("yookassa_test_mode") == "true"
        
        if yookassa_test_mode:
            shop_id = (get_setting("yookassa_test_shop_id") or "").strip() or (get_setting("yookassa_shop_id") or "").strip()
            secret_key = (get_setting("yookassa_test_secret_key") or "").strip() or (get_setting("yookassa_secret_key") or "").strip()
            api_url = (get_setting("yookassa_test_api_url") or "").strip() or (get_setting("yookassa_api_url") or "").strip() or "https://api.test.yookassa.ru/v3"
            verify_ssl = get_setting("yookassa_test_verify_ssl") != "false"
        else:
            shop_id = (get_setting("yookassa_shop_id") or "").strip()
            secret_key = (get_setting("yookassa_secret_key") or "").strip()
            api_url = (get_setting("yookassa_api_url") or "").strip() or "https://api.yookassa.ru/v3"
            verify_ssl = get_setting("yookassa_verify_ssl") != "false"
        
        Configuration.account_id = shop_id
        Configuration.secret_key = secret_key
        Configuration.api_url = api_url
        
        logger.info(f"YooKassa reconfigured: test_mode={yookassa_test_mode}, shop_id={shop_id[:8]}..., api_url={api_url}")
        
    except Exception as e:
        logger.error(f"Failed to reconfigure YooKassa: {e}", exc_info=True)
        raise

def get_payment_from_yookassa(payment_id: str) -> dict:
    """Получает данные платежа из YooKassa API"""
    logger.info(f"Получение данных платежа {payment_id} из YooKassa API...")
    
    reconfigure_yookassa()
    
    try:
        payment = Payment.find_one(payment_id)
        payment_dict = {
            "id": payment.id,
            "status": payment.status,
            "paid": payment.paid,
            "test": payment.test if hasattr(payment, 'test') else False,
            "amount": {
                "value": payment.amount.value,
                "currency": payment.amount.currency
            },
            "metadata": payment.metadata if hasattr(payment, 'metadata') else {},
            "authorization_details": payment.authorization_details.__dict__ if hasattr(payment, 'authorization_details') and payment.authorization_details else {},
            "payment_method": payment.payment_method.__dict__ if hasattr(payment, 'payment_method') and payment.payment_method else {}
        }
        
        logger.info(f"Платеж получен. Статус: {payment_dict.get('status')}, paid: {payment_dict.get('paid')}, test: {payment_dict.get('test')}")
        
        return payment_dict
        
    except Exception as e:
        logger.error(f"Ошибка при получении платежа: {e}", exc_info=True)
        raise

def check_transaction_in_db(payment_id: str):
    """Проверяет наличие транзакции в БД"""
    logger.info(f"Проверка транзакции {payment_id} в БД...")
    
    transaction = get_transaction_by_payment_id(payment_id)
    
    if transaction:
        logger.info(f"✅ Транзакция найдена в БД:")
        logger.info(f"  transaction_id: {transaction.get('transaction_id')}")
        logger.info(f"  user_id: {transaction.get('user_id')}")
        logger.info(f"  status: {transaction.get('status')}")
        logger.info(f"  amount_rub: {transaction.get('amount_rub')}")
        logger.info(f"  payment_method: {transaction.get('payment_method')}")
        logger.info(f"  created_date: {transaction.get('created_date')}")
        return transaction
    else:
        logger.warning(f"⚠️  Транзакция {payment_id} не найдена в БД")
        return None

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
        logger.error(f"❌ Ошибка обработки платежа: {e}", exc_info=True)
        raise
        
    finally:
        await bot.session.close()
        logger.info("Bot session closed")

def main():
    """Главная функция"""
    try:
        logger.info("=" * 60)
        logger.info("Проверка и обработка платежа YooKassa")
        logger.info(f"Payment ID: {PAYMENT_ID}")
        logger.info("=" * 60)
        
        # Проверяем транзакцию в БД
        db_transaction = check_transaction_in_db(PAYMENT_ID)
        
        # Получаем данные платежа из YooKassa
        payment_data = get_payment_from_yookassa(PAYMENT_ID)
        
        logger.info("=" * 60)
        logger.info("Анализ платежа:")
        logger.info(f"  Статус: {payment_data.get('status')}")
        logger.info(f"  Оплачен: {payment_data.get('paid')}")
        logger.info(f"  Тестовый: {payment_data.get('test')}")
        logger.info(f"  Сумма: {payment_data.get('amount', {}).get('value')} {payment_data.get('amount', {}).get('currency')}")
        logger.info("=" * 60)
        
        # Проверяем статус платежа
        if payment_data.get('status') == 'pending' and not payment_data.get('paid'):
            logger.warning("⚠️  Платеж в статусе 'pending' и не оплачен (paid=false)")
            logger.warning("Это означает, что пользователь еще не оплатил платеж.")
            logger.warning("Webhook придет только после оплаты.")
            return
        
        if payment_data.get('status') == 'succeeded' and payment_data.get('paid'):
            logger.info("✅ Платеж оплачен и успешно завершен")
            
            # Подготавливаем metadata
            metadata = prepare_metadata(payment_data)
            
            # Проверяем обязательные поля
            required_fields = ['user_id', 'plan_id', 'host_name', 'price']
            missing_fields = [f for f in required_fields if not metadata.get(f)]
            
            if missing_fields:
                logger.error(f"❌ Отсутствуют обязательные поля в metadata: {missing_fields}")
                logger.error(f"Metadata: {metadata}")
                return
            
            # Проверяем, не обработан ли уже платеж
            if db_transaction and db_transaction.get('status') == 'paid':
                logger.warning("⚠️  Платеж уже обработан (status=paid в БД)")
                user_input = input("Повторить обработку? (y/n): ")
                if user_input.lower() != 'y':
                    logger.info("Обработка отменена пользователем")
                    return
            
            # Обрабатываем платеж
            logger.info("Запуск обработки платежа...")
            asyncio.run(process_payment(metadata))
            
            logger.info("=" * 60)
            logger.info("✅ УСПЕШНО! Платеж обработан")
            logger.info("=" * 60)
            
        elif payment_data.get('status') == 'waiting_for_capture' and payment_data.get('paid'):
            logger.info("✅ Платеж оплачен и ожидает подтверждения (capture)")
            
            # Подготавливаем metadata
            metadata = prepare_metadata(payment_data)
            
            # Проверяем обязательные поля
            required_fields = ['user_id', 'plan_id', 'host_name', 'price']
            missing_fields = [f for f in required_fields if not metadata.get(f)]
            
            if missing_fields:
                logger.error(f"❌ Отсутствуют обязательные поля в metadata: {missing_fields}")
                logger.error(f"Metadata: {metadata}")
                return
            
            # Обрабатываем платеж
            logger.info("Запуск обработки платежа...")
            asyncio.run(process_payment(metadata))
            
            logger.info("=" * 60)
            logger.info("✅ УСПЕШНО! Платеж обработан")
            logger.info("=" * 60)
            
        elif payment_data.get('status') == 'canceled':
            logger.warning("⚠️  Платеж отменен")
            return
            
        else:
            logger.warning(f"⚠️  Неизвестный статус платежа: {payment_data.get('status')}, paid: {payment_data.get('paid')}")
            logger.warning("Обработка не требуется")
            return
        
    except Exception as e:
        logger.error(f"❌ ОШИБКА: {e}", exc_info=True)
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()







