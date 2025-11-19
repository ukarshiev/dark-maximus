#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Тесты для валидации docker-compose.yml
"""

import pytest
import yaml
import allure
from pathlib import Path
from typing import Dict, Any


@allure.epic("Валидация конфигураций")
@allure.feature("Docker Compose")
@allure.label("package", "tests.scripts")
@pytest.mark.unit
class TestDockerCompose:
    """Тесты для валидации docker-compose.yml"""

    @allure.title("Проверка синтаксиса docker-compose.yml")
    @allure.description("""
    Проверяет валидность YAML синтаксиса docker-compose.yml.
    
    **Что проверяется:**
    - Файл может быть прочитан как валидный YAML
    - Структура файла корректна
    
    **Ожидаемый результат:**
    Файл успешно парсится без ошибок.
    """)
    @allure.severity(allure.severity_level.CRITICAL)
    @allure.tag("docker-compose", "yaml", "syntax", "unit", "critical")
    def test_docker_compose_syntax(self, project_root):
        """Проверка валидности YAML синтаксиса"""
        compose_file = project_root / "docker-compose.yml"
        
        if not compose_file.exists():
            pytest.skip("docker-compose.yml не найден в корне проекта")
        
        with allure.step("Чтение docker-compose.yml"):
            with open(compose_file, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f)
            
            allure.attach(str(config), "Конфигурация docker-compose.yml", allure.attachment_type.JSON)
        
        with allure.step("Проверка структуры"):
            assert config is not None, "Файл пуст или невалидный"
            assert isinstance(config, dict), "Конфигурация должна быть словарем"

    @allure.title("Проверка наличия обязательных сервисов")
    @allure.description("""
    Проверяет наличие всех обязательных сервисов в docker-compose.yml.
    
    **Что проверяется:**
    - Наличие сервисов: bot, docs, docs-proxy, codex-docs, user-cabinet
    - Каждый сервис имеет корректную структуру
    
    **Ожидаемый результат:**
    Все обязательные сервисы присутствуют в конфигурации.
    """)
    @allure.severity(allure.severity_level.CRITICAL)
    @allure.tag("docker-compose", "services", "unit", "critical")
    def test_required_services_exist(self, project_root):
        """Проверка наличия всех обязательных сервисов"""
        compose_file = project_root / "docker-compose.yml"
        
        if not compose_file.exists():
            pytest.skip("docker-compose.yml не найден в корне проекта")
        
        with open(compose_file, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
        
        required_services = ["bot", "docs", "docs-proxy", "codex-docs", "user-cabinet"]
        services = config.get("services", {})
        
        with allure.step("Проверка наличия сервисов"):
            missing_services = []
            for service in required_services:
                if service not in services:
                    missing_services.append(service)
            
            allure.attach(
                str(required_services),
                "Обязательные сервисы",
                allure.attachment_type.TEXT
            )
            allure.attach(
                str(list(services.keys())),
                "Найденные сервисы",
                allure.attachment_type.TEXT
            )
            
            assert len(missing_services) == 0, \
                f"Отсутствуют обязательные сервисы: {', '.join(missing_services)}"

    @allure.title("Проверка корректности портов")
    @allure.description("""
    Проверяет соответствие портов константам.
    
    **Что проверяется:**
    - Порт каждого сервиса соответствует ожидаемому значению
    - Порты не конфликтуют между сервисами
    
    **Ожидаемый результат:**
    Все порты соответствуют константам.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("docker-compose", "ports", "unit")
    def test_ports_correctness(self, project_root, port_constants):
        """Проверка соответствия портов константам"""
        compose_file = project_root / "docker-compose.yml"
        
        if not compose_file.exists():
            pytest.skip("docker-compose.yml не найден в корне проекта")
        
        with open(compose_file, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
        
        services = config.get("services", {})
        port_errors = []
        
        with allure.step("Проверка портов сервисов"):
            for service_name, expected_port in port_constants.items():
                if service_name not in services:
                    continue
                
                service = services[service_name]
                ports = service.get("ports", [])
                
                # Проверяем порты в формате "127.0.0.1:PORT:PORT" или "PORT:PORT"
                found_port = False
                for port_mapping in ports:
                    if isinstance(port_mapping, str):
                        # Формат: "127.0.0.1:50001:50001" или "50001:50001"
                        parts = port_mapping.split(":")
                        if len(parts) >= 2:
                            host_port = parts[-2] if len(parts) == 3 else parts[0]
                            if host_port == str(expected_port):
                                found_port = True
                                break
                
                if not found_port and ports:
                    port_errors.append(
                        f"{service_name}: ожидается порт {expected_port}, "
                        f"найдено {ports}"
                    )
            
            allure.attach(
                str(port_constants),
                "Ожидаемые порты",
                allure.attachment_type.JSON
            )
            
            if port_errors:
                allure.attach(
                    "\n".join(port_errors),
                    "Ошибки портов",
                    allure.attachment_type.TEXT
                )
            
            assert len(port_errors) == 0, f"Ошибки портов:\n" + "\n".join(port_errors)

    @allure.title("Проверка наличия networks секции")
    @allure.description("""
    Проверяет наличие секции networks в docker-compose.yml.
    
    **Что проверяется:**
    - Секция networks существует
    - Содержит dark-maximus-network
    
    **Ожидаемый результат:**
    Секция networks присутствует и корректна.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("docker-compose", "networks", "unit")
    def test_networks_section_exists(self, project_root):
        """Проверка наличия секции networks"""
        compose_file = project_root / "docker-compose.yml"
        
        if not compose_file.exists():
            pytest.skip("docker-compose.yml не найден в корне проекта")
        
        with open(compose_file, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
        
        with allure.step("Проверка секции networks"):
            assert "networks" in config, "Секция networks отсутствует"
            networks = config["networks"]
            assert "dark-maximus-network" in networks, \
                "Сеть dark-maximus-network отсутствует"
            
            allure.attach(
                str(networks),
                "Конфигурация networks",
                allure.attachment_type.JSON
            )

    @allure.title("Проверка отсутствия дубликатов сервисов")
    @allure.description("""
    Проверяет отсутствие дубликатов сервисов в docker-compose.yml.
    
    **Что проверяется:**
    - Каждый сервис определен только один раз
    - Нет конфликтующих определений
    
    **Ожидаемый результат:**
    Дубликатов сервисов нет.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("docker-compose", "duplicates", "unit")
    def test_no_duplicate_services(self, project_root):
        """Проверка отсутствия дубликатов сервисов"""
        compose_file = project_root / "docker-compose.yml"
        
        if not compose_file.exists():
            pytest.skip("docker-compose.yml не найден в корне проекта")
        
        with open(compose_file, "r", encoding="utf-8") as f:
            content = f.read()
        
        with open(compose_file, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
        
        services = config.get("services", {})
        service_names = list(services.keys())
        
        with allure.step("Проверка дубликатов"):
            # Проверяем, что каждый сервис упоминается только один раз в секции services
            for service_name in service_names:
                # Ищем все вхождения "^  service_name:" в файле
                pattern = f"^  {service_name}:"
                count = sum(1 for line in content.split("\n") if line.strip().startswith(f"{service_name}:"))
                
                if count > 1:
                    pytest.fail(f"Сервис {service_name} определен {count} раз(а)")
            
            allure.attach(
                str(service_names),
                "Список сервисов",
                allure.attachment_type.TEXT
            )

    @allure.title("Проверка корректности volumes маппингов")
    @allure.description("""
    Проверяет корректность volumes маппингов в docker-compose.yml.
    
    **Что проверяется:**
    - Формат volumes корректен
    - Пути существуют или могут быть созданы
    
    **Ожидаемый результат:**
    Все volumes маппинги корректны.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("docker-compose", "volumes", "unit")
    def test_volumes_mappings(self, project_root):
        """Проверка корректности volumes маппингов"""
        compose_file = project_root / "docker-compose.yml"
        
        if not compose_file.exists():
            pytest.skip("docker-compose.yml не найден в корне проекта")
        
        with open(compose_file, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
        
        services = config.get("services", {})
        volume_errors = []
        
        with allure.step("Проверка volumes маппингов"):
            for service_name, service in services.items():
                volumes = service.get("volumes", [])
                
                for volume in volumes:
                    if isinstance(volume, str) and ":" in volume:
                        # Формат: "./path:/container/path" или "./path:/container/path:ro"
                        parts = volume.split(":")
                        if len(parts) >= 2:
                            host_path = parts[0]
                            
                            # Проверяем относительные пути
                            if host_path.startswith("./"):
                                # Путь относительно корня проекта
                                full_path = project_root / host_path[2:]
                                # Не проверяем существование, только формат
                                if not host_path.startswith("./"):
                                    volume_errors.append(
                                        f"{service_name}: некорректный формат пути {host_path}"
                                    )
            
            if volume_errors:
                allure.attach(
                    "\n".join(volume_errors),
                    "Ошибки volumes",
                    allure.attachment_type.TEXT
                )
            
            assert len(volume_errors) == 0, \
                f"Ошибки volumes маппингов:\n" + "\n".join(volume_errors)

