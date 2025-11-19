#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Тесты для проверки функционала автопродления с баланса
"""

import pytest
import allure
import sqlite3
import tempfile
from pathlib import Path
import sys
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, patch

# Добавляем путь к src для импорта модулей
project_root = Path(__file__).parent.parent.parent.parent
src_path = project_root / "src"
sys.path.insert(0, str(src_path))

from shop_bot.data_manager import database


@pytest.mark.unit
@pytest.mark.database
@allure.epic("База данных")
@allure.feature("Автопродление")
@allure.label("package", "src.shop_bot.database")
class TestAutoRenewalDatabase:
    """Тесты для функций работы с автопродлением в БД"""
    
    @allure.title("Получение статуса автопродления по умолчанию (True)")
    @allure.description("""
    Проверяет, что функция get_auto_renewal_enabled возвращает True по умолчанию для новых пользователей.
    
    **Что проверяется:**
    - Создание пользователя без явного указания auto_renewal_enabled
    - Корректная работа функции get_auto_renewal_enabled для нового пользователя
    
    **Тестовые данные:**
    - user_id: 123456789
    - username: "test_user"
    - balance: 100.0
    - auto_renewal_enabled: не указан (должен быть True по умолчанию)
    
    **Ожидаемый результат:**
    - Функция get_auto_renewal_enabled возвращает True для нового пользователя
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("auto_renewal", "default_value", "unit", "database")
    def test_get_auto_renewal_enabled_default(self, temp_db):
        """Тест 1: Получение статуса автопродления по умолчанию (True)"""
        # Создаем пользователя без явного указания auto_renewal_enabled
        # Используем temp_db напрямую, а не database.DB_FILE, чтобы гарантировать использование правильной тестовой БД
        conn = sqlite3.connect(str(temp_db))
        cursor = conn.cursor()
        cursor.execute("INSERT INTO users (telegram_id, username, balance) VALUES (?, ?, ?)", 
                      (123456789, "test_user", 100.0))
        conn.commit()
        conn.close()
        
        # Проверяем, что по умолчанию возвращается True
        result = database.get_auto_renewal_enabled(123456789)
        assert result is True, "По умолчанию автопродление должно быть включено"
    
    @allure.title("Получение явно установленного статуса автопродления")
    @allure.description("""
    Проверяет, что функция get_auto_renewal_enabled корректно возвращает явно установленное значение.
    
    **Что проверяется:**
    - Создание пользователя с явно отключенным автопродлением (auto_renewal_enabled = 0)
    - Корректная работа функции get_auto_renewal_enabled для пользователя с отключенным автопродлением
    
    **Тестовые данные:**
    - user_id: 123456789
    - username: "test_user"
    - balance: 100.0
    - auto_renewal_enabled: 0 (отключено)
    
    **Ожидаемый результат:**
    - Функция get_auto_renewal_enabled возвращает False для пользователя с отключенным автопродлением
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("auto_renewal", "explicit_value", "unit", "database")
    def test_get_auto_renewal_enabled_explicit(self, temp_db):
        """Тест 2: Получение явно установленного статуса автопродления"""
        # Используем temp_db напрямую, а не database.DB_FILE, чтобы гарантировать использование правильной тестовой БД
        conn = sqlite3.connect(str(temp_db))
        cursor = conn.cursor()
        cursor.execute("INSERT INTO users (telegram_id, username, balance, auto_renewal_enabled) VALUES (?, ?, ?, ?)", 
                      (123456789, "test_user", 100.0, 0))
        conn.commit()
        conn.close()
        
        # Проверяем, что возвращается False
        result = database.get_auto_renewal_enabled(123456789)
        assert result is False, "Автопродление должно быть отключено"
    
    @allure.title("Установка статуса автопродления")
    @allure.description("""
    Проверяет, что функция set_auto_renewal_enabled корректно устанавливает статус автопродления.
    
    **Что проверяется:**
    - Создание пользователя
    - Отключение автопродления через set_auto_renewal_enabled
    - Включение автопродления обратно через set_auto_renewal_enabled
    - Проверка изменений в БД
    
    **Тестовые данные:**
    - user_id: 123456789
    - username: "test_user"
    - balance: 100.0
    
    **Ожидаемый результат:**
    - set_auto_renewal_enabled возвращает True при успешной установке
    - Значение в БД корректно обновляется (0 для отключено, 1 для включено)
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("auto_renewal", "set_value", "unit", "database")
    def test_set_auto_renewal_enabled(self, temp_db):
        """Тест 3: Установка статуса автопродления"""
        # Создаем пользователя
        # Используем temp_db напрямую, а не database.DB_FILE, чтобы гарантировать использование правильной тестовой БД
        conn = sqlite3.connect(str(temp_db))
        cursor = conn.cursor()
        cursor.execute("INSERT INTO users (telegram_id, username, balance) VALUES (?, ?, ?)", 
                      (123456789, "test_user", 100.0))
        conn.commit()
        conn.close()
        
        # Отключаем автопродление
        result = database.set_auto_renewal_enabled(123456789, False)
        assert result is True, "set_auto_renewal_enabled должна вернуть True"
        
        # Проверяем в БД
        # Используем temp_db напрямую, а не database.DB_FILE, чтобы гарантировать использование правильной тестовой БД
        conn = sqlite3.connect(str(temp_db))
        cursor = conn.cursor()
        cursor.execute("SELECT auto_renewal_enabled FROM users WHERE telegram_id = ?", (123456789,))
        row = cursor.fetchone()
        conn.close()
        
        assert row is not None, "Пользователь должен существовать"
        assert row[0] == 0, "auto_renewal_enabled должен быть 0 (отключено)"
        
        # Включаем обратно
        result = database.set_auto_renewal_enabled(123456789, True)
        assert result is True
        
        # Проверяем в БД
        # Используем temp_db напрямую, а не database.DB_FILE, чтобы гарантировать использование правильной тестовой БД
        conn = sqlite3.connect(str(temp_db))
        cursor = conn.cursor()
        cursor.execute("SELECT auto_renewal_enabled FROM users WHERE telegram_id = ?", (123456789,))
        row = cursor.fetchone()
        conn.close()
        
        assert row[0] == 1, "auto_renewal_enabled должен быть 1 (включено)"
    
    @allure.title("Обработка отсутствия колонки auto_renewal_enabled")
    @allure.description("""
    Проверяет, что функция get_auto_renewal_enabled корректно обрабатывает отсутствие колонки в БД.
    
    **Что проверяется:**
    - Удаление колонки auto_renewal_enabled из таблицы users
    - Создание пользователя после удаления колонки
    - Корректная работа функции get_auto_renewal_enabled при отсутствии колонки
    
    **Тестовые данные:**
    - user_id: 123456789
    - username: "test_user"
    - balance: 100.0
    
    **Ожидаемый результат:**
    - Функция get_auto_renewal_enabled возвращает True по умолчанию даже если колонки нет
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("auto_renewal", "missing_column", "unit", "database", "error_handling")
    def test_get_auto_renewal_enabled_missing_column(self, temp_db):
        """Тест 4: Обработка отсутствия колонки auto_renewal_enabled"""
        # Удаляем колонку для теста
        # Используем temp_db напрямую, а не database.DB_FILE, чтобы гарантировать использование правильной тестовой БД
        conn = sqlite3.connect(str(temp_db))
        cursor = conn.cursor()
        cursor.execute("ALTER TABLE users DROP COLUMN auto_renewal_enabled")
        conn.commit()
        conn.close()
        
        # Создаем пользователя
        # Используем temp_db напрямую, а не database.DB_FILE, чтобы гарантировать использование правильной тестовой БД
        conn = sqlite3.connect(str(temp_db))
        cursor = conn.cursor()
        cursor.execute("INSERT INTO users (telegram_id, username, balance) VALUES (?, ?, ?)", 
                      (123456789, "test_user", 100.0))
        conn.commit()
        conn.close()
        
        # Функция должна вернуть True по умолчанию даже если колонки нет
        result = database.get_auto_renewal_enabled(123456789)
        assert result is True, "При отсутствии колонки должно возвращаться True по умолчанию"


@pytest.mark.unit
@pytest.mark.database
@allure.epic("База данных")
@allure.feature("Автопродление")
class TestAutoRenewalNotifications:
    """Тесты для уведомлений об автопродлении"""
    
    @allure.title("Логирование уведомления о списании баланса")
    @allure.description("""
    Проверяет, что уведомление о списании баланса корректно логируется в БД.
    
    **Что проверяется:**
    - Создание пользователя
    - Логирование уведомления типа balance_deduction через log_notification
    - Корректное сохранение уведомления в БД
    
    **Тестовые данные:**
    - user_id: 123456789
    - username: "test_user"
    - balance: 100.0
    - notif_type: "balance_deduction"
    - key_id: 1
    - amount: 50.0
    
    **Ожидаемый результат:**
    - Уведомление успешно записывается в БД (notification_id > 0)
    - Тип уведомления в БД соответствует "balance_deduction"
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("auto_renewal", "notifications", "balance_deduction", "unit", "database")
    def test_balance_deduction_notification_logged(self, temp_db):
        """Тест 5: Логирование уведомления о списании баланса"""
        # Создаем пользователя
        # Используем temp_db напрямую, а не database.DB_FILE, чтобы гарантировать использование правильной тестовой БД
        conn = sqlite3.connect(str(temp_db))
        cursor = conn.cursor()
        cursor.execute("INSERT INTO users (telegram_id, username, balance) VALUES (?, ?, ?)", 
                      (123456789, "test_user", 100.0))
        conn.commit()
        conn.close()
        
        # Логируем уведомление о списании
        notification_id = database.log_notification(
            user_id=123456789,
            username="test_user",
            notif_type="balance_deduction",
            title="Списание баланса",
            message="Произошло списание 50.00 RUB по тарифу Тестовый тариф на сервере Тестовый сервер.",
            status="sent",
            meta={"key_id": 1, "amount": 50.0, "plan_name": "Тестовый тариф", "host_name": "Тестовый сервер"},
            key_id=1
        )
        
        assert notification_id > 0, "Уведомление должно быть записано"
        
        # Проверяем в БД
        # Используем temp_db напрямую, а не database.DB_FILE, чтобы гарантировать использование правильной тестовой БД
        conn = sqlite3.connect(str(temp_db))
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM notifications WHERE notification_id = ?", (notification_id,))
        result = cursor.fetchone()
        conn.close()
        
        assert result is not None, "Уведомление должно быть в БД"
        assert result[3] == "balance_deduction", "Тип уведомления должен быть balance_deduction"
    
    @allure.title("Логирование уведомления об отключенном автопродлении")
    @allure.description("""
    Проверяет, что уведомление об отключенном автопродлении корректно логируется в БД.
    
    **Что проверяется:**
    - Создание пользователя с отключенным автопродлением
    - Логирование уведомления типа subscription_autorenew_disabled через log_notification
    - Корректное сохранение уведомления в БД
    
    **Тестовые данные:**
    - user_id: 123456789
    - username: "test_user"
    - balance: 100.0
    - auto_renewal_enabled: 0 (отключено)
    - notif_type: "subscription_autorenew_disabled"
    - key_id: 1
    - marker_hours: 24
    
    **Ожидаемый результат:**
    - Уведомление успешно записывается в БД (notification_id > 0)
    - Тип уведомления в БД соответствует "subscription_autorenew_disabled"
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("auto_renewal", "notifications", "subscription_autorenew_disabled", "unit", "database")
    def test_autorenew_disabled_notification_logged(self, temp_db):
        """Тест 6: Логирование уведомления об отключенном автопродлении"""
        # Создаем пользователя
        # Используем temp_db напрямую, а не database.DB_FILE, чтобы гарантировать использование правильной тестовой БД
        conn = sqlite3.connect(str(temp_db))
        cursor = conn.cursor()
        cursor.execute("INSERT INTO users (telegram_id, username, balance, auto_renewal_enabled) VALUES (?, ?, ?, ?)", 
                      (123456789, "test_user", 100.0, 0))
        conn.commit()
        conn.close()
        
        # Логируем уведомление об отключенном автопродлении
        notification_id = database.log_notification(
            user_id=123456789,
            username="test_user",
            notif_type="subscription_autorenew_disabled",
            title="Автопродление отключено",
            message="Вы отключили 'Автопродление с баланса' и списание не произойдет.",
            status="sent",
            meta={"key_id": 1, "time_left_hours": 24, "balance": 100.0, "price_to_renew": 50.0},
            key_id=1,
            marker_hours=24
        )
        
        assert notification_id > 0, "Уведомление должно быть записано"
        
        # Проверяем в БД
        # Используем temp_db напрямую, а не database.DB_FILE, чтобы гарантировать использование правильной тестовой БД
        conn = sqlite3.connect(str(temp_db))
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM notifications WHERE notification_id = ?", (notification_id,))
        result = cursor.fetchone()
        conn.close()
        
        assert result is not None, "Уведомление должно быть в БД"
        assert result[3] == "subscription_autorenew_disabled", "Тип уведомления должен быть subscription_autorenew_disabled"


@pytest.mark.unit
@pytest.mark.database
@allure.epic("База данных")
@allure.feature("Автопродление")
class TestAutoRenewalIntegration:
    """Интеграционные тесты автопродления"""
    
    @allure.title("Автопродление пропускается, когда отключено у пользователя")
    @allure.description("""
    Проверяет, что автопродление корректно пропускается, когда оно отключено у пользователя.
    
    **Что проверяется:**
    - Создание пользователя с отключенным автопродлением (auto_renewal_enabled = 0)
    - Создание ключа для пользователя
    - Корректная работа функции get_auto_renewal_enabled при отключенном автопродлении
    - Возможность включения автопродления обратно через set_auto_renewal_enabled
    
    **Тестовые данные:**
    - user_id: 123456789
    - username: "test_user"
    - balance: 100.0
    - auto_renewal_enabled: 0 (отключено)
    - host_name: "Тестовый сервер"
    - plan_name: "Тестовый тариф"
    - price: 50.0
    - xui_client_uuid: "test-uuid-123"
    - key_email: "test@example.com"
    
    **Ожидаемый результат:**
    - Функция get_auto_renewal_enabled возвращает False для пользователя с отключенным автопродлением
    - После включения автопродления функция возвращает True
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("auto_renewal", "user_settings", "unit", "database")
    def test_autorenewal_skipped_when_disabled(self, temp_db):
        """Тест 7: Автопродление пропускается, когда отключено"""
        with allure.step("Подготовка тестовых данных: создание пользователя с отключенным автопродлением"):
            # Создаем пользователя с отключенным автопродлением
            # Используем temp_db напрямую, а не database.DB_FILE, чтобы гарантировать использование правильной тестовой БД
            conn = sqlite3.connect(str(temp_db))
            cursor = conn.cursor()
            cursor.execute("INSERT INTO users (telegram_id, username, balance, auto_renewal_enabled) VALUES (?, ?, ?, ?)", 
                          (123456789, "test_user", 100.0, 0))
            conn.commit()
            conn.close()
            allure.attach("123456789", "User ID", allure.attachment_type.TEXT)
        
        with allure.step("Создание ключа для пользователя"):
            # Создаем ключ, который истекает через час
            expiry_date = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(hours=1)
            allure.attach(str(expiry_date), "Expiry Date", allure.attachment_type.TEXT)
            # Используем temp_db напрямую, а не database.DB_FILE, чтобы гарантировать использование правильной тестовой БД
            conn = sqlite3.connect(str(temp_db))
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO vpn_keys (user_id, host_name, xui_client_uuid, key_email, plan_name, price, expiry_date, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (123456789, "Тестовый сервер", "test-uuid-123", "test@example.com", "Тестовый тариф", 50.0, expiry_date, "active"))
            conn.commit()
            conn.close()
        
        with allure.step("Проверка статуса автопродления: должно быть отключено"):
            # Проверяем, что функция get_auto_renewal_enabled работает корректно
            result = database.get_auto_renewal_enabled(123456789)
            allure.attach(str(result), "Результат get_auto_renewal_enabled", allure.attachment_type.TEXT)
            assert result is False, "Автопродление должно быть отключено"
        
        with allure.step("Включение автопродления и проверка изменения статуса"):
            # Проверяем, что можно включить обратно
            database.set_auto_renewal_enabled(123456789, True)
            result = database.get_auto_renewal_enabled(123456789)
            allure.attach(str(result), "Результат get_auto_renewal_enabled после включения", allure.attachment_type.TEXT)
            assert result is True, "Автопродление должно быть включено"
    
    @allure.title("Автопродление включено по умолчанию для новых пользователей")
    @allure.description("""
    Проверяет, что автопродление включено по умолчанию для новых пользователей.
    
    **Что проверяется:**
    - Создание нового пользователя без указания auto_renewal_enabled
    - Корректная работа функции get_auto_renewal_enabled для нового пользователя
    
    **Тестовые данные:**
    - user_id: 123456789
    - username: "new_user"
    - balance: 0.0
    - auto_renewal_enabled: не указан (должен быть True по умолчанию)
    
    **Ожидаемый результат:**
    - Функция get_auto_renewal_enabled возвращает True для нового пользователя
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("auto_renewal", "default_value", "new_user", "unit", "database")
    def test_autorenewal_enabled_by_default(self, temp_db):
        """Тест 8: Автопродление включено по умолчанию для новых пользователей"""
        # Создаем нового пользователя без указания auto_renewal_enabled
        # Используем temp_db напрямую, а не database.DB_FILE, чтобы гарантировать использование правильной тестовой БД
        conn = sqlite3.connect(str(temp_db))
        cursor = conn.cursor()
        cursor.execute("INSERT INTO users (telegram_id, username, balance) VALUES (?, ?, ?)", 
                      (123456789, "new_user", 0.0))
        conn.commit()
        conn.close()
        
        # Проверяем статус
        result = database.get_auto_renewal_enabled(123456789)
        assert result is True, "Новые пользователи должны иметь автопродление включенным по умолчанию"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

