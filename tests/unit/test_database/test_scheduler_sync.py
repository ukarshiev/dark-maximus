# -*- coding: utf-8 -*-
"""
Unit-тесты: синхронизация ключей с панелями — без удаления, только привязанный inbound.
"""

import pytest
import allure
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from shop_bot.data_manager.scheduler import SYNC_DELETION_DISABLED, sync_keys_with_panels


@pytest.mark.unit
@pytest.mark.database
@allure.epic("База данных")
@allure.feature("Синхронизация с панелями")
@allure.label("package", "src.shop_bot.data_manager.scheduler")
class TestSchedulerSyncNoDelete:
    """Политика безопасности: истекшие и orphan ключи не удаляются."""

    @allure.title("Флаг отключения удаления включён")
    @allure.severity(allure.severity_level.CRITICAL)
    @allure.tag("sync", "no-delete", "unit", "critical")
    def test_sync_deletion_disabled_flag(self):
        assert SYNC_DELETION_DISABLED is True, "Удаление ключей должно быть отключено политикой"

    @pytest.mark.asyncio
    @allure.title("sync_keys_with_panels не вызывает удаление ключей и клиентов")
    @allure.description("При синхронизации не вызываются delete_client_on_host, delete_key_by_email.")
    @allure.severity(allure.severity_level.CRITICAL)
    @allure.tag("sync", "no-delete", "unit", "critical")
    async def test_sync_does_not_delete_keys_or_clients(self, temp_db):
        from shop_bot.data_manager import database
        database.DB_FILE = temp_db
        database.initialize_db()
        database.create_host("h1", "http://localhost", "u", "p", 1, "c1")
        database.register_user_if_not_exists(123, "u", None, None)
        expiry_ms = int((datetime.now(timezone.utc) + timedelta(days=1)).timestamp() * 1000)
        database.add_new_key(123, "h1", "uuid1", "u1@h.bot", expiry_ms)

        with patch("shop_bot.data_manager.scheduler.xui_api.login_to_host") as login:
            inbound = MagicMock()
            inbound.id = 1
            full_inbound = MagicMock()
            full_inbound.settings.clients = []
            login.return_value = (MagicMock(), inbound)
            api = login.return_value[0]
            api.inbound.get_by_id = MagicMock(return_value=full_inbound)
            with patch("shop_bot.data_manager.scheduler.xui_api.delete_client_on_host", new_callable=AsyncMock) as del_client:
                with patch("shop_bot.data_manager.scheduler.database.delete_key_by_email") as del_key:
                    await sync_keys_with_panels()
                    del_client.assert_not_called()
                    del_key.assert_not_called()


@pytest.mark.unit
@allure.epic("База данных")
@allure.feature("Синхронизация с панелями")
@allure.label("package", "src.shop_bot.data_manager.scheduler")
class TestSchedulerSyncBoundInbound:
    """Синхронизация использует только привязанный host_inbound_id."""

    @pytest.mark.asyncio
    @allure.title("login_to_host вызывается с host_inbound_id из хоста")
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("sync", "inbound", "unit")
    async def test_sync_uses_bound_inbound_id(self, temp_db):
        from shop_bot.data_manager import database
        database.DB_FILE = temp_db
        database.initialize_db()
        database.create_host("h2", "http://localhost", "u", "p", 42, "c2")

        with patch("shop_bot.data_manager.scheduler.xui_api.login_to_host") as login:
            inbound = MagicMock()
            inbound.id = 42
            inbound.settings.clients = []
            api = MagicMock()
            api.inbound.get_by_id = MagicMock(return_value=MagicMock(settings=MagicMock(clients=[])))
            login.return_value = (api, inbound)
            await sync_keys_with_panels()
            inbound_ids = [c[1].get("inbound_id") for c in login.call_args_list if len(c) >= 2]
            assert 42 in inbound_ids, "Должен вызываться login_to_host с host_inbound_id=42 из БД"
