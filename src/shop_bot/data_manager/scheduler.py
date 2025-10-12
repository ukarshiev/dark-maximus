# -*- coding: utf-8 -*-
"""
Планировщик задач для бота
"""

import asyncio
import logging

from datetime import datetime, timedelta, timezone
from decimal import Decimal
import uuid
import json

from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram import Bot

from shop_bot.bot_controller import BotController
from shop_bot.data_manager import database
from shop_bot.modules import xui_api
from shop_bot.bot import keyboards

CHECK_INTERVAL_SECONDS = 300
NOTIFY_BEFORE_HOURS = {72, 48, 24, 1}
notified_users = {}

logger = logging.getLogger(__name__)

def format_time_left(hours: int) -> str:
    if hours >= 24:
        days = hours // 24
        if days % 10 == 1 and days % 100 != 11:
            return f"{days} день"
        elif 2 <= days % 10 <= 4 and (days % 100 < 10 or days % 100 >= 20):
            return f"{days} дня"
        else:
            return f"{days} дней"
    else:
        if hours % 10 == 1 and hours % 100 != 11:
            return f"{hours} час"
        elif 2 <= hours % 10 <= 4 and (hours % 100 < 10 or hours % 100 >= 20):
            return f"{hours} часа"
        else:
            return f"{hours} часов"

async def send_subscription_notification(bot: Bot, user_id: int, key_id: int, time_left_hours: int, expiry_date: datetime):
    try:
        from datetime import timezone, timedelta
        # Дополнительная проверка: не отправляем уведомления, если время истекло
        # Используем UTC для сравнения, т.к. expiry_date хранится в UTC
        current_time_utc = datetime.now(timezone.utc).replace(tzinfo=None)
        if expiry_date <= current_time_utc:
            logger.warning(f"Attempted to send expiry notification for already expired key {key_id} (user {user_id}). Skipping.")
            return
        
        # Проверяем, что time_left_hours соответствует реальному времени до истечения
        actual_time_left = expiry_date - current_time_utc
        actual_hours_left = int(actual_time_left.total_seconds() / 3600)
        if time_left_hours <= 0 or actual_hours_left <= 0:
            logger.warning(f"Invalid time_left_hours ({time_left_hours}) or actual_hours_left ({actual_hours_left}) for key {key_id}. Skipping notification.")
            return
        
        time_text = format_time_left(time_left_hours)
        # Конвертируем время из UTC в UTC+3 (Moscow) для отображения пользователю
        moscow_tz = timezone(timedelta(hours=3))
        expiry_moscow = expiry_date.replace(tzinfo=timezone.utc).astimezone(moscow_tz)
        expiry_str = expiry_moscow.strftime('%d.%m.%Y в %H:%M')

        # Получаем номер ключа для пользователя и имя сервера
        try:
            from shop_bot.data_manager.database import get_user_keys, get_key_by_id
            key_data = get_key_by_id(key_id) or {}
            host_name = key_data.get('host_name', 'Неизвестный сервер')
            # Определяем порядковый номер ключа среди ключей пользователя
            user_keys = get_user_keys(user_id) or []
            key_number = next((i + 1 for i, k in enumerate(user_keys) if k.get('key_id') == key_id), 0)
        except Exception:
            host_name = 'Неизвестный сервер'
            key_number = 0

        key_descriptor = f"#{key_number} ({host_name})" if key_number > 0 else f"({host_name})"

        # Баланс пользователя
        try:
            from shop_bot.data_manager.database import get_user_balance
            balance_val = float(get_user_balance(user_id) or 0.0)
        except Exception:
            balance_val = 0.0
        balance_str = f"{balance_val:.2f} RUB"

        message = (
            f"⚠️ **Внимание!** ⚠️\n\n"
            f"Срок действия вашего ключа {key_descriptor} истекает через **{time_text}**.\n"
            f"📅 Дата окончания: **{expiry_str}**\n"
            f"💰 Ваш баланс : **{balance_str}**\n\n"
            f"Пополните счет, чтобы произошло автоматическое списание с баланса или продлите подписку прямо сейчас, чтобы не остаться без доступа к VPN!"
        )

        builder = InlineKeyboardBuilder()
        builder.button(text="🔄 Продлить ключ", callback_data=f"extend_key_{key_id}")
        builder.button(text="💰 Пополнить баланс", callback_data="topup_root")
        builder.adjust(2)

        await bot.send_message(chat_id=user_id, text=message, reply_markup=builder.as_markup(), parse_mode='Markdown')
        # Логируем уведомление в БД
        try:
            from shop_bot.data_manager.database import log_notification, get_user
            user = get_user(user_id)
            log_notification(
                user_id=user_id,
                username=(user or {}).get('username'),
                notif_type='subscription_expiry',
                title=f'Окончание подписки (через {time_text})',
                message=message,
                status='sent',
                meta={
                    'key_id': key_id,
                    'expiry_at': expiry_str,
                    'time_left_hours': time_left_hours,
                    'key_number': key_number,
                    'host_name': host_name
                },
                key_id=key_id,
                marker_hours=time_left_hours
            )
        except Exception as le:
            logger.warning(f"Failed to log notification for user {user_id}: {le}")
        logger.info(f"Sent subscription notification to user {user_id} for key {key_id} ({time_left_hours} hours left).")
        
    except Exception as e:
        logger.error(f"Error sending subscription notification to user {user_id}: {e}")

