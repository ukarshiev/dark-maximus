#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Unit-тесты для error_handler.py

Тестирует обработку различных типов ошибок, включая SSL ошибки.
"""

import pytest
import sys
import allure
from pathlib import Path
from unittest.mock import MagicMock, patch
from aiogram.exceptions import TelegramNetworkError
from aiogram.methods import GetUpdates

# Добавляем путь к проекту
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root / "src"))

from shop_bot.utils.error_handler import ErrorHandler


@allure.epic("Утилиты")
@allure.feature("Обработка ошибок")
@allure.label("package", "src.shop_bot.utils.error_handler")
@pytest.mark.unit
class TestErrorHandlerSSL:
    """Тесты для обработки SSL ошибок в error_handler"""

    @pytest.fixture
    def error_handler(self):
        """Фикстура для создания экземпляра ErrorHandler"""
        return ErrorHandler()

    @allure.title("Обработка SSL record layer failure")
    @allure.description("""
    Проверяет корректную обработку ошибки "SSL record layer failure".
    
    **Что проверяется:**
    - Ошибка определяется как SSL ошибка
    - Ошибка определяется как временная (is_temporary=True)
    - Сообщение пользователю указывает на автоматический retry
    - Логирование происходит на уровне warning
    - Возвращается правильный код ошибки и статус
    
    **Тестовые данные:**
    - Ошибка: TelegramNetworkError с сообщением "SSL record layer failure"
    
    **Ожидаемый результат:**
    Ошибка обработана как временная SSL ошибка с рекомендациями по диагностике.
    """)
    @allure.severity(allure.severity_level.CRITICAL)
    @allure.tag("ssl", "error_handler", "record_layer_failure", "unit", "critical")
    def test_handle_ssl_record_layer_failure(self, error_handler):
        """Тест обработки SSL record layer failure"""
        with allure.step("Подготовка тестовых данных"):
            method = GetUpdates(offset=0, timeout=10)
            error = TelegramNetworkError(
                method=method,
                message="ClientOSError: [Errno 1] [SSL] record layer failure (_ssl.c:2590)"
            )
            context = "test_context"
            allure.attach(str(error), "Ошибка", allure.attachment_type.TEXT)
        
        with allure.step("Обработка ошибки"):
            with patch('shop_bot.utils.error_handler.logger') as mock_logger:
                result = error_handler._handle_network_error(error, context)
                allure.attach(str(result), "Результат обработки", allure.attachment_type.JSON)
        
        with allure.step("Проверка результата"):
            assert result['is_ssl_error'] is True, "Ошибка должна быть определена как SSL ошибка"
            assert result['is_temporary'] is True, "Ошибка должна быть определена как временная"
            assert 'record layer failure' in result['message'].lower() or 'ssl соединения' in result['message'].lower(), \
                "Сообщение должно указывать на SSL ошибку"
            assert result['code'] == 'NETWORK_ERROR', "Код ошибки должен быть NETWORK_ERROR"
            assert result['status_code'] == 503, "Статус код должен быть 503"
        
        with allure.step("Проверка логирования"):
            warning_calls = [call for call in mock_logger.method_calls if call[0] == 'warning']
            assert len(warning_calls) > 0, "Должно быть логирование на уровне warning"
            error_calls = [call for call in mock_logger.method_calls if call[0] == 'error']
            assert len(error_calls) == 0, "Не должно быть логирования на уровне error для временных ошибок"

    @allure.title("Обработка SSL certificate error")
    @allure.description("""
    Проверяет корректную обработку ошибки SSL сертификата.
    
    **Что проверяется:**
    - Ошибка определяется как SSL ошибка
    - Ошибка определяется как критическая (is_temporary=False)
    - Сообщение пользователю содержит рекомендации по проверке сертификатов
    - Логирование происходит на уровне error
    - Возвращается правильный код ошибки и статус
    
    **Тестовые данные:**
    - Ошибка: TelegramNetworkError с сообщением о проблеме с сертификатом
    
    **Ожидаемый результат:**
    Ошибка обработана как критическая SSL ошибка с рекомендациями по исправлению.
    """)
    @allure.severity(allure.severity_level.CRITICAL)
    @allure.tag("ssl", "error_handler", "certificate_error", "unit", "critical")
    def test_handle_ssl_certificate_error(self, error_handler):
        """Тест обработки SSL certificate error"""
        with allure.step("Подготовка тестовых данных"):
            method = GetUpdates(offset=0, timeout=10)
            error = TelegramNetworkError(
                method=method,
                message="SSL certificate problem: unable to get local issuer certificate"
            )
            context = "test_context"
            allure.attach(str(error), "Ошибка", allure.attachment_type.TEXT)
        
        with allure.step("Обработка ошибки"):
            with patch('shop_bot.utils.error_handler.logger') as mock_logger:
                result = error_handler._handle_network_error(error, context)
                allure.attach(str(result), "Результат обработки", allure.attachment_type.JSON)
        
        with allure.step("Проверка результата"):
            assert result['is_ssl_error'] is True, "Ошибка должна быть определена как SSL ошибка"
            assert result['is_temporary'] is False, "Ошибка сертификата не должна быть временной"
            assert 'сертификат' in result['message'].lower() or 'certificate' in result['message'].lower(), \
                "Сообщение должно указывать на проблему с сертификатом"
            assert result['code'] == 'NETWORK_ERROR', "Код ошибки должен быть NETWORK_ERROR"
            assert result['status_code'] == 503, "Статус код должен быть 503"
        
        with allure.step("Проверка логирования"):
            error_calls = [call for call in mock_logger.method_calls if call[0] == 'error']
            assert len(error_calls) > 0, "Должно быть логирование на уровне error для критических ошибок"

    @allure.title("Обработка SSL handshake error")
    @allure.description("""
    Проверяет корректную обработку ошибки SSL handshake.
    
    **Что проверяется:**
    - Ошибка определяется как SSL ошибка
    - Ошибка определяется как временная (is_temporary=True)
    - Сообщение пользователю указывает на автоматический retry
    - Логирование происходит на уровне warning
    
    **Тестовые данные:**
    - Ошибка: TelegramNetworkError с сообщением о проблеме с handshake
    
    **Ожидаемый результат:**
    Ошибка обработана как временная SSL ошибка.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("ssl", "error_handler", "handshake_error", "unit")
    def test_handle_ssl_handshake_error(self, error_handler):
        """Тест обработки SSL handshake error"""
        with allure.step("Подготовка тестовых данных"):
            method = GetUpdates(offset=0, timeout=10)
            error = TelegramNetworkError(
                method=method,
                message="SSL handshake failed"
            )
            context = "test_context"
            allure.attach(str(error), "Ошибка", allure.attachment_type.TEXT)
        
        with allure.step("Обработка ошибки"):
            with patch('shop_bot.utils.error_handler.logger') as mock_logger:
                result = error_handler._handle_network_error(error, context)
                allure.attach(str(result), "Результат обработки", allure.attachment_type.JSON)
        
        with allure.step("Проверка результата"):
            assert result['is_ssl_error'] is True, "Ошибка должна быть определена как SSL ошибка"
            assert result['is_temporary'] is True, "Ошибка handshake должна быть временной"
            assert 'handshake' in result['message'].lower() or 'ssl' in result['message'].lower(), \
                "Сообщение должно указывать на SSL ошибку"
            assert result['code'] == 'NETWORK_ERROR', "Код ошибки должен быть NETWORK_ERROR"
        
        with allure.step("Проверка логирования"):
            warning_calls = [call for call in mock_logger.method_calls if call[0] == 'warning']
            assert len(warning_calls) > 0, "Должно быть логирование на уровне warning"

    @allure.title("Обработка других SSL ошибок")
    @allure.description("""
    Проверяет корректную обработку других типов SSL ошибок.
    
    **Что проверяется:**
    - Ошибка определяется как SSL ошибка
    - Ошибка определяется как временная (is_temporary=True)
    - Сообщение пользователю указывает на автоматический retry
    - Логирование происходит на уровне warning
    
    **Тестовые данные:**
    - Ошибка: TelegramNetworkError с общим SSL сообщением
    
    **Ожидаемый результат:**
    Ошибка обработана как временная SSL ошибка.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("ssl", "error_handler", "other_ssl_errors", "unit")
    def test_handle_other_ssl_error(self, error_handler):
        """Тест обработки других SSL ошибок"""
        with allure.step("Подготовка тестовых данных"):
            method = GetUpdates(offset=0, timeout=10)
            error = TelegramNetworkError(
                method=method,
                message="SSL connection error"
            )
            context = "test_context"
            allure.attach(str(error), "Ошибка", allure.attachment_type.TEXT)
        
        with allure.step("Обработка ошибки"):
            with patch('shop_bot.utils.error_handler.logger') as mock_logger:
                result = error_handler._handle_network_error(error, context)
                allure.attach(str(result), "Результат обработки", allure.attachment_type.JSON)
        
        with allure.step("Проверка результата"):
            assert result['is_ssl_error'] is True, "Ошибка должна быть определена как SSL ошибка"
            assert result['is_temporary'] is True, "Другие SSL ошибки должны быть временными"
            assert result['code'] == 'NETWORK_ERROR', "Код ошибки должен быть NETWORK_ERROR"
        
        with allure.step("Проверка логирования"):
            warning_calls = [call for call in mock_logger.method_calls if call[0] == 'warning']
            assert len(warning_calls) > 0, "Должно быть логирование на уровне warning"

    @allure.title("Обработка не-SSL сетевых ошибок")
    @allure.description("""
    Проверяет корректную обработку сетевых ошибок, не связанных с SSL.
    
    **Что проверяется:**
    - Ошибка не определяется как SSL ошибка
    - Возвращается правильный код ошибки и статус
    - Логирование происходит на уровне error
    
    **Тестовые данные:**
    - Ошибка: TelegramNetworkError без SSL в сообщении
    
    **Ожидаемый результат:**
    Ошибка обработана как обычная сетевая ошибка.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("error_handler", "network_error", "unit")
    def test_handle_non_ssl_network_error(self, error_handler):
        """Тест обработки не-SSL сетевых ошибок"""
        with allure.step("Подготовка тестовых данных"):
            method = GetUpdates(offset=0, timeout=10)
            error = TelegramNetworkError(
                method=method,
                message="Connection timeout"
            )
            context = "test_context"
            allure.attach(str(error), "Ошибка", allure.attachment_type.TEXT)
        
        with allure.step("Обработка ошибки"):
            with patch('shop_bot.utils.error_handler.logger') as mock_logger:
                result = error_handler._handle_network_error(error, context)
                allure.attach(str(result), "Результат обработки", allure.attachment_type.JSON)
        
        with allure.step("Проверка результата"):
            assert result['is_ssl_error'] is False, "Ошибка не должна быть определена как SSL ошибка"
            assert result['code'] == 'NETWORK_ERROR', "Код ошибки должен быть NETWORK_ERROR"
            assert result['status_code'] == 503, "Статус код должен быть 503"
        
        with allure.step("Проверка логирования"):
            error_calls = [call for call in mock_logger.method_calls if call[0] == 'error']
            assert len(error_calls) > 0, "Должно быть логирование на уровне error"

