# -*- coding: utf-8 -*-
"""
Централизованная система логирования для Dark Maximus
"""

import logging
import logging.handlers
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any
import json

class StructuredLogger:
    """Структурированный логгер с поддержкой JSON и ротации файлов"""
    
    def __init__(self, name: str, log_dir: str = "logs"):
        self.name = name
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(exist_ok=True)
        
        # Создаем логгер
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.INFO)
        
        # Очищаем существующие обработчики
        self.logger.handlers.clear()
        
        # Настраиваем форматирование
        self._setup_formatters()
        
        # Настраиваем обработчики
        self._setup_handlers()
    
    def _setup_formatters(self):
        """Настройка форматтеров для логов"""
        # Форматтер для консоли
        self.console_formatter = logging.Formatter(
            '%(asctime)s - [%(levelname)s] - %(name)s - (%(filename)s).%(funcName)s(%(lineno)d) - %(message)s'
        )
        
        # Форматтер для файлов
        self.file_formatter = logging.Formatter(
            '%(asctime)s - [%(levelname)s] - %(name)s - (%(filename)s).%(funcName)s(%(lineno)d) - %(message)s'
        )
        
        # JSON форматтер для структурированных логов
        self.json_formatter = JSONFormatter()
    
    def _setup_handlers(self):
        """Настройка обработчиков логов"""
        # Консольный обработчик
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(self.console_formatter)
        self.logger.addHandler(console_handler)
        
        # Файловый обработчик для общих логов
        general_log_file = self.log_dir / "dark_maximus.log"
        file_handler = logging.handlers.RotatingFileHandler(
            general_log_file,
            maxBytes=10*1024*1024,  # 10MB
            backupCount=5
        )
        file_handler.setLevel(logging.INFO)
        file_handler.setFormatter(self.file_formatter)
        self.logger.addHandler(file_handler)
        
        # Файловый обработчик для ошибок
        error_log_file = self.log_dir / "errors.log"
        error_handler = logging.handlers.RotatingFileHandler(
            error_log_file,
            maxBytes=10*1024*1024,  # 10MB
            backupCount=5
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(self.file_formatter)
        self.logger.addHandler(error_handler)
        
        # Файловый обработчик для структурированных логов
        structured_log_file = self.log_dir / "structured.log"
        structured_handler = logging.handlers.RotatingFileHandler(
            structured_log_file,
            maxBytes=10*1024*1024,  # 10MB
            backupCount=5
        )
        structured_handler.setLevel(logging.INFO)
        structured_handler.setFormatter(self.json_formatter)
        self.logger.addHandler(structured_handler)
    
    def info(self, message: str, **kwargs):
        """Логирование информационного сообщения"""
        self.logger.info(message, extra=kwargs)
    
    def warning(self, message: str, **kwargs):
        """Логирование предупреждения"""
        self.logger.warning(message, extra=kwargs)
    
    def error(self, message: str, **kwargs):
        """Логирование ошибки"""
        self.logger.error(message, extra=kwargs)
    
    def debug(self, message: str, **kwargs):
        """Логирование отладочной информации"""
        self.logger.debug(message, extra=kwargs)
    
    def critical(self, message: str, **kwargs):
        """Логирование критической ошибки"""
        self.logger.critical(message, extra=kwargs)
    
    def log_user_action(self, user_id: int, action: str, details: Optional[Dict[str, Any]] = None):
        """Логирование действий пользователя"""
        self.info(
            f"User action: {action}",
            user_id=user_id,
            action=action,
            details=details or {},
            log_type="user_action"
        )
    
    def log_payment(self, user_id: int, payment_method: str, amount: float, status: str, details: Optional[Dict[str, Any]] = None):
        """Логирование платежей"""
        self.info(
            f"Payment: {status} - {payment_method} - {amount}",
            user_id=user_id,
            payment_method=payment_method,
            amount=amount,
            status=status,
            details=details or {},
            log_type="payment"
        )
    
    def log_security_event(self, event_type: str, ip: str, details: Optional[Dict[str, Any]] = None):
        """Логирование событий безопасности"""
        self.warning(
            f"Security event: {event_type}",
            event_type=event_type,
            ip=ip,
            details=details or {},
            log_type="security"
        )
    
    def log_database_operation(self, operation: str, table: str, details: Optional[Dict[str, Any]] = None):
        """Логирование операций с базой данных"""
        self.info(
            f"Database operation: {operation} on {table}",
            operation=operation,
            table=table,
            details=details or {},
            log_type="database"
        )

class JSONFormatter(logging.Formatter):
    """Форматтер для JSON логов"""
    
    def format(self, record):
        log_entry = {
            'timestamp': datetime.fromtimestamp(record.created).isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno
        }
        
        # Добавляем дополнительные поля из extra
        for key, value in record.__dict__.items():
            if key not in ['name', 'msg', 'args', 'levelname', 'levelno', 'pathname', 
                          'filename', 'module', 'lineno', 'funcName', 'created', 
                          'msecs', 'relativeCreated', 'thread', 'threadName', 
                          'processName', 'process', 'getMessage', 'exc_info', 
                          'exc_text', 'stack_info']:
                log_entry[key] = value
        
        # Добавляем информацию об исключении, если есть
        if record.exc_info:
            log_entry['exception'] = self.formatException(record.exc_info)
        
        return json.dumps(log_entry, ensure_ascii=False, default=str)

# Глобальные логгеры
app_logger = StructuredLogger("dark_maximus")
security_logger = StructuredLogger("security")
payment_logger = StructuredLogger("payments")
database_logger = StructuredLogger("database")

def get_logger(name: str) -> StructuredLogger:
    """Получить логгер по имени"""
    return StructuredLogger(name)

def setup_logging(log_level: str = "INFO", log_dir: str = "logs"):
    """Настройка глобального логирования"""
    # Устанавливаем уровень логирования
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)
    
    # Настраиваем корневой логгер
    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)
    
    # Очищаем существующие обработчики
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Создаем директорию для логов
    log_path = Path(log_dir)
    log_path.mkdir(exist_ok=True)
    
    # Настраиваем обработчик для всех логгеров
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(numeric_level)
    console_formatter = logging.Formatter(
        '%(asctime)s - [%(levelname)s] - %(name)s - %(message)s'
    )
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)
    
    # Файловый обработчик
    file_handler = logging.handlers.RotatingFileHandler(
        log_path / "application.log",
        maxBytes=10*1024*1024,  # 10MB
        backupCount=5
    )
    file_handler.setLevel(numeric_level)
    file_handler.setFormatter(console_formatter)
    root_logger.addHandler(file_handler)
    
    # Отключаем логирование от внешних библиотек
    logging.getLogger('werkzeug').setLevel(logging.WARNING)
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('requests').setLevel(logging.WARNING)
    logging.getLogger('aiohttp').setLevel(logging.WARNING)
