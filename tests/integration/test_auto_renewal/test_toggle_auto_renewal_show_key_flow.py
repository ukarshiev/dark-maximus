#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Интеграционный тест для проверки вызова show_key_handler из toggle_key_auto_renewal_handler

Тестирует полный flow переключения автопродления и отображения ключа,
включая проверку корректной обработки callback data формата toggle_key_auto_renewal_{key_id}
"""

import pytest
import sys
import allure
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone, timedelta
from aiogram.types import CallbackQuery, User, Message, Chat

# Добавляем путь к проекту
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root / "src"))


@allure.epic("Интеграционные тесты")
@allure.feature("Автопродление")
@allure.label("package", "tests.integration.test_auto_renewal")
@pytest.mark.integration
@pytest.mark.database
@pytest.mark.bot
class TestToggleAutoRenewalShowKeyFlow:
    """Тесты для проверки вызова show_key_handler из toggle_key_auto_renewal_handler"""

    @pytest.mark.asyncio
    @allure.story("Полный flow переключения автопродления и отображения ключа")
    @allure.title("Полный flow переключения автопродления и отображения ключа")
    @allure.description("""
    Интеграционный тест, проверяющий полный цикл переключения автопродления и отображения ключа.
    
    **Что проверяется:**
    - Корректное переключение статуса автопродления через toggle_key_auto_renewal_handler
    - Вызов show_key_handler из toggle_key_auto_renewal_handler с форматом toggle_key_auto_renewal_{key_id}
    - Корректное извлечение key_id из callback data формата toggle_key_auto_renewal_{key_id} в show_key_handler
    - Отображение информации о ключе после переключения автопродления
    
    **Тестовые данные:**
    - user_id: 123600
    - key_id: создается динамически
    - host_name: 'test_host_flow'
    - key_email: 'test@example.com'
    
    **Шаги теста:**
    1. Создание пользователя, хоста, тарифа и ключа
    2. Создание callback query с форматом toggle_key_auto_renewal_{key_id}
    3. Вызов toggle_key_auto_renewal_handler
    4. Проверка переключения статуса автопродления
    5. Проверка вызова show_key_handler с правильным форматом callback data
    6. Проверка корректного извлечения key_id в show_key_handler
    7. Проверка отображения информации о ключе
    
    **Предусловия:**
    - Используется временная БД (temp_db)
    - Мок xui_api настроен (mock_xui_api)
    - Пользователь зарегистрирован
    - Хост создан с тарифами
    """)
    @allure.severity(allure.severity_level.CRITICAL)
    @allure.tag("auto_renewal", "toggle", "show_key", "integration", "critical", "full_flow")
    async def test_toggle_auto_renewal_calls_show_key_handler(self, temp_db, mock_bot, mock_xui_api):
        """Тест полного flow переключения автопродления и отображения ключа"""
        from shop_bot.data_manager.database import (
            register_user_if_not_exists,
            add_new_key,
            create_host,
            create_plan,
            get_key_auto_renewal_enabled,
            set_key_auto_renewal_enabled,
        )
        import shop_bot.bot.handlers as handlers_module
        
        with allure.step("Подготовка тестовых данных"):
            # Настройка БД
            user_id = 123600
            host_name = "test_host_flow"
            
            register_user_if_not_exists(user_id, "test_flow_user", None, "Test Flow User")
            
            # Создаем хост и тариф
            create_host(host_name, "http://test.com", "user", "pass", 1, "testcode")
            create_plan(host_name, "Test Plan Flow", 1, 100.0, 0, 0.0, 0)
            
            # Создаем ключ
            expiry_date = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=30)
            expiry_ms = int(expiry_date.timestamp() * 1000)
            
            key_id = add_new_key(
                user_id=user_id,
                host_name=host_name,
                xui_client_uuid="test-uuid-flow-123",
                key_email=f"user{user_id}-key1@{host_name}.bot",
                expiry_timestamp_ms=expiry_ms,
                protocol="vless",
                plan_name="Test Plan Flow",
                price=100.0,
            )
            
            allure.attach(str(user_id), "User ID", allure.attachment_type.TEXT)
            allure.attach(str(key_id), "Key ID", allure.attachment_type.TEXT)
            allure.attach(str(host_name), "Host Name", allure.attachment_type.TEXT)
        
        with allure.step("Проверка начального статуса автопродления"):
            initial_status = get_key_auto_renewal_enabled(key_id)
            assert initial_status is True, "Автопродление должно быть включено по умолчанию"
            allure.attach(str(initial_status), "Initial auto-renewal status", allure.attachment_type.TEXT)
        
        with allure.step("Создание callback query с форматом toggle_key_auto_renewal_{key_id}"):
            # Создаем мок для callback с форматом toggle_key_auto_renewal_{key_id}
            callback = MagicMock(spec=CallbackQuery)
            callback.data = f"toggle_key_auto_renewal_{key_id}"  # Важно: формат toggle_key_auto_renewal_{key_id}
            callback.from_user = MagicMock(spec=User)
            callback.from_user.id = user_id
            callback.answer = AsyncMock()
            callback.message = MagicMock(spec=Message)
            callback.message.edit_text = AsyncMock()
            callback.message.chat = MagicMock(spec=Chat)
            callback.message.chat.id = user_id
            
            allure.attach(callback.data, "Callback data", allure.attachment_type.TEXT)
        
        with allure.step("Настройка моков для xui_api"):
            # Мокируем xui_api для show_key_handler
            mock_xui_api.get_key_details_from_host = AsyncMock(return_value={
                'connection_string': 'vless://test-connection-flow',
                'status': 'active',
                'subscription_link': None,
            })
        
        with allure.step("Получение handler из роутера"):
            user_router = handlers_module.get_user_router()
            
            # Находим handler для toggle_key_auto_renewal
            toggle_handler = None
            for handler_obj in user_router.callback_query.handlers:
                # Проверяем по имени функции
                if hasattr(handler_obj, 'callback'):
                    callback_name = getattr(handler_obj.callback, '__name__', '')
                    if callback_name == 'toggle_key_auto_renewal_handler':
                        toggle_handler = handler_obj.callback
                        break
                # Также проверяем по фильтрам
                if hasattr(handler_obj, 'filters'):
                    try:
                        filters_list = list(handler_obj.filters) if handler_obj.filters else []
                        for f in filters_list:
                            f_str = str(f)
                            if 'toggle_key_auto_renewal' in f_str:
                                toggle_handler = handler_obj.callback
                                break
                        if toggle_handler:
                            break
                    except Exception:
                        pass
            
            assert toggle_handler is not None, "toggle_key_auto_renewal_handler не найден в роутере"
        
        with allure.step("Вызов toggle_key_auto_renewal_handler"):
            # Патчим xui_api в handlers
            with patch('shop_bot.bot.handlers.xui_api', mock_xui_api):
                # Вызываем handler
                await toggle_handler(callback)
            
            allure.attach("Handler executed", "Toggle handler execution", allure.attachment_type.TEXT)
        
        with allure.step("Проверка переключения статуса автопродления"):
            new_status = get_key_auto_renewal_enabled(key_id)
            assert new_status is False, "Автопродление должно быть отключено после переключения"
            allure.attach(str(new_status), "New auto-renewal status", allure.attachment_type.TEXT)
        
        with allure.step("Проверка вызова show_key_handler"):
            # Проверяем, что show_key_handler был вызван (через edit_text)
            assert callback.message.edit_text.called, "show_key_handler должен быть вызван через edit_text"
            
            # Проверяем количество вызовов edit_text
            # Первый вызов - "Загружаю информацию о ключе..."
            # Второй вызов - результат show_key_handler
            call_count = callback.message.edit_text.call_count
            assert call_count >= 2, f"edit_text должен быть вызван минимум 2 раза (получено {call_count})"
            
            allure.attach(str(call_count), "edit_text call count", allure.attachment_type.TEXT)
        
        with allure.step("Проверка корректного извлечения key_id в show_key_handler"):
            # Проверяем, что xui_api.get_key_details_from_host был вызван с правильным key_id
            mock_xui_api.get_key_details_from_host.assert_called()
            
            # Получаем аргументы вызова
            call_args = mock_xui_api.get_key_details_from_host.call_args
            assert call_args is not None, "get_key_details_from_host должен быть вызван"
            
            # Проверяем, что был передан правильный key_data с key_id
            key_data_arg = call_args[0][0] if call_args[0] else None
            assert key_data_arg is not None, "key_data должен быть передан в get_key_details_from_host"
            assert key_data_arg.get('key_id') == key_id, f"key_id должен быть {key_id}, получен {key_data_arg.get('key_id')}"
            
            allure.attach(str(key_data_arg.get('key_id')), "Key ID from show_key_handler", allure.attachment_type.TEXT)
        
        with allure.step("Проверка отображения информации о ключе"):
            # Проверяем, что edit_text был вызван хотя бы один раз
            assert callback.message.edit_text.call_count > 0, "edit_text должен быть вызван хотя бы один раз"
            
            # Проверяем все вызовы edit_text
            all_calls = callback.message.edit_text.call_args_list
            text_found = False
            for call in all_calls:
                if call and call[0]:
                    text_arg = call[0][0] if call[0] else ""
                    if len(text_arg) > 0:
                        text_found = True
                        # Проверяем, что текст содержит ключевую информацию
                        if "ключ" in text_arg.lower() or "тариф" in text_arg.lower() or "подписка" in text_arg.lower() or "vless" in text_arg.lower():
                            allure.attach(text_arg[:200], "Message text preview", allure.attachment_type.TEXT)
                            break
            
            # Если не нашли текст в вызовах, проверяем последний вызов
            if not text_found and all_calls:
                last_call = all_calls[-1]
                if last_call and last_call[0]:
                    text_arg = last_call[0][0] if last_call[0] else ""
                    allure.attach(f"Last call args: {last_call}", "Last call details", allure.attachment_type.TEXT)
                    allure.attach(text_arg[:200] if text_arg else "Empty text", "Last call text", allure.attachment_type.TEXT)
            
            # Проверяем, что xui_api был вызван (это означает, что show_key_handler работал)
            assert mock_xui_api.get_key_details_from_host.called, "get_key_details_from_host должен быть вызван из show_key_handler"
        
        with allure.step("Проверка callback.answer"):
            # Проверяем, что callback.answer был вызван
            assert callback.answer.called, "callback.answer должен быть вызван"
            
            # Проверяем, что в ответе есть информация о переключении
            answer_call = callback.answer.call_args
            if answer_call and answer_call[0]:
                answer_text = answer_call[0][0]
                assert "автопродление" in answer_text.lower() or "включено" in answer_text.lower() or "отключено" in answer_text.lower(), \
                    f"Ответ должен содержать информацию об автопродлении, получен: {answer_text}"
                allure.attach(answer_text, "Callback answer text", allure.attachment_type.TEXT)

    @pytest.mark.asyncio
    @allure.story("Обработка формата toggle_key_auto_renewal_{key_id} в show_key_handler")
    @allure.title("Проверка обработки формата toggle_key_auto_renewal_{key_id} в show_key_handler")
    @allure.description("""
    Проверяет, что show_key_handler корректно обрабатывает callback data формата toggle_key_auto_renewal_{key_id}.
    
    **Что проверяется:**
    - Корректное извлечение key_id из callback data формата toggle_key_auto_renewal_{key_id}
    - Отсутствие ошибки ValueError при парсинге callback data
    - Корректная работа show_key_handler с нестандартным форматом callback data
    
    **Тестовые данные:**
    - user_id: 123601
    - key_id: создается динамически
    - callback.data: toggle_key_auto_renewal_{key_id}
    """)
    @allure.severity(allure.severity_level.CRITICAL)
    @allure.tag("show_key", "callback_data", "parsing", "integration", "critical")
    async def test_show_key_handler_with_toggle_format(self, temp_db, mock_bot, mock_xui_api):
        """Тест обработки формата toggle_key_auto_renewal_{key_id} в show_key_handler"""
        from shop_bot.data_manager.database import (
            register_user_if_not_exists,
            add_new_key,
            create_host,
            create_plan,
        )
        import shop_bot.bot.handlers as handlers_module
        
        with allure.step("Подготовка тестовых данных"):
            user_id = 123601
            host_name = "test_host_show_key"
            
            register_user_if_not_exists(user_id, "test_show_key_user", None, "Test Show Key User")
            create_host(host_name, "http://test.com", "user", "pass", 1, "testcode")
            create_plan(host_name, "Test Plan Show Key", 1, 100.0, 0, 0.0, 0)
            
            expiry_date = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=30)
            expiry_ms = int(expiry_date.timestamp() * 1000)
            
            key_id = add_new_key(
                user_id=user_id,
                host_name=host_name,
                xui_client_uuid="test-uuid-show-key-123",
                key_email=f"user{user_id}-key1@{host_name}.bot",
                expiry_timestamp_ms=expiry_ms,
                protocol="vless",
                plan_name="Test Plan Show Key",
                price=100.0,
            )
            
            allure.attach(str(key_id), "Key ID", allure.attachment_type.TEXT)
        
        with allure.step("Создание callback query с форматом toggle_key_auto_renewal_{key_id}"):
            # Создаем callback с форматом toggle_key_auto_renewal_{key_id}
            # Это симулирует ситуацию, когда show_key_handler вызывается из toggle_key_auto_renewal_handler
            callback = MagicMock(spec=CallbackQuery)
            callback.data = f"toggle_key_auto_renewal_{key_id}"  # Важно: нестандартный формат
            callback.from_user = MagicMock(spec=User)
            callback.from_user.id = user_id
            callback.answer = AsyncMock()
            callback.message = MagicMock(spec=Message)
            callback.message.edit_text = AsyncMock()
            callback.message.chat = MagicMock(spec=Chat)
            callback.message.chat.id = user_id
            
            allure.attach(callback.data, "Callback data", allure.attachment_type.TEXT)
        
        with allure.step("Настройка моков для xui_api"):
            mock_xui_api.get_key_details_from_host = AsyncMock(return_value={
                'connection_string': 'vless://test-connection-show-key',
                'status': 'active',
                'subscription_link': None,
            })
        
        with allure.step("Получение show_key_handler из роутера"):
            user_router = handlers_module.get_user_router()
            
            # Находим handler для show_key
            show_key_handler = None
            for handler_obj in user_router.callback_query.handlers:
                # Проверяем по имени функции
                if hasattr(handler_obj, 'callback'):
                    callback_name = getattr(handler_obj.callback, '__name__', '')
                    if callback_name == 'show_key_handler':
                        show_key_handler = handler_obj.callback
                        break
                # Также проверяем по фильтрам
                if hasattr(handler_obj, 'filters'):
                    try:
                        filters_list = list(handler_obj.filters) if handler_obj.filters else []
                        for f in filters_list:
                            f_str = str(f)
                            if 'show_key' in f_str:
                                show_key_handler = handler_obj.callback
                                break
                        if show_key_handler:
                            break
                    except Exception:
                        pass
        
        with allure.step("Вызов show_key_handler с форматом toggle_key_auto_renewal_{key_id}"):
            assert show_key_handler is not None, "show_key_handler не найден"
            
            # Патчим xui_api в handlers
            with patch('shop_bot.bot.handlers.xui_api', mock_xui_api):
                # Вызываем handler - не должно быть ошибки ValueError
                try:
                    await show_key_handler(callback)
                except ValueError as e:
                    if "invalid literal for int() with base 10: 'auto'" in str(e):
                        pytest.fail(f"Ошибка парсинга callback data: {e}. show_key_handler не может обработать формат toggle_key_auto_renewal_{key_id}")
                    else:
                        raise
        
        with allure.step("Проверка успешного выполнения"):
            # Проверяем, что edit_text был вызван (значит handler выполнился успешно)
            assert callback.message.edit_text.called, "show_key_handler должен быть вызван успешно"
            
            # Проверяем, что xui_api.get_key_details_from_host был вызван
            mock_xui_api.get_key_details_from_host.assert_called()
            
            # Проверяем, что был передан правильный key_id
            call_args = mock_xui_api.get_key_details_from_host.call_args
            key_data_arg = call_args[0][0] if call_args[0] else None
            assert key_data_arg is not None, "key_data должен быть передан"
            assert key_data_arg.get('key_id') == key_id, f"key_id должен быть {key_id}"
            
            allure.attach(str(key_data_arg.get('key_id')), "Extracted Key ID", allure.attachment_type.TEXT)

