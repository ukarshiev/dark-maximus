import uuid
from datetime import datetime, timedelta
import logging
from urllib.parse import urlparse
from typing import List, Dict
import json
import requests
import sqlite3

from py3xui import Api, Client, Inbound

from shop_bot.data_manager.database import get_host, get_key_by_email, DB_FILE

logger = logging.getLogger(__name__)

def _panel_update_client_quota(host_url: str, username: str, password: str, inbound_id: int, client_uuid: str, email: str, expiry_ms: int, traffic_bytes: int) -> None:
    """Обновляет клиента через нативный эндпоинт панели, как делает UI (form: id + settings)."""
    try:
        base = host_url.rstrip('/')
        session = requests.Session()
        # Логин
        session.post(f"{base}/login", json={"username": username, "password": password}, timeout=10, verify=False)
        # Пейлоад клиента (минимально достаточный набор полей)
        now_ms = int(datetime.utcnow().timestamp() * 1000)
        # В UI разных форков поле ограничения может называться по-разному:
        # total (bytes) или totalGB (гигабайты). Мы передаём оба: bytes и GB.
        client_payload = {
            "id": client_uuid,
            "flow": "xtls-rprx-vision",
            "email": email,
            "limitIp": 0,
            # Байтный лимит (универсально поддерживается как total)
            "total": int(traffic_bytes),
            # Дублируем в гигабайтах для некоторых сборок x-ui, ожидающих GB
            "totalGB": round(int(traffic_bytes) / (1024 * 1024 * 1024), 2),
            "expiryTime": int(expiry_ms),
            "enable": True,
            "tgId": "",
            "subId": "",
            "comment": "",
            "reset": None,
            "created_at": now_ms,
            "updated_at": now_ms,
        }
        form = {
            "id": str(inbound_id),
            "settings": json.dumps({"clients": [client_payload]}, ensure_ascii=False)
        }
        # Обновление
        url = f"{base}/panel/inbound/updateClient/{client_uuid}"
        headers = {"Content-Type": "application/x-www-form-urlencoded; charset=UTF-8", "X-Requested-With": "XMLHttpRequest"}
        session.post(url, data=form, headers=headers, timeout=10, verify=False)
    except Exception as e:
        try:
            from shop_bot.webhook_server.app import logger as app_logger
            app_logger.error(f"Failed panel updateClient for {email}: {e}")
        except Exception:
            logger.error(f"Failed panel updateClient for {email}: {e}")

def login_to_host(host_url: str, username: str, password: str, inbound_id: int) -> tuple[Api | None, Inbound | None]:
    try:
        api = Api(host=host_url, username=username, password=password)
        api.login()
        inbounds: List[Inbound] = api.inbound.get_list()
        target_inbound = next((inbound for inbound in inbounds if inbound.id == inbound_id), None)
        
        if target_inbound is None:
            logger.error(f"Inbound with ID '{inbound_id}' not found on host '{host_url}'")
            return api, None
        return api, target_inbound
    except Exception as e:
        logger.error(f"Login or inbound retrieval failed for host '{host_url}': {e}", exc_info=True)
        return None, None

def get_connection_string(inbound: Inbound, user_uuid: str, host_url: str, remark: str) -> str | None:
    if not inbound: return None
    settings = inbound.stream_settings.reality_settings.get("settings")
    if not settings: return None
    
    public_key = settings.get("publicKey")
    fp = settings.get("fingerprint")
    server_names = inbound.stream_settings.reality_settings.get("serverNames")
    short_ids = inbound.stream_settings.reality_settings.get("shortIds")
    port = inbound.port
    
    if not all([public_key, server_names, short_ids]): return None
    
    parsed_url = urlparse(host_url)
    short_id = short_ids[0]
    
    connection_string = (
        f"vless://{user_uuid}@{parsed_url.hostname}:{port}"
        f"?type=tcp&security=reality&pbk={public_key}&fp={fp}&sni={server_names[0]}"
        f"&sid={short_id}&spx=%2F&flow=xtls-rprx-vision#{remark}"
    )
    return connection_string

