#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Unit-тесты для операций с пробным периодом (триалами)
"""

import pytest
import allure
import sqlite3
from datetime import datetime, timezone, timedelta
from shop_bot.data_manager.database import (
    register_user_if_not_exists,
    set_trial_used,
    set_trial_days_given,
    increment_trial_reuses,
    reset_trial_used,
    admin_reset_trial_completely,
    get_trial_info,
    get_user,
    add_new_key,
    get_user_keys,
    get_key_by_id
)


@pytest.mark.unit
@pytest.mark.database
@allure.epic("База данных")
@allure.feature("Пробный период")
@allure.label("package", "src.shop_bot.database")
@allure.title("Проверка возможности получить триал")
@allure.description("""
Проверяет возможность получения триального ключа пользователем.

**Что проверяется:**
- Новый пользователь может получить триал (trial_used = False, trial_reuses_count = 0)
- Пользователь, использовавший триал без повторных использований, не может получить триал
- Пользователь с повторными использованиями может получить триал (trial_used = False, trial_reuses_count > 0)

**Тестовые данные:**
- user_id: 123456

**Ожидаемый результат:**
Новый пользователь может получить триал, использовавший без повторных использований - не может, с повторными использованиями - может.
""")
@allure.severity(allure.severity_level.NORMAL)
@allure.tag("trial", "eligibility", "database", "unit")
def test_trial_eligibility_check(temp_db):
    """Проверка возможности получить триал"""
    # Создаем пользователя
    user_id = 123456
    register_user_if_not_exists(user_id, "test_user", None)
    user = get_user(user_id)
    assert user is not None
    
    # Тест 1: Новый пользователь может получить триал
    trial_info = get_trial_info(user_id)
    assert trial_info['trial_used'] is False
    assert trial_info['trial_reuses_count'] == 0
    # Новый пользователь может получить триал (trial_used = 0)
    
    # Тест 2: Пользователь, который использовал триал без повторных использований - не может
    set_trial_used(user_id)
    trial_info = get_trial_info(user_id)
    assert trial_info['trial_used'] is True
    assert trial_info['trial_reuses_count'] == 0
    # Пользователь с trial_used=1 и trial_reuses_count=0 не может получить триал
    
    # Тест 3: Пользователь с повторными использованиями может получить триал
    increment_trial_reuses(user_id)
    reset_trial_used(user_id)
    trial_info = get_trial_info(user_id)
    assert trial_info['trial_used'] is False
    assert trial_info['trial_reuses_count'] == 1
    # Пользователь с trial_used=0 и trial_reuses_count>0 может получить триал


@pytest.mark.unit
@pytest.mark.database
@allure.epic("База данных")
@allure.feature("Пробный период")
@allure.label("package", "src.shop_bot.database")
@allure.title("Создание триального ключа")
@allure.description("""
Проверяет создание триального ключа для пользователя.

**Что проверяется:**
- Создание триального ключа через add_new_key с is_trial=1
- Установка флагов триала (trial_used, trial_days_given, trial_reuses_count)
- Корректность данных созданного ключа (is_trial, plan_name, price)
- Обновление информации о триале в БД

**Тестовые данные:**
- user_id: 123456
- host_name: "test_host"
- trial_days: 7
- plan_name: "Пробный период"
- price: 0.0

