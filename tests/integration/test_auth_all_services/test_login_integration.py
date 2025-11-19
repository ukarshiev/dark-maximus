#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Интеграционные тесты авторизации для всех сервисов проекта

Проверяет успешную авторизацию без ошибок AttributeError на всех сервисах:
- docs-proxy (порт 50001)
- allure-homepage (порт 50005)
- webhook_server (порт 50000)
"""

import pytest
import allure
import requests
from typing import Dict


@allure.epic("Интеграционные тесты")
@allure.feature("Авторизация на всех сервисах")
@allure.label("package", "tests.integration.test_auth_all_services")
@pytest.mark.integration
class TestAuthAllServices:
    """Тесты авторизации для всех сервисов проекта"""
    
    @pytest.mark.parametrize("service_name", [
        "docs-proxy",
        "allure-homepage",
        "webhook_server",
    ])
    @allure.story("Успешная авторизация без ошибок")
    @allure.title("Успешная авторизация на {service_name} без ошибок AttributeError")
    @allure.description("""
    Проверяет успешную авторизацию на сервисе без ошибок AttributeError.
    
    **Что проверяется:**
    - Доступность страницы логина
    - Успешная авторизация с корректными учетными данными
    - Отсутствие ошибок AttributeError в процессе авторизации
    - Корректное сохранение сессии после авторизации
    - Доступ к защищенной странице после авторизации
    
    **Тестовые данные:**
    - Учетные данные из admin_credentials фикстуры
    
    **Ожидаемый результат:**
    Авторизация проходит успешно без ошибок, сессия сохраняется, доступ к защищенным страницам разрешен.
    """)
    @allure.severity(allure.severity_level.CRITICAL)
    @allure.tag("auth", "login", "integration", "critical", "all-services")
    def test_login_success_no_errors(
        self,
        service_name: str,
        service_configs: Dict,
        admin_credentials: Dict[str, str],
        check_service_available,
        service_client
    ):
        """Проверяет успешную авторизацию без ошибок AttributeError"""
        # Пропускаем тест, если сервис недоступен
        if not check_service_available(service_name):
            pytest.skip(f"Сервис {service_name} недоступен")
        
        config = service_configs[service_name]
        
        with allure.step(f"Проверка доступности страницы логина {config['login_url']}"):
            response = service_client.get(config["login_url"], timeout=5)
            assert response.status_code == 200, f"Страница логина недоступна: {response.status_code}"
            allure.attach(str(response.status_code), "Статус код страницы логина", allure.attachment_type.TEXT)
        
        with allure.step(f"Выполнение авторизации на {service_name}"):
            # Отправляем POST запрос на авторизацию
            response = service_client.post(
                config["login_url"],
                data=admin_credentials,
                allow_redirects=False,
                timeout=10
            )
            
            # Проверяем, что нет ошибок 500 (Internal Server Error)
            assert response.status_code != 500, (
                f"Ошибка 500 при авторизации на {service_name}. "
                f"Возможно, ошибка AttributeError не исправлена. "
                f"Ответ: {response.text[:500]}"
            )
            
            # Проверяем, что авторизация прошла успешно (редирект или 200)
            assert response.status_code in (200, 302, 303, 307, 308), (
                f"Неожиданный статус код при авторизации: {response.status_code}. "
                f"Ответ: {response.text[:500]}"
            )
            
            allure.attach(str(response.status_code), "Статус код авторизации", allure.attachment_type.TEXT)
            allure.attach(response.text[:500], "Ответ сервера", allure.attachment_type.TEXT)
        
        with allure.step("Проверка сохранения сессии и доступа к защищенной странице"):
            # Пытаемся получить доступ к защищенной странице
            response = service_client.get(config["protected_url"], timeout=5)
            
            # Если редирект на логин - сессия не сохранилась
            if response.status_code == 302 and '/login' in response.headers.get('Location', ''):
                pytest.fail(
                    f"Сессия не сохранилась после авторизации на {service_name}. "
                    f"Происходит редирект на страницу логина."
                )
            
            # Проверяем, что доступ разрешен (не редирект на логин)
            assert response.status_code != 302 or '/login' not in response.headers.get('Location', ''), (
                f"Доступ к защищенной странице запрещен после авторизации на {service_name}"
            )
            
            allure.attach(str(response.status_code), "Статус код защищенной страницы", allure.attachment_type.TEXT)
    
    @pytest.mark.parametrize("service_name", [
        "docs-proxy",
        "allure-homepage",
        "webhook_server",
    ])
    @allure.story("Обработка неверных учетных данных")
    @allure.title("Обработка неверных учетных данных на {service_name} без ошибок")
    @allure.description("""
    Проверяет обработку неверных учетных данных без ошибок AttributeError.
    
    **Что проверяется:**
    - Отправка POST запроса с неверными учетными данными
    - Отсутствие ошибок 500 (Internal Server Error)
    - Корректная обработка ошибки авторизации
    - Отсутствие ошибок AttributeError в процессе обработки
    
    **Тестовые данные:**
    - username: 'wrong_user'
    - password: 'wrong_password'
    
    **Ожидаемый результат:**
    Ошибка авторизации обрабатывается корректно без ошибок AttributeError, возвращается статус 200 с сообщением об ошибке.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("auth", "login", "failure", "integration", "all-services")
    def test_login_failure_no_errors(
        self,
        service_name: str,
        service_configs: Dict,
        check_service_available,
        service_client
    ):
        """Проверяет обработку неверных данных без ошибок AttributeError"""
        # Пропускаем тест, если сервис недоступен
        if not check_service_available(service_name):
            pytest.skip(f"Сервис {service_name} недоступен")
        
        config = service_configs[service_name]
        
        with allure.step(f"Отправка запроса с неверными учетными данными на {service_name}"):
            wrong_credentials = {
                'username': 'wrong_user',
                'password': 'wrong_password'
            }
            
            response = service_client.post(
                config["login_url"],
                data=wrong_credentials,
                allow_redirects=False,
                timeout=10
            )
            
            # Проверяем, что нет ошибок 500 (Internal Server Error)
            assert response.status_code != 500, (
                f"Ошибка 500 при обработке неверных данных на {service_name}. "
                f"Возможно, ошибка AttributeError не исправлена. "
                f"Ответ: {response.text[:500]}"
            )
            
            # Проверяем, что ошибка обработана корректно (200 или редирект)
            assert response.status_code in (200, 302, 303, 307, 308), (
                f"Неожиданный статус код при обработке неверных данных: {response.status_code}. "
                f"Ответ: {response.text[:500]}"
            )
            
            allure.attach(str(response.status_code), "Статус код обработки ошибки", allure.attachment_type.TEXT)
            allure.attach(response.text[:500], "Ответ сервера", allure.attachment_type.TEXT)
    
    @pytest.mark.parametrize("service_name", [
        "docs-proxy",
        "allure-homepage",
        "webhook_server",
    ])
    @allure.story("Сохранение сессии между запросами")
    @allure.title("Сохранение сессии между запросами на {service_name}")
    @allure.description("""
    Проверяет сохранение сессии между запросами после успешной авторизации.
    
    **Что проверяется:**
    - Успешная авторизация
    - Сохранение сессии между несколькими запросами
    - Доступ к защищенным страницам через сохраненную сессию
    
    **Ожидаемый результат:**
    Сессия сохраняется между запросами, доступ к защищенным страницам разрешен во всех запросах.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("auth", "session", "persistence", "integration", "all-services")
    def test_session_persistence(
        self,
        service_name: str,
        service_configs: Dict,
        admin_credentials: Dict[str, str],
        check_service_available,
        service_client
    ):
        """Проверяет сохранение сессии между запросами"""
        # Пропускаем тест, если сервис недоступен
        if not check_service_available(service_name):
            pytest.skip(f"Сервис {service_name} недоступен")
        
        config = service_configs[service_name]
        
        with allure.step("Выполнение авторизации"):
            response = service_client.post(
                config["login_url"],
                data=admin_credentials,
                allow_redirects=False,
                timeout=10
            )
            
            assert response.status_code != 500, (
                f"Ошибка 500 при авторизации на {service_name}"
            )
            assert response.status_code in (200, 302, 303, 307, 308), (
                f"Авторизация не прошла: {response.status_code}"
            )
        
        with allure.step("Проверка доступа к защищенной странице (первый запрос)"):
            response1 = service_client.get(config["protected_url"], timeout=5)
            status1 = response1.status_code
            allure.attach(str(status1), "Статус код первого запроса", allure.attachment_type.TEXT)
        
        with allure.step("Проверка доступа к защищенной странице (второй запрос)"):
            response2 = service_client.get(config["protected_url"], timeout=5)
            status2 = response2.status_code
            allure.attach(str(status2), "Статус код второго запроса", allure.attachment_type.TEXT)
        
        with allure.step("Проверка сохранения сессии"):
            # Оба запроса должны иметь одинаковый статус (сессия сохранилась)
            assert status1 == status2, (
                f"Сессия не сохранилась между запросами на {service_name}. "
                f"Первый запрос: {status1}, второй запрос: {status2}"
            )
            
            # Оба запроса не должны быть редиректами на логин
            assert status1 != 302 or '/login' not in response1.headers.get('Location', ''), (
                f"Доступ запрещен после авторизации на {service_name}"
            )

