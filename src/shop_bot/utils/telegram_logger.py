# -*- coding: utf-8 -*-
"""
Telegram Logger - отправка логов в Telegram бота с умным rate limiting
"""

import asyncio
import logging
import traceback
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict
from collections import deque
import aiohttp


class TelegramLoggerHandler(logging.Handler):
    """
    Обработчик логов для отправки в Telegram бота.
    Включает умный rate limiting и группировку сообщений.
    """
    
    # Telegram API ограничения (консервативные значения)
    MAX_MESSAGES_PER_SECOND = 20  # Telegram лимит ~30, используем 20 для безопасности
    MAX_MESSAGES_PER_MINUTE = 50  # Telegram лимит ~60, используем 50
    MAX_MESSAGE_LENGTH = 4000  # Telegram лимит 4096, используем 4000
    
    def __init__(
        self,
        bot_token: str,
        admin_chat_id: str,
        log_level: str = "error",
        enabled: bool = True
    ):
        """
        Инициализация обработчика
        
        Args:
            bot_token: Токен Telegram бота
            admin_chat_id: ID чата администратора
            log_level: Уровень логирования (none, error, warning, all)
            enabled: Включен ли обработчик
        """
        super().__init__()
        self.bot_token = bot_token
        self.admin_chat_id = admin_chat_id
        self.log_level = log_level
        self.enabled = enabled
        
        # Rate limiting
        self._message_timestamps = deque()  # Временные метки отправленных сообщений
        self._message_queue = deque()  # Очередь сообщений для отправки
        self._grouping_window = 10  # Окно группировки в секундах
        self._max_logs_per_group = 20  # Максимум логов в одном сообщении
        
        # Статистика
        self._total_sent = 0
        self._total_dropped = 0
        self._last_send_time = None
        
        # Флаг для предотвращения множественных отправок
        self._sending = False
        self._pending_start = False
        
        # Настройка уровня логирования
        self._setup_log_level()
        
    def _setup_log_level(self):
        """Настройка уровня логирования на основе конфигурации"""
        if not self.enabled or self.log_level == "none":
            self.setLevel(logging.CRITICAL + 1)  # Отключаем все логи
        elif self.log_level == "error":
            self.setLevel(logging.ERROR)
        elif self.log_level == "warning":
            self.setLevel(logging.WARNING)
        elif self.log_level == "all":
            self.setLevel(logging.DEBUG)
        else:
            self.setLevel(logging.ERROR)
        # Ссылка на event loop, если доступен
        self._loop: asyncio.AbstractEventLoop | None = None

    def set_loop(self, loop: asyncio.AbstractEventLoop):
        """Устанавливает event loop для запуска фоновых задач логгера"""
        self._loop = loop
        # Если очередь не пуста и цикл уже запущен — сразу инициируем обработку
        self._ensure_processing(loop)
    
    def _should_filter_error(self, record: logging.LogRecord) -> bool:
        """
        Проверяет, нужно ли фильтровать ошибку (не отправлять в Telegram).
        
        Фильтрует сетевые ошибки Telegram API, которые aiogram обрабатывает автоматически.
        
        Args:
            record: Запись лога
            
        Returns:
            True если ошибку нужно отфильтровать, False если нужно отправить
        """
        message = record.getMessage().lower()
        pathname = record.pathname.lower()
        
        # Фильтруем ошибки из aiogram dispatcher._listen_updates
        # Это сетевые ошибки при получении обновлений, которые aiogram обрабатывает автоматически
        if 'dispatcher' in pathname and 'failed to fetch updates' in message:
            # Проверяем типичные сетевые ошибки
            network_error_patterns = [
                'telegramnetworkerror',
                'telegramservererror',
                'bad gateway',
                'request timeout',
                'cannot connect to host',
                'ssl record layer failure',
                'clientconnectorerror',
                'clientoserror',
                'ssl',
            ]
            
            for pattern in network_error_patterns:
                if pattern in message:
                    return True
        
        # Фильтруем специфичные сетевые ошибки по сообщению
        network_error_messages = [
            'telegram server says - bad gateway',
            'http client says - request timeout error',
            'http client says - cannot connect to host',
            'http client says - clientoserror',
            'http client says - clientconnectorerror',
            'ssl record layer failure',
        ]
        
        for error_msg in network_error_messages:
            if error_msg in message:
                return True
        
        return False
    
    def emit(self, record: logging.LogRecord):
        """
        Обработка лог-записи
        
        Args:
            record: Запись лога
        """
        if not self.enabled or self.log_level == "none":
            return
        
        # Фильтруем сетевые ошибки Telegram API
        if self._should_filter_error(record):
            return
            
        try:
            # Форматируем сообщение
            message = self._format_message(record)
            
            # Добавляем в очередь
            self._message_queue.append({
                'message': message,
                'timestamp': datetime.now(timezone.utc),
                'level': record.levelname
            })
            
            # Запускаем асинхронную отправку если не запущена
            if not self._sending:
                target_loop = self._loop

                # Если цикл не задан, пробуем использовать текущий активный
                try:
                    running_loop = asyncio.get_running_loop()
                except RuntimeError:
                    running_loop = None

                if target_loop is None:
                    target_loop = running_loop

                self._ensure_processing(target_loop, running_loop)
                
        except Exception as e:
            # Не логируем ошибки обработчика, чтобы избежать рекурсии
            print(f"Error in TelegramLoggerHandler.emit: {e}")
    
    def _format_message(self, record: logging.LogRecord) -> str:
        """
        Форматирование лог-записи в читаемое сообщение
        
        Args:
            record: Запись лога
            
        Returns:
            Отформатированное сообщение
        """
        # Иконки для уровней
        level_icons = {
            'DEBUG': '🔍',
            'INFO': 'ℹ️',
            'WARNING': '⚠️',
            'ERROR': '❌',
            'CRITICAL': '🚨'
        }
        
        icon = level_icons.get(record.levelname, '📝')
        
        # Время в UTC+3 (Moscow)
        moscow_tz = timezone(timedelta(hours=3))
        log_time = datetime.fromtimestamp(record.created, tz=moscow_tz)
        time_str = log_time.strftime('%d.%m.%Y %H:%M:%S')
        
        # Обработка специфичных сообщений
        message = record.getMessage()
        
        # Преобразуем SIGTERM предупреждение в информационное сообщение
        if "Received SIGTERM signal" in message or "Received SIGINT signal" in message:
            return (
                f"🛑 <b>Завершение работы</b> | {time_str}\n\n"
                f"ℹ️ <b>Статус:</b> Корректное завершение работы приложения\n"
                f"📝 <b>Детали:</b> Получен сигнал остановки от системы\n\n"
                f"Приложение корректно завершает работу и освобождает ресурсы."
            )
        
        # Преобразуем другие известные предупреждения
        if "signal_stop_polling" in record.funcName and "signal" in message.lower():
            return (
                f"🛑 <b>Остановка polling</b> | {time_str}\n\n"
                f"ℹ️ <b>Статус:</b> Корректная остановка бота\n"
                f"📝 <b>Детали:</b> Polling остановлен по сигналу от системы\n\n"
                f"Это нормальная операция при перезапуске или остановке приложения."
            )
        
        # Формируем заголовок
        header = f"{icon} <b>{record.levelname}</b> | {time_str}\n"
        
        # Информация о модуле
        module_info = f"📁 <b>Модуль:</b> {record.pathname}\n"
        module_info += f"🔧 <b>Функция:</b> {record.funcName} (строка {record.lineno})\n"
        
        # Сообщение
        message_text = f"💬 <b>Сообщение:</b> {message}\n"
        
        # Traceback для ошибок
        traceback_text = ""
        if record.exc_info:
            traceback_text = "\n📋 <b>Traceback:</b>\n"
            traceback_text += f"<pre>{traceback.format_exception(*record.exc_info)}</pre>"
        
        # Объединяем все части
        full_message = header + module_info + message_text + traceback_text
        
        # Ограничиваем длину сообщения
        if len(full_message) > self.MAX_MESSAGE_LENGTH:
            # Обрезаем traceback если он слишком длинный
            max_traceback_length = self.MAX_MESSAGE_LENGTH - len(header + module_info + message_text + "\n📋 <b>Traceback:</b>\n<pre>...")
            if traceback_text:
                traceback_text = f"\n📋 <b>Traceback:</b>\n<pre>{traceback.format_exception(*record.exc_info)[:max_traceback_length]}...</pre>"
                full_message = header + module_info + message_text + traceback_text
        
        return full_message
    
    async def _process_queue(self):
        """Асинхронная обработка очереди сообщений"""
        if self._sending:
            return
            
        self._sending = True
        
        try:
            while self._message_queue:
                # Проверяем rate limits
                await self._check_rate_limits()
                
                # Группируем сообщения
                grouped_messages = self._group_messages()
                
                # Отправляем группу
                for message in grouped_messages:
                    await self._send_message(message)
                    
                # Небольшая задержка между группами
                await asyncio.sleep(0.1)
                
        finally:
            self._sending = False
    
    def _group_messages(self) -> List[str]:
        """
        Группировка сообщений по времени
        
        Returns:
            Список сгруппированных сообщений
        """
        if not self._message_queue:
            return []
        
        current_time = datetime.now(timezone.utc)
        grouped = []
        current_group = []
        
        while self._message_queue:
            item = self._message_queue.popleft()
            
            # Проверяем, входит ли в текущее окно группировки
            time_diff = (current_time - item['timestamp']).total_seconds()
            
            if time_diff <= self._grouping_window and len(current_group) < self._max_logs_per_group:
                current_group.append(item)
            else:
                # Завершаем текущую группу и начинаем новую
                if current_group:
                    grouped.append(self._format_grouped_message(current_group))
                current_group = [item]
        
        # Добавляем последнюю группу
        if current_group:
            grouped.append(self._format_grouped_message(current_group))
        
        return grouped
    
    def _format_grouped_message(self, logs: List[Dict]) -> str:
        """
        Форматирование группы логов в одно сообщение
        
        Args:
            logs: Список логов для группировки
            
        Returns:
            Отформатированное сообщение
        """
        if len(logs) == 1:
            return logs[0]['message']
        
        # Заголовок группы
        header = f"📦 <b>Группа логов ({len(logs)} записей)</b>\n"
        header += f"⏰ <b>Время:</b> {logs[0]['timestamp'].strftime('%d.%m.%Y %H:%M:%S')}\n\n"
        
        # Счетчики по уровням
        level_counts = {}
        for log in logs:
            level = log['level']
            level_counts[level] = level_counts.get(level, 0) + 1
        
        # Статистика
        stats = "📊 <b>Статистика:</b>\n"
        for level, count in sorted(level_counts.items()):
            stats += f"  • {level}: {count}\n"
        stats += "\n"
        
        # Первые несколько логов (максимум 5)
        logs_text = "📋 <b>Последние логи:</b>\n\n"
        for i, log in enumerate(logs[:5], 1):
            logs_text += f"<b>{i}.</b> {log['message'][:500]}...\n\n"
        
        if len(logs) > 5:
            logs_text += f"<i>... и еще {len(logs) - 5} логов</i>"
        
        return header + stats + logs_text
    
    def _ensure_processing(
        self,
        loop: Optional[asyncio.AbstractEventLoop] = None,
        running_loop: Optional[asyncio.AbstractEventLoop] = None
    ) -> None:
        """
        Гарантирует запуск фоновой задачи обработки очереди.

        Args:
            loop: Целевой цикл событий. Если не передан, используется сохраненный.
            running_loop: Активный цикл, из которого вызвали метод (если есть).
        """
        loop = loop or self._loop

        if loop is None:
            # Нет доступного цикла — обработаем позже при появлении
            self._pending_start = True
            return

        if not loop.is_running():
            # Цикл еще не стартовал — отметим и вернемся позже
            self._pending_start = True
            return

        self._pending_start = False

        def runner():
            if self._sending:
                return
            task = loop.create_task(self._process_queue())
            task.add_done_callback(self._handle_task_exception)

        try:
            current_loop = running_loop or asyncio.get_running_loop()
        except RuntimeError:
            current_loop = None

        try:
            if current_loop is loop:
                loop.call_soon(runner)
            else:
                loop.call_soon_threadsafe(runner)
        except RuntimeError as err:
            # Возможны ситуации с закрытым циклом — запомним и попробуем позже
            self._pending_start = True
            print(f"TelegramLoggerHandler: failed to schedule queue processing: {err}")

    @staticmethod
    def _handle_task_exception(task: asyncio.Task) -> None:
        """Выводит исключения фоновой задачи, если они возникли."""
        try:
            task.result()
        except Exception as exc:  # noqa: BLE001
            print(f"TelegramLoggerHandler: queue processing error: {exc}")

    async def _check_rate_limits(self):
        """
        Проверка и соблюдение rate limits Telegram API
        
        Удаляет старые временные метки и добавляет задержку если необходимо
        """
        current_time = datetime.now(timezone.utc)
        
        # Удаляем старые метки (старше 1 минуты)
        while self._message_timestamps and (current_time - self._message_timestamps[0]).total_seconds() > 60:
            self._message_timestamps.popleft()
        
        # Проверяем лимит на минуту
        if len(self._message_timestamps) >= self.MAX_MESSAGES_PER_MINUTE:
            # Ждем пока не освободится место
            wait_time = 60 - (current_time - self._message_timestamps[0]).total_seconds()
            if wait_time > 0:
                await asyncio.sleep(wait_time)
                # Обновляем время после ожидания
                current_time = datetime.now(timezone.utc)
                # Очищаем старые метки
                while self._message_timestamps and (current_time - self._message_timestamps[0]).total_seconds() > 60:
                    self._message_timestamps.popleft()
        
        # Проверяем лимит на секунду
        recent_messages = [ts for ts in self._message_timestamps if (current_time - ts).total_seconds() <= 1]
        if len(recent_messages) >= self.MAX_MESSAGES_PER_SECOND:
            # Ждем 1 секунду
            await asyncio.sleep(1)
    
    async def _send_message(self, message: str):
        """
        Отправка сообщения в Telegram
        
        Args:
            message: Текст сообщения
        """
        if not self.bot_token or not self.admin_chat_id:
            return
        
        try:
            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            payload = {
                'chat_id': self.admin_chat_id,
                'text': message,
                'parse_mode': 'HTML',
                'disable_web_page_preview': True
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=10)) as response:
                    if response.status == 200:
                        self._message_timestamps.append(datetime.now(timezone.utc))
                        self._total_sent += 1
                        self._last_send_time = datetime.now(timezone.utc)
                    else:
                        self._total_dropped += 1
                        print(f"Failed to send message to Telegram: {response.status}")
                        
        except asyncio.TimeoutError:
            self._total_dropped += 1
            print("Timeout while sending message to Telegram")
        except Exception as e:
            self._total_dropped += 1
            print(f"Error sending message to Telegram: {e}")
    
    async def send_test_message(self, message: str = "🧪 Тестовое сообщение от бота логирования"):
        """
        Отправка тестового сообщения
        
        Args:
            message: Текст тестового сообщения
        """
        if not self.enabled:
            return {"success": False, "message": "Бот логирования отключен"}
        
        try:
            await self._send_message(message)
            return {"success": True, "message": "Тестовое сообщение отправлено"}
        except Exception as e:
            return {"success": False, "message": f"Ошибка отправки: {str(e)}"}
    
    def get_stats(self) -> Dict:
        """
        Получение статистики обработчика
        
        Returns:
            Словарь со статистикой
        """
        return {
            'enabled': self.enabled,
            'log_level': self.log_level,
            'total_sent': self._total_sent,
            'total_dropped': self._total_dropped,
            'queue_size': len(self._message_queue),
            'last_send_time': self._last_send_time.isoformat() if self._last_send_time else None
        }


def create_telegram_logger_handler(bot_token: str, admin_chat_id: str, log_level: str = "error") -> TelegramLoggerHandler:
    """
    Фабричная функция для создания обработчика Telegram логов
    
    Args:
        bot_token: Токен Telegram бота
        admin_chat_id: ID чата администратора
        log_level: Уровень логирования (none, error, warning, all)
        
    Returns:
        Настроенный обработчик логов
    """
    enabled = bool(bot_token and admin_chat_id and log_level != "none")
    return TelegramLoggerHandler(
        bot_token=bot_token,
        admin_chat_id=admin_chat_id,
        log_level=log_level,
        enabled=enabled
    )
