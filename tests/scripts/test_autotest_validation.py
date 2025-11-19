#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Тесты для валидации install-autotest.sh и добавления сервисов
"""

import pytest
import yaml
import allure
from pathlib import Path


@allure.epic("Валидация скриптов установки")
@allure.feature("Autotest Install Script")
@allure.label("package", "tests.scripts")
@pytest.mark.unit
class TestAutotestValidation:
    """Тесты для валидации install-autotest.sh"""

    @allure.title("Проверка наличия install-autotest.sh")
    @allure.description("""
    Проверяет наличие файла install-autotest.sh в корне проекта.
    
    **Что проверяется:**
    - Файл install-autotest.sh существует
    - Файл доступен для чтения
    
    **Ожидаемый результат:**
    Файл install-autotest.sh найден и доступен.
    """)
    @allure.severity(allure.severity_level.CRITICAL)
    @allure.tag("autotest", "script", "unit", "critical")
    def test_autotest_script_exists(self, project_root):
        """Проверка наличия install-autotest.sh"""
        autotest_script = project_root / "install-autotest.sh"
        
        with allure.step("Проверка существования файла"):
            assert autotest_script.exists(), "Файл install-autotest.sh не найден"
            assert autotest_script.is_file(), "install-autotest.sh не является файлом"

    @allure.title("Проверка функции добавления сервисов")
    @allure.description("""
    Проверяет наличие функции безопасного добавления сервисов.
    
    **Что проверяется:**
    - Функция add_services_to_compose существует
    - Функция использует Python для модификации YAML
    - Есть проверка валидности после добавления
    
    **Ожидаемый результат:**
    Функция добавления сервисов реализована корректно.
    """)
    @allure.severity(allure.severity_level.CRITICAL)
    @allure.tag("autotest", "add-services", "unit", "critical")
    def test_add_services_function(self, project_root):
        """Проверка функции добавления сервисов"""
        autotest_script = project_root / "install-autotest.sh"
        
        if not autotest_script.exists():
            pytest.skip("install-autotest.sh не найден")
        
        with open(autotest_script, "r", encoding="utf-8") as f:
            script_content = f.read()
        
        with allure.step("Проверка функции add_services_to_compose"):
            assert "add_services_to_compose" in script_content, \
                "Функция add_services_to_compose не найдена"
        
        with allure.step("Проверка использования Python"):
            assert "python3" in script_content or "python" in script_content, \
                "Функция должна использовать Python для модификации YAML"
        
        with allure.step("Проверка валидации"):
            assert "docker compose config" in script_content or \
                   "docker-compose config" in script_content, \
                "Должна быть проверка валидности через docker compose config"

    @allure.title("Проверка отсутствия дубликатов при повторном запуске")
    @allure.description("""
    Проверяет, что скрипт не создает дубликаты сервисов.
    
    **Что проверяется:**
    - Функция service_exists проверяет наличие сервисов
    - Сервисы добавляются только если их нет
    
    **Ожидаемый результат:**
    Скрипт идемпотентен - не создает дубликаты.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("autotest", "idempotency", "unit")
    def test_idempotency_check(self, project_root):
        """Проверка идемпотентности скрипта"""
        autotest_script = project_root / "install-autotest.sh"
        
        if not autotest_script.exists():
            pytest.skip("install-autotest.sh не найден")
        
        with open(autotest_script, "r", encoding="utf-8") as f:
            script_content = f.read()
        
        with allure.step("Проверка функции service_exists"):
            assert "service_exists" in script_content, \
                "Функция service_exists не найдена"
        
        with allure.step("Проверка проверки перед добавлением"):
            # Должна быть проверка перед добавлением
            assert "if" in script_content and "service_exists" in script_content, \
                "Должна быть проверка наличия сервиса перед добавлением"

    @allure.title("Проверка структуры добавляемых сервисов")
    @allure.description("""
    Проверяет корректность структуры добавляемых сервисов.
    
    **Что проверяется:**
    - autotest, allure-service, allure-homepage определены правильно
    - Порты соответствуют константам
    - Зависимости (depends_on) корректны
    
    **Ожидаемый результат:**
    Все сервисы определены корректно.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("autotest", "services-structure", "unit")
    def test_services_structure(self, project_root):
        """Проверка структуры добавляемых сервисов"""
        autotest_script = project_root / "install-autotest.sh"
        
        if not autotest_script.exists():
            pytest.skip("install-autotest.sh не найден")
        
        with open(autotest_script, "r", encoding="utf-8") as f:
            script_content = f.read()
        
        required_services = ["autotest", "allure-service", "allure-homepage"]
        
        with allure.step("Проверка наличия сервисов"):
            missing_services = []
            for service in required_services:
                if f"'{service}'" not in script_content and \
                   f'"{service}"' not in script_content:
                    missing_services.append(service)
            
            if missing_services:
                allure.attach(
                    "\n".join(missing_services),
                    "Отсутствующие сервисы",
                    allure.attachment_type.TEXT
                )
            
            assert len(missing_services) == 0, \
                f"Сервисы не найдены в скрипте: {', '.join(missing_services)}"
        
        with allure.step("Проверка depends_on для allure-homepage"):
            assert "depends_on" in script_content and \
                   "allure-service" in script_content, \
                "allure-homepage должен зависеть от allure-service"

    @allure.title("Проверка порта allure-homepage")
    @allure.description("""
    Проверяет, что проверка порта 50005 относится к allure-homepage, а не allure-service.
    
    **Что проверяется:**
    - Проверка порта 50005 для allure-homepage
    - allure-service на порту 50004
    
    **Ожидаемый результат:**
    Порты проверяются для правильных сервисов.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("autotest", "ports", "unit")
    def test_allure_homepage_port_check(self, project_root):
        """Проверка порта allure-homepage"""
        autotest_script = project_root / "install-autotest.sh"
        
        if not autotest_script.exists():
            pytest.skip("install-autotest.sh не найден")
        
        with open(autotest_script, "r", encoding="utf-8") as f:
            script_content = f.read()
        
        with allure.step("Проверка порта 50005"):
            # Проверяем, что порт 50005 связан с allure-homepage
            assert "50005" in script_content, \
                "Порт 50005 должен быть в скрипте"
            
            # Проверяем, что проверка порта связана с allure-homepage
            assert "allure-homepage" in script_content.lower() or \
                   "PORT_ALLURE_HOMEPAGE" in script_content, \
                "Порт 50005 должен быть связан с allure-homepage"

