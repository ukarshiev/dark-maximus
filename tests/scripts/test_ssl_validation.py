#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Тесты для валидации ssl-install.sh и nginx конфигурации
"""

import pytest
import allure
from pathlib import Path


@allure.epic("Валидация скриптов установки")
@allure.feature("SSL Install Script")
@allure.label("package", "tests.scripts")
@pytest.mark.unit
class TestSSLValidation:
    """Тесты для валидации ssl-install.sh"""

    @allure.title("Проверка наличия ssl-install.sh")
    @allure.description("""
    Проверяет наличие файла ssl-install.sh в корне проекта.
    
    **Что проверяется:**
    - Файл ssl-install.sh существует
    - Файл доступен для чтения
    
    **Ожидаемый результат:**
    Файл ssl-install.sh найден и доступен.
    """)
    @allure.severity(allure.severity_level.CRITICAL)
    @allure.tag("ssl", "script", "unit", "critical")
    def test_ssl_script_exists(self, project_root):
        """Проверка наличия ssl-install.sh"""
        ssl_script = project_root / "ssl-install.sh"
        
        with allure.step("Проверка существования файла"):
            assert ssl_script.exists(), "Файл ssl-install.sh не найден"
            assert ssl_script.is_file(), "ssl-install.sh не является файлом"

    @allure.title("Проверка порта docs-proxy в ssl-install.sh")
    @allure.description("""
    Проверяет, что ssl-install.sh проверяет порт docs-proxy, а не docs.
    
    **Что проверяется:**
    - Проверка порта 50001 для docs-proxy
    - Логи относятся к docs-proxy
    
    **Ожидаемый результат:**
    Скрипт проверяет docs-proxy на правильном порту.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("ssl", "docs-proxy", "unit")
    def test_docs_proxy_port_check(self, project_root):
        """Проверка порта docs-proxy в ssl-install.sh"""
        ssl_script = project_root / "ssl-install.sh"
        
        if not ssl_script.exists():
            pytest.skip("ssl-install.sh не найден")
        
        with open(ssl_script, "r", encoding="utf-8") as f:
            script_content = f.read()
        
        with allure.step("Проверка порта 50001"):
            assert "50001" in script_content, \
                "Порт 50001 должен быть в скрипте"
        
        with allure.step("Проверка docs-proxy"):
            # Проверяем, что упоминается docs-proxy, а не просто docs
            assert "docs-proxy" in script_content, \
                "Скрипт должен проверять docs-proxy, а не docs"

    @allure.title("Проверка nginx конфигурации")
    @allure.description("""
    Проверяет наличие nginx конфигурации и её корректность.
    
    **Что проверяется:**
    - Шаблон nginx конфигурации существует
    - upstream docs_backend указывает на правильный порт
    
    **Ожидаемый результат:**
    Nginx конфигурация корректна.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("ssl", "nginx", "unit")
    def test_nginx_config(self, project_root):
        """Проверка nginx конфигурации"""
        nginx_template = project_root / "deploy" / "nginx" / "dark-maximus.conf.tpl"
        
        if not nginx_template.exists():
            pytest.skip("Nginx шаблон не найден")
        
        with open(nginx_template, "r", encoding="utf-8") as f:
            nginx_content = f.read()
        
        with allure.step("Проверка upstream docs_backend"):
            assert "docs_backend" in nginx_content, \
                "upstream docs_backend должен быть в конфигурации"
            assert "127.0.0.1:50001" in nginx_content, \
                "upstream docs_backend должен указывать на порт 50001"