def update_or_create_client_on_panel(api: Api, inbound_id: int, email: str, days_to_add: int, comment: str | None = None, traffic_gb: float | None = None) -> tuple[str | None, int | None]:
    try:
        inbound_to_modify = api.inbound.get_by_id(inbound_id)
        if not inbound_to_modify:
            raise ValueError(f"Could not find inbound with ID {inbound_id}")

        if inbound_to_modify.settings.clients is None:
            inbound_to_modify.settings.clients = []
            
        client_index = -1
        for i, client in enumerate(inbound_to_modify.settings.clients):
            if client.email == email:
                client_index = i
                break
        
        # Используем UTC+3 для соответствия с ботом
        from datetime import timezone, timedelta
        local_tz = timezone(timedelta(hours=3))  # UTC+3 для России
        local_now = datetime.now(local_tz)
        
        if client_index != -1:
            existing_client = inbound_to_modify.settings.clients[client_index]
            if existing_client.expiry_time > int(local_now.timestamp() * 1000):
                current_expiry_dt = datetime.fromtimestamp(existing_client.expiry_time / 1000, tz=local_tz)
                new_expiry_dt = current_expiry_dt + timedelta(days=days_to_add)
            else:
                new_expiry_dt = local_now + timedelta(days=days_to_add)
        else:
            new_expiry_dt = local_now + timedelta(days=days_to_add)

        new_expiry_ms = int(new_expiry_dt.timestamp() * 1000)

        # Подготовим лимит трафика
        traffic_bytes = None
        if traffic_gb is not None:
            try:
                traffic_gb_val = float(traffic_gb)
                traffic_bytes = int(traffic_gb_val * 1024 * 1024 * 1024)
                if traffic_bytes < 0:
                    traffic_bytes = 0
            except Exception:
                traffic_bytes = None
                traffic_gb_val = None

        if client_index != -1:
            c = inbound_to_modify.settings.clients[client_index]
            c.expiry_time = new_expiry_ms
            c.enable = True
            try:
                if comment is not None:
                    c.comment = comment
            except Exception:
                pass
            before_total = getattr(c, 'total', None)
            before_totalGB = getattr(c, 'totalGB', None)
            if traffic_bytes is not None:
                try:
                    setattr(c, 'total', int(traffic_bytes))  # bytes
                except Exception:
                    pass
                try:
                    # Для совместимости: некоторые форки трактуют totalGB как гигабайты
                    setattr(c, 'totalGB', round(int(traffic_bytes) / (1024 * 1024 * 1024), 2))
                except Exception:
                    pass
            after_total = getattr(c, 'total', None)
            after_totalGB = getattr(c, 'totalGB', None)
            try:
                from shop_bot.webhook_server.app import logger as app_logger
                app_logger.info(f"XUI set traffic for {email}: before total={before_total}, totalGB={before_totalGB} -> after total={after_total}, totalGB={after_totalGB}")
            except Exception:
                pass
            client_uuid = c.id
        else:
            client_uuid = str(uuid.uuid4())
            new_client = Client(
                id=client_uuid,
                email=email,
                enable=True,
                flow="xtls-rprx-vision",
                expiry_time=new_expiry_ms
            )
            try:
                if comment is not None:
                    setattr(new_client, 'comment', comment)
            except Exception:
                pass
            if traffic_bytes is not None:
                try:
                    setattr(new_client, 'total', int(traffic_bytes))  # bytes
                except Exception:
                    pass
                try:
                    setattr(new_client, 'totalGB', round(int(traffic_bytes) / (1024 * 1024 * 1024), 2))
                except Exception:
                    pass
            inbound_to_modify.settings.clients.append(new_client)

        api.inbound.update(inbound_id, inbound_to_modify)

        # Дополнительно client.update
        try:
            updated_client = Client(
                id=client_uuid,
                email=email,
                enable=True,
                flow="xtls-rprx-vision",
                expiry_time=new_expiry_ms
            )
            if traffic_bytes is not None:
                try:
                    setattr(updated_client, 'total', int(traffic_bytes))  # bytes
                except Exception:
                    pass
                try:
                    setattr(updated_client, 'totalGB', round(int(traffic_bytes) / (1024 * 1024 * 1024), 2))
                except Exception:
                    pass
            api.client.update(inbound_id, updated_client)
            try:
                from shop_bot.webhook_server.app import logger as app_logger
                app_logger.info(f"XUI client.update pushed for {email}: total(bytes)={traffic_bytes}")
            except Exception:
                pass
        except Exception:
            pass

        # Верификация
        try:
            updated_inbound = api.inbound.get_by_id(inbound_id)
            for cli in (updated_inbound.settings.clients or []):
                if getattr(cli, 'email', None) == email:
                    ut = getattr(cli, 'total', None)
                    utGB = getattr(cli, 'totalGB', None)
                    from shop_bot.webhook_server.app import logger as app_logger
                    app_logger.info(f"XUI verify traffic for {email}: total={ut}, totalGB={utGB}")
                    break
        except Exception:
            pass

        return client_uuid, new_expiry_ms

    except Exception as e:
        logger.error(f"Error in update_or_create_client_on_panel: {e}", exc_info=True)
        return None, None