def _cleanup_notified_users(all_db_keys: list[dict]):
    if not notified_users:
        return

    logger.info("Scheduler: Cleaning up the notification cache...")
    
    active_key_ids = {key['key_id'] for key in all_db_keys}
    
    users_to_check = list(notified_users.keys())
    
    cleaned_users = 0
    cleaned_keys = 0

    for user_id in users_to_check:
        keys_to_check = list(notified_users[user_id].keys())
        for key_id in keys_to_check:
            if key_id not in active_key_ids:
                del notified_users[user_id][key_id]
                cleaned_keys += 1
        
        if not notified_users[user_id]:
            del notified_users[user_id]
            cleaned_users += 1
    
    if cleaned_users > 0 or cleaned_keys > 0:
        logger.info(f"Scheduler: Cleanup complete. Removed {cleaned_users} user entries and {cleaned_keys} key entries from the cache.")

def _marker_logged(user_id: int, key_id: int, marker_hours: int, notif_type: str = 'subscription_expiry') -> bool:
    try:
        from shop_bot.data_manager.database import DB_FILE
        import sqlite3
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT 1 FROM notifications WHERE user_id = ? AND key_id = ? AND marker_hours = ? AND type = ? LIMIT 1",
                (user_id, key_id, marker_hours, notif_type)
            )
            return cursor.fetchone() is not None
    except Exception:
        return False

async def send_plan_unavailable_notice(bot: Bot, user_id: int, key_id: int, time_left_hours: int, expiry_date: datetime):
    """Уведомление о недоступности тарифа для автопродления."""
    try:
        from datetime import timezone, timedelta
        # Проверяем, что время не истекло
        current_time_utc = datetime.now(timezone.utc).replace(tzinfo=None)
        if expiry_date <= current_time_utc:
            logger.warning(f"Attempted to send plan unavailable notice for already expired key {key_id} (user {user_id}). Skipping.")
            return
        
        time_text = format_time_left(time_left_hours)
        # Конвертируем время из UTC в UTC+3 (Moscow) для отображения пользователю
        moscow_tz = timezone(timedelta(hours=3))
        expiry_moscow = expiry_date.replace(tzinfo=timezone.utc).astimezone(moscow_tz)
        expiry_str = expiry_moscow.strftime('%d.%m.%Y в %H:%M')

        # Получаем номер ключа и имя сервера
        try:
            from shop_bot.data_manager.database import get_user_keys, get_key_by_id
            key_data = get_key_by_id(key_id) or {}
            host_name = key_data.get('host_name', 'Неизвестный сервер')
            user_keys = get_user_keys(user_id) or []
            key_number = next((i + 1 for i, k in enumerate(user_keys) if k.get('key_id') == key_id), 0)
        except Exception:
            host_name = 'Неизвестный сервер'
            key_number = 0

        message = (
            "⚠️ Внимание! Ваш тариф больше не доступен для автопродления.\n\n"
            f"Ключ #{key_number} ({host_name}) истекает через {time_text}.\n"
            f"📅 Окончание: {expiry_str}\n\n"
            "Пожалуйста, выберите новый тариф до истечения срока.\n\n"
            "Для продления перейдите в меню: 🛒 Купить → 🔄 Продлить ключ"
        )

        await bot.send_message(chat_id=user_id, text=message)

        # Логируем уведомление в БД
        try:
            from shop_bot.data_manager.database import log_notification, get_user
            user = get_user(user_id)
            log_notification(
                user_id=user_id,
                username=(user or {}).get('username'),
                notif_type='subscription_plan_unavailable',
                title=f'Тариф недоступен (через {time_text})',
                message=message,
                status='sent',
                meta={
                    'key_id': key_id,
                    'expiry_at': expiry_str,
                    'time_left_hours': time_left_hours,
                    'key_number': key_number,
                    'host_name': host_name
                }
            )
        except Exception as e:
            logger.warning(f"Failed to log plan unavailable notification: {e}")

        logger.info(f"Sent plan unavailable notice to user {user_id} for key {key_id}, time_left={time_left_hours}h")
    except Exception as e:
        logger.error(f"Failed to send plan unavailable notice to user {user_id} for key {key_id}: {e}", exc_info=True)


