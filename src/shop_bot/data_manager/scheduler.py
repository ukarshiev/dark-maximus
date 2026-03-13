# -*- coding: utf-8 -*-
"""
Планировщик задач для бота
"""

import asyncio
import logging
import os

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
from shop_bot.utils.datetime_utils import ensure_utc_datetime, format_datetime_for_user

CHECK_INTERVAL_SECONDS = 300
NOTIFY_BEFORE_HOURS = {24, 1}
MANUAL_NOTIFICATION_TEMPLATES: dict[str, dict] = {
    "subscription_expiry": {
        "code": "subscription_expiry",
        "name": "Окончание подписки",
        "description": "Стандартное напоминание об окончании подписки, когда тариф доступен и списание возможно.",
        "markers": [72, 48, 24, 1],
        "default_marker": 24,
        "supports_force": True,
        "conditions": {
            "require_plan_available": True,
            "require_balance_covers": False,
            "require_autorenew_enabled": False,
            "require_autorenew_disabled": False,
        },
    },
    "subscription_plan_unavailable": {
        "code": "subscription_plan_unavailable",
        "name": "Тариф недоступен",
        "description": "Предупреждение о том, что тариф снят с продажи и автопродление невозможно.",
        "markers": [72, 48, 24, 1],
        "default_marker": 24,
        "supports_force": True,
        "conditions": {
            "require_plan_available": False,
            "require_balance_covers": False,
            "require_autorenew_enabled": False,
            "require_autorenew_disabled": False,
        },
    },
    "subscription_autorenew_notice": {
        "code": "subscription_autorenew_notice",
        "name": "Автопродление с баланса",
        "description": "Сообщение о том, что автопродление выполнится автоматически при достаточном балансе.",
        "markers": [24, 1],
        "default_marker": 24,
        "supports_force": True,
        "conditions": {
            "require_plan_available": True,
            "require_balance_covers": True,
            "require_autorenew_enabled": True,
            "require_autorenew_disabled": False,
        },
    },
    "subscription_autorenew_disabled": {
        "code": "subscription_autorenew_disabled",
        "name": "Автопродление отключено",
        "description": "Уведомление о том, что баланс достаточен, но автопродление выключено.",
        "markers": [24, 1],
        "default_marker": 24,
        "supports_force": True,
        "conditions": {
            "require_plan_available": True,
            "require_balance_covers": True,
            "require_autorenew_enabled": False,
            "require_autorenew_disabled": True,
        },
    },
}
notified_users = {}

logger = logging.getLogger(__name__)

# Путь к лог-файлу удалённых orphan клиентов (только для ручного recovery; автоудаление отключено)
ORPHAN_DELETION_LOG = database.PROJECT_ROOT / "logs" / "orphan_deletions.log"

# Политика безопасности: удаление ключей из панели и БД отключено. Только логирование и репортинг.
SYNC_DELETION_DISABLED = True


def _format_datetime_for_user(user_id: int, dt_utc: datetime) -> str:
    """Возвращает строку даты/времени с учётом timezone пользователя"""
    feature_enabled = database.is_timezone_feature_enabled()
    user_timezone = database.get_user_timezone(user_id) if feature_enabled else None
    dt_prepared = ensure_utc_datetime(dt_utc if dt_utc.tzinfo else dt_utc.replace(tzinfo=timezone.utc))
    return format_datetime_for_user(dt_prepared, user_timezone=user_timezone, feature_enabled=feature_enabled)

def log_orphan_deletion(host_name: str, client_email: str, client_id: str, expiry_time: int):
    """Записывает информацию об удалённом orphan клиенте в лог-файл."""
    try:
        # Создаём директорию logs, если её нет
        os.makedirs(database.PROJECT_ROOT / "logs", exist_ok=True)
        
        # Форматируем дату истечения
        if expiry_time > 0:
            expiry_dt = datetime.fromtimestamp(expiry_time / 1000)
            expiry_str = expiry_dt.strftime('%Y-%m-%d %H:%M:%S')
        else:
            expiry_str = "Без срока"
        
        # Текущая дата и время (UTC для консистентности)
        now_str = datetime.now(timezone.utc).replace(tzinfo=None).strftime('%Y-%m-%d %H:%M:%S')
        
        # Формируем запись
        log_entry = {
            'timestamp': now_str,
            'host_name': host_name,
            'client_email': client_email,
            'client_id': client_id,
            'expiry_time': expiry_str
        }
        
        # Записываем в файл
        with open(ORPHAN_DELETION_LOG, 'a', encoding='utf-8') as f:
            f.write(json.dumps(log_entry, ensure_ascii=False) + '\n')
            
    except Exception as e:
        logger.error(f"Failed to log orphan deletion: {e}")


def _format_marker_label(hours: int) -> str:
    """Возвращает текстовую метку для значения marker_hours."""
    if hours <= 0:
        return "менее часа"
    if hours % 24 == 0 and hours >= 24:
        days = hours // 24
        if days == 1:
            return "через 1 день"
        if days in (2, 3, 4):
            return f"через {days} дня"
        return f"через {days} дней"
    if hours == 1:
        return "через 1 час"
    if hours in (2, 3, 4):
        return f"через {hours} часа"
    return f"через {hours} часов"


