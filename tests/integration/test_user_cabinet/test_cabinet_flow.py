#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Интеграционные тесты для пользовательского кабинета

Тестирует полный flow работы кабинета
"""

import pytest
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone, timedelta
import allure

# Добавляем путь к проекту
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root / "src"))
sys.path.insert(0, str(project_root / "apps" / "user-cabinet"))


def _load_user_cabinet_app():
    """
    Утилита для безопасной загрузки Flask приложения user-cabinet.
    
    Проверяет все возможные пути к файлу app.py и возвращает объект приложения.
    Если файл не найден, вызывает pytest.skip().
    
    Returns:
        Flask app объект
        
    Raises:
        pytest.skip: Если файл app.py не найден ни по одному из путей
    """
    import importlib.util
    
    # Проверяем разные возможные пути к модулю
    possible_paths = [
        project_root / "apps" / "user-cabinet" / "app.py",  # Локальная разработка
        Path("/app/project/apps/user-cabinet/app.py"),  # Docker окружение
        Path("/app/apps/user-cabinet/app.py"),  # Альтернативный Docker путь
    ]
    
    app_file = None
    for path in possible_paths:
        if path.exists():
            app_file = path
            break
    
    # Если файл не найден, пропускаем тест
    if not app_file:
        pytest.skip(f"App file not found in any of the expected locations: {[str(p) for p in possible_paths]}")
    
    # Используем importlib для загрузки модуля напрямую из файла
    spec = importlib.util.spec_from_file_location("user_cabinet_app", app_file)
    app_module = importlib.util.module_from_spec(spec)
    
    # Добавляем путь к модулям в sys.path для корректного импорта зависимостей
    app_dir = app_file.parent
    if str(app_dir) not in sys.path:
        sys.path.insert(0, str(app_dir))
    if str(project_root / "src") not in sys.path:
        sys.path.insert(0, str(project_root / "src"))
    
    spec.loader.exec_module(app_module)
    
    # Исправляем путь к шаблонам для Flask приложения
    # Когда приложение загружается через importlib, Flask не может автоматически найти templates
    flask_app = app_module.app
    templates_dir = app_dir / "templates"
    if templates_dir.exists():
        flask_app.template_folder = str(templates_dir)
        flask_app.static_folder = str(app_dir / "static")
    
    return flask_app


@pytest.mark.integration
@allure.epic("Интеграционные тесты")
@allure.feature("Личный кабинет")
@allure.label("package", "tests.integration.test_user_cabinet")
class TestCabinetFlow:
    """Интеграционные тесты для пользовательского кабинета"""

    @allure.story("Полный цикл работы личного кабинета")
    @allure.title("Полный flow личного кабинета: токен → авторизация → отображение ключа")
    @allure.description("""
    Интеграционный тест, проверяющий полный цикл работы личного кабинета от создания токена до отображения ключа.
    
    **Что проверяется:**
    - Создание постоянного токена для пользователя и ключа
    - Валидация токена
    - Авторизация по токену через /auth/{token}
    - Отображение главной страницы кабинета
    
    **Тестовые данные:**
    - user_id: 123470
    - username: "test_user"
    - host_name: "test_host"
    - key_email: "user123470-key1@testcode.bot"
    - plan_name: "Test Plan"
    - price: 100.0
    
    **Предусловия:**
    - Используется временная БД (temp_db)
    - Пользователь зарегистрирован
    - Хост создан
    - Ключ создан
    
    **Шаги теста:**
    1. Регистрация пользователя
    2. Создание хоста
    3. Создание ключа
    4. Создание постоянного токена
    5. Валидация токена
    6. Авторизация по токену через /auth/{token}
    7. Отображение главной страницы кабинета
    
    **Ожидаемый результат:**
    Токен успешно создан и валидирован, авторизация по токену работает, главная страница кабинета отображается.
    """)
    @allure.severity(allure.severity_level.CRITICAL)
    @allure.tag("cabinet", "token", "auth", "integration", "critical")
    def test_full_cabinet_flow(self, temp_db):
        from shop_bot.data_manager.database import (
            register_user_if_not_exists,
            add_new_key,
            get_or_create_permanent_token,
            validate_permanent_token,
            create_host,
        )
        app = _load_user_cabinet_app()
        
        # Настройка БД
        user_id = 123470
        register_user_if_not_exists(user_id, "test_user", referrer_id=None)
        create_host("test_host", "http://test.com", "user", "pass", 1, "testcode")
        
        # Создаем ключ
        expiry_ms = int((datetime.now(timezone.utc) + timedelta(days=30)).timestamp() * 1000)
        key_id = add_new_key(
            user_id,
            "test_host",
            "test-uuid-cabinet",
            f"user{user_id}-key1@testcode.bot",
            expiry_ms,
            connection_string="vless://test-cabinet",
            plan_name="Test Plan",
            price=100.0,
        )
        
        # Создаем токен
        from shop_bot.data_manager.database import get_or_create_permanent_token
        token = get_or_create_permanent_token(user_id, key_id)
        assert token is not None
        
        # Валидируем токен
        token_data = validate_permanent_token(token)
        assert token_data is not None
        assert token_data['user_id'] == user_id
        assert token_data['key_id'] == key_id
        
        # Тестируем Flask приложение
        with app.test_client() as client:
            # Тестируем авторизацию по токену
            response = client.get(f'/auth/{token}')
            assert response.status_code in [200, 302]  # Может быть редирект
            
            # Тестируем главную страницу
            with client.session_transaction() as sess:
                sess['token'] = token
                sess['user_id'] = user_id
                sess['key_id'] = key_id
            
            response = client.get('/')
            assert response.status_code == 200

    @allure.story("Личный кабинет с subscription link")
    def test_cabinet_with_subscription_link(self, temp_db):
        """Тест кабинета с subscription link"""
        from shop_bot.data_manager.database import (
            register_user_if_not_exists,
            add_new_key,
            get_or_create_permanent_token,
            update_key_info,
            get_key_by_id,
            create_host,
        )
        app = _load_user_cabinet_app()
        
        # Настройка БД
        user_id = 123471
        register_user_if_not_exists(user_id, "test_user2", referrer_id=None)
        create_host("test_host", "http://test.com", "user", "pass", 1, "testcode")
        
        # Создаем ключ с subscription link
        expiry_ms = int((datetime.now(timezone.utc) + timedelta(days=30)).timestamp() * 1000)
        xui_client_uuid = "test-uuid-sub"
        key_id = add_new_key(
            user_id,
            "test_host",
            xui_client_uuid,
            f"user{user_id}-key1@testcode.bot",
            expiry_ms,
            connection_string="vless://test-sub",
            plan_name="Test Plan",
            price=100.0,
        )
        
        # Получаем ключ для получения текущих значений
        key = get_key_by_id(key_id)
        assert key is not None, "Ключ должен существовать"
        
        # Обновляем ключ с subscription link
        # Используем текущие значения xui_client_uuid и expiry_timestamp_ms из ключа
        subscription_link = "https://example.com/subscription-link"
        update_key_info(
            key_id,
            key['xui_client_uuid'],  # Используем текущий UUID из ключа
            key['expiry_timestamp_ms'],  # Используем текущий expiry из ключа
            subscription_link=subscription_link
        )
        
        # Создаем токен
        from shop_bot.data_manager.database import get_or_create_permanent_token
        token = get_or_create_permanent_token(user_id, key_id)
        
        # Тестируем Flask приложение
        with app.test_client() as client:
            with client.session_transaction() as sess:
                sess['token'] = token
                sess['user_id'] = user_id
                sess['key_id'] = key_id
                sess['subscription_link'] = subscription_link
            
            response = client.get('/')
            assert response.status_code == 200
            # Проверяем, что subscription link присутствует в ответе
            assert b'subscription' in response.data.lower() or subscription_link in response.get_data(as_text=True)

    @allure.story("Личный кабинет без subscription link")
    def test_cabinet_without_subscription_link(self, temp_db):
        """Тест кабинета без subscription link"""
        from shop_bot.data_manager.database import (
            register_user_if_not_exists,
            add_new_key,
            get_or_create_permanent_token,
            create_host,
        )
        app = _load_user_cabinet_app()
        
        # Настройка БД
        user_id = 123472
        register_user_if_not_exists(user_id, "test_user3", referrer_id=None)
        create_host("test_host", "http://test.com", "user", "pass", 1, "testcode")
        
        # Создаем ключ без subscription link
        expiry_ms = int((datetime.now(timezone.utc) + timedelta(days=30)).timestamp() * 1000)
        key_id = add_new_key(
            user_id,
            "test_host",
            "test-uuid-no-sub",
            f"user{user_id}-key1@testcode.bot",
            expiry_ms,
            connection_string="vless://test-no-sub",
            plan_name="Test Plan",
            price=100.0,
        )
        
        # Создаем токен
        from shop_bot.data_manager.database import get_or_create_permanent_token
        token = get_or_create_permanent_token(user_id, key_id)
        
        # Тестируем Flask приложение
        with app.test_client() as client:
            with client.session_transaction() as sess:
                sess['token'] = token
                sess['user_id'] = user_id
                sess['key_id'] = key_id
            
            response = client.get('/')
            assert response.status_code == 200

    @allure.story("Отображение данных ключа в личном кабинете")
    def test_cabinet_key_data_display(self, temp_db):
        """Тест отображения данных ключа в кабинете"""
        from shop_bot.data_manager.database import (
            register_user_if_not_exists,
            add_new_key,
            get_or_create_permanent_token,
            get_key_by_id,
            create_host,
        )
        app = _load_user_cabinet_app()
        
        # Настройка БД
        user_id = 123473
        register_user_if_not_exists(user_id, "test_user4", referrer_id=None)
        create_host("test_host", "http://test.com", "user", "pass", 1, "testcode")
        
        # Создаем ключ
        expiry_ms = int((datetime.now(timezone.utc) + timedelta(days=30)).timestamp() * 1000)
        connection_string = "vless://test-connection-string"
        key_id = add_new_key(
            user_id,
            "test_host",
            "test-uuid-display",
            f"user{user_id}-key1@testcode.bot",
            expiry_ms,
            connection_string=connection_string,
            plan_name="Test Plan",
            price=100.0,
        )
        
        # Проверяем, что key_id не None
        assert key_id is not None, "add_new_key должен вернуть key_id"
        
        # Создаем токен
        from shop_bot.data_manager.database import get_or_create_permanent_token
        token = get_or_create_permanent_token(user_id, key_id)
        
        # Получаем данные ключа
        key = get_key_by_id(key_id)
        assert key is not None
        assert key['connection_string'] == connection_string
        
        # Тестируем Flask приложение
        with app.test_client() as client:
            with client.session_transaction() as sess:
                sess['token'] = token
                sess['user_id'] = user_id
                sess['key_id'] = key_id
            
            response = client.get('/')
            assert response.status_code == 200
            # Страница успешно загружена, connection_string не отображается в шаблоне

    @allure.story("Обработка ошибок в личном кабинете")
    def test_cabinet_error_handling(self, temp_db):
        """Тест обработки ошибок в кабинете"""
        app = _load_user_cabinet_app()
        
        # Тестируем доступ без токена
        with app.test_client() as client:
            response = client.get('/')
            assert response.status_code == 401  # Unauthorized
        
        # Тестируем доступ с невалидным токеном
        with app.test_client() as client:
            response = client.get('/auth/invalid-token-12345')
            assert response.status_code in [403, 404]  # Forbidden или Not Found
        
        # Тестируем health endpoint
        with app.test_client() as client:
            response = client.get('/health')
            assert response.status_code == 200
            assert b'status' in response.data

    @allure.story("Проверка доступности валидных ссылок личного кабинета")
    @allure.title("Проверка доступности валидных ссылок личного кабинета")
    @allure.description("""
    Проверяет полный flow работы валидных ссылок на личный кабинет: от создания пользователя и ключа до успешной авторизации.
    
    **Что проверяется:**
    - Создание полного сценария: пользователь → ключ → токен
    - Доступность ссылки `/auth/{token}` без ошибки 403
    - Успешная авторизация после перехода по ссылке
    - Доступ к главной странице после авторизации
    - Отсутствие ошибок 403 на всех этапах
    
    **Тестовые данные:**
    - user_id: 123480 (создается в тесте)
    - host_name: 'test_host' (создается в тесте)
    - key_id: создается через add_new_key
    - token: генерируется через get_or_create_permanent_token
    
    **Шаги теста:**
    1. **Создание полного сценария: пользователь → ключ → токен**
       - Метод: register_user_if_not_exists(), add_new_key(), get_or_create_permanent_token()
       - Параметры: user_id, host_name, expiry_ms
       - Ожидаемый результат: пользователь, ключ и токен успешно созданы
       - Проверка: token is not None
    
    2. **Проверка доступности ссылки /auth/{token}**
       - Метод: client.get(f'/auth/{token}')
       - Параметры: token
       - Ожидаемый результат: успешный ответ (200 или 302)
       - Проверка: response.status_code != 403
       - Проверка: response.status_code in [200, 302]
    
    3. **Проверка доступа к главной странице после авторизации**
       - Метод: client.get('/')
       - Параметры: сессия с токеном
       - Ожидаемый результат: успешный доступ к главной странице
       - Проверка: response.status_code == 200
    
    4. **Проверка отсутствия ошибок 403 на всех этапах**
       - Метод: проверка всех HTTP-ответов
       - Параметры: все response.status_code
       - Ожидаемый результат: ни один ответ не имеет статус 403
       - Проверка: все статусы != 403
    
    **Предусловия:**
    - Используется временная БД (temp_db)
    - Хост создан в БД через create_host
    
    **Ожидаемый результат:**
    Полный flow работы валидных ссылок должен работать без ошибок 403.
    Пользователь должен успешно авторизоваться через ссылку `/auth/{token}`
    и получить доступ к главной странице личного кабинета.
    """)
    @allure.severity(allure.severity_level.CRITICAL)
    @allure.tag("cabinet", "links", "accessibility", "integration", "critical")
    def test_valid_cabinet_link_accessible(self, temp_db):
        """Тест проверки доступности валидных ссылок личного кабинета"""
        from shop_bot.data_manager.database import (
            register_user_if_not_exists,
            add_new_key,
            get_or_create_permanent_token,
            validate_permanent_token,
            create_host,
        )
        app = _load_user_cabinet_app()
        
        with allure.step("Создание полного сценария: пользователь → ключ → токен"):
            user_id = 123480
            register_user_if_not_exists(user_id, "test_user_link", referrer_id=None)
            create_host("test_host", "http://test.com", "user", "pass", 1, "testcode")
            
            expiry_ms = int((datetime.now(timezone.utc) + timedelta(days=30)).timestamp() * 1000)
            key_id = add_new_key(
                user_id,
                "test_host",
                "test-uuid-link",
                f"user{user_id}-key1@testcode.bot",
                expiry_ms,
                connection_string="vless://test-link",
                plan_name="Test Plan",
                price=100.0,
            )
            
            token = get_or_create_permanent_token(user_id, key_id)
            assert token is not None, "Токен должен быть создан"
            allure.attach(token, "Токен", allure.attachment_type.TEXT)
            allure.attach(str(user_id), "User ID", allure.attachment_type.TEXT)
            allure.attach(str(key_id), "Key ID", allure.attachment_type.TEXT)
        
        with allure.step("Проверка доступности ссылки /auth/{token}"):
            with app.test_client() as client:
                response = client.get(f'/auth/{token}', follow_redirects=False)
                allure.attach(str(response.status_code), "Статус код /auth/{token}", allure.attachment_type.TEXT)
                
                assert response.status_code != 403, \
                    f"Валидная ссылка не должна возвращать 403, получен статус {response.status_code}"
                assert response.status_code in [200, 302], \
                    f"Ожидался статус 200 или 302, получен {response.status_code}"
        
        with allure.step("Проверка доступа к главной странице после авторизации"):
            with app.test_client() as client:
                with client.session_transaction() as sess:
                    sess['token'] = token
                    sess['user_id'] = user_id
                    sess['key_id'] = key_id
                
                response = client.get('/')
                allure.attach(str(response.status_code), "Статус код главной страницы", allure.attachment_type.TEXT)
                
                assert response.status_code == 200, \
                    f"Главная страница должна быть доступна, получен статус {response.status_code}"
                assert response.status_code != 403, \
                    "Главная страница не должна возвращать 403"
        
        with allure.step("Проверка отсутствия ошибок 403 на всех этапах"):
            # Все проверки уже выполнены выше, но явно подтверждаем
            assert True, "Все этапы прошли без ошибки 403"

    @allure.story("Проверка множественных валидных ссылок личного кабинета")
    @allure.title("Проверка множественных валидных ссылок")
    @allure.description("""
    Проверяет, что множественные валидные ссылки для одного пользователя работают корректно и не возвращают ошибку 403.
    
    **Что проверяется:**
    - Создание нескольких ключей для одного пользователя
    - Генерация токенов для каждого ключа
    - Проверка, что все ссылки работают и не возвращают 403
    - Проверка уникальности токенов для разных ключей
    
    **Тестовые данные:**
    - user_id: 123490 (создается в тесте)
    - host_name: 'test_host' (создается в тесте)
    - key_ids: создаются через add_new_key (3 ключа)
    - tokens: генерируются через get_or_create_permanent_token для каждого ключа
    
    **Шаги теста:**
    1. **Создание нескольких ключей для одного пользователя**
       - Метод: add_new_key() в цикле
       - Параметры: user_id, host_name, уникальные email для каждого ключа
       - Ожидаемый результат: создано 3 ключа
       - Проверка: len(key_ids) == 3
    
    2. **Генерация токенов для каждого ключа**
       - Метод: get_or_create_permanent_token() для каждого key_id
       - Параметры: user_id, key_id
       - Ожидаемый результат: создано 3 уникальных токена
       - Проверка: len(tokens) == 3
       - Проверка: все токены уникальны
    
    3. **Проверка, что все ссылки работают и не возвращают 403**
       - Метод: client.get(f'/auth/{token}') для каждого токена
       - Параметры: каждый токен из списка
       - Ожидаемый результат: все ссылки возвращают успешный статус
       - Проверка: все response.status_code != 403
       - Проверка: все response.status_code in [200, 302]
    
    **Предусловия:**
    - Используется временная БД (temp_db)
    - Хост создан в БД через create_host
    
    **Ожидаемый результат:**
    Все множественные валидные ссылки должны работать корректно.
    Каждая ссылка должна успешно авторизовать пользователя без ошибки 403.
    Токены должны быть уникальными для каждого ключа.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("cabinet", "links", "multiple", "integration", "normal")
    def test_multiple_valid_links_not_broken(self, temp_db):
        """Тест проверки множественных валидных ссылок"""
        from shop_bot.data_manager.database import (
            register_user_if_not_exists,
            add_new_key,
            get_or_create_permanent_token,
            create_host,
        )
        app = _load_user_cabinet_app()
        
        with allure.step("Создание нескольких ключей для одного пользователя"):
            user_id = 123490
            register_user_if_not_exists(user_id, "test_user_multiple", referrer_id=None)
            create_host("test_host", "http://test.com", "user", "pass", 1, "testcode")
            
            key_ids = []
            expiry_ms = int((datetime.now(timezone.utc) + timedelta(days=30)).timestamp() * 1000)
            
            for i in range(3):
                key_id = add_new_key(
                    user_id,
                    "test_host",
                    f"test-uuid-multiple-{i}",
                    f"user{user_id}-key{i+1}@testcode.bot",
                    expiry_ms,
                    connection_string=f"vless://test-multiple-{i}",
                    plan_name=f"Test Plan {i+1}",
                    price=100.0 + i * 10,
                )
                key_ids.append(key_id)
            
            assert len(key_ids) == 3, f"Должно быть создано 3 ключа, создано {len(key_ids)}"
            allure.attach(str(len(key_ids)), "Количество созданных ключей", allure.attachment_type.TEXT)
        
        with allure.step("Генерация токенов для каждого ключа"):
            tokens = []
            for key_id in key_ids:
                token = get_or_create_permanent_token(user_id, key_id)
                assert token is not None, f"Токен должен быть создан для key_id {key_id}"
                tokens.append(token)
            
            assert len(tokens) == 3, f"Должно быть создано 3 токена, создано {len(tokens)}"
            assert len(set(tokens)) == 3, "Все токены должны быть уникальными"
            allure.attach(str(len(tokens)), "Количество созданных токенов", allure.attachment_type.TEXT)
        
        with allure.step("Проверка, что все ссылки работают и не возвращают 403"):
            for i, token in enumerate(tokens):
                with app.test_client() as client:
                    response = client.get(f'/auth/{token}', follow_redirects=False)
                    allure.attach(
                        f"Токен {i+1}: статус {response.status_code}",
                        f"Результат проверки ссылки {i+1}",
                        allure.attachment_type.TEXT
                    )
                    
                    assert response.status_code != 403, \
                        f"Ссылка {i+1} не должна возвращать 403, получен статус {response.status_code}"
                    assert response.status_code in [200, 302], \
                        f"Ссылка {i+1} должна возвращать 200 или 302, получен {response.status_code}"

    @pytest.mark.integration
    @allure.epic("Личный кабинет")
    @allure.feature("Режим предоставления: Личный кабинет")
    @allure.story("Полный цикл покупки и работы кабинета")
    @allure.title("Тест полного цикла работы личного кабинета с режимом предоставления 'cabinet'")
    @allure.description("""
    Интеграционный тест, проверяющий полный цикл работы личного кабинета при режиме предоставления "Личный кабинет".
    
    **Что проверяется:**
    - Создание тарифного плана с режимом предоставления 'cabinet'
    - Симуляция покупки тарифа
    - Генерация ссылки на личный кабинет
    - Работа всех трех вкладок: Инструкции, Подписка, Проверка IP
    - Корректная работа API /api/ip-info
    
    **Тестовые данные:**
    - user_id: 123500 (создается в тесте)
    - host_name: 'test_host_cabinet' (создается в тесте)
    - plan_name: 'Test Cabinet Plan'
    - key_provision_mode: 'cabinet'
    
    **Шаги теста:**
    1. Создание тарифного плана с режимом 'cabinet'
    2. Симуляция покупки тарифа
    3. Проверка ссылки на личный кабинет
    4. Проверка вкладки 'Инструкции'
    5. Проверка вкладки 'Подписка'
    6. Проверка вкладки 'Проверка IP'
    7. Тестирование API /api/ip-info
    """)
    @allure.severity(allure.severity_level.CRITICAL)
    @allure.tag("cabinet", "provision_mode", "integration", "critical", "full_flow")
    def test_cabinet_provision_mode_flow(self, temp_db):
        """Тест полного цикла работы личного кабинета с режимом предоставления 'cabinet'"""
        from shop_bot.data_manager.database import (
            register_user_if_not_exists,
            add_new_key,
            get_or_create_permanent_token,
            get_key_by_id,
            create_host,
            create_plan,
            get_plans_for_host,
        )
        from shop_bot.config import get_user_cabinet_domain
        from unittest.mock import patch, MagicMock
        import json
        
        with allure.step("Создание тарифного плана с режимом 'cabinet'"):
            # Настройка БД
            user_id = 123500
            host_name = "test_host_cabinet"
            plan_name = "Test Cabinet Plan"
            
            register_user_if_not_exists(user_id, "test_user_cabinet", referrer_id=None)
            create_host(host_name, "http://test.com", "user", "pass", 1, "testcode")
            
            # Создаем тарифный план с режимом предоставления 'cabinet'
            create_plan(
                host_name=host_name,
                plan_name=plan_name,
                months=1,
                price=200.0,
                days=0,
                traffic_gb=0.0,
                hours=0,
                key_provision_mode='cabinet',
                display_mode='all',
                display_mode_groups=None
            )
            
            # Получаем созданный план для проверки
            plans = get_plans_for_host(host_name)
            assert len(plans) > 0, "План должен быть создан"
            plan = plans[0]
            assert plan['key_provision_mode'] == 'cabinet', f"Режим предоставления должен быть 'cabinet', получен '{plan.get('key_provision_mode')}'"
            assert plan['plan_name'] == plan_name, f"Название плана должно быть '{plan_name}'"
            
            allure.attach(
                json.dumps({
                    'plan_id': plan.get('plan_id'),
                    'plan_name': plan.get('plan_name'),
                    'key_provision_mode': plan.get('key_provision_mode'),
                    'price': plan.get('price')
                }, indent=2, ensure_ascii=False),
                "Созданный тарифный план",
                allure.attachment_type.JSON
            )
        
        with allure.step("Симуляция покупки тарифа"):
            # Создаем ключ (симуляция покупки)
            expiry_ms = int((datetime.now(timezone.utc) + timedelta(days=30)).timestamp() * 1000)
            key_id = add_new_key(
                user_id,
                host_name,
                "test-uuid-cabinet",
                f"user{user_id}-key1@testcode.bot",
                expiry_ms,
                connection_string="vless://test-connection-string-cabinet",
                plan_name=plan_name,
                price=200.0,
            )
            
            assert key_id is not None, "add_new_key должен вернуть key_id"
            
            # Создаем токен для личного кабинета
            token = get_or_create_permanent_token(user_id, key_id)
            assert token is not None, "Токен должен быть создан"
            
            # Получаем данные ключа
            key = get_key_by_id(key_id)
            assert key is not None, "Ключ должен быть найден в БД"
            
            allure.attach(
                json.dumps({
                    'key_id': key_id,
                    'user_id': user_id,
                    'token_preview': token[:20] + '...' if len(token) > 20 else token
                }, indent=2, ensure_ascii=False),
                "Созданный ключ и токен",
                allure.attachment_type.JSON
            )
        
        with allure.step("Проверка ссылки на личный кабинет"):
            # Получаем домен личного кабинета
            cabinet_domain = get_user_cabinet_domain()
            if not cabinet_domain:
                # Если домен не настроен, используем тестовый
                cabinet_domain = "http://localhost:50003"
            
            cabinet_url = f"{cabinet_domain}/auth/{token}"
            assert cabinet_url is not None, "URL личного кабинета должен быть сформирован"
            assert token in cabinet_url, "URL должен содержать токен"
            
            allure.attach(cabinet_url, "URL личного кабинета", allure.attachment_type.TEXT)
        
        with allure.step("Тестирование веб-интерфейса"):
            app = _load_user_cabinet_app()
            
            # Тестируем переход по ссылке /auth/{token}
            with app.test_client() as client:
                response = client.get(f'/auth/{token}', follow_redirects=True)
                assert response.status_code == 200, f"Страница должна загружаться успешно, получен статус {response.status_code}"
                
                response_text = response.get_data(as_text=True)
                
                allure.attach(
                    response_text[:1000] + "..." if len(response_text) > 1000 else response_text,
                    "HTML ответ главной страницы (первые 1000 символов)",
                    allure.attachment_type.HTML
                )
        
        with allure.step("Проверка вкладки 'Инструкции'"):
            with app.test_client() as client:
                with client.session_transaction() as sess:
                    sess['token'] = token
                    sess['user_id'] = user_id
                    sess['key_id'] = key_id
                
                response = client.get('/')
                assert response.status_code == 200
                
                response_text = response.get_data(as_text=True)
                
                # Проверяем наличие вкладки "Инструкции"
                assert 'step-tab-setup' in response_text, "Вкладка 'Инструкции' должна присутствовать"
                assert 'step-panel-setup' in response_text, "Панель 'Инструкции' должна присутствовать"
                assert 'is-active' in response_text or 'step-tab-setup' in response_text, "Вкладка 'Инструкции' должна быть активна"
                assert 'setup-iframe' in response_text, "Iframe для инструкций должен присутствовать"
                assert 'Настройка VPN' in response_text or 'настройка vpn' in response_text.lower(), "Текст 'Настройка VPN' должен присутствовать"
                
                allure.attach(
                    "Вкладка 'Инструкции' найдена и корректно отображается",
                    "Результат проверки вкладки 'Инструкции'",
                    allure.attachment_type.TEXT
                )
        
        with allure.step("Проверка вкладки 'Подписка'"):
            with app.test_client() as client:
                with client.session_transaction() as sess:
                    sess['token'] = token
                    sess['user_id'] = user_id
                    sess['key_id'] = key_id
                
                response = client.get('/')
                assert response.status_code == 200
                
                response_text = response.get_data(as_text=True)
                
                # Проверяем наличие вкладки "Подписка"
                assert 'step-tab-subscription' in response_text, "Вкладка 'Подписка' должна присутствовать"
                assert 'step-panel-subscription' in response_text, "Панель 'Подписка' должна присутствовать"
                assert 'Подключение' in response_text or 'подключение' in response_text.lower(), "Текст 'Подключение' должен присутствовать"
                
                # Проверяем наличие iframe для подписки (может быть условным)
                # Если subscription_link есть, должен быть iframe
                if key.get('subscription_link'):
                    assert 'subscription-iframe' in response_text, "Iframe для подписки должен присутствовать при наличии subscription_link"
                
                allure.attach(
                    "Вкладка 'Подписка' найдена и корректно отображается",
                    "Результат проверки вкладки 'Подписка'",
                    allure.attachment_type.TEXT
                )
        
        with allure.step("Проверка вкладки 'Проверка IP'"):
            with app.test_client() as client:
                with client.session_transaction() as sess:
                    sess['token'] = token
                    sess['user_id'] = user_id
                    sess['key_id'] = key_id
                
                response = client.get('/')
                assert response.status_code == 200
                
                response_text = response.get_data(as_text=True)
                
                # Проверяем наличие вкладки "Проверка IP"
                assert 'step-tab-ip-check' in response_text, "Вкладка 'Проверка IP' должна присутствовать"
                assert 'step-panel-ip-check' in response_text, "Панель 'Проверка IP' должна присутствовать"
                assert 'Проверка IP' in response_text or 'проверка ip' in response_text.lower(), "Текст 'Проверка IP' должен присутствовать"
                assert 'ip-refresh' in response_text or 'ip-refresh' in response_text, "Кнопка 'Обновить IP' должна присутствовать"
                assert 'checkIP' in response_text or 'checkip' in response_text.lower(), "Функция checkIP должна присутствовать"
                
                allure.attach(
                    "Вкладка 'Проверка IP' найдена и корректно отображается",
                    "Результат проверки вкладки 'Проверка IP'",
                    allure.attachment_type.TEXT
                )
        
        with allure.step("Тестирование API /api/ip-info"):
            # Мокируем внешние API для проверки IP
            # Находим модуль app и патчим requests.get в нем
            import sys
            import importlib
            
            # Ищем модуль app в sys.modules
            app_module = None
            for module_name, module in sys.modules.items():
                if hasattr(module, 'app') and hasattr(module, 'requests') and module.app == app:
                    app_module = module
                    break
            
            # Если модуль не найден, пытаемся импортировать напрямую
            if not app_module:
                try:
                    # Пробуем разные возможные имена модуля
                    possible_names = ['app', 'user_cabinet_app', 'apps.user_cabinet.app']
                    for name in possible_names:
                        if name in sys.modules:
                            app_module = sys.modules[name]
                            break
                except:
                    pass
            
            # Патчим requests.get
            if app_module and hasattr(app_module, 'requests'):
                patch_target = f"{app_module.__name__}.requests.get"
            else:
                # Fallback: патчим глобально
                patch_target = 'requests.get'
            
            with patch(patch_target) as mock_get:
                # Настраиваем мок для успешного ответа от первого провайдера (ipapi)
                mock_response = MagicMock()
                mock_response.status_code = 200
                mock_response.json.return_value = {
                    "ip": "192.168.1.1",
                    "country_name": "Russia",
                    "city": "Moscow",
                    "org": "Test ISP"
                }
                mock_get.return_value = mock_response
                
                with app.test_client() as client:
                    response = client.get('/api/ip-info')
                    assert response.status_code == 200, f"API должен возвращать 200, получен {response.status_code}"
                    
                    data = json.loads(response.get_data(as_text=True))
                    assert 'status' in data, "Ответ должен содержать поле 'status'"
                    assert data['status'] == 'ok', f"Статус должен быть 'ok', получен '{data.get('status')}'"
                    assert 'data' in data, "Ответ должен содержать поле 'data'"
                    
                    ip_data = data['data']
                    assert 'ip' in ip_data, "Данные должны содержать поле 'ip'"
                    assert 'country' in ip_data, "Данные должны содержать поле 'country'"
                    assert 'city' in ip_data, "Данные должны содержать поле 'city'"
                    assert 'provider' in ip_data, "Данные должны содержать поле 'provider'"
                    
                    allure.attach(
                        json.dumps(data, indent=2, ensure_ascii=False),
                        "Ответ API /api/ip-info",
                        allure.attachment_type.JSON
                    )
                    
                    allure.attach(
                        f"IP: {ip_data.get('ip')}\nCountry: {ip_data.get('country')}\nCity: {ip_data.get('city')}\nProvider: {ip_data.get('provider')}",
                        "Данные IP из API",
                        allure.attachment_type.TEXT
                    )