async def send_autorenew_balance_notice(bot: Bot, user_id: int, key_id: int, time_left_hours: int, expiry_date: datetime, balance_val: float):
    try:
        from datetime import timezone, timedelta
        # Дополнительная проверка: не отправляем уведомления, если время истекло
        # Используем UTC для сравнения, т.к. expiry_date хранится в UTC
        current_time_utc = datetime.now(timezone.utc).replace(tzinfo=None)
        if expiry_date <= current_time_utc:
            logger.warning(f"Attempted to send autorenew notice for already expired key {key_id} (user {user_id}). Skipping.")
            return
        
        # Проверяем, что time_left_hours соответствует реальному времени до истечения
        actual_time_left = expiry_date - current_time_utc
        actual_hours_left = int(actual_time_left.total_seconds() / 3600)
        if time_left_hours <= 0 or actual_hours_left <= 0:
            logger.warning(f"Invalid time_left_hours ({time_left_hours}) or actual_hours_left ({actual_hours_left}) for autorenew notice key {key_id}. Skipping notification.")
            return
        
        time_text = format_time_left(time_left_hours)
        # Конвертируем время из UTC в UTC+3 (Moscow) для отображения пользователю
        moscow_tz = timezone(timedelta(hours=3))
        expiry_moscow = expiry_date.replace(tzinfo=timezone.utc).astimezone(moscow_tz)
        expiry_str = expiry_moscow.strftime('%d.%m.%Y в %H:%M')

        # Получаем номер ключа и имя сервера
        try:
            from shop_bot.data_manager.database import get_user_keys, get_key_by_id
            key_data = get_key_by_id(key_id) or {}
            host_name = key_data.get('host_name', 'Неизвестный сервер')
            user_keys = get_user_keys(user_id) or []
            key_number = next((i + 1 for i, k in enumerate(user_keys) if k.get('key_id') == key_id), 0)
        except Exception:
            host_name = 'Неизвестный сервер'
            key_number = 0

        balance_str = f"{float(balance_val or 0):.2f} RUB"

        # Определяем сумму тарифа для продления
        try:
            _, price_to_renew, _, _, _ = _get_plan_info_for_key(key_data)
        except Exception:
            price_to_renew = float(key_data.get('price') or 0.0)
        price_str = f"{float(price_to_renew or 0):.2f} RUB"

        message = (
            "❕ Информация о ключе ❔\n\n"
            f"Срок действия ключа #{key_number} ({host_name}) истекает через {time_text}.\n"
            f"📅 Окончание: {expiry_str}\n"
            f"💰 Баланс: {balance_str}\n\n"
            f"🔄 Не беспокойтесь - вам ничего делать не нужно! Услуга продлится автоматически, сумма {price_str} будет списана с вашего баланса.\n\n"
            "❤️ Спасибо, что остаётесь с нами!"
        )

        await bot.send_message(chat_id=user_id, text=message)

        # Логируем уведомление в БД
        try:
            from shop_bot.data_manager.database import log_notification, get_user
            user = get_user(user_id)
            log_notification(
                user_id=user_id,
                username=(user or {}).get('username'),
                notif_type='subscription_autorenew_notice',
                title=f'Автопродление (через {time_text})',
                message=message,
                status='sent',
                meta={
                    'key_id': key_id,
                    'expiry_at': expiry_str,
                    'time_left_hours': time_left_hours,
                    'key_number': key_number,
                    'host_name': host_name,
                    'balance': balance_str,
                    'price': price_str
                },
                key_id=key_id,
                marker_hours=time_left_hours
            )
        except Exception as le:
            logger.warning(f"Failed to log autorenew notice for user {user_id}: {le}")
        logger.info(f"Sent autorenew balance notice to user {user_id} for key {key_id} ({time_left_hours} hours left).")
    except Exception as e:
        logger.error(f"Error sending autorenew notice to user {user_id}: {e}")

