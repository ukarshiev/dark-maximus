# -*- coding: utf-8 -*-
"""
Справочник часовых поясов для выбора пользователем

Этот модуль содержит:
- Список всех доступных часовых поясов (24 зоны от UTC-11 до UTC+12)
- Функции для пагинации списка часовых поясов
- Функции для валидации timezone
"""

from typing import Optional
import logging

logger = logging.getLogger(__name__)

# Список всех доступных часовых поясов
# Формат: (timezone_name, display_name, utc_offset)
TIMEZONES = [
    ("Pacific/Midway", "🌎 Самоа (UTC-11)", -11),
    ("Pacific/Honolulu", "🌎 Гонолулу (UTC-10)", -10),
    ("America/Anchorage", "🌎 Анкоридж (UTC-9)", -9),
    ("America/Los_Angeles", "🌎 Лос-Анджелес (UTC-8)", -8),
    ("America/Denver", "🌎 Денвер (UTC-7)", -7),
    ("America/Chicago", "🌎 Чикаго (UTC-6)", -6),
    ("America/New_York", "🌎 Нью-Йорк (UTC-5)", -5),
    ("America/Caracas", "🌎 Каракас (UTC-4)", -4),
    ("America/Argentina/Buenos_Aires", "🌎 Буэнос-Айрес (UTC-3)", -3),
    ("Atlantic/South_Georgia", "🌎 Южная Георгия (UTC-2)", -2),
    ("Atlantic/Azores", "🌎 Азорские о-ва (UTC-1)", -1),
    ("Europe/London", "🌍 Лондон (UTC+0)", 0),
    ("Europe/Paris", "🌍 Париж (UTC+1)", 1),
    ("Europe/Kiev", "🌍 Киев (UTC+2)", 2),
    ("Europe/Moscow", "🌍 Москва (UTC+3)", 3),
    ("Asia/Dubai", "🌍 Дубай (UTC+4)", 4),
    ("Asia/Karachi", "🌏 Карачи (UTC+5)", 5),
    ("Asia/Dhaka", "🌏 Дакка (UTC+6)", 6),
    ("Asia/Bangkok", "🌏 Бангкок (UTC+7)", 7),
    ("Asia/Shanghai", "🌏 Шанхай (UTC+8)", 8),
    ("Asia/Tokyo", "🌏 Токио (UTC+9)", 9),
    ("Australia/Sydney", "🌏 Сидней (UTC+10)", 10),
    ("Pacific/Noumea", "🌏 Нумеа (UTC+11)", 11),
    ("Pacific/Auckland", "🌏 Окленд (UTC+12)", 12),
]

# Часовой пояс по умолчанию
DEFAULT_TIMEZONE = "Europe/Moscow"

# Количество часовых поясов на одной странице
TIMEZONES_PER_PAGE = 10


def get_timezone_by_name(timezone_name: str) -> Optional[tuple]:
    """
    Получает информацию о часовом поясе по его имени
    
    Args:
        timezone_name: Имя timezone (например, "Europe/Moscow")
        
    Returns:
        Кортеж (timezone_name, display_name, utc_offset) или None если не найдено
        
    Examples:
        >>> tz = get_timezone_by_name("Europe/Moscow")
        >>> tz[1]
        '🌍 Москва (UTC+3)'
    """
    for tz in TIMEZONES:
        if tz[0] == timezone_name:
            return tz
    return None


def get_timezone_display_name(timezone_name: str) -> str:
    """
    Возвращает отображаемое имя часового пояса
    
    Args:
        timezone_name: Имя timezone (например, "Europe/Moscow")
        
    Returns:
        Отображаемое имя или timezone_name если не найдено
        
    Examples:
        >>> get_timezone_display_name("Europe/Moscow")
        '🌍 Москва (UTC+3)'
    """
    tz = get_timezone_by_name(timezone_name)
    if tz:
        return tz[1]
    return timezone_name


def validate_timezone(timezone_name: str) -> bool:
    """
    Проверяет, что timezone валиден и может быть загружен
    
    Args:
        timezone_name: Имя timezone для проверки
        
    Returns:
        True если timezone валиден, False иначе
        
    Examples:
        >>> validate_timezone("Europe/Moscow")
        True
        >>> validate_timezone("Invalid/Timezone")
        False
    """
    try:
        from zoneinfo import ZoneInfo
        ZoneInfo(timezone_name)
        return True
    except Exception as e:
        logger.warning(f"Invalid timezone {timezone_name}: {e}")
        return False


def get_timezones_page(page: int = 0) -> tuple[list, int, bool, bool]:
    """
    Возвращает часовые пояса для указанной страницы
    
    Args:
        page: Номер страницы (начиная с 0)
        
    Returns:
        Кортеж (timezones_on_page, total_pages, has_prev, has_next)
        - timezones_on_page: список часовых поясов на странице
        - total_pages: общее количество страниц
        - has_prev: есть ли предыдущая страница
        - has_next: есть ли следующая страница
        
    Examples:
        >>> timezones, total, has_prev, has_next = get_timezones_page(0)
        >>> len(timezones) <= 10
        True
        >>> has_prev
        False
    """
    total_timezones = len(TIMEZONES)
    total_pages = (total_timezones + TIMEZONES_PER_PAGE - 1) // TIMEZONES_PER_PAGE
    
    # Ограничиваем номер страницы
    page = max(0, min(page, total_pages - 1))
    
    # Вычисляем индексы
    start_idx = page * TIMEZONES_PER_PAGE
    end_idx = min(start_idx + TIMEZONES_PER_PAGE, total_timezones)
    
    # Получаем часовые пояса для страницы
    timezones_on_page = TIMEZONES[start_idx:end_idx]
    
    # Проверяем наличие предыдущей и следующей страницы
    has_prev = page > 0
    has_next = page < total_pages - 1
    
    return timezones_on_page, total_pages, has_prev, has_next


def get_timezone_offset_str(timezone_name: str) -> str:
    """
    Возвращает строку с UTC offset для часового пояса
    
    Args:
        timezone_name: Имя timezone (например, "Europe/Moscow")
        
    Returns:
        Строка вида "UTC+3" или "UTC-5"
        
    Examples:
        >>> get_timezone_offset_str("Europe/Moscow")
        'UTC+3'
    """
    tz = get_timezone_by_name(timezone_name)
    if tz:
        offset = tz[2]
        if offset >= 0:
            return f"UTC+{offset}"
        else:
            return f"UTC{offset}"
    return "UTC+0"


# Экспорт основных функций
__all__ = [
    'TIMEZONES',
    'DEFAULT_TIMEZONE',
    'TIMEZONES_PER_PAGE',
    'get_timezone_by_name',
    'get_timezone_display_name',
    'validate_timezone',
    'get_timezones_page',
    'get_timezone_offset_str',
]

