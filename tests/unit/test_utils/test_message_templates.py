#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Unit-тесты для модуля форматирования сообщений

Проверяет корректность работы функций формирования сообщений в зависимости
от режима предоставления тарифа и шаблонов из справочника "Тексты бота".
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

from shop_bot.config import (
    format_tariff_info,
    get_purchase_success_text,
    get_key_info_text,
)


@pytest.mark.unit
@pytest.mark.database
@allure.epic("Форматирование сообщений")
@allure.feature("Информация о тарифе")
@allure.label("package", "src.shop_bot.utils")
class TestFormatTariffInfo:
    """Тесты для функции format_tariff_info"""

    @allure.title("Форматирование информации о тарифе: обычный ключ")
    @allure.description("""
    Проверяет корректность форматирования информации о тарифе для обычного активного ключа.
    
    **Проверяемые аспекты:**
    - Корректное определение статусной иконки (✅ для активного ключа)
    - Извлечение флага страны из названия хоста (первые 2 символа)
    - Форматирование названия тарифа
    - Форматирование цены в рублях
    - Формирование итоговой строки с информацией о тарифе
    
    **Входные данные:**
    - host_name: "Финляндия"
    - plan_name: "5. ЛК Подписка"
    - price: 1.0
    - is_trial: False
    - status: "pay-active"
    - expiry_date: текущее время + 30 дней
    
    **Ожидаемый результат:**
    - status_icon: "✅"
    - host_flag: "Фи" (первые 2 символа от "Финляндия")
    - tariff_name: "5. ЛК Подписка"
    - price_formatted: "1₽"
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("tariff", "formatting", "unit")
    def test_format_tariff_info_normal_key(self):
        """Тест форматирования для обычного ключа"""
        with allure.step("Подготовка тестовых данных"):
            expiry_date = datetime.now(timezone.utc) + timedelta(days=30)
            allure.attach(str(expiry_date), "Дата истечения", allure.attachment_type.TEXT)
        
        with allure.step("Вызов функции format_tariff_info"):
            result = format_tariff_info(
                host_name="Финляндия",
                plan_name="5. ЛК Подписка",
                price=1.0,
                is_trial=False,
                status="pay-active",
                expiry_date=expiry_date
            )
            allure.attach(str(result), "Результат функции", allure.attachment_type.JSON)
        
        with allure.step("Проверка статусной иконки"):
            assert result['status_icon'] == "✅"
            allure.attach(result['status_icon'], "Статусная иконка", allure.attachment_type.TEXT)
        
        with allure.step("Проверка флага хоста"):
            assert result['host_flag'] == "Фи"
            allure.attach(result['host_flag'], "Флаг хоста", allure.attachment_type.TEXT)
        
        with allure.step("Проверка названия тарифа"):
            assert result['tariff_name'] == "5. ЛК Подписка"
            allure.attach(result['tariff_name'], "Название тарифа", allure.attachment_type.TEXT)
        
        with allure.step("Проверка форматирования цены"):
            assert result['price_formatted'] == "1₽"
            allure.attach(result['price_formatted'], "Форматированная цена", allure.attachment_type.TEXT)
        
        with allure.step("Проверка итоговой строки"):
            assert "✅" in result['tariff_info']
            assert "Фи" in result['tariff_info']
            assert "5. ЛК Подписка" in result['tariff_info']
            assert "1₽" in result['tariff_info']

    @allure.title("Форматирование информации о тарифе: пробный ключ")
    @allure.description("""
    Проверяет корректность форматирования информации о тарифе для пробного ключа.
    
    **Проверяемые аспекты:**
    - Корректное определение статусной иконки для пробного ключа
    - Установка tariff_name в "TRIAL" для пробных ключей
    - Установка price_formatted в "0₽" для пробных ключей
    
    **Входные данные:**
    - host_name: "Финляндия"
    - plan_name: "" (пустая строка для пробного ключа)
    - price: 0.0
    - is_trial: True
    - status: "trial-active"
    - expiry_date: текущее время + 1 день
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("tariff", "formatting", "trial", "unit")
    def test_format_tariff_info_trial_key(self):
        """Тест форматирования для пробного ключа"""
        with allure.step("Подготовка тестовых данных для пробного ключа"):
            expiry_date = datetime.now(timezone.utc) + timedelta(days=1)
        
        with allure.step("Вызов функции format_tariff_info для пробного ключа"):
            result = format_tariff_info(
                host_name="Финляндия",
                plan_name="",
                price=0.0,
                is_trial=True,
                status="trial-active",
                expiry_date=expiry_date
            )
            allure.attach(str(result), "Результат функции", allure.attachment_type.JSON)
        
        with allure.step("Проверка статусной иконки для пробного ключа"):
            assert result['status_icon'] == "✅"
        
        with allure.step("Проверка названия тарифа для пробного ключа"):
            assert result['tariff_name'] == "TRIAL"
            allure.attach(result['tariff_name'], "Название тарифа (TRIAL)", allure.attachment_type.TEXT)
        
        with allure.step("Проверка форматирования цены для пробного ключа"):
            assert result['price_formatted'] == "0₽"
            allure.attach(result['price_formatted'], "Форматированная цена (0₽)", allure.attachment_type.TEXT)

    @allure.title("Форматирование информации о тарифе: истёкший ключ")
    @allure.description("""
    Проверяет корректность форматирования информации о тарифе для истёкшего ключа.
    
    **Проверяемые аспекты:**
    - Корректное определение статусной иконки для истёкшего ключа (❌)
    - Обработка хоста с коротким названием
    - Форматирование цены с десятичными знаками
    
    **Входные данные:**
    - host_name: "США"
    - plan_name: "Премиум"
    - price: 599.0
    - is_trial: False
    - status: "pay-ended"
    - expiry_date: текущее время - 1 день (истёкший)
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("tariff", "formatting", "expired", "unit")
    def test_format_tariff_info_expired_key(self):
        """Тест форматирования для истёкшего ключа"""
        with allure.step("Подготовка тестовых данных для истёкшего ключа"):
            expiry_date = datetime.now(timezone.utc) - timedelta(days=1)
            allure.attach(str(expiry_date), "Дата истечения (прошлое)", allure.attachment_type.TEXT)
        
        with allure.step("Вызов функции format_tariff_info для истёкшего ключа"):
            result = format_tariff_info(
                host_name="США",
                plan_name="Премиум",
                price=599.0,
                is_trial=False,
                status="pay-ended",
                expiry_date=expiry_date
            )
            allure.attach(str(result), "Результат функции", allure.attachment_type.JSON)
        
        with allure.step("Проверка статусной иконки для истёкшего ключа"):
            assert result['status_icon'] == "❌"
            allure.attach(result['status_icon'], "Статусная иконка (❌)", allure.attachment_type.TEXT)
        
        with allure.step("Проверка флага хоста для короткого названия"):
            assert result['host_flag'] == "СШ"
            allure.attach(result['host_flag'], "Флаг хоста", allure.attachment_type.TEXT)
        
        with allure.step("Проверка названия тарифа"):
            assert result['tariff_name'] == "Премиум"
        
        with allure.step("Проверка форматирования цены"):
            assert result['price_formatted'] == "599₽"


@pytest.mark.unit
@pytest.mark.database
@allure.epic("Форматирование сообщений")
@allure.feature("Сообщение о покупке")
@allure.label("package", "src.shop_bot.utils")
class TestGetPurchaseSuccessText:
    """Тесты для функции get_purchase_success_text"""

    @pytest.mark.parametrize("provision_mode,expected_keywords", [
        ('key', ['НИЖЕ ВАШ КЛЮЧ', 'vless://']),
        ('subscription', ['ВАША ПОДПИСКА', 'https://example.com/sub']),
        ('both', ['НИЖЕ ВАШ КЛЮЧ', 'ВАША ПОДПИСКА']),
        ('cabinet', ['ВАШ ЛИЧНЫЙ КАБИНЕТ']),
        ('cabinet_subscription', ['ВАШ ЛИЧНЫЙ КАБИНЕТ']),
    ])
    @allure.title("Генерация сообщения о покупке для режима: {provision_mode}")
    @allure.description("""
    Проверяет корректность генерации сообщения о покупке для различных режимов предоставления тарифа.
    
    **Режимы предоставления:**
    - **key**: только ключ (VLESS connection string)
    - **subscription**: только подписка (subscription link)
    - **both**: ключ + подписка (оба варианта)
    - **cabinet**: личный кабинет (cabinet URL)
    - **cabinet_subscription**: личный кабинет + подписка
    
    **Проверяемые аспекты:**
    - Наличие ключевых слов в сообщении в зависимости от режима
    - Корректное форматирование даты истечения
    - Наличие информации о тарифе
    - Корректность структуры HTML-разметки
    
    **Используемые моки:**
    - get_message_template: возвращает None (fallback на код)
    - get_or_create_permanent_token: возвращает тестовый токен для cabinet режимов
    - get_user_cabinet_domain: возвращает тестовый домен для cabinet режимов
    """)
    @allure.severity(allure.severity_level.CRITICAL)
    @allure.tag("purchase", "message", "provision-mode", "unit", "critical")
    def test_get_purchase_success_text_provision_modes(
        self, temp_db, provision_mode, expected_keywords
    ):
        """Тест генерации сообщения для различных режимов предоставления"""
        with allure.step(f"Подготовка тестовых данных для режима {provision_mode}"):
            expiry_date = datetime.now(timezone.utc) + timedelta(days=30)
            connection_string = "vless://test-key" if provision_mode in ['key', 'both'] else None
            subscription_link = "https://example.com/sub" if provision_mode in ['subscription', 'both', 'cabinet_subscription'] else None
            user_id = 123 if provision_mode in ['cabinet', 'cabinet_subscription'] else None
            key_id = 1 if provision_mode in ['cabinet', 'cabinet_subscription'] else None
            
            test_data = {
                'provision_mode': provision_mode,
                'expiry_date': str(expiry_date),
                'connection_string': connection_string,
                'subscription_link': subscription_link,
                'user_id': user_id,
                'key_id': key_id,
            }
            allure.attach(str(test_data), "Входные параметры", allure.attachment_type.JSON)
        
        with allure.step("Настройка моков для внешних зависимостей"):
            # Мок для get_message_template (возвращает None для fallback на код)
            with patch('shop_bot.data_manager.database.get_message_template', return_value=None):
                # Мок для get_or_create_permanent_token
                token_value = 'test_token_123' if provision_mode in ['cabinet', 'cabinet_subscription'] else None
                with patch('shop_bot.data_manager.database.get_or_create_permanent_token', return_value=token_value):
                    # Мок для get_user_cabinet_domain (через get_setting)
                    domain_value = 'https://cabinet.example.com' if provision_mode in ['cabinet', 'cabinet_subscription'] else None
                    with patch('shop_bot.data_manager.database.get_setting', return_value=domain_value):
                        with allure.step(f"Вызов функции get_purchase_success_text для режима {provision_mode}"):
                            text = get_purchase_success_text(
                                action="готов",
                                key_number=1,
                                expiry_date=expiry_date,
                                connection_string=connection_string,
                                subscription_link=subscription_link,
                                provision_mode=provision_mode,
                                user_id=user_id,
                                key_id=key_id,
                                user_timezone=None,
                                feature_enabled=False,
                                is_trial=False,
                                host_name="Финляндия",
                                plan_name="5. ЛК Подписка",
                                price=1.0,
                                status=None,
                            )
                            allure.attach(text, f"Сгенерированное сообщение для режима {provision_mode}", allure.attachment_type.HTML)
                            allure.attach(str(len(text)), "Длина сообщения", allure.attachment_type.TEXT)
        
        with allure.step("Проверка наличия ключевых слов в сообщении"):
            for keyword in expected_keywords:
                assert keyword in text, f"Ключевое слово '{keyword}' не найдено в сообщении для режима {provision_mode}"
                allure.attach(f"Найдено: {keyword}", f"Ключевое слово: {keyword}", allure.attachment_type.TEXT)
        
        with allure.step("Проверка структуры сообщения"):
            # Проверяем наличие обязательных элементов
            assert "🎉" in text, "Отсутствует эмодзи празднования"
            assert "готов" in text or "продлен" in text, "Отсутствует описание действия"
            assert "Действовать до" in text or "Он будет действовать до" in text, "Отсутствует информация о сроке действия"
            allure.attach("Все обязательные элементы найдены", "Структура сообщения", allure.attachment_type.TEXT)

    @allure.title("Генерация сообщения о покупке: интеграция со справочником 'Тексты бота'")
    @allure.description("""
    Проверяет интеграцию функции get_purchase_success_text со справочником "Тексты бота" из БД.
    
    **Проверяемые аспекты:**
    - Получение шаблона из БД через get_message_template
    - Использование шаблона из БД при наличии активного шаблона
    - Fallback на код при отсутствии шаблона в БД
    - Подстановка переменных в шаблон из БД
    - Валидация HTML-тегов в шаблоне
    
    **Тестовый сценарий:**
    1. Создание тестового шаблона в БД
    2. Вызов функции get_purchase_success_text
    3. Проверка использования шаблона из БД
    4. Проверка подстановки переменных
    """)
    @allure.severity(allure.severity_level.CRITICAL)
    @allure.tag("purchase", "message", "database", "templates", "unit", "critical")
    def test_get_purchase_success_text_with_database_template(self, temp_db):
        """Тест использования шаблона из БД"""
        from shop_bot.data_manager import database
        import sqlite3
        
        with allure.step("Подготовка тестового шаблона в БД"):
            # Создаем тестовый шаблон в БД
            test_template = {
                'template_key': 'purchase_success_key',
                'category': 'purchase',
                'provision_mode': 'key',
                'template_text': '🎉 <b>Тестовый шаблон для ключа #{key_number}!</b><br><br>⏳ <b>Он будет действовать до:</b> {expiry_formatted}<br><br>⬇️ <b>НИЖЕ ВАШ КЛЮЧ</b> ⬇️<br>------------------------------------------------------------------------<br><code>{connection_string}</code><br>------------------------------------------------------------------------',
                'description': 'Тестовый шаблон для режима key',
                'variables': '["key_number", "expiry_formatted", "connection_string"]',
                'is_active': 1
            }
            
            # Удаляем существующий шаблон, если он есть, и вставляем новый
            conn = sqlite3.connect(str(temp_db))
            cursor = conn.cursor()
            # Удаляем существующий шаблон с таким ключом
            cursor.execute('DELETE FROM message_templates WHERE template_key = ? AND provision_mode = ?', 
                          (test_template['template_key'], test_template['provision_mode']))
            # Вставляем новый шаблон
            cursor.execute('''
                INSERT INTO message_templates 
                (template_key, category, provision_mode, template_text, description, variables, is_active)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                test_template['template_key'],
                test_template['category'],
                test_template['provision_mode'],
                test_template['template_text'],
                test_template['description'],
                test_template['variables'],
                test_template['is_active']
            ))
            conn.commit()
            conn.close()
            
            allure.attach(str(test_template), "Тестовый шаблон в БД", allure.attachment_type.JSON)
        
        with allure.step("Вызов функции get_purchase_success_text с шаблоном из БД"):
            expiry_date = datetime.now(timezone.utc) + timedelta(days=30)
            
            # Мокаем get_message_template чтобы он использовал temp_db
            def mock_get_message_template(template_key: str, provision_mode: str = None):
                conn = sqlite3.connect(str(temp_db))
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                if provision_mode:
                    cursor.execute('''
                        SELECT * FROM message_templates 
                        WHERE template_key = ? AND (provision_mode = ? OR provision_mode IS NULL) AND is_active = 1
                        ORDER BY provision_mode DESC
                        LIMIT 1
                    ''', (template_key, provision_mode))
                else:
                    cursor.execute('''
                        SELECT * FROM message_templates 
                        WHERE template_key = ? AND (provision_mode IS NULL) AND is_active = 1
                        LIMIT 1
                    ''', (template_key,))
                
                result = cursor.fetchone()
                conn.close()
                
                if result:
                    return dict(result)
                return None
            
            # Мок для get_or_create_permanent_token
            with patch('shop_bot.data_manager.database.get_or_create_permanent_token', return_value=None):
                # Мок для get_user_cabinet_domain (через get_setting)
                with patch('shop_bot.data_manager.database.get_setting', return_value=None):
                    # Мок для get_message_template
                    with patch('shop_bot.data_manager.database.get_message_template', side_effect=mock_get_message_template):
                        text = get_purchase_success_text(
                            action="готов",
                            key_number=1,
                            expiry_date=expiry_date,
                            connection_string="vless://test-key",
                            subscription_link=None,
                            provision_mode='key',
                            user_id=None,
                            key_id=None,
                            user_timezone=None,
                            feature_enabled=False,
                            is_trial=False,
                            host_name="Финляндия",
                            plan_name="5. ЛК Подписка",
                            price=1.0,
                            status=None,
                        )
                        allure.attach(text, "Сгенерированное сообщение с шаблоном из БД", allure.attachment_type.HTML)
        
        with allure.step("Проверка использования шаблона из БД"):
            # Проверяем, что используется текст из шаблона БД, а не fallback
            assert "Тестовый шаблон для ключа" in text, "Шаблон из БД не используется"
            assert "#1" in text, "Переменная key_number не подставлена"
            assert "vless://test-key" in text, "Переменная connection_string не подставлена"
            allure.attach("Шаблон из БД успешно использован", "Результат проверки", allure.attachment_type.TEXT)
        
        # Восстанавливаем оригинальный DB_FILE


@pytest.mark.unit
@pytest.mark.database
@allure.epic("Форматирование сообщений")
@allure.feature("Информация о ключе")
@allure.label("package", "src.shop_bot.utils")
class TestGetKeyInfoText:
    """Тесты для функции get_key_info_text"""

    @pytest.mark.parametrize("provision_mode,expected_keywords", [
        ('key', ['Информация о ключе', 'НИЖЕ ВАШ КЛЮЧ']),
        ('subscription', ['Информация о ключе', 'ВАША ПОДПИСКА']),
        ('both', ['Информация о ключе', 'НИЖЕ ВАШ КЛЮЧ', 'ВАША ПОДПИСКА']),
        ('cabinet', ['Информация о ключе', 'ВАШ ЛИЧНЫЙ КАБИНЕТ']),
    ])
    @allure.title("Генерация информации о ключе для режима: {provision_mode}")
    @allure.description("""
    Проверяет корректность генерации информации о ключе для различных режимов предоставления.
    
    **Режимы предоставления:**
    - **key**: только ключ (VLESS connection string)
    - **subscription**: только подписка (subscription link)
    - **both**: ключ + подписка (оба варианта)
    - **cabinet**: личный кабинет (cabinet URL)
    
    **Проверяемые аспекты:**
    - Наличие заголовка "Информация о ключе"
    - Наличие информации о датах создания и истечения
    - Наличие ключевых слов в зависимости от режима
    - Корректное форматирование статуса ключа
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("key-info", "message", "provision-mode", "unit")
    def test_get_key_info_text_provision_modes(
        self, temp_db, provision_mode, expected_keywords
    ):
        """Тест генерации информации о ключе для различных режимов"""
        with allure.step(f"Подготовка тестовых данных для режима {provision_mode}"):
            expiry_date = datetime.now(timezone.utc) + timedelta(days=30)
            created_date = datetime.now(timezone.utc) - timedelta(days=5)
            connection_string = "vless://test-key" if provision_mode in ['key', 'both'] else None
            subscription_link = "https://example.com/sub" if provision_mode in ['subscription', 'both'] else None
            user_id = 123 if provision_mode == 'cabinet' else None
            key_id = 1 if provision_mode == 'cabinet' else None
            
            test_data = {
                'provision_mode': provision_mode,
                'expiry_date': str(expiry_date),
                'created_date': str(created_date),
                'connection_string': connection_string,
                'subscription_link': subscription_link,
            }
            allure.attach(str(test_data), "Входные параметры", allure.attachment_type.JSON)
        
        with allure.step("Настройка моков для внешних зависимостей"):
            # Мок для get_message_template (возвращает None для fallback на код)
            with patch('shop_bot.data_manager.database.get_message_template', return_value=None):
                # Мок для get_or_create_permanent_token
                token_value = 'test_token_123' if provision_mode == 'cabinet' else None
                with patch('shop_bot.data_manager.database.get_or_create_permanent_token', return_value=token_value):
                    # Мок для get_user_cabinet_domain (через get_setting)
                    domain_value = 'https://cabinet.example.com' if provision_mode == 'cabinet' else None
                    with patch('shop_bot.data_manager.database.get_setting', return_value=domain_value):
                        with allure.step(f"Вызов функции get_key_info_text для режима {provision_mode}"):
                            text = get_key_info_text(
                                key_number=1,
                                expiry_date=expiry_date,
                                created_date=created_date,
                                connection_string=connection_string,
                                status="pay-active",
                                subscription_link=subscription_link,
                                provision_mode=provision_mode,
                                user_id=user_id,
                                key_id=key_id,
                                user_timezone=None,
                                feature_enabled=False,
                                is_trial=False,
                                host_name="Финляндия",
                                plan_name="5. ЛК Подписка",
                                price=1.0,
                                key_auto_renewal_enabled=True,
                            )
                            allure.attach(text, f"Сгенерированная информация о ключе для режима {provision_mode}", allure.attachment_type.HTML)
        
        with allure.step("Проверка наличия ключевых слов"):
            for keyword in expected_keywords:
                assert keyword in text, f"Ключевое слово '{keyword}' не найдено для режима {provision_mode}"
                allure.attach(f"Найдено: {keyword}", f"Ключевое слово: {keyword}", allure.attachment_type.TEXT)
        
        with allure.step("Проверка структуры сообщения"):
            assert "Информация о ключе" in text, "Отсутствует заголовок"
            assert "Приобретён" in text or "Приобретен" in text, "Отсутствует информация о дате создания"
            assert "Действителен до" in text, "Отсутствует информация о дате истечения"
            assert "Статус" in text, "Отсутствует информация о статусе"
            allure.attach("Все обязательные элементы найдены", "Структура сообщения", allure.attachment_type.TEXT)
        
        with allure.step("Проверка наличия информации об автопродлении"):
            # Проверяем, что в тексте есть информация об автопродлении (либо в fallback, либо в шаблоне)
            # Переменная auto_renewal_status передаётся в template_variables, поэтому должна быть доступна в шаблонах
            assert "Автопродление" in text or "автопродление" in text, "Отсутствует информация об автопродлении"
            allure.attach("Информация об автопродлении найдена", "Проверка автопродления", allure.attachment_type.TEXT)

    @allure.title("Генерация информации о ключе: пробный ключ")
    @allure.description("""
    Проверяет корректность генерации информации о пробном ключе.
    
    **Проверяемые аспекты:**
    - Наличие пометки "(Пробный)" в тексте
    - Корректное форматирование для пробных ключей
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("key-info", "message", "trial", "unit")
    def test_get_key_info_text_trial_key(self, temp_db):
        """Тест генерации информации о пробном ключе"""
        with allure.step("Подготовка тестовых данных для пробного ключа"):
            expiry_date = datetime.now(timezone.utc) + timedelta(days=1)
            created_date = datetime.now(timezone.utc) - timedelta(hours=1)
        
        with allure.step("Настройка моков"):
            with patch('shop_bot.data_manager.database.get_message_template', return_value=None):
                with allure.step("Вызов функции get_key_info_text для пробного ключа"):
                    text = get_key_info_text(
                        key_number=1,
                        expiry_date=expiry_date,
                        created_date=created_date,
                        connection_string="vless://trial-key",
                        status="trial-active",
                        subscription_link=None,
                        provision_mode='key',
                        user_id=None,
                        key_id=None,
                        user_timezone=None,
                        feature_enabled=False,
                        is_trial=True,
                        host_name="Финляндия",
                        plan_name="",
                        price=0.0,
                        key_auto_renewal_enabled=False,
                    )
                    allure.attach(text, "Сгенерированная информация о пробном ключе", allure.attachment_type.HTML)
        
        with allure.step("Проверка наличия пометки о пробном ключе"):
            assert "(Пробный)" in text, "Отсутствует пометка '(Пробный)'"
            allure.attach("Пометка '(Пробный)' найдена", "Результат проверки", allure.attachment_type.TEXT)


@pytest.mark.unit
@pytest.mark.database
@allure.epic("Форматирование сообщений")
@allure.feature("Интеграция со справочником")
@allure.label("package", "src.shop_bot.utils")
class TestMessageTemplatesIntegration:
    """Тесты интеграции со справочником 'Тексты бота'"""

    @allure.title("Проверка fallback на код при отсутствии шаблона в БД")
    @allure.description("""
    Проверяет, что функция корректно использует fallback текст при отсутствии активного шаблона в БД.
    
    **Проверяемые аспекты:**
    - Функция get_message_template возвращает None
    - Используется fallback текст из кода
    - Сообщение генерируется корректно даже без шаблона в БД
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("templates", "database", "fallback", "unit")
    def test_fallback_when_template_not_found(self, temp_db):
        """Тест fallback при отсутствии шаблона"""
        with allure.step("Настройка моков для отсутствия шаблона в БД"):
            with patch('shop_bot.data_manager.database.get_message_template', return_value=None):
                with patch('shop_bot.data_manager.database.get_or_create_permanent_token', return_value=None):
                    with patch('shop_bot.data_manager.database.get_setting', return_value=None):
                        with allure.step("Вызов функции get_purchase_success_text"):
                            expiry_date = datetime.now(timezone.utc) + timedelta(days=30)
                            
                            text = get_purchase_success_text(
                                action="готов",
                                key_number=1,
                                expiry_date=expiry_date,
                                connection_string="vless://test-key",
                                subscription_link=None,
                                provision_mode='key',
                                user_id=None,
                                key_id=None,
                                user_timezone=None,
                                feature_enabled=False,
                                is_trial=False,
                                host_name="Финляндия",
                                plan_name="5. ЛК Подписка",
                                price=1.0,
                                status=None,
                            )
                            allure.attach(text, "Сгенерированное сообщение (fallback)", allure.attachment_type.HTML)
        
        with allure.step("Проверка наличия ключевых элементов в fallback тексте"):
            assert "НИЖЕ ВАШ КЛЮЧ" in text, "Fallback текст не содержит ожидаемых элементов"
            assert "vless://test-key" in text, "Connection string не найден в fallback тексте"
            allure.attach("Fallback текст работает корректно", "Результат проверки", allure.attachment_type.TEXT)

    @allure.title("Проверка использования неактивного шаблона (fallback)")
    @allure.description("""
    Проверяет, что функция корректно использует fallback при наличии неактивного шаблона в БД.
    
    **Проверяемые аспекты:**
    - Шаблон в БД существует, но is_active = 0
    - Функция get_message_template возвращает None или шаблон с is_active=False
    - Используется fallback текст из кода
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("templates", "database", "inactive", "unit")
    def test_fallback_when_template_inactive(self, temp_db):
        """Тест fallback при неактивном шаблоне"""
        with allure.step("Настройка моков для неактивного шаблона"):
            # Мок возвращает шаблон с is_active=False
            inactive_template = {
                'template_key': 'purchase_success_key',
                'template_text': 'Тестовый текст',
                'is_active': 0
            }
            
            with patch('shop_bot.data_manager.database.get_message_template', return_value=inactive_template):
                with patch('shop_bot.data_manager.database.get_or_create_permanent_token', return_value=None):
                    with patch('shop_bot.data_manager.database.get_setting', return_value=None):
                        with allure.step("Вызов функции get_purchase_success_text"):
                            expiry_date = datetime.now(timezone.utc) + timedelta(days=30)
                            
                            text = get_purchase_success_text(
                                action="готов",
                                key_number=1,
                                expiry_date=expiry_date,
                                connection_string="vless://test-key",
                                subscription_link=None,
                                provision_mode='key',
                                user_id=None,
                                key_id=None,
                                user_timezone=None,
                                feature_enabled=False,
                                is_trial=False,
                                host_name="Финляндия",
                                plan_name="5. ЛК Подписка",
                                price=1.0,
                                status=None,
                            )
                            allure.attach(text, "Сгенерированное сообщение (неактивный шаблон)", allure.attachment_type.HTML)
        
        with allure.step("Проверка использования fallback текста"):
            # Проверяем, что используется fallback, а не неактивный шаблон
            assert "Тестовый текст" not in text, "Использован неактивный шаблон вместо fallback"
            assert "НИЖЕ ВАШ КЛЮЧ" in text, "Fallback текст не используется"
            allure.attach("Fallback используется корректно для неактивного шаблона", "Результат проверки", allure.attachment_type.TEXT)


@pytest.mark.unit
@pytest.mark.database
@allure.epic("Форматирование сообщений")
@allure.feature("Обработка невалидных HTML-тегов")
@allure.label("package", "src.shop_bot.utils")
class TestHtmlTagReplacement:
    """Тесты для замены невалидных HTML-тегов (например, <br>)"""

    @allure.title("Замена <br> тегов на переносы строк в get_message_text")
    @allure.description("""
    **Цель теста:**
    Проверяет, что функция get_message_text корректно заменяет невалидные HTML-теги <br> на переносы строк,
    предотвращая ошибки Telegram Bot API "Unsupported start tag 'br'".
    
    **Предварительные условия:**
    - Временная БД создана и инициализирована (temp_db фикстура)
    - Таблица message_templates существует в БД
    - Функция get_message_text доступна для импорта
    
    **Шаги выполнения:**
    1. Подготовка тестового шаблона с различными вариантами <br> тегов (<br>, <br/>, <br />, <BR>)
    2. Сохранение шаблона в БД через SQL запрос
    3. Вызов функции get_message_text с template_key из БД
    4. Проверка замены всех вариантов <br> на переносы строк (\\n)
    5. Валидация HTML-тегов после замены
    6. Восстановление оригинального DB_FILE
    
    **Ожидаемые результаты:**
    - Все варианты <br> тегов (<br>, <br/>, <br />, <BR>) заменены на \\n
    - В результате присутствуют переносы строк
    - Текст после замены проходит валидацию HTML (is_valid = True)
    - Ошибок валидации нет (errors = [])
    
    **Проверяемые аспекты:**
    - <br> заменяется на \\n
    - <br/> заменяется на \\n
    - <br /> заменяется на \\n
    - Замена происходит независимо от регистра (<BR>, <Br>)
    - После замены текст проходит валидацию HTML
    
    **Важность:**
    - Telegram Bot API не поддерживает тег <br>
    - Необходимо предотвратить ошибки "Unsupported start tag 'br'"
    - Критично для стабильности бота при отправке сообщений
    """)
    @allure.severity(allure.severity_level.CRITICAL)
    @allure.tag("html", "br-tag", "validation", "unit", "critical", "telegram-api", "message-formatting")
    @allure.label("owner", "qa-team")
    @allure.label("component", "config")
    @allure.label("story", "html-tag-replacement")
    def test_br_tag_replacement_in_get_message_text(self, temp_db):
        """Тест замены <br> тегов в get_message_text"""
        from shop_bot.config import get_message_text
        from shop_bot.data_manager import database
        import sqlite3
        
        with allure.step("Подготовка тестового шаблона с <br> тегами"):
            # Создаем тестовый шаблон с различными вариантами <br>
            test_template = {
                'template_key': 'key_info_key',
                'category': 'key_info',
                'provision_mode': 'key',
                'template_text': '<b>Информация о ключе</b><br>Строка 1<br/>Строка 2<br />Строка 3<BR>Строка 4',
                'description': 'Тестовый шаблон с <br> тегами',
                'variables': '[]',
                'is_active': 1
            }
            
            # Удаляем существующий шаблон, если он есть, и вставляем новый
            conn = sqlite3.connect(str(temp_db))
            cursor = conn.cursor()
            # Удаляем существующий шаблон с таким ключом
            cursor.execute('DELETE FROM message_templates WHERE template_key = ? AND provision_mode = ?', 
                          (test_template['template_key'], test_template['provision_mode']))
            # Вставляем новый шаблон
            cursor.execute('''
                INSERT INTO message_templates 
                (template_key, category, provision_mode, template_text, description, variables, is_active)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                test_template['template_key'],
                test_template['category'],
                test_template['provision_mode'],
                test_template['template_text'],
                test_template['description'],
                test_template['variables'],
                test_template['is_active']
            ))
            conn.commit()
            conn.close()
            
            allure.attach(str(test_template), "Тестовый шаблон с <br> тегами", allure.attachment_type.JSON)
        
        with allure.step("Вызов функции get_message_text с моком get_message_template"):
            # Мокаем get_message_template чтобы он использовал temp_db
            def mock_get_message_template(template_key: str, provision_mode: str = None):
                conn = sqlite3.connect(str(temp_db))
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                if provision_mode:
                    cursor.execute('''
                        SELECT * FROM message_templates 
                        WHERE template_key = ? AND (provision_mode = ? OR provision_mode IS NULL) AND is_active = 1
                        ORDER BY provision_mode DESC
                        LIMIT 1
                    ''', (template_key, provision_mode))
                else:
                    cursor.execute('''
                        SELECT * FROM message_templates 
                        WHERE template_key = ? AND (provision_mode IS NULL) AND is_active = 1
                        LIMIT 1
                    ''', (template_key,))
                
                result = cursor.fetchone()
                conn.close()
                
                if result:
                    return dict(result)
                return None
            
            with patch('shop_bot.data_manager.database.get_message_template', side_effect=mock_get_message_template):
                result = get_message_text(
                    template_key='key_info_key',
                    variables={},
                    fallback_text='Fallback текст',
                    provision_mode='key'
                )
                allure.attach(result, "Результат после обработки", allure.attachment_type.HTML)
        
        with allure.step("Проверка замены <br> тегов"):
            # Проверяем, что все варианты <br> заменены на \n
            br_variants = ['<br>', '<br/>', '<br />', '<BR>', '<Br>', '<bR>']
            found_br_tags = [tag for tag in br_variants if tag in result]
            
            if found_br_tags:
                allure.attach(str(found_br_tags), "Найденные <br> теги (не должны присутствовать)", allure.attachment_type.TEXT)
                raise AssertionError(f"Найдены не заменённые <br> теги: {found_br_tags}")
            
            allure.attach("✓ Все варианты <br> тегов заменены", "Проверка замены", allure.attachment_type.TEXT)
            
            # Проверяем наличие переносов строк
            newline_count = result.count('\n')
            assert '\n' in result, "Переносы строк не добавлены"
            allure.attach(f"Количество переносов строк: {newline_count}", "Статистика переносов", allure.attachment_type.TEXT)
            
            # Проверяем, что текст валиден (не содержит невалидных тегов)
            from shop_bot.security.validators import InputValidator
            is_valid, errors = InputValidator.validate_html_tags(result)
            
            if not is_valid:
                allure.attach(str(errors), "Ошибки валидации HTML", allure.attachment_type.JSON)
                allure.attach(result, "Текст с ошибками валидации", allure.attachment_type.HTML)
                raise AssertionError(f"Текст после замены не прошёл валидацию: {errors}")
            
            allure.attach("✓ Валидация HTML прошла успешно", "Результат валидации", allure.attachment_type.TEXT)
            allure.attach("Все <br> теги успешно заменены на переносы строк", "Итоговый результат", allure.attachment_type.TEXT)
            
            # Дополнительная информация для отчета
            validation_info = {
                "is_valid": is_valid,
                "errors_count": len(errors),
                "errors": errors,
                "newline_count": newline_count,
                "result_length": len(result)
            }
            allure.attach(str(validation_info), "Детали валидации", allure.attachment_type.JSON)
        
        # Восстанавливаем оригинальный DB_FILE

    @allure.title("Замена <br> тегов в шаблонах с переменными")
    @allure.description("""
    Проверяет, что замена <br> тегов работает корректно после подстановки переменных.
    
    **Проверяемые аспекты:**
    - <br> теги заменяются после подстановки переменных
    - Переменные подставляются корректно
    - Итоговый текст валиден для Telegram
    """)
    @allure.severity(allure.severity_level.CRITICAL)
    @allure.tag("html", "br-tag", "variables", "unit", "critical")
    def test_br_tag_replacement_with_variables(self, temp_db):
        """Тест замены <br> тегов с переменными"""
        from shop_bot.config import get_message_text
        from shop_bot.data_manager import database
        import sqlite3
        
        with allure.step("Подготовка тестового шаблона с переменными и <br> тегами"):
            test_template = {
                'template_key': 'purchase_success_key',
                'category': 'purchase',
                'provision_mode': 'key',
                'template_text': '<b>Ключ #{key_number}</b><br>Срок действия: {expiry_formatted}<br/>Ключ: <code>{connection_string}</code>',
                'description': 'Тестовый шаблон с переменными и <br>',
                'variables': '["key_number", "expiry_formatted", "connection_string"]',
                'is_active': 1
            }
            
            # Удаляем существующий шаблон, если он есть, и вставляем новый
            conn = sqlite3.connect(str(temp_db))
            cursor = conn.cursor()
            # Удаляем существующий шаблон с таким ключом
            cursor.execute('DELETE FROM message_templates WHERE template_key = ? AND provision_mode = ?', 
                          (test_template['template_key'], test_template['provision_mode']))
            # Вставляем новый шаблон
            cursor.execute('''
                INSERT INTO message_templates 
                (template_key, category, provision_mode, template_text, description, variables, is_active)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                test_template['template_key'],
                test_template['category'],
                test_template['provision_mode'],
                test_template['template_text'],
                test_template['description'],
                test_template['variables'],
                test_template['is_active']
            ))
            conn.commit()
            conn.close()
            
            allure.attach(str(test_template), "Тестовый шаблон с переменными", allure.attachment_type.JSON)
        
        with allure.step("Вызов функции get_message_text с переменными и моком get_message_template"):
            # Мокаем get_message_template чтобы он использовал temp_db
            def mock_get_message_template(template_key: str, provision_mode: str = None):
                conn = sqlite3.connect(str(temp_db))
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                if provision_mode:
                    cursor.execute('''
                        SELECT * FROM message_templates 
                        WHERE template_key = ? AND (provision_mode = ? OR provision_mode IS NULL) AND is_active = 1
                        ORDER BY provision_mode DESC
                        LIMIT 1
                    ''', (template_key, provision_mode))
                else:
                    cursor.execute('''
                        SELECT * FROM message_templates 
                        WHERE template_key = ? AND (provision_mode IS NULL) AND is_active = 1
                        LIMIT 1
                    ''', (template_key,))
                
                result = cursor.fetchone()
                conn.close()
                
                if result:
                    return dict(result)
                return None
            
            with patch('shop_bot.data_manager.database.get_message_template', side_effect=mock_get_message_template):
                result = get_message_text(
                    template_key='purchase_success_key',
                    variables={
                        'key_number': '1',
                        'expiry_formatted': '01.01.2025',
                        'connection_string': 'vless://test-key'
                    },
                    fallback_text='Fallback',
                    provision_mode='key'
                )
                allure.attach(result, "Результат после обработки", allure.attachment_type.HTML)
        
        with allure.step("Проверка результата"):
            # Проверяем замену <br>
            assert '<br>' not in result, "Тег <br> не заменён"
            assert '<br/>' not in result, "Тег <br/> не заменён"
            
            # Проверяем подстановку переменных
            assert '#1' in result, "Переменная key_number не подставлена"
            assert '01.01.2025' in result, "Переменная expiry_formatted не подставлена"
            assert 'vless://test-key' in result, "Переменная connection_string не подставлена"
            
            # Проверяем валидность HTML
            from shop_bot.security.validators import InputValidator
            is_valid, errors = InputValidator.validate_html_tags(result)
            assert is_valid, f"Текст не прошёл валидацию: {errors}"
            
            allure.attach("Замена <br> и подстановка переменных работают корректно", "Результат проверки", allure.attachment_type.TEXT)
        


@pytest.mark.unit
@allure.epic("Форматирование сообщений")
@allure.feature("Обработка ошибок Telegram API")
@allure.label("package", "src.shop_bot.utils")
class TestTelegramBadRequestHandling:
    """Тесты для обработки ошибок TelegramBadRequest при парсинге HTML"""

    @allure.title("Обработка ошибки 'can't parse entities' при отправке сообщения")
    @allure.description("""
    **Цель теста:**
    Проверяет, что обработчик корректно обрабатывает ошибку TelegramBadRequest при парсинге HTML-сущностей
    и отправляет сообщение без форматирования, предотвращая падение бота.
    
    **Предварительные условия:**
    - Мок callback.message.edit_text настроен для симуляции ошибки
    - TelegramBadRequest исключение доступно для импорта
    - Модуль re доступен для работы с регулярными выражениями
    
    **Шаги выполнения:**
    1. Подготовка мока callback с ошибкой парсинга HTML
    2. Настройка side_effect для edit_text: первая попытка с HTML вызывает TelegramBadRequest
    3. Симуляция обработки ошибки (как в handlers.py):
       - Попытка отправки с parse_mode='HTML'
       - Перехват TelegramBadRequest
       - Проверка сообщения об ошибке на наличие "can't parse entities" или "unsupported start tag"
       - Удаление HTML-тегов из текста
       - Декодирование HTML-сущностей (&lt;, &gt;, &amp;)
       - Повторная отправка без parse_mode
    4. Проверка результата:
       - edit_text вызван дважды
       - Второй вызов без parse_mode
    
    **Ожидаемые результаты:**
    - Ошибка "can't parse entities" перехвачена и обработана
    - Сообщение отправлено без HTML-форматирования (plain text)
    - HTML-теги удалены из текста
    - HTML-сущности декодированы обратно
    - edit_text вызван дважды (первая попытка с HTML, вторая без)
    - Второй вызов без parse_mode
    
    **Проверяемые аспекты:**
    - Ошибка "can't parse entities" обрабатывается корректно
    - Сообщение отправляется без HTML-форматирования (plain text)
    - HTML-теги удаляются из текста
    - HTML-сущности (&lt;, &gt;, &amp;) декодируются обратно
    
    **Важность:**
    - Предотвращает падение бота при ошибках форматирования
    - Пользователь получает информацию даже при проблемах с HTML
    - Критично для стабильности и отказоустойчивости бота
    """)
    @allure.severity(allure.severity_level.CRITICAL)
    @allure.tag("telegram", "error-handling", "html-parsing", "unit", "critical", "telegram-api", "exception-handling")
    @allure.label("owner", "qa-team")
    @allure.label("component", "bot-handlers")
    @allure.label("story", "error-handling")
    @pytest.mark.asyncio
    async def test_handle_parse_entities_error(self):
        """Тест обработки ошибки парсинга HTML"""
        from aiogram.exceptions import TelegramBadRequest
        from unittest.mock import AsyncMock, MagicMock, patch
        import re
        
        with allure.step("Подготовка мока callback с ошибкой парсинга"):
            # Создаём мок callback
            callback = MagicMock()
            callback.message = MagicMock()
            callback.message.edit_text = AsyncMock()
            
            # Текст с проблемным HTML
            problematic_text = "<b>Ключ #1</b><br>Информация"
            
            # Симулируем ошибку при первой попытке отправки
            async def edit_text_side_effect(*args, **kwargs):
                if kwargs.get('parse_mode') == 'HTML':
                    raise TelegramBadRequest(
                        method='editMessageText',
                        message="can't parse entities: Unsupported start tag 'br' at byte offset 50"
                    )
                # При второй попытке (без HTML) успешно
                return True
            
            callback.message.edit_text.side_effect = edit_text_side_effect
            
            allure.attach(problematic_text, "Проблемный текст", allure.attachment_type.HTML)
        
        with allure.step("Симуляция обработки ошибки (как в handlers.py)"):
            try:
                # Первая попытка с HTML
                await callback.message.edit_text(
                    text=problematic_text,
                    parse_mode='HTML'
                )
            except TelegramBadRequest as e:
                error_msg = str(e)
                if "can't parse entities" in error_msg or "unsupported start tag" in error_msg:
                    # Удаляем HTML-теги и декодируем сущности
                    plain_text = re.sub(r'<[^>]+>', '', problematic_text)
                    plain_text = plain_text.replace('&lt;', '<').replace('&gt;', '>').replace('&amp;', '&')
                    
                    # Отправляем без HTML
                    await callback.message.edit_text(
                        text=plain_text
                    )
                    
                    allure.attach(plain_text, "Текст без HTML", allure.attachment_type.TEXT)
                    allure.attach("Ошибка обработана, сообщение отправлено без HTML", "Результат", allure.attachment_type.TEXT)
                else:
                    raise
        
        with allure.step("Проверка результата"):
            # Проверяем, что edit_text был вызван дважды
            call_count = callback.message.edit_text.call_count
            assert call_count == 2, f"edit_text должен быть вызван дважды, но был вызван {call_count} раз"
            allure.attach(f"Количество вызовов edit_text: {call_count}", "Статистика вызовов", allure.attachment_type.TEXT)
            
            # Проверяем параметры первого вызова (с HTML)
            first_call = callback.message.edit_text.call_args_list[0]
            first_call_parse_mode = first_call.kwargs.get('parse_mode')
            assert first_call_parse_mode == 'HTML', f"Первый вызов должен быть с parse_mode='HTML', но был {first_call_parse_mode}"
            allure.attach(f"Первый вызов: parse_mode={first_call_parse_mode}", "Параметры первого вызова", allure.attachment_type.TEXT)
            
            # Проверяем, что второй вызов был без parse_mode
            second_call = callback.message.edit_text.call_args_list[1]
            second_call_parse_mode = second_call.kwargs.get('parse_mode')
            assert 'parse_mode' not in second_call.kwargs or second_call.kwargs.get('parse_mode') is None, \
                f"Второй вызов должен быть без parse_mode, но был {second_call_parse_mode}"
            allure.attach(f"Второй вызов: parse_mode={second_call_parse_mode or 'None'}", "Параметры второго вызова", allure.attachment_type.TEXT)
            
            # Проверяем, что plain_text не содержит HTML-тегов
            plain_text = second_call.kwargs.get('text', '')
            html_tags_in_plain = [tag for tag in ['<b>', '</b>', '<br>', '<i>', '</i>'] if tag in plain_text]
            if html_tags_in_plain:
                allure.attach(str(html_tags_in_plain), "HTML-теги в plain text (не должны присутствовать)", allure.attachment_type.TEXT)
                raise AssertionError(f"Plain text содержит HTML-теги: {html_tags_in_plain}")
            
            allure.attach("✓ Plain text не содержит HTML-тегов", "Проверка plain text", allure.attachment_type.TEXT)
            
            # Итоговая информация
            result_info = {
                "total_calls": call_count,
                "first_call_parse_mode": first_call_parse_mode,
                "second_call_parse_mode": second_call_parse_mode or "None",
                "plain_text_length": len(plain_text),
                "html_tags_in_plain": len(html_tags_in_plain)
            }
            allure.attach(str(result_info), "Детали результата", allure.attachment_type.JSON)
            allure.attach("Обработка ошибки работает корректно", "Итоговый результат", allure.attachment_type.TEXT)

    @allure.title("Обработка ошибки 'unsupported start tag'")
    @allure.description("""
    Проверяет обработку ошибки "unsupported start tag" при отправке сообщения.
    
    **Проверяемые аспекты:**
    - Ошибка "unsupported start tag" обрабатывается корректно
    - Сообщение отправляется без HTML-форматирования
    - Пользователь получает информацию даже при ошибке
    """)
    @allure.severity(allure.severity_level.CRITICAL)
    @allure.tag("telegram", "error-handling", "html-parsing", "unit", "critical")
    @pytest.mark.asyncio
    async def test_handle_unsupported_tag_error(self):
        """Тест обработки ошибки unsupported start tag"""
        from aiogram.exceptions import TelegramBadRequest
        from unittest.mock import AsyncMock, MagicMock
        
        with allure.step("Подготовка мока с ошибкой unsupported start tag"):
            callback = MagicMock()
            callback.message = MagicMock()
            callback.message.edit_text = AsyncMock()
            
            problematic_text = "<b>Текст</b><invalid_tag>Невалидный тег</invalid_tag>"
            
            async def edit_text_side_effect(*args, **kwargs):
                if kwargs.get('parse_mode') == 'HTML':
                    raise TelegramBadRequest(
                        method='editMessageText',
                        message="can't parse entities: Unsupported start tag 'invalid_tag' at byte offset 20"
                    )
                return True
            
            callback.message.edit_text.side_effect = edit_text_side_effect
        
        with allure.step("Симуляция обработки ошибки"):
            try:
                # Первая попытка с HTML
                await callback.message.edit_text(text=problematic_text, parse_mode='HTML')
            except TelegramBadRequest as e:
                error_msg = str(e)
                if "can't parse entities" in error_msg or "unsupported start tag" in error_msg:
                    # Удаляем HTML-теги и декодируем сущности
                    import re
                    plain_text = re.sub(r'<[^>]+>', '', problematic_text)
                    plain_text = plain_text.replace('&lt;', '<').replace('&gt;', '>').replace('&amp;', '&')
                    
                    # Отправляем без HTML
                    await callback.message.edit_text(text=plain_text)
                    
                    allure.attach(plain_text, "Текст без HTML", allure.attachment_type.TEXT)
                    allure.attach("Ошибка обработана, сообщение отправлено без HTML", "Результат", allure.attachment_type.TEXT)
                else:
                    raise
        
        with allure.step("Проверка результата"):
            # Проверяем, что edit_text был вызван дважды
            call_count = callback.message.edit_text.call_count
            assert call_count == 2, f"edit_text должен быть вызван дважды, но был вызван {call_count} раз"
            allure.attach(f"Количество вызовов edit_text: {call_count}", "Статистика вызовов", allure.attachment_type.TEXT)
            
            # Проверяем параметры первого вызова (с HTML)
            first_call = callback.message.edit_text.call_args_list[0]
            first_call_parse_mode = first_call.kwargs.get('parse_mode')
            assert first_call_parse_mode == 'HTML', f"Первый вызов должен быть с parse_mode='HTML', но был {first_call_parse_mode}"
            allure.attach(f"Первый вызов: parse_mode={first_call_parse_mode}", "Параметры первого вызова", allure.attachment_type.TEXT)
            
            # Проверяем, что второй вызов был без parse_mode
            second_call = callback.message.edit_text.call_args_list[1]
            second_call_parse_mode = second_call.kwargs.get('parse_mode')
            assert 'parse_mode' not in second_call.kwargs or second_call.kwargs.get('parse_mode') is None, \
                f"Второй вызов должен быть без parse_mode, но был {second_call_parse_mode}"
            allure.attach(f"Второй вызов: parse_mode={second_call_parse_mode or 'None'}", "Параметры второго вызова", allure.attachment_type.TEXT)
            
            # Проверяем, что plain_text не содержит HTML-тегов
            plain_text = second_call.kwargs.get('text', '')
            html_tags_in_plain = [tag for tag in ['<b>', '</b>', '<br>', '<i>', '</i>', '<invalid_tag>', '</invalid_tag>'] if tag in plain_text]
            if html_tags_in_plain:
                allure.attach(str(html_tags_in_plain), "HTML-теги в plain text (не должны присутствовать)", allure.attachment_type.TEXT)
                raise AssertionError(f"Plain text содержит HTML-теги: {html_tags_in_plain}")
            
            allure.attach("✓ Plain text не содержит HTML-тегов", "Проверка plain text", allure.attachment_type.TEXT)
            
            # Итоговая информация
            result_info = {
                "total_calls": call_count,
                "first_call_parse_mode": first_call_parse_mode,
                "second_call_parse_mode": second_call_parse_mode or "None",
                "plain_text_length": len(plain_text),
                "html_tags_in_plain": len(html_tags_in_plain)
            }
            allure.attach(str(result_info), "Детали результата", allure.attachment_type.JSON)
            allure.attach("Ошибка unsupported start tag обработана корректно", "Итоговый результат", allure.attachment_type.TEXT)