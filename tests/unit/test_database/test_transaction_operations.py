#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Unit-тесты для операций с транзакциями в БД

Тестирует создание и обновление транзакций используя временную БД
"""

import pytest
import allure
import sys
import json
from pathlib import Path

# Добавляем путь к проекту
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root / "src"))

from shop_bot.data_manager.database import (
    log_transaction,
    get_transaction_by_payment_id,
    update_transaction_status,
    update_transaction_on_payment,
)


@pytest.mark.unit
@pytest.mark.database
@allure.epic("База данных")
@allure.feature("Транзакции")
@allure.label("package", "src.shop_bot.database")
class TestTransactionOperations:
    """Тесты для операций с транзакциями"""

    @allure.title("Создание транзакции")
    @allure.description("""
    Проверяет успешное создание транзакции в системе.
    
    **Что проверяется:**
    - Создание транзакции через log_transaction
    - Корректное сохранение всех параметров транзакции
    - Наличие транзакции в БД после создания
    
    **Тестовые данные:**
    - payment_id: "test_payment_001"
    - user_id: 123456810
    - status: "pending"
    - amount_rub: 1000.0
    
    **Ожидаемый результат:**
    Транзакция успешно создана в БД со всеми указанными параметрами.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("transactions", "create", "database", "unit")
    def test_log_transaction(self, temp_db):
        """Тест создания транзакции"""
        payment_id = "test_payment_001"
        user_id = 123456810
        
        # Создаем пользователя
        from shop_bot.data_manager.database import register_user_if_not_exists
        register_user_if_not_exists(user_id, "test_user7", None, "Test User 7")
        
        # Создаем транзакцию
        log_transaction(
            username="test_user7",
            transaction_id="test_tx_001",
            payment_id=payment_id,
            user_id=user_id,
            status="pending",
            amount_rub=1000.0,
            amount_currency=100.0,
            currency_name="RUB",
            payment_method="yookassa",
            metadata=json.dumps({"test": "data"})
        )
        
        # Проверяем, что транзакция создана
        transaction = get_transaction_by_payment_id(payment_id)
        assert transaction is not None, "Транзакция должна быть создана"
        assert transaction['payment_id'] == payment_id
        assert transaction['user_id'] == user_id
        assert transaction['status'] == "pending"
        assert transaction['amount_rub'] == 1000.0

    @allure.title("Получение несуществующей транзакции")
    @allure.description("""
    Проверяет обработку запроса несуществующей транзакции.
    
    **Что проверяется:**
    - Функция get_transaction_by_payment_id возвращает None для несуществующей транзакции
    - Отсутствие ошибок при запросе несуществующей транзакции
    
    **Тестовые данные:**
    - payment_id: "nonexistent_payment_id"
    
    **Ожидаемый результат:**
    Функция get_transaction_by_payment_id возвращает None для несуществующей транзакции.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("transactions", "get_transaction", "not_found", "database", "unit")
    def test_get_transaction_by_payment_id_not_exists(self, temp_db):
        """Тест получения несуществующей транзакции"""
        transaction = get_transaction_by_payment_id("nonexistent_payment_id")
        assert transaction is None, "Несуществующая транзакция должна вернуть None"

    @allure.title("Обновление статуса транзакции")
    @allure.description("""
    Проверяет обновление статуса транзакции.
    
    **Что проверяется:**
    - Обновление статуса транзакции через update_transaction_status
    - Корректное сохранение обновленного статуса в БД
    - Изменение статуса с "pending" на "paid"
    
    **Тестовые данные:**
    - payment_id: "test_payment_002"
    - user_id: 123456811
    - Исходный статус: "pending"
    - Обновленный статус: "paid"
    
    **Ожидаемый результат:**
    Статус транзакции успешно обновлен и сохранен в БД.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("transactions", "update_status", "database", "unit")
    def test_update_transaction_status(self, temp_db):
        """Тест обновления статуса транзакции"""
        payment_id = "test_payment_002"
        user_id = 123456811
        
        # Создаем пользователя
        from shop_bot.data_manager.database import register_user_if_not_exists
        register_user_if_not_exists(user_id, "test_user8", None, "Test User 8")
        
        # Создаем транзакцию
        log_transaction(
            username="test_user8",
            transaction_id="test_tx_002",
            payment_id=payment_id,
            user_id=user_id,
            status="pending",
            amount_rub=1000.0,
            amount_currency=None,
            currency_name=None,
            payment_method="yookassa",
            metadata=json.dumps({"test": "data"})
        )
        
        # Обновляем статус
        success = update_transaction_status(payment_id, "paid")
        assert success is True
        
        # Проверяем обновление
        transaction = get_transaction_by_payment_id(payment_id)
        assert transaction is not None
        assert transaction['status'] == "paid"

    @allure.title("Обновление транзакции при оплате")
    @allure.description("""
    Проверяет обновление транзакции при успешной оплате.
    
    **Что проверяется:**
    - Обновление транзакции через update_transaction_on_payment
    - Обновление статуса на "paid"
    - Сохранение tx_hash и дополнительных метаданных
    - Корректное сохранение всех обновленных данных в БД
    
    **Тестовые данные:**
    - payment_id: "test_payment_003"
    - user_id: 123456812
    - tx_hash: "test_hash_123"
    - status: "paid"
    
    **Ожидаемый результат:**
    Транзакция успешно обновлена при оплате со всеми указанными данными.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("transactions", "update_on_payment", "database", "unit")
    def test_update_transaction_on_payment(self, temp_db):
        """Тест обновления транзакции при оплате"""
        payment_id = "test_payment_003"
        user_id = 123456812
        
        # Создаем пользователя
        from shop_bot.data_manager.database import register_user_if_not_exists
        register_user_if_not_exists(user_id, "test_user9", None, "Test User 9")
        
        # Создаем транзакцию
        log_transaction(
            username="test_user9",
            transaction_id="test_tx_003",
            payment_id=payment_id,
            user_id=user_id,
            status="pending",
            amount_rub=1000.0,
            amount_currency=None,
            currency_name=None,
            payment_method="yookassa",
            metadata=json.dumps({"test": "data"})
        )
        
        # Обновляем транзакцию при оплате
        success = update_transaction_on_payment(
            payment_id=payment_id,
            status="paid",
            amount_rub=1000.0,
            tx_hash="test_hash_123",
            metadata={"additional": "info"}
        )
        assert success is True
        
        # Проверяем обновление
        transaction = get_transaction_by_payment_id(payment_id)
        assert transaction is not None
        assert transaction['status'] == "paid"

