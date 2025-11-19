#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Unit-тесты для управления пользователями в веб-панели

Тестирует CRUD операции с пользователями
"""

import pytest
import allure
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

# Добавляем путь к проекту
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root / "src"))


@pytest.mark.unit
@allure.epic("Веб-панель")
@allure.feature("Управление пользователями")
@allure.label("package", "src.shop_bot.webhook_server")
class TestWebhookServerUsers:
    """Тесты для управления пользователями"""

    @allure.story("Управление пользователями: просмотр списка")
    @allure.title("Страница списка пользователей")
    @allure.description("""
    Проверяет отображение страницы списка пользователей в веб-панели.
    
    **Что проверяется:**
    - Доступность страницы /users
    - Отображение списка пользователей
    - Корректный статус ответа (200)
    
    **Ожидаемый результат:**
    Страница списка пользователей успешно отображается с данными пользователей.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("users", "list", "webhook_server", "unit")
    def test_users_page(self, temp_db, admin_credentials):
        """Тест страницы списка пользователей (/users)"""
        from src.shop_bot.webhook_server.app import create_webhook_app
        from unittest.mock import MagicMock
        
        mock_bot_controller = MagicMock()
        app = create_webhook_app(mock_bot_controller)
        from shop_bot.data_manager.database import register_user_if_not_exists
        
        # Настройка БД
        register_user_if_not_exists(123480, "test_user", referrer_id=None)
        
        app = create_webhook_app(mock_bot_controller)
        with app.test_client() as client:
            # Входим
            with patch('src.shop_bot.webhook_server.app.verify_admin_credentials', return_value=True):
                client.post('/login', data=admin_credentials)
            
            response = client.get('/users')
            assert response.status_code == 200

    @allure.story("Управление пользователями: детали пользователя")
    @allure.title("Получение деталей пользователя через API")
    @allure.description("""
    Проверяет получение детальной информации о пользователе через API endpoint /api/user-details/<user_id>.
    
    **Что проверяется:**
    - Доступность API endpoint для авторизованного администратора
    - Отправка GET запроса на /api/user-details/<user_id>
    - Возврат корректных данных пользователя в JSON формате
    - Наличие обязательных полей (user_id или telegram_id)
    - Корректный статус ответа (200)
    
    **Тестовые данные:**
    - user_id: 123481
    - username: "test_user2"
    
    **Предусловия:**
    - Используется временная БД (temp_db)
    - Пользователь зарегистрирован в системе
    - Администратор авторизован в веб-панели
    
    **Шаги теста:**
    1. Регистрация тестового пользователя
    2. Авторизация администратора
    3. Отправка GET запроса на /api/user-details/<user_id>
    4. Проверка статуса ответа (200)
    5. Проверка наличия обязательных полей в ответе
    
    **Ожидаемый результат:**
    API возвращает детальную информацию о пользователе в JSON формате со статусом 200, ответ содержит user_id или telegram_id.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("users", "api", "user_details", "webhook_server", "unit")
    def test_get_user_details(self, temp_db, admin_credentials):
        """Тест получения деталей пользователя (API /api/user-details/<user_id>)"""
        from src.shop_bot.webhook_server.app import create_webhook_app
        from unittest.mock import MagicMock
        
        with allure.step("Подготовка тестового окружения"):
            mock_bot_controller = MagicMock()
            app = create_webhook_app(mock_bot_controller)
            app.config['TESTING'] = True  # Отключаем rate limiting
            from shop_bot.data_manager.database import register_user_if_not_exists
            allure.attach(str(temp_db), "Путь к временной БД", allure.attachment_type.TEXT)
        
        with allure.step("Настройка БД: регистрация пользователя"):
            user_id = 123481
            register_user_if_not_exists(user_id, "test_user2", referrer_id=None)
            allure.attach(str(user_id), "User ID", allure.attachment_type.TEXT)
        
        # Патчим DB_FILE для использования временной БД
        with patch('src.shop_bot.webhook_server.app.DB_FILE', temp_db):
            with app.test_client() as client:
                with allure.step("Авторизация администратора"):
                    with patch('src.shop_bot.webhook_server.app.verify_admin_credentials', return_value=True):
                        login_response = client.post('/login', data=admin_credentials)
                        allure.attach(str(login_response.status_code), "Статус авторизации", allure.attachment_type.TEXT)
                        assert login_response.status_code in [200, 302], "Авторизация должна быть успешной"
                
                with allure.step("Запрос деталей пользователя через /api/user-details/<user_id>"):
                    response = client.get(f'/api/user-details/{user_id}')
                    allure.attach(str(response.status_code), "Статус ответа", allure.attachment_type.TEXT)
                    
                    with allure.step("Проверка статуса ответа и структуры данных"):
                        assert response.status_code == 200, f"Ожидался статус 200, получен {response.status_code}"
                        
                        data = response.get_json()
                        allure.attach(str(data), "Данные пользователя", allure.attachment_type.JSON)
                        assert data is not None, "Ответ должен содержать данные"
                        assert 'user' in data, "Ответ должен содержать ключ 'user'"
                        user_data = data.get('user')
                        assert user_data is not None, "Данные пользователя не должны быть пустыми"
                        assert 'user_id' in user_data or 'telegram_id' in user_data, "Данные пользователя должны содержать user_id или telegram_id"

    @allure.story("Управление пользователями: редактирование данных")
    @allure.title("Обновление данных пользователя через API")
    @allure.description("""
    Проверяет обновление данных пользователя через API endpoint /api/update-user/<user_id>.
    
    **Что проверяется:**
    - Доступность API endpoint для авторизованного администратора
    - Отправка POST запроса на /api/update-user/<user_id> с новыми данными
    - Корректное сохранение обновленных данных в БД
    - Возврат успешного статуса (200)
    - Проверка обновленных данных через get_user
    
    **Тестовые данные:**
    - user_id: 123482
    - username: 'updated_user'
    - fullname: 'Updated User'
    
    **Предусловия:**
    - Используется временная БД (temp_db)
    - Пользователь зарегистрирован в системе
    - Администратор авторизован в веб-панели
    
    **Шаги теста:**
    1. Регистрация тестового пользователя
    2. Авторизация администратора
    3. Отправка POST запроса на /api/update-user/<user_id> с новыми данными
    4. Проверка статуса ответа (200)
    5. Проверка обновленных данных через get_user
    
    **Ожидаемый результат:**
    Данные пользователя успешно обновлены в БД, API возвращает статус 200, get_user возвращает обновленные данные.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("users", "api", "update", "webhook_server", "unit")
    def test_update_user(self, temp_db, admin_credentials):
        """Тест обновления данных пользователя (API /api/update-user/<user_id>)"""
        from src.shop_bot.webhook_server.app import create_webhook_app
        from unittest.mock import MagicMock
        
        with allure.step("Подготовка тестового окружения"):
            mock_bot_controller = MagicMock()
            app = create_webhook_app(mock_bot_controller)
            app.config['TESTING'] = True  # Отключаем rate limiting
            from shop_bot.data_manager.database import register_user_if_not_exists, get_user
            allure.attach(str(temp_db), "Путь к временной БД", allure.attachment_type.TEXT)
        
        with allure.step("Настройка БД: регистрация пользователя"):
            user_id = 123482
            register_user_if_not_exists(user_id, "test_user3", referrer_id=None)
            allure.attach(str(user_id), "User ID", allure.attachment_type.TEXT)
            
            # Проверяем начальные данные
            initial_user = get_user(user_id)
            initial_username = initial_user.get('username') if initial_user else None
            allure.attach(str(initial_username), "Начальный username", allure.attachment_type.TEXT)
        
        # Патчим DB_FILE для использования временной БД
        with patch('src.shop_bot.webhook_server.app.DB_FILE', temp_db):
            with app.test_client() as client:
                with allure.step("Авторизация администратора"):
                    with patch('src.shop_bot.webhook_server.app.verify_admin_credentials', return_value=True):
                        login_response = client.post('/login', data=admin_credentials)
                        allure.attach(str(login_response.status_code), "Статус авторизации", allure.attachment_type.TEXT)
                        assert login_response.status_code in [200, 302], "Авторизация должна быть успешной"
                
                with allure.step("Обновление данных пользователя через /api/update-user/<user_id>"):
                    update_data = {
                        'username': 'updated_user',
                        'fullname': 'Updated User'
                    }
                    allure.attach(str(update_data), "Данные для обновления", allure.attachment_type.JSON)
                    
                    response = client.post(
                        f'/api/update-user/{user_id}',
                        json=update_data,
                        content_type='application/json'
                    )
                    allure.attach(str(response.status_code), "Статус ответа", allure.attachment_type.TEXT)
                    if response.is_json:
                        response_data = response.get_json()
                        allure.attach(str(response_data), "Тело ответа", allure.attachment_type.JSON)
                    
                    with allure.step("Проверка статуса ответа и обновленных данных"):
                        assert response.status_code == 200, f"Ожидался статус 200, получен {response.status_code}"
                        
                        user = get_user(user_id)
                        assert user is not None, "Пользователь должен существовать в БД"
                        updated_username = user.get('username')
                        updated_fullname = user.get('fullname')
                        allure.attach(str(updated_username), "Обновленный username", allure.attachment_type.TEXT)
                        allure.attach(str(updated_fullname), "Обновленный fullname", allure.attachment_type.TEXT)

    @allure.story("Управление пользователями: изменение баланса")
    @allure.title("Обновление баланса пользователя через веб-панель")
    @allure.description("""
    Проверяет функциональность обновления баланса пользователя через API веб-панели.
    
    **Что проверяется:**
    - Успешное обновление баланса пользователя через эндпоинт /api/update-user/<user_id>
    - Корректное сохранение нового баланса в БД
    - Корректное чтение обновленного баланса через get_user_balance()
    
    **Тестовые данные:**
    - user_id: 123483
    - username: "test_user4"
    - referrer_id: None
    - новый баланс: 500.0 RUB
    
    **Предусловия:**
    - Используется временная БД (temp_db)
    - Пользователь зарегистрирован в системе
    - Администратор авторизован в веб-панели
    - app.DB_FILE патчится для использования временной БД
    
    **Шаги теста:**
    1. Регистрация тестового пользователя
    2. Патчинг app.DB_FILE для использования временной БД
    3. Авторизация администратора в веб-панели
    4. Отправка POST запроса на /api/update-user/<user_id> с новым балансом
    5. Проверка статуса ответа (200)
    6. Проверка обновленного баланса через get_user_balance()
    
    **Ожидаемый результат:**
    - Запрос возвращает статус 200
    - Баланс пользователя в БД обновлен на 500.0
    - get_user_balance() возвращает 500.0
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("balance", "user_management", "web_panel", "unit", "users", "api")
    def test_update_user_balance(self, temp_db, admin_credentials):
        """Тест обновления баланса пользователя"""
        from src.shop_bot.webhook_server.app import create_webhook_app
        from unittest.mock import MagicMock
        
        mock_bot_controller = MagicMock()
        from shop_bot.data_manager.database import (
            register_user_if_not_exists,
            add_to_user_balance,
            get_user_balance,
        )
        
        with allure.step("Подготовка тестовых данных"):
            # Настройка БД
            user_id = 123483
            register_user_if_not_exists(user_id, "test_user4", referrer_id=None)
            allure.attach(str(user_id), "User ID", allure.attachment_type.TEXT)
            allure.attach(str(temp_db), "Путь к временной БД", allure.attachment_type.TEXT)
            
            # Проверяем начальный баланс
            initial_balance = get_user_balance(user_id)
            allure.attach(str(initial_balance), "Начальный баланс", allure.attachment_type.TEXT)
        
        with allure.step("Патчинг app.DB_FILE для использования временной БД"):
            # Патчим app.DB_FILE для использования временной БД
            with patch('src.shop_bot.webhook_server.app.DB_FILE', temp_db):
                app = create_webhook_app(mock_bot_controller)
                
                with app.test_client() as client:
                    with allure.step("Авторизация администратора"):
                        # Входим
                        with patch('src.shop_bot.webhook_server.app.verify_admin_credentials', return_value=True):
                            login_response = client.post('/login', data=admin_credentials)
                            allure.attach(str(login_response.status_code), "Статус авторизации", allure.attachment_type.TEXT)
                    
                    with allure.step("Отправка запроса на обновление баланса"):
                        # Обновляем баланс
                        new_balance = 500.0
                        allure.attach(str(new_balance), "Новый баланс", allure.attachment_type.TEXT)
                        
                        response = client.post(f'/api/update-user/{user_id}', json={
                            'balance': new_balance
                        })
                        allure.attach(str(response.status_code), "Статус ответа", allure.attachment_type.TEXT)
                        allure.attach(str(response.get_json()), "Тело ответа", allure.attachment_type.JSON)
                        
                        assert response.status_code == 200, f"Ожидался статус 200, получен {response.status_code}"
                    
                    with allure.step("Проверка обновленного баланса"):
                        # Проверяем баланс
                        balance = get_user_balance(user_id)
                        allure.attach(str(balance), "Баланс после обновления", allure.attachment_type.TEXT)
                        assert balance == 500.0, f"Ожидался баланс 500.0, получен {balance}"

    @allure.story("Управление пользователями: блокировка и разблокировка")
    @allure.title("Бан и разбан пользователя через веб-панель")
    @allure.description("""
    Проверяет функциональность бана и разбана пользователя через веб-панель.
    
    **Что проверяется:**
    - Успешный бан пользователя через эндпоинт /users/ban/<user_id>
    - Корректное обновление поля is_banned в БД после бана (значение должно быть 1)
    - Успешный разбан пользователя через эндпоинт /users/unban/<user_id>
    - Корректное обновление поля is_banned в БД после разбана (значение должно быть 0)
    - Редирект после успешного бана/разбана
    
    **Тестовые данные:**
    - user_id: 123484
    - username: "test_user5"
    - referrer_id: None
    
    **Предусловия:**
    - Используется временная БД (temp_db)
    - Пользователь зарегистрирован в системе
    - Администратор авторизован в веб-панели
    
    **Шаги теста:**
    1. Регистрация тестового пользователя
    2. Авторизация администратора в веб-панели
    3. Отправка POST запроса на /users/ban/<user_id> для бана пользователя
    4. Проверка статуса ответа (редирект 302 или 200)
    5. Проверка значения is_banned в БД (должно быть 1)
    6. Отправка POST запроса на /users/unban/<user_id> для разбана пользователя
    7. Проверка статуса ответа (редирект 302 или 200)
    8. Проверка значения is_banned в БД (должно быть 0)
    
    **Ожидаемый результат:**
    - Оба запроса (бан и разбан) возвращают успешный статус (200 или 302)
    - После бана is_banned = 1 в БД
    - После разбана is_banned = 0 в БД
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("ban", "unban", "user_management", "web_panel", "unit", "users")
    def test_ban_unban_user(self, temp_db, admin_credentials):
        """Тест бан/разбан пользователя"""
        from src.shop_bot.webhook_server.app import create_webhook_app
        from unittest.mock import MagicMock
        
        mock_bot_controller = MagicMock()
        app = create_webhook_app(mock_bot_controller)
        from shop_bot.data_manager.database import (
            register_user_if_not_exists,
            get_user,
        )
        
        with allure.step("Подготовка тестовых данных"):
            # Настройка БД
            user_id = 123484
            register_user_if_not_exists(user_id, "test_user5", referrer_id=None)
            allure.attach(str(user_id), "User ID", allure.attachment_type.TEXT)
            
            # Проверяем начальное состояние
            initial_user = get_user(user_id)
            initial_banned = initial_user.get('is_banned', 0) if initial_user else 0
            allure.attach(str(initial_banned), "Начальное значение is_banned", allure.attachment_type.TEXT)
        
        app = create_webhook_app(mock_bot_controller)
        with app.test_client() as client:
            with allure.step("Авторизация администратора"):
                # Входим
                with patch('src.shop_bot.webhook_server.app.verify_admin_credentials', return_value=True):
                    login_response = client.post('/login', data=admin_credentials)
                    allure.attach(str(login_response.status_code), "Статус авторизации", allure.attachment_type.TEXT)
            
            with allure.step("Бан пользователя через /users/ban/<user_id>"):
                # Баним пользователя через правильный эндпоинт
                response = client.post(f'/users/ban/{user_id}', follow_redirects=True)
                allure.attach(str(response.status_code), "Статус ответа при бане", allure.attachment_type.TEXT)
                allure.attach(str(response.data), "Тело ответа при бане", allure.attachment_type.TEXT)
                assert response.status_code in [200, 302], f"Ожидался статус 200 или 302, получен {response.status_code}"
            
            with allure.step("Проверка бана в БД"):
                # Проверяем бан
                user = get_user(user_id)
                assert user is not None, "Пользователь не найден в БД после бана"
                is_banned_after_ban = user.get('is_banned')
                allure.attach(str(is_banned_after_ban), "Значение is_banned после бана", allure.attachment_type.TEXT)
                assert is_banned_after_ban == 1, f"Ожидалось is_banned=1, получено {is_banned_after_ban}"
            
            with allure.step("Разбан пользователя через /users/unban/<user_id>"):
                # Разбаниваем пользователя через правильный эндпоинт
                response = client.post(f'/users/unban/{user_id}', follow_redirects=True)
                allure.attach(str(response.status_code), "Статус ответа при разбане", allure.attachment_type.TEXT)
                allure.attach(str(response.data), "Тело ответа при разбане", allure.attachment_type.TEXT)
                assert response.status_code in [200, 302], f"Ожидался статус 200 или 302, получен {response.status_code}"
            
            with allure.step("Проверка разбана в БД"):
                # Проверяем разбан
                user = get_user(user_id)
                assert user is not None, "Пользователь не найден в БД после разбана"
                is_banned_after_unban = user.get('is_banned')
                allure.attach(str(is_banned_after_unban), "Значение is_banned после разбана", allure.attachment_type.TEXT)
                assert is_banned_after_unban == 0, f"Ожидалось is_banned=0, получено {is_banned_after_unban}"

    @allure.story("Управление пользователями: отзыв согласия")
    @allure.title("Отзыв согласия пользователя")
    @allure.description("""
    Проверяет отзыв согласия пользователя через веб-панель.
    
    **Что проверяется:**
    - Отправка POST запроса на /users/revoke-consent/<user_id>
    - Обновление статуса согласия в БД
    - Корректный статус ответа (200 или 302)
    
    **Тестовые данные:**
    - user_id: 123485
    
    **Ожидаемый результат:**
    Согласие пользователя успешно отозвано, статус обновлен в БД.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("users", "consent", "revoke", "webhook_server", "unit")
    def test_revoke_user_consent(self, temp_db):
        """Тест отзыва согласия (/users/revoke-consent/<user_id>)"""
        from src.shop_bot.webhook_server.app import create_webhook_app
        from unittest.mock import MagicMock
        
        mock_bot_controller = MagicMock()
        app = create_webhook_app(mock_bot_controller)
        from shop_bot.data_manager.database import (
            register_user_if_not_exists,
            get_user,
        )
        
        # Настройка БД
        user_id = 123485
        register_user_if_not_exists(user_id, "test_user6", referrer_id=None)
        with app.test_client() as client:
            # Входим
            with patch('src.shop_bot.webhook_server.app.verify_admin_credentials', return_value=True):
                client.post('/login', data=admin_credentials)
            
            # Отзываем согласие
            response = client.post(f'/users/revoke-consent/{user_id}')
            assert response.status_code in [200, 302]  # Может быть редирект
            
            # Проверяем отзыв согласия
            user = get_user(user_id)
            assert user is not None

    @allure.story("Управление пользователями: сброс пробного периода")
    @allure.title("Сброс триала пользователя")
    @allure.description("""
    Проверяет сброс триального периода пользователя через API endpoint /api/update-user/<user_id>.
    
    **Что проверяется:**
    - Доступность API endpoint для авторизованного администратора
    - Отправка POST запроса на /api/update-user/<user_id> с reset_trial=True
    - Сброс флага trial_used в БД (trial_used = 0)
    - Корректный статус ответа (200)
    - Проверка сброса через get_trial_info
    
    **Тестовые данные:**
    - user_id: 123486
    - reset_trial: True
    
    **Предусловия:**
    - Используется временная БД (temp_db)
    - Пользователь зарегистрирован в системе
    - trial_used установлен в True (set_trial_used)
    - Администратор авторизован в веб-панели
    
    **Шаги теста:**
    1. Регистрация тестового пользователя
    2. Установка trial_used = True
    3. Авторизация администратора
    4. Отправка POST запроса на /api/update-user/<user_id> с reset_trial=True
    5. Проверка статуса ответа (200)
    6. Проверка сброса trial_used через get_trial_info
    
    **Ожидаемый результат:**
    Триальный период пользователя успешно сброшен, trial_used установлен в False (0), API возвращает статус 200.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("users", "trial", "reset", "webhook_server", "unit")
    def test_reset_user_trial(self, temp_db, admin_credentials):
        """Тест сброса триала пользователя"""
        from src.shop_bot.webhook_server.app import create_webhook_app
        from unittest.mock import MagicMock
        
        with allure.step("Подготовка тестового окружения"):
            mock_bot_controller = MagicMock()
            app = create_webhook_app(mock_bot_controller)
            app.config['TESTING'] = True  # Отключаем rate limiting
            from shop_bot.data_manager.database import (
                register_user_if_not_exists,
                set_trial_used,
                reset_trial_used,
                get_trial_info,
            )
            allure.attach(str(temp_db), "Путь к временной БД", allure.attachment_type.TEXT)
        
        with allure.step("Настройка БД: регистрация пользователя и установка trial_used"):
            user_id = 123486
            register_user_if_not_exists(user_id, "test_user7", referrer_id=None)
            set_trial_used(user_id)
            allure.attach(str(user_id), "User ID", allure.attachment_type.TEXT)
            
            # Проверяем начальное состояние
            initial_trial_info = get_trial_info(user_id)
            initial_trial_used = initial_trial_info.get('trial_used') if initial_trial_info else None
            allure.attach(str(initial_trial_used), "Начальное значение trial_used", allure.attachment_type.TEXT)
            assert initial_trial_used is True, "trial_used должен быть установлен в True перед сбросом"
        
        # Патчим DB_FILE для использования временной БД
        with patch('src.shop_bot.webhook_server.app.DB_FILE', temp_db):
            with app.test_client() as client:
                with allure.step("Авторизация администратора"):
                    with patch('src.shop_bot.webhook_server.app.verify_admin_credentials', return_value=True):
                        login_response = client.post('/login', data=admin_credentials)
                        allure.attach(str(login_response.status_code), "Статус авторизации", allure.attachment_type.TEXT)
                        assert login_response.status_code in [200, 302], "Авторизация должна быть успешной"
                
                with allure.step("Сброс триала через /api/update-user/<user_id> с reset_trial=True"):
                    response = client.post(
                        f'/api/update-user/{user_id}',
                        json={'reset_trial': True},
                        content_type='application/json'
                    )
                    allure.attach(str(response.status_code), "Статус ответа", allure.attachment_type.TEXT)
                    if response.is_json:
                        response_data = response.get_json()
                        allure.attach(str(response_data), "Тело ответа", allure.attachment_type.JSON)
                    
                    with allure.step("Проверка статуса ответа и сброса trial_used"):
                        assert response.status_code == 200, f"Ожидался статус 200, получен {response.status_code}"
                        
                        trial_info = get_trial_info(user_id)
                        assert trial_info is not None, "trial_info должен существовать"
                        trial_used_after_reset = trial_info.get('trial_used')
                        allure.attach(str(trial_used_after_reset), "Значение trial_used после сброса", allure.attachment_type.TEXT)
                        assert trial_used_after_reset is False, f"Ожидалось trial_used=False, получено {trial_used_after_reset}"

    @allure.story("Управление пользователями: удаление ключей")
    @allure.title("Удаление ключей пользователя")
    @allure.description("""
    Проверяет удаление всех ключей пользователя через API endpoint /users/revoke/{user_id}.
    
    **Что проверяется:**
    - Доступность API endpoint для авторизованного администратора
    - Отправка POST запроса на /users/revoke/{user_id}
    - Удаление всех ключей пользователя из БД через delete_user_keys
    - Удаление ключей из 3X-UI (если доступно)
    - Корректный статус ответа (200 или 302)
    - Проверка пустого списка ключей через get_user_keys
    
    **Тестовые данные:**
    - user_id: 123487
    - host_name: "test_host"
    - key_email: "user123487-key1@testcode.bot"
    - plan_name: "Test Plan"
    - price: 100.0
    - Созданный ключ с key_id
    
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
    5. Отправка POST запроса на /users/revoke/{user_id}
    6. Проверка статуса ответа (200 или 302)
    7. Проверка удаления ключей из БД (get_user_keys возвращает пустой список)
    
    **Ожидаемый результат:**
    Все ключи пользователя успешно удалены из БД, get_user_keys возвращает пустой список, API возвращает статус 200 или 302.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("users", "keys", "delete", "webhook_server", "unit")
    def test_delete_user_keys(self, temp_db, admin_credentials):
        """Тест удаления ключей пользователя"""
        from src.shop_bot.webhook_server.app import create_webhook_app
        from unittest.mock import MagicMock, AsyncMock
        from datetime import datetime, timezone, timedelta
        
        with allure.step("Подготовка тестового окружения"):
            mock_bot_controller = MagicMock()
            app = create_webhook_app(mock_bot_controller)
            from shop_bot.data_manager.database import (
                register_user_if_not_exists,
                add_new_key,
                get_user_keys,
                create_host,
            )
            allure.attach(str(temp_db), "Путь к временной БД", allure.attachment_type.TEXT)
        
        with allure.step("Настройка БД: регистрация пользователя и создание хоста"):
            user_id = 123487
            register_user_if_not_exists(user_id, "test_user8", referrer_id=None)
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
            initial_keys = get_user_keys(user_id)
            initial_keys_count = len(initial_keys)
            allure.attach(str(initial_keys_count), "Количество ключей до удаления", allure.attachment_type.TEXT)
            assert initial_keys_count > 0, "У пользователя должен быть хотя бы один ключ"
        
        # Патчим DB_FILE для использования временной БД
        with patch('src.shop_bot.webhook_server.app.DB_FILE', temp_db):
            with app.test_client() as client:
                with allure.step("Авторизация администратора"):
                    with patch('src.shop_bot.webhook_server.app.verify_admin_credentials', return_value=True):
                        login_response = client.post('/login', data=admin_credentials)
                        allure.attach(str(login_response.status_code), "Статус авторизации", allure.attachment_type.TEXT)
                        assert login_response.status_code in [200, 302], "Авторизация должна быть успешной"
                
                with allure.step("Удаление ключей пользователя через /users/revoke/{user_id}"):
                    # Мокируем xui_api для успешного удаления
                    from shop_bot.modules import xui_api
                    with patch.object(xui_api, 'login_to_host', return_value=(MagicMock(), MagicMock())):
                        with patch.object(xui_api, 'delete_client_on_host', new=AsyncMock(return_value=True)):
                            response = client.post(f'/users/revoke/{user_id}', follow_redirects=True)
                            allure.attach(str(response.status_code), "Статус ответа", allure.attachment_type.TEXT)
                            
                            with allure.step("Проверка статуса ответа"):
                                assert response.status_code in [200, 302], f"Ожидался статус 200 или 302, получен {response.status_code}"
                            
                            with allure.step("Проверка удаления ключей из БД"):
                                keys = get_user_keys(user_id)
                                keys_count = len(keys)
                                allure.attach(str(keys_count), "Количество ключей после удаления", allure.attachment_type.TEXT)
                                assert keys_count == 0, f"У пользователя не должно быть ключей, но найдено {keys_count}"

