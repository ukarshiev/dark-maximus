# -*- coding: utf-8 -*-
"""
Модуль безопасности для Dark Maximus
"""

from .rate_limiter import rate_limit, get_client_ip, check_rate_limit, rate_limiter

__all__ = ['rate_limit', 'get_client_ip', 'check_rate_limit', 'rate_limiter']
