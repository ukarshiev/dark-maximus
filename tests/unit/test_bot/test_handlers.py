#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Unit-тесты для обработчиков бота

Тестирует базовую логику обработчиков с использованием моков
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


@pytest.mark.unit
@pytest.mark.bot
@allure.epic("Обработчики бота")
@allure.feature("Обработка команд")
@allure.label("package", "src.shop_bot.handlers")
class TestHandlersLogic:
    """Тесты для логики обработчиков"""

    @allure.title("Парсинг deeplink параметров в start handler")
    @allure.description("""
    Проверяет парсинг различных форматов deeplink параметров в start handler.
    
    **Что проверяется:**
    - Парсинг base64 формата deeplink (группа и промокод)
    - Парсинг referral формата deeplink (реферер)
    - Корректность извлечения параметров из различных форматов
    
    **Тестовые данные:**
    - base64 format: "eyJnIjoidmlwIiwicCI6IlNBTEU1MCJ9" (group: "vip", promo: "SALE50")
    - referral format: "ref_123456" (referrer: 123456)
    
    **Ожидаемый результат:**
    Все форматы deeplink корректно парсятся, параметры извлекаются правильно.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("handlers", "deeplink", "parsing", "bot", "unit")
    def test_deeplink_parsing_in_start_handler(self, temp_db):
        """Тест парсинга deeplink параметров в start handler"""
        from shop_bot.utils.deeplink import parse_deeplink
        
        # Тестируем парсинг различных форматов deeplink
        test_cases = [
            ("eyJnIjoidmlwIiwicCI6IlNBTEU1MCJ9", "vip", "SALE50", None),  # base64 format
            ("ref_123456", None, None, 123456),  # referral format
        ]
        
        for param, expected_group, expected_promo, expected_referrer in test_cases:
            group, promo, referrer = parse_deeplink(param)
            assert group == expected_group
            assert promo == expected_promo
            assert referrer == expected_referrer

    @allure.title("Логика регистрации пользователя")
    @allure.description("""
    Проверяет полный поток регистрации пользователя в системе.
    
    **Что проверяется:**
    - Регистрация нового пользователя через register_user_if_not_exists
    - Проверка наличия пользователя в БД после регистрации
    - Назначение пользователя в группу через deeplink
    - Корректность данных зарегистрированного пользователя
    
    **Тестовые данные:**
    - telegram_id: 123456830
    - username: "new_user"
    - group_code: "test_group"
    
    **Ожидаемый результат:**
    Пользователь успешно зарегистрирован и назначен в группу.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("handlers", "registration", "user_group", "bot", "unit")
    def test_user_registration_flow(self, temp_db):
        """Тест логики регистрации пользователя"""
        from shop_bot.data_manager.database import (
            register_user_if_not_exists,
            get_user,
            assign_user_to_group_by_code,
        )
        
        telegram_id = 123456830
        username = "new_user"
        
        # Регистрируем пользователя
        register_user_if_not_exists(telegram_id, username, None, "New User")
        
        # Проверяем регистрацию
        user = get_user(telegram_id)
        assert user is not None
        assert user['username'] == username
        
        # Проверяем назначение в группу через deeplink
        # Создаем группу
        from shop_bot.data_manager.database import create_user_group
        group_id = create_user_group(
            group_name="Test Group",
            group_description="Test",
            group_code="test_group"
        )
        
        # Назначаем пользователя в группу
        success = assign_user_to_group_by_code(telegram_id, "test_group")
        assert success is True

    @allure.title("Логика согласия с условиями")
    @allure.description("""
    Проверяет логику согласия пользователя с условиями использования.
    
    **Что проверяется:**
    - Регистрация пользователя
    - Установка флага согласия через set_terms_agreed
    - Проверка сохранения флага agreed_to_terms в БД
    
    **Тестовые данные:**
    - telegram_id: 123456831
    - username: "test_user14"
    
    **Ожидаемый результат:**
    Флаг согласия с условиями успешно установлен и сохранен в БД.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("handlers", "terms_agreement", "bot", "unit")
    @patch('shop_bot.data_manager.database.get_setting')
    def test_terms_agreement_flow(self, mock_get_setting, temp_db):
        """Тест логики согласия с условиями"""
        from shop_bot.data_manager.database import (
            register_user_if_not_exists,
            set_terms_agreed,
            get_user,
        )
        
        mock_get_setting.return_value = None
        
        telegram_id = 123456831
        register_user_if_not_exists(telegram_id, "test_user14", None, "Test User 14")
        
        # Устанавливаем согласие
        set_terms_agreed(telegram_id)
        
        # Проверяем согласие
        user = get_user(telegram_id)
        assert user is not None
        assert user.get('agreed_to_terms') == 1

