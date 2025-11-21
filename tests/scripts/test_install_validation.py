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
    Проверяет наличие и доступность файла install.sh в корне проекта.
    
    **Что проверяется:**
    - Файл install.sh существует в корне проекта
    - Файл является обычным файлом (не директорией)
    - Файл имеет права на выполнение (исполняемый)
    
    **Тестовые данные:**
    - Путь к файлу: {project_root}/install.sh
    - Ожидаемый тип: обычный файл
    - Ожидаемые права: исполняемый (st_mode & 0o111)
    
    **Предусловия:**
    - Файл install.sh должен быть доступен в контейнере через volume маппинг
    - Фикстура project_root должна указывать на корень проекта
    
    **Ожидаемый результат:**
    Файл install.sh найден, является обычным файлом и имеет права на выполнение.
    """)
    @allure.severity(allure.severity_level.CRITICAL)
    @allure.tag("install", "script", "unit", "critical", "file-validation")
    def test_install_script_exists(self, project_root):
        """Проверка наличия install.sh"""
        install_script = project_root / "install.sh"
        
        with allure.step("Подготовка: определение пути к файлу"):
            allure.attach(
                str(install_script),
                "Путь к файлу install.sh",
                allure.attachment_type.TEXT
            )
            allure.attach(
                str(project_root),
                "Корень проекта",
                allure.attachment_type.TEXT
            )
        
        with allure.step("Проверка существования файла"):
            file_exists = install_script.exists()
            allure.attach(
                str(file_exists),
                "Файл существует",
                allure.attachment_type.TEXT
            )
            assert file_exists, f"Файл install.sh не найден по пути: {install_script}"
            
            is_file = install_script.is_file()
            allure.attach(
                str(is_file),
                "Является файлом",
                allure.attachment_type.TEXT
            )
            assert is_file, "install.sh не является файлом"
        
        with allure.step("Проверка прав доступа"):
            file_stat = install_script.stat()
            is_executable = bool(file_stat.st_mode & 0o111)
            allure.attach(
                f"st_mode: {oct(file_stat.st_mode)}\nИсполняемый: {is_executable}",
                "Права доступа к файлу",
                allure.attachment_type.TEXT
            )
            assert is_executable, \
                f"Файл install.sh должен быть исполняемым. Текущие права: {oct(file_stat.st_mode)}"

    @allure.title("Проверка создания необходимых директорий")
    @allure.description("""
    Проверяет, что install.sh содержит команды для создания всех необходимых директорий проекта.
    
    **Что проверяется:**
    - Наличие упоминаний директорий в содержимом скрипта install.sh
    - Директории: logs, backups, sessions, sessions-docs, codex.docs/uploads, codex.docs/db
    - Все директории должны быть упомянуты в скрипте (через mkdir или другие команды)
    
    **Тестовые данные:**
    - Список необходимых директорий:
      - logs
      - backups
      - sessions
      - sessions-docs
      - codex.docs/uploads
      - codex.docs/db
    
    **Предусловия:**
    - Файл install.sh должен существовать и быть доступен для чтения
    - Скрипт должен содержать команды создания директорий
    
    **Ожидаемый результат:**
    Все необходимые директории упоминаются в скрипте install.sh. Скрипт должен содержать команды для их создания.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("install", "directories", "unit", "script-validation")
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
        
        with allure.step("Подготовка: чтение содержимого скрипта"):
            with open(install_script, "r", encoding="utf-8") as f:
                script_content = f.read()
            
            allure.attach(
                str(len(script_content)),
                "Размер файла (символов)",
                allure.attachment_type.TEXT
            )
            allure.attach(
                str(required_dirs),
                "Необходимые директории",
                allure.attachment_type.TEXT
            )
        
        with allure.step("Проверка упоминания директорий в скрипте"):
            missing_dirs = []
            found_dirs = []
            
            for dir_name in required_dirs:
                if dir_name in script_content:
                    found_dirs.append(dir_name)
                else:
                    missing_dirs.append(dir_name)
            
            allure.attach(
                "\n".join(found_dirs) if found_dirs else "Нет найденных директорий",
                "Найденные директории",
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
    Проверяет, что install.sh правильно определяет сервис docs-proxy и корректно настраивает сервис docs.
    
    **Что проверяется:**
    - Скрипт содержит определение сервиса docs-proxy в docker-compose.yml
    - Сервис docs-proxy имеет правильный порт (127.0.0.1:50001:50001)
    - Сервис docs использует expose вместо ports (безопасность - порт не публикуется наружу)
    
    **Тестовые данные:**
    - Имя сервиса: docs-proxy
    - Ожидаемый порт: 127.0.0.1:50001:50001
    - Сервис docs должен использовать expose: ['80']
    
    **Предусловия:**
    - Файл install.sh должен существовать и быть доступен для чтения
    - Скрипт должен создавать docker-compose.yml с правильной конфигурацией
    
    **Ожидаемый результат:**
    Сервис docs-proxy правильно определен в скрипте с портом 127.0.0.1:50001:50001, а сервис docs использует expose вместо ports для безопасности.
    """)
    @allure.severity(allure.severity_level.CRITICAL)
    @allure.tag("install", "docs-proxy", "unit", "critical", "docker-compose", "security")
    def test_docs_proxy_in_script(self, project_root):
        """Проверка наличия docs-proxy в install.sh"""
        install_script = project_root / "install.sh"
        
        if not install_script.exists():
            pytest.skip("install.sh не найден")
        
        with allure.step("Подготовка: чтение содержимого скрипта"):
            with open(install_script, "r", encoding="utf-8") as f:
                script_content = f.read()
            
            allure.attach(
                str(len(script_content)),
                "Размер файла (символов)",
                allure.attachment_type.TEXT
            )
        
        with allure.step("Проверка определения сервиса docs-proxy"):
            has_docs_proxy = "docs-proxy:" in script_content
            allure.attach(
                str(has_docs_proxy),
                "Сервис docs-proxy найден",
                allure.attachment_type.TEXT
            )
            assert has_docs_proxy, \
                "Сервис docs-proxy не найден в install.sh"
        
        with allure.step("Проверка порта docs-proxy"):
            has_port = "127.0.0.1:50001:50001" in script_content
            allure.attach(
                str(has_port),
                "Порт 127.0.0.1:50001:50001 найден",
                allure.attachment_type.TEXT
            )
            assert has_port, \
                "Порт docs-proxy (127.0.0.1:50001:50001) не найден в install.sh"
        
        with allure.step("Проверка конфигурации сервиса docs (expose)"):
            # Проверяем, что docs имеет expose, а не ports
            has_expose = "expose:" in script_content or '"expose"' in script_content
            allure.attach(
                str(has_expose),
                "Сервис docs использует expose",
                allure.attachment_type.TEXT
            )
            assert has_expose, \
                "Сервис docs должен использовать expose вместо ports для безопасности"

    @allure.title("Проверка консистентности портов в скрипте")
    @allure.description("""
    Проверяет, что все необходимые порты сервисов упоминаются в скрипте install.sh.
    
    **Что проверяется:**
    - Все порты основных сервисов упоминаются в скрипте
    - Порты: 50000 (bot), 50001 (docs-proxy), 50002 (codex-docs), 50003 (user-cabinet)
    - Порты должны быть упомянуты в контексте создания docker-compose.yml
    
    **Тестовые данные:**
    - Порт 50000: сервис bot
    - Порт 50001: сервис docs-proxy
    - Порт 50002: сервис codex-docs
    - Порт 50003: сервис user-cabinet
    
    **Предусловия:**
    - Файл install.sh должен существовать и быть доступен для чтения
    - Скрипт должен создавать docker-compose.yml с правильными портами
    
    **Ожидаемый результат:**
    Все необходимые порты упоминаются в скрипте install.sh. Порты должны быть консистентными и соответствовать конфигурации docker-compose.yml.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("install", "ports", "unit", "docker-compose", "consistency")
    def test_port_consistency(self, project_root, port_constants):
        """Проверка консистентности портов в install.sh"""
        install_script = project_root / "install.sh"
        
        if not install_script.exists():
            pytest.skip("install.sh не найден")
        
        with allure.step("Подготовка: чтение содержимого скрипта"):
            with open(install_script, "r", encoding="utf-8") as f:
                script_content = f.read()
            
            allure.attach(
                str(len(script_content)),
                "Размер файла (символов)",
                allure.attachment_type.TEXT
            )
        
        with allure.step("Проверка упоминания портов в скрипте"):
            # Проверяем, что порты упоминаются в скрипте
            port_checks = {
                "50000": "bot",
                "50001": "docs-proxy",
                "50002": "codex-docs",
                "50003": "user-cabinet"
            }
            
            missing_ports = []
            found_ports = []
            
            for port, service in port_checks.items():
                if port in script_content:
                    found_ports.append(f"{service} (порт {port})")
                else:
                    missing_ports.append(f"{service} (порт {port})")
            
            allure.attach(
                "\n".join(found_ports) if found_ports else "Нет найденных портов",
                "Найденные порты",
                allure.attachment_type.TEXT
            )
            
            if missing_ports:
                allure.attach(
                    "\n".join(missing_ports),
                    "Отсутствующие порты",
                    allure.attachment_type.TEXT
                )
            
            # Проверяем, что все порты упоминаются в скрипте
            assert len(missing_ports) == 0, \
                f"Порты не упоминаются в install.sh: {', '.join(missing_ports)}"
            
            allure.attach(
                f"Всего проверено портов: {len(port_checks)}\nНайдено: {len(found_ports)}\nОтсутствует: {len(missing_ports)}",
                "Итоговая статистика",
                allure.attachment_type.TEXT
            )

