#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Unit-тесты для операций с хостами в БД

Тестирует CRUD операции с хостами и планами используя временную БД
"""

import pytest
import allure
import sys
from pathlib import Path

# Добавляем путь к проекту
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root / "src"))

from shop_bot.data_manager.database import (
    get_host,
    get_host_by_code,
    get_all_hosts,
    get_plans_for_host,
    get_plan_by_id,
    create_plan,
)


@pytest.mark.unit
@pytest.mark.database
@allure.epic("База данных")
@allure.feature("Операции с хостами")
@allure.label("package", "src.shop_bot.database")
class TestHostOperations:
    """Тесты для операций с хостами"""

    @allure.title("Получение хоста")
    @allure.description("""
    Проверяет получение хоста по имени.
    
    **Что проверяется:**
    - Получение существующего хоста по host_name
    - Корректность данных полученного хоста
    - Обработка запроса несуществующего хоста (возврат None)
    
    **Тестовые данные:**
    - host_name: из sample_host
    - Несуществующий host_name: "nonexistent_host"
    
    **Ожидаемый результат:**
    Существующий хост успешно получен, несуществующий хост возвращает None.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("host_operations", "get_host", "database", "unit")
    def test_get_host(self, temp_db, sample_host):
        """Тест получения хоста"""
        # Создаем хост в БД
        import sqlite3
        with sqlite3.connect(temp_db) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO xui_hosts (host_name, host_url, host_username, host_pass, host_inbound_id, host_code) VALUES (?, ?, ?, ?, ?, ?)",
                (sample_host['host_name'], sample_host['host_url'], sample_host['host_username'], 
                 sample_host['host_pass'], sample_host['host_inbound_id'], sample_host['host_code'])
            )
            conn.commit()
        
        # Получаем хост по имени
        host = get_host(sample_host['host_name'])
        assert host is not None, "Хост должен быть найден"
        assert host['host_name'] == sample_host['host_name']
        assert host['host_url'] == sample_host['host_url']
        assert host['host_username'] == sample_host['host_username']
        assert host['host_code'] == sample_host['host_code']
        
        # Проверяем несуществующий хост
        non_existent_host = get_host("nonexistent_host")
        assert non_existent_host is None, "Несуществующий хост должен вернуть None"

    @allure.title("Получение хоста по коду")
    @allure.description("""
    Проверяет получение хоста по его коду.
    
    **Что проверяется:**
    - Получение существующего хоста по host_code
    - Корректность данных полученного хоста
    - Обработка запроса несуществующего кода (возврат None)
    
    **Тестовые данные:**
    - host_code: из sample_host
    - Несуществующий host_code: "nonexistent_code"
    
    **Ожидаемый результат:**
    Существующий хост успешно получен по коду, несуществующий код возвращает None.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("host_operations", "get_host", "code", "database", "unit")
    def test_get_host_by_code(self, temp_db, sample_host):
        """Тест получения хоста по коду"""
        # Создаем хост в БД
        import sqlite3
        with sqlite3.connect(temp_db) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO xui_hosts (host_name, host_url, host_username, host_pass, host_inbound_id, host_code) VALUES (?, ?, ?, ?, ?, ?)",
                (sample_host['host_name'], sample_host['host_url'], sample_host['host_username'], 
                 sample_host['host_pass'], sample_host['host_inbound_id'], sample_host['host_code'])
            )
            conn.commit()
        
        # Получаем хост по коду
        host = get_host_by_code(sample_host['host_code'])
        assert host is not None, "Хост должен быть найден по коду"
        assert host['host_name'] == sample_host['host_name']
        assert host['host_code'] == sample_host['host_code']
        
        # Проверяем несуществующий код
        non_existent_host = get_host_by_code("nonexistent_code")
        assert non_existent_host is None, "Несуществующий код должен вернуть None"

    @allure.title("Получение всех хостов")
    @allure.description("""
    Проверяет получение списка всех хостов.
    
    **Что проверяется:**
    - Получение всех хостов через get_all_hosts
    - Корректность количества хостов в списке
    - Наличие всех созданных хостов в списке
    
    **Тестовые данные:**
    - Количество создаваемых хостов: 2
    
    **Ожидаемый результат:**
    Список содержит все созданные хосты.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("host_operations", "get_all_hosts", "database", "unit")
    def test_get_all_hosts(self, temp_db, sample_host):
        """Тест получения всех хостов"""
        # Создаем несколько хостов в БД
        import sqlite3
        with sqlite3.connect(temp_db) as conn:
            cursor = conn.cursor()
            
            # Первый хост
            cursor.execute(
                "INSERT INTO xui_hosts (host_name, host_url, host_username, host_pass, host_inbound_id, host_code) VALUES (?, ?, ?, ?, ?, ?)",
                (sample_host['host_name'], sample_host['host_url'], sample_host['host_username'], 
                 sample_host['host_pass'], sample_host['host_inbound_id'], sample_host['host_code'])
            )
            
            # Второй хост
            cursor.execute(
                "INSERT INTO xui_hosts (host_name, host_url, host_username, host_pass, host_inbound_id, host_code) VALUES (?, ?, ?, ?, ?, ?)",
                ("test-host-2", "https://test2.example.com:8443/configpanel", "admin2", "password2", 2, "test-code-2")
            )
            
            conn.commit()
        
        # Получаем все хосты
        hosts = get_all_hosts()
        assert len(hosts) >= 2, "Должно быть минимум 2 хоста"
        
        # Проверяем, что оба хоста присутствуют
        host_names = [h['host_name'] for h in hosts]
        assert sample_host['host_name'] in host_names, "Первый хост должен быть в списке"
        assert "test-host-2" in host_names, "Второй хост должен быть в списке"

    @allure.title("Получение планов для хоста")
    @allure.description("""
    Проверяет получение списка планов для конкретного хоста.
    
    **Что проверяется:**
    - Получение планов для хоста через get_plans_for_host
    - Корректность количества планов в списке
    - Наличие всех созданных планов в списке
    - Обработка несуществующего хоста (пустой список)
    
    **Тестовые данные:**
    - host_name: из sample_host
    - Количество создаваемых планов: 2
    - Несуществующий host_name: "nonexistent_host"
    
    **Ожидаемый результат:**
    Список содержит все созданные планы для хоста, для несуществующего хоста возвращается пустой список.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("host_operations", "get_plans", "database", "unit")
    def test_get_plans_for_host(self, temp_db, sample_host):
        """Тест получения планов для хоста"""
        # Создаем хост в БД
        import sqlite3
        with sqlite3.connect(temp_db) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO xui_hosts (host_name, host_url, host_username, host_pass, host_inbound_id, host_code) VALUES (?, ?, ?, ?, ?, ?)",
                (sample_host['host_name'], sample_host['host_url'], sample_host['host_username'], 
                 sample_host['host_pass'], sample_host['host_inbound_id'], sample_host['host_code'])
            )
            conn.commit()
        
        # Создаем несколько планов для хоста
        create_plan(
            host_name=sample_host['host_name'],
            plan_name="Plan 1 Month",
            months=1,
            price=100.0,
            days=0,
            traffic_gb=0.0,
            hours=0
        )
        
        create_plan(
            host_name=sample_host['host_name'],
            plan_name="Plan 3 Months",
            months=3,
            price=250.0,
            days=0,
            traffic_gb=0.0,
            hours=0
        )
        
        # Получаем планы для хоста
        plans = get_plans_for_host(sample_host['host_name'])
        assert len(plans) >= 2, "Должно быть минимум 2 плана"
        
        # Проверяем, что планы присутствуют
        plan_names = [p['plan_name'] for p in plans]
        assert "Plan 1 Month" in plan_names, "План 1 месяц должен быть в списке"
        assert "Plan 3 Months" in plan_names, "План 3 месяца должен быть в списке"
        
        # Проверяем несуществующий хост
        empty_plans = get_plans_for_host("nonexistent_host")
        assert len(empty_plans) == 0, "Для несуществующего хоста должен быть пустой список планов"

    @allure.title("Получение плана по ID")
    @allure.description("""
    Проверяет получение плана по его идентификатору.
    
    **Что проверяется:**
    - Получение существующего плана по plan_id
    - Корректность данных полученного плана
    - Обработка запроса несуществующего плана (возврат None)
    
    **Тестовые данные:**
    - plan_name: "Test Plan"
    - months: 1
    - price: 100.0
    - Несуществующий plan_id: 999999
    
    **Ожидаемый результат:**
    Существующий план успешно получен по ID, несуществующий план возвращает None.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("host_operations", "get_plan", "database", "unit")
    def test_get_plan_by_id(self, temp_db, sample_host):
        """Тест получения плана по ID"""
        # Создаем хост в БД
        import sqlite3
        with sqlite3.connect(temp_db) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO xui_hosts (host_name, host_url, host_username, host_pass, host_inbound_id, host_code) VALUES (?, ?, ?, ?, ?, ?)",
                (sample_host['host_name'], sample_host['host_url'], sample_host['host_username'], 
                 sample_host['host_pass'], sample_host['host_inbound_id'], sample_host['host_code'])
            )
            conn.commit()
        
        # Создаем план
        create_plan(
            host_name=sample_host['host_name'],
            plan_name="Test Plan",
            months=1,
            price=100.0,
            days=0,
            traffic_gb=0.0,
            hours=0
        )
        
        # Получаем планы для хоста и находим созданный план
        plans = get_plans_for_host(sample_host['host_name'])
        assert len(plans) > 0, "Должен быть создан хотя бы один план"
        
        created_plan = plans[0]
        plan_id = created_plan['plan_id']
        
        # Получаем план по ID
        plan = get_plan_by_id(plan_id)
        assert plan is not None, "План должен быть найден по ID"
        assert plan['plan_id'] == plan_id
        assert plan['plan_name'] == "Test Plan"
        assert plan['months'] == 1
        assert plan['price'] == 100.0
        
        # Проверяем несуществующий план
        non_existent_plan = get_plan_by_id(999999)
        assert non_existent_plan is None, "Несуществующий план должен вернуть None"

