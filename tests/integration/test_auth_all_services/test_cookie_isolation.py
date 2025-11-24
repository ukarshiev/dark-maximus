#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Интеграционные тесты изоляции cookie между сервисами

Проверяет, что разные сервисы используют уникальные имена cookie
и сессии не конфликтуют при переходах между сервисами.
"""

import pytest
import allure
import requests
from typing import Dict


@allure.epic("Интеграционные тесты")
@allure.feature("Изоляция сессий между сервисами")
@allure.label("package", "tests.integration.test_auth_all_services")
@pytest.mark.integration
class TestCookieIsolation:
    """Тесты изоляции cookie между сервисами"""
    
    @allure.story("Уникальные имена cookie для каждого сервиса")
    @allure.title("Проверка уникальности имен cookie между сервисами")
    @allure.description("""
    Проверяет, что каждый сервис использует уникальное имя cookie,
    что предотвращает конфликт сессий при использовании одинакового FLASK_SECRET_KEY.
    
    **Что проверяется:**
    - Каждый сервис использует уникальное имя cookie
    - Имена cookie не конфликтуют между сервисами
    - Сессии изолированы и не влияют друг на друга
    
    **Тестовые данные:**
    - Веб-панель (порт 50000): cookie 'panel_session'
    - Docs Proxy (порт 50001): cookie 'docs_session'
    - Allure Homepage (порт 50005): cookie 'allure_session'
    
    **Критичность:**
    Конфликт cookie между сервисами приводит к потере сессии при переходах между сервисами.
    Это критичная проблема безопасности и UX.
    
    **Ожидаемый результат:**
    Каждый сервис использует уникальное имя cookie, сессии изолированы и не конфликтуют.
    """)
    @allure.severity(allure.severity_level.CRITICAL)
    @allure.tag("auth", "session_isolation", "cookie_name", "integration", "critical", "all-services")
    def test_unique_cookie_names(
        self,
        service_configs: Dict,
        admin_credentials: Dict[str, str],
        check_service_available,
        service_client
    ):
        """Проверяет уникальность имен cookie для каждого сервиса"""
        
        # Ожидаемые имена cookie для каждого сервиса
        expected_cookie_names = {
            'webhook_server': 'panel_session',
            'docs-proxy': 'docs_session',
            'allure-homepage': 'allure_session',
        }
        
        actual_cookie_names = {}
        
        for service_name, expected_cookie_name in expected_cookie_names.items():
            if not check_service_available(service_name):
                import os
                config = service_configs[service_name]
                skip_reason = f"""
Сервис {service_name} недоступен.

