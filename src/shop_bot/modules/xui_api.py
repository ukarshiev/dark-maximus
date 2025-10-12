# -*- coding: utf-8 -*-
"""
API для работы с X-UI панелью
"""

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

# Кэш для subURI настроек
_sub_uri_cache = {}

def get_sub_uri_from_panel(host_url: str, username: str, password: str) -> str | None:
    """Получает subURI из настроек 3x-ui панели"""
    cache_key = f"{host_url}:{username}"
    
    # Проверяем кэш
    if cache_key in _sub_uri_cache:
        return _sub_uri_cache[cache_key]
    
    try:
        session = requests.Session()
        base = host_url.rstrip('/')
        
        # Логин
        login_response = session.post(f"{base}/login", json={"username": username, "password": password}, timeout=10, verify=False)
        if login_response.status_code != 200:
            logger.warning(f"Failed to login to {base} for getting subURI")
            return None
        
        # Получаем настройки подписки
        settings_response = session.post(f"{base}/panel/setting/all", timeout=10, verify=False)
        if settings_response.status_code != 200:
            logger.warning(f"Failed to get settings from {base}")
            return None
        
        settings_data = settings_response.json()
        if not settings_data.get('success'):
            logger.warning(f"Settings request was not successful for {base}")
            return None
        
        # Получаем настройки из obj (это словарь, а не массив)
        obj = settings_data.get('obj', {})
        
        # Проверяем, есть ли готовый subURI
        sub_uri = obj.get('subURI')
        if sub_uri:
            # Кэшируем результат
            _sub_uri_cache[cache_key] = sub_uri
            logger.info(f"Got subURI from 3x-ui settings: {sub_uri}")
            return sub_uri
        
        # Если subURI пустой, формируем его из других полей
        sub_port = obj.get('subPort')
        sub_path = obj.get('subPath', '/sub/')
        sub_domain = obj.get('subDomain')
        
        if not sub_port:
            logger.warning(f"subPort not found in settings for {base}")
            return None
        
        # Определяем домен
        if sub_domain:
            domain = sub_domain
        else:
            # Используем домен из host_url
            parsed_url = urlparse(host_url)
            domain = parsed_url.hostname
        
        # Формируем subURI
        sub_uri = f"http://{domain}:{sub_port}{sub_path}"
        
        # Кэшируем результат
        _sub_uri_cache[cache_key] = sub_uri
        logger.info(f"Generated subURI from settings: {sub_uri}")
        return sub_uri
        
    except Exception as e:
        logger.error(f"Error getting subURI from {base}: {e}")
        return None

def login_to_host(host_url: str, username: str, password: str, inbound_id: int, max_retries: int = 3) -> tuple[Api | None, Inbound | None]:
    """Подключение к хосту с механизмом повторных попыток"""
    import time
    
    for attempt in range(max_retries):
        try:
            api = Api(host=host_url, username=username, password=password)
            api.login()
            inbounds: List[Inbound] = api.inbound.get_list()
            target_inbound = next((inbound for inbound in inbounds if inbound.id == inbound_id), None)
            
            if target_inbound is None:
                logger.error(f"Inbound with ID '{inbound_id}' not found on host '{host_url}'")
                return api, None
                
            logger.info(f"Successfully connected to host '{host_url}' (attempt {attempt + 1})")
            return api, target_inbound
            
        except Exception as e:
            logger.warning(f"Login attempt {attempt + 1}/{max_retries} failed for host '{host_url}': {e}")
            
            if attempt < max_retries - 1:
                wait_time = 2 ** attempt  # Экспоненциальная задержка: 1, 2, 4 секунды
                logger.info(f"Retrying in {wait_time} seconds...")
                time.sleep(wait_time)
            else:
                logger.error(f"All {max_retries} login attempts failed for host '{host_url}': {e}", exc_info=True)
                
    return None, None