def _get_plan_info_for_key(key: dict) -> tuple[dict | None, float, int, int | None, bool]:
    """Возвращает (plan_dict, price, months, plan_id, is_available) для ключа.
    
    is_available = True, если тариф найден и доступен для автопродления
    is_available = False, если тариф удален или скрыт (hidden_all, hidden_old)
    """
    try:
        from shop_bot.data_manager.database import get_plans_for_host
        host_name = key.get('host_name')
        plan_name = key.get('plan_name')
        price_fallback = float(key.get('price') or 0.0)
        plans = get_plans_for_host(host_name) if host_name else []
        matched = next((p for p in plans if (p.get('plan_name') == plan_name)), None)
        
        if matched:
            # Проверяем режим отображения тарифа
            display_mode = matched.get('display_mode', 'all')
            # Тариф недоступен, если скрыт для всех или для старых пользователей
            is_available = display_mode not in ['hidden_all', 'hidden_old']
            return matched, float(matched.get('price') or 0.0), int(matched.get('months') or 0), int(matched.get('plan_id')), is_available
        
        # Тариф не найден - недоступен
        return None, price_fallback, 0, None, False
    except Exception as e:
        logger.warning(f"Failed to resolve plan for key {key.get('key_id')}: {e}")
        return None, float(key.get('price') or 0.0), 0, None, False

async def check_expiring_subscriptions(bot: Bot):
    from datetime import timezone
    logger.info("Scheduler: Checking for expiring subscriptions...")
    # Используем UTC для проверки истечения, т.к. все даты в БД хранятся в UTC
    current_time = datetime.now(timezone.utc).replace(tzinfo=None)
    all_keys = database.get_all_keys()
    
    _cleanup_notified_users(all_keys)
    
    for key in all_keys:
        try:
            expiry_date = datetime.fromisoformat(key['expiry_date'])
            # Убираем timezone info для совместимости
            if expiry_date.tzinfo is not None:
                expiry_date = expiry_date.replace(tzinfo=None)
            time_left = expiry_date - current_time

            if time_left.total_seconds() < 0:
                continue

            total_hours_left = int(time_left.total_seconds() / 3600)
            user_id = key['user_id']
            key_id = key['key_id']

            # Цена и длительность для продления, баланс пользователя, доступность тарифа
            plan_info, price_to_renew, months_to_renew, plan_id, is_plan_available = _get_plan_info_for_key(key)
            from shop_bot.data_manager.database import get_user_balance
            user_balance = float(get_user_balance(user_id) or 0.0)

            # Catch-up: решаем, что отправлять на каждом маркере
            # Важно: не отправляем уведомления, если ключ уже истек
            # Проверяем по секундам, а не по целым часам, чтобы обрабатывать ключи с оставшимся временем < 1 часа
            if time_left.total_seconds() > 0:
                # Ищем наименьший подходящий маркер (сортируем по возрастанию: 1, 24, 48, 72)
                for hours_mark in sorted(NOTIFY_BEFORE_HOURS):
                    if total_hours_left <= hours_mark:
                        # Проверяем доступность тарифа для автопродления
                        if not is_plan_available:
                            # Тариф удален или скрыт - отправляем предупреждение
                            if not _marker_logged(user_id, key_id, hours_mark, 'subscription_plan_unavailable'):
                                await send_plan_unavailable_notice(bot, user_id, key_id, hours_mark, expiry_date)
                                notified_users.setdefault(user_id, {}).setdefault(key_id, set()).add(hours_mark)
                                break
                            continue
                        
                        balance_covers = price_to_renew > 0 and user_balance >= price_to_renew
                        if balance_covers:
                            # Подавляем стандартные уведомления. На 24ч — отправляем новый тип, один раз.
                            if hours_mark == 24 and not _marker_logged(user_id, key_id, hours_mark, 'subscription_autorenew_notice'):
                                await send_autorenew_balance_notice(bot, user_id, key_id, hours_mark, expiry_date, user_balance)
                                notified_users.setdefault(user_id, {}).setdefault(key_id, set()).add(hours_mark)
                                break
                            # 72/48/1 — ничего не отправляем
                            continue
                        else:
                            # Обычные уведомления
                            if not _marker_logged(user_id, key_id, hours_mark, 'subscription_expiry'):
                                await send_subscription_notification(bot, user_id, key_id, hours_mark, expiry_date)
                                notified_users.setdefault(user_id, {}).setdefault(key_id, set()).add(hours_mark)
                                break
            else:
                # Ключ уже истек - не отправляем уведомления об истечении
                logger.debug(f"Key {key_id} for user {user_id} has already expired ({int(time_left.total_seconds())} seconds left). Skipping notifications.")

        except Exception as e:
            logger.error(f"Error processing expiry for key {key.get('key_id')}: {e}")