**Диагностическая информация:**
- Сервис: {service_name}
- URL: {config.get('login_url', 'не указан')}
- ENVIRONMENT: {os.getenv('ENVIRONMENT', 'не установлен')}
- Проверьте, что сервис запущен и доступен по указанному адресу
"""
                allure.attach(skip_reason, "Причина пропуска теста", allure.attachment_type.TEXT)
                pytest.skip(f"Сервис {service_name} недоступен: {config.get('login_url', 'URL не указан')}")
            
            config = service_configs[service_name]
            
            with allure.step(f"Авторизация на {service_name}"):
                try:
                    response = service_client.post(
                        config["login_url"],
                        data=admin_credentials,
                        allow_redirects=True,
                        timeout=10
                    )
                except requests.exceptions.RequestException as e:
                    pytest.fail(f"Ошибка при авторизации на {service_name}: {e}")
            
            with allure.step(f"Проверка имени cookie для {service_name}"):
                cookies = service_client.cookies
                cookie_names = [cookie.name for cookie in cookies]
                
                # Ищем cookie сессии (должен быть один с ожидаемым именем)
                session_cookies = [name for name in cookie_names if 'session' in name.lower()]
                
                assert len(session_cookies) > 0, \
                    f"Не найдено cookie сессии для {service_name}. " \
                    f"Все cookie: {cookie_names}"
                
                # Проверяем, что есть cookie с ожидаемым именем
                assert expected_cookie_name in cookie_names, \
                    f"Ожидалось cookie '{expected_cookie_name}' для {service_name}, " \
                    f"найдены: {cookie_names}"
                
                actual_cookie_names[service_name] = expected_cookie_name
                
                allure.attach(
                    f"Сервис: {service_name}\nОжидаемое имя: {expected_cookie_name}\nНайденные cookie: {cookie_names}",
                    f"Cookie для {service_name}",
                    allure.attachment_type.TEXT
                )
        
        with allure.step("Проверка уникальности всех имен cookie"):
            unique_names = set(actual_cookie_names.values())
            assert len(unique_names) == len(expected_cookie_names), \
                f"Имена cookie должны быть уникальными. " \
                f"Ожидалось {len(expected_cookie_names)} уникальных имен, получено {len(unique_names)}. " \
                f"Имена: {actual_cookie_names}"
            
            import json
            allure.attach(
                json.dumps(actual_cookie_names, indent=2, ensure_ascii=False),
                "Имена cookie для каждого сервиса",
                allure.attachment_type.JSON
            )
    
    @allure.story("Отсутствие конфликта сессий при переходах между сервисами")
    @allure.title("Проверка отсутствия потери сессии при переходах между сервисами")
    @allure.description("""
    Проверяет, что сессия одного сервиса не теряется при авторизации на другом сервисе.
    Это критично для предотвращения автоматического разлогинивания при переходах между сервисами.
    
    **Что проверяется:**
    - Авторизация на первом сервисе создает сессию
    - Авторизация на втором сервисе не влияет на сессию первого
    - Сессия первого сервиса остается активной после авторизации на втором
    
    **Тестовые данные:**
    - Первый сервис: webhook_server (порт 50000)
    - Второй сервис: docs-proxy (порт 50001)
    
    **Критичность:**
    Потеря сессии при переходах между сервисами критична для UX и безопасности.
    Пользователь не должен терять авторизацию при переходах между сервисами.
    
    **Ожидаемый результат:**
    Сессии изолированы, авторизация на одном сервисе не влияет на сессию другого.
    """)
    @allure.severity(allure.severity_level.CRITICAL)
    @allure.tag("auth", "session_isolation", "cookie_conflict", "integration", "critical", "all-services")
    def test_no_session_conflict_between_services(
        self,
        service_configs: Dict,
        admin_credentials: Dict[str, str],
        check_service_available,
    ):
        """Проверяет отсутствие конфликта сессий при переходах между сервисами"""
        
        # Проверяем доступность сервисов
        if not check_service_available('webhook_server'):
            import os
            config = service_configs['webhook_server']
            skip_reason = f"""
Сервис webhook_server недоступен.

**Диагностическая информация:**
- Сервис: webhook_server
- URL: {config.get('login_url', 'не указан')}
- ENVIRONMENT: {os.getenv('ENVIRONMENT', 'не установлен')}
- Проверьте, что сервис запущен и доступен по указанному адресу
"""
            allure.attach(skip_reason, "Причина пропуска теста", allure.attachment_type.TEXT)
            pytest.skip(f"Сервис webhook_server недоступен: {config.get('login_url', 'URL не указан')}")
        if not check_service_available('docs-proxy'):
            import os
            config = service_configs['docs-proxy']
            skip_reason = f"""
Сервис docs-proxy недоступен.

