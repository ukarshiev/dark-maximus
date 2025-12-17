#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Фикстуры для тестов скриптов установки
"""

import pytest
import yaml
import tempfile
import shutil
import os
import logging
from pathlib import Path
from typing import Dict, Any

logger = logging.getLogger(__name__)


@pytest.fixture
def temp_compose_file(tmp_path):
    """Создает временный docker-compose.yml файл для тестирования"""
    compose_file = tmp_path / "docker-compose.yml"
    yield compose_file
    # Очистка после теста
    if compose_file.exists():
        compose_file.unlink()


@pytest.fixture
def sample_compose_config() -> Dict[str, Any]:
    """Возвращает пример конфигурации docker-compose.yml"""
    return {
        "services": {
            "bot": {
                "build": ".",
                "container_name": "dark-maximus-bot",
                "ports": ["127.0.0.1:50000:50000"],
                "networks": ["dark-maximus-network"]
            },
            "docs": {
                "build": {
                    "context": ".",
                    "dockerfile": "Dockerfile.docs"
                },
                "expose": ["80"],
                "networks": ["dark-maximus-network"]
            },
            "docs-proxy": {
                "build": {
                    "context": "./apps/docs-proxy",
                    "dockerfile": "Dockerfile"
                },
                "ports": ["127.0.0.1:50001:50001"],
                "networks": ["dark-maximus-network"],
                "depends_on": ["docs"]
            },
            "codex-docs": {
                "build": {
                    "context": ".",
                    "dockerfile": "Dockerfile.codex-docs"
                },
                "ports": ["127.0.0.1:50002:50002"],
                "networks": ["dark-maximus-network"]
            },
            "user-cabinet": {
                "build": {
                    "context": "./apps/user-cabinet",
                    "dockerfile": "Dockerfile"
                },
                "ports": ["127.0.0.1:50003:50003"],
                "networks": ["dark-maximus-network"]
            }
        },
        "networks": {
            "dark-maximus-network": {
                "driver": "bridge",
                "name": "dark-maximus-network"
            }
        }
    }


@pytest.fixture
def compose_file_with_services(tmp_path, sample_compose_config):
    """Создает docker-compose.yml файл с базовыми сервисами"""
    compose_file = tmp_path / "docker-compose.yml"
    with open(compose_file, "w", encoding="utf-8") as f:
        yaml.dump(sample_compose_config, f, default_flow_style=False, allow_unicode=True)
    return compose_file


@pytest.fixture
def project_root() -> Path:
    """
    Возвращает путь к корню проекта.
    
    Определяет путь автоматически:
    - Через переменную окружения PROJECT_ROOT (если установлена)
    - В Docker контейнере: использует /app/ (где маппятся скрипты)
    - Локально: вычисляет относительно расположения этого файла
    """
    # Проверяем переменную окружения PROJECT_ROOT
    project_root_env = os.getenv('PROJECT_ROOT')
    if project_root_env:
        env_path = Path(project_root_env).resolve()
        if env_path.exists() and env_path.is_dir():
            test_script = env_path / "install-autotest.sh"
            if test_script.exists():
                logger.debug(f"Используем PROJECT_ROOT из переменной окружения: {env_path}")
                return env_path
    
    # Проверяем, запущен ли тест в Docker контейнере
    app_path = Path("/app")
    if app_path.exists() and app_path.is_dir():
        # В Docker контейнере скрипты маппятся в /app/
        # Проверяем наличие всех трех скриптов для большей надежности
        test_scripts = [
            app_path / "install.sh",
            app_path / "install-autotest.sh",
            app_path / "ssl-install.sh"
        ]
        found_scripts = [s for s in test_scripts if s.exists()]
        if found_scripts:
            logger.debug(f"Используем /app из Docker контейнера. Найдено скриптов: {len(found_scripts)}")
            return app_path
        else:
            # Если скрипты не найдены, но мы в контейнере, все равно возвращаем /app
            # Это может быть случай, когда файлы не маппятся на боевом сервере
            logger.warning(
                f"Директория /app существует, но скрипты не найдены. "
                f"Проверяем: {[str(s) for s in test_scripts]}. "
                f"Возвращаем /app как fallback."
            )
            return app_path  # Возвращаем /app даже если скрипты не найдены
    
    # Локальный запуск: вычисляем относительно расположения файла
    # tests/scripts/conftest.py -> tests/scripts/ -> tests/ -> корень проекта
    local_root = Path(__file__).parent.parent.parent
    
    # Проверяем, что это действительно корень проекта (должен содержать хотя бы один скрипт)
    test_scripts = [
        local_root / "install.sh",
        local_root / "install-autotest.sh",
        local_root / "ssl-install.sh"
    ]
    found_scripts = [s for s in test_scripts if s.exists()]
    if found_scripts:
        logger.debug(f"Используем локальный путь: {local_root}. Найдено скриптов: {len(found_scripts)}")
        return local_root
    
    # Если ничего не найдено, возвращаем вычисленный путь (для совместимости)
    logger.warning(f"Не удалось найти скрипты. Возвращаем вычисленный путь: {local_root}")
    return local_root


@pytest.fixture
def port_constants() -> Dict[str, int]:
    """Возвращает константы портов для проверки"""
    return {
        "bot": 50000,
        "docs-proxy": 50001,
        "codex-docs": 50002,
        "user-cabinet": 50003,
        "allure-service": 50004,
        "allure-homepage": 50005
    }