def get_connection_string(inbound: Inbound, user_uuid: str, host_url: str, remark: str) -> str | None:
    if not inbound: 
        return None
    
    # Получаем stream_settings с проверкой типа
    stream_settings = inbound.stream_settings
    
    # Если stream_settings - строка, пытаемся распарсить JSON
    if isinstance(stream_settings, str):
        try:
            stream_settings = json.loads(stream_settings)
        except (json.JSONDecodeError, TypeError):
            logger.error(f"Failed to parse stream_settings JSON: {stream_settings}")
            return None
    
    # Проверяем наличие reality_settings
    if not hasattr(stream_settings, 'reality_settings') and not isinstance(stream_settings, dict):
        logger.error("stream_settings does not have reality_settings attribute and is not a dict")
        return None
    
    # Получаем reality_settings
    if hasattr(stream_settings, 'reality_settings'):
        reality_settings = getattr(stream_settings, 'reality_settings')
    elif isinstance(stream_settings, dict):
        reality_settings = stream_settings.get('reality_settings', {})
    else:
        logger.error("Cannot access reality_settings from stream_settings")
        return None
    
    # Если reality_settings - строка, пытаемся распарсить JSON
    if isinstance(reality_settings, str):
        try:
            reality_settings = json.loads(reality_settings)
        except (json.JSONDecodeError, TypeError):
            logger.error(f"Failed to parse reality_settings JSON: {reality_settings}")
            return None
    
    # Получаем настройки
    if isinstance(reality_settings, dict):
        settings = reality_settings.get("settings", {})
        public_key = settings.get("publicKey")
        fp = settings.get("fingerprint")
        server_names = reality_settings.get("serverNames")
        short_ids = reality_settings.get("shortIds")
    else:
        logger.error("reality_settings is not a dict")
        return None
    
    if not all([public_key, server_names, short_ids]): 
        return None
    
    # Проверяем, что server_names и short_ids - это списки
    if not isinstance(server_names, list) or not isinstance(short_ids, list):
        logger.error("server_names and short_ids must be lists")
        return None
    
    if not server_names or not short_ids:
        logger.error("server_names and short_ids cannot be empty")
        return None
    
    parsed_url = urlparse(host_url)
    short_id = short_ids[0]
    
    connection_string = (
        f"vless://{user_uuid}@{parsed_url.hostname}:{inbound.port}"
        f"?type=tcp&security=reality&pbk={public_key}&fp={fp}&sni={server_names[0]}"
        f"&sid={short_id}&spx=%2F&flow=xtls-rprx-vision#{remark}"
    )
    return connection_string

def update_client_quota_on_host(host_name: str, email: str, traffic_bytes: int) -> bool:
    """Обновляет квоту трафика клиента на указанном хосте через API панели"""
    try:
        host_data = get_host(host_name)
        if not host_data:
            logger.error(f"Host '{host_name}' not found in database")
            return False
            
        # Получаем информацию о ключе
        key_data = get_key_by_email(email)
        if not key_data:
            logger.error(f"Key with email '{email}' not found in database")
            return False
            
        # Сначала пробуем нативный API панели
        success = _panel_update_client_quota(
            host_url=host_data['host_url'],
            username=host_data['host_username'],
            password=host_data['host_pass'],
            inbound_id=host_data['host_inbound_id'],
            client_uuid=key_data['xui_client_uuid'],
            email=email,
            traffic_bytes=traffic_bytes,
            expiry_ms=key_data.get('expiry_date', 0),
            comment=str(key_data['user_id'])
        )
        
        if success:
            logger.info(f"Successfully updated quota for '{email}' on host '{host_name}' to {traffic_bytes} bytes via panel API")
            return True
        
        # Если API панели не сработал, пробуем через py3xui как fallback
        logger.warning(f"Panel API failed for '{email}', trying py3xui fallback")
        
        api, inbound = login_to_host(
            host_data['host_url'],
            host_data['host_username'], 
            host_data['host_pass'],
            host_data['host_inbound_id']
        )
        
        if not api or not inbound:
            logger.error(f"Failed to connect to host '{host_name}' via py3xui")
            return False
            
        # Используем старый метод через py3xui
        client_uuid, new_expiry_ms = update_or_create_client_on_panel(
            api, 
            inbound.id, 
            email, 
            days_to_add=0,  # Не изменяем срок действия
            comment=str(key_data['user_id']),
            traffic_gb=traffic_bytes / (1024 * 1024 * 1024)  # Конвертируем в гигабайты
        )
        
        if client_uuid:
            logger.info(f"Successfully updated quota for '{email}' on host '{host_name}' to {traffic_bytes} bytes via py3xui fallback")
            return True
        else:
            logger.error(f"Failed to update quota for '{email}' on host '{host_name}' via both methods")
            return False
        
    except Exception as e:
        logger.error(f"Error updating quota for '{email}' on host '{host_name}': {e}", exc_info=True)
        return False

