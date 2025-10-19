# -*- coding: utf-8 -*-
"""
Контроллер для управления ботами
"""

import asyncio
import logging

from yookassa import Configuration
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode 

from shop_bot.data_manager import database
from shop_bot.bot.handlers import get_user_router
from shop_bot.bot.middlewares import BanMiddleware, PerformanceMiddleware, RateLimitMiddleware
from shop_bot.bot import handlers, support_handlers
from shop_bot.bot.support_handlers import get_support_router

logger = logging.getLogger(__name__)

DEFAULT_YOOKASSA_API_URL = "https://api.yookassa.ru/v3"


def _setting_to_bool(value: str | None, default: bool = True) -> bool:
    if value is None:
        return default
    return value.strip().lower() not in {"false", "0", "off", "no"}


def _safe_strip(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


class BotController:
    def __init__(self):
        self._loop = None

        self.shop_bot = None
        self.shop_dp = None
        self.shop_task = None
        self.shop_is_running = False

        self.support_bot = None
        self.support_dp = None
        self.support_task = None
        self.support_is_running = False

    def set_loop(self, loop: asyncio.AbstractEventLoop):
        self._loop = loop
        logger.info("BotController: Event loop has been set.")

    def get_bot_instance(self) -> Bot | None:
        return self.shop_bot

    
    async def _start_polling(self, bot, dp, name):
        logger.info(f"BotController: Polling task for '{name}' has been started.")
        try:
            print(f"DEBUG: Starting polling for {name} with bot {bot.id}")
            await dp.start_polling(bot)
        except asyncio.CancelledError:
            logger.info(f"BotController: Polling task for '{name}' was cancelled.")
        except Exception as e:
            logger.error(f"BotController: An error occurred during polling for '{name}': {e}", exc_info=True)
        finally:
            logger.info(f"BotController: Polling for '{name}' has gracefully stopped.")
            if bot:
                await bot.close()
            if name == "ShopBot":
                self.shop_is_running = False
                self.shop_task = None
                self.shop_bot = None
                self.shop_dp = None
            elif name == "SupportBot":
                self.support_is_running = False
                self.support_task = None
                self.support_bot = None
                self.support_dp = None

    def start_shop_bot(self):
        if self.shop_is_running:
            return {"status": "error", "message": "Бот уже запущен."}
        
        if not self._loop or not self._loop.is_running():
            return {"status": "error", "message": "Критическая ошибка: цикл событий не установлен."}

        token = database.get_setting("telegram_bot_token")
        bot_username = database.get_setting("telegram_bot_username")
        admin_id = database.get_setting("admin_telegram_id")

        if not all([token, bot_username, admin_id]):
            return {
                "status": "error",
                "message": "Невозможно запустить: не все обязательные настройки Telegram заполнены (токен, username, ID админа)."
            }

        try:
            logger.warning("🟢 ShopBot: Запуск бота...")
            self.shop_bot = Bot(token=token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
            self.shop_dp = Dispatcher()
            
            # Добавляем middleware в правильном порядке
            self.shop_dp.update.outer_middleware(PerformanceMiddleware(log_slow_requests=True, slow_threshold=0.5))
            self.shop_dp.update.outer_middleware(RateLimitMiddleware(max_requests_per_minute=30))
            self.shop_dp.update.outer_middleware(BanMiddleware())
            
            self.shop_dp.include_router(get_user_router())

            self.shop_is_running = True

            # Проверяем режим YooKassa (тестовый или боевой)
            yookassa_test_mode = database.get_setting("yookassa_test_mode") == "true"
            
            # Для YooKassa API нужны реальные ключи в обоих режимах
            # Тестовый режим = реальные ключи + тестовые данные
            # Боевой режим = реальные ключи + продакшн данные
            
            if yookassa_test_mode:
                yookassa_shop_id = _safe_strip(database.get_setting("yookassa_test_shop_id")) or _safe_strip(database.get_setting("yookassa_shop_id"))
                yookassa_secret_key = _safe_strip(database.get_setting("yookassa_test_secret_key")) or _safe_strip(database.get_setting("yookassa_secret_key"))
                api_url = _safe_strip(database.get_setting("yookassa_test_api_url")) or _safe_strip(database.get_setting("yookassa_api_url")) or DEFAULT_YOOKASSA_API_URL
                verify_ssl = _setting_to_bool(database.get_setting("yookassa_test_verify_ssl"), True)
                mode_text = "тестовый"
            else:
                yookassa_shop_id = _safe_strip(database.get_setting("yookassa_shop_id"))
                yookassa_secret_key = _safe_strip(database.get_setting("yookassa_secret_key"))
                api_url = _safe_strip(database.get_setting("yookassa_api_url")) or DEFAULT_YOOKASSA_API_URL
                verify_ssl = _setting_to_bool(database.get_setting("yookassa_verify_ssl"), True)
                mode_text = "боевой"

            # Проверяем, что есть хотя бы один набор ключей
            yookassa_enabled = bool(yookassa_shop_id and yookassa_secret_key)

            cryptobot_token = database.get_setting("cryptobot_token")
            cryptobot_enabled = bool(cryptobot_token)

            heleket_shop_id = database.get_setting("heleket_merchant_id")
            heleket_api_key = database.get_setting("heleket_api_key")
            heleket_enabled = bool(heleket_api_key and heleket_shop_id)
            
            ton_wallet_address = database.get_setting("ton_wallet_address")
            tonapi_key = database.get_setting("tonapi_key")
            tonconnect_enabled = bool(ton_wallet_address and tonapi_key)

            stars_enabled = database.get_setting("stars_enabled") == "true"

            if yookassa_enabled:
                # Правильная настройка YooKassa через configure()
                Configuration.configure(account_id=yookassa_shop_id, secret_key=yookassa_secret_key, api_url=api_url, verify=verify_ssl)
                logger.info(f"YooKassa configured ({mode_text} режим): shop_id={yookassa_shop_id}, api_url={api_url}, verify_ssl={verify_ssl}")
            
            handlers.PAYMENT_METHODS = {
                "yookassa": yookassa_enabled,
                "heleket": heleket_enabled,
                "cryptobot": cryptobot_enabled,
                "tonconnect": tonconnect_enabled,
                "stars": stars_enabled
            }
            handlers.TELEGRAM_BOT_USERNAME = bot_username
            handlers.ADMIN_ID = admin_id

            self.shop_task = asyncio.run_coroutine_threadsafe(self._start_polling(self.shop_bot, self.shop_dp, "ShopBot"), self._loop)
            logger.warning("🟢 ShopBot: Бот успешно запущен и работает")
            logger.info("BotController: Start command sent to event loop.")
            return {"status": "success", "message": "Команда на запуск бота отправлена."}
            
        except Exception as e:
            logger.error(f"Failed to start bot: {e}", exc_info=True)
            self.shop_bot = None
            self.shop_dp = None
            return {"status": "error", "message": f"Ошибка при запуске: {e}"}

    def start_support_bot(self):
        if self.support_is_running:
            return {"status": "error", "message": "Бот-Саппорт уже запущен."}
            
        token = database.get_setting("support_bot_token")
        group_id = database.get_setting("support_group_id")
        
        if not token or not group_id:
            return {"status": "error", "message": "Токен для Бота-Саппорта и Айди группы не указаны."}

        try:
            logger.warning("🟢 SupportBot: Запуск бота...")
            self.support_bot = Bot(token=token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
            self.support_dp = Dispatcher()
            
            support_handlers.user_bot = self.shop_bot
            
            support_router = get_support_router()
            self.support_dp.include_router(support_router)

            self.support_is_running = True
            self.support_task = asyncio.run_coroutine_threadsafe(
                self._start_polling(self.support_bot, self.support_dp, "SupportBot"), self._loop
            )
            logger.warning("🟢 SupportBot: Бот успешно запущен и работает")
            return {"status": "success", "message": "Команда на запуск бота отправлена."}
        except Exception as e:
            self.support_bot = None
            self.support_dp = None
            logger.error(f"Failed to start Support Bot: {e}", exc_info=True)
            return {"status": "error", "message": f"Error starting Support Bot: {e}"}

    def stop_shop_bot(self):
        if not self.shop_is_running:
            return {"status": "error", "message": "Бот не запущен."}

        if not self._loop or not self.shop_dp:
            return {"status": "error", "message": "Критическая ошибка: компоненты бота недоступны."}

        logger.warning("🔴 ShopBot: Остановка бота...")
        self.shop_is_running = False

        logger.info("BotController: Sending graceful stop signal...")
        asyncio.run_coroutine_threadsafe(self.shop_dp.stop_polling(), self._loop)

        return {"status": "success", "message": "Команда на остановку бота отправлена."}
    
    def stop_support_bot(self):
        if not self.support_is_running:
            return {"status": "error", "message": "Бот не запущен."}

        if not self._loop or not self.support_dp:
            return {"status": "error", "message": "Критическая ошибка: компоненты бота недоступны."}

        logger.warning("🔴 SupportBot: Остановка бота...")
        self.support_is_running = False

        logger.info("BotController: Sending graceful stop signal...")
        asyncio.run_coroutine_threadsafe(self.support_dp.stop_polling(), self._loop)

        return {"status": "success", "message": "Команда на остановку бота отправлена."}

    def get_status(self):
        return {"shop_bot_running": self.shop_is_running,
                "support_bot_running": self.support_is_running
            }