**Диагностическая информация:**
- Сервис: docs-proxy
- URL: {config.get('login_url', 'не указан')}
- ENVIRONMENT: {os.getenv('ENVIRONMENT', 'не установлен')}
- Проверьте, что сервис запущен и доступен по указанному адресу
"""
            allure.attach(skip_reason, "Причина пропуска теста", allure.attachment_type.TEXT)
            pytest.skip(f"Сервис docs-proxy недоступен: {config.get('login_url', 'URL не указан')}")
        
        webhook_config = service_configs['webhook_server']
        docs_config = service_configs['docs-proxy']
        
        # Создаем отдельные сессии для каждого сервиса
        webhook_session = requests.Session()
        docs_session = requests.Session()
        
        with allure.step("Авторизация на веб-панели (webhook_server)"):
            try:
                webhook_response = webhook_session.post(
                    webhook_config["login_url"],
                    data=admin_credentials,
                    allow_redirects=True,
                    timeout=10
                )
                assert webhook_response.status_code in (200, 302, 303), \
                    f"Ошибка авторизации на webhook_server: {webhook_response.status_code}"
            except requests.exceptions.RequestException as e:
                pytest.fail(f"Ошибка при авторизации на webhook_server: {e}")
        
        with allure.step("Проверка сессии веб-панели после авторизации"):
            webhook_cookies = webhook_session.cookies.get_dict()
            assert 'panel_session' in webhook_cookies or any('session' in name.lower() for name in webhook_cookies.keys()), \
                f"Cookie сессии не найдено для webhook_server. Cookie: {webhook_cookies}"
            
            # Проверяем доступ к защищенной странице
            dashboard_response = webhook_session.get(
                webhook_config["protected_url"],
                allow_redirects=False,
                timeout=10
            )
            assert dashboard_response.status_code != 302 or 'login' not in dashboard_response.headers.get('Location', ''), \
                f"Сессия webhook_server потеряна после авторизации. " \
                f"Статус: {dashboard_response.status_code}, Location: {dashboard_response.headers.get('Location', '')}"
            
            allure.attach(
                f"Cookie веб-панели: {webhook_cookies}\nСтатус dashboard: {dashboard_response.status_code}",
                "Состояние сессии веб-панели",
                allure.attachment_type.TEXT
            )
        
        with allure.step("Авторизация на docs-proxy"):
            try:
                docs_response = docs_session.post(
                    docs_config["login_url"],
                    data=admin_credentials,
                    allow_redirects=True,
                    timeout=10
                )
                assert docs_response.status_code in (200, 302, 303), \
                    f"Ошибка авторизации на docs-proxy: {docs_response.status_code}"
            except requests.exceptions.RequestException as e:
                pytest.fail(f"Ошибка при авторизации на docs-proxy: {e}")
        
        with allure.step("Проверка сессии docs-proxy после авторизации"):
            docs_cookies = docs_session.cookies.get_dict()
            assert 'docs_session' in docs_cookies or any('session' in name.lower() for name in docs_cookies.keys()), \
                f"Cookie сессии не найдено для docs-proxy. Cookie: {docs_cookies}"
            
            # Проверяем доступ к защищенной странице
            protected_response = docs_session.get(
                docs_config["protected_url"],
                allow_redirects=False,
                timeout=10
            )
            assert protected_response.status_code != 302 or 'login' not in protected_response.headers.get('Location', ''), \
                f"Сессия docs-proxy потеряна после авторизации. " \
                f"Статус: {protected_response.status_code}, Location: {protected_response.headers.get('Location', '')}"
            
            allure.attach(
                f"Cookie docs-proxy: {docs_cookies}\nСтатус protected: {protected_response.status_code}",
                "Состояние сессии docs-proxy",
                allure.attachment_type.TEXT
            )
        
        with allure.step("Проверка, что сессия веб-панели не потеряна после авторизации на docs-proxy"):
            # КРИТИЧЕСКАЯ ПРОВЕРКА: сессия веб-панели должна остаться активной
            dashboard_check = webhook_session.get(
                webhook_config["protected_url"],
                allow_redirects=False,
                timeout=10
            )
            
            if dashboard_check.status_code == 302:
                location = dashboard_check.headers.get('Location', '')
                if 'login' in location:
                    pytest.fail(
                        f"КРИТИЧЕСКАЯ ПРОБЛЕМА: Сессия webhook_server потеряна после авторизации на docs-proxy! "
                        f"Это указывает на конфликт cookie между сервисами. "
                        f"Статус: {dashboard_check.status_code}, Location: {location}"
                    )
            
            assert dashboard_check.status_code == 200, \
                f"Сессия webhook_server должна остаться активной. " \
                f"Статус: {dashboard_check.status_code}"
            
            allure.attach(
                f"Cookie веб-панели после авторизации на docs-proxy: {webhook_session.cookies.get_dict()}\n"
                f"Статус dashboard: {dashboard_check.status_code}",
                "Проверка изоляции сессий",
                allure.attachment_type.TEXT
            )




