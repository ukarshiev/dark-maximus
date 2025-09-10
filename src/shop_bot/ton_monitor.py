#!/usr/bin/env python3
"""
TON Transaction Monitor
Мониторит транзакции на TON кошельке и обрабатывает платежи
"""

import asyncio
import logging
import requests
import time
from datetime import datetime, timedelta
from shop_bot.data_manager.database import find_ton_transaction_by_amount, find_and_complete_ton_transaction
from shop_bot.bot_controller import BotController

logger = logging.getLogger(__name__)

class TONMonitor:
    def __init__(self, tonapi_key: str, wallet_address: str, bot_controller: BotController):
        self.tonapi_key = tonapi_key
        self.wallet_address = wallet_address
        self.bot_controller = bot_controller
        self.last_lt = None
        self.running = False
        self.processed_tx_hashes = set()  # Для отслеживания обработанных транзакций
        
    async def start_monitoring(self):
        """Запускает мониторинг транзакций"""
        self.running = True
        logger.info(f"Starting TON monitoring for wallet: {self.wallet_address}")
        
        while self.running:
            try:
                await self.check_transactions()
                await asyncio.sleep(60)  # Проверяем каждые 60 секунд (1 минута)
            except Exception as e:
                logger.error(f"Error in TON monitoring: {e}", exc_info=True)
                await asyncio.sleep(300)  # При ошибке ждем 5 минут
                
    async def check_transactions(self):
        """Проверяет новые транзакции"""
        try:
            # Получаем транзакции аккаунта
            response = requests.get(
                f"https://tonapi.io/v2/accounts/{self.wallet_address}/events",
                headers={"Authorization": f"Bearer {self.tonapi_key}"},
                params={
                    "limit": 5,  # Уменьшаем количество событий
                    "start_lt": self.last_lt,
                    "start_utime": int((datetime.now() - timedelta(minutes=10)).timestamp())  # Увеличиваем период
                }
            )
            
            if response.status_code == 200:
                data = response.json()
                events = data.get('events', [])
                
                logger.info(f"TON Monitor: Found {len(events)} events")
                
                for event in events:
                    await self.process_event(event)
                    
                # Обновляем last_lt
                if events:
                    self.last_lt = events[-1].get('lt')
            else:
                logger.error(f"Failed to get events: {response.status_code} - {response.text}")
                    
        except Exception as e:
            logger.error(f"Failed to check transactions: {e}")
            
    async def process_event(self, event):
        """Обрабатывает событие транзакции"""
        try:
            # Получаем детали транзакции
            tx_hash = event.get('event_id')
            if not tx_hash:
                return
            
            # Проверяем, не обрабатывали ли мы уже эту транзакцию
            if tx_hash in self.processed_tx_hashes:
                return
            
            # Добавляем в список обработанных
            self.processed_tx_hashes.add(tx_hash)
            
            # Ограничиваем размер множества (оставляем только последние 1000)
            if len(self.processed_tx_hashes) > 1000:
                self.processed_tx_hashes = set(list(self.processed_tx_hashes)[-500:])
                
            tx_response = requests.get(
                f"https://tonapi.io/v2/blockchain/transactions/{tx_hash}",
                headers={"Authorization": f"Bearer {self.tonapi_key}"}
            )
            
            if tx_response.status_code == 200:
                tx_details = tx_response.json()
                
                # Ищем входящие сообщения
                in_msg = tx_details.get('in_msg')
                if in_msg:
                    amount_nano = int(in_msg.get('value', 0))
                    amount_ton = float(amount_nano / 1_000_000_000)
                    
                    # Игнорируем нулевые транзакции
                    if amount_ton <= 0:
                        return
                    
                    # Проверяем комментарий
                    comment = in_msg.get('decoded_comment', '')
                    logger.info(f"TON Transaction detected: {amount_ton} TON, comment: {comment}")
                    
                    # Ищем по комментарию
                    if comment.startswith('payment:'):
                        payment_id = comment[8:]  # Убираем "payment:"
                        logger.info(f"Found payment comment: {payment_id}")
                        
                        # Ищем pending транзакцию по payment_id
                        metadata = find_and_complete_ton_transaction(payment_id, amount_ton, tx_hash)
                        if metadata:
                            logger.info(f"TON Payment found by comment: {payment_id}")
                            
                            # Обрабатываем платеж
                            bot = self.bot_controller.get_bot_instance()
                            if bot:
                                from shop_bot.bot import handlers
                                await handlers.process_successful_payment(bot, metadata, tx_hash)
                            else:
                                logger.error("Bot instance not available")
                        else:
                            logger.warning(f"No pending transaction found for payment_id: {payment_id}")
                    else:
                        # Если нет комментария, ищем по сумме (fallback)
                        # Но только для транзакций с разумной суммой (больше 0.001 TON)
                        if amount_ton >= 0.001:
                            metadata = find_ton_transaction_by_amount(amount_ton)
                            if metadata:
                                logger.info(f"TON Payment found by amount: {amount_ton} TON")
                                
                                # Обрабатываем платеж
                                bot = self.bot_controller.get_bot_instance()
                                if bot:
                                    from shop_bot.bot import handlers
                                    await handlers.process_successful_payment(bot, metadata, tx_hash)
                                else:
                                    logger.error("Bot instance not available")
                            else:
                                logger.debug(f"No pending transaction found for amount: {amount_ton} TON")
                        else:
                            logger.debug(f"Ignoring small transaction: {amount_ton} TON")
                        
        except Exception as e:
            logger.error(f"Failed to process event: {e}")
            
    def stop(self):
        """Останавливает мониторинг"""
        self.running = False
        logger.info("TON monitoring stopped")

# Функция для запуска мониторинга
async def start_ton_monitoring(tonapi_key: str, wallet_address: str, bot_controller: BotController):
    """Запускает мониторинг TON транзакций"""
    monitor = TONMonitor(tonapi_key, wallet_address, bot_controller)
    await monitor.start_monitoring()