**Ожидаемый результат:**
Триальный ключ успешно создан, флаги триала установлены, информация о триале обновлена в БД.
""")
@allure.severity(allure.severity_level.NORMAL)
@allure.tag("trial", "creation", "database", "unit")
def test_trial_creation(temp_db):
    """Создание триального ключа"""
    # Создаем пользователя
    user_id = 123456
    register_user_if_not_exists(user_id, "test_user", None)
    user = get_user(user_id)
    assert user is not None
    
    # Проверяем начальное состояние
    trial_info = get_trial_info(user_id)
    assert trial_info['trial_used'] is False
    assert trial_info['trial_days_given'] == 0
    assert trial_info['trial_reuses_count'] == 0
    
    # Создаем триальный ключ
    host_name = "test_host"
    xui_client_uuid = "test-uuid-123"
    key_email = f"user{user_id}-key1-trial@test.bot"
    
    # Вычисляем expiry_timestamp_ms (7 дней от текущего момента)
    now = datetime.now(timezone.utc)
    expiry_date = now + timedelta(days=7)
    expiry_timestamp_ms = int(expiry_date.timestamp() * 1000)
    
    key_id = add_new_key(
        user_id=user_id,
        host_name=host_name,
        xui_client_uuid=xui_client_uuid,
        key_email=key_email,
        expiry_timestamp_ms=expiry_timestamp_ms,
        connection_string="vless://test",
        plan_name="Пробный период",
        price=0.0,
        protocol='vless',
        is_trial=1,
        comment="Тестовый триальный ключ"
    )
    
    assert key_id is not None
    
    # Устанавливаем флаги триала
    set_trial_used(user_id)
    set_trial_days_given(user_id, 7)
    increment_trial_reuses(user_id)
    
    # Проверяем, что ключ создан
    key = get_key_by_id(key_id)
    assert key is not None
    assert key['is_trial'] == 1
    assert key['plan_name'] == "Пробный период"
    assert key['price'] == 0.0
    
    # Проверяем обновленную информацию о триале
    trial_info = get_trial_info(user_id)
    assert trial_info['trial_used'] is True
    assert trial_info['trial_days_given'] == 7
    assert trial_info['trial_reuses_count'] == 1


@pytest.mark.unit
@pytest.mark.database
@allure.epic("База данных")
@allure.feature("Пробный период")
@allure.label("package", "src.shop_bot.database")
@allure.title("Логика повторного использования триала")
@allure.description("""
Проверяет логику повторного использования триального ключа.

**Что проверяется:**
- Первое использование триала (trial_used = True, trial_reuses_count = 1)
- Сброс для повторного использования (reset_trial_used)
- Увеличение счетчика повторных использований
- Создание второго триального ключа после сброса
- Корректность финального состояния (trial_used = True, trial_reuses_count = 2)

**Тестовые данные:**
- user_id: 123456
- Количество использований: 2

**Ожидаемый результат:**
Триал может быть использован повторно после сброса, счетчик повторных использований увеличивается.
""")
@allure.severity(allure.severity_level.NORMAL)
@allure.tag("trial", "reuse", "database", "unit")
def test_trial_reuse_logic(temp_db):
    """Логика повторного использования триала"""
    # Создаем пользователя
    user_id = 123456
    register_user_if_not_exists(user_id, "test_user", None)
    user = get_user(user_id)
    assert user is not None
    
    # Симулируем первое использование триала
    set_trial_used(user_id)
    set_trial_days_given(user_id, 7)
    increment_trial_reuses(user_id)
    
    trial_info = get_trial_info(user_id)
    assert trial_info['trial_used'] is True
    assert trial_info['trial_reuses_count'] == 1
    
    # Сбрасываем для повторного использования
    reset_trial_used(user_id)
    increment_trial_reuses(user_id)
    
    # Проверяем, что теперь можно использовать триал снова
    trial_info = get_trial_info(user_id)
    assert trial_info['trial_used'] is False  # Сброшено для повторного использования
    assert trial_info['trial_reuses_count'] == 2  # Увеличен счетчик
    
    # Создаем второй триальный ключ
    host_name = "test_host"
    xui_client_uuid = "test-uuid-456"
    key_email = f"user{user_id}-key2-trial@test.bot"
    
    now = datetime.now(timezone.utc)
    expiry_date = now + timedelta(days=7)
    expiry_timestamp_ms = int(expiry_date.timestamp() * 1000)
    
    key_id = add_new_key(
        user_id=user_id,
        host_name=host_name,
        xui_client_uuid=xui_client_uuid,
        key_email=key_email,
        expiry_timestamp_ms=expiry_timestamp_ms,
        connection_string="vless://test2",
        plan_name="Пробный период",
        price=0.0,
        protocol='vless',
        is_trial=1,
        comment="Второй триальный ключ"
    )
    
    assert key_id is not None
    
    # Устанавливаем флаг использования снова
    set_trial_used(user_id)
    
    # Проверяем финальное состояние
    trial_info = get_trial_info(user_id)
    assert trial_info['trial_used'] is True
    assert trial_info['trial_reuses_count'] == 2


@pytest.mark.unit
@pytest.mark.database
@allure.epic("База данных")
@allure.feature("Пробный период")
@allure.label("package", "src.shop_bot.database")
@allure.title("Отзыв триального ключа")
@allure.description("""
Проверяет идентификацию триальных ключей для отзыва.

