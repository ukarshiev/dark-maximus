#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Утилиты для работы с Telegram deeplink ссылками.

Telegram Bot API ограничивает параметры start:
- Допустимые символы: a-z, A-Z, 0-9, -, _
- Максимальная длина: 64 символа
- Запрещены: =, ,, &, /, пробелы и другие спецсимволы

Для передачи сложных параметров используется base64 кодирование JSON.
"""

import base64
import json
import logging
from typing import Dict, Optional, Tuple

logger = logging.getLogger(__name__)


def create_deeplink(
    bot_username: str,
    group_code: Optional[str] = None,
    promo_code: Optional[str] = None,
    referrer_id: Optional[int] = None
) -> str:
    """
    Создаёт deeplink ссылку для Telegram бота с параметрами.
    
    Args:
        bot_username: Имя бота (без @)
        group_code: Код группы пользователей
        promo_code: Промокод
        referrer_id: ID реферера
    
    Returns:
        Полная deeplink ссылка
    
    Examples:
        >>> create_deeplink("mybot", group_code="vip", promo_code="SALE50")
        'https://t.me/mybot?start=eyJnIjoidmlwIiwicCI6IlNBTEU1MCJ9'
        
        >>> create_deeplink("mybot", referrer_id=123456)
        'https://t.me/mybot?start=ref_123456'
    """
    # Реферальные ссылки используют старый формат для совместимости
    if referrer_id and not group_code and not promo_code:
        return f"https://t.me/{bot_username}?start=ref_{referrer_id}"
    
    # Формируем данные для кодирования
    data = {}
    if group_code:
        data['g'] = group_code  # g = group
    if promo_code:
        data['p'] = promo_code  # p = promo
    if referrer_id:
        data['r'] = referrer_id  # r = referrer
    
    if not data:
        # Если нет параметров, возвращаем простую ссылку
        return f"https://t.me/{bot_username}"
    
    try:
        # Кодируем в JSON (компактный формат без пробелов)
        json_str = json.dumps(data, ensure_ascii=False, separators=(',', ':'))
        
        # Кодируем в base64 (urlsafe для совместимости)
        encoded = base64.urlsafe_b64encode(json_str.encode('utf-8')).decode('utf-8')
        
        # Убираем padding (=) для красоты и экономии символов
        encoded = encoded.rstrip('=')
        
        # Проверяем длину (ограничение Telegram: 64 символа)
        if len(encoded) > 64:
            logger.warning(f"Deeplink parameter too long: {len(encoded)} chars (max 64)")
            # Можно сократить имена или использовать короткие коды
        
        return f"https://t.me/{bot_username}?start={encoded}"
    
    except Exception as e:
        logger.error(f"Failed to create deeplink: {e}", exc_info=True)
        return f"https://t.me/{bot_username}"


def parse_deeplink(param: str) -> Tuple[Optional[str], Optional[str], Optional[int]]:
    """
    Парсит параметр deeplink ссылки.
    
    Args:
        param: Параметр из command.args
    
    Returns:
        Кортеж (group_code, promo_code, referrer_id)
    
    Examples:
        >>> parse_deeplink("eyJnIjoidmlwIiwicCI6IlNBTEU1MCJ9")
        ('vip', 'SALE50', None)
        
        >>> parse_deeplink("ref_123456")
        (None, None, 123456)
    """
    if not param:
        return None, None, None
    
    # Старый формат: ref_123456
    if param.startswith('ref_'):
        try:
            referrer_id = int(param.split('_')[1])
            return None, None, referrer_id
        except (IndexError, ValueError) as e:
            logger.warning(f"Invalid referral code format: {param}, error: {e}")
            return None, None, None
    
    # Новый формат: base64 encoded JSON
    try:
        # Добавляем padding если нужно
        padding = '=' * (4 - len(param) % 4) if len(param) % 4 else ''
        param_padded = param + padding
        
        # Декодируем base64
        decoded_bytes = base64.urlsafe_b64decode(param_padded)
        decoded_str = decoded_bytes.decode('utf-8')
        
        # Парсим JSON
        data = json.loads(decoded_str)
        
        group_code = data.get('g')  # g = group
        promo_code = data.get('p')  # p = promo
        referrer_id = data.get('r')  # r = referrer
        
        logger.info(f"Parsed deeplink: group={group_code}, promo={promo_code}, referrer={referrer_id}")
        
        return group_code, promo_code, referrer_id
    
    except (json.JSONDecodeError, base64.binascii.Error, UnicodeDecodeError) as e:
        logger.warning(f"Failed to parse deeplink parameter '{param}': {e}")
        # Fallback: пытаемся парсить старый формат с запятыми (для совместимости)
        return _parse_legacy_format(param)
    
    except Exception as e:
        logger.error(f"Unexpected error parsing deeplink '{param}': {e}", exc_info=True)
        return None, None, None


def _parse_legacy_format(param: str) -> Tuple[Optional[str], Optional[str], Optional[int]]:
    """
    Парсит старый формат с запятыми (для обратной совместимости).
    Формат: user_groups=code,promo=CODE или promo_CODE
    
    ВНИМАНИЕ: Этот формат НЕ РАБОТАЕТ в Telegram из-за недопустимых символов!
    Оставлен только для обратной совместимости с существующими данными.
    """
    group_code = None
    promo_code = None
    
    try:
        # Проверяем наличие разделителей
        if '=' in param or ',' in param:
            parts = param.split(',')
            
            for part in parts:
                part = part.strip()
                
                if part.startswith('user_groups='):
                    group_code = part.replace('user_groups=', '').strip()
                
                elif part.startswith('promo='):
                    promo_code = part.replace('promo=', '').strip()
                
                elif part.startswith('promo_'):
                    promo_code = part.replace('promo_', '').strip()
        
        elif param.startswith('promo_'):
            promo_code = param.replace('promo_', '').strip()
        
        if group_code or promo_code:
            logger.info(f"Parsed legacy format: group={group_code}, promo={promo_code}")
        
        return group_code, promo_code, None
    
    except Exception as e:
        logger.error(f"Failed to parse legacy format '{param}': {e}", exc_info=True)
        return None, None, None


def validate_deeplink_length(data: Dict) -> bool:
    """
    Проверяет, что закодированные данные не превысят лимит Telegram (64 символа).
    
    Args:
        data: Словарь с данными для кодирования
    
    Returns:
        True если длина в пределах нормы, False если превышает
    """
    try:
        json_str = json.dumps(data, ensure_ascii=False, separators=(',', ':'))
        encoded = base64.urlsafe_b64encode(json_str.encode('utf-8')).decode('utf-8')
        encoded = encoded.rstrip('=')
        
        return len(encoded) <= 64
    
    except Exception:
        return False


# Экспорт публичных функций
__all__ = ['create_deeplink', 'parse_deeplink', 'validate_deeplink_length']

