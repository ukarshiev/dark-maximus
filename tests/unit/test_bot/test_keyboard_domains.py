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
from shop_bot.data_manager.database import update_setting, get_setting, is_production_server, is_development_server


@pytest.mark.unit
@pytest.mark.bot
@allure.epic("Обработчики бота")
@allure.feature("Клавиатуры")
@allure.label("package", "src.shop_bot.bot")
class TestKeyboardDomains:
    """Тесты для формирования клавиатур с использованием доменов"""

    @allure.title("Кнопка Настройка всегда отображается с фиксированным URL")
    @allure.description("""
    Проверяет, что кнопка "Настройка" всегда отображается с фиксированным URL независимо от настроек.
    
    **Что проверяется:**
    - Формирование кнопки "Настройка" через create_key_info_keyboard()
    - Использование фиксированного URL https://help.dark-maximus.com/setup
    - Независимость от настройки codex_docs_domain
    
    **Тестовые данные:**
    - key_id: 1
    
    **Ожидаемый результат:**
    Кнопка "Настройка" всегда содержит URL "https://help.dark-maximus.com/setup".
    """)
    @allure.severity(allure.severity_level.CRITICAL)
    @allure.tag("keyboard", "setup-button", "bot", "unit", "critical")
    def test_setup_button_always_present(self, temp_db):
        """Проверка что кнопка Настройка всегда отображается с фиксированным URL"""
        with allure.step("Формирование клавиатуры без настройки codex_docs_domain"):
            keyboard = create_key_info_keyboard(key_id=1)
            allure.attach(str(keyboard), "Сформированная клавиатура", allure.attachment_type.TEXT)
        
        with allure.step("Проверка наличия кнопки Настройка с фиксированным URL"):
            keyboard_dict = keyboard.model_dump() if hasattr(keyboard, 'model_dump') else str(keyboard)
            keyboard_str = str(keyboard_dict)
            assert "help.dark-maximus.com/setup" in keyboard_str or "https://help.dark-maximus.com/setup" in keyboard_str, \
                "Кнопка 'Настройка' должна всегда присутствовать с URL https://help.dark-maximus.com/setup"

    @allure.title("Кнопка Настройка отображается в development режиме")
    @allure.description("""
    Проверяет, что кнопка "Настройка" отображается даже в development режиме с фиксированным URL.
    
    **Что проверяется:**
    - Установка server_environment в "development"
    - Формирование кнопки "Настройка" через create_key_info_keyboard()
    - Наличие кнопки "Настройка" с фиксированным URL
    
    **Тестовые данные:**
    - server_environment: "development"
    - key_id: 1
    
    **Ожидаемый результат:**
    Кнопка "Настройка" отображается с URL "https://help.dark-maximus.com/setup" даже в development.
    """)
    @allure.severity(allure.severity_level.CRITICAL)
    @allure.tag("keyboard", "setup-button", "development", "bot", "unit", "critical")
    def test_setup_button_in_development(self, temp_db):
        """Проверка что кнопка Настройка отображается в development режиме"""
        with allure.step("Установка server_environment в development"):
            update_setting("server_environment", "development")
            allure.attach("development", "Установленное окружение", allure.attachment_type.TEXT)
        
        with allure.step("Проверка окружения"):
            assert is_development_server() is True
        
        with allure.step("Формирование клавиатуры"):
            keyboard = create_key_info_keyboard(key_id=1)
            allure.attach(str(keyboard), "Сформированная клавиатура", allure.attachment_type.TEXT)
        
        with allure.step("Проверка наличия кнопки Настройка"):
            keyboard_dict = keyboard.model_dump() if hasattr(keyboard, 'model_dump') else str(keyboard)
            keyboard_str = str(keyboard_dict)
            # Кнопка "Настройка" должна быть всегда, даже в development
            assert "help.dark-maximus.com/setup" in keyboard_str or "https://help.dark-maximus.com/setup" in keyboard_str, \
                "Кнопка 'Настройка' должна присутствовать даже в development режиме"

    @allure.title("Кнопка Настройка использует фиксированный URL независимо от настроек")
    @allure.description("""
    Проверяет, что кнопка "Настройка" использует фиксированный URL независимо от настройки codex_docs_domain.
    
    **Что проверяется:**
    - Установка codex_docs_domain с другим доменом
    - Формирование кнопки "Настройка" через create_key_info_keyboard()
    - Использование фиксированного URL https://help.dark-maximus.com/setup
    
    **Тестовые данные:**
    - codex_docs_domain: "help.example.com"
    - key_id: 1
    
    **Ожидаемый результат:**
    Кнопка "Настройка" игнорирует codex_docs_domain и использует фиксированный URL.
    """)
    @allure.severity(allure.severity_level.CRITICAL)
    @allure.tag("keyboard", "setup-button", "fixed-url", "bot", "unit", "critical")
    def test_setup_button_ignores_codex_docs_domain(self, temp_db):
        """Проверка что кнопка Настройка игнорирует настройку codex_docs_domain"""
        with allure.step("Установка codex_docs_domain с другим доменом"):
            update_setting("codex_docs_domain", "help.example.com")
            allure.attach("help.example.com", "Установленное значение", allure.attachment_type.TEXT)
        
        with allure.step("Формирование клавиатуры"):
            keyboard = create_key_info_keyboard(key_id=1)
            allure.attach(str(keyboard), "Сформированная клавиатура", allure.attachment_type.TEXT)
        
        with allure.step("Проверка использования фиксированного URL"):
            keyboard_dict = keyboard.model_dump() if hasattr(keyboard, 'model_dump') else str(keyboard)
            keyboard_str = str(keyboard_dict)
            # Кнопка должна использовать фиксированный URL, игнорируя настройку
            assert "help.dark-maximus.com/setup" in keyboard_str or "https://help.dark-maximus.com/setup" in keyboard_str, \
                "Кнопка 'Настройка' должна использовать фиксированный URL https://help.dark-maximus.com/setup"
            # Проверяем, что НЕ используется домен из настройки
            assert "help.example.com" not in keyboard_str, \
                "Кнопка 'Настройка' НЕ должна использовать домен из настройки codex_docs_domain"

    @allure.title("Кнопка Настройка содержит путь /setup")
    @allure.description("""
    Проверяет, что URL кнопки "Настройка" содержит путь /setup.
    
    **Что проверяется:**
    - Формирование кнопки "Настройка" через create_key_info_keyboard()
    - Наличие пути /setup в URL
    
    **Тестовые данные:**
    - key_id: 1
    
    **Ожидаемый результат:**
    URL кнопки "Настройка" содержит "/setup": "https://help.dark-maximus.com/setup".
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("keyboard", "setup-button", "setup-path", "bot", "unit")
    def test_setup_button_url_with_setup_path(self, temp_db):
        """Проверка что URL кнопки Настройка содержит путь /setup"""
        with allure.step("Формирование клавиатуры"):
            keyboard = create_key_info_keyboard(key_id=1)
            allure.attach(str(keyboard), "Сформированная клавиатура", allure.attachment_type.TEXT)
        
        with allure.step("Проверка наличия /setup в URL"):
            keyboard_dict = keyboard.model_dump() if hasattr(keyboard, 'model_dump') else str(keyboard)
            keyboard_str = str(keyboard_dict)
            # Проверяем, что URL содержит /setup
            assert "/setup" in keyboard_str, "URL кнопки 'Настройка' должен содержать путь /setup"
            assert "help.dark-maximus.com/setup" in keyboard_str or "https://help.dark-maximus.com/setup" in keyboard_str, \
                "URL должен быть https://help.dark-maximus.com/setup"

    @allure.title("Кнопка Настройка отображается в production режиме с фиксированным URL")
    @allure.description("""
    Проверяет, что кнопка "Настройка" отображается в production режиме с фиксированным URL.
    
    **Что проверяется:**
    - Установка server_environment в "production"
    - Формирование кнопки "Настройка" через create_key_info_keyboard()
    - Использование фиксированного URL https://help.dark-maximus.com/setup
    
    **Тестовые данные:**
    - server_environment: "production"
    - key_id: 1
    
    **Ожидаемый результат:**
    Кнопка "Настройка" содержит фиксированный URL "https://help.dark-maximus.com/setup".
    """)
    @allure.severity(allure.severity_level.CRITICAL)
    @allure.tag("keyboard", "setup-button", "production", "bot", "unit", "critical")
    def test_setup_button_in_production(self, temp_db):
        """Проверка что кнопка Настройка отображается в production режиме с фиксированным URL"""
        with allure.step("Установка server_environment в production"):
            update_setting("server_environment", "production")
            allure.attach("production", "Установленное окружение", allure.attachment_type.TEXT)
        
        with allure.step("Проверка окружения"):
            assert is_production_server() is True
        
        with allure.step("Формирование клавиатуры"):
            keyboard = create_key_info_keyboard(key_id=1)
            allure.attach(str(keyboard), "Сформированная клавиатура", allure.attachment_type.TEXT)
        
        with allure.step("Проверка URL кнопки Настройка"):
            keyboard_dict = keyboard.model_dump() if hasattr(keyboard, 'model_dump') else str(keyboard)
            keyboard_str = str(keyboard_dict)
            assert "help.dark-maximus.com/setup" in keyboard_str or "https://help.dark-maximus.com/setup" in keyboard_str, \
                "Кнопка 'Настройка' должна содержать фиксированный URL https://help.dark-maximus.com/setup"

    @allure.title("Кнопка Настройка отображается даже при локальном codex_docs_domain")
    @allure.description("""
    Проверяет, что кнопка "Настройка" отображается с фиксированным URL даже если codex_docs_domain локальный.
    
    **Что проверяется:**
    - Установка codex_docs_domain с локальным адресом
    - Формирование кнопки "Настройка" через create_key_info_keyboard()
    - Использование фиксированного URL вместо локального адреса
    
    **Тестовые данные:**
    - codex_docs_domain: "localhost:3001"
    - key_id: 1
    
    **Ожидаемый результат:**
    Кнопка "Настройка" отображается с фиксированным URL https://help.dark-maximus.com/setup.
    """)
    @allure.severity(allure.severity_level.CRITICAL)
    @allure.tag("keyboard", "setup-button", "localhost", "bot", "unit", "critical")
    def test_setup_button_with_localhost_domain(self, temp_db):
        """Проверка что кнопка Настройка отображается даже при локальном codex_docs_domain"""
        with allure.step("Установка codex_docs_domain с локальным адресом"):
            update_setting("codex_docs_domain", "localhost:3001")
            allure.attach("localhost:3001", "Установленное значение", allure.attachment_type.TEXT)
        
        with allure.step("Формирование клавиатуры"):
            keyboard = create_key_info_keyboard(key_id=1)
            allure.attach(str(keyboard), "Сформированная клавиатура", allure.attachment_type.TEXT)
        
        with allure.step("Проверка использования фиксированного URL вместо localhost"):
            keyboard_dict = keyboard.model_dump() if hasattr(keyboard, 'model_dump') else str(keyboard)
            keyboard_str = str(keyboard_dict)
            # Кнопка должна использовать фиксированный URL, игнорируя локальный адрес
            assert "help.dark-maximus.com/setup" in keyboard_str or "https://help.dark-maximus.com/setup" in keyboard_str, \
                "Кнопка 'Настройка' должна использовать фиксированный URL https://help.dark-maximus.com/setup"
            # Проверяем, что НЕ используется локальный адрес
            assert "localhost" not in keyboard_str, \
                "Кнопка 'Настройка' НЕ должна использовать локальный адрес"

    @allure.title("Кнопка Личный кабинет отображается только в production для режима cabinet")
    @allure.description("""
    Проверяет отображение кнопки "Личный кабинет" только в production режиме для ключей с режимом предоставления "cabinet".
    
    **Что проверяется:**
    - Установка server_environment в "production"
    - Создание ключа с режимом предоставления "cabinet"
    - Формирование кнопки "Личный кабинет" через create_key_info_keyboard()
    - Использование правильного URL из настроек
    - Проверка структуры клавиатуры и наличия кнопки
    
    **Тестовые данные:**
    - server_environment: "production"
    - user_cabinet_domain: "cabinet.example.com"
    - provision_mode: "cabinet"
    - key_id: создается динамически
    
    **Ожидаемый результат:**
    Кнопка "Личный кабинет" отображается в клавиатуре с правильным URL.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("keyboard", "cabinet", "production", "bot", "unit", "server-environment")
    def test_cabinet_button_in_production_cabinet_mode(self, temp_db):
        """Проверка отображения кнопки Личный кабинет в production для режима cabinet"""
        from shop_bot.data_manager.database import (
            register_user_if_not_exists, add_new_key, create_host, create_plan,
            update_setting, get_or_create_permanent_token
        )
        from shop_bot.config import get_user_cabinet_domain
        from datetime import datetime, timezone, timedelta
        from aiogram.types import InlineKeyboardButton
        
        with allure.step("Установка server_environment в production"):
            update_setting("server_environment", "production")
            allure.attach("production", "Установленное окружение", allure.attachment_type.TEXT)
        
        with allure.step("Установка user_cabinet_domain"):
            update_setting("user_cabinet_domain", "cabinet.example.com")
            allure.attach("cabinet.example.com", "Установленный домен", allure.attachment_type.TEXT)
        
        with allure.step("Создание тестовых данных"):
            user_id = 123456
            register_user_if_not_exists(user_id, "test_user", None)
            create_host("test_host", "https://test-host.example.com", "admin", "password", 0, "test_host_code")
            create_plan(
                host_name="test_host",
                plan_name="Test Plan Cabinet",
                months=1,
                days=0,
                price=100.0,
                key_provision_mode="cabinet"
            )
            
            expiry_date = datetime.now(timezone.utc) + timedelta(days=30)
            expiry_ms = int(expiry_date.timestamp() * 1000)
            
            key_id = add_new_key(
                user_id=user_id,
                host_name="test_host",
                xui_client_uuid="test-uuid-123",
                key_email=f"test_{user_id}@test.com",
                expiry_timestamp_ms=expiry_ms,
                connection_string="",
                plan_name="Test Plan Cabinet",
                price=100.0,
                protocol='vless',
                is_trial=0
            )
            allure.attach(str(key_id), "Созданный key_id", allure.attachment_type.TEXT)
        
        with allure.step("Проверка окружения"):
            assert is_production_server() is True, "Окружение должно быть production"
            allure.attach("production", "Проверенное окружение", allure.attachment_type.TEXT)
        
        with allure.step("Проверка настроек домена"):
            cabinet_domain = get_user_cabinet_domain()
            assert cabinet_domain is not None, "Домен личного кабинета должен быть настроен"
            assert "cabinet.example.com" in cabinet_domain, f"Домен должен содержать 'cabinet.example.com', получен: {cabinet_domain}"
            allure.attach(cabinet_domain, "Полученный домен", allure.attachment_type.TEXT)
        
        with allure.step("Проверка создания токена"):
            cabinet_token = get_or_create_permanent_token(user_id, key_id)
            assert cabinet_token is not None, "Токен должен быть создан"
            assert len(cabinet_token) > 0, "Токен не должен быть пустым"
            allure.attach(cabinet_token[:20] + "...", "Созданный токен (первые 20 символов)", allure.attachment_type.TEXT)
        
        with allure.step("Формирование клавиатуры"):
            keyboard = create_key_info_keyboard(key_id=key_id)
            keyboard_dict = keyboard.model_dump() if hasattr(keyboard, 'model_dump') else None
            allure.attach(str(keyboard_dict) if keyboard_dict else str(keyboard), "Сформированная клавиатура", allure.attachment_type.TEXT)
        
        with allure.step("Проверка структуры клавиатуры"):
            # Проверяем, что клавиатура имеет структуру inline_keyboard
            assert hasattr(keyboard, 'inline_keyboard'), "Клавиатура должна иметь атрибут inline_keyboard"
            assert keyboard.inline_keyboard is not None, "inline_keyboard не должен быть None"
            assert len(keyboard.inline_keyboard) > 0, "Клавиатура должна содержать хотя бы один ряд кнопок"
            allure.attach(str(len(keyboard.inline_keyboard)), "Количество рядов кнопок", allure.attachment_type.TEXT)
        
        with allure.step("Поиск кнопки Личный кабинет в структуре клавиатуры"):
            cabinet_button_found = False
            cabinet_button_url = None
            cabinet_button_text = None
            
            for row in keyboard.inline_keyboard:
                for button in row:
                    # Проверяем текст кнопки
                    button_text = button.text if hasattr(button, 'text') else str(button)
                    if "Личный кабинет" in button_text or "🗂️" in button_text:
                        cabinet_button_found = True
                        cabinet_button_text = button_text
                        # Проверяем URL кнопки
                        if hasattr(button, 'url') and button.url:
                            cabinet_button_url = button.url
                        break
                if cabinet_button_found:
                    break
            
            assert cabinet_button_found, "Кнопка 'Личный кабинет' должна быть найдена в клавиатуре"
            assert cabinet_button_text is not None, "Текст кнопки должен быть определен"
            allure.attach(cabinet_button_text, "Текст найденной кнопки", allure.attachment_type.TEXT)
        
        with allure.step("Проверка URL кнопки Личный кабинет"):
            assert cabinet_button_url is not None, "URL кнопки должен быть определен"
            assert "cabinet.example.com" in cabinet_button_url, f"URL должен содержать 'cabinet.example.com', получен: {cabinet_button_url}"
            assert cabinet_button_url.startswith("https://"), f"URL должен начинаться с 'https://', получен: {cabinet_button_url}"
            # Проверяем, что URL содержит токен или корневой путь
            assert "/auth/" in cabinet_button_url or cabinet_button_url.endswith("/"), f"URL должен содержать '/auth/' или заканчиваться '/', получен: {cabinet_button_url}"
            allure.attach(cabinet_button_url, "URL кнопки Личный кабинет", allure.attachment_type.TEXT)

    @allure.title("Кнопка Личный кабинет не отображается в development режиме")
    @allure.description("""
    Проверяет, что кнопка "Личный кабинет" не отображается в development режиме даже для ключей с режимом предоставления "cabinet".
    
    **Что проверяется:**
    - Установка server_environment в "development"
    - Создание ключа с режимом предоставления "cabinet"
    - Формирование клавиатуры через create_key_info_keyboard()
    - Отсутствие кнопки "Личный кабинет"
    
    **Тестовые данные:**
    - server_environment: "development"
    - user_cabinet_domain: "https://cabinet.example.com"
    - provision_mode: "cabinet"
    - key_id: 1
    
    **Ожидаемый результат:**
    Кнопка "Личный кабинет" не отображается в клавиатуре (только в production).
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("keyboard", "cabinet", "development", "bot", "unit", "server-environment")
    def test_cabinet_button_not_in_development(self, temp_db):
        """Проверка отсутствия кнопки Личный кабинет в development режиме"""
        from shop_bot.data_manager.database import (
            register_user_if_not_exists, add_new_key, create_host, create_plan,
            update_setting
        )
        from datetime import datetime, timezone, timedelta
        
        with allure.step("Установка server_environment в development"):
            update_setting("server_environment", "development")
            allure.attach("development", "Установленное окружение", allure.attachment_type.TEXT)
        
        with allure.step("Установка user_cabinet_domain"):
            update_setting("user_cabinet_domain", "cabinet.example.com")
            allure.attach("cabinet.example.com", "Установленный домен", allure.attachment_type.TEXT)
        
        with allure.step("Создание тестовых данных"):
            user_id = 123457
            register_user_if_not_exists(user_id, "test_user", None)
            create_host("test_host_dev", "https://test-host-dev.example.com", "admin", "password", 0, "test_host_code_dev")
            create_plan(
                host_name="test_host_dev",
                plan_name="Test Plan Cabinet Dev",
                months=1,
                days=0,
                price=100.0,
                key_provision_mode="cabinet"
            )
            
            expiry_date = datetime.now(timezone.utc) + timedelta(days=30)
            expiry_ms = int(expiry_date.timestamp() * 1000)
            
            key_id = add_new_key(
                user_id=user_id,
                host_name="test_host_dev",
                xui_client_uuid="test-uuid-456",
                key_email=f"test_{user_id}@test.com",
                expiry_timestamp_ms=expiry_ms,
                connection_string="",
                plan_name="Test Plan Cabinet Dev",
                price=100.0,
                protocol='vless',
                is_trial=0
            )
            allure.attach(str(key_id), "Созданный key_id", allure.attachment_type.TEXT)
        
        with allure.step("Проверка окружения"):
            assert is_development_server() is True
        
        with allure.step("Формирование клавиатуры"):
            keyboard = create_key_info_keyboard(key_id=key_id)
            allure.attach(str(keyboard), "Сформированная клавиатура", allure.attachment_type.TEXT)
        
        with allure.step("Проверка отсутствия кнопки Личный кабинет"):
            keyboard_dict = keyboard.model_dump() if hasattr(keyboard, 'model_dump') else str(keyboard)
            keyboard_str = str(keyboard_dict)
            # В development кнопка "Личный кабинет" не должна отображаться
            assert "Личный кабинет" not in keyboard_str

    @allure.title("Кнопка Личный кабинет не отображается для режима key")
    @allure.description("""
    Проверяет, что кнопка "Личный кабинет" не отображается для ключей с режимом предоставления "key" даже в production.
    
    **Что проверяется:**
    - Установка server_environment в "production"
    - Создание ключа с режимом предоставления "key"
    - Формирование клавиатуры через create_key_info_keyboard()
    - Отсутствие кнопки "Личный кабинет"
    
    **Тестовые данные:**
    - server_environment: "production"
    - user_cabinet_domain: "https://cabinet.example.com"
    - provision_mode: "key"
    - key_id: 1
    
    **Ожидаемый результат:**
    Кнопка "Личный кабинет" не отображается в клавиатуре (только для режимов cabinet/cabinet_subscription).
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("keyboard", "cabinet", "provision_mode", "bot", "unit", "server-environment")
    def test_cabinet_button_not_for_key_mode(self, temp_db):
        """Проверка отсутствия кнопки Личный кабинет для режима key"""
        from shop_bot.data_manager.database import (
            register_user_if_not_exists, add_new_key, create_host, create_plan,
            update_setting
        )
        from datetime import datetime, timezone, timedelta
        
        with allure.step("Установка server_environment в production"):
            update_setting("server_environment", "production")
            allure.attach("production", "Установленное окружение", allure.attachment_type.TEXT)
        
        with allure.step("Установка user_cabinet_domain"):
            update_setting("user_cabinet_domain", "cabinet.example.com")
            allure.attach("cabinet.example.com", "Установленный домен", allure.attachment_type.TEXT)
        
        with allure.step("Создание тестовых данных с режимом key"):
            user_id = 123458
            register_user_if_not_exists(user_id, "test_user", None)
            create_host("test_host_key", "https://test-host-key.example.com", "admin", "password", 0, "test_host_code_key")
            create_plan(
                host_name="test_host_key",
                plan_name="Test Plan Key",
                months=1,
                days=0,
                price=100.0,
                key_provision_mode="key"
            )
            
            expiry_date = datetime.now(timezone.utc) + timedelta(days=30)
            expiry_ms = int(expiry_date.timestamp() * 1000)
            
            key_id = add_new_key(
                user_id=user_id,
                host_name="test_host_key",
                xui_client_uuid="test-uuid-789",
                key_email=f"test_{user_id}@test.com",
                expiry_timestamp_ms=expiry_ms,
                connection_string="vless://test",
                plan_name="Test Plan Key",
                price=100.0,
                protocol='vless',
                is_trial=0
            )
            allure.attach(str(key_id), "Созданный key_id", allure.attachment_type.TEXT)
        
        with allure.step("Проверка окружения"):
            assert is_production_server() is True
        
        with allure.step("Формирование клавиатуры"):
            keyboard = create_key_info_keyboard(key_id=key_id)
            allure.attach(str(keyboard), "Сформированная клавиатура", allure.attachment_type.TEXT)
        
        with allure.step("Проверка отсутствия кнопки Личный кабинет"):
            keyboard_dict = keyboard.model_dump() if hasattr(keyboard, 'model_dump') else str(keyboard)
            keyboard_str = str(keyboard_dict)
            # Для режима "key" кнопка "Личный кабинет" не должна отображаться
            assert "Личный кабинет" not in keyboard_str

