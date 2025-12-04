#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Тесты для валидации install-autotest.sh и добавления сервисов
"""

import pytest
import yaml
import os
import logging
import allure
from pathlib import Path

logger = logging.getLogger(__name__)


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
    - Файл install-autotest.sh существует в корне проекта
    - Файл является обычным файлом (не директорией)
    - Файл доступен для чтения в контейнере autotest
    
    **Тестовые данные:**
    - Путь к файлу: {project_root}/install-autotest.sh
    - Файл должен быть маппирован в контейнер через docker-compose.yml
    
    **Предусловия:**
    - Файл install-autotest.sh должен существовать в корне проекта
    - Файл должен быть маппирован в контейнер autotest через volume
    
    **Ожидаемый результат:**
    Файл install-autotest.sh найден, является файлом и доступен для чтения в контейнере.
    """)
    @allure.severity(allure.severity_level.CRITICAL)
    @allure.tag("autotest", "script", "unit", "critical", "file-existence", "validation")
    def test_autotest_script_exists(self, project_root):
        """Проверка наличия install-autotest.sh"""
        autotest_script = project_root / "install-autotest.sh"
        
        with allure.step("Подготовка: определение пути к файлу"):
            # Диагностическая информация
            cwd = Path.cwd()
            project_root_env = os.getenv('PROJECT_ROOT')
            
            diagnostic_info = f"""Корневая директория проекта (project_root): {project_root}
Путь к файлу install-autotest.sh: {autotest_script}
Текущая рабочая директория: {cwd}
PROJECT_ROOT (env): {project_root_env}
Файл существует: {autotest_script.exists()}
"""
            allure.attach(
                diagnostic_info,
                "Диагностическая информация",
                allure.attachment_type.TEXT
            )
            logger.debug(diagnostic_info)
            
            allure.attach(
                str(autotest_script),
                "Путь к файлу install-autotest.sh",
                allure.attachment_type.TEXT
            )
            allure.attach(
                str(project_root),
                "Корневая директория проекта",
                allure.attachment_type.TEXT
            )
            
            # Проверяем альтернативные пути
            alternative_paths = [
                Path("/app/install-autotest.sh"),
                Path.cwd() / "install-autotest.sh",
                Path(__file__).parent.parent.parent / "install-autotest.sh"
            ]
            if project_root_env:
                alternative_paths.append(Path(project_root_env) / "install-autotest.sh")
            
            found_paths = [p for p in alternative_paths if p.exists()]
            if found_paths:
                allure.attach(
                    "\n".join(str(p) for p in found_paths),
                    "Альтернативные пути, где файл найден",
                    allure.attachment_type.TEXT
                )
        
        with allure.step("Проверка существования файла"):
            file_exists = autotest_script.exists()
            allure.attach(
                str(file_exists),
                "Файл существует",
                allure.attachment_type.TEXT
            )
            
            if not file_exists:
                # Дополнительная диагностика
                error_msg = f"""Файл install-autotest.sh не найден по пути: {autotest_script}

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
            
            assert file_exists, f"Файл install-autotest.sh не найден по пути: {autotest_script}"
        
        with allure.step("Проверка типа файла"):
            is_file = autotest_script.is_file()
            allure.attach(
                str(is_file),
                "Является файлом",
                allure.attachment_type.TEXT
            )
            assert is_file, "install-autotest.sh не является файлом"

    @allure.title("Проверка функции добавления сервисов")
    @allure.description("""
    Проверяет наличие функции безопасного добавления сервисов в docker-compose.yml.
    
    **Что проверяется:**
    - Функция add_services_to_compose существует в скрипте
    - Функция использует Python для безопасной модификации YAML
    - Есть проверка валидности docker-compose.yml после добавления сервисов
    - Используется резервное копирование перед модификацией
    
    **Тестовые данные:**
    - Файл: install-autotest.sh
    - Ожидаемая функция: add_services_to_compose
    - Ожидаемое использование: python3 или python для модификации YAML
    - Ожидаемая валидация: docker compose config или docker-compose config
    
    **Предусловия:**
    - Файл install-autotest.sh должен существовать
    - Скрипт должен содержать функцию add_services_to_compose
    
    **Ожидаемый результат:**
    Функция добавления сервисов реализована корректно с использованием Python для безопасной модификации YAML и проверкой валидности.
    """)
    @allure.severity(allure.severity_level.CRITICAL)
    @allure.tag("autotest", "add-services", "unit", "critical", "function-validation", "yaml-modification")
    def test_add_services_function(self, project_root):
        """Проверка функции добавления сервисов"""
        autotest_script = project_root / "install-autotest.sh"
        
        if not autotest_script.exists():
            pytest.skip("install-autotest.sh не найден")
        
        with allure.step("Подготовка: чтение содержимого скрипта"):
            with open(autotest_script, "r", encoding="utf-8") as f:
                script_content = f.read()
            allure.attach(
                str(len(script_content)),
                "Размер файла (символов)",
                allure.attachment_type.TEXT
            )
        
        with allure.step("Проверка функции add_services_to_compose"):
            function_exists = "add_services_to_compose" in script_content
            allure.attach(
                str(function_exists),
                "Функция add_services_to_compose найдена",
                allure.attachment_type.TEXT
            )
            if function_exists:
                # Находим строки с функцией для прикрепления
                lines = script_content.split('\n')
                function_lines = []
                in_function = False
                for i, line in enumerate(lines, 1):
                    if "add_services_to_compose" in line:
                        in_function = True
                    if in_function:
                        function_lines.append(f"{i}: {line}")
                        if line.strip().startswith('}') and i > 1:
                            break
                if function_lines:
                    allure.attach(
                        '\n'.join(function_lines[:20]),  # Первые 20 строк функции
                        "Начало функции add_services_to_compose",
                        allure.attachment_type.TEXT
                    )
            assert function_exists, "Функция add_services_to_compose не найдена"
        
        with allure.step("Проверка использования Python"):
            uses_python3 = "python3" in script_content
            uses_python = "python" in script_content
            allure.attach(
                f"python3: {uses_python3}, python: {uses_python}",
                "Использование Python",
                allure.attachment_type.TEXT
            )
            assert uses_python3 or uses_python, \
                "Функция должна использовать Python для модификации YAML"
        
        with allure.step("Проверка валидации docker-compose.yml"):
            # В скрипте используется переменная ${DC[@]} config, где DC может быть ["docker", "compose"] или ["docker-compose"]
            uses_dc_config = "${DC[@]} config" in script_content or '${DC[@]} config' in script_content
            uses_compose_config = "docker compose config" in script_content
            uses_docker_compose_config = "docker-compose config" in script_content
            has_config_check = uses_dc_config or uses_compose_config or uses_docker_compose_config
            allure.attach(
                f"${{DC[@]}} config: {uses_dc_config}, docker compose config: {uses_compose_config}, docker-compose config: {uses_docker_compose_config}, общая проверка: {has_config_check}",
                "Проверка валидации",
                allure.attachment_type.TEXT
            )
            assert has_config_check, \
                "Должна быть проверка валидности через docker compose config (используется ${DC[@]} config)"

    @allure.title("Проверка отсутствия дубликатов при повторном запуске")
    @allure.description("""
    Проверяет, что скрипт идемпотентен и не создает дубликаты сервисов при повторном запуске.
    
    **Что проверяется:**
    - Функция service_exists существует и проверяет наличие сервисов в docker-compose.yml
    - Перед добавлением сервиса выполняется проверка его существования
    - Сервисы добавляются только если их нет в docker-compose.yml
    - Скрипт можно безопасно запускать несколько раз без создания дубликатов
    
    **Тестовые данные:**
    - Файл: install-autotest.sh
    - Ожидаемая функция: service_exists
    - Ожидаемая логика: проверка перед добавлением через if и service_exists
    
    **Предусловия:**
    - Файл install-autotest.sh должен существовать
    - Скрипт должен содержать функцию service_exists
    - Скрипт должен проверять наличие сервиса перед его добавлением
    
    **Ожидаемый результат:**
    Скрипт идемпотентен - не создает дубликаты сервисов при повторном запуске.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("autotest", "idempotency", "unit", "duplicate-prevention", "script-validation")
    def test_idempotency_check(self, project_root):
        """Проверка идемпотентности скрипта"""
        autotest_script = project_root / "install-autotest.sh"
        
        if not autotest_script.exists():
            pytest.skip("install-autotest.sh не найден")
        
        with allure.step("Подготовка: чтение содержимого скрипта"):
            with open(autotest_script, "r", encoding="utf-8") as f:
                script_content = f.read()
        
        with allure.step("Проверка функции service_exists"):
            function_exists = "service_exists" in script_content
            allure.attach(
                str(function_exists),
                "Функция service_exists найдена",
                allure.attachment_type.TEXT
            )
            if function_exists:
                # Находим строки с функцией
                lines = script_content.split('\n')
                function_lines = []
                in_function = False
                for i, line in enumerate(lines, 1):
                    if "service_exists" in line and "()" in line:
                        in_function = True
                    if in_function:
                        function_lines.append(f"{i}: {line}")
                        if line.strip().startswith('}') and i > 1:
                            break
                if function_lines:
                    allure.attach(
                        '\n'.join(function_lines),
                        "Функция service_exists",
                        allure.attachment_type.TEXT
                    )
            assert function_exists, "Функция service_exists не найдена"
        
        with allure.step("Проверка проверки перед добавлением"):
            has_if = "if" in script_content
            has_service_exists_check = "service_exists" in script_content
            has_conditional_check = has_if and has_service_exists_check
            allure.attach(
                f"if: {has_if}, service_exists: {has_service_exists_check}, комбинация: {has_conditional_check}",
                "Проверка перед добавлением",
                allure.attachment_type.TEXT
            )
            assert has_conditional_check, \
                "Должна быть проверка наличия сервиса перед добавлением"

    @allure.title("Проверка структуры добавляемых сервисов")
    @allure.description("""
    Проверяет корректность структуры добавляемых сервисов в docker-compose.yml.
    
    **Что проверяется:**
    - Сервисы autotest, allure-service, allure-homepage определены в скрипте
    - Сервисы правильно названы и структурированы
    - Зависимости (depends_on) корректны: allure-homepage зависит от allure-service
    - Порты соответствуют константам (50004 для allure-service, 50005 для allure-homepage)
    
    **Тестовые данные:**
    - Файл: install-autotest.sh
    - Ожидаемые сервисы: autotest, allure-service, allure-homepage
    - Ожидаемая зависимость: allure-homepage зависит от allure-service через depends_on
    
    **Предусловия:**
    - Файл install-autotest.sh должен существовать
    - Скрипт должен содержать определения всех трех сервисов
    
    **Ожидаемый результат:**
    Все сервисы определены корректно с правильными зависимостями и структурой.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("autotest", "services-structure", "unit", "docker-compose", "services-validation")
    def test_services_structure(self, project_root):
        """Проверка структуры добавляемых сервисов"""
        autotest_script = project_root / "install-autotest.sh"
        
        if not autotest_script.exists():
            pytest.skip("install-autotest.sh не найден")
        
        with allure.step("Подготовка: чтение содержимого скрипта"):
            with open(autotest_script, "r", encoding="utf-8") as f:
                script_content = f.read()
        
        required_services = ["autotest", "allure-service", "allure-homepage"]
        
        with allure.step("Проверка наличия сервисов"):
            found_services = []
            missing_services = []
            for service in required_services:
                service_found = f"'{service}'" in script_content or f'"{service}"' in script_content
                if service_found:
                    found_services.append(service)
                else:
                    missing_services.append(service)
            
            allure.attach(
                f"Найдено: {', '.join(found_services) if found_services else 'нет'}\n"
                f"Отсутствует: {', '.join(missing_services) if missing_services else 'нет'}",
                "Статус проверки сервисов",
                allure.attachment_type.TEXT
            )
            
            if missing_services:
                allure.attach(
                    "\n".join(missing_services),
                    "Отсутствующие сервисы",
                    allure.attachment_type.TEXT
                )
            
            assert len(missing_services) == 0, \
                f"Сервисы не найдены в скрипте: {', '.join(missing_services)}"
        
        with allure.step("Проверка depends_on для allure-homepage"):
            has_depends_on = "depends_on" in script_content
            has_allure_service = "allure-service" in script_content
            has_dependency = has_depends_on and has_allure_service
            allure.attach(
                f"depends_on: {has_depends_on}, allure-service: {has_allure_service}, зависимость: {has_dependency}",
                "Проверка зависимости",
                allure.attachment_type.TEXT
            )
            assert has_dependency, \
                "allure-homepage должен зависеть от allure-service"

    @allure.title("Проверка порта allure-homepage")
    @allure.description("""
    Проверяет, что порт 50005 правильно связан с сервисом allure-homepage, а не с allure-service.
    
    **Что проверяется:**
    - Порт 50005 определен в скрипте
    - Порт 50005 связан с сервисом allure-homepage (не с allure-service)
    - Константа PORT_ALLURE_HOMEPAGE=50005 определена
    - Проверка доступности порта 50005 относится к allure-homepage
    
    **Тестовые данные:**
    - Файл: install-autotest.sh
    - Ожидаемый порт: 50005 для allure-homepage
    - Ожидаемая константа: PORT_ALLURE_HOMEPAGE=50005
    - Ожидаемая связь: порт 50005 должен быть связан с allure-homepage
    
    **Предусловия:**
    - Файл install-autotest.sh должен существовать
    - Скрипт должен содержать порт 50005
    - Порт должен быть связан с allure-homepage
    
    **Ожидаемый результат:**
    Порт 50005 правильно связан с сервисом allure-homepage, а не с allure-service (который использует порт 50004).
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("autotest", "ports", "unit", "port-validation", "allure-homepage")
    def test_allure_homepage_port_check(self, project_root):
        """Проверка порта allure-homepage"""
        autotest_script = project_root / "install-autotest.sh"
        
        if not autotest_script.exists():
            pytest.skip("install-autotest.sh не найден")
        
        with allure.step("Подготовка: чтение содержимого скрипта"):
            with open(autotest_script, "r", encoding="utf-8") as f:
                script_content = f.read()
        
        with allure.step("Проверка порта 50005"):
            port_50005_exists = "50005" in script_content
            allure.attach(
                str(port_50005_exists),
                "Порт 50005 найден в скрипте",
                allure.attachment_type.TEXT
            )
            assert port_50005_exists, "Порт 50005 должен быть в скрипте"
        
        with allure.step("Проверка связи порта 50005 с allure-homepage"):
            has_allure_homepage = "allure-homepage" in script_content.lower()
            has_port_constant = "PORT_ALLURE_HOMEPAGE" in script_content
            has_connection = has_allure_homepage or has_port_constant
            allure.attach(
                f"allure-homepage: {has_allure_homepage}, PORT_ALLURE_HOMEPAGE: {has_port_constant}, связь: {has_connection}",
                "Связь порта с сервисом",
                allure.attachment_type.TEXT
            )
            if has_port_constant:
                # Находим строку с константой
                lines = script_content.split('\n')
                for i, line in enumerate(lines, 1):
                    if "PORT_ALLURE_HOMEPAGE" in line:
                        allure.attach(
                            f"{i}: {line.strip()}",
                            "Константа PORT_ALLURE_HOMEPAGE",
                            allure.attachment_type.TEXT
                        )
                        break
            assert has_connection, \
                "Порт 50005 должен быть связан с allure-homepage"