def update_or_create_client_on_panel(api: Api, inbound_id: int, email: str, days_to_add: float, comment: str | None = None, traffic_gb: float | None = None, sub_id: str | None = None, telegram_chat_id: int | None = None) -> tuple[str | None, int | None]:
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
        
        # Используем UTC для совместимости с 3x-ui
        from datetime import timezone, timedelta
        utc_tz = timezone.utc
        utc_now = datetime.now(utc_tz)
        
        if client_index != -1:
            existing_client = inbound_to_modify.settings.clients[client_index]
            if existing_client.expiry_time > int(utc_now.timestamp() * 1000):
                current_expiry_dt = datetime.fromtimestamp(existing_client.expiry_time / 1000, tz=utc_tz)
                new_expiry_dt = current_expiry_dt + timedelta(days=days_to_add)
            else:
                new_expiry_dt = utc_now + timedelta(days=days_to_add)
        else:
            new_expiry_dt = utc_now + timedelta(days=days_to_add)

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
                    setattr(c, 'comment', comment)
                else:
                    setattr(c, 'comment', "")
            except Exception:
                pass
            # Обновляем subscription для существующих клиентов
            if sub_id:
                try:
                    setattr(c, 'subId', sub_id)
                    setattr(c, 'subscription', sub_id)
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
                    # totalGB должен быть в байтах, как и total
                    setattr(c, 'totalGB', int(traffic_bytes))
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
                flow="xtls-rprx-vision"
            )
            # Устанавливаем expiry_time через setattr
            setattr(new_client, 'expiry_time', new_expiry_ms)
            try:
                if comment is not None:
                    setattr(new_client, 'comment', comment)
                else:
                    setattr(new_client, 'comment', "")
            except Exception:
                pass
            # Устанавливаем subId для поддержки subscription (пробуем разные варианты)
            if sub_id:
                try:
                    setattr(new_client, 'sub_id', sub_id)
                    setattr(new_client, 'subId', sub_id)
                    setattr(new_client, 'subscription', sub_id)
                except Exception:
                    pass
            # Устанавливаем telegram_chat_id
            if telegram_chat_id:
                try:
                    setattr(new_client, 'tg_id', telegram_chat_id)
                    setattr(new_client, 'tgId', telegram_chat_id)
                except Exception:
                    pass
            elif email and 'user' in email:
                # Fallback: извлекаем user_id из email (user6044240344-key1@host.bot)
                try:
                    parts = email.split('@')[0].split('-')
                    if parts and parts[0].startswith('user'):
                        user_id = parts[0][4:]  # убираем 'user'
                        setattr(new_client, 'tg_id', int(user_id))
                        setattr(new_client, 'tgId', int(user_id))
                except Exception:
                    pass
            if traffic_bytes is not None:
                try:
                    setattr(new_client, 'total', int(traffic_bytes))  # bytes
                except Exception:
                    pass
                try:
                    # totalGB должен быть в байтах, как и total
                    setattr(new_client, 'totalGB', int(traffic_bytes))
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
                flow="xtls-rprx-vision"
            )
            # Устанавливаем expiry_time через setattr
            setattr(updated_client, 'expiry_time', new_expiry_ms)
            # Устанавливаем subId для поддержки subscription (пробуем разные варианты)
            if sub_id:
                try:
                    setattr(updated_client, 'sub_id', sub_id)
                    setattr(updated_client, 'subId', sub_id)
                    setattr(updated_client, 'subscription', sub_id)
                except Exception:
                    pass
            # Устанавливаем telegram_chat_id
            if telegram_chat_id:
                try:
                    setattr(updated_client, 'tg_id', telegram_chat_id)
                    setattr(updated_client, 'tgId', telegram_chat_id)
                except Exception:
                    pass
            elif email and 'user' in email:
                # Fallback: извлекаем user_id из email (user6044240344-key1@host.bot)
                try:
                    parts = email.split('@')[0].split('-')
                    if parts and parts[0].startswith('user'):
                        user_id = parts[0][4:]  # убираем 'user'
                        setattr(updated_client, 'tg_id', int(user_id))
                        setattr(updated_client, 'tgId', int(user_id))
                except Exception:
                    pass
            if traffic_bytes is not None:
                try:
                    setattr(updated_client, 'total', int(traffic_bytes))  # bytes
                except Exception:
                    pass
                try:
                    # totalGB должен быть в байтах, как и total
                    setattr(updated_client, 'totalGB', int(traffic_bytes))
                except Exception:
                    pass
            api.client.update(str(inbound_id), updated_client)
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

        return str(client_uuid) if client_uuid else None, new_expiry_ms

    except Exception as e:
        logger.error(f"Error in update_or_create_client_on_panel: {e}", exc_info=True)
        return None, None

