#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Unit-тесты для проверки атрибутов ключа в БД

Тестирует наличие и корректность всех атрибутов ключа:
- Subscription
- Subscription Link
- Личный кабинет
- Ключ подключения
- Email (3x-ui)
- UUID (3x-ui)
- Telegram ChatID
"""

import pytest
import allure
import sys
import logging
from pathlib import Path
from datetime import datetime, timezone, timedelta
import uuid
import sqlite3

# Добавляем путь к проекту
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root / "src"))

from shop_bot.data_manager.database import (
    register_user_if_not_exists,
    add_new_key,
    get_key_by_id,
    get_or_create_permanent_token,
    get_tokens_for_key,
)

logger = logging.getLogger(__name__)


@pytest.mark.unit
@pytest.mark.database
@allure.epic("База данных")
@allure.feature("Операции с ключами")
@allure.label("package", "src.shop_bot.database")
class TestKeyAttributes:
    """Тесты для проверки атрибутов ключа в БД"""

    @allure.title("Проверка всех атрибутов ключа в БД")
    @allure.description("""
    Проверяет наличие и корректность всех атрибутов ключа в базе данных.
    
    **Что проверяется:**
    - Subscription (subscription) - идентификатор подписки
    - Subscription Link (subscription_link) - ссылка на подписку
    - Личный кабинет (cabinet_links) - ссылки на личный кабинет через user_tokens
    - Ключ подключения (connection_string) - VLESS строка подключения
    - Email (3x-ui) (key_email) - email ключа в 3x-ui
    - UUID (3x-ui) (xui_client_uuid) - UUID клиента в 3x-ui
    - Telegram ChatID (telegram_chat_id) - ID чата в Telegram
    
    **Тестовые данные:**
    - user_id: 123456999
    - host_name: test_host
    - Все атрибуты ключа заполнены
    
    **Ожидаемый результат:**
    Все атрибуты ключа должны быть заполнены и корректны.
    """)
    @allure.severity(allure.severity_level.CRITICAL)
    @allure.tag("key_attributes", "database", "unit", "critical")
    def test_key_attributes_in_database(self, temp_db, sample_host):
        """Тест проверки всех атрибутов ключа в БД"""
        with allure.step("Подготовка тестовых данных"):
            user_id = 123456999
            register_user_if_not_exists(user_id, "test_user_attrs", None, "Test User Attributes")
            
            # Создаем хост в БД
            with sqlite3.connect(temp_db) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT OR IGNORE INTO xui_hosts (host_name, host_url, host_username, host_pass, host_inbound_id, host_code) VALUES (?, ?, ?, ?, ?, ?)",
                    (sample_host['host_name'], sample_host['host_url'], sample_host['host_username'], 
                     sample_host['host_pass'], sample_host['host_inbound_id'], sample_host['host_code'])
                )
                conn.commit()
            
            # Подготавливаем данные ключа
            xui_client_uuid = str(uuid.uuid4())
            key_email = f"test_{uuid.uuid4().hex[:8]}@example.com"
            expiry_timestamp_ms = int((datetime.now(timezone.utc) + timedelta(days=30)).timestamp() * 1000)
            subscription = "test-sub-id-123"
            subscription_link = "https://serv1.dark-maximus.com/subs/test-sub-id-123"
            connection_string = "vless://test-uuid@serv1.dark-maximus.com:443?type=tcp&security=reality"
            telegram_chat_id = 123456999
            
            allure.attach(str({
                'user_id': user_id,
                'xui_client_uuid': xui_client_uuid,
                'key_email': key_email,
                'subscription': subscription,
                'subscription_link': subscription_link,
                'connection_string': connection_string,
                'telegram_chat_id': telegram_chat_id
            }), "Тестовые данные ключа", allure.attachment_type.JSON)
        
        with allure.step("Создание ключа с всеми атрибутами"):
            key_id = add_new_key(
                user_id=user_id,
                host_name=sample_host['host_name'],
                xui_client_uuid=xui_client_uuid,
                key_email=key_email,
                expiry_timestamp_ms=expiry_timestamp_ms,
                connection_string=connection_string,
                plan_name="Test Plan",
                price=100.0,
                subscription=subscription,
                subscription_link=subscription_link,
                telegram_chat_id=telegram_chat_id
            )
            
            assert key_id is not None, "Ключ должен быть создан"
            allure.attach(str(key_id), "ID созданного ключа", allure.attachment_type.TEXT)
        
        with allure.step("Создание токена для личного кабинета"):
            # Создаем токен для личного кабинета
            token = get_or_create_permanent_token(user_id, key_id)
            assert token is not None, "Токен должен быть создан"
            allure.attach(str(token[:20]) + "...", "Токен личного кабинета (первые 20 символов)", allure.attachment_type.TEXT)
        
        with allure.step("Получение ключа из БД и проверка атрибутов"):
            key = get_key_by_id(key_id)
            assert key is not None, "Ключ должен быть найден по ID"
            
            # Проверяем Subscription
            with allure.step("Проверка Subscription"):
                assert 'subscription' in key, "Поле subscription должно присутствовать в ключе"
                assert key['subscription'] == subscription, f"Subscription должен быть равен '{subscription}', получено '{key.get('subscription')}'"
                allure.attach(str(key['subscription']), "Subscription", allure.attachment_type.TEXT)
            
            # Проверяем Subscription Link
            with allure.step("Проверка Subscription Link"):
                assert 'subscription_link' in key, "Поле subscription_link должно присутствовать в ключе"
                assert key['subscription_link'] == subscription_link, f"Subscription Link должен быть равен '{subscription_link}', получено '{key.get('subscription_link')}'"
                assert key['subscription_link'].startswith('http'), "Subscription Link должен быть валидной URL"
                allure.attach(str(key['subscription_link']), "Subscription Link", allure.attachment_type.TEXT)
            
            # Проверяем Ключ подключения
            with allure.step("Проверка Ключа подключения"):
                assert 'connection_string' in key, "Поле connection_string должно присутствовать в ключе"
                assert key['connection_string'] == connection_string, f"Connection String должен быть равен '{connection_string}', получено '{key.get('connection_string')}'"
                assert key['connection_string'].startswith('vless://'), "Connection String должен начинаться с 'vless://'"
                allure.attach(str(key['connection_string']), "Connection String", allure.attachment_type.TEXT)
            
            # Проверяем Email (3x-ui)
            with allure.step("Проверка Email (3x-ui)"):
                assert 'key_email' in key, "Поле key_email должно присутствовать в ключе"
                assert key['key_email'] == key_email, f"Key Email должен быть равен '{key_email}', получено '{key.get('key_email')}'"
                assert '@' in key['key_email'], "Key Email должен содержать символ '@'"
                allure.attach(str(key['key_email']), "Email (3x-ui)", allure.attachment_type.TEXT)
            
            # Проверяем UUID (3x-ui)
            with allure.step("Проверка UUID (3x-ui)"):
                assert 'xui_client_uuid' in key, "Поле xui_client_uuid должно присутствовать в ключе"
                assert key['xui_client_uuid'] == xui_client_uuid, f"XUI Client UUID должен быть равен '{xui_client_uuid}', получено '{key.get('xui_client_uuid')}'"
                # Проверяем, что это валидный UUID
                try:
                    uuid.UUID(key['xui_client_uuid'])
                except ValueError:
                    pytest.fail(f"XUI Client UUID должен быть валидным UUID, получено '{key.get('xui_client_uuid')}'")
                allure.attach(str(key['xui_client_uuid']), "UUID (3x-ui)", allure.attachment_type.TEXT)
            
            # Проверяем Telegram ChatID
            with allure.step("Проверка Telegram ChatID"):
                assert 'telegram_chat_id' in key, "Поле telegram_chat_id должно присутствовать в ключе"
                assert key['telegram_chat_id'] == telegram_chat_id, f"Telegram ChatID должен быть равен '{telegram_chat_id}', получено '{key.get('telegram_chat_id')}'"
                assert isinstance(key['telegram_chat_id'], int) or (isinstance(key['telegram_chat_id'], str) and key['telegram_chat_id'].isdigit()), "Telegram ChatID должен быть числом"
                allure.attach(str(key['telegram_chat_id']), "Telegram ChatID", allure.attachment_type.TEXT)
        
        with allure.step("Проверка ссылок личного кабинета"):
            # Получаем токены для ключа
            tokens = get_tokens_for_key(key_id)
            assert tokens is not None, "Токены должны быть получены"
            assert len(tokens) > 0, "Должен быть хотя бы один токен для ключа"
            
            # Проверяем структуру токена
            token_info = tokens[0]
            assert 'token' in token_info, "Токен должен содержать поле 'token'"
            assert 'created_at' in token_info, "Токен должен содержать поле 'created_at'"
            assert token_info['token'] == token, "Токен должен совпадать с созданным токеном"
            
            # Формируем ссылки личного кабинета (URL формируется на основе токена)
            cabinet_links = []
            for token_info in tokens:
                if token_info and token_info.get('token'):
                    cabinet_links.append({
                        'token': token_info.get('token'),
                        'url': f"https://app.dark-maximus.com/auth/{token_info.get('token')}",
                        'created_at': token_info.get('created_at'),
                        'last_used_at': token_info.get('last_used_at'),
                        'access_count': token_info.get('access_count', 0),
                    })
            
            assert len(cabinet_links) > 0, "Должна быть хотя бы одна ссылка на личный кабинет"
            assert cabinet_links[0]['token'] == token, "Токен в ссылке должен совпадать с созданным токеном"
            assert 'https://' in cabinet_links[0]['url'], "URL личного кабинета должен быть валидной ссылкой"
            assert '/auth/' in cabinet_links[0]['url'], "URL личного кабинета должен содержать '/auth/'"
            
            allure.attach(str(cabinet_links), "Ссылки личного кабинета", allure.attachment_type.JSON)
        
        with allure.step("Проверка результата"):
            # Финальная проверка: все атрибуты должны быть заполнены
            required_attributes = {
                'subscription': key.get('subscription'),
                'subscription_link': key.get('subscription_link'),
                'connection_string': key.get('connection_string'),
                'key_email': key.get('key_email'),
                'xui_client_uuid': key.get('xui_client_uuid'),
                'telegram_chat_id': key.get('telegram_chat_id'),
            }
            
            missing_attributes = [attr for attr, value in required_attributes.items() if not value]
            assert len(missing_attributes) == 0, f"Следующие атрибуты не заполнены: {', '.join(missing_attributes)}"
            
            allure.attach(str(required_attributes), "Все атрибуты ключа", allure.attachment_type.JSON)
            
            logger.info(f"Все атрибуты ключа key_id={key_id} успешно проверены")

