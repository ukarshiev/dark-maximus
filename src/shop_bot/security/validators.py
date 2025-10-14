# -*- coding: utf-8 -*-
"""
Модуль для валидации входных данных
"""

import re
import logging
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

class ValidationError(Exception):
    """Исключение для ошибок валидации"""
    pass

class InputValidator:
    """Класс для валидации входных данных"""
    
    @staticmethod
    def validate_required(value: Any, field_name: str) -> Any:
        """Проверяет, что поле обязательно для заполнения"""
        if value is None or (isinstance(value, str) and not value.strip()):
            raise ValidationError(f"Поле '{field_name}' обязательно для заполнения")
        return value
    
    @staticmethod
    def validate_string(value: Any, field_name: str, min_length: int = 1, max_length: int = 255) -> str:
        """Валидирует строковое поле"""
        if not isinstance(value, str):
            raise ValidationError(f"Поле '{field_name}' должно быть строкой")
        
        value = value.strip()
        if len(value) < min_length:
            raise ValidationError(f"Поле '{field_name}' должно содержать минимум {min_length} символов")
        
        if len(value) > max_length:
            raise ValidationError(f"Поле '{field_name}' не должно превышать {max_length} символов")
        
        return value
    
    @staticmethod
    def validate_integer(value: Any, field_name: str, min_value: Optional[int] = None, max_value: Optional[int] = None) -> int:
        """Валидирует целочисленное поле"""
        # Обрабатываем пустые строки как 0
        if value == '' or value is None:
            value = 0
            
        try:
            int_value = int(value)
        except (ValueError, TypeError):
            raise ValidationError(f"Поле '{field_name}' должно быть целым числом")
        
        if min_value is not None and int_value < min_value:
            raise ValidationError(f"Поле '{field_name}' не должно быть меньше {min_value}")
        
        if max_value is not None and int_value > max_value:
            raise ValidationError(f"Поле '{field_name}' не должно быть больше {max_value}")
        
        return int_value
    
    @staticmethod
    def validate_float(value: Any, field_name: str, min_value: Optional[float] = None, max_value: Optional[float] = None) -> float:
        """Валидирует числовое поле с плавающей точкой"""
        # Обрабатываем пустые строки как 0
        if value == '' or value is None:
            value = 0
            
        try:
            float_value = float(value)
        except (ValueError, TypeError):
            raise ValidationError(f"Поле '{field_name}' должно быть числом")
        
        if min_value is not None and float_value < min_value:
            raise ValidationError(f"Поле '{field_name}' не должно быть меньше {min_value}")
        
        if max_value is not None and float_value > max_value:
            raise ValidationError(f"Поле '{field_name}' не должно быть больше {max_value}")
        
        return float_value
    
    @staticmethod
    def validate_url(value: Any, field_name: str) -> str:
        """Валидирует URL"""
        value = InputValidator.validate_string(value, field_name)
        
        try:
            parsed = urlparse(value)
            if not parsed.scheme or not parsed.netloc:
                raise ValidationError(f"Поле '{field_name}' должно содержать корректный URL")
        except Exception:
            raise ValidationError(f"Поле '{field_name}' должно содержать корректный URL")
        
        return value
    
    @staticmethod
    def validate_email(value: Any, field_name: str) -> str:
        """Валидирует email"""
        value = InputValidator.validate_string(value, field_name)
        
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, value):
            raise ValidationError(f"Поле '{field_name}' должно содержать корректный email")
        
        return value
    
    @staticmethod
    def validate_username(value: Any, field_name: str) -> str:
        """Валидирует имя пользователя"""
        value = InputValidator.validate_string(value, field_name, min_length=3, max_length=50)
        
        # Разрешаем только буквы, цифры, подчеркивания и дефисы
        if not re.match(r'^[a-zA-Z0-9_-]+$', value):
            raise ValidationError(f"Поле '{field_name}' может содержать только буквы, цифры, подчеркивания и дефисы")
        
        return value
    
    @staticmethod
    def validate_password(value: Any, field_name: str) -> str:
        """Валидирует пароль"""
        value = InputValidator.validate_string(value, field_name, min_length=6, max_length=128)
        
        # Проверяем сложность пароля
        if len(value) < 6:
            raise ValidationError(f"Поле '{field_name}' должно содержать минимум 6 символов")
        
        return value
    
    @staticmethod
    def validate_telegram_id(value: Any, field_name: str) -> int:
        """Валидирует Telegram ID"""
        try:
            telegram_id = int(value)
        except (ValueError, TypeError):
            raise ValidationError(f"Поле '{field_name}' должно быть числом")
        
        if telegram_id <= 0:
            raise ValidationError(f"Поле '{field_name}' должно быть положительным числом")
        
        return telegram_id
    
    @staticmethod
    def validate_host_data(data: Dict[str, Any]) -> Dict[str, Any]:
        """Валидирует данные хоста"""
        validated = {}
        
        validated['host_name'] = InputValidator.validate_string(
            data.get('host_name'), 'host_name', min_length=1, max_length=100
        )
        
        validated['host_url'] = InputValidator.validate_url(
            data.get('host_url'), 'host_url'
        )
        
        validated['host_username'] = InputValidator.validate_string(
            data.get('host_username'), 'host_username', min_length=1, max_length=100
        )
        
        validated['host_pass'] = InputValidator.validate_string(
            data.get('host_pass'), 'host_pass', min_length=1, max_length=255
        )
        
        validated['host_inbound_id'] = InputValidator.validate_integer(
            data.get('host_inbound_id'), 'host_inbound_id', min_value=1
        )
        
        return validated
    
    @staticmethod
    def validate_plan_data(data: Dict[str, Any]) -> Dict[str, Any]:
        """Валидирует данные тарифа"""
        validated = {}
        
        validated['plan_name'] = InputValidator.validate_string(
            data.get('plan_name'), 'plan_name', min_length=1, max_length=100
        )
        
        validated['months'] = InputValidator.validate_integer(
            data.get('months'), 'months', min_value=0, max_value=120
        )
        
        validated['days'] = InputValidator.validate_integer(
            data.get('days', 0), 'days', min_value=0, max_value=31
        )
        
        validated['hours'] = InputValidator.validate_integer(
            data.get('hours', 0), 'hours', min_value=0, max_value=23
        )
        
        validated['price'] = InputValidator.validate_float(
            data.get('price'), 'price', min_value=0, max_value=100000
        )
        
        validated['traffic_gb'] = InputValidator.validate_float(
            data.get('traffic_gb', 0), 'traffic_gb', min_value=0, max_value=10000
        )
        
        return validated
    
    @staticmethod
    def validate_user_action_data(data: Dict[str, Any]) -> Dict[str, Any]:
        """Валидирует данные для действий с пользователем"""
        validated = {}
        
        validated['telegram_id'] = InputValidator.validate_telegram_id(
            data.get('telegram_id'), 'telegram_id'
        )
        
        return validated
    
    @staticmethod
    def sanitize_string(value: str) -> str:
        """Очищает строку от потенциально опасных символов"""
        if not isinstance(value, str):
            return str(value)
        
        # Удаляем HTML теги
        value = re.sub(r'<[^>]+>', '', value)
        
        # Удаляем потенциально опасные символы
        value = re.sub(r'[<>"\']', '', value)
        
        return value.strip()

def validate_form_data(form_data: Dict[str, Any], validation_rules: Dict[str, callable]) -> Dict[str, Any]:
    """
    Валидирует данные формы согласно правилам
    
    Args:
        form_data: Данные формы
        validation_rules: Словарь с правилами валидации для каждого поля
    
    Returns:
        Валидированные данные
        
    Raises:
        ValidationError: При ошибке валидации
    """
    validated_data = {}
    
    for field_name, validator_func in validation_rules.items():
        try:
            value = form_data.get(field_name)
            validated_data[field_name] = validator_func(value, field_name)
        except ValidationError as e:
            logger.warning(f"Validation error for field '{field_name}': {e}")
            raise e
        except Exception as e:
            logger.error(f"Unexpected error validating field '{field_name}': {e}")
            raise ValidationError(f"Ошибка валидации поля '{field_name}'")
    
    return validated_data
