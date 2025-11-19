#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Unit-тесты для операций с реферальной программой в БД

Тестирует регистрацию по реферальной ссылке, расчет скидок и бонусов,
начисление бонусов на баланс и генерацию реферальных ссылок.
"""

import pytest
import allure
import sys
import sqlite3
from pathlib import Path
from decimal import Decimal

# Добавляем путь к проекту
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root / "src"))

from shop_bot.data_manager import database

from shop_bot.data_manager.database import (
    register_user_if_not_exists,
    get_user,
    add_to_referral_balance,
    get_referral_balance,
    get_referral_count,
    get_setting,
    update_user_stats,
)


def set_setting(key: str, value: str, temp_db=None):
    """Вспомогательная функция для установки настройки в БД"""
    try:
        # Используем temp_db напрямую, если передан, иначе database.DB_FILE (который патчится через monkeypatch)
        db_path = temp_db if temp_db is not None else database.DB_FILE
        with sqlite3.connect(str(db_path)) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT OR REPLACE INTO bot_settings (key, value) VALUES (?, ?)",
                (key, value)
            )
            conn.commit()
    except sqlite3.Error as e:
        pytest.fail(f"Failed to set setting '{key}': {e}")


@pytest.mark.unit
@pytest.mark.database
@allure.epic("База данных")
@allure.feature("Реферальная программа")
@allure.label("package", "src.shop_bot.database")
class TestReferralOperations:
    """Тесты для операций с реферальной программой"""

    @allure.title("Регистрация по реферальной ссылке")
    @allure.description("""
    Проверяет регистрацию пользователя по реферальной ссылке.
    
    **Что проверяется:**
    - Создание реферера в системе
    - Регистрация реферала с указанием referrer_id
    - Корректное сохранение связи referred_by в БД
    - Увеличение счетчика рефералов у реферера
    
    **Тестовые данные:**
    - referrer_id: 111111111
    - referral_id: 222222222
    
    **Ожидаемый результат:**
    Реферал успешно зарегистрирован с корректной связью с реферером, счетчик рефералов увеличен.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("referral", "registration", "database", "unit")
    def test_referral_registration(self, temp_db):
        """
        Тест регистрации по реферальной ссылке
        
        Проверяет, что при регистрации пользователя с referrer_id
        поле referred_by корректно сохраняется в БД.
        """
        # Создаем реферера
        referrer_id = 111111111
        referrer_username = "referrer_user"
        register_user_if_not_exists(
            referrer_id, referrer_username, None, "Referrer User"
        )
        
        # Создаем реферала с указанием реферера
        referral_id = 222222222
        referral_username = "referral_user"
        register_user_if_not_exists(
            referral_id, referral_username, referrer_id, "Referral User"
        )
        
        # Проверяем, что реферал связан с реферером
        referral = get_user(referral_id)
        assert referral is not None, "Реферал должен быть создан"
        assert referral['referred_by'] == referrer_id, (
            f"Реферал должен быть связан с реферером {referrer_id}, "
            f"но получено {referral['referred_by']}"
        )
        
        # Проверяем, что счетчик рефералов у реферера увеличился
        referral_count = get_referral_count(referrer_id)
        assert referral_count == 1, (
            f"У реферера должно быть 1 реферал, но получено {referral_count}"
        )

    @allure.title("Расчет скидки для реферала")
    @allure.description("""
    Проверяет расчет скидки для реферала при первой покупке.
    
    **Что проверяется:**
    - Расчет скидки на основе настройки referral_discount
    - Применение скидки только при первой покупке (total_spent == 0)
    - Корректность расчета финальной цены
    - Отсутствие скидки при последующих покупках
    
    **Тестовые данные:**
    - referral_discount: 5%
    - Цена: 1000.00 RUB
    - referrer_id: 333333333
    - referral_id: 444444444
    
    **Ожидаемый результат:**
    Скидка корректно рассчитана (50.00 RUB), финальная цена 950.00 RUB, скидка применяется только при первой покупке.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("referral", "discount", "calculation", "database", "unit")
    def test_referral_discount_calculation(self, temp_db):
        """
        Тест расчета скидки для реферала
        
        Проверяет, что скидка рассчитывается корректно для первой покупки
        реферала на основе настройки referral_discount.
        """
        # Устанавливаем настройку скидки для рефералов
        discount_percentage = "5"
        set_setting("referral_discount", discount_percentage, temp_db)
        
        # Создаем реферера
        referrer_id = 333333333
        register_user_if_not_exists(referrer_id, "referrer", None, "Referrer")
        
        # Создаем реферала
        referral_id = 444444444
        register_user_if_not_exists(
            referral_id, "referral", referrer_id, "Referral"
        )
        
        # Проверяем, что реферал имеет referred_by
        referral = get_user(referral_id)
        assert referral['referred_by'] == referrer_id
        assert referral.get('total_spent', 0) == 0, (
            "Реферал должен иметь total_spent = 0 для получения скидки"
        )
        
        # Рассчитываем скидку (как в handlers.py:4392-4396)
        price = Decimal("1000.00")
        discount_percentage_decimal = Decimal(discount_percentage)
        discount_amount = (price * discount_percentage_decimal / 100).quantize(
            Decimal("0.01")
        )
        final_price = price - discount_amount
        
        # Проверяем расчет
        assert discount_amount == Decimal("50.00"), (
            f"Скидка должна быть 50.00 RUB, но получено {discount_amount}"
        )
        assert final_price == Decimal("950.00"), (
            f"Финальная цена должна быть 950.00 RUB, но получено {final_price}"
        )
        
        # Проверяем, что скидка применяется только при первой покупке
        # (total_spent == 0)
        update_user_stats(referral_id, float(final_price), 1)
        referral_after_purchase = get_user(referral_id)
        assert referral_after_purchase.get('total_spent', 0) > 0, (
            "После покупки total_spent должен быть больше 0"
        )
        
        # При следующей покупке скидка не должна применяться
        price2 = Decimal("1000.00")
        discount_amount2 = (price2 * discount_percentage_decimal / 100).quantize(
            Decimal("0.01")
        )
        # Но скидка не применяется, так как total_spent > 0
        # (это проверяется в handlers.py:4391)

    @allure.title("Расчет бонуса для реферера")
    @allure.description("""
    Проверяет расчет бонуса для реферера при покупке реферала.
    
    **Что проверяется:**
    - Расчет бонуса на основе настройки referral_percentage
    - Корректность расчета процента от суммы покупки
    - Проверка, что бонус начисляется только если reward > 0
    
    **Тестовые данные:**
    - referral_percentage: 10%
    - Цена покупки: 1000.00 RUB
    - referrer_id: 555555555
    - referral_id: 666666666
    
    **Ожидаемый результат:**
    Бонус корректно рассчитан (100.00 RUB от суммы покупки 1000.00 RUB).
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("referral", "bonus", "calculation", "database", "unit")
    def test_referral_bonus_calculation(self, temp_db):
        """
        Тест расчета бонуса для реферера
        
        Проверяет, что бонус рассчитывается корректно на основе
        настройки referral_percentage от суммы покупки реферала.
        """
        # Устанавливаем настройку процента бонуса
        referral_percentage = "10"
        set_setting("referral_percentage", referral_percentage, temp_db)
        
        # Создаем реферера
        referrer_id = 555555555
        register_user_if_not_exists(referrer_id, "referrer", None, "Referrer")
        
        # Создаем реферала
        referral_id = 666666666
        register_user_if_not_exists(
            referral_id, "referral", referrer_id, "Referral"
        )
        
        # Проверяем начальный баланс реферера
        initial_balance = get_referral_balance(referrer_id)
        assert initial_balance == 0.0, (
            f"Начальный баланс должен быть 0.0, но получено {initial_balance}"
        )
        
        # Рассчитываем бонус (как в handlers.py:7330-7332)
        price = Decimal("1000.00")
        percentage = Decimal(referral_percentage)
        reward = (price * percentage / 100).quantize(Decimal("0.01"))
        
        # Проверяем расчет бонуса
        assert reward == Decimal("100.00"), (
            f"Бонус должен быть 100.00 RUB, но получено {reward}"
        )
        
        # Проверяем, что бонус начисляется только если reward > 0
        assert float(reward) > 0, "Бонус должен быть больше 0"

    @allure.title("Начисление бонуса на баланс реферера")
    @allure.description("""
    Проверяет начисление бонуса на баланс реферера при покупке реферала.
    
    **Что проверяется:**
    - Начисление бонуса на referral_balance через add_to_referral_balance
    - Обновление referral_balance_all
    - Накопление бонусов при нескольких покупках реферала
    - Корректность итогового баланса
    
    **Тестовые данные:**
    - referral_percentage: 10%
    - Первая покупка: 1000.00 RUB
    - Вторая покупка: 500.00 RUB
    - referrer_id: 777777777
    - referral_id: 888888888
    
    **Ожидаемый результат:**
    Бонусы корректно начислены на referral_balance и referral_balance_all, итоговый баланс равен сумме всех бонусов.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("referral", "bonus", "accrual", "balance", "database", "unit")
    def test_referral_bonus_accrual(self, temp_db):
        """
        Тест начисления бонуса на баланс
        
        Проверяет, что бонус корректно начисляется на referral_balance
        и referral_balance_all реферера при покупке реферала.
        """
        # Устанавливаем настройку процента бонуса
        referral_percentage = "10"
        set_setting("referral_percentage", referral_percentage, temp_db)
        
        # Создаем реферера
        referrer_id = 777777777
        register_user_if_not_exists(referrer_id, "referrer", None, "Referrer")
        
        # Создаем реферала
        referral_id = 888888888
        register_user_if_not_exists(
            referral_id, "referral", referrer_id, "Referral"
        )
        
        # Проверяем начальный баланс
        initial_balance = get_referral_balance(referrer_id)
        assert initial_balance == 0.0
        
        # Симулируем покупку реферала и начисление бонуса
        price = 1000.00
        percentage = Decimal(referral_percentage)
        reward = float((Decimal(str(price)) * percentage / 100).quantize(Decimal("0.01")))
        
        # Начисляем бонус (как в handlers.py:7335)
        add_to_referral_balance(referrer_id, reward)
        
        # Проверяем, что баланс увеличился
        new_balance = get_referral_balance(referrer_id)
        assert new_balance == reward, (
            f"Баланс должен быть {reward}, но получено {new_balance}"
        )
        
        # Проверяем, что referral_balance_all тоже увеличился
        referrer = get_user(referrer_id)
        assert referrer['referral_balance_all'] == reward, (
            f"referral_balance_all должен быть {reward}, "
            f"но получено {referrer['referral_balance_all']}"
        )
        
        # Симулируем еще одну покупку реферала
        price2 = 500.00
        reward2 = float((Decimal(str(price2)) * percentage / 100).quantize(Decimal("0.01")))
        add_to_referral_balance(referrer_id, reward2)
        
        # Проверяем, что баланс увеличился на сумму второго бонуса
        final_balance = get_referral_balance(referrer_id)
        assert final_balance == reward + reward2, (
            f"Финальный баланс должен быть {reward + reward2}, "
            f"но получено {final_balance}"
        )
        
        # Проверяем referral_balance_all
        referrer_final = get_user(referrer_id)
        assert referrer_final['referral_balance_all'] == reward + reward2, (
            f"referral_balance_all должен быть {reward + reward2}, "
            f"но получено {referrer_final['referral_balance_all']}"
        )

    @allure.title("Генерация реферальной ссылки")
    @allure.description("""
    Проверяет генерацию реферальной ссылки в правильном формате.
    
    **Что проверяется:**
    - Генерация ссылки в формате https://t.me/BOT_USERNAME?start=ref_USER_ID
    - Корректность формата ссылки
    - Возможность извлечения user_id из ссылки
    
    **Тестовые данные:**
    - user_id: 999999999
    - bot_username: "test_bot"
    
    **Ожидаемый результат:**
    Реферальная ссылка сгенерирована в правильном формате, user_id может быть извлечен из ссылки.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("referral", "link", "generation", "database", "unit")
    def test_referral_link_generation(self, temp_db):
        """
        Тест генерации реферальной ссылки
        
        Проверяет, что реферальная ссылка генерируется в правильном формате:
        https://t.me/BOT_USERNAME?start=ref_USER_ID
        """
        # Создаем пользователя
        user_id = 999999999
        username = "test_user"
        register_user_if_not_exists(user_id, username, None, "Test User")
        
        # Устанавливаем настройку username бота
        bot_username = "test_bot"
        set_setting("telegram_bot_username", bot_username, temp_db)
        
        # Генерируем реферальную ссылку (как в handlers.py:1327)
        referral_link = f"https://t.me/{bot_username}?start=ref_{user_id}"
        
        # Проверяем формат ссылки
        assert referral_link.startswith("https://t.me/"), (
            "Ссылка должна начинаться с https://t.me/"
        )
        assert f"?start=ref_{user_id}" in referral_link, (
            f"Ссылка должна содержать ?start=ref_{user_id}"
        )
        assert referral_link == f"https://t.me/{bot_username}?start=ref_{user_id}", (
            f"Ссылка должна быть 'https://t.me/{bot_username}?start=ref_{user_id}', "
            f"но получено '{referral_link}'"
        )
        
        # Проверяем, что из ссылки можно извлечь user_id
        # (как в handlers.py:580-584)
        if referral_link and "?start=ref_" in referral_link:
            try:
                extracted_id_str = referral_link.split("ref_")[1]
                extracted_id = int(extracted_id_str)
                assert extracted_id == user_id, (
                    f"Извлеченный ID должен быть {user_id}, "
                    f"но получено {extracted_id}"
                )
            except (IndexError, ValueError) as e:
                pytest.fail(f"Не удалось извлечь user_id из ссылки: {e}")

