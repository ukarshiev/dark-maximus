#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Unit-тесты для генерации клавиатур бота

Тестирует функции генерации клавиатур из keyboards.py
"""

import pytest
import allure
import sys
from pathlib import Path
from unittest.mock import patch

# Добавляем путь к проекту
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root / "src"))

from shop_bot.bot import keyboards
from aiogram.types import ReplyKeyboardMarkup, InlineKeyboardMarkup


@pytest.mark.unit
@pytest.mark.bot
@allure.epic("Обработчики бота")
@allure.feature("Генерация клавиатур")
@allure.label("package", "src.shop_bot.keyboards")
class TestKeyboardGeneration:
    """Тесты для генерации клавиатур"""

    @allure.title("Генерация главной клавиатуры для обычного пользователя")
    @allure.description("""
    Проверяет генерацию главной reply-клавиатуры для обычного пользователя.
    
    **Что проверяется:**
    - Генерация клавиатуры через get_main_reply_keyboard(is_admin=False)
    - Наличие основных кнопок (🛒 Купить, 👤 Мой профиль, ⁉️ Помощь и поддержка)
    - Отсутствие кнопки админ-панели для обычного пользователя
    - Корректность типа клавиатуры (ReplyKeyboardMarkup)
    
    **Ожидаемый результат:**
    Клавиатура содержит все необходимые кнопки для обычного пользователя, кнопка админ-панели отсутствует.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("keyboard", "reply_keyboard", "user", "bot", "unit")
    def test_get_main_reply_keyboard_user(self):
        """Тест генерации главной клавиатуры для обычного пользователя"""
        keyboard = keyboards.get_main_reply_keyboard(is_admin=False)
        
        assert isinstance(keyboard, ReplyKeyboardMarkup)
        assert keyboard.resize_keyboard is True
        
        # Проверяем наличие основных кнопок
        buttons_text = [btn.text for row in keyboard.keyboard for btn in row]
        assert "🛒 Купить" in buttons_text
        assert "👤 Мой профиль" in buttons_text
        assert "⁉️ Помощь и поддержка" in buttons_text
        assert "⚙️ Админ-панель" not in buttons_text

    @allure.title("Генерация главной клавиатуры для администратора")
    @allure.description("""
    Проверяет генерацию главной reply-клавиатуры для администратора.
    
    **Что проверяется:**
    - Генерация клавиатуры через get_main_reply_keyboard(is_admin=True)
    - Наличие кнопки админ-панели для администратора
    - Корректность типа клавиатуры (ReplyKeyboardMarkup)
    
    **Ожидаемый результат:**
    Клавиатура содержит кнопку админ-панели для администратора.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("keyboard", "reply_keyboard", "admin", "bot", "unit")
    def test_get_main_reply_keyboard_admin(self):
        """Тест генерации главной клавиатуры для администратора"""
        keyboard = keyboards.get_main_reply_keyboard(is_admin=True)
        
        assert isinstance(keyboard, ReplyKeyboardMarkup)
        
        # Проверяем наличие кнопки админ-панели
        buttons_text = [btn.text for row in keyboard.keyboard for btn in row]
        assert "⚙️ Админ-панель" in buttons_text

    @allure.title("Генерация клавиатуры покупки без ключей")
    @allure.description("""
    Проверяет генерацию inline-клавиатуры покупки для пользователя без ключей.
    
    **Что проверяется:**
    - Генерация клавиатуры через create_buy_root_keyboard([])
    - Наличие кнопки "Купить новый ключ"
    - Корректность типа клавиатуры (InlineKeyboardMarkup)
    
    **Ожидаемый результат:**
    Клавиатура содержит кнопку для покупки нового ключа.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("keyboard", "buy_keyboard", "empty", "bot", "unit")
    def test_create_buy_root_keyboard_empty(self):
        """Тест генерации клавиатуры покупки без ключей"""
        keyboard = keyboards.create_buy_root_keyboard([])
        
        assert isinstance(keyboard, InlineKeyboardMarkup)
        # Должна быть кнопка "Купить новый ключ"
        buttons = keyboard.inline_keyboard
        assert len(buttons) > 0

    @allure.title("Генерация клавиатуры покупки с ключами")
    @allure.description("""
    Проверяет генерацию inline-клавиатуры покупки для пользователя с существующими ключами.
    
    **Что проверяется:**
    - Генерация клавиатуры через create_buy_root_keyboard(user_keys)
    - Наличие кнопок для существующих ключей
    - Наличие кнопки "Купить новый ключ"
    - Корректность типа клавиатуры (InlineKeyboardMarkup)
    
    **Тестовые данные:**
    - user_keys: 2 ключа с key_id 1 и 2
    
    **Ожидаемый результат:**
    Клавиатура содержит кнопки для существующих ключей и кнопку для покупки нового ключа.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("keyboard", "buy_keyboard", "with_keys", "bot", "unit")
    def test_create_buy_root_keyboard_with_keys(self):
        """Тест генерации клавиатуры покупки с ключами"""
        user_keys = [
            {"key_id": 1, "plan_name": "Test Plan 1"},
            {"key_id": 2, "plan_name": "Test Plan 2"},
        ]
        
        keyboard = keyboards.create_buy_root_keyboard(user_keys)
        
        assert isinstance(keyboard, InlineKeyboardMarkup)
        # Должны быть кнопки для существующих ключей и "Купить новый ключ"
        buttons = keyboard.inline_keyboard
        assert len(buttons) > 0

    @allure.title("Генерация клавиатуры профиля")
    @allure.description("""
    Проверяет генерацию inline-клавиатуры профиля пользователя.
    
    **Что проверяется:**
    - Генерация клавиатуры через create_profile_menu_keyboard
    - Наличие кнопок профиля с учетом параметров (total_keys_count, trial_used, auto_renewal_enabled)
    - Корректность типа клавиатуры (InlineKeyboardMarkup)
    
    **Тестовые данные:**
    - total_keys_count: 5
    - trial_used: 1
    - auto_renewal_enabled: True
    
    **Ожидаемый результат:**
    Клавиатура содержит все необходимые кнопки профиля.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("keyboard", "profile_keyboard", "bot", "unit")
    def test_create_profile_menu_keyboard(self):
        """Тест генерации клавиатуры профиля"""
        keyboard = keyboards.create_profile_menu_keyboard(
            total_keys_count=5,
            trial_used=1,
            auto_renewal_enabled=True
        )
        
        assert isinstance(keyboard, InlineKeyboardMarkup)
        buttons = keyboard.inline_keyboard
        assert len(buttons) > 0

    @allure.title("Генерация клавиатуры помощи")
    @allure.description("""
    Проверяет генерацию inline-клавиатуры центра помощи.
    
    **Что проверяется:**
    - Генерация клавиатуры через create_help_center_keyboard
    - Использование настройки support_user из БД
    - Корректность типа клавиатуры (InlineKeyboardMarkup)
    
    **Тестовые данные:**
    - support_user: "test_support_user"
    
    **Ожидаемый результат:**
    Клавиатура содержит все необходимые кнопки центра помощи.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("keyboard", "help_keyboard", "bot", "unit")
    @patch('shop_bot.bot.keyboards.get_setting')
    def test_create_help_center_keyboard(self, mock_get_setting):
        """Тест генерации клавиатуры помощи"""
        mock_get_setting.return_value = "test_support_user"
        
        keyboard = keyboards.create_help_center_keyboard()
        
        assert isinstance(keyboard, InlineKeyboardMarkup)
        buttons = keyboard.inline_keyboard
        assert len(buttons) > 0

    @allure.title("Генерация клавиатуры оплаты через Stars")
    @allure.description("""
    Проверяет генерацию inline-клавиатуры для оплаты через Telegram Stars.
    
    **Что проверяется:**
    - Генерация клавиатуры через create_stars_payment_keyboard
    - Корректность типа клавиатуры (InlineKeyboardMarkup)
    - Наличие кнопок для оплаты через Stars
    
    **Ожидаемый результат:**
    Клавиатура содержит кнопки для оплаты через Telegram Stars.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("keyboard", "payment_keyboard", "stars", "bot", "unit")
    def test_create_stars_payment_keyboard(self):
        """Тест генерации клавиатуры оплаты через Stars"""
        keyboard = keyboards.create_stars_payment_keyboard(amount_stars=100)
        
        assert isinstance(keyboard, InlineKeyboardMarkup)
        buttons_text = [btn.text for row in keyboard.inline_keyboard for btn in row]
        assert any("100 ⭐" in text for text in buttons_text)

    @allure.title("Генерация клавиатуры оплаты")
    @allure.description("""
    Проверяет генерацию inline-клавиатуры для оплаты.
    
    **Что проверяется:**
    - Генерация клавиатуры через create_payment_keyboard
    - Корректность типа клавиатуры (InlineKeyboardMarkup)
    - Наличие кнопок для различных способов оплаты
    
    **Ожидаемый результат:**
    Клавиатура содержит кнопки для различных способов оплаты.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("keyboard", "payment_keyboard", "bot", "unit")
    def test_create_payment_keyboard(self):
        """Тест генерации клавиатуры оплаты"""
        payment_url = "https://yookassa.ru/test"
        keyboard = keyboards.create_payment_keyboard(payment_url)
        
        assert isinstance(keyboard, InlineKeyboardMarkup)
        # Проверяем, что есть кнопка с URL оплаты
        buttons = keyboard.inline_keyboard
        assert len(buttons) > 0
        # Должна быть кнопка с payment_url
        found_url = False
        for row in buttons:
            for btn in row:
                if hasattr(btn, 'url') and btn.url == payment_url:
                    found_url = True
        assert found_url, "Должна быть кнопка с URL оплаты"

