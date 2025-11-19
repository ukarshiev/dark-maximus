#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Unit-тесты для фильтрации планов по режиму отображения

Тестирует функцию filter_plans_by_display_mode() с различными режимами отображения,
группами пользователей и edge cases используя временную БД
"""

import pytest
import sqlite3
import sys
import json
from pathlib import Path

# Добавляем путь к проекту
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root / "src"))

import allure
from shop_bot.data_manager.database import (
    filter_plans_by_display_mode,
    create_plan,
    register_user_if_not_exists,
    create_user_group,
)


@pytest.mark.unit
@pytest.mark.database
@allure.epic("База данных")
@allure.feature("Фильтрация планов")
@allure.label("package", "src.shop_bot.database")
class TestPlanDisplayMode:
    """Тесты для фильтрации планов по режиму отображения"""

    @allure.story("Режим отображения: all")
    @allure.title("План с режимом 'all' показывается всем пользователям")
    @allure.description("""
    Тест проверяет, что планы с режимом отображения 'all' показываются всем пользователям,
    независимо от их группы и истории использования тарифов.
    
    **Сценарий:**
    1. Создаем план с display_mode='all'
    2. Создаем пользователей из разных групп
    3. Проверяем, что план виден всем пользователям
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("plan_display_mode", "all", "filtering", "database", "unit")
    def test_display_mode_all_visible_to_everyone(self, temp_db):
        """План с режимом 'all' показывается всем пользователям"""
        import sqlite3
        
        with allure.step("Создаем тестовый хост"):
            with sqlite3.connect(temp_db) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO xui_hosts (host_name, host_url, host_username, host_pass, host_inbound_id, host_code) VALUES (?, ?, ?, ?, ?, ?)",
                    ("test-host", "https://test.example.com:8443", "admin", "password", 1, "test-code")
                )
                conn.commit()
        
        with allure.step("Создаем план с режимом 'all'"):
            create_plan(
                host_name="test-host",
                plan_name="План для всех",
                months=1,
                price=100.0,
                days=0,
                traffic_gb=0.0,
                hours=0,
                display_mode="all"
            )
        
        with allure.step("Получаем созданный план"):
            with sqlite3.connect(temp_db) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM plans WHERE plan_name = 'План для всех'")
                row = cursor.fetchone()
                columns = [desc[0] for desc in cursor.description]
                plan = dict(zip(columns, row))
        
        plans = [plan]
        
        with allure.step("Создаем пользователей из разных групп"):
            user1 = register_user_if_not_exists(111111, "user1", None, "User 1")
            user2 = register_user_if_not_exists(222222, "user2", None, "User 2")
            
            # Создаем группы
            group1_id = create_user_group("Группа 1", "Описание группы 1", "group1")
            group2_id = create_user_group("Группа 2", "Описание группы 2", "group2")
            
            # Назначаем пользователей в разные группы
            with sqlite3.connect(temp_db) as conn:
                cursor = conn.cursor()
                cursor.execute("UPDATE users SET group_id = ? WHERE telegram_id = ?", (group1_id, 111111))
                cursor.execute("UPDATE users SET group_id = ? WHERE telegram_id = ?", (group2_id, 222222))
                conn.commit()
        
        with allure.step("Проверяем, что план виден всем пользователям"):
            filtered_user1 = filter_plans_by_display_mode(plans, 111111)
            filtered_user2 = filter_plans_by_display_mode(plans, 222222)
            
            assert len(filtered_user1) == 1, "План должен быть виден пользователю 1"
            assert len(filtered_user2) == 1, "План должен быть виден пользователю 2"
            assert filtered_user1[0]['plan_name'] == "План для всех"
            assert filtered_user2[0]['plan_name'] == "План для всех"

    @allure.story("Режим отображения: hidden_all")
    @allure.title("План с режимом 'hidden_all' скрыт у всех пользователей")
    @allure.description("""
    Тест проверяет, что планы с режимом отображения 'hidden_all' скрыты у всех пользователей,
    независимо от их группы, истории использования или других настроек.
    
    **Сценарий:**
    1. Создаем план с display_mode='hidden_all'
    2. Создаем пользователей из разных групп, с разной историей использования
    3. Проверяем, что план скрыт у всех пользователей
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("plan_display_mode", "hidden_all", "filtering", "database", "unit")
    def test_display_mode_hidden_all_hidden_from_everyone(self, temp_db):
        """План с режимом 'hidden_all' скрыт у всех пользователей"""
        import sqlite3
        
        with allure.step("Создаем тестовый хост"):
            with sqlite3.connect(temp_db) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO xui_hosts (host_name, host_url, host_username, host_pass, host_inbound_id, host_code) VALUES (?, ?, ?, ?, ?, ?)",
                    ("test-host", "https://test.example.com:8443", "admin", "password", 1, "test-code")
                )
                conn.commit()
        
        with allure.step("Создаем план с режимом 'hidden_all' и группой"):
            create_plan(
                host_name="test-host",
                plan_name="Скрытый план",
                months=1,
                price=100.0,
                days=0,
                traffic_gb=0.0,
                hours=0,
                display_mode="hidden_all",
                display_mode_groups=[1]  # Даже если указана группа, план должен быть скрыт
            )
        
        with allure.step("Получаем созданный план"):
            with sqlite3.connect(temp_db) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM plans WHERE plan_name = 'Скрытый план'")
                row = cursor.fetchone()
                columns = [desc[0] for desc in cursor.description]
                plan = dict(zip(columns, row))
                # Десериализуем display_mode_groups
                if plan.get('display_mode_groups'):
                    plan['display_mode_groups'] = json.loads(plan['display_mode_groups'])
        
        plans = [plan]
        
        with allure.step("Создаем пользователей с разными настройками"):
            user1 = register_user_if_not_exists(111111, "user1", None, "User 1")
            user2 = register_user_if_not_exists(222222, "user2", None, "User 2")
            
            # Создаем группу и назначаем пользователя
            group1_id = create_user_group("Группа 1", "Описание", "group1")
            with sqlite3.connect(temp_db) as conn:
                cursor = conn.cursor()
                cursor.execute("UPDATE users SET group_id = ? WHERE telegram_id = ?", (group1_id, 111111))
                # Создаем транзакцию для user2 (он использовал план)
                cursor.execute(
                    "INSERT INTO transactions (payment_id, user_id, status, amount_rub, metadata) VALUES (?, ?, ?, ?, ?)",
                    ("pay_123", 222222, "paid", 100.0, json.dumps({"plan_id": plan['plan_id']}))
                )
                conn.commit()
        
        with allure.step("Проверяем, что план скрыт у всех пользователей"):
            filtered_user1 = filter_plans_by_display_mode(plans, 111111)
            filtered_user2 = filter_plans_by_display_mode(plans, 222222)
            
            assert len(filtered_user1) == 0, "План должен быть скрыт у пользователя 1 (даже если он в нужной группе)"
            assert len(filtered_user2) == 0, "План должен быть скрыт у пользователя 2 (даже если он использовал план)"

    @allure.story("Режим отображения: hidden_new")
    @allure.title("План с режимом 'hidden_new' скрыт у новых пользователей")
    @allure.description("""
    Тест проверяет, что планы с режимом отображения 'hidden_new' скрыты только у новых пользователей,
    которые ни разу не использовали этот тариф. Пользователи, которые уже использовали тариф, видят его.
    
    **Сценарий:**
    1. Создаем план с display_mode='hidden_new'
    2. Создаем нового пользователя (не использовал план)
    3. Создаем старого пользователя (использовал план через транзакцию)
    4. Проверяем, что план скрыт у нового, но виден старому
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("plan_display_mode", "hidden_new", "filtering", "database", "unit")
    def test_display_mode_hidden_new_hidden_from_new_users(self, temp_db):
        """План с режимом 'hidden_new' скрыт у новых пользователей"""
        import sqlite3
        
        with allure.step("Создаем тестовый хост"):
            with sqlite3.connect(temp_db) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO xui_hosts (host_name, host_url, host_username, host_pass, host_inbound_id, host_code) VALUES (?, ?, ?, ?, ?, ?)",
                    ("test-host", "https://test.example.com:8443", "admin", "password", 1, "test-code")
                )
                conn.commit()
        
        with allure.step("Создаем план с режимом 'hidden_new'"):
            create_plan(
                host_name="test-host",
                plan_name="План скрыт у новых",
                months=1,
                price=100.0,
                days=0,
                traffic_gb=0.0,
                hours=0,
                display_mode="hidden_new"
            )
        
        with allure.step("Получаем созданный план"):
            with sqlite3.connect(temp_db) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM plans WHERE plan_name = 'План скрыт у новых'")
                row = cursor.fetchone()
                columns = [desc[0] for desc in cursor.description]
                plan = dict(zip(columns, row))
        
        plans = [plan]
        
        with allure.step("Создаем нового пользователя (не использовал план)"):
            new_user = register_user_if_not_exists(111111, "new_user", None, "New User")
        
        with allure.step("Создаем старого пользователя (использовал план)"):
            old_user = register_user_if_not_exists(222222, "old_user", None, "Old User")
            
            # Создаем оплаченную транзакцию для старого пользователя
            with sqlite3.connect(temp_db) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO transactions (payment_id, user_id, status, amount_rub, metadata) VALUES (?, ?, ?, ?, ?)",
                    ("pay_123", 222222, "paid", 100.0, json.dumps({"plan_id": plan['plan_id']}))
                )
                conn.commit()
        
        with allure.step("Проверяем фильтрацию для нового пользователя"):
            filtered_new = filter_plans_by_display_mode(plans, 111111)
            assert len(filtered_new) == 0, "План должен быть скрыт у нового пользователя"
        
        with allure.step("Проверяем фильтрацию для старого пользователя"):
            filtered_old = filter_plans_by_display_mode(plans, 222222)
            assert len(filtered_old) == 1, "План должен быть виден старому пользователю"
            assert filtered_old[0]['plan_name'] == "План скрыт у новых"

    @allure.story("Режим отображения: hidden_old")
    @allure.title("План с режимом 'hidden_old' скрыт у старых пользователей")
    @allure.description("""
    Тест проверяет, что планы с режимом отображения 'hidden_old' скрыты только у старых пользователей,
    которые уже использовали этот тариф. Новые пользователи, которые не использовали тариф, видят его.
    
    **Сценарий:**
    1. Создаем план с display_mode='hidden_old'
    2. Создаем нового пользователя (не использовал план)
    3. Создаем старого пользователя (использовал план через транзакцию)
    4. Проверяем, что план виден новому, но скрыт старому
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("plan_display_mode", "hidden_old", "filtering", "database", "unit")
    def test_display_mode_hidden_old_hidden_from_old_users(self, temp_db):
        """План с режимом 'hidden_old' скрыт у старых пользователей"""
        import sqlite3
        
        with allure.step("Создаем тестовый хост"):
            with sqlite3.connect(temp_db) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO xui_hosts (host_name, host_url, host_username, host_pass, host_inbound_id, host_code) VALUES (?, ?, ?, ?, ?, ?)",
                    ("test-host", "https://test.example.com:8443", "admin", "password", 1, "test-code")
                )
                conn.commit()
        
        with allure.step("Создаем план с режимом 'hidden_old'"):
            create_plan(
                host_name="test-host",
                plan_name="План скрыт у старых",
                months=1,
                price=100.0,
                days=0,
                traffic_gb=0.0,
                hours=0,
                display_mode="hidden_old"
            )
        
        with allure.step("Получаем созданный план"):
            with sqlite3.connect(temp_db) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM plans WHERE plan_name = 'План скрыт у старых'")
                row = cursor.fetchone()
                columns = [desc[0] for desc in cursor.description]
                plan = dict(zip(columns, row))
        
        plans = [plan]
        
        with allure.step("Создаем нового пользователя (не использовал план)"):
            new_user = register_user_if_not_exists(111111, "new_user", None, "New User")
        
        with allure.step("Создаем старого пользователя (использовал план)"):
            old_user = register_user_if_not_exists(222222, "old_user", None, "Old User")
            
            # Создаем оплаченную транзакцию для старого пользователя
            with sqlite3.connect(temp_db) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO transactions (payment_id, user_id, status, amount_rub, metadata) VALUES (?, ?, ?, ?, ?)",
                    ("pay_123", 222222, "paid", 100.0, json.dumps({"plan_id": plan['plan_id']}))
                )
                conn.commit()
        
        with allure.step("Проверяем фильтрацию для нового пользователя"):
            filtered_new = filter_plans_by_display_mode(plans, 111111)
            assert len(filtered_new) == 1, "План должен быть виден новому пользователю"
            assert filtered_new[0]['plan_name'] == "План скрыт у старых"
        
        with allure.step("Проверяем фильтрацию для старого пользователя"):
            filtered_old = filter_plans_by_display_mode(plans, 222222)
            assert len(filtered_old) == 0, "План должен быть скрыт у старого пользователя"

    @allure.story("Группы пользователей")
    @allure.title("План показывается только пользователям из указанных групп")
    @allure.description("""
    Тест проверяет фильтрацию планов по группам пользователей через display_mode_groups.
    План должен показываться только пользователям, которые принадлежат к указанным группам.
    
    **Сценарий:**
    1. Создаем план с display_mode='all' и display_mode_groups=[group1_id]
    2. Создаем пользователей в разных группах
    3. Проверяем, что план виден только пользователям из указанной группы
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("plan_display_mode", "groups", "filtering", "database", "unit")
    def test_display_mode_groups_filter_by_groups(self, temp_db):
        """План показывается только пользователям из указанных групп"""
        import sqlite3
        
        with allure.step("Создаем тестовый хост"):
            with sqlite3.connect(temp_db) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO xui_hosts (host_name, host_url, host_username, host_pass, host_inbound_id, host_code) VALUES (?, ?, ?, ?, ?, ?)",
                    ("test-host", "https://test.example.com:8443", "admin", "password", 1, "test-code")
                )
                conn.commit()
        
        with allure.step("Создаем группы пользователей"):
            group1_id = create_user_group("VIP группа", "VIP пользователи", "vip")
            group2_id = create_user_group("Обычная группа", "Обычные пользователи", "regular")
        
        with allure.step("Создаем план с фильтрацией по группе VIP"):
            create_plan(
                host_name="test-host",
                plan_name="VIP план",
                months=1,
                price=200.0,
                days=0,
                traffic_gb=0.0,
                hours=0,
                display_mode="all",
                display_mode_groups=[group1_id]  # Только для VIP группы
            )
        
        with allure.step("Получаем созданный план"):
            with sqlite3.connect(temp_db) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM plans WHERE plan_name = 'VIP план'")
                row = cursor.fetchone()
                columns = [desc[0] for desc in cursor.description]
                plan = dict(zip(columns, row))
                # Десериализуем display_mode_groups
                if plan.get('display_mode_groups'):
                    plan['display_mode_groups'] = json.loads(plan['display_mode_groups'])
        
        plans = [plan]
        
        with allure.step("Создаем пользователей в разных группах"):
            vip_user = register_user_if_not_exists(111111, "vip_user", None, "VIP User")
            regular_user = register_user_if_not_exists(222222, "regular_user", None, "Regular User")
            no_group_user = register_user_if_not_exists(333333, "no_group_user", None, "No Group User")
            
            # Назначаем пользователей в группы
            with sqlite3.connect(temp_db) as conn:
                cursor = conn.cursor()
                cursor.execute("UPDATE users SET group_id = ? WHERE telegram_id = ?", (group1_id, 111111))
                cursor.execute("UPDATE users SET group_id = ? WHERE telegram_id = ?", (group2_id, 222222))
                # Пользователь 333333 остается без группы (group_id = NULL или default)
                conn.commit()
        
        with allure.step("Проверяем фильтрацию для VIP пользователя"):
            filtered_vip = filter_plans_by_display_mode(plans, 111111)
            assert len(filtered_vip) == 1, "План должен быть виден VIP пользователю"
            assert filtered_vip[0]['plan_name'] == "VIP план"
        
        with allure.step("Проверяем фильтрацию для обычного пользователя"):
            filtered_regular = filter_plans_by_display_mode(plans, 222222)
            assert len(filtered_regular) == 0, "План должен быть скрыт у обычного пользователя"
        
        with allure.step("Проверяем фильтрацию для пользователя без группы"):
            filtered_no_group = filter_plans_by_display_mode(plans, 333333)
            assert len(filtered_no_group) == 0, "План должен быть скрыт у пользователя без группы"

    @allure.story("Группы пользователей")
    @allure.title("План с display_mode_groups=None показывается всем пользователям")
    @allure.description("""
    Тест проверяет, что план с пустым display_mode_groups показывается всем пользователям,
    независимо от их группы.
    
    **Сценарий:**
    1. Создаем план с display_mode='all' и display_mode_groups=None
    2. Создаем пользователей в разных группах
    3. Проверяем, что план виден всем
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("plan_display_mode", "groups", "none", "filtering", "database", "unit")
    def test_display_mode_groups_none_shows_to_everyone(self, temp_db):
        """План с display_mode_groups=None показывается всем пользователям"""
        import sqlite3
        
        with allure.step("Создаем тестовый хост"):
            with sqlite3.connect(temp_db) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO xui_hosts (host_name, host_url, host_username, host_pass, host_inbound_id, host_code) VALUES (?, ?, ?, ?, ?, ?)",
                    ("test-host", "https://test.example.com:8443", "admin", "password", 1, "test-code")
                )
                conn.commit()
        
        with allure.step("Создаем план без фильтрации по группам"):
            create_plan(
                host_name="test-host",
                plan_name="План для всех групп",
                months=1,
                price=100.0,
                days=0,
                traffic_gb=0.0,
                hours=0,
                display_mode="all",
                display_mode_groups=None  # Нет фильтрации по группам
            )
        
        with allure.step("Получаем созданный план"):
            with sqlite3.connect(temp_db) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM plans WHERE plan_name = 'План для всех групп'")
                row = cursor.fetchone()
                columns = [desc[0] for desc in cursor.description]
                plan = dict(zip(columns, row))
        
        plans = [plan]
        
        with allure.step("Создаем пользователей в разных группах"):
            group1_id = create_user_group("Группа 1", "Описание", "group1")
            group2_id = create_user_group("Группа 2", "Описание", "group2")
            
            user1 = register_user_if_not_exists(111111, "user1", None, "User 1")
            user2 = register_user_if_not_exists(222222, "user2", None, "User 2")
            user3 = register_user_if_not_exists(333333, "user3", None, "User 3")
            
            with sqlite3.connect(temp_db) as conn:
                cursor = conn.cursor()
                cursor.execute("UPDATE users SET group_id = ? WHERE telegram_id = ?", (group1_id, 111111))
                cursor.execute("UPDATE users SET group_id = ? WHERE telegram_id = ?", (group2_id, 222222))
                # user3 остается без группы
                conn.commit()
        
        with allure.step("Проверяем, что план виден всем пользователям"):
            filtered_user1 = filter_plans_by_display_mode(plans, 111111)
            filtered_user2 = filter_plans_by_display_mode(plans, 222222)
            filtered_user3 = filter_plans_by_display_mode(plans, 333333)
            
            assert len(filtered_user1) == 1, "План должен быть виден пользователю 1"
            assert len(filtered_user2) == 1, "План должен быть виден пользователю 2"
            assert len(filtered_user3) == 1, "План должен быть виден пользователю 3"

    @allure.story("Приоритет режимов")
    @allure.title("Режим display_mode имеет приоритет над display_mode_groups")
    @allure.description("""
    Тест проверяет приоритет display_mode над display_mode_groups.
    Если display_mode='hidden_all', тариф должен быть скрыт у всех пользователей,
    даже если они находятся в указанных в display_mode_groups группах.
    
    **Сценарий:**
    1. Создаем план с display_mode='hidden_all' и display_mode_groups=[group_id]
    2. Создаем пользователя в указанной группе
    3. Проверяем, что план скрыт несмотря на группу
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("plan_display_mode", "priority", "filtering", "database", "unit")
    def test_display_mode_priority_over_groups(self, temp_db):
        """Режим display_mode имеет приоритет над display_mode_groups"""
        import sqlite3
        
        with allure.step("Создаем тестовый хост"):
            with sqlite3.connect(temp_db) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO xui_hosts (host_name, host_url, host_username, host_pass, host_inbound_id, host_code) VALUES (?, ?, ?, ?, ?, ?)",
                    ("test-host", "https://test.example.com:8443", "admin", "password", 1, "test-code")
                )
                conn.commit()
        
        with allure.step("Создаем группу и план с conflicting настройками"):
            group_id = create_user_group("Тестовая группа", "Описание", "test_group")
            
            create_plan(
                host_name="test-host",
                plan_name="План с конфликтом",
                months=1,
                price=100.0,
                days=0,
                traffic_gb=0.0,
                hours=0,
                display_mode="hidden_all",  # Скрыт у всех
                display_mode_groups=[group_id]  # Но указана группа
            )
        
        with allure.step("Получаем созданный план"):
            with sqlite3.connect(temp_db) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM plans WHERE plan_name = 'План с конфликтом'")
                row = cursor.fetchone()
                columns = [desc[0] for desc in cursor.description]
                plan = dict(zip(columns, row))
                if plan.get('display_mode_groups'):
                    plan['display_mode_groups'] = json.loads(plan['display_mode_groups'])
        
        plans = [plan]
        
        with allure.step("Создаем пользователя в указанной группе"):
            user = register_user_if_not_exists(111111, "test_user", None, "Test User")
            with sqlite3.connect(temp_db) as conn:
                cursor = conn.cursor()
                cursor.execute("UPDATE users SET group_id = ? WHERE telegram_id = ?", (group_id, 111111))
                conn.commit()
        
        with allure.step("Проверяем, что план скрыт несмотря на группу"):
            filtered = filter_plans_by_display_mode(plans, 111111)
            assert len(filtered) == 0, "План должен быть скрыт у всех, даже если пользователь в нужной группе (приоритет display_mode)"

    @allure.story("Edge cases")
    @allure.title("Пустой список планов возвращает пустой список")
    @allure.description("""
    Тест проверяет edge cases: пустые списки планов, None значения, планы без plan_id.
    
    **Сценарии:**
    1. Пустой список планов возвращает пустой список
    2. План без plan_id обрабатывается корректно
    3. Пользователь без группы обрабатывается корректно
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("plan_display_mode", "edge_cases", "empty_list", "database", "unit")
    def test_edge_cases_empty_list(self, temp_db):
        """Пустой список планов возвращает пустой список"""
        with allure.step("Проверяем фильтрацию пустого списка"):
            filtered = filter_plans_by_display_mode([], 111111)
            assert filtered == [], "Пустой список планов должен возвращать пустой список"

    @allure.story("Edge cases")
    @allure.title("План без plan_id обрабатывается корректно")
    @allure.description("""
    Тест проверяет обработку плана без plan_id при использовании режимов hidden_new и hidden_old.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("plan_display_mode", "edge_cases", "plan_without_id", "database", "unit")
    def test_edge_cases_plan_without_id(self, temp_db):
        """План без plan_id обрабатывается корректно"""
        import sqlite3
        
        with allure.step("Создаем план без plan_id (симуляция)"):
            plan_without_id = {
                'plan_id': None,  # Нет ID
                'plan_name': 'План без ID',
                'display_mode': 'hidden_new',  # Требует проверки использования
                'display_mode_groups': None
            }
        
        plans = [plan_without_id]
        
        with allure.step("Создаем пользователя"):
            user = register_user_if_not_exists(111111, "test_user", None, "Test User")
        
        with allure.step("Проверяем фильтрацию (план должен быть виден, т.к. нет ID для проверки)"):
            filtered = filter_plans_by_display_mode(plans, 111111)
            # Если plan_id отсутствует, то проверка использования не выполняется
            # и план должен пройти фильтрацию
            assert len(filtered) == 1, "План без plan_id должен быть виден (нет возможности проверить использование)"

    @allure.story("Edge cases")
    @allure.title("Пользователь без группы не видит планы с фильтрацией по группам")
    @allure.description("""
    Тест проверяет обработку пользователя без группы при фильтрации по группам.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("plan_display_mode", "edge_cases", "user_without_group", "database", "unit")
    def test_edge_cases_user_without_group(self, temp_db):
        """Пользователь без группы не видит планы с фильтрацией по группам"""
        import sqlite3
        
        with allure.step("Создаем тестовый хост"):
            with sqlite3.connect(temp_db) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO xui_hosts (host_name, host_url, host_username, host_pass, host_inbound_id, host_code) VALUES (?, ?, ?, ?, ?, ?)",
                    ("test-host", "https://test.example.com:8443", "admin", "password", 1, "test-code")
                )
                conn.commit()
        
        with allure.step("Создаем группу и план только для этой группы"):
            group_id = create_user_group("Эксклюзивная группа", "Описание", "exclusive")
            
            create_plan(
                host_name="test-host",
                plan_name="Эксклюзивный план",
                months=1,
                price=100.0,
                days=0,
                traffic_gb=0.0,
                hours=0,
                display_mode="all",
                display_mode_groups=[group_id]
            )
        
        with allure.step("Получаем созданный план"):
            with sqlite3.connect(temp_db) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM plans WHERE plan_name = 'Эксклюзивный план'")
                row = cursor.fetchone()
                columns = [desc[0] for desc in cursor.description]
                plan = dict(zip(columns, row))
                if plan.get('display_mode_groups'):
                    plan['display_mode_groups'] = json.loads(plan['display_mode_groups'])
        
        plans = [plan]
        
        with allure.step("Создаем пользователя без группы (удаляем группу или оставляем NULL)"):
            user = register_user_if_not_exists(111111, "no_group_user", None, "No Group User")
            # Убеждаемся, что у пользователя нет группы (или default)
            with sqlite3.connect(temp_db) as conn:
                cursor = conn.cursor()
                # Устанавливаем group_id в NULL
                cursor.execute("UPDATE users SET group_id = NULL WHERE telegram_id = ?", (111111,))
                conn.commit()
        
        with allure.step("Проверяем, что план скрыт у пользователя без группы"):
            filtered = filter_plans_by_display_mode(plans, 111111)
            assert len(filtered) == 0, "План должен быть скрыт у пользователя без группы"

    @allure.story("Комплексный сценарий")
    @allure.title("Комплексный сценарий с несколькими планами и пользователями")
    @allure.description("""
    Тест проверяет комплексный сценарий с несколькими планами и пользователями:
    - План 1: 'all', без групп
    - План 2: 'hidden_new', для группы VIP
    - План 3: 'hidden_old', для группы Regular
    - План 4: 'hidden_all', для группы VIP
    
    Проверяем фильтрацию для разных пользователей с разной историей.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("plan_display_mode", "complex_scenario", "multiple_plans", "database", "unit")
    def test_complex_scenario_multiple_plans(self, temp_db):
        """Комплексный сценарий с несколькими планами и пользователями"""
        import sqlite3
        
        with allure.step("Создаем тестовый хост"):
            with sqlite3.connect(temp_db) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO xui_hosts (host_name, host_url, host_username, host_pass, host_inbound_id, host_code) VALUES (?, ?, ?, ?, ?, ?)",
                    ("test-host", "https://test.example.com:8443", "admin", "password", 1, "test-code")
                )
                conn.commit()
        
        with allure.step("Создаем группы пользователей"):
            vip_group_id = create_user_group("VIP", "VIP пользователи", "vip")
            regular_group_id = create_user_group("Regular", "Обычные пользователи", "regular")
        
        with allure.step("Создаем планы с различными настройками"):
            # План 1: для всех, без групп
            create_plan("test-host", "План для всех", 1, 100.0, display_mode="all", display_mode_groups=None)
            
            # План 2: скрыт у новых, для VIP
            create_plan("test-host", "VIP план скрыт у новых", 1, 200.0, display_mode="hidden_new", display_mode_groups=[vip_group_id])
            
            # План 3: скрыт у старых, для Regular
            create_plan("test-host", "Regular план скрыт у старых", 1, 150.0, display_mode="hidden_old", display_mode_groups=[regular_group_id])
            
            # План 4: скрыт у всех, для VIP (тест приоритета)
            create_plan("test-host", "Скрытый VIP план", 1, 300.0, display_mode="hidden_all", display_mode_groups=[vip_group_id])
        
        with allure.step("Получаем все созданные планы"):
            with sqlite3.connect(temp_db) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM plans WHERE host_name = 'test-host' ORDER BY plan_id")
                rows = cursor.fetchall()
                columns = [desc[0] for desc in cursor.description]
                plans = []
                for row in rows:
                    plan = dict(zip(columns, row))
                    if plan.get('display_mode_groups'):
                        plan['display_mode_groups'] = json.loads(plan['display_mode_groups'])
                    plans.append(plan)
        
        with allure.step("Создаем пользователей с разной историей"):
            # VIP новый пользователь
            vip_new = register_user_if_not_exists(111111, "vip_new", None, "VIP New")
            with sqlite3.connect(temp_db) as conn:
                cursor = conn.cursor()
                cursor.execute("UPDATE users SET group_id = ? WHERE telegram_id = ?", (vip_group_id, 111111))
                conn.commit()
            
            # VIP старый пользователь (использовал план 2)
            vip_old = register_user_if_not_exists(222222, "vip_old", None, "VIP Old")
            with sqlite3.connect(temp_db) as conn:
                cursor = conn.cursor()
                cursor.execute("UPDATE users SET group_id = ? WHERE telegram_id = ?", (vip_group_id, 222222))
                # Создаем транзакцию для плана 2 (VIP план скрыт у новых)
                plan2_id = next(p['plan_id'] for p in plans if p['plan_name'] == "VIP план скрыт у новых")
                cursor.execute(
                    "INSERT INTO transactions (payment_id, user_id, status, amount_rub, metadata) VALUES (?, ?, ?, ?, ?)",
                    ("pay_vip_old", 222222, "paid", 200.0, json.dumps({"plan_id": plan2_id}))
                )
                conn.commit()
            
            # Regular новый пользователь
            regular_new = register_user_if_not_exists(333333, "regular_new", None, "Regular New")
            with sqlite3.connect(temp_db) as conn:
                cursor = conn.cursor()
                cursor.execute("UPDATE users SET group_id = ? WHERE telegram_id = ?", (regular_group_id, 333333))
                conn.commit()
        
        with allure.step("Проверяем фильтрацию для VIP нового пользователя"):
            filtered_vip_new = filter_plans_by_display_mode(plans, 111111)
            plan_names = [p['plan_name'] for p in filtered_vip_new]
            assert "План для всех" in plan_names, "VIP новый должен видеть план для всех"
            assert "VIP план скрыт у новых" not in plan_names, "VIP новый НЕ должен видеть план скрытый у новых"
            assert "VIP план скрыт у новых" not in plan_names, "План 2 должен быть скрыт"
            assert "Regular план скрыт у старых" not in plan_names, "Regular план должен быть скрыт (другая группа)"
            assert "Скрытый VIP план" not in plan_names, "Скрытый план не должен быть виден"
        
        with allure.step("Проверяем фильтрацию для VIP старого пользователя"):
            filtered_vip_old = filter_plans_by_display_mode(plans, 222222)
            plan_names = [p['plan_name'] for p in filtered_vip_old]
            assert "План для всех" in plan_names, "VIP старый должен видеть план для всех"
            assert "VIP план скрыт у новых" in plan_names, "VIP старый должен видеть план (он использовал его)"
            assert "Regular план скрыт у старых" not in plan_names, "Regular план должен быть скрыт (другая группа)"
            assert "Скрытый VIP план" not in plan_names, "Скрытый план не должен быть виден"
        
        with allure.step("Проверяем фильтрацию для Regular нового пользователя"):
            filtered_regular_new = filter_plans_by_display_mode(plans, 333333)
            plan_names = [p['plan_name'] for p in filtered_regular_new]
            assert "План для всех" in plan_names, "Regular новый должен видеть план для всех"
            assert "Regular план скрыт у старых" in plan_names, "Regular новый должен видеть план (он новый)"
            assert "VIP план скрыт у новых" not in plan_names, "VIP план должен быть скрыт (другая группа)"
            assert "Скрытый VIP план" not in plan_names, "Скрытый план не должен быть виден"