async def create_or_update_key_on_host(host_name: str, email: str, days_to_add: float, comment: str | None = None, traffic_gb: float | None = None, sub_id: str | None = None, telegram_chat_id: int | None = None) -> Dict | None:
    logger.info(f"Starting key creation/update process for '{email}' on host '{host_name}' (days: {days_to_add})")
    
    host_data = get_host(host_name)
    if not host_data:
        logger.error(f"Workflow failed: Host '{host_name}' not found in the database.")
        return None

    logger.info(f"Attempting to connect to host '{host_name}' at {host_data['host_url']}")
    api, inbound = login_to_host(
        host_url=host_data['host_url'],
        username=host_data['host_username'],
        password=host_data['host_pass'],
        inbound_id=host_data['host_inbound_id']
    )
    if not api or not inbound:
        logger.error(f"Workflow failed: Could not log in or find inbound on host '{host_name}'.")
        return None
    
    logger.info(f"Successfully connected to host '{host_name}', attempting to create/update client '{email}'")
    client_uuid, new_expiry_ms = update_or_create_client_on_panel(api, inbound.id, email, days_to_add, comment, traffic_gb, sub_id, telegram_chat_id)
    if not client_uuid:
        logger.error(f"Workflow failed: Could not create/update client '{email}' on host '{host_name}'.")
        return None
    
    logger.info(f"Client '{email}' created/updated successfully, generating connection string")
    # Используем host_code вместо host_name для стабильности ключей
    host_code = host_data.get('host_code') or host_name
    connection_string = get_connection_string(inbound, client_uuid, host_data['host_url'], remark=host_code)
    
    logger.info(f"Successfully processed key for '{email}' on host '{host_name}'.")
    # Если задан лимит — продублируем точно как UI
    try:
        if traffic_gb is not None:
            traffic_bytes = int(float(traffic_gb) * 1024 * 1024 * 1024)
            if client_uuid and new_expiry_ms:
                _panel_update_client_quota(host_data['host_url'], host_data['host_username'], host_data['host_pass'], host_data['host_inbound_id'], client_uuid, email, new_expiry_ms, traffic_bytes)
    except Exception:
        pass
    
    # Получаем subscription_link из 3x-ui настроек
    subscription_link = None
    if sub_id:
        sub_uri = get_sub_uri_from_panel(host_data['host_url'], host_data['host_username'], host_data['host_pass'])
        if sub_uri:
            subscription_link = f"{sub_uri}{sub_id}"
            logger.info(f"Created subscription link: {subscription_link}")
        else:
            logger.warning(f"Could not get subURI from panel, subscription link will not be available")
    
    if new_expiry_ms:
        return {
            "client_uuid": client_uuid,
            "email": email,
            "expiry_timestamp_ms": new_expiry_ms,
            "connection_string": connection_string,
            "subscription_link": subscription_link,
            "host_name": host_name
        }
    else:
        return None

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

    # Используем host_code вместо host_name для стабильности ключей
    host_code = host_db_data.get('host_code') or host_name
    connection_string = get_connection_string(inbound, key_data['xui_client_uuid'], host_db_data['host_url'], remark=host_code)
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
        enabled_status = None
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
                    # Получаем статус включения
                    enabled_status = getattr(c, 'enable', None)
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
                    
                    # Проверяем, не отозван ли триал (квота = 1 МБ)
                    is_revoked_trial = False
                    if quota_total_gb is not None and quota_total_gb <= 0.001:  # 1 МБ = 0.001 ГБ
                        is_revoked_trial = True
                    
                    if is_trial and active and not is_revoked_trial:
                        status = 'trial-active'
                    elif is_trial and not active:
                        status = 'trial-ended'
                    elif is_trial and is_revoked_trial:
                        status = 'deactivate'  # Отозванный триал
                    elif not is_trial and active:
                        status = 'pay-active'
                    else:
                        status = 'pay-ended'
                    break
        # Получаем дополнительные поля из клиента (используем правильные поля 3x-ui)
        subscription = None
        subscription_link = None
        telegram_chat_id = None
        comment = None

        if target_inbound and target_inbound.settings and target_inbound.settings.clients:
            for c in target_inbound.settings.clients:
                cid = str(getattr(c, 'id', '') or '')
                cemail = str(getattr(c, 'email', '') or '')
                if cid == str(key_data.get('xui_client_uuid')) or (key_data.get('key_email') and cemail == str(key_data.get('key_email'))):
                    # Используем правильные поля 3x-ui
                    subscription = getattr(c, 'sub_id', None) or getattr(c, 'subId', None)
                    telegram_chat_id = getattr(c, 'tg_id', None) or getattr(c, 'tgId', None)
                    # Пробуем извлечь comment из разных полей
                    comment = getattr(c, 'comment', None) or getattr(c, 'comments', None) or getattr(c, 'description', None)
                    
                    # Получаем subscription link из 3x-ui настроек
                    if subscription:
                        sub_uri = get_sub_uri_from_panel(host_db_data['host_url'], host_db_data['host_username'], host_db_data['host_pass'])
                        if sub_uri:
                            subscription_link = f"{sub_uri}{subscription}"
                            logger.debug(f"Created subscription link: {subscription_link}")
                        else:
                            logger.warning(f"Could not get subURI from panel for {cemail}")
                    
                    break
        
        return {
            "connection_string": connection_string, 
            "expiry_timestamp_ms": exp_ms, 
            "status": status, 
            "protocol": protocol, 
            "created_at": created_at, 
            "remaining_seconds": remaining_seconds, 
            "quota_remaining_bytes": quota_remaining_bytes, 
            "quota_total_gb": quota_total_gb, 
            "traffic_down_bytes": traffic_down_bytes, 
            "enabled": enabled_status,
            "subscription": subscription,
            "subscription_link": subscription_link,
            "telegram_chat_id": telegram_chat_id,
            "comment": comment
        }
    except Exception:
        return {"connection_string": connection_string}