**Что проверяется:**
- Создание триального ключа с is_trial=1
- Создание токена для триального ключа
- Идентификация триальных ключей пользователя
- Наличие триального ключа в списке ключей пользователя

**Тестовые данные:**
- user_id: 123456
- key_email: "user{user_id}-key1-trial@test.bot"

**Ожидаемый результат:**
Триальный ключ успешно идентифицирован и может быть отозван.
""")
@allure.severity(allure.severity_level.NORMAL)
@allure.tag("trial", "revocation", "database", "unit")
def test_trial_revocation(temp_db):
    """Отзыв триального ключа"""
    # Создаем пользователя
    user_id = 123456
    register_user_if_not_exists(user_id, "test_user", None)
    user = get_user(user_id)
    assert user is not None
    
    # Создаем триальный ключ
    host_name = "test_host"
    xui_client_uuid = "test-uuid-123"
    key_email = f"user{user_id}-key1-trial@test.bot"
    
    now = datetime.now(timezone.utc)
    expiry_date = now + timedelta(days=7)
    expiry_timestamp_ms = int(expiry_date.timestamp() * 1000)
    
    key_id = add_new_key(
        user_id=user_id,
        host_name=host_name,
        xui_client_uuid=xui_client_uuid,
        key_email=key_email,
        expiry_timestamp_ms=expiry_timestamp_ms,
        connection_string="vless://test",
        plan_name="Пробный период",
        price=0.0,
        protocol='vless',
        is_trial=1,
        comment="Триальный ключ для отзыва"
    )
    
    assert key_id is not None
    
    # Создаем токен для ключа (симулируем)
    with sqlite3.connect(temp_db) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO user_tokens (token, user_id, key_id, created_at) VALUES (?, ?, ?, ?)",
            ("test-token-123", user_id, key_id, datetime.now(timezone.utc).isoformat())
        )
        conn.commit()
    
    # Проверяем, что ключ существует
    key = get_key_by_id(key_id)
    assert key is not None
    assert key['is_trial'] == 1
    
    # Проверяем, что токен существует (может быть создан автоматически при создании ключа)
    with sqlite3.connect(temp_db) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM user_tokens WHERE key_id = ?", (key_id,))
        token_count = cursor.fetchone()[0]
        assert token_count >= 1  # Может быть создан автоматически
    
    # Отзываем триальный ключ (удаляем через admin_reset_trial_completely)
    # Но сначала проверим, что функция работает корректно
    # Для отзыва конкретного ключа нужно использовать delete_key или аналогичную функцию
    # В данном тесте проверяем, что триальные ключи можно идентифицировать
    
    # Получаем все триальные ключи пользователя
    user_keys = get_user_keys(user_id)
    trial_keys = [key for key in user_keys if key.get('is_trial') == 1]
    assert len(trial_keys) == 1
    assert trial_keys[0]['key_id'] == key_id


@pytest.mark.unit
@pytest.mark.database
@allure.epic("База данных")
@allure.feature("Пробный период")
@allure.label("package", "src.shop_bot.database")
@allure.title("Сброс триала администратором")
@allure.description("""
Проверяет полный сброс триала администратором через admin_reset_trial_completely.

