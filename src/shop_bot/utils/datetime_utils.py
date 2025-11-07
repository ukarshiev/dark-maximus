# -*- coding: utf-8 -*-
"""
Утилиты для работы с датой и временем с поддержкой timezone

Этот модуль обеспечивает:
- Корректное хранение дат в UTC в БД (без tzinfo)
- Конвертацию для отображения пользователю
- Обратную совместимость со старым кодом
"""

from datetime import datetime, timezone, timedelta, tzinfo
from typing import Optional, Tuple
import logging

# Константы
UTC = timezone.utc

# Moscow timezone: пробуем использовать ZoneInfo, если не получается - fallback на timedelta
try:
    from zoneinfo import ZoneInfo
    try:
        MOSCOW_TZ = ZoneInfo("Europe/Moscow")
    except Exception:
        # Fallback на Windows или системах без tzdata
        MOSCOW_TZ = timezone(timedelta(hours=3))
        logging.warning("ZoneInfo 'Europe/Moscow' недоступен, используем статический UTC+3")
except ImportError:
    # Python < 3.9 или tzdata не установлена
    MOSCOW_TZ = timezone(timedelta(hours=3))
    logging.warning("ZoneInfo не доступен (Python < 3.9 или tzdata не установлена), используем статический UTC+3")

# Дефолтная timezone для панели управления (UTC+3 / Europe/Moscow)
DEFAULT_PANEL_TIMEZONE = "Europe/Moscow"


def _load_timezone(timezone_name: Optional[str]) -> tzinfo:
    """Возвращает tzinfo для указанного timezone с fallback на Москву."""
    if not timezone_name:
        return MOSCOW_TZ

    try:
        from zoneinfo import ZoneInfo  # type: ignore

        return ZoneInfo(timezone_name)
    except Exception as exc:
        logging.warning(
            "Не удалось загрузить timezone %s, используем Moscow: %s",
            timezone_name,
            exc,
        )
        return MOSCOW_TZ


def normalize_to_timezone(dt: datetime, timezone_name: Optional[str]) -> datetime:
    """Конвертирует datetime в указанный timezone (aware)."""
    tz = _load_timezone(timezone_name)

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)

    return dt.astimezone(tz)


def ensure_isoformat_for_timezone(dt: Optional[datetime], timezone_name: Optional[str]) -> Optional[str]:
    """Возвращает ISO строку в заданном timezone или None."""
    if dt is None:
        return None

    localized = normalize_to_timezone(dt, timezone_name)
    return localized.isoformat()


def get_timezone_meta(timezone_name: Optional[str]) -> Tuple[str, str]:
    """Возвращает (timezone_name, offset_str) c fallback."""
    tz = _load_timezone(timezone_name)
    tz_name = timezone_name
    if hasattr(tz, "key"):
        tz_name = getattr(tz, "key")
    if not tz_name:
        tz_name = "Europe/Moscow"

    current_local = datetime.now(UTC).astimezone(tz)
    offset_text = _format_utc_offset(current_local.utcoffset())
    return tz_name, offset_text


def format_datetime_for_timezone(
    dt: datetime,
    timezone_name: Optional[str],
    fmt: str = "%d.%m.%Y %H:%M",
    include_offset: bool = False,
    fallback: str = "N/A",
) -> str:
    """Форматирует datetime для указанного timezone."""
    if dt is None:
        return fallback

    try:
        localized = normalize_to_timezone(dt, timezone_name)
    except Exception as exc:
        logging.warning("Не удалось преобразовать дату %s: %s", dt, exc)
        return fallback

    result = localized.strftime(fmt)
    if include_offset:
        offset = _format_utc_offset(localized.utcoffset())
        result = f"{result} ({offset})"
    return result


def ensure_utc_datetime(dt: datetime) -> datetime:
    """
    Гарантирует, что datetime в UTC без tzinfo для записи в БД
    
    Args:
        dt: datetime объект (может быть naive или aware)
        
    Returns:
        datetime в UTC без tzinfo (naive UTC)
        
    Examples:
        >>> from datetime import datetime, timezone, timedelta
        >>> dt_utc = datetime(2025, 1, 1, 12, 0, tzinfo=timezone.utc)
        >>> result = ensure_utc_datetime(dt_utc)
        >>> result.tzinfo is None
        True
        >>> result.hour
        12
        
        >>> moscow_tz = timezone(timedelta(hours=3))
        >>> dt_moscow = datetime(2025, 1, 1, 15, 0, tzinfo=moscow_tz)
        >>> result = ensure_utc_datetime(dt_moscow)
        >>> result.hour
        12
    """
    if dt.tzinfo is None:
        # Если naive, предполагаем что это UTC (для обратной совместимости)
        logging.warning(
            f"ensure_utc_datetime: получен naive datetime {dt}, "
            "предполагаем что это UTC. Рекомендуется всегда передавать aware datetime."
        )
        return dt
    
    # Конвертируем в UTC и убираем tzinfo
    return dt.astimezone(UTC).replace(tzinfo=None)


def timestamp_to_utc_datetime(timestamp_ms: int) -> datetime:
    """
    Конвертирует timestamp (миллисекунды) в UTC datetime без tzinfo
    
    Args:
        timestamp_ms: timestamp в миллисекундах
        
    Returns:
        datetime в UTC без tzinfo (naive UTC)
        
    Examples:
        >>> result = timestamp_to_utc_datetime(1735732800000)  # 2025-01-01 12:00:00 UTC
        >>> result.tzinfo is None
        True
        >>> result.year
        2025
    """
    # Конвертируем миллисекунды в секунды и создаем aware datetime в UTC
    dt_utc = datetime.fromtimestamp(timestamp_ms / 1000, tz=UTC)
    
    # Убираем tzinfo для совместимости с БД
    return dt_utc.replace(tzinfo=None)