async def delete_client_by_uuid(client_uuid: str, client_email: str | None = None) -> bool:
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
                api.client.delete(inbound.id, str(client_uuid))
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


async def update_client_attributes_on_host(host_name: str, email: str, subscription: str = None, telegram_chat_id: int = None, comment: str = None) -> bool:
    """Обновляет атрибуты клиента (subscription, telegram_chat_id, comment) в 3x-ui панели"""
    try:
        host_data = get_host(host_name)
        if not host_data:
            logger.error(f"Host '{host_name}' not found in database")
            return False
            
        # Получаем информацию о ключе
        key_data = get_key_by_email(email)
        if not key_data:
            logger.error(f"Key with email '{email}' not found in database")
            return False
            
        # Подключаемся к панели
        api, inbound = login_to_host(
            host_url=host_data['host_url'],
            username=host_data['host_username'],
            password=host_data['host_pass'],
            inbound_id=host_data['host_inbound_id']
        )
        
        if not api or not inbound:
            logger.error(f"Cannot login to host '{host_name}'")
            return False
            
        # Получаем данные inbound
        inbound_to_modify = api.inbound.get_by_id(inbound.id)
        if not inbound_to_modify or not inbound_to_modify.settings.clients:
            logger.error(f"No clients found in inbound {inbound.id}")
            return False
            
        # Находим клиента
        client_found = False
        for client in inbound_to_modify.settings.clients:
            if client.email == email:
                client_found = True
                
                # Обновляем атрибуты (пробуем разные варианты полей для UI)
                if subscription:
                    try:
                        setattr(client, 'sub_id', subscription)
                        setattr(client, 'subId', subscription)
                        setattr(client, 'subscription', subscription)
                    except Exception as e:
                        logger.warning(f"Failed to set subscription for {email}: {e}")
                        
                if telegram_chat_id:
                    try:
                        setattr(client, 'tg_id', telegram_chat_id)
                        setattr(client, 'tgId', telegram_chat_id)
                        setattr(client, 'telegram_chat_id', telegram_chat_id)
                        setattr(client, 'telegramChatId', telegram_chat_id)
                        setattr(client, 'telegram_id', telegram_chat_id)
                    except Exception as e:
                        logger.warning(f"Failed to set telegram_chat_id for {email}: {e}")
                        
                # Пробуем разные варианты для комментария
                if comment is not None:
                    try:
                        setattr(client, 'comment', comment)
                        setattr(client, 'comments', comment)
                        setattr(client, 'description', comment)
                        setattr(client, 'remark', comment)
                        setattr(client, 'label', comment)
                    except Exception as e:
                        logger.warning(f"Failed to set comment for {email}: {e}")
                        
                break
                
        if not client_found:
            logger.error(f"Client '{email}' not found on host '{host_name}'")
            return False
            
        # Обновляем inbound
        api.inbound.update(inbound.id, inbound_to_modify)
        logger.info(f"Successfully updated client attributes for '{email}' on host '{host_name}'")
        return True
        
    except Exception as e:
        logger.error(f"Failed to update client attributes for '{email}' on host '{host_name}': {e}")
        return False

async def delete_client_on_host(host_name: str, client_email: str, client_uuid: str | None = None) -> bool:
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
                api.client.delete(inbound.id, str(client_to_delete['xui_client_uuid']))
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
                        api.client.delete(inbound.id, str(client.id))
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

