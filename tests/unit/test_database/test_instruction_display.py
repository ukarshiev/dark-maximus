#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Unit-тесты для функций отображения инструкций в боте
"""

import pytest
import allure
import sys
from pathlib import Path
from unittest.mock import patch

project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root / "src"))

from shop_bot.data_manager import database


@pytest.mark.unit
@pytest.mark.database
@allure.epic("База данных")
@allure.feature("Отображение инструкций")
@allure.label("package", "src.shop_bot.database")
class TestInstructionDisplay:
    """Тесты для функций отображения инструкций"""

    @allure.title("Проверка наличия включенных инструкций: все отключены")
    @allure.description("""
    Проверяет, что функция has_any_instructions_enabled() возвращает False, когда все инструкции отключены.
    
    **Что проверяется:**
    - Все платформы (android, ios, windows, macos, linux) отключены
    - Видеоинструкции отключены
    - Функция возвращает False
    
    **Тестовые данные:**
    - Все get_instruction_display_setting возвращают False
    - get_video_instructions_display_setting возвращает False
    
    **Ожидаемый результат:**
    Функция has_any_instructions_enabled() возвращает False.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("instructions", "display", "database", "unit")
    @patch('shop_bot.data_manager.database.get_video_instructions_display_setting')
    @patch('shop_bot.data_manager.database.get_instruction_display_setting')
    def test_has_any_instructions_enabled_all_disabled(self, mock_get_instruction, mock_get_video):
        """Тест проверки наличия включенных инструкций: все отключены"""
        # Все инструкции отключены
        mock_get_instruction.return_value = False
        mock_get_video.return_value = False
        
        result = database.has_any_instructions_enabled()
        
        assert result is False
        # Проверяем, что функция проверила все платформы
        assert mock_get_instruction.call_count == 5
        assert mock_get_video.call_count == 1

    @allure.title("Проверка наличия включенных инструкций: одна платформа включена")
    @allure.description("""
    Проверяет, что функция has_any_instructions_enabled() возвращает True, когда хотя бы одна платформа включена.
    
    **Что проверяется:**
    - Платформа android включена
    - Остальные платформы отключены
    - Видеоинструкции отключены
    - Функция возвращает True
    
    **Тестовые данные:**
    - get_instruction_display_setting('android') возвращает True
    - Остальные платформы возвращают False
    - get_video_instructions_display_setting возвращает False
    
    **Ожидаемый результат:**
    Функция has_any_instructions_enabled() возвращает True.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("instructions", "display", "database", "unit")
    @patch('shop_bot.data_manager.database.get_video_instructions_display_setting')
    @patch('shop_bot.data_manager.database.get_instruction_display_setting')
    def test_has_any_instructions_enabled_one_platform_enabled(self, mock_get_instruction, mock_get_video):
        """Тест проверки наличия включенных инструкций: одна платформа включена"""
        # Android включен, остальные отключены
        def side_effect(platform):
            return platform == 'android'
        
        mock_get_instruction.side_effect = side_effect
        mock_get_video.return_value = False
        
        result = database.has_any_instructions_enabled()
        
        assert result is True

    @allure.title("Проверка наличия включенных инструкций: видеоинструкции включены")
    @allure.description("""
    Проверяет, что функция has_any_instructions_enabled() возвращает True, когда видеоинструкции включены.
    
    **Что проверяется:**
    - Все платформы отключены
    - Видеоинструкции включены
    - Функция возвращает True
    
    **Тестовые данные:**
    - Все get_instruction_display_setting возвращают False
    - get_video_instructions_display_setting возвращает True
    
    **Ожидаемый результат:**
    Функция has_any_instructions_enabled() возвращает True.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("instructions", "display", "video", "database", "unit")
    @patch('shop_bot.data_manager.database.get_video_instructions_display_setting')
    @patch('shop_bot.data_manager.database.get_instruction_display_setting')
    def test_has_any_instructions_enabled_video_enabled(self, mock_get_instruction, mock_get_video):
        """Тест проверки наличия включенных инструкций: видеоинструкции включены"""
        # Все платформы отключены, но видеоинструкции включены
        mock_get_instruction.return_value = False
        mock_get_video.return_value = True
        
        result = database.has_any_instructions_enabled()
        
        assert result is True

    @allure.title("Проверка наличия включенных инструкций: обработка ошибок")
    @allure.description("""
    Проверяет, что функция has_any_instructions_enabled() возвращает True при ошибке (безопасное поведение).
    
    **Что проверяется:**
    - Функция обрабатывает исключения
    - При ошибке возвращает True (чтобы не скрывать кнопку)
    
    **Тестовые данные:**
    - get_instruction_display_setting вызывает исключение
    
    **Ожидаемый результат:**
    Функция has_any_instructions_enabled() возвращает True при ошибке.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("instructions", "display", "error_handling", "database", "unit")
    @patch('shop_bot.data_manager.database.get_instruction_display_setting')
    def test_has_any_instructions_enabled_error_handling(self, mock_get_instruction):
        """Тест обработки ошибок в has_any_instructions_enabled"""
        # Вызываем исключение
        mock_get_instruction.side_effect = Exception("Database error")
        
        result = database.has_any_instructions_enabled()
        
        # При ошибке функция должна вернуть True (безопасное поведение)
        assert result is True

