#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Unit-тесты для функциональности работы с настройками доменов

Проверяет корректность работы функций получения доменов из БД:
get_global_domain, get_user_cabinet_domain, get_setting для всех доменов.
"""

import pytest
import allure
import sys
from pathlib import Path

# Добавляем путь к проекту
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root / "src"))

from shop_bot.data_manager.database import (
    get_global_domain,
    get_setting,
    update_setting,
    initialize_db,
)
from shop_bot.config import get_user_cabinet_domain


@pytest.mark.unit
@pytest.mark.database
@allure.epic("База данных")
@allure.feature("Настройки доменов")
@allure.label("package", "src.shop_bot.database")
class TestDomainSettings:
    """Тесты для функциональности работы с настройками доменов"""

    @allure.title("Чтение global_domain из БД")
    @allure.description("""
    Проверяет корректное чтение настройки global_domain из БД.
    
    **Что проверяется:**
    - Установка значения global_domain в БД
    - Чтение значения через get_global_domain()
    - Корректное возвращение установленного значения
    
    **Тестовые данные:**
    - global_domain: "https://example.com"
    
    **Ожидаемый результат:**
    get_global_domain() возвращает установленное значение.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("domain", "settings", "database", "unit")
    def test_get_global_domain_from_db(self, temp_db):
        """Проверка чтения global_domain из БД"""
        with allure.step("Установка global_domain в БД"):
            update_setting("global_domain", "https://example.com")
            allure.attach("https://example.com", "Установленное значение", allure.attachment_type.TEXT)
        
        with allure.step("Чтение global_domain из БД"):
            result = get_global_domain()
            allure.attach(str(result), "Полученное значение", allure.attachment_type.TEXT)
        
        with allure.step("Проверка результата"):
            assert result == "https://example.com"

    @allure.title("Fallback на domain если global_domain отсутствует")
    @allure.description("""
    Проверяет fallback на старый параметр domain если global_domain отсутствует.
    
    **Что проверяется:**
    - Установка только domain (без global_domain)
    - Чтение через get_global_domain()
    - Корректный fallback на domain
    
    **Тестовые данные:**
    - domain: "https://old-example.com"
    
    **Ожидаемый результат:**
    get_global_domain() возвращает значение из domain с добавлением https:// если нужно.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("domain", "settings", "fallback", "database", "unit")
    def test_get_global_domain_fallback_to_domain(self, temp_db):
        """Проверка fallback на domain если global_domain отсутствует"""
        with allure.step("Установка только domain (без global_domain)"):
            update_setting("domain", "old-example.com")
            allure.attach("old-example.com", "Установленное значение domain", allure.attachment_type.TEXT)
        
        with allure.step("Чтение через get_global_domain()"):
            result = get_global_domain()
            allure.attach(str(result), "Полученное значение", allure.attachment_type.TEXT)
        
        with allure.step("Проверка результата"):
            assert result == "https://old-example.com"

    @allure.title("Fallback на localhost если оба домена отсутствуют")
    @allure.description("""
    Проверяет fallback на localhost если и global_domain и domain отсутствуют.
    
    **Что проверяется:**
    - Отсутствие global_domain и domain в БД
    - Чтение через get_global_domain()
    - Fallback на дефолтное значение localhost
    
    **Ожидаемый результат:**
    get_global_domain() возвращает "https://localhost:8443".
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("domain", "settings", "fallback", "database", "unit")
    def test_get_global_domain_fallback_to_localhost(self, temp_db):
        """Проверка fallback на localhost если оба домена отсутствуют"""
        with allure.step("Проверка отсутствия настроек"):
            global_domain = get_setting("global_domain")
            domain = get_setting("domain")
            allure.attach(f"global_domain: {global_domain}, domain: {domain}", "Текущие настройки", allure.attachment_type.TEXT)
        
        with allure.step("Чтение через get_global_domain()"):
            result = get_global_domain()
            allure.attach(str(result), "Полученное значение", allure.attachment_type.TEXT)
        
        with allure.step("Проверка результата"):
            assert result == "https://localhost:8443"

    @allure.title("Чтение user_cabinet_domain из БД")
    @allure.description("""
    Проверяет корректное чтение настройки user_cabinet_domain из БД.
    
    **Что проверяется:**
    - Установка значения user_cabinet_domain в БД
    - Чтение значения через get_user_cabinet_domain()
    - Нормализация домена (добавление протокола)
    
    **Тестовые данные:**
    - user_cabinet_domain: "app.example.com"
    
    **Ожидаемый результат:**
    get_user_cabinet_domain() возвращает нормализованное значение с протоколом.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("domain", "settings", "cabinet", "database", "unit")
    def test_get_user_cabinet_domain_from_db(self, temp_db):
        """Проверка чтения user_cabinet_domain из БД"""
        with allure.step("Установка user_cabinet_domain в БД"):
            update_setting("user_cabinet_domain", "app.example.com")
            allure.attach("app.example.com", "Установленное значение", allure.attachment_type.TEXT)
        
        with allure.step("Чтение user_cabinet_domain из БД"):
            result = get_user_cabinet_domain()
            allure.attach(str(result), "Полученное значение", allure.attachment_type.TEXT)
        
        with allure.step("Проверка результата"):
            assert result == "https://app.example.com"
            assert result.startswith("https://")

    @allure.title("Возврат None если user_cabinet_domain отсутствует")
    @allure.description("""
    Проверяет возврат None если настройка user_cabinet_domain отсутствует.
    
    **Что проверяется:**
    - Отсутствие user_cabinet_domain в БД
    - Чтение через get_user_cabinet_domain()
    - Возврат None
    
    **Ожидаемый результат:**
    get_user_cabinet_domain() возвращает None.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("domain", "settings", "cabinet", "database", "unit")
    def test_get_user_cabinet_domain_returns_none(self, temp_db):
        """Проверка возврата None если настройка отсутствует"""
        with allure.step("Проверка отсутствия настройки"):
            setting = get_setting("user_cabinet_domain")
            allure.attach(str(setting), "Текущее значение", allure.attachment_type.TEXT)
        
        with allure.step("Чтение через get_user_cabinet_domain()"):
            result = get_user_cabinet_domain()
            allure.attach(str(result), "Полученное значение", allure.attachment_type.TEXT)
        
        with allure.step("Проверка результата"):
            assert result is None

    @allure.title("Чтение codex_docs_domain из БД")
    @allure.description("""
    Проверяет корректное чтение настройки codex_docs_domain из БД.
    
    **Что проверяется:**
    - Установка значения codex_docs_domain в БД
    - Чтение значения через get_setting()
    - Корректное возвращение установленного значения
    
    **Тестовые данные:**
    - codex_docs_domain: "https://help.example.com"
    
    **Ожидаемый результат:**
    get_setting("codex_docs_domain") возвращает установленное значение.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("domain", "settings", "codex-docs", "database", "unit")
    def test_get_codex_docs_domain_from_db(self, temp_db):
        """Проверка чтения codex_docs_domain из БД"""
        with allure.step("Установка codex_docs_domain в БД"):
            update_setting("codex_docs_domain", "https://help.example.com")
            allure.attach("https://help.example.com", "Установленное значение", allure.attachment_type.TEXT)
        
        with allure.step("Чтение codex_docs_domain из БД"):
            result = get_setting("codex_docs_domain")
            allure.attach(str(result), "Полученное значение", allure.attachment_type.TEXT)
        
        with allure.step("Проверка результата"):
            assert result == "https://help.example.com"

    @allure.title("Чтение docs_domain из БД")
    @allure.description("""
    Проверяет корректное чтение настройки docs_domain из БД.
    
    **Что проверяется:**
    - Установка значения docs_domain в БД
    - Чтение значения через get_setting()
    - Корректное возвращение установленного значения
    
    **Тестовые данные:**
    - docs_domain: "https://docs.example.com"
    
    **Ожидаемый результат:**
    get_setting("docs_domain") возвращает установленное значение.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("domain", "settings", "docs", "database", "unit")
    def test_get_docs_domain_from_db(self, temp_db):
        """Проверка чтения docs_domain из БД"""
        with allure.step("Установка docs_domain в БД"):
            update_setting("docs_domain", "https://docs.example.com")
            allure.attach("https://docs.example.com", "Установленное значение", allure.attachment_type.TEXT)
        
        with allure.step("Чтение docs_domain из БД"):
            result = get_setting("docs_domain")
            allure.attach(str(result), "Полученное значение", allure.attachment_type.TEXT)
        
        with allure.step("Проверка результата"):
            assert result == "https://docs.example.com"

    @allure.title("Нормализация user_cabinet_domain с протоколом")
    @allure.description("""
    Проверяет нормализацию user_cabinet_domain с добавлением протокола если отсутствует.
    
    **Что проверяется:**
    - Установка user_cabinet_domain без протокола
    - Чтение через get_user_cabinet_domain()
    - Автоматическое добавление https://
    
    **Тестовые данные:**
    - user_cabinet_domain: "app.example.com"
    
    **Ожидаемый результат:**
    get_user_cabinet_domain() возвращает "https://app.example.com".
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("domain", "normalization", "cabinet", "database", "unit")
    def test_user_cabinet_domain_normalization_with_protocol(self, temp_db):
        """Проверка нормализации user_cabinet_domain с протоколом"""
        with allure.step("Установка user_cabinet_domain без протокола"):
            update_setting("user_cabinet_domain", "app.example.com")
            allure.attach("app.example.com", "Установленное значение (без протокола)", allure.attachment_type.TEXT)
        
        with allure.step("Чтение через get_user_cabinet_domain()"):
            result = get_user_cabinet_domain()
            allure.attach(str(result), "Полученное значение", allure.attachment_type.TEXT)
        
        with allure.step("Проверка результата"):
            assert result == "https://app.example.com"
            assert result.startswith("https://")

    @allure.title("Нормализация user_cabinet_domain с удалением trailing slash")
    @allure.description("""
    Проверяет нормализацию user_cabinet_domain с удалением trailing slash.
    
    **Что проверяется:**
    - Установка user_cabinet_domain с trailing slash
    - Чтение через get_user_cabinet_domain()
    - Удаление trailing slash
    
    **Тестовые данные:**
    - user_cabinet_domain: "https://app.example.com/"
    
    **Ожидаемый результат:**
    get_user_cabinet_domain() возвращает "https://app.example.com" (без trailing slash).
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("domain", "normalization", "cabinet", "database", "unit")
    def test_user_cabinet_domain_normalization_remove_trailing_slash(self, temp_db):
        """Проверка нормализации user_cabinet_domain с удалением trailing slash"""
        with allure.step("Установка user_cabinet_domain с trailing slash"):
            update_setting("user_cabinet_domain", "https://app.example.com/")
            allure.attach("https://app.example.com/", "Установленное значение (с trailing slash)", allure.attachment_type.TEXT)
        
        with allure.step("Чтение через get_user_cabinet_domain()"):
            result = get_user_cabinet_domain()
            allure.attach(str(result), "Полученное значение", allure.attachment_type.TEXT)
        
        with allure.step("Проверка результата"):
            assert result == "https://app.example.com"
            assert not result.endswith("/")

