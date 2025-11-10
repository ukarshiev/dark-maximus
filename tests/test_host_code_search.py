# -*- coding: utf-8 -*-
"""
Тесты для проверки использования host_code для поиска хоста
"""

import sys
import os
import asyncio
from unittest.mock import Mock, patch, AsyncMock

# Добавляем путь к проекту
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from shop_bot.modules import xui_api
from shop_bot.data_manager.database import get_host, get_host_by_code


def test_get_host_by_code_exists():
    """Тест: проверка получения хоста по коду"""
    # Тестируем, что функция get_host_by_code работает
    # Это базовый тест для проверки, что функция существует и работает
    try:
        # Попробуем найти любой хост по коду (если есть хосты в БД)
        # Это не должен упасть с ошибкой
        result = get_host_by_code("test_code_that_does_not_exist")
        # Если хост не найден, должен вернуться None
        assert result is None or isinstance(result, dict)
        print("[OK] test_get_host_by_code_exists: PASSED")
    except Exception as e:
        print(f"[FAIL] test_get_host_by_code_exists: FAILED - {e}")
        raise


def test_create_or_update_key_on_host_with_host_code():
    """Тест: проверка создания ключа с передачей host_code"""
    # Мокаем зависимости
    with patch('shop_bot.modules.xui_api.get_host_by_code') as mock_get_by_code, \
         patch('shop_bot.modules.xui_api.get_host') as mock_get_host, \
         patch('shop_bot.modules.xui_api.login_to_host') as mock_login, \
         patch('shop_bot.modules.xui_api.update_or_create_client_on_panel') as mock_create_client:
        
        # Настраиваем моки
        mock_host_data = {
            'host_url': 'https://test.example.com',
            'host_username': 'admin',
            'host_pass': 'password',
            'host_inbound_id': 1,
            'host_code': 'testcode'
        }
        mock_get_by_code.return_value = mock_host_data
        mock_api = Mock()
        mock_inbound = Mock()
        mock_inbound.id = 1
        mock_login.return_value = (mock_api, mock_inbound)
        mock_create_client.return_value = ('test-uuid', 1234567890000)
        
        # Тестируем функцию с host_code
        async def run_test():
            result = await xui_api.create_or_update_key_on_host(
                host_name="Test Host",
                email="test@example.com",
                days_to_add=30.0,
                host_code="testcode"
            )
            # Проверяем, что был вызван get_host_by_code
            mock_get_by_code.assert_called_once_with("testcode")
            # Проверяем, что get_host не был вызван (так как хост найден по коду)
            mock_get_host.assert_not_called()
            print("[OK] test_create_or_update_key_on_host_with_host_code: PASSED")
        
        asyncio.run(run_test())


def test_create_or_update_key_on_host_without_host_code():
    """Тест: проверка обратной совместимости без host_code"""
    # Мокаем зависимости
    with patch('shop_bot.modules.xui_api.get_host') as mock_get_host, \
         patch('shop_bot.modules.xui_api.login_to_host') as mock_login, \
         patch('shop_bot.modules.xui_api.update_or_create_client_on_panel') as mock_create_client:
        
        # Настраиваем моки
        mock_host_data = {
            'host_url': 'https://test.example.com',
            'host_username': 'admin',
            'host_pass': 'password',
            'host_inbound_id': 1
        }
        mock_get_host.return_value = mock_host_data
        mock_api = Mock()
        mock_inbound = Mock()
        mock_inbound.id = 1
        mock_login.return_value = (mock_api, mock_inbound)
        mock_create_client.return_value = ('test-uuid', 1234567890000)
        
        # Тестируем функцию без host_code
        async def run_test():
            result = await xui_api.create_or_update_key_on_host(
                host_name="Test Host",
                email="test@example.com",
                days_to_add=30.0
                # host_code не передается
            )
            # Проверяем, что был вызван get_host
            mock_get_host.assert_called_once_with("Test Host")
            print("[OK] test_create_or_update_key_on_host_without_host_code: PASSED")
        
        asyncio.run(run_test())


def test_create_or_update_key_on_host_fallback():
    """Тест: проверка fallback на host_name, если host_code не найден"""
    # Мокаем зависимости
    with patch('shop_bot.modules.xui_api.get_host_by_code') as mock_get_by_code, \
         patch('shop_bot.modules.xui_api.get_host') as mock_get_host, \
         patch('shop_bot.modules.xui_api.login_to_host') as mock_login, \
         patch('shop_bot.modules.xui_api.update_or_create_client_on_panel') as mock_create_client:
        
        # Настраиваем моки: host_code не найден, но host_name найден
        mock_get_by_code.return_value = None  # Хост не найден по коду
        mock_host_data = {
            'host_url': 'https://test.example.com',
            'host_username': 'admin',
            'host_pass': 'password',
            'host_inbound_id': 1
        }
        mock_get_host.return_value = mock_host_data
        mock_api = Mock()
        mock_inbound = Mock()
        mock_inbound.id = 1
        mock_login.return_value = (mock_api, mock_inbound)
        mock_create_client.return_value = ('test-uuid', 1234567890000)
        
        # Тестируем функцию с host_code, который не найден
        async def run_test():
            result = await xui_api.create_or_update_key_on_host(
                host_name="Test Host",
                email="test@example.com",
                days_to_add=30.0,
                host_code="nonexistent_code"
            )
            # Проверяем, что был вызван get_host_by_code
            mock_get_by_code.assert_called_once_with("nonexistent_code")
            # Проверяем, что был вызван fallback на get_host
            mock_get_host.assert_called_once_with("Test Host")
            print("[OK] test_create_or_update_key_on_host_fallback: PASSED")
        
        asyncio.run(run_test())


def test_host_code_parameter_exists():
    """Тест: проверка, что параметр host_code добавлен в функцию"""
    import inspect
    sig = inspect.signature(xui_api.create_or_update_key_on_host)
    params = list(sig.parameters.keys())
    
    assert 'host_code' in params, "Параметр host_code должен быть в функции create_or_update_key_on_host"
    print("[OK] test_host_code_parameter_exists: PASSED")


if __name__ == "__main__":
    print("Запуск тестов для проверки использования host_code...")
    print("=" * 60)
    
    try:
        test_host_code_parameter_exists()
        test_get_host_by_code_exists()
        test_create_or_update_key_on_host_with_host_code()
        test_create_or_update_key_on_host_without_host_code()
        test_create_or_update_key_on_host_fallback()
        
        print("=" * 60)
        print("Все тесты пройдены успешно!")
    except Exception as e:
        print("=" * 60)
        print(f"Тесты завершились с ошибкой: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