async def create_or_update_key_on_host(host_name: str, email: str, days_to_add: int, comment: str | None = None, traffic_gb: float | None = None) -> Dict | None:
    host_data = get_host(host_name)
    if not host_data:
        logger.error(f"Workflow failed: Host '{host_name}' not found in the database.")
        return None

    api, inbound = login_to_host(
        host_url=host_data['host_url'],
        username=host_data['host_username'],
        password=host_data['host_pass'],
        inbound_id=host_data['host_inbound_id']
    )
    if not api or not inbound:
        logger.error(f"Workflow failed: Could not log in or find inbound on host '{host_name}'.")
        return None
        
    client_uuid, new_expiry_ms = update_or_create_client_on_panel(api, inbound.id, email, days_to_add, comment, traffic_gb)
    if not client_uuid:
        logger.error(f"Workflow failed: Could not create/update client '{email}' on host '{host_name}'.")
        return None
    
    connection_string = get_connection_string(inbound, client_uuid, host_data['host_url'], remark=host_name)
    
    logger.info(f"Successfully processed key for '{email}' on host '{host_name}'.")
    # Если задан лимит — продублируем точно как UI
    try:
        if traffic_gb is not None:
            traffic_bytes = int(float(traffic_gb) * 1024 * 1024 * 1024)
            _panel_update_client_quota(host_data['host_url'], host_data['host_username'], host_data['host_pass'], host_data['host_inbound_id'], client_uuid, email, new_expiry_ms, traffic_bytes)
    except Exception:
        pass
    
    return {
        "client_uuid": client_uuid,
        "email": email,
        "expiry_timestamp_ms": new_expiry_ms,
        "connection_string": connection_string,
        "host_name": host_name
    }

