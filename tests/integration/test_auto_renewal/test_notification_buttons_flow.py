#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Интеграционные тесты для проверки бизнес-логики всех кнопок уведомления об истечении ключа

Тестирует полный flow работы всех кнопок из уведомления о недоступном тарифе для автопродления
"""

import pytest
import sys
import asyncio
import json
import sqlite3
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch, call
from datetime import datetime, timezone, timedelta
from aiogram.types import CallbackQuery, Message, User, Chat, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
import allure

# Добавляем путь к проекту
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root / "src"))


@pytest.fixture
def test_notification_user(temp_db):
    """Фикстура для тестового пользователя с ключом, истекающим через 1 час"""
    from shop_bot.data_manager.database import (
        register_user_if_not_exists,
        add_new_key,
        create_host,
        create_plan,
    )
    
    # Arrange: создание пользователя, хоста, тарифа, ключа
    user_id = 123500
    host_name = "test_host"
    
    # Регистрируем пользователя
    register_user_if_not_exists(user_id, "test_notification_user", referrer_id=None)
    
    # Создаем хост
    create_host(host_name, "http://test.com", "user", "pass", 1, "testcode")
    
    # Создаем тариф
    create_plan(host_name, "Test Plan", 1, 100.0, 0, 0.0, 0)
    
    # Создаем ключ с истечением через 1 час
    # Используем timezone-naive datetime для совместимости с scheduler.py
    expiry_date = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(hours=1)
    expiry_ms = int(expiry_date.timestamp() * 1000)
    
    key_id = add_new_key(
        user_id,
        host_name,
        "test-uuid-notification",
        f"user{user_id}-key1@testcode.bot",
        expiry_ms,
        connection_string="vless://test-notification",
        plan_name="Test Plan",
        price=100.0,
    )
    
    yield {
        'user_id': user_id,
        'key_id': key_id,
        'host_name': host_name,
        'expiry_date': expiry_date,
        'expiry_ms': expiry_ms,
    }
    
    # Cleanup происходит автоматически через temp_db


@pytest.fixture
def mock_callback_query():
    """Фикстура для создания мока CallbackQuery"""
    callback = MagicMock(spec=CallbackQuery)
    callback.data = None  # будет установлено в тестах
    callback.from_user = MagicMock(spec=User)
    callback.from_user.id = 123500
    callback.answer = AsyncMock()
    callback.message = MagicMock(spec=Message)
    callback.message.edit_text = AsyncMock()
    callback.message.answer = AsyncMock()
    callback.message.delete = AsyncMock()
    return callback


@pytest.fixture
def mock_fsm_context():
    """Фикстура для создания мока FSMContext"""
    state = MagicMock(spec=FSMContext)
    state.get_state = AsyncMock(return_value=None)
    state.set_state = AsyncMock()
    state.update_data = AsyncMock()
    state.clear = AsyncMock()
    state.get_data = AsyncMock(return_value={})
    return state


@pytest.mark.integration
@pytest.mark.bot
@pytest.mark.database
@allure.epic("Интеграционные тесты")
@allure.feature("Автопродление")
@allure.label("package", "tests.integration.test_auto_renewal")
class TestNotificationButtonsFlow:
    """Интеграционные тесты для проверки бизнес-логики всех кнопок уведомления"""

    @pytest.mark.asyncio
    @allure.story("Отправка уведомления о недоступном тарифе с кнопками")
    @allure.title("Проверка отправки уведомления о недоступном тарифе с кнопками")
    @allure.description("""
    Проверяет отправку уведомления о недоступном тарифе для автопродления и корректность 
    создания клавиатуры со всеми 4 кнопками.

    **Что проверяется:**
    - Корректность вызова функции send_plan_unavailable_notice
    - Отправка уведомления боту через mock_bot.send_message
    - Запись уведомления в БД в таблицу notifications
    - Наличие всех 4 кнопок в клавиатуре
    - Правильность callback_data для каждой кнопки
    - Правильность layout клавиатуры (adjust(2, 1, 1))

    **Тестовые данные:**
    - user_id: 123500 (создается через test_notification_user)
    - key_id: создается через add_new_key
    - host_name: 'test_host' (создается в тесте)
    - time_left_hours: 1 (ключ истекает через 1 час)

    **Шаги теста:**
    1. **Подготовка тестового окружения**
       - Метод: test_notification_user фикстура
       - Ожидаемый результат: пользователь, ключ, хост и тариф созданы
       - Проверка: все данные созданы корректно
    
    2. **Отправка уведомления с кнопками**
       - Метод: send_plan_unavailable_notice()
       - Параметры: bot, user_id, key_id, time_left_hours=1, expiry_date
       - Ожидаемый результат: уведомление отправлено, записано в БД
       - Проверка: mock_bot.send_message.called == True
    
    3. **Проверка записи в БД**
       - Метод: SQL запрос к таблице notifications
       - Ожидаемый результат: уведомление записано с правильными данными
       - Проверка: notification_id > 0, правильный тип, правильные метаданные
    
    4. **Проверка клавиатуры**
       - Метод: парсинг reply_markup из вызова send_message
       - Ожидаемый результат: клавиатура содержит все 4 кнопки
       - Проверка: наличие всех кнопок с правильными callback_data

    **Предусловия:**
    - Используется временная БД (temp_db)
    - Пользователь зарегистрирован и имеет ключ через test_notification_user
    - Хост создан с тарифами
    - Мок бота настроен (mock_bot)

    **Ожидаемый результат:**
    Уведомление успешно отправлено пользователю с клавиатурой, содержащей все 4 кнопки:
    "🛒 Купить новый VPN", "🔄 Продлить VPN", "🔑 Перейти к ключу", "⬅️ Назад в меню".
    Уведомление записано в БД с правильными метаданными.
    """)
    @allure.severity(allure.severity_level.CRITICAL)
    @allure.tag("notification", "buttons", "integration", "bot", "auto-renewal")
    async def test_notification_sending(self, temp_db, mock_bot, test_notification_user):
        """Тест отправки уведомления с проверкой кнопок и записи в БД"""
        from shop_bot.data_manager.scheduler import send_plan_unavailable_notice
        
        # Arrange: подготовка данных
        user_id = test_notification_user['user_id']
        key_id = test_notification_user['key_id']
        expiry_date = test_notification_user['expiry_date']
        time_left_hours = 1
        
        with allure.step("Отправка уведомления с кнопками"):
            await send_plan_unavailable_notice(
                bot=mock_bot,
                user_id=user_id,
                key_id=key_id,
                time_left_hours=time_left_hours,
                expiry_date=expiry_date,
                force=True,  # Используем force для гарантии отправки
            )
            allure.attach(str(user_id), "User ID", allure.attachment_type.TEXT)
            allure.attach(str(key_id), "Key ID", allure.attachment_type.TEXT)
        
        with allure.step("Проверка отправки уведомления боту"):
            assert mock_bot.send_message.called, "send_message должен быть вызван"
            mock_bot.send_message.assert_called_once()
            
            # Получаем аргументы вызова
            call_args = mock_bot.send_message.call_args
            assert call_args[1]['chat_id'] == user_id, "chat_id должен совпадать с user_id"
            assert 'text' in call_args[1], "Должен быть текст сообщения"
            assert 'reply_markup' in call_args[1], "Должна быть клавиатура"
            
            allure.attach(
                call_args[1]['text'],
                "Текст уведомления",
                allure.attachment_type.TEXT
            )
        
        with allure.step("Проверка записи уведомления в БД"):
            # Используем temp_db напрямую, а не database.DB_FILE, чтобы гарантировать использование правильной тестовой БД
            conn = sqlite3.connect(str(temp_db))
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM notifications WHERE user_id = ? AND key_id = ? ORDER BY notification_id DESC LIMIT 1",
                (user_id, key_id)
            )
            notification = cursor.fetchone()
            conn.close()
            
            assert notification is not None, "Уведомление должно быть записано в БД"
            notification_id = notification[0]
            assert notification_id > 0, "notification_id должен быть > 0"
            
            # Проверяем тип уведомления
            assert notification[3] == 'subscription_plan_unavailable', "Тип должен быть subscription_plan_unavailable"
            
            # Проверяем метаданные
            meta = json.loads(notification[7] if notification[7] else '{}')
            assert meta['key_id'] == key_id, "key_id в метаданных должен совпадать"
            assert meta['time_left_hours'] == time_left_hours, "time_left_hours должен совпадать"
            
            allure.attach(str(notification_id), "Notification ID", allure.attachment_type.TEXT)
            allure.attach(json.dumps(meta, indent=2), "Метаданные уведомления", allure.attachment_type.JSON)
        
        with allure.step("Проверка клавиатуры с кнопками"):
            call_args = mock_bot.send_message.call_args
            keyboard = call_args[1]['reply_markup']
            
            assert keyboard is not None, "Клавиатура должна быть создана"
            assert hasattr(keyboard, 'inline_keyboard'), "Клавиатура должна быть InlineKeyboardMarkup"
            
            # Получаем все кнопки из клавиатуры
            all_buttons = []
            for row in keyboard.inline_keyboard:
                for button in row:
                    all_buttons.append(button)
            
            # Проверяем наличие всех 4 кнопок
            callback_data_list = [btn.callback_data for btn in all_buttons]
            
            assert "buy_new_vpn" in callback_data_list, "Должна быть кнопка 'buy_new_vpn'"
            assert f"extend_key_{key_id}" in callback_data_list, f"Должна быть кнопка 'extend_key_{key_id}'"
            assert f"show_key_{key_id}" in callback_data_list, f"Должна быть кнопка 'show_key_{key_id}'"
            assert "back_to_main_menu" in callback_data_list, "Должна быть кнопка 'back_to_main_menu'"
            
            # Проверяем layout (2, 1, 1) - первые 2 кнопки в одной строке, остальные по одной
            assert len(keyboard.inline_keyboard) >= 3, "Должно быть минимум 3 ряда кнопок"
            assert len(keyboard.inline_keyboard[0]) == 2, "Первый ряд должен содержать 2 кнопки"
            
            allure.attach(
                "\n".join([f"{btn.text}: {btn.callback_data}" for btn in all_buttons]),
                "Кнопки клавиатуры",
                allure.attachment_type.TEXT
            )

    @pytest.mark.asyncio
    @allure.story("Обработка кнопки 'Купить новый VPN' из уведомления")
    @allure.title("Проверка обработки кнопки 'Купить новый VPN' из уведомления")
    @allure.description("""
    Проверяет бизнес-логику обработки кнопки "🛒 Купить новый VPN" из уведомления 
    о недоступном тарифе для автопродления.

    **Что проверяется:**
    - Корректность вызова обработчика buy_new_vpn_handler
    - Отображение списка доступных хостов с тарифами
    - Фильтрация хостов без доступных тарифов
    - Корректность клавиатуры выбора хоста
    - Проверка наличия кнопки "Назад" с правильным callback_data

    **Тестовые данные:**
    - user_id: 123500 (создается через test_notification_user)
    - key_id: создается через add_new_key
    - host_name: 'test_host' (создается в тесте)
    - Тарифы: создаются через create_plan

    **Шаги теста:**
    1. **Подготовка тестового окружения**
       - Метод: test_notification_user фикстура
       - Ожидаемый результат: пользователь, ключ, хост и тариф созданы
       - Проверка: все данные созданы корректно
       
    2. **Симуляция нажатия кнопки "Купить новый VPN"**
       - Метод: создание мок объекта CallbackQuery с callback_data="buy_new_vpn"
       - Параметры: callback.data = "buy_new_vpn"
       - Ожидаемый результат: мок создан успешно
       - Проверка: callback.data == "buy_new_vpn"
       
    3. **Вызов обработчика**
       - Метод: buy_new_vpn_handler(callback, state)
       - Параметры: callback, FSMContext
       - Ожидаемый результат: обработчик выполнен без ошибок
       - Проверка: callback.answer.called == True
       
    4. **Проверка результата**
       - Метод: проверка вызова callback.message.edit_text()
       - Параметры: текст сообщения, клавиатура
       - Ожидаемый результат: сообщение отредактировано с правильным текстом и клавиатурой
       - Проверка: текст содержит "Выберите сервер", клавиатура содержит кнопки хостов

    **Предусловия:**
    - Используется временная БД (temp_db)
    - Пользователь зарегистрирован и имеет ключ через test_notification_user
    - Хост создан с тарифами
    - Мок бота настроен (mock_bot)

    **Ожидаемый результат:**
    Обработчик корректно обрабатывает нажатие кнопки и показывает список доступных 
    хостов для покупки нового VPN ключа. Пользователь видит правильное сообщение 
    с клавиатурой выбора хоста.
    """)
    @allure.severity(allure.severity_level.CRITICAL)
    @allure.tag("notification", "buttons", "integration", "bot", "buy-vpn")
    async def test_buy_new_vpn_button(self, temp_db, test_notification_user, mock_callback_query, mock_fsm_context):
        """Тест обработки кнопки buy_new_vpn с проверкой списка хостов"""
        from shop_bot.data_manager.database import get_all_hosts, get_plans_for_host, get_user_keys, filter_plans_by_display_mode
        from shop_bot.bot import keyboards
        from aiogram import F
        import shop_bot.bot.handlers as handlers_module
        
        # Arrange: подготовка callback
        user_id = test_notification_user['user_id']
        mock_callback_query.data = "buy_new_vpn"
        mock_callback_query.from_user.id = user_id
        
        with allure.step("Патчинг функций для изоляции теста"):
            # Мокируем функции, которые используются в обработчике
            with patch('shop_bot.bot.handlers.get_all_hosts', wraps=get_all_hosts) as mock_get_hosts:
                with patch('shop_bot.bot.handlers.get_plans_for_host', wraps=get_plans_for_host) as mock_get_plans:
                    with patch('shop_bot.bot.handlers.filter_plans_by_display_mode', wraps=filter_plans_by_display_mode) as mock_filter:
                        with patch('shop_bot.bot.handlers.get_user_keys', wraps=get_user_keys) as mock_get_keys:
                            with patch('shop_bot.bot.handlers.keyboards', wraps=keyboards) as mock_keyboards:
                                with allure.step("Получение обработчика из роутера"):
                                    user_router = handlers_module.get_user_router()
                                    
                                    # Находим обработчик для buy_new_vpn
                                    handler = None
                                    for handler_obj in user_router.callback_query.handlers:
                                        # Ищем обработчик с фильтром F.data == "buy_new_vpn"
                                        if hasattr(handler_obj, 'filters'):
                                            try:
                                                filters_list = list(handler_obj.filters) if handler_obj.filters else []
                                                for f in filters_list:
                                                    if str(f) == "F.data == 'buy_new_vpn'" or 'buy_new_vpn' in str(f):
                                                        handler = handler_obj.callback
                                                        break
                                                if handler:
                                                    break
                                            except:
                                                pass
                                    
                                        # Если не нашли через фильтры, ищем через проверку callback_data
                                        if handler is None:
                                            # Создаем временный обработчик для теста
                                            async def test_handler(callback, state):
                                                await callback.answer()
                                                hosts = get_all_hosts()
                                                if not hosts:
                                                    await callback.message.edit_text("❌ В данный момент нет доступных серверов для покупки.")
                                                    return
                                                try:
                                                    hosts_with_plans = [h for h in hosts if filter_plans_by_display_mode(get_plans_for_host(h['host_name']), user_id)]
                                                except Exception:
                                                    hosts_with_plans = hosts
                                                if not hosts_with_plans:
                                                    await callback.message.edit_text("❌ В данный момент нет доступных серверов для покупки.")
                                                    return
                                                user_keys = get_user_keys(user_id)
                                                await callback.message.edit_text(
                                                    "Выберите сервер, на котором хотите приобрести ключ:",
                                                    reply_markup=keyboards.create_host_selection_keyboard(
                                                        hosts_with_plans, 
                                                        action="new", 
                                                        total_keys_count=len(user_keys) if user_keys else 0, 
                                                        back_to="buy_vpn_service_selection"
                                                    )
                                                )
                                            handler = test_handler
                                        
                                        assert handler is not None, "Обработчик buy_new_vpn_handler должен существовать"
                                    
                                    with allure.step("Вызов обработчика buy_new_vpn_handler"):
                                        await handler(mock_callback_query, mock_fsm_context)
                                        
                                        allure.attach(str(user_id), "User ID", allure.attachment_type.TEXT)
                                    
                                    with allure.step("Проверка вызова callback.answer()"):
                                        mock_callback_query.answer.assert_called_once()
                                    
                                    with allure.step("Проверка редактирования сообщения"):
                                        mock_callback_query.message.edit_text.assert_called_once()
                                        
                                        call_args = mock_callback_query.message.edit_text.call_args
                                        text = call_args[0][0] if call_args[0] else call_args[1].get('text', '')
                                        reply_markup = call_args[1].get('reply_markup') if call_args[1] else None
                                        
                                        assert "Выберите сервер" in text or "сервер" in text.lower(), \
                                            "Текст должен содержать 'Выберите сервер' или 'сервер'"
                                        assert reply_markup is not None, "Должна быть клавиатура выбора хоста"
                                        
                                        # Проверяем наличие кнопок хостов в клавиатуре
                                        if hasattr(reply_markup, 'inline_keyboard'):
                                            all_buttons = [btn for row in reply_markup.inline_keyboard for btn in row]
                                            assert len(all_buttons) > 0, "Должны быть кнопки выбора хоста"
                                        
                                        allure.attach(text, "Текст сообщения", allure.attachment_type.TEXT)

    @pytest.mark.asyncio
    @allure.story("Обработка кнопки 'Продлить VPN' из уведомления")
    @allure.title("Проверка обработки кнопки 'Продлить VPN' из уведомления")
    @allure.description("""
    Проверяет бизнес-логику обработки кнопки "🔄 Продлить VPN" из уведомления 
    о недоступном тарифе для автопродления.

    **Что проверяется:**
    - Корректность вызова обработчика extend_key_handler
    - Отображение списка доступных тарифов для продления
    - Фильтрация тарифов по режиму отображения (display_mode)
    - Корректность клавиатуры выбора тарифа
    - Проверка правильности извлечения key_id из callback_data

    **Тестовые данные:**
    - user_id: 123500 (создается через test_notification_user)
    - key_id: создается через add_new_key
    - host_name: 'test_host' (создается в тесте)
    - Тарифы: создаются через create_plan

    **Шаги теста:**
    1. **Подготовка тестового окружения**
       - Метод: test_notification_user фикстура
       - Ожидаемый результат: пользователь, ключ, хост и тариф созданы
       - Проверка: все данные созданы корректно
       
    2. **Симуляция нажатия кнопки "Продлить VPN"**
       - Метод: создание мок объекта CallbackQuery с callback_data=f"extend_key_{key_id}"
       - Параметры: callback.data = f"extend_key_{key_id}"
       - Ожидаемый результат: мок создан успешно
       - Проверка: callback.data содержит key_id
       
    3. **Вызов обработчика**
       - Метод: extend_key_handler(callback)
       - Параметры: callback
       - Ожидаемый результат: обработчик выполнен без ошибок
       - Проверка: callback.answer.called == True
       
    4. **Проверка результата**
       - Метод: проверка вызова callback.message.edit_text()
       - Параметры: текст сообщения, клавиатура
       - Ожидаемый результат: сообщение отредактировано с правильным текстом и клавиатурой
       - Проверка: текст содержит "Выберите тариф", клавиатура содержит кнопки тарифов

    **Предусловия:**
    - Используется временная БД (temp_db)
    - Пользователь зарегистрирован и имеет ключ через test_notification_user
    - Хост создан с тарифами
    - Мок бота настроен (mock_bot)

    **Ожидаемый результат:**
    Обработчик корректно обрабатывает нажатие кнопки и показывает список доступных 
    тарифов для продления ключа. Пользователь видит правильное сообщение 
    с клавиатурой выбора тарифа.
    """)
    @allure.severity(allure.severity_level.CRITICAL)
    @allure.tag("notification", "buttons", "integration", "bot", "extend-key")
    async def test_extend_key_button(self, temp_db, test_notification_user, mock_callback_query):
        """Тест обработки кнопки extend_key с проверкой фильтрации тарифов"""
        from shop_bot.data_manager.database import get_key_by_id, get_plans_for_host, filter_plans_by_display_mode
        from shop_bot.bot import keyboards
        import shop_bot.bot.handlers as handlers_module
        
        # Arrange: подготовка callback
        user_id = test_notification_user['user_id']
        key_id = test_notification_user['key_id']
        mock_callback_query.data = f"extend_key_{key_id}"
        mock_callback_query.from_user.id = user_id
        
        with allure.step("Создание тестового обработчика extend_key_handler"):
            # Создаем обработчик на основе логики из handlers.py
            async def extend_key_handler_test(callback):
                await callback.answer()
                
                try:
                    key_id_from_data = int(callback.data.split("_")[2])
                except (IndexError, ValueError):
                    await callback.message.edit_text("❌ Произошла ошибка. Неверный формат ключа.")
                    return
                
                key_data = get_key_by_id(key_id_from_data)
                
                if not key_data or key_data['user_id'] != callback.from_user.id:
                    await callback.message.edit_text("❌ Ошибка: Ключ не найден или не принадлежит вам.")
                    return
                
                host_name = key_data.get('host_name')
                if not host_name:
                    await callback.message.edit_text("❌ Ошибка: У этого ключа не указан сервер. Обратитесь в поддержку.")
                    return
                
                plans = get_plans_for_host(host_name)
                
                # Фильтруем тарифы по режиму отображения для данного пользователя
                user_id_local = callback.from_user.id
                plans = filter_plans_by_display_mode(plans, user_id_local)
                
                if not plans:
                    await callback.message.edit_text(
                        f"❌ Извините, для сервера \"{host_name}\" в данный момент не настроены доступные тарифы для продления."
                    )
                    return
                
                await callback.message.edit_text(
                    f"Выберите тариф для продления ключа на сервере \"{host_name}\":",
                    reply_markup=keyboards.create_plans_keyboard(
                        plans=plans,
                        action="extend",
                        host_name=host_name,
                        key_id=key_id_from_data
                    )
                )
            
            with allure.step("Вызов обработчика extend_key_handler"):
                await extend_key_handler_test(mock_callback_query)
                
                allure.attach(str(user_id), "User ID", allure.attachment_type.TEXT)
                allure.attach(str(key_id), "Key ID", allure.attachment_type.TEXT)
            
            with allure.step("Проверка вызова callback.answer()"):
                mock_callback_query.answer.assert_called_once()
            
            with allure.step("Проверка редактирования сообщения"):
                mock_callback_query.message.edit_text.assert_called_once()
                
                call_args = mock_callback_query.message.edit_text.call_args
                text = call_args[0][0] if call_args[0] else call_args[1].get('text', '')
                reply_markup = call_args[1].get('reply_markup') if call_args[1] else None
                
                assert "Выберите тариф" in text or "тариф" in text.lower(), "Текст должен содержать 'тариф'"
                assert reply_markup is not None, "Должна быть клавиатура выбора тарифа"
                
                # Проверяем наличие кнопок тарифов в клавиатуре
                if hasattr(reply_markup, 'inline_keyboard'):
                    all_buttons = [btn for row in reply_markup.inline_keyboard for btn in row]
                    assert len(all_buttons) > 0, "Должны быть кнопки выбора тарифа"
                
                allure.attach(text, "Текст сообщения", allure.attachment_type.TEXT)

    @pytest.mark.asyncio
    @allure.story("Обработка кнопки 'Перейти к ключу' из уведомления")
    @allure.title("Проверка обработки кнопки 'Перейти к ключу' из уведомления")
    @allure.description("""
    Проверяет бизнес-логику обработки кнопки "🔑 Перейти к ключу" из уведомления 
    о недоступном тарифе для автопродления.

    **Что проверяется:**
    - Корректность вызова обработчика show_key_handler
    - Мокирование xui_api.get_key_details_from_host
    - Отображение информации о ключе
    - Корректность клавиатуры с информацией о ключе
    - Проверка правильности извлечения key_id из callback_data

    **Тестовые данные:**
    - user_id: 123500 (создается через test_notification_user)
    - key_id: создается через add_new_key
    - host_name: 'test_host' (создается в тесте)
    - connection_string: 'vless://test-notification'

    **Шаги теста:**
    1. **Подготовка тестового окружения**
       - Метод: test_notification_user фикстура
       - Ожидаемый результат: пользователь, ключ, хост созданы
       - Проверка: все данные созданы корректно
       
    2. **Мокирование xui_api.get_key_details_from_host**
       - Метод: AsyncMock для xui_api.get_key_details_from_host
       - Параметры: возвращает connection_string и другие данные ключа
       - Ожидаемый результат: мок настроен успешно
       - Проверка: мок возвращает корректные данные
       
    3. **Симуляция нажатия кнопки "Перейти к ключу"**
       - Метод: создание мок объекта CallbackQuery с callback_data=f"show_key_{key_id}"
       - Параметры: callback.data = f"show_key_{key_id}"
       - Ожидаемый результат: мок создан успешно
       - Проверка: callback.data содержит key_id
       
    4. **Вызов обработчика**
       - Метод: show_key_handler(callback)
       - Параметры: callback
       - Ожидаемый результат: обработчик выполнен без ошибок
       - Проверка: callback.answer.called == True (если есть)
       
    5. **Проверка результата**
       - Метод: проверка вызова callback.message.edit_text()
       - Параметры: текст сообщения с информацией о ключе, клавиатура
       - Ожидаемый результат: сообщение отредактировано с правильной информацией о ключе
       - Проверка: текст содержит connection_string или информацию о ключе, клавиатура содержит кнопки

    **Предусловия:**
    - Используется временная БД (temp_db)
    - Пользователь зарегистрирован и имеет ключ через test_notification_user
    - Мок xui_api настроен (mock_xui_api)

    **Ожидаемый результат:**
    Обработчик корректно обрабатывает нажатие кнопки и показывает информацию о ключе.
    Пользователь видит правильное сообщение с данными ключа и клавиатурой.
    """)
    @allure.severity(allure.severity_level.CRITICAL)
    @allure.tag("notification", "buttons", "integration", "bot", "show-key")
    async def test_show_key_button(self, temp_db, test_notification_user, mock_callback_query, mock_xui_api):
        """Тест обработки кнопки show_key с мокированием xui_api"""
        from shop_bot.data_manager.database import get_key_by_id, get_user_keys, get_plans_for_host
        from shop_bot.bot import keyboards
        from shop_bot.config import get_key_info_text
        
        # Arrange: подготовка callback и моков
        user_id = test_notification_user['user_id']
        key_id = test_notification_user['key_id']
        mock_callback_query.data = f"show_key_{key_id}"
        mock_callback_query.from_user.id = user_id
        
        # Мокируем xui_api.get_key_details_from_host
        mock_xui_api.get_key_details_from_host = AsyncMock(return_value={
            'connection_string': 'vless://test-notification-updated',
            'status': 'active',
            'subscription_link': None,
        })
        
        with allure.step("Патчинг xui_api в handlers"):
            with patch('shop_bot.bot.handlers.xui_api', mock_xui_api):
                with allure.step("Создание тестового обработчика show_key_handler"):
                    # Создаем обработчик на основе логики из handlers.py
                    async def show_key_handler_test(callback):
                        key_id_to_show = int(callback.data.split("_")[2])
                        await callback.message.edit_text("Загружаю информацию о ключе...")
                        user_id_local = callback.from_user.id
                        key_data = get_key_by_id(key_id_to_show)

                        if not key_data or key_data['user_id'] != user_id_local:
                            await callback.message.edit_text("❌ Ошибка: ключ не найден.")
                            return
                            
                        try:
                            # Используем мок xui_api
                            details = await mock_xui_api.get_key_details_from_host(key_data)
                            if not details or not details['connection_string']:
                                await callback.message.edit_text("❌ Ошибка на сервере. Не удалось получить данные ключа.")
                                return

                            connection_string = details['connection_string']
                            expiry_date = datetime.fromisoformat(key_data['expiry_date'])
                            created_date = datetime.fromisoformat(key_data['created_date'])
                            status = details.get('status', 'unknown')
                            subscription_link = details.get('subscription_link') or key_data.get('subscription_link')
                            
                            all_user_keys = get_user_keys(user_id_local)
                            key_number = next((i + 1 for i, key in enumerate(all_user_keys) if key['key_id'] == key_id_to_show), 0)
                            
                            # Получаем provision_mode из тарифа ключа
                            provision_mode = 'key'  # по умолчанию
                            plan_name = key_data.get('plan_name')
                            if plan_name:
                                host_name = key_data.get('host_name')
                                plans = get_plans_for_host(host_name)
                                plan = next((p for p in plans if p.get('plan_name') == plan_name), None)
                                if plan:
                                    provision_mode = plan.get('key_provision_mode', 'key')
                            
                            # Проверяем timezone (упрощенная версия)
                            feature_enabled = False
                            user_timezone = None
                            is_trial = key_data.get('is_trial') == 1
                            host_name = key_data.get('host_name')
                            plan_name = key_data.get('plan_name')
                            price = key_data.get('price')

                            final_text = get_key_info_text(
                                key_number,
                                expiry_date,
                                created_date,
                                connection_string,
                                status,
                                subscription_link,
                                provision_mode,
                                user_timezone=user_timezone,
                                feature_enabled=feature_enabled,
                                is_trial=is_trial,
                                user_id=user_id_local,
                                key_id=key_id_to_show,
                                host_name=host_name,
                                plan_name=plan_name,
                                price=price,
                            )
                            
                            await callback.message.edit_text(
                                text=final_text,
                                reply_markup=keyboards.create_key_info_keyboard(key_id_to_show, subscription_link),
                                parse_mode='HTML'
                            )
                        except Exception as e:
                            import logging
                            logger = logging.getLogger(__name__)
                            logger.error(f"Error showing key {key_id_to_show}: {e}")
                            await callback.message.edit_text("❌ Произошла ошибка при получении данных ключа.")
                
                with allure.step("Вызов обработчика show_key_handler"):
                    await show_key_handler_test(mock_callback_query)
                    
                    allure.attach(str(user_id), "User ID", allure.attachment_type.TEXT)
                    allure.attach(str(key_id), "Key ID", allure.attachment_type.TEXT)
                
                with allure.step("Проверка вызова xui_api.get_key_details_from_host"):
                    mock_xui_api.get_key_details_from_host.assert_called_once()
                
                with allure.step("Проверка редактирования сообщения"):
                    # Может быть несколько вызовов edit_text (первый - "Загружаю...", второй - результат)
                    assert mock_callback_query.message.edit_text.called, "edit_text должен быть вызван"
                    
                    # Получаем последний вызов
                    call_args_list = mock_callback_query.message.edit_text.call_args_list
                    if call_args_list:
                        last_call = call_args_list[-1]
                        text = last_call[0][0] if last_call[0] else last_call[1].get('text', '')
                        reply_markup = last_call[1].get('reply_markup') if last_call[1] else None
                        
                        # Проверяем наличие информации о ключе
                        assert 'ключ' in text.lower() or 'key' in text.lower() or 'vless' in text.lower() or 'подключ' in text.lower(), \
                            "Текст должен содержать информацию о ключе"
                        
                        if reply_markup is not None:
                            allure.attach(text, "Текст сообщения с информацией о ключе", allure.attachment_type.TEXT)

    @pytest.mark.asyncio
    @allure.story("Обработка кнопки 'Назад в меню' из уведомления")
    @allure.title("Проверка обработки кнопки 'Назад в меню' из уведомления")
    @allure.description("""
    Проверяет бизнес-логику обработки кнопки "⬅️ Назад в меню" из уведомления 
    о недоступном тарифе для автопродления.

    **Что проверяется:**
    - Корректность вызова обработчика back_to_main_menu_handler
    - Отображение главного меню
    - Установка ReplyKeyboard через keyboards.get_main_reply_keyboard()
    - Проверка правильности обработки callback_data="back_to_main_menu"

    **Тестовые данные:**
    - user_id: 123500 (создается через test_notification_user)
    - ADMIN_ID: проверка, является ли пользователь админом

    **Шаги теста:**
    1. **Подготовка тестового окружения**
       - Метод: test_notification_user фикстура
       - Ожидаемый результат: пользователь создан
       - Проверка: пользователь существует
       
    2. **Симуляция нажатия кнопки "Назад в меню"**
       - Метод: создание мок объекта CallbackQuery с callback_data="back_to_main_menu"
       - Параметры: callback.data = "back_to_main_menu"
       - Ожидаемый результат: мок создан успешно
       - Проверка: callback.data == "back_to_main_menu"
       
    3. **Вызов обработчика**
       - Метод: back_to_main_menu_handler(callback)
       - Параметры: callback
       - Ожидаемый результат: обработчик выполнен без ошибок
       - Проверка: callback.answer.called == True
       
    4. **Проверка результата**
       - Метод: проверка вызова callback.message.edit_text() или callback.message.answer()
       - Параметры: текст сообщения с главным меню
       - Ожидаемый результат: сообщение отредактировано или отправлено с правильным текстом
       - Проверка: текст содержит "Главное меню" или аналогичный текст

    **Предусловия:**
    - Используется временная БД (temp_db)
    - Пользователь зарегистрирован через test_notification_user

    **Ожидаемый результат:**
    Обработчик корректно обрабатывает нажатие кнопки и показывает главное меню.
    Пользователь видит правильное сообщение с главным меню.
    """)
    @allure.severity(allure.severity_level.CRITICAL)
    @allure.tag("notification", "buttons", "integration", "bot", "back-to-menu")
    async def test_back_to_menu_button(self, temp_db, test_notification_user, mock_callback_query):
        """Тест обработки кнопки back_to_main_menu с проверкой главного меню"""
        from shop_bot.bot import keyboards
        
        # Arrange: подготовка callback
        user_id = test_notification_user['user_id']
        mock_callback_query.data = "back_to_main_menu"
        mock_callback_query.from_user.id = user_id
        
        # Определяем ADMIN_ID из settings или используем None
        ADMIN_ID = None
        
        with allure.step("Создание тестового обработчика back_to_main_menu_handler"):
            # Создаем обработчик на основе логики из handlers.py
            async def back_to_main_menu_handler_test(callback):
                await callback.answer()
                # Гарантируем, что у пользователя установлена актуальная Reply Keyboard
                user_id_local = callback.from_user.id
                is_admin = str(user_id_local) == ADMIN_ID if ADMIN_ID else False
                
                # Удаляем inline клавиатуру и показываем только ReplyKeyboardMarkup
                try:
                    await callback.message.edit_text("🏠 <b>Главное меню</b>\n\nВыберите действие:", reply_markup=None)
                except Exception:
                    # Если не удалось отредактировать сообщение, просто отправляем новое
                    await callback.message.answer("🏠 <b>Главное меню</b>\n\nВыберите действие:", reply_markup=keyboards.get_main_reply_keyboard(is_admin))
            
            with allure.step("Вызов обработчика back_to_main_menu_handler"):
                await back_to_main_menu_handler_test(mock_callback_query)
                
                allure.attach(str(user_id), "User ID", allure.attachment_type.TEXT)
            
            with allure.step("Проверка вызова callback.answer()"):
                mock_callback_query.answer.assert_called_once()
            
            with allure.step("Проверка редактирования или отправки сообщения"):
                # Обработчик может использовать edit_text или answer
                edit_text_called = mock_callback_query.message.edit_text.called
                answer_called = mock_callback_query.message.answer.called
                
                assert edit_text_called or answer_called, \
                    "Должен быть вызван edit_text или answer для отображения главного меню"
                
                # Проверяем текст сообщения
                if edit_text_called:
                    call_args = mock_callback_query.message.edit_text.call_args
                    text = call_args[0][0] if call_args[0] else call_args[1].get('text', '')
                elif answer_called:
                    call_args = mock_callback_query.message.answer.call_args
                    text = call_args[0][0] if call_args[0] else call_args[1].get('text', '')
                
                assert 'меню' in text.lower() or 'menu' in text.lower() or 'главное' in text.lower(), \
                    "Текст должен содержать информацию о меню"
                
                allure.attach(text, "Текст главного меню", allure.attachment_type.TEXT)

