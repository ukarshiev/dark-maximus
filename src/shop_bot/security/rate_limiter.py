# -*- coding: utf-8 -*-
"""
Модуль для ограничения частоты запросов (Rate Limiting)
"""

import time
import logging
from typing import Dict, Optional
from collections import defaultdict, deque
from functools import wraps
from flask import request, jsonify, current_app

logger = logging.getLogger(__name__)

class RateLimiter:
    """Класс для ограничения частоты запросов"""
    
    def __init__(self):
        # Словарь для хранения истории запросов по IP
        self.requests: Dict[str, deque] = defaultdict(deque)
        # Настройки по умолчанию
        self.default_limits = {
            'per_minute': 60,
            'per_hour': 1000,
            'per_day': 10000
        }
        # Максимальное количество IP для предотвращения утечки памяти
        self.max_ips = 10000
    
    def is_allowed(self, ip: str, limit_type: str = 'per_minute', limit_value: Optional[int] = None) -> bool:
        """
        Проверяет, разрешен ли запрос для данного IP
        
        Args:
            ip: IP адрес клиента
            limit_type: Тип ограничения ('per_minute', 'per_hour', 'per_day')
            limit_value: Кастомное значение лимита
            
        Returns:
            True если запрос разрешен, False если превышен лимит
        """
        try:
            # Валидация входных данных
            if not ip or not isinstance(ip, str):
                logger.warning("Invalid IP address provided to rate limiter")
                return True
            
            # Очистка старых IP для предотвращения утечки памяти
            if len(self.requests) > self.max_ips:
                self._cleanup_old_ips()
            
            # Получаем лимит
            if limit_value is None:
                limit_value = self.default_limits.get(limit_type, 60)
            
            # Определяем временное окно
            time_windows = {
                'per_minute': 60,
                'per_hour': 3600,
                'per_day': 86400
            }
            window_seconds = time_windows.get(limit_type, 60)
            
            current_time = time.time()
            cutoff_time = current_time - window_seconds
            
            # Очищаем старые запросы
            request_times = self.requests[ip]
            while request_times and request_times[0] < cutoff_time:
                request_times.popleft()
            
            # Проверяем лимит
            if len(request_times) >= limit_value:
                logger.warning(f"Rate limit exceeded for IP {ip}: {len(request_times)}/{limit_value} requests in {limit_type}")
                return False
            
            # Добавляем текущий запрос
            request_times.append(current_time)
            return True
            
        except Exception as e:
            logger.error(f"Error in rate limiter: {e}")
            # В случае ошибки разрешаем запрос
            return True
    
    def _cleanup_old_ips(self):
        """Очищает старые IP адреса для предотвращения утечки памяти"""
        try:
            current_time = time.time()
            # Удаляем IP, которые не использовались более часа
            cutoff_time = current_time - 3600
            
            ips_to_remove = []
            for ip, request_times in self.requests.items():
                if not request_times or request_times[-1] < cutoff_time:
                    ips_to_remove.append(ip)
            
            for ip in ips_to_remove:
                del self.requests[ip]
                
            logger.info(f"Cleaned up {len(ips_to_remove)} old IP addresses from rate limiter")
        except Exception as e:
            logger.error(f"Error cleaning up old IPs: {e}")
    
    def get_remaining_requests(self, ip: str, limit_type: str = 'per_minute', limit_value: Optional[int] = None) -> int:
        """Возвращает количество оставшихся запросов"""
        try:
            if limit_value is None:
                limit_value = self.default_limits.get(limit_type, 60)
            
            time_windows = {
                'per_minute': 60,
                'per_hour': 3600,
                'per_day': 86400
            }
            window_seconds = time_windows.get(limit_type, 60)
            
            current_time = time.time()
            cutoff_time = current_time - window_seconds
            
            request_times = self.requests[ip]
            while request_times and request_times[0] < cutoff_time:
                request_times.popleft()
            
            return max(0, limit_value - len(request_times))
            
        except Exception as e:
            logger.error(f"Error getting remaining requests: {e}")
            return limit_value or 60

# Глобальный экземпляр rate limiter
rate_limiter = RateLimiter()

def rate_limit(limit_type: str = 'per_minute', limit_value: Optional[int] = None, 
               error_message: str = "Rate limit exceeded. Please try again later."):
    """
    Декоратор для ограничения частоты запросов
    
    Args:
        limit_type: Тип ограничения ('per_minute', 'per_hour', 'per_day')
        limit_value: Кастомное значение лимита
        error_message: Сообщение об ошибке при превышении лимита
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Отключаем rate limiting в тестовом окружении
            if current_app.config.get('TESTING', False):
                return f(*args, **kwargs)
            
            # Получаем IP адрес клиента
            ip = request.environ.get('HTTP_X_FORWARDED_FOR', request.remote_addr)
            if ip:
                ip = ip.split(',')[0].strip()
            
            # Проверяем лимит
            if not rate_limiter.is_allowed(ip, limit_type, limit_value):
                remaining = rate_limiter.get_remaining_requests(ip, limit_type, limit_value)
                return jsonify({
                    'error': error_message,
                    'remaining_requests': remaining,
                    'limit_type': limit_type
                }), 429
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def get_client_ip() -> str:
    """Получает IP адрес клиента с учетом прокси"""
    ip = request.environ.get('HTTP_X_FORWARDED_FOR', request.remote_addr)
    if ip:
        return ip.split(',')[0].strip()
    return request.remote_addr or 'unknown'

def check_rate_limit(ip: str, limit_type: str = 'per_minute', limit_value: Optional[int] = None) -> tuple[bool, int]:
    """
    Проверяет rate limit для конкретного IP
    
    Returns:
        tuple: (is_allowed, remaining_requests)
    """
    is_allowed = rate_limiter.is_allowed(ip, limit_type, limit_value)
    remaining = rate_limiter.get_remaining_requests(ip, limit_type, limit_value)
    return is_allowed, remaining