def get_manual_notification_templates() -> list[dict]:
    """Возвращает список шаблонов уведомлений для панели."""
    templates: list[dict] = []
    for template in MANUAL_NOTIFICATION_TEMPLATES.values():
        markers = [
            {
                "hours": hours,
                "label": _format_marker_label(hours),
            }
            for hours in template.get("markers", [])
        ]
        templates.append(
            {
                "code": template["code"],
                "name": template["name"],
                "description": template["description"],
                "markers": markers,
                "default_marker": template.get("default_marker"),
                "supports_force": template.get("supports_force", False),
                "conditions": template.get("conditions", {}),
            }
        )
    return templates


def get_manual_notification_template(code: str) -> dict | None:
    """Возвращает шаблон уведомления по коду."""
    return MANUAL_NOTIFICATION_TEMPLATES.get(code)

def format_time_left(hours: int) -> str:
    """Форматирует оставшееся время в читаемый формат.
    
    Args:
        hours: Количество часов (может быть 0 для ключей с остатком < 1 часа)
    
    Returns:
        Строка с отформатированным временем
    """
    # Если часов 0 или меньше, показываем "менее часа"
    if hours <= 0:
        return "менее часа"
    
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

async def send_subscription_notification(
    bot: Bot,
    user_id: int,
    key_id: int,
    time_left_hours: int,
    expiry_date: datetime,
    status: str = 'sent',
):
    try:
        # Дополнительная проверка: не отправляем уведомления, если время истекло
        # Используем UTC для сравнения, т.к. expiry_date хранится в UTC
        current_time_utc = datetime.now(timezone.utc).replace(tzinfo=None)
        if expiry_date <= current_time_utc:
            logger.warning(f"Attempted to send expiry notification for already expired key {key_id} (user {user_id}). Skipping.")
            return
        
        # Проверяем, что time_left_hours соответствует реальному времени до истечения
        actual_time_left = expiry_date - current_time_utc
        actual_hours_left = int(actual_time_left.total_seconds() / 3600)
        # Исправлено: проверяем секунды, а не часы, чтобы разрешить уведомления для ключей с остатком < 1 часа
        if time_left_hours <= 0 or actual_time_left.total_seconds() <= 0:
            logger.warning(f"Invalid time_left_hours ({time_left_hours}) or actual_time_left ({actual_time_left.total_seconds():.0f}s) for key {key_id}. Skipping notification.")
            return
        
        time_text = format_time_left(time_left_hours)
        expiry_str = _format_datetime_for_user(user_id, expiry_date)

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

        if time_left_hours == 1:
            expiry_line = f"Срок действия вашего ключа {key_descriptor} истекает в течение 1 часа.\n"
        else:
            expiry_line = f"Срок действия вашего ключа {key_descriptor} истекает через **{time_text}**.\n"

        message = (
            f"⚠️ **Внимание!** ⚠️\n\n"
            f"{expiry_line}"
            f"📅 Дата окончания: **{expiry_str}**\n"
            f"💰 Ваш баланс : **{balance_str}**\n\n"
            f"Пополните счет, чтобы произошло автоматическое списание с баланса или продлите подписку прямо сейчас, чтобы не остаться без доступа к VPN!"
        )

        builder = InlineKeyboardBuilder()
        builder.button(text="🔄 Продлить ключ", callback_data=f"extend_key_{key_id}")
        builder.button(text="💰 Пополнить баланс", callback_data="topup_root")
        builder.adjust(2)

        # Сначала логируем уведомление в БД, чтобы предотвратить дублирование
        try:
            from shop_bot.data_manager.database import log_notification, get_user
            user = get_user(user_id)
            notification_id = log_notification(
                user_id=user_id,
                username=(user or {}).get('username'),
                notif_type='subscription_expiry',
                title=f'Окончание подписки (через {time_text})',
                message=message,
                status=status,
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
            # Проверяем, что логирование прошло успешно (возвращает ID > 0)
            if notification_id == 0:
                logger.warning(f"Failed to log notification for user {user_id}: log_notification returned 0")
                return  # Не отправляем сообщение, если не удалось записать в БД
        except Exception as le:
            logger.warning(f"Failed to log notification for user {user_id}: {le}")
            return  # Не отправляем сообщение, если не удалось записать в БД

        # Теперь отправляем сообщение
        await bot.send_message(chat_id=user_id, text=message, reply_markup=builder.as_markup(), parse_mode='Markdown')
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
        from shop_bot.data_manager.database import _get_db_connection
        import sqlite3
        with _get_db_connection() as conn:
            cursor = conn.cursor()
            # Устанавливаем PRAGMA настройки для предотвращения блокировок
            try:
                cursor.execute("PRAGMA busy_timeout=30000")
                cursor.execute("PRAGMA journal_mode=DELETE")
            except Exception:
                pass
            
            # БЕЗОПАСНАЯ ПРОВЕРКА: существует ли колонка key_id
            cursor.execute("PRAGMA table_info(notifications)")
            columns = [row[1] for row in cursor.fetchall()]
            if 'key_id' not in columns or 'marker_hours' not in columns:
                logger.debug("Column 'key_id' or 'marker_hours' does not exist in notifications table. Returning False.")
                return False
            
            cursor.execute(
                "SELECT 1 FROM notifications WHERE user_id = ? AND key_id = ? AND marker_hours = ? AND type = ? LIMIT 1",
                (user_id, key_id, marker_hours, notif_type)
            )
            return cursor.fetchone() is not None
    except Exception:
        return False

def cleanup_duplicate_notifications():
    """Очищает дублирующиеся уведомления в базе данных."""
    try:
        from shop_bot.data_manager.database import _get_db_connection
        import sqlite3
        from datetime import datetime, timedelta
        
        with _get_db_connection() as conn:
            cursor = conn.cursor()
            
            # Устанавливаем PRAGMA настройки для предотвращения блокировок
            try:
                cursor.execute("PRAGMA busy_timeout=30000")
                cursor.execute("PRAGMA journal_mode=DELETE")
            except Exception:
                pass
            
            # БЕЗОПАСНАЯ ПРОВЕРКА: существуют ли колонки key_id и marker_hours
            cursor.execute("PRAGMA table_info(notifications)")
            columns = [row[1] for row in cursor.fetchall()]
            has_key_id = 'key_id' in columns
            has_marker_hours = 'marker_hours' in columns
            
            # Очистка дубликатов только если обе колонки существуют
            if has_key_id and has_marker_hours:
                cursor.execute("""
                    DELETE FROM notifications 
                    WHERE notification_id NOT IN (
                        SELECT MAX(notification_id) 
                        FROM notifications 
                        WHERE type = 'subscription_plan_unavailable'
                        GROUP BY user_id, key_id, marker_hours
                    ) AND type = 'subscription_plan_unavailable'
                """)
                
                deleted_count = cursor.rowcount
                if deleted_count > 0:
                    logger.info(f"Cleaned up {deleted_count} duplicate plan unavailable notifications")
            else:
                logger.warning("Columns 'key_id' or 'marker_hours' do not exist in notifications table. Skipping duplicate cleanup.")
            
            # Удаляем уведомления старше 7 дней (используем UTC для консистентности)
            # Эта часть работает даже без key_id и marker_hours
            week_ago = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=7)
            cursor.execute("""
                DELETE FROM notifications 
                WHERE created_date < ? AND type IN ('subscription_plan_unavailable', 'subscription_expiry', 'subscription_autorenew_notice', 'subscription_autorenew_disabled')
            """, (week_ago,))
            
            old_deleted = cursor.rowcount
            if old_deleted > 0:
                logger.info(f"Cleaned up {old_deleted} old notifications (older than 7 days)")
            
            conn.commit()
            
    except Exception as e:
        logger.error(f"Failed to cleanup duplicate notifications: {e}")

