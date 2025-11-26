#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Unit-тесты для проверки применения часового пояса в сообщениях бота

Проверяет, что функции get_key_info_text() и get_purchase_success_text()
правильно применяют часовой пояс пользователя при форматировании дат.
"""

import sys
from pathlib import Path
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch

import pytest
import allure

# Добавляем путь к модулям проекта
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root / "src"))

from shop_bot.config import get_key_info_text, get_purchase_success_text
from shop_bot.utils.datetime_utils import format_datetime_for_user


@pytest.mark.unit
@allure.epic("Форматирование сообщений")
@allure.feature("Часовой пояс в сообщениях")
@allure.label("package", "src.shop_bot.config")
class TestTimezoneInKeyInfoText:
    """Тесты для применения часового пояса в get_key_info_text"""

    @allure.title("Применение часового пояса Самоа (UTC+13) в информации о ключе")
    @allure.description("""
    Проверяет, что функция get_key_info_text() правильно применяет часовой пояс пользователя
    при форматировании дат создания и истечения ключа.
    
    **Что проверяется:**
    - Форматирование даты создания с учетом часового пояса Самоа (UTC+13)
    - Форматирование даты истечения с учетом часового пояса Самоа (UTC+13)
    - Отображение правильного смещения часового пояса в тексте (UTC+13)
    - Отсутствие UTC+3 в тексте сообщения
    
    **Тестовые данные:**
    - user_timezone: "Pacific/Apia" (Самоа, UTC+13)
    - feature_enabled: True
    - created_date: текущее время UTC
    - expiry_date: текущее время UTC + 1 час
    
    **Ожидаемый результат:**
    Даты должны отображаться в формате "DD.MM.YYYY в HH:MM (UTC+13)" вместо UTC+3.
    """)
    @allure.severity(allure.severity_level.CRITICAL)
    @allure.tag("timezone", "key-info", "samoa", "utc+13", "unit", "critical")
    def test_key_info_text_with_samoa_timezone(self, temp_db):
        """Тест применения часового пояса Самоа в информации о ключе"""
        with allure.step("Подготовка тестовых данных"):
            # Создаем даты в UTC
            now_utc = datetime.now(timezone.utc)
            created_utc = now_utc - timedelta(days=5)
            expiry_utc = now_utc + timedelta(hours=1)
            
            user_timezone = "Pacific/Apia"  # Самоа, UTC+13 (с 2011 года)
            feature_enabled = True
            
            allure.attach(str(created_utc), "Дата создания (UTC)", allure.attachment_type.TEXT)
            allure.attach(str(expiry_utc), "Дата истечения (UTC)", allure.attachment_type.TEXT)
            allure.attach(user_timezone, "Часовой пояс пользователя", allure.attachment_type.TEXT)
        
        with allure.step("Настройка моков для внешних зависимостей"):
            with patch('shop_bot.data_manager.database.get_message_template', return_value=None):
                with patch('shop_bot.data_manager.database.get_or_create_permanent_token', return_value=None):
                    with patch('shop_bot.data_manager.database.get_setting', return_value=None):
                        with allure.step("Вызов функции get_key_info_text с часовым поясом Самоа"):
                            text = get_key_info_text(
                                key_number=1,
                                expiry_date=expiry_utc,
                                created_date=created_utc,
                                connection_string="vless://test-key",
                                status="pay-active",
                                subscription_link=None,
                                provision_mode="key",
                                user_id=None,
                                key_id=None,
                                user_timezone=user_timezone,
                                feature_enabled=feature_enabled,
                                is_trial=False,
                                host_name="Финляндия",
                                plan_name="5. ЛК Подписка",
                                price=1.0,
                                key_auto_renewal_enabled=True,
                            )
                            allure.attach(text, "Сгенерированная информация о ключе", allure.attachment_type.HTML)
        
        with allure.step("Проверка применения часового пояса UTC+13"):
            # Проверяем, что в тексте есть UTC+13 (Самоа использует UTC+13 с 2011 года)
            assert "(UTC+13)" in text, \
                f"В тексте должно быть указано (UTC+13), но найдено: {text}"
            allure.attach("Найдено (UTC+13)", "Проверка часового пояса", allure.attachment_type.TEXT)
        
        with allure.step("Проверка отсутствия UTC+3"):
            # Проверяем, что в тексте НЕТ UTC+3
            assert "(UTC+3)" not in text, \
                f"В тексте не должно быть (UTC+3), но найдено: {text}"
            allure.attach("UTC+3 не найден (корректно)", "Проверка отсутствия UTC+3", allure.attachment_type.TEXT)
        
        with allure.step("Проверка формата дат"):
            # Проверяем, что даты отформатированы правильно
            assert "Приобретён:" in text or "Приобретен:" in text, \
                "В тексте должна быть информация о дате создания"
            assert "Действителен до:" in text, \
                "В тексте должна быть информация о дате истечения"
            
            # Проверяем, что даты содержат правильный формат
            import re
            date_pattern = r'\d{2}\.\d{2}\.\d{4} в \d{2}:\d{2} \(UTC\+13\)'
            matches = re.findall(date_pattern, text)
            assert len(matches) >= 2, \
                f"Должно быть минимум 2 даты в формате с UTC+13, найдено: {len(matches)}"
            allure.attach(str(matches), "Найденные даты с UTC+13", allure.attachment_type.TEXT)

    @allure.title("Применение часового пояса Москва (UTC+3) в информации о ключе")
    @allure.description("""
    Проверяет, что функция get_key_info_text() правильно применяет часовой пояс пользователя
    при форматировании дат для часового пояса Москва (UTC+3).
    
    **Что проверяется:**
    - Форматирование даты создания с учетом часового пояса Москва (UTC+3)
    - Форматирование даты истечения с учетом часового пояса Москва (UTC+3)
    - Отображение правильного смещения часового пояса в тексте (UTC+3)
    
    **Тестовые данные:**
    - user_timezone: "Europe/Moscow" (Москва, UTC+3)
    - feature_enabled: True
    - created_date: текущее время UTC
    - expiry_date: текущее время UTC + 1 час
    
    **Ожидаемый результат:**
    Даты должны отображаться в формате "DD.MM.YYYY в HH:MM (UTC+3)".
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("timezone", "key-info", "moscow", "utc+3", "unit")
    def test_key_info_text_with_moscow_timezone(self, temp_db):
        """Тест применения часового пояса Москва в информации о ключе"""
        with allure.step("Подготовка тестовых данных"):
            now_utc = datetime.now(timezone.utc)
            created_utc = now_utc - timedelta(days=5)
            expiry_utc = now_utc + timedelta(hours=1)
            
            user_timezone = "Europe/Moscow"  # Москва, UTC+3
            feature_enabled = True
            
            allure.attach(str(created_utc), "Дата создания (UTC)", allure.attachment_type.TEXT)
            allure.attach(str(expiry_utc), "Дата истечения (UTC)", allure.attachment_type.TEXT)
            allure.attach(user_timezone, "Часовой пояс пользователя", allure.attachment_type.TEXT)
        
        with allure.step("Настройка моков"):
            with patch('shop_bot.data_manager.database.get_message_template', return_value=None):
                with patch('shop_bot.data_manager.database.get_or_create_permanent_token', return_value=None):
                    with patch('shop_bot.data_manager.database.get_setting', return_value=None):
                        with allure.step("Вызов функции get_key_info_text с часовым поясом Москва"):
                            text = get_key_info_text(
                                key_number=1,
                                expiry_date=expiry_utc,
                                created_date=created_utc,
                                connection_string="vless://test-key",
                                status="pay-active",
                                subscription_link=None,
                                provision_mode="key",
                                user_id=None,
                                key_id=None,
                                user_timezone=user_timezone,
                                feature_enabled=feature_enabled,
                                is_trial=False,
                                host_name="Финляндия",
                                plan_name="5. ЛК Подписка",
                                price=1.0,
                                key_auto_renewal_enabled=True,
                            )
                            allure.attach(text, "Сгенерированная информация о ключе", allure.attachment_type.HTML)
        
        with allure.step("Проверка применения часового пояса UTC+3"):
            assert "(UTC+3)" in text, \
                f"В тексте должно быть указано (UTC+3), но найдено: {text}"
            allure.attach("Найдено (UTC+3)", "Проверка часового пояса", allure.attachment_type.TEXT)

    @allure.title("Отключение часового пояса (feature_enabled=False)")
    @allure.description("""
    Проверяет, что при feature_enabled=False часовой пояс не применяется
    и даты отображаются в UTC+3 (по умолчанию).
    
    **Что проверяется:**
    - При feature_enabled=False часовой пояс пользователя игнорируется
    - Даты отображаются в UTC+3 (по умолчанию)
    
    **Тестовые данные:**
    - user_timezone: "Pacific/Apia" (Самоа, UTC+13)
    - feature_enabled: False
    
    **Ожидаемый результат:**
    Даты должны отображаться в формате "DD.MM.YYYY в HH:MM (UTC+3)" независимо от user_timezone.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("timezone", "key-info", "feature-disabled", "unit")
    def test_key_info_text_with_timezone_disabled(self, temp_db):
        """Тест отключения часового пояса"""
        with allure.step("Подготовка тестовых данных"):
            now_utc = datetime.now(timezone.utc)
            created_utc = now_utc - timedelta(days=5)
            expiry_utc = now_utc + timedelta(hours=1)
            
            user_timezone = "Pacific/Apia"  # Самоа, UTC+13
            feature_enabled = False  # Функция отключена
            
            allure.attach(str(created_utc), "Дата создания (UTC)", allure.attachment_type.TEXT)
            allure.attach(str(expiry_utc), "Дата истечения (UTC)", allure.attachment_type.TEXT)
            allure.attach(f"user_timezone={user_timezone}, feature_enabled={feature_enabled}", 
                         "Параметры часового пояса", allure.attachment_type.TEXT)
        
        with allure.step("Настройка моков"):
            with patch('shop_bot.data_manager.database.get_message_template', return_value=None):
                with patch('shop_bot.data_manager.database.get_or_create_permanent_token', return_value=None):
                    with patch('shop_bot.data_manager.database.get_setting', return_value=None):
                        with allure.step("Вызов функции get_key_info_text с отключенным часовым поясом"):
                            text = get_key_info_text(
                                key_number=1,
                                expiry_date=expiry_utc,
                                created_date=created_utc,
                                connection_string="vless://test-key",
                                status="pay-active",
                                subscription_link=None,
                                provision_mode="key",
                                user_id=None,
                                key_id=None,
                                user_timezone=user_timezone,
                                feature_enabled=feature_enabled,
                                is_trial=False,
                                host_name="Финляндия",
                                plan_name="5. ЛК Подписка",
                                price=1.0,
                                key_auto_renewal_enabled=True,
                            )
                            allure.attach(text, "Сгенерированная информация о ключе", allure.attachment_type.HTML)
        
        with allure.step("Проверка применения UTC+3 по умолчанию"):
            # При feature_enabled=False должен использоваться UTC+3 по умолчанию
            assert "(UTC+3)" in text, \
                f"При feature_enabled=False должно быть (UTC+3), но найдено: {text}"
            allure.attach("Найдено (UTC+3) - корректно для отключенной функции", 
                         "Проверка часового пояса", allure.attachment_type.TEXT)
        
        with allure.step("Проверка отсутствия UTC+13"):
            # UTC+13 не должен применяться при feature_enabled=False
            assert "(UTC+13)" not in text, \
                f"При feature_enabled=False не должно быть (UTC+13), но найдено: {text}"


@pytest.mark.unit
@allure.epic("Форматирование сообщений")
@allure.feature("Часовой пояс в сообщениях")
@allure.label("package", "src.shop_bot.config")
class TestTimezoneInPurchaseSuccessText:
    """Тесты для применения часового пояса в get_purchase_success_text"""

    @allure.title("Применение часового пояса Самоа (UTC+13) в сообщении о покупке")
    @allure.description("""
    Проверяет, что функция get_purchase_success_text() правильно применяет часовой пояс пользователя
    при форматировании даты истечения ключа.
    
    **Что проверяется:**
    - Форматирование даты истечения с учетом часового пояса Самоа (UTC+13)
    - Отображение правильного смещения часового пояса в тексте (UTC+13)
    - Отсутствие UTC+3 в тексте сообщения
    
    **Тестовые данные:**
    - user_timezone: "Pacific/Apia" (Самоа, UTC+13)
    - feature_enabled: True
    - expiry_date: текущее время UTC + 1 час
    
    **Ожидаемый результат:**
    Дата должна отображаться в формате "DD.MM.YYYY в HH:MM (UTC+13)" вместо UTC+3.
    """)
    @allure.severity(allure.severity_level.CRITICAL)
    @allure.tag("timezone", "purchase-success", "samoa", "utc+13", "unit", "critical")
    def test_purchase_success_text_with_samoa_timezone(self, temp_db):
        """Тест применения часового пояса Самоа в сообщении о покупке"""
        with allure.step("Подготовка тестовых данных"):
            now_utc = datetime.now(timezone.utc)
            expiry_utc = now_utc + timedelta(hours=1)
            
            user_timezone = "Pacific/Apia"  # Самоа, UTC+13 (с 2011 года)
            feature_enabled = True
            
            allure.attach(str(expiry_utc), "Дата истечения (UTC)", allure.attachment_type.TEXT)
            allure.attach(user_timezone, "Часовой пояс пользователя", allure.attachment_type.TEXT)
        
        with allure.step("Настройка моков"):
            with patch('shop_bot.data_manager.database.get_message_template', return_value=None):
                with patch('shop_bot.data_manager.database.get_or_create_permanent_token', return_value=None):
                    with patch('shop_bot.data_manager.database.get_setting', return_value=None):
                        with allure.step("Вызов функции get_purchase_success_text с часовым поясом Самоа"):
                            text = get_purchase_success_text(
                                action="new",
                                key_number=1,
                                expiry_date=expiry_utc,
                                is_trial=False,
                                user_id=123456,
                                key_id=1,
                                user_timezone=user_timezone,
                                feature_enabled=feature_enabled,
                            )
                            allure.attach(text, "Сгенерированное сообщение о покупке", allure.attachment_type.HTML)
        
        with allure.step("Проверка применения часового пояса UTC+13"):
            assert "(UTC+13)" in text, \
                f"В тексте должно быть указано (UTC+13), но найдено: {text}"
            allure.attach("Найдено (UTC+13)", "Проверка часового пояса", allure.attachment_type.TEXT)
        
        with allure.step("Проверка отсутствия UTC+3"):
            assert "(UTC+3)" not in text, \
                f"В тексте не должно быть (UTC+3), но найдено: {text}"
            allure.attach("UTC+3 не найден (корректно)", "Проверка отсутствия UTC+3", allure.attachment_type.TEXT)
        
        with allure.step("Проверка формата даты"):
            assert "Действителен до:" in text or "будет действовать до:" in text, \
                "В тексте должна быть информация о дате истечения"
            
            # Проверяем, что дата содержит правильный формат
            import re
            date_pattern = r'\d{2}\.\d{2}\.\d{4} в \d{2}:\d{2} \(UTC\+13\)'
            matches = re.findall(date_pattern, text)
            assert len(matches) >= 1, \
                f"Должна быть минимум 1 дата в формате с UTC+13, найдено: {len(matches)}"
            allure.attach(str(matches), "Найденные даты с UTC+13", allure.attachment_type.TEXT)

    @allure.title("Применение часового пояса Москва (UTC+3) в сообщении о покупке")
    @allure.description("""
    Проверяет, что функция get_purchase_success_text() правильно применяет часовой пояс пользователя
    при форматировании даты для часового пояса Москва (UTC+3).
    
    **Что проверяется:**
    - Форматирование даты истечения с учетом часового пояса Москва (UTC+3)
    - Отображение правильного смещения часового пояса в тексте (UTC+3)
    
    **Тестовые данные:**
    - user_timezone: "Europe/Moscow" (Москва, UTC+3)
    - feature_enabled: True
    - expiry_date: текущее время UTC + 1 час
    
    **Ожидаемый результат:**
    Дата должна отображаться в формате "DD.MM.YYYY в HH:MM (UTC+3)".
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("timezone", "purchase-success", "moscow", "utc+3", "unit")
    def test_purchase_success_text_with_moscow_timezone(self, temp_db):
        """Тест применения часового пояса Москва в сообщении о покупке"""
        with allure.step("Подготовка тестовых данных"):
            now_utc = datetime.now(timezone.utc)
            expiry_utc = now_utc + timedelta(hours=1)
            
            user_timezone = "Europe/Moscow"  # Москва, UTC+3
            feature_enabled = True
            
            allure.attach(str(expiry_utc), "Дата истечения (UTC)", allure.attachment_type.TEXT)
            allure.attach(user_timezone, "Часовой пояс пользователя", allure.attachment_type.TEXT)
        
        with allure.step("Настройка моков"):
            with patch('shop_bot.data_manager.database.get_message_template', return_value=None):
                with patch('shop_bot.data_manager.database.get_or_create_permanent_token', return_value=None):
                    with patch('shop_bot.data_manager.database.get_setting', return_value=None):
                        with allure.step("Вызов функции get_purchase_success_text с часовым поясом Москва"):
                            text = get_purchase_success_text(
                                action="new",
                                key_number=1,
                                expiry_date=expiry_utc,
                                is_trial=False,
                                user_id=123456,
                                key_id=1,
                                user_timezone=user_timezone,
                                feature_enabled=feature_enabled,
                            )
                            allure.attach(text, "Сгенерированное сообщение о покупке", allure.attachment_type.HTML)
        
        with allure.step("Проверка применения часового пояса UTC+3"):
            assert "(UTC+3)" in text, \
                f"В тексте должно быть указано (UTC+3), но найдено: {text}"
            allure.attach("Найдено (UTC+3)", "Проверка часового пояса", allure.attachment_type.TEXT)

    @allure.title("Отключение часового пояса в сообщении о покупке (feature_enabled=False)")
    @allure.description("""
    Проверяет, что при feature_enabled=False часовой пояс не применяется
    и даты отображаются в UTC+3 (по умолчанию).
    
    **Что проверяется:**
    - При feature_enabled=False часовой пояс пользователя игнорируется
    - Даты отображаются в UTC+3 (по умолчанию)
    
    **Тестовые данные:**
    - user_timezone: "Pacific/Apia" (Самоа, UTC+13)
    - feature_enabled: False
    
    **Ожидаемый результат:**
    Дата должна отображаться в формате "DD.MM.YYYY в HH:MM (UTC+3)" независимо от user_timezone.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("timezone", "purchase-success", "feature-disabled", "unit")
    def test_purchase_success_text_with_timezone_disabled(self, temp_db):
        """Тест отключения часового пояса в сообщении о покупке"""
        with allure.step("Подготовка тестовых данных"):
            now_utc = datetime.now(timezone.utc)
            expiry_utc = now_utc + timedelta(hours=1)
            
            user_timezone = "Pacific/Apia"  # Самоа, UTC+13
            feature_enabled = False  # Функция отключена
            
            allure.attach(str(expiry_utc), "Дата истечения (UTC)", allure.attachment_type.TEXT)
            allure.attach(f"user_timezone={user_timezone}, feature_enabled={feature_enabled}", 
                         "Параметры часового пояса", allure.attachment_type.TEXT)
        
        with allure.step("Настройка моков"):
            with patch('shop_bot.data_manager.database.get_message_template', return_value=None):
                with patch('shop_bot.data_manager.database.get_or_create_permanent_token', return_value=None):
                    with patch('shop_bot.data_manager.database.get_setting', return_value=None):
                        with allure.step("Вызов функции get_purchase_success_text с отключенным часовым поясом"):
                            text = get_purchase_success_text(
                                action="new",
                                key_number=1,
                                expiry_date=expiry_utc,
                                is_trial=False,
                                user_id=123456,
                                key_id=1,
                                user_timezone=user_timezone,
                                feature_enabled=feature_enabled,
                            )
                            allure.attach(text, "Сгенерированное сообщение о покупке", allure.attachment_type.HTML)
        
        with allure.step("Проверка применения UTC+3 по умолчанию"):
            # При feature_enabled=False должен использоваться UTC+3 по умолчанию
            assert "(UTC+3)" in text, \
                f"При feature_enabled=False должно быть (UTC+3), но найдено: {text}"
            allure.attach("Найдено (UTC+3) - корректно для отключенной функции", 
                         "Проверка часового пояса", allure.attachment_type.TEXT)
        
        with allure.step("Проверка отсутствия UTC+13"):
            # UTC+13 не должен применяться при feature_enabled=False
            assert "(UTC+13)" not in text, \
                f"При feature_enabled=False не должно быть (UTC+13), но найдено: {text}"

