#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Тесты для валидации ssl-install.sh и nginx конфигурации
"""

import pytest
import allure
import os
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


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
        
        with allure.step("Подготовка: определение пути к файлу"):
            # Диагностическая информация
            cwd = Path.cwd()
            project_root_env = os.getenv('PROJECT_ROOT')
            
            diagnostic_info = f"""Корневая директория проекта (project_root): {project_root}
Путь к файлу ssl-install.sh: {ssl_script}
Текущая рабочая директория: {cwd}
PROJECT_ROOT (env): {project_root_env}
Файл существует: {ssl_script.exists()}
"""
            allure.attach(
                diagnostic_info,
                "Диагностическая информация",
                allure.attachment_type.TEXT
            )
            logger.debug(diagnostic_info)
            
            allure.attach(
                str(ssl_script),
                "Путь к файлу ssl-install.sh",
                allure.attachment_type.TEXT
            )
            allure.attach(
                str(project_root),
                "Корневая директория проекта",
                allure.attachment_type.TEXT
            )
            
            # Проверяем альтернативные пути
            alternative_paths = [
                Path("/app/ssl-install.sh"),
                Path.cwd() / "ssl-install.sh",
                Path(__file__).parent.parent.parent / "ssl-install.sh"
            ]
            if project_root_env:
                alternative_paths.append(Path(project_root_env) / "ssl-install.sh")
            
            found_paths = [p for p in alternative_paths if p.exists()]
            if found_paths:
                allure.attach(
                    "\n".join(str(p) for p in found_paths),
                    "Альтернативные пути, где файл найден",
                    allure.attachment_type.TEXT
                )
        
        with allure.step("Проверка существования файла"):
            file_exists = ssl_script.exists()
            allure.attach(
                str(file_exists),
                "Файл существует",
                allure.attachment_type.TEXT
            )
            
            if not file_exists:
                # Дополнительная диагностика
                error_msg = f"""Файл ssl-install.sh не найден по пути: {ssl_script}

Возможные причины:
1. Файл не существует в репозитории на сервере
2. Файл не маппится в Docker контейнер через docker-compose.yml
3. Фикстура project_root возвращает неправильный путь

Проверьте:
- Существует ли файл в корне проекта на сервере
- Правильно ли настроен volume-маппинг в docker-compose.yml
- Запускается ли тест в Docker контейнере или локально
"""
                allure.attach(
                    error_msg,
                    "Детальная информация об ошибке",
                    allure.attachment_type.TEXT
                )
                logger.error(error_msg)
            
            assert file_exists, f"Файл ssl-install.sh не найден по пути: {ssl_script}"
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

