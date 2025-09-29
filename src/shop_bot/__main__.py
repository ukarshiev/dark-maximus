# -*- coding: utf-8 -*-
"""
Точка входа в приложение
"""

import logging
import threading
import asyncio
import signal

from shop_bot.webhook_server.app import create_webhook_app
from shop_bot.data_manager.scheduler import periodic_subscription_check
from shop_bot.data_manager import database
from shop_bot.data_manager.backup import initialize_backup_system, shutdown_backup_system
from shop_bot.bot_controller import BotController
from shop_bot.utils import setup_logging, app_logger

def main():
    # Настройка централизованного логирования
    setup_logging(log_level="INFO", log_dir="logs")
    logger = app_logger.logger

    database.initialize_db()
    logger.info("Database initialization check complete.")
    
    # Инициализация системы бэкапов
    initialize_backup_system()
    logger.info("Backup system initialized.")

    bot_controller = BotController()
    flask_app = create_webhook_app(bot_controller)
    
    async def shutdown(sig: signal.Signals, loop: asyncio.AbstractEventLoop):
        logger.info(f"Received signal: {sig.name}. Shutting down...")
        
        # Останавливаем систему бэкапов
        shutdown_backup_system()
        
        if bot_controller.get_status()["is_running"]:
            bot_controller.stop()
            await asyncio.sleep(2)
        tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
        if tasks:
            [task.cancel() for task in tasks]
            await asyncio.gather(*tasks, return_exceptions=True)
        loop.stop()

    async def start_services():
        loop = asyncio.get_running_loop()
        bot_controller.set_loop(loop)
        flask_app.config['EVENT_LOOP'] = loop
        
        # Отключаем логи Werkzeug
        import logging
        logging.getLogger('werkzeug').setLevel(logging.ERROR)
        
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
            required = ['telegram_bot_token', 'telegram_bot_username', 'admin_telegram_id']
            if all(database.get_setting(k) for k in required):
                start_res = bot_controller.start_shop_bot()
                logger.info(f"Autostart ShopBot: {start_res.get('message')}")
            else:
                logger.warning("Autostart ShopBot skipped: Telegram settings are incomplete.")

            support_enabled = (database.get_setting("support_enabled") == "true")
            if support_enabled and database.get_setting("support_bot_token") and database.get_setting("support_group_id"):
                start_sup = bot_controller.start_support_bot()
                logger.info(f"Autostart SupportBot: {start_sup.get('message')}")
            else:
                logger.info("Autostart SupportBot skipped or disabled.")
        except Exception as e:
            logger.error(f"Autostart error: {e}", exc_info=True)
            
        logger.info("Application is running. Bots are managed automatically and via web panel.")
        
        asyncio.create_task(periodic_subscription_check(bot_controller))

        await asyncio.Future()

    try:
        asyncio.run(start_services())
    finally:
        logger.info("Application is shutting down.")

if __name__ == "__main__":
    main()
