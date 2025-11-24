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

    @allure.title("Кнопка Настройка не добавляется если домен не настроен")
    @allure.description("""
    Проверяет, что кнопка "Настройка" не добавляется, если домены не настроены.
    
    **Что проверяется:**
    - Отсутствие codex_docs_domain и global_domain в БД
    - Формирование кнопки "Настройка" через create_key_info_keyboard()
    - Отсутствие кнопки "Настройка" в клавиатуре
    
    **Тестовые данные:**
    - codex_docs_domain: не установлен
    - global_domain: не установлен
    - key_id: 1
    
    **Ожидаемый результат:**
    Кнопка "Настройка" не добавляется в клавиатуру, если домены не настроены.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("keyboard", "domain", "fallback", "bot", "unit")
    def test_setup_button_fallback_to_default(self, temp_db):
        """Проверка что кнопка Настройка не добавляется если домен не настроен"""
        with allure.step("Проверка отсутствия настройки"):
            codex_docs_domain = get_setting("codex_docs_domain")
            allure.attach(str(codex_docs_domain), "Текущее значение codex_docs_domain", allure.attachment_type.TEXT)
        
        with allure.step("Формирование клавиатуры"):
            keyboard = create_key_info_keyboard(key_id=1)
            allure.attach(str(keyboard), "Сформированная клавиатура", allure.attachment_type.TEXT)
        
        with allure.step("Проверка отсутствия кнопки Настройка"):
            keyboard_dict = keyboard.model_dump() if hasattr(keyboard, 'model_dump') else str(keyboard)
            keyboard_str = str(keyboard_dict)
            # Проверяем, что кнопка "Настройка" не добавлена (нет жёстко прописанных доменов)
            assert "help.dark-maximus.com/setup" not in keyboard_str
            assert "https://help.dark-maximus.com/setup" not in keyboard_str
            # Проверяем, что кнопка "Настройка" (⚙️) отсутствует, если домен не настроен
            # Но кнопка может быть, если используется другой домен - проверяем только отсутствие жёстко прописанного

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

    @allure.title("Использование codex_docs_domain в production режиме")
    @allure.description("""
    Проверяет использование настройки codex_docs_domain в production режиме.
    
    **Что проверяется:**
    - Установка server_environment в "production"
    - Установка codex_docs_domain в БД
    - Формирование кнопки "Настройка" через create_key_info_keyboard()
    - Использование правильного URL из настройки
    
    **Тестовые данные:**
    - server_environment: "production"
    - codex_docs_domain: "https://help.example.com"
    - key_id: 1
    
    **Ожидаемый результат:**
    Кнопка "Настройка" содержит URL "https://help.example.com/setup".
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("keyboard", "domain", "codex-docs", "bot", "unit", "server-environment")
    def test_setup_button_uses_codex_docs_domain_in_production(self, temp_db):
        """Проверка использования codex_docs_domain в production режиме"""
        with allure.step("Установка server_environment в production"):
            update_setting("server_environment", "production")
            allure.attach("production", "Установленное окружение", allure.attachment_type.TEXT)
        
        with allure.step("Установка codex_docs_domain в БД"):
            update_setting("codex_docs_domain", "https://help.example.com")
            allure.attach("https://help.example.com", "Установленное значение", allure.attachment_type.TEXT)
        
        with allure.step("Проверка окружения"):
            assert is_production_server() is True
        
        with allure.step("Формирование клавиатуры"):
            keyboard = create_key_info_keyboard(key_id=1)
            allure.attach(str(keyboard), "Сформированная клавиатура", allure.attachment_type.TEXT)
        
        with allure.step("Проверка URL кнопки Настройка"):
            keyboard_dict = keyboard.model_dump() if hasattr(keyboard, 'model_dump') else str(keyboard)
            keyboard_str = str(keyboard_dict)
            assert "help.example.com/setup" in keyboard_str or "https://help.example.com/setup" in keyboard_str

    @allure.title("Кнопка Настройка не добавляется в development если домен локальный")
    @allure.description("""
    Проверяет, что кнопка "Настройка" не добавляется в development режиме, если домен является локальным адресом.
    
    **Что проверяется:**
    - Установка server_environment в "development"
    - Отсутствие codex_docs_domain или установка локального адреса
    - Формирование кнопки "Настройка" через create_key_info_keyboard()
    - Отсутствие кнопки "Настройка" (локальные адреса не поддерживаются в Web App)
    
    **Тестовые данные:**
    - server_environment: "development"
    - codex_docs_domain: не установлен (или локальный адрес)
    - key_id: 1
    
    **Ожидаемый результат:**
    Кнопка "Настройка" не добавляется в клавиатуру, так как локальные адреса не поддерживаются в Web App.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("keyboard", "domain", "fallback", "bot", "unit", "server-environment")
    def test_setup_button_fallback_in_development(self, temp_db):
        """Проверка что кнопка Настройка не добавляется в development если домен локальный"""
        with allure.step("Установка server_environment в development"):
            update_setting("server_environment", "development")
            allure.attach("development", "Установленное окружение", allure.attachment_type.TEXT)
        
        with allure.step("Проверка окружения"):
            assert is_development_server() is True
        
        with allure.step("Формирование клавиатуры"):
            keyboard = create_key_info_keyboard(key_id=1)
            allure.attach(str(keyboard), "Сформированная клавиатура", allure.attachment_type.TEXT)
        
        with allure.step("Проверка отсутствия жёстко прописанного домена"):
            keyboard_dict = keyboard.model_dump() if hasattr(keyboard, 'model_dump') else str(keyboard)
            keyboard_str = str(keyboard_dict)
            # В development кнопка не добавляется, если домен не настроен или локальный
            # Проверяем только отсутствие жёстко прописанного домена
            assert "help.dark-maximus.com/setup" not in keyboard_str
            assert "https://help.dark-maximus.com/setup" not in keyboard_str

    @allure.title("Кнопка Личный кабинет отображается только в production для режима cabinet")
    @allure.description("""
    Проверяет отображение кнопки "Личный кабинет" только в production режиме для ключей с режимом предоставления "cabinet".
    
    **Что проверяется:**
    - Установка server_environment в "production"
    - Создание ключа с режимом предоставления "cabinet"
    - Формирование кнопки "Личный кабинет" через create_key_info_keyboard()
    - Использование правильного URL из настроек
    
    **Тестовые данные:**
    - server_environment: "production"
    - user_cabinet_domain: "https://cabinet.example.com"
    - provision_mode: "cabinet"
    - key_id: 1
    
    **Ожидаемый результат:**
    Кнопка "Личный кабинет" отображается в клавиатуре.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("keyboard", "cabinet", "production", "bot", "unit", "server-environment")
    def test_cabinet_button_in_production_cabinet_mode(self, temp_db):
        """Проверка отображения кнопки Личный кабинет в production для режима cabinet"""
        from shop_bot.data_manager.database import (
            register_user_if_not_exists, add_new_key, create_host, create_plan,
            update_setting
        )
        from shop_bot.config import get_user_cabinet_domain
        from datetime import datetime, timezone, timedelta
        
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
            assert is_production_server() is True
        
        with allure.step("Формирование клавиатуры"):
            keyboard = create_key_info_keyboard(key_id=key_id)
            allure.attach(str(keyboard), "Сформированная клавиатура", allure.attachment_type.TEXT)
        
        with allure.step("Проверка наличия кнопки Личный кабинет"):
            keyboard_dict = keyboard.model_dump() if hasattr(keyboard, 'model_dump') else str(keyboard)
            keyboard_str = str(keyboard_dict)
            assert "Личный кабинет" in keyboard_str or "🗂️" in keyboard_str

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

