#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Интеграционные тесты для проверки CSP заголовков личного кабинета

Проверяет корректность Content Security Policy заголовков,
чтобы автоматически обнаруживать проблемы с невалидными wildcard паттернами.
"""

import pytest
import allure
import requests
import re
from typing import Dict, List, Optional


def _is_docker_environment() -> bool:
    """
    Определяет, запущены ли тесты внутри Docker контейнера.
    
    Returns:
        True если тесты запущены в Docker, False если на хосте
    """
    import os
    from pathlib import Path
    
    try:
        cgroup_path = Path("/proc/1/cgroup")
        if cgroup_path.exists():
            content = cgroup_path.read_text()
            return "docker" in content.lower()
    except Exception:
        pass
    
    try:
        hostname = os.environ.get("HOSTNAME", "")
        if "dark-maximus" in hostname.lower():
            return True
    except Exception:
        pass
    
    return False


def _get_user_cabinet_host() -> str:
    """
    Возвращает правильный хост для личного кабинета в зависимости от окружения.
    
    Returns:
        Хост для подключения (localhost или имя Docker сервиса)
    """
    if _is_docker_environment():
        return "user-cabinet"
    else:
        return "localhost"


@pytest.fixture
def user_cabinet_config():
    """Конфигурация личного кабинета"""
    host = _get_user_cabinet_host()
    return {
        "name": "user-cabinet",
        "port": 50003,
        "base_url": f"http://{host}:50003",
        "health_url": f"http://{host}:50003/health",
    }


@pytest.fixture
def check_user_cabinet_available(user_cabinet_config):
    """Проверяет доступность личного кабинета перед тестом"""
    def _check(timeout: int = 5) -> bool:
        """Проверяет доступность личного кабинета"""
        try:
            response = requests.get(user_cabinet_config["health_url"], timeout=timeout)
            return response.status_code == 200
        except requests.exceptions.RequestException:
            return False
    
    return _check


def parse_csp_directive(csp_header: str, directive: str) -> List[str]:
    """
    Парсит CSP заголовок и извлекает источники для указанной директивы.
    
    Args:
        csp_header: Значение заголовка Content-Security-Policy
        directive: Название директивы (например, 'frame-src', 'connect-src')
    
    Returns:
        Список источников для директивы
    """
    # Ищем директиву в CSP заголовке
    pattern = rf"{directive}\s+([^;]+)"
    match = re.search(pattern, csp_header)
    
    if not match:
        return []
    
    # Разбиваем источники по пробелам
    sources_str = match.group(1).strip()
    sources = [s.strip() for s in sources_str.split() if s.strip()]
    
    return sources


def has_invalid_wildcard_pattern(source: str) -> bool:
    """
    Проверяет, содержит ли источник невалидный wildcard паттерн.
    
    CSP не поддерживает wildcard в середине домена (например, serv*.domain.com).
    Поддерживается только wildcard в начале поддомена (например, *.domain.com).
    
    Args:
        source: Источник из CSP директивы
    
    Returns:
        True если паттерн невалидный, False если валидный
    """
    # Проверяем паттерны типа serv*.domain.com (невалидный)
    # Валидные паттерны: *.domain.com, https://*.domain.com
    invalid_pattern = re.search(r'[a-zA-Z0-9-]+\*[a-zA-Z0-9-]+', source)
    return invalid_pattern is not None


@allure.epic("Интеграционные тесты")
@allure.feature("Личный кабинет")
@allure.label("package", "tests.integration.test_user_cabinet")
@pytest.mark.integration
class TestCSPHeaders:
    """Тесты проверки CSP заголовков личного кабинета"""
    
    @allure.story("Проверка корректности CSP заголовков")
    @allure.title("Проверка отсутствия невалидных wildcard паттернов в CSP")
    @allure.description("""
    Проверяет, что CSP заголовки личного кабинета не содержат невалидных wildcard паттернов,
    которые вызывают ошибку ERR_BLOCKED_BY_CSP при загрузке subscription links в iframe.
    
    **Что проверяется:**
    - Наличие заголовка Content-Security-Policy
    - Отсутствие невалидных wildcard паттернов типа `serv*.domain.com` в директивах `frame-src` и `connect-src`
    - Наличие валидных wildcard паттернов типа `*.domain.com` для разрешения всех поддоменов
    - Корректность директив `frame-src` и `connect-src` для загрузки subscription links
    
    **Тестовые данные:**
    - Сервис: user-cabinet (порт 50003)
    - Проверяемые директивы: `frame-src`, `connect-src`
    
    **Критичность:**
    Невалидные wildcard паттерны в CSP вызывают ошибку ERR_BLOCKED_BY_CSP в браузере,
    что блокирует загрузку subscription links (например, https://serv1.dark-maximus.com/subs/...)
    в iframe на вкладке "Подключение" личного кабинета.
    
    **Ожидаемый результат:**
    CSP заголовки содержат только валидные паттерны, все поддомены разрешены через `*.domain.com`.
    """)
    @allure.severity(allure.severity_level.CRITICAL)
    @allure.tag("csp", "security", "headers", "cabinet", "integration", "critical", "wildcard", "iframe")
    def test_csp_no_invalid_wildcard_patterns(
        self,
        user_cabinet_config: Dict,
        check_user_cabinet_available,
    ):
        """Проверяет отсутствие невалидных wildcard паттернов в CSP заголовках"""
        
        if not check_user_cabinet_available():
            pytest.skip("Личный кабинет недоступен")
        
        with allure.step("Выполнение HTTP запроса к личному кабинету"):
            try:
                # Используем /health endpoint, так как он не требует токена
                # CSP заголовки устанавливаются в nginx с флагом 'always', поэтому доступны для всех ответов
                response = requests.get(
                    user_cabinet_config["health_url"],
                    allow_redirects=True,
                    timeout=10
                )
                assert response.status_code == 200, \
                    f"Ожидался статус 200, получен {response.status_code}"
            except requests.exceptions.RequestException as e:
                pytest.fail(f"Ошибка при запросе к личному кабинету: {e}")
        
        with allure.step("Проверка наличия заголовка Content-Security-Policy"):
            csp_header = response.headers.get("Content-Security-Policy")
            assert csp_header is not None, \
                "Заголовок Content-Security-Policy отсутствует в ответе"
            
            allure.attach(
                csp_header,
                "Content-Security-Policy заголовок",
                allure.attachment_type.TEXT
            )
        
        with allure.step("Проверка директивы frame-src"):
            frame_src_sources = parse_csp_directive(csp_header, "frame-src")
            assert len(frame_src_sources) > 0, \
                "Директива frame-src отсутствует в CSP заголовке"
            
            # Проверяем наличие невалидных wildcard паттернов
            invalid_patterns = [
                source for source in frame_src_sources
                if has_invalid_wildcard_pattern(source)
            ]
            
            assert len(invalid_patterns) == 0, \
                f"Найдены невалидные wildcard паттерны в frame-src: {invalid_patterns}. " \
                f"CSP не поддерживает wildcard в середине домена (например, serv*.domain.com). " \
                f"Используйте валидный паттерн *.domain.com для разрешения всех поддоменов."
            
            # Проверяем наличие валидного wildcard паттерна для поддоменов
            has_valid_wildcard = any(
                re.search(r'\*\.', source) for source in frame_src_sources
            )
            
            allure.attach(
                f"Директива: frame-src\n"
                f"Источники: {frame_src_sources}\n"
                f"Валидный wildcard для поддоменов: {has_valid_wildcard}",
                "frame-src источники",
                allure.attachment_type.TEXT
            )
        
        with allure.step("Проверка директивы connect-src"):
            connect_src_sources = parse_csp_directive(csp_header, "connect-src")
            assert len(connect_src_sources) > 0, \
                "Директива connect-src отсутствует в CSP заголовке"
            
            # Проверяем наличие невалидных wildcard паттернов
            invalid_patterns = [
                source for source in connect_src_sources
                if has_invalid_wildcard_pattern(source)
            ]
            
            assert len(invalid_patterns) == 0, \
                f"Найдены невалидные wildcard паттерны в connect-src: {invalid_patterns}. " \
                f"CSP не поддерживает wildcard в середине домена (например, serv*.domain.com). " \
                f"Используйте валидный паттерн *.domain.com для разрешения всех поддоменов."
            
            # Проверяем наличие валидного wildcard паттерна для поддоменов
            has_valid_wildcard = any(
                re.search(r'\*\.', source) for source in connect_src_sources
            )
            
            allure.attach(
                f"Директива: connect-src\n"
                f"Источники: {connect_src_sources}\n"
                f"Валидный wildcard для поддоменов: {has_valid_wildcard}",
                "connect-src источники",
                allure.attachment_type.TEXT
            )
        
        with allure.step("Проверка полного CSP заголовка"):
            # Проверяем, что заголовок не содержит очевидных ошибок
            assert "serv*" not in csp_header.lower(), \
                f"Найден невалидный паттерн 'serv*' в CSP заголовке. " \
                f"Используйте валидный паттерн '*.domain.com' вместо 'serv*.domain.com'."
            
            allure.attach(
                f"Полный CSP заголовок:\n{csp_header}\n\n"
                f"Проверка завершена успешно: невалидные wildcard паттерны не найдены.",
                "Результат проверки CSP",
                allure.attachment_type.TEXT
            )
    
    @allure.story("Проверка разрешения поддоменов в CSP")
    @allure.title("Проверка наличия валидного wildcard паттерна для поддоменов")
    @allure.description("""
    Проверяет, что CSP заголовки содержат валидный wildcard паттерн для разрешения всех поддоменов,
    что необходимо для загрузки subscription links с различных серверов (serv1, serv2, serv3 и т.д.).
    
    **Что проверяется:**
    - Наличие валидного wildcard паттерна `*.domain.com` в директивах `frame-src` и `connect-src`
    - Возможность загрузки subscription links с любых поддоменов (serv1, serv2, serv3 и т.д.)
    
    **Тестовые данные:**
    - Сервис: user-cabinet (порт 50003)
    - Ожидаемый паттерн: `*.dark-maximus.com` или `https://*.dark-maximus.com`
    
    **Важно:**
    Тест обращается напрямую к Flask приложению (минуя nginx), поэтому проверяет CSP заголовки,
    установленные Flask приложением. Flask приложение использует разные CSP заголовки в зависимости
    от настройки `server_environment` в БД:
    - Если `server_environment = 'development'`: `frame-src` НЕ содержит wildcard паттерн
    - Если `server_environment = 'production'`: `frame-src` содержит wildcard паттерн
    
    **Критичность:**
    Отсутствие валидного wildcard паттерна приведет к блокировке загрузки subscription links
    с поддоменов, которые не указаны явно в CSP.
    
    **Ожидаемый результат:**
    CSP заголовки содержат валидный wildcard паттерн для разрешения всех поддоменов.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("csp", "security", "headers", "cabinet", "integration", "wildcard", "subdomains")
    def test_csp_has_valid_wildcard_for_subdomains(
        self,
        user_cabinet_config: Dict,
        check_user_cabinet_available,
    ):
        """Проверяет наличие валидного wildcard паттерна для поддоменов"""
        
        if not check_user_cabinet_available():
            pytest.skip("Личный кабинет недоступен")
        
        # Проверяем режим сервера для диагностики
        try:
            from shop_bot.data_manager.database import is_development_server, get_server_environment
            is_dev = is_development_server()
            server_env = get_server_environment()
            
            allure.attach(
                f"Режим сервера: {server_env}\n"
                f"is_development_server(): {is_dev}\n"
                f"Примечание: В development режиме frame-src не содержит wildcard паттерн",
                "Диагностика: Режим сервера",
                allure.attachment_type.TEXT
            )
        except Exception as e:
            allure.attach(
                f"Не удалось проверить режим сервера: {e}",
                "Диагностика: Ошибка проверки режима",
                allure.attachment_type.TEXT
            )
        
        with allure.step("Выполнение HTTP запроса к личному кабинету"):
            try:
                # Используем /health endpoint, так как он не требует токена
                # ВАЖНО: Тест обращается напрямую к Flask приложению (минуя nginx)
                # Flask приложение устанавливает CSP заголовки в зависимости от server_environment
                response = requests.get(
                    user_cabinet_config["health_url"],
                    allow_redirects=True,
                    timeout=10
                )
                assert response.status_code == 200, \
                    f"Ожидался статус 200, получен {response.status_code}"
            except requests.exceptions.RequestException as e:
                pytest.fail(f"Ошибка при запросе к личному кабинету: {e}")
        
        with allure.step("Проверка наличия заголовка Content-Security-Policy"):
            csp_header = response.headers.get("Content-Security-Policy")
            assert csp_header is not None, \
                "Заголовок Content-Security-Policy отсутствует в ответе"
            
            allure.attach(
                csp_header,
                "Content-Security-Policy заголовок",
                allure.attachment_type.TEXT
            )
        
        with allure.step("Проверка валидного wildcard паттерна в frame-src"):
            frame_src_sources = parse_csp_directive(csp_header, "frame-src")
            assert len(frame_src_sources) > 0, \
                "Директива frame-src отсутствует в CSP заголовке"
            
            # Ищем валидный wildcard паттерн (например, *.domain.com или https://*.domain.com)
            valid_wildcard_pattern = re.compile(r'https?://\*\.|^\*\.', re.IGNORECASE)
            has_wildcard = any(
                valid_wildcard_pattern.search(source) for source in frame_src_sources
            )
            
            # Формируем диагностическое сообщение
            diagnostic_info = (
                f"Найденные источники frame-src: {frame_src_sources}\n"
                f"Wildcard паттерн найден: {has_wildcard}\n\n"
            )
            
            # Проверяем режим сервера для более информативного сообщения об ошибке
            try:
                from shop_bot.data_manager.database import is_development_server, get_server_environment
                is_dev = is_development_server()
                server_env = get_server_environment()
                
                if is_dev and not has_wildcard:
                    diagnostic_info += (
                        f"ПРОБЛЕМА: server_environment установлен в 'development'\n"
                        f"В development режиме Flask приложение использует frame-src без wildcard паттерна.\n"
                        f"РЕШЕНИЕ: Установите server_environment = 'production' через веб-панель\n"
                        f"(/settings → Глобальные параметры → Тип сервера)\n"
                        f"Затем перезапустите user-cabinet контейнер: docker compose restart user-cabinet"
                    )
            except Exception:
                pass
            
            assert has_wildcard, \
                f"Валидный wildcard паттерн для поддоменов не найден в frame-src.\n" \
                f"{diagnostic_info}\n" \
                f"Ожидается паттерн типа '*.domain.com' или 'https://*.domain.com' для разрешения всех поддоменов."
            
            allure.attach(
                f"Директива: frame-src\n"
                f"Источники: {frame_src_sources}\n"
                f"Валидный wildcard паттерн найден: ✓",
                "frame-src источники",
                allure.attachment_type.TEXT
            )
        
        with allure.step("Проверка валидного wildcard паттерна в connect-src"):
            connect_src_sources = parse_csp_directive(csp_header, "connect-src")
            assert len(connect_src_sources) > 0, \
                "Директива connect-src отсутствует в CSP заголовке"
            
            # Ищем валидный wildcard паттерн
            valid_wildcard_pattern = re.compile(r'https?://\*\.|^\*\.', re.IGNORECASE)
            has_wildcard = any(
                valid_wildcard_pattern.search(source) for source in connect_src_sources
            )
            
            assert has_wildcard, \
                f"Валидный wildcard паттерн для поддоменов не найден в connect-src. " \
                f"Найденные источники: {connect_src_sources}. " \
                f"Ожидается паттерн типа '*.domain.com' или 'https://*.domain.com' для разрешения всех поддоменов."
            
            allure.attach(
                f"Директива: connect-src\n"
                f"Источники: {connect_src_sources}\n"
                f"Валидный wildcard паттерн найден: ✓",
                "connect-src источники",
                allure.attachment_type.TEXT
            )

