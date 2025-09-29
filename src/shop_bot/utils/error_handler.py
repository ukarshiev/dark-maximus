# -*- coding: utf-8 -*-
"""
Модуль для централизованной обработки ошибок
"""

import logging
import traceback
from typing import Any, Dict, Optional, Callable
from functools import wraps
from flask import jsonify, request, current_app
from sqlite3 import Error as SQLiteError
from aiogram.exceptions import TelegramBadRequest, TelegramNetworkError

logger = logging.getLogger(__name__)

class ErrorHandler:
    """Класс для централизованной обработки ошибок"""
    
    def __init__(self):
        self.error_mappings = {
            SQLiteError: self._handle_database_error,
            TelegramBadRequest: self._handle_telegram_error,
            TelegramNetworkError: self._handle_network_error,
            ValueError: self._handle_value_error,
            TypeError: self._handle_type_error,
            KeyError: self._handle_key_error,
            FileNotFoundError: self._handle_file_error,
            PermissionError: self._handle_permission_error,
        }
    
    def _handle_database_error(self, error: SQLiteError, context: str = "") -> Dict[str, Any]:
        """Обработка ошибок базы данных"""
        logger.error(f"Database error in {context}: {error}")
        return {
            'error': 'Database operation failed',
            'message': 'Внутренняя ошибка базы данных. Попробуйте позже.',
            'code': 'DB_ERROR',
            'status_code': 500
        }
    
    def _handle_telegram_error(self, error: TelegramBadRequest, context: str = "") -> Dict[str, Any]:
        """Обработка ошибок Telegram API"""
        logger.error(f"Telegram API error in {context}: {error}")
        return {
            'error': 'Telegram API error',
            'message': 'Ошибка при работе с Telegram API',
            'code': 'TELEGRAM_ERROR',
            'status_code': 502
        }
    
    def _handle_network_error(self, error: TelegramNetworkError, context: str = "") -> Dict[str, Any]:
        """Обработка сетевых ошибок"""
        logger.error(f"Network error in {context}: {error}")
        return {
            'error': 'Network error',
            'message': 'Ошибка сети. Проверьте подключение.',
            'code': 'NETWORK_ERROR',
            'status_code': 503
        }
    
    def _handle_value_error(self, error: ValueError, context: str = "") -> Dict[str, Any]:
        """Обработка ошибок значений"""
        logger.error(f"Value error in {context}: {error}")
        return {
            'error': 'Invalid value',
            'message': 'Некорректное значение параметра',
            'code': 'VALUE_ERROR',
            'status_code': 400
        }
    
    def _handle_type_error(self, error: TypeError, context: str = "") -> Dict[str, Any]:
        """Обработка ошибок типов"""
        logger.error(f"Type error in {context}: {error}")
        return {
            'error': 'Type error',
            'message': 'Ошибка типа данных',
            'code': 'TYPE_ERROR',
            'status_code': 400
        }
    
    def _handle_key_error(self, error: KeyError, context: str = "") -> Dict[str, Any]:
        """Обработка ошибок ключей"""
        logger.error(f"Key error in {context}: {error}")
        return {
            'error': 'Missing key',
            'message': 'Отсутствует обязательный параметр',
            'code': 'KEY_ERROR',
            'status_code': 400
        }
    
    def _handle_file_error(self, error: FileNotFoundError, context: str = "") -> Dict[str, Any]:
        """Обработка ошибок файлов"""
        logger.error(f"File error in {context}: {error}")
        return {
            'error': 'File not found',
            'message': 'Файл не найден',
            'code': 'FILE_ERROR',
            'status_code': 404
        }
    
    def _handle_permission_error(self, error: PermissionError, context: str = "") -> Dict[str, Any]:
        """Обработка ошибок прав доступа"""
        logger.error(f"Permission error in {context}: {error}")
        return {
            'error': 'Permission denied',
            'message': 'Недостаточно прав доступа',
            'code': 'PERMISSION_ERROR',
            'status_code': 403
        }
    
    def handle_error(self, error: Exception, context: str = "") -> Dict[str, Any]:
        """Централизованная обработка ошибок"""
        error_type = type(error)
        
        # Ищем обработчик для конкретного типа ошибки
        for error_class, handler in self.error_mappings.items():
            if issubclass(error_type, error_class):
                return handler(error, context)
        
        # Обработка неизвестных ошибок
        logger.error(f"Unhandled error in {context}: {error}\n{traceback.format_exc()}")
        return {
            'error': 'Internal server error',
            'message': 'Внутренняя ошибка сервера',
            'code': 'INTERNAL_ERROR',
            'status_code': 500
        }

# Глобальный экземпляр обработчика ошибок
error_handler = ErrorHandler()

def handle_exceptions(context: str = ""):
    """Декоратор для обработки исключений в Flask-приложении"""
    def decorator(f: Callable) -> Callable:
        @wraps(f)
        def decorated_function(*args, **kwargs):
            try:
                return f(*args, **kwargs)
            except Exception as e:
                error_info = error_handler.handle_error(e, context or f.__name__)
                
                # Если это API endpoint, возвращаем JSON
                if request.path.startswith('/api/'):
                    return jsonify({
                        'success': False,
                        'error': error_info['error'],
                        'message': error_info['message'],
                        'code': error_info['code']
                    }), error_info['status_code']
                
                # Для обычных страниц возвращаем редирект или ошибку
                from flask import flash, redirect, url_for
                flash(error_info['message'], 'danger')
                return redirect(url_for('dashboard_page'))
        
        return decorated_function
    return decorator

def handle_async_exceptions(context: str = ""):
    """Декоратор для обработки исключений в асинхронных функциях"""
    def decorator(f: Callable) -> Callable:
        @wraps(f)
        async def decorated_function(*args, **kwargs):
            try:
                return await f(*args, **kwargs)
            except Exception as e:
                error_info = error_handler.handle_error(e, context or f.__name__)
                logger.error(f"Async error in {context or f.__name__}: {error_info}")
                # Для асинхронных функций просто логируем ошибку
                return None
        
        return decorated_function
    return decorator

def safe_execute(func: Callable, *args, context: str = "", default_return: Any = None, **kwargs) -> Any:
    """Безопасное выполнение функции с обработкой ошибок"""
    try:
        return func(*args, **kwargs)
    except Exception as e:
        error_info = error_handler.handle_error(e, context or func.__name__)
        logger.error(f"Safe execute error in {context or func.__name__}: {error_info}")
        return default_return

async def safe_execute_async(func: Callable, *args, context: str = "", default_return: Any = None, **kwargs) -> Any:
    """Безопасное выполнение асинхронной функции с обработкой ошибок"""
    try:
        return await func(*args, **kwargs)
    except Exception as e:
        error_info = error_handler.handle_error(e, context or func.__name__)
        logger.error(f"Safe execute async error in {context or func.__name__}: {error_info}")
        return default_return
