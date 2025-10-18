# -*- coding: utf-8 -*-
"""
Middleware для Telegram-бота с кэшированием
"""

import asyncio
import logging
from typing import Callable, Dict, Any, Awaitable, Optional
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery, Chat
from functools import lru_cache
from datetime import datetime, timedelta
from shop_bot.utils.performance_monitor import get_performance_monitor

logger = logging.getLogger(__name__)

# Кэш для проверки бана пользователей
_user_ban_cache: Dict[int, tuple[bool, datetime]] = {}
CACHE_TTL = 300  # 5 минут

class BanMiddleware(BaseMiddleware):
    """Middleware для проверки бана пользователей с кэшированием"""
    
    def __init__(self):
        super().__init__()
        self._cache_cleanup_task = None
    
    def _start_cache_cleanup(self):
        """Запуск задачи очистки кэша"""
        try:
            if self._cache_cleanup_task is None or self._cache_cleanup_task.done():
                self._cache_cleanup_task = asyncio.create_task(self._cleanup_cache())
        except RuntimeError:
            # Event loop еще не запущен, запустим позже
            pass
    
    async def _cleanup_cache(self):
        """Очистка устаревших записей из кэша"""
        while True:
            try:
                await asyncio.sleep(60)  # Проверяем каждую минуту
                current_time = datetime.now()
                expired_users = [
                    user_id for user_id, (_, cache_time) in _user_ban_cache.items()
                    if current_time - cache_time > timedelta(seconds=CACHE_TTL)
                ]
                for user_id in expired_users:
                    _user_ban_cache.pop(user_id, None)
                if expired_users:
                    logger.debug(f"Cleaned up {len(expired_users)} expired cache entries")
            except Exception as e:
                logger.error(f"Error in cache cleanup: {e}")
    
    async def _is_user_banned_cached(self, user_id: int) -> bool:
        """Проверка бана пользователя с кэшированием"""
        current_time = datetime.now()
        
        # Проверяем кэш
        if user_id in _user_ban_cache:
            is_banned, cache_time = _user_ban_cache[user_id]
            if current_time - cache_time < timedelta(seconds=CACHE_TTL):
                return is_banned
        
        # Если нет в кэше или кэш устарел, запрашиваем из БД
        try:
            from shop_bot.data_manager.async_database import get_user_async
            user_data = await get_user_async(user_id)
            is_banned = user_data and user_data.get('is_banned', False)
            
            # Обновляем кэш
            _user_ban_cache[user_id] = (is_banned, current_time)
            return is_banned
        except Exception as e:
            logger.error(f"Error checking user ban status for {user_id}: {e}")
            return False
    
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        # Запускаем очистку кэша, если еще не запущена
        self._start_cache_cleanup()
        
        user = data.get('event_from_user')
        if not user:
            return await handler(event, data)

        # Проверяем бан с кэшированием
        is_banned = await self._is_user_banned_cached(user.id)
        
        if is_banned:
            ban_message_text = "Вы заблокированы и не можете использовать этого бота."
            if isinstance(event, CallbackQuery):
                await event.answer(ban_message_text, show_alert=True)
            elif isinstance(event, Message):
                await event.answer(ban_message_text)
            return
        
        return await handler(event, data)