async def perform_auto_renewals(bot: Bot):
    """Автопродление по истечении срока при достаточном балансе."""
    try:
        all_keys = database.get_all_keys()
        now = datetime.now()
        for key in all_keys:
            try:
                expiry_date = datetime.fromisoformat(key['expiry_date'])
                # Убираем timezone info для совместимости
                if expiry_date.tzinfo is not None:
                    expiry_date = expiry_date.replace(tzinfo=None)
            except Exception:
                continue

            # Продлеваем только если уже истёк
            if expiry_date > now:
                continue

            user_id = key['user_id']
            key_id = key['key_id']
            host_name = key.get('host_name')
            plan_info, price_to_renew, months_to_renew, plan_id, is_plan_available = _get_plan_info_for_key(key)

            # Требуем валидный план, цену и доступность тарифа
            if not plan_info or not months_to_renew or not plan_id or price_to_renew <= 0 or not is_plan_available:
                continue

            from shop_bot.data_manager.database import get_user_balance, add_to_user_balance, log_transaction, get_user
            current_balance = float(get_user_balance(user_id) or 0.0)
            if current_balance < price_to_renew:
                continue

            # Метаданные платежа
            payment_id = str(uuid.uuid4())
            metadata = {
                'user_id': user_id,
                'months': int(months_to_renew),
                'price': float(price_to_renew),
                'action': 'extend',
                'key_id': key_id,
                'host_name': host_name,
                'plan_id': int(plan_id),
                'customer_email': None,
                'payment_method': 'Auto-Renewal',
                'payment_id': payment_id
            }

            try:
                # Списание и логирование
                add_to_user_balance(user_id, -float(price_to_renew))
                user = get_user(user_id) or {}
                username = user.get('username', 'N/A')
                log_transaction(
                    username=username,
                    transaction_id=None,
                    payment_id=payment_id,
                    user_id=user_id,
                    status='paid',
                    amount_rub=float(price_to_renew),
                    amount_currency=None,
                    currency_name=None,
                    payment_method='Auto-Renewal',
                    metadata=json.dumps(metadata)
                )

                # Обработка, как при обычной оплате
                from shop_bot.bot.handlers import process_successful_payment
                await process_successful_payment(bot, metadata)
                logger.info(f"Auto-renewal completed for user {user_id}, key {key_id} on host '{host_name}'.")
            except Exception as e:
                logger.error(f"Auto-renewal failed for user {user_id}, key {key_id}: {e}", exc_info=True)
    except Exception as e:
        logger.error(f"perform_auto_renewals: fatal error: {e}")

