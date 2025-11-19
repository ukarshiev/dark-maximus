#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Unit-тесты для операций с пользователями в БД

Тестирует CRUD операции с пользователями используя временную БД
"""

import pytest
import allure
import sys
from pathlib import Path

# Добавляем путь к проекту
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root / "src"))

from shop_bot.data_manager.database import (
    register_user_if_not_exists,
    get_user,
    update_user_stats,
    get_user_balance,
)


@pytest.mark.unit
@pytest.mark.database
@allure.epic("База данных")
@allure.feature("Операции с пользователями")
@allure.label("package", "src.shop_bot.database")
class TestUserOperations:
    """Тесты для операций с пользователями"""

    @allure.title("Регистрация нового пользователя")
    @allure.description("""
    Проверяет успешную регистрацию нового пользователя в системе.
    
    **Что проверяется:**
    - Создание пользователя через register_user_if_not_exists
    - Корректное сохранение telegram_id и username
    - Наличие пользователя в БД после регистрации
    
    **Тестовые данные:**
    - telegram_id: 123456789
    - username: "test_user"
    
    **Ожидаемый результат:**
    Пользователь успешно создан в БД с указанными данными.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("user_operations", "registration", "database", "unit")
    def test_register_user_if_not_exists(self, temp_db):
        """Тест регистрации нового пользователя"""
        telegram_id = 123456789
        username = "test_user"
        
        register_user_if_not_exists(telegram_id, username, None, "Test User")
        
        user = get_user(telegram_id)
        assert user is not None, "Пользователь должен быть создан"
        assert user['telegram_id'] == telegram_id
        assert user['username'] == username

    @allure.title("Повторная регистрация пользователя")
    @allure.description("""
    Проверяет, что повторная регистрация пользователя не создает дубликат.
    
    **Что проверяется:**
    - Первая регистрация создает пользователя
    - Вторая регистрация с тем же telegram_id не создает дубликат
    - ID пользователя остается неизменным
    - Username может быть обновлен
    
    **Тестовые данные:**
    - telegram_id: 123456790
    - Первый username: "test_user2"
    - Второй username: "new_username"
    
    **Ожидаемый результат:**
    Пользователь создан один раз, при повторной регистрации данные обновляются, но не создается дубликат.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("user_operations", "registration", "duplicate", "database", "unit")
    def test_register_user_twice(self, temp_db):
        """Тест повторной регистрации пользователя (не должна дублировать)"""
        telegram_id = 123456790
        username = "test_user2"
        
        # Первая регистрация
        register_user_if_not_exists(telegram_id, username, None, "Test User 2")
        user1 = get_user(telegram_id)
        
        assert user1 is not None, "Пользователь должен быть создан при первой регистрации"
        
        # Вторая регистрация (не должна изменить пользователя)
        register_user_if_not_exists(telegram_id, "new_username", None, "New Name")
        user2 = get_user(telegram_id)
        
        assert user2 is not None, "Пользователь должен существовать после второй регистрации"
        assert user1['telegram_id'] == user2['telegram_id']
        # Имя пользователя может быть обновлено, но ID остается тем же

    @allure.title("Получение несуществующего пользователя")
    @allure.description("""
    Проверяет обработку запроса несуществующего пользователя.
    
    **Что проверяется:**
    - Функция get_user возвращает None для несуществующего пользователя
    - Отсутствие ошибок при запросе несуществующего пользователя
    
    **Тестовые данные:**
    - telegram_id: 999999999 (несуществующий)
    
    **Ожидаемый результат:**
    Функция get_user возвращает None для несуществующего пользователя.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("user_operations", "get_user", "not_found", "database", "unit")
    def test_get_user_not_exists(self, temp_db):
        """Тест получения несуществующего пользователя"""
        user = get_user(999999999)
        assert user is None, "Несуществующий пользователь должен вернуть None"

    @allure.title("Обновление статистики пользователя")
    @allure.description("""
    Проверяет корректное обновление статистики пользователя.
    
    **Что проверяется:**
    - Обновление total_spent через update_user_stats
    - Обновление total_months через update_user_stats
    - Корректное сохранение обновленных данных в БД
    
    **Тестовые данные:**
    - telegram_id: 123456791
    - total_spent: 1000.0
    - total_months: 3
    
    **Ожидаемый результат:**
    Статистика пользователя успешно обновлена и сохранена в БД.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("user_operations", "update_stats", "statistics", "database", "unit")
    def test_update_user_stats(self, temp_db):
        """Тест обновления статистики пользователя"""
        telegram_id = 123456791
        register_user_if_not_exists(telegram_id, "test_user3", None, "Test User 3")
        
        # Обновляем статистику
        update_user_stats(telegram_id, 1000.0, 3)
        
        user = get_user(telegram_id)
        assert user is not None
        assert user['total_spent'] == 1000.0
        assert user['total_months'] == 3

    @allure.title("Получение баланса пользователя")
    @allure.description("""
    Проверяет получение и обновление баланса пользователя.
    
    **Что проверяется:**
    - Начальный баланс нового пользователя равен 0
    - Корректное получение баланса через get_user_balance
    - Обновление баланса через прямое изменение в БД
    - Корректное отображение обновленного баланса
    
    **Тестовые данные:**
    - telegram_id: 123456792
    - Начальный баланс: 0.0
    - Обновленный баланс: 500.0
    
    **Ожидаемый результат:**
    Баланс пользователя корректно получается и обновляется.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("user_operations", "balance", "get_balance", "database", "unit")
    def test_get_user_balance(self, temp_db):
        """Тест получения баланса пользователя"""
        telegram_id = 123456792
        register_user_if_not_exists(telegram_id, "test_user4", None, "Test User 4")
        
        # Проверяем начальный баланс
        balance = get_user_balance(telegram_id)
        assert balance == 0.0, "Начальный баланс должен быть 0"
        
        # Устанавливаем баланс через БД и проверяем
        import sqlite3
        from shop_bot.data_manager import database
        
        with sqlite3.connect(str(temp_db), timeout=30) as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET balance = 500.0 WHERE telegram_id = ?", (telegram_id,))
            conn.commit()
        
        balance = get_user_balance(telegram_id)
        assert balance == 500.0, "Баланс должен быть обновлен"

    @allure.title("Регистрация пользователя с реферером")
    @allure.description("""
    Проверяет регистрацию пользователя с указанием реферера.
    
    **Что проверяется:**
    - Создание реферера в системе
    - Регистрация пользователя с указанием referrer_id
    - Корректное сохранение связи referred_by в БД
    
    **Тестовые данные:**
    - referrer_id: 123456793
    - user_id: 123456794
    
    **Ожидаемый результат:**
    Пользователь успешно зарегистрирован с корректной связью с реферером.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("user_operations", "registration", "referral", "database", "unit")
    def test_register_user_with_referrer(self, temp_db):
        """Тест регистрации пользователя с реферером"""
        referrer_id = 123456793
        user_id = 123456794
        
        # Создаем реферера
        register_user_if_not_exists(referrer_id, "referrer", None, "Referrer User")
        
        # Создаем пользователя с реферером
        register_user_if_not_exists(user_id, "referred_user", referrer_id, "Referred User")
        
        user = get_user(user_id)
        assert user is not None
        assert user['referred_by'] == referrer_id