class PerformanceMiddleware(BaseMiddleware):
    """Middleware для мониторинга производительности"""
    
    def __init__(self, log_slow_requests: bool = True, slow_threshold: float = 1.0):
        super().__init__()
        self.log_slow_requests = log_slow_requests
        self.slow_threshold = slow_threshold
    
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        start_time = asyncio.get_event_loop().time()
        
        try:
            result = await handler(event, data)
            return result
        finally:
            end_time = asyncio.get_event_loop().time()
            duration = end_time - start_time
            
            if self.log_slow_requests and duration > self.slow_threshold:
                event_type = type(event).__name__
                user_id = getattr(event.from_user, 'id', 'unknown') if hasattr(event, 'from_user') else 'unknown'
                logger.warning(f"Slow request detected: {event_type} from user {user_id} took {duration:.2f}s")
            
            # Логируем все запросы в debug режиме
            if logger.isEnabledFor(logging.DEBUG):
                event_type = type(event).__name__
                user_id = getattr(event.from_user, 'id', 'unknown') if hasattr(event, 'from_user') else 'unknown'
                logger.debug(f"Request processed: {event_type} from user {user_id} in {duration:.3f}s")

            # Записываем метрику в глобальный монитор (охват всех обработчиков)
            try:
                monitor = get_performance_monitor()
                # Улучшенное имя операции: пытаемся взять конкретный handler, иначе тип события
                handler_obj = data.get('handler') if isinstance(data, dict) else None
                handler_name = getattr(handler_obj, '__name__', None) or getattr(handler, '__name__', None)
                event_type = type(event).__name__
                
                # Добавляем подробное логирование для отладки
                logger.info(f"PerformanceMiddleware: handler_obj={handler_obj}, handler_name={handler_name}, event_type={event_type}, data_keys={list(data.keys()) if isinstance(data, dict) else 'not_dict'}")
                
                # Создаем более читаемые имена операций
                if handler_name:
                    # Убираем суффиксы _handler, _message, _callback для читаемости
                    clean_name = handler_name.replace('_handler', '').replace('_message', '').replace('_callback', '')
                    operation_name = clean_name
                else:
                    operation_name = event_type
                
                user_id = getattr(event, 'from_user', None)
                user_id = getattr(user_id, 'id', None) if user_id else None
                
                logger.debug(f"PerformanceMiddleware: recording metric - operation={operation_name}, duration={duration}, user_id={user_id}")
                
                # В middleware мы не знаем про успех/ошибку, поэтому считаем успехом
                await monitor.record_metric(
                    operation=operation_name,
                    duration=duration,
                    user_id=user_id,
                    success=True
                )
            except Exception as e:
                logger.error(f"PerformanceMiddleware: failed to record metric: {e}", exc_info=True)

class RateLimitMiddleware(BaseMiddleware):
    """Middleware для ограничения частоты запросов"""
    
    def __init__(self, max_requests_per_minute: int = 30):
        super().__init__()
        self.max_requests = max_requests_per_minute
        self._user_requests: Dict[int, list] = {}
    
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        user = data.get('event_from_user')
        if not user:
            return await handler(event, data)
        
        current_time = datetime.now()
        user_id = user.id
        
        # Очищаем старые запросы (старше минуты)
        if user_id in self._user_requests:
            self._user_requests[user_id] = [
                req_time for req_time in self._user_requests[user_id]
                if current_time - req_time < timedelta(minutes=1)
            ]
        else:
            self._user_requests[user_id] = []
        
        # Добавляем текущий запрос
        self._user_requests[user_id].append(current_time)
        
        # Проверяем, нужно ли предупредить пользователя (28-й запрос)
        if len(self._user_requests[user_id]) == self.max_requests - 2:
            warning_message = "⚠️ Внимание! Сработала защита от спам команд.\nВы будете ограничены на некоторое время.\nЕсли вы продолжите спамить, то бот заблокирует вас."
            
            # Логируем предупреждение
            logger.warning(f"Rate limiting warning for user {user_id}: {len(self._user_requests[user_id])} requests in the last minute")
            
            if isinstance(event, CallbackQuery):
                await event.answer(warning_message, show_alert=True)
            elif isinstance(event, Message):
                await event.answer(warning_message)
        
        # Проверяем лимит ПОСЛЕ добавления текущего запроса
        if len(self._user_requests[user_id]) >= self.max_requests:
            warning_message = "⚠️ Внимание! Сработала защита от спам команд.\nВы будете ограничены на некоторое время.\nЕсли вы продолжите спамить, то бот заблокирует вас."
            
            # Логируем срабатывание rate limiting
            logger.warning(f"Rate limiting triggered for user {user_id}: {len(self._user_requests[user_id])} requests in the last minute")
            
            if isinstance(event, CallbackQuery):
                await event.answer(warning_message, show_alert=True)
            elif isinstance(event, Message):
                await event.answer(warning_message)
            return
        
        return await handler(event, data)
