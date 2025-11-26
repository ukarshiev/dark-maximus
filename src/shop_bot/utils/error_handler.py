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
        
        error_message = str(error)
        user_message = 'Ошибка при работе с Telegram API'
        
        # Парсим специфичные ошибки Telegram
        if "can't parse entities" in error_message:
            user_message = 'Ошибка форматирования сообщения: некорректные HTML-теги или специальные символы'
        elif "message is too long" in error_message:
            user_message = 'Сообщение слишком длинное. Максимум 4096 символов'
        elif "chat not found" in error_message:
            user_message = 'Чат не найден. Пользователь не запускал бота'
        elif "user is deactivated" in error_message:
            user_message = 'Пользователь деактивирован'
        elif "bot was blocked by the user" in error_message:
            user_message = 'Пользователь заблокировал бота'
        elif "message to edit not found" in error_message:
            user_message = 'Сообщение для редактирования не найдено'
        elif "message to delete not found" in error_message:
            user_message = 'Сообщение для удаления не найдено'
        elif "message_id_invalid" in error_message:
            user_message = 'Неверный ID сообщения'
        elif "file is too big" in error_message:
            user_message = 'Файл слишком большой'
        elif "unsupported start tag" in error_message:
            user_message = f'Неподдерживаемый HTML-тег в сообщении'
        elif "bad request" in error_message.lower():
            user_message = 'Некорректный запрос к Telegram API'
        
        return {
            'error': 'Telegram API error',
            'message': user_message,
            'code': 'TELEGRAM_ERROR',
            'status_code': 502,
            'original_error': error_message
        }
    
    def _handle_network_error(self, error: TelegramNetworkError, context: str = "") -> Dict[str, Any]:
        """
        Обработка сетевых ошибок, включая SSL ошибки.
        
        Детально обрабатывает различные типы SSL ошибок:
        - record layer failure - временные ошибки, aiogram автоматически повторяет попытки
        - certificate errors - критические ошибки, требуют проверки системного времени и сертификатов
        - другие SSL ошибки - логируются как предупреждения с указанием на автоматический retry
        """
        error_message = str(error)
        error_str_lower = error_message.lower()
        
        # Определяем тип сетевой ошибки для более информативного логирования
        is_ssl_error = False
        is_temporary = False
        user_message = 'Ошибка сети. Проверьте подключение.'
        log_level = 'error'
        
        # Проверяем на SSL ошибки
        if "SSL" in error_message or "ssl" in error_str_lower:
            is_ssl_error = True
            
            if "record layer failure" in error_str_lower:
                # Временная SSL ошибка - обычно связана с сетевыми проблемами
                is_temporary = True
                user_message = 'Временная ошибка SSL соединения. Повторная попытка выполняется автоматически.'
                log_level = 'warning'
                logger.warning(
                    f"⚠️ SSL record layer failure detected in {context}. "
                    f"Error: {error_message}\n"
                    f"Это обычно временная сетевая проблема. "
                    f"Aiogram автоматически повторяет попытки подключения. "
                    f"Если ошибки повторяются часто, проверьте:\n"
                    f"  - Стабильность интернет-соединения\n"
                    f"  - Настройки файрвола и прокси\n"
                    f"  - Актуальность SSL сертификатов (certifi)"
                )
            elif "certificate" in error_str_lower or "cert" in error_str_lower:
                # Критическая SSL ошибка - проблема с сертификатами
                is_temporary = False
                user_message = 'Ошибка проверки SSL сертификата. Проверьте системное время и сертификаты.'
                log_level = 'error'
                logger.error(
                    f"❌ SSL certificate error in {context}. "
                    f"Error: {error_message}\n"
                    f"Это критическая ошибка SSL сертификата. Проверьте:\n"
                    f"  - Системное время сервера (должно быть синхронизировано)\n"
                    f"  - Актуальность SSL сертификатов (certifi)\n"
                    f"  - Настройки SSL контекста в bot_controller.py"
                )
            elif "handshake" in error_str_lower:
                # Ошибка SSL handshake - может быть временной
                is_temporary = True
                user_message = 'Ошибка SSL handshake. Повторная попытка выполняется автоматически.'
                log_level = 'warning'
                logger.warning(
                    f"⚠️ SSL handshake error in {context}. "
                    f"Error: {error_message}\n"
                    f"Это может быть временная сетевая проблема. "
                    f"Aiogram автоматически повторяет попытки подключения."
                )
            else:
                # Другие SSL ошибки
                is_temporary = True
                user_message = 'Ошибка SSL соединения. Повторная попытка выполняется автоматически.'
                log_level = 'warning'
                logger.warning(
                    f"⚠️ SSL error in {context}. "
                    f"Error: {error_message}\n"
                    f"Aiogram автоматически повторяет попытки подключения. "
                    f"Если ошибки повторяются, проверьте сетевые настройки."
                )
        else:
            # Не SSL ошибка - обычная сетевая ошибка
            logger.error(f"Network error in {context}: {error_message}")
        
        return {
            'error': 'Network error',
            'message': user_message,
            'code': 'NETWORK_ERROR',
            'status_code': 503,
            'is_ssl_error': is_ssl_error,
            'is_temporary': is_temporary,
            'original_error': error_message
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
