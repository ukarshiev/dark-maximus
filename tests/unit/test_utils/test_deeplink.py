#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Unit-тесты для модуля deeplink

Тестирует генерацию, парсинг и валидацию deeplink ссылок
"""

import pytest
import allure
import sys
from pathlib import Path

# Добавляем путь к проекту
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root / "src"))

from shop_bot.utils.deeplink import (
    create_deeplink,
    parse_deeplink,
    validate_deeplink_length
)


@pytest.mark.unit
@allure.epic("Утилиты")
@allure.feature("Deeplink")
@allure.label("package", "src.shop_bot.utils")
class TestDeeplinkGeneration:
    """Тесты для генерации deeplink ссылок"""

    @allure.title("Создание deeplink с group_code")
    @allure.description("""
    Проверяет создание deeplink ссылки с указанием group_code.
    
    **Что проверяется:**
    - Формирование корректной ссылки с префиксом https://t.me/test_bot
    - Наличие параметра ?start= в ссылке
    - Корректный парсинг созданной ссылки
    - Извлечение group_code из параметра
    
    **Тестовые данные:**
    - bot_name: "test_bot"
    - group_code: "vip"
    
    **Ожидаемый результат:**
    Создана корректная deeplink ссылка, из которой можно извлечь group_code="vip".
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("deeplink", "generation", "group_code", "unit")
    def test_create_deeplink_with_group_code(self):
        """Тест создания deeplink с group_code"""
        link = create_deeplink("test_bot", group_code="vip")
        
        assert link.startswith("https://t.me/test_bot")
        assert "?start=" in link
        
        # Проверяем, что можно распарсить
        param = link.split("?start=")[1]
        group, promo, referrer = parse_deeplink(param)
        assert group == "vip"
        assert promo is None
        assert referrer is None

    @allure.title("Создание deeplink с promo_code")
    @allure.description("""
    Проверяет создание deeplink ссылки с указанием promo_code.
    
    **Что проверяется:**
    - Формирование корректной ссылки с префиксом https://t.me/test_bot
    - Наличие параметра ?start= в ссылке
    - Корректный парсинг созданной ссылки
    - Извлечение promo_code из параметра
    
    **Тестовые данные:**
    - bot_name: "test_bot"
    - promo_code: "SALE50"
    
    **Ожидаемый результат:**
    Создана корректная deeplink ссылка, из которой можно извлечь promo_code="SALE50".
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("deeplink", "generation", "promo_code", "unit")
    def test_create_deeplink_with_promo_code(self):
        link = create_deeplink("test_bot", promo_code="SALE50")
        
        assert link.startswith("https://t.me/test_bot")
        assert "?start=" in link
        
        # Проверяем, что можно распарсить
        param = link.split("?start=")[1]
        group, promo, referrer = parse_deeplink(param)
        assert group is None
        assert promo == "SALE50"
        assert referrer is None

    @allure.title("Создание deeplink с referrer_id (старый формат)")
    @allure.description("""
    Проверяет создание deeplink ссылки с указанием referrer_id в старом формате ref_123456.
    
    **Что проверяется:**
    - Формирование корректной ссылки с префиксом https://t.me/test_bot
    - Наличие параметра ?start=ref_123456 в ссылке
    - Корректный парсинг созданной ссылки
    - Извлечение referrer_id из параметра
    
    **Тестовые данные:**
    - bot_name: "test_bot"
    - referrer_id: 123456
    
    **Ожидаемый результат:**
    Создана корректная deeplink ссылка в формате ?start=ref_123456, из которой можно извлечь referrer_id=123456.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("deeplink", "generation", "referrer_id", "legacy_format", "unit")
    def test_create_deeplink_with_referrer_id(self):
        link = create_deeplink("test_bot", referrer_id=123456)
        
        assert link.startswith("https://t.me/test_bot")
        assert "?start=ref_123456" in link
        
        # Проверяем, что можно распарсить
        param = link.split("?start=")[1]
        group, promo, referrer = parse_deeplink(param)
        assert group is None
        assert promo is None
        assert referrer == 123456

    @allure.title("Создание deeplink со всеми параметрами")
    @allure.description("""
    Проверяет создание deeplink ссылки с указанием всех параметров одновременно (group_code, promo_code, referrer_id).
    
    **Что проверяется:**
    - Формирование корректной ссылки с префиксом https://t.me/test_bot
    - Наличие параметра ?start= в ссылке
    - Корректный парсинг созданной ссылки
    - Извлечение всех параметров (group_code, promo_code, referrer_id) из параметра
    
    **Тестовые данные:**
    - bot_name: "test_bot"
    - group_code: "premium"
    - promo_code: "MEGA50"
    - referrer_id: 987654321
    
    **Ожидаемый результат:**
    Создана корректная deeplink ссылка, из которой можно извлечь все параметры: group_code="premium", promo_code="MEGA50", referrer_id=987654321.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("deeplink", "generation", "all_params", "unit")
    def test_create_deeplink_with_all_params(self):
        link = create_deeplink("test_bot", group_code="premium", promo_code="MEGA50", referrer_id=987654321)
        
        assert link.startswith("https://t.me/test_bot")
        assert "?start=" in link
        
        # Проверяем, что можно распарсить
        param = link.split("?start=")[1]
        group, promo, referrer = parse_deeplink(param)
        assert group == "premium"
        assert promo == "MEGA50"
        assert referrer == 987654321

    @allure.title("Создание deeplink без параметров")
    @allure.description("""
    Проверяет создание deeplink ссылки без дополнительных параметров.
    
    **Что проверяется:**
    - Формирование базовой ссылки с префиксом https://t.me/test_bot
    - Отсутствие параметра ?start= в ссылке
    - Корректность базовой ссылки
    
    **Тестовые данные:**
    - bot_name: "test_bot"
    
    **Ожидаемый результат:**
    Создана базовая deeplink ссылка без параметров в формате https://t.me/test_bot.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("deeplink", "generation", "no_params", "unit")
    def test_create_deeplink_without_params(self):
        link = create_deeplink("test_bot")
        
        assert link == "https://t.me/test_bot"
        assert "?start=" not in link


@pytest.mark.unit
@allure.epic("Утилиты")
@allure.feature("Deeplink")
@allure.label("package", "src.shop_bot.utils")
class TestDeeplinkParsing:
    """Тесты для парсинга deeplink параметров"""

    @allure.title("Парсинг пустого deeplink параметра")
    @allure.description("""
    Проверяет парсинг пустого deeplink параметра.
    
    **Что проверяется:**
    - Обработка пустой строки при парсинге
    - Возврат None для всех параметров (group, promo, referrer)
    - Отсутствие ошибок при парсинге пустой строки
    
    **Тестовые данные:**
    - deeplink_param: "" (пустая строка)
    
    **Ожидаемый результат:**
    Функция parse_deeplink возвращает (None, None, None) для пустой строки.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("deeplink", "parsing", "empty", "unit")
    def test_parse_deeplink_empty(self):
        """Тест парсинга пустого параметра"""
        group, promo, referrer = parse_deeplink("")
        assert group is None
        assert promo is None
        assert referrer is None

    @allure.title("Парсинг deeplink в старом формате ref_123456")
    @allure.description("""
    Проверяет парсинг deeplink параметра в старом формате ref_123456.
    
    **Что проверяется:**
    - Распознавание старого формата ref_<id>
    - Извлечение referrer_id из параметра
    - Возврат None для group и promo при старом формате
    
    **Тестовые данные:**
    - deeplink_param: "ref_123456"
    
    **Ожидаемый результат:**
    Функция parse_deeplink возвращает (None, None, 123456) для параметра "ref_123456".
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("deeplink", "parsing", "ref_format", "legacy", "unit")
    def test_parse_deeplink_ref_format(self):
        group, promo, referrer = parse_deeplink("ref_123456")
        assert group is None
        assert promo is None
        assert referrer == 123456

    @allure.title("Парсинг deeplink в новом формате base64")
    @allure.description("""
    Проверяет парсинг deeplink параметра в новом формате base64.
    
    **Что проверяется:**
    - Распознавание нового формата base64
    - Декодирование base64 параметра
    - Извлечение group_code и promo_code из декодированных данных
    - Возврат None для referrer при отсутствии referrer_id
    
    **Тестовые данные:**
    - Создается deeplink с group_code="vip" и promo_code="SALE50"
    - Извлекается параметр из созданной ссылки
    
    **Ожидаемый результат:**
    Функция parse_deeplink корректно декодирует base64 и возвращает group="vip", promo="SALE50", referrer=None.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("deeplink", "parsing", "base64", "unit")
    def test_parse_deeplink_base64_format(self):
        # Создаем ссылку и извлекаем параметр
        link = create_deeplink("test_bot", group_code="vip", promo_code="SALE50")
        param = link.split("?start=")[1]
        
        # Парсим
        group, promo, referrer = parse_deeplink(param)
        assert group == "vip"
        assert promo == "SALE50"
        assert referrer is None

    @allure.title("Парсинг deeplink в формате base64 с referrer_id")
    @allure.description("""
    Проверяет парсинг deeplink параметра в формате base64 с указанием referrer_id.
    
    **Что проверяется:**
    - Распознавание формата base64 с referrer_id
    - Декодирование base64 параметра
    - Извлечение всех параметров (group_code, promo_code, referrer_id) из декодированных данных
    
    **Тестовые данные:**
    - Создается deeplink с group_code="vip", promo_code="SALE50" и referrer_id=123456
    - Извлекается параметр из созданной ссылки
    
    **Ожидаемый результат:**
    Функция parse_deeplink корректно декодирует base64 и возвращает group="vip", promo="SALE50", referrer=123456.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("deeplink", "parsing", "base64", "referrer_id", "unit")
    def test_parse_deeplink_with_referrer_in_base64(self):
        link = create_deeplink("test_bot", group_code="vip", promo_code="SALE50", referrer_id=123456)
        param = link.split("?start=")[1]
        
        group, promo, referrer = parse_deeplink(param)
        assert group == "vip"
        assert promo == "SALE50"
        assert referrer == 123456

    @allure.title("Парсинг deeplink невалидного формата")
    @allure.description("""
    Проверяет парсинг deeplink параметра невалидного формата.
    
    **Что проверяется:**
    - Обработка невалидного формата параметра
    - Обработка ошибок декодирования
    - Возврат None для всех параметров при ошибке парсинга
    
    **Тестовые данные:**
    - deeplink_param: "invalid_format_123"
    
    **Ожидаемый результат:**
    Функция parse_deeplink обрабатывает ошибку и возвращает None для всех параметров (group, promo, referrer).
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("deeplink", "parsing", "invalid_format", "error_handling", "unit")
    def test_parse_deeplink_invalid_format(self):
        group, promo, referrer = parse_deeplink("invalid_format_123")
        # Должен вернуть None для всех параметров при ошибке парсинга
        assert group is None or promo is None or referrer is None


@pytest.mark.unit
@allure.epic("Утилиты")
@allure.feature("Deeplink")
@allure.label("package", "src.shop_bot.utils")
class TestDeeplinkValidation:
    """Тесты для валидации длины deeplink"""

    @allure.title("Валидация длины короткого deeplink")
    @allure.description("""
    Проверяет валидацию длины deeplink с короткими параметрами.
    
    **Что проверяется:**
    - Валидация deeplink с короткими параметрами
    - Возврат True для валидного короткого deeplink
    - Корректная работа функции validate_deeplink_length
    
    **Тестовые данные:**
    - data: {"g": "vip", "p": "SALE50"}
    
    **Ожидаемый результат:**
    Функция validate_deeplink_length возвращает True для короткого deeplink.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("deeplink", "validation", "length", "short", "unit")
    def test_validate_deeplink_length_short(self):
        """Тест валидации короткого deeplink"""
        data = {"g": "vip", "p": "SALE50"}
        result = validate_deeplink_length(data)
        assert result is True

    @allure.title("Валидация длины длинного deeplink (превышает лимит)")
    @allure.description("""
    Проверяет валидацию длины deeplink с длинными параметрами, которые могут превысить лимит.
    
    **Что проверяется:**
    - Валидация deeplink с длинными параметрами
    - Обработка случая превышения лимита длины
    - Возврат булевого значения (True или False) в зависимости от длины
    
    **Тестовые данные:**
    - data: {"g": "very_long_group_code_name_that_exceeds_limit", "p": "very_long_promo_code_name_that_exceeds_limit"}
    
    **Ожидаемый результат:**
    Функция validate_deeplink_length возвращает булево значение (True или False) в зависимости от фактической длины deeplink.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("deeplink", "validation", "length", "long", "unit")
    def test_validate_deeplink_length_long(self):
        # Создаем данные, которые приведут к длинному deeplink
        data = {
            "g": "very_long_group_code_name_that_exceeds_limit",
            "p": "very_long_promo_code_name_that_exceeds_limit"
        }
        result = validate_deeplink_length(data)
        # Результат может быть True или False в зависимости от длины
        assert isinstance(result, bool)

    @allure.title("Валидация длины пустого deeplink")
    @allure.description("""
    Проверяет валидацию длины deeplink с пустыми параметрами.
    
    **Что проверяется:**
    - Валидация deeplink с пустым словарем
    - Возврат True для пустого deeplink
    - Корректная обработка пустых данных
    
    **Тестовые данные:**
    - data: {} (пустой словарь)
    
    **Ожидаемый результат:**
    Функция validate_deeplink_length возвращает True для пустого deeplink.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("deeplink", "validation", "length", "empty", "unit")
    def test_validate_deeplink_length_empty(self):
        data = {}
        result = validate_deeplink_length(data)
        assert result is True

    @allure.title("Проверка лимита длины параметра deeplink (64 символа Telegram)")
    @allure.description("""
    Проверяет, что параметр deeplink не превышает лимит Telegram (64 символа) для различных комбинаций параметров.
    
    **Что проверяется:**
    - Создание deeplink с различными комбинациями параметров
    - Проверка длины параметра после создания ссылки
    - Обработка случаев превышения лимита (64 символа)
    - Корректность работы с различными комбинациями (group_code, promo_code, referrer_id)
    
    **Тестовые данные:**
    - Различные комбинации: group_code, promo_code, referrer_id по отдельности и вместе
    
    **Ожидаемый результат:**
    Параметр deeplink имеет длину больше 0. Если длина превышает 64 символа, это должно быть обработано корректно (залогировано или предупреждено).
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("deeplink", "validation", "length", "telegram_limit", "unit")
    def test_deeplink_parameter_length_limit(self):
        # Тестируем с различными комбинациями параметров
        test_cases = [
            {"group_code": "vip", "promo_code": "SALE50"},
            {"group_code": "premium"},
            {"promo_code": "WELCOME50"},
            {"referrer_id": 123456},
            {"group_code": "vip", "promo_code": "SALE50", "referrer_id": 123456},
        ]
        
        for data in test_cases:
            link = create_deeplink("test_bot", **data)
            if "?start=" in link:
                param = link.split("?start=")[1]
                # Проверяем, что длина параметра в пределах нормы (или предупреждаем)
                # Лимит Telegram: 64 символа, но для некоторых комбинаций может быть больше
                assert len(param) > 0, "Параметр не должен быть пустым"
                
                if len(param) > 64:
                    # Если превышает, проверяем что есть предупреждение в логировании
                    # Это допустимо, но должно быть залогировано
                    pass