async def send_plan_unavailable_notice(
    bot: Bot,
    user_id: int,
    key_id: int,
    time_left_hours: int,
    expiry_date: datetime,
    force: bool = False,
    status: str = 'sent',
):
    """Уведомление о недоступности тарифа для автопродления."""
    try:
        # ДОПОЛНИТЕЛЬНАЯ ЗАЩИТА ОТ СПАМА: проверяем, не было ли уже отправлено уведомление
        if not force and _marker_logged(user_id, key_id, time_left_hours, 'subscription_plan_unavailable'):
            logger.debug(f"Plan unavailable notice already sent for user {user_id}, key {key_id}, marker {time_left_hours}h. Skipping.")
            return
        
        # Проверяем, что время не истекло
        current_time_utc = datetime.now(timezone.utc).replace(tzinfo=None)
        if expiry_date <= current_time_utc:
            logger.warning(f"Attempted to send plan unavailable notice for already expired key {key_id} (user {user_id}). Skipping.")
            return
        
        time_text = format_time_left(time_left_hours)
        expiry_str = _format_datetime_for_user(user_id, expiry_date)

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

        key_label = f"#{key_number}" if key_number > 0 else f"ID {key_id}"

        message = (
            "⚠️ Внимание! ⚠️\n\n"
            "Ваш тариф больше не доступен для автопродления.\n\n"
            f"Ключ {key_label} ({host_name}) истекает через {time_text}.\n\n"
            f"📅 Окончание: {expiry_str}\n\n"
            "Пожалуйста, выберите новый тариф до истечения срока.\n\n"
            "Для продления перейдите в меню: 🛒 Купить → 🔄 Продлить ключ и выберите другой тариф"
        )

        keyboard_builder = InlineKeyboardBuilder()
        keyboard_builder.button(text="🛒 Купить новый VPN", callback_data="buy_new_vpn")
        keyboard_builder.button(text="🔄 Продлить VPN", callback_data=f"extend_key_{key_id}")
        keyboard_builder.button(text="🔑 Перейти к ключу", callback_data=f"show_key_{key_id}")
        keyboard_builder.button(text="⬅️ Назад в меню", callback_data="back_to_main_menu")
        keyboard_builder.adjust(2, 1, 1)

        # Сначала логируем уведомление в БД, чтобы предотвратить дублирование
        try:
            from shop_bot.data_manager.database import log_notification, get_user
            user = get_user(user_id)
            notification_id = log_notification(
                user_id=user_id,
                username=(user or {}).get('username'),
                notif_type='subscription_plan_unavailable',
                title=f'Тариф недоступен (через {time_text})',
                message=message,
                status=status if status else 'sent',
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
            # Проверяем, что логирование прошло успешно (возвращает ID > 0)
            if notification_id == 0:
                logger.warning(f"Failed to log plan unavailable notification: log_notification returned 0")
                return  # Не отправляем сообщение, если не удалось записать в БД
        except Exception as e:
            logger.warning(f"Failed to log plan unavailable notification: {e}")
            return  # Не отправляем сообщение, если не удалось записать в БД

        # Теперь отправляем сообщение
        await bot.send_message(
            chat_id=user_id,
            text=message,
            reply_markup=keyboard_builder.as_markup()
        )

        logger.info(f"Sent plan unavailable notice to user {user_id} for key {key_id}, time_left={time_left_hours}h")
    except Exception as e:
        logger.error(f"Failed to send plan unavailable notice to user {user_id} for key {key_id}: {e}", exc_info=True)


async def send_autorenew_balance_notice(
    bot: Bot,
    user_id: int,
    key_id: int,
    time_left_hours: int,
    expiry_date: datetime,
    balance_val: float,
    status: str = 'sent',
):
    try:
        from datetime import timezone, timedelta
        from shop_bot.data_manager.database import get_key_auto_renewal_enabled
        # Проверяем, включено ли автопродление для ключа
        if not get_key_auto_renewal_enabled(key_id):
            logger.debug(f"Skipping autorenew balance notice for key {key_id}: key auto-renewal is disabled")
            return
        # Дополнительная проверка: не отправляем уведомления, если время истекло
        # Используем UTC для сравнения, т.к. expiry_date хранится в UTC
        current_time_utc = datetime.now(timezone.utc).replace(tzinfo=None)
        if expiry_date <= current_time_utc:
            logger.warning(f"Attempted to send autorenew notice for already expired key {key_id} (user {user_id}). Skipping.")
            return
        
        # Проверяем, что time_left_hours соответствует реальному времени до истечения
        actual_time_left = expiry_date - current_time_utc
        actual_hours_left = int(actual_time_left.total_seconds() / 3600)
        # Исправлено: проверяем секунды, а не часы, чтобы разрешить уведомления для ключей с остатком < 1 часа
        if time_left_hours <= 0 or actual_time_left.total_seconds() <= 0:
            logger.warning(f"Invalid time_left_hours ({time_left_hours}) or actual_time_left ({actual_time_left.total_seconds():.0f}s) for autorenew notice key {key_id}. Skipping notification.")
            return
        
        time_text = format_time_left(time_left_hours)
        expiry_str = _format_datetime_for_user(user_id, expiry_date)
        expiry_date_only = expiry_str.split(' в ')[0] if ' в ' in expiry_str else expiry_str

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

        time_phrase = "в течении" if time_left_hours == 1 else "через"
        time_text_for_message = "1 часа" if time_left_hours == 1 else time_text

        key_label = f"#{key_number}" if key_number > 0 else f"ID {key_id}"

        message = (
            "❕ Информация о ключе ❔\n\n"
            f"Срок действия ключа #{key_number} ({host_name}) истекает {time_phrase} {time_text_for_message}.\n"
            f"📅 Окончание: {expiry_str}\n"
            f"💰 Баланс: {balance_str}\n\n"
            f"🔄 Если \"Автопродление с баланса\" включено, то услуга продлится автоматически, сумма {price_str} будет списана с вашего баланса.\n\n"
            "❤️ Спасибо, что остаётесь с нами!"
        )

        keyboard_builder = InlineKeyboardBuilder()
        keyboard_builder.button(
            text=f"🔑 Ключ {key_label} ({host_name}) до {expiry_date_only}",
            callback_data=f"show_key_{key_id}"
        )
        keyboard_builder.button(text="⬅️ Назад в меню", callback_data="back_to_main_menu")
        keyboard_builder.adjust(1)

        # Сначала логируем уведомление в БД, чтобы предотвратить дублирование
        try:
            from shop_bot.data_manager.database import log_notification, get_user
            user = get_user(user_id)
            notification_id = log_notification(
                user_id=user_id,
                username=(user or {}).get('username'),
                notif_type='subscription_autorenew_notice',
                title=f'Автопродление (через {time_text})',
                message=message,
                status=status,
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
            # Проверяем, что логирование прошло успешно (возвращает ID > 0)
            if notification_id == 0:
                logger.warning(f"Failed to log autorenew notice for user {user_id}: log_notification returned 0")
                return  # Не отправляем сообщение, если не удалось записать в БД
        except Exception as le:
            logger.warning(f"Failed to log autorenew notice for user {user_id}: {le}")
            return  # Не отправляем сообщение, если не удалось записать в БД

        # Теперь отправляем сообщение
        await bot.send_message(
            chat_id=user_id,
            text=message,
            reply_markup=keyboard_builder.as_markup()
        )
        logger.info(f"Sent autorenew balance notice to user {user_id} for key {key_id} ({time_left_hours} hours left).")
    except Exception as e:
        logger.error(f"Error sending autorenew notice to user {user_id}: {e}")

async def send_balance_deduction_notice(bot: Bot, user_id: int, key_id: int, amount: float, plan_name: str, host_name: str):
    """Отправляет уведомление о списании баланса при автопродлении."""
    try:
        from shop_bot.data_manager.database import get_user_keys
        
        # Получаем номер ключа для пользователя
        user_keys = get_user_keys(user_id) or []
        key_number = next((i + 1 for i, k in enumerate(user_keys) if k.get('key_id') == key_id), 0)
        
        key_label = f"#{key_number}" if key_number > 0 else f"ID {key_id}"

        message = (
            f"💳 Произошло списание {amount:.2f} RUB\n\n"
            f"✅ Тип операции: автопродление с баланса\n\n"
            f"🔑 Ключ {key_label}. {host_name} - {plan_name}\n\n"
            f"Спасибо, что остаётесь с нами! ❤️"
        )
        
        # Создаем клавиатуру с кнопками "Перейти к ключу" и "Назад в меню"
        builder = InlineKeyboardBuilder()
        builder.button(text="🔑 Перейти к ключу", callback_data=f"show_key_{key_id}")
        builder.button(text="⬅️ Назад в меню", callback_data="back_to_main_menu")
        builder.adjust(1)  # По одной кнопке в ряд
        
        await bot.send_message(
            chat_id=user_id,
            text=message,
            reply_markup=builder.as_markup()
        )
        logger.info(f"Sent balance deduction notice to user {user_id} for key {key_id}")
    except Exception as e:
        logger.error(f"Failed to send balance deduction notice to user {user_id}: {e}")

async def send_autorenew_disabled_notice(
    bot: Bot,
    user_id: int,
    key_id: int,
    time_left_hours: int,
    expiry_date: datetime,
    balance_val: float,
    price_to_renew: float,
    status: str = 'sent',
):
    """Отправляет уведомление о том, что автопродление отключено, но баланс достаточен."""
    try:
        from shop_bot.bot import keyboards
        from shop_bot.data_manager.database import get_user_keys, get_key_by_id, get_key_auto_renewal_enabled, get_auto_renewal_enabled
        
        # Проверяем, что время не истекло
        current_time_utc = datetime.now(timezone.utc).replace(tzinfo=None)
        if expiry_date <= current_time_utc:
            logger.warning(f"Attempted to send autorenew disabled notice for already expired key {key_id} (user {user_id}). Skipping.")
            return
        
        # Проверяем статус автопродления: если оба включены, не отправляем это уведомление
        if get_auto_renewal_enabled(user_id) and get_key_auto_renewal_enabled(key_id):
            logger.debug(f"Skipping autorenew disabled notice for key {key_id}: both global and key auto-renewal are enabled")
            return
        
        time_text = format_time_left(time_left_hours)
        expiry_str = _format_datetime_for_user(user_id, expiry_date)

        # Получаем номер ключа и имя сервера
        try:
            key_data = get_key_by_id(key_id) or {}
            host_name = key_data.get('host_name', 'Неизвестный сервер')
            user_keys = get_user_keys(user_id) or []
            key_number = next((i + 1 for i, k in enumerate(user_keys) if k.get('key_id') == key_id), 0)
        except Exception:
            host_name = 'Неизвестный сервер'
            key_number = 0

        balance_str = f"{float(balance_val or 0):.2f} RUB"
        price_str = f"{float(price_to_renew or 0):.2f} RUB"

        message = (
            f"⚠️ Автопродление с баланса отключено.\n\n"
            f"Ключ #{key_number} ({host_name}) истекает через {time_text}.\n"
            f"📅 Окончание: {expiry_str}\n"
            f"💰 Ваш баланс: {balance_str}\n"
            f"💳 Сумма продления: {price_str}\n\n"
            f"Ваш баланс достаточен для продления, но списание не произойдет автоматически.\n"
            f"Включите автопродление в профиле, чтобы не остаться без доступа."
        )

        builder = InlineKeyboardBuilder()
        builder.button(text="⚙️ Настройки профиля", callback_data="show_profile")
        builder.button(text="🔄 Продлить ключ", callback_data=f"extend_key_{key_id}")
        builder.adjust(1)

        # Сначала логируем уведомление, чтобы избежать повторной отправки
        try:
            from shop_bot.data_manager.database import log_notification, get_user
            user = get_user(user_id)
            notification_id = log_notification(
                user_id=user_id,
                username=(user or {}).get('username'),
                notif_type='subscription_autorenew_disabled',
                title=f'Автопродление отключено (через {time_text})',
                message=message,
                status=status,
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
            if notification_id == 0:
                logger.warning(f"Failed to log autorenew disabled notice for user {user_id}: log_notification returned 0")
                return
        except Exception as le:
            logger.warning(f"Failed to log autorenew disabled notice for user {user_id}: {le}")
            return

        await bot.send_message(
            chat_id=user_id,
            text=message,
            reply_markup=builder.as_markup()
        )
        logger.info(f"Sent autorenew disabled notice to user {user_id} for key {key_id} ({time_left_hours} hours left).")
    except Exception as e:
        logger.error(f"Failed to send autorenew disabled notice to user {user_id}: {e}")

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
            total_seconds_left = int(time_left.total_seconds())
            user_id = key['user_id']
            key_id = key['key_id']

            # Цена и длительность для продления, баланс пользователя, доступность тарифа
            plan_info, price_to_renew, months_to_renew, plan_id, is_plan_available = _get_plan_info_for_key(key)
            from shop_bot.data_manager.database import get_user_balance
            user_balance = float(get_user_balance(user_id) or 0.0)

            # Логируем информацию о ключе для отладки (только для ключей с остатком < 2 часов)
            if total_seconds_left < 7200:  # Меньше 2 часов
                logger.info(f"Key {key_id} (user {user_id}): {total_seconds_left}s left ({total_hours_left}h), balance={user_balance}, price={price_to_renew}, plan_available={is_plan_available}")

            # Catch-up: решаем, что отправлять на каждом маркере
            # Важно: не отправляем уведомления, если ключ уже истек
            # Проверяем по секундам, а не по целым часам, чтобы обрабатывать ключи с оставшимся временем < 1 часа
            if time_left.total_seconds() > 0:
                # Ищем наименьший подходящий маркер (сортируем по возрастанию: 1, 24, 48, 72)
                for hours_mark in sorted(NOTIFY_BEFORE_HOURS):
                    # Проверяем, что осталось времени меньше или равно маркеру (в секундах)
                    # Для маркера 1 час: осталось <= 3600 секунд (1 час)
                    # Для маркера 24 часа: осталось <= 86400 секунд (24 часа)
                    mark_seconds = hours_mark * 3600
                    if total_seconds_left <= mark_seconds:
                        # Проверяем доступность тарифа для автопродления
                        if not is_plan_available:
                            # Тариф удален или скрыт - отправляем предупреждение
                            if not _marker_logged(user_id, key_id, hours_mark, 'subscription_plan_unavailable'):
                                try:
                                    await send_plan_unavailable_notice(bot, user_id, key_id, hours_mark, expiry_date)
                                    notified_users.setdefault(user_id, {}).setdefault(key_id, set()).add(hours_mark)
                                    logger.info(f"Sent plan unavailable notice for user {user_id}, key {key_id}, marker {hours_mark}h")
                                except Exception as e:
                                    logger.error(f"Failed to send plan unavailable notice: {e}")
                            break  # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: выходим из цикла после проверки недоступности тарифа
                        
                        balance_covers = price_to_renew > 0 and user_balance >= price_to_renew
                        if balance_covers:
                            # Проверяем статус автопродления
                            from shop_bot.data_manager.database import get_auto_renewal_enabled, get_key_auto_renewal_enabled
                            auto_renewal_enabled = get_auto_renewal_enabled(user_id)
                            key_auto_renewal_enabled = get_key_auto_renewal_enabled(key_id)
                            
                            # Логируем для отладки
                            if total_seconds_left < 7200:  # Меньше 2 часов
                                logger.info(f"Key {key_id}: balance_covers={balance_covers}, auto_renewal_enabled={auto_renewal_enabled}, key_auto_renewal_enabled={key_auto_renewal_enabled}, hours_mark={hours_mark}, marker_logged={_marker_logged(user_id, key_id, hours_mark, 'subscription_autorenew_notice')}")
                            
                            # Проверяем, включено ли автопродление для пользователя и ключа
                            if auto_renewal_enabled and key_auto_renewal_enabled:
                                # Подавляем стандартные уведомления. На 24ч и 1ч — отправляем новый тип, один раз.
                                if hours_mark in (24, 1) and not _marker_logged(user_id, key_id, hours_mark, 'subscription_autorenew_notice'):
                                    try:
                                        await send_autorenew_balance_notice(bot, user_id, key_id, hours_mark, expiry_date, user_balance)
                                        notified_users.setdefault(user_id, {}).setdefault(key_id, set()).add(hours_mark)
                                        logger.info(f"Sent autorenew notice for user {user_id}, key {key_id}, marker {hours_mark}h")
                                    except Exception as e:
                                        logger.error(f"Failed to send autorenew notice: {e}")
                                break  # ВАЖНО: выходим из цикла после проверки автопродления
                            else:
                                # Автопродление отключено (глобально или для ключа), но баланс достаточен - отправляем специальное уведомление
                                if not _marker_logged(user_id, key_id, hours_mark, 'subscription_autorenew_disabled'):
                                    try:
                                        await send_autorenew_disabled_notice(bot, user_id, key_id, hours_mark, expiry_date, user_balance, price_to_renew)
                                        notified_users.setdefault(user_id, {}).setdefault(key_id, set()).add(hours_mark)
                                        logger.info(f"Sent autorenew disabled notice for user {user_id}, key {key_id}, marker {hours_mark}h")
                                    except Exception as e:
                                        logger.error(f"Failed to send autorenew disabled notice: {e}")
                                break  # ВАЖНО: выходим из цикла после отправки уведомления об отключенном автопродлении
                        else:
                            # Обычные уведомления
                            if not _marker_logged(user_id, key_id, hours_mark, 'subscription_expiry'):
                                try:
                                    await send_subscription_notification(bot, user_id, key_id, hours_mark, expiry_date)
                                    notified_users.setdefault(user_id, {}).setdefault(key_id, set()).add(hours_mark)
                                    logger.info(f"Sent subscription expiry notice for user {user_id}, key {key_id}, marker {hours_mark}h")
                                except Exception as e:
                                    logger.error(f"Failed to send subscription expiry notice: {e}")
                            break  # ВАЖНО: выходим из цикла после отправки обычного уведомления
            else:
                # Ключ уже истек - не отправляем уведомления об истечении
                logger.debug(f"Key {key_id} for user {user_id} has already expired ({int(time_left.total_seconds())} seconds left). Skipping notifications.")

        except KeyError as e:
            logger.error(f"Missing key data for processing expiry: {e}")
        except ValueError as e:
            logger.error(f"Invalid data format for key {key.get('key_id')}: {e}")
        except Exception as e:
            logger.error(f"Unexpected error processing expiry for key {key.get('key_id')}: {e}", exc_info=True)

async def perform_auto_renewals(bot: Bot):
    """Автопродление по истечении срока при достаточном балансе."""
    try:
        all_keys = database.get_all_keys()
        # Используем UTC для консистентности с данными в БД
        now = datetime.now(timezone.utc).replace(tzinfo=None)
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
            # Исправлено: проверяем не только месяцы, но и дни/часы для тарифов с months=0
            plan_has_duration = False
            if plan_info:
                months = plan_info.get('months', 0) or 0
                days = plan_info.get('days', 0) or 0
                hours = plan_info.get('hours', 0) or 0
                plan_has_duration = months > 0 or days > 0 or hours > 0
            
            if not plan_info or not plan_has_duration or not plan_id or price_to_renew <= 0 or not is_plan_available:
                if not plan_has_duration:
                    logger.debug(f"Auto-renewal skipped for key {key_id}: plan has no valid duration (months={plan_info.get('months', 0) if plan_info else 0}, days={plan_info.get('days', 0) if plan_info else 0}, hours={plan_info.get('hours', 0) if plan_info else 0})")
                continue

            from shop_bot.data_manager.database import get_user_balance, add_to_user_balance, log_transaction, get_user, get_key_by_id
            current_balance = float(get_user_balance(user_id) or 0.0)
            if current_balance < price_to_renew:
                continue

            # Проверяем, включено ли автопродление для пользователя
            from shop_bot.data_manager.database import get_auto_renewal_enabled, get_key_auto_renewal_enabled
            if not get_auto_renewal_enabled(user_id):
                logger.info(f"Auto-renewal skipped for user {user_id}, key {key_id}: global auto-renewal is disabled")
                continue

            # Проверяем, включено ли автопродление для конкретного ключа
            if not get_key_auto_renewal_enabled(key_id):
                logger.info(f"Auto-renewal skipped for user {user_id}, key {key_id}: key auto-renewal is disabled")
                continue

            # Сохраняем старое expiry_date для проверки на дублирование
            old_expiry_date = expiry_date

            # Получаем название тарифа для уведомления
            plan_name = plan_info.get('plan_name', key.get('plan_name', 'Неизвестный тариф'))

            # Метаданные платежа
            payment_id = str(uuid.uuid4())
            # Для тарифов с months=0 используем days и hours из plan_info
            plan_months = plan_info.get('months', 0) or 0
            plan_days = plan_info.get('days', 0) or 0
            plan_hours = plan_info.get('hours', 0) or 0
            metadata = {
                'user_id': user_id,
                'months': int(plan_months),
                'days': int(plan_days),
                'hours': int(plan_hours),
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
                
                # Проверяем, что ключ действительно был продлен (защита от дублирования)
                updated_key = get_key_by_id(key_id)
                if updated_key:
                    new_expiry_date = datetime.fromisoformat(updated_key['expiry_date'])
                    if new_expiry_date.tzinfo is not None:
                        new_expiry_date = new_expiry_date.replace(tzinfo=None)
                    
                    # Если expiry_date изменился, значит продление прошло успешно
                    if new_expiry_date > old_expiry_date:
                        # Отправляем уведомление о списании
                        await send_balance_deduction_notice(bot, user_id, key_id, price_to_renew, plan_name, host_name)
                        logger.info(f"Auto-renewal completed for user {user_id}, key {key_id} on host '{host_name}'. Deduction notice sent.")
                    else:
                        logger.warning(f"Auto-renewal: expiry_date did not change for key {key_id}. Possible duplicate renewal attempt.")
                else:
                    logger.warning(f"Auto-renewal: could not retrieve updated key {key_id} after renewal.")
            except ValueError as e:
                logger.error(f"Invalid data for auto-renewal user {user_id}, key {key_id}: {e}")
            except KeyError as e:
                logger.error(f"Missing required data for auto-renewal user {user_id}, key {key_id}: {e}")
            except Exception as e:
                logger.error(f"Auto-renewal failed for user {user_id}, key {key_id}: {e}", exc_info=True)
    except Exception as e:
        logger.error(f"perform_auto_renewals: fatal error: {e}")

async def sync_keys_with_panels():
    """Синхронизация данных ключей с панелями 3x-ui. Удаление ключей отключено политикой безопасности."""
    logger.info("Scheduler: Starting sync with XUI panels...")
    if SYNC_DELETION_DISABLED:
        logger.info("Scheduler: Deletion of keys from panel and DB is disabled by security policy; only read/update sync.")
    total_affected_records = 0

    all_hosts = database.get_all_hosts()
    if not all_hosts:
        logger.info("Scheduler: No hosts configured in the database. Sync skipped.")
        return

    orphan_summary: list[tuple[str, int]] = []
    orphan_summary_with_errors: list[tuple[str, int]] = []

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
                logger.warning(f"Scheduler: Could not log in to host '{host_name}'. Skipping this host. This may be a temporary network issue.")
                continue
            bound_inbound_id = host.get('host_inbound_id')
            panel_inbound_id = getattr(inbound, 'id', bound_inbound_id)
            logger.info(
                f"Scheduler: Using bound inbound only for host '{host_name}' "
                f"(host_inbound_id={bound_inbound_id}, panel_inbound_id={panel_inbound_id})."
            )
            full_inbound_details = api.inbound.get_by_id(inbound.id)
            clients_on_server = {client.email: client for client in (full_inbound_details.settings.clients or [])}
            logger.info(f"Scheduler: Found {len(clients_on_server)} clients on the '{host_name}' panel (inbound id={panel_inbound_id}).")

            keys_in_db = database.get_keys_for_host(host_name)
            
            for db_key in keys_in_db:
                key_email = db_key['key_email']
                expiry_date = datetime.fromisoformat(db_key['expiry_date'])
                # Убираем timezone info для совместимости
                if expiry_date.tzinfo is not None:
                    expiry_date = expiry_date.replace(tzinfo=None)
                # Используем UTC для консистентности с данными в БД
                now = datetime.now(timezone.utc).replace(tzinfo=None)
                if expiry_date < now - timedelta(days=5):
                    logger.info(
                        f"Scheduler: Key '{key_email}' expired more than 5 days ago "
                        "(deletion disabled by policy; key kept in DB and panel)."
                    )
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
                    logger.warning(
                        f"Scheduler: Key '{key_email}' for host '{host_name}' not found on server "
                        "(deletion disabled by policy; key kept in DB)."
                    )

            if clients_on_server:
                count_orphans = len(clients_on_server)
                orphan_summary.append((host_name, count_orphans))

                # Логируем информацию о orphan clients
                orphan_ids = [str(getattr(client, "id", "unknown")) for client in clients_on_server.values()]
                max_display_ids = 5
                shown_ids = ", ".join(orphan_ids[:max_display_ids])
                if len(orphan_ids) > max_display_ids:
                    shown_ids += ", ..."
                logger.warning(
                    f"Scheduler: Found {count_orphans} orphan client(s) on host '{host_name}'"
                    + (f" (ID(s): {shown_ids})" if shown_ids else "")
                )
                
                # Логируем первые 5 orphan clients для диагностики
                sample_orphans = list(clients_on_server.items())[:5]
                for orphan_email, orphan_client in sample_orphans:
                    logger.info(f"Scheduler: Orphan client - Email: {orphan_email}, ID: {orphan_client.id}, Expiry: {orphan_client.expiry_time}")
                
                if count_orphans > 5:
                    logger.info(f"Scheduler: ... and {count_orphans - 5} more orphan client(s)")
                logger.info(
                    f"Scheduler: Orphan client(s) on '{host_name}' will NOT be deleted (deletion disabled by security policy)."
                )
                orphan_summary_with_errors.append((host_name, count_orphans))

        except ConnectionError as e:
            logger.warning(f"Scheduler: Connection error while processing host '{host_name}': {e}. This may be a temporary network issue.")
        except TimeoutError as e:
            logger.warning(f"Scheduler: Timeout error while processing host '{host_name}': {e}. This may be a temporary network issue.")
        except ValueError as e:
            logger.error(f"Scheduler: Invalid data while processing host '{host_name}': {e}")
        except Exception as e:
            logger.error(f"Scheduler: An unexpected error occurred while processing host '{host_name}': {e}", exc_info=True)
            
    # Выводим предупреждение только если автоудаление выключено или были ошибки
    if orphan_summary_with_errors:
        summary_str = ", ".join([f"{hn}:{cnt}" for hn, cnt in orphan_summary_with_errors])
        logger.warning(f"Scheduler: Orphan summary -> {summary_str}")
    logger.info(f"Scheduler: Sync with XUI panels finished. Total records affected: {total_affected_records}.")

async def periodic_subscription_check(bot_controller: BotController):
    logger.info("Scheduler has been started.")
    await asyncio.sleep(10)
    
    # Счетчик циклов для периодической очистки webhook'ов (раз в день)
    webhook_cleanup_counter = 0
    WEBHOOK_CLEANUP_INTERVAL = 288  # 288 циклов * 300 сек = 24 часа
    
    # Счетчик циклов для периодической очистки токенов (раз в день)
    token_cleanup_counter = 0
    TOKEN_CLEANUP_INTERVAL = 288  # 288 циклов * 300 сек = 24 часа

    while True:
        try:
            # Очищаем дублирующиеся уведомления (раз в цикл)
            cleanup_duplicate_notifications()
            
            # Обновляем статус ключей на основе реального времени истечения
            from shop_bot.data_manager.database import update_keys_status_by_expiry
            update_keys_status_by_expiry()
            
            await sync_keys_with_panels()
            
            # Периодическая очистка старых webhook'ов (раз в день)
            webhook_cleanup_counter += 1
            if webhook_cleanup_counter >= WEBHOOK_CLEANUP_INTERVAL:
                try:
                    from shop_bot.data_manager.database import cleanup_old_webhooks
                    deleted_count = cleanup_old_webhooks(days_to_keep=90)
                    if deleted_count > 0:
                        logger.info(f"Scheduler: Cleaned up {deleted_count} old webhook records")
                    webhook_cleanup_counter = 0
                except Exception as cleanup_error:
                    logger.error(f"Scheduler: Failed to cleanup old webhooks: {cleanup_error}", exc_info=True)
            
            # Периодическая очистка токенов истекших подписок (раз в день)
            token_cleanup_counter += 1
            if token_cleanup_counter >= TOKEN_CLEANUP_INTERVAL:
                logger.debug("Scheduler: Token cleanup skipped (persistent cabinet links enabled)")
                token_cleanup_counter = 0

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