#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Тесты для проверки исправлений битых ссылок личного кабинета

Использует временную БД через фикстуру temp_db из conftest.py
"""

import pytest
import allure
import sqlite3
from datetime import datetime, timezone, timedelta

from shop_bot.data_manager.database import (
    get_or_create_permanent_token,
    validate_permanent_token,
    add_new_key,
    delete_key_by_email,
    delete_user_keys,
    DB_FILE
)


@pytest.mark.unit
@pytest.mark.database
@allure.epic("База данных")
@allure.feature("Ссылки личного кабинета")
@allure.label("package", "src.shop_bot.database")
class TestCabinetLinks:
    """Тесты для исправлений битых ссылок личного кабинета"""

    @allure.title("Валидация токена с удаленным ключом")
    @allure.description("""
    Проверяет валидацию токена после удаления ключа.
    
    **Что проверяется:**
    - Создание токена для ключа
    - Валидация токена до удаления ключа
    - Валидация токена после удаления ключа (с флагом key_deleted)
    - Установка флага key_deleted при валидации удаленного ключа
    
    **Тестовые данные:**
    - user_id: 999999
    - key_email: "test_{user_id}@test.com"
    
    **Ожидаемый результат:**
    Токен валидируется до и после удаления ключа, после удаления устанавливается флаг key_deleted=True.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("cabinet_links", "token_validation", "deleted_key", "database", "unit")
    def test_validate_token_with_deleted_key(self, temp_db):
        """Тест 1: Валидация токена с удаленным ключом"""
        # Создаем тестового пользователя и ключ
        test_user_id = 999999
        test_key_id = None
        
        try:
            # Создаем тестовый ключ
            expiry_ms = int((datetime.now(timezone.utc) + timedelta(days=30)).timestamp() * 1000)
            test_key_id = add_new_key(
                user_id=test_user_id,
                host_name="test_host",
                xui_client_uuid="test-uuid-123",
                key_email=f"test_{test_user_id}@test.com",
                expiry_timestamp_ms=expiry_ms,
                connection_string="vless://test",
                plan_name="Test Plan",
                price=100.0,
                protocol='vless',
                is_trial=0
            )
            
            assert test_key_id is not None, "Не удалось создать тестовый ключ"
            
            # Создаем токен
            token = get_or_create_permanent_token(test_user_id, test_key_id)
            assert token is not None, "Не удалось создать токен"
            
            # Проверяем, что токен валиден
            token_data = validate_permanent_token(token)
            assert token_data is not None, "Токен не валидируется до удаления ключа"
            assert token_data.get('user_id') == test_user_id
            assert token_data.get('key_id') == test_key_id
            
            # Удаляем ключ
            with sqlite3.connect(str(temp_db), timeout=30) as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM vpn_keys WHERE key_id = ?", (test_key_id,))
                conn.commit()
            
            # Проверяем, что токен все еще валидируется (но с флагом key_deleted)
            token_data_after = validate_permanent_token(token)
            assert token_data_after is not None, "Токен не валидируется после удаления ключа (должен валидироваться с флагом key_deleted)"
            assert token_data_after.get('key_deleted') is True, "Флаг key_deleted не установлен"
            assert token_data_after.get('user_id') == test_user_id
            assert token_data_after.get('key_id') == test_key_id
            
        finally:
            # Очистка
            if test_key_id:
                try:
                    with sqlite3.connect(str(temp_db), timeout=30) as conn:
                        cursor = conn.cursor()
                        cursor.execute("DELETE FROM vpn_keys WHERE key_id = ?", (test_key_id,))
                        cursor.execute("DELETE FROM user_tokens WHERE key_id = ?", (test_key_id,))
                        conn.commit()
                except:
                    pass

    @allure.title("Создание токена при создании ключа")
    @allure.description("""
    Проверяет автоматическое создание токена при создании ключа.
    
    **Что проверяется:**
    - Автоматическое создание токена при создании ключа через add_new_key
    - Наличие токена в БД после создания ключа
    - Валидация автоматически созданного токена
    
    **Тестовые данные:**
    - user_id: 999998
    - key_email: "test_{user_id}@test.com"
    
    **Ожидаемый результат:**
    Токен автоматически создан при создании ключа и успешно валидируется.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("cabinet_links", "token_creation", "auto_create", "database", "unit")
    def test_token_creation_on_key_creation(self, temp_db):
        """Тест 2: Создание токена при создании ключа"""
        test_user_id = 999998
        test_key_id = None
        
        try:
            # Создаем ключ (токен должен создаться автоматически)
            expiry_ms = int((datetime.now(timezone.utc) + timedelta(days=30)).timestamp() * 1000)
            test_key_id = add_new_key(
                user_id=test_user_id,
                host_name="test_host",
                xui_client_uuid="test-uuid-456",
                key_email=f"test_{test_user_id}@test.com",
                expiry_timestamp_ms=expiry_ms,
                connection_string="vless://test",
                plan_name="Test Plan",
                price=100.0,
                protocol='vless',
                is_trial=0
            )
            
            assert test_key_id is not None, "Не удалось создать тестовый ключ"
            
            # Проверяем, что токен создан автоматически
            with sqlite3.connect(str(temp_db), timeout=30) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute("SELECT token FROM user_tokens WHERE user_id = ? AND key_id = ?", (test_user_id, test_key_id))
                token_row = cursor.fetchone()
            
            assert token_row is not None, "Токен не создан автоматически при создании ключа"
            token = token_row['token']
            
            # Проверяем валидацию токена
            token_data = validate_permanent_token(token)
            assert token_data is not None, "Созданный токен не валидируется"
            assert token_data.get('user_id') == test_user_id
            assert token_data.get('key_id') == test_key_id
            
        finally:
            # Очистка
            if test_key_id:
                try:
                    with sqlite3.connect(str(temp_db), timeout=30) as conn:
                        cursor = conn.cursor()
                        cursor.execute("DELETE FROM vpn_keys WHERE key_id = ?", (test_key_id,))
                        cursor.execute("DELETE FROM user_tokens WHERE key_id = ?", (test_key_id,))
                        conn.commit()
                except:
                    pass

    @allure.title("Удаление токена при удалении ключа")
    @allure.description("""
    Проверяет, что токен НЕ удаляется при удалении ключа через функцию delete_key_by_email.
    Это позволяет validate_permanent_token корректно определять удаленный ключ через LEFT JOIN
    и возвращать key_deleted=True, что обеспечивает правильную обработку в приложении user-cabinet
    (возврат 404 "Ключ удален" вместо 403 "Ссылка недействительна").
    
    **Что проверяется:**
    - Создание ключа через add_new_key с автоматическим созданием токена
    - Создание дополнительного токена через get_or_create_permanent_token
    - Проверка наличия токена в БД перед удалением ключа
    - Удаление ключа через delete_key_by_email
    - Проверка сохранения токена в таблице user_tokens после удаления ключа
    - Токен должен остаться в БД для корректной обработки удаленного ключа
    
    **Тестовые данные:**
    - user_id: 999997
    - host_name: 'test_host'
    - key_email: "test_999997@test.com"
    - xui_client_uuid: "test-uuid-789"
    - plan_name: "Test Plan"
    - price: 100.0
    - protocol: 'vless'
    
    **Шаги теста:**
    1. Создание тестового ключа через add_new_key
    2. Создание токена через get_or_create_permanent_token
    3. Проверка наличия токена в таблице user_tokens
    4. Удаление ключа через delete_key_by_email
    5. Проверка сохранения токена в таблице user_tokens
    
    **Ожидаемый результат:**
    Токен НЕ удаляется из таблицы user_tokens при удалении ключа через delete_key_by_email.
    Это позволяет validate_permanent_token определить, что ключ удален, и вернуть key_deleted=True.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("cabinet_links", "token_preservation", "key_deletion", "database", "unit", "delete_key_by_email")
    def test_token_deletion_on_key_deletion(self, temp_db):
        """Тест 3: Токен НЕ удаляется при удалении ключа"""
        test_user_id = 999997
        test_key_id = None
        test_token = None
        
        try:
            with allure.step("Подготовка тестовых данных"):
                expiry_ms = int((datetime.now(timezone.utc) + timedelta(days=30)).timestamp() * 1000)
                allure.attach(str(test_user_id), "User ID", allure.attachment_type.TEXT)
                allure.attach(str(expiry_ms), "Expiry timestamp (ms)", allure.attachment_type.TEXT)
            
            with allure.step("Создание тестового ключа"):
                test_key_id = add_new_key(
                    user_id=test_user_id,
                    host_name="test_host",
                    xui_client_uuid="test-uuid-789",
                    key_email=f"test_{test_user_id}@test.com",
                    expiry_timestamp_ms=expiry_ms,
                    connection_string="vless://test",
                    plan_name="Test Plan",
                    price=100.0,
                    protocol='vless',
                    is_trial=0
                )
                allure.attach(str(test_key_id), "Created Key ID", allure.attachment_type.TEXT)
                assert test_key_id is not None, "Не удалось создать тестовый ключ"
            
            with allure.step("Создание токена для ключа"):
                test_token = get_or_create_permanent_token(test_user_id, test_key_id)
                allure.attach(str(test_token), "Created Token", allure.attachment_type.TEXT)
                assert test_token is not None, "Не удалось создать токен"
            
            with allure.step("Проверка наличия токена в БД перед удалением"):
                with sqlite3.connect(str(temp_db), timeout=30) as conn:
                    conn.row_factory = sqlite3.Row
                    cursor = conn.cursor()
                    cursor.execute("SELECT token FROM user_tokens WHERE key_id = ?", (test_key_id,))
                    token_row = cursor.fetchone()
                
                allure.attach(str(token_row is not None), "Token exists in DB", allure.attachment_type.TEXT)
                assert token_row is not None, "Токен не найден в БД"
            
            with allure.step("Удаление ключа через delete_key_by_email"):
                key_email = f"test_{test_user_id}@test.com"
                allure.attach(key_email, "Key Email", allure.attachment_type.TEXT)
                delete_key_by_email(key_email)
            
            with allure.step("Проверка сохранения токена в БД после удаления ключа"):
                with sqlite3.connect(str(temp_db), timeout=30) as conn:
                    conn.row_factory = sqlite3.Row
                    cursor = conn.cursor()
                    cursor.execute("SELECT token FROM user_tokens WHERE key_id = ?", (test_key_id,))
                    token_row = cursor.fetchone()
                
                allure.attach(str(token_row is not None), "Token preserved in DB", allure.attachment_type.TEXT)
                assert token_row is not None, "Токен должен остаться в БД после удаления ключа для корректной обработки удаленного ключа"
            
        finally:
            with allure.step("Очистка тестовых данных"):
                if test_key_id:
                    try:
                        with sqlite3.connect(str(temp_db), timeout=30) as conn:
                            cursor = conn.cursor()
                            cursor.execute("DELETE FROM vpn_keys WHERE key_id = ?", (test_key_id,))
                            cursor.execute("DELETE FROM user_tokens WHERE key_id = ?", (test_key_id,))
                            conn.commit()
                    except:
                        pass

    @allure.title("Удаление токенов при удалении всех ключей пользователя")
    @allure.description("""
    Проверяет удаление всех токенов при удалении всех ключей пользователя через delete_user_keys.
    
    **Что проверяется:**
    - Создание нескольких ключей и токенов
    - Удаление всех ключей пользователя через delete_user_keys
    - Удаление всех токенов при удалении ключей
    - Отсутствие токенов в БД после удаления ключей
    
    **Тестовые данные:**
    - user_id: 999996
    - Количество создаваемых ключей: 3
    
    **Ожидаемый результат:**
    Все токены успешно удалены при удалении всех ключей пользователя, токены отсутствуют в БД.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("cabinet_links", "token_deletion", "delete_user_keys", "database", "unit")
    def test_token_deletion_on_user_keys_deletion(self, temp_db):
        """Тест 4: Удаление токенов при удалении всех ключей пользователя"""
        test_user_id = 999996
        test_key_ids = []
        
        try:
            # Создаем несколько ключей и токенов
            expiry_ms = int((datetime.now(timezone.utc) + timedelta(days=30)).timestamp() * 1000)
            
            for i in range(3):
                key_id = add_new_key(
                    user_id=test_user_id,
                    host_name="test_host",
                    xui_client_uuid=f"test-uuid-{i}",
                    key_email=f"test_{test_user_id}_{i}@test.com",
                    expiry_timestamp_ms=expiry_ms,
                    connection_string="vless://test",
                    plan_name="Test Plan",
                    price=100.0,
                    protocol='vless',
                    is_trial=0
                )
                if key_id:
                    test_key_ids.append(key_id)
            
            assert len(test_key_ids) >= 3, f"Не удалось создать все тестовые ключи. Создано: {len(test_key_ids)}"
            
            # Проверяем, что токены созданы
            with sqlite3.connect(str(temp_db), timeout=30) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                placeholders = ','.join(['?'] * len(test_key_ids))
                cursor.execute(f"SELECT COUNT(*) as count FROM user_tokens WHERE key_id IN ({placeholders})", test_key_ids)
                count_row = cursor.fetchone()
                token_count = count_row['count'] if count_row else 0
            
            assert token_count >= len(test_key_ids), f"Создано только {token_count} токенов из {len(test_key_ids)}"
            
            # Удаляем все ключи пользователя
            delete_user_keys(test_user_id)
            
            # Проверяем, что все токены удалены
            with sqlite3.connect(str(temp_db), timeout=30) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                placeholders = ','.join(['?'] * len(test_key_ids))
                cursor.execute(f"SELECT COUNT(*) as count FROM user_tokens WHERE key_id IN ({placeholders})", test_key_ids)
                count_row = cursor.fetchone()
                remaining_tokens = count_row['count'] if count_row else 0
            
            assert remaining_tokens == 0, f"Осталось {remaining_tokens} токенов после удаления ключей"
            
        finally:
            # Очистка
            if test_key_ids:
                try:
                    with sqlite3.connect(str(temp_db), timeout=30) as conn:
                        cursor = conn.cursor()
                        placeholders = ','.join(['?'] * len(test_key_ids))
                        cursor.execute(f"DELETE FROM vpn_keys WHERE key_id IN ({placeholders})", test_key_ids)
                        cursor.execute(f"DELETE FROM user_tokens WHERE key_id IN ({placeholders})", test_key_ids)
                        conn.commit()
                except:
                    pass

    @allure.title("Валидация несуществующего токена")
    @allure.description("""
    Проверяет валидацию несуществующего токена.
    
    **Что проверяется:**
    - Валидация несуществующего токена через validate_permanent_token
    - Возврат None для несуществующего токена
    - Отсутствие ошибок при валидации несуществующего токена
    
    **Тестовые данные:**
    - fake_token: "fake_token_that_does_not_exist_12345"
    
    **Ожидаемый результат:**
    Валидация несуществующего токена возвращает None без ошибок.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("cabinet_links", "token_validation", "invalid_token", "database", "unit")
    def test_invalid_token(self, temp_db):
        """Тест 5: Валидация несуществующего токена"""
        fake_token = "fake_token_that_does_not_exist_12345"
        
        token_data = validate_permanent_token(fake_token)
        
        assert token_data is None, "Несуществующий токен валидируется (не должен)"

