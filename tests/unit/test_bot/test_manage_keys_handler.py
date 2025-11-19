#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Unit-тесты для обработчика manage_keys_handler

Тестирует обработку callback query для управления ключами пользователя,
включая обработку устаревших callback queries.
"""

import pytest
import sys
import allure
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from aiogram.types import CallbackQuery, User, Message, Chat
from aiogram.exceptions import TelegramBadRequest

# Добавляем путь к проекту
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root / "src"))


@allure.epic("Обработчики бота")
@allure.feature("Управление ключами")
@allure.label("package", "src.shop_bot.handlers")
@pytest.mark.unit
@pytest.mark.bot
@pytest.mark.database
class TestManageKeysHandler:
    """Тесты для обработчика manage_keys_handler"""

    @pytest.mark.asyncio
    @allure.title("Успешная обработка manage_keys с ключами у пользователя")
    @allure.description("""
    Проверяет успешную обработку callback query "manage_keys" когда у пользователя есть ключи.
    
    **Что проверяется:**
    - Вызов callback.answer() для подтверждения получения callback query
    - Вызов callback.message.edit_text() с правильным текстом
    - Отображение текста "Ваши ключи:" или содержащего слово "ключ"
    - Корректная работа handler при наличии ключей в БД
    
    **Тестовые данные:**
    - user_id: 123456
    - host_name: 'test_host'
    - key_email: 'test@example.com'
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("manage_keys", "callback_query", "keys_management", "unit")
    async def test_manage_keys_success_with_keys(self, temp_db, mock_bot):
        """Тест успешного сценария с ключами у пользователя"""
        from shop_bot.data_manager.database import (
            register_user_if_not_exists,
            add_new_key,
            create_host,
        )
        import shop_bot.bot.handlers as handlers_module
        
        # Настройка БД
        user_id = 123456
        register_user_if_not_exists(user_id, "test_user", None, "Test User")
        
        # Создаем хост и ключ
        create_host("test_host", "http://test.com", "user", "pass", 1, "testcode")
        # expiry_timestamp_ms должен быть int (timestamp в миллисекундах) или 0 для бессрочного
        add_new_key(
            user_id=user_id,
            host_name="test_host",
            xui_client_uuid="test-uuid-123",
            key_email="test@example.com",
            expiry_timestamp_ms=0,  # 0 означает бессрочный ключ
            protocol="vless"
        )
        
        # Создаем мок для callback
        callback = MagicMock(spec=CallbackQuery)
        callback.data = "manage_keys"
        callback.from_user = MagicMock(spec=User)
        callback.from_user.id = user_id
        callback.answer = AsyncMock()
        callback.message = MagicMock(spec=Message)
        callback.message.edit_text = AsyncMock()
        callback.message.chat = MagicMock(spec=Chat)
        callback.message.chat.id = user_id
        
        # Получаем handler из роутера
        import shop_bot.bot.handlers as handlers_module
        user_router = handlers_module.get_user_router()
        
        # Находим handler для manage_keys по фильтрам
        handler = None
        for handler_obj in user_router.callback_query.handlers:
            if hasattr(handler_obj, 'filters'):
                try:
                    filters_list = list(handler_obj.filters) if handler_obj.filters else []
                    for f in filters_list:
                        if 'manage_keys' in str(f) or (hasattr(f, 'callback') and 'manage_keys' in str(f.callback)):
                            handler = handler_obj.callback
                            break
                    if handler:
                        break
                except:
                    pass
            # Также проверяем по имени функции
            if hasattr(handler_obj, 'callback'):
                callback_name = getattr(handler_obj.callback, '__name__', '')
                if callback_name == 'manage_keys_handler':
                    handler = handler_obj.callback
                    break
        
        assert handler is not None, "manage_keys_handler не найден в роутере"
        
        # Вызываем handler
        await handler(callback)
        
        # Проверяем, что callback.answer был вызван
        callback.answer.assert_called_once()
        
        # Проверяем, что edit_text был вызван с правильным текстом
        callback.message.edit_text.assert_called_once()
        call_args = callback.message.edit_text.call_args
        assert "Ваши ключи:" in call_args[0][0] or "ключ" in call_args[0][0].lower()

    @pytest.mark.asyncio
    @allure.title("Успешная обработка manage_keys без ключей у пользователя")
    @allure.description("""
    Проверяет успешную обработку callback query "manage_keys" когда у пользователя нет ключей.
    
    **Что проверяется:**
    - Вызов callback.answer() для подтверждения получения callback query
    - Вызов callback.message.edit_text() с правильным текстом
    - Отображение текста "У вас пока нет ключей" или содержащего "нет ключей"
    - Корректная работа handler при отсутствии ключей в БД
    
    **Тестовые данные:**
    - user_id: 123457
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("manage_keys", "callback_query", "keys_management", "unit")
    async def test_manage_keys_success_without_keys(self, temp_db, mock_bot):
        """Тест успешного сценария без ключей"""
        from shop_bot.data_manager.database import register_user_if_not_exists
        import shop_bot.bot.handlers as handlers_module
        
        # Настройка БД
        user_id = 123457
        register_user_if_not_exists(user_id, "test_user2", None, "Test User 2")
        
        # Создаем мок для callback
        callback = MagicMock(spec=CallbackQuery)
        callback.data = "manage_keys"
        callback.from_user = MagicMock(spec=User)
        callback.from_user.id = user_id
        callback.answer = AsyncMock()
        callback.message = MagicMock(spec=Message)
        callback.message.edit_text = AsyncMock()
        callback.message.chat = MagicMock(spec=Chat)
        callback.message.chat.id = user_id
        
        # Получаем handler из роутера
        import shop_bot.bot.handlers as handlers_module
        user_router = handlers_module.get_user_router()
        
        # Находим handler для manage_keys по фильтрам
        handler = None
        for handler_obj in user_router.callback_query.handlers:
            if hasattr(handler_obj, 'filters'):
                try:
                    filters_list = list(handler_obj.filters) if handler_obj.filters else []
                    for f in filters_list:
                        if 'manage_keys' in str(f) or (hasattr(f, 'callback') and 'manage_keys' in str(f.callback)):
                            handler = handler_obj.callback
                            break
                    if handler:
                        break
                except:
                    pass
            # Также проверяем по имени функции
            if hasattr(handler_obj, 'callback'):
                callback_name = getattr(handler_obj.callback, '__name__', '')
                if callback_name == 'manage_keys_handler':
                    handler = handler_obj.callback
                    break
        
        assert handler is not None, "manage_keys_handler не найден в роутере"
        
        # Вызываем handler
        await handler(callback)
        
        # Проверяем, что callback.answer был вызван
        callback.answer.assert_called_once()
        
        # Проверяем, что edit_text был вызван с правильным текстом (без ключей)
        callback.message.edit_text.assert_called_once()
        call_args = callback.message.edit_text.call_args
        assert "нет ключей" in call_args[0][0].lower() or "у вас пока нет" in call_args[0][0].lower()

    @pytest.mark.asyncio
    @allure.title("Обработка устаревшего callback query в manage_keys_handler")
    @allure.description("""
    Проверяет корректную обработку устаревшего callback query в manage_keys_handler.
    
    **Что проверяется:**
    - Handler обрабатывает TelegramBadRequest для устаревших callback queries
    - Handler продолжает выполнение после обработки ошибки (не выбрасывает исключение)
    - Вызов callback.message.edit_text() происходит даже при устаревшем callback query
    - Handler корректно обрабатывает ошибку "query is too old and response timeout expired"
    
    **Важность:**
    Этот тест критически важен, так как проверяет обработку реальной проблемы,
    которая возникала в production и логировалась как CRITICAL ошибка.
    
    **Тестовые данные:**
    - Использует фикстуру expired_callback_query
    - user_id: из expired_callback_query
    """)
    @allure.severity(allure.severity_level.CRITICAL)
    @allure.tag("manage_keys", "callback_query", "expired_query", "error_handling", "unit")
    async def test_manage_keys_expired_callback_query(self, temp_db, mock_bot, expired_callback_query):
        """Тест обработки устаревшего callback query"""
        from shop_bot.data_manager.database import register_user_if_not_exists
        import shop_bot.bot.handlers as handlers_module
        
        # Настройка БД
        user_id = expired_callback_query.from_user.id
        register_user_if_not_exists(user_id, "test_user3", None, "Test User 3")
        
        # Получаем handler из роутера
        import shop_bot.bot.handlers as handlers_module
        user_router = handlers_module.get_user_router()
        
        # Находим handler для manage_keys по фильтрам
        handler = None
        for handler_obj in user_router.callback_query.handlers:
            if hasattr(handler_obj, 'filters'):
                try:
                    filters_list = list(handler_obj.filters) if handler_obj.filters else []
                    for f in filters_list:
                        if 'manage_keys' in str(f) or (hasattr(f, 'callback') and 'manage_keys' in str(f.callback)):
                            handler = handler_obj.callback
                            break
                    if handler:
                        break
                except:
                    pass
            # Также проверяем по имени функции
            if hasattr(handler_obj, 'callback'):
                callback_name = getattr(handler_obj.callback, '__name__', '')
                if callback_name == 'manage_keys_handler':
                    handler = handler_obj.callback
                    break
        
        assert handler is not None, "manage_keys_handler не найден в роутере"
        
        # Вызываем handler с устаревшим callback query
        # Handler должен обработать ошибку и продолжить выполнение
        await handler(expired_callback_query)
        
        # Проверяем, что edit_text был вызван (handler продолжил работу после ошибки)
        expired_callback_query.message.edit_text.assert_called_once()
        
        # Проверяем, что answer был вызван (но выбросил исключение)
        assert expired_callback_query.answer.called

    @pytest.mark.asyncio
    @allure.title("Обработка других TelegramBadRequest ошибок в manage_keys_handler")
    @allure.description("""
    Проверяет, что handler правильно обрабатывает другие TelegramBadRequest ошибки
    (не устаревшие callback queries).
    
    **Что проверяется:**
    - Handler выбрасывает исключение для других TelegramBadRequest ошибок
    - Handler НЕ продолжает выполнение при других ошибках
    - callback.message.edit_text() НЕ вызывается при других ошибках
    - Различие в обработке устаревших и других TelegramBadRequest ошибок
    
    **Тестовые данные:**
    - user_id: 123458
    - Ошибка: "Bad Request: some other error" (не устаревший callback)
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("manage_keys", "callback_query", "error_handling", "telegram_bad_request", "unit")
    async def test_manage_keys_other_telegram_bad_request(self, temp_db, mock_bot):
        """Тест обработки других TelegramBadRequest ошибок"""
        from shop_bot.data_manager.database import register_user_if_not_exists
        import shop_bot.bot.handlers as handlers_module
        
        # Настройка БД
        user_id = 123458
        register_user_if_not_exists(user_id, "test_user4", None, "Test User 4")
        
        # Создаем мок для callback с другой ошибкой TelegramBadRequest
        callback = MagicMock(spec=CallbackQuery)
        callback.data = "manage_keys"
        callback.from_user = MagicMock(spec=User)
        callback.from_user.id = user_id
        callback.message = MagicMock(spec=Message)
        callback.message.edit_text = AsyncMock()
        callback.message.chat = MagicMock(spec=Chat)
        callback.message.chat.id = user_id
        
        # Настраиваем answer() чтобы выбрасывать другую ошибку TelegramBadRequest
        async def other_error_answer(*args, **kwargs):
            raise TelegramBadRequest(
                method="answerCallbackQuery",
                message="Bad Request: some other error"
            )
        
        callback.answer = AsyncMock(side_effect=other_error_answer)
        
        # Получаем handler из роутера
        import shop_bot.bot.handlers as handlers_module
        user_router = handlers_module.get_user_router()
        
        # Находим handler для manage_keys по фильтрам
        handler = None
        for handler_obj in user_router.callback_query.handlers:
            if hasattr(handler_obj, 'filters'):
                try:
                    filters_list = list(handler_obj.filters) if handler_obj.filters else []
                    for f in filters_list:
                        if 'manage_keys' in str(f) or (hasattr(f, 'callback') and 'manage_keys' in str(f.callback)):
                            handler = handler_obj.callback
                            break
                    if handler:
                        break
                except:
                    pass
            # Также проверяем по имени функции
            if hasattr(handler_obj, 'callback'):
                callback_name = getattr(handler_obj.callback, '__name__', '')
                if callback_name == 'manage_keys_handler':
                    handler = handler_obj.callback
                    break
        
        assert handler is not None, "manage_keys_handler не найден в роутере"
        
        # Вызываем handler - должна быть выброшена ошибка (не устаревший callback)
        with pytest.raises(TelegramBadRequest):
            await handler(callback)
        
        # Проверяем, что edit_text НЕ был вызван (handler выбросил исключение)
        assert not callback.message.edit_text.called

