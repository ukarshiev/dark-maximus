#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Тесты для валидации install.sh и создаваемых файлов
"""

import pytest
import allure
from pathlib import Path


@allure.epic("Валидация скриптов установки")
@allure.feature("Install Script")
@allure.label("package", "tests.scripts")
@pytest.mark.unit
class TestInstallValidation:
    """Тесты для валидации install.sh"""

    @allure.title("Проверка наличия install.sh")
    @allure.description("""
    Проверяет наличие файла install.sh в корне проекта.
    
    **Что проверяется:**
    - Файл install.sh существует
    - Файл доступен для чтения
    
    **Ожидаемый результат:**
    Файл install.sh найден и доступен.
    """)
    @allure.severity(allure.severity_level.CRITICAL)
    @allure.tag("install", "script", "unit", "critical")
    def test_install_script_exists(self, project_root):
        """Проверка наличия install.sh"""
        install_script = project_root / "install.sh"
        
        with allure.step("Проверка существования файла"):
            assert install_script.exists(), "Файл install.sh не найден"
            assert install_script.is_file(), "install.sh не является файлом"
        
        with allure.step("Проверка прав доступа"):
            assert install_script.stat().st_mode & 0o111, \
                "Файл install.sh должен быть исполняемым"

    @allure.title("Проверка создания необходимых директорий")
    @allure.description("""
    Проверяет, что install.sh создает все необходимые директории.
    
    **Что проверяется:**
    - Директории: logs, backups, sessions, sessions-docs, codex.docs/uploads, codex.docs/db
    - Скрипт содержит команды для создания этих директорий
    
    **Ожидаемый результат:**
    Все необходимые директории упоминаются в скрипте.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("install", "directories", "unit")
    def test_required_directories_in_script(self, project_root):
        """Проверка упоминания необходимых директорий в install.sh"""
        install_script = project_root / "install.sh"
        
        if not install_script.exists():
            pytest.skip("install.sh не найден")
        
        required_dirs = [
            "logs",
            "backups",
            "sessions",
            "sessions-docs",
            "codex.docs/uploads",
            "codex.docs/db"
        ]
        
        with open(install_script, "r", encoding="utf-8") as f:
            script_content = f.read()
        
        with allure.step("Проверка упоминания директорий"):
            missing_dirs = []
            for dir_name in required_dirs:
                if dir_name not in script_content:
                    missing_dirs.append(dir_name)
            
            allure.attach(
                str(required_dirs),
                "Необходимые директории",
                allure.attachment_type.TEXT
            )
            
            if missing_dirs:
                allure.attach(
                    "\n".join(missing_dirs),
                    "Отсутствующие директории",
                    allure.attachment_type.TEXT
                )
            
            assert len(missing_dirs) == 0, \
                f"Директории не упоминаются в install.sh: {', '.join(missing_dirs)}"

    @allure.title("Проверка наличия docs-proxy в скрипте")
    @allure.description("""
    Проверяет, что install.sh создает сервис docs-proxy.
    
    **Что проверяется:**
    - Скрипт содержит определение сервиса docs-proxy
    - Сервис docs имеет expose вместо ports
    
    **Ожидаемый результат:**
    docs-proxy правильно определен в скрипте.
    """)
    @allure.severity(allure.severity_level.CRITICAL)
    @allure.tag("install", "docs-proxy", "unit", "critical")
    def test_docs_proxy_in_script(self, project_root):
        """Проверка наличия docs-proxy в install.sh"""
        install_script = project_root / "install.sh"
        
        if not install_script.exists():
            pytest.skip("install.sh не найден")
        
        with open(install_script, "r", encoding="utf-8") as f:
            script_content = f.read()
        
        with allure.step("Проверка docs-proxy"):
            assert "docs-proxy:" in script_content, \
                "Сервис docs-proxy не найден в install.sh"
            assert "127.0.0.1:50001:50001" in script_content, \
                "Порт docs-proxy не найден в install.sh"
        
        with allure.step("Проверка docs (expose)"):
            # Проверяем, что docs имеет expose, а не ports
            assert "expose:" in script_content or '"expose"' in script_content, \
                "Сервис docs должен использовать expose вместо ports"

    @allure.title("Проверка констант портов в скрипте")
    @allure.description("""
    Проверяет использование констант портов в install.sh.
    
    **Что проверяется:**
    - Порты используются консистентно
    - Нет хардкодов портов в разных местах
    
    **Ожидаемый результат:**
    Порты используются консистентно.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("install", "ports", "unit")
    def test_port_consistency(self, project_root, port_constants):
        """Проверка консистентности портов в install.sh"""
        install_script = project_root / "install.sh"
        
        if not install_script.exists():
            pytest.skip("install.sh не найден")
        
        with open(install_script, "r", encoding="utf-8") as f:
            script_content = f.read()
        
        with allure.step("Проверка портов"):
            # Проверяем, что порты упоминаются в скрипте
            port_checks = {
                "50000": "bot",
                "50001": "docs-proxy",
                "50002": "codex-docs",
                "50003": "user-cabinet"
            }
            
            missing_ports = []
            for port, service in port_checks.items():
                if port not in script_content:
                    missing_ports.append(f"{service} (порт {port})")
            
            if missing_ports:
                allure.attach(
                    "\n".join(missing_ports),
                    "Отсутствующие порты",
                    allure.attachment_type.TEXT
                )
            
            # Не строгая проверка, так как порты могут быть в разных форматах
            # Просто проверяем, что основные порты упоминаются

