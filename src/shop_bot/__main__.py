# -*- coding: utf-8 -*-
"""
Точка входа в приложение
"""

import logging
import threading
import asyncio
import signal
import os

from shop_bot.webhook_server.app import create_webhook_app
from shop_bot.data_manager.scheduler import periodic_subscription_check
from shop_bot.data_manager import database
from shop_bot.data_manager.async_database import initialize_async_db, close_async_db
from shop_bot.data_manager.backup import initialize_backup_system, shutdown_backup_system
from shop_bot.utils.performance_monitor import get_performance_monitor, start_metrics_cleanup
from shop_bot.bot_controller import BotController
from shop_bot.utils import setup_logging, app_logger, security_logger, payment_logger, database_logger

def main():
    # Настройка централизованного логирования
    setup_logging(log_level="INFO", log_dir="logs")
    logger = app_logger.logger
    
    logger.warning("🚀 Dark Maximus: Запуск приложения...")

    database.initialize_db()
    logger.info("Database initialization check complete.")
    
    # Инициализация асинхронной БД
    asyncio.run(initialize_async_db())
    logger.info("Async database initialized.")
    
    # Инициализация Telegram Logger Handler
    try:
        from shop_bot.utils.telegram_logger import create_telegram_logger_handler
        
        # Получаем настройки бота логов
        logging_bot_token = database.get_setting('logging_bot_token') or ''
        logging_bot_admin_chat_id = database.get_setting('logging_bot_admin_chat_id') or ''
        logging_bot_level = database.get_setting('logging_bot_level') or 'error'
        
        # Создаем и добавляем обработчик если настройки заполнены
        if logging_bot_token and logging_bot_admin_chat_id:
            telegram_handler = create_telegram_logger_handler(
                bot_token=logging_bot_token,
                admin_chat_id=logging_bot_admin_chat_id,
                log_level=logging_bot_level
            )
            
            # Добавляем обработчик к корневому логгеру
            root_logger = logging.getLogger()
            root_logger.addHandler(telegram_handler)
            
            # Также добавляем к основным логгерам для гарантии
            app_logger.logger.addHandler(telegram_handler)
            security_logger.logger.addHandler(telegram_handler)
            payment_logger.logger.addHandler(telegram_handler)
            database_logger.logger.addHandler(telegram_handler)
            
            logger.info(f"Telegram logging handler initialized with level: {logging_bot_level}")
        else:
            logger.info("Telegram logging handler skipped: settings not configured")
    except Exception as e:
        logger.warning(f"Failed to initialize Telegram logging handler: {e}")
    
    # Инициализация системы бэкапов
    initialize_backup_system()
    logger.info("Backup system initialized.")

    bot_controller = BotController()
    flask_app = create_webhook_app(bot_controller)
    
    async def shutdown(sig: signal.Signals, loop: asyncio.AbstractEventLoop):
        # Определяем тип сигнала для более понятного сообщения
        signal_type = "🛑 Сигнал завершения (SIGTERM)" if sig == signal.SIGTERM else "🛑 Сигнал прерывания (SIGINT)"
        logger.warning(f"{signal_type} - Корректное завершение работы приложения...")
        
        # Останавливаем систему бэкапов
        shutdown_backup_system()
        
        # Закрываем асинхронную БД
        await close_async_db()
        
        status = bot_controller.get_status()
        if status.get("shop_bot_running"):
            logger.warning("🛑 Остановка ShopBot...")
            bot_controller.stop_shop_bot()
        if status.get("support_bot_running"):
            logger.warning("🛑 Остановка SupportBot...")
            bot_controller.stop_support_bot()
        
        await asyncio.sleep(2)
        tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
        if tasks:
            [task.cancel() for task in tasks]
            await asyncio.gather(*tasks, return_exceptions=True)
        loop.stop()
        logger.warning("✅ Dark Maximus: Приложение корректно остановлено")

    async def start_services():
        loop = asyncio.get_running_loop()
        bot_controller.set_loop(loop)
        flask_app.config['EVENT_LOOP'] = loop
        
        # Настраиваем логирование Werkzeug в зависимости от окружения
        import logging
        werkzeug_logger = logging.getLogger('werkzeug')
        if os.getenv('FLASK_DEBUG', 'false').lower() == 'true':
            werkzeug_logger.setLevel(logging.INFO)
        else:
            werkzeug_logger.setLevel(logging.ERROR)
        
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, lambda sig=sig: asyncio.create_task(shutdown(sig, loop)))
        
        flask_thread = threading.Thread(
            target=lambda: flask_app.run(host='0.0.0.0', port=1488, use_reloader=False, debug=False),
            daemon=True
        )
        flask_thread.start()
        
        logger.info("Flask server started in a background thread on http://0.0.0.0:1488")
        
        # Автозапуск ботов при старте приложения (без захода на панель)
        try:
            logger.warning("🔄 Dark Maximus: Автозапуск ботов...")
            required = ['telegram_bot_token', 'telegram_bot_username', 'admin_telegram_id']
            if all(database.get_setting(k) for k in required):
                start_res = bot_controller.start_shop_bot()
                if start_res.get('status') == 'success':
                    logger.info(f"✅ Autostart ShopBot: {start_res.get('message')}")
                else:
                    # Проверяем, не является ли это случаем "бот уже запущен"
                    error_msg = start_res.get('message', '')
                    if 'уже запущен' in error_msg.lower():
                        logger.info(f"ℹ️ Autostart ShopBot: {error_msg}")
                    else:
                        logger.error(f"❌ Autostart ShopBot failed: {error_msg}")
            else:
                logger.warning("⚠️ Autostart ShopBot skipped: Telegram settings are incomplete.")

            support_enabled = (database.get_setting("support_enabled") == "true")
            if support_enabled and database.get_setting("support_bot_token") and database.get_setting("support_group_id"):
                start_sup = bot_controller.start_support_bot()
                if start_sup.get('status') == 'success':
                    logger.info(f"✅ Autostart SupportBot: {start_sup.get('message')}")
                else:
                    # Проверяем, не является ли это случаем "бот уже запущен"
                    error_msg = start_sup.get('message', '')
                    if 'уже запущен' in error_msg.lower():
                        logger.info(f"ℹ️ Autostart SupportBot: {error_msg}")
                    else:
                        logger.error(f"❌ Autostart SupportBot failed: {error_msg}")
            else:
                logger.info("ℹ️ Autostart SupportBot skipped or disabled.")
        except Exception as e:
            logger.error(f"❌ Autostart error: {e}", exc_info=True)
            # Не прерываем работу приложения из-за ошибок автозапуска
            
        logger.warning("✅ Dark Maximus: Приложение запущено и работает")
        logger.info("Application is running. Bots are managed automatically and via web panel.")
        
        asyncio.create_task(periodic_subscription_check(bot_controller))
        
        # Запускаем мониторинг производительности
        asyncio.create_task(start_metrics_cleanup())
        logger.info("Performance monitoring started.")

        await asyncio.Future()

    try:
        asyncio.run(start_services())
    finally:
        logger.warning("🛑 Dark Maximus: Завершение работы приложения")
        logger.info("Application is shutting down.")

if __name__ == "__main__":
    main()
