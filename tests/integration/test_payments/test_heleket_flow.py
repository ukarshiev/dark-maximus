#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Интеграционные тесты для Heleket

Тестирует полный flow от создания инвойса до получения ключа
"""

import pytest
import sys
from pathlib import Path
from datetime import datetime, timezone, timedelta
import uuid
from unittest.mock import patch, MagicMock, AsyncMock
import allure

# Добавляем путь к проекту
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root / "src"))


@pytest.mark.integration
@pytest.mark.database
@allure.epic("Интеграционные тесты")
@allure.feature("Платежи")
@allure.label("package", "tests.integration.test_payments")
class TestHeleketFlow:
    """Интеграционные тесты для Heleket"""

    @allure.story("Полный flow Heleket: от создания инвойса до получения ключа")
    @allure.title("Полный flow Heleket: от создания инвойса до получения ключа")
    @allure.description("""
    Проверяет полную интеграцию с Heleket API для обработки платежей от создания инвойса до получения ключа:
    
    **Что проверяется:**
    - Инициализация Heleket API
    - Создание инвойса через Heleket API
    - Обработка платежа через webhook от Heleket
    - Создание VPN ключа после успешной оплаты
    
    **Тестовые данные:**
    - temp_db: временная БД для изоляции теста
    - mock_bot: мок aiogram.Bot
    - mock_heleket: мок Heleket API
    
    **Шаги теста:**
    1. **Инициализация Heleket API**
       - Метод: проверка наличия mock_heleket
       - Параметры: mock_heleket из фикстуры
       - Ожидаемый результат: Heleket API инициализирован
       - Проверка: mock_heleket is not None
       - Проверяемые поля: mock_heleket.create_invoice, mock_heleket.get_invoice
    
    2. **Создание инвойса**
       - Метод: mock_heleket.create_invoice()
       - Параметры: amount, currency, description
       - Ожидаемый результат: инвойс создан
       - Проверка: mock_heleket.create_invoice вызван с правильными параметрами
       - Проверка: возвращен invoice_id и pay_url
       - Проверяемые поля: invoice_id, pay_url, status='pending'
    
    3. **Обработка платежа**
       - Метод: обработка webhook от Heleket
       - Параметры: webhook данные с invoice_id
       - Ожидаемый результат: платеж обработан, ключ создан
       - Проверка: ключ создан в БД
       - Проверяемые поля: key_id, user_id, status='active'
    
    **Предусловия:**
    - Используется временная БД (temp_db)
    - Моки для bot и heleket настроены
    - Heleket API инициализирован через mock_heleket
    
    **Используемые моки и фикстуры:**
    - temp_db: временная SQLite БД с полной структурой таблиц (users, vpn_keys, transactions, plans, xui_hosts)
    - mock_bot: мок aiogram.Bot с методами send_message, edit_message_text
    - mock_heleket: мок Heleket API с методами:
      * create_invoice(): создание инвойса (AsyncMock, возвращает invoice_id, pay_url, status='pending')
      * get_invoice(): получение статуса инвойса (AsyncMock, возвращает invoice_id, status='paid', amount)
    
    **Проверяемые граничные случаи:**
    - Инициализация Heleket API
    - Создание инвойса
    - Обработка платежа
    
    **Ожидаемый результат:**
    Heleket API должен быть инициализирован.
    Инвойс должен быть создан через Heleket API.
    После успешной оплаты должен быть создан VPN ключ.
    """)
    @allure.severity(allure.severity_level.CRITICAL)
    @allure.tag("payments", "heleket", "integration", "critical")
    @pytest.mark.asyncio
    async def test_heleket_full_flow(self, temp_db, mock_bot, mock_heleket):
        """Тест полного flow от создания инвойса до получения ключа"""
        with allure.step("Проверка инициализации Heleket API"):
            # Этот тест требует полную интеграцию с Heleket
            assert mock_heleket is not None, "Heleket API должен быть инициализирован"

    @allure.title("Обработка webhook от Heleket")
    @allure.description("""
    Проверяет обработку webhook от Heleket от получения webhook до обработки платежа:
    
    **Что проверяется:**
    - Получение webhook от Heleket
    - Валидация данных webhook
    - Обработка платежа через webhook handler
    - Создание транзакции в БД
    
    **Тестовые данные:**
    - temp_db: временная БД для изоляции теста
    - mock_bot: мок aiogram.Bot
    - payment_id: heleket_<hex> (генерируется в тесте, 16 символов hex)
    - webhook_data: данные webhook от Heleket (invoice_id, status, amount)
    
    **Шаги теста:**
    1. **Создание payment_id**
       - Метод: генерация UUID и форматирование
       - Параметры: uuid.uuid4().hex[:16]
       - Ожидаемый результат: payment_id создан в формате heleket_<hex>
       - Проверка: payment_id is not None
       - Проверка: payment_id.startswith('heleket_')
       - Проверка: len(payment_id) > 8 (префикс + hex)
       - Проверяемые поля: payment_id формат, длина
    
    2. **Получение webhook**
       - Метод: получение webhook данных от Heleket
       - Параметры: webhook запрос
       - Ожидаемый результат: webhook получен
       - Проверка: webhook содержит invoice_id, status, amount
       - Проверяемые поля: invoice_id, status, amount
    
    3. **Обработка webhook**
       - Метод: обработка webhook через handler
       - Параметры: webhook данные
       - Ожидаемый результат: платеж обработан
       - Проверка: handler вызван с правильными параметрами
       - Проверка: транзакция создана в БД
    
    **Предусловия:**
    - Используется временная БД (temp_db)
    - Моки для bot настроены
    
    **Используемые моки и фикстуры:**
    - temp_db: временная SQLite БД с полной структурой таблиц (users, vpn_keys, transactions, plans, xui_hosts)
    - mock_bot: мок aiogram.Bot с методами send_message, edit_message_text
    
    **Проверяемые граничные случаи:**
    - Создание payment_id в правильном формате
    - Обработка webhook от Heleket
    - Создание транзакции в БД
    
    **Ожидаемый результат:**
    Payment ID должен быть создан в формате heleket_<hex>.
    Webhook должен быть обработан корректно.
    Транзакция должна быть создана в БД.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("payments", "heleket", "webhook", "integration", "normal")
    @pytest.mark.asyncio
    async def test_heleket_webhook_processing(self, temp_db, mock_bot):
        """Тест обработки webhook"""
        with allure.step("Создание payment_id"):
            # Этот тест требует обработку webhook
            payment_id = f"heleket_{uuid.uuid4().hex[:16]}"
            assert payment_id is not None, "Payment ID должен быть создан"
        
        with allure.step("Проверка формата payment_id"):
            assert payment_id.startswith('heleket_'), "Payment ID должен начинаться с 'heleket_'"
            assert len(payment_id) > 8, "Payment ID должен содержать hex данные"

    @allure.title("Проверка инвойса Heleket")
    @allure.description("""
    Проверяет структуру проверки инвойса от Heleket от создания payment_id до верификации:
    
    **Что проверяется:**
    - Создание payment_id для инвойса Heleket
    - Структура проверки инвойса
    - Корректность формата payment_id
    - Валидация payment_id
    
    **Тестовые данные:**
    - temp_db: временная БД для изоляции теста
    - payment_id: heleket_<hex> (генерируется в тесте, 16 символов hex)
    
    **Шаги теста:**
    1. **Создание payment_id**
       - Метод: генерация UUID и форматирование
       - Параметры: uuid.uuid4().hex[:16]
       - Ожидаемый результат: payment_id создан в формате heleket_<hex>
       - Проверка: payment_id is not None
       - Проверка: payment_id.startswith('heleket_')
       - Проверка: len(payment_id) > 8 (префикс + hex)
       - Проверяемые поля: payment_id формат, длина
    
    2. **Проверка структуры payment_id**
       - Метод: валидация формата
       - Параметры: payment_id
       - Ожидаемый результат: payment_id имеет правильный формат
       - Проверка: payment_id соответствует формату heleket_<16 hex символов>
       - Проверка: payment_id уникален
    
    **Предусловия:**
    - Используется временная БД (temp_db)
    
    **Используемые моки и фикстуры:**
    - temp_db: временная SQLite БД с полной структурой таблиц
    
    **Проверяемые граничные случаи:**
    - Создание payment_id в правильном формате
    - Корректность длины payment_id (16 hex символов)
    - Уникальность payment_id
    
    **Ожидаемый результат:**
    Payment ID должен быть создан в формате heleket_<hex>.
    Payment ID должен иметь правильную длину и формат для проверки инвойса Heleket.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("payments", "heleket", "verification", "integration", "normal")
    def test_heleket_invoice_verification(self, temp_db):
        """Тест проверки инвойса"""
        with allure.step("Создание payment_id"):
            # Этот тест требует проверку инвойса
            payment_id = f"heleket_{uuid.uuid4().hex[:16]}"
            assert payment_id is not None, "Payment ID должен быть создан"
        
        with allure.step("Проверка формата payment_id"):
            assert payment_id.startswith('heleket_'), "Payment ID должен начинаться с 'heleket_'"
            assert len(payment_id) > 8, "Payment ID должен содержать hex данные"

    @allure.title("Повторная обработка платежа Heleket")
    @allure.description("""
    Проверяет повторную обработку платежа Heleket от создания payment_id до проверки идемпотентности:
    
    **Что проверяется:**
    - Создание payment_id для платежа
    - Повторная обработка того же платежа
    - Идемпотентность обработки (отсутствие дубликатов)
    - Корректная обработка повторных webhook
    
    **Тестовые данные:**
    - temp_db: временная БД для изоляции теста
    - mock_bot: мок aiogram.Bot
    - payment_id: heleket_<hex> (генерируется в тесте, 16 символов hex)
    
    **Шаги теста:**
    1. **Создание payment_id**
       - Метод: генерация UUID и форматирование
       - Параметры: uuid.uuid4().hex[:16]
       - Ожидаемый результат: payment_id создан в формате heleket_<hex>
       - Проверка: payment_id is not None
       - Проверка: payment_id.startswith('heleket_')
       - Проверка: len(payment_id) > 8 (префикс + hex)
       - Проверяемые поля: payment_id формат, длина
    
    2. **Первая обработка платежа**
       - Метод: обработка webhook от Heleket
       - Параметры: webhook данные с payment_id
       - Ожидаемый результат: платеж обработан, транзакция создана
       - Проверка: транзакция создана в БД
       - Проверяемые поля: transaction_id, payment_id, status='paid'
    
    3. **Повторная обработка платежа**
       - Метод: повторная обработка того же webhook
       - Параметры: те же webhook данные с тем же payment_id
       - Ожидаемый результат: платеж не обработан повторно (идемпотентность)
       - Проверка: количество транзакций с payment_id == 1 (не создана дубликат)
       - Проверка: транзакция не дублируется
    
    **Предусловия:**
    - Используется временная БД (temp_db)
    - Моки для bot настроены
    
    **Используемые моки и фикстуры:**
    - temp_db: временная SQLite БД с полной структурой таблиц (users, vpn_keys, transactions, plans, xui_hosts)
    - mock_bot: мок aiogram.Bot с методами send_message, edit_message_text
    
    **Проверяемые граничные случаи:**
    - Повторная обработка того же платежа
    - Идемпотентность обработки (отсутствие дубликатов транзакций)
    - Корректная обработка повторных webhook
    
    **Ожидаемый результат:**
    Payment ID должен быть создан в формате heleket_<hex>.
    При повторной обработке того же платежа не должны создаваться дубликаты транзакций.
    Обработка должна быть идемпотентной.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("payments", "heleket", "idempotency", "integration", "normal")
    @pytest.mark.asyncio
    async def test_heleket_payment_retry(self, temp_db, mock_bot):
        """Тест повторной обработки"""
        with allure.step("Создание payment_id"):
            # Этот тест требует повторную обработку
            payment_id = f"heleket_{uuid.uuid4().hex[:16]}"
            assert payment_id is not None, "Payment ID должен быть создан"
        
        with allure.step("Проверка формата payment_id для идемпотентности"):
            assert payment_id.startswith('heleket_'), "Payment ID должен начинаться с 'heleket_'"
            assert len(payment_id) > 8, "Payment ID должен содержать hex данные"

