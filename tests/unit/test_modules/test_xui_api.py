#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Unit-тесты для модуля xui_api

Тестирует работу с 3X-UI API: создание, обновление, удаление клиентов,
получение subscription link, логику карантина хостов.
"""

import pytest
import allure
import sys
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock, patch, Mock
from datetime import datetime, timezone, timedelta

# Добавляем путь к проекту
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root / "src"))


@pytest.mark.unit
@allure.epic("Модули")
@allure.feature("3X-UI API")
@allure.label("package", "src.shop_bot.modules")
class TestXUIApi:
    """Тесты для работы с 3X-UI API"""

    @pytest.fixture
    def mock_api(self):
        """Создает мок для py3xui.Api"""
        api = MagicMock()
        api.login = Mock()
        
        # Мок для inbound
        mock_inbound = MagicMock()
        mock_inbound.id = 1
        mock_inbound.settings = MagicMock()
        mock_inbound.settings.clients = []
        
        # Мок для метода get_list
        api.inbound.get_list = Mock(return_value=[mock_inbound])
        api.inbound.get_by_id = Mock(return_value=mock_inbound)
        api.inbound.update = Mock()
        api.client.update = Mock()
        api.client.delete = Mock()
        
        return api

    @pytest.fixture
    def mock_inbound(self):
        """Создает мок для Inbound"""
        inbound = MagicMock()
        inbound.id = 1
        inbound.port = 443
        inbound.settings = MagicMock()
        inbound.settings.clients = []
        inbound.stream_settings = {
            "reality_settings": {
                "settings": {
                    "publicKey": "test-public-key",
                    "fingerprint": "test-fingerprint"
                },
                "serverNames": ["example.com"],
                "shortIds": ["test-short-id"]
            }
        }
        return inbound

    @pytest.fixture
    def mock_client(self):
        """Создает мок для Client"""
        client = MagicMock()
        client.id = "test-uuid-123"
        client.email = "user123-key1@host.bot"
        client.enable = True
        client.expiry_time = int((datetime.now(timezone.utc) + timedelta(days=30)).timestamp() * 1000)
        client.flow = "xtls-rprx-vision"
        return client

    @pytest.fixture
    def sample_host(self):
        """Создает тестовый хост"""
        return {
            'host_name': 'test-host',
            'host_url': 'https://test.example.com:8443/configpanel',
            'host_username': 'admin',
            'host_pass': 'password',
            'host_inbound_id': 1,
            'host_code': 'test-code'
        }

    @allure.title("Создание нового клиента в 3X-UI")
    @allure.description("Проверяет создание нового клиента в 3X-UI через update_or_create_client_on_panel. **Что проверяется:** создание клиента с email и временем истечения, вызов inbound.update. **Тестовые данные:** email='user123-key1@host.bot', days_to_add=30.0. **Ожидаемый результат:** клиент успешно создан, возвращен client_uuid и new_expiry_ms.")
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("xui_api", "create_client", "unit")
    def test_create_client(self, mock_api, mock_inbound, sample_host, temp_db):
        from shop_bot.modules.xui_api import update_or_create_client_on_panel
        import sqlite3
        
        # Добавляем хост в БД
        with sqlite3.connect(str(temp_db), timeout=30) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO xui_hosts (host_name, host_url, host_username, host_pass, host_inbound_id, host_code)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                sample_host['host_name'],
                sample_host['host_url'],
                sample_host['host_username'],
                sample_host['host_pass'],
                sample_host['host_inbound_id'],
                sample_host['host_code']
            ))
            conn.commit()
        
        # Настраиваем мок
        email = "user123-key1@host.bot"
        days_to_add = 30.0
        
        # В начале клиентов нет
        mock_inbound.settings.clients = []
        
        # Вызываем функцию
        client_uuid, new_expiry_ms = update_or_create_client_on_panel(
            mock_api,
            mock_inbound.id,
            email,
            days_to_add,
            comment="test-comment"
        )
        
        # Проверяем результаты
        assert client_uuid is not None, "Клиент должен быть создан"
        assert new_expiry_ms is not None, "Должно быть установлено время истечения"
        assert isinstance(new_expiry_ms, int), "Время истечения должно быть в миллисекундах"
        
        # Проверяем, что был вызван update
        mock_api.inbound.update.assert_called_once()

    @allure.title("Обновление существующего клиента в 3X-UI")
    @allure.description("Проверяет обновление существующего клиента в 3X-UI через update_or_create_client_on_panel. **Что проверяется:** обновление времени истечения существующего клиента, вызов inbound.update. **Тестовые данные:** email существующего клиента, days_to_add=30.0. **Ожидаемый результат:** клиент успешно обновлен, возвращен client_uuid и new_expiry_ms.")
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("xui_api", "update_client", "unit")
    def test_update_client(self, mock_api, mock_inbound, sample_host, temp_db):
        from shop_bot.modules.xui_api import update_or_create_client_on_panel
        import sqlite3
        
        # Добавляем хост в БД
        with sqlite3.connect(str(temp_db), timeout=30) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO xui_hosts (host_name, host_url, host_username, host_pass, host_inbound_id, host_code)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                sample_host['host_name'],
                sample_host['host_url'],
                sample_host['host_username'],
                sample_host['host_pass'],
                sample_host['host_inbound_id'],
                sample_host['host_code']
            ))
            conn.commit()
        
        # Настраиваем мок с существующим клиентом
        email = "user123-key1@host.bot"
        existing_expiry = int((datetime.now(timezone.utc) + timedelta(days=10)).timestamp() * 1000)
        existing_client = MagicMock()
        existing_client.email = email
        existing_client.id = "existing-uuid-123"
        existing_client.expiry_time = existing_expiry
        existing_client.enable = True
        # Убеждаемся, что expiry_time возвращает значение, а не мок
        type(existing_client).expiry_time = existing_expiry
        
        mock_inbound.settings.clients = [existing_client]
        mock_api.inbound.get_by_id.return_value = mock_inbound
        
        # Вызываем функцию для продления на 20 дней
        days_to_add = 20.0
        client_uuid, new_expiry_ms = update_or_create_client_on_panel(
            mock_api,
            mock_inbound.id,
            email,
            days_to_add,
            comment="updated-comment"
        )
        
        # Проверяем результаты
        assert client_uuid == existing_client.id, "UUID должен остаться тем же"
        assert new_expiry_ms is not None, "Должно быть установлено новое время истечения"
        assert new_expiry_ms > existing_expiry, "Время истечения должно быть увеличено"
        
        # Проверяем, что был вызван update
        mock_api.inbound.update.assert_called_once()

    @pytest.mark.asyncio
    @allure.title("Удаление клиента из 3X-UI")
    @allure.description("Проверяет удаление клиента из 3X-UI через delete_client_on_host. **Что проверяется:** удаление клиента по email, вызов client.delete. **Тестовые данные:** email='user123-key1@host.bot'. **Ожидаемый результат:** клиент успешно удален, возвращен True.")
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("xui_api", "delete_client", "unit")
    async def test_delete_client(self, sample_host, temp_db):
        from shop_bot.modules.xui_api import delete_client_on_host
        import sqlite3
        
        # Добавляем хост в БД
        with sqlite3.connect(str(temp_db), timeout=30) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO xui_hosts (host_name, host_url, host_username, host_pass, host_inbound_id, host_code)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                sample_host['host_name'],
                sample_host['host_url'],
                sample_host['host_username'],
                sample_host['host_pass'],
                sample_host['host_inbound_id'],
                sample_host['host_code']
            ))
            conn.commit()
        
        # Мокаем login_to_host
        mock_api = MagicMock()
        mock_inbound = MagicMock()
        mock_inbound.id = 1
        
        # Мокаем клиента для удаления
        mock_client = MagicMock()
        mock_client.id = "client-uuid-123"
        mock_client.email = "user123-key1@host.bot"
        
        mock_inbound_data = MagicMock()
        mock_inbound_data.settings.clients = [mock_client]
        
        mock_api.inbound.get_by_id.return_value = mock_inbound_data
        mock_api.client.delete = Mock()
        
        with patch('shop_bot.modules.xui_api.login_to_host', return_value=(mock_api, mock_inbound)):
            with patch('shop_bot.modules.xui_api.get_key_by_email', return_value=None):
                # Передаем None для client_uuid, чтобы использовалась основная логика delete_client_on_host
                # а не delete_client_by_uuid, которая требует мокирования всех хостов
                result = await delete_client_on_host(
                    sample_host['host_name'],
                    mock_client.email,
                    None  # Не передаем client_uuid, чтобы использовать основную логику
                )
                
                # Проверяем результаты
                assert result is True, "Удаление должно быть успешным"
                mock_api.client.delete.assert_called_once_with(mock_inbound.id, str(mock_client.id))

    @pytest.mark.asyncio
    @allure.title("Получение subscription link клиента")
    @allure.description("Проверяет получение subscription link клиента через get_client_subscription_link. **Что проверяется:** формирование subscription link из subURI и subId клиента. **Тестовые данные:** email='user123-key1@host.bot', subId='sub-id-123'. **Ожидаемый результат:** subscription link успешно получен и правильно сформирован.")
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("xui_api", "subscription_link", "unit")
    async def test_get_client_subscription_link(self, sample_host, temp_db):
        from shop_bot.modules.xui_api import get_client_subscription_link
        import sqlite3
        
        # Добавляем хост в БД
        with sqlite3.connect(str(temp_db), timeout=30) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO xui_hosts (host_name, host_url, host_username, host_pass, host_inbound_id, host_code)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                sample_host['host_name'],
                sample_host['host_url'],
                sample_host['host_username'],
                sample_host['host_pass'],
                sample_host['host_inbound_id'],
                sample_host['host_code']
            ))
            conn.commit()
        
        # Мокаем компоненты
        mock_api = MagicMock()
        mock_inbound = MagicMock()
        mock_inbound.id = 1
        
        mock_client = MagicMock()
        mock_client.email = "user123-key1@host.bot"
        mock_client.subId = "sub-id-123"
        
        mock_inbound_data = MagicMock()
        mock_inbound_data.settings.clients = [mock_client]
        
        mock_api.inbound.get_by_id.return_value = mock_inbound_data
        
        # Мокаем get_subscription_settings
        mock_sub_settings = {
            'subURI': 'http://example.com:8080/sub/',
            'subJsonURI': 'http://example.com:8080/sub-json/'
        }
        
        with patch('shop_bot.modules.xui_api.login_to_host', return_value=(mock_api, mock_inbound)):
            with patch('shop_bot.modules.xui_api.get_subscription_settings', return_value=mock_sub_settings):
                subscription_link = await get_client_subscription_link(
                    sample_host['host_name'],
                    mock_client.email
                )
                
                # Проверяем результаты
                assert subscription_link is not None, "Subscription link должен быть получен"
                assert subscription_link == f"{mock_sub_settings['subURI']}{mock_client.subId}", \
                    "Subscription link должен быть правильно сформирован"

    @pytest.mark.asyncio
    @allure.title("Создание нового ключа на хосте")
    @allure.description("Проверяет создание нового ключа на хосте через create_or_update_key_on_host. **Что проверяется:** создание ключа с email, временем истечения и connection_string. **Тестовые данные:** email='user123-key1@host.bot', days_to_add=30.0. **Ожидаемый результат:** ключ успешно создан, возвращен результат с client_uuid, email, expiry_timestamp_ms, connection_string.")
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("xui_api", "create_key", "unit")
    async def test_create_or_update_key_new(self, sample_host, temp_db):
        from shop_bot.modules.xui_api import create_or_update_key_on_host
        import sqlite3
        
        # Добавляем хост в БД
        with sqlite3.connect(str(temp_db), timeout=30) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO xui_hosts (host_name, host_url, host_username, host_pass, host_inbound_id, host_code)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                sample_host['host_name'],
                sample_host['host_url'],
                sample_host['host_username'],
                sample_host['host_pass'],
                sample_host['host_inbound_id'],
                sample_host['host_code']
            ))
            conn.commit()
        
        # Мокаем компоненты
        mock_api = MagicMock()
        mock_inbound = MagicMock()
        mock_inbound.id = 1
        mock_inbound.port = 443
        mock_inbound.stream_settings = {
            "reality_settings": {
                "settings": {
                    "publicKey": "test-public-key",
                    "fingerprint": "test-fingerprint"
                },
                "serverNames": ["example.com"],
                "shortIds": ["test-short-id"]
            }
        }
        mock_inbound.settings = MagicMock()
        mock_inbound.settings.clients = []
        
        mock_api.inbound.get_by_id.return_value = mock_inbound
        mock_api.inbound.get_list.return_value = [mock_inbound]
        mock_api.inbound.update = Mock()
        mock_api.client.update = Mock()
        
        email = "user123-key1@host.bot"
        days_to_add = 30.0
        
        # Мокаем update_or_create_client_on_panel
        with patch('shop_bot.modules.xui_api.login_to_host', return_value=(mock_api, mock_inbound)):
            with patch('shop_bot.modules.xui_api.update_or_create_client_on_panel', return_value=("test-uuid-123", int((datetime.now(timezone.utc) + timedelta(days=30)).timestamp() * 1000))):
                with patch('shop_bot.modules.xui_api.get_sub_uri_from_panel', return_value=None):
                    with patch('shop_bot.modules.xui_api._panel_update_client_quota', return_value=True):
                        result = await create_or_update_key_on_host(
                            sample_host['host_name'],
                            email,
                            days_to_add,
                            comment="test-comment"
                        )
                        
                        # Проверяем результаты
                        assert result is not None, "Результат должен быть не None"
                        assert 'client_uuid' in result, "Результат должен содержать client_uuid"
                        assert 'email' in result, "Результат должен содержать email"
                        assert 'expiry_timestamp_ms' in result, "Результат должен содержать expiry_timestamp_ms"
                        assert 'connection_string' in result, "Результат должен содержать connection_string"
                        assert result['client_uuid'] == "test-uuid-123"
                        assert result['email'] == email

    @pytest.mark.asyncio
    @allure.title("Продление существующего ключа на хосте")
    @allure.description("Проверяет продление существующего ключа на хосте через create_or_update_key_on_host. **Что проверяется:** обновление времени истечения существующего ключа, сохранение client_uuid. **Тестовые данные:** email='user123-key1@host.bot', days_to_add=20.0. **Ожидаемый результат:** ключ успешно продлен, client_uuid остался прежним, expiry_timestamp_ms обновлен.")
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("xui_api", "extend_key", "unit")
    async def test_create_or_update_key_extend(self, sample_host, temp_db):
        from shop_bot.modules.xui_api import create_or_update_key_on_host
        import sqlite3
        
        # Добавляем хост в БД
        with sqlite3.connect(str(temp_db), timeout=30) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO xui_hosts (host_name, host_url, host_username, host_pass, host_inbound_id, host_code)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                sample_host['host_name'],
                sample_host['host_url'],
                sample_host['host_username'],
                sample_host['host_pass'],
                sample_host['host_inbound_id'],
                sample_host['host_code']
            ))
            conn.commit()
        
        # Мокаем компоненты
        mock_api = MagicMock()
        mock_inbound = MagicMock()
        mock_inbound.id = 1
        mock_inbound.port = 443
        mock_inbound.stream_settings = {
            "reality_settings": {
                "settings": {
                    "publicKey": "test-public-key",
                    "fingerprint": "test-fingerprint"
                },
                "serverNames": ["example.com"],
                "shortIds": ["test-short-id"]
            }
        }
        mock_inbound.settings = MagicMock()
        
        # Существующий клиент
        existing_client = MagicMock()
        existing_client.email = "user123-key1@host.bot"
        existing_client.id = "existing-uuid-123"
        existing_client.expiry_time = int((datetime.now(timezone.utc) + timedelta(days=10)).timestamp() * 1000)
        
        mock_inbound.settings.clients = [existing_client]
        mock_api.inbound.get_by_id.return_value = mock_inbound
        mock_api.inbound.get_list.return_value = [mock_inbound]
        mock_api.inbound.update = Mock()
        mock_api.client.update = Mock()
        
        email = "user123-key1@host.bot"
        days_to_add = 20.0  # Продлеваем на 20 дней
        
        # Мокаем update_or_create_client_on_panel - возвращает новое время истечения
        new_expiry_ms = int((datetime.now(timezone.utc) + timedelta(days=30)).timestamp() * 1000)
        
        with patch('shop_bot.modules.xui_api.login_to_host', return_value=(mock_api, mock_inbound)):
            with patch('shop_bot.modules.xui_api.update_or_create_client_on_panel', return_value=("existing-uuid-123", new_expiry_ms)):
                with patch('shop_bot.modules.xui_api.get_sub_uri_from_panel', return_value=None):
                    with patch('shop_bot.modules.xui_api._panel_update_client_quota', return_value=True):
                        result = await create_or_update_key_on_host(
                            sample_host['host_name'],
                            email,
                            days_to_add,
                            comment="updated-comment"
                        )
                        
                        # Проверяем результаты
                        assert result is not None, "Результат должен быть не None"
                        assert result['client_uuid'] == "existing-uuid-123", "UUID должен остаться тем же"
                        assert result['expiry_timestamp_ms'] == new_expiry_ms, "Время истечения должно быть обновлено"
                        assert result['expiry_timestamp_ms'] > existing_client.expiry_time, \
                            "Новое время истечения должно быть больше старого"

    @allure.title("Логика карантина проблемных хостов")
    @allure.description("Проверяет логику карантина проблемных хостов в login_to_host. **Что проверяется:** пропуск подключения к хосту в карантине, очистка карантина, успешное подключение после карантина. **Тестовые данные:** host_url из sample_host. **Ожидаемый результат:** подключение к хосту в карантине пропущено (api=None, inbound=None), после очистки карантина подключение успешно.")
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("xui_api", "quarantine", "unit")
    def test_host_quarantine_logic(self, sample_host):
        from shop_bot.modules.xui_api import login_to_host, _host_quarantine_until, _HOST_QUARANTINE_SECONDS
        from time import time
        
        # Очищаем карантин перед тестом
        _host_quarantine_until.clear()
        
        # Помещаем хост в карантин
        host_url = sample_host['host_url']
        quarantine_until = time() + _HOST_QUARANTINE_SECONDS
        _host_quarantine_until[host_url] = quarantine_until
        
        # Попытка подключения к хосту в карантине должна вернуть None, None
        with patch('shop_bot.modules.xui_api.Api') as mock_api_class:
            api, inbound = login_to_host(
                host_url,
                sample_host['host_username'],
                sample_host['host_pass'],
                sample_host['host_inbound_id'],
                max_retries=1
            )
            
            # Проверяем, что подключение пропущено из-за карантина
            assert api is None, "API должен быть None из-за карантина"
            assert inbound is None, "Inbound должен быть None из-за карантина"
            
            # Проверяем, что Api не был вызван
            mock_api_class.assert_not_called()
        
        # Очищаем карантин и проверяем, что подключение возможно
        _host_quarantine_until.clear()
        
        # Мокаем успешное подключение
        mock_api = MagicMock()
        mock_api.login = Mock()
        mock_inbound = MagicMock()
        mock_inbound.id = 1
        mock_inbound.settings = MagicMock()
        mock_inbound.settings.clients = []
        
        mock_api.inbound.get_list.return_value = [mock_inbound]
        
        with patch('shop_bot.modules.xui_api.Api', return_value=mock_api):
            api, inbound = login_to_host(
                host_url,
                sample_host['host_username'],
                sample_host['host_pass'],
                sample_host['host_inbound_id'],
                max_retries=1
            )
            
            # Проверяем, что подключение успешно
            assert api is not None, "API должен быть не None после очистки карантина"
            assert inbound is not None, "Inbound должен быть не None после очистки карантина"
            
            # Проверяем, что карантин был очищен
            assert host_url not in _host_quarantine_until, "Карантин должен быть очищен после успешного подключения"

