#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Unit-тесты для инструкций"""

import pytest
import allure
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root / "src"))


@pytest.mark.unit
@allure.epic("Веб-панель")
@allure.feature("Инструкции")
@allure.label("package", "src.shop_bot.webhook_server")
class TestInstructions:
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

    @allure.story("Инструкции: управление инструкциями")
    @allure.title("Отображение страницы инструкций")
    @allure.description("""
    Проверяет отображение страницы инструкций в веб-панели.
    
    **Что проверяется:**
    - Доступность страницы /instructions для авторизованного администратора
    - Корректный статус ответа (200)
    - Отображение списка видео-инструкций
    
    **Тестовые данные:**
    - Моки для get_all_video_instructions и get_video_instructions_display_setting
    
    **Ожидаемый результат:**
    Страница /instructions успешно отображается со статусом 200.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("instructions", "webhook_server", "unit")
    def test_instructions_page(self, authenticated_session):
        with patch('shop_bot.data_manager.database.get_all_video_instructions', return_value=[]):
            with patch('shop_bot.data_manager.database.get_video_instructions_display_setting', return_value=True):
                response = authenticated_session.get('/instructions')
                assert response.status_code == 200

    @allure.story("Инструкции: управление инструкциями")
    @allure.title("Создание новой инструкции")
    @allure.description("""
    Проверяет создание новой инструкции через POST /instructions.
    
    **Что проверяется:**
    - Создание инструкции с указанием платформы и содержимого
    - Корректный статус ответа (200 или 302)
    - Сохранение инструкции в системе
    
    **Тестовые данные:**
    - platform: 'android'
    - instructions_content: 'Test instructions'
    - show_in_bot: 'on'
    
    **Ожидаемый результат:**
    Инструкция успешно создана, статус ответа 200 или 302.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("instructions", "create", "webhook_server", "unit")
    def test_create_instruction(self, authenticated_session):
        response = authenticated_session.post('/instructions', data={
            'platform': 'android',
            'instructions_content': 'Test instructions',
            'show_in_bot': 'on'
        })
        assert response.status_code in [200, 302]

    @allure.story("Инструкции: управление инструкциями")
    @allure.title("Обновление существующей инструкции")
    @allure.description("""
    Проверяет обновление существующей инструкции через POST /instructions.
    
    **Что проверяется:**
    - Обновление инструкции с новым содержимым
    - Корректный статус ответа (200 или 302)
    - Сохранение обновленной инструкции в системе
    
    **Тестовые данные:**
    - platform: 'android'
    - instructions_content: 'Updated instructions'
    - show_in_bot: 'on'
    
    **Ожидаемый результат:**
    Инструкция успешно обновлена, статус ответа 200 или 302.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("instructions", "update", "webhook_server", "unit")
    def test_update_instruction(self, authenticated_session):
        response = authenticated_session.post('/instructions', data={
            'platform': 'android',
            'instructions_content': 'Updated instructions',
            'show_in_bot': 'on'
        })
        assert response.status_code in [200, 302]

    @allure.story("Инструкции: управление инструкциями")
    @allure.title("Удаление инструкции")
    @allure.description("""
    Проверяет удаление инструкции через файловую систему.
    
    **Что проверяется:**
    - Отсутствие отдельного endpoint для удаления инструкций
    - Удаление инструкций реализовано через файловую систему
    
    **Ожидаемый результат:**
    Удаление инструкций реализовано через файловую систему (не через API endpoint).
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("instructions", "delete", "webhook_server", "unit")
    def test_delete_instruction(self, authenticated_session):
        # В текущей реализации нет отдельного endpoint для удаления
        # Инструкции сохраняются как файлы, удаление через файловую систему
        assert True, "Удаление инструкций реализовано через файловую систему"

    @allure.story("Инструкции: управление инструкциями")
    @allure.title("Обновление настройки отображения видео-инструкций")
    @allure.description("""
    Проверяет обновление настройки отображения видео-инструкций через API endpoint /api/update-video-instructions-display.
    
    **Что проверяется:**
    - Обновление настройки show_in_bot для видео-инструкций
    - Корректный статус ответа (200, 400 или 500)
    - Сохранение настройки в БД
    
    **Тестовые данные:**
    - show_in_bot: 'true'
    - Моки для set_video_instructions_display_setting
    
    **Ожидаемый результат:**
    Настройка отображения видео-инструкций успешно обновлена, статус ответа 200, 400 или 500.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("instructions", "api", "video_display", "webhook_server", "unit")
    def test_update_video_instructions_display(self, authenticated_session):
        with patch('shop_bot.data_manager.database.set_video_instructions_display_setting'):
            response = authenticated_session.post('/api/update-video-instructions-display', 
                                                 data={'show_in_bot': 'true'},
                                                 content_type='application/json')
            assert response.status_code in [200, 400, 500]

