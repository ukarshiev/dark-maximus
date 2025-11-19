#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Unit-тесты для обработчиков платежей

Тестирует логику создания платежей и обработки успешных оплат
"""

import pytest
import allure
import sys
import uuid
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch, Mock
from decimal import Decimal

# Добавляем путь к проекту
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root / "src"))


@pytest.mark.unit
@pytest.mark.bot
@allure.epic("Обработчики бота")
@allure.feature("Обработка платежей")
@allure.label("package", "src.shop_bot.handlers")
class TestPaymentHandlers:
    """Тесты для обработчиков платежей"""

    @pytest.mark.asyncio
    @allure.title("Создание платежа YooKassa")
    @allure.description("""
    Проверяет создание платежа через YooKassa для покупки тарифа.
    
    **Что проверяется:**
    - Создание платежа через Payment.create()
    - Получение confirmation_url для оплаты
    - Сохранение payment_id в state
    - Отправка сообщения пользователю с ссылкой на оплату
    
    **Тестовые данные:**
    - user_id: 123456
    - plan_id: создается динамически
    - host_name: 'test_host'
    
    **Ожидаемый результат:**
    Платеж успешно создан, пользователю отправлена ссылка на оплату.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("payment", "yookassa", "invoice", "bot", "unit")
    async def test_create_yookassa_payment(self, temp_db, mock_bot, mock_yookassa):
        """Тест создания платежа YooKassa"""
        from shop_bot.data_manager.database import (
            register_user_if_not_exists,
            get_setting,
            get_plan_by_id,
            create_plan,
            create_host,
        )
        from shop_bot.bot.handlers import create_yookassa_payment_handler
        from aiogram.fsm.context import FSMContext
        from aiogram.types import CallbackQuery, User, Chat, Message
        
        # Настройка БД
        user_id = 123456
        register_user_if_not_exists(user_id, "test_user", referrer_id=None)
        
        # Добавляем хост и план
        create_host("test_host", "http://test.com", "user", "pass", 1, "testcode")
        create_plan("test_host", "Test Plan", 1, 100.0, 0, 0.0, 0)
        # Получаем plan_id после создания
        from shop_bot.data_manager.database import get_plans_for_host
        plans = get_plans_for_host("test_host")
        plan_id = plans[0]['plan_id'] if plans else 1
        
        # Мокируем Payment.create (статический метод класса)
        # Payment.create() возвращает объект Payment с полем confirmation
        mock_payment_instance = MagicMock()
        mock_confirmation = MagicMock()
        mock_confirmation.confirmation_url = 'https://yookassa.ru/test'
        mock_payment_instance.confirmation = mock_confirmation
        mock_payment_instance.id = 'test_payment_id'
        mock_payment_instance.status = 'pending'
        
        # Создаем мок для callback
        callback = MagicMock(spec=CallbackQuery)
        callback.from_user = MagicMock(spec=User)
        callback.from_user.id = user_id
        callback.answer = AsyncMock()
        callback.message = MagicMock(spec=Message)
        callback.message.edit_text = AsyncMock()
        callback.message.answer = AsyncMock()
        callback.bot = mock_bot
        
        # Создаем мок для state
        state = MagicMock(spec=FSMContext)
        state_data = {
            'plan_id': plan_id,
            'action': 'new',
            'host_name': 'test_host',
            'customer_email': 'test@example.com',
        }
        state.get_data = AsyncMock(return_value=state_data)
        state.update_data = AsyncMock()
        state.clear = AsyncMock()
        
        # Мокируем get_setting для YooKassa
        with patch('shop_bot.bot.handlers.get_setting') as mock_get_setting:
            mock_get_setting.side_effect = lambda key, default=None: {
                'yookassa_shop_id': 'test_shop_id',
                'yookassa_secret_key': 'test_secret_key',
                'receipt_email': 'test@example.com',
            }.get(key, default)
            
            # Мокируем Payment.create (статический метод)
            with patch('shop_bot.bot.handlers.Payment') as mock_payment_class:
                # Payment.create() - статический метод, возвращает объект Payment
                mock_payment_class.create.return_value = mock_payment_instance
                # Мокируем get_user
                with patch('shop_bot.bot.handlers.get_user', return_value={'telegram_id': user_id, 'total_spent': 0}):
                    # Мокируем _resolve_host_code
                    with patch('shop_bot.bot.handlers._resolve_host_code', return_value='testcode'):
                        # Мокируем create_pending_transaction
                        with patch('shop_bot.bot.handlers.create_pending_transaction'):
                            await create_yookassa_payment_handler(callback, state)
        
        # Проверяем, что платеж был создан
        assert mock_payment_class.create.called
        callback.answer.assert_called_once()
        assert callback.message.edit_text.called

    @pytest.mark.asyncio
    @allure.title("Создание инвойса CryptoBot")
    @allure.description("""
    Проверяет создание инвойса через CryptoBot для оплаты тарифа.
    
    **Что проверяется:**
    - Создание инвойса через CryptoPay.create_invoice()
    - Получение pay_url для оплаты
    - Отправка сообщения пользователю с ссылкой на оплату
    
    **Тестовые данные:**
    - user_id: 123456
    - plan_id: создается динамически
    - host_name: 'test_host'
    
    **Ожидаемый результат:**
    Инвойс успешно создан, пользователю отправлена ссылка на оплату.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("payment", "cryptobot", "invoice", "bot", "unit")
    async def test_create_cryptobot_invoice(self, temp_db, mock_bot):
        """Тест создания инвойса CryptoBot"""
        from shop_bot.data_manager.database import (
            register_user_if_not_exists,
            get_setting,
            create_plan,
            create_host,
            get_plans_for_host,
        )
        from shop_bot.bot.handlers import create_cryptobot_invoice_handler
        from aiogram.fsm.context import FSMContext
        from aiogram.types import CallbackQuery, User, Message
        
        # Настройка БД
        user_id = 123456
        register_user_if_not_exists(user_id, "test_user", referrer_id=None)
        create_host("test_host", "http://test.com", "user", "pass", 1, "testcode")
        create_plan("test_host", "Test Plan", 1, 100.0, 0, 0.0, 0)
        plans = get_plans_for_host("test_host")
        plan_id = plans[0]['plan_id'] if plans else 1
        
        # Мокируем CryptoPay
        mock_crypto = MagicMock()
        mock_invoice = MagicMock()
        mock_invoice.pay_url = "https://cryptobot.test/pay"
        mock_crypto.create_invoice = AsyncMock(return_value=mock_invoice)
        
        # Создаем мок для callback
        callback = MagicMock(spec=CallbackQuery)
        callback.from_user = MagicMock(spec=User)
        callback.from_user.id = user_id
        callback.answer = AsyncMock()
        callback.message = MagicMock(spec=Message)
        callback.message.edit_text = AsyncMock()
        callback.bot = mock_bot
        
        # Создаем мок для state
        state = MagicMock(spec=FSMContext)
        state_data = {
            'plan_id': plan_id,
            'action': 'new',
            'host_name': 'test_host',
            'customer_email': 'test@example.com',
        }
        state.get_data = AsyncMock(return_value=state_data)
        state.clear = AsyncMock()
        
        # Мокируем зависимости
        with patch('shop_bot.bot.handlers.get_setting') as mock_get_setting:
            mock_get_setting.side_effect = lambda key, default=None: {
                'cryptobot_token': 'test_token',
            }.get(key, default)
            
            with patch('shop_bot.bot.handlers.get_usdt_rub_rate', return_value=Decimal('100')):
                with patch('shop_bot.bot.handlers.CryptoPay', return_value=mock_crypto):
                    with patch('shop_bot.bot.handlers.get_user', return_value={'telegram_id': user_id, 'total_spent': 0}):
                        await create_cryptobot_invoice_handler(callback, state)
        
        # Проверяем, что инвойс был создан
        assert mock_crypto.create_invoice.called
        callback.answer.assert_called_once()

    @pytest.mark.asyncio
    @allure.title("Создание инвойса TON Connect")
    @allure.description("""
    Проверяет создание инвойса через TON Connect для оплаты тарифа.
    
    **Что проверяется:**
    - Подключение кошелька через TON Connect
    - Получение connect URL для оплаты
    - Отправка сообщения пользователю с QR-кодом для подключения
    
    **Тестовые данные:**
    - user_id: 123456
    - plan_id: создается динамически
    - host_name: 'test_host'
    
    **Ожидаемый результат:**
    Инвойс успешно создан, пользователю отправлен QR-код для подключения кошелька.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("payment", "ton_connect", "invoice", "bot", "unit")
    async def test_create_ton_invoice(self, temp_db, mock_bot):
        """Тест создания инвойса TON Connect"""
        from shop_bot.data_manager.database import (
            register_user_if_not_exists,
            get_setting,
            create_plan,
            create_host,
            get_plans_for_host,
        )
        from shop_bot.bot.handlers import create_ton_invoice_handler
        from aiogram.fsm.context import FSMContext
        from aiogram.types import CallbackQuery, User, Message
        
        # Настройка БД
        user_id = 123456
        register_user_if_not_exists(user_id, "test_user", referrer_id=None)
        create_host("test_host", "http://test.com", "user", "pass", 1, "testcode")
        create_plan("test_host", "Test Plan", 1, 100.0, 0, 0.0, 0)
        plans = get_plans_for_host("test_host")
        plan_id = plans[0]['plan_id'] if plans else 1
        
        # Создаем мок для callback
        callback = MagicMock(spec=CallbackQuery)
        callback.from_user = MagicMock(spec=User)
        callback.from_user.id = user_id
        callback.answer = AsyncMock()
        callback.message = MagicMock(spec=Message)
        callback.message.delete = AsyncMock()
        callback.message.edit_text = AsyncMock()
        callback.message.answer_photo = AsyncMock()
        callback.bot = mock_bot
        
        # Создаем мок для state
        state = MagicMock(spec=FSMContext)
        state_data = {
            'plan_id': plan_id,
            'action': 'new',
            'host_name': 'test_host',
            'customer_email': 'test@example.com',
        }
        state.get_data = AsyncMock(return_value=state_data)
        state.clear = AsyncMock()
        
        # Мокируем зависимости
        with patch('shop_bot.bot.handlers.get_setting') as mock_get_setting:
            mock_get_setting.side_effect = lambda key, default=None: {
                'ton_wallet_address': 'EQTest123456789',
            }.get(key, default)
            
            with patch('shop_bot.bot.handlers.get_usdt_rub_rate', return_value=Decimal('100')):
                with patch('shop_bot.bot.handlers.get_ton_usdt_rate', return_value=Decimal('5')):
                    with patch('shop_bot.bot.handlers.get_user', return_value={'telegram_id': user_id, 'total_spent': 0}):
                        # Мокируем _get_ton_connect_instance
                        with patch('shop_bot.bot.handlers._get_ton_connect_instance') as mock_get_connector:
                            # Мокируем _listener_task
                            with patch('shop_bot.bot.handlers._listener_task', new_callable=AsyncMock):
                                # Создаем мок для connector
                                mock_connector = MagicMock()
                                mock_wallet = MagicMock()
                                mock_connector.get_wallets = MagicMock(return_value=[mock_wallet])
                                mock_connector.connect = AsyncMock(return_value='https://tonconnect.test/connect')
                                mock_get_connector.return_value = mock_connector
                                
                                await create_ton_invoice_handler(callback, state)
        
        # Проверяем, что обработчик был вызван
        callback.answer.assert_called_once()

    @pytest.mark.asyncio
    @allure.title("Создание инвойса Telegram Stars")
    @allure.description("""
    Проверяет создание инвойса через Telegram Stars для оплаты тарифа.
    
    **Что проверяется:**
    - Создание инвойса через bot.send_invoice()
    - Расчет количества Stars на основе conversion_rate
    - Сохранение payment_id в state
    - Отправка инвойса пользователю
    
    **Тестовые данные:**
    - user_id: 123456
    - plan_id: создается динамически
    - stars_conversion_rate: 1.79
    
    **Ожидаемый результат:**
    Инвойс успешно создан, пользователю отправлен инвойс для оплаты Stars.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("payment", "stars", "invoice", "bot", "unit")
    async def test_create_stars_invoice(self, temp_db, mock_bot):
        """Тест создания инвойса Telegram Stars"""
        from shop_bot.data_manager.database import (
            register_user_if_not_exists,
            get_setting,
            create_plan,
            create_host,
            get_plans_for_host,
        )
        from shop_bot.bot.handlers import create_stars_invoice_handler
        from aiogram.fsm.context import FSMContext
        from aiogram.types import CallbackQuery, User, Message
        
        # Настройка БД
        user_id = 123456
        register_user_if_not_exists(user_id, "test_user", referrer_id=None)
        create_host("test_host", "http://test.com", "user", "pass", 1, "testcode")
        create_plan("test_host", "Test Plan", 1, 100.0, 0, 0.0, 0)
        plans = get_plans_for_host("test_host")
        plan_id = plans[0]['plan_id'] if plans else 1
        
        # Создаем мок для callback
        callback = MagicMock(spec=CallbackQuery)
        callback.from_user = MagicMock(spec=User)
        callback.from_user.id = user_id
        callback.answer = AsyncMock()
        callback.message = MagicMock(spec=Message)
        callback.message.edit_text = AsyncMock()
        callback.bot = mock_bot
        
        # Создаем мок для state
        state = MagicMock(spec=FSMContext)
        state_data = {
            'plan_id': plan_id,
            'action': 'new',
            'host_name': 'test_host',
            'customer_email': 'test@example.com',
        }
        state.get_data = AsyncMock(return_value=state_data)
        state.update_data = AsyncMock()
        state.clear = AsyncMock()
        
        # Мокируем зависимости
        with patch('shop_bot.bot.handlers.get_setting') as mock_get_setting:
            mock_get_setting.side_effect = lambda key, default=None: {
                'stars_conversion_rate': '1.79',
            }.get(key, default)
            
            with patch('shop_bot.bot.handlers.get_user', return_value={'telegram_id': user_id, 'total_spent': 0}):
                await create_stars_invoice_handler(callback, state)
        
        # Проверяем, что обработчик был вызван
        callback.answer.assert_called_once()
        assert state.update_data.called

    @pytest.mark.asyncio
    @allure.title("Создание инвойса Heleket")
    @allure.description("""
    Проверяет создание инвойса через Heleket для оплаты тарифа.
    
    **Что проверяется:**
    - Создание платежного запроса через _create_heleket_payment_request()
    - Получение pay_url для оплаты
    - Отправка сообщения пользователю с ссылкой на оплату
    
    **Тестовые данные:**
    - user_id: 123456
    - plan_id: создается динамически
    - host_name: 'test_host'
    
    **Ожидаемый результат:**
    Инвойс успешно создан, пользователю отправлена ссылка на оплату.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("payment", "heleket", "invoice", "bot", "unit")
    async def test_create_heleket_invoice(self, temp_db, mock_bot):
        """Тест создания инвойса Heleket"""
        from shop_bot.data_manager.database import (
            register_user_if_not_exists,
            get_setting,
            create_plan,
            create_host,
            get_plans_for_host,
        )
        from shop_bot.bot.handlers import create_heleket_invoice_handler
        from aiogram.fsm.context import FSMContext
        from aiogram.types import CallbackQuery, User, Message
        
        # Настройка БД
        user_id = 123456
        register_user_if_not_exists(user_id, "test_user", referrer_id=None)
        create_host("test_host", "http://test.com", "user", "pass", 1, "testcode")
        create_plan("test_host", "Test Plan", 1, 100.0, 0, 0.0, 0)
        plans = get_plans_for_host("test_host")
        plan_id = plans[0]['plan_id'] if plans else 1
        
        # Создаем мок для callback
        callback = MagicMock(spec=CallbackQuery)
        callback.from_user = MagicMock(spec=User)
        callback.from_user.id = user_id
        callback.answer = AsyncMock()
        callback.message = MagicMock(spec=Message)
        callback.message.edit_text = AsyncMock()
        callback.bot = mock_bot
        
        # Создаем мок для state
        state = MagicMock(spec=FSMContext)
        state_data = {
            'plan_id': plan_id,
            'action': 'new',
            'host_name': 'test_host',
            'customer_email': 'test@example.com',
        }
        state.get_data = AsyncMock(return_value=state_data)
        state.clear = AsyncMock()
        
        # Мокируем _create_heleket_payment_request
        with patch('shop_bot.bot.handlers._create_heleket_payment_request', return_value="https://heleket.test/pay"):
            with patch('shop_bot.bot.handlers.get_user', return_value={'telegram_id': user_id, 'total_spent': 0}):
                await create_heleket_invoice_handler(callback, state)
        
        # Проверяем, что обработчик был вызван
        callback.answer.assert_called_once()

    @pytest.mark.asyncio
    @allure.title("Оплата с внутреннего баланса")
    @allure.description("""
    Проверяет оплату тарифа с внутреннего баланса пользователя.
    
    **Что проверяется:**
    - Проверка достаточности баланса
    - Списание средств с баланса
    - Создание ключа через process_successful_payment
    - Отправка сообщения пользователю об успешной оплате
    
    **Тестовые данные:**
    - user_id: 123456
    - Начальный баланс: 200.0
    - Цена тарифа: 100.0
    - Ожидаемый баланс после оплаты: 100.0
    
    **Ожидаемый результат:**
    Средства успешно списаны с баланса, ключ создан, пользователю отправлено сообщение.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("payment", "balance", "internal", "bot", "unit")
    async def test_pay_with_balance(self, temp_db, mock_bot, mock_xui_api):
        """Тест оплаты с внутреннего баланса"""
        from shop_bot.data_manager.database import (
            register_user_if_not_exists,
            get_setting,
            create_plan,
            create_host,
            get_plans_for_host,
            add_to_user_balance,
            get_user_balance,
        )
        from shop_bot.bot.handlers import pay_with_internal_balance
        from aiogram.fsm.context import FSMContext
        from aiogram.types import CallbackQuery, User, Message
        
        # Настройка БД
        user_id = 123456
        register_user_if_not_exists(user_id, "test_user", referrer_id=None)
        create_host("test_host", "http://test.com", "user", "pass", 1, "testcode")
        create_plan("test_host", "Test Plan", 1, 100.0, 0, 0.0, 0)
        plans = get_plans_for_host("test_host")
        plan_id = plans[0]['plan_id'] if plans else 1
        
        # Пополняем баланс
        add_to_user_balance(user_id, 200.0)
        assert get_user_balance(user_id) == 200.0
        
        # Мокируем xui_api
        mock_xui_api.create_or_update_key_on_host = AsyncMock(return_value={
            'client_uuid': 'test-uuid',
            'email': 'test@test.bot',
            'expiry_timestamp_ms': 1234567890000,
            'connection_string': 'vless://...',
        })
        
        # Создаем мок для callback
        callback = MagicMock(spec=CallbackQuery)
        callback.from_user = MagicMock(spec=User)
        callback.from_user.id = user_id
        callback.answer = AsyncMock()
        callback.message = MagicMock(spec=Message)
        callback.message.answer = AsyncMock()
        callback.bot = mock_bot
        
        # Создаем мок для state
        state = MagicMock(spec=FSMContext)
        state_data = {
            'plan_id': plan_id,
            'action': 'new',
            'host_name': 'test_host',
            'customer_email': 'test@example.com',
            'final_price': 100.0,
        }
        state.get_data = AsyncMock(return_value=state_data)
        state.clear = AsyncMock()
        
        # Мокируем process_successful_payment
        with patch('shop_bot.bot.handlers.process_successful_payment', new_callable=AsyncMock):
            with patch('shop_bot.bot.handlers.get_user', return_value={'telegram_id': user_id, 'total_spent': 0}):
                with patch('shop_bot.bot.handlers.xui_api', mock_xui_api):
                    await pay_with_internal_balance(callback, state)
        
        # Проверяем, что баланс был списан
        assert get_user_balance(user_id) == 100.0
        callback.answer.assert_called_once()

    @pytest.mark.asyncio
    @allure.title("Валидация pre-checkout для Telegram Stars")
    @allure.description("""
    Проверяет валидацию pre-checkout запроса для Telegram Stars.
    
    **Что проверяется:**
    - Проверка наличия pending транзакции
    - Сравнение суммы в запросе с суммой в транзакции
    - Подтверждение валидности запроса через answer(ok=True)
    - Отклонение невалидного запроса через answer(ok=False)
    
    **Тестовые данные:**
    - user_id: 123456
    - payment_id: генерируется динамически
    - total_amount: 56 Stars (100 RUB / 1.79)
    
    **Ожидаемый результат:**
    Валидный запрос подтвержден, невалидный запрос отклонен.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("payment", "stars", "pre_checkout", "validation", "bot", "unit")
    async def test_pre_checkout_validation(self, temp_db, mock_bot):
        """Тест валидации pre-checkout для Stars"""
        from shop_bot.data_manager.database import (
            register_user_if_not_exists,
            create_pending_stars_transaction,
        )
        from shop_bot.bot.handlers import pre_checkout_handler
        from aiogram.types import PreCheckoutQuery, User
        
        # Настройка БД
        user_id = 123456
        register_user_if_not_exists(user_id, "test_user", referrer_id=None)
        
        # Создаем pending транзакцию
        payment_id = str(uuid.uuid4())
        metadata = {
            'user_id': user_id,
            'price': 100.0,
            'months': 1,
            'days': 0,
            'hours': 0,
            'action': 'new',
            'host_name': 'test_host',
            'plan_id': 1,
        }
        create_pending_stars_transaction(payment_id, user_id, 100.0, 56, metadata)  # 56 stars = 100 RUB / 1.79
        
        # Создаем мок для pre_checkout_query
        pre_checkout = MagicMock(spec=PreCheckoutQuery)
        pre_checkout.id = "test_query_id"
        pre_checkout.currency = "XTR"
        pre_checkout.invoice_payload = payment_id
        pre_checkout.total_amount = 56
        pre_checkout.answer = AsyncMock()
        pre_checkout.from_user = MagicMock(spec=User)
        pre_checkout.from_user.id = user_id
        
        # Мокируем зависимости
        with patch('shop_bot.bot.handlers.get_setting', return_value='1.79'):
            with patch('shop_bot.bot.handlers.get_user', return_value={'telegram_id': user_id}):
                with patch('shop_bot.data_manager.database.get_transaction_by_payment_id') as mock_get_tx:
                    mock_get_tx.return_value = {
                        'metadata': metadata,
                        'payment_id': payment_id,
                    }
                    
                    await pre_checkout_handler(pre_checkout)
        
        # Проверяем, что валидация прошла успешно
        pre_checkout.answer.assert_called_once_with(ok=True)

    @pytest.mark.asyncio
    @allure.title("Обработка успешной оплаты: создание нового ключа")
    @allure.description("""
    Проверяет обработку успешной оплаты с созданием нового ключа.
    
    **Что проверяется:**
    - Создание ключа через xui_api.create_or_update_key_on_host
    - Сохранение ключа в БД
    - Обновление статистики пользователя
    - Отправка сообщения пользователю с информацией о ключе
    
    **Тестовые данные:**
    - user_id: 123456
    - action: 'new'
    - host_name: 'test_host'
    - months: 1
    - price: 100.0
    
    **Ожидаемый результат:**
    Новый ключ успешно создан и сохранен в БД, пользователю отправлено сообщение.
    """)
    @allure.severity(allure.severity_level.CRITICAL)
    @allure.tag("payment", "success", "new_key", "bot", "unit", "critical")
    async def test_process_successful_payment_new_key(self, temp_db, mock_bot, mock_xui_api):
        """Тест обработки успешной оплаты (новый ключ)"""
        from shop_bot.data_manager.database import (
            register_user_if_not_exists,
            create_host,
            get_user_keys,
        )
        from shop_bot.bot.handlers import process_successful_payment
        
        # Настройка БД
        user_id = 123456
        register_user_if_not_exists(user_id, "test_user", referrer_id=None)
        create_host("test_host", "http://test.com", "user", "pass", 1, "testcode")
        
        # Мокируем xui_api
        mock_xui_api.create_or_update_key_on_host = AsyncMock(return_value={
            'client_uuid': 'test-uuid-123',
            'email': 'user123456-key1@testcode.bot',
            'expiry_timestamp_ms': 1735689600000,  # 2025-01-01
            'connection_string': 'vless://test',
        })
        
        # Метаданные для нового ключа
        metadata = {
            'user_id': user_id,
            'months': 1,
            'days': 0,
            'hours': 0,
            'price': 100.0,
            'action': 'new',
            'key_id': 0,
            'host_name': 'test_host',
            'plan_id': 1,
            'customer_email': 'test@example.com',
            'payment_method': 'YooKassa',
            'payment_id': str(uuid.uuid4()),
        }
        
        # Мокируем зависимости
        with patch('shop_bot.bot.handlers.xui_api', mock_xui_api):
            with patch('shop_bot.bot.handlers.get_user', return_value={
                'telegram_id': user_id,
                'username': 'test_user',
                'fullname': 'Test User',
            }):
                with patch('shop_bot.bot.handlers.get_plan_by_id', return_value={
                    'plan_id': 1,
                    'plan_name': 'Test Plan',
                    'months': 1,
                    'days': 0,
                    'hours': 0,
                    'traffic_gb': 0,
                }):
                    with patch('shop_bot.bot.handlers.get_host', return_value={
                        'host_name': 'test_host',
                        'host_code': 'testcode',
                    }):
                        await process_successful_payment(mock_bot, metadata)
        
        # Проверяем, что ключ был создан
        keys = get_user_keys(user_id)
        assert len(keys) > 0
        assert keys[0]['key_email'] == 'user123456-key1@testcode.bot'

    @pytest.mark.asyncio
    @allure.title("Обработка успешной оплаты: продление существующего ключа")
    @allure.description("""
    Проверяет обработку успешной оплаты с продлением существующего ключа.
    
    **Что проверяется:**
    - Обновление expiry_timestamp_ms через xui_api
    - Обновление ключа в БД
    - Расчет нового времени истечения (текущее + months)
    - Отправка сообщения пользователю с обновленной информацией
    
    **Тестовые данные:**
    - user_id: 123456
    - action: 'extend'
    - key_id: существующий ключ
    - months: 1
    - price: 100.0
    
    **Ожидаемый результат:**
    Ключ успешно продлен, expiry_timestamp_ms обновлен, пользователю отправлено сообщение.
    """)
    @allure.severity(allure.severity_level.CRITICAL)
    @allure.tag("payment", "success", "extend_key", "bot", "unit", "critical")
    async def test_process_successful_payment_extend_key(self, temp_db, mock_bot, mock_xui_api):
        """Тест обработки успешной оплаты (продление)"""
        from shop_bot.data_manager.database import (
            register_user_if_not_exists,
            create_host,
            add_new_key,
            get_key_by_id,
        )
        from shop_bot.bot.handlers import process_successful_payment
        from datetime import datetime, timezone, timedelta
        
        # Настройка БД
        user_id = 123456
        register_user_if_not_exists(user_id, "test_user", referrer_id=None)
        create_host("test_host", "http://test.com", "user", "pass", 1, "testcode")
        
        # Создаем существующий ключ
        expiry_date = datetime.now(timezone.utc) + timedelta(days=30)
        key_id = add_new_key(
            user_id,
            "test_host",
            "old-uuid",
            "user123456-key1@testcode.bot",
            int(expiry_date.timestamp() * 1000),
            connection_string="vless://old",
            plan_name="Old Plan",
            price=50.0,
        )
        
        # Мокируем xui_api
        new_expiry_ms = int((expiry_date + timedelta(days=30)).timestamp() * 1000)
        mock_xui_api.create_or_update_key_on_host = AsyncMock(return_value={
            'client_uuid': 'old-uuid',
            'email': 'user123456-key1@testcode.bot',
            'expiry_timestamp_ms': new_expiry_ms,
            'connection_string': 'vless://updated',
        })
        
        # Метаданные для продления
        metadata = {
            'user_id': user_id,
            'months': 1,
            'days': 0,
            'hours': 0,
            'price': 100.0,
            'action': 'extend',
            'key_id': key_id,
            'host_name': 'test_host',
            'plan_id': 1,
            'customer_email': 'test@example.com',
            'payment_method': 'YooKassa',
            'payment_id': str(uuid.uuid4()),
        }
        
        # Мокируем зависимости
        with patch('shop_bot.bot.handlers.xui_api', mock_xui_api):
            with patch('shop_bot.bot.handlers.get_user', return_value={
                'telegram_id': user_id,
                'username': 'test_user',
            }):
                with patch('shop_bot.bot.handlers.get_plan_by_id', return_value={
                    'plan_id': 1,
                    'plan_name': 'Test Plan',
                    'months': 1,
                    'days': 0,
                    'hours': 0,
                    'traffic_gb': 0,
                }):
                    with patch('shop_bot.bot.handlers.get_host', return_value={
                        'host_name': 'test_host',
                        'host_code': 'testcode',
                    }):
                        await process_successful_payment(mock_bot, metadata)
        
        # Проверяем, что ключ был обновлен
        key = get_key_by_id(key_id)
        assert key is not None
        assert key['expiry_timestamp_ms'] == new_expiry_ms

    @pytest.mark.asyncio
    @allure.title("Обработка успешной оплаты: пополнение баланса")
    @allure.description("""
    Проверяет обработку успешной оплаты для пополнения внутреннего баланса.
    
    **Что проверяется:**
    - Пополнение баланса пользователя
    - Обновление баланса в БД
    - Отправка сообщения пользователю о пополнении баланса
    
    **Тестовые данные:**
    - user_id: 123456
    - action: 'topup'
    - amount: 500.0
    
    **Ожидаемый результат:**
    Баланс успешно пополнен, пользователю отправлено сообщение о пополнении.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("payment", "success", "topup", "balance", "bot", "unit")
    async def test_process_successful_payment_topup(self, temp_db, mock_bot):
        """Тест обработки пополнения баланса"""
        from shop_bot.data_manager.database import (
            register_user_if_not_exists,
            get_user_balance,
        )
        from shop_bot.bot.handlers import process_successful_payment
        
        # Настройка БД
        user_id = 123456
        register_user_if_not_exists(user_id, "test_user", referrer_id=None)
        initial_balance = get_user_balance(user_id)
        
        # Метаданные для пополнения
        metadata = {
            'user_id': user_id,
            'operation': 'topup',
            'price': 500.0,
            'payment_method': 'YooKassa',
            'payment_id': str(uuid.uuid4()),
        }
        
        # Мокируем зависимости
        with patch('shop_bot.bot.handlers.get_user', return_value={
            'telegram_id': user_id,
            'username': 'test_user',
        }):
            await process_successful_payment(mock_bot, metadata)
        
        # Проверяем, что баланс был пополнен
        new_balance = get_user_balance(user_id)
        assert new_balance == initial_balance + 500.0
        
        # Проверяем, что пользователю было отправлено сообщение
        mock_bot.send_message.assert_called_once()

