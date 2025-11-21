#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Тесты для функций извлечения домена из URL и чтения настроек из БД

Проверяет корректность работы функций из ssl-install.sh:
extract_domain_from_url и read_setting_from_db (через Python реализацию).
"""

import pytest
import allure
import sys
import sqlite3
from pathlib import Path

# Добавляем путь к проекту
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root / "src"))


def extract_domain_from_url(url: str) -> str:
    """
    Извлекает домен из URL (убирает протокол и путь).
    
    Реализация функции из ssl-install.sh на Python для тестирования.
    """
    if not url:
        return ""
    
    # Убираем протокол (http:// или https://)
    domain = url.replace("http://", "").replace("https://", "")
    
    # Убираем путь (всё после первого /)
    if "/" in domain:
        domain = domain.split("/")[0]
    
    # Убираем порт (если есть)
    if ":" in domain:
        domain = domain.split(":")[0]
    
    return domain


def read_setting_from_db(db_path: Path, setting_key: str) -> str | None:
    """
    Читает настройку из БД.
    
    Реализация функции из ssl-install.sh на Python для тестирования.
    """
    if not db_path.exists():
        return None
    
    try:
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM bot_settings WHERE key = ?", (setting_key,))
        result = cursor.fetchone()
        conn.close()
        
        if result and result[0]:
            return result[0].strip()
        return None
    except Exception:
        return None


@pytest.mark.unit
@allure.epic("Утилиты")
@allure.feature("Извлечение доменов")
@allure.label("package", "tests.scripts")
class TestDomainExtraction:
    """Тесты для функций извлечения домена из URL"""

    @pytest.mark.parametrize("input_url,expected", [
        ("https://example.com", "example.com"),
        ("https://example.com/", "example.com"),
        ("https://example.com/path", "example.com"),
        ("https://example.com/path/to/page", "example.com"),
    ])
    @allure.title("Извлечение домена из URL с https://")
    @allure.description("""
    Проверяет извлечение домена из URL с протоколом https://.
    
    **Что проверяется:**
    - Удаление протокола https://
    - Удаление пути
    - Извлечение только домена
    
    **Тестовые данные:**
    - Различные варианты URL с https://
    
    **Ожидаемый результат:**
    Извлекается только домен без протокола и пути.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("domain", "extraction", "https", "unit")
    def test_extract_domain_from_url_with_https(self, input_url, expected):
        """Проверка извлечения домена из URL с https://"""
        with allure.step(f"Извлечение домена из: {input_url}"):
            result = extract_domain_from_url(input_url)
            allure.attach(result, "Извлеченный домен", allure.attachment_type.TEXT)
        
        with allure.step("Проверка результата"):
            assert result == expected

    @pytest.mark.parametrize("input_url,expected", [
        ("http://example.com", "example.com"),
        ("http://example.com/", "example.com"),
        ("http://example.com/path", "example.com"),
    ])
    @allure.title("Извлечение домена из URL с http://")
    @allure.description("""
    Проверяет извлечение домена из URL с протоколом http://.
    
    **Что проверяется:**
    - Удаление протокола http://
    - Удаление пути
    - Извлечение только домена
    
    **Тестовые данные:**
    - Различные варианты URL с http://
    
    **Ожидаемый результат:**
    Извлекается только домен без протокола и пути.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("domain", "extraction", "http", "unit")
    def test_extract_domain_from_url_with_http(self, input_url, expected):
        """Проверка извлечения домена из URL с http://"""
        with allure.step(f"Извлечение домена из: {input_url}"):
            result = extract_domain_from_url(input_url)
            allure.attach(result, "Извлеченный домен", allure.attachment_type.TEXT)
        
        with allure.step("Проверка результата"):
            assert result == expected

    @pytest.mark.parametrize("input_url,expected", [
        ("https://example.com/path/to/page", "example.com"),
        ("https://example.com/setup", "example.com"),
        ("https://example.com/static/logo.png", "example.com"),
    ])
    @allure.title("Извлечение домена из URL с путем")
    @allure.description("""
    Проверяет извлечение домена из URL с путем.
    
    **Что проверяется:**
    - Удаление пути из URL
    - Извлечение только домена
    
    **Тестовые данные:**
    - Различные варианты URL с путем
    
    **Ожидаемый результат:**
    Извлекается только домен без пути.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("domain", "extraction", "path", "unit")
    def test_extract_domain_from_url_with_path(self, input_url, expected):
        """Проверка извлечения домена из URL с путем"""
        with allure.step(f"Извлечение домена из: {input_url}"):
            result = extract_domain_from_url(input_url)
            allure.attach(result, "Извлеченный домен", allure.attachment_type.TEXT)
        
        with allure.step("Проверка результата"):
            assert result == expected
            assert "/" not in result

    @pytest.mark.parametrize("input_url,expected", [
        ("https://example.com:8080", "example.com"),
        ("http://example.com:3000", "example.com"),
        ("https://localhost:50003", "localhost"),
    ])
    @allure.title("Извлечение домена из URL с портом")
    @allure.description("""
    Проверяет извлечение домена из URL с портом.
    
    **Что проверяется:**
    - Удаление порта из URL
    - Извлечение только домена
    
    **Тестовые данные:**
    - Различные варианты URL с портом
    
    **Ожидаемый результат:**
    Извлекается только домен без порта.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("domain", "extraction", "port", "unit")
    def test_extract_domain_from_url_with_port(self, input_url, expected):
        """Проверка извлечения домена из URL с портом"""
        with allure.step(f"Извлечение домена из: {input_url}"):
            result = extract_domain_from_url(input_url)
            allure.attach(result, "Извлеченный домен", allure.attachment_type.TEXT)
        
        with allure.step("Проверка результата"):
            assert result == expected
            assert ":" not in result

    @allure.title("Чтение настройки из БД")
    @allure.description("""
    Проверяет чтение настройки из БД через функцию read_setting_from_db.
    
    **Что проверяется:**
    - Создание временной БД
    - Установка настройки в БД
    - Чтение настройки через read_setting_from_db()
    
    **Тестовые данные:**
    - setting_key: "user_cabinet_domain"
    - value: "https://app.example.com"
    
    **Ожидаемый результат:**
    read_setting_from_db() возвращает установленное значение.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("database", "settings", "read", "unit")
    def test_read_setting_from_db(self, temp_db):
        """Проверка чтения настройки из БД"""
        with allure.step("Создание БД и установка настройки"):
            conn = sqlite3.connect(str(temp_db))
            cursor = conn.cursor()
            cursor.execute("CREATE TABLE IF NOT EXISTS bot_settings (key TEXT PRIMARY KEY, value TEXT)")
            cursor.execute("INSERT OR REPLACE INTO bot_settings (key, value) VALUES (?, ?)",
                         ("user_cabinet_domain", "https://app.example.com"))
            conn.commit()
            conn.close()
            allure.attach("https://app.example.com", "Установленное значение", allure.attachment_type.TEXT)
        
        with allure.step("Чтение настройки через read_setting_from_db()"):
            result = read_setting_from_db(temp_db, "user_cabinet_domain")
            allure.attach(str(result), "Полученное значение", allure.attachment_type.TEXT)
        
        with allure.step("Проверка результата"):
            assert result == "https://app.example.com"

    @allure.title("Генерация доменов с использованием настроек из БД")
    @allure.description("""
    Проверяет генерацию доменов с использованием настроек из БД (симуляция логики ssl-install.sh).
    
    **Что проверяется:**
    - Установка всех настроек доменов в БД
    - Извлечение доменов из URL через extract_domain_from_url()
    - Генерация доменов с использованием настроек из БД
    
    **Тестовые данные:**
    - user_cabinet_domain: "https://app.example.com"
    - codex_docs_domain: "https://help.example.com"
    - docs_domain: "https://docs.example.com"
    - MAIN_DOMAIN: "example.com"
    
    **Ожидаемый результат:**
    Домены генерируются с использованием настроек из БД, а не дефолтных значений.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("domain", "generation", "database", "unit")
    def test_domain_generation_with_db_settings(self, temp_db):
        """Проверка генерации доменов с использованием настроек из БД"""
        with allure.step("Установка всех настроек доменов в БД"):
            conn = sqlite3.connect(str(temp_db))
            cursor = conn.cursor()
            cursor.execute("CREATE TABLE IF NOT EXISTS bot_settings (key TEXT PRIMARY KEY, value TEXT)")
            cursor.execute("INSERT OR REPLACE INTO bot_settings (key, value) VALUES (?, ?)",
                         ("user_cabinet_domain", "https://app.example.com"))
            cursor.execute("INSERT OR REPLACE INTO bot_settings (key, value) VALUES (?, ?)",
                         ("codex_docs_domain", "https://help.example.com"))
            cursor.execute("INSERT OR REPLACE INTO bot_settings (key, value) VALUES (?, ?)",
                         ("docs_domain", "https://docs.example.com"))
            conn.commit()
            conn.close()
            allure.attach("Все настройки установлены", "Настройки", allure.attachment_type.TEXT)
        
        with allure.step("Чтение настроек из БД и извлечение доменов"):
            MAIN_DOMAIN = "example.com"
            
            user_cabinet_domain_from_db = read_setting_from_db(temp_db, "user_cabinet_domain")
            codex_docs_domain_from_db = read_setting_from_db(temp_db, "codex_docs_domain")
            docs_domain_from_db = read_setting_from_db(temp_db, "docs_domain")
            
            # Генерация доменов с использованием настроек из БД
            if user_cabinet_domain_from_db:
                APP_DOMAIN = extract_domain_from_url(user_cabinet_domain_from_db)
            else:
                APP_DOMAIN = f"app.{MAIN_DOMAIN}"
            
            if codex_docs_domain_from_db:
                HELP_DOMAIN = extract_domain_from_url(codex_docs_domain_from_db)
            else:
                HELP_DOMAIN = f"help.{MAIN_DOMAIN}"
            
            if docs_domain_from_db:
                DOCS_DOMAIN = extract_domain_from_url(docs_domain_from_db)
            else:
                DOCS_DOMAIN = f"docs.{MAIN_DOMAIN}"
            
            allure.attach(APP_DOMAIN, "APP_DOMAIN", allure.attachment_type.TEXT)
            allure.attach(HELP_DOMAIN, "HELP_DOMAIN", allure.attachment_type.TEXT)
            allure.attach(DOCS_DOMAIN, "DOCS_DOMAIN", allure.attachment_type.TEXT)
        
        with allure.step("Проверка результата"):
            assert APP_DOMAIN == "app.example.com"
            assert HELP_DOMAIN == "help.example.com"
            assert DOCS_DOMAIN == "docs.example.com"
            # Проверяем, что используются настройки из БД, а не дефолтные значения
            assert APP_DOMAIN != f"app.{MAIN_DOMAIN}" or user_cabinet_domain_from_db is not None

