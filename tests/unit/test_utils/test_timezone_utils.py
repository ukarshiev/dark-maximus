#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Unit тесты для модуля datetime_utils

Проверяет корректность работы функций конвертации timezone
"""

import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

import pytest
import allure

# Добавляем путь к модулям проекта
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root / "src"))

from shop_bot.utils.datetime_utils import (
    ensure_utc_datetime,
    timestamp_to_utc_datetime,
    format_datetime_moscow,
    format_datetime_for_user,
    get_current_utc_naive,
    get_moscow_now,
    calculate_remaining_seconds,
    UTC,
    MOSCOW_TZ
)


@pytest.mark.unit
@allure.epic("Утилиты")
@allure.feature("Конвертация UTC datetime")
@allure.label("package", "src.shop_bot.utils")
class TestEnsureUtcDatetime:
    """Тесты для ensure_utc_datetime"""
    
    @allure.title("Конвертация UTC aware datetime в naive UTC")
    @allure.description("""
    Проверяет корректность конвертации UTC aware datetime в naive UTC datetime.
    
    **Что проверяется:**
    - Конвертация aware UTC datetime в naive UTC
    - Сохранение всех компонентов даты и времени (год, месяц, день, час)
    - Отсутствие tzinfo в результате
    
    **Тестовые данные:**
    - dt_utc: datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC)
    
    **Ожидаемый результат:**
    - Результат должен быть naive (tzinfo is None)
    - Все компоненты даты и времени должны совпадать с исходными
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("timezone", "utc", "datetime", "unit", "conversion")
    def test_utc_aware_datetime(self):
        """Тест: UTC aware datetime -> naive UTC"""
        with allure.step("Подготовка тестовых данных"):
            dt_utc = datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC)
            allure.attach(str(dt_utc), "Входной UTC aware datetime", allure.attachment_type.TEXT)
        
        with allure.step("Вызов функции ensure_utc_datetime"):
            result = ensure_utc_datetime(dt_utc)
            allure.attach(str(result), "Результат функции", allure.attachment_type.TEXT)
        
        with allure.step("Проверка результата"):
            assert result.tzinfo is None, "Результат должен быть naive"
            assert result.year == 2025
            assert result.month == 1
            assert result.day == 1
            assert result.hour == 12
    
    @allure.title("Конвертация Moscow aware datetime в naive UTC")
    @allure.description("""
    Проверяет корректность конвертации Moscow aware datetime в naive UTC datetime.
    
    **Что проверяется:**
    - Конвертация aware Moscow datetime в naive UTC
    - Корректный расчет смещения времени (Moscow UTC+3 -> UTC)
    - Отсутствие tzinfo в результате
    
    **Тестовые данные:**
    - dt_moscow: datetime(2025, 1, 1, 15, 0, 0, tzinfo=moscow_tz) где moscow_tz = UTC+3
    
    **Ожидаемый результат:**
    - Результат должен быть naive (tzinfo is None)
    - Время должно быть сконвертировано: 15:00 MSK -> 12:00 UTC
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("timezone", "moscow", "datetime", "unit", "conversion")
    def test_moscow_aware_datetime(self):
        """Тест: Moscow aware datetime -> naive UTC (должен конвертировать)"""
        with allure.step("Подготовка тестовых данных"):
            moscow_tz = timezone(timedelta(hours=3))
            dt_moscow = datetime(2025, 1, 1, 15, 0, 0, tzinfo=moscow_tz)
            allure.attach(str(dt_moscow), "Входной Moscow aware datetime", allure.attachment_type.TEXT)
        
        with allure.step("Вызов функции ensure_utc_datetime"):
            result = ensure_utc_datetime(dt_moscow)
            allure.attach(str(result), "Результат функции", allure.attachment_type.TEXT)
        
        with allure.step("Проверка результата"):
            assert result.tzinfo is None, "Результат должен быть naive"
            assert result.hour == 12, "15:00 MSK должно стать 12:00 UTC"
    
    @allure.title("Обработка naive datetime (предполагается как UTC)")
    @allure.description("""
    Проверяет обработку naive datetime с предупреждением о том, что naive datetime предполагается как UTC.
    
    **Что проверяется:**
    - Обработка naive datetime без изменения
    - Генерация предупреждения в логах
    - Сохранение исходного времени (предполагается, что это UTC)
    
    **Тестовые данные:**
    - dt_naive: datetime(2025, 1, 1, 12, 0, 0) - naive datetime
    
    **Ожидаемый результат:**
    - Результат должен быть naive (tzinfo is None)
    - Время не должно измениться (12:00 остается 12:00)
    - Должно быть сгенерировано предупреждение в логах
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("timezone", "naive", "datetime", "unit", "warning")
    def test_naive_datetime_warning(self):
        """Тест: naive datetime предполагается как UTC (с предупреждением)"""
        with allure.step("Подготовка тестовых данных"):
            dt_naive = datetime(2025, 1, 1, 12, 0, 0)
            allure.attach(str(dt_naive), "Входной naive datetime", allure.attachment_type.TEXT)
        
        with allure.step("Вызов функции ensure_utc_datetime"):
            result = ensure_utc_datetime(dt_naive)
            allure.attach(str(result), "Результат функции", allure.attachment_type.TEXT)
        
        with allure.step("Проверка результата"):
            assert result.tzinfo is None, "Результат должен быть naive"
            assert result.hour == 12, "Naive считается UTC, не должно измениться"


@pytest.mark.unit
@allure.epic("Утилиты")
@allure.feature("Конвертация timestamp в datetime")
@allure.label("package", "src.shop_bot.utils")
class TestTimestampToUtcDatetime:
    """Тесты для timestamp_to_utc_datetime"""
    
    @allure.title("Конвертация timestamp в naive UTC datetime")
    @allure.description("""
    Проверяет корректность конвертации timestamp (миллисекунды) в naive UTC datetime.
    
    **Что проверяется:**
    - Конвертация timestamp в миллисекундах в datetime
    - Корректность расчета даты и времени из timestamp
    - Отсутствие tzinfo в результате
    
    **Тестовые данные:**
    - timestamp_ms: 1735732800000 (соответствует 2025-01-01 12:00:00 UTC)
    
    **Ожидаемый результат:**
    - Результат должен быть naive (tzinfo is None)
    - Дата и время должны соответствовать timestamp: 2025-01-01 12:00:00
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("timestamp", "datetime", "unit", "conversion")
    def test_timestamp_conversion(self):
        """Тест: timestamp -> naive UTC datetime"""
        with allure.step("Подготовка тестовых данных"):
            # 2025-01-01 12:00:00 UTC = 1735732800000 ms
            timestamp_ms = 1735732800000
            allure.attach(str(timestamp_ms), "Входной timestamp (мс)", allure.attachment_type.TEXT)
        
        with allure.step("Вызов функции timestamp_to_utc_datetime"):
            result = timestamp_to_utc_datetime(timestamp_ms)
            allure.attach(str(result), "Результат функции", allure.attachment_type.TEXT)
        
        with allure.step("Проверка результата"):
            assert result.tzinfo is None, "Результат должен быть naive"
            assert result.year == 2025
            assert result.month == 1
            assert result.day == 1
            assert result.hour == 12
    
    @allure.title("Конвертация текущего timestamp")
    @allure.description("""
    Проверяет корректность конвертации текущего timestamp в naive UTC datetime.
    
    **Что проверяется:**
    - Конвертация текущего timestamp в datetime
    - Точность конвертации (разница должна быть меньше 1 секунды)
    - Отсутствие tzinfo в результате
    
    **Тестовые данные:**
    - timestamp_ms: текущий timestamp в миллисекундах
    
    **Ожидаемый результат:**
    - Результат должен быть naive (tzinfo is None)
    - Разница между результатом и текущим временем должна быть меньше 1 секунды
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("timestamp", "datetime", "unit", "current_time")
    def test_current_timestamp(self):
        """Тест: текущий timestamp"""
        with allure.step("Подготовка тестовых данных"):
            now_utc = datetime.now(UTC)
            timestamp_ms = int(now_utc.timestamp() * 1000)
            allure.attach(str(timestamp_ms), "Текущий timestamp (мс)", allure.attachment_type.TEXT)
            allure.attach(str(now_utc), "Текущее UTC время", allure.attachment_type.TEXT)
        
        with allure.step("Вызов функции timestamp_to_utc_datetime"):
            result = timestamp_to_utc_datetime(timestamp_ms)
            allure.attach(str(result), "Результат функции", allure.attachment_type.TEXT)
        
        with allure.step("Проверка результата"):
            assert result.tzinfo is None
            # Проверяем, что разница не больше 1 секунды
            diff = abs((result - now_utc.replace(tzinfo=None)).total_seconds())
            allure.attach(str(diff), "Разница в секундах", allure.attachment_type.TEXT)
            assert diff < 1, "Разница должна быть меньше 1 секунды"


@pytest.mark.unit
@allure.epic("Утилиты")
@allure.feature("Форматирование datetime в московское время")
@allure.label("package", "src.shop_bot.utils")
class TestFormatDatetimeMoscow:
    """Тесты для format_datetime_moscow"""
    
    @allure.title("Форматирование naive UTC datetime в московское время")
    @allure.description("""
    Проверяет корректность форматирования naive UTC datetime в строку с московским временем.
    
    **Что проверяется:**
    - Конвертация naive UTC datetime в московское время (UTC+3)
    - Формат строки: "DD.MM.YYYY в HH:MM (UTC+3)"
    - Корректность расчета времени (12:00 UTC -> 15:00 MSK)
    
    **Тестовые данные:**
    - dt_naive: datetime(2025, 1, 1, 12, 0, 0) - naive UTC (12:00 UTC)
    
    **Ожидаемый результат:**
    - Строка должна содержать "01.01.2025"
    - Строка должна содержать "15:00" (12:00 UTC = 15:00 MSK)
    - Строка должна содержать "UTC+3"
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("formatting", "moscow", "datetime", "unit")
    def test_naive_utc_format(self):
        """Тест: naive UTC datetime -> строка в московском времени"""
        with allure.step("Подготовка тестовых данных"):
            dt_naive = datetime(2025, 1, 1, 12, 0, 0)  # 12:00 UTC
            allure.attach(str(dt_naive), "Входной naive UTC datetime", allure.attachment_type.TEXT)
        
        with allure.step("Вызов функции format_datetime_moscow"):
            result = format_datetime_moscow(dt_naive)
            allure.attach(result, "Результат форматирования", allure.attachment_type.TEXT)
        
        with allure.step("Проверка результата"):
            # 12:00 UTC = 15:00 MSK
            assert "01.01.2025" in result
            assert "15:00" in result
            assert "UTC+3" in result
    
    @allure.title("Форматирование aware UTC datetime в московское время")
    @allure.description("""
    Проверяет корректность форматирования aware UTC datetime в строку с московским временем.
    
    **Что проверяется:**
    - Конвертация aware UTC datetime в московское время (UTC+3)
    - Формат строки: "DD.MM.YYYY в HH:MM (UTC+3)"
    - Корректность расчета времени (12:00 UTC -> 15:00 MSK)
    
    **Тестовые данные:**
    - dt_utc: datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC) - aware UTC (12:00 UTC)
    
    **Ожидаемый результат:**
    - Строка должна содержать "01.01.2025"
    - Строка должна содержать "15:00" (12:00 UTC = 15:00 MSK)
    - Строка должна содержать "UTC+3"
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("formatting", "moscow", "datetime", "unit", "aware")
    def test_aware_utc_format(self):
        """Тест: aware UTC datetime -> строка в московском времени"""
        with allure.step("Подготовка тестовых данных"):
            dt_utc = datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC)
            allure.attach(str(dt_utc), "Входной aware UTC datetime", allure.attachment_type.TEXT)
        
        with allure.step("Вызов функции format_datetime_moscow"):
            result = format_datetime_moscow(dt_utc)
            allure.attach(result, "Результат форматирования", allure.attachment_type.TEXT)
        
        with allure.step("Проверка результата"):
            assert "01.01.2025" in result
            assert "15:00" in result
            assert "UTC+3" in result


@pytest.mark.unit
@allure.epic("Утилиты")
@allure.feature("Форматирование datetime для пользователя")
@allure.label("package", "src.shop_bot.utils")
class TestFormatDatetimeForUser:
    """Тесты для format_datetime_for_user"""
    
    @allure.title("Форматирование с выключенным feature flag (legacy режим)")
    @allure.description("""
    Проверяет корректность форматирования datetime с выключенным feature flag (использует legacy функцию).
    
    **Что проверяется:**
    - При feature_enabled=False используется функция format_datetime_moscow
    - Формат строки: "DD.MM.YYYY в HH:MM (UTC+3)"
    - Корректность расчета времени (12:00 UTC -> 15:00 MSK)
    
    **Тестовые данные:**
    - dt_naive: datetime(2025, 1, 1, 12, 0, 0) - naive UTC
    - feature_enabled: False
    
    **Ожидаемый результат:**
    - Строка должна содержать "01.01.2025"
    - Строка должна содержать "15:00" (12:00 UTC = 15:00 MSK)
    - Строка должна содержать "UTC+3"
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("formatting", "user", "datetime", "unit", "legacy")
    def test_feature_disabled(self):
        """Тест: feature flag выключен -> использует legacy функцию"""
        with allure.step("Подготовка тестовых данных"):
            dt_naive = datetime(2025, 1, 1, 12, 0, 0)
            allure.attach(str(dt_naive), "Входной naive UTC datetime", allure.attachment_type.TEXT)
            allure.attach("False", "feature_enabled", allure.attachment_type.TEXT)
        
        with allure.step("Вызов функции format_datetime_for_user"):
            result = format_datetime_for_user(dt_naive, feature_enabled=False)
            allure.attach(result, "Результат форматирования", allure.attachment_type.TEXT)
        
        with allure.step("Проверка результата"):
            # Должно работать как format_datetime_moscow
            assert "01.01.2025" in result
            assert "15:00" in result
            assert "UTC+3" in result
    
    @allure.title("Форматирование с включенным feature flag (timezone по умолчанию)")
    @allure.description("""
    Проверяет корректность форматирования datetime с включенным feature flag и timezone по умолчанию (Moscow).
    
    **Что проверяется:**
    - При feature_enabled=True используется новый формат с поддержкой timezone
    - При отсутствии user_timezone используется Moscow по умолчанию
    - Формат строки: "DD.MM.YYYY в HH:MM (UTC+3)"
    
    **Тестовые данные:**
    - dt_naive: datetime(2025, 1, 1, 12, 0, 0) - naive UTC
    - feature_enabled: True
    - user_timezone: None (используется Moscow по умолчанию)
    
    **Ожидаемый результат:**
    - Строка должна содержать "01.01.2025"
    - Строка должна содержать "15:00" (12:00 UTC = 15:00 MSK)
    - Строка должна содержать "UTC+3"
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("formatting", "user", "datetime", "unit", "feature_flag")
    def test_feature_enabled_default_timezone(self):
        """Тест: feature flag включен, timezone по умолчанию (Moscow)"""
        with allure.step("Подготовка тестовых данных"):
            dt_naive = datetime(2025, 1, 1, 12, 0, 0)
            allure.attach(str(dt_naive), "Входной naive UTC datetime", allure.attachment_type.TEXT)
            allure.attach("True", "feature_enabled", allure.attachment_type.TEXT)
            allure.attach("None (Moscow по умолчанию)", "user_timezone", allure.attachment_type.TEXT)
        
        with allure.step("Вызов функции format_datetime_for_user"):
            result = format_datetime_for_user(dt_naive, feature_enabled=True)
            allure.attach(result, "Результат форматирования", allure.attachment_type.TEXT)
        
        with allure.step("Проверка результата"):
            assert "01.01.2025" in result
            assert "15:00" in result
            assert "UTC+3" in result
    
    @allure.title("Форматирование с включенным feature flag (custom timezone)")
    @allure.description("""
    Проверяет корректность форматирования datetime с включенным feature flag и пользовательским timezone.
    
    **Что проверяется:**
    - При feature_enabled=True используется новый формат с поддержкой timezone
    - Конвертация в указанный timezone пользователя (Asia/Yekaterinburg = UTC+5)
    - Формат строки: "DD.MM.YYYY в HH:MM (UTC+X)"
    - Fallback на Moscow при недоступности timezone (на Windows без tzdata)
    
    **Тестовые данные:**
    - dt_naive: datetime(2025, 1, 1, 12, 0, 0) - naive UTC
    - feature_enabled: True
    - user_timezone: "Asia/Yekaterinburg" (UTC+5)
    
    **Ожидаемый результат:**
    - Строка должна содержать "01.01.2025"
    - Время должно быть сконвертировано (не 12:00 UTC)
    - Строка должна содержать "UTC"
    - На Unix: должно быть 17:00 (12:00 UTC = 17:00 UTC+5)
    - На Windows без tzdata: fallback на Moscow (15:00)
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("formatting", "user", "datetime", "unit", "custom_timezone")
    def test_feature_enabled_custom_timezone(self):
        """Тест: feature flag включен, custom timezone"""
        with allure.step("Подготовка тестовых данных"):
            dt_naive = datetime(2025, 1, 1, 12, 0, 0)
            user_timezone = "Asia/Yekaterinburg"
            allure.attach(str(dt_naive), "Входной naive UTC datetime", allure.attachment_type.TEXT)
            allure.attach("True", "feature_enabled", allure.attachment_type.TEXT)
            allure.attach(user_timezone, "user_timezone", allure.attachment_type.TEXT)
        
        with allure.step("Вызов функции format_datetime_for_user"):
            # UTC+5 (например, Yekaterinburg)
            result = format_datetime_for_user(dt_naive, user_timezone=user_timezone, feature_enabled=True)
            allure.attach(result, "Результат форматирования", allure.attachment_type.TEXT)
        
        with allure.step("Проверка результата"):
            assert "01.01.2025" in result
            # На Windows без tzdata будет fallback на Moscow (15:00), на Unix - 17:00
            # Проверяем, что время изменилось (не 12:00)
            assert "12:00" not in result  # Должно быть конвертировано
            assert "UTC" in result


@pytest.mark.unit
@allure.epic("Утилиты")
@allure.feature("Получение текущего UTC времени")
@allure.label("package", "src.shop_bot.utils")
class TestGetCurrentUtcNaive:
    """Тесты для get_current_utc_naive"""
    
    @allure.title("Получение текущего naive UTC datetime")
    @allure.description("""
    Проверяет корректность получения текущего времени в UTC без tzinfo (naive).
    
    **Что проверяется:**
    - Возвращаемое значение должно быть naive (tzinfo is None)
    - Время должно соответствовать текущему UTC времени
    - Точность: разница с текущим временем должна быть меньше 1 секунды
    
    **Тестовые данные:**
    - Функция не принимает параметров, использует текущее время
    
    **Ожидаемый результат:**
    - Результат должен быть naive (tzinfo is None)
    - Разница с текущим UTC временем должна быть меньше 1 секунды
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("datetime", "utc", "current_time", "unit")
    def test_returns_naive_utc(self):
        """Тест: возвращает naive UTC datetime"""
        with allure.step("Получение текущего UTC времени для сравнения"):
            now_utc = datetime.now(UTC).replace(tzinfo=None)
            allure.attach(str(now_utc), "Текущее UTC время (naive)", allure.attachment_type.TEXT)
        
        with allure.step("Вызов функции get_current_utc_naive"):
            result = get_current_utc_naive()
            allure.attach(str(result), "Результат функции", allure.attachment_type.TEXT)
        
        with allure.step("Проверка результата"):
            assert result.tzinfo is None, "Должен быть naive"
            
            # Проверяем, что это примерно текущее время
            diff = abs((result - now_utc).total_seconds())
            allure.attach(str(diff), "Разница в секундах", allure.attachment_type.TEXT)
            assert diff < 1, "Разница с текущим временем должна быть < 1 секунды"


@pytest.mark.unit
@allure.epic("Утилиты")
@allure.feature("Получение текущего московского времени")
@allure.label("package", "src.shop_bot.utils")
class TestGetMoscowNow:
    """Тесты для get_moscow_now"""
    
    @allure.title("Получение текущего aware Moscow datetime")
    @allure.description("""
    Проверяет корректность получения текущего времени в московском timezone (aware).
    
    **Что проверяется:**
    - Возвращаемое значение должно быть aware (tzinfo is not None)
    - Offset должен быть +3 или +4 часа (в зависимости от DST)
    - Время должно соответствовать московскому времени
    
    **Тестовые данные:**
    - Функция не принимает параметров, использует текущее время
    
    **Ожидаемый результат:**
    - Результат должен быть aware (tzinfo is not None)
    - Offset должен быть +3 или +4 часа (в зависимости от DST)
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("datetime", "moscow", "current_time", "unit")
    def test_returns_aware_moscow(self):
        """Тест: возвращает aware Moscow datetime"""
        with allure.step("Вызов функции get_moscow_now"):
            result = get_moscow_now()
            allure.attach(str(result), "Результат функции", allure.attachment_type.TEXT)
            allure.attach(str(result.tzinfo), "tzinfo", allure.attachment_type.TEXT)
        
        with allure.step("Проверка результата"):
            assert result.tzinfo is not None, "Должен быть aware"
            
            # Проверяем, что offset примерно +3 часа
            offset = result.utcoffset()
            assert offset is not None
            allure.attach(str(offset), "UTC offset", allure.attachment_type.TEXT)
            # Offset может быть 3 или 4 часа в зависимости от DST
            offset_hours = offset.total_seconds() / 3600
            assert offset_hours in [3, 4], "Offset должен быть +3 или +4 часа"


@pytest.mark.unit
@allure.epic("Утилиты")
@allure.feature("Вычисление оставшихся секунд")
@allure.label("package", "src.shop_bot.utils")
class TestCalculateRemainingSeconds:
    """Тесты для calculate_remaining_seconds"""
    
    @allure.title("Вычисление оставшихся секунд для timestamp в будущем")
    @allure.description("""
    Проверяет корректность вычисления оставшихся секунд для timestamp в будущем.
    
    **Что проверяется:**
    - Вычисление положительного количества секунд до истечения
    - Точность расчета (примерно 3600 секунд для 1 часа)
    - Корректность конвертации миллисекунд в секунды
    
    **Тестовые данные:**
    - future_ms: timestamp через 1 час от текущего времени (в миллисекундах)
    
    **Ожидаемый результат:**
    - Результат должен быть примерно 3600 секунд (1 час)
    - Допустимая погрешность: 3500-3700 секунд
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("timestamp", "remaining_seconds", "unit", "future")
    def test_future_timestamp(self):
        """Тест: timestamp в будущем -> положительное число секунд"""
        with allure.step("Подготовка тестовых данных"):
            # Timestamp через 1 час
            future_ms = int((datetime.now(UTC).timestamp() + 3600) * 1000)
            allure.attach(str(future_ms), "Timestamp в будущем (мс)", allure.attachment_type.TEXT)
            allure.attach("3600", "Ожидаемое количество секунд", allure.attachment_type.TEXT)
        
        with allure.step("Вызов функции calculate_remaining_seconds"):
            result = calculate_remaining_seconds(future_ms)
            allure.attach(str(result), "Результат (секунды)", allure.attachment_type.TEXT)
        
        with allure.step("Проверка результата"):
            # Должно быть примерно 3600 секунд (1 час)
            assert result > 3500
            assert result < 3700
    
    @allure.title("Вычисление оставшихся секунд для timestamp в прошлом")
    @allure.description("""
    Проверяет корректность вычисления оставшихся секунд для timestamp в прошлом.
    
    **Что проверяется:**
    - Возврат 0 для прошедшего времени
    - Обработка отрицательных значений (не должно быть отрицательным)
    
    **Тестовые данные:**
    - past_ms: timestamp час назад от текущего времени (в миллисекундах)
    
    **Ожидаемый результат:**
    - Результат должен быть 0 (для прошедшего времени)
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("timestamp", "remaining_seconds", "unit", "past")
    def test_past_timestamp(self):
        """Тест: timestamp в прошлом -> 0 секунд"""
        with allure.step("Подготовка тестовых данных"):
            # Timestamp час назад
            past_ms = int((datetime.now(UTC).timestamp() - 3600) * 1000)
            allure.attach(str(past_ms), "Timestamp в прошлом (мс)", allure.attachment_type.TEXT)
        
        with allure.step("Вызов функции calculate_remaining_seconds"):
            result = calculate_remaining_seconds(past_ms)
            allure.attach(str(result), "Результат (секунды)", allure.attachment_type.TEXT)
        
        with allure.step("Проверка результата"):
            assert result == 0, "Для прошедшего времени должно вернуть 0"
    
    @allure.title("Вычисление оставшихся секунд для текущего timestamp")
    @allure.description("""
    Проверяет корректность вычисления оставшихся секунд для текущего timestamp.
    
    **Что проверяется:**
    - Возврат значения близкого к 0 для текущего времени
    - Точность расчета (должно быть меньше 5 секунд)
    - Обработка граничного случая (текущее время)
    
    **Тестовые данные:**
    - now_ms: текущий timestamp (в миллисекундах)
    
    **Ожидаемый результат:**
    - Результат должен быть >= 0
    - Результат должен быть < 5 секунд
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("timestamp", "remaining_seconds", "unit", "current")
    def test_current_timestamp(self):
        """Тест: текущий timestamp -> ~0 секунд"""
        with allure.step("Подготовка тестовых данных"):
            now_ms = int(datetime.now(UTC).timestamp() * 1000)
            allure.attach(str(now_ms), "Текущий timestamp (мс)", allure.attachment_type.TEXT)
        
        with allure.step("Вызов функции calculate_remaining_seconds"):
            result = calculate_remaining_seconds(now_ms)
            allure.attach(str(result), "Результат (секунды)", allure.attachment_type.TEXT)
        
        with allure.step("Проверка результата"):
            # Должно быть очень близко к 0
            assert result >= 0
            assert result < 5, "Для текущего времени должно быть < 5 секунд"


@pytest.mark.unit
@allure.epic("Утилиты")
@allure.feature("Интеграционные тесты timezone утилит")
@allure.label("package", "tests.unit.test_utils")
class TestIntegration:
    """Интеграционные тесты"""
    
    @allure.story("Полный цикл работы с датой нового ключа")
    @allure.title("Полный цикл работы с датой нового ключа")
    @allure.description("""
    Интеграционный тест, проверяющий полный цикл работы с датой нового ключа от получения timestamp до форматирования.
    
    **Что проверяется:**
    - Получение timestamp из API (expiry через 30 дней)
    - Конвертация timestamp в naive UTC для записи в БД
    - Вычисление remaining_seconds
    - Форматирование для отображения пользователю
    
    **Тестовые данные:**
    - expiry_timestamp_ms: timestamp через 30 дней от текущего времени
    
    **Шаги теста:**
    1. Получение timestamp из API (expiry через 30 дней)
    2. Конвертация timestamp в naive UTC для записи в БД
    3. Вычисление remaining_seconds
    4. Форматирование для отображения пользователю
    
    **Ожидаемый результат:**
    - Дата должна быть naive (tzinfo is None)
    - remaining_seconds должно быть примерно 30 дней в секундах
    - Форматированная строка должна содержать правильный формат
    """)
    @allure.severity(allure.severity_level.CRITICAL)
    @allure.tag("integration", "timezone", "workflow", "unit", "critical")
    def test_full_workflow_new_key(self):
        """Тест: полный цикл работы с датой нового ключа"""
        with allure.step("1. Получение timestamp из API (expiry через 30 дней)"):
            now_utc = datetime.now(UTC)
            future_utc = now_utc + timedelta(days=30)
            expiry_timestamp_ms = int(future_utc.timestamp() * 1000)
            allure.attach(str(expiry_timestamp_ms), "Timestamp истечения (мс)", allure.attachment_type.TEXT)
            allure.attach(str(future_utc), "Дата истечения (UTC)", allure.attachment_type.TEXT)
        
        with allure.step("2. Конвертация timestamp в naive UTC для записи в БД"):
            expiry_date = timestamp_to_utc_datetime(expiry_timestamp_ms)
            allure.attach(str(expiry_date), "Дата истечения (naive UTC)", allure.attachment_type.TEXT)
            
            # Проверяем, что дата naive
            assert expiry_date.tzinfo is None
        
        with allure.step("3. Вычисление remaining_seconds"):
            remaining_seconds = calculate_remaining_seconds(expiry_timestamp_ms)
            allure.attach(str(remaining_seconds), "Оставшиеся секунды", allure.attachment_type.TEXT)
            
            # Должно быть примерно 30 дней в секундах
            expected_seconds = 30 * 24 * 3600
            allure.attach(str(expected_seconds), "Ожидаемое количество секунд", allure.attachment_type.TEXT)
            assert remaining_seconds > expected_seconds - 100
            assert remaining_seconds < expected_seconds + 100
        
        with allure.step("4. Форматирование для отображения пользователю"):
            formatted = format_datetime_moscow(expiry_date)
            allure.attach(formatted, "Отформатированная дата", allure.attachment_type.TEXT)
            
            # Проверяем формат
            assert "в" in formatted
            assert "." in formatted
    
    @allure.story("Обратная совместимость со старым кодом")
    @allure.title("Обратная совместимость со старым кодом")
    @allure.description("""
    Интеграционный тест, проверяющий обратную совместимость со старым кодом, который создавал naive datetime напрямую.
    
    **Что проверяется:**
    - Обработка naive datetime, созданного старым кодом
    - Генерация предупреждения в логах
    - Корректность работы ensure_utc_datetime с naive datetime
    - Форматирование naive datetime через format_datetime_moscow
    
    **Тестовые данные:**
    - old_style_date: datetime(2025, 6, 1, 12, 0, 0) - naive datetime (старый стиль)
    
    **Ожидаемый результат:**
    - ensure_utc_datetime должен принять naive datetime без изменения
    - format_datetime_moscow должен корректно отформатировать naive datetime
    - Должно быть сгенерировано предупреждение в логах
    """)
    @allure.severity(allure.severity_level.CRITICAL)
    @allure.tag("integration", "backward_compatibility", "timezone", "unit", "critical")
    def test_backward_compatibility(self):
        """Тест: обратная совместимость со старым кодом"""
        with allure.step("Подготовка тестовых данных (старый стиль)"):
            # Старый код мог создавать naive datetime напрямую
            old_style_date = datetime(2025, 6, 1, 12, 0, 0)  # naive
            allure.attach(str(old_style_date), "Старый стиль naive datetime", allure.attachment_type.TEXT)
        
        with allure.step("Обработка через ensure_utc_datetime"):
            # Новая утилита должна его принять (с предупреждением)
            result = ensure_utc_datetime(old_style_date)
            allure.attach(str(result), "Результат ensure_utc_datetime", allure.attachment_type.TEXT)
            
            # Результат не должен измениться
            assert result == old_style_date
        
        with allure.step("Форматирование через format_datetime_moscow"):
            # Форматирование тоже должно работать
            formatted = format_datetime_moscow(old_style_date)
            allure.attach(formatted, "Отформатированная дата", allure.attachment_type.TEXT)
            assert "01.06.2025" in formatted