async def sync_keys_with_panels():
    logger.info("Scheduler: Starting sync with XUI panels...")
    total_affected_records = 0
    
    all_hosts = database.get_all_hosts()
    if not all_hosts:
        logger.info("Scheduler: No hosts configured in the database. Sync skipped.")
        return

    orphan_summary: list[tuple[str, int]] = []
    auto_delete = (database.get_setting("auto_delete_orphans") == "true")

    for host in all_hosts:
        host_name = host['host_name']
        logger.info(f"Scheduler: Processing host: '{host_name}'")
        
        try:
            api, inbound = xui_api.login_to_host(
                host_url=host['host_url'],
                username=host['host_username'],
                password=host['host_pass'],
                inbound_id=host['host_inbound_id']
            )

            if not api or not inbound:
                logger.error(f"Scheduler: Could not log in to host '{host_name}'. Skipping this host.")
                continue
            
            full_inbound_details = api.inbound.get_by_id(inbound.id)
            clients_on_server = {client.email: client for client in (full_inbound_details.settings.clients or [])}
            logger.info(f"Scheduler: Found {len(clients_on_server)} clients on the '{host_name}' panel.")

            keys_in_db = database.get_keys_for_host(host_name)
            
            for db_key in keys_in_db:
                key_email = db_key['key_email']
                expiry_date = datetime.fromisoformat(db_key['expiry_date'])
                # Убираем timezone info для совместимости
                if expiry_date.tzinfo is not None:
                    expiry_date = expiry_date.replace(tzinfo=None)
                now = datetime.now()
                if expiry_date < now - timedelta(days=5):
                    logger.info(f"Scheduler: Key '{key_email}' expired more than 5 days ago. Deleting from panel and DB.")
                    try:
                        await xui_api.delete_client_on_host(host_name, key_email)
                    except Exception as e:
                        logger.error(f"Scheduler: Failed to delete client '{key_email}' from panel: {e}")
                    database.delete_key_by_email(key_email)
                    total_affected_records += 1
                    continue

                server_client = clients_on_server.pop(key_email, None)

                if server_client:
                    reset_days = server_client.reset if server_client.reset is not None else 0
                    server_expiry_ms = server_client.expiry_time + reset_days * 24 * 3600 * 1000
                    local_expiry_dt = expiry_date
                    local_expiry_ms = int(local_expiry_dt.timestamp() * 1000)

                    if abs(server_expiry_ms - local_expiry_ms) > 1000:
                        database.update_key_status_from_server(key_email, server_client)
                        total_affected_records += 1
                        logger.info(f"Scheduler: Synced (updated) key '{key_email}' for host '{host_name}'.")
                else:
                    logger.warning(f"Scheduler: Key '{key_email}' for host '{host_name}' not found on server. Deleting from local DB.")
                    database.update_key_status_from_server(key_email, None)
                    total_affected_records += 1

            if clients_on_server:
                count_orphans = len(clients_on_server)
                orphan_summary.append((host_name, count_orphans))
                # Логируем кратко список до 5 шт. для наглядности
                sample = list(clients_on_server.keys())[:5]
                logger.warning(f"Scheduler: Found {count_orphans} orphan clients on host '{host_name}'. Sample: {sample}")
                # Опциональное автоудаление осиротевших клиентов с панели
                if auto_delete:
                    deleted = 0
                    for orphan_email in list(clients_on_server.keys()):
                        try:
                            await xui_api.delete_client_on_host(host_name, orphan_email)
                            deleted += 1
                        except Exception as de:
                            logger.error(f"Scheduler: Failed to auto-delete orphan '{orphan_email}' on '{host_name}': {de}")
                    total_affected_records += deleted
                    logger.info(f"Scheduler: Auto-deleted {deleted} orphan clients on host '{host_name}'.")

        except Exception as e:
            logger.error(f"Scheduler: An unexpected error occurred while processing host '{host_name}': {e}", exc_info=True)
            
    if orphan_summary:
        summary_str = ", ".join([f"{hn}:{cnt}" for hn, cnt in orphan_summary])
        logger.warning(f"Scheduler: Orphan summary -> {summary_str}")
    logger.info(f"Scheduler: Sync with XUI panels finished. Total records affected: {total_affected_records}.")

async def periodic_subscription_check(bot_controller: BotController):
    logger.info("Scheduler has been started.")
    await asyncio.sleep(10)

    while True:
        try:
            # Обновляем статус ключей на основе реального времени истечения
            from shop_bot.data_manager.database import update_keys_status_by_expiry
            update_keys_status_by_expiry()
            
            await sync_keys_with_panels()

            if bot_controller.get_status().get("shop_bot_running"):
                bot = bot_controller.get_bot_instance()
                if bot:
                    await check_expiring_subscriptions(bot)
                    await perform_auto_renewals(bot)
                else:
                    logger.warning("Scheduler: Bot is marked as running, but instance is not available.")
            else:
                logger.info("Scheduler: Bot is stopped, skipping user notifications.")

        except Exception as e:
            logger.error(f"Scheduler: An unhandled error occurred in the main loop: {e}", exc_info=True)
            
        logger.info(f"Scheduler: Cycle finished. Next check in {CHECK_INTERVAL_SECONDS} seconds.")
        await asyncio.sleep(CHECK_INTERVAL_SECONDS)