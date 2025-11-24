#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Тесты проверки отсутствия ошибок AttributeError при авторизации

Проверяет, что при авторизации не возникает ошибок AttributeError,
связанных с session_interface.save_session
"""

import pytest
import allure
import requests
from typing import Dict


@allure.epic("Интеграционные тесты")
@allure.feature("Авторизация на всех сервисах")
@allure.label("package", "tests.integration.test_auth_all_services")
@pytest.mark.integration
class TestAuthErrorDetection:
    """Тесты проверки отсутствия ошибок при авторизации"""
    
    @pytest.mark.parametrize("service_name", [
        "docs-proxy",
        "allure-homepage",
        "webhook_server",
    ])
    @allure.story("Отсутствие ошибок AttributeError при авторизации")
    @allure.title("Проверка отсутствия ошибок AttributeError на {service_name}")
    @allure.description("""
    Проверяет, что при авторизации не возникает ошибок AttributeError,
    связанных с session_interface.save_session.
    
    **Что проверяется:**
    - Отсутствие ошибок 500 (Internal Server Error) при авторизации
    - Отсутствие ошибок AttributeError в ответе сервера
    - Отсутствие упоминаний 'NoneType' и 'vary' в ответе сервера
    - Корректная обработка авторизации без исключений
    
    **Критичность:**
    Ошибки AttributeError при авторизации критичны, так как блокируют доступ к сервисам.
    Этот тест предотвращает регрессию после исправления проблемы.
    
    **Ожидаемый результат:**
    Авторизация проходит без ошибок AttributeError, сервер возвращает корректный ответ.
    """)
    @allure.severity(allure.severity_level.CRITICAL)
    @allure.tag("auth", "error-detection", "AttributeError", "integration", "critical", "all-services")
    def test_no_attribute_error_on_login(
        self,
        service_name: str,
        service_configs: Dict,
        admin_credentials: Dict[str, str],
        check_service_available,
        service_client
    ):
        """Проверяет отсутствие ошибок AttributeError при авторизации"""
        # Пропускаем тест, если сервис недоступен
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
        
        with allure.step(f"Выполнение авторизации на {service_name}"):
            try:
                response = service_client.post(
                    config["login_url"],
                    data=admin_credentials,
                    allow_redirects=False,
                    timeout=10
                )
            except requests.exceptions.RequestException as e:
                pytest.fail(f"Ошибка при выполнении запроса авторизации: {e}")
        
        with allure.step("Проверка отсутствия ошибок 500"):
            assert response.status_code != 500, (
                f"Ошибка 500 при авторизации на {service_name}. "
                f"Возможно, ошибка AttributeError не исправлена. "
                f"Ответ: {response.text[:1000]}"
            )
            allure.attach(str(response.status_code), "Статус код", allure.attachment_type.TEXT)
        
        with allure.step("Проверка отсутствия ошибок AttributeError в ответе"):
            response_text = response.text.lower()
            
            # Проверяем отсутствие упоминаний об ошибке AttributeError
            error_indicators = [
                'attributerror',
                'noneType',
                'nonetype',
                'object has no attribute',
                'vary',
                'save_session',
                'session_interface',
            ]
            
            found_errors = []
            for indicator in error_indicators:
                if indicator in response_text:
                    found_errors.append(indicator)
            
            if found_errors:
                pytest.fail(
                    f"Обнаружены индикаторы ошибки AttributeError в ответе сервера {service_name}: {found_errors}. "
                    f"Ответ: {response.text[:1000]}"
                )
            
            allure.attach(response.text[:1000], "Ответ сервера", allure.attachment_type.TEXT)
        
        with allure.step("Проверка корректности ответа"):
            # Проверяем, что ответ корректен (не страница с ошибкой)
            assert response.status_code in (200, 302, 303, 307, 308), (
                f"Неожиданный статус код: {response.status_code}. "
                f"Ответ: {response.text[:500]}"
            )
            
            # Если это редирект, проверяем, что он не ведет на страницу ошибки
            if response.status_code in (302, 303, 307, 308):
                location = response.headers.get('Location', '')
                assert 'error' not in location.lower(), (
                    f"Редирект ведет на страницу ошибки: {location}"
                )
                allure.attach(location, "Location заголовок", allure.attachment_type.TEXT)

