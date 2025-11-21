#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Unit-тесты для формирования клавиатур с использованием настроек доменов

Проверяет корректность использования codex_docs_domain для формирования
кнопки "Настройка" в клавиатурах бота.
"""

import pytest
import allure
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

# Добавляем путь к проекту
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root / "src"))

from shop_bot.bot.keyboards import create_key_info_keyboard
from shop_bot.data_manager.database import update_setting, get_setting


@pytest.mark.unit
@pytest.mark.bot
@allure.epic("Обработчики бота")
@allure.feature("Клавиатуры")
@allure.label("package", "src.shop_bot.bot")
class TestKeyboardDomains:
    """Тесты для формирования клавиатур с использованием доменов"""

    @allure.title("Использование codex_docs_domain для кнопки Настройка")
    @allure.description("""
    Проверяет использование настройки codex_docs_domain для формирования URL кнопки "Настройка".
    
    **Что проверяется:**
    - Установка codex_docs_domain в БД
    - Формирование кнопки "Настройка" через create_key_info_keyboard()
    - Использование правильного URL из настройки
    
    **Тестовые данные:**
    - codex_docs_domain: "https://help.example.com"
    - key_id: 1
    
    **Ожидаемый результат:**
    Кнопка "Настройка" содержит URL "https://help.example.com/setup".
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("keyboard", "domain", "codex-docs", "bot", "unit")
    def test_setup_button_uses_codex_docs_domain(self, temp_db):
        """Проверка использования codex_docs_domain для кнопки Настройка"""
        with allure.step("Установка codex_docs_domain в БД"):
            update_setting("codex_docs_domain", "https://help.example.com")
            allure.attach("https://help.example.com", "Установленное значение", allure.attachment_type.TEXT)
        
        with allure.step("Формирование клавиатуры"):
            keyboard = create_key_info_keyboard(key_id=1)
            allure.attach(str(keyboard), "Сформированная клавиатура", allure.attachment_type.TEXT)
        
        with allure.step("Проверка URL кнопки Настройка"):
            # Проверяем, что в клавиатуре есть кнопка с правильным URL
            keyboard_dict = keyboard.model_dump() if hasattr(keyboard, 'model_dump') else str(keyboard)
            keyboard_str = str(keyboard_dict)
            assert "help.example.com/setup" in keyboard_str or "https://help.example.com/setup" in keyboard_str

    @allure.title("Fallback на дефолтный URL если настройка отсутствует")
    @allure.description("""
    Проверяет fallback на дефолтный URL если codex_docs_domain отсутствует.
    
    **Что проверяется:**
    - Отсутствие codex_docs_domain в БД
    - Формирование кнопки "Настройка" через create_key_info_keyboard()
    - Использование дефолтного URL
    
    **Тестовые данные:**
    - codex_docs_domain: не установлен
    - key_id: 1
    
    **Ожидаемый результат:**
    Кнопка "Настройка" содержит дефолтный URL "https://help.dark-maximus.com/setup".
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("keyboard", "domain", "fallback", "bot", "unit")
    def test_setup_button_fallback_to_default(self, temp_db):
        """Проверка fallback на дефолтный URL если настройка отсутствует"""
        with allure.step("Проверка отсутствия настройки"):
            codex_docs_domain = get_setting("codex_docs_domain")
            allure.attach(str(codex_docs_domain), "Текущее значение", allure.attachment_type.TEXT)
        
        with allure.step("Формирование клавиатуры"):
            keyboard = create_key_info_keyboard(key_id=1)
            allure.attach(str(keyboard), "Сформированная клавиатура", allure.attachment_type.TEXT)
        
        with allure.step("Проверка использования дефолтного URL"):
            keyboard_dict = keyboard.model_dump() if hasattr(keyboard, 'model_dump') else str(keyboard)
            keyboard_str = str(keyboard_dict)
            # Проверяем, что используется дефолтный URL (fallback)
            assert "help.dark-maximus.com/setup" in keyboard_str or "https://help.dark-maximus.com/setup" in keyboard_str

    @allure.title("Нормализация URL кнопки Настройка")
    @allure.description("""
    Проверяет нормализацию URL кнопки "Настройка" (протокол, слэши).
    
    **Что проверяется:**
    - Установка codex_docs_domain без протокола
    - Установка codex_docs_domain с trailing slash
    - Формирование правильного URL с /setup
    
    **Тестовые данные:**
    - codex_docs_domain: "help.example.com"
    
    **Ожидаемый результат:**
    URL кнопки "Настройка" нормализован: "https://help.example.com/setup".
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("keyboard", "domain", "normalization", "bot", "unit")
    def test_setup_button_url_normalization(self, temp_db):
        """Проверка нормализации URL кнопки Настройка"""
        with allure.step("Установка codex_docs_domain без протокола"):
            update_setting("codex_docs_domain", "help.example.com")
            allure.attach("help.example.com", "Установленное значение (без протокола)", allure.attachment_type.TEXT)
        
        with allure.step("Формирование клавиатуры"):
            keyboard = create_key_info_keyboard(key_id=1)
            allure.attach(str(keyboard), "Сформированная клавиатура", allure.attachment_type.TEXT)
        
        with allure.step("Проверка нормализованного URL"):
            keyboard_dict = keyboard.model_dump() if hasattr(keyboard, 'model_dump') else str(keyboard)
            keyboard_str = str(keyboard_dict)
            # Проверяем, что URL нормализован (есть https:// и /setup)
            assert "https://help.example.com/setup" in keyboard_str

    @allure.title("Добавление /setup к домену")
    @allure.description("""
    Проверяет добавление пути /setup к домену codex_docs_domain.
    
    **Что проверяется:**
    - Установка codex_docs_domain
    - Формирование URL кнопки "Настройка"
    - Добавление /setup к домену
    
    **Тестовые данные:**
    - codex_docs_domain: "https://help.example.com"
    
    **Ожидаемый результат:**
    URL кнопки "Настройка" содержит "/setup" в конце.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("keyboard", "domain", "setup-path", "bot", "unit")
    def test_setup_button_url_with_setup_path(self, temp_db):
        """Проверка добавления /setup к домену"""
        with allure.step("Установка codex_docs_domain"):
            update_setting("codex_docs_domain", "https://help.example.com")
            allure.attach("https://help.example.com", "Установленное значение", allure.attachment_type.TEXT)
        
        with allure.step("Формирование клавиатуры"):
            keyboard = create_key_info_keyboard(key_id=1)
            allure.attach(str(keyboard), "Сформированная клавиатура", allure.attachment_type.TEXT)
        
        with allure.step("Проверка наличия /setup в URL"):
            keyboard_dict = keyboard.model_dump() if hasattr(keyboard, 'model_dump') else str(keyboard)
            keyboard_str = str(keyboard_dict)
            # Проверяем, что URL содержит /setup
            assert "/setup" in keyboard_str
            assert "help.example.com/setup" in keyboard_str or "https://help.example.com/setup" in keyboard_str

