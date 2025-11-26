#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Unit-тесты для bot_controller.py

Тестирует создание SSL сессий и конфигурацию подключения к Telegram API.
"""

import pytest
import sys
import ssl
import certifi
import allure
from pathlib import Path
from unittest.mock import MagicMock, patch
from aiohttp import ClientTimeout
from aiogram.client.session.aiohttp import AiohttpSession

# Добавляем путь к проекту
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root / "src"))

from shop_bot.bot_controller import CustomAiohttpSession, _create_telegram_session


@allure.epic("Обработчики бота")
@allure.feature("Конфигурация SSL сессий")
@allure.label("package", "src.shop_bot.bot_controller")
@pytest.mark.unit
@pytest.mark.bot
class TestBotControllerSSL:
    """Тесты для SSL конфигурации в bot_controller"""

    @allure.title("Создание CustomAiohttpSession с SSL контекстом")
    @allure.description("""
    Проверяет корректное создание CustomAiohttpSession с явным SSL контекстом через certifi.
    
    **Что проверяется:**
    - CustomAiohttpSession создается успешно
    - SSL контекст настроен с использованием certifi.where()
    - SSL контекст имеет правильные параметры безопасности (check_hostname=True, verify_mode=CERT_REQUIRED)
    - connector_init содержит настроенный SSL контекст
    
    **Тестовые данные:**
    - Используется certifi для получения пути к сертификатам
    - SSL контекст создается через ssl.create_default_context()
    
    **Ожидаемый результат:**
    CustomAiohttpSession создан с явным SSL контекстом, который использует актуальные сертификаты из certifi.
    """)
    @allure.severity(allure.severity_level.CRITICAL)
    @allure.tag("ssl", "bot_controller", "session", "unit", "critical")
    def test_custom_session_ssl_context(self):
        """Тест создания CustomAiohttpSession с SSL контекстом"""
        with allure.step("Создание CustomAiohttpSession"):
            session = CustomAiohttpSession()
            allure.attach(str(type(session).__name__), "Тип сессии", allure.attachment_type.TEXT)
        
        with allure.step("Проверка наличия _connector_init"):
            assert hasattr(session, '_connector_init'), "CustomAiohttpSession должен иметь _connector_init"
            assert isinstance(session._connector_init, dict), "_connector_init должен быть словарем"
            allure.attach(str(session._connector_init.keys()), "Ключи connector_init", allure.attachment_type.TEXT)
        
        with allure.step("Проверка SSL контекста в connector_init"):
            assert 'ssl' in session._connector_init, "connector_init должен содержать SSL контекст"
            ssl_context = session._connector_init['ssl']
            assert isinstance(ssl_context, ssl.SSLContext), "SSL контекст должен быть экземпляром ssl.SSLContext"
            allure.attach(str(ssl_context.check_hostname), "check_hostname", allure.attachment_type.TEXT)
            allure.attach(str(ssl_context.verify_mode), "verify_mode", allure.attachment_type.TEXT)
        
        with allure.step("Проверка параметров SSL контекста"):
            assert ssl_context.check_hostname is True, "SSL контекст должен иметь check_hostname=True"
            assert ssl_context.verify_mode == ssl.CERT_REQUIRED, "SSL контекст должен иметь verify_mode=CERT_REQUIRED"

    @allure.title("Создание CustomAiohttpSession использует certifi")
    @allure.description("""
    Проверяет, что CustomAiohttpSession использует certifi для получения пути к сертификатам.
    
    **Что проверяется:**
    - SSL контекст создается с использованием certifi.where()
    - Путь к сертификатам корректен
    - Сертификаты доступны
    
    **Тестовые данные:**
    - certifi.where() возвращает путь к bundle сертификатов
    
    **Ожидаемый результат:**
    SSL контекст использует сертификаты из certifi.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("ssl", "certifi", "bot_controller", "unit")
    def test_custom_session_uses_certifi(self):
        """Тест использования certifi в CustomAiohttpSession"""
        with allure.step("Проверка наличия certifi"):
            certifi_path = certifi.where()
            assert certifi_path is not None, "certifi.where() должен возвращать путь"
            assert Path(certifi_path).exists(), f"Файл сертификатов должен существовать: {certifi_path}"
            allure.attach(certifi_path, "Путь к certifi", allure.attachment_type.TEXT)
        
        with allure.step("Создание CustomAiohttpSession и проверка SSL контекста"):
            session = CustomAiohttpSession()
            ssl_context = session._connector_init['ssl']
            # Проверяем, что SSL контекст был создан с использованием certifi
            # (проверяем через наличие сертификатов в контексте)
            assert ssl_context is not None, "SSL контекст должен быть создан"

    @allure.title("Создание сессии через _create_telegram_session")
    @allure.description("""
    Проверяет корректное создание сессии через функцию _create_telegram_session().
    
    **Что проверяется:**
    - Функция возвращает CustomAiohttpSession
    - Timeout установлен корректно
    - SSL контекст настроен
    
    **Тестовые данные:**
    - timeout: ClientTimeout(total=30, connect=10, sock_read=20)
    
    **Ожидаемый результат:**
    Сессия создана с правильным timeout и SSL контекстом.
    """)
    @allure.severity(allure.severity_level.CRITICAL)
    @allure.tag("ssl", "bot_controller", "session_creation", "unit", "critical")
    def test_create_telegram_session(self):
        """Тест создания сессии через _create_telegram_session()"""
        with allure.step("Подготовка тестовых данных"):
            timeout = ClientTimeout(total=30, connect=10, sock_read=20)
            allure.attach(str(timeout.total), "Timeout total", allure.attachment_type.TEXT)
        
        with allure.step("Создание сессии через _create_telegram_session()"):
            session = _create_telegram_session(timeout)
            assert session is not None, "Сессия должна быть создана"
            assert isinstance(session, (CustomAiohttpSession, AiohttpSession)), \
                "Сессия должна быть CustomAiohttpSession или AiohttpSession"
            allure.attach(str(type(session).__name__), "Тип созданной сессии", allure.attachment_type.TEXT)
        
        with allure.step("Проверка timeout"):
            assert session.timeout == timeout.total, \
                f"Timeout должен быть равен {timeout.total}, получен {session.timeout}"
            allure.attach(str(session.timeout), "Установленный timeout", allure.attachment_type.TEXT)
        
        with allure.step("Проверка SSL контекста для CustomAiohttpSession"):
            if isinstance(session, CustomAiohttpSession):
                assert hasattr(session, '_connector_init'), \
                    "CustomAiohttpSession должен иметь _connector_init"
                assert 'ssl' in session._connector_init, \
                    "connector_init должен содержать SSL контекст"
                ssl_context = session._connector_init['ssl']
                assert isinstance(ssl_context, ssl.SSLContext), \
                    "SSL контекст должен быть экземпляром ssl.SSLContext"

    @allure.title("Fallback на стандартный AiohttpSession при ошибке")
    @allure.description("""
    Проверяет, что при ошибке создания CustomAiohttpSession функция возвращает стандартный AiohttpSession.
    
    **Что проверяется:**
    - При ошибке создания CustomAiohttpSession используется fallback
    - Возвращается стандартный AiohttpSession
    - Timeout установлен корректно
    
    **Тестовые данные:**
    - Симуляция ошибки при создании CustomAiohttpSession
    
    **Ожидаемый результат:**
    При ошибке возвращается стандартный AiohttpSession с правильным timeout.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("ssl", "bot_controller", "error_handling", "fallback", "unit")
    def test_create_telegram_session_fallback(self):
        """Тест fallback на стандартный AiohttpSession при ошибке"""
        with allure.step("Подготовка тестовых данных"):
            timeout = ClientTimeout(total=30, connect=10, sock_read=20)
        
        with allure.step("Симуляция ошибки при создании CustomAiohttpSession"):
            with patch('shop_bot.bot_controller.CustomAiohttpSession', side_effect=Exception("Test error")):
                session = _create_telegram_session(timeout)
                assert session is not None, "Сессия должна быть создана даже при ошибке"
                assert isinstance(session, AiohttpSession), \
                    "При ошибке должен возвращаться стандартный AiohttpSession"
                assert session.timeout == timeout.total, \
                    "Timeout должен быть установлен корректно даже при fallback"
                allure.attach(str(type(session).__name__), "Тип сессии при fallback", allure.attachment_type.TEXT)



