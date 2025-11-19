#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Unit-тесты для обработчика toggle_key_auto_renewal_handler

Тестирует обработку callback query для переключения автопродления ключа,
включая проверку вызова show_key_handler после переключения.
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
@allure.feature("Автопродление ключей")
@allure.label("package", "src.shop_bot.handlers")
@pytest.mark.unit
@pytest.mark.bot
@pytest.mark.database
class TestToggleKeyAutoRenewalHandler:
    """Тесты для обработчика toggle_key_auto_renewal_handler"""

    @pytest.mark.asyncio
    @allure.title("Успешное переключение автопродления ключа")
    @allure.description("""
    Проверяет успешное переключение статуса автопродления для ключа.
    
    **Что проверяется:**
    - Вызов callback.answer() для подтверждения получения callback query
    - Корректное извлечение key_id из callback data
    - Переключение статуса автопродления через set_key_auto_renewal_enabled
    - Вызов show_key_handler после успешного переключения
    - Корректная обработка callback data формата toggle_key_auto_renewal_{key_id}
    
    **Тестовые данные:**
    - user_id: 123456
    - key_id: 1
    - host_name: 'test_host'
    - key_email: 'test@example.com'
    """)
    @allure.severity(allure.severity_level.CRITICAL)
    @allure.tag("auto_renewal", "toggle", "callback_query", "unit", "critical")
    async def test_toggle_key_auto_renewal_success(self, temp_db, mock_bot, mock_xui_api):
        """Тест успешного переключения автопродления"""
        from shop_bot.data_manager.database import (
            register_user_if_not_exists,
            add_new_key,
            create_host,
            get_key_auto_renewal_enabled,
            set_key_auto_renewal_enabled,
        )
        import shop_bot.bot.handlers as handlers_module
        
        # Настройка БД
        user_id = 123456
        register_user_if_not_exists(user_id, "test_user", None, "Test User")
        
        # Создаем хост и ключ
        create_host("test_host", "http://test.com", "user", "pass", 1, "testcode")
        key_id = add_new_key(
            user_id=user_id,
            host_name="test_host",
            xui_client_uuid="test-uuid-123",
            key_email="test@example.com",
            expiry_timestamp_ms=0,
            protocol="vless"
        )
        
        # Проверяем начальный статус автопродления (по умолчанию должен быть True)
        initial_status = get_key_auto_renewal_enabled(key_id)
        assert initial_status is True, "Автопродление должно быть включено по умолчанию"
        
        # Создаем мок для callback
        callback = MagicMock(spec=CallbackQuery)
        callback.data = f"toggle_key_auto_renewal_{key_id}"
        callback.from_user = MagicMock(spec=User)
        callback.from_user.id = user_id
        callback.answer = AsyncMock()
        callback.message = MagicMock(spec=Message)
        callback.message.edit_text = AsyncMock()
        callback.message.chat = MagicMock(spec=Chat)
        callback.message.chat.id = user_id
        
        # Мокируем xui_api для show_key_handler
        mock_xui_api.get_key_details_from_host = AsyncMock(return_value={
            'connection_string': 'vless://test-connection',
            'status': 'active',
            'subscription_link': None,
        })
        
        # Получаем handler из роутера
        user_router = handlers_module.get_user_router()
        
        # Находим handler для toggle_key_auto_renewal
        handler = None
        for handler_obj in user_router.callback_query.handlers:
            # Проверяем по имени функции
            if hasattr(handler_obj, 'callback'):
                callback_name = getattr(handler_obj.callback, '__name__', '')
                if callback_name == 'toggle_key_auto_renewal_handler':
                    handler = handler_obj.callback
                    break
            # Также проверяем по фильтрам
            if hasattr(handler_obj, 'filters'):
                try:
                    filters_list = list(handler_obj.filters) if handler_obj.filters else []
                    for f in filters_list:
                        f_str = str(f)
                        if 'toggle_key_auto_renewal' in f_str:
                            handler = handler_obj.callback
                            break
                    if handler:
                        break
                except Exception:
                    pass
        
        assert handler is not None, "toggle_key_auto_renewal_handler не найден в роутере"
        
        # Патчим xui_api в handlers
        with patch('shop_bot.bot.handlers.xui_api', mock_xui_api):
            # Вызываем handler
            await handler(callback)
        
        # Проверяем, что статус автопродления изменился
        new_status = get_key_auto_renewal_enabled(key_id)
        assert new_status is False, "Автопродление должно быть отключено после переключения"
        
        # Проверяем, что callback.answer был вызван
        assert callback.answer.called, "callback.answer должен быть вызван"
        
        # Проверяем, что show_key_handler был вызван (через edit_text)
        assert callback.message.edit_text.called, "show_key_handler должен быть вызван через edit_text"
        
        # Проверяем, что edit_text был вызван с правильными параметрами
        call_args = callback.message.edit_text.call_args
        assert call_args is not None, "edit_text должен быть вызван"
        
        # Проверяем, что xui_api.get_key_details_from_host был вызван (из show_key_handler)
        mock_xui_api.get_key_details_from_host.assert_called()

    @pytest.mark.asyncio
    @allure.title("Обработка ошибки: ключ не найден")
    @allure.description("""
    Проверяет обработку случая, когда ключ не найден или не принадлежит пользователю.
    
    **Что проверяется:**
    - Корректная обработка случая, когда key_id не существует
    - Вызов callback.answer с сообщением об ошибке
    - Отсутствие вызова show_key_handler при ошибке
    
    **Тестовые данные:**
    - user_id: 123456
    - key_id: 99999 (несуществующий ключ)
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("auto_renewal", "error_handling", "unit")
    async def test_toggle_key_auto_renewal_key_not_found(self, temp_db, mock_bot):
        """Тест обработки ошибки: ключ не найден"""
        from shop_bot.data_manager.database import register_user_if_not_exists
        import shop_bot.bot.handlers as handlers_module
        
        # Настройка БД
        user_id = 123456
        register_user_if_not_exists(user_id, "test_user", None, "Test User")
        
        # Создаем мок для callback с несуществующим key_id
        callback = MagicMock(spec=CallbackQuery)
        callback.data = "toggle_key_auto_renewal_99999"
        callback.from_user = MagicMock(spec=User)
        callback.from_user.id = user_id
        callback.answer = AsyncMock()
        callback.message = MagicMock(spec=Message)
        callback.message.edit_text = AsyncMock()
        
        # Получаем handler из роутера
        user_router = handlers_module.get_user_router()
        
        # Находим handler для toggle_key_auto_renewal
        handler = None
        for handler_obj in user_router.callback_query.handlers:
            # Проверяем по имени функции
            if hasattr(handler_obj, 'callback'):
                callback_name = getattr(handler_obj.callback, '__name__', '')
                if callback_name == 'toggle_key_auto_renewal_handler':
                    handler = handler_obj.callback
                    break
            # Также проверяем по фильтрам
            if hasattr(handler_obj, 'filters'):
                try:
                    filters_list = list(handler_obj.filters) if handler_obj.filters else []
                    for f in filters_list:
                        f_str = str(f)
                        if 'toggle_key_auto_renewal' in f_str:
                            handler = handler_obj.callback
                            break
                    if handler:
                        break
                except Exception:
                    pass
        
        assert handler is not None, "toggle_key_auto_renewal_handler не найден в роутере"
        
        # Вызываем handler
        await handler(callback)
        
        # Проверяем, что callback.answer был вызван с сообщением об ошибке
        assert callback.answer.called, "callback.answer должен быть вызван"
        call_args = callback.answer.call_args
        assert call_args is not None
        # Проверяем, что в сообщении есть текст об ошибке
        answer_text = call_args[0][0] if call_args[0] else ""
        assert "Ошибка" in answer_text or "не найден" in answer_text.lower(), "Должно быть сообщение об ошибке"
        
        # Проверяем, что show_key_handler НЕ был вызван
        assert not callback.message.edit_text.called, "show_key_handler не должен быть вызван при ошибке"

    @pytest.mark.asyncio
    @allure.title("Обработка устаревшего callback query")
    @allure.description("""
    Проверяет корректную обработку устаревшего callback query в toggle_key_auto_renewal_handler.
    
    **Что проверяется:**
    - Обработка TelegramBadRequest с сообщением "query is too old"
    - Продолжение выполнения handler даже при устаревшем callback query
    - Корректное переключение статуса автопродления
    
    **Тестовые данные:**
    - user_id: 123456
    - key_id: 1
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("auto_renewal", "expired_query", "error_handling", "unit")
    async def test_toggle_key_auto_renewal_expired_callback_query(self, temp_db, mock_bot, mock_xui_api):
        """Тест обработки устаревшего callback query"""
        from shop_bot.data_manager.database import (
            register_user_if_not_exists,
            add_new_key,
            create_host,
            get_key_auto_renewal_enabled,
        )
        import shop_bot.bot.handlers as handlers_module
        
        # Настройка БД
        user_id = 123456
        register_user_if_not_exists(user_id, "test_user", None, "Test User")
        
        # Создаем хост и ключ
        create_host("test_host", "http://test.com", "user", "pass", 1, "testcode")
        key_id = add_new_key(
            user_id=user_id,
            host_name="test_host",
            xui_client_uuid="test-uuid-123",
            key_email="test@example.com",
            expiry_timestamp_ms=0,
            protocol="vless"
        )
        
        # Создаем мок для callback
        callback = MagicMock(spec=CallbackQuery)
        callback.data = f"toggle_key_auto_renewal_{key_id}"
        callback.from_user = MagicMock(spec=User)
        callback.from_user.id = user_id
        # Настраиваем side_effect так, чтобы первый вызов вызывал ошибку, а последующие - нет
        call_count = [0]
        async def answer_side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                raise TelegramBadRequest(
                    message="Bad Request: query is too old",
                    method="answerCallbackQuery"
                )
            # Последующие вызовы успешны
            return True
        callback.answer = AsyncMock(side_effect=answer_side_effect)
        callback.message = MagicMock(spec=Message)
        callback.message.edit_text = AsyncMock()
        callback.message.chat = MagicMock(spec=Chat)
        callback.message.chat.id = user_id
        
        # Мокируем xui_api для show_key_handler
        mock_xui_api.get_key_details_from_host = AsyncMock(return_value={
            'connection_string': 'vless://test-connection',
            'status': 'active',
            'subscription_link': None,
        })
        
        # Получаем handler из роутера
        user_router = handlers_module.get_user_router()
        
        # Находим handler для toggle_key_auto_renewal
        handler = None
        for handler_obj in user_router.callback_query.handlers:
            # Проверяем по имени функции
            if hasattr(handler_obj, 'callback'):
                callback_name = getattr(handler_obj.callback, '__name__', '')
                if callback_name == 'toggle_key_auto_renewal_handler':
                    handler = handler_obj.callback
                    break
            # Также проверяем по фильтрам
            if hasattr(handler_obj, 'filters'):
                try:
                    filters_list = list(handler_obj.filters) if handler_obj.filters else []
                    for f in filters_list:
                        f_str = str(f)
                        if 'toggle_key_auto_renewal' in f_str:
                            handler = handler_obj.callback
                            break
                    if handler:
                        break
                except Exception:
                    pass
        
        assert handler is not None, "toggle_key_auto_renewal_handler не найден в роутере"
        
        # Патчим xui_api в handlers
        with patch('shop_bot.bot.handlers.xui_api', mock_xui_api):
            # Вызываем handler - не должно быть исключения
            await handler(callback)
        
        # Проверяем, что статус автопродления изменился (handler продолжил работу)
        new_status = get_key_auto_renewal_enabled(key_id)
        assert new_status is False, "Автопродление должно быть отключено после переключения"
        
        # Проверяем, что show_key_handler был вызван
        assert callback.message.edit_text.called, "show_key_handler должен быть вызван"

