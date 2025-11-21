#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Unit-тесты для нормализации доменов

Проверяет корректность работы функций нормализации доменов:
добавление протокола, удаление trailing slash, обработка порта и пути.
"""

import pytest
import allure
import sys
from pathlib import Path

# Добавляем путь к проекту
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root / "src"))

from shop_bot.config import get_user_cabinet_domain
from shop_bot.data_manager.database import get_global_domain, get_setting, update_setting


@pytest.mark.unit
@allure.epic("Утилиты")
@allure.feature("Нормализация доменов")
@allure.label("package", "src.shop_bot.utils")
class TestDomainNormalization:
    """Тесты для нормализации доменов"""

    @pytest.mark.parametrize("input_domain,expected", [
        ("example.com", "https://example.com"),
        ("https://example.com", "https://example.com"),
        ("http://example.com", "https://example.com"),  # get_user_cabinet_domain преобразует http в https
    ])
    @allure.title("Добавление https:// протокола если отсутствует")
    @allure.description("""
    Проверяет автоматическое добавление протокола https:// если он отсутствует.
    
    **Что проверяется:**
    - Добавление https:// для домена без протокола
    - Сохранение https:// если уже есть
    - Преобразование http:// в https://
    
    **Тестовые данные:**
    - Различные варианты входных доменов (с протоколом и без)
    
    **Ожидаемый результат:**
    Все домены нормализуются с протоколом https://.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("domain", "normalization", "protocol", "unit")
    def test_add_https_protocol_if_missing(self, temp_db, input_domain, expected):
        """Проверка добавления https:// если протокол отсутствует"""
        with allure.step(f"Установка домена: {input_domain}"):
            update_setting("user_cabinet_domain", input_domain)
            allure.attach(input_domain, "Входной домен", allure.attachment_type.TEXT)
        
        with allure.step("Чтение через get_user_cabinet_domain()"):
            result = get_user_cabinet_domain()
            allure.attach(str(result), "Результат нормализации", allure.attachment_type.TEXT)
        
        with allure.step("Проверка результата"):
            assert result == expected

    @pytest.mark.parametrize("input_domain,expected", [
        ("https://example.com/", "https://example.com"),
        ("https://example.com", "https://example.com"),
        ("example.com/", "https://example.com"),
    ])
    @allure.title("Удаление trailing slash")
    @allure.description("""
    Проверяет удаление trailing slash из домена.
    
    **Что проверяется:**
    - Удаление / в конце домена
    - Сохранение домена без trailing slash
    
    **Тестовые данные:**
    - Различные варианты доменов с trailing slash и без
    
    **Ожидаемый результат:**
    Все домены нормализуются без trailing slash.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("domain", "normalization", "trailing-slash", "unit")
    def test_remove_trailing_slash(self, temp_db, input_domain, expected):
        """Проверка удаления trailing slash"""
        with allure.step(f"Установка домена: {input_domain}"):
            update_setting("user_cabinet_domain", input_domain)
            allure.attach(input_domain, "Входной домен", allure.attachment_type.TEXT)
        
        with allure.step("Чтение через get_user_cabinet_domain()"):
            result = get_user_cabinet_domain()
            allure.attach(str(result), "Результат нормализации", allure.attachment_type.TEXT)
        
        with allure.step("Проверка результата"):
            assert result == expected
            assert not result.endswith("/")

    @allure.title("Обработка домена с портом")
    @allure.description("""
    Проверяет обработку домена с указанным портом.
    
    **Что проверяется:**
    - Сохранение порта в домене
    - Корректная нормализация домена с портом
    
    **Тестовые данные:**
    - user_cabinet_domain: "localhost:50003"
    
    **Ожидаемый результат:**
    Домен нормализуется с сохранением порта.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("domain", "normalization", "port", "unit")
    def test_handle_domain_with_port(self, temp_db):
        """Проверка обработки домена с портом"""
        with allure.step("Установка домена с портом"):
            update_setting("user_cabinet_domain", "localhost:50003")
            allure.attach("localhost:50003", "Входной домен", allure.attachment_type.TEXT)
        
        with allure.step("Чтение через get_user_cabinet_domain()"):
            result = get_user_cabinet_domain()
            allure.attach(str(result), "Результат нормализации", allure.attachment_type.TEXT)
        
        with allure.step("Проверка результата"):
            # Порт должен сохраняться
            assert result == "https://localhost:50003"
            assert ":50003" in result

    @allure.title("Обработка домена с путем")
    @allure.description("""
    Проверяет обработку домена с путем (путь должен быть удален при нормализации).
    
    **Что проверяется:**
    - Удаление пути из домена при нормализации
    - Сохранение только домена
    
    **Тестовые данные:**
    - user_cabinet_domain: "https://example.com/path/to/page"
    
    **Ожидаемый результат:**
    Домен нормализуется без пути (только домен с протоколом).
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("domain", "normalization", "path", "unit")
    def test_handle_domain_with_path(self, temp_db):
        """Проверка обработки домена с путем"""
        with allure.step("Установка домена с путем"):
            update_setting("user_cabinet_domain", "https://example.com/path/to/page")
            allure.attach("https://example.com/path/to/page", "Входной домен", allure.attachment_type.TEXT)
        
        with allure.step("Чтение через get_user_cabinet_domain()"):
            result = get_user_cabinet_domain()
            allure.attach(str(result), "Результат нормализации", allure.attachment_type.TEXT)
        
        with allure.step("Проверка результата"):
            # get_user_cabinet_domain удаляет путь при нормализации
            assert result == "https://example.com"
            assert "/path" not in result
            assert result.count("/") == 2  # Только https:// и домен

    @pytest.mark.parametrize("input_value", [None, "", "   "])
    @allure.title("Обработка None и пустых строк")
    @allure.description("""
    Проверяет обработку None и пустых строк при нормализации домена.
    
    **Что проверяется:**
    - Обработка None значения
    - Обработка пустой строки
    - Обработка строки только с пробелами
    
    **Тестовые данные:**
    - None, "", "   "
    
    **Ожидаемый результат:**
    get_user_cabinet_domain() возвращает None для всех этих случаев.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("domain", "normalization", "empty", "unit")
    def test_handle_none_and_empty_string(self, temp_db, input_value):
        """Проверка обработки None и пустых строк"""
        with allure.step(f"Установка значения: {repr(input_value)}"):
            if input_value is not None:
                update_setting("user_cabinet_domain", input_value)
            else:
                # Для None просто не устанавливаем настройку
                pass
            allure.attach(str(input_value), "Входное значение", allure.attachment_type.TEXT)
        
        with allure.step("Чтение через get_user_cabinet_domain()"):
            result = get_user_cabinet_domain()
            allure.attach(str(result), "Результат", allure.attachment_type.TEXT)
        
        with allure.step("Проверка результата"):
            assert result is None

    @pytest.mark.parametrize("input_url,expected_domain", [
        ("https://example.com", "example.com"),
        ("http://example.com", "example.com"),
        ("https://example.com:8080", "example.com"),
        ("https://example.com/path/to/page", "example.com"),
        ("https://subdomain.example.com", "subdomain.example.com"),
    ])
    @allure.title("Извлечение домена из полного URL")
    @allure.description("""
    Проверяет извлечение домена из полного URL (удаление протокола, пути, порта).
    
    **Что проверяется:**
    - Извлечение домена из URL с https://
    - Извлечение домена из URL с http://
    - Извлечение домена из URL с портом
    - Извлечение домена из URL с путем
    - Извлечение домена из поддомена
    
    **Тестовые данные:**
    - Различные варианты URL
    
    **Ожидаемый результат:**
    Извлекается только домен без протокола, пути и порта.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("domain", "normalization", "extraction", "unit")
    def test_extract_domain_from_url(self, temp_db, input_url, expected_domain):
        """Проверка извлечения домена из полного URL"""
        with allure.step(f"Установка URL: {input_url}"):
            update_setting("user_cabinet_domain", input_url)
            allure.attach(input_url, "Входной URL", allure.attachment_type.TEXT)
        
        with allure.step("Чтение через get_user_cabinet_domain() и извлечение домена"):
            full_url = get_user_cabinet_domain()
            # Извлекаем домен из полного URL (убираем протокол)
            if full_url:
                extracted_domain = full_url.replace("https://", "").replace("http://", "").split("/")[0].split(":")[0]
            else:
                extracted_domain = None
            allure.attach(str(extracted_domain), "Извлеченный домен", allure.attachment_type.TEXT)
        
        with allure.step("Проверка результата"):
            if expected_domain:
                assert extracted_domain == expected_domain
            else:
                assert extracted_domain is None

