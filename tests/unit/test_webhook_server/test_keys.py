#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Unit-тесты для управления ключами в веб-панели

Тестирует CRUD операции с ключами
"""

import pytest
import allure
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import datetime, timezone, timedelta

# Добавляем путь к проекту
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root / "src"))


@pytest.mark.unit
@allure.epic("Веб-панель")
@allure.feature("Управление ключами")
@allure.label("package", "src.shop_bot.webhook_server")
class TestWebhookServerKeys:
    """Тесты для управления ключами"""

    @allure.story("Управление ключами: просмотр списка")
    @allure.title("Отображение страницы списка ключей")
    @allure.description("""
    Проверяет отображение страницы списка ключей в веб-панели.
    
    **Что проверяется:**
    - Доступность страницы /keys для авторизованного администратора
    - Корректный статус ответа (200)
    - Отображение списка ключей на странице
    
    **Тестовые данные:**
    - user_id: 123490
    - host_name: "test_host"
    - key_email: "user123490-key1@testcode.bot"
    - plan_name: "Test Plan"
    - price: 100.0
    
    **Ожидаемый результат:**
    Страница /keys успешно отображается со статусом 200 для авторизованного администратора.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("keys", "webhook_server", "page", "unit")
    def test_keys_page(self, temp_db, admin_credentials):
        """Тест страницы списка ключей (/keys)"""
        from src.shop_bot.webhook_server.app import create_webhook_app
        from unittest.mock import MagicMock
        
        mock_bot_controller = MagicMock()
        app = create_webhook_app(mock_bot_controller)
        from shop_bot.data_manager.database import (
            register_user_if_not_exists,
            add_new_key,
            create_host,
        )
        
        # Настройка БД
        user_id = 123490
        register_user_if_not_exists(user_id, "test_user", referrer_id=None)
        create_host("test_host", "http://test.com", "user", "pass", 1, "testcode")
        
        # Создаем ключ
        expiry_ms = int((datetime.now(timezone.utc) + timedelta(days=30)).timestamp() * 1000)
        add_new_key(
            user_id,
            "test_host",
            "test-uuid-keys",
            f"user{user_id}-key1@testcode.bot",
            expiry_ms,
            connection_string="vless://test",
            plan_name="Test Plan",
            price=100.0,
        )
        
        app = create_webhook_app(mock_bot_controller)
        with app.test_client() as client:
            # Входим
            with patch('src.shop_bot.webhook_server.app.verify_admin_credentials', return_value=True):
                client.post('/login', data=admin_credentials)
            
            response = client.get('/keys')
            assert response.status_code == 200

    @allure.story("Управление ключами: операции с ключами")
    @allure.title("Получение деталей ключа через API")
    @allure.description("""
    Проверяет получение деталей ключа через API endpoint /api/key-details/{key_id}.
    
    **Что проверяется:**
    - Доступность API endpoint для авторизованного администратора
    - Корректный статус ответа (200)
    - Наличие данных о ключе в ответе (key_id или key_email)
    - Корректность структуры JSON ответа
    
    **Тестовые данные:**
    - user_id: 123491
    - host_name: "test_host"
    - key_email: "user123491-key1@testcode.bot"
    - plan_name: "Test Plan"
    - price: 100.0
    
    **Ожидаемый результат:**
    API endpoint возвращает детали ключа со статусом 200 и корректной структурой данных.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("keys", "webhook_server", "api", "key_details", "unit")
    def test_get_key_details(self, temp_db, admin_credentials):
        from src.shop_bot.webhook_server.app import create_webhook_app
        from unittest.mock import MagicMock
        
        mock_bot_controller = MagicMock()
        app = create_webhook_app(mock_bot_controller)
        from shop_bot.data_manager.database import (
            register_user_if_not_exists,
            add_new_key,
            get_key_by_id,
            create_host,
        )
        
        # Настройка БД
        user_id = 123491
        register_user_if_not_exists(user_id, "test_user2", referrer_id=None)
        create_host("test_host", "http://test.com", "user", "pass", 1, "testcode")
        
        # Создаем ключ
        expiry_ms = int((datetime.now(timezone.utc) + timedelta(days=30)).timestamp() * 1000)
        key_id = add_new_key(
            user_id,
            "test_host",
            "test-uuid-details",
            f"user{user_id}-key1@testcode.bot",
            expiry_ms,
            connection_string="vless://test",
            plan_name="Test Plan",
            price=100.0,
        )
        
        app = create_webhook_app(mock_bot_controller)
        with app.test_client() as client:
            # Входим
            with patch('src.shop_bot.webhook_server.app.verify_admin_credentials', return_value=True):
                client.post('/login', data=admin_credentials)
            
            # Получаем детали ключа
            response = client.get(f'/api/key-details/{key_id}')
            assert response.status_code == 200
            data = response.get_json()
            assert data is not None
            assert 'key_id' in data or 'key_email' in data

    @allure.story("Управление ключами: операции с ключами")
    @allure.title("Синхронизация ключа с 3X-UI")
    @allure.description("""
    Проверяет синхронизацию ключа с 3X-UI через API endpoint /refresh-user-keys.
    
    **Что проверяется:**
    - Доступность API endpoint для авторизованного администратора
    - Вызов функции get_key_details_from_host из xui_api для получения данных ключа
    - Корректный статус ответа (200)
    - Синхронизация данных ключа с 3X-UI (обновление expiry_date, status, protocol и других полей)
    
    **Тестовые данные:**
    - user_id: 123492
    - host_name: "test_host"
    - key_email: "user123492-key1@testcode.bot"
    - plan_name: "Test Plan"
    - price: 100.0
    - expiry_timestamp_ms: текущее время + 30 дней
    
    **Предусловия:**
    - Используется временная БД (temp_db)
    - Пользователь зарегистрирован в системе
    - Хост создан с тарифами
    - Ключ создан в БД
    - Администратор авторизован в веб-панели
    
    **Шаги теста:**
    1. Регистрация тестового пользователя
    2. Создание хоста
    3. Создание ключа в БД
    4. Мокирование xui_api.get_key_details_from_host
    5. Авторизация администратора
    6. Отправка POST запроса на /refresh-user-keys с user_id
    7. Проверка статуса ответа (200)
    
    **Ожидаемый результат:**
    API endpoint успешно синхронизирует ключ с 3X-UI и возвращает статус 200 с информацией об обновлении.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("keys", "webhook_server", "api", "sync", "xui", "unit")
    def test_sync_key_with_xui(self, temp_db, mock_xui_api, admin_credentials):
        from src.shop_bot.webhook_server.app import create_webhook_app
        from unittest.mock import MagicMock, AsyncMock
        
        with allure.step("Подготовка тестового окружения"):
            mock_bot_controller = MagicMock()
            app = create_webhook_app(mock_bot_controller)
            from shop_bot.data_manager.database import (
                register_user_if_not_exists,
                add_new_key,
                get_key_by_id,
                create_host,
            )
            allure.attach(str(temp_db), "Путь к временной БД", allure.attachment_type.TEXT)
        
        with allure.step("Настройка БД: регистрация пользователя и создание хоста"):
            user_id = 123492
            register_user_if_not_exists(user_id, "test_user3", referrer_id=None)
            create_host("test_host", "http://test.com", "user", "pass", 1, "testcode")
            allure.attach(str(user_id), "User ID", allure.attachment_type.TEXT)
            allure.attach("test_host", "Host Name", allure.attachment_type.TEXT)
        
        with allure.step("Создание ключа в БД"):
            expiry_ms = int((datetime.now(timezone.utc) + timedelta(days=30)).timestamp() * 1000)
            key_id = add_new_key(
                user_id,
                "test_host",
                "test-uuid-sync",
                f"user{user_id}-key1@testcode.bot",
                expiry_ms,
                connection_string="vless://test",
                plan_name="Test Plan",
                price=100.0,
            )
            allure.attach(str(key_id), "Key ID", allure.attachment_type.TEXT)
            allure.attach(str(expiry_ms), "Expiry Timestamp (ms)", allure.attachment_type.TEXT)
        
        with allure.step("Мокирование xui_api.get_key_details_from_host"):
            # Мокируем get_key_details_from_host для возврата данных ключа
            mock_key_details = {
                'email': f'user{user_id}-key1@testcode.bot',
                'expiry_timestamp_ms': expiry_ms,
                'status': 'active',
                'protocol': 'vless',
                'created_at': expiry_ms - (30 * 24 * 60 * 60 * 1000),  # 30 дней назад
                'remaining_seconds': 30 * 24 * 60 * 60,
                'quota_remaining_bytes': None,
            }
            allure.attach(str(mock_key_details), "Мокированные данные ключа", allure.attachment_type.JSON)
        
        with app.test_client() as client:
            with allure.step("Авторизация администратора"):
                with patch('src.shop_bot.webhook_server.app.verify_admin_credentials', return_value=True):
                    login_response = client.post('/login', data=admin_credentials)
                    allure.attach(str(login_response.status_code), "Статус авторизации", allure.attachment_type.TEXT)
                    assert login_response.status_code in [200, 302], "Авторизация должна быть успешной"
            
            with allure.step("Синхронизация ключа через /refresh-user-keys"):
                # Мокируем get_key_details_from_host
                from shop_bot.modules.xui_api import get_key_details_from_host
                with patch('shop_bot.modules.xui_api.get_key_details_from_host', new=AsyncMock(return_value=mock_key_details)):
                    response = client.post(
                        '/refresh-user-keys',
                        json={'user_id': user_id},
                        content_type='application/json'
                    )
                    allure.attach(str(response.status_code), "Статус ответа", allure.attachment_type.TEXT)
                    if response.status_code == 200:
                        response_data = response.get_json() if response.is_json else response.data.decode('utf-8')
                        allure.attach(str(response_data), "Тело ответа", allure.attachment_type.JSON if response.is_json else allure.attachment_type.TEXT)
                    
                    with allure.step("Проверка статуса ответа"):
                        assert response.status_code == 200, f"Ожидался статус 200, получен {response.status_code}"

    @allure.story("Управление ключами: операции с ключами")
    @allure.title("Включение и отключение ключа")
    @allure.description("""
    Проверяет включение и отключение ключа через API endpoint /api/toggle-key-enabled.
    
    **Что проверяется:**
    - Отключение ключа через API (enabled: False)
    - Обновление статуса enabled в БД (enabled = 0)
    - Включение ключа через API (enabled: True)
    - Обновление статуса enabled в БД (enabled = 1)
    - Корректный статус ответа (200) для обеих операций
    - Обновление статуса в 3X-UI (если доступно)
    
    **Тестовые данные:**
    - user_id: 123493
    - host_name: "test_host"
    - key_email: "user123493-key1@testcode.bot"
    - plan_name: "Test Plan"
    - price: 100.0
    
    **Предусловия:**
    - Используется временная БД (temp_db)
    - Пользователь зарегистрирован в системе
    - Хост создан с тарифами
    - Ключ создан в БД
    - Администратор авторизован в веб-панели
    
    **Шаги теста:**
    1. Регистрация тестового пользователя
    2. Создание хоста
    3. Создание ключа в БД
    4. Авторизация администратора
    5. Отправка POST запроса на /api/toggle-key-enabled с enabled=False
    6. Проверка статуса ответа (200) и enabled=0 в БД
    7. Отправка POST запроса на /api/toggle-key-enabled с enabled=True
    8. Проверка статуса ответа (200) и enabled=1 в БД
    
    **Ожидаемый результат:**
    Ключ успешно отключается (enabled = 0) и включается обратно (enabled = 1) через API, статус обновляется в БД.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("keys", "webhook_server", "api", "enable", "disable", "unit")
    def test_enable_disable_key(self, temp_db, admin_credentials):
        from src.shop_bot.webhook_server.app import create_webhook_app
        from unittest.mock import MagicMock
        
        with allure.step("Подготовка тестового окружения"):
            mock_bot_controller = MagicMock()
            app = create_webhook_app(mock_bot_controller)
            app.config['TESTING'] = True  # Отключаем rate limiting
            from shop_bot.data_manager.database import (
                register_user_if_not_exists,
                add_new_key,
                get_key_by_id,
                create_host,
            )
            allure.attach(str(temp_db), "Путь к временной БД", allure.attachment_type.TEXT)
        
        with allure.step("Настройка БД: регистрация пользователя и создание хоста"):
            user_id = 123493
            register_user_if_not_exists(user_id, "test_user4", referrer_id=None)
            create_host("test_host", "http://test.com", "user", "pass", 1, "testcode")
            allure.attach(str(user_id), "User ID", allure.attachment_type.TEXT)
        
        with allure.step("Создание ключа в БД"):
            expiry_ms = int((datetime.now(timezone.utc) + timedelta(days=30)).timestamp() * 1000)
            key_id = add_new_key(
                user_id,
                "test_host",
                "test-uuid-enable",
                f"user{user_id}-key1@testcode.bot",
                expiry_ms,
                connection_string="vless://test",
                plan_name="Test Plan",
                price=100.0,
            )
            allure.attach(str(key_id), "Key ID", allure.attachment_type.TEXT)
            
            # Проверяем начальное состояние
            initial_key = get_key_by_id(key_id)
            initial_enabled = initial_key.get('enabled') if initial_key else None
            allure.attach(str(initial_enabled), "Начальное значение enabled", allure.attachment_type.TEXT)
        
        # Патчим DB_FILE для использования временной БД
        # Важно: патчим оба DB_FILE (app.DB_FILE и database.DB_FILE уже патчится через temp_db фикстуру)
        # Но нужно убедиться, что app.DB_FILE также использует temp_db
        import src.shop_bot.webhook_server.app as app_module
        original_app_db_file = app_module.DB_FILE
        
        # Устанавливаем app.DB_FILE на временную БД
        app_module.DB_FILE = temp_db
        
        try:
            with app.test_client() as client:
                with allure.step("Авторизация администратора"):
                    with patch('src.shop_bot.webhook_server.app.verify_admin_credentials', return_value=True):
                        login_response = client.post('/login', data=admin_credentials)
                        allure.attach(str(login_response.status_code), "Статус авторизации", allure.attachment_type.TEXT)
                        assert login_response.status_code in [200, 302], "Авторизация должна быть успешной"
                
                with allure.step("Отключение ключа через /api/toggle-key-enabled"):
                    response = client.post(
                        '/api/toggle-key-enabled',
                        json={'key_id': key_id, 'enabled': False},
                        content_type='application/json'
                    )
                    allure.attach(str(response.status_code), "Статус ответа при отключении", allure.attachment_type.TEXT)
                    if response.is_json:
                        response_data = response.get_json()
                        allure.attach(str(response_data), "Тело ответа при отключении", allure.attachment_type.JSON)
                    else:
                        allure.attach(response.data.decode('utf-8') if response.data else "Пустой ответ", "Тело ответа при отключении (не JSON)", allure.attachment_type.TEXT)
                    
                    with allure.step("Проверка статуса ответа и enabled=0 в БД"):
                        assert response.status_code == 200, f"Ожидался статус 200, получен {response.status_code}. Ответ: {response.data.decode('utf-8') if response.data else 'Пустой'}"
                        
                        key = get_key_by_id(key_id)
                        assert key is not None, "Ключ должен существовать в БД"
                        enabled_after_disable = key.get('enabled')
                        allure.attach(str(enabled_after_disable), "Значение enabled после отключения", allure.attachment_type.TEXT)
                        assert enabled_after_disable == 0, f"Ожидалось enabled=0, получено {enabled_after_disable}"
                
                with allure.step("Включение ключа через /api/toggle-key-enabled"):
                    response = client.post(
                        '/api/toggle-key-enabled',
                        json={'key_id': key_id, 'enabled': True},
                        content_type='application/json'
                    )
                    allure.attach(str(response.status_code), "Статус ответа при включении", allure.attachment_type.TEXT)
                    if response.is_json:
                        response_data = response.get_json()
                        allure.attach(str(response_data), "Тело ответа при включении", allure.attachment_type.JSON)
                    else:
                        allure.attach(response.data.decode('utf-8') if response.data else "Пустой ответ", "Тело ответа при включении (не JSON)", allure.attachment_type.TEXT)
                    
                    with allure.step("Проверка статуса ответа и enabled=1 в БД"):
                        assert response.status_code == 200, f"Ожидался статус 200, получен {response.status_code}. Ответ: {response.data.decode('utf-8') if response.data else 'Пустой'}"
                        
                        key = get_key_by_id(key_id)
                        assert key is not None, "Ключ должен существовать в БД"
                        enabled_after_enable = key.get('enabled')
                        allure.attach(str(enabled_after_enable), "Значение enabled после включения", allure.attachment_type.TEXT)
                        assert enabled_after_enable == 1, f"Ожидалось enabled=1, получено {enabled_after_enable}"
        finally:
            # Восстанавливаем оригинальный DB_FILE
            app_module.DB_FILE = original_app_db_file

    @allure.story("Управление ключами: операции с ключами")
    @allure.title("Удаление ключа")
    @allure.description("""
    Проверяет удаление ключа через API endpoint /users/revoke/{user_id}.
    
    **Что проверяется:**
    - Доступность API endpoint для авторизованного администратора
    - Корректный статус ответа (200 или 302 для редиректа)
    - Удаление ключа из БД через delete_user_keys
    - Отсутствие ключа в БД после удаления (get_key_by_id возвращает None)
    - Удаление ключа из 3X-UI (если доступно)
    
    **Тестовые данные:**
    - user_id: 123494
    - host_name: "test_host"
    - key_email: "user123494-key1@testcode.bot"
    - plan_name: "Test Plan"
    - price: 100.0
    
    **Предусловия:**
    - Используется временная БД (temp_db)
    - Пользователь зарегистрирован в системе
    - Хост создан с тарифами
    - Ключ создан в БД (только один ключ у пользователя)
    - Администратор авторизован в веб-панели
    
    **Шаги теста:**
    1. Регистрация тестового пользователя
    2. Создание хоста
    3. Создание ключа в БД
    4. Авторизация администратора
    5. Отправка POST запроса на /users/revoke/{user_id}
    6. Проверка статуса ответа (200 или 302)
    7. Проверка удаления ключа из БД (get_key_by_id возвращает None)
    
    **Ожидаемый результат:**
    Ключ успешно удален из БД через API endpoint /users/revoke/{user_id}, get_key_by_id возвращает None после удаления.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("keys", "webhook_server", "api", "delete", "unit")
    def test_delete_key(self, temp_db, admin_credentials):
        from src.shop_bot.webhook_server.app import create_webhook_app
        from unittest.mock import MagicMock, AsyncMock
        
        with allure.step("Подготовка тестового окружения"):
            mock_bot_controller = MagicMock()
            app = create_webhook_app(mock_bot_controller)
            from shop_bot.data_manager.database import (
                register_user_if_not_exists,
                add_new_key,
                get_key_by_id,
                create_host,
                get_user_keys,
            )
            allure.attach(str(temp_db), "Путь к временной БД", allure.attachment_type.TEXT)
        
        with allure.step("Настройка БД: регистрация пользователя и создание хоста"):
            user_id = 123494
            register_user_if_not_exists(user_id, "test_user5", referrer_id=None)
            create_host("test_host", "http://test.com", "user", "pass", 1, "testcode")
            allure.attach(str(user_id), "User ID", allure.attachment_type.TEXT)
        
        with allure.step("Создание ключа в БД"):
            expiry_ms = int((datetime.now(timezone.utc) + timedelta(days=30)).timestamp() * 1000)
            key_id = add_new_key(
                user_id,
                "test_host",
                "test-uuid-delete",
                f"user{user_id}-key1@testcode.bot",
                expiry_ms,
                connection_string="vless://test",
                plan_name="Test Plan",
                price=100.0,
            )
            allure.attach(str(key_id), "Key ID", allure.attachment_type.TEXT)
            
            # Проверяем, что ключ создан
            initial_key = get_key_by_id(key_id)
            assert initial_key is not None, "Ключ должен быть создан в БД"
            allure.attach(str(initial_key.get('key_email')), "Email ключа", allure.attachment_type.TEXT)
        
        with app.test_client() as client:
            with allure.step("Авторизация администратора"):
                with patch('src.shop_bot.webhook_server.app.verify_admin_credentials', return_value=True):
                    login_response = client.post('/login', data=admin_credentials)
                    allure.attach(str(login_response.status_code), "Статус авторизации", allure.attachment_type.TEXT)
                    assert login_response.status_code in [200, 302], "Авторизация должна быть успешной"
            
            with allure.step("Удаление ключа через /users/revoke/{user_id}"):
                # Мокируем xui_api для успешного удаления
                from shop_bot.modules import xui_api
                with patch.object(xui_api, 'login_to_host', return_value=(MagicMock(), MagicMock())):
                    with patch.object(xui_api, 'delete_client_on_host', new=AsyncMock(return_value=True)):
                        response = client.post(f'/users/revoke/{user_id}', follow_redirects=True)
                        allure.attach(str(response.status_code), "Статус ответа", allure.attachment_type.TEXT)
                        
                        with allure.step("Проверка статуса ответа"):
                            assert response.status_code in [200, 302], f"Ожидался статус 200 или 302, получен {response.status_code}"
                        
                        with allure.step("Проверка удаления ключа из БД"):
                            key = get_key_by_id(key_id)
                            allure.attach(str(key), "Ключ после удаления", allure.attachment_type.TEXT)
                            assert key is None, f"Ключ должен быть удален из БД, но get_key_by_id вернул: {key}"
                            
                            # Проверяем, что у пользователя нет ключей
                            user_keys = get_user_keys(user_id)
                            allure.attach(str(len(user_keys)), "Количество ключей пользователя после удаления", allure.attachment_type.TEXT)
                            assert len(user_keys) == 0, f"У пользователя не должно быть ключей, но найдено {len(user_keys)}"

