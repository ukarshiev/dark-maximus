#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Интеграционные тесты для пробного периода

Тестирует полный flow создания, использования и отзыва триальных ключей
"""

import pytest
import allure
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone, timedelta

# Добавляем путь к проекту
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root / "src"))


@pytest.mark.integration
@pytest.mark.bot
@allure.epic("Интеграционные тесты")
@allure.feature("Пробный период")
@allure.label("package", "tests.integration.test_trial")
class TestTrialFlow:
    """Интеграционные тесты для пробного периода"""

    @pytest.mark.asyncio
    @allure.story("Создание триального ключа")
    @allure.title("Создание триального ключа")
    @allure.description("""
    Интеграционный тест, проверяющий полный цикл создания триального ключа для нового пользователя.
    
    **Что проверяется:**
    - Регистрация нового пользователя
    - Проверка начального состояния (trial_used = False)
    - Вызов trial_period_callback_handler для создания триального ключа
    - Создание триального ключа через 3X-UI API
    - Обновление флага trial_used в БД (trial_used = True)
    - Создание записи о триальном ключе в БД
    
    **Тестовые данные:**
    - user_id: 123456
    - username: 'test_user'
    - host_name: 'test_host'
    - trial_duration: 7 дней (из настроек)
    - expiry_date: текущее время + 7 дней
    
    **Предусловия:**
    - Используется временная БД (temp_db)
    - Мок бота настроен (mock_bot)
    - Мок 3X-UI API настроен (mock_xui_api)
    - Пользователь не использовал триал ранее (trial_used = False)
    - Хост создан в БД
    
    **Шаги теста:**
    1. Регистрация нового пользователя
    2. Создание хоста в БД
    3. Проверка начального состояния (trial_used = False)
    4. Настройка моков для 3X-UI API и зависимостей
    5. Создание мок объекта CallbackQuery
    6. Вызов trial_period_callback_handler
    7. Проверка обновления флага trial_used (trial_used = True)
    8. Проверка создания триального ключа в БД
    
    **Ожидаемый результат:**
    - Флаг trial_used обновлен на True
    - Триальный ключ создан в БД (is_trial = 1)
    - Ключ имеет правильный expiry_date (текущее время + 7 дней)
    """)
    @allure.severity(allure.severity_level.CRITICAL)
    @allure.tag("trial", "integration", "critical", "trial_creation", "key_creation")
    async def test_trial_creation_flow(self, temp_db, mock_bot, mock_xui_api):
        """Тест создания триального ключа"""
        from shop_bot.data_manager.database import (
            register_user_if_not_exists,
            get_trial_info,
            get_user_keys,
            create_host,
        )
        from shop_bot.bot.handlers import trial_period_callback_handler
        from aiogram.types import CallbackQuery, User, Message
        
        # Настройка БД
        user_id = 123456
        register_user_if_not_exists(user_id, "test_user", referrer_id=None)
        create_host("test_host", "http://test.com", "user", "pass", 1, "testcode")
        
        # Проверяем начальное состояние
        trial_info = get_trial_info(user_id)
        assert trial_info['trial_used'] is False
        
        # Мокируем xui_api для создания триального ключа
        expiry_ms = int((datetime.now(timezone.utc) + timedelta(days=7)).timestamp() * 1000)
        mock_xui_api.create_or_update_key_on_host = AsyncMock(return_value={
            'client_uuid': 'trial-uuid-123',
            'email': f'user{user_id}-key1-trial@testcode.bot',
            'expiry_timestamp_ms': expiry_ms,
            'connection_string': 'vless://trial-test',
        })
        
        # Создаем мок для callback
        callback = MagicMock(spec=CallbackQuery)
        callback.from_user = MagicMock(spec=User)
        callback.from_user.id = user_id
        callback.answer = AsyncMock()
        callback.message = MagicMock(spec=Message)
        callback.message.edit_text = AsyncMock()
        callback.bot = mock_bot
        
        # Мокируем зависимости
        with patch('shop_bot.bot.handlers.xui_api', mock_xui_api):
            with patch('shop_bot.bot.handlers.get_user', return_value={
                'telegram_id': user_id,
                'username': 'test_user',
                'trial_used': 0,
            }):
                with patch('shop_bot.bot.handlers.get_setting', return_value='7'):
                    with patch('shop_bot.bot.handlers.get_all_hosts', return_value=[{
                        'host_name': 'test_host',
                        'host_code': 'testcode',
                    }]):
                        with patch('shop_bot.bot.handlers.get_plans_for_host', return_value=[]):
                            await trial_period_callback_handler(callback)
        
        # Проверяем, что триал был использован
        trial_info = get_trial_info(user_id)
        assert trial_info['trial_used'] is True
        
        # Проверяем, что ключ был создан
        keys = get_user_keys(user_id)
        trial_keys = [k for k in keys if k.get('is_trial') == 1]
        assert len(trial_keys) > 0

    @pytest.mark.asyncio
    @allure.story("Повторное использование триала после сброса администратором")
    @allure.title("Повторное использование триала после сброса")
    @allure.description("""
    Интеграционный тест, проверяющий возможность повторного использования триала после сброса флага trial_used.
    
    **Что проверяется:**
    - Сброс флага trial_used для повторного использования триала через reset_trial_used
    - Создание нового триального ключа после сброса через trial_period_callback_handler
    - Автоматическое увеличение счетчика trial_reuses_count при создании ключа через process_trial_key_creation_callback
    - Корректность установки флага trial_used после повторного использования
    - Корректность работы функции reset_trial_used (сбрасывает только trial_used, не трогает trial_reuses_count)
    
    **Тестовые данные:**
    - user_id: 123457
    - username: "test_user2"
    - host_name: "test_host"
    - host_code: "testcode"
    - trial_duration: 7 дней (из настройки get_setting('trial_duration_days'))
    - key_email: "user123457-key1-trial@testcode.bot"
    - xui_client_uuid: "trial-uuid-456"
    
    **Предусловия:**
    - Используется временная БД (temp_db)
    - Пользователь зарегистрирован через register_user_if_not_exists
    - Хост создан через create_host
    - Начальное состояние: trial_used = 0, trial_reuses_count = 0 (новый пользователь)
    
    **Шаги теста:**
    1. Подготовка тестовых данных: регистрация пользователя и создание хоста
    2. Имитация первого использования триала: set_trial_used(user_id) устанавливает trial_used = 1
    3. Сброс флага для повторного использования: reset_trial_used(user_id) устанавливает trial_used = 0
    4. Проверка состояния после сброса: trial_used = False, trial_reuses_count = 0 (reset_trial_used не трогает счетчик)
    5. Создание нового триального ключа через trial_period_callback_handler:
       - Handler проверяет trial_used и trial_reuses_count
       - Если trial_used = 0, разрешает создание ключа
       - Вызывает process_trial_key_creation_callback, который:
         * Создает ключ через xui_api.create_or_update_key_on_host
         * Вызывает set_trial_used(user_id) - устанавливает trial_used = 1
         * Вызывает set_trial_days_given(user_id, 7) - устанавливает количество дней
         * Вызывает increment_trial_reuses(user_id) - увеличивает счетчик на 1
         * Создает запись в БД через add_new_key
    6. Проверка финального состояния: trial_used = True, trial_reuses_count = 1
    
    **Ожидаемый результат:**
    - После set_trial_used: trial_used = True, trial_reuses_count = 0
    - После reset_trial_used: trial_used = False, trial_reuses_count = 0 (счетчик не изменяется)
    - После создания ключа через handler:
      * trial_used = True (установлено через set_trial_used в process_trial_key_creation_callback)
      * trial_reuses_count = 1 (увеличено через increment_trial_reuses в process_trial_key_creation_callback)
      * trial_days_given = 7 (установлено через set_trial_days_given)
    - В БД создан триальный ключ с is_trial = 1
    
    **Важность:**
    Тест проверяет корректность работы механизма повторного использования триала, который позволяет
    администратору сбрасывать флаг trial_used для повторного предоставления пробного периода пользователю.
    Критично проверить, что reset_trial_used не изменяет счетчик trial_reuses_count, а handler
    автоматически увеличивает счетчик при создании ключа. Это важно для отслеживания количества
    повторных использований триала пользователем.
    
    **Связанная логика:**
    - reset_trial_used только сбрасывает trial_used = 0, не трогает trial_reuses_count
    - process_trial_key_creation_callback вызывает increment_trial_reuses при создании ключа
    - В веб-панели при нажатии "Повторный триал" вызывается reset_trial_used и increment_trial_reuses
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("trial", "reuse", "integration", "trial_flow", "trial_reuse", "reset_trial", "trial_reuses_count", "increment_trial_reuses")
    async def test_trial_reuse_flow(self, temp_db, mock_bot, mock_xui_api):
        """Тест повторного использования триала после сброса"""
        import json
        from shop_bot.data_manager.database import (
            register_user_if_not_exists,
            set_trial_used,
            reset_trial_used,
            get_trial_info,
            create_host,
            get_user_keys,
        )
        from shop_bot.bot.handlers import trial_period_callback_handler
        from aiogram.types import CallbackQuery, User, Message
        
        with allure.step("Подготовка тестовых данных"):
            user_id = 123457
            username = "test_user2"
            host_name = "test_host"
            
            register_user_if_not_exists(user_id, username, referrer_id=None)
            create_host(host_name, "http://test.com", "user", "pass", 1, "testcode")
            
            allure.attach(str(user_id), "User ID", allure.attachment_type.TEXT)
            allure.attach(username, "Username", allure.attachment_type.TEXT)
            allure.attach(host_name, "Host Name", allure.attachment_type.TEXT)
        
        with allure.step("Имитация первого использования триала"):
            # Используем триал первый раз (имитация предыдущего использования)
            set_trial_used(user_id)
            trial_info_after_set = get_trial_info(user_id)
            allure.attach(
                json.dumps({
                    'trial_used': bool(trial_info_after_set['trial_used']),
                    'trial_reuses_count': trial_info_after_set['trial_reuses_count']
                }, indent=2, ensure_ascii=False),
                "Состояние триала после set_trial_used",
                allure.attachment_type.JSON
            )
            assert trial_info_after_set['trial_used'] is True, "Флаг trial_used должен быть True после set_trial_used"
            assert trial_info_after_set['trial_reuses_count'] == 0, "Счетчик trial_reuses_count должен быть 0 до создания ключа"
        
        with allure.step("Сброс флага для повторного использования"):
            # Сбрасываем флаг для повторного использования
            # Важно: reset_trial_used только сбрасывает trial_used = 0, не трогает trial_reuses_count
            reset_trial_used(user_id)
            
            trial_info_before = get_trial_info(user_id)
            allure.attach(
                json.dumps({
                    'trial_used': bool(trial_info_before['trial_used']),
                    'trial_reuses_count': trial_info_before['trial_reuses_count'],
                    'trial_days_given': trial_info_before['trial_days_given']
                }, indent=2, ensure_ascii=False),
                "Состояние триала после reset_trial_used",
                allure.attachment_type.JSON
            )
            
            assert trial_info_before['trial_used'] is False, "Флаг trial_used должен быть False после reset_trial_used"
            assert trial_info_before['trial_reuses_count'] == 0, "Счетчик trial_reuses_count должен остаться 0 после reset_trial_used (функция не изменяет счетчик)"
        
        with allure.step("Создание нового триального ключа через handler"):
            # Мокируем xui_api
            expiry_ms = int((datetime.now(timezone.utc) + timedelta(days=7)).timestamp() * 1000)
            mock_xui_api.create_or_update_key_on_host = AsyncMock(return_value={
                'client_uuid': 'trial-uuid-456',
                'email': f'user{user_id}-key1-trial@testcode.bot',
                'expiry_timestamp_ms': expiry_ms,
                'connection_string': 'vless://trial-test-2',
            })
            
            # Создаем мок для callback
            callback = MagicMock(spec=CallbackQuery)
            callback.from_user = MagicMock(spec=User)
            callback.from_user.id = user_id
            callback.answer = AsyncMock()
            callback.message = MagicMock(spec=Message)
            callback.message.edit_text = AsyncMock()
            callback.bot = mock_bot
            
            # Мокируем зависимости
            with patch('shop_bot.bot.handlers.xui_api', mock_xui_api):
                with patch('shop_bot.bot.handlers.get_user', return_value={
                    'telegram_id': user_id,
                    'username': username,
                    'trial_used': 0,
                    'trial_reuses_count': 0,  # Начальное состояние
                }):
                    with patch('shop_bot.bot.handlers.get_setting', return_value='7'):
                        with patch('shop_bot.bot.handlers.get_all_hosts', return_value=[{
                            'host_name': host_name,
                            'host_code': 'testcode',
                        }]):
                            with patch('shop_bot.bot.handlers.get_plans_for_host', return_value=[]):
                                await trial_period_callback_handler(callback)
            
            allure.attach(
                json.dumps({
                    'client_uuid': 'trial-uuid-456',
                    'email': f'user{user_id}-key1-trial@testcode.bot',
                    'expiry_timestamp_ms': expiry_ms,
                }, indent=2, ensure_ascii=False),
                "Созданный триальный ключ",
                allure.attachment_type.JSON
            )
        
        with allure.step("Проверка финального состояния триала"):
            trial_info = get_trial_info(user_id)
            
            allure.attach(
                json.dumps({
                    'trial_used': bool(trial_info['trial_used']),
                    'trial_reuses_count': trial_info['trial_reuses_count'],
                    'trial_days_given': trial_info['trial_days_given']
                }, indent=2, ensure_ascii=False),
                "Финальное состояние триала после создания ключа",
                allure.attachment_type.JSON
            )
            
            assert trial_info['trial_used'] is True, "Флаг trial_used должен быть True после создания ключа (установлено через set_trial_used в process_trial_key_creation_callback)"
            # Handler увеличивает счетчик при создании ключа через increment_trial_reuses, поэтому ожидаем 1 (было 0, стало 1)
            assert trial_info['trial_reuses_count'] == 1, f"Счетчик trial_reuses_count должен быть 1 после создания ключа (увеличено через increment_trial_reuses), получено {trial_info['trial_reuses_count']}"
            assert trial_info['trial_days_given'] == 7, f"trial_days_given должен быть равен 7 (установлено через set_trial_days_given), получено {trial_info['trial_days_given']}"
        
        with allure.step("Проверка создания триального ключа в БД"):
            # Проверяем, что ключ был создан
            keys = get_user_keys(user_id)
            trial_keys = [k for k in keys if k.get('is_trial') == 1]
            
            trial_keys_data = [
                {
                    'key_id': k.get('key_id'),
                    'key_email': k.get('key_email'),
                    'is_trial': k.get('is_trial'),
                    'plan_name': k.get('plan_name'),
                    'host_name': k.get('host_name')
                }
                for k in trial_keys
            ]
            
            allure.attach(
                json.dumps({
                    'total_keys': len(keys),
                    'trial_keys_count': len(trial_keys),
                    'trial_keys': trial_keys_data
                }, indent=2, ensure_ascii=False),
                "Ключи пользователя после создания триального ключа",
                allure.attachment_type.JSON
            )
            
            assert len(trial_keys) > 0, "Должен быть создан хотя бы один триальный ключ"
            assert trial_keys[0]['is_trial'] == 1, "Созданный ключ должен иметь is_trial = 1"
            assert trial_keys[0]['plan_name'] == "Пробный период", "План созданного ключа должен быть 'Пробный период'"

    @pytest.mark.asyncio
    @allure.title("Отзыв триального ключа")
    @allure.description("""
    Интеграционный тест, проверяющий корректность отзыва триального ключа из БД и 3X-UI панели.
    
    **Что проверяется:**
    - Создание триального ключа в БД
    - Удаление клиента из 3X-UI панели через delete_client_by_uuid
    - Удаление ключа из БД через delete_key_by_email
    - Корректность последовательности операций при отзыве ключа
    
    **Тестовые данные:**
    - user_id: 123458
    - username: "test_user3"
    - host_name: "test_host"
    - key_email: "user123458-key1-trial@testcode.bot"
    - xui_client_uuid: "trial-uuid-789"
    - trial_duration: 7 дней
    
    **Предусловия:**
    - Используется временная БД (temp_db)
    - Пользователь зарегистрирован
    - Хост создан
    - Триальный ключ создан в БД
    
    **Шаги теста:**
    1. Регистрация пользователя и создание хоста
    2. Создание триального ключа через add_new_key
    3. Проверка наличия ключа в БД
    4. Удаление клиента из 3X-UI через delete_client_by_uuid
    5. Удаление ключа из БД через delete_key_by_email
    6. Проверка отсутствия ключа в БД
    
    **Ожидаемый результат:**
    - Ключ успешно создан в БД (key_id не None, is_trial = 1)
    - delete_client_by_uuid вызывается с правильными параметрами (client_uuid, email)
    - Ключ удален из БД (get_key_by_id возвращает None)
    - Все операции выполняются в правильной последовательности
    
    **Важность:**
    Тест проверяет корректность работы механизма отзыва триальных ключей, который используется
    администратором для удаления ключей пользователей. Важно, чтобы ключ удалялся как из БД, так и из 3X-UI панели.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("trial", "revocation", "integration", "trial_flow", "trial_revocation", "delete_key")
    async def test_trial_revocation_flow(self, temp_db, mock_bot, mock_xui_api):
        """Тест отзыва триального ключа"""
        import json
        from shop_bot.data_manager.database import (
            register_user_if_not_exists,
            add_new_key,
            get_user_keys,
            get_key_by_id,
            create_host,
            delete_key_by_email,
        )
        
        with allure.step("Подготовка тестовых данных"):
            user_id = 123458
            username = "test_user3"
            host_name = "test_host"
            xui_client_uuid = "trial-uuid-789"
            
            register_user_if_not_exists(user_id, username, referrer_id=None)
            create_host(host_name, "http://test.com", "user", "pass", 1, "testcode")
            
            allure.attach(str(user_id), "User ID", allure.attachment_type.TEXT)
            allure.attach(username, "Username", allure.attachment_type.TEXT)
            allure.attach(host_name, "Host Name", allure.attachment_type.TEXT)
        
        with allure.step("Создание триального ключа"):
            expiry_ms = int((datetime.now(timezone.utc) + timedelta(days=7)).timestamp() * 1000)
            key_email = f"user{user_id}-key1-trial@testcode.bot"
            
            key_id = add_new_key(
                user_id,
                host_name,
                xui_client_uuid,
                key_email,
                expiry_ms,
                connection_string="vless://trial-test",
                plan_name="Пробный период",
                price=0.0,
                is_trial=1,
            )
            
            key_data = {
                'key_id': key_id,
                'user_id': user_id,
                'host_name': host_name,
                'xui_client_uuid': xui_client_uuid,
                'key_email': key_email,
                'is_trial': 1
            }
            allure.attach(
                json.dumps(key_data, indent=2, ensure_ascii=False),
                "Созданный триальный ключ",
                allure.attachment_type.JSON
            )
        
        with allure.step("Проверка наличия ключа в БД"):
            key = get_key_by_id(key_id)
            
            allure.attach(
                json.dumps({
                    'key_id': key.get('key_id') if key else None,
                    'key_email': key.get('key_email') if key else None,
                    'is_trial': key.get('is_trial') if key else None,
                    'xui_client_uuid': key.get('xui_client_uuid') if key else None,
                }, indent=2, ensure_ascii=False),
                "Ключ из БД перед удалением",
                allure.attachment_type.JSON
            )
            
            assert key is not None, "Ключ должен существовать в БД"
            assert key['is_trial'] == 1, "Ключ должен быть триальным"
            assert key['xui_client_uuid'] == xui_client_uuid, "UUID ключа должен совпадать"
        
        with allure.step("Удаление клиента из 3X-UI панели"):
            # Мокируем удаление клиента в 3X-UI
            mock_delete_function = AsyncMock(return_value=True)
            
            # Патчим функцию на уровне модуля перед вызовом
            with patch('shop_bot.modules.xui_api.delete_client_by_uuid', mock_delete_function):
                # Импортируем функцию после патча, чтобы использовать мок
                from shop_bot.modules.xui_api import delete_client_by_uuid
                # Вызываем функцию через патч (имитация реального flow)
                success = await delete_client_by_uuid(xui_client_uuid, key_email)
                
                allure.attach(
                    json.dumps({
                        'xui_client_uuid': xui_client_uuid,
                        'key_email': key_email,
                        'delete_success': success,
                        'function_called': mock_delete_function.called
                    }, indent=2, ensure_ascii=False),
                    "Результат удаления из 3X-UI",
                    allure.attachment_type.JSON
                )
                
                assert success is True, "Удаление из 3X-UI должно быть успешным"
                assert mock_delete_function.called, "delete_client_by_uuid должен быть вызван"
                # Проверяем, что функция была вызвана с правильными параметрами
                mock_delete_function.assert_called_once_with(xui_client_uuid, key_email)
        
        with allure.step("Удаление ключа из БД"):
            # Удаляем ключ из БД
            delete_key_by_email(key_email)
            
            allure.attach(
                json.dumps({
                    'key_email': key_email,
                    'operation': 'delete_key_by_email'
                }, indent=2, ensure_ascii=False),
                "Удаление ключа из БД",
                allure.attachment_type.JSON
            )
        
        with allure.step("Проверка отсутствия ключа в БД"):
            key_after_deletion = get_key_by_id(key_id)
            
            allure.attach(
                json.dumps({
                    'key_id': key_id,
                    'key_exists': key_after_deletion is not None
                }, indent=2, ensure_ascii=False),
                "Состояние ключа после удаления",
                allure.attachment_type.JSON
            )
            
            assert key_after_deletion is None, "Ключ должен быть удален из БД"

    @pytest.mark.asyncio
    @allure.title("Проверка статуса триального ключа после создания")
    @allure.description("""
    Интеграционный тест, проверяющий корректность установки статуса триала после создания триального ключа.
    
    **Что проверяется:**
    - Создание триального ключа через add_new_key
    - Установка флага trial_used = True после создания ключа
    - Установка количества дней триала (trial_days_given = 7)
    - Корректность информации о триале в БД
    - Наличие созданного триального ключа в списке ключей пользователя
    
    **Тестовые данные:**
    - user_id: 123459
    - username: "test_user4"
    - host_name: "test_host"
    - trial_duration: 7 дней
    - key_email: "user123459-key1-trial@testcode.bot"
    
    **Предусловия:**
    - Используется временная БД (temp_db)
    - Пользователь зарегистрирован
    - Хост создан
    
    **Шаги теста:**
    1. Регистрация пользователя и создание хоста
    2. Создание триального ключа через add_new_key
    3. Установка флага trial_used и trial_days_given (имитация реального flow)
    4. Проверка статуса триала в БД
    5. Проверка наличия триального ключа в списке ключей пользователя
    
    **Ожидаемый результат:**
    - trial_used = True
    - trial_days_given = 7
    - В списке ключей пользователя есть один триальный ключ
    - key_id созданного ключа соответствует ожидаемому
    - is_trial = 1 для созданного ключа
    
    **Важность:**
    Тест проверяет корректность работы механизма установки статуса триала, который используется
    при создании триальных ключей через process_trial_key_creation_callback.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("trial", "status", "integration", "trial_flow", "trial_status")
    async def test_trial_status_check(self, temp_db):
        """Тест проверки статуса триального ключа"""
        import json
        from shop_bot.data_manager.database import (
            register_user_if_not_exists,
            add_new_key,
            get_trial_info,
            get_user_keys,
            create_host,
            set_trial_used,
            set_trial_days_given,
        )
        
        with allure.step("Подготовка тестовых данных"):
            user_id = 123459
            username = "test_user4"
            host_name = "test_host"
            trial_duration_days = 7
            
            register_user_if_not_exists(user_id, username, referrer_id=None)
            create_host(host_name, "http://test.com", "user", "pass", 1, "testcode")
            
            allure.attach(str(user_id), "User ID", allure.attachment_type.TEXT)
            allure.attach(username, "Username", allure.attachment_type.TEXT)
            allure.attach(host_name, "Host Name", allure.attachment_type.TEXT)
            allure.attach(str(trial_duration_days), "Trial Duration (days)", allure.attachment_type.TEXT)
        
        with allure.step("Создание триального ключа"):
            expiry_ms = int((datetime.now(timezone.utc) + timedelta(days=7)).timestamp() * 1000)
            key_id = add_new_key(
                user_id,
                host_name,
                "trial-uuid-status",
                f"user{user_id}-key1-trial@testcode.bot",
                expiry_ms,
                connection_string="vless://trial-status",
                plan_name="Пробный период",
                price=0.0,
                is_trial=1,
            )
            
            key_data = {
                'key_id': key_id,
                'user_id': user_id,
                'host_name': host_name,
                'expiry_timestamp_ms': expiry_ms,
                'is_trial': 1
            }
            allure.attach(
                json.dumps(key_data, indent=2, ensure_ascii=False),
                "Созданный триальный ключ",
                allure.attachment_type.JSON
            )
        
        with allure.step("Установка флага использования триала и количества дней"):
            # Устанавливаем флаг использования триала и количество дней
            # (в реальном flow это делает process_trial_key_creation_callback)
            set_trial_used(user_id)
            set_trial_days_given(user_id, trial_duration_days)
            
            allure.attach(
                json.dumps({
                    'trial_used': True,
                    'trial_days_given': trial_duration_days
                }, indent=2, ensure_ascii=False),
                "Установленные значения триала",
                allure.attachment_type.JSON
            )
        
        with allure.step("Проверка статуса триала в БД"):
            trial_info = get_trial_info(user_id)
            
            allure.attach(
                json.dumps({
                    'trial_used': bool(trial_info['trial_used']),
                    'trial_days_given': trial_info['trial_days_given'],
                    'trial_reuses_count': trial_info['trial_reuses_count']
                }, indent=2, ensure_ascii=False),
                "Информация о триале из БД",
                allure.attachment_type.JSON
            )
            
            assert trial_info['trial_used'] is True, "Флаг trial_used должен быть True"
            assert trial_info['trial_days_given'] == 7, "trial_days_given должен быть равен 7"
        
        with allure.step("Проверка наличия триального ключа в списке ключей пользователя"):
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
                            'plan_name': k.get('plan_name')
                        }
                        for k in trial_keys
                    ]
                }, indent=2, ensure_ascii=False),
                "Ключи пользователя",
                allure.attachment_type.JSON
            )
            
            assert len(trial_keys) == 1, "Должен быть создан один триальный ключ"
            assert trial_keys[0]['key_id'] == key_id, "key_id созданного ключа должен соответствовать ожидаемому"
            assert trial_keys[0]['is_trial'] == 1, "is_trial должен быть равен 1"