**Что проверяется:**
- Полный сброс всех флагов триала (trial_used = False, trial_days_given = 0, trial_reuses_count = 0)
- Удаление триального ключа из БД
- Удаление токена триального ключа
- Возможность пользователя снова получить триал (как новый пользователь)

**Тестовые данные:**
- user_id: 123456
- Количество использований до сброса: 2

**Ожидаемый результат:**
Все флаги триала сброшены, триальный ключ и токен удалены, пользователь может снова получить триал.
""")
@allure.severity(allure.severity_level.NORMAL)
@allure.tag("trial", "reset", "admin", "database", "unit")
def test_trial_reset(temp_db):
    """Сброс триала администратором"""
    # Создаем пользователя
    user_id = 123456
    register_user_if_not_exists(user_id, "test_user", None)
    user = get_user(user_id)
    assert user is not None
    
    # Создаем триальный ключ
    host_name = "test_host"
    xui_client_uuid = "test-uuid-123"
    key_email = f"user{user_id}-key1-trial@test.bot"
    
    now = datetime.now(timezone.utc)
    expiry_date = now + timedelta(days=7)
    expiry_timestamp_ms = int(expiry_date.timestamp() * 1000)
    
    key_id = add_new_key(
        user_id=user_id,
        host_name=host_name,
        xui_client_uuid=xui_client_uuid,
        key_email=key_email,
        expiry_timestamp_ms=expiry_timestamp_ms,
        connection_string="vless://test",
        plan_name="Пробный период",
        price=0.0,
        protocol='vless',
        is_trial=1,
        comment="Триальный ключ для сброса"
    )
    
    assert key_id is not None
    
    # Устанавливаем флаги триала
    set_trial_used(user_id)
    set_trial_days_given(user_id, 7)
    increment_trial_reuses(user_id)
    increment_trial_reuses(user_id)  # Два использования
    
    # Создаем токен для ключа
    with sqlite3.connect(temp_db) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO user_tokens (token, user_id, key_id, created_at) VALUES (?, ?, ?, ?)",
            ("test-token-123", user_id, key_id, datetime.now(timezone.utc).isoformat())
        )
        conn.commit()
    
    # Проверяем состояние до сброса
    trial_info = get_trial_info(user_id)
    assert trial_info['trial_used'] is True
    assert trial_info['trial_days_given'] == 7
    assert trial_info['trial_reuses_count'] == 2
    
    # Проверяем наличие ключа
    key = get_key_by_id(key_id)
    assert key is not None
    assert key['is_trial'] == 1
    
    # Проверяем наличие токена (может быть создан автоматически при создании ключа)
    with sqlite3.connect(temp_db) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM user_tokens WHERE key_id = ?", (key_id,))
        token_count_before = cursor.fetchone()[0]
        assert token_count_before >= 1  # Может быть создан автоматически
    
    # Выполняем полный сброс триала администратором
    result = admin_reset_trial_completely(user_id)
    assert result is True
    
    # Проверяем состояние после сброса
    trial_info = get_trial_info(user_id)
    assert trial_info['trial_used'] is False
    assert trial_info['trial_days_given'] == 0
    assert trial_info['trial_reuses_count'] == 0
    
    # Проверяем, что триальный ключ удален
    key_after = get_key_by_id(key_id)
    assert key_after is None
    
    # Проверяем, что токен удален
    with sqlite3.connect(temp_db) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM user_tokens WHERE key_id = ?", (key_id,))
        token_count_after = cursor.fetchone()[0]
        assert token_count_after == 0
    
    # Проверяем, что пользователь может снова получить триал
    # (trial_used = 0, trial_reuses_count = 0 - как новый пользователь)

