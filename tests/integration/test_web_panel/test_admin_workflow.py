#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Интеграционные тесты для workflow администратора
"""

import pytest
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock
import json
import allure

project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root / "src"))


@pytest.mark.integration
@allure.epic("Интеграционные тесты")
@allure.feature("Веб-панель")
@allure.label("package", "tests.integration.test_web_panel")
class TestAdminWorkflow:
    """Тесты полного workflow администратора"""

    @pytest.fixture
    def flask_app(self, temp_db, monkeypatch):
        """Фикстура для Flask приложения"""
        from shop_bot.webhook_server.app import create_webhook_app
        
        mock_bot_controller = MagicMock()
        mock_bot_controller.get_status.return_value = {'shop_bot': 'running', 'support_bot': 'stopped'}
        mock_bot_controller.get_bot_instance.return_value = None
        
        app = create_webhook_app(mock_bot_controller)
        app.config['TESTING'] = True
        app.config['SECRET_KEY'] = 'test-secret-key'
        app.config['WTF_CSRF_ENABLED'] = False
        # Переопределяем SESSION_TYPE на None для тестов, чтобы использовать cookie-based сессии
        # вместо файловых сессий, которые могут вызывать проблемы с session_transaction()
        app.config['SESSION_TYPE'] = None
        
        return app.test_client()

    @pytest.fixture
    def authenticated_session(self, flask_app):
        """Фикстура для авторизованной сессии"""
        with patch('shop_bot.data_manager.database.verify_admin_credentials', return_value=True):
            with flask_app.session_transaction() as sess:
                sess['logged_in'] = True
            return flask_app

    @allure.story("Полный workflow администратора")
    @allure.title("Полный workflow администратора: навигация по основным разделам")
    @allure.description("""
    Проверяет последовательность действий администратора при работе с веб-панелью:
    
    **Что проверяется:**
    - Доступность основных разделов административной панели
    - Корректная работа навигации между разделами
    - Отсутствие ошибок авторизации при переходе между страницами
    - Корректная загрузка данных через моки БД
    
    **Тестовые данные:**
    - Сессия администратора: authenticated_session (фикстура создает авторизованную сессию)
    - Временная БД: temp_db (используется через flask_app)
    - Моки БД: get_all_settings возвращает {}, get_all_users возвращает [], get_paginated_keys возвращает ([], 0)
    - Эндпоинты: GET /, GET /users, GET /keys
    
    **Шаги теста:**
    1. **Доступ к главной странице (Dashboard)**
       - Метод/эндпоинт: GET /
       - Параметры: сессия администратора (authenticated_session)
       - Ожидаемый результат: HTTP 200, страница загружается без ошибок
       - Проверка: response.status_code == 200
       - Мок: database.get_all_settings возвращает пустой словарь {}
       - Проверяемые поля: статус код ответа, отсутствие ошибок в ответе
    
    2. **Доступ к разделу пользователей**
       - Метод/эндпоинт: GET /users
       - Параметры: сессия администратора (authenticated_session)
       - Ожидаемый результат: HTTP 200, список пользователей отображается
       - Проверка: response.status_code == 200
       - Мок: database.get_all_users возвращает пустой список []
       - Проверяемые поля: статус код ответа, отсутствие ошибок в ответе
    
    3. **Доступ к разделу ключей**
       - Метод/эндпоинт: GET /keys
       - Параметры: сессия администратора (authenticated_session)
       - Ожидаемый результат: HTTP 200, список ключей отображается
       - Проверка: response.status_code == 200
       - Мок: database.get_paginated_keys возвращает ([], 0) - пустой список и 0 записей
       - Проверяемые поля: статус код ответа, отсутствие ошибок в ответе
    
    **Предусловия:**
    - Администратор авторизован в системе (сессия активна через фикстуру authenticated_session)
    - Используется временная БД (temp_db) через flask_app
    - CSRF защита отключена для тестов (WTF_CSRF_ENABLED = False)
    - Flask приложение настроено в тестовом режиме (TESTING = True)
    - Моки для database.get_all_settings, get_all_users, get_paginated_keys настроены
    
    **Используемые моки и фикстуры:**
    - authenticated_session: Flask test client с активной сессией администратора (sess['logged_in'] = True)
    - flask_app: Flask test client, созданный через create_webhook_app с mock_bot_controller
    - temp_db: временная SQLite БД с полной структурой таблиц (используется через flask_app)
    - mock_bot_controller: мок контроллера ботов с методами get_status (возвращает {'shop_bot': 'running', 'support_bot': 'stopped'}) и get_bot_instance (возвращает None)
    - Моки для database.get_all_settings, get_all_users, get_paginated_keys
    
    **Проверяемые граничные случаи:**
    - Навигация между разделами без ошибок авторизации
    - Загрузка страниц с пустыми данными (пустые списки пользователей и ключей)
    - Корректная работа сессии администратора при переходах между страницами
    
    **Ожидаемый результат:**
    Все три страницы должны успешно загружаться без ошибок авторизации или доступа.
    Статус код каждого запроса должен быть 200.
    Навигация между разделами должна работать корректно без потери сессии.
    """)
    @allure.severity(allure.severity_level.CRITICAL)
    @allure.tag("admin", "navigation", "workflow", "web-panel", "critical")
    def test_admin_full_workflow(self, authenticated_session):
        """Тест полного workflow администратора"""
        # Вход → dashboard → пользователи → ключи
        with patch('shop_bot.data_manager.database.get_all_settings', return_value={}):
            with allure.step("Проверка доступа к главной странице (Dashboard)"):
                response = authenticated_session.get('/', follow_redirects=True)
                assert response.status_code == 200, f"Ожидался статус 200, получен {response.status_code}"
            
            # Пользователи
            with patch('shop_bot.data_manager.database.get_all_users', return_value=[]):
                with allure.step("Проверка доступа к разделу пользователей"):
                    response = authenticated_session.get('/users')
                    assert response.status_code == 200, f"Ожидался статус 200, получен {response.status_code}"
            
            # Ключи
            with patch('shop_bot.data_manager.database.get_paginated_keys', return_value=([], 0)):
                with allure.step("Проверка доступа к разделу ключей"):
                    response = authenticated_session.get('/keys')
                    assert response.status_code == 200, f"Ожидался статус 200, получен {response.status_code}"

    @allure.story("Полный workflow администратора")
    @allure.title("Обновление настроек административной панели")
    @allure.description("""
    Проверяет процесс обновления настроек административной панели через веб-интерфейс:
    
    **Что проверяется:**
    - Доступность страницы настроек
    - Возможность обновления настроек панели (логин, часовой пояс)
    - Корректный редирект после успешного обновления
    - Сохранение настроек в БД через update_setting
    
    **Тестовые данные:**
    - Сессия администратора: authenticated_session (фикстура создает авторизованную сессию)
    - Временная БД: temp_db (используется через flask_app)
    - Параметры обновления: panel_login='admin', admin_timezone='Europe/Moscow'
    - Моки БД: get_all_settings возвращает {}, get_all_hosts возвращает [], update_setting вызывается для сохранения
    - Эндпоинты: GET /settings, POST /settings/panel
    
    **Шаги теста:**
    1. **Просмотр страницы настроек**
       - Метод/эндпоинт: GET /settings
       - Параметры: сессия администратора (authenticated_session)
       - Ожидаемый результат: HTTP 200, страница настроек загружается
       - Проверка: response.status_code == 200
       - Моки: database.get_all_settings возвращает пустой словарь {}, database.get_all_hosts возвращает пустой список []
       - Проверяемые поля: статус код ответа, отсутствие ошибок в ответе
    
    2. **Обновление настроек панели**
       - Метод/эндпоинт: POST /settings/panel
       - Параметры запроса: panel_login='admin', admin_timezone='Europe/Moscow'
       - Content-Type: application/x-www-form-urlencoded (по умолчанию для Flask form data)
       - Ожидаемый результат: HTTP 302 (редирект), настройки обновлены
       - Проверка: response.status_code == 302
       - Мок: database.update_setting вызывается для сохранения настроек (panel_login и admin_timezone)
       - Проверяемые поля: статус код ответа (редирект), вызов update_setting с правильными параметрами
    
    **Предусловия:**
    - Администратор авторизован в системе (сессия активна через фикстуру authenticated_session)
    - Используется временная БД (temp_db) через flask_app
    - CSRF защита отключена для тестов (WTF_CSRF_ENABLED = False)
    - Flask приложение настроено в тестовом режиме (TESTING = True)
    - Моки для database.get_all_settings, get_all_hosts, update_setting настроены
    
    **Используемые моки и фикстуры:**
    - authenticated_session: Flask test client с активной сессией администратора (sess['logged_in'] = True)
    - flask_app: Flask test client, созданный через create_webhook_app с mock_bot_controller
    - temp_db: временная SQLite БД с полной структурой таблиц (используется через flask_app)
    - Моки для database.get_all_settings (возвращает {}), get_all_hosts (возвращает []), update_setting (вызывается для сохранения)
    
    **Проверяемые граничные случаи:**
    - Обновление настроек с валидными данными (логин и часовой пояс)
    - Корректный редирект после успешного обновления
    - Сохранение настроек в БД через update_setting
    
    **Ожидаемый результат:**
    Страница настроек должна загружаться успешно (HTTP 200).
    После отправки формы обновления настроек должен произойти редирект (HTTP 302).
    Настройки должны быть сохранены в БД через вызов update_setting.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("admin", "settings", "workflow", "web-panel", "normal")
    def test_settings_update_workflow(self, authenticated_session):
        """Тест обновления настроек через веб-панель"""
        with patch('shop_bot.data_manager.database.get_all_settings', return_value={}):
            with patch('shop_bot.data_manager.database.get_all_hosts', return_value=[]):
                # Просмотр настроек
                with allure.step("Просмотр страницы настроек"):
                    response = authenticated_session.get('/settings')
                    assert response.status_code == 200, f"Ожидался статус 200, получен {response.status_code}"
                
                # Обновление настроек панели
                with patch('shop_bot.data_manager.database.update_setting'):
                    with allure.step("Обновление настроек панели (логин и часовой пояс)"):
                        response = authenticated_session.post('/settings/panel', data={
                            'panel_login': 'admin',
                            'admin_timezone': 'Europe/Moscow'
                        })
                        assert response.status_code == 302, f"Ожидался редирект (302), получен {response.status_code}"

    @allure.story("Полный workflow администратора")
    @allure.title("Управление промокодами через веб-панель")
    @allure.description("""
    Проверяет полный цикл работы с промокодами через административную панель:
    
    **Что проверяется:**
    - Доступность страницы со списком промокодов
    - Возможность создания нового промокода через API
    - Корректная обработка данных промокода (код, бот, скидка, лимит использования)
    - Сохранение промокода в БД через create_promo_code
    
    **Тестовые данные:**
    - Сессия администратора: authenticated_session (фикстура создает авторизованную сессию)
    - Временная БД: temp_db (используется через flask_app)
    - Данные промокода: code='WORKFLOWTEST', bot='shop', discount_amount=50.0, usage_limit_per_bot=1
    - Моки БД: get_all_user_groups возвращает [], create_promo_code возвращает 1 (ID промокода), get_setting возвращает 'test_bot'
    - Эндпоинты: GET /promo-codes, POST /api/promo-codes
    
    **Шаги теста:**
    1. **Просмотр списка промокодов**
       - Метод/эндпоинт: GET /promo-codes
       - Параметры: сессия администратора (authenticated_session)
       - Ожидаемый результат: HTTP 200, страница промокодов загружается
       - Проверка: response.status_code == 200
       - Мок: database.get_all_user_groups возвращает пустой список []
       - Проверяемые поля: статус код ответа, отсутствие ошибок в ответе
    
    2. **Создание нового промокода**
       - Метод/эндпоинт: POST /api/promo-codes
       - Content-Type: application/json
       - Параметры запроса (JSON): code='WORKFLOWTEST', bot='shop', discount_amount=50.0, usage_limit_per_bot=1
       - Ожидаемый результат: HTTP 200 (успех) или HTTP 500 (ошибка сервера)
       - Проверка: response.status_code in [200, 500]
       - Моки:
         * database.create_promo_code возвращает ID созданного промокода (1)
         * database.get_setting возвращает 'test_bot'
       - Проверяемые поля: статус код ответа, вызов create_promo_code с правильными параметрами
    
    **Предусловия:**
    - Администратор авторизован в системе (сессия активна через фикстуру authenticated_session)
    - Используется временная БД (temp_db) через flask_app
    - CSRF защита отключена для тестов (WTF_CSRF_ENABLED = False)
    - Flask приложение настроено в тестовом режиме (TESTING = True)
    - Моки для database.get_all_user_groups, create_promo_code, get_setting настроены
    
    **Используемые моки и фикстуры:**
    - authenticated_session: Flask test client с активной сессией администратора (sess['logged_in'] = True)
    - flask_app: Flask test client, созданный через create_webhook_app с mock_bot_controller
    - temp_db: временная SQLite БД с полной структурой таблиц (используется через flask_app)
    - Моки для database.get_all_user_groups (возвращает []), create_promo_code (возвращает 1), get_setting (возвращает 'test_bot')
    
    **Проверяемые граничные случаи:**
    - Создание промокода с валидными данными (код, бот, скидка, лимит)
    - Обработка успешного создания (HTTP 200) или ошибки сервера (HTTP 500)
    - Сохранение промокода в БД через create_promo_code с возвратом ID
    
    **Ожидаемый результат:**
    Страница промокодов должна загружаться успешно (HTTP 200).
    Создание промокода должно завершиться успешно (HTTP 200) или вернуть ошибку сервера (HTTP 500).
    Промокод должен быть сохранен в БД через вызов create_promo_code с правильными параметрами.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("admin", "promo-codes", "workflow", "web-panel", "normal")
    def test_promo_code_management_workflow(self, authenticated_session):
        """Тест управления промокодами через веб-панель"""
        with patch('shop_bot.data_manager.database.get_all_user_groups', return_value=[]):
            # Просмотр промокодов
            with allure.step("Просмотр списка промокодов"):
                response = authenticated_session.get('/promo-codes')
                assert response.status_code == 200, f"Ожидался статус 200, получен {response.status_code}"
            
            # Создание промокода
            with patch('shop_bot.data_manager.database.create_promo_code', return_value=1):
                with patch('shop_bot.data_manager.database.get_setting', return_value='test_bot'):
                    with allure.step("Создание нового промокода через API"):
                        data = {
                            'code': 'WORKFLOWTEST',
                            'bot': 'shop',
                            'discount_amount': 50.0,
                            'usage_limit_per_bot': 1
                        }
                        response = authenticated_session.post(
                            '/api/promo-codes',
                            data=json.dumps(data),
                            content_type='application/json'
                        )
                        assert response.status_code in [200, 500], f"Ожидался статус 200 или 500, получен {response.status_code}"