def _format_utc_offset(offset: Optional[timedelta]) -> str:
    """Форматирует смещение таймзоны в строку вида UTC+3 или UTC-05:30"""
    if offset is None:
        return "UTC+0"

    total_minutes = int(offset.total_seconds() // 60)
    sign = '+' if total_minutes >= 0 else '-'
    abs_minutes = abs(total_minutes)
    hours = abs_minutes // 60
    minutes = abs_minutes % 60

    if minutes == 0:
        return f"UTC{sign}{hours}"

    return f"UTC{sign}{hours:02d}:{minutes:02d}"


def format_datetime_moscow(dt: datetime) -> str:
    """
    Legacy функция для обратной совместимости
    Форматирует datetime в московское время
    
    Args:
        dt: datetime объект (naive UTC или aware)
        
    Returns:
        Строка формата "DD.MM.YYYY в HH:MM" (московское время)
        
    Examples:
        >>> dt = datetime(2025, 1, 1, 12, 0)  # naive UTC
        >>> result = format_datetime_moscow(dt)
        >>> "01.01.2025" in result
        True
    """
    # Если naive, считаем что это UTC
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    
    # Конвертируем в московское время
    dt_moscow = dt.astimezone(MOSCOW_TZ)
    
    offset_text = _format_utc_offset(dt_moscow.utcoffset())
    return f"{dt_moscow.strftime('%d.%m.%Y в %H:%M')} ({offset_text})"


def format_datetime_for_user(
    dt: datetime,
    user_timezone: Optional[str] = None,
    feature_enabled: bool = False
) -> str:
    """
    Форматирует datetime с учётом timezone пользователя (с feature flag)
    
    Args:
        dt: datetime объект (naive UTC или aware)
        user_timezone: timezone пользователя (например, "Europe/Moscow")
                      Если None, используется Moscow по умолчанию
        feature_enabled: включен ли feature flag timezone support
        
    Returns:
        Строка формата "DD.MM.YYYY в HH:MM" в нужном часовом поясе
        
    Examples:
        >>> dt = datetime(2025, 1, 1, 12, 0)  # naive UTC
        >>> result = format_datetime_for_user(dt, feature_enabled=False)
        >>> "01.01.2025" in result
        True
    """
    # Если feature flag выключен, используем legacy функцию
    if not feature_enabled:
        return format_datetime_moscow(dt)
    
    # Если naive, считаем что это UTC
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    
    # Определяем timezone пользователя
    try:
        if user_timezone:
            try:
                from zoneinfo import ZoneInfo
                tz = ZoneInfo(user_timezone)
            except (ImportError, Exception) as e:
                logging.warning(f"Не удалось загрузить timezone {user_timezone}, используем Moscow: {e}")
                tz = MOSCOW_TZ
        else:
            tz = MOSCOW_TZ
    except Exception as e:
        logging.warning(f"Invalid timezone {user_timezone}, falling back to Moscow: {e}")
        tz = MOSCOW_TZ
    
    # Конвертируем в нужный timezone
    dt_local = dt.astimezone(tz)

    offset_text = _format_utc_offset(dt_local.utcoffset())

    return f"{dt_local.strftime('%d.%m.%Y в %H:%M')} ({offset_text})"


def get_current_utc_naive() -> datetime:
    """
    Возвращает текущее время в UTC без tzinfo (naive)
    Полезно для записи в БД
    
    Returns:
        datetime текущего времени в UTC без tzinfo
        
    Examples:
        >>> result = get_current_utc_naive()
        >>> result.tzinfo is None
        True
    """
    return datetime.now(UTC).replace(tzinfo=None)


def get_moscow_now() -> datetime:
    """
    Возвращает текущее время в московском timezone (aware)
    Legacy функция для обратной совместимости
    
    Returns:
        datetime текущего времени в московском timezone
        
    Examples:
        >>> result = get_moscow_now()
        >>> result.tzinfo is not None
        True
    """
    return datetime.now(MOSCOW_TZ)


def calculate_remaining_seconds(expiry_timestamp_ms: int) -> int:
    """
    Вычисляет оставшиеся секунды до истечения срока
    
    Args:
        expiry_timestamp_ms: timestamp истечения в миллисекундах
        
    Returns:
        Количество оставшихся секунд (не может быть отрицательным)
        
    Examples:
        >>> from datetime import datetime, timezone
        >>> future_time = int((datetime.now(timezone.utc).timestamp() + 3600) * 1000)
        >>> result = calculate_remaining_seconds(future_time)
        >>> 3500 < result < 3700  # примерно 1 час
        True
    """
    now_ms = int(datetime.now(UTC).timestamp() * 1000)
    return max(0, int((expiry_timestamp_ms - now_ms) / 1000))


# Экспорт основных функций
__all__ = [
    'ensure_utc_datetime',
    'timestamp_to_utc_datetime',
    'format_datetime_moscow',
    'format_datetime_for_user',
    'get_current_utc_naive',
    'get_moscow_now',
    'calculate_remaining_seconds',
    'UTC',
    'MOSCOW_TZ',
    'DEFAULT_PANEL_TIMEZONE',
    'normalize_to_timezone',
    'ensure_isoformat_for_timezone',
    'get_timezone_meta',
    'format_datetime_for_timezone',
]