async def get_key_details_from_host(key_data: dict) -> dict | None:
    host_name = key_data.get('host_name')
    if not host_name:
        logger.error(f"Could not get key details: host_name is missing for key_id {key_data.get('key_id')}")
        return None

    host_db_data = get_host(host_name)
    if not host_db_data:
        logger.error(f"Could not get key details: Host '{host_name}' not found in the database.")
        return None

    api, inbound = login_to_host(
        host_url=host_db_data['host_url'],
        username=host_db_data['host_username'],
        password=host_db_data['host_pass'],
        inbound_id=host_db_data['host_inbound_id']
    )
    if not api or not inbound: return None

    connection_string = get_connection_string(inbound, key_data['xui_client_uuid'], host_db_data['host_url'], remark=host_name)
    # Получаем свежий expiry_time клиента из панели
    try:
        target_inbound = api.inbound.get_by_id(host_db_data['host_inbound_id'])
        # На некоторых сборках get_by_id не возвращает clientStats.
        # В таком случае подменим inbound объектом из списка, где clientStats присутствует.
        try:
            has_stats = getattr(target_inbound, 'clientStats', None) is not None or getattr(target_inbound, 'client_stats', None) is not None
            if not has_stats:
                inbounds_list = api.inbound.get_list()
                for ib in inbounds_list:
                    if getattr(ib, 'id', None) == host_db_data['host_inbound_id']:
                        target_inbound = ib
                        break
        except Exception:
            pass
        exp_ms = None
        status = None
        protocol = None
        created_at = None
        remaining_seconds = None
        quota_remaining_bytes = None
        quota_total_gb = None
        traffic_down_bytes = None
        if target_inbound and target_inbound.settings and target_inbound.settings.clients:
            protocol = getattr(target_inbound, 'protocol', None)
            # Собираем карту статистики по email из clientStats, если доступно
            stats_map = {}
            try:
                client_stats = getattr(target_inbound, 'clientStats', None)
                if client_stats is None:
                    client_stats = getattr(target_inbound, 'client_stats', None)
                if client_stats:
                    for s in client_stats:
                        s_email = str(getattr(s, 'email', '') or '')
                        if not s_email:
                            continue
                        try:
                            s_total = int(getattr(s, 'total', 0) or 0)
                            s_up = int(getattr(s, 'up', 0) or 0)
                            s_down = int(getattr(s, 'down', 0) or 0)
                        except Exception:
                            s_total, s_up, s_down = 0, 0, 0
                        stats_map[s_email] = (s_total, s_up, s_down)
            except Exception:
                pass

            for c in target_inbound.settings.clients:
                cid = str(getattr(c, 'id', '') or '')
                cemail = str(getattr(c, 'email', '') or '')
                if cid == str(key_data.get('xui_client_uuid')) or (key_data.get('key_email') and cemail == str(key_data.get('key_email'))):
                    exp_ms = getattr(c, 'expiry_time', None)
                    # created_at / usage start
                    created_at = getattr(c, 'created_at', None) or getattr(c, 'enableDate', None)
                    # traffic quota remaining: сначала пробуем clientStats, затем fallback на settings.clients
                    try:
                        total_limit_bytes = None
                        up_bytes = 0
                        down_bytes = 0

                        if cemail in stats_map:
                            s_total, s_up, s_down = stats_map[cemail]
                            total_limit_bytes = s_total
                            up_bytes = s_up
                            down_bytes = s_down
                            traffic_down_bytes = down_bytes
                            quota_total_gb = round(total_limit_bytes / (1024*1024*1024), 2) if total_limit_bytes else None
                            try:
                                from shop_bot.webhook_server.app import logger as app_logger  # lazy import
                            except Exception:
                                app_logger = None
                            if app_logger:
                                app_logger.info(f"XUI traffic debug (clientStats) for {key_data.get('key_email')}: total={total_limit_bytes}, up={up_bytes}, down={down_bytes}")
                        else:
                            # traffic fields across x-ui forks
                            if hasattr(c, 'total') and getattr(c, 'total') not in [None, '', 'null']:
                                total_limit_bytes = int(getattr(c, 'total'))
                                quota_total_gb = round(total_limit_bytes / (1024*1024*1024), 2)
                            elif hasattr(c, 'totalGB') and getattr(c, 'totalGB') not in [None, '', 'null']:
                                quota_total_gb = float(getattr(c, 'totalGB'))
                                total_limit_bytes = int(quota_total_gb * 1024 * 1024 * 1024)
                            elif hasattr(c, 'total_gb') and getattr(c, 'total_gb') not in [None, '', 'null']:
                                quota_total_gb = float(getattr(c, 'total_gb'))
                                total_limit_bytes = int(quota_total_gb * 1024 * 1024 * 1024)

                            def _to_int(val):
                                try:
                                    if val in [None, '', 'null']:
                                        return 0
                                    return int(float(val))
                                except Exception:
                                    return 0
                            up_bytes = _to_int(getattr(c, 'up', getattr(c, 'upload', 0)))
                            down_bytes = _to_int(getattr(c, 'down', getattr(c, 'download', 0)))
                            traffic_down_bytes = down_bytes

                            try:
                                from shop_bot.webhook_server.app import logger as app_logger  # lazy import
                            except Exception:
                                app_logger = None
                            if app_logger:
                                app_logger.info(f"XUI traffic debug (clients) for {key_data.get('key_email')}: total={total_limit_bytes}, up={up_bytes}, down={down_bytes}")

                        if total_limit_bytes is None or total_limit_bytes == 0 or total_limit_bytes == -1:
                            quota_remaining_bytes = None  # бесконечно/не задано
                        else:
                            quota_remaining_bytes = max(0, int(total_limit_bytes) - (up_bytes + down_bytes))
                    except Exception:
                        quota_remaining_bytes = None
                    # вычисление статуса
                    from datetime import timezone, datetime
                    now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
                    is_trial = int(key_data.get('is_trial') or 0) == 1
                    active = exp_ms is not None and exp_ms > now_ms
                    if exp_ms is not None:
                        remaining_seconds = max(0, int((exp_ms - now_ms) / 1000))
                    if is_trial and active:
                        status = 'trial-active'
                    elif is_trial and not active:
                        status = 'trial-ended'
                    elif not is_trial and active:
                        status = 'pay-active'
                    else:
                        status = 'pay-ended'
                    break
        return {"connection_string": connection_string, "expiry_timestamp_ms": exp_ms, "status": status, "protocol": protocol, "created_at": created_at, "remaining_seconds": remaining_seconds, "quota_remaining_bytes": quota_remaining_bytes, "quota_total_gb": quota_total_gb, "traffic_down_bytes": traffic_down_bytes}
    except Exception:
        return {"connection_string": connection_string}

