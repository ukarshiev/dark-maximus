#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Фикстуры для интеграционных тестов авторизации всех сервисов
"""

import pytest
import requests
import time
import os
from pathlib import Path
from typing import Dict, Tuple


def _is_docker_environment() -> bool:
    """
    Определяет, запущены ли тесты внутри Docker контейнера.
    
    Проверяет наличие файла /proc/1/cgroup, который в Docker контейнере
    содержит упоминание "docker".
    
    Returns:
        True если тесты запущены в Docker, False если на хосте
    """
    try:
        cgroup_path = Path("/proc/1/cgroup")
        if cgroup_path.exists():
            content = cgroup_path.read_text()
            return "docker" in content.lower()
    except Exception:
        pass
    
    # Дополнительная проверка: если hostname содержит "dark-maximus", вероятно Docker
    try:
        hostname = os.environ.get("HOSTNAME", "")
        if "dark-maximus" in hostname.lower():
            return True
    except Exception:
        pass
    
    return False


def _get_service_host(service_name: str) -> str:
    """
    Возвращает правильный хост для сервиса в зависимости от окружения.
    
    Args:
        service_name: Имя сервиса (docs-proxy, allure-homepage, webhook_server)
    
    Returns:
        Хост для подключения (localhost или имя Docker сервиса)
    """
    if _is_docker_environment():
        # Внутри Docker используем имена сервисов
        service_hosts = {
            "docs-proxy": "docs-proxy",
            "allure-homepage": "allure-homepage",
            "webhook_server": "bot",  # webhook_server запущен в контейнере bot
        }
        return service_hosts.get(service_name, "localhost")
    else:
        # На хосте используем localhost
        return "localhost"


@pytest.fixture
def service_configs():
    """Конфигурация всех сервисов с авторизацией"""
    docs_proxy_host = _get_service_host("docs-proxy")
    allure_homepage_host = _get_service_host("allure-homepage")
    webhook_server_host = _get_service_host("webhook_server")
    
    return {
        "docs-proxy": {
            "name": "docs-proxy",
            "port": 50001,
            "base_url": f"http://{docs_proxy_host}:50001",
            "login_url": f"http://{docs_proxy_host}:50001/login",
            "protected_url": f"http://{docs_proxy_host}:50001/",
        },
        "allure-homepage": {
            "name": "allure-homepage",
            "port": 50005,
            "base_url": f"http://{allure_homepage_host}:50005",
            "login_url": f"http://{allure_homepage_host}:50005/login",
            "protected_url": f"http://{allure_homepage_host}:50005/allure-docker-service/",
        },
        "webhook_server": {
            "name": "webhook_server",
            "port": 50000,
            "base_url": f"http://{webhook_server_host}:50000",
            "login_url": f"http://{webhook_server_host}:50000/login",
            "protected_url": f"http://{webhook_server_host}:50000/dashboard",
        },
    }


@pytest.fixture
def check_service_available(service_configs):
    """Проверяет доступность сервиса перед тестом"""
    def _check(service_name: str, timeout: int = 5) -> bool:
        """Проверяет доступность сервиса"""
        if service_name not in service_configs:
            return False
        
        config = service_configs[service_name]
        try:
            response = requests.get(config["login_url"], timeout=timeout)
            return response.status_code == 200
        except requests.exceptions.RequestException:
            return False
    
    return _check


@pytest.fixture
def service_client():
    """Создает HTTP клиент для работы с сервисами"""
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Dark-Maximus-Test-Client/1.0'
    })
    return session

