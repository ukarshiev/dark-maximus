#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Фикстуры для интеграционных тестов авторизации всех сервисов
"""

import pytest
import requests
import time
import os
import sys
import sqlite3
from pathlib import Path
from typing import Dict, Tuple, Optional
from urllib.parse import urlparse


def _is_production_environment() -> bool:
    """
    Проверяет, запущен ли тест в продакшн окружении.
    Сначала проверяет переменную окружения ENVIRONMENT, затем server_environment из БД.
    
    Returns:
        True если ENVIRONMENT=production или server_environment=production в БД
    """
    import logging
    logger = logging.getLogger(__name__)
    
    # Сначала проверяем переменную окружения
    env = os.getenv("ENVIRONMENT", "").strip().lower()
    # Обрабатываем случай, когда в .env файле комментарий в той же строке
    # Например: "ENVIRONMENT=production - комментарий"
    if " " in env:
        env = env.split()[0]  # Берем только первое слово до пробела
    
    logger.debug(f"ENVIRONMENT из переменных окружения: '{env}'")
    
    if env == "production":
        logger.debug("Определено как production по ENVIRONMENT")
        return True
    if env == "development":
        logger.debug("Определено как development по ENVIRONMENT")
        return False
    
    # Если ENVIRONMENT не установлен, проверяем server_environment из БД
    # Это важно для случаев, когда тесты запускаются на сервере с настройкой в БД
    server_env = _get_setting_from_db("server_environment")
    logger.debug(f"server_environment из БД: '{server_env}'")
    
    if server_env:
        server_env_lower = server_env.strip().lower()
        is_prod = server_env_lower == "production"
        logger.debug(f"Определено как {'production' if is_prod else 'development'} по server_environment из БД")
        return is_prod
    
    # По умолчанию считаем development для безопасности
    logger.debug("Не удалось определить окружение, используем development по умолчанию")
    return False


def _is_docker_environment() -> bool:
    """
    Определяет, запущены ли тесты внутри Docker контейнера.
    
    Проверяет наличие файла /.dockerenv, который создается Docker автоматически
    во всех контейнерах и является стандартным способом определения Docker окружения.
    
    Также проверяет /proc/1/cgroup как fallback для старых версий Docker
    и HOSTNAME как дополнительный fallback.
    
    Returns:
        True если тесты запущены в Docker, False если на хосте
    """
    # Основной способ: проверка файла /.dockerenv (стандартный способ Docker)
    try:
        dockerenv_path = Path("/.dockerenv")
        if dockerenv_path.exists():
            return True
    except Exception:
        pass
    
    # Fallback 1: проверка /proc/1/cgroup (для старых версий Docker с cgroup v1)
    try:
        cgroup_path = Path("/proc/1/cgroup")
        if cgroup_path.exists():
            content = cgroup_path.read_text()
            if "docker" in content.lower():
                return True
    except Exception:
        pass
    
    # Fallback 2: проверка hostname (если содержит "dark-maximus", вероятно Docker)
    try:
        hostname = os.environ.get("HOSTNAME", "")
        if "dark-maximus" in hostname.lower():
            return True
    except Exception:
        pass
    
    return False


def _get_setting_from_db(setting_key: str, db_path: Optional[Path] = None) -> Optional[str]:
    """
    Получает значение настройки из БД.
    
    Args:
        setting_key: Ключ настройки в таблице bot_settings
        db_path: Путь к БД (если None, используется users.db из корня проекта)
    
    Returns:
        Значение настройки или None если не найдено
    """
    if db_path is None:
        project_root = Path(__file__).parent.parent.parent.parent
        db_path = project_root / "users.db"
    
    if not db_path.exists():
        return None
    
    try:
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM bot_settings WHERE key = ?", (setting_key,))
        result = cursor.fetchone()
        conn.close()
        
        if result and result[0]:
            return result[0].strip()
    except Exception:
        pass
    
    return None


def _extract_domain_from_url(url: str) -> str:
    """
    Извлекает домен из URL (убирает протокол и путь).
    
    Args:
        url: URL (может быть с протоколом или без)
    
    Returns:
        Домен без протокола и пути
    """
    if not url:
        return ""
    
    # Убираем протокол
    url = url.replace("https://", "").replace("http://", "")
    # Убираем путь (всё после первого /)
    url = url.split("/")[0]
    # Убираем порт (если есть)
    url = url.split(":")[0]
    
    return url


def _get_service_host(service_name: str) -> str:
    """
    Возвращает правильный хост для сервиса в зависимости от окружения.
    
    Логика определения хоста:
    - Если ENVIRONMENT=production и домены найдены в БД, используем домены
      (на продакшне сервисы доступны через домены, например panel.dark-maximus.com)
    - Если ENVIRONMENT=production, но домены не найдены в БД, и мы в Docker - используем имена сервисов
    - Если ENVIRONMENT=development и тесты в Docker, используем имена сервисов
    - Если ENVIRONMENT=development и тесты на хосте, используем localhost
    
    Args:
        service_name: Имя сервиса (docs-proxy, allure-homepage, webhook_server)
    
    Returns:
        Хост для подключения (домен, localhost или имя Docker сервиса)
    """
    # Маппинг сервисов на ключи настроек в БД
    service_settings = {
        "docs-proxy": "docs_domain",
        "allure-homepage": "allure_domain",
        "webhook_server": "global_domain",
    }
    
    # ИСПРАВЛЕНИЕ: Всегда сначала проверяем, доступны ли домены из БД
    # Если домены недоступны или мы в Docker - используем имена Docker сервисов
    is_prod = _is_production_environment()
    is_docker = _is_docker_environment()
    
    # Маппинг имен Docker сервисов
    docker_service_hosts = {
        "docs-proxy": "docs-proxy",
        "allure-homepage": "allure-homepage",
        "webhook_server": "bot",
    }
    
    # Если мы в Docker, всегда используем имена Docker сервисов для внутренней связи
    # Домены из БД используются только на реальном production сервере вне Docker
    if is_docker:
        return docker_service_hosts.get(service_name, "localhost")
    
    # Если не в Docker и это production - пытаемся использовать домены из БД
    if is_prod:
        setting_key = service_settings.get(service_name)
        if setting_key:
            # Пытаемся получить домен из БД
            domain = _get_setting_from_db(setting_key)
            if domain:
                host = _extract_domain_from_url(domain)
                if host and host != "localhost":
                    return host
            
            # Если для allure-homepage не найден allure_domain, пробуем global_domain
            if service_name == "allure-homepage":
                global_domain = _get_setting_from_db("global_domain")
                if global_domain:
                    base_domain = _extract_domain_from_url(global_domain)
                    if base_domain and base_domain != "localhost" and not base_domain.startswith("allure."):
                        if "." in base_domain:
                            parts = base_domain.split(".")
                            if len(parts) >= 2:
                                main_domain = ".".join(parts[-2:])
                                return f"allure.{main_domain}"
                        return f"allure.{base_domain}"
            
            # Если для webhook_server не найден global_domain, пробуем извлечь из panel поддомена
            if service_name == "webhook_server":
                docs_domain = _get_setting_from_db("docs_domain")
                if docs_domain:
                    base_domain = _extract_domain_from_url(docs_domain)
                    if base_domain and base_domain != "localhost" and "." in base_domain:
                        parts = base_domain.split(".")
                        if len(parts) >= 2:
                            main_domain = ".".join(parts[-2:])
                            return f"panel.{main_domain}"
        
        # Если домены не найдены - используем localhost как fallback
        return "localhost"
    
    # Для development окружения на хосте используем localhost
    return "localhost"
    
    # Для development окружения
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
    """
    Конфигурация всех сервисов с авторизацией.
    
    На продакшне использует домены из БД (https://domain.com).
    На development использует localhost или имена Docker сервисов.
    """
    docs_proxy_host = _get_service_host("docs-proxy")
    allure_homepage_host = _get_service_host("allure-homepage")
    webhook_server_host = _get_service_host("webhook_server")
    
    # Определяем протокол и порт в зависимости от окружения
    is_prod = _is_production_environment()
    is_docker = _is_docker_environment()
    
    # ИСПРАВЛЕНИЕ: Используем https только если это реальный домен (не localhost и не имя Docker сервиса)
    # Если используется имя Docker сервиса (docs-proxy, allure-homepage, bot) - всегда http
    docker_service_names = {"docs-proxy", "allure-homepage", "bot", "localhost"}
    use_https = is_prod and docs_proxy_host not in docker_service_names and allure_homepage_host not in docker_service_names and webhook_server_host not in docker_service_names
    protocol = "https" if use_https else "http"
    
    # На продакшне с реальными доменами порты не нужны (стандартные порты 80/443)
    # На development или при использовании Docker сервисов используем порты из docker-compose.yml
    def get_url(host: str, port: int, path: str = "") -> str:
        """Формирует URL в зависимости от окружения"""
        if use_https and host not in docker_service_names:
            # На продакшне с реальными доменами используем домен без порта (стандартные порты 80/443)
            return f"{protocol}://{host}{path}"
        else:
            # На development или при использовании Docker сервисов используем порт
            return f"{protocol}://{host}:{port}{path}"
    
    return {
        "docs-proxy": {
            "name": "docs-proxy",
            "port": 50001,
            "base_url": get_url(docs_proxy_host, 50001),
            "login_url": get_url(docs_proxy_host, 50001, "/login"),
            "protected_url": get_url(docs_proxy_host, 50001, "/"),
        },
        "allure-homepage": {
            "name": "allure-homepage",
            "port": 50005,
            "base_url": get_url(allure_homepage_host, 50005),
            "login_url": get_url(allure_homepage_host, 50005, "/login"),
            "protected_url": get_url(allure_homepage_host, 50005, "/allure-docker-service/"),
        },
        "webhook_server": {
            "name": "webhook_server",
            "port": 50000,
            "base_url": get_url(webhook_server_host, 50000),
            "login_url": get_url(webhook_server_host, 50000, "/login"),
            "protected_url": get_url(webhook_server_host, 50000, "/dashboard"),
        },
    }


@pytest.fixture
def check_service_available(service_configs):
    """Проверяет доступность сервиса перед тестом"""
    def _check(service_name: str, timeout: int = 5) -> bool:
        """
        Проверяет доступность сервиса.
        
        Args:
            service_name: Имя сервиса для проверки
            timeout: Таймаут запроса в секундах
        
        Returns:
            True если сервис доступен, False в противном случае
        """
        import logging
        logger = logging.getLogger(__name__)
        
        if service_name not in service_configs:
            logger.warning(f"⚠️ Сервис {service_name} не найден в конфигурации")
            return False
        
        config = service_configs[service_name]
        login_url = config["login_url"]
        
        # Логируем информацию о попытке подключения
        env_info = {
            "ENVIRONMENT": os.getenv("ENVIRONMENT", "не установлен"),
            "is_docker": _is_docker_environment(),
            "is_production": _is_production_environment(),
            "service_name": service_name,
            "login_url": login_url,
        }
        logger.info(f"🔍 Проверка доступности сервиса {service_name}: {login_url}")
        logger.debug(f"   Окружение: {env_info}")
        
        try:
            response = requests.get(login_url, timeout=timeout)
            is_available = response.status_code == 200
            if is_available:
                logger.info(f"✅ Сервис {service_name} доступен (статус: {response.status_code})")
            else:
                logger.warning(
                    f"⚠️ Сервис {service_name} недоступен: "
                    f"статус {response.status_code}, URL: {login_url}"
                )
            return is_available
        except requests.exceptions.Timeout:
            logger.warning(
                f"⏱️ Таймаут при проверке сервиса {service_name}: "
                f"URL {login_url} не ответил за {timeout} секунд"
            )
            return False
        except requests.exceptions.ConnectionError as e:
            logger.warning(
                f"🔌 Ошибка подключения к сервису {service_name}: "
                f"не удалось подключиться к {login_url}. Ошибка: {e}"
            )
            return False
        except requests.exceptions.RequestException as e:
            logger.warning(
                f"❌ Ошибка при проверке сервиса {service_name}: "
                f"URL {login_url}, ошибка: {e}"
            )
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

