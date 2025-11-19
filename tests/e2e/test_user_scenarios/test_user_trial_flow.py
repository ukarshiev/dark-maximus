#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
E2E тесты для пробного периода

Тестирует полный пользовательский сценарий использования пробного периода:
от регистрации до получения триального ключа и проверки ограничений
"""

import pytest
import allure
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import datetime, timezone, timedelta

project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root / "src"))


@pytest.mark.e2e
@pytest.mark.asyncio
@allure.epic("E2E тесты")
@allure.feature("Пользовательские сценарии")
class TestUserTrialFlow:
    """E2E тесты для пробного периода"""

    @allure.story("Получение триального ключа новым пользователем")
    @allure.title("Новый пользователь запрашивает пробный период и получает ключ")
    @allure.description("""
    E2E тест, проверяющий полный цикл получения триального ключа новым пользователем.
    
    **Что проверяется:**
    - Регистрация нового пользователя
    - Создание хоста для триального ключа
    - Установка настройки длительности триала
    - Проверка начального состояния (trial_used = False, trial_reuses_count = 0)
    - Вызов обработчика пробного периода (trial_period_callback_handler)
    - Создание триального ключа через xui_api
    - Обновление состояния триала в БД (trial_used = True, trial_days_given = 7)
    - Проверка создания триального ключа в БД
    - Отправка сообщения пользователю об успешном создании ключа
    
    **Тестовые данные:**
    - user_id: 123456789
    - username: "trial_user"
    - fullname: "Trial User"
    - host_name: "test_host"
    - host_code: "testcode"
    - trial_duration_days: 7
    
    **Предусловия:**
    - Используется временная БД (temp_db)
    - Пользователь не зарегистрирован
    - Хост не создан
    - Триал не использован (trial_used = False)
    
    **Шаги теста:**
    1. Регистрация нового пользователя
    2. Создание хоста для триального ключа
    3. Установка настройки длительности триала (7 дней)
    4. Проверка начального состояния (trial_used = False, trial_reuses_count = 0)
    5. Подготовка моков для xui_api (создание триального ключа)
    6. Создание мока для callback query
    7. Вызов обработчика пробного периода (trial_period_callback_handler)
    8. Проверка обновления состояния триала (trial_used = True, trial_days_given = 7)
    9. Проверка создания триального ключа в БД
    10. Проверка отправки сообщения пользователю
    
    **Ожидаемый результат:**
    - Пользователь успешно регистрируется
    - Хост создается
    - Триал помечается как использованный (trial_used = True)
    - Устанавливается длительность триала (trial_days_given = 7)
    - Создается триальный ключ с правильными параметрами (is_trial = 1, plan_name = "Пробный период")
    - Пользователю отправляется сообщение об успешном создании ключа
    
    **Критичность:**
    Тест проверяет критичный функционал получения триального ключа новым пользователем.
    Это основной пользовательский сценарий, который должен работать корректно для привлечения новых пользователей.
    """)
    @allure.severity(allure.severity_level.CRITICAL)
    @allure.tag("trial", "e2e", "critical", "trial_flow", "new_user", "key_creation")
    async def test_new_user_requests_trial_and_gets_key(self, temp_db, mock_bot, mock_xui_api):
        """Тест: новый пользователь запрашивает пробный период и получает ключ"""
        import json
        from shop_bot.data_manager.database import (
            register_user_if_not_exists,
            get_user,
            get_trial_info,
            get_user_keys,
            create_host,
            get_setting,
            update_setting,
        )
        from shop_bot.bot.handlers import trial_period_callback_handler
        from aiogram.types import CallbackQuery, User, Message
        
        with allure.step("Подготовка тестовых данных: регистрация пользователя и создание хоста"):
            user_id = 123456789
            username = "trial_user"
            fullname = "Trial User"
            host_name = "test_host"
            host_code = "testcode"
            
            register_user_if_not_exists(user_id, username, None, fullname)
            create_host(host_name, "http://test.com", "user", "pass", 1, host_code)
            
            allure.attach(str(user_id), "User ID", allure.attachment_type.TEXT)
            allure.attach(username, "Username", allure.attachment_type.TEXT)
            allure.attach(fullname, "Fullname", allure.attachment_type.TEXT)
            allure.attach(host_name, "Host Name", allure.attachment_type.TEXT)
            allure.attach(host_code, "Host Code", allure.attachment_type.TEXT)
        
        with allure.step("Установка настройки длительности триала"):
            trial_duration_days = "7"
            update_setting("trial_duration_days", trial_duration_days)
            allure.attach(trial_duration_days, "Trial Duration (days)", allure.attachment_type.TEXT)
        
        with allure.step("Проверка начального состояния пользователя и триала"):
            user = get_user(user_id)
            assert user is not None, "Пользователь должен быть зарегистрирован"
            assert user['telegram_id'] == user_id
            
            trial_info_initial = get_trial_info(user_id)
            allure.attach(
                json.dumps({
                    'user_id': user['telegram_id'],
                    'username': user.get('username'),
                    'fullname': user.get('fullname'),
                    'trial_used': bool(trial_info_initial['trial_used']),
                    'trial_reuses_count': trial_info_initial['trial_reuses_count'],
                    'trial_days_given': trial_info_initial.get('trial_days_given')
                }, indent=2, ensure_ascii=False),
                "Начальное состояние пользователя и триала",
                allure.attachment_type.JSON
            )
            
            assert trial_info_initial['trial_used'] is False, "Триал не должен быть использован"
            assert trial_info_initial['trial_reuses_count'] == 0, "Счетчик повторных использований должен быть 0"
        
        with allure.step("Подготовка моков для создания триального ключа через xui_api"):
            expiry_ms = int((datetime.now(timezone.utc) + timedelta(days=7)).timestamp() * 1000)
            mock_key_data = {
                'client_uuid': 'trial-uuid-123',
                'email': f'user{user_id}-key1-trial@{host_code}.bot',
                'expiry_timestamp_ms': expiry_ms,
                'connection_string': 'vless://trial-test-connection',
                'subscription_link': 'https://example.com/subscription',
            }
            mock_xui_api.create_or_update_key_on_host = AsyncMock(return_value=mock_key_data)
            
            allure.attach(
                json.dumps(mock_key_data, indent=2, ensure_ascii=False),
                "Мокированные данные ключа от xui_api",
                allure.attachment_type.JSON
            )
        
        with allure.step("Создание мока для callback query"):
            callback = MagicMock(spec=CallbackQuery)
            callback.from_user = MagicMock(spec=User)
            callback.from_user.id = user_id
            callback.answer = AsyncMock()
            callback.message = MagicMock(spec=Message)
            callback.message.edit_text = AsyncMock()
            callback.bot = mock_bot
            
            allure.attach(
                json.dumps({
                    'callback_user_id': callback.from_user.id,
                    'callback_type': type(callback).__name__
                }, indent=2, ensure_ascii=False),
                "Данные callback query",
                allure.attachment_type.JSON
            )
        
        with allure.step("Вызов обработчика пробного периода"):
            # Мокируем зависимости
            with patch('shop_bot.bot.handlers.xui_api', mock_xui_api):
                with patch('shop_bot.bot.handlers.get_user', return_value=user):
                    with patch('shop_bot.bot.handlers.get_setting', side_effect=lambda key, default=None: {
                        'trial_duration_days': '7',
                    }.get(key, default)):
                        with patch('shop_bot.bot.handlers.get_all_hosts', return_value=[{
                            'host_name': host_name,
                            'host_code': host_code,
                        }]):
                            with patch('shop_bot.bot.handlers.get_plans_for_host', return_value=[]):
                                # Вызываем обработчик пробного периода
                                await trial_period_callback_handler(callback)
            
            allure.attach(
                str(callback.message.edit_text.called),
                "Callback message.edit_text вызван",
                allure.attachment_type.TEXT
            )
        
        with allure.step("Проверка результата: обновление состояния триала"):
            trial_info_after = get_trial_info(user_id)
            allure.attach(
                json.dumps({
                    'trial_used': bool(trial_info_after['trial_used']),
                    'trial_reuses_count': trial_info_after['trial_reuses_count'],
                    'trial_days_given': trial_info_after.get('trial_days_given')
                }, indent=2, ensure_ascii=False),
                "Состояние триала после создания ключа",
                allure.attachment_type.JSON
            )
            
            assert trial_info_after['trial_used'] is True, "Триал должен быть помечен как использованный"
            assert trial_info_after['trial_days_given'] == 7, "Должно быть установлено 7 дней триала"
        
        with allure.step("Проверка результата: создание триального ключа в БД"):
            keys = get_user_keys(user_id)
            trial_keys = [k for k in keys if k.get('is_trial') == 1]
            
            allure.attach(
                json.dumps({
                    'total_keys': len(keys),
                    'trial_keys_count': len(trial_keys),
                    'trial_keys': [
                        {
                            'key_id': k.get('key_id'),
                            'key_email': k.get('key_email'),
                            'is_trial': k.get('is_trial'),
                            'plan_name': k.get('plan_name'),
                            'status': k.get('status'),
                            'remaining_seconds': k.get('remaining_seconds')
                        }
                        for k in trial_keys
                    ]
                }, indent=2, ensure_ascii=False),
                "Созданные триальные ключи",
                allure.attachment_type.JSON
            )
            
            assert len(trial_keys) > 0, "Должен быть создан триальный ключ"
            assert trial_keys[0]['key_email'] == f'user{user_id}-key1-trial@{host_code}.bot'
            assert trial_keys[0]['is_trial'] == 1
            assert trial_keys[0]['plan_name'] == "Пробный период"
        
        with allure.step("Проверка результата: отправка сообщения пользователю"):
            assert callback.message.edit_text.called, "Должно быть отправлено сообщение пользователю"
            callback.answer.assert_called_once()
            
            if callback.message.edit_text.called and callback.message.edit_text.call_args:
                try:
                    # Пытаемся получить текст из позиционных аргументов
                    if callback.message.edit_text.call_args[0] and len(callback.message.edit_text.call_args[0]) > 0:
                        callback_text = callback.message.edit_text.call_args[0][0]
                    # Или из именованных аргументов
                    elif hasattr(callback.message.edit_text.call_args, 'kwargs') and 'text' in callback.message.edit_text.call_args.kwargs:
                        callback_text = callback.message.edit_text.call_args.kwargs['text']
                    else:
                        callback_text = "N/A (не удалось извлечь текст)"
                except (IndexError, AttributeError):
                    callback_text = "N/A (ошибка при извлечении текста)"
            else:
                callback_text = "N/A (call_args отсутствует)"
            
            allure.attach(
                callback_text,
                "Текст сообщения пользователю",
                allure.attachment_type.TEXT
            )

    @allure.title("Пользователь не может получить второй триал без сброса")
    @allure.description("""
    E2E тест, проверяющий, что пользователь не может получить второй триал без сброса администратором.
    
    **Что проверяется:**
    - Обработка запроса триала пользователем, который уже использовал триал
    - Проверка условия trial_used = True и trial_reuses_count = 0
    - Отправка сообщения об отказе пользователю
    - Сохранение состояния trial_used = True после попытки получить второй триал
    
    **Тестовые данные:**
    - user_id: 123456790
    - username: "trial_user2"
    - fullname: "Trial User 2"
    - host_name: "test_host"
    - trial_used: True (установлен перед тестом)
    - trial_reuses_count: 0
    
    **Предусловия:**
    - Используется временная БД (temp_db)
    - Пользователь зарегистрирован
    - Хост создан
    - Триал помечен как использованный (trial_used = True)
    - Счетчик повторных использований равен 0 (trial_reuses_count = 0)
    
    **Шаги теста:**
    1. Регистрация пользователя и создание хоста
    2. Установка флага trial_used = True (имитация использования триала)
    3. Проверка начального состояния (trial_used = True, trial_reuses_count = 0)
    4. Вызов обработчика пробного периода (trial_period_callback_handler)
    5. Проверка отправки сообщения об отказе пользователю
    6. Проверка сохранения состояния trial_used = True
    
    **Ожидаемый результат:**
    - Обработчик пробного периода отклоняет запрос
    - Пользователю отправляется сообщение с текстом, содержащим "уже использовали" или "использовали"
    - Флаг trial_used остается True
    - Новый триальный ключ не создается
    
    **Критичность:**
    Тест проверяет критичную бизнес-логику ограничения повторного использования триала без сброса администратором.
    Это предотвращает злоупотребление системой пробных периодов.
    """)
    @allure.story("Ограничение получения второго триала без сброса")
    @allure.severity(allure.severity_level.CRITICAL)
    @allure.tag("trial", "restriction", "e2e", "critical", "trial_flow", "second_trial")
    async def test_user_cannot_get_second_trial_without_reset(self, temp_db, mock_bot):
        """Тест: пользователь не может получить второй триал без сброса"""
        import json
        from shop_bot.data_manager.database import (
            register_user_if_not_exists,
            get_user,
            get_trial_info,
            set_trial_used,
            create_host,
        )
        from shop_bot.bot.handlers import trial_period_callback_handler
        from aiogram.types import CallbackQuery, User, Message
        
        with allure.step("Подготовка тестовых данных"):
            user_id = 123456790
            username = "trial_user2"
            fullname = "Trial User 2"
            host_name = "test_host"
            
            register_user_if_not_exists(user_id, username, None, fullname)
            create_host(host_name, "http://test.com", "user", "pass", 1, "testcode")
            
            allure.attach(str(user_id), "User ID", allure.attachment_type.TEXT)
            allure.attach(username, "Username", allure.attachment_type.TEXT)
            allure.attach(fullname, "Fullname", allure.attachment_type.TEXT)
            allure.attach(host_name, "Host Name", allure.attachment_type.TEXT)
        
        with allure.step("Установка флага trial_used = True (имитация использования триала)"):
            set_trial_used(user_id)
            
            trial_info_initial = get_trial_info(user_id)
            allure.attach(
                json.dumps({
                    'trial_used': bool(trial_info_initial['trial_used']),
                    'trial_reuses_count': trial_info_initial['trial_reuses_count'],
                    'trial_days_given': trial_info_initial.get('trial_days_given')
                }, indent=2, ensure_ascii=False),
                "Состояние триала после установки trial_used",
                allure.attachment_type.JSON
            )
            
            assert trial_info_initial['trial_used'] is True, "Флаг trial_used должен быть True"
            assert trial_info_initial['trial_reuses_count'] == 0, "Счетчик повторных использований должен быть 0"
        
        with allure.step("Создание мока для callback query"):
            callback = MagicMock(spec=CallbackQuery)
            callback.from_user = MagicMock(spec=User)
            callback.from_user.id = user_id
            callback.answer = AsyncMock()
            callback.message = MagicMock(spec=Message)
            callback.message.edit_text = AsyncMock()
            callback.bot = mock_bot
            
            user = get_user(user_id)
            allure.attach(
                json.dumps({
                    'user_id': user['telegram_id'],
                    'username': user.get('username'),
                    'fullname': user.get('fullname'),
                    'trial_used': bool(user.get('trial_used', 0))
                }, indent=2, ensure_ascii=False),
                "Данные пользователя",
                allure.attachment_type.JSON
            )
        
        with allure.step("Вызов обработчика пробного периода"):
            # Мокируем зависимости
            with patch('shop_bot.bot.handlers.get_user', return_value=user):
                with patch('shop_bot.bot.handlers.get_all_hosts', return_value=[{
                    'host_name': 'test_host',
                    'host_code': 'testcode',
                }]):
                    # Вызываем обработчик пробного периода
                    await trial_period_callback_handler(callback)
            
            allure.attach(
                str(callback.message.edit_text.called),
                "Callback message.edit_text вызван",
                allure.attachment_type.TEXT
            )
        
        with allure.step("Проверка отправки сообщения об отказе пользователю"):
            assert callback.message.edit_text.called, "Должно быть отправлено сообщение об отказе"
            
            callback_text = callback.message.edit_text.call_args[0][0]
            allure.attach(
                callback_text,
                "Текст сообщения об отказе",
                allure.attachment_type.TEXT
            )
            
            assert "уже использовали" in callback_text.lower() or "использовали" in callback_text.lower(), \
                "Сообщение должно указывать, что триал уже использован"
        
        with allure.step("Проверка сохранения состояния trial_used = True"):
            trial_info_final = get_trial_info(user_id)
            allure.attach(
                json.dumps({
                    'trial_used': bool(trial_info_final['trial_used']),
                    'trial_reuses_count': trial_info_final['trial_reuses_count'],
                    'trial_days_given': trial_info_final.get('trial_days_given')
                }, indent=2, ensure_ascii=False),
                "Состояние триала после попытки получить второй триал",
                allure.attachment_type.JSON
            )
            
            assert trial_info_final['trial_used'] is True, "Флаг trial_used должен остаться True"

    @allure.story("Повторное использование триала после сброса")
    @allure.title("Пользователь может повторно использовать триал после сброса")
    @allure.description("""
    E2E тест, проверяющий полный цикл повторного использования триала после сброса администратором.
    
    **Что проверяется:**
    - Возможность повторного использования триала после сброса флага trial_used
    - Корректность работы счетчика повторных использований (trial_reuses_count)
    - Создание нового триального ключа после сброса
    - Обновление состояния триала в БД после повторного использования
    
    **Тестовые данные:**
    - user_id: 123456791
    - username: "trial_user3"
    - host_name: "test_host"
    - trial_duration_days: 7
    
    **Предусловия:**
    - Используется временная БД (temp_db)
    - Пользователь зарегистрирован
    - Хост создан с тарифами
    - Триал был использован ранее и затем сброшен администратором
    
    **Шаги теста:**
    1. Регистрация пользователя и создание хоста
    2. Симуляция первого использования триала (set_trial_used, increment_trial_reuses)
    3. Сброс триала для повторного использования (reset_trial_used)
    4. Проверка состояния после сброса (trial_used=False, trial_reuses_count=1)
    5. Вызов обработчика пробного периода (trial_period_callback_handler)
    6. Проверка создания нового триального ключа
    7. Проверка обновления состояния триала (trial_used=True)
    
    **Ожидаемый результат:**
    - После сброса триал может быть использован повторно
    - Создается новый триальный ключ
    - Флаг trial_used устанавливается в True
    - Счетчик trial_reuses_count увеличивается до 2 (увеличивается при каждом использовании триала, включая повторное)
    - Пользователю отправляется сообщение об успешном создании ключа
    
    **Критичность:**
    Тест проверяет критичный функционал повторного использования триала, который используется администраторами
    для предоставления дополнительных пробных периодов пользователям.
    """)
    @allure.severity(allure.severity_level.CRITICAL)
    @allure.tag("trial", "reset", "reuse", "e2e", "critical", "trial_flow")
    async def test_user_can_reuse_trial_after_reset(self, temp_db, mock_bot, mock_xui_api):
        """Тест: пользователь может повторно использовать триал после сброса"""
        from shop_bot.data_manager.database import (
            register_user_if_not_exists,
            get_user,
            get_trial_info,
            set_trial_used,
            increment_trial_reuses,
            reset_trial_used,
            create_host,
            update_setting,
            get_user_keys,
        )
        from shop_bot.bot.handlers import trial_period_callback_handler
        from aiogram.types import CallbackQuery, User, Message
        import json
        
        with allure.step("Подготовка тестовых данных"):
            user_id = 123456791
            username = "trial_user3"
            host_name = "test_host"
            trial_duration_days = "7"
            
            register_user_if_not_exists(user_id, username, None, "Trial User 3")
            create_host(host_name, "http://test.com", "user", "pass", 1, "testcode")
            update_setting("trial_duration_days", trial_duration_days)
            
            allure.attach(str(user_id), "User ID", allure.attachment_type.TEXT)
            allure.attach(host_name, "Host Name", allure.attachment_type.TEXT)
            allure.attach(trial_duration_days, "Trial Duration (days)", allure.attachment_type.TEXT)
        
        with allure.step("Симуляция первого использования триала"):
            set_trial_used(user_id)
            increment_trial_reuses(user_id)
            
            # Проверяем состояние после первого использования
            trial_info_after_first = get_trial_info(user_id)
            allure.attach(
                json.dumps({
                    'trial_used': bool(trial_info_after_first['trial_used']),
                    'trial_reuses_count': trial_info_after_first['trial_reuses_count']
                }, indent=2, ensure_ascii=False),
                "Состояние триала после первого использования",
                allure.attachment_type.JSON
            )
        
        with allure.step("Сброс триала для повторного использования"):
            reset_trial_used(user_id)
            
            # Проверяем состояние после сброса
            trial_info_after_reset = get_trial_info(user_id)
            allure.attach(
                json.dumps({
                    'trial_used': bool(trial_info_after_reset['trial_used']),
                    'trial_reuses_count': trial_info_after_reset['trial_reuses_count']
                }, indent=2, ensure_ascii=False),
                "Состояние триала после сброса",
                allure.attachment_type.JSON
            )
            
            assert trial_info_after_reset['trial_used'] is False, "Триал должен быть сброшен"
            assert trial_info_after_reset['trial_reuses_count'] == 1, "Счетчик повторных использований должен быть 1"
        
        with allure.step("Подготовка моков для создания триального ключа"):
            expiry_ms = int((datetime.now(timezone.utc) + timedelta(days=7)).timestamp() * 1000)
            mock_key_data = {
                'client_uuid': 'trial-uuid-456',
                'email': f'user{user_id}-key1-trial@testcode.bot',
                'expiry_timestamp_ms': expiry_ms,
                'connection_string': 'vless://trial-test-connection-2',
                'subscription_link': 'https://example.com/subscription',
            }
            mock_xui_api.create_or_update_key_on_host = AsyncMock(return_value=mock_key_data)
            
            allure.attach(
                json.dumps(mock_key_data, indent=2, ensure_ascii=False),
                "Мокированные данные ключа от xui_api",
                allure.attachment_type.JSON
            )
        
        with allure.step("Создание мока для callback query"):
            callback = MagicMock(spec=CallbackQuery)
            callback.from_user = MagicMock(spec=User)
            callback.from_user.id = user_id
            callback.answer = AsyncMock()
            callback.message = MagicMock(spec=Message)
            callback.message.edit_text = AsyncMock()
            callback.bot = mock_bot
            
            user = get_user(user_id)
            allure.attach(
                json.dumps({
                    'user_id': user['telegram_id'],
                    'username': user.get('username'),
                    'fullname': user.get('fullname')
                }, indent=2, ensure_ascii=False),
                "Данные пользователя",
                allure.attachment_type.JSON
            )
        
        with allure.step("Вызов обработчика пробного периода"):
            # Мокируем зависимости
            with patch('shop_bot.bot.handlers.xui_api', mock_xui_api):
                with patch('shop_bot.bot.handlers.get_user', return_value=user):
                    with patch('shop_bot.bot.handlers.get_setting', side_effect=lambda key, default=None: {
                        'trial_duration_days': '7',
                    }.get(key, default)):
                        with patch('shop_bot.bot.handlers.get_all_hosts', return_value=[{
                            'host_name': 'test_host',
                            'host_code': 'testcode',
                        }]):
                            with patch('shop_bot.bot.handlers.get_plans_for_host', return_value=[]):
                                # Вызываем обработчик пробного периода
                                await trial_period_callback_handler(callback)
            
            allure.attach(
                str(callback.message.edit_text.called),
                "Callback message.edit_text вызван",
                allure.attachment_type.TEXT
            )
        
        with allure.step("Проверка результата: состояние триала после повторного использования"):
            trial_info_after_reuse = get_trial_info(user_id)
            allure.attach(
                json.dumps({
                    'trial_used': bool(trial_info_after_reuse['trial_used']),
                    'trial_reuses_count': trial_info_after_reuse['trial_reuses_count'],
                    'trial_days_given': trial_info_after_reuse.get('trial_days_given')
                }, indent=2, ensure_ascii=False),
                "Состояние триала после повторного использования",
                allure.attachment_type.JSON
            )
            
            assert trial_info_after_reuse['trial_used'] is True, "Триал должен быть снова использован"
            assert trial_info_after_reuse['trial_reuses_count'] == 2, "Счетчик повторных использований должен увеличиться до 2 (1 от первого использования + 1 от повторного использования)"
        
        with allure.step("Проверка результата: создание триального ключа"):
            keys = get_user_keys(user_id)
            trial_keys = [k for k in keys if k.get('is_trial') == 1]
            
            allure.attach(
                json.dumps({
                    'total_keys': len(keys),
                    'trial_keys_count': len(trial_keys),
                    'trial_keys': [
                        {
                            'key_id': k.get('key_id'),
                            'key_email': k.get('key_email'),
                            'is_trial': k.get('is_trial'),
                            'plan_name': k.get('plan_name'),
                            'status': k.get('status')
                        }
                        for k in trial_keys
                    ]
                }, indent=2, ensure_ascii=False),
                "Созданные триальные ключи",
                allure.attachment_type.JSON
            )
            
            assert len(trial_keys) > 0, "Должен быть создан триальный ключ"
            assert trial_keys[0]['key_email'] == f'user{user_id}-key1-trial@testcode.bot'
            assert trial_keys[0]['is_trial'] == 1
            assert trial_keys[0]['plan_name'] == "Пробный период"
        
        with allure.step("Проверка результата: отправка сообщения пользователю"):
            assert callback.message.edit_text.called, "Должно быть отправлено сообщение пользователю"
            callback.answer.assert_called_once()
            
            if callback.message.edit_text.called and callback.message.edit_text.call_args:
                try:
                    # Пытаемся получить текст из позиционных аргументов
                    if callback.message.edit_text.call_args[0] and len(callback.message.edit_text.call_args[0]) > 0:
                        message_text = callback.message.edit_text.call_args[0][0]
                    # Или из именованных аргументов
                    elif hasattr(callback.message.edit_text.call_args, 'kwargs') and 'text' in callback.message.edit_text.call_args.kwargs:
                        message_text = callback.message.edit_text.call_args.kwargs['text']
                    else:
                        message_text = "N/A (не удалось извлечь текст)"
                except (IndexError, AttributeError):
                    message_text = "N/A (ошибка при извлечении текста)"
            else:
                message_text = "N/A (call_args отсутствует)"
            
            allure.attach(
                message_text,
                "Текст сообщения пользователю",
                allure.attachment_type.TEXT
            )

    @allure.story("Ограничение получения триала при наличии активного ключа")
    @allure.title("Пользователь не может получить триал, если у него есть активный триальный ключ")
    @allure.description("""
    E2E тест, проверяющий ограничение получения триального ключа при наличии активного триального ключа.
    
    **Что проверяется:**
    - Регистрация пользователя
    - Создание активного триального ключа в БД
    - Проверка наличия активного триального ключа (is_trial = 1, remaining_seconds > 0, status != 'deactivate')
    - Вызов обработчика пробного периода (trial_period_callback_handler)
    - Отклонение запроса на создание нового триального ключа
    - Отправка сообщения об отказе пользователю
    - Сохранение состояния (новый триальный ключ не создается)
    
    **Тестовые данные:**
    - user_id: 123456792
    - username: "trial_user4"
    - fullname: "Trial User 4"
    - host_name: "test_host"
    - host_code: "testcode"
    - trial_key_email: "user{user_id}-key1-trial@testcode.bot"
    - trial_key_expiry: текущее время + 5 дней
    - is_trial: 1
    - plan_name: "Пробный период"
    
    **Предусловия:**
    - Используется временная БД (temp_db)
    - Пользователь зарегистрирован
    - Хост создан
    - У пользователя уже есть активный триальный ключ (is_trial = 1, remaining_seconds > 0)
    - Триал может быть не использован (trial_used = False), но есть активный ключ
    
    **Шаги теста:**
    1. Регистрация пользователя и создание хоста
    2. Создание активного триального ключа в БД
    3. Проверка наличия активного триального ключа
    4. Создание мока для callback query
    5. Вызов обработчика пробного периода (trial_period_callback_handler)
    6. Проверка отправки сообщения об отказе пользователю
    7. Проверка, что новый триальный ключ не создан
    
    **Ожидаемый результат:**
    - Обработчик пробного периода отклоняет запрос
    - Пользователю отправляется сообщение с текстом, содержащим "активный" или "уже есть"
    - Новый триальный ключ не создается
    - Состояние БД остается неизменным (количество триальных ключей не увеличивается)
    
    **Критичность:**
    Тест проверяет критичную бизнес-логику ограничения создания нескольких активных триальных ключей.
    Это предотвращает злоупотребление системой пробных периодов и обеспечивает корректную работу ограничений.
    """)
    @allure.severity(allure.severity_level.CRITICAL)
    @allure.tag("trial", "restriction", "e2e", "critical", "trial_flow", "active_key", "key_limitation")
    async def test_user_cannot_get_trial_with_active_trial_key(self, temp_db, mock_bot):
        """Тест: пользователь не может получить триал, если у него есть активный триальный ключ"""
        import json
        from shop_bot.data_manager.database import (
            register_user_if_not_exists,
            get_user,
            get_trial_info,
            create_host,
            add_new_key,
            get_user_keys,
        )
        from shop_bot.bot.handlers import trial_period_callback_handler
        from aiogram.types import CallbackQuery, User, Message
        
        with allure.step("Подготовка тестовых данных: регистрация пользователя и создание хоста"):
            user_id = 123456792
            username = "trial_user4"
            fullname = "Trial User 4"
            host_name = "test_host"
            host_code = "testcode"
            
            register_user_if_not_exists(user_id, username, None, fullname)
            create_host(host_name, "http://test.com", "user", "pass", 1, host_code)
            
            allure.attach(str(user_id), "User ID", allure.attachment_type.TEXT)
            allure.attach(username, "Username", allure.attachment_type.TEXT)
            allure.attach(fullname, "Fullname", allure.attachment_type.TEXT)
            allure.attach(host_name, "Host Name", allure.attachment_type.TEXT)
            allure.attach(host_code, "Host Code", allure.attachment_type.TEXT)
        
        with allure.step("Создание активного триального ключа в БД"):
            expiry_ms = int((datetime.now(timezone.utc) + timedelta(days=5)).timestamp() * 1000)
            trial_key_email = f"user{user_id}-key1-trial@{host_code}.bot"
            
            key_id = add_new_key(
                user_id,
                host_name,
                "active-trial-uuid",
                trial_key_email,
                expiry_ms,
                connection_string="vless://active-trial",
                plan_name="Пробный период",
                price=0.0,
                is_trial=1,
            )
            
            allure.attach(
                json.dumps({
                    'key_id': key_id,
                    'key_email': trial_key_email,
                    'expiry_timestamp_ms': expiry_ms,
                    'is_trial': 1,
                    'plan_name': "Пробный период",
                    'host_name': host_name
                }, indent=2, ensure_ascii=False),
                "Созданный активный триальный ключ",
                allure.attachment_type.JSON
            )
        
        with allure.step("Проверка наличия активного триального ключа и состояния триала"):
            trial_info = get_trial_info(user_id)
            keys = get_user_keys(user_id)
            trial_keys = [k for k in keys if k.get('is_trial') == 1]
            active_trial_keys = [k for k in trial_keys if k.get('remaining_seconds', 0) > 0 and k.get('status') != 'deactivate']
            
            allure.attach(
                json.dumps({
                    'trial_used': bool(trial_info['trial_used']),
                    'trial_reuses_count': trial_info['trial_reuses_count'],
                    'total_keys': len(keys),
                    'trial_keys_count': len(trial_keys),
                    'active_trial_keys_count': len(active_trial_keys),
                    'active_trial_keys': [
                        {
                            'key_id': k.get('key_id'),
                            'key_email': k.get('key_email'),
                            'is_trial': k.get('is_trial'),
                            'remaining_seconds': k.get('remaining_seconds'),
                            'status': k.get('status')
                        }
                        for k in active_trial_keys
                    ]
                }, indent=2, ensure_ascii=False),
                "Состояние триала и активных триальных ключей",
                allure.attachment_type.JSON
            )
            
            assert len(active_trial_keys) > 0, "Должен быть создан активный триальный ключ"
        
        with allure.step("Создание мока для callback query"):
            callback = MagicMock(spec=CallbackQuery)
            callback.from_user = MagicMock(spec=User)
            callback.from_user.id = user_id
            callback.answer = AsyncMock()
            callback.message = MagicMock(spec=Message)
            callback.message.edit_text = AsyncMock()
            callback.bot = mock_bot
            
            user = get_user(user_id)
            allure.attach(
                json.dumps({
                    'callback_user_id': callback.from_user.id,
                    'user_id': user['telegram_id'],
                    'username': user.get('username'),
                    'fullname': user.get('fullname')
                }, indent=2, ensure_ascii=False),
                "Данные callback query и пользователя",
                allure.attachment_type.JSON
            )
        
        with allure.step("Вызов обработчика пробного периода"):
            # Мокируем зависимости
            with patch('shop_bot.bot.handlers.get_user', return_value=user):
                with patch('shop_bot.bot.handlers.get_all_hosts', return_value=[{
                    'host_name': host_name,
                    'host_code': host_code,
                }]):
                    # Вызываем обработчик пробного периода
                    await trial_period_callback_handler(callback)
            
            allure.attach(
                str(callback.message.edit_text.called),
                "Callback message.edit_text вызван",
                allure.attachment_type.TEXT
            )
        
        with allure.step("Проверка результата: отправка сообщения об отказе пользователю"):
            assert callback.message.edit_text.called, "Должно быть отправлено сообщение об отказе"
            
            if callback.message.edit_text.called and callback.message.edit_text.call_args:
                try:
                    # Пытаемся получить текст из позиционных аргументов
                    if callback.message.edit_text.call_args[0] and len(callback.message.edit_text.call_args[0]) > 0:
                        callback_text = callback.message.edit_text.call_args[0][0]
                    # Или из именованных аргументов
                    elif hasattr(callback.message.edit_text.call_args, 'kwargs') and 'text' in callback.message.edit_text.call_args.kwargs:
                        callback_text = callback.message.edit_text.call_args.kwargs['text']
                    else:
                        callback_text = "N/A (не удалось извлечь текст)"
                except (IndexError, AttributeError):
                    callback_text = "N/A (ошибка при извлечении текста)"
            else:
                callback_text = "N/A (call_args отсутствует)"
            
            allure.attach(
                callback_text,
                "Текст сообщения об отказе",
                allure.attachment_type.TEXT
            )
            
            assert "активный" in callback_text.lower() or "уже есть" in callback_text.lower(), \
                "Сообщение должно указывать, что есть активный триальный ключ"
        
        with allure.step("Проверка результата: новый триальный ключ не создан"):
            keys_after = get_user_keys(user_id)
            trial_keys_after = [k for k in keys_after if k.get('is_trial') == 1]
            active_trial_keys_after = [k for k in trial_keys_after if k.get('remaining_seconds', 0) > 0 and k.get('status') != 'deactivate']
            
            allure.attach(
                json.dumps({
                    'total_keys_before': len(keys),
                    'total_keys_after': len(keys_after),
                    'trial_keys_count_before': len(trial_keys),
                    'trial_keys_count_after': len(trial_keys_after),
                    'active_trial_keys_count_before': len(active_trial_keys),
                    'active_trial_keys_count_after': len(active_trial_keys_after),
                    'new_keys_created': len(keys_after) - len(keys)
                }, indent=2, ensure_ascii=False),
                "Сравнение состояния ключей до и после вызова обработчика",
                allure.attachment_type.JSON
            )
            
            # Проверяем, что количество активных триальных ключей не увеличилось
            assert len(active_trial_keys_after) == len(active_trial_keys), \
                "Количество активных триальных ключей не должно увеличиться"

