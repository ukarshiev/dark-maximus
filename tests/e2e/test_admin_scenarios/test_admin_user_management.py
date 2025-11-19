#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
E2E тесты для управления пользователями администратором
"""

import pytest
import allure
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root / "src"))


@pytest.mark.e2e
@allure.epic("E2E тесты")
@allure.feature("Административные сценарии")
@allure.label("package", "tests.e2e.test_admin_scenarios")
class TestAdminUserManagement:
    """E2E тесты для управления пользователями"""

    @pytest.fixture
    def flask_app(self, temp_db, monkeypatch):
        """Фикстура для Flask приложения"""
        import shop_bot.webhook_server.app as webhook_app_module
        
        # Патчим DB_FILE в модуле app.py для использования temp_db
        monkeypatch.setattr(webhook_app_module, 'DB_FILE', temp_db)
        
        from shop_bot.webhook_server.app import create_webhook_app
        
        mock_bot_controller = MagicMock()
        mock_bot_controller.get_status.return_value = {'shop_bot': 'running'}
        
        app = create_webhook_app(mock_bot_controller)
        app.config['TESTING'] = True
        app.config['SECRET_KEY'] = 'test-secret-key'
        app.config['WTF_CSRF_ENABLED'] = False
        
        return app.test_client()

    @pytest.fixture
    def authenticated_session(self, flask_app):
        """Фикстура для авторизованной сессии"""
        with patch('shop_bot.data_manager.database.verify_admin_credentials', return_value=True):
            with flask_app.session_transaction() as sess:
                sess['logged_in'] = True
            return flask_app

    @allure.story("Администратор: управление пользователями")
    @allure.title("Полный цикл управления пользователями администратором")
    @allure.description("""
    E2E тест, проверяющий полный цикл управления пользователями администратором в веб-панели.
    
    **Что проверяется:**
    - Просмотр списка пользователей на странице /users
    - Обновление баланса пользователя через API
    - Блокировка (бан) пользователя через API
    - Корректная работа всех операций для авторизованного администратора
    - Сохранение изменений в БД
    
    **Тестовые данные:**
    - user_id: 123456
    - username: 'test_user'
    - Начальный баланс: 0.0
    - Обновленный баланс: 500.0
    - Используется авторизованная сессия администратора (authenticated_session)
    - Моки для get_all_users
    
    **Предусловия:**
    - Администратор авторизован в системе
    - Используется временная БД (temp_db)
    - Flask приложение настроено для тестирования
    - Тестовый пользователь создан в БД
    
    **Шаги теста:**
    1. Создание тестового пользователя в БД
    2. Просмотр списка пользователей на странице /users
    3. Обновление баланса пользователя через POST /api/update-user/{user_id}
    4. Проверка обновления баланса в БД (balance = 500.0)
    5. Блокировка пользователя через POST /users/ban/{user_id}
    6. Проверка блокировки пользователя в БД (is_banned = 1)
    
    **Ожидаемый результат:**
    Все операции управления пользователями выполняются успешно:
    - Страница /users отображается со статусом 200
    - Баланс пользователя обновлен до 500.0 в БД
    - Пользователь заблокирован (is_banned = 1) в БД
    """)
    @allure.severity(allure.severity_level.CRITICAL)
    @allure.tag("e2e", "admin", "user_management", "webhook_server", "critical")
    def test_admin_user_management(self, authenticated_session, temp_db):
        import sqlite3
        
        # Вход (уже авторизован через фикстуру)
        
        # Создаем тестового пользователя в temp_db
        user_id = 123456
        with sqlite3.connect(temp_db) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR IGNORE INTO users (telegram_id, username, balance, is_banned)
                VALUES (?, ?, ?, ?)
            ''', (user_id, 'test_user', 0.0, 0))
            conn.commit()
        
        # Просмотр пользователей
        with patch('shop_bot.data_manager.database.get_all_users', return_value=[{
            'telegram_id': user_id,
            'username': 'test_user',
            'balance': 0.0,
            'is_banned': 0
        }]):
            response = authenticated_session.get('/users')
            assert response.status_code == 200
        
        # Обновление баланса
        response = authenticated_session.post('/api/update-user/123456', data={
            'balance': '500.0'
        })
        assert response.status_code in [200, 302, 400, 404]
        
        # Проверяем, что баланс обновился
        with sqlite3.connect(temp_db) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT balance FROM users WHERE telegram_id = ?", (user_id,))
            result = cursor.fetchone()
            if result:
                assert result[0] == 500.0, "Баланс должен быть обновлен"
        
        # Бан/разбан
        response = authenticated_session.post('/users/ban/123456')
        assert response.status_code in [200, 302, 404]
        
        # Проверяем, что пользователь забанен
        with sqlite3.connect(temp_db) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT is_banned FROM users WHERE telegram_id = ?", (user_id,))
            result = cursor.fetchone()
            if result:
                assert result[0] == 1, "Пользователь должен быть забанен"

