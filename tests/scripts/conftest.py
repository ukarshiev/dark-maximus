#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Фикстуры для тестов скриптов установки
"""

import pytest
import yaml
import tempfile
import shutil
from pathlib import Path
from typing import Dict, Any


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
    """Возвращает путь к корню проекта"""
    return Path(__file__).parent.parent.parent


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