async def delete_client_by_uuid(client_uuid: str, client_email: str = None) -> bool:
    """Удаляет клиента напрямую по UUID из всех доступных хостов"""
    if not client_uuid or client_uuid == 'Unknown':
        logger.error(f"Cannot delete client: Invalid UUID '{client_uuid}'")
        return False
    
    # Получаем все хосты из базы данных
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM xui_hosts")
            hosts = [dict(row) for row in cursor.fetchall()]
    except Exception as e:
        logger.error(f"Error getting hosts: {e}")
        return False
    
    # Пытаемся удалить клиента с каждого хоста
    for host_data in hosts:
        try:
            api, inbound = login_to_host(
                host_url=host_data['host_url'],
                username=host_data['host_username'],
                password=host_data['host_pass'],
                inbound_id=host_data['host_inbound_id']
            )
            
            if not api or not inbound:
                logger.warning(f"Cannot login to host '{host_data['host_name']}', skipping...")
                continue
            
            try:
                # Пытаемся удалить по UUID
                api.client.delete(inbound.id, client_uuid)
                logger.info(f"Successfully deleted client '{client_uuid}' (email: '{client_email or 'Unknown'}') from host '{host_data['host_name']}'")
                return True
            except Exception as e:
                logger.debug(f"Client '{client_uuid}' not found on host '{host_data['host_name']}': {e}")
                continue
                
        except Exception as e:
            logger.warning(f"Error processing host '{host_data['host_name']}': {e}")
            continue
    
    logger.warning(f"Client with UUID '{client_uuid}' not found on any host")
    return False

async def delete_client_on_host(host_name: str, client_email: str, client_uuid: str = None) -> bool:
    """Устаревшая функция - используйте delete_client_by_uuid для прямого удаления по UUID"""
    # Если есть UUID, используем новую функцию
    if client_uuid and client_uuid != 'Unknown':
        return await delete_client_by_uuid(client_uuid, client_email)
    
    # Иначе используем старую логику
    host_data = get_host(host_name)
    if not host_data:
        logger.error(f"Cannot delete client: Host '{host_name}' not found.")
        return False

    api, inbound = login_to_host(
        host_url=host_data['host_url'],
        username=host_data['host_username'],
        password=host_data['host_pass'],
        inbound_id=host_data['host_inbound_id']
    )

    if not api or not inbound:
        logger.error(f"Cannot delete client: Login or inbound lookup failed for host '{host_name}'.")
        return False
        
    try:
        # Ищем в базе данных
        client_to_delete = get_key_by_email(client_email)
        
        if client_to_delete and client_to_delete.get('xui_client_uuid'):
            # Если клиент найден в базе, удаляем по UUID из базы
            try:
                api.client.delete(inbound.id, client_to_delete['xui_client_uuid'])
                logger.info(f"Successfully deleted client '{client_to_delete['xui_client_uuid']}' from host '{host_name}' by database UUID.")
                return True
            except Exception as e:
                logger.warning(f"Failed to delete client '{client_to_delete['xui_client_uuid']}' by database UUID: {e}. Trying email search.")
        
        # Если удаление по UUID не удалось, ищем по email в 3x-ui панели
        logger.info(f"Searching client by email '{client_email}' in 3x-ui panel.")
        
        # Получаем список всех клиентов в inbound
        inbound_data = api.inbound.get_by_id(inbound.id)
        if inbound_data and inbound_data.settings.clients:
            for client in inbound_data.settings.clients:
                if client.email == client_email:
                    # Найден клиент в панели, удаляем его
                    try:
                        api.client.delete(inbound.id, client.id)
                        logger.info(f"Successfully deleted client '{client.id}' (email: '{client_email}') from host '{host_name}' by email search.")
                        return True
                    except Exception as e:
                        logger.error(f"Failed to delete client '{client.id}' by email search: {e}")
                        continue
        
        # Клиент не найден ни в базе, ни в панели
        logger.warning(f"Client with email '{client_email}' not found on host '{host_name}' (already deleted or never existed).")
        return True
            
    except Exception as e:
        logger.error(f"Failed to delete client '{client_email}' from host '{host_name}': {e}", exc_info=True)
        return False