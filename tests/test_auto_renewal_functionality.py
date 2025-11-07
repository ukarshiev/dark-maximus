#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Тесты для проверки функционала автопродления с баланса
"""

import pytest
import sqlite3
import tempfile
from pathlib import Path
import sys
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, patch

# Добавляем путь к src для импорта модулей
project_root = Path(__file__).parent.parent
src_path = project_root / "src"
sys.path.insert(0, str(src_path))

from shop_bot.data_manager import database


@pytest.fixture
def temp_db(tmp_path, monkeypatch):
    """Создает временную БД для тестов"""
    db_path = tmp_path / "test_users.db"
    
    # Создаем базовую структуру БД
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    
    # Создаем таблицу users
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            telegram_id INTEGER PRIMARY KEY,
            username TEXT,
            balance REAL DEFAULT 0,
            auto_renewal_enabled INTEGER DEFAULT 1
        )
    ''')
    
    # Создаем таблицу vpn_keys
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS vpn_keys (
            key_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            host_name TEXT,
            plan_name TEXT,
            price REAL,
            expiry_date TIMESTAMP,
            status TEXT DEFAULT 'active',
            FOREIGN KEY (user_id) REFERENCES users(telegram_id)
        )
    ''')
    
    # Создаем таблицу notifications
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS notifications (
            notification_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            username TEXT,
            type TEXT NOT NULL,
            title TEXT NOT NULL,
            message TEXT NOT NULL,
            status TEXT NOT NULL,
            meta TEXT,
            key_id INTEGER,
            marker_hours INTEGER,
            created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    conn.commit()
    conn.close()
    
    # Сохраняем оригинальный DB_FILE
    original_db_file = database.DB_FILE
    
    # Патчим DB_FILE для использования временной БД
    monkeypatch.setattr(database, 'DB_FILE', db_path)
    
    yield db_path
    
    # Восстанавливаем оригинальный DB_FILE
    monkeypatch.setattr(database, 'DB_FILE', original_db_file)


class TestAutoRenewalDatabase:
    """Тесты для функций работы с автопродлением в БД"""
    
    def test_get_auto_renewal_enabled_default(self, temp_db):
        """Тест 1: Получение статуса автопродления по умолчанию (True)"""
        # Создаем пользователя без явного указания auto_renewal_enabled
        conn = sqlite3.connect(str(temp_db))
        cursor = conn.cursor()
        cursor.execute("INSERT INTO users (telegram_id, username, balance) VALUES (?, ?, ?)", 
                      (123456789, "test_user", 100.0))
        conn.commit()
        conn.close()
        
        # Проверяем, что по умолчанию возвращается True
        result = database.get_auto_renewal_enabled(123456789)
        assert result is True, "По умолчанию автопродление должно быть включено"
    
    def test_get_auto_renewal_enabled_explicit(self, temp_db):
        """Тест 2: Получение явно установленного статуса автопродления"""
        conn = sqlite3.connect(str(temp_db))
        cursor = conn.cursor()
        cursor.execute("INSERT INTO users (telegram_id, username, balance, auto_renewal_enabled) VALUES (?, ?, ?, ?)", 
                      (123456789, "test_user", 100.0, 0))
        conn.commit()
        conn.close()
        
        # Проверяем, что возвращается False
        result = database.get_auto_renewal_enabled(123456789)
        assert result is False, "Автопродление должно быть отключено"
    
    def test_set_auto_renewal_enabled(self, temp_db):
        """Тест 3: Установка статуса автопродления"""
        # Создаем пользователя
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
        conn = sqlite3.connect(str(temp_db))
        cursor = conn.cursor()
        cursor.execute("SELECT auto_renewal_enabled FROM users WHERE telegram_id = ?", (123456789,))
        row = cursor.fetchone()
        conn.close()
        
        assert row[0] == 1, "auto_renewal_enabled должен быть 1 (включено)"
    
    def test_get_auto_renewal_enabled_missing_column(self, temp_db):
        """Тест 4: Обработка отсутствия колонки auto_renewal_enabled"""
        # Удаляем колонку для теста
        conn = sqlite3.connect(str(temp_db))
        cursor = conn.cursor()
        cursor.execute("ALTER TABLE users DROP COLUMN auto_renewal_enabled")
        conn.commit()
        conn.close()
        
        # Создаем пользователя
        conn = sqlite3.connect(str(temp_db))
        cursor = conn.cursor()
        cursor.execute("INSERT INTO users (telegram_id, username, balance) VALUES (?, ?, ?)", 
                      (123456789, "test_user", 100.0))
        conn.commit()
        conn.close()
        
        # Функция должна вернуть True по умолчанию даже если колонки нет
        result = database.get_auto_renewal_enabled(123456789)
        assert result is True, "При отсутствии колонки должно возвращаться True по умолчанию"


class TestAutoRenewalNotifications:
    """Тесты для уведомлений об автопродлении"""
    
    def test_balance_deduction_notification_logged(self, temp_db):
        """Тест 5: Логирование уведомления о списании баланса"""
        # Создаем пользователя
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
        conn = sqlite3.connect(str(temp_db))
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM notifications WHERE notification_id = ?", (notification_id,))
        result = cursor.fetchone()
        conn.close()
        
        assert result is not None, "Уведомление должно быть в БД"
        assert result[3] == "balance_deduction", "Тип уведомления должен быть balance_deduction"
    
    def test_autorenew_disabled_notification_logged(self, temp_db):
        """Тест 6: Логирование уведомления об отключенном автопродлении"""
        # Создаем пользователя
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
        conn = sqlite3.connect(str(temp_db))
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM notifications WHERE notification_id = ?", (notification_id,))
        result = cursor.fetchone()
        conn.close()
        
        assert result is not None, "Уведомление должно быть в БД"
        assert result[3] == "subscription_autorenew_disabled", "Тип уведомления должен быть subscription_autorenew_disabled"


class TestAutoRenewalIntegration:
    """Интеграционные тесты автопродления"""
    
    def test_autorenewal_skipped_when_disabled(self, temp_db):
        """Тест 7: Автопродление пропускается, когда отключено"""
        # Создаем пользователя с отключенным автопродлением
        conn = sqlite3.connect(str(temp_db))
        cursor = conn.cursor()
        cursor.execute("INSERT INTO users (telegram_id, username, balance, auto_renewal_enabled) VALUES (?, ?, ?, ?)", 
                      (123456789, "test_user", 100.0, 0))
        conn.commit()
        conn.close()
        
        # Создаем ключ, который истекает через час
        expiry_date = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(hours=1)
        conn = sqlite3.connect(str(temp_db))
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO vpn_keys (user_id, host_name, plan_name, price, expiry_date, status)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (123456789, "Тестовый сервер", "Тестовый тариф", 50.0, expiry_date, "active"))
        conn.commit()
        conn.close()
        
        # Проверяем, что функция get_auto_renewal_enabled работает корректно
        result = database.get_auto_renewal_enabled(123456789)
        assert result is False, "Автопродление должно быть отключено"
        
        # Проверяем, что можно включить обратно
        database.set_auto_renewal_enabled(123456789, True)
        result = database.get_auto_renewal_enabled(123456789)
        assert result is True, "Автопродление должно быть включено"
    
    def test_autorenewal_enabled_by_default(self, temp_db):
        """Тест 8: Автопродление включено по умолчанию для новых пользователей"""
        # Создаем нового пользователя без указания auto_renewal_enabled
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

