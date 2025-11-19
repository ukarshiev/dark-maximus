#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Unit-тесты для операций с ключами в БД

Тестирует CRUD операции с ключами используя временную БД
"""

import pytest
import allure
import sys
from pathlib import Path
from datetime import datetime, timezone, timedelta
import uuid

# Добавляем путь к проекту
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root / "src"))

from shop_bot.data_manager.database import (
    create_key_with_stats_atomic,
    add_new_key,
    get_key_by_id,
    get_key_by_email,
    get_user_keys,
    update_key_info,
    delete_key_by_email,
    get_next_key_number,
    register_user_if_not_exists,
)


@pytest.mark.unit
@pytest.mark.database
@allure.epic("База данных")
@allure.feature("Операции с ключами")
@allure.label("package", "src.shop_bot.database")
class TestKeyOperations:
    """Тесты для операций с ключами"""

    @allure.title("Создание ключа")
    @allure.description("""
    Проверяет успешное создание ключа в системе.
    
    **Что проверяется:**
    - Создание ключа через create_key_with_stats_atomic
    - Корректное сохранение всех параметров ключа (user_id, key_email, xui_client_uuid, host_name)
    - Наличие ключа в БД после создания
    
    **Тестовые данные:**
    - user_id: 123456789
    - host_name: из sample_host
    - amount_spent: 100.0
    - months_purchased: 1
    
    **Ожидаемый результат:**
    Ключ успешно создан в БД со всеми указанными параметрами.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("key_operations", "create_key", "database", "unit")
    def test_create_key(self, temp_db, sample_host):
        """Тест создания ключа"""
        # Создаем пользователя
        user_id = 123456789
        register_user_if_not_exists(user_id, "test_user", None, "Test User")
        
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
        
        # Создаем ключ
        xui_client_uuid = str(uuid.uuid4())
        key_email = f"test_{uuid.uuid4().hex[:8]}@example.com"
        expiry_timestamp_ms = int((datetime.now(timezone.utc) + timedelta(days=30)).timestamp() * 1000)
        
        key_id = create_key_with_stats_atomic(
            user_id=user_id,
            host_name=sample_host['host_name'],
            xui_client_uuid=xui_client_uuid,
            key_email=key_email,
            expiry_timestamp_ms=expiry_timestamp_ms,
            amount_spent=100.0,
            months_purchased=1,
            plan_name="Test Plan",
            price=100.0
        )
        
        assert key_id is not None, "Ключ должен быть создан"
        
        # Проверяем ключ
        key = get_key_by_id(key_id)
        assert key is not None, "Ключ должен быть найден по ID"
        assert key['user_id'] == user_id
        assert key['key_email'] == key_email
        assert key['xui_client_uuid'] == xui_client_uuid
        assert key['host_name'] == sample_host['host_name']

    @allure.title("Получение ключа по ID")
    @allure.description("""
    Проверяет получение ключа по его идентификатору.
    
    **Что проверяется:**
    - Получение существующего ключа по key_id
    - Корректность данных полученного ключа
    - Обработка запроса несуществующего ключа (возврат None)
    
    **Тестовые данные:**
    - user_id: 123456790
    - Несуществующий key_id: 999999
    
    **Ожидаемый результат:**
    Существующий ключ успешно получен, несуществующий ключ возвращает None.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("key_operations", "get_key", "database", "unit")
    def test_get_key_by_id(self, temp_db, sample_host):
        """Тест получения ключа по ID"""
        # Создаем пользователя
        user_id = 123456790
        register_user_if_not_exists(user_id, "test_user2", None, "Test User 2")
        
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
        
        # Создаем ключ
        xui_client_uuid = str(uuid.uuid4())
        key_email = f"test_{uuid.uuid4().hex[:8]}@example.com"
        expiry_timestamp_ms = int((datetime.now(timezone.utc) + timedelta(days=30)).timestamp() * 1000)
        
        key_id = create_key_with_stats_atomic(
            user_id=user_id,
            host_name=sample_host['host_name'],
            xui_client_uuid=xui_client_uuid,
            key_email=key_email,
            expiry_timestamp_ms=expiry_timestamp_ms,
            amount_spent=100.0,
            months_purchased=1
        )
        
        # Получаем ключ по ID
        key = get_key_by_id(key_id)
        assert key is not None, "Ключ должен быть найден по ID"
        assert key['key_id'] == key_id
        assert key['key_email'] == key_email
        
        # Проверяем несуществующий ключ
        non_existent_key = get_key_by_id(999999)
        assert non_existent_key is None, "Несуществующий ключ должен вернуть None"

    @allure.title("Получение ключа по email")
    @allure.description("""
    Проверяет получение ключа по его email адресу.
    
    **Что проверяется:**
    - Получение существующего ключа по key_email
    - Корректность данных полученного ключа
    - Обработка запроса несуществующего email (возврат None)
    
    **Тестовые данные:**
    - user_id: 123456791
    - Несуществующий email: "nonexistent@example.com"
    
    **Ожидаемый результат:**
    Существующий ключ успешно получен по email, несуществующий email возвращает None.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("key_operations", "get_key", "email", "database", "unit")
    def test_get_key_by_email(self, temp_db, sample_host):
        """Тест получения ключа по email"""
        # Создаем пользователя
        user_id = 123456791
        register_user_if_not_exists(user_id, "test_user3", None, "Test User 3")
        
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
        
        # Создаем ключ
        xui_client_uuid = str(uuid.uuid4())
        key_email = f"test_{uuid.uuid4().hex[:8]}@example.com"
        expiry_timestamp_ms = int((datetime.now(timezone.utc) + timedelta(days=30)).timestamp() * 1000)
        
        key_id = create_key_with_stats_atomic(
            user_id=user_id,
            host_name=sample_host['host_name'],
            xui_client_uuid=xui_client_uuid,
            key_email=key_email,
            expiry_timestamp_ms=expiry_timestamp_ms,
            amount_spent=100.0,
            months_purchased=1
        )
        
        # Получаем ключ по email
        key = get_key_by_email(key_email)
        assert key is not None, "Ключ должен быть найден по email"
        assert key['key_id'] == key_id
        assert key['key_email'] == key_email
        
        # Проверяем несуществующий email
        non_existent_key = get_key_by_email("nonexistent@example.com")
        assert non_existent_key is None, "Несуществующий email должен вернуть None"

    @allure.title("Получение всех ключей пользователя")
    @allure.description("""
    Проверяет получение списка всех ключей пользователя.
    
    **Что проверяется:**
    - Получение всех ключей пользователя через get_user_keys
    - Корректность количества ключей в списке
    - Наличие всех созданных ключей в списке
    - Обработка пользователя без ключей (пустой список)
    
    **Тестовые данные:**
    - user_id: 123456792
    - Количество созданных ключей: 2
    - empty_user_id: 999999999
    
    **Ожидаемый результат:**
    Список содержит все созданные ключи пользователя, для пользователя без ключей возвращается пустой список.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("key_operations", "get_user_keys", "database", "unit")
    def test_get_user_keys(self, temp_db, sample_host):
        """Тест получения всех ключей пользователя"""
        # Создаем пользователя
        user_id = 123456792
        register_user_if_not_exists(user_id, "test_user4", None, "Test User 4")
        
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
        
        # Создаем несколько ключей
        expiry_timestamp_ms = int((datetime.now(timezone.utc) + timedelta(days=30)).timestamp() * 1000)
        
        key1_id = create_key_with_stats_atomic(
            user_id=user_id,
            host_name=sample_host['host_name'],
            xui_client_uuid=str(uuid.uuid4()),
            key_email=f"test1_{uuid.uuid4().hex[:8]}@example.com",
            expiry_timestamp_ms=expiry_timestamp_ms,
            amount_spent=100.0,
            months_purchased=1
        )
        
        key2_id = create_key_with_stats_atomic(
            user_id=user_id,
            host_name=sample_host['host_name'],
            xui_client_uuid=str(uuid.uuid4()),
            key_email=f"test2_{uuid.uuid4().hex[:8]}@example.com",
            expiry_timestamp_ms=expiry_timestamp_ms,
            amount_spent=100.0,
            months_purchased=1
        )
        
        # Получаем все ключи пользователя
        keys = get_user_keys(user_id)
        assert len(keys) == 2, "Должно быть 2 ключа"
        assert any(k['key_id'] == key1_id for k in keys), "Ключ 1 должен быть в списке"
        assert any(k['key_id'] == key2_id for k in keys), "Ключ 2 должен быть в списке"
        
        # Проверяем пользователя без ключей
        empty_user_id = 999999999
        register_user_if_not_exists(empty_user_id, "empty_user", None, "Empty User")
        empty_keys = get_user_keys(empty_user_id)
        assert len(empty_keys) == 0, "У пользователя без ключей должен быть пустой список"

    @allure.title("Обновление информации о ключе")
    @allure.description("""
    Проверяет обновление информации о ключе (UUID, expiry, subscription_link).
    
    **Что проверяется:**
    - Обновление xui_client_uuid через update_key_info
    - Обновление expiry_timestamp_ms
    - Обновление subscription_link
    - Корректное сохранение обновленных данных в БД
    
    **Тестовые данные:**
    - user_id: 123456793
    - Новый expiry: +60 дней от текущего момента
    
    **Ожидаемый результат:**
    Информация о ключе успешно обновлена и сохранена в БД.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("key_operations", "update_key", "database", "unit")
    def test_update_key_info(self, temp_db, sample_host):
        """Тест обновления информации о ключе"""
        # Создаем пользователя
        user_id = 123456793
        register_user_if_not_exists(user_id, "test_user5", None, "Test User 5")
        
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
        
        # Создаем ключ
        xui_client_uuid = str(uuid.uuid4())
        key_email = f"test_{uuid.uuid4().hex[:8]}@example.com"
        expiry_timestamp_ms = int((datetime.now(timezone.utc) + timedelta(days=30)).timestamp() * 1000)
        
        key_id = create_key_with_stats_atomic(
            user_id=user_id,
            host_name=sample_host['host_name'],
            xui_client_uuid=xui_client_uuid,
            key_email=key_email,
            expiry_timestamp_ms=expiry_timestamp_ms,
            amount_spent=100.0,
            months_purchased=1
        )
        
        # Обновляем информацию о ключе
        new_xui_client_uuid = str(uuid.uuid4())
        new_expiry_timestamp_ms = int((datetime.now(timezone.utc) + timedelta(days=60)).timestamp() * 1000)
        subscription_link = "https://example.com/subscription"
        
        update_key_info(key_id, new_xui_client_uuid, new_expiry_timestamp_ms, subscription_link)
        
        # Проверяем обновленный ключ
        updated_key = get_key_by_id(key_id)
        assert updated_key is not None, "Ключ должен быть найден"
        assert updated_key['xui_client_uuid'] == new_xui_client_uuid, "UUID должен быть обновлен"
        assert updated_key['subscription_link'] == subscription_link, "Subscription link должен быть обновлен"

    @allure.title("Удаление ключа")
    @allure.description("""
    Проверяет удаление ключа из системы.
    
    **Что проверяется:**
    - Удаление ключа через delete_key_by_email
    - Отсутствие ключа в БД после удаления
    - Корректная обработка удаления существующего ключа
    
    **Тестовые данные:**
    - user_id: 123456794
    
    **Ожидаемый результат:**
    Ключ успешно удален из БД и больше не доступен для получения.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("key_operations", "delete_key", "database", "unit")
    def test_delete_key(self, temp_db, sample_host):
        """Тест удаления ключа"""
        # Создаем пользователя
        user_id = 123456794
        register_user_if_not_exists(user_id, "test_user6", None, "Test User 6")
        
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
        
        # Создаем ключ
        xui_client_uuid = str(uuid.uuid4())
        key_email = f"test_{uuid.uuid4().hex[:8]}@example.com"
        expiry_timestamp_ms = int((datetime.now(timezone.utc) + timedelta(days=30)).timestamp() * 1000)
        
        key_id = create_key_with_stats_atomic(
            user_id=user_id,
            host_name=sample_host['host_name'],
            xui_client_uuid=xui_client_uuid,
            key_email=key_email,
            expiry_timestamp_ms=expiry_timestamp_ms,
            amount_spent=100.0,
            months_purchased=1
        )
        
        # Проверяем, что ключ существует
        key = get_key_by_id(key_id)
        assert key is not None, "Ключ должен существовать до удаления"
        
        # Удаляем ключ
        delete_key_by_email(key_email)
        
        # Проверяем, что ключ удален
        deleted_key = get_key_by_email(key_email)
        assert deleted_key is None, "Ключ должен быть удален"

    @allure.title("Синхронизация ключа с 3X-UI")
    @allure.description("""
    Проверяет синхронизацию ключа с системой 3X-UI.
    
    **Что проверяется:**
    - Обновление xui_client_uuid при синхронизации
    - Обновление expiry_timestamp_ms
    - Обновление subscription_link
    - Корректное сохранение синхронизированных данных
    
    **Тестовые данные:**
    - user_id: 123456795
    - Новый expiry: +60 дней от текущего момента
    
    **Ожидаемый результат:**
    Ключ успешно синхронизирован с 3X-UI, все данные обновлены в БД.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("key_operations", "sync", "xui", "database", "unit")
    def test_sync_key_with_xui(self, temp_db, sample_host):
        """Тест синхронизации ключа с 3X-UI"""
        # Создаем пользователя
        user_id = 123456795
        register_user_if_not_exists(user_id, "test_user7", None, "Test User 7")
        
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
        
        # Создаем ключ
        xui_client_uuid = str(uuid.uuid4())
        key_email = f"test_{uuid.uuid4().hex[:8]}@example.com"
        expiry_timestamp_ms = int((datetime.now(timezone.utc) + timedelta(days=30)).timestamp() * 1000)
        
        key_id = create_key_with_stats_atomic(
            user_id=user_id,
            host_name=sample_host['host_name'],
            xui_client_uuid=xui_client_uuid,
            key_email=key_email,
            expiry_timestamp_ms=expiry_timestamp_ms,
            amount_spent=100.0,
            months_purchased=1
        )
        
        # Синхронизируем ключ (обновляем UUID и expiry)
        new_xui_client_uuid = str(uuid.uuid4())
        new_expiry_timestamp_ms = int((datetime.now(timezone.utc) + timedelta(days=60)).timestamp() * 1000)
        subscription_link = "https://example.com/subscription"
        
        update_key_info(key_id, new_xui_client_uuid, new_expiry_timestamp_ms, subscription_link)
        
        # Проверяем синхронизацию
        synced_key = get_key_by_id(key_id)
        assert synced_key is not None, "Ключ должен быть найден"
        assert synced_key['xui_client_uuid'] == new_xui_client_uuid, "UUID должен быть обновлен"
        assert synced_key['subscription_link'] == subscription_link, "Subscription link должен быть обновлен"

    @allure.title("Нумерация ключей")
    @allure.description("""
    Проверяет последовательную нумерацию ключей пользователя.
    
    **Что проверяется:**
    - Получение следующего номера ключа через get_next_key_number
    - Последовательность номеров (1, 2, 3...)
    - Корректность инкремента номера при создании нового ключа
    
    **Тестовые данные:**
    - user_id: 123456796
    - Количество создаваемых ключей: 2
    
    **Ожидаемый результат:**
    Ключи получают последовательные номера (1, 2, 3...).
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("key_operations", "numbering", "database", "unit")
    def test_key_numbering(self, temp_db, sample_host):
        """Тест нумерации ключей"""
        # Создаем пользователя
        user_id = 123456796
        register_user_if_not_exists(user_id, "test_user8", None, "Test User 8")
        
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
        
        # Получаем первый номер ключа
        key_number_1 = get_next_key_number(user_id)
        assert key_number_1 == 1, "Первый ключ должен иметь номер 1"
        
        # Создаем первый ключ
        expiry_timestamp_ms = int((datetime.now(timezone.utc) + timedelta(days=30)).timestamp() * 1000)
        create_key_with_stats_atomic(
            user_id=user_id,
            host_name=sample_host['host_name'],
            xui_client_uuid=str(uuid.uuid4()),
            key_email=f"test1_{uuid.uuid4().hex[:8]}@example.com",
            expiry_timestamp_ms=expiry_timestamp_ms,
            amount_spent=100.0,
            months_purchased=1
        )
        
        # Получаем второй номер ключа
        key_number_2 = get_next_key_number(user_id)
        assert key_number_2 == 2, "Второй ключ должен иметь номер 2"
        
        # Создаем второй ключ
        create_key_with_stats_atomic(
            user_id=user_id,
            host_name=sample_host['host_name'],
            xui_client_uuid=str(uuid.uuid4()),
            key_email=f"test2_{uuid.uuid4().hex[:8]}@example.com",
            expiry_timestamp_ms=expiry_timestamp_ms,
            amount_spent=100.0,
            months_purchased=1
        )
        
        # Получаем третий номер ключа
        key_number_3 = get_next_key_number(user_id)
        assert key_number_3 == 3, "Третий ключ должен иметь номер 3"
        
        # Проверяем, что номера последовательные
        assert key_number_1 < key_number_2 < key_number_3, "Номера ключей должны быть последовательными"