def _panel_update_client_quota(host_url: str, username: str, password: str, inbound_id: int, client_uuid: str, email: str, traffic_bytes: int, expiry_ms: int, comment: str = "") -> bool:
    """Обновляет квоту трафика клиента через нативный эндпоинт панели"""
    try:
        base = host_url.rstrip('/')
        session = requests.Session()
        
        # Логин
        login_response = session.post(f"{base}/login", json={"username": username, "password": password}, timeout=10, verify=False)
        if login_response.status_code != 200:
            logger.error(f"Failed to login to {base}")
            return False
            
        # Получаем текущие данные inbound
        get_response = session.get(f"{base}/panel/inbound/get/{inbound_id}", timeout=10, verify=False)
        if get_response.status_code != 200:
            logger.error(f"Failed to get inbound data: HTTP {get_response.status_code}")
            logger.error(f"Response content: {get_response.text[:500]}")
            return False
            
        try:
            inbound_data = get_response.json()
        except Exception as e:
            logger.error(f"Failed to parse JSON response: {e}")
            logger.error(f"Response content: {get_response.text[:500]}")
            return False
            
        if not inbound_data.get('success'):
            logger.error(f"Failed to get inbound data: {inbound_data.get('msg', 'Unknown error')}")
            return False
            
        # Находим и обновляем клиента
        clients = inbound_data.get('obj', {}).get('settings', {}).get('clients', [])
        updated_clients = []
        
        for client in clients:
            if client.get('id') == client_uuid or client.get('email') == email:
                # Обновляем только квоту трафика
                client['total'] = traffic_bytes
                client['totalGB'] = traffic_bytes  # totalGB тоже в байтах
                client['updated_at'] = int(datetime.utcnow().timestamp() * 1000)
                logger.info(f"Updated client {email} quota to {traffic_bytes} bytes")
            updated_clients.append(client)
        
        # Подготавливаем данные для обновления всего inbound
        obj = inbound_data.get('obj', {})
        update_data = {
            "id": str(inbound_id),
            "userId": "0",
            "up": str(obj.get('up', 0)),
            "down": str(obj.get('down', 0)),
            "total": str(obj.get('total', 0)),
            "allTime": str(obj.get('allTime', 0)),
            "remark": obj.get('remark', ''),
            "enable": str(obj.get('enable', True)),
            "expiryTime": str(obj.get('expiryTime', 0)),
            "listen": obj.get('listen', ''),
            "port": str(obj.get('port', 0)),
            "protocol": obj.get('protocol', ''),
            "settings": json.dumps({"clients": updated_clients, "decryption": obj.get('settings', {}).get('decryption', 'none'), "fallbacks": obj.get('settings', {}).get('fallbacks', [])}, ensure_ascii=False),
            "streamSettings": json.dumps(obj.get('streamSettings', {}), ensure_ascii=False),
            "sniffing": json.dumps(obj.get('sniffing', {}), ensure_ascii=False),
            "tag": obj.get('tag', '')
        }
        
        # Добавляем статистику клиентов
        client_stats = inbound_data.get('obj', {}).get('clientStats', [])
        for i, client in enumerate(client_stats):
            for key, value in client.items():
                update_data[f"clientStats[{i}][{key}]"] = str(value)
        
        # Отправляем обновление
        headers = {"Content-Type": "application/x-www-form-urlencoded; charset=UTF-8", "X-Requested-With": "XMLHttpRequest"}
        response = session.post(f"{base}/panel/inbound/update/{inbound_id}", data=update_data, headers=headers, timeout=10, verify=False)
        
        if response.status_code == 200:
            try:
                response_data = response.json()
                if response_data.get('success'):
                    logger.info(f"Successfully updated quota for client '{email}' to {traffic_bytes} bytes via panel endpoint")
                    return True
                else:
                    logger.error(f"Failed to update client: {response_data.get('msg', 'Unknown error')}")
                    return False
            except ValueError:
                # Если ответ не JSON, но статус 200, считаем успешным
                logger.info(f"Successfully updated quota for client '{email}' to {traffic_bytes} bytes via panel endpoint (non-JSON response)")
                return True
            except Exception as e:
                logger.error(f"Failed to parse update response JSON: {e}")
                logger.error(f"Update response content: {response.text[:500]}")
                return False
        else:
            logger.warning(f"Panel endpoint returned status {response.status_code} for client '{email}'")
            logger.warning(f"Update response content: {response.text[:500]}")
            return False
            
    except Exception as e:
        try:
            from shop_bot.webhook_server.app import logger as app_logger
            app_logger.error(f"Error in _panel_update_client_quota: {e}", exc_info=True)
        except Exception:
            pass
        return False

