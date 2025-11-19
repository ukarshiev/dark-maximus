#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Unit-тесты для обработчика ошибок роутера

Тестирует обработку различных ошибок в user_router, включая устаревшие callback queries.
"""

import pytest
import sys
import allure
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from aiogram.types import Update, CallbackQuery, Message, User, Chat, ErrorEvent
from aiogram.exceptions import TelegramBadRequest, TelegramNetworkError

# Добавляем путь к проекту
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root / "src"))


@allure.epic("Обработчики бота")
@allure.feature("Обработка ошибок роутера")
@allure.label("package", "src.shop_bot.handlers")
@pytest.mark.unit
@pytest.mark.bot
class TestRouterErrorHandler:
    """Тесты для обработчика ошибок роутера"""

    @pytest.mark.asyncio
    @allure.title("Обработка устаревшего callback query в error handler")
    @allure.description("""
    Проверяет корректную обработку устаревшего callback query в user_router_error_handler.
    
    **Что проверяется:**
    - Error handler НЕ логирует устаревшие callback queries как CRITICAL
    - Error handler логирует устаревшие callback queries как DEBUG
    - Error handler не отправляет уведомления пользователю при устаревшем callback query
    - Корректная обработка ошибки "query is too old and response timeout expired"
    
    **Важность:**
    Этот тест критически важен, так как проверяет исправление проблемы,
    когда устаревшие callback queries логировались как CRITICAL ошибки в production.
    
    **Тестовые данные:**
    - Использует фикстуру expired_callback_query
    """)
    @allure.severity(allure.severity_level.CRITICAL)
    @allure.tag("error_handler", "expired_query", "logging", "unit")
    async def test_error_handler_expired_callback_query(self, temp_db, mock_bot, expired_callback_query):
        """Тест обработки устаревшего callback query в error handler"""
        import shop_bot.bot.handlers as handlers_module
        from aiogram import Bot
        
        # Создаем ErrorEvent с устаревшим callback query
        update = MagicMock(spec=Update)
        update.callback_query = expired_callback_query
        update.message = None
        
        error = TelegramBadRequest(
            method="answerCallbackQuery",
            message="Bad Request: query is too old and response timeout expired or query ID is invalid"
        )
        
        error_event = MagicMock(spec=ErrorEvent)
        error_event.exception = error
        error_event.update = update
        
        # Получаем error handler
        user_router = handlers_module.get_user_router()
        error_handler = None
        for handler_obj in user_router.errors.handlers:
            if hasattr(handler_obj, 'callback'):
                callback_name = getattr(handler_obj.callback, '__name__', '')
                if callback_name == 'user_router_error_handler':
                    error_handler = handler_obj.callback
                    break
        
        assert error_handler is not None, "user_router_error_handler не найден в роутере"
        
        # Вызываем error handler
        # Он должен обработать устаревший callback query без логирования как CRITICAL
        with patch('shop_bot.bot.handlers.logger') as mock_logger:
            await error_handler(error_event, mock_bot)
            
            # Проверяем, что НЕ было логирования как CRITICAL
            critical_calls = [call for call in mock_logger.method_calls if call[0] == 'critical']
            assert len(critical_calls) == 0, "Устаревший callback query не должен логироваться как CRITICAL"
            
            # Проверяем, что было логирование как DEBUG
            debug_calls = [call for call in mock_logger.method_calls if call[0] == 'debug']
            assert len(debug_calls) > 0, "Устаревший callback query должен логироваться как DEBUG"

    @pytest.mark.asyncio
    @allure.title("Проверка, что устаревшие callback queries не логируются как CRITICAL")
    @allure.description("""
    Проверяет, что устаревшие callback queries не логируются как CRITICAL ошибки.
    
    **Что проверяется:**
    - Отсутствие вызовов logger.critical() для устаревших callback queries
    - Наличие вызовов logger.debug() для устаревших callback queries
    - Правильный уровень логирования для устаревших callback queries
    
    **Важность:**
    Этот тест проверяет исправление проблемы с неправильным уровнем логирования,
    что приводило к засорению логов CRITICAL ошибками для нормальных ситуаций.
    
    **Тестовые данные:**
    - user_id: 123459
    - Ошибка: "query is too old and response timeout expired or query ID is invalid"
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("error_handler", "expired_query", "logging", "unit")
    async def test_error_handler_expired_callback_not_critical(self, temp_db, mock_bot):
        """Проверка, что устаревшие callback queries не логируются как CRITICAL"""
        import shop_bot.bot.handlers as handlers_module
        from aiogram import Bot
        
        # Создаем ErrorEvent с устаревшим callback query
        callback = MagicMock(spec=CallbackQuery)
        callback.from_user = MagicMock(spec=User)
        callback.from_user.id = 123459
        
        update = MagicMock(spec=Update)
        update.callback_query = callback
        update.message = None
        
        error = TelegramBadRequest(
            method="answerCallbackQuery",
            message="Bad Request: query is too old and response timeout expired or query ID is invalid"
        )
        
        error_event = MagicMock(spec=ErrorEvent)
        error_event.exception = error
        error_event.update = update
        
        # Получаем error handler
        user_router = handlers_module.get_user_router()
        error_handler = None
        for handler_obj in user_router.errors.handlers:
            if hasattr(handler_obj, 'callback'):
                callback_name = getattr(handler_obj.callback, '__name__', '')
                if callback_name == 'user_router_error_handler':
                    error_handler = handler_obj.callback
                    break
        
        assert error_handler is not None, "user_router_error_handler не найден в роутере"
        
        # Вызываем error handler с патчем logger
        with patch('shop_bot.bot.handlers.logger') as mock_logger:
            await error_handler(error_event, mock_bot)
            
            # Проверяем, что НЕ было вызова logger.critical
            critical_calls = [call for call in mock_logger.method_calls if call[0] == 'critical']
            assert len(critical_calls) == 0, f"Устаревший callback query не должен логироваться как CRITICAL, но было {len(critical_calls)} вызовов"
            
            # Проверяем, что был вызов logger.debug
            debug_calls = [call for call in mock_logger.method_calls if call[0] == 'debug']
            assert len(debug_calls) > 0, "Устаревший callback query должен логироваться как DEBUG"

    @pytest.mark.asyncio
    @allure.title("Обработка других ошибок в callback query handlers")
    @allure.description("""
    Проверяет обработку других ошибок (не устаревших callback queries) в error handler.
    
    **Что проверяется:**
    - Error handler логирует другие ошибки как CRITICAL
    - Правильное различие в обработке устаревших и других ошибок
    - Корректная обработка различных типов ошибок в callback query handlers
    
    **Тестовые данные:**
    - user_id: 123460
    - Ошибка: ValueError("Some other error")
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("error_handler", "callback_query", "error_handling", "unit")
    async def test_error_handler_other_callback_errors(self, temp_db, mock_bot):
        """Тест обработки других ошибок в callback query handlers"""
        import shop_bot.bot.handlers as handlers_module
        from aiogram import Bot
        
        # Создаем ErrorEvent с другой ошибкой (не устаревший callback)
        callback = MagicMock(spec=CallbackQuery)
        callback.from_user = MagicMock(spec=User)
        callback.from_user.id = 123460
        callback.answer = AsyncMock()
        
        update = MagicMock(spec=Update)
        update.callback_query = callback
        update.message = None
        
        # Создаем другую ошибку (не устаревший callback)
        error = ValueError("Some other error")
        
        error_event = MagicMock(spec=ErrorEvent)
        error_event.exception = error
        error_event.update = update
        
        # Получаем error handler
        user_router = handlers_module.get_user_router()
        error_handler = None
        for handler_obj in user_router.errors.handlers:
            if hasattr(handler_obj, 'callback'):
                callback_name = getattr(handler_obj.callback, '__name__', '')
                if callback_name == 'user_router_error_handler':
                    error_handler = handler_obj.callback
                    break
        
        assert error_handler is not None, "user_router_error_handler не найден в роутере"
        
        # Вызываем error handler
        with patch('shop_bot.bot.handlers.logger') as mock_logger:
            # Мокируем callback.answer чтобы не выбрасывать ошибку при попытке отправить уведомление
            callback.answer = AsyncMock()
            
            await error_handler(error_event, mock_bot)
            
            # Проверяем, что было логирование как CRITICAL для других ошибок
            critical_calls = [call for call in mock_logger.method_calls if call[0] == 'critical']
            assert len(critical_calls) > 0, "Другие ошибки должны логироваться как CRITICAL"

    @pytest.mark.asyncio
    @allure.title("Обработка ошибок в message handlers")
    @allure.description("""
    Проверяет обработку ошибок в message handlers через error handler.
    
    **Что проверяется:**
    - Error handler логирует ошибки в message handlers как CRITICAL
    - Отправка уведомления пользователю об ошибке
    - Корректная обработка ошибок в message handlers
    
    **Тестовые данные:**
    - user_id: 123461
    - Ошибка: ValueError("Error in message handler")
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("error_handler", "message_handler", "error_handling", "unit")
    async def test_error_handler_message_handler_errors(self, temp_db, mock_bot):
        """Тест обработки ошибок в message handlers"""
        import shop_bot.bot.handlers as handlers_module
        from aiogram import Bot
        
        # Создаем ErrorEvent с ошибкой в message handler
        message = MagicMock(spec=Message)
        message.from_user = MagicMock(spec=User)
        message.from_user.id = 123461
        message.answer = AsyncMock()
        message.chat = MagicMock(spec=Chat)
        message.chat.id = 123461
        
        update = MagicMock(spec=Update)
        update.message = message
        update.callback_query = None
        
        # Создаем ошибку
        error = ValueError("Error in message handler")
        
        error_event = MagicMock(spec=ErrorEvent)
        error_event.exception = error
        error_event.update = update
        
        # Получаем error handler
        user_router = handlers_module.get_user_router()
        error_handler = None
        for handler_obj in user_router.errors.handlers:
            if hasattr(handler_obj, 'callback'):
                callback_name = getattr(handler_obj.callback, '__name__', '')
                if callback_name == 'user_router_error_handler':
                    error_handler = handler_obj.callback
                    break
        
        assert error_handler is not None, "user_router_error_handler не найден в роутере"
        
        # Вызываем error handler
        with patch('shop_bot.bot.handlers.logger') as mock_logger:
            await error_handler(error_event, mock_bot)
            
            # Проверяем, что было логирование как CRITICAL
            critical_calls = [call for call in mock_logger.method_calls if call[0] == 'critical']
            assert len(critical_calls) > 0, "Ошибки в message handlers должны логироваться как CRITICAL"
            
            # Проверяем, что было отправлено сообщение пользователю
            message.answer.assert_called_once()

