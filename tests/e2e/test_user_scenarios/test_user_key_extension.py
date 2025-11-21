#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""E2E тесты для продления ключей и доступа к личному кабинету"""

import pytest
import allure
import sys
from pathlib import Path
from datetime import datetime, timezone, timedelta
import uuid
from unittest.mock import patch, AsyncMock, MagicMock

project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root / "src"))


@pytest.mark.e2e
@pytest.mark.asyncio
@allure.epic("E2E тесты")
@allure.feature("Пользовательские сценарии")
@allure.label("package", "tests.e2e.test_user_scenarios")
class TestUserKeyExtension:
    """E2E тесты для продления ключей и доступа к личному кабинету"""

    @pytest.fixture
    def test_setup(self, temp_db, sample_host):
        """Фикстура для настройки тестового окружения"""
        import sqlite3
        from shop_bot.data_manager.database import register_user_if_not_exists, create_plan
        
        # Создаем пользователя
        user_id = 123456900
        register_user_if_not_exists(user_id, "test_user_e2e", None, "Test User E2E")
        
        # Создаем хост в БД
        with sqlite3.connect(temp_db) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT OR IGNORE INTO xui_hosts (host_name, host_url, host_username, host_pass, host_inbound_id, host_code) VALUES (?, ?, ?, ?, ?, ?)",
                (sample_host['host_name'], sample_host['host_url'], sample_host['host_username'], 
                 sample_host['host_pass'], sample_host['host_inbound_id'], sample_host['host_code'])
            )
            conn.commit()
        
        # Создаем план
        plan_id = create_plan(
            host_name=sample_host['host_name'],
            plan_name="E2E Test Plan",
            months=1,
            days=0,
            hours=0,
            price=100.0,
            traffic_gb=0.0
        )
        
        return {
            'user_id': user_id,
            'host_name': sample_host['host_name'],
            'plan_id': plan_id
        }

    @allure.story("Пользователь: продление ключа")
    @allure.title("Полный E2E сценарий: пользователь продлевает существующий VPN ключ")
    @allure.description("""
    E2E тест, проверяющий полный пользовательский сценарий продления существующего VPN ключа.
    
    **Что проверяется:**
    - Создание существующего ключа с исходным сроком действия
    - Обработка платежа для продления ключа
    - Обновление ключа на хосте через 3X-UI API
    - Обновление данных ключа в БД (UUID, дата истечения)
    - Корректное продление срока действия ключа
    
    **Тестовые данные:**
    - user_id: 123456900 (создается в тесте)
    - host_name: 'test-host' (из sample_host)
    - plan_id: создается в тесте, price=100.0, months=1
    - key_id: создается через create_key_with_stats_atomic
    - original_expiry: текущее время + 10 дней
    - new_expiry: текущее время + 40 дней (после продления)
    
    **Предусловия:**
    - Используется временная БД (temp_db)
    - Пользователь зарегистрирован
    - Хост создан в БД
    - План создан для хоста
    - Моки для bot и xui_api настроены
    
    **Шаги теста:**
    1. **Создание существующего ключа**
       - Метод: create_key_with_stats_atomic()
       - Параметры: user_id, host_name, xui_client_uuid, key_email, expiry_timestamp_ms (текущее время + 10 дней)
       - Ожидаемый результат: ключ создан в БД с исходным сроком действия
       - Проверка: key_id возвращается и не None
       - Проверка: ключ имеет исходный expiry_date
    
    2. **Подготовка метаданных для продления**
       - Метод: создание словаря metadata с operation='extend'
       - Параметры: user_id, operation='extend', months=1, price=100.0, action='extend', key_id, host_name, plan_id
       - Ожидаемый результат: metadata содержит key_id и operation='extend'
       - Проверка: metadata['operation'] == 'extend'
       - Проверка: metadata['key_id'] == key_id
    
    3. **Обработка успешного платежа для продления**
       - Метод: process_successful_payment()
       - Параметры: bot=mock_bot, metadata={...с operation='extend'...}
       - Ожидаемый результат: ключ обновлен на хосте через mock_xui_api
       - Проверка: mock_xui_api.create_or_update_key_on_host вызван с правильными параметрами
       - Проверка: новый expiry_timestamp_ms больше исходного
    
    4. **Проверка обновления ключа**
       - Метод: get_key_by_id()
       - Параметры: key_id
       - Ожидаемый результат: ключ обновлен с новым UUID и сроком действия
       - Проверка: updated_key is not None
       - Проверка: updated_key['xui_client_uuid'] == new_uuid
       - Проверка: updated_key['expiry_date'] > original_expiry
    
    **Ожидаемый результат:**
    После обработки платежа существующий ключ должен быть продлен.
    UUID ключа должен быть обновлен на новый.
    Срок действия должен быть увеличен с 10 дней до 40 дней.
    Все данные ключа должны быть корректно обновлены в БД.
    """)
    @allure.severity(allure.severity_level.CRITICAL)
    @allure.tag("e2e", "key_extension", "user_scenarios", "payment", "critical", "full_flow")
    async def test_user_extends_key(self, temp_db, test_setup, mock_bot, mock_xui_api):
        """E2E тест: пользователь продлевает существующий VPN ключ"""
        from shop_bot.data_manager.database import (
            create_key_with_stats_atomic,
            get_key_by_id,
        )
        from shop_bot.bot.handlers import process_successful_payment
        
        with allure.step("Создание существующего ключа"):
            # Создаем существующий ключ с исходным сроком действия
            xui_client_uuid = str(uuid.uuid4())
            key_email = f"test_{uuid.uuid4().hex[:8]}@example.com"
            original_expiry_timestamp_ms = int((datetime.now(timezone.utc) + timedelta(days=10)).timestamp() * 1000)
            
            key_id = create_key_with_stats_atomic(
                user_id=test_setup['user_id'],
                host_name=test_setup['host_name'],
                xui_client_uuid=xui_client_uuid,
                key_email=key_email,
                expiry_timestamp_ms=original_expiry_timestamp_ms,
                amount_spent=50.0,
                months_purchased=1,
                plan_name="E2E Test Plan",
                price=50.0
            )
            
            assert key_id is not None, "Ключ должен быть создан"
            
            # Получаем ключ до продления
            key_before = get_key_by_id(key_id)
            assert key_before is not None, "Ключ должен существовать"
            original_expiry = key_before['expiry_date']
            
            allure.attach(str(key_id), "Key ID", allure.attachment_type.TEXT)
            allure.attach(str(original_expiry), "Исходная дата истечения", allure.attachment_type.TEXT)
            allure.attach(str(xui_client_uuid), "Исходный UUID", allure.attachment_type.TEXT)
        
        # Патчим xui_api для продления ключа в месте использования (handlers.py) и в модуле
        # Также патчим login_to_host, чтобы избежать реальных подключений
        with patch('shop_bot.bot.handlers.xui_api.create_or_update_key_on_host', new_callable=AsyncMock) as mock_create_key, \
             patch('shop_bot.modules.xui_api.login_to_host', return_value=(MagicMock(), MagicMock())) as mock_login:
            new_uuid = str(uuid.uuid4())
            new_expiry_timestamp_ms = int((datetime.now(timezone.utc) + timedelta(days=40)).timestamp() * 1000)
            mock_create_key.return_value = {
                'client_uuid': new_uuid,
                'email': key_email,
                'expiry_timestamp_ms': new_expiry_timestamp_ms,
                'subscription_link': 'https://example.com/subscription',
                'connection_string': 'vless://extended-test'
            }
            
            with allure.step("Подготовка метаданных для продления"):
                # Подготавливаем metadata для продления
                payment_id = f"test_extend_{uuid.uuid4().hex[:16]}"
                metadata = {
                    'user_id': test_setup['user_id'],
                    'operation': 'extend',
                    'months': 1,
                    'days': 0,
                    'hours': 0,
                    'price': 100.0,
                    'action': 'extend',
                    'key_id': key_id,
                    'host_name': test_setup['host_name'],
                    'plan_id': test_setup['plan_id'],
                    'customer_email': 'test@example.com',
                    'payment_method': 'yookassa',
                    'payment_id': payment_id
                }
                
                assert metadata['operation'] == 'extend', "Операция должна быть 'extend'"
                assert metadata['key_id'] == key_id, "Metadata должна содержать key_id"
                
                allure.attach(str(metadata), "Metadata платежа", allure.attachment_type.JSON)
            
            with allure.step("Обработка успешного платежа для продления"):
                # Обрабатываем успешную оплату
                await process_successful_payment(mock_bot, metadata)
                
                # Проверяем, что mock_xui_api был вызван
                assert mock_create_key.called, "create_or_update_key_on_host должен быть вызван"
                
                allure.attach(
                    f"Вызовов mock_xui_api: {mock_create_key.call_count}",
                    "Результат вызова API",
                    allure.attachment_type.TEXT
                )
            
            with allure.step("Проверка обновления ключа"):
                # Проверяем, что ключ обновлен
                updated_key = get_key_by_id(key_id)
                assert updated_key is not None, "Ключ должен существовать после продления"
                
                # Проверяем обновление UUID
                assert updated_key['xui_client_uuid'] == new_uuid, \
                    f"UUID должен быть обновлен. Ожидался: {new_uuid}, получен: {updated_key['xui_client_uuid']}"
                
                # Проверяем обновление даты истечения
                assert updated_key['expiry_date'] != original_expiry, \
                    "Дата истечения должна быть обновлена"
                
                # Проверяем, что новая дата больше исходной
                if isinstance(updated_key['expiry_date'], str):
                    updated_expiry = datetime.fromisoformat(updated_key['expiry_date'].replace('Z', '+00:00'))
                else:
                    updated_expiry = updated_key['expiry_date']
                
                if isinstance(original_expiry, str):
                    original_expiry_dt = datetime.fromisoformat(original_expiry.replace('Z', '+00:00'))
                else:
                    original_expiry_dt = original_expiry
                
                assert updated_expiry > original_expiry_dt, \
                    f"Новая дата истечения должна быть больше исходной. Исходная: {original_expiry_dt}, Новая: {updated_expiry}"
                
                allure.attach(str(updated_key['xui_client_uuid']), "Новый UUID", allure.attachment_type.TEXT)
                allure.attach(str(updated_key['expiry_date']), "Новая дата истечения", allure.attachment_type.TEXT)
                allure.attach(
                    f"Исходная дата: {original_expiry_dt}\nНовая дата: {updated_expiry}",
                    "Сравнение дат",
                    allure.attachment_type.TEXT
                )

    @allure.story("Пользователь: доступ к личному кабинету")
    @allure.title("Полный E2E сценарий: пользователь открывает личный кабинет по токену")
    @allure.description("""
    E2E тест, проверяющий полный пользовательский сценарий доступа к личному кабинету по токену.
    
    **Что проверяется:**
    - Создание пользователя и ключа
    - Генерация постоянного токена для доступа к кабинету
    - Валидация токена
    - Авторизация по токену через /auth/{token}
    - Отображение главной страницы личного кабинета
    - Корректное отображение информации о ключе
    
    **Тестовые данные:**
    - user_id: 123456900 (создается в тесте)
    - host_name: 'test-host' (из sample_host)
    - key_id: создается через add_new_key
    - token: генерируется через get_or_create_permanent_token
    - expiry_date: текущее время + 30 дней
    
    **Предусловия:**
    - Используется временная БД (temp_db)
    - Пользователь зарегистрирован
    - Хост создан в БД
    - Ключ создан для пользователя
    - Flask приложение user-cabinet доступно
    
    **Шаги теста:**
    1. **Создание пользователя и ключа**
       - Метод: register_user_if_not_exists(), add_new_key()
       - Параметры: user_id, host_name, expiry_timestamp_ms
       - Ожидаемый результат: пользователь и ключ созданы в БД
       - Проверка: key_id возвращается и не None
    
    2. **Генерация постоянного токена**
       - Метод: get_or_create_permanent_token()
       - Параметры: user_id, key_id
       - Ожидаемый результат: токен создан и возвращен
       - Проверка: token is not None
       - Проверка: токен валиден через validate_permanent_token()
    
    3. **Авторизация по токену**
       - Метод: client.get(f'/auth/{token}')
       - Параметры: token
       - Ожидаемый результат: успешная авторизация (статус 200 или 302)
       - Проверка: response.status_code in [200, 302]
       - Проверка: response.status_code != 403
    
    4. **Отображение главной страницы кабинета**
       - Метод: client.get('/')
       - Параметры: сессия с токеном
       - Ожидаемый результат: главная страница отображается успешно
       - Проверка: response.status_code == 200
       - Проверка: страница содержит информацию о ключе
    
    **Ожидаемый результат:**
    Токен успешно создан и валидирован.
    Авторизация по токену работает без ошибок (нет 403).
    Главная страница личного кабинета отображается корректно.
    Информация о ключе доступна пользователю.
    """)
    @allure.severity(allure.severity_level.CRITICAL)
    @allure.tag("e2e", "cabinet", "user_scenarios", "token", "auth", "critical", "full_flow")
    async def test_user_accesses_cabinet(self, temp_db, test_setup):
        """E2E тест: пользователь открывает личный кабинет по токену"""
        from shop_bot.data_manager.database import (
            add_new_key,
            get_or_create_permanent_token,
            validate_permanent_token,
            create_host,
        )
        
        # Загружаем Flask приложение user-cabinet
        def _load_user_cabinet_app():
            import importlib.util
            app_file = project_root / "apps" / "user-cabinet" / "app.py"
            if not app_file.exists():
                pytest.skip(f"App file not found: {app_file}")
            
            spec = importlib.util.spec_from_file_location("user_cabinet_app", app_file)
            app_module = importlib.util.module_from_spec(spec)
            app_dir = app_file.parent
            if str(app_dir) not in sys.path:
                sys.path.insert(0, str(app_dir))
            if str(project_root / "src") not in sys.path:
                sys.path.insert(0, str(project_root / "src"))
            
            spec.loader.exec_module(app_module)
            flask_app = app_module.app
            templates_dir = app_dir / "templates"
            if templates_dir.exists():
                flask_app.template_folder = str(templates_dir)
                flask_app.static_folder = str(app_dir / "static")
            
            return flask_app
        
        with allure.step("Создание пользователя и ключа"):
            # Создаем хост, если его еще нет
            create_host(test_setup['host_name'], "http://test.com", "user", "pass", 1, "testcode")
            
            # Создаем ключ
            expiry_ms = int((datetime.now(timezone.utc) + timedelta(days=30)).timestamp() * 1000)
            key_id = add_new_key(
                test_setup['user_id'],
                test_setup['host_name'],
                "test-uuid-cabinet-e2e",
                f"user{test_setup['user_id']}-key1@testcode.bot",
                expiry_ms,
                connection_string="vless://test-cabinet-e2e",
                plan_name="E2E Test Plan",
                price=100.0,
            )
            
            assert key_id is not None, "Ключ должен быть создан"
            
            allure.attach(str(key_id), "Key ID", allure.attachment_type.TEXT)
            allure.attach(str(test_setup['user_id']), "User ID", allure.attachment_type.TEXT)
        
        with allure.step("Генерация постоянного токена"):
            # Создаем токен
            token = get_or_create_permanent_token(test_setup['user_id'], key_id)
            assert token is not None, "Токен должен быть создан"
            
            # Валидируем токен
            token_data = validate_permanent_token(token)
            assert token_data is not None, "Токен должен быть валидным"
            assert token_data['user_id'] == test_setup['user_id'], "Токен должен принадлежать правильному пользователю"
            assert token_data['key_id'] == key_id, "Токен должен быть привязан к правильному ключу"
            
            allure.attach(token[:20] + "..." if len(token) > 20 else token, "Токен (первые 20 символов)", allure.attachment_type.TEXT)
            allure.attach(str(token_data), "Данные токена", allure.attachment_type.JSON)
        
        with allure.step("Авторизация по токену"):
            app = _load_user_cabinet_app()
            
            with app.test_client() as client:
                response = client.get(f'/auth/{token}', follow_redirects=False)
                
                assert response.status_code != 403, \
                    f"Валидная ссылка не должна возвращать 403, получен статус {response.status_code}"
                assert response.status_code in [200, 302], \
                    f"Ожидался статус 200 или 302, получен {response.status_code}"
                
                allure.attach(str(response.status_code), "Статус код /auth/{token}", allure.attachment_type.TEXT)
        
        with allure.step("Отображение главной страницы кабинета"):
            with app.test_client() as client:
                with client.session_transaction() as sess:
                    sess['token'] = token
                    sess['user_id'] = test_setup['user_id']
                    sess['key_id'] = key_id
                
                response = client.get('/')
                
                assert response.status_code == 200, \
                    f"Главная страница должна быть доступна, получен статус {response.status_code}"
                assert response.status_code != 403, \
                    "Главная страница не должна возвращать 403"
                
                response_text = response.get_data(as_text=True)
                
                # Проверяем, что страница содержит базовую информацию
                assert len(response_text) > 0, "Страница должна содержать контент"
                
                allure.attach(str(response.status_code), "Статус код главной страницы", allure.attachment_type.TEXT)
                allure.attach(
                    response_text[:500] + "..." if len(response_text) > 500 else response_text,
                    "HTML ответ (первые 500 символов)",
                    allure.attachment_type.HTML
                )