def _panel_update_client_enabled_status(host_url: str, username: str, password: str, inbound_id: int, client_uuid: str, email: str, enabled: bool, expiry_ms: int, comment: str = "") -> bool:
    """Обновляет статус включения/отключения клиента через нативный эндпоинт панели"""
    try:
        base = host_url.rstrip('/')
        session = requests.Session()
        
        # Логин
        login_response = session.post(f"{base}/login", json={"username": username, "password": password}, timeout=10, verify=False)
        if login_response.status_code != 200:
            logger.error(f"Failed to login to {base}")
            return False
            
        # Получаем текущие данные inbound
        get_response = session.get(f"{base}/panel/inbound/get/{inbound_id}", timeout=10, verify=False)
        if get_response.status_code != 200:
            logger.error(f"Failed to get inbound data: HTTP {get_response.status_code}")
            return False
            
        inbound_data = get_response.json()
        if not inbound_data.get('success'):
            logger.error(f"Failed to get inbound data: {inbound_data.get('msg', 'Unknown error')}")
            return False
            
        # Находим и обновляем клиента
        clients = inbound_data.get('obj', {}).get('settings', {}).get('clients', [])
        updated_clients = []
        
        for client in clients:
            if client.get('id') == client_uuid or client.get('email') == email:
                # Обновляем статус включения
                client['enable'] = enabled
                client['updated_at'] = int(datetime.utcnow().timestamp() * 1000)
                
                # При отключении ключа устанавливаем expiryTime на текущее время
                if not enabled:
                    from datetime import timezone as _tz
                    now_ms = int(datetime.now(_tz.utc).timestamp() * 1000)
                    client['expiryTime'] = now_ms
                
                logger.info(f"Updated client {email} enabled status to {enabled}")
            updated_clients.append(client)
        
        # Подготавливаем данные для обновления всего inbound
        obj = inbound_data.get('obj', {})
        update_data = {
            "id": str(inbound_id),
            "userId": "0",
            "up": str(obj.get('up', 0)),
            "down": str(obj.get('down', 0)),
            "total": str(obj.get('total', 0)),
            "allTime": str(obj.get('allTime', 0)),
            "remark": obj.get('remark', ''),
            "enable": str(obj.get('enable', True)),  # Статус inbound остается неизменным
            "expiryTime": str(obj.get('expiryTime', 0)),
            "listen": obj.get('listen', ''),
            "port": str(obj.get('port', 0)),
            "protocol": obj.get('protocol', ''),
            "settings": json.dumps({"clients": updated_clients, "decryption": obj.get('settings', {}).get('decryption', 'none'), "fallbacks": obj.get('settings', {}).get('fallbacks', [])}, ensure_ascii=False),
            "streamSettings": json.dumps(obj.get('streamSettings', {}), ensure_ascii=False),
            "sniffing": json.dumps(obj.get('sniffing', {}), ensure_ascii=False),
            "tag": obj.get('tag', '')
        }
        
        # Добавляем статистику клиентов
        client_stats = inbound_data.get('obj', {}).get('clientStats', [])
        for i, client in enumerate(client_stats):
            for key, value in client.items():
                update_data[f"clientStats[{i}][{key}]"] = str(value)
        
        # Отправляем обновление
        headers = {"Content-Type": "application/x-www-form-urlencoded; charset=UTF-8", "X-Requested-With": "XMLHttpRequest"}
        response = session.post(f"{base}/panel/inbound/update/{inbound_id}", data=update_data, headers=headers, timeout=10, verify=False)
        
        if response.status_code == 200:
            try:
                response_data = response.json()
                if response_data.get('success'):
                    logger.info(f"Successfully updated enabled status for client '{email}' to {enabled} via panel endpoint")
                    return True
                else:
                    logger.error(f"Failed to update client: {response_data.get('msg', 'Unknown error')}")
                    return False
            except ValueError:
                # Если ответ не JSON, но статус 200, считаем успешным
                logger.info(f"Successfully updated enabled status for client '{email}' to {enabled} via panel endpoint (non-JSON response)")
                return True
        else:
            logger.warning(f"Panel endpoint returned status {response.status_code} for client '{email}'")
            return False
            
    except Exception as e:
        try:
            from shop_bot.webhook_server.app import logger as app_logger
            app_logger.error(f"Failed panel updateClient enabled status for {email}: {e}")
        except Exception:
            logger.error(f"Failed panel updateClient enabled status for {email}: {e}")
        return False

