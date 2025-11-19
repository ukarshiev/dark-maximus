#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Unit-тесты для документов"""

import pytest
import allure
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root / "src"))


@pytest.mark.unit
@allure.epic("Веб-панель")
@allure.feature("Документы")
@allure.label("package", "src.shop_bot.webhook_server")
class TestDocuments:
    @pytest.fixture
    def flask_app(self):
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
        with patch('shop_bot.data_manager.database.verify_admin_credentials', return_value=True):
            with flask_app.session_transaction() as sess:
                sess['logged_in'] = True
            return flask_app

    @allure.story("Документы: управление документами")
    @allure.title("Отображение страницы условий")
    @allure.description("""
    Проверяет отображение страницы условий использования в веб-панели.
    
    **Что проверяется:**
    - Доступность страницы /terms для авторизованного администратора
    - Корректный статус ответа (200)
    
    **Ожидаемый результат:**
    Страница /terms успешно отображается со статусом 200.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("documents", "terms", "webhook_server", "unit")
    def test_terms_page(self, authenticated_session):
        response = authenticated_session.get('/terms')
        assert response.status_code == 200

    @allure.story("Документы: управление документами")
    @allure.title("Отображение страницы политики конфиденциальности")
    @allure.description("""
    Проверяет отображение страницы политики конфиденциальности в веб-панели.
    
    **Что проверяется:**
    - Доступность страницы /privacy для авторизованного администратора
    - Корректный статус ответа (200)
    
    **Ожидаемый результат:**
    Страница /privacy успешно отображается со статусом 200.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("documents", "privacy", "webhook_server", "unit")
    def test_privacy_page(self, authenticated_session):
        response = authenticated_session.get('/privacy')
        assert response.status_code == 200

    @allure.story("Документы: управление документами")
    @allure.title("Отображение страницы редактирования условий")
    @allure.description("""
    Проверяет отображение страницы редактирования условий использования в веб-панели.
    
    **Что проверяется:**
    - Доступность страницы /edit-terms для авторизованного администратора
    - Корректный статус ответа (200)
    
    **Ожидаемый результат:**
    Страница /edit-terms успешно отображается со статусом 200.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("documents", "edit_terms", "webhook_server", "unit")
    def test_edit_terms(self, authenticated_session):
        response = authenticated_session.get('/edit-terms')
        assert response.status_code == 200

    @allure.story("Документы: управление документами")
    @allure.title("Отображение страницы редактирования политики конфиденциальности")
    @allure.description("""
    Проверяет отображение страницы редактирования политики конфиденциальности в веб-панели.
    
    **Что проверяется:**
    - Доступность страницы /edit-privacy для авторизованного администратора
    - Корректный статус ответа (200)
    
    **Ожидаемый результат:**
    Страница /edit-privacy успешно отображается со статусом 200.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("documents", "edit_privacy", "webhook_server", "unit")
    def test_edit_privacy(self, authenticated_session):
        response = authenticated_session.get('/edit-privacy')
        assert response.status_code == 200

    @allure.story("Документы: управление документами")
    @allure.title("Получение содержимого условий через API")
    @allure.description("""
    Проверяет получение содержимого условий использования через API endpoint /api/get-terms-content.
    
    **Что проверяется:**
    - Доступность API endpoint для авторизованного администратора
    - Корректный статус ответа (200)
    - Возврат содержимого условий
    
    **Ожидаемый результат:**
    API endpoint возвращает содержимое условий со статусом 200.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("documents", "api", "terms_content", "webhook_server", "unit")
    def test_get_terms_content(self, authenticated_session):
        response = authenticated_session.get('/api/get-terms-content')
        assert response.status_code == 200

    @allure.story("Документы: управление документами")
    @allure.title("Получение содержимого политики конфиденциальности через API")
    @allure.description("""
    Проверяет получение содержимого политики конфиденциальности через API endpoint /api/get-privacy-content.
    
    **Что проверяется:**
    - Доступность API endpoint для авторизованного администратора
    - Корректный статус ответа (200)
    - Возврат содержимого политики
    
    **Ожидаемый результат:**
    API endpoint возвращает содержимое политики конфиденциальности со статусом 200.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("documents", "api", "privacy_content", "webhook_server", "unit")
    def test_get_privacy_content(self, authenticated_session):
        response = authenticated_session.get('/api/get-privacy-content')
        assert response.status_code == 200