async def update_client_enabled_status_on_host(host_name: str, client_email: str, enabled: bool) -> bool:
    """Обновляет статус включения/отключения клиента на указанном хосте"""
    try:
        host_data = get_host(host_name)
        if not host_data:
            logger.error(f"Host '{host_name}' not found in database.")
            return False
        
        api, inbound = login_to_host(host_data['host_url'], host_data['host_username'], host_data['host_pass'], host_data['host_inbound_id'])
        if not api or not inbound:
            logger.error(f"Failed to login to host '{host_name}'.")
            return False
        
        # Получаем данные inbound с клиентами
        inbound_data = api.inbound.get_by_id(inbound.id)
        if not inbound_data or not inbound_data.settings.clients:
            logger.warning(f"No clients found in inbound on host '{host_name}'.")
            return False
        
        # Ищем клиента по email
        client = None
        for c in inbound_data.settings.clients:
            if c.email == client_email:
                client = c
                break
        
        if not client:
            logger.warning(f"Client with email '{client_email}' not found on host '{host_name}'.")
            return False
        
        # Обновляем статус включения клиента
        client.enable = enabled
        
        # При отключении ключа устанавливаем expiry_time на текущее время
        if not enabled:
            from datetime import timezone as _tz
            now_ms = int(datetime.now(_tz.utc).timestamp() * 1000)
            client.expiry_time = now_ms
        
        # Сохраняем изменения через inbound
        api.inbound.update(inbound.id, inbound_data)
        
        # Дополнительно используем нативный эндпоинт панели для максимальной совместимости
        try:
            panel_success = _panel_update_client_enabled_status(
                host_data['host_url'], 
                host_data['host_username'], 
                host_data['host_pass'], 
                host_data['host_inbound_id'], 
                str(client.id), 
                client_email, 
                enabled,
                client.expiry_time
            )
            if panel_success:
                logger.info(f"Successfully updated enabled status for client '{client_email}' via panel endpoint.")
            else:
                logger.warning(f"Panel endpoint update failed for '{client_email}', but API updates succeeded.")
        except Exception as e:
            logger.warning(f"Panel endpoint update failed for '{client_email}': {e}, but API updates succeeded.")
        
        logger.info(f"Successfully updated enabled status for client '{client_email}' on host '{host_name}' to {enabled}.")
        return True
        
    except Exception as e:
        logger.error(f"Failed to update enabled status for client '{client_email}' on host '{host_name}': {e}", exc_info=True)
        return False

def get_subscription_settings(host_url: str, username: str, password: str) -> dict | None:
    """Получает настройки подписки (subscription) из панели 3x-ui"""
    try:
        base = host_url.rstrip('/')
        session = requests.Session()
        
        # Логин
        login_response = session.post(f"{base}/login", json={"username": username, "password": password}, timeout=10, verify=False)
        if login_response.status_code != 200:
            logger.error(f"Failed to login to {base} to get subscription settings")
            return None
        
        # Получаем настройки панели через API
        # В 3x-ui настройки подписки хранятся в /panel/setting
        settings_response = session.post(f"{base}/panel/setting/all", timeout=10, verify=False)
        if settings_response.status_code != 200:
            logger.error(f"Failed to get settings from {base}: HTTP {settings_response.status_code}")
            return None
        
        try:
            settings_data = settings_response.json()
            if not settings_data.get('success'):
                logger.error(f"Failed to get settings: {settings_data.get('msg', 'Unknown error')}")
                return None
            
            obj = settings_data.get('obj', {})
            sub_uri = obj.get('subURI', '')
            sub_json_uri = obj.get('subJsonURI', '')
            
            return {
                'subURI': sub_uri,
                'subJsonURI': sub_json_uri
            }
        except Exception as e:
            logger.error(f"Failed to parse settings response: {e}")
            return None
            
    except Exception as e:
        logger.error(f"Error getting subscription settings from {host_url}: {e}", exc_info=True)
        return None

async def get_client_subscription_link(host_name: str, client_email: str) -> str | None:
    """Получает subscription link для клиента по email"""
    try:
        host_data = get_host(host_name)
        if not host_data:
            logger.error(f"Host '{host_name}' not found in database")
            return None
        
        api, inbound = login_to_host(
            host_data['host_url'],
            host_data['host_username'],
            host_data['host_pass'],
            host_data['host_inbound_id']
        )
        
        if not api or not inbound:
            logger.error(f"Failed to login to host '{host_name}'")
            return None
        
        # Получаем данные inbound с клиентами
        inbound_data = api.inbound.get_by_id(inbound.id)
        if not inbound_data or not inbound_data.settings.clients:
            logger.warning(f"No clients found in inbound on host '{host_name}'")
            return None
        
        # Ищем клиента по email и получаем его subId
        client_sub_id = None
        for client in inbound_data.settings.clients:
            if client.email == client_email:
                # subId может быть атрибутом клиента
                client_sub_id = getattr(client, 'subId', None) or getattr(client, 'sub_id', None)
                break
        
        if not client_sub_id:
            logger.warning(f"Client '{client_email}' not found or has no subId on host '{host_name}'")
            return None
        
        # Получаем настройки подписки из панели
        sub_settings = get_subscription_settings(
            host_data['host_url'],
            host_data['host_username'],
            host_data['host_pass']
        )
        
        if not sub_settings or not sub_settings.get('subURI'):
            logger.error(f"Failed to get subscription settings for host '{host_name}'")
            return None
        
        # Формируем subscription link
        subscription_link = f"{sub_settings['subURI']}{client_sub_id}"
        logger.info(f"Generated subscription link for client '{client_email}': {subscription_link}")
        
        return subscription_link
        
    except Exception as e:
        logger.error(f"Error getting subscription link for '{client_email}' on host '{host_name}': {e}", exc_info=True)
        return None

