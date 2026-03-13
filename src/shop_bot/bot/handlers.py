# -*- coding: utf-8 -*-
"""
Обработчики команд и сообщений для Telegram-бота
"""

import logging
import uuid
import qrcode
import aiohttp
import re
import hashlib
import json
import base64
import asyncio
import sqlite3
import time

from urllib.parse import urlencode
from hmac import compare_digest
from functools import wraps
from yookassa import Payment
from io import BytesIO
from datetime import datetime, timedelta, timezone
from aiosend import CryptoPay, TESTNET
from decimal import Decimal, ROUND_HALF_UP, ROUND_CEILING
from typing import Dict, Tuple

from pytonconnect import TonConnect
from pytonconnect.exceptions import UserRejectsError

from aiogram import Bot, Router, F, types, html
from aiogram.filters import Command, CommandObject, CommandStart, StateFilter
from aiogram.types import BufferedInputFile, InlineKeyboardMarkup, InlineKeyboardButton, ErrorEvent
from aiogram.exceptions import TelegramBadRequest, TelegramNetworkError
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.enums import ChatMemberStatus, ParseMode
from aiogram.utils.keyboard import InlineKeyboardBuilder

from shop_bot.bot import keyboards
from shop_bot.bot.keyboards import normalize_web_app_url, _is_local_address
from shop_bot.modules import xui_api
from shop_bot.data_manager.database import (
    get_user, add_new_key, get_user_keys, update_user_stats,
    register_user_if_not_exists, get_next_key_number, get_key_by_id, get_key_by_email,
    update_key_info, set_trial_used, set_terms_agreed, set_documents_agreed, get_setting, get_all_hosts, get_host,
    get_plans_for_host, get_plan_by_id, log_transaction, get_referral_count,
    add_to_referral_balance, create_pending_transaction, create_pending_ton_transaction, create_pending_stars_transaction, get_all_users,
    set_referral_balance, set_referral_balance_all, update_transaction_on_payment, update_yookassa_transaction,
    set_subscription_status, revoke_user_consent, set_trial_days_given, increment_trial_reuses, 
    reset_trial_used, get_trial_info, filter_plans_by_display_mode, assign_user_to_group_by_code, is_production_server
)

from shop_bot.config import (
    get_profile_text, get_vpn_active_text, VPN_INACTIVE_TEXT, VPN_NO_DATA_TEXT,
    get_key_info_text, CHOOSE_PAYMENT_METHOD_MESSAGE, HOWTO_CHOOSE_OS_MESSAGE, get_purchase_success_text, get_payment_method_message_with_plan,
    VIDEO_INSTRUCTIONS_ENABLED, get_video_instruction_path, has_video_instruction, VIDEO_INSTRUCTIONS_DIR
)
from shop_bot.utils.performance_monitor import measure_performance

from pathlib import Path

TELEGRAM_BOT_USERNAME = None
PAYMENT_METHODS = {}
ADMIN_ID = None
CRYPTO_BOT_TOKEN = get_setting("cryptobot_token")

logger = logging.getLogger(__name__)
admin_router = Router()
user_router = Router()

# Экспорт функций-обработчиков для тестирования
create_yookassa_payment_handler = None
create_cryptobot_invoice_handler = None
create_ton_invoice_handler = None
create_stars_invoice_handler = None
create_heleket_invoice_handler = None
pay_with_internal_balance = None
pre_checkout_handler = None
trial_period_callback_handler = None


def _get_user_timezone_context(user_id: int) -> Tuple[bool, str | None]:
    """Возвращает флаг включения timezone и значение timezone пользователя"""
    from shop_bot.data_manager.database import get_user_timezone, is_timezone_feature_enabled

    feature_enabled = is_timezone_feature_enabled()
    user_timezone = get_user_timezone(user_id) if feature_enabled else None
    return feature_enabled, user_timezone


def _safe_strip(value: str | None) -> str | None:
    """Безопасное удаление пробелов"""
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def _resolve_host_code(host_name: str | None) -> str:
    """Возвращает стабильный host_code без эмодзи"""
    if not host_name:
        return ""
    try:
        host_record = get_host(host_name)
        if host_record and host_record.get('host_code'):
            return str(host_record['host_code'])
    except Exception:
        pass
    # ИСПРАВЛЕНИЕ: Удаляем эмодзи и специальные символы из fallback
    import re
    # Удаляем все эмодзи (Unicode ranges для эмодзи) и оставляем только буквы, цифры, пробелы, дефисы
    cleaned = re.sub(r'[\U0001F300-\U0001F9FF\U00002600-\U000027BF\U0001F600-\U0001F64F\U0001F680-\U0001F6FF]', '', str(host_name))
    # Удаляем все остальные не-буквенно-цифровые символы кроме пробелов и дефисов
    cleaned = re.sub(r'[^\w\s-]', '', cleaned)
    return cleaned.replace(' ', '').lower()


def _should_use_yookassa_stub() -> bool:
    """Проверяет, нужно ли использовать локальный stub для YooKassa."""
    if get_setting("yookassa_local_stub") != "true":
        return False
    if get_setting("yookassa_test_mode") != "true":
        return False
    return True


def _reconfigure_yookassa():
    """Переинициализирует Configuration с актуальными настройками из БД"""
    from yookassa import Configuration
    
    yookassa_test_mode = get_setting("yookassa_test_mode") == "true"
    
    # КРИТИЧНО: НЕ смешиваем тестовые и боевые credentials
    # Каждый режим использует ТОЛЬКО свои ключи и API URL
    if yookassa_test_mode:
        # Тестовый режим: используем ТОЛЬКО test credentials
        shop_id = _safe_strip(get_setting("yookassa_test_shop_id"))
        secret_key = _safe_strip(get_setting("yookassa_test_secret_key"))
        api_url = _safe_strip(get_setting("yookassa_test_api_url")) or "https://api.test.yookassa.ru/v3"
        verify_ssl = get_setting("yookassa_test_verify_ssl") != "false"
        mode_text = "ТЕСТОВЫЙ"
    else:
        # Боевой режим: используем ТОЛЬКО production credentials
        shop_id = _safe_strip(get_setting("yookassa_shop_id"))
        secret_key = _safe_strip(get_setting("yookassa_secret_key"))
        api_url = _safe_strip(get_setting("yookassa_api_url")) or "https://api.yookassa.ru/v3"
        verify_ssl = get_setting("yookassa_verify_ssl") != "false"
        mode_text = "БОЕВОЙ"
    
    if shop_id and secret_key:
        # КРИТИЧНО: Явно логируем режим и параметры
        logger.info(
            f"[YOOKASSA_RECONFIGURE] mode={mode_text}, "
            f"shop_id={shop_id[:8]}..., api_url={api_url}, verify_ssl={verify_ssl}"
        )
        Configuration.configure(
            account_id=shop_id,
            secret_key=secret_key,
            api_url=api_url,
            verify=verify_ssl
        )
        return True
    else:
        logger.warning(f"[YOOKASSA_RECONFIGURE] Missing credentials for {mode_text} mode! shop_id={bool(shop_id)}, secret_key={bool(secret_key)}")
        return False


def get_yookassa_return_url() -> str:
    """
    Получить return_url для YooKassa с безопасным fallback на Telegram deep link.
    
    Согласно документации YooKassa, для мобильных платежей рекомендуется использовать
    валидный HTTP(S) URL вместо deep links. Если домен не настроен, используется
    fallback на Telegram deep link для обратной совместимости.
    
    Returns:
        str: URL для редиректа после оплаты
    """
    from shop_bot.data_manager.database import get_global_domain
    
    global_domain = get_global_domain()
    
    if global_domain:
        # Убираем trailing slash если есть
        domain = global_domain.rstrip('/')
        return_url = f"{domain}/yookassa-return"
        logger.info(
            f"[YOOKASSA_RETURN_URL] Using domain-based return_url: {return_url} "
            f"(domain: {domain})"
        )
        return return_url
    else:
        # Fallback на Telegram deep link если домен не настроен
        # Это сохраняет обратную совместимость и не ломает существующий функционал
        fallback_url = f"https://t.me/{TELEGRAM_BOT_USERNAME}"
        logger.warning(
            f"[YOOKASSA_RETURN_URL] global_domain not configured, "
            f"using fallback Telegram deep link: {fallback_url}. "
            f"Рекомендуется настроить global_domain в настройках панели для лучшей "
            f"совместимости с мобильными платежами (особенно Mir Pay)."
        )
        return fallback_url


# Добавляем обработчик ошибок для admin_router
@admin_router.error()
@measure_performance("admin_router_error")
async def admin_router_error_handler(event: ErrorEvent):
    """Глобальный обработчик ошибок для admin_router"""
    logger.critical(
        "Critical error in admin router caused by %s", 
        event.exception, 
        exc_info=True
    )
    
    # Пытаемся определить тип update и отправить сообщение администратору
    update = event.update
    admin_id = None
    
    try:
        if update.message:
            admin_id = update.message.from_user.id
            # Админу показываем больше деталей
            error_details = f"{type(event.exception).__name__}: {str(event.exception)}"
            await update.message.answer(
                f"⚠️ <b>Ошибка администратора:</b>\n\n"
                f"<code>{error_details}</code>\n\n"
                f"Проверьте логи для подробностей.",
                parse_mode="HTML"
            )
        elif update.callback_query:
            admin_id = update.callback_query.from_user.id
            await update.callback_query.answer(
                "⚠️ Ошибка. Проверьте логи для подробностей.",
                show_alert=True
            )
    except Exception as notification_error:
        logger.error(f"Failed to send error notification to admin {admin_id}: {notification_error}")

def get_admin_id() -> int | None:
    """Безопасно получает ID администратора"""
    admin_id_str = get_setting("admin_telegram_id")
    if admin_id_str:
        try:
            return int(admin_id_str)
        except ValueError:
            return None
    return None

class KeyPurchase(StatesGroup):
    waiting_for_host_selection = State()
    waiting_for_plan_selection = State()

class Onboarding(StatesGroup):
    waiting_for_terms_agreement = State()     # Состояние для согласия с условиями
    waiting_for_documents_agreement = State() # Состояние для согласия с политикой
    waiting_for_subscription = State()        # Состояние для проверки подписки

class PaymentProcess(StatesGroup):
    waiting_for_email = State()
    waiting_for_payment_method = State()
    waiting_for_promo_code = State()
    waiting_for_payment = State()  # Ожидание оплаты (после создания ссылки)

class TopupProcess(StatesGroup):
    waiting_for_custom_amount = State()
    waiting_for_payment_method = State()

class Broadcast(StatesGroup):
    waiting_for_message = State()
    waiting_for_button_option = State()
    waiting_for_button_text = State()
    waiting_for_button_url = State()
    waiting_for_confirmation = State()

class WithdrawStates(StatesGroup):
    waiting_for_payment_method = State()
    waiting_for_bank = State()
    waiting_for_details = State()

class DeclineWithdrawStates(StatesGroup):
    waiting_for_decline_reason = State()

class TrialResetStates(StatesGroup):
    waiting_for_user_id = State()

def is_valid_email(email: str) -> bool:
    pattern = r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$'
    return re.match(pattern, email) is not None

# -------------------- Instructions loader (shared with web panel) --------------------
def _resolve_instructions_dir() -> Path:
    candidates = [
        Path("/app/project") / "instructions",
        Path(__file__).resolve().parents[3] / "instructions",
        Path.cwd() / "instructions",
    ]
    for p in candidates:
        try:
            if p.exists():
                return p
        except Exception:
            continue
    return candidates[0]

def _get_instruction_file(platform: str) -> Path:
    mapping = {
        'android': 'android.md',
        'ios': 'ios.md',
        'windows': 'windows.md',
        'macos': 'macos.md',
        'linux': 'linux.md',
    }
    return _resolve_instructions_dir() / mapping.get(platform, 'android.md')

def _default_instruction_text(platform: str) -> str:
    if platform == 'android':
        return (
            "<b>Подключение на Android</b>\n\n"
            "1. <b>Установите приложение V2RayTun:</b> Загрузите и установите приложение V2RayTun из Google Play Store.\n"
            "2. <b>Скопируйте свой ключ (vless://)</b> Перейдите в раздел «Моя подписка» в нашем боте и скопируйте свой ключ.\n"
            "3. <b>Импортируйте конфигурацию:</b>\n"
            "   • Откройте V2RayTun.\n"
            "   • Нажмите на значок + в правом нижнем углу.\n"
            "   • Выберите «Импортировать конфигурацию из буфера обмена» (или аналогичный пункт).\n"
            "4. <b>Выберите сервер:</b> Выберите появившийся сервер в списке.\n"
            "5. <b>Подключитесь к VPN:</b> Нажмите на кнопку подключения (значок «V» или воспроизведения). Возможно, потребуется разрешение на создание VPN-подключения.\n"
            "6. <b>Проверьте подключение:</b> После подключения проверьте свой IP-адрес, например, на https://whatismyipaddress.com/. Он должен отличаться от вашего реального IP."
        )
    if platform in ['ios', 'macos']:
        return (
            f"<b>Подключение на {'MacOS' if platform=='macos' else 'iOS (iPhone/iPad)'}</b>\n\n"
            "1. <b>Установите приложение V2RayTun:</b> Загрузите и установите приложение V2RayTun из App Store.\n"
            "2. <b>Скопируйте свой ключ (vless://):</b> Перейдите в раздел «Моя подписка» в нашем боте и скопируйте свой ключ.\n"
            "3. <b>Импортируйте конфигурацию:</b>\n"
            "   • Откройте V2RayTun.\n"
            "   • Нажмите на значок +.\n"
            "   • Выберите «Импортировать конфигурацию из буфера обмена» (или аналогичный пункт).\n"
            "4. <b>Выберите сервер:</b> Выберите появившийся сервер в списке.\n"
            "5. <b>Подключитесь к VPN:</b> Включите главный переключатель в V2RayTun. Возможно, потребуется разрешить создание VPN-подключения.\n"
            "6. <b>Проверьте подключение:</b> После подключения проверьте свой IP-адрес, например, на https://whatismyipaddress.com/. Он должен отличаться от вашего реального IP."
        )
    if platform == 'windows':
        return (
            "<b>Подключение на Windows</b>\n\n"
            "1. <b>Установите приложение Nekoray:</b> Загрузите Nekoray с https://github.com/MatsuriDayo/Nekoray/releases. Выберите подходящую версию (например, Nekoray-x64.exe).\n"
            "2. <b>Распакуйте архив:</b> Распакуйте скачанный архив в удобное место.\n"
            "3. <b>Запустите Nekoray.exe:</b> Откройте исполняемый файл.\n"
            "4. <b>Скопируйте свой ключ (vless://)</b> Перейдите в раздел «Моя подписка» в нашем боте и скопируйте свой ключ.\n"
            "5. <b>Импортируйте конфигурацию:</b>\n"
            "   • В Nekoray нажмите «Сервер» (Server).\n"
            "   • Выберите «Импортировать из буфера обмена».\n"
            "   • Nekoray автоматически импортирует конфигурацию.\n"
            "6. <b>Обновите серверы (если нужно):</b> Если серверы не появились, нажмите «Серверы» → «Обновить все серверы».\n"
            "7. Сверху включите пункт 'Режим TUN' ('Tun Mode')\n"
            "8. <b>Выберите сервер:</b> В главном окне выберите появившийся сервер.\n"
            "9. <b>Подключитесь к VPN:</b> Нажмите «Подключить» (Connect).\n"
            "10. <b>Проверьте подключение:</b> Откройте браузер и проверьте IP на https://whatismyipaddress.com/. Он должен отличаться от вашего реального IP."
        )
    if platform == 'linux':
        return (
            "<b>Подключение на Linux</b>\n\n"
            "1. <b>Скачайте и распакуйте Nekoray:</b> Перейдите на https://github.com/MatsuriDayo/Nekoray/releases и скачайте архив для Linux. Распакуйте его в удобную папку.\n"
            "2. <b>Запустите Nekoray:</b> Откройте терминал, перейдите в папку с Nekoray и выполните <code>./nekoray</code> (или используйте графический запуск, если доступен).\n"
            "3. <b>Скопируйте свой ключ (vless://)</b> Перейдите в раздел «Моя подписка» в нашем боте и скопируйте свой ключ.\n"
            "4. <b>Импортируйте конфигурацию:</b>\n"
            "   • В Nekoray нажмите «Сервер» (Server).\n"
            "   • Выберите «Импортировать из буфера обмена».\n"
            "   • Nekoray автоматически импортирует конфигурацию.\n"
            "5. <b>Обновите серверы (если нужно):</b> Если серверы не появились, нажмите «Серверы» → «Обновить все серверы».\n"
            "6. Сверху включите пункт 'Режим TUN' ('Tun Mode')\n"
            "7. <b>Выберите сервер:</b> В главном окне выберите появившийся сервер.\n"
            "8. <b>Подключитесь к VPN:</b> Нажмите «Подключить» (Connect).\n"
            "9. <b>Проверьте подключение:</b> Откройте браузер и проверьте IP на https://whatismyipaddress.com/. Он должен отличаться от вашего реального IP."
        )
    return ''

def _load_instruction_text(platform: str) -> str:
    try:
        file_path = _get_instruction_file(platform)
        if file_path.exists():
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()
    except Exception:
        pass
    return _default_instruction_text(platform)

async def _send_instruction_with_video(callback: types.CallbackQuery, platform: str, keyboard_func):
    """Отправляет инструкцию с видео, если оно доступно"""
    text = _load_instruction_text(platform)
    
    if VIDEO_INSTRUCTIONS_ENABLED and has_video_instruction(platform):
        try:
            video_path = Path(get_video_instruction_path(platform))
            if video_path.exists():
                # Отправляем видео с текстом
                with open(video_path, 'rb') as video_file:
                    video_input = BufferedInputFile(video_file.read(), filename=f"{platform}_instruction.mp4")
                    await callback.message.answer_video(
                        video=video_input,
                        caption=text,
                        reply_markup=keyboard_func(),
                        parse_mode="HTML"
                    )
                return
        except Exception as e:
            logger.error(f"Ошибка при отправке видеоинструкции для {platform}: {e}")
    
    # Если видео недоступно, отправляем только текст
    await callback.message.edit_text(
        text,
        reply_markup=keyboard_func(),
        disable_web_page_preview=True,
        parse_mode="HTML"
    )

async def show_main_menu(message: types.Message, edit_message: bool = False):
    """Показывает главное меню используя ReplyKeyboardMarkup"""
    user_id = message.chat.id
    is_admin = str(user_id) == ADMIN_ID

    text = "🏠 <b>Главное меню</b>\n\nВыберите действие:"
    keyboard = keyboards.get_main_reply_keyboard(is_admin)
    
    if edit_message:
        try:
            await message.edit_text(text, reply_markup=None)  # Убираем inline клавиатуру
        except TelegramBadRequest:
            pass
    else:
        await message.answer(text, reply_markup=keyboard)

def registration_required(f):
    @wraps(f)
    async def decorated_function(event: types.Update, *args, **kwargs):
        user_id = event.from_user.id
        user_data = get_user(user_id)
        if user_data:
            return await f(event, *args, **kwargs)
        else:
            message_text = "Пожалуйста, для начала работы со мной, отправьте команду /start"
            if isinstance(event, types.CallbackQuery):
                await event.answer(message_text, show_alert=True)
            else:
                await event.answer(message_text)
    return decorated_function

async def check_user_subscription(user_id: int, bot: Bot, channel_url: str) -> tuple[bool, str]:
    """
    Проверяет подписку пользователя на канал
    Возвращает (is_subscribed, error_message)
    """
    try:
        if '@' not in channel_url and 't.me/' not in channel_url:
            logger.error(f"Неверный формат URL канала: {channel_url}")
            return False, "Неверный формат URL канала"
        
        channel_id = '@' + channel_url.split('/')[-1] if 't.me/' in channel_url else channel_url
        
        try:
            member = await bot.get_chat_member(chat_id=channel_id, user_id=user_id)
            
            if member.status in [ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR]:
                # Пользователь подписан - обновляем статус в базе данных
                set_subscription_status(user_id, 'subscribed')
                return True, ""
            else:
                # Пользователь не подписан - обновляем статус в базе данных
                set_subscription_status(user_id, 'not_subscribed')
                return False, ""
                
        except TelegramBadRequest as e:
            if "member list is inaccessible" in str(e):
                # Если бот не может получить доступ к списку участников, 
                # НЕ доверяем пользователю - возвращаем False
                logger.warning(f"Не удалось проверить подписку для user_id {user_id} на канал {channel_url}: {e}. Требуется подписка.")
                set_subscription_status(user_id, 'not_subscribed')
                return False, "Не удалось проверить подписку. Пожалуйста, убедитесь, что вы подписаны на канал."
            else:
                # Другие ошибки Telegram API - тоже не доверяем
                logger.error(f"Ошибка Telegram API при проверке подписки для user_id {user_id} на канал {channel_url}: {e}")
                set_subscription_status(user_id, 'not_subscribed')
                return False, f"Ошибка проверки подписки: {str(e)}"
                
    except Exception as e:
        logger.error(f"Ошибка при проверке подписки для user_id {user_id} на канал {channel_url}: {e}")
        set_subscription_status(user_id, 'not_subscribed')
        return False, f"Не удалось проверить подписку. Убедитесь, что бот является администратором канала. Попробуйте позже."

def subscription_required(f):
    @wraps(f)
    async def decorated_function(event: types.Update, *args, **kwargs):
        user_id = event.from_user.id
        user_data = get_user(user_id)
        
        # Проверяем регистрацию
        if not user_data:
            message_text = "Пожалуйста, для начала работы со мной, отправьте команду /start"
            if isinstance(event, types.CallbackQuery):
                await event.answer(message_text, show_alert=True)
            else:
                await event.answer(message_text)
            return
        
        # Проверяем подписку на канал
        is_subscription_forced = get_setting("force_subscription") == "true"
        channel_url = get_setting("channel_url")
        
        if is_subscription_forced and channel_url:
            # Проверяем статус подписки из базы данных
            subscription_status = user_data.get('subscription_status', 'not_subscribed')
            
            if subscription_status != 'subscribed':
                message_text = "❌ Для использования бота необходимо подписаться на наш канал. Пожалуйста, подпишитесь и попробуйте снова."
                
                # Создаем клавиатуру с кнопками
                builder = InlineKeyboardBuilder()
                builder.button(text="📢 Перейти в канал", url=channel_url)
                builder.button(text="✅ Я подписался", callback_data="check_subscription_and_agree")
                builder.adjust(1)
                
                if isinstance(event, types.CallbackQuery):
                    try:
                        await event.message.edit_text(
                            message_text,
                            reply_markup=builder.as_markup()
                        )
                    except TelegramBadRequest as e:
                        if "message is not modified" in str(e):
                            # Сообщение уже имеет нужное содержимое, просто отвечаем
                            await event.answer("❌ Пожалуйста, подпишитесь на канал", show_alert=True)
                        else:
                            raise e
                else:
                    await event.answer(
                        message_text,
                        reply_markup=builder.as_markup()
                    )
                return
        
        return await f(event, *args, **kwargs)
    return decorated_function

def documents_consent_required(f):
    @wraps(f)
    async def decorated_function(event: types.Update, *args, **kwargs):
        user_id = event.from_user.id
        user_data = get_user(user_id)
        
        # Проверяем регистрацию
        if not user_data:
            message_text = "Пожалуйста, для начала работы со мной, отправьте команду /start"
            if isinstance(event, types.CallbackQuery):
                await event.answer(message_text, show_alert=True)
            else:
                await event.answer(message_text)
            return
        
        # Проверяем согласие с документами
        if not user_data.get('agreed_to_documents', False):
            # Получаем домен из настроек для динамического формирования URL
            from shop_bot.data_manager.database import get_global_domain
            domain = get_global_domain()
            
            terms_url = None
            privacy_url = None
            if is_production_server() and domain and not _is_local_address(domain):
                terms_url = normalize_web_app_url(f"{domain.rstrip('/')}/terms")
                privacy_url = normalize_web_app_url(f"{domain.rstrip('/')}/privacy")
            
            if not terms_url or not privacy_url:
                # Если документы не настроены, разрешаем доступ
                return await f(event, *args, **kwargs)
            
            message_text = (
                "❌ Для использования бота необходимо согласиться с документами.\n\n"
                "Пожалуйста, ознакомьтесь с условиями использования и политикой конфиденциальности, "
                "а затем примите их для продолжения работы."
            )
            
            # Создаем клавиатуру с кнопками
            builder = InlineKeyboardBuilder()
            if terms_url:
                builder.button(text="📄 Условия использования", web_app={"url": terms_url})
            if privacy_url:
                builder.button(text="🔒 Политика конфиденциальности", web_app={"url": privacy_url})
            builder.button(text="✅ Я согласен с документами", callback_data="agree_to_terms")
            builder.adjust(1)
            
            if isinstance(event, types.CallbackQuery):
                try:
                    await event.message.edit_text(
                        message_text,
                        reply_markup=builder.as_markup()
                    )
                except TelegramBadRequest as e:
                    if "message is not modified" in str(e):
                        # Сообщение уже имеет нужное содержимое, просто отвечаем
                        await event.answer("❌ Пожалуйста, согласитесь с документами", show_alert=True)
                    else:
                        raise e
            else:
                await event.answer(
                    message_text,
                    reply_markup=builder.as_markup()
                )
            return
        
        return await f(event, *args, **kwargs)
    return decorated_function

def get_user_router() -> Router:
    user_router = Router()

    @user_router.message(CommandStart())
    @measure_performance("start_handler")
    async def start_handler(message: types.Message, state: FSMContext, bot: Bot, command: CommandObject):
        user_id = message.from_user.id
        username = message.from_user.username or message.from_user.full_name
        referrer_id = None

        print(f"DEBUG: MAIN BOT START HANDLER CALLED for user {user_id} ({username})")
        logger.info(f"MAIN BOT START HANDLER: User {user_id} ({username}) started bot")
        
        # Принудительно выводим в консоль для отладки
        print(f"FORCE DEBUG: START HANDLER EXECUTING for user {user_id}")

        # Сначала парсим referrer_id из deeplink (если есть)
        if command.args and command.args.startswith('ref_'):
            try:
                potential_referrer_id = int(command.args.split('_')[1])
                if potential_referrer_id != user_id:
                    referrer_id = potential_referrer_id
                    logger.info(f"New user {user_id} was referred by {referrer_id}")
            except (IndexError, ValueError):
                logger.warning(f"Invalid referral code received: {command.args}")
        
        # Регистрируем пользователя СРАЗУ (до обработки остальных deeplink параметров)
        register_user_if_not_exists(user_id, username, referrer_id, message.from_user.full_name)
        logger.info(f"User {user_id} registered/updated before deeplink processing")

        # Обработка deeplink параметров
        if command.args:
            try:
                from shop_bot.utils.deeplink import parse_deeplink
                from shop_bot.data_manager.database import can_user_use_promo_code, record_promo_code_usage, add_to_user_balance
                
                start_param = command.args
                logger.info(f"DEBUG: Parsing deeplink start_param: '{start_param}' for user {user_id}")
                
                # Парсим deeplink параметры (поддерживает base64 и старые форматы)
                group_code, promo_code, deeplink_referrer_id = parse_deeplink(start_param)
                
                # Обработка реферера из deeplink (если не был обработан выше)
                if deeplink_referrer_id and deeplink_referrer_id != user_id and not referrer_id:
                    referrer_id = deeplink_referrer_id
                    logger.info(f"New user {user_id} was referred by {referrer_id} (from deeplink)")
                    # Обновляем referrer_id в БД
                    register_user_if_not_exists(user_id, username, referrer_id, message.from_user.full_name)
                
                applied_groups = []
                applied_promos = []
                already_applied_promos = []  # Промокоды, которые уже были применены ранее
                
                # Обработка группы пользователей
                if group_code:
                    logger.info(f"Processing group assignment: user {user_id} -> group_code '{group_code}'")
                    success = assign_user_to_group_by_code(user_id, group_code)
                    if success:
                        applied_groups.append(group_code)
                        logger.info(f"Successfully assigned user {user_id} to group '{group_code}'")
                    else:
                        logger.warning(f"Failed to assign user {user_id} to group '{group_code}'")
                
                # Обработка промокода
                if promo_code:
                    logger.info(f"Processing promo code: user {user_id} -> promo '{promo_code}'")
                    validation_result = can_user_use_promo_code(user_id, promo_code, "shop")
                    if validation_result.get('can_use'):
                        promo_data = validation_result.get('promo_data') or {}
                        existing_usage_id = validation_result.get('existing_usage_id')
                        
                        # Записываем или обновляем использование промокода со статусом 'applied'
                        success = record_promo_code_usage(
                            promo_id=promo_data.get('promo_id'),
                            user_id=user_id,
                            bot="shop",
                            plan_id=None,
                            discount_amount=promo_data.get('discount_amount', 0.0),
                            discount_percent=promo_data.get('discount_percent', 0.0),
                            discount_bonus=promo_data.get('discount_bonus', 0.0),
                            metadata={"source": "deep_link"},
                            status='applied',
                            existing_usage_id=existing_usage_id
                        )
                        
                        if success:
                            # ИСПРАВЛЕНИЕ: Разделяем промокоды на новые и уже примененные
                            if not existing_usage_id:
                                # Промокод применен впервые
                                applied_promos.append(promo_code)
                            else:
                                # Промокод уже был применен ранее
                                already_applied_promos.append(promo_code)
                            
                            # Сохраняем промокод в state для дальнейшего использования
                            await state.update_data(
                                promo_code=promo_code,
                                promo_usage_id=validation_result.get('existing_usage_id'),
                                promo_data=promo_data
                            )
                            
                            # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: Зачисляем discount_bonus ТОЛЬКО если existing_usage_id отсутствует
                            # Это предотвращает многократное начисление бонуса при повторном переходе по deeplink ссылке
                            bonus_amount = promo_data.get('discount_bonus', 0.0)
                            if not existing_usage_id and bonus_amount > 0:
                                add_to_user_balance(user_id, bonus_amount)
                                logger.info(f"Applied bonus {bonus_amount} RUB to user {user_id} from promo '{promo_code}' (first time)")
                            elif existing_usage_id and bonus_amount > 0:
                                logger.info(f"Bonus NOT applied for user {user_id} from promo '{promo_code}' (already applied, existing_usage_id={existing_usage_id})")
                            
                            logger.info(f"Successfully processed promo code '{promo_code}' for user {user_id}: first_time={not existing_usage_id}")
                        else:
                            # Проверяем, почему не удалось применить промокод
                            # Проверяем, есть ли уже запись о применении этого промокода
                            from shop_bot.data_manager.database import get_promo_code_usage_by_user
                            existing_usage = get_promo_code_usage_by_user(promo_data.get('promo_id'), user_id, "shop")
                            
                            if existing_usage and existing_usage.get('status') == 'applied':
                                # Промокод уже применён ранее
                                already_applied_promos.append(promo_code)
                                logger.info(f"Promo code '{promo_code}' was already applied for user {user_id}")
                            else:
                                # Промокод уже использован или другая ошибка
                                logger.warning(f"Failed to record promo code usage for user {user_id} - promo may be already used")
                    else:
                        logger.warning(f"Promo code '{promo_code}' is invalid or already used for user {user_id}")
                
                # Сохраняем информацию о примененных параметрах в state для показа после онбординга
                if applied_groups or applied_promos or already_applied_promos:
                    # Получаем promo_data из state (если есть)
                    state_data = await state.get_data()
                    current_promo_data = state_data.get('promo_data', {})
                    
                    await state.update_data(
                        deeplink_applied_groups=applied_groups,
                        deeplink_applied_promos=applied_promos,
                        deeplink_already_applied_promos=already_applied_promos,
                        promo_data=current_promo_data
                    )
                    logger.info(f"Deeplink processing completed for user {user_id}: groups={applied_groups}, promos={applied_promos}, already_applied={already_applied_promos}")
                
            except Exception as e:
                logger.error(f"Error handling deeplink parameters: {e}", exc_info=True)
                
        # Получаем данные пользователя (уже зарегистрирован на строке 502)
        user_data = get_user(user_id)

        # Получаем настройки
        from shop_bot.data_manager.database import get_global_domain
        domain = get_global_domain()
        
        terms_url = None
        privacy_url = None
        if is_production_server() and domain and not _is_local_address(domain):
            terms_url = normalize_web_app_url(f"{domain.rstrip('/')}/terms")
            privacy_url = normalize_web_app_url(f"{domain.rstrip('/')}/privacy")
            
        channel_url = get_setting("channel_url")
        is_subscription_forced = get_setting("force_subscription") == "true"
        
        logger.info(f"START HANDLER: Settings - force_subscription: {is_subscription_forced}, channel_url: {channel_url}, terms_url: {terms_url}, privacy_url: {privacy_url}")

        # Получаем текущий статус пользователя
        agreed_to_terms = user_data.get('agreed_to_terms', False)
        agreed_to_documents = user_data.get('agreed_to_documents', False)
        subscription_status = user_data.get('subscription_status', 'not_subscribed')
        
        logger.info(f"START HANDLER: User {user_id} status - agreed_to_terms: {agreed_to_terms}, agreed_to_documents: {agreed_to_documents}, subscription_status: {subscription_status}")
        
        # ПРОВЕРКА 1: Согласие с условиями
        if not agreed_to_terms and terms_url:
            logger.info(f"START HANDLER: User {user_id} needs to agree to terms, showing terms screen")
            await show_terms_agreement_screen(message, state)
            return
        
        # ПРОВЕРКА 2: Согласие с документами
        if not agreed_to_documents and privacy_url:
            logger.info(f"START HANDLER: User {user_id} needs to agree to documents, showing documents screen")
            await show_documents_agreement_screen(message, state)
            return
        
        # Если URL не настроены, устанавливаем согласия автоматически
        if not terms_url and not privacy_url:
            if not agreed_to_terms:
                set_terms_agreed(user_id)
                logger.info(f"START HANDLER: User {user_id} terms agreement set automatically (no URL configured)")
            if not agreed_to_documents:
                set_documents_agreed(user_id)
                logger.info(f"START HANDLER: User {user_id} documents agreement set automatically (no URL configured)")
        
        # ПРОВЕРКА 3: Подписка на канал
        if is_subscription_forced and channel_url and subscription_status != 'subscribed':
            logger.info(f"START HANDLER: User {user_id} needs to subscribe, showing subscription screen")
            await show_subscription_screen(message, state)
            return
        
        # Если все проверки пройдены, показываем главное меню
        logger.info(f"START HANDLER: All checks passed for user {user_id}, showing main menu")
        
        # Проверяем, были ли применены deeplink параметры
        state_data = await state.get_data()
        deeplink_groups = state_data.get('deeplink_applied_groups', [])
        deeplink_promos = state_data.get('deeplink_applied_promos', [])
        deeplink_already_applied_promos = state_data.get('deeplink_already_applied_promos', [])
        
        if deeplink_groups or deeplink_promos or deeplink_already_applied_promos:
            message_parts = []
            if deeplink_groups:
                message_parts.append(f"✅ Вы добавлены в группу(ы): {', '.join(deeplink_groups)}")
            if deeplink_promos:
                promo_data = state_data.get('promo_data', {})
                bonus_amount = promo_data.get('discount_bonus', 0.0)
                if bonus_amount > 0:
                    message_parts.append(f"✅ Применен промокод: {', '.join(deeplink_promos)}")
                    message_parts.append(f"💰 На ваш баланс зачислено {bonus_amount} руб.")
                else:
                    message_parts.append(f"✅ Применен промокод: {', '.join(deeplink_promos)}")
            if deeplink_already_applied_promos:
                message_parts.append(f"❌ Вы ранее использовали промокод: {', '.join(deeplink_already_applied_promos)}")
            
            if message_parts:
                await message.answer('\n'.join(message_parts))
                # Очищаем данные из state
                await state.update_data(
                    deeplink_applied_groups=None,
                    deeplink_applied_promos=None,
                    deeplink_already_applied_promos=None,
                    promo_data=None
                )
                logger.info(f"Deeplink notification sent to user {user_id}: groups={deeplink_groups}, promos={deeplink_promos}, already_applied={deeplink_already_applied_promos}")
        
        is_admin = str(user_id) == ADMIN_ID
        await message.answer(
            f"👋 Добро пожаловать, {html.bold(message.from_user.full_name)}!",
            reply_markup=keyboards.get_main_reply_keyboard(is_admin)
        )
        await show_main_menu(message)

    @user_router.callback_query(F.data == "check_subscription_and_agree")
    @measure_performance("check_subscription_and_agree")
    async def check_subscription_and_agree_handler(callback: types.CallbackQuery, state: FSMContext, bot: Bot):
        user_id = callback.from_user.id
        channel_url = get_setting("channel_url")
        is_subscription_forced = get_setting("force_subscription") == "true"

        if not is_subscription_forced or not channel_url:
            # Если подписка не принудительная, обрабатываем как успешный онбординг
            await process_successful_onboarding(callback, state)
            return
            
        # Используем общую функцию проверки подписки
        is_subscribed, error_message = await check_user_subscription(user_id, bot, channel_url)
        
        if error_message:
            await callback.answer(error_message, show_alert=True)
            return
            
        if is_subscribed:
            # Пользователь подписан - обновляем статус в базе данных
            set_subscription_status(user_id, 'subscribed')
            
            # Проверяем, в каком состоянии мы находимся
            current_state = await state.get_state()
            if current_state == Onboarding.waiting_for_subscription:
                # Мы в состоянии онбординга - завершаем его
                await process_successful_onboarding(callback, state)
            else:
                # Мы в обычном режиме - просто показываем успех и возвращаемся к главному меню
                await callback.answer("✅ Отлично! Теперь вы можете пользоваться ботом.", show_alert=True)
                await callback.message.delete()
                await show_main_menu(callback.message)
        else:
            # Пользователь не подписан - показываем сообщение с кнопками
            await show_subscription_required_message(callback, channel_url)


    async def show_subscription_required_message(callback: types.CallbackQuery, channel_url: str):
        """Показывает сообщение о необходимости подписки с кнопками"""
        message_text = "❌ Вы еще не подписались на канал. Пожалуйста, подпишитесь и попробуйте снова."
        builder = InlineKeyboardBuilder()
        builder.button(text="📢 Перейти в канал", url=channel_url)
        builder.button(text="✅ Я подписался", callback_data="check_subscription_and_agree")
        builder.adjust(1)
        
        try:
            await callback.message.edit_text(
                message_text,
                reply_markup=builder.as_markup()
            )
        except TelegramBadRequest as e:
            if "message is not modified" in str(e):
                # Сообщение уже имеет нужное содержимое, просто отвечаем
                await callback.answer("❌ Пожалуйста, подпишитесь на канал", show_alert=True)
            else:
                raise e

    @user_router.callback_query(F.data == "revoke_consent")
    @measure_performance("revoke_consent")
    async def revoke_consent_handler(callback: types.CallbackQuery):
        """Обработчик отзыва согласия пользователя"""
        user_id = callback.from_user.id
        
        # Отзываем согласие в базе данных
        revoke_user_consent(user_id)
        
        await callback.answer("✅ Ваше согласие с документами отозвано. Для дальнейшего использования бота необходимо будет заново принять условия.", show_alert=True)
        
        # Возвращаемся к главному меню
        await callback.message.delete()
        await show_main_menu(callback.message)

    @user_router.callback_query(F.data == "agree_to_terms")
    @measure_performance("agree_to_terms")
    async def agree_to_terms_handler(callback: types.CallbackQuery, state: FSMContext):
        """Обработчик согласия с документами"""
        user_id = callback.from_user.id
        set_documents_agreed(user_id)
        await callback.answer("✅ Согласие получено!")
        
        # Проверяем, находимся ли мы в процессе онбординга
        current_state = await state.get_state()
        if current_state == Onboarding.waiting_for_terms_agreement:
            # В процессе онбординга - переходим к проверке подписки
            await callback.message.delete()
            await show_subscription_screen(callback.message, state)
        else:
            # Согласие из главного меню - проверяем подписку
            is_subscription_forced = get_setting("force_subscription") == "true"
            channel_url = get_setting("channel_url")
            
            if is_subscription_forced and channel_url:
                # Нужно проверить подписку
                await callback.message.delete()
                await show_subscription_screen(callback.message, state)
            else:
                # Подписка не требуется - показываем главное меню
                is_admin = str(user_id) == ADMIN_ID
                try:
                    await callback.message.edit_text("🏠 <b>Главное меню</b>\n\nВыберите действие:", reply_markup=None)
                except Exception:
                    await callback.message.answer("🏠 <b>Главное меню</b>\n\nВыберите действие:", reply_markup=keyboards.get_main_reply_keyboard(is_admin))

    @user_router.callback_query(F.data == "agree_to_terms_only")
    @measure_performance("agree_to_terms_only")
    async def agree_to_terms_only_handler(callback: types.CallbackQuery, state: FSMContext):
        """Обработчик согласия только с условиями"""
        user_id = callback.from_user.id
        logger.info(f"User {user_id} agreed to terms only")
        
        # Устанавливаем согласие с условиями
        set_terms_agreed(user_id)
        await callback.answer("✅ Согласие с условиями получено!")
        
        # Переходим к проверке документов
        await callback.message.delete()
        await show_documents_agreement_screen(callback.message, state)

    @user_router.callback_query(F.data == "agree_to_documents_only")
    @measure_performance("agree_to_documents_only")
    async def agree_to_documents_only_handler(callback: types.CallbackQuery, state: FSMContext):
        """Обработчик согласия только с политикой конфиденциальности"""
        user_id = callback.from_user.id
        logger.info(f"User {user_id} agreed to documents only")
        
        # Устанавливаем согласие с документами
        set_documents_agreed(user_id)
        await callback.answer("✅ Согласие с политикой получено!")
        
        # Проверяем, нужна ли подписка
        is_subscription_forced = get_setting("force_subscription") == "true"
        channel_url = get_setting("channel_url")
        
        if is_subscription_forced and channel_url:
            # Нужно проверить подписку
            await callback.message.delete()
            await show_subscription_screen(callback.message, state)
        else:
            # Подписка не требуется - завершаем онбординг
            await process_successful_onboarding(callback, state)

    @user_router.callback_query(F.data == "check_subscription")
    @measure_performance("check_subscription")
    async def check_subscription_handler(callback: types.CallbackQuery, state: FSMContext, bot: Bot):
        """Обработчик проверки подписки на канал"""
        user_id = callback.from_user.id
        channel_url = get_setting("channel_url")
        is_subscription_forced = get_setting("force_subscription") == "true"

        if not is_subscription_forced or not channel_url:
            await process_successful_onboarding(callback, state)
            return
            
        # Используем общую функцию проверки подписки
        is_subscribed, error_message = await check_user_subscription(user_id, bot, channel_url)
        
        if error_message:
            await callback.answer(error_message, show_alert=True)
            return
            
        if is_subscribed:
            # Пользователь подписан - обновляем статус в базе данных
            set_subscription_status(user_id, 'subscribed')
            
            # Проверяем, в каком состоянии мы находимся
            current_state = await state.get_state()
            if current_state == Onboarding.waiting_for_subscription:
                # Мы в состоянии онбординга - завершаем его
                await process_successful_onboarding(callback, state)
            else:
                # Мы в обычном режиме - просто показываем успех и возвращаемся к главному меню
                await callback.answer("✅ Отлично! Теперь вы можете пользоваться ботом.", show_alert=True)
                await callback.message.delete()
                await show_main_menu(callback.message)
        else:
            # Пользователь не подписан - показываем сообщение с кнопками
            await show_subscription_required_message(callback, channel_url)

    @user_router.message(Onboarding.waiting_for_terms_agreement)
    @measure_performance("terms_agreement_fallback")
    async def terms_agreement_fallback_handler(message: types.Message):
        await message.answer("Пожалуйста, ознакомьтесь с документами и нажмите кнопку согласия в сообщении выше.")

    @user_router.message(Onboarding.waiting_for_subscription)
    @measure_performance("subscription_fallback")
    async def subscription_fallback_handler(message: types.Message):
        await message.answer("Пожалуйста, подпишитесь на канал и нажмите кнопку проверки в сообщении выше.")

    @user_router.message(F.text == "🏠 Главное меню")
    @documents_consent_required
    @subscription_required
    @measure_performance("main_menu_handler")
    async def main_menu_handler(message: types.Message):
        # Обновляем/навешиваем актуальную Reply Keyboard на чат
        user_id = message.from_user.id
        is_admin = str(user_id) == ADMIN_ID
        try:
            await message.answer("Выберите действие:", reply_markup=keyboards.get_main_reply_keyboard(is_admin))
        except Exception:
            pass
        await show_main_menu(message)

    @user_router.callback_query(F.data == "back_to_main_menu")
    @documents_consent_required
    @subscription_required
    @measure_performance("back_to_main_menu")
    async def back_to_main_menu_handler(callback: types.CallbackQuery):
        await callback.answer()
        # Гарантируем, что у пользователя установлена актуальная Reply Keyboard
        user_id = callback.from_user.id
        is_admin = str(user_id) == ADMIN_ID
        
        # Удаляем inline клавиатуру и показываем только ReplyKeyboardMarkup
        try:
            await callback.message.edit_text("🏠 <b>Главное меню</b>\n\nВыберите действие:", reply_markup=None)
        except Exception:
            # Если не удалось отредактировать сообщение, просто отправляем новое
            await callback.message.answer("🏠 <b>Главное меню</b>\n\nВыберите действие:", reply_markup=keyboards.get_main_reply_keyboard(is_admin))

    @user_router.message(F.text == "🛒 Купить")
    @documents_consent_required
    @subscription_required
    @measure_performance("buy_message_handler")
    async def buy_message_handler(message: types.Message, state: FSMContext):
        """Обработчик кнопки 'Купить' - показывает меню выбора услуг"""
        user_id = message.from_user.id
        
        # Сохраняем промокод в state, если он был применен ранее
        current_data = await state.get_data()
        if current_data.get('promo_code'):
            await state.update_data(
                promo_code=current_data.get('promo_code'),
                final_price=current_data.get('final_price'),
                promo_usage_id=current_data.get('promo_usage_id'),
                promo_data=current_data.get('promo_data')
            )
        user_db_data = get_user(user_id)
        trial_used = user_db_data.get('trial_used', 1) if user_db_data else 1
        user_keys = get_user_keys(user_id)
        total_keys_count = len(user_keys) if user_keys else 0
        
        await message.answer(
            "Выберите услугу:",
            reply_markup=keyboards.create_service_selection_keyboard(trial_used, total_keys_count)
        )

    @user_router.message(F.text == "🛒 Купить VPN")
    @documents_consent_required
    @subscription_required
    @measure_performance("buy_vpn_message")
    async def buy_vpn_message_handler(message: types.Message):
        """Обработчик кнопки 'Купить VPN' - показывает меню выбора услуг (для совместимости со старыми клавиатурами)"""
        user_id = message.from_user.id
        user_db_data = get_user(user_id)
        trial_used = user_db_data.get('trial_used', 1) if user_db_data else 1
        user_keys = get_user_keys(user_id)
        total_keys_count = len(user_keys) if user_keys else 0
        
        await message.answer(
            "Выберите услугу:",
            reply_markup=keyboards.create_service_selection_keyboard(trial_used, total_keys_count)
        )

    @user_router.callback_query(F.data == "buy_new_vpn")
    @documents_consent_required
    @subscription_required
    @measure_performance("buy_new_vpn")
    async def buy_new_vpn_handler(callback: types.CallbackQuery, state: FSMContext):
        """Обработчик кнопки 'Купить новый VPN'"""
        await callback.answer()
        user_id = callback.from_user.id
        
        hosts = get_all_hosts()
        if not hosts:
            await callback.message.edit_text("❌ В данный момент нет доступных серверов для покупки.")
            return
        # Скрываем сервера без доступных тарифов (с учётом режима отображения)
        try:
            hosts_with_plans = [h for h in hosts if filter_plans_by_display_mode(get_plans_for_host(h['host_name']), user_id)]
        except Exception:
            hosts_with_plans = hosts
        if not hosts_with_plans:
            await callback.message.edit_text("❌ В данный момент нет доступных серверов для покупки.")
            return
        user_keys = get_user_keys(user_id)
        await callback.message.edit_text(
            "Выберите сервер, на котором хотите приобрести ключ:",
            # Назад ведёт к выбору услуги
            reply_markup=keyboards.create_host_selection_keyboard(hosts_with_plans, action="new", total_keys_count=len(user_keys) if user_keys else 0, back_to="buy_vpn_service_selection")
        )

    @user_router.callback_query(F.data == "buy_vpn_service_selection")
    @documents_consent_required
    @subscription_required
    @measure_performance("buy_vpn_service_selection")
    async def buy_vpn_service_selection_handler(callback: types.CallbackQuery):
        """Обработчик кнопки 'Назад' - возврат к выбору услуги"""
        await callback.answer()
        user_id = callback.from_user.id
        user_keys = get_user_keys(user_id)
        user_db_data = get_user(user_id)
        trial_used = user_db_data.get('trial_used', 1) if user_db_data else 1
        total_keys_count = len(user_keys) if user_keys else 0
        
        await callback.message.edit_text(
            "Выберите услугу:",
            reply_markup=keyboards.create_service_selection_keyboard(trial_used, total_keys_count)
        )

    @user_router.callback_query(F.data == "buy_vpn_root")
    @documents_consent_required
    @subscription_required
    @measure_performance("buy_vpn_root")
    async def buy_vpn_root_handler(callback: types.CallbackQuery):
        await callback.answer()
        user_id = callback.from_user.id
        hosts = get_all_hosts()
        if not hosts:
            await callback.message.edit_text("❌ В данный момент нет доступных серверов для покупки.")
            return
        # Скрываем сервера без доступных тарифов (с учётом режима отображения)
        try:
            hosts_with_plans = [h for h in hosts if filter_plans_by_display_mode(get_plans_for_host(h['host_name']), user_id)]
        except Exception:
            hosts_with_plans = hosts
        if not hosts_with_plans:
            await callback.message.edit_text("❌ В данный момент нет доступных серверов для покупки.")
            return
        user_keys = get_user_keys(user_id)
        await callback.message.edit_text(
            "Выберите сервер, на котором хотите приобрести ключ:",
            # Назад ведёт к выбору услуги
            reply_markup=keyboards.create_host_selection_keyboard(hosts_with_plans, action="new", total_keys_count=len(user_keys) if user_keys else 0, back_to="buy_vpn_root")
        )

    @user_router.message(F.text == "⁉️ Помощь и поддержка")
    @documents_consent_required
    @subscription_required
    @measure_performance("help_center_message")
    async def help_center_message_handler(message: types.Message):
        # Получаем контент поддержки из настроек
        support_content = get_setting("support_content")
        
        # Определяем текст для отображения
        if support_content and support_content.strip():
            # Убираем HTML теги, которые не поддерживает Telegram
            import re
            display_text = re.sub(r'<[^>]+>', '', support_content)
        else:
            display_text = "⁉️ Помощь и поддержка:"
        
        await message.answer(display_text, reply_markup=keyboards.create_help_center_keyboard())

    @user_router.callback_query(F.data == "help_center")
    @documents_consent_required
    @subscription_required
    @measure_performance("help_center")
    async def help_center_callback_handler(callback: types.CallbackQuery):
        await callback.answer()
        
        # Получаем контент поддержки из настроек
        support_content = get_setting("support_content")
        
        # Определяем текст для отображения
        if support_content and support_content.strip():
            # Убираем HTML теги, которые не поддерживает Telegram
            import re
            display_text = re.sub(r'<[^>]+>', '', support_content)
        else:
            display_text = "⁉️ Помощь и поддержка:"
        
        await callback.message.edit_text(display_text, reply_markup=keyboards.create_help_center_keyboard())

    @user_router.message(F.text == "💰Пополнить баланс")
    @documents_consent_required
    @subscription_required
    @measure_performance("topup_message")
    async def topup_message_handler(message: types.Message, state: FSMContext):
        await state.clear()
        # Запоминаем источник входа в пополнение (главное меню)
        await state.update_data(topup_origin="main")
        await message.answer(
            "Выберите сумму пополнения:",
            reply_markup=keyboards.create_topup_amounts_keyboard()
        )

    @user_router.callback_query(F.data == "topup_root")
    @documents_consent_required
    @subscription_required
    @measure_performance("topup_root")
    async def topup_root_handler(callback: types.CallbackQuery, state: FSMContext):
        await callback.answer()
        await state.clear()
        # Запоминаем источник входа в пополнение (профиль)
        await state.update_data(topup_origin="profile")
        await callback.message.edit_text(
            "Выберите сумму пополнения:",
            reply_markup=keyboards.create_topup_amounts_keyboard()
        )

    @user_router.callback_query(F.data.in_(
        {"topup_amount_150","topup_amount_300","topup_amount_500"}
    ))
    @registration_required
    @measure_performance("topup_select_preset")
    async def topup_select_preset_handler(callback: types.CallbackQuery, state: FSMContext):
        await callback.answer()
        mapping = {
            "topup_amount_150": 150,
            "topup_amount_300": 300,
            "topup_amount_500": 500
        }
        amount = mapping.get(callback.data, 0)
        await state.update_data(topup_amount=amount)
        await callback.message.edit_text(
            f"Сумма пополнения: {amount} RUB\n\nВыберите способ оплаты:",
            reply_markup=keyboards.create_topup_payment_methods_keyboard()
        )
        await state.set_state(TopupProcess.waiting_for_payment_method)

    @user_router.callback_query(F.data == "topup_amount_custom")
    @registration_required
    @measure_performance("topup_custom_amount")
    async def topup_custom_amount_prompt(callback: types.CallbackQuery, state: FSMContext):
        await callback.answer()
        # Создаем клавиатуру с кнопкой "Назад"
        back_keyboard = InlineKeyboardBuilder()
        back_keyboard.button(text="⬅️ Назад", callback_data="topup_back_to_amounts")
        back_keyboard.adjust(1)
        
        await callback.message.edit_text(
            "Введите сумму пополнения в рублях (целое число)",
            reply_markup=back_keyboard.as_markup()
        )
        await state.set_state(TopupProcess.waiting_for_custom_amount)

    @user_router.message(TopupProcess.waiting_for_custom_amount)
    @measure_performance("topup_custom_amount_receive")
    async def topup_custom_amount_receive(message: types.Message, state: FSMContext):
        # Создаем клавиатуру с кнопкой "Назад" для случаев ошибки
        back_keyboard = InlineKeyboardBuilder()
        back_keyboard.button(text="⬅️ Назад", callback_data="topup_back_to_amounts")
        back_keyboard.adjust(1)
        
        try:
            amount = int(message.text.strip())
            try:
                min_topup = int(get_setting("minimum_topup") or 50)
            except Exception:
                min_topup = 50
            if amount < min_topup:
                await message.answer(
                    f"Минимальная сумма пополнения {min_topup} RUB. Введите другую сумму:",
                    reply_markup=back_keyboard.as_markup()
                )
                return
        except Exception:
            await message.answer(
                "Введите корректное целое число в рублях:",
                reply_markup=back_keyboard.as_markup()
            )
            return
        await state.update_data(topup_amount=amount)
        await message.answer(
            f"Сумма пополнения: {amount} RUB\n\nВыберите способ оплаты:",
            reply_markup=keyboards.create_topup_payment_methods_keyboard()
        )
        await state.set_state(TopupProcess.waiting_for_payment_method)

    @user_router.callback_query(TopupProcess.waiting_for_custom_amount, F.data == "topup_back_to_amounts")
    @registration_required
    @measure_performance("topup_back_from_custom_amount")
    async def topup_back_from_custom_amount(callback: types.CallbackQuery, state: FSMContext):
        """Обработчик кнопки 'Назад' при вводе пользовательской суммы"""
        await callback.answer()
        await state.clear()
        await callback.message.edit_text(
            "Выберите сумму пополнения:",
            reply_markup=keyboards.create_topup_amounts_keyboard()
        )

    @user_router.callback_query(TopupProcess.waiting_for_payment_method, F.data == "topup_back_to_amounts")
    @registration_required
    @measure_performance("topup_back_to_amounts")
    async def topup_back_to_amounts(callback: types.CallbackQuery, state: FSMContext):
        await callback.answer()
        await state.clear()
        await callback.message.edit_text(
            "Выберите сумму пополнения:",
            reply_markup=keyboards.create_topup_amounts_keyboard()
        )

    @user_router.callback_query(F.data == "topup_back_to_origin")
    @registration_required
    @measure_performance("topup_back_to_origin")
    async def topup_back_to_origin_handler(callback: types.CallbackQuery, state: FSMContext):
        await callback.answer()
        data = await state.get_data()
        origin = data.get("topup_origin", "main")
        await state.clear()
        if origin == "profile":
            # Возврат в профиль
            user_id = callback.from_user.id
            user_db_data = get_user(user_id)
            user_keys = get_user_keys(user_id)
            if not user_db_data:
                await callback.message.edit_text("Не удалось получить данные профиля.")
                return
            username = html.bold(user_db_data.get('username', 'Пользователь'))
            total_spent, total_months = user_db_data.get('total_spent', 0), user_db_data.get('total_months', 0)
            from shop_bot.data_manager.database import get_user_balance, get_setting, get_auto_renewal_enabled
            balance = get_user_balance(user_id)
            auto_renewal_enabled = get_auto_renewal_enabled(user_id)
            now = datetime.now()
            active_keys = [key for key in user_keys if datetime.fromisoformat(key['expiry_date']) > now]
            if active_keys:
                latest_key = max(active_keys, key=lambda k: datetime.fromisoformat(k['expiry_date']))
                latest_expiry_date = datetime.fromisoformat(latest_key['expiry_date'])
                time_left = latest_expiry_date - now
                vpn_status_text = get_vpn_active_text(time_left.days, time_left.seconds // 3600)
            elif user_keys: vpn_status_text = VPN_INACTIVE_TEXT
            else: vpn_status_text = VPN_NO_DATA_TEXT
            trial_used = user_db_data.get('trial_used', 1) if user_db_data else 1
            referral_balance = user_db_data.get('referral_balance', 0)
            show_referral = get_setting("enable_referrals") == "true"
            referral_link = None
            referral_percentage = None
            if show_referral:
                bot_username = (await callback.bot.get_me()).username
                referral_link = f"https://t.me/{bot_username}?start=ref_{user_id}"
                referral_percentage = get_setting("referral_percentage") or "10"
            final_text = get_profile_text(username, balance, total_spent, total_months, vpn_status_text, referral_balance, show_referral, referral_link, referral_percentage, auto_renewal_enabled)
            await callback.message.edit_text(final_text, reply_markup=keyboards.create_profile_menu_keyboard(total_keys_count=len(user_keys or []), trial_used=trial_used, auto_renewal_enabled=auto_renewal_enabled))
        else:
            # Возврат в главное меню
            try:
                await callback.message.edit_text("🏠 <b>Главное меню</b>\n\nВыберите действие:", reply_markup=None)
            except Exception:
                pass
            await show_main_menu(callback.message)
    @user_router.message(F.text == "👤 Мой профиль")
    @documents_consent_required
    @subscription_required
    @measure_performance("profile_handler")
    async def profile_handler_message(message: types.Message):
        user_id = message.from_user.id
        user_db_data = get_user(user_id)
        user_keys = get_user_keys(user_id)
        if not user_db_data:
            await message.answer("Не удалось получить данные профиля.")
            return
        username = html.bold(user_db_data.get('username', 'Пользователь'))
        total_spent, total_months = user_db_data.get('total_spent', 0), user_db_data.get('total_months', 0)
        from shop_bot.data_manager.database import get_user_balance, get_setting, get_auto_renewal_enabled
        balance = get_user_balance(user_id)
        auto_renewal_enabled = get_auto_renewal_enabled(user_id)
        now = datetime.now()
        active_keys = [key for key in user_keys if datetime.fromisoformat(key['expiry_date']) > now]
        if active_keys:
            latest_key = max(active_keys, key=lambda k: datetime.fromisoformat(k['expiry_date']))
            latest_expiry_date = datetime.fromisoformat(latest_key['expiry_date'])
            time_left = latest_expiry_date - now
            vpn_status_text = get_vpn_active_text(time_left.days, time_left.seconds // 3600)
        elif user_keys: vpn_status_text = VPN_INACTIVE_TEXT
        else: vpn_status_text = VPN_NO_DATA_TEXT
        trial_used = user_db_data.get('trial_used', 1) if user_db_data else 1
        
        # Получаем реферальный баланс и проверяем, включена ли реферальная система
        referral_balance = user_db_data.get('referral_balance', 0)
        show_referral = get_setting("enable_referrals") == "true"
        
        # Формируем реферальную ссылку и получаем процент вознаграждения
        referral_link = None
        referral_percentage = None
        if show_referral:
            bot_username = (await message.bot.get_me()).username
            referral_link = f"https://t.me/{bot_username}?start=ref_{user_id}"
            referral_percentage = get_setting("referral_percentage") or "10"
        
        # Получаем timezone для отображения
        from shop_bot.data_manager.database import get_user_timezone
        from shop_bot.data.timezones import get_timezone_display_name
        user_timezone = get_user_timezone(user_id)
        timezone_display = get_timezone_display_name(user_timezone) if user_timezone else None
        
        final_text = get_profile_text(username, balance, total_spent, total_months, vpn_status_text, referral_balance, show_referral, referral_link, referral_percentage, auto_renewal_enabled, timezone_display)
        await message.answer(final_text, reply_markup=keyboards.create_profile_menu_keyboard(total_keys_count=len(user_keys or []), trial_used=trial_used, auto_renewal_enabled=auto_renewal_enabled))

    @user_router.message(F.text == "🔑 Мои ключи")
    @registration_required
    async def manage_keys_message(message: types.Message):
        user_id = message.from_user.id
        user_keys = get_user_keys(user_id)
        user_db_data = get_user(user_id)
        trial_used = user_db_data.get('trial_used', 1) if user_db_data else 1
        
        menu_text = """=== Мои ключи ===
Условные обозначения:
<blockquote>
1. Статус иконка: ✅ для активных, ❌ для истёкших/деактивированных
2. Порядковый номер ключа
3. Страна сервера ключа
4. Название тарифа
5. Цена
6. Дата окончания
7. Автопродление ключа: 🟢 включено, 🔴 выключено
</blockquote>""" if user_keys else "У вас пока нет ключей."
        
        await message.answer(
            menu_text,
            reply_markup=keyboards.create_keys_management_keyboard(user_keys, trial_used),
            parse_mode="HTML"
        )

    @user_router.callback_query(F.data == "trial_period")
    @documents_consent_required
    @subscription_required
    @measure_performance("trial_period_callback")
    async def trial_period_callback_handler(callback: types.CallbackQuery):
        """Обработчик кнопки 'Пробный период' из меню профиля"""
        await callback.answer()
        user_id = callback.from_user.id
        user_db_data = get_user(user_id)
        
        # Проверяем, использовал ли пользователь триал и есть ли у него повторные использования
        trial_used = user_db_data.get('trial_used', 0) if user_db_data else 0
        trial_reuses_count = user_db_data.get('trial_reuses_count', 0) if user_db_data else 0
        
        # Если триал использован и нет повторных использований - запрещаем
        if trial_used and trial_reuses_count == 0:
            await callback.message.edit_text("Вы уже использовали бесплатный пробный период.")
            return
        
        # Дополнительная проверка: нет ли активных триальных ключей (только с активным статусом)
        user_keys = get_user_keys(user_id)
        active_trial_keys = [key for key in user_keys if key.get('is_trial') == 1 and key.get('remaining_seconds', 0) > 0 and key.get('status') != 'deactivate']
        if active_trial_keys:
            await callback.message.edit_text("У вас уже есть активный пробный ключ.")
            return

        # Получаем список доступных хостов
        hosts = get_all_hosts()
        if not hosts:
            await callback.message.edit_text("❌ В данный момент нет доступных серверов для создания пробного ключа.")
            return

        # Если только один хост, сразу создаем пробный ключ
        if len(hosts) == 1:
            await process_trial_key_creation_callback(callback, hosts[0]['host_name'])
        else:
            # Если несколько хостов, показываем выбор
            await callback.message.edit_text(
                "Выберите сервер для создания пробного ключа:",
                reply_markup=keyboards.create_host_selection_keyboard(hosts, action="trial", back_to="buy_vpn_service_selection")
            )

    @user_router.callback_query(F.data == "toggle_auto_renewal")
    @documents_consent_required
    @subscription_required
    @measure_performance("toggle_auto_renewal")
    async def toggle_auto_renewal_handler(callback: types.CallbackQuery):
        """Обработчик переключения автопродления с баланса"""
        await callback.answer()
        user_id = callback.from_user.id
        from shop_bot.data_manager.database import get_auto_renewal_enabled, set_auto_renewal_enabled, get_user, get_user_keys
        
        # Получаем текущий статус
        current_status = get_auto_renewal_enabled(user_id)
        new_status = not current_status
        
        # Устанавливаем новый статус
        if set_auto_renewal_enabled(user_id, new_status):
            status_text = "включено" if new_status else "отключено"
            status_emoji = "🟢" if new_status else "🔴"
            
            # Получаем данные для обновления клавиатуры
            user_db_data = get_user(user_id)
            user_keys = get_user_keys(user_id)
            trial_used = user_db_data.get('trial_used', 1) if user_db_data else 1
            
            # Обновляем сообщение с новым статусом
            await callback.message.edit_reply_markup(
                reply_markup=keyboards.create_profile_menu_keyboard(
                    total_keys_count=len(user_keys or []),
                    trial_used=trial_used,
                    auto_renewal_enabled=new_status
                )
            )
            
            # Отправляем подтверждающее сообщение
            message_text = (
                f"✅ Автопродление с баланса {status_text} {status_emoji}\n\n"
            )
            if new_status:
                message_text += (
                    "Теперь при истечении срока действия ключа и достаточном балансе "
                    "продление будет происходить автоматически. Спасибо, что остаётесь с нами! ❤️"
                )
            else:
                message_text += (
                    "Автоматическое списание с баланса отключено. "
                    "Вы сможете продлить ключ вручную в любое время."
                )
            
            await callback.message.answer(message_text)
        else:
            await callback.message.answer("❌ Произошла ошибка при изменении настроек. Попробуйте позже.")

    @user_router.callback_query(F.data == "change_timezone")
    @documents_consent_required
    @subscription_required
    @measure_performance("change_timezone")
    async def timezone_change_handler(callback: types.CallbackQuery):
        """Обработчик кнопки изменения часового пояса"""
        await callback.answer()
        user_id = callback.from_user.id
        from shop_bot.data_manager.database import get_user_timezone
        
        # Получаем текущий часовой пояс пользователя
        current_timezone = get_user_timezone(user_id)
        
        # Показываем список часовых поясов
        await callback.message.edit_text(
            "🌍 <b>Выбор часового пояса</b>\n\n"
            "Выберите ваш часовой пояс из списка ниже.\n"
            "Это повлияет на отображение дат и времени в боте.",
            reply_markup=keyboards.create_timezone_selection_keyboard(page=0, current_timezone=current_timezone),
            parse_mode="HTML"
        )

    @user_router.callback_query(F.data.startswith("tz_page:"))
    @documents_consent_required
    @subscription_required
    @measure_performance("timezone_page_navigation")
    async def timezone_page_handler(callback: types.CallbackQuery):
        """Обработчик навигации по страницам часовых поясов"""
        await callback.answer()
        user_id = callback.from_user.id
        from shop_bot.data_manager.database import get_user_timezone
        
        # Извлекаем номер страницы из callback_data
        page = int(callback.data.split(":")[1])
        
        # Получаем текущий часовой пояс пользователя
        current_timezone = get_user_timezone(user_id)
        
        # Обновляем клавиатуру с новой страницей
        try:
            await callback.message.edit_reply_markup(
                reply_markup=keyboards.create_timezone_selection_keyboard(page=page, current_timezone=current_timezone)
            )
        except TelegramBadRequest as e:
            # Если сообщение не изменилось, просто игнорируем
            if "message is not modified" not in str(e).lower():
                raise

    @user_router.callback_query(F.data == "tz_page_info")
    async def timezone_page_info_handler(callback: types.CallbackQuery):
        """Обработчик кнопки информации о странице (ничего не делает)"""
        await callback.answer()

    @user_router.callback_query(F.data.startswith("select_tz:"))
    @documents_consent_required
    @subscription_required
    @measure_performance("timezone_select")
    async def timezone_select_handler(callback: types.CallbackQuery):
        """Обработчик выбора часового пояса"""
        await callback.answer()
        user_id = callback.from_user.id
        
        # Извлекаем timezone из callback_data
        timezone_name = callback.data.split(":", 1)[1]
        
        # Валидируем timezone
        from shop_bot.data.timezones import validate_timezone, get_timezone_display_name
        if not validate_timezone(timezone_name):
            await callback.answer("❌ Неверный часовой пояс", show_alert=True)
            return
        
        # Получаем отображаемое имя
        timezone_display = get_timezone_display_name(timezone_name)
        
        # Показываем текущее время в выбранном часовом поясе
        from datetime import datetime, timezone as dt_timezone
        from zoneinfo import ZoneInfo
        from shop_bot.utils.datetime_utils import format_datetime_for_user
        try:
            tz = ZoneInfo(timezone_name)
            current_dt = format_datetime_for_user(
                datetime.now(dt_timezone.utc),
                user_timezone=timezone_name,
                feature_enabled=True,
            )
        except Exception as e:
            logger.error(f"Error getting time for timezone {timezone_name}: {e}")
            current_dt = "—"
        
        # Показываем подтверждение с текущим временем
        await callback.message.edit_text(
            f"🌍 <b>Подтверждение выбора часового пояса</b>\n\n"
            f"<b>Выбран:</b> {timezone_display}\n\n"
            f"<b>Текущая дата и время:</b> {current_dt}\n\n"
            f"Подтвердите выбор часового пояса:",
            reply_markup=keyboards.create_timezone_confirmation_keyboard(timezone_name),
            parse_mode="HTML"
        )

    @user_router.callback_query(F.data.startswith("confirm_tz:"))
    @documents_consent_required
    @subscription_required
    @measure_performance("timezone_confirm")
    async def timezone_confirm_handler(callback: types.CallbackQuery):
        """Обработчик подтверждения выбора часового пояса"""
        await callback.answer()
        user_id = callback.from_user.id
        
        # Извлекаем timezone из callback_data
        timezone_name = callback.data.split(":", 1)[1]
        
        # Валидируем timezone
        from shop_bot.data.timezones import validate_timezone, get_timezone_display_name
        if not validate_timezone(timezone_name):
            await callback.answer("❌ Неверный часовой пояс", show_alert=True)
            return
        
        # Сохраняем timezone в БД
        from shop_bot.data_manager.database import set_user_timezone
        set_user_timezone(user_id, timezone_name)
        
        # Получаем отображаемое имя
        timezone_display = get_timezone_display_name(timezone_name)
        
        # Возвращаемся в профиль с обновлёнными данными
        user_db_data = get_user(user_id)
        user_keys = get_user_keys(user_id)
        if not user_db_data:
            await callback.answer("Не удалось получить данные профиля.", show_alert=True)
            return
        
        username = html.bold(user_db_data.get('username', 'Пользователь'))
        total_spent, total_months = user_db_data.get('total_spent', 0), user_db_data.get('total_months', 0)
        from shop_bot.data_manager.database import get_user_balance, get_setting, get_auto_renewal_enabled
        balance = get_user_balance(user_id)
        auto_renewal_enabled = get_auto_renewal_enabled(user_id)
        now = datetime.now()
        active_keys = [key for key in user_keys if datetime.fromisoformat(key['expiry_date']) > now]
        if active_keys:
            latest_key = max(active_keys, key=lambda k: datetime.fromisoformat(k['expiry_date']))
            latest_expiry_date = datetime.fromisoformat(latest_key['expiry_date'])
            time_left = latest_expiry_date - now
            vpn_status_text = get_vpn_active_text(time_left.days, time_left.seconds // 3600)
        elif user_keys: vpn_status_text = VPN_INACTIVE_TEXT
        else: vpn_status_text = VPN_NO_DATA_TEXT
        
        trial_used = user_db_data.get('trial_used', 1) if user_db_data else 1
        
        # Получаем реферальный баланс и проверяем, включена ли реферальная система
        referral_balance = user_db_data.get('referral_balance', 0)
        show_referral = get_setting("enable_referrals") == "true"
        
        # Формируем реферальную ссылку и получаем процент вознаграждения
        referral_link = None
        referral_percentage = None
        if show_referral:
            bot_username = (await callback.bot.get_me()).username
            referral_link = f"https://t.me/{bot_username}?start=ref_{user_id}"
            referral_percentage = get_setting("referral_percentage") or "10"
        
        # Формируем текст профиля с новым часовым поясом
        final_text = get_profile_text(
            username, balance, total_spent, total_months, vpn_status_text, 
            referral_balance, show_referral, referral_link, referral_percentage, 
            auto_renewal_enabled, timezone_display
        )
        
        await callback.message.edit_text(
            final_text, 
            reply_markup=keyboards.create_profile_menu_keyboard(
                total_keys_count=len(user_keys or []), 
                trial_used=trial_used, 
                auto_renewal_enabled=auto_renewal_enabled
            )
        )
        
        # Отправляем подтверждающее сообщение
        await callback.message.answer(f"✅ Часовой пояс изменён на {timezone_display}")

    @user_router.callback_query(F.data == "back_to_profile")
    @documents_consent_required
    @subscription_required
    async def back_to_profile_handler(callback: types.CallbackQuery):
        """Обработчик возврата в профиль"""
        await callback.answer()
        user_id = callback.from_user.id
        user_db_data = get_user(user_id)
        user_keys = get_user_keys(user_id)
        if not user_db_data:
            await callback.answer("Не удалось получить данные профиля.", show_alert=True)
            return
        
        username = html.bold(user_db_data.get('username', 'Пользователь'))
        total_spent, total_months = user_db_data.get('total_spent', 0), user_db_data.get('total_months', 0)
        from shop_bot.data_manager.database import get_user_balance, get_setting, get_auto_renewal_enabled, get_user_timezone
        from shop_bot.data.timezones import get_timezone_display_name
        balance = get_user_balance(user_id)
        auto_renewal_enabled = get_auto_renewal_enabled(user_id)
        
        # Получаем timezone для отображения
        user_timezone = get_user_timezone(user_id)
        timezone_display = get_timezone_display_name(user_timezone) if user_timezone else None
        
        now = datetime.now()
        active_keys = [key for key in user_keys if datetime.fromisoformat(key['expiry_date']) > now]
        if active_keys:
            latest_key = max(active_keys, key=lambda k: datetime.fromisoformat(k['expiry_date']))
            latest_expiry_date = datetime.fromisoformat(latest_key['expiry_date'])
            time_left = latest_expiry_date - now
            vpn_status_text = get_vpn_active_text(time_left.days, time_left.seconds // 3600)
        elif user_keys: vpn_status_text = VPN_INACTIVE_TEXT
        else: vpn_status_text = VPN_NO_DATA_TEXT
        
        trial_used = user_db_data.get('trial_used', 1) if user_db_data else 1
        
        # Получаем реферальный баланс и проверяем, включена ли реферальная система
        referral_balance = user_db_data.get('referral_balance', 0)
        show_referral = get_setting("enable_referrals") == "true"
        
        # Формируем реферальную ссылку и получаем процент вознаграждения
        referral_link = None
        referral_percentage = None
        if show_referral:
            bot_username = (await callback.bot.get_me()).username
            referral_link = f"https://t.me/{bot_username}?start=ref_{user_id}"
            referral_percentage = get_setting("referral_percentage") or "10"
        
        final_text = get_profile_text(
            username, balance, total_spent, total_months, vpn_status_text, 
            referral_balance, show_referral, referral_link, referral_percentage, 
            auto_renewal_enabled, timezone_display
        )
        
        await callback.message.edit_text(
            final_text, 
            reply_markup=keyboards.create_profile_menu_keyboard(
                total_keys_count=len(user_keys or []), 
                trial_used=trial_used, 
                auto_renewal_enabled=auto_renewal_enabled
            )
        )

    @user_router.callback_query(F.data == "promo_code")
    @documents_consent_required
    @subscription_required
    @measure_performance("promo_code")
    async def promo_code_handler(callback: types.CallbackQuery):
        """Обработчик кнопки 'Промокод'"""
        await callback.answer()
        await callback.message.edit_text(
            "🎫 <b>Промокоды</b>\n\n"
            "Введите промокод для получения скидки или бонуса.\n\n"
            "Если у вас есть промокод, отправьте его текстовым сообщением.\n\n"
            "Пример: <code>HABITAT</code>",
            reply_markup=keyboards.create_back_to_menu_keyboard()
        )

    @user_router.callback_query(F.data == "my_promo_codes")
    @documents_consent_required
    @subscription_required
    @measure_performance("my_promo_codes")
    async def my_promo_codes_handler(callback: types.CallbackQuery):
        """Обработчик кнопки 'Мои промокоды' в профиле"""
        await callback.answer()
        
        user_id = callback.from_user.id
        from shop_bot.data_manager.database import get_user_promo_codes
        
        # Получаем использованные промокоды пользователя
        user_promo_codes = get_user_promo_codes(user_id, "shop")
        
        if not user_promo_codes:
            await callback.message.edit_text(
                "🎫 <b>Применить промокод</b>\n\n"
                "У вас пока нет использованных промокодов.\n\n"
                "Чтобы использовать промокод:\n"
                "1. Введите промокод текстом в чат\n"
                "2. Следуйте инструкциям для применения\n\n"
                "Промокоды можно вводить в любое время в чате!",
                reply_markup=keyboards.create_back_to_menu_keyboard()
            )
        else:
            text = "🎫 <b>Применить промокод</b>\n\n"
            text += f"Использовано промокодов: <b>{len(user_promo_codes)}</b>\n\n"
            
            for i, promo in enumerate(user_promo_codes, 1):
                text += f"<b>{i}. {promo['code']}</b>\n"
                text += f"📅 Использован: {promo['used_at'][:10]}\n"
                
                # Добавляем описание скидки
                if promo['discount_amount'] > 0:
                    text += f"💰 Скидка: {promo['discount_amount']} руб.\n"
                if promo['discount_percent'] > 0:
                    text += f"📊 Скидка: {promo['discount_percent']}%\n"
                if promo['discount_bonus'] > 0:
                    text += f"🎁 Бонус: {promo['discount_bonus']} руб.\n"
                
                if promo['plan_name']:
                    text += f"🔗 Тариф: {promo['plan_name']}\n"
                
                text += "\n"
            
            await callback.message.edit_text(
                text,
                reply_markup=keyboards.create_user_promo_codes_keyboard(user_promo_codes)
            )

    @user_router.callback_query(F.data.startswith("remove_promo_"))
    @documents_consent_required
    @subscription_required
    @measure_performance("remove_promo_code")
    async def remove_promo_code_handler(callback: types.CallbackQuery):
        """Обработчик удаления применённого промокода"""
        await callback.answer()
        
        # Извлекаем usage_id из callback_data
        usage_id = int(callback.data.replace("remove_promo_", ""))
        user_id = callback.from_user.id
        
        try:
            from shop_bot.data_manager.database import remove_user_promo_code_usage, get_user_promo_codes
            
            # Удаляем промокод
            success = remove_user_promo_code_usage(user_id, usage_id, "shop")
            
            if success:
                # Получаем обновленный список промокодов
                user_promo_codes = get_user_promo_codes(user_id, "shop")
                
                if not user_promo_codes:
                    # Если промокодов больше нет, показываем пустое состояние
                    await callback.message.edit_text(
                        "🎫 <b>Применить промокод</b>\n\n"
                        "✅ Промокод успешно удален!\n\n"
                        "У вас пока нет использованных промокодов.\n\n"
                        "Чтобы использовать промокод:\n"
                        "1. Введите промокод текстом в чат\n"
                        "2. Следуйте инструкциям для применения\n\n"
                        "Промокоды можно вводить в любое время в чате!",
                        reply_markup=keyboards.create_back_to_menu_keyboard()
                    )
                else:
                    # Обновляем список промокодов
                    text = "🎫 <b>Применить промокод</b>\n\n"
                    text += f"✅ Промокод успешно удален!\n\n"
                    text += f"Использовано промокодов: <b>{len(user_promo_codes)}</b>\n\n"
                    
                    for i, promo in enumerate(user_promo_codes, 1):
                        text += f"<b>{i}. {promo['code']}</b>\n"
                        text += f"📅 Использован: {promo['used_at'][:10]}\n"
                        
                        # Добавляем описание скидки
                        if promo['discount_amount'] > 0:
                            text += f"💰 Скидка: {promo['discount_amount']} руб.\n"
                        if promo['discount_percent'] > 0:
                            text += f"📊 Скидка: {promo['discount_percent']}%\n"
                        if promo['discount_bonus'] > 0:
                            text += f"🎁 Бонус: {promo['discount_bonus']} руб.\n"
                        
                        if promo['plan_name']:
                            text += f"🔗 Тариф: {promo['plan_name']}\n"
                        
                        text += "\n"
                    
                    await callback.message.edit_text(
                        text,
                        reply_markup=keyboards.create_user_promo_codes_keyboard(user_promo_codes)
                    )
            else:
                await callback.answer("❌ Не удалось удалить промокод. Попробуйте еще раз.", show_alert=True)
                
        except Exception as e:
            logger.error(f"Error removing promo code: {e}", exc_info=True)
            await callback.answer("❌ Произошла ошибка при удалении промокода.", show_alert=True)

    @user_router.message(F.text == "🆓 Пробный период")
    @documents_consent_required
    @subscription_required
    @measure_performance("trial_period_message")
    async def trial_period_message_handler(message: types.Message):
        """Обработчик кнопки 'Пробный период' из главного меню"""
        user_id = message.from_user.id
        user_db_data = get_user(user_id)
        
        # Проверяем, использовал ли пользователь триал и есть ли у него повторные использования
        trial_used = user_db_data.get('trial_used', 0) if user_db_data else 0
        trial_reuses_count = user_db_data.get('trial_reuses_count', 0) if user_db_data else 0
        
        # Если триал использован и нет повторных использований - запрещаем
        if trial_used and trial_reuses_count == 0:
            await message.answer("Вы уже использовали бесплатный пробный период.", show_alert=True)
            return
        
        # Дополнительная проверка: нет ли активных триальных ключей (только с активным статусом)
        user_keys = get_user_keys(user_id)
        active_trial_keys = [key for key in user_keys if key.get('is_trial') == 1 and key.get('remaining_seconds', 0) > 0 and key.get('status') != 'deactivate']
        if active_trial_keys:
            await message.answer("У вас уже есть активный пробный ключ.")
            return

        # Получаем список доступных хостов
        hosts = get_all_hosts()
        if not hosts:
            await message.answer("❌ В данный момент нет доступных серверов для создания пробного ключа.")
            return

        # Если только один хост, сразу создаем пробный ключ
        if len(hosts) == 1:
            await process_trial_key_creation(message, hosts[0]['host_name'])
        else:
            # Если несколько хостов, показываем выбор
            await message.answer(
                "Выберите сервер для создания пробного ключа:",
                reply_markup=keyboards.create_host_selection_keyboard(hosts, action="trial", back_to="buy_vpn_service_selection")
            )

    @user_router.message(F.text == "🤝 Реферальная программа")
    @registration_required
    async def referral_program_message(message: types.Message):
        user_id = message.from_user.id
        user_data = get_user(user_id)
        bot_username = (await message.bot.get_me()).username
        referral_link = f"https://t.me/{bot_username}?start=ref_{user_id}"
        referral_count = get_referral_count(user_id)
        balance = user_data.get('referral_balance', 0) if user_data else 0
        from shop_bot.data_manager.database import get_setting
        min_withdraw = get_setting("minimum_withdrawal") or "100"
        referral_percentage = get_setting("referral_percentage") or "10"
        text = (
            "🤝 <b>Реферальная программа</b>\n\n"
            f"🗣 Приглашай друзей и получайте {referral_percentage}% от их расходов, которые затем ты сможешь вывести на свой счет! Вывод доступен от {min_withdraw} руб.\n\n"
            f"<b>Ваша реферальная ссылка:</b>\n<code>{referral_link}</code>\n\n"
            f"<b>Приглашено пользователей:</b> {referral_count}\n"
            f"<b>Ваш баланс:</b> {balance:.2f} руб."
        )
        builder = InlineKeyboardBuilder()
        if balance >= 100:
            builder.button(text="💸 Оставить заявку на вывод средств", callback_data="withdraw_request")
        # Возврат в профиль
        builder.button(text="⬅️ Назад", callback_data="show_profile")
        builder.adjust(1)
        await message.answer(text, reply_markup=builder.as_markup())

    @user_router.message(F.text == "🆘 Поддержка")
    @registration_required
    async def support_message(message: types.Message):
        from shop_bot.data_manager.database import get_setting
        if get_setting("support_enabled") != "true":
            await message.answer(
                "Раздел поддержки недоступен.",
                reply_markup=keyboards.create_back_to_menu_keyboard()
            )
            return
        support_user = get_setting("support_user")
        support_text = get_setting("support_content")
        
        # Проверяем, есть ли отдельный бот поддержки
        support_bot_token = get_setting("support_bot_token")
        support_group_id = get_setting("support_group_id")
        
        if support_bot_token and support_group_id:
            # Если настроен отдельный бот поддержки, перенаправляем к нему
            support_url = support_user if support_user and support_user.startswith('https://') else f"https://t.me/{support_user.replace('@', '')}" if support_user else None
            
            if support_url:
                await message.answer(
                    "Для получения поддержки перейдите к нашему боту поддержки:",
                    reply_markup=keyboards.create_support_keyboard(support_url)
                )
            else:
                await message.answer(
                    "Служба поддержки временно недоступна.",
                    reply_markup=keyboards.create_back_to_menu_keyboard()
                )
        elif support_user == None and support_text == None:
            await message.answer(
                "Информация о поддержке не установлена. Установите её в админ-панели.",
                reply_markup=keyboards.create_back_to_menu_keyboard()
            )
        else:
            # Обрабатываем username бота как URL
            if support_user and support_user.startswith('@'):
                support_url = f"https://t.me/{support_user.replace('@', '')}"
            else:
                support_url = support_user or ""
            
            # Определяем текст для отображения
            if support_text:
                display_text = support_text + "\n\n"
            else:
                display_text = "Для связи с поддержкой используйте кнопку ниже.\n\n"
            
            await message.answer(
                display_text,
                reply_markup=keyboards.create_support_keyboard(support_url)
            )

    @user_router.message(Command("reset_terms"))
    async def reset_terms_command(message: types.Message):
        """Команда для сброса статуса согласия с условиями (для тестирования)"""
        user_id = message.from_user.id
        is_admin = str(user_id) == ADMIN_ID
        
        if not is_admin:
            await message.answer("❌ У вас нет прав для выполнения этой команды.")
            return
            
        # Сбрасываем статус согласия
        set_terms_agreed(user_id, False)
        await message.answer("✅ Статус согласия сброшен. Теперь при следующем /start будет показана проверка подписки.")

    @user_router.message(F.text == "ℹ️ О проекте")
    @documents_consent_required
    @subscription_required
    async def about_message(message: types.Message):
        about_text = get_setting("about_content")
        channel_url = get_setting("channel_url")
        
        # Получаем домен из настроек или используем дефолтный
        from shop_bot.data_manager.database import get_global_domain
        domain = get_global_domain()
        
        # Генерируем URL для страниц только если домен не localhost
        terms_url = None
        privacy_url = None
        if is_production_server() and domain and not _is_local_address(domain):
            terms_url = normalize_web_app_url(f"{domain.rstrip('/')}/terms")
            privacy_url = normalize_web_app_url(f"{domain.rstrip('/')}/privacy")
        
        final_text = about_text if about_text else "Информация о проекте не добавлена."
        
        # Убираем HTML теги, которые не поддерживает Telegram
        final_text = re.sub(r'<[^>]+>', '', final_text)
        
        # Проверяем, что текст не пустой
        if not final_text.strip():
            final_text = "Информация о проекте не добавлена."
        
        keyboard = keyboards.create_about_keyboard(channel_url, terms_url, privacy_url)
        await message.answer(final_text, reply_markup=keyboard, disable_web_page_preview=True)

    @user_router.message(F.text == "⚙️ Админ-панель")
    @documents_consent_required
    @subscription_required
    @measure_performance("admin_panel_message")
    async def admin_panel_message(message: types.Message):
        """Обработчик для админ-панели"""
        user_id = message.from_user.id
        is_admin = str(user_id) == ADMIN_ID
        
        if not is_admin:
            await message.answer("❌ У вас нет прав для доступа к админ-панели.")
            return
        
        text = "⚙️ <b>Админ-панель</b>\n\nВыберите действие:"
        keyboard = keyboards.create_admin_panel_keyboard()
        await message.answer(text, reply_markup=keyboard, parse_mode='HTML')

    @user_router.callback_query(F.data == "show_profile")
    @documents_consent_required
    @subscription_required
    @measure_performance("profile_handler_callback")
    async def profile_handler_callback(callback: types.CallbackQuery):
        await callback.answer()
        user_id = callback.from_user.id
        user_db_data = get_user(user_id)
        user_keys = get_user_keys(user_id)
        if not user_db_data:
            await callback.answer("Не удалось получить данные профиля.", show_alert=True)
            return
        username = html.bold(user_db_data.get('username', 'Пользователь'))
        total_spent, total_months = user_db_data.get('total_spent', 0), user_db_data.get('total_months', 0)
        from shop_bot.data_manager.database import get_user_balance, get_setting, get_auto_renewal_enabled
        balance = get_user_balance(user_id)
        auto_renewal_enabled = get_auto_renewal_enabled(user_id)
        now = datetime.now()
        active_keys = [key for key in user_keys if datetime.fromisoformat(key['expiry_date']) > now]
        if active_keys:
            latest_key = max(active_keys, key=lambda k: datetime.fromisoformat(k['expiry_date']))
            latest_expiry_date = datetime.fromisoformat(latest_key['expiry_date'])
            time_left = latest_expiry_date - now
            vpn_status_text = get_vpn_active_text(time_left.days, time_left.seconds // 3600)
        elif user_keys: vpn_status_text = VPN_INACTIVE_TEXT
        else: vpn_status_text = VPN_NO_DATA_TEXT
        
        trial_used = user_db_data.get('trial_used', 1) if user_db_data else 1
        
        # Получаем реферальный баланс и проверяем, включена ли реферальная система
        referral_balance = user_db_data.get('referral_balance', 0)
        show_referral = get_setting("enable_referrals") == "true"
        
        # Формируем реферальную ссылку и получаем процент вознаграждения
        referral_link = None
        referral_percentage = None
        if show_referral:
            bot_username = (await callback.bot.get_me()).username
            referral_link = f"https://t.me/{bot_username}?start=ref_{user_id}"
            referral_percentage = get_setting("referral_percentage") or "10"
        
        # Получаем timezone для отображения
        from shop_bot.data_manager.database import get_user_timezone
        from shop_bot.data.timezones import get_timezone_display_name
        user_timezone = get_user_timezone(user_id)
        timezone_display = get_timezone_display_name(user_timezone) if user_timezone else None
        
        final_text = get_profile_text(username, balance, total_spent, total_months, vpn_status_text, referral_balance, show_referral, referral_link, referral_percentage, auto_renewal_enabled, timezone_display)
        await callback.message.edit_text(final_text, reply_markup=keyboards.create_profile_menu_keyboard(total_keys_count=len(user_keys or []), trial_used=trial_used, auto_renewal_enabled=auto_renewal_enabled))

    @user_router.callback_query(F.data == "start_broadcast")
    @registration_required
    @measure_performance("start_broadcast")
    async def start_broadcast_handler(callback: types.CallbackQuery, state: FSMContext):
        if str(callback.from_user.id) != ADMIN_ID:
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        
        await callback.answer()
        await callback.message.edit_text(
            "Пришлите сообщение, которое вы хотите разослать всем пользователям.\n"
            "Вы можете использовать форматирование (<b>жирный</b>, <i>курсив</i>).\n"
            "Также поддерживаются фото, видео и документы.\n",
            reply_markup=keyboards.create_broadcast_cancel_keyboard()
        )
        await state.set_state(Broadcast.waiting_for_message)

    @user_router.message(Broadcast.waiting_for_message)
    @measure_performance("broadcast_message_received")
    async def broadcast_message_received_handler(message: types.Message, state: FSMContext):
        await state.update_data(message_to_send=message.model_dump_json())
        
        await message.answer(
            "Сообщение получено. Хотите добавить к нему кнопку со ссылкой?",
            reply_markup=keyboards.create_broadcast_options_keyboard()
        )
        await state.set_state(Broadcast.waiting_for_button_option)

    @user_router.callback_query(Broadcast.waiting_for_button_option, F.data == "broadcast_add_button")
    @measure_performance("add_button_prompt")
    async def add_button_prompt_handler(callback: types.CallbackQuery, state: FSMContext):
        await callback.answer()
        await callback.message.edit_text(
            "Хорошо. Теперь отправьте мне текст для кнопки.",
            reply_markup=keyboards.create_broadcast_cancel_keyboard()
        )
        await state.set_state(Broadcast.waiting_for_button_text)

    @user_router.message(Broadcast.waiting_for_button_text)
    @measure_performance("button_text_received")
    async def button_text_received_handler(message: types.Message, state: FSMContext):
        await state.update_data(button_text=message.text)
        await message.answer(
            "Текст кнопки получен. Теперь отправьте ссылку (URL), куда она будет вести.",
            reply_markup=keyboards.create_broadcast_cancel_keyboard()
        )
        await state.set_state(Broadcast.waiting_for_button_url)

    @user_router.message(Broadcast.waiting_for_button_url)
    @measure_performance("button_url_received")
    async def button_url_received_handler(message: types.Message, state: FSMContext, bot: Bot):
        url_to_check = message.text

        is_valid = await is_url_reachable(url_to_check)
        
        if not is_valid:
            await message.answer(
                "❌ **Ссылка не прошла проверку.**\n\n"
                "Пожалуйста, убедитесь, что:\n"
                "1. Ссылка начинается с `http://` или `https://`.\n"
                "2. Доменное имя корректно (например, `example.com`).\n"
                "3. Сайт доступен в данный момент.\n\n"
                "Попробуйте еще раз."
            )
            return

        await state.update_data(button_url=url_to_check)
        await show_broadcast_preview(message, state, bot)

    @user_router.callback_query(Broadcast.waiting_for_button_option, F.data == "broadcast_skip_button")
    @measure_performance("skip_button")
    async def skip_button_handler(callback: types.CallbackQuery, state: FSMContext, bot: Bot):
        await callback.answer()
        await state.update_data(button_text=None, button_url=None)
        await show_broadcast_preview(callback.message, state, bot)

    async def show_broadcast_preview(message: types.Message, state: FSMContext, bot: Bot):
        data = await state.get_data()
        message_json = data.get('message_to_send')
        original_message = types.Message.model_validate_json(message_json)
        
        button_text = data.get('button_text')
        button_url = data.get('button_url')
        
        preview_keyboard = None
        if button_text and button_url:
            builder = InlineKeyboardBuilder()
            builder.button(text=button_text, url=button_url)
            preview_keyboard = builder.as_markup()

        await message.answer(
            "Вот так будет выглядеть ваше сообщение. Отправляем?",
            reply_markup=keyboards.create_broadcast_confirmation_keyboard()
        )
        
        await bot.copy_message(
            chat_id=message.chat.id,
            from_chat_id=original_message.chat.id,
            message_id=original_message.message_id,
            reply_markup=preview_keyboard
        )

        await state.set_state(Broadcast.waiting_for_confirmation)

    @user_router.callback_query(Broadcast.waiting_for_confirmation, F.data == "confirm_broadcast")
    @measure_performance("confirm_broadcast")
    async def confirm_broadcast_handler(callback: types.CallbackQuery, state: FSMContext, bot: Bot):
        await callback.message.edit_text("⏳ Начинаю рассылку... Это может занять некоторое время.")
        
        data = await state.get_data()
        message_json = data.get('message_to_send')
        original_message = types.Message.model_validate_json(message_json)
        
        button_text = data.get('button_text')
        button_url = data.get('button_url')
        
        final_keyboard = None
        if button_text and button_url:
            builder = InlineKeyboardBuilder()
            builder.button(text=button_text, url=button_url)
            final_keyboard = builder.as_markup()

        await state.clear()
        
        users = get_all_users()
        logger.info(f"Broadcast: Starting to iterate over {len(users)} users.")

        sent_count = 0
        failed_count = 0
        banned_count = 0

        for user in users:
            user_id = user['telegram_id']
            if user.get('is_banned'):
                banned_count += 1
                continue
            
            try:
                await bot.copy_message(
                    chat_id=user_id,
                    from_chat_id=original_message.chat.id,
                    message_id=original_message.message_id,
                    reply_markup=final_keyboard
                )

                sent_count += 1
                await asyncio.sleep(0.1)
            except Exception as e:
                failed_count += 1
                logger.warning(f"Failed to send broadcast message to user {user_id}: {e}")
        
        await callback.message.answer(
            f"✅ Рассылка завершена!\n\n"
            f"👍 Отправлено: {sent_count}\n"
            f"👎 Не удалось отправить: {failed_count}\n"
            f"🚫 Пропущено (забанены): {banned_count}"
        )
        await show_main_menu(callback.message)

    @user_router.callback_query(StateFilter(Broadcast), F.data == "cancel_broadcast")
    @measure_performance("cancel_broadcast")
    async def cancel_broadcast_handler(callback: types.CallbackQuery, state: FSMContext):
        await callback.answer("Рассылка отменена.")
        await state.clear()
        user_id = callback.from_user.id
        is_admin = str(user_id) == ADMIN_ID
        try:
            await callback.message.edit_text("🏠 <b>Главное меню</b>\n\nВыберите действие:", reply_markup=None)
        except Exception:
            await callback.message.answer("🏠 <b>Главное меню</b>\n\nВыберите действие:", reply_markup=keyboards.get_main_reply_keyboard(is_admin))

    @user_router.callback_query(F.data == "show_referral_program")
    @registration_required
    @measure_performance("referral_program")
    async def referral_program_handler(callback: types.CallbackQuery):
        await callback.answer()
        user_id = callback.from_user.id
        user_data = get_user(user_id)
        bot_username = (await callback.bot.get_me()).username
        
        referral_link = f"https://t.me/{bot_username}?start=ref_{user_id}"
        referral_count = get_referral_count(user_id)
        balance = user_data.get('referral_balance', 0)
        from shop_bot.data_manager.database import get_setting
        min_withdraw = get_setting("minimum_withdrawal") or "100"
        referral_percentage = get_setting("referral_percentage") or "10"

        text = (
            "🤝 <b>Реферальная программа</b>\n\n"
            f"🗣 Приглашай друзей и получайте {referral_percentage}% от их расходов, которые затем ты сможешь вывести на свой счет! Вывод доступен от {min_withdraw} руб.\n\n"
            f"<b>Ваша реферальная ссылка:</b>\n<code>{referral_link}</code>\n\n"
            f"<b>Приглашено пользователей:</b> {referral_count}\n"
            f"<b>Ваш баланс:</b> {balance:.2f} руб."
        )

        builder = InlineKeyboardBuilder()
        if balance >= 100:
            builder.button(text="💸 Оставить заявку на вывод средств", callback_data="withdraw_request")
        # Возврат в профиль
        builder.button(text="⬅️ Назад", callback_data="show_profile")
        builder.adjust(1)
        await callback.message.edit_text(
            text, reply_markup=builder.as_markup()
        )

    @user_router.callback_query(F.data == "withdraw_request")
    @registration_required
    async def withdraw_request_handler(callback: types.CallbackQuery, state: FSMContext):
        await callback.answer()
        
        # Создаем клавиатуру для выбора способа вывода
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="📱 По номеру телефона (Рекомендуемый)", callback_data="withdraw_method_phone")
            ],
            [
                InlineKeyboardButton(text="💳 По номеру банковской карты", callback_data="withdraw_method_card")
            ],
            [
                InlineKeyboardButton(text="⬅️ Назад", callback_data="show_referral_program")
            ]
        ])
        
        await callback.message.edit_text(
            "💸 <b>Вывод реферальных средств</b>\n\n"
            "Выберите способ вывода средств:",
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        await state.set_state(WithdrawStates.waiting_for_payment_method)

    @user_router.callback_query(WithdrawStates.waiting_for_payment_method, F.data.in_(["withdraw_method_phone", "withdraw_method_card"]))
    @registration_required
    async def withdraw_method_handler(callback: types.CallbackQuery, state: FSMContext):
        """Обработчик выбора способа вывода"""
        await callback.answer()
        
        method = "phone" if callback.data == "withdraw_method_phone" else "card"
        method_text = "по номеру телефона" if method == "phone" else "по номеру банковской карты"
        
        # Сохраняем способ вывода в состоянии
        await state.update_data(withdrawal_method=method, withdrawal_method_text=method_text)
        
        # Если выбран телефон - показываем выбор банка
        if method == "phone":
            text = (
                "🏦 <b>Выбор банка для перевода</b>\n\n"
                "Выберите банк, на который будет произведен перевод.\n\n"
                "💡 <i>Комиссия банка (до 50 рублей) оплачивается нами.</i>"
            )
            
            # Создаем клавиатуру с популярными банками
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(text="🏦 Сбербанк", callback_data="bank_sberbank")
                ],
                [
                    InlineKeyboardButton(text="🏦 ВТБ", callback_data="bank_vtb")
                ],
                [
                    InlineKeyboardButton(text="🏦 Альфа-Банк", callback_data="bank_alfabank")
                ],
                [
                    InlineKeyboardButton(text="🏦 Тинькофф", callback_data="bank_tinkoff")
                ],
                [
                    InlineKeyboardButton(text="🏦 Газпромбанк", callback_data="bank_gazprombank")
                ],
                [
                    InlineKeyboardButton(text="🏦 Райффайзенбанк", callback_data="bank_raiffeisenbank")
                ],
                [
                    InlineKeyboardButton(text="🏦 Другой банк", callback_data="bank_other")
                ],
                [
                    InlineKeyboardButton(text="⬅️ Назад", callback_data="withdraw_request")
                ]
            ])
            
            await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
            await state.set_state(WithdrawStates.waiting_for_bank)
        else:
            # Для карты сразу просим ввести реквизиты
            text = (
                "💳 <b>Вывод по номеру банковской карты</b>\n\n"
                "Пожалуйста, отправьте номер банковской карты для перевода.\n\n"
                "Формат: XXXX XXXX XXXX XXXX"
            )
            await callback.message.edit_text(text, parse_mode="HTML")
            await state.set_state(WithdrawStates.waiting_for_details)

    @user_router.callback_query(WithdrawStates.waiting_for_bank, F.data.startswith("bank_"))
    @registration_required
    async def withdraw_bank_handler(callback: types.CallbackQuery, state: FSMContext):
        """Обработчик выбора банка"""
        await callback.answer()
        
        # Получаем название банка из callback_data
        bank_key = callback.data.replace("bank_", "")
        bank_names = {
            "sberbank": "Сбербанк",
            "vtb": "ВТБ",
            "alfabank": "Альфа-Банк",
            "tinkoff": "Тинькофф",
            "gazprombank": "Газпромбанк",
            "raiffeisenbank": "Райффайзенбанк",
            "other": "Другой банк"
        }
        bank_name = bank_names.get(bank_key, "Неизвестный банк")
        
        # Сохраняем выбранный банк в состоянии
        await state.update_data(bank_name=bank_name)
        
        # Просим ввести номер телефона
        text = (
            "📱 <b>Ввод номера телефона</b>\n\n"
            f"Выбран банк: <b>{bank_name}</b>\n\n"
            "Пожалуйста, отправьте номер телефона для перевода.\n\n"
            "Формат: +7XXXXXXXXXX"
        )
        
        await callback.message.edit_text(text, parse_mode="HTML")
        await state.set_state(WithdrawStates.waiting_for_details)

    @user_router.message(WithdrawStates.waiting_for_details)
    @registration_required
    async def process_withdraw_details(message: types.Message, state: FSMContext):
        user_id = message.from_user.id
        user = get_user(user_id)
        balance = user.get('referral_balance', 0)
        details = message.text.strip()
        if balance < 100:
            await message.answer("❌ Ваш баланс менее 100 руб. Вывод недоступен.")
            await state.clear()
            return

        # Получаем способ вывода и банк из состояния
        data = await state.get_data()
        method = data.get('withdrawal_method', 'unknown')
        method_text = data.get('withdrawal_method_text', 'не указан')
        bank_name = data.get('bank_name', '')

        admin_id = get_admin_id()
        if not admin_id:
            await message.answer("❌ Администратор не настроен.")
            await state.clear()
            return
        from html import escape
        
        username = user.get('username', 'N/A')
        # Экранируем все специальные символы для HTML
        username_safe = escape(username)
        details_safe = escape(details)
        
        # Определяем иконку в зависимости от способа вывода
        method_icon = "📱" if method == "phone" else "💳"
        
        # Формируем текст заявки
        if method == "phone" and bank_name:
            # Для телефона показываем банк и номер телефона
            text = (
                f"💸 <b>Заявка на вывод реферальных средств</b>\n"
                f"👤 Пользователь: @{username_safe} (ID: <code>{user_id}</code>)\n"
                f"💰 Сумма: <b>{balance:.2f} RUB</b>\n"
                f"{method_icon} Способ вывода: <b>{method_text}</b>\n"
                f"🏦 Банк: <b>{bank_name}</b>\n"
                f"📱 Номер телефона: <code>{details_safe}</code>"
            )
        else:
            # Для карты показываем только номер карты
            text = (
                f"💸 <b>Заявка на вывод реферальных средств</b>\n"
                f"👤 Пользователь: @{username_safe} (ID: <code>{user_id}</code>)\n"
                f"💰 Сумма: <b>{balance:.2f} RUB</b>\n"
                f"{method_icon} Способ вывода: <b>{method_text}</b>\n"
                f"💳 Номер карты: <code>{details_safe}</code>"
            )
        
        # Создаем клавиатуру с кнопками
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Одобрить", callback_data=f"approve_withdraw_{user_id}"),
                InlineKeyboardButton(text="❌ Отклонить", callback_data=f"decline_withdraw_{user_id}")
            ]
        ])
        
        await message.answer("Ваша заявка отправлена администратору. Ожидайте ответа.")
        
        try:
            await message.bot.send_message(admin_id, text, parse_mode="HTML", reply_markup=keyboard)
        except TelegramBadRequest as e:
            error_msg = str(e)
            if "can't parse entities" in error_msg or "unsupported start tag" in error_msg:
                logger.error(f"HTML parsing error in withdraw request: {e}")
                # Отправляем без форматирования, если есть ошибка парсинга
                if method == "phone" and bank_name:
                    text_plain = (
                        f"💸 Заявка на вывод реферальных средств\n"
                        f"👤 Пользователь: @{username} (ID: {user_id})\n"
                        f"💰 Сумма: {balance:.2f} RUB\n"
                        f"{method_icon} Способ вывода: {method_text}\n"
                        f"🏦 Банк: {bank_name}\n"
                        f"📱 Номер телефона: {details}"
                    )
                else:
                    text_plain = (
                        f"💸 Заявка на вывод реферальных средств\n"
                        f"👤 Пользователь: @{username} (ID: {user_id})\n"
                        f"💰 Сумма: {balance:.2f} RUB\n"
                        f"{method_icon} Способ вывода: {method_text}\n"
                        f"💳 Номер карты: {details}"
                    )
                await message.bot.send_message(admin_id, text_plain, reply_markup=keyboard)
            else:
                raise
        except Exception as e:
            logger.error(f"Failed to send withdraw request to admin: {e}", exc_info=True)
            await message.answer("❌ Не удалось отправить заявку администратору. Попробуйте позже.")
            await state.clear()
            return
        
        await state.clear()

    @user_router.message(Command(commands=["approve_withdraw"]))
    async def approve_withdraw_handler(message: types.Message, command: CommandObject):
        admin_id = get_admin_id()
        if not admin_id or message.from_user.id != admin_id:
            return
        try:
            # Извлекаем user_id из аргументов команды
            if not command.args:
                await message.answer("❌ Укажите ID пользователя: /approve_withdraw <user_id>")
                return
            
            user_id = int(command.args.strip())
            user = get_user(user_id)
            balance = user.get('referral_balance', 0)
            if balance < 100:
                await message.answer("❌ Баланс пользователя менее 100 руб.")
                return
            set_referral_balance(user_id, 0)
            # referral_balance_all НЕ обнуляем - это история всех заработков
            await message.answer(f"✅ Выплата {balance:.2f} RUB пользователю {user_id} подтверждена.")
            await message.bot.send_message(
                user_id,
                f"✅ Ваша заявка на вывод {balance:.2f} RUB одобрена. Деньги будут переведены в ближайшее время."
            )
        except ValueError:
            await message.answer("❌ Неверный формат ID пользователя. Используйте: /approve_withdraw <user_id>")
        except Exception as e:
            await message.answer(f"❌ Ошибка: {e}")

    @user_router.message(Command(commands=["decline_withdraw"]))
    async def decline_withdraw_handler(message: types.Message, command: CommandObject):
        admin_id = get_admin_id()
        if not admin_id or message.from_user.id != admin_id:
            return
        try:
            # Извлекаем user_id из аргументов команды
            if not command.args:
                await message.answer("❌ Укажите ID пользователя: /decline_withdraw <user_id>")
                return
            
            user_id = int(command.args.strip())
            await message.answer(f"❌ Заявка пользователя {user_id} отклонена.")
            await message.bot.send_message(
                user_id,
                "❌ Ваша заявка на вывод отклонена. Проверьте корректность реквизитов и попробуйте снова."
            )
        except ValueError:
            await message.answer("❌ Неверный формат ID пользователя. Используйте: /decline_withdraw <user_id>")
        except Exception as e:
            await message.answer(f"❌ Ошибка: {e}")

    @user_router.callback_query(F.data.startswith("approve_withdraw_"))
    async def approve_withdraw_callback(callback: types.CallbackQuery):
        """Обработчик кнопки одобрения вывода"""
        admin_id = get_admin_id()
        if not admin_id or callback.from_user.id != admin_id:
            await callback.answer("❌ У вас нет прав.", show_alert=True)
            return
        
        try:
            # Извлекаем user_id из callback_data
            user_id = int(callback.data.split("_")[-1])
            user = get_user(user_id)
            balance = user.get('referral_balance', 0)
            
            if balance < 100:
                await callback.answer("❌ Баланс пользователя менее 100 руб.", show_alert=True)
                return
            
            set_referral_balance(user_id, 0)
            
            # Обновляем сообщение с заявкой
            await callback.message.edit_text(
                f"✅ <b>Заявка одобрена</b>\n"
                f"👤 Пользователь: {user.get('username', 'N/A')} (ID: <code>{user_id}</code>)\n"
                f"💰 Выплачено: <b>{balance:.2f} RUB</b>",
                parse_mode="HTML"
            )
            
            # Уведомляем пользователя
            try:
                await callback.bot.send_message(
                    user_id,
                    f"✅ Ваша заявка на вывод {balance:.2f} RUB одобрена. Деньги будут переведены в ближайшее время."
                )
            except Exception as e:
                logger.error(f"Failed to notify user {user_id}: {e}")
            
            await callback.answer("✅ Выплата подтверждена", show_alert=True)
            
        except ValueError:
            await callback.answer("❌ Неверный формат ID пользователя", show_alert=True)
        except Exception as e:
            logger.error(f"Error approving withdraw: {e}", exc_info=True)
            await callback.answer(f"❌ Ошибка: {e}", show_alert=True)

    @user_router.callback_query(F.data.startswith("decline_withdraw_"))
    async def decline_withdraw_callback(callback: types.CallbackQuery, state: FSMContext):
        """Обработчик кнопки отклонения вывода"""
        admin_id = get_admin_id()
        if not admin_id or callback.from_user.id != admin_id:
            await callback.answer("❌ У вас нет прав.", show_alert=True)
            return
        
        try:
            # Извлекаем user_id из callback_data
            user_id = int(callback.data.split("_")[-1])
            user = get_user(user_id)
            
            # Извлекаем данные заявки из текста сообщения
            message_text = callback.message.text or callback.message.caption or ""
            
            # Парсим данные из сообщения
            username_match = re.search(r'👤 Пользователь: @?([^\s]+)', message_text)
            amount_match = re.search(r'💰 Сумма: ([0-9.]+) RUB', message_text)
            method_match = re.search(r'📱 Способ вывода: ([^\n]+)', message_text)
            bank_match = re.search(r'🏦 Банк: ([^\n]+)', message_text)
            phone_match = re.search(r'📱 Номер телефона: ([^\n]+)', message_text)
            card_match = re.search(r'💳 Номер карты: ([^\n]+)', message_text)
            
            username = username_match.group(1) if username_match else user.get('username', 'N/A')
            amount = amount_match.group(1) if amount_match else "0.00"
            method_text = method_match.group(1).strip() if method_match else "не указан"
            bank_name = bank_match.group(1).strip() if bank_match else None
            phone = phone_match.group(1).strip() if phone_match else None
            card = card_match.group(1).strip() if card_match else None
            
            # Определяем способ вывода
            method_icon = "📱" if phone else "💳"
            details = phone if phone else card
            
            # Сохраняем все данные в состоянии
            await state.update_data(
                decline_user_id=user_id,
                decline_message_id=callback.message.message_id,
                decline_username=username,
                decline_amount=amount,
                decline_method_text=method_text,
                decline_bank_name=bank_name,
                decline_details=details,
                decline_method_icon=method_icon
            )
            
            # Формируем текст с полными данными заявки
            request_text = (
                f"📝 <b>Укажите причину отклонения заявки</b>\n\n"
                f"<b>Данные заявки пользователя:</b>\n"
                f"👤 Пользователь: @{username}\n"
                f"💰 Сумма: {amount} RUB\n"
                f"{method_icon} Способ вывода: {method_text}"
            )
            
            if bank_name:
                request_text += f"\n🏦 Банк: {bank_name}"
            
            if phone:
                request_text += f"\n📱 Номер телефона: {phone}"
            elif card:
                request_text += f"\n💳 Номер карты: {card}"
            
            request_text += "\n\n📝 <b>Напишите причину отклонения заявки</b>\n"
            request_text += "💡 Вы можете отправить текст или фото с подписью (например, скриншот ошибки)."
            request_text += "\nЭто сообщение будет отправлено пользователю."
            
            # Запрашиваем причину отклонения
            await callback.message.edit_text(
                request_text,
                parse_mode="HTML"
            )
            
            await state.set_state(DeclineWithdrawStates.waiting_for_decline_reason)
            await callback.answer("Введите причину отклонения", show_alert=False)
            
        except ValueError:
            await callback.answer("❌ Неверный формат ID пользователя", show_alert=True)
        except Exception as e:
            logger.error(f"Error declining withdraw: {e}", exc_info=True)
            await callback.answer(f"❌ Ошибка: {e}", show_alert=True)

    @user_router.message(DeclineWithdrawStates.waiting_for_decline_reason)
    async def decline_withdraw_reason_handler(message: types.Message, state: FSMContext):
        """Обработчик получения причины отклонения заявки (поддерживает текст и фото)"""
        admin_id = get_admin_id()
        if not admin_id or message.from_user.id != admin_id:
            return
        
        try:
            # Получаем данные из состояния
            data = await state.get_data()
            user_id = data.get('decline_user_id')
            message_id = data.get('decline_message_id')
            
            # Проверяем наличие user_id
            if not user_id:
                logger.error(f"Failed to get decline_user_id from state. Data: {data}")
                await message.answer("❌ Ошибка: не удалось получить данные заявки. Попробуйте отклонить заявку снова.")
                await state.clear()
                return
            
            # Получаем текст причины (может быть в тексте сообщения или в подписи к фото)
            reason = message.text or message.caption or ""
            
            if not reason:
                await message.answer("❌ Пожалуйста, укажите причину отклонения текстом или с подписью к фото.")
                return
            
            user = get_user(user_id)
            if not user:
                await message.answer("❌ Пользователь не найден")
                await state.clear()
                return
            
            # Получаем данные заявки из состояния
            username = data.get('decline_username', user.get('username', 'N/A'))
            amount = data.get('decline_amount', '0.00')
            method_text = data.get('decline_method_text', 'не указан')
            bank_name = data.get('decline_bank_name')
            details = data.get('decline_details')
            method_icon = data.get('decline_method_icon', '💳')
            
            # Формируем сообщение для пользователя с полными данными заявки
            user_message = (
                f"❌ <b>Ваша заявка на вывод отклонена</b>\n\n"
                f"<b>Данные вашей заявки:</b>\n"
                f"👤 Пользователь: @{username}\n"
                f"💰 Сумма: {amount} RUB\n"
                f"{method_icon} Способ вывода: {method_text}"
            )
            
            if bank_name:
                user_message += f"\n🏦 Банк: {bank_name}"
            
            if details:
                if method_icon == "📱":
                    user_message += f"\n📱 Номер телефона: {details}"
                else:
                    user_message += f"\n💳 Номер карты: {details}"
            
            user_message += f"\n\n⚠️ <b>Причина:</b> {reason}\n\n"
            user_message += "Пожалуйста, проверьте корректность реквизитов и попробуйте снова."
            
            # Отправляем сообщение пользователю с причиной отклонения
            try:
                # Если есть фото, отправляем фото с текстом
                if message.photo:
                    # Получаем фото наибольшего размера
                    photo = message.photo[-1]
                    await message.bot.send_photo(
                        user_id,
                        photo.file_id,
                        caption=user_message,
                        parse_mode="HTML"
                    )
                else:
                    # Отправляем только текст
                    await message.bot.send_message(
                        user_id,
                        user_message,
                        parse_mode="HTML"
                    )
            except Exception as e:
                logger.error(f"Failed to notify user {user_id}: {e}")
                await message.answer(f"❌ Не удалось отправить уведомление пользователю: {e}")
                await state.clear()
                return
            
            # Обновляем сообщение с заявкой
            try:
                decline_status = f"📝 <b>Причина:</b> {reason}"
                if message.photo:
                    decline_status += " (со скриншотом)"
                
                await message.bot.edit_message_text(
                    f"❌ <b>Заявка отклонена</b>\n"
                    f"👤 Пользователь: {username} (ID: <code>{user_id}</code>)\n\n"
                    f"{decline_status}",
                    chat_id=admin_id,
                    message_id=message_id,
                    parse_mode="HTML"
                )
            except Exception as e:
                logger.error(f"Failed to edit message: {e}")
            
            # Отправляем подтверждение админу
            confirmation_text = f"✅ Заявка пользователя {username} (ID: {user_id}) отклонена.\nПричина отправлена пользователю."
            if message.photo:
                confirmation_text += " (вместе со скриншотом)"
            
            await message.answer(confirmation_text)
            
            await state.clear()
            
        except Exception as e:
            logger.error(f"Error processing decline reason: {e}", exc_info=True)
            await message.answer(f"❌ Ошибка: {e}")
            await state.clear()

    @user_router.message(Command(commands=["upload_video"]))
    async def upload_video_handler(message: types.Message):
        """Админская команда для загрузки видеоинструкций"""
        admin_id = get_admin_id()
        if not admin_id or message.from_user.id != admin_id:
            return
        
        if not message.video:
            await message.answer("❌ Пожалуйста, отправьте видеофайл вместе с командой /upload_video")
            return
        
        # Получаем платформу из текста команды
        command_text = message.text or ""
        parts = command_text.split()
        if len(parts) < 2:
            await message.answer(
                "❌ Использование: /upload_video <платформа>\n"
                "Доступные платформы: android, ios, windows, macos, linux"
            )
            return
        
        platform = parts[1].lower()
        valid_platforms = ['android', 'ios', 'windows', 'macos', 'linux']
        if platform not in valid_platforms:
            await message.answer(f"❌ Неверная платформа. Доступные: {', '.join(valid_platforms)}")
            return
        
        try:
            # Создаем папку если не существует
            video_dir = Path(VIDEO_INSTRUCTIONS_DIR)
            video_dir.mkdir(exist_ok=True)
            
            # Получаем файл
            video_file = await message.bot.get_file(message.video.file_id)
            video_path = video_dir / f"{platform}_video.mp4"
            
            # Скачиваем и сохраняем видео
            await video_file.download_to_drive(video_path)
            
            await message.answer(f"✅ Видеоинструкция для {platform} успешно загружена!")
            
        except Exception as e:
            logger.error(f"Ошибка при загрузке видео для {platform}: {e}")
            await message.answer(f"❌ Ошибка при загрузке видео: {e}")

    @user_router.message(Command(commands=["list_videos"]))
    async def list_videos_handler(message: types.Message):
        """Админская команда для просмотра загруженных видеоинструкций"""
        admin_id = get_admin_id()
        if not admin_id or message.from_user.id != admin_id:
            return
        
        try:
            video_dir = Path(VIDEO_INSTRUCTIONS_DIR)
            if not video_dir.exists():
                await message.answer("📁 Папка с видеоинструкциями не существует")
                return
            
            videos = list(video_dir.glob("*_video.mp4"))
            if not videos:
                await message.answer("📁 Видеоинструкции не загружены")
                return
            
            text = "📹 <b>Загруженные видеоинструкции:</b>\n\n"
            for video in videos:
                platform = video.stem.replace("_video", "")
                size_mb = video.stat().st_size / (1024 * 1024)
                text += f"• {platform}: {size_mb:.1f} MB\n"
            
            await message.answer(text, parse_mode="HTML")
            
        except Exception as e:
            logger.error(f"Ошибка при получении списка видео: {e}")
            await message.answer(f"❌ Ошибка: {e}")

    @user_router.message(Command(commands=["delete_video"]))
    async def delete_video_handler(message: types.Message):
        """Админская команда для удаления видеоинструкций"""
        admin_id = get_admin_id()
        if not admin_id or message.from_user.id != admin_id:
            return
        
        command_text = message.text or ""
        parts = command_text.split()
        if len(parts) < 2:
            await message.answer(
                "❌ Использование: /delete_video <платформа>\n"
                "Доступные платформы: android, ios, windows, macos, linux"
            )
            return
        
        platform = parts[1].lower()
        valid_platforms = ['android', 'ios', 'windows', 'macos', 'linux']
        if platform not in valid_platforms:
            await message.answer(f"❌ Неверная платформа. Доступные: {', '.join(valid_platforms)}")
            return
        
        try:
            video_path = Path(VIDEO_INSTRUCTIONS_DIR) / f"{platform}_video.mp4"
            if video_path.exists():
                video_path.unlink()
                await message.answer(f"✅ Видеоинструкция для {platform} удалена")
            else:
                await message.answer(f"❌ Видеоинструкция для {platform} не найдена")
                
        except Exception as e:
            logger.error(f"Ошибка при удалении видео для {platform}: {e}")
            await message.answer(f"❌ Ошибка при удалении видео: {e}")

    @user_router.callback_query(F.data == "show_about")
    @documents_consent_required
    @subscription_required
    @measure_performance("about")
    async def about_handler(callback: types.CallbackQuery):
        await callback.answer()
        
        about_text = get_setting("about_content")
        channel_url = get_setting("channel_url")
        
        # Получаем домен из настроек или используем дефолтный
        from shop_bot.data_manager.database import get_global_domain
        domain = get_global_domain()
        
        # Генерируем URL для страниц только если домен не localhost
        terms_url = None
        privacy_url = None
        if is_production_server() and domain and not _is_local_address(domain):
            terms_url = normalize_web_app_url(f"{domain.rstrip('/')}/terms")
            privacy_url = normalize_web_app_url(f"{domain.rstrip('/')}/privacy")

        final_text = about_text if about_text else "Информация о проекте не добавлена."
        
        # Убираем HTML теги, которые не поддерживает Telegram
        final_text = re.sub(r'<[^>]+>', '', final_text)
        
        # Проверяем, что текст не пустой
        if not final_text.strip():
            final_text = "Информация о проекте не добавлена."

        keyboard = keyboards.create_about_keyboard(channel_url, terms_url, privacy_url)

        await callback.message.edit_text(
            final_text,
            reply_markup=keyboard,
            disable_web_page_preview=True
        )

    @user_router.callback_query(F.data == "show_help")
    @registration_required
    @measure_performance("help")
    async def help_handler(callback: types.CallbackQuery):
        await callback.answer()
        from shop_bot.data_manager.database import get_setting
        if get_setting("support_enabled") != "true":
            await callback.message.edit_text(
                "Раздел поддержки недоступен.",
                reply_markup=keyboards.create_back_to_menu_keyboard()
            )
            return
        support_user = get_setting("support_user")
        support_text = get_setting("support_content")
        
        # Проверяем, есть ли отдельный бот поддержки
        support_bot_token = get_setting("support_bot_token")
        support_group_id = get_setting("support_group_id")
        
        if support_bot_token and support_group_id:
            # Если настроен отдельный бот поддержки, перенаправляем к нему
            support_url = support_user if support_user and support_user.startswith('https://') else f"https://t.me/{support_user.replace('@', '')}" if support_user else None
            
            if support_url:
                await callback.message.edit_text(
                    "Для получения поддержки перейдите к нашему боту поддержки:",
                    reply_markup=keyboards.create_support_keyboard(support_url)
                )
            else:
                await callback.message.edit_text(
                    "Служба поддержки временно недоступна.",
                    reply_markup=keyboards.create_back_to_menu_keyboard()
                )
        elif support_user == None and support_text == None:
            await callback.message.edit_text(
                "Информация о поддержке не установлена. Установите её в админ-панели.",
                reply_markup=keyboards.create_back_to_menu_keyboard()
            )
        else:
            # Обрабатываем username бота как URL
            if support_user and support_user.startswith('@'):
                support_url = f"https://t.me/{support_user.replace('@', '')}"
            else:
                support_url = support_user
            
            # Проверяем, что support_url не None
            if support_url:
                # Определяем текст для отображения
                if support_text:
                    display_text = support_text + "\n\n"
                else:
                    display_text = "Для связи с поддержкой используйте кнопку ниже.\n\n"
                
                await callback.message.edit_text(
                    display_text,
                    reply_markup=keyboards.create_support_keyboard(support_url)
                )
            else:
                # Если support_url None, показываем сообщение об ошибке
                await callback.message.edit_text(
                    "Информация о поддержке не установлена. Установите её в админ-панели.",
                    reply_markup=keyboards.create_back_to_menu_keyboard()
                )

    @user_router.callback_query(F.data == "manage_keys")
    @registration_required
    @measure_performance("manage_keys")
    async def manage_keys_handler(callback: types.CallbackQuery):
        try:
            await callback.answer()
        except TelegramBadRequest as e:
            error_msg = str(e).lower()
            # Если callback query устарел, просто пропускаем answer и продолжаем
            if "query is too old" in error_msg or "response timeout expired" in error_msg or "query id is invalid" in error_msg:
                logger.debug(f"Callback query expired in manage_keys_handler for user {callback.from_user.id}, continuing without answer")
            else:
                raise
        
        user_id = callback.from_user.id
        user_keys = get_user_keys(user_id)
        user_db_data = get_user(user_id)
        trial_used = user_db_data.get('trial_used', 1) if user_db_data else 1
        
        menu_text = """=== Мои ключи ===
Условные обозначения:<blockquote>1. Статус иконка: ✅ для активных, ❌ для истёкших/деактивированных
2. Порядковый номер ключа
3. Страна сервера ключа
4. Название тарифа
5. Цена
6. Дата окончания
7. Автопродление ключа: 🟢 включено, 🔴 выключено
</blockquote>""" if user_keys else "У вас пока нет ключей."
        
        await callback.message.edit_text(
            menu_text,
            reply_markup=keyboards.create_keys_management_keyboard(user_keys, trial_used),
            parse_mode="HTML"
        )

    @user_router.callback_query(F.data == "get_trial")
    @documents_consent_required
    @registration_required
    @measure_performance("trial_period")
    async def trial_period_handler(callback: types.CallbackQuery, state: FSMContext):
        user_id = callback.from_user.id
        user_db_data = get_user(user_id)
        
        # Добавляем логирование для отладки
        logger.info(f"Trial check for user {user_id}: user_db_data={user_db_data}")
        if user_db_data:
            trial_used_value = user_db_data.get('trial_used')
            logger.info(f"Trial check for user {user_id}: trial_used={trial_used_value} (type: {type(trial_used_value)})")
            logger.info(f"Trial check for user {user_id}: bool(trial_used_value)={bool(trial_used_value)}")
        
        if user_db_data and user_db_data.get('trial_used'):
            logger.info(f"Trial blocked for user {user_id}: trial_used is True")
            await callback.answer("Вы уже использовали бесплатный пробный период.", show_alert=True)
            return
        
        # Дополнительная проверка: нет ли активных триальных ключей (только с активным статусом)
        user_keys = get_user_keys(user_id)
        active_trial_keys = [key for key in user_keys if key.get('is_trial') == 1 and key.get('remaining_seconds', 0) > 0 and key.get('status') != 'deactivate']
        if active_trial_keys:
            await callback.answer("У вас уже есть активный пробный ключ.", show_alert=True)
            return

        hosts = get_all_hosts()
        if not hosts:
            await callback.message.edit_text("❌ В данный момент нет доступных серверов для создания пробного ключа.")
            return
        # Скрываем сервера без тарифов (для единообразия выбора серверов)
        try:
            hosts = [h for h in hosts if get_plans_for_host(h['host_name'])]
        except Exception:
            pass
        if not hosts:
            await callback.message.edit_text("❌ В данный момент нет доступных серверов для создания пробного ключа.")
            return
            
        if len(hosts) == 1:
            await callback.answer()
            await process_trial_key_creation(callback.message, hosts[0]['host_name'])
        else:
            await callback.answer()
            await callback.message.edit_text(
                "Выберите сервер, на котором хотите получить пробный ключ:",
                reply_markup=keyboards.create_host_selection_keyboard(hosts, action="trial")
            )

    @user_router.callback_query(F.data.startswith("select_host_trial_"))
    @registration_required
    @measure_performance("trial_host_selection")
    async def trial_host_selection_handler(callback: types.CallbackQuery):
        await callback.answer()
        host_name = callback.data[len("select_host_trial_"):]
        await process_trial_key_creation(callback.message, host_name)

    async def process_trial_key_creation_callback(callback: types.CallbackQuery, host_name: str):
        """Callback-версия функции создания пробного ключа"""
        user_id = callback.from_user.id
        trial_duration_display = get_setting('trial_duration_days') or "7"
        await callback.message.edit_text(f"Отлично! Создаю для вас бесплатный ключ на {trial_duration_display} дня на сервере \"{host_name}\"...")

        try:
            trial_duration = get_setting("trial_duration_days")
            if trial_duration is None:
                trial_duration = "7"  # Значение по умолчанию - 7 дней
            # Нормализуем к числу (float для timedelta, int для сохранения)
            try:
                trial_duration_float = float(trial_duration)
            except Exception:
                trial_duration_float = 7.0
            
            # Получаем host_code для триального ключа
            try:
                from shop_bot.data_manager.database import get_host
                host_rec = get_host(host_name)
                host_code_for_email = (host_rec.get('host_code') or host_name).replace(' ', '').lower() if host_rec else host_name.replace(' ', '').lower()
                host_code_for_search = host_rec.get('host_code') if host_rec else None
            except Exception:
                host_code_for_email = host_name.replace(' ', '').lower()
                host_code_for_search = None
            
            # Получаем данные пользователя для формирования subscription (до создания ключа)
            user_data = get_user(user_id)
            username = user_data.get('username', '') if user_data else ''
            fullname = user_data.get('fullname', '') if user_data else ''
            subscription = f"{user_id}-{username}".lower().replace('@', '')
            telegram_chat_id = user_id
            
            key_number = get_next_key_number(user_id)
            result = await xui_api.create_or_update_key_on_host(
                host_name=host_name,
                email=f"user{user_id}-key{key_number}-trial@{host_code_for_email}.bot",
                days_to_add=trial_duration_float,
                comment=f"{user_id}",
                sub_id=subscription,
                telegram_chat_id=telegram_chat_id,
                host_code=host_code_for_search
            )
            if not result:
                await callback.message.edit_text("❌ Не удалось создать пробный ключ. Ошибка на сервере.")
                return

            # Устанавливаем флаг использования триала
            set_trial_used(user_id)
            # Устанавливаем количество дней из админки
            set_trial_days_given(user_id, int(trial_duration_float))
            # Увеличиваем счетчик повторных использований
            increment_trial_reuses(user_id)
            
            new_key_id = add_new_key(
                user_id=user_id,
                host_name=host_name,
                xui_client_uuid=result['client_uuid'],
                key_email=result['email'],
                expiry_timestamp_ms=result['expiry_timestamp_ms'],
                connection_string=result.get('connection_string') or "",
                plan_name="Пробный период",
                price=0.0,
                protocol='vless',
                is_trial=1,
                subscription=subscription,
                subscription_link=result.get('subscription_link'),
                telegram_chat_id=telegram_chat_id,
                comment=f"Пробный период для пользователя {fullname or username or user_id}"
            )
            # Дополнительно сразу сохраним remaining_seconds и expiry_date
            if new_key_id:
                try:
                    from datetime import datetime, timezone
                    from shop_bot.data_manager.database import update_key_remaining_seconds
                    now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
                    remaining = max(0, int((result['expiry_timestamp_ms'] - now_ms) / 1000))
                    update_key_remaining_seconds(new_key_id, remaining, datetime.fromtimestamp(result['expiry_timestamp_ms']/1000))
                except Exception:
                    pass
                
                # Создаем транзакцию для пробного ключа
                try:
                    log_metadata = json.dumps({
                        "plan_name": "Пробный период",
                        "host_name": host_name,
                        "key_id": new_key_id,
                        "is_trial": True,
                        "trial_duration_days": trial_duration_float
                    })
                    
                    log_transaction(
                        username=username or 'N/A',
                        transaction_id=None,
                        payment_id=str(uuid.uuid4()),
                        user_id=user_id,
                        status='paid',
                        amount_rub=0.0,
                        amount_currency=None,
                        currency_name=None,
                        payment_method='Trial',
                        metadata=log_metadata
                    )
                except Exception as e:
                    logger.error(f"Failed to create transaction for trial key {new_key_id}: {e}", exc_info=True)
            
            new_expiry_date = datetime.fromtimestamp(result['expiry_timestamp_ms'] / 1000)
            subscription_link = result.get('subscription_link')
            feature_enabled, user_timezone = _get_user_timezone_context(user_id)
            
            # Получаем данные для информации о тарифе (триал)
            plan_name = "TRIAL"
            plan_price = 0.0
            
            final_text = get_purchase_success_text(
                "готов",
                get_next_key_number(user_id) - 1,
                new_expiry_date,
                result['connection_string'],
                subscription_link,
                'subscription',
                user_timezone=user_timezone,
                feature_enabled=feature_enabled,
                is_trial=True,
                user_id=user_id,
                key_id=new_key_id,
                host_name=host_name,
                plan_name=plan_name,
                price=plan_price,
                status=None,  # Для триала статус еще не определен
            )
            
            # Проверяем, что new_key_id не None перед созданием клавиатуры
            if new_key_id is not None:
                await callback.message.edit_text(
                    text=final_text,
                    reply_markup=keyboards.create_key_info_keyboard(new_key_id, subscription_link),
                    parse_mode=ParseMode.HTML,
                )
            else:
                await callback.message.edit_text(
                    text=final_text,
                    parse_mode=ParseMode.HTML,
                )

        except Exception as e:
            logger.error(f"Error creating trial key for user {user_id} on host {host_name}: {e}", exc_info=True)
            await callback.message.edit_text("❌ Произошла ошибка при создании пробного ключа.")

    async def process_trial_key_creation(message: types.Message, host_name: str):
        user_id = message.chat.id
        trial_duration_display = get_setting('trial_duration_days') or "7"
        await message.edit_text(f"Отлично! Создаю для вас бесплатный ключ на {trial_duration_display} дня на сервере \"{host_name}\"...")

        try:
            trial_duration = get_setting("trial_duration_days")
            if trial_duration is None:
                trial_duration = "7"  # Значение по умолчанию - 7 дней
            # Нормализуем к числу (float для timedelta, int для сохранения)
            try:
                trial_duration_float = float(trial_duration)
            except Exception:
                trial_duration_float = 7.0
            
            # Получаем host_code для триального ключа
            try:
                from shop_bot.data_manager.database import get_host
                host_rec = get_host(host_name)
                host_code_for_email = (host_rec.get('host_code') or host_name).replace(' ', '').lower() if host_rec else host_name.replace(' ', '').lower()
                host_code_for_search = host_rec.get('host_code') if host_rec else None
            except Exception:
                host_code_for_email = host_name.replace(' ', '').lower()
                host_code_for_search = None
            
            # Получаем данные пользователя для формирования subscription (до создания ключа)
            user_data = get_user(user_id)
            username = user_data.get('username', '') if user_data else ''
            fullname = user_data.get('fullname', '') if user_data else ''
            subscription = f"{user_id}-{username}".lower().replace('@', '')
            telegram_chat_id = user_id
            
            key_number = get_next_key_number(user_id)
            result = await xui_api.create_or_update_key_on_host(
                host_name=host_name,
                email=f"user{user_id}-key{key_number}-trial@{host_code_for_email}.bot",
                days_to_add=trial_duration_float,
                comment=f"{user_id}",
                sub_id=subscription,
                telegram_chat_id=telegram_chat_id,
                host_code=host_code_for_search
            )
            if not result:
                await message.edit_text("❌ Не удалось создать пробный ключ. Ошибка на сервере.")
                return

            # Устанавливаем флаг использования триала
            set_trial_used(user_id)
            # Устанавливаем количество дней из админки
            set_trial_days_given(user_id, int(trial_duration_float))
            # Увеличиваем счетчик повторных использований
            increment_trial_reuses(user_id)
            
            new_key_id = add_new_key(
                user_id=user_id,
                host_name=host_name,
                xui_client_uuid=result['client_uuid'],
                key_email=result['email'],
                expiry_timestamp_ms=result['expiry_timestamp_ms'],
                connection_string=result.get('connection_string') or "",
                plan_name="Пробный период",
                price=0.0,
                protocol='vless',
                is_trial=1,
                subscription=subscription,
                subscription_link=result.get('subscription_link'),
                telegram_chat_id=telegram_chat_id,
                comment=f"Пробный период для пользователя {fullname or username or user_id}"
            )
            # Дополнительно сразу сохраним remaining_seconds и expiry_date
            if new_key_id:
                try:
                    from datetime import datetime, timezone
                    from shop_bot.data_manager.database import update_key_remaining_seconds
                    now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
                    remaining = max(0, int((result['expiry_timestamp_ms'] - now_ms) / 1000))
                    update_key_remaining_seconds(new_key_id, remaining, datetime.fromtimestamp(result['expiry_timestamp_ms']/1000))
                except Exception:
                    pass
                
                # Создаем транзакцию для пробного ключа
                try:
                    log_metadata = json.dumps({
                        "plan_name": "Пробный период",
                        "host_name": host_name,
                        "key_id": new_key_id,
                        "is_trial": True,
                        "trial_duration_days": trial_duration_float
                    })
                    
                    log_transaction(
                        username=username or 'N/A',
                        transaction_id=None,
                        payment_id=str(uuid.uuid4()),
                        user_id=user_id,
                        status='paid',
                        amount_rub=0.0,
                        amount_currency=None,
                        currency_name=None,
                        payment_method='Trial',
                        metadata=log_metadata
                    )
                except Exception as e:
                    logger.error(f"Failed to create transaction for trial key {new_key_id}: {e}", exc_info=True)
            
            await message.delete()
            new_expiry_date = datetime.fromtimestamp(result['expiry_timestamp_ms'] / 1000)
            subscription_link = result.get('subscription_link')
            feature_enabled, user_timezone = _get_user_timezone_context(user_id)
            
            # Получаем данные для информации о тарифе (триал)
            plan_name = "TRIAL"
            plan_price = 0.0
            
            final_text = get_purchase_success_text(
                "готов",
                get_next_key_number(user_id) - 1,
                new_expiry_date,
                result['connection_string'],
                subscription_link,
                'subscription',
                user_timezone=user_timezone,
                feature_enabled=feature_enabled,
                is_trial=True,
                user_id=user_id,
                key_id=new_key_id,
                host_name=host_name,
                plan_name=plan_name,
                price=plan_price,
                status=None,  # Для триала статус еще не определен
            )
            
            # Проверяем, что new_key_id не None перед созданием клавиатуры
            if new_key_id is not None:
                await message.answer(
                    text=final_text,
                    reply_markup=keyboards.create_key_info_keyboard(new_key_id, subscription_link),
                    parse_mode=ParseMode.HTML,
                )
            else:
                await message.answer(
                    text=final_text,
                    parse_mode=ParseMode.HTML,
                )

        except Exception as e:
            logger.error(f"Error creating trial key for user {user_id} on host {host_name}: {e}", exc_info=True)
            await message.edit_text("❌ Произошла ошибка при создании пробного ключа.")

    @user_router.callback_query(F.data.startswith("show_key_"))
    @registration_required
    @measure_performance("show_key")
    async def show_key_handler(callback: types.CallbackQuery):
        # Извлекаем key_id из разных форматов callback data
        parts = callback.data.split("_")
        if callback.data.startswith("show_key_"):
            key_id_to_show = int(parts[2])
        elif callback.data.startswith("toggle_key_auto_renewal_"):
            key_id_to_show = int(parts[-1])  # последний элемент
        else:
            # Fallback: пытаемся извлечь из последнего элемента
            key_id_to_show = int(parts[-1])
        await callback.message.edit_text("Загружаю информацию о ключе...")
        user_id = callback.from_user.id
        key_data = get_key_by_id(key_id_to_show)

        if not key_data or key_data['user_id'] != user_id:
            await callback.message.edit_text("❌ Ошибка: ключ не найден.")
            return
            
        try:
            details = await xui_api.get_key_details_from_host(key_data)
            if not details or not details['connection_string']:
                await callback.message.edit_text("❌ Ошибка на сервере. Не удалось получить данные ключа.")
                return

            connection_string = details['connection_string']
            expiry_date = datetime.fromisoformat(key_data['expiry_date'])
            created_date = datetime.fromisoformat(key_data['created_date'])
            status = details.get('status', 'unknown')
            subscription_link = details.get('subscription_link') or key_data.get('subscription_link')
            
            all_user_keys = get_user_keys(user_id)
            key_number = next((i + 1 for i, key in enumerate(all_user_keys) if key['key_id'] == key_id_to_show), 0)
            
            # Получаем provision_mode из тарифа ключа
            provision_mode = 'key'  # по умолчанию
            plan_name = key_data.get('plan_name')
            if plan_name:
                # Получаем тариф по имени и хосту
                host_name = key_data.get('host_name')
                plans = get_plans_for_host(host_name)
                plan = next((p for p in plans if p.get('plan_name') == plan_name), None)
                if plan:
                    provision_mode = plan.get('key_provision_mode', 'key')
            
            feature_enabled, user_timezone = _get_user_timezone_context(user_id)
            is_trial = key_data.get('is_trial') == 1
            host_name = key_data.get('host_name')
            plan_name = key_data.get('plan_name')
            price = key_data.get('price')
            
            # Получаем статус автопродления ключа
            from shop_bot.data_manager.database import get_key_auto_renewal_enabled
            key_auto_renewal_enabled = get_key_auto_renewal_enabled(key_id_to_show)

            final_text = get_key_info_text(
                key_number,
                expiry_date,
                created_date,
                connection_string,
                status,
                subscription_link,
                provision_mode,
                user_timezone=user_timezone,
                feature_enabled=feature_enabled,
                is_trial=is_trial,
                user_id=user_id,
                key_id=key_id_to_show,
                host_name=host_name,
                plan_name=plan_name,
                price=price,
                key_auto_renewal_enabled=key_auto_renewal_enabled,
            )
            
            try:
                await callback.message.edit_text(
                    text=final_text,
                    reply_markup=keyboards.create_key_info_keyboard(key_id_to_show, subscription_link, key_auto_renewal_enabled),
                    parse_mode=ParseMode.HTML
                )
            except TelegramBadRequest as e:
                error_msg = str(e)
                if "can't parse entities" in error_msg or "unsupported start tag" in error_msg:
                    # Пытаемся отправить без HTML-форматирования
                    logger.warning(f"HTML parsing error for key {key_id_to_show}, sending without HTML: {e}")
                    # Удаляем HTML-теги из текста для отправки без форматирования
                    plain_text = re.sub(r'<[^>]+>', '', final_text)
                    plain_text = plain_text.replace('&lt;', '<').replace('&gt;', '>').replace('&amp;', '&')
                    await callback.message.edit_text(
                        text=plain_text,
                        reply_markup=keyboards.create_key_info_keyboard(key_id_to_show, subscription_link, key_auto_renewal_enabled)
                    )
                else:
                    raise
        except Exception as e:
            logger.error(f"Error showing key {key_id_to_show}: {e}", exc_info=True)
            await callback.message.edit_text("❌ Произошла ошибка при получении данных ключа.")


    @user_router.callback_query(F.data.startswith("copy_key_"))
    @registration_required
    @measure_performance("copy_key")
    async def copy_key_handler(callback: types.CallbackQuery):
        await callback.answer("Подготавливаю ключ для копирования...")
        key_id = int(callback.data.split("_")[2])
        key_data = get_key_by_id(key_id)
        if not key_data or key_data['user_id'] != callback.from_user.id: 
            return
        
        try:
            details = await xui_api.get_key_details_from_host(key_data)
            if not details or not details['connection_string']:
                await callback.answer("Ошибка: Не удалось получить ключ.", show_alert=True)
                return

            connection_string = details['connection_string']
            copy_text = (
                f"📋 <b>Ваш Ключ для копирования:</b>\n\n"
                f"<code>{connection_string}</code>\n\n"
                f"💡 <i>Нажмите на ключ выше, чтобы скопировать его</i>"
            )
            
            await callback.message.answer(
                text=copy_text,
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                    InlineKeyboardButton(text="⬅️ Назад к ключу", callback_data=f"show_key_{key_id}")
                ]])
            )
        except Exception as e:
            logger.error(f"Error copying key {key_id}: {e}")
            await callback.answer("Ошибка при получении ключа.", show_alert=True)

    @user_router.callback_query(F.data.startswith("show_qr_"))
    @registration_required
    async def show_qr_handler(callback: types.CallbackQuery):
        await callback.answer("Генерирую QR-код...")
        key_id = int(callback.data.split("_")[2])
        key_data = get_key_by_id(key_id)
        if not key_data or key_data['user_id'] != callback.from_user.id: return
        
        try:
            details = await xui_api.get_key_details_from_host(key_data)
            if not details or not details['connection_string']:
                await callback.answer("Ошибка: Не удалось сгенерировать QR-код.", show_alert=True)
                return

            connection_string = details['connection_string']
            qr_img = qrcode.make(connection_string)
            bio = BytesIO(); qr_img.save(bio, "PNG"); bio.seek(0)
            qr_code_file = BufferedInputFile(bio.read(), filename="vpn_qr.png")
            
            await callback.message.answer_photo(
                photo=qr_code_file,
                caption="📱 Отсканируйте QR-код через VPN приложение",
                reply_markup=keyboards.create_qr_keyboard(key_id)
            )
        except Exception as e:
            logger.error(f"Error showing QR for key {key_id}: {e}")

    @user_router.callback_query(F.data.startswith("toggle_key_auto_renewal_"))
    @registration_required
    @measure_performance("toggle_key_auto_renewal")
    async def toggle_key_auto_renewal_handler(callback: types.CallbackQuery):
        """Обработчик переключения автопродления для конкретного ключа"""
        try:
            await callback.answer()
        except TelegramBadRequest as e:
            error_msg = str(e).lower()
            if "query is too old" in error_msg or "response timeout expired" in error_msg or "query id is invalid" in error_msg:
                logger.debug(f"Callback query expired in toggle_key_auto_renewal_handler for user {callback.from_user.id}, continuing without answer")
            else:
                raise
        
        user_id = callback.from_user.id
        key_id = int(callback.data.split("_")[-1])
        
        # Проверяем, что ключ принадлежит пользователю
        key_data = get_key_by_id(key_id)
        if not key_data or key_data['user_id'] != user_id:
            await callback.answer("❌ Ошибка: ключ не найден.", show_alert=True)
            return
        
        # Получаем текущий статус и переключаем
        from shop_bot.data_manager.database import get_key_auto_renewal_enabled, set_key_auto_renewal_enabled
        current_status = get_key_auto_renewal_enabled(key_id)
        new_status = not current_status
        
        # Устанавливаем новый статус
        if set_key_auto_renewal_enabled(key_id, new_status):
            status_text = "включено" if new_status else "отключено"
            await callback.answer(f"✅ Автопродление для ключа {status_text}", show_alert=True)
            
            # Обновляем сообщение с информацией о ключе
            await show_key_handler(callback)
        else:
            await callback.answer("❌ Ошибка при изменении статуса автопродления.", show_alert=True)

    @user_router.callback_query(F.data.startswith("howto_vless_"))
    @registration_required
    async def show_instruction_handler(callback: types.CallbackQuery):
        await callback.answer()
        key_id = int(callback.data.split("_")[2])

        await callback.message.edit_text(
            HOWTO_CHOOSE_OS_MESSAGE,
            reply_markup=keyboards.create_howto_vless_keyboard_key(key_id),
            disable_web_page_preview=True
        )
    
    @user_router.callback_query(F.data == "howto_vless")
    @registration_required
    async def show_instruction_general_handler(callback: types.CallbackQuery):
        await callback.answer()

        await callback.message.edit_text(
            HOWTO_CHOOSE_OS_MESSAGE,
            reply_markup=keyboards.create_howto_vless_keyboard(),
            disable_web_page_preview=True
        )

    @user_router.callback_query(F.data == "howto_android")
    @registration_required
    @measure_performance("howto_android")
    async def howto_android_handler(callback: types.CallbackQuery):
        await callback.answer()
        await _send_instruction_with_video(callback, 'android', keyboards.create_howto_vless_keyboard)

    @user_router.callback_query(F.data == "howto_ios")
    @registration_required
    @measure_performance("howto_ios")
    async def howto_ios_handler(callback: types.CallbackQuery):
        await callback.answer()
        await _send_instruction_with_video(callback, 'ios', keyboards.create_howto_vless_keyboard)

    @user_router.callback_query(F.data == "howto_macos")
    @registration_required
    @measure_performance("howto_macos")
    async def howto_macos_handler(callback: types.CallbackQuery):
        await callback.answer()
        await _send_instruction_with_video(callback, 'macos', keyboards.create_howto_vless_keyboard)

    @user_router.callback_query(F.data == "howto_windows")
    @registration_required
    @measure_performance("howto_windows")
    async def howto_windows_handler(callback: types.CallbackQuery):
        await callback.answer()
        await _send_instruction_with_video(callback, 'windows', keyboards.create_howto_vless_keyboard)

    @user_router.callback_query(F.data == "howto_linux")
    @registration_required
    @measure_performance("howto_linux")
    async def howto_linux_handler(callback: types.CallbackQuery):
        await callback.answer()
        await _send_instruction_with_video(callback, 'linux', keyboards.create_howto_vless_keyboard)

    
    @user_router.callback_query(F.data == "back_to_instructions")
    @registration_required
    @measure_performance("back_to_instructions")
    async def back_to_instructions_handler(callback: types.CallbackQuery):
        """Возврат к выбору типа инструкции"""
        await callback.answer()
        
        await callback.message.edit_text(
            HOWTO_CHOOSE_OS_MESSAGE,
            reply_markup=keyboards.create_howto_vless_keyboard(),
            disable_web_page_preview=True
        )

    @user_router.callback_query(F.data == "video_instructions_list")
    @registration_required
    @measure_performance("video_instructions_list")
    async def video_instructions_list_handler(callback: types.CallbackQuery):
        """Показывает список видеоинструкций"""
        await callback.answer()
        
        from shop_bot.data_manager.database import get_all_video_instructions
        videos = get_all_video_instructions()
        
        if not videos:
            await callback.message.edit_text(
                "🎬 <b>Видеоинструкции</b>\n\n"
                "В данный момент видеоинструкции отсутствуют.",
                reply_markup=keyboards.create_back_to_instructions_keyboard(),
                parse_mode="HTML"
            )
            return
        
        text = "🎬 <b>Видеоинструкции</b>\n\n"
        for i, video in enumerate(videos, 1):
            text += f"{i}. <b>{video['title']}</b>\n"
            if video.get('file_size_mb'):
                text += f"   📁 Размер: {video['file_size_mb']:.2f} МБ\n"
            text += f"   📅 Загружено: {video['created_at']}\n\n"
        
        text += "Выберите видеоинструкцию для просмотра:"
        
        # Создаем клавиатуру с видеоинструкциями
        builder = InlineKeyboardBuilder()
        for video in videos:
            builder.button(
                text=f"▶️ {video['title']}", 
                callback_data=f"show_video_{video['video_id']}"
            )
        builder.button(text="⬅️ Назад к инструкциям", callback_data="back_to_instructions")
        builder.adjust(1)
        
        await callback.message.edit_text(
            text,
            reply_markup=builder.as_markup(),
            parse_mode="HTML"
        )

    @user_router.callback_query(F.data.startswith("show_video_"))
    @registration_required
    @measure_performance("show_video")
    async def show_video_handler(callback: types.CallbackQuery):
        """Показывает конкретное видеоинструкцию"""
        await callback.answer()
        
        try:
            video_id = int(callback.data.split("_")[2])
            from shop_bot.data_manager.database import get_video_instruction_by_id
            
            video = get_video_instruction_by_id(video_id)
            if not video:
                await callback.message.edit_text(
                    "❌ Видеоинструкция не найдена.",
                    reply_markup=keyboards.create_back_to_instructions_keyboard()
                )
                return
            
            # Отправляем видео если файл существует
            from pathlib import Path
            video_path = Path(PROJECT_ROOT) / "src" / "shop_bot" / "webhook_server" / "uploads" / "videos" / video['filename']
            
            if video_path.exists():
                with open(video_path, 'rb') as video_file:
                    video_input = BufferedInputFile(video_file.read(), filename=video['filename'])
                    await callback.message.answer_video(
                        video=video_input,
                        caption=f"🎬 <b>{video['title']}</b>\n\n"
                               f"📅 Загружено: {video['created_at']}",
                        reply_markup=keyboards.create_back_to_instructions_keyboard(),
                        parse_mode="HTML"
                    )
                # Удаляем предыдущее сообщение
                await callback.message.delete()
            else:
                await callback.message.edit_text(
                    f"❌ Файл видеоинструкции '{video['title']}' не найден.",
                    reply_markup=keyboards.create_back_to_instructions_keyboard()
                )
                
        except Exception as e:
            logger.error(f"Error showing video {video_id}: {e}")
            await callback.message.edit_text(
                "❌ Ошибка при загрузке видеоинструкции.",
                reply_markup=keyboards.create_back_to_instructions_keyboard()
            )

    @user_router.callback_query(F.data == "buy_new_key")
    @registration_required
    @measure_performance("buy_new_key")
    async def buy_new_key_handler(callback: types.CallbackQuery):
        await callback.answer()
        user_id = callback.from_user.id
        hosts = get_all_hosts()
        if not hosts:
            await callback.message.edit_text("❌ В данный момент нет доступных серверов для покупки.")
            return
        # Скрываем сервера без доступных тарифов (с учётом режима отображения)
        try:
            hosts_with_plans = [h for h in hosts if filter_plans_by_display_mode(get_plans_for_host(h['host_name']), user_id)]
        except Exception:
            hosts_with_plans = hosts
        if not hosts_with_plans:
            await callback.message.edit_text("❌ В данный момент нет доступных серверов для покупки.")
            return
        
        await callback.message.edit_text(
            "Выберите сервер, на котором хотите приобрести ключ:",
            reply_markup=keyboards.create_host_selection_keyboard(hosts_with_plans, action="new")
        )

    @user_router.callback_query(F.data.startswith("select_host_new_"))
    @registration_required
    async def select_host_for_purchase_handler(callback: types.CallbackQuery, state: FSMContext):
        await callback.answer()
        user_id = callback.from_user.id
        host_name = callback.data[len("select_host_new_"):]
        
        # Получаем текущие данные из state, чтобы сохранить промокод если он был применен
        current_data = await state.get_data()
        
        # Сохраняем host_name И промокод в состоянии для возможности возврата
        await state.update_data(
            selected_host=host_name,
            # Сохраняем промокод, если он был применен
            promo_code=current_data.get('promo_code'),
            promo_usage_id=current_data.get('promo_usage_id'),
            promo_data=current_data.get('promo_data')
        )
        
        plans = get_plans_for_host(host_name)
        
        # Фильтруем тарифы по режиму отображения для данного пользователя
        plans = filter_plans_by_display_mode(plans, user_id)
        
        if not plans:
            await callback.message.edit_text(f"❌ Для сервера \"{host_name}\" не настроены доступные тарифы.")
            return
        await callback.message.edit_text(
            f"Вы выбрали:\n\n✅ {host_name}\n\n➡️ Теперь выберите тариф для нового ключа:", 
            reply_markup=keyboards.create_plans_keyboard(plans, action="new", host_name=host_name)
        )

    @user_router.callback_query(F.data.startswith("extend_key_"))
    @registration_required
    @measure_performance("extend_key")
    async def extend_key_handler(callback: types.CallbackQuery):
        await callback.answer()

        try:
            key_id = int(callback.data.split("_")[2])
        except (IndexError, ValueError):
            await callback.message.edit_text("❌ Произошла ошибка. Неверный формат ключа.")
            return

        key_data = get_key_by_id(key_id)

        if not key_data or key_data['user_id'] != callback.from_user.id:
            await callback.message.edit_text("❌ Ошибка: Ключ не найден или не принадлежит вам.")
            return
        
        host_name = key_data.get('host_name')
        if not host_name:
            await callback.message.edit_text("❌ Ошибка: У этого ключа не указан сервер. Обратитесь в поддержку.")
            return

        plans = get_plans_for_host(host_name)
        
        # Фильтруем тарифы по режиму отображения для данного пользователя
        user_id = callback.from_user.id
        plans = filter_plans_by_display_mode(plans, user_id)

        if not plans:
            await callback.message.edit_text(
                f"❌ Извините, для сервера \"{host_name}\" в данный момент не настроены доступные тарифы для продления."
            )
            return

        await callback.message.edit_text(
            f"Выберите тариф для продления ключа на сервере \"{host_name}\":",
            reply_markup=keyboards.create_plans_keyboard(
                plans=plans,
                action="extend",
                host_name=host_name,
                key_id=key_id
            )
        )

    @user_router.callback_query(F.data.startswith("buy_"))
    @registration_required
    @measure_performance("plan_selection")
    async def plan_selection_handler(callback: types.CallbackQuery, state: FSMContext):
        await callback.answer()
        
        parts = callback.data.split("_")[1:]
        action = parts[-2]
        key_id = int(parts[-1])
        plan_id = int(parts[-3])
        host_name = "_".join(parts[:-3])

        # Получаем текущие данные из state, чтобы сохранить промокод если он был применен
        current_data = await state.get_data()
        
        # Если есть промокод, но нет final_price, рассчитываем его
        final_price = current_data.get('final_price')
        if not final_price and current_data.get('promo_data'):
            from shop_bot.data_manager.database import get_plan_by_id
            from decimal import Decimal
            plan = get_plan_by_id(plan_id)
            if plan:
                promo_data = current_data.get('promo_data')
                base_price = Decimal(str(plan['price']))
                final_price = base_price
                
                # Применяем скидку по сумме
                if promo_data.get('discount_amount', 0) > 0:
                    final_price = max(Decimal('0'), base_price - Decimal(str(promo_data['discount_amount'])))
                
                # Применяем скидку по проценту
                if promo_data.get('discount_percent', 0) > 0:
                    discount_amount = base_price * Decimal(str(promo_data['discount_percent'])) / 100
                    final_price = max(Decimal('0'), base_price - discount_amount)
                
                final_price = float(final_price)
                logger.info(f"DEBUG plan_selection: Calculated final_price={final_price} from promo_data")
        
        await state.update_data(
            action=action,
            key_id=key_id,
            plan_id=plan_id,
            host_name=host_name,
            host_code=_resolve_host_code(host_name),
            # Сохраняем промокод и финальную цену, если они были применены ранее
            promo_code=current_data.get('promo_code'),
            final_price=final_price,
            promo_usage_id=current_data.get('promo_usage_id'),
            promo_data=current_data.get('promo_data'),
            customer_email=None,
        )

        message_text, reply_markup = await _build_payment_method_prompt(state, callback.from_user.id)
        await callback.message.edit_text(message_text, reply_markup=reply_markup)
        await state.set_state(PaymentProcess.waiting_for_payment_method)


    async def _build_payment_method_prompt(state: FSMContext, user_id: int) -> tuple[str, InlineKeyboardMarkup]:
        """
        Собирает текст и клавиатуру для выбора способа оплаты на основе текущего состояния.
        """
        data = await state.get_data()
        from shop_bot.data_manager.database import get_user_balance, get_plan_by_id

        user_balance = get_user_balance(user_id)
        plan_id = data.get('plan_id')
        host_name = data.get('host_name')
        plan_info = get_plan_by_id(plan_id) if plan_id else None

        if plan_info:
            final_price = data.get('final_price')
            promo_code = data.get('promo_code')
            promo_data = data.get('promo_data')

            if final_price is not None:
                price_to_show = float(final_price)
                original_price = float(plan_info.get('price', 0))
            elif promo_data:
                base_price = float(plan_info.get('price', 0))
                price_to_show = base_price
                if promo_data.get('discount_amount', 0) > 0:
                    price_to_show = max(0, base_price - float(promo_data['discount_amount']))
                if promo_data.get('discount_percent', 0) > 0:
                    discount_amount = base_price * float(promo_data['discount_percent']) / 100
                    price_to_show = max(0, base_price - discount_amount)
                original_price = base_price
            else:
                price_to_show = float(plan_info.get('price', 0))
                original_price = None

            message_text = get_payment_method_message_with_plan(
                host_name=host_name,
                plan_name=plan_info.get('plan_name', 'Неизвестный тариф'),
                price=price_to_show,
                original_price=original_price,
                promo_code=promo_code,
            )
        else:
            message_text = CHOOSE_PAYMENT_METHOD_MESSAGE

        reply_markup = keyboards.create_payment_method_keyboard(
            payment_methods=PAYMENT_METHODS,
            action=data.get('action'),
            key_id=data.get('key_id'),
            user_balance=float(user_balance or 0),
        )

        return message_text, reply_markup

    @user_router.callback_query(StateFilter(PaymentProcess.waiting_for_email, PaymentProcess.waiting_for_payment_method, PaymentProcess.waiting_for_payment), F.data == "back_to_plans")
    @measure_performance("back_to_plans")
    async def back_to_plans_handler(callback: types.CallbackQuery, state: FSMContext):
        await callback.answer()
        current_state = await state.get_state()
        data = await state.get_data()
        action = data.get('action')
        host_name = data.get('host_name')
        host_code = data.get('host_code')
        if not host_code:
            host_code = _resolve_host_code(host_name)
        key_id = data.get('key_id', 0)
        user_id = callback.from_user.id

        # Очищаем промокод при возврате из состояния выбора способа оплаты или ожидания оплаты
        if current_state in (PaymentProcess.waiting_for_payment_method.state, PaymentProcess.waiting_for_payment.state):
            await _cleanup_promo_usage_if_needed(callback.from_user.id, data)

        # Очищаем состояние, но сохраняем selected_host и промокод для возможности дальнейшего возврата
        selected_host = data.get('selected_host')
        promo_code = data.get('promo_code')
        final_price = data.get('final_price')
        promo_usage_id = data.get('promo_usage_id')
        promo_data = data.get('promo_data')
        
        await state.clear()
        
        # Восстанавливаем selected_host и промокод если они были применены
        update_dict = {}
        if selected_host:
            update_dict['selected_host'] = selected_host
        if promo_code:
            update_dict['promo_code'] = promo_code
            if final_price is not None:
                update_dict['final_price'] = final_price
            if promo_usage_id is not None:
                update_dict['promo_usage_id'] = promo_usage_id
            if promo_data is not None:
                update_dict['promo_data'] = promo_data
        
        if update_dict:
            await state.update_data(**update_dict)

        if action == 'new' and host_name:
            # Возвращаемся к выбору тарифа для конкретного хоста
            plans = get_plans_for_host(host_name)
            plans = filter_plans_by_display_mode(plans, user_id)
            
            if not plans:
                await callback.message.edit_text(f"❌ Для сервера \"{host_name}\" не настроены доступные тарифы.")
                return
            
            await callback.message.edit_text(
                f"Вы выбрали:\n\n✅ {host_name}\n\n➡️ Теперь выберите тариф для нового ключа:", 
                reply_markup=keyboards.create_plans_keyboard(plans, action="new", host_name=host_name)
            )
        elif action == 'extend' and key_id:
            # Для продления возвращаемся к extend_key_handler через изменение callback.data
            callback.data = f"extend_key_{key_id}"
            await extend_key_handler(callback)
        else:
            await back_to_main_menu_handler(callback)

    async def _cleanup_promo_usage_if_needed(user_id: int, data: dict) -> None:
        promo_code = data.get('promo_code')
        if not promo_code:
            return

        try:
            from shop_bot.data_manager.database import (
                get_promo_code_by_code,
                get_user_promo_codes,
                remove_user_promo_code_usage,
            )

            promo_data = get_promo_code_by_code(promo_code, "shop")
            if not promo_data:
                return

            user_promo_codes = get_user_promo_codes(user_id, "shop")
            usage_id = None
            for promo in user_promo_codes:
                if promo['promo_id'] == promo_data['promo_id']:
                    usage_id = promo['usage_id']
                    break

            if usage_id:
                success = remove_user_promo_code_usage(user_id=user_id, usage_id=usage_id, bot="shop")
                if success:
                    logger.info(f"Removed promo code usage for cancelled purchase: {promo_code} for user {user_id}")
                else:
                    logger.error(f"Failed to remove promo code usage for cancelled purchase: {promo_code} for user {user_id}")
            else:
                logger.warning(f"Usage ID not found for promo code {promo_code} and user {user_id}")
        except Exception as e:
            logger.error(f"Error removing promo code usage for cancelled purchase: {e}", exc_info=True)


    @user_router.message(PaymentProcess.waiting_for_email)
    @measure_performance("process_email")
    async def process_email_handler(message: types.Message, state: FSMContext):
        if is_valid_email(message.text):
            await state.update_data(customer_email=message.text)
            await message.answer(f"✅ Email принят: {message.text}")

            message_text, reply_markup = await _build_payment_method_prompt(state, message.chat.id)
            await message.answer(message_text, reply_markup=reply_markup)
            await state.set_state(PaymentProcess.waiting_for_payment_method)
            logger.info(f"User {message.chat.id}: State set to waiting_for_payment_method")
        else:
            await message.answer("❌ Неверный формат email. Попробуйте еще раз.")

    @user_router.callback_query(PaymentProcess.waiting_for_email, F.data == "skip_email")
    @measure_performance("skip_email")
    async def skip_email_handler(callback: types.CallbackQuery, state: FSMContext):
        await callback.answer()
        await state.update_data(customer_email=None)

        message_text, reply_markup = await _build_payment_method_prompt(state, callback.from_user.id)
        await callback.message.edit_text(message_text, reply_markup=reply_markup)
        await state.set_state(PaymentProcess.waiting_for_payment_method)
        logger.info(f"User {callback.from_user.id}: State set to waiting_for_payment_method")

    # ====== Topup flow payments via Stars and TON Connect ======
    @user_router.callback_query(TopupProcess.waiting_for_payment_method, F.data == "topup_pay_stars")
    @measure_performance("topup_pay_stars")
    async def topup_pay_stars(callback: types.CallbackQuery, state: FSMContext):
        await callback.answer("Подготовка оплаты через Stars...")
        data = await state.get_data()
        user_id = callback.from_user.id
        amount_rub = Decimal(str(data.get('topup_amount', 0)))
        if amount_rub <= 0:
            await callback.message.edit_text("❌ Некорректная сумма пополнения.")
            await state.clear()
            return
        conversion_rate = Decimal(str(get_setting("stars_conversion_rate") or "1.79"))
        if conversion_rate <= 0:
            conversion_rate = Decimal("1.0")
        price_stars = int((amount_rub / conversion_rate).quantize(Decimal("1"), rounding=ROUND_CEILING))
        if price_stars < 1:
            price_stars = 1

        # Сохраняем данные для последующего создания инвойса
        await state.update_data(
            topup_amount_stars=price_stars,
            topup_amount_rub=float(amount_rub),
            topup_conversion_rate=float(conversion_rate)
        )

        # Показываем клавиатуру с кнопками оплаты
        from src.shop_bot.bot.keyboards import create_stars_payment_keyboard
        keyboard = create_stars_payment_keyboard(price_stars, is_topup=True)
        
        text = (
            f"💳 **Пополнение баланса через Telegram Stars**\n\n"
            f"💰 Сумма: {amount_rub} RUB\n"
            f"⭐ К оплате: {price_stars} звезд\n\n"
            f"Нажмите кнопку ниже для создания счета на оплату."
        )
        
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="Markdown")

    @user_router.callback_query(TopupProcess.waiting_for_payment_method, F.data == "confirm_stars_payment")
    @measure_performance("confirm_topup_stars_payment")
    async def confirm_topup_stars_payment(callback: types.CallbackQuery, state: FSMContext):
        """Обработчик подтверждения оплаты звездами для пополнения"""
        await callback.answer("Создаю счет на пополнение через Stars...")
        data = await state.get_data()
        user_id = callback.from_user.id
        
        amount_rub = data.get('topup_amount_rub', 0)
        price_stars = data.get('topup_amount_stars', 0)
        conversion_rate = data.get('topup_conversion_rate', 1.79)
        
        if amount_rub <= 0 or price_stars <= 0:
            await callback.message.edit_text("❌ Некорректные данные для оплаты.")
            await state.clear()
            return

        try:
            invoice = types.LabeledPrice(label=f"Пополнение баланса", amount=price_stars)

            payment_metadata = {
                'user_id': user_id,
                'price': float(amount_rub),
                'operation': 'topup',
                'payment_method': 'Stars',
                'stars_rate': float(conversion_rate),
                'chat_id': callback.message.chat.id,
                'message_id': callback.message.message_id
            }
            payment_id = str(uuid.uuid4())
            payment_metadata['payment_id'] = payment_id

            # Сохраняем pending транзакцию
            create_pending_stars_transaction(
                payment_id=payment_id,
                user_id=user_id,
                amount_rub=float(amount_rub),
                amount_stars=price_stars,
                metadata=payment_metadata
            )

            await callback.message.answer_invoice(
                title=f"Пополнение баланса",
                description=f"Пополнение кошелька в боте",
                payload=payment_id,
                provider_token="",
                currency="XTR",
                prices=[invoice]
            )
            await state.clear()
        except Exception as e:
            logger.error(f"Failed to create Stars topup invoice: {e}", exc_info=True)
            await callback.message.answer("❌ Не удалось создать счет для пополнения звездами. Попробуйте позже.")
            await state.clear()

    @user_router.callback_query(TopupProcess.waiting_for_payment_method, F.data == "topup_stars_payment_failed")
    @measure_performance("topup_stars_payment_failed")
    async def topup_stars_payment_failed(callback: types.CallbackQuery, state: FSMContext):
        """Обработчик кнопки 'Не удалось заплатить' для пополнения"""
        from src.shop_bot.bot.keyboards import create_stars_payment_failed_keyboard
        
        text = (
            "💳 **Возможно вы не смогли заплатить из-за отсутствия валютной карты.**\n\n"
            "Иногда ваш счет в Telegram может или мог быть привязанным к ранее существовавшим VISA/Master картам.\n\n"
            "Можно купить звезды по карте РФ через официального \"Premium Bot\""
        )
        
        keyboard = create_stars_payment_failed_keyboard(is_topup=True)
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="Markdown")

    @user_router.callback_query(TopupProcess.waiting_for_payment_method, F.data == "topup_back_to_payment_methods")
    @registration_required
    @measure_performance("topup_back_to_payment_methods")
    async def topup_back_to_payment_methods(callback: types.CallbackQuery, state: FSMContext):
        """Возврат к выбору методов оплаты для пополнения"""
        await callback.answer()
        from src.shop_bot.bot.keyboards import create_topup_payment_methods_keyboard
        
        data = await state.get_data()
        amount_rub = data.get('topup_amount', 0)
        
        text = (
            f"💳 **Выберите способ оплаты**\n\n"
            f"💰 Сумма пополнения: {amount_rub} RUB\n\n"
            f"Выберите удобный способ оплаты:"
        )
        
        keyboard = create_topup_payment_methods_keyboard()
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="Markdown")

    @user_router.callback_query(TopupProcess.waiting_for_payment_method, F.data == "topup_pay_tonconnect")
    @measure_performance("topup_pay_tonconnect")
    async def topup_pay_tonconnect(callback: types.CallbackQuery, state: FSMContext):
        await callback.answer("Готовлю оплату через TON Connect...")
        data = await state.get_data()
        user_id = callback.from_user.id
        amount_rub = Decimal(str(data.get('topup_amount', 0)))
        if amount_rub <= 0:
            await callback.message.edit_text("❌ Некорректная сумма пополнения.")
            await state.clear()
            return

        usdt_rub_rate = await get_usdt_rub_rate()
        ton_usdt_rate = await get_ton_usdt_rate()
        if not usdt_rub_rate or not ton_usdt_rate:
            await callback.message.edit_text("❌ Не удалось получить курс TON. Попробуйте позже.")
            await state.clear()
            return

        price_ton = (amount_rub / usdt_rub_rate / ton_usdt_rate).quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)
        amount_nanoton = int(price_ton * 1_000_000_000)

        payment_id = str(uuid.uuid4())
        metadata = {
            'user_id': user_id,
            'price': float(amount_rub),
            'operation': 'topup',
            'payment_method': 'TON Connect',
            'payment_id': payment_id
        }

        # Сохраняем pending транзакцию с TON суммой
        create_pending_ton_transaction(payment_id, user_id, float(amount_rub), float(price_ton), metadata, payment_link=None)

        wallet_address = get_setting("ton_wallet_address")
        if not wallet_address:
            await callback.message.edit_text("❌ TON кошелек не настроен. Обратитесь к администратору.")
            await state.clear()
            return

        transaction_payload = {
            'valid_until': int(datetime.now().timestamp()) + 600,
            'messages': [{
                'address': wallet_address,
                'amount': amount_nanoton
            }]
        }

        try:
            bot_instance = getattr(callback, 'bot', None)
            if bot_instance is None and hasattr(callback, 'message'):
                bot_instance = getattr(callback.message, 'bot', None)
            if bot_instance is None:
                from aiogram import Bot
                bot_instance = Bot.get_current()
            connect_url = await _start_ton_connect_process(user_id, transaction_payload, metadata, bot_instance)
            qr_img = qrcode.make(connect_url)
            bio = BytesIO()
            qr_img.save(bio, "PNG")
            qr_file = BufferedInputFile(bio.getvalue(), "ton_qr.png")
            await callback.message.delete()
            await callback.message.answer_photo(
                photo=qr_file,
                caption=(
                    f"💎 Оплата пополнения через TON Connect\n\n"
                    f"Сумма к оплате: `{price_ton}` TON\n\n"
                    f"Нажмите 'Открыть кошелек' или отсканируйте QR-код."
                ),
                parse_mode="Markdown",
                reply_markup=keyboards.create_ton_connect_keyboard(connect_url)
            )
            await state.clear()
        except Exception as e:
            logger.error(f"Failed to generate TON Connect link for topup: {e}", exc_info=True)
            await callback.message.answer("❌ Не удалось создать ссылку для TON Connect. Попробуйте позже.")
            await state.clear()

    @user_router.callback_query(TopupProcess.waiting_for_payment_method, F.data == "topup_pay_yookassa")
    @measure_performance("topup_pay_yookassa")
    async def topup_pay_yookassa(callback: types.CallbackQuery, state: FSMContext):
        await callback.answer("Создаю ссылку на оплату пополнения...")
        
        data = await state.get_data()
        user_id = callback.from_user.id
        amount_rub = Decimal(str(data.get('topup_amount', 0)))
        
        if amount_rub <= 0:
            await callback.message.edit_text("❌ Некорректная сумма пополнения.")
            await state.clear()
            return

        try:
            price_str_for_api = f"{amount_rub:.2f}"
            price_float_for_metadata = float(amount_rub)

            # Определяем тестовый режим для YooKassa
            yookassa_test_mode = get_setting("yookassa_test_mode") == "true"

            # КРИТИЧЕСКИ ВАЖНО: Переинициализируем Configuration перед созданием платежа
            _reconfigure_yookassa()
            
            # Логируем активный режим после переинициализации
            from yookassa import Configuration
            logger.info(
                f"[YOOKASSA_PAYMENT_TOPUP] user_id={user_id}, amount={amount_rub} RUB, "
                f"test_mode={yookassa_test_mode}, "
                f"active_shop_id={Configuration.account_id[:8] if Configuration.account_id else 'None'}..."
            )

            return_url = get_yookassa_return_url()
            payment_payload = {
                "amount": {"value": price_str_for_api, "currency": "RUB"},
                "confirmation": {"type": "redirect", "return_url": return_url},
                "capture": True,
                "description": "Пополнение баланса",
                "test": yookassa_test_mode,  # Критически важно для определения режима YooKassa
                "metadata": {
                    "user_id": user_id,
                    "price": price_float_for_metadata,
                    "operation": "topup",
                    "payment_method": "YooKassa",
                    "host_code": data.get('host_code')
                }
            }
            
            # Логируем return_url для диагностики
            logger.info(
                f"[YOOKASSA_PAYMENT_TOPUP] Created payment payload with return_url: {return_url}"
            )

            if _should_use_yookassa_stub():
                stub_payment_id = f"stub-{uuid.uuid4()}"
                stub_metadata = {
                    "user_id": user_id,
                    "price": price_float_for_metadata,
                    "operation": "topup",
                    "payment_method": "YooKassa",
                    "host_code": data.get('host_code'),
                    "payment_id": stub_payment_id,
                    "yookassa_stub": True
                }
                create_pending_transaction(stub_payment_id, user_id, float(amount_rub), stub_metadata)
                await state.clear()
                await callback.message.edit_text(
                    "🧪 Тестовый режим YooKassa: пополнение выполнено локально.\n\n"
                    "Обработка зачисления...",
                    reply_markup=keyboards.create_back_to_menu_keyboard()
                )
                try:
                    await process_successful_payment(callback.message.bot, stub_metadata)
                except Exception as stub_error:
                    logger.error(f"Failed to process YooKassa stub topup: {stub_error}", exc_info=True)
                    await callback.message.answer("❌ Ошибка при обработке тестового пополнения YooKassa.")
                return

            # Выполняем создание платежа в отдельном потоке с таймаутом, чтобы не блокировать event loop
            start_time = time.time()
            try:
                payment = await asyncio.wait_for(
                    asyncio.to_thread(Payment.create, payment_payload, uuid.uuid4()),
                    timeout=30.0
                )
                elapsed_time = time.time() - start_time
                logger.info(
                    f"[YOOKASSA_PAYMENT_TOPUP] Payment created successfully in {elapsed_time:.2f}s, "
                    f"payment_id={payment.id}"
                )
            except asyncio.TimeoutError:
                elapsed_time = time.time() - start_time
                logger.error(
                    f"[YOOKASSA_PAYMENT_TOPUP] Timeout after {elapsed_time:.2f}s while creating topup payment "
                    f"for user_id={user_id}"
                )
                await callback.message.answer(
                    "❌ Не удалось создать ссылку на оплату. Пожалуйста, попробуйте снова или выберите другой "
                    "способ оплаты. Если проблема повториться обратитесь в службу поддержки"
                )
                await state.clear()
                return
            except Exception as e:
                elapsed_time = time.time() - start_time
                logger.error(
                    f"[YOOKASSA_PAYMENT_TOPUP] Failed to create topup payment after {elapsed_time:.2f}s: {e}",
                    exc_info=True
                )
                await callback.message.answer(
                    "❌ Не удалось создать ссылку на оплату. Пожалуйста, попробуйте снова или выберите другой "
                    "способ оплаты. Если проблема повториться обратитесь в службу поддержки"
                )
                await state.clear()
                return
            
            # Создаем транзакцию в базе данных
            payment_metadata = {
                "user_id": user_id,
                "price": price_float_for_metadata,
                "operation": "topup",
                "payment_method": "YooKassa",
                "host_code": data.get('host_code')
            }
            create_pending_transaction(payment.id, user_id, float(amount_rub), payment_metadata)
            
            await state.clear()
            
            await callback.message.edit_text(
                f"💳 Пополнение баланса на {amount_rub:.2f} RUB\n\nНажмите на кнопку ниже для оплаты:",
                reply_markup=keyboards.create_payment_keyboard(payment.confirmation.confirmation_url, back_callback=None)
            )
        except Exception as e:
            logger.error(f"Failed to create YooKassa topup payment: {e}", exc_info=True)
            await callback.message.answer(
                "❌ Не удалось создать ссылку на оплату. Пожалуйста, попробуйте снова или выберите другой "
                "способ оплаты. Если проблема повториться обратитесь в службу поддержки"
            )
            await state.clear()

    async def show_payment_options(message: types.Message, state: FSMContext):
        data = await state.get_data()
        user_data = get_user(message.chat.id)
        plan = get_plan_by_id(data.get('plan_id'))
        
        if not plan:
            await message.edit_text("❌ Ошибка: Тариф не найден.")
            await state.clear()
            return

        price = Decimal(str(plan['price']))
        
        # Проверяем, есть ли уже примененная скидка (промокод) в state
        state_final_price = data.get('final_price')
        promo_data = data.get('promo_data')
        
        if state_final_price is not None:
            final_price = Decimal(str(state_final_price))
            discount_applied = True
        elif promo_data:
            # Применяем скидку из promo_data
            final_price = price
            
            # Применяем скидку по сумме
            if promo_data.get('discount_amount', 0) > 0:
                final_price = max(Decimal('0'), price - Decimal(str(promo_data['discount_amount'])))
            
            # Применяем скидку по проценту
            if promo_data.get('discount_percent', 0) > 0:
                discount_amount = price * Decimal(str(promo_data['discount_percent'])) / 100
                final_price = max(Decimal('0'), price - discount_amount)
            
            discount_applied = True
        else:
            final_price = price
            discount_applied = False
        
        # Базовое сообщение с информацией о тарифе
        host_name = data.get('host_name', 'Неизвестный хост')
        host_code = _resolve_host_code(host_name)
        promo_code = data.get('promo_code')
        
        if discount_applied and state_final_price is not None:
            # Если есть скидка, используем улучшенную функцию
            message_text = get_payment_method_message_with_plan(
                host_name=host_name,
                plan_name=plan.get('plan_name', 'Неизвестный тариф'),
                price=float(final_price),
                original_price=float(price),
                promo_code=promo_code
            )
        else:
            # Обычное сообщение без скидки
            message_text = get_payment_method_message_with_plan(
                host_name=host_name,
                plan_name=plan.get('plan_name', 'Неизвестный тариф'),
                price=float(price)
            )

        # Применяем реферальную скидку только если нет промокода
        if not discount_applied and user_data.get('referred_by') and user_data.get('total_spent', 0) == 0:
            discount_percentage_str = get_setting("referral_discount") or "0"
            discount_percentage = Decimal(discount_percentage_str)
            
            if discount_percentage > 0:
                discount_amount = (price * discount_percentage / 100).quantize(Decimal("0.01"))
                final_price = price - discount_amount

                message_text = (
                    f"🎉 Как приглашенному пользователю, на вашу первую покупку предоставляется скидка {discount_percentage_str}%!\n"
                    f"Старая цена: <s>{price:.2f} RUB</s>\n"
                    f"<b>Новая цена: {final_price:.2f} RUB</b>\n\n"
                ) + message_text

        # Обновляем final_price в state
        await state.update_data(final_price=float(final_price))

        from shop_bot.data_manager.database import get_user_balance
        user_balance = get_user_balance(message.chat.id)
        await message.edit_text(
            message_text,
            reply_markup=keyboards.create_payment_method_keyboard(
                payment_methods=PAYMENT_METHODS,
                action=data.get('action'),
                key_id=data.get('key_id'),
                user_balance=float(user_balance or 0)
            )
        )
        await state.set_state(PaymentProcess.waiting_for_payment_method)
        
    @user_router.callback_query(PaymentProcess.waiting_for_payment_method, F.data == "apply_promo_code")
    @measure_performance("apply_promo_code")
    async def apply_promo_code_handler(callback: types.CallbackQuery, state: FSMContext):
        await callback.answer()
        await callback.message.edit_text(
            "🎫 Введите промокод для получения скидки:\n\n"
            "Промокод должен быть введен точно как указано (с учетом регистра).",
            reply_markup=keyboards.create_back_to_payment_methods_keyboard()
        )
        await state.set_state(PaymentProcess.waiting_for_promo_code)

    @user_router.message(PaymentProcess.waiting_for_promo_code)
    @measure_performance("process_promo_code")
    async def process_promo_code_handler(message: types.Message, state: FSMContext):
        promo_code = message.text.strip()
        
        # Валидируем промокод
        from shop_bot.data_manager.database import can_user_use_promo_code, get_user_balance
        user_id = message.from_user.id
        validation_result = can_user_use_promo_code(user_id, promo_code, "shop")
        
        if validation_result['can_use']:
            # Сохраняем промокод и данные в state
            await state.update_data(
                promo_code=promo_code,
                promo_data=validation_result['promo_data'],
                promo_usage_id=validation_result.get('existing_usage_id')
            )
            
            # Применяем скидку
            promo_data = validation_result['promo_data']
            existing_usage_id = validation_result.get('existing_usage_id')
            data = await state.get_data()
            plan_id = data.get('plan_id')
            plan = get_plan_by_id(plan_id)
            
            if plan:
                base_price = Decimal(str(plan['price']))
                final_price = base_price
                
                # Применяем скидку по сумме
                if promo_data.get('discount_amount', 0) > 0:
                    final_price = max(Decimal('0'), base_price - Decimal(str(promo_data['discount_amount'])))
                
                # Применяем скидку по проценту
                if promo_data.get('discount_percent', 0) > 0:
                    discount_amount = base_price * Decimal(str(promo_data['discount_percent'])) / 100
                    final_price = max(Decimal('0'), base_price - discount_amount)
                
                # Обновляем цену в state
                await state.update_data(final_price=float(final_price))
                
                # ЗАПИСЫВАЕМ ИСПОЛЬЗОВАНИЕ ПРОМОКОДА СО СТАТУСОМ 'applied'
                try:
                    from shop_bot.data_manager.database import record_promo_code_usage, add_to_user_balance
                    success = record_promo_code_usage(
                        promo_id=promo_data['promo_id'],
                        user_id=user_id,
                        bot="shop",
                        plan_id=plan_id,
                        discount_amount=promo_data.get('discount_amount', 0.0),
                        discount_percent=promo_data.get('discount_percent', 0.0),
                        discount_bonus=promo_data.get('discount_bonus', 0.0),
                        metadata={"source": "manual_input"},
                        status='applied',
                        existing_usage_id=existing_usage_id
                    )
                    if not success:
                        # Если не удалось записать использование, откатываем применение промокода
                        logger.error(f"Failed to record promo code usage: {promo_code} for user {user_id}")
                        await message.answer(
                            "❌ Ошибка при применении промокода. Попробуйте еще раз или обратитесь в поддержку.",
                            reply_markup=keyboards.create_back_to_payment_methods_keyboard()
                        )
                        return
                    else:
                        logger.info(f"Successfully recorded promo code usage: {promo_code} for user {user_id}")
                        
                        # Получаем usage_id для последующего обновления статуса
                        from shop_bot.data_manager.database import get_promo_usage_id
                        usage_id = get_promo_usage_id(promo_data['promo_id'], user_id, "shop")
                        if usage_id:
                            await state.update_data(promo_usage_id=usage_id)
                        
                        # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: Зачисляем discount_bonus ТОЛЬКО если existing_usage_id отсутствует
                        # Это предотвращает многократное начисление бонуса при повторном применении промокода
                        bonus_amount = promo_data.get('discount_bonus', 0.0)
                        if not existing_usage_id and bonus_amount > 0:
                            add_to_user_balance(user_id, bonus_amount)
                            logger.info(f"Added {bonus_amount} RUB bonus to user {user_id} balance from promo code {promo_code} (first time)")
                        elif existing_usage_id and bonus_amount > 0:
                            logger.info(f"Bonus NOT added for user {user_id} from promo code {promo_code} (already applied, existing_usage_id={existing_usage_id})")
                except Exception as e:
                    logger.error(f"Error recording promo code usage: {e}", exc_info=True)
                    await message.answer(
                        "❌ Произошла ошибка при применении промокода. Попробуйте еще раз или обратитесь в поддержку.",
                        reply_markup=keyboards.create_back_to_payment_methods_keyboard()
                    )
                    return
                
                # Формируем сообщение с использованием улучшенной функции
                host_name = data.get('host_name', 'Неизвестный хост')
                plan_name = plan.get('plan_name', 'Неизвестный тариф')
                
                message_text = f"✅ Промокод '{promo_code}' применен!\n\n"
                
                # Добавляем информацию о бонусе, если он есть
                bonus_amount = promo_data.get('discount_bonus', 0.0)
                if bonus_amount > 0:
                    message_text += f"🎁 Бонус на баланс: {bonus_amount} RUB\n\n"
                
                # Используем улучшенную функцию для отображения информации о тарифе
                message_text += get_payment_method_message_with_plan(
                    host_name=host_name,
                    plan_name=plan_name,
                    price=float(final_price),
                    original_price=float(base_price),
                    promo_code=promo_code
                )
                
                await message.answer(
                    message_text,
                    reply_markup=keyboards.create_payment_method_keyboard(
                        payment_methods=PAYMENT_METHODS,
                        action=data.get('action'),
                        key_id=data.get('key_id'),
                        user_balance=float(get_user_balance(user_id) or 0)
                    )
                )
                await state.set_state(PaymentProcess.waiting_for_payment_method)
            else:
                await message.answer("❌ Ошибка при применении промокода. Попробуйте еще раз.")
        else:
            await message.answer(
                f"❌ {validation_result['message']}\n\n"
                "Проверьте правильность написания промокода.\n"
                "Промокод должен быть введен точно как указано (с учетом регистра).",
                reply_markup=keyboards.create_back_to_payment_methods_keyboard()
            )

    @user_router.callback_query(PaymentProcess.waiting_for_promo_code, F.data == "back_to_payment_methods")
    @measure_performance("back_to_payment_methods")
    async def back_to_payment_methods_handler(callback: types.CallbackQuery, state: FSMContext):
        await callback.answer()
        data = await state.get_data()
        from shop_bot.data_manager.database import get_user_balance, get_plan_by_id
        user_balance = get_user_balance(callback.from_user.id)
        
        # Получаем информацию о выбранном тарифе
        plan_id = data.get('plan_id')
        host_name = data.get('host_name')
        plan_info = get_plan_by_id(plan_id) if plan_id else None
        
        if plan_info:
            # Используем final_price из state, если он есть (применена скидка)
            final_price = data.get('final_price')
            promo_code = data.get('promo_code')
            promo_data = data.get('promo_data')
            
            logger.info(f"DEBUG back_to_payment_methods: final_price={final_price}, promo_code={promo_code}, promo_data={promo_data}")
            
            if final_price is not None:
                price_to_show = float(final_price)
                original_price = float(plan_info.get('price', 0))
            elif promo_data:
                # Применяем скидку из promo_data
                base_price = float(plan_info.get('price', 0))
                price_to_show = base_price
                
                # Применяем скидку по сумме
                if promo_data.get('discount_amount', 0) > 0:
                    price_to_show = max(0, base_price - float(promo_data['discount_amount']))
                
                # Применяем скидку по проценту
                if promo_data.get('discount_percent', 0) > 0:
                    discount_amount = base_price * float(promo_data['discount_percent']) / 100
                    price_to_show = max(0, base_price - discount_amount)
                
                original_price = base_price
                logger.info(f"DEBUG: Applied promo discount: base_price={base_price}, final_price={price_to_show}")
            else:
                price_to_show = float(plan_info.get('price', 0))
                original_price = None
            
            message_text = get_payment_method_message_with_plan(
                host_name=host_name,
                plan_name=plan_info.get('plan_name', 'Неизвестный тариф'),
                price=price_to_show,
                original_price=original_price,
                promo_code=promo_code
            )
        else:
            message_text = CHOOSE_PAYMENT_METHOD_MESSAGE
        
        await callback.message.edit_text(
            message_text,
            reply_markup=keyboards.create_payment_method_keyboard(
                payment_methods=PAYMENT_METHODS,
                action=data.get('action'),
                key_id=data.get('key_id'),
                user_balance=float(user_balance or 0)
            )
        )
        await state.set_state(PaymentProcess.waiting_for_payment_method)

    @user_router.callback_query(PaymentProcess.waiting_for_payment_method, F.data == "back_to_email_prompt")
    @measure_performance("back_to_email_prompt")
    async def back_to_email_prompt_handler(callback: types.CallbackQuery, state: FSMContext):
        await back_to_plans_handler(callback, state)



    @user_router.callback_query(PaymentProcess.waiting_for_payment_method, F.data == "pay_yookassa")
    @measure_performance("create_yookassa_payment")
    async def create_yookassa_payment_handler(callback: types.CallbackQuery, state: FSMContext):
        await callback.answer("Создаю ссылку на оплату...")
        
        data = await state.get_data()
        user_data = get_user(callback.from_user.id)
        
        plan_id = data.get('plan_id')
        plan = get_plan_by_id(plan_id)

        if not plan:
            await callback.message.edit_text("❌ Ошибка: Тариф не найден.")
            await state.clear()
            return

        # days/traffic для оплаты
        plan_days = int(plan.get('days') or 0)
        plan_traffic_gb = float(plan.get('traffic_gb') or 0)
        await state.update_data(plan_days=plan_days, plan_traffic_gb=plan_traffic_gb)

        base_price = Decimal(str(plan['price']))
        price_rub = base_price

        # Проверяем, есть ли применённый промокод
        promo_code = data.get('promo_code')
        if promo_code:
            # Используем финальную цену с учетом промокода
            final_price = data.get('final_price')
            if final_price is not None:
                price_rub = Decimal(str(final_price))
        elif user_data.get('referred_by') and user_data.get('total_spent', 0) == 0:
            discount_percentage_str = get_setting("referral_discount") or "0"
            discount_percentage = Decimal(discount_percentage_str)
            if discount_percentage > 0:
                discount_amount = (base_price * discount_percentage / 100).quantize(Decimal("0.01"))
                price_rub = base_price - discount_amount

        plan_id = data.get('plan_id')
        customer_email = data.get('customer_email')
        host_name = data.get('host_name')
        action = data.get('action')
        key_id = data.get('key_id')
        host_code = data.get('host_code')
        if not host_code:
            resolved_host_code = _resolve_host_code(host_name)
            if not resolved_host_code:
                logger.warning(
                    "[YOOKASSA_PAYMENT_PURCHASE] Не удалось определить host_code для пользователя %s "
                    "и host_name '%s'. Использую безопасное значение по умолчанию.",
                    callback.from_user.id,
                    host_name
                )
                resolved_host_code = ""
            host_code = resolved_host_code
            try:
                await state.update_data(host_code=host_code)
            except Exception as update_error:
                logger.error(
                    "[YOOKASSA_PAYMENT_PURCHASE] Не удалось сохранить host_code в состоянии FSM: %s",
                    update_error,
                    exc_info=True
                )
        
        if not customer_email:
            customer_email = get_setting("receipt_email")

        plan = get_plan_by_id(plan_id)
        if not plan:
            await callback.message.answer("Произошла ошибка при выборе тарифа.")
            await state.clear()
            return

        months = plan['months']
        days = int(plan.get('days') or 0)
        hours = int(plan.get('hours') or 0)
        user_id = callback.from_user.id

        # Проверяем, если цена 0 рублей - обрабатываем бесплатно
        if price_rub == 0:
            await callback.message.edit_text("🎉 Бесплатный тариф! Обрабатываю ваш запрос...")
            
            # Получаем данные из state
            action = data.get('action')
            key_id = data.get('key_id')
            host_name = data.get('host_name')
            
            # Создаем ключ бесплатно
            try:
                email = ""
                host_code_for_search = None
                if action == "new":
                    key_number = get_next_key_number(user_id)
                    try:
                        from shop_bot.data_manager.database import get_host
                        host_rec = get_host(host_name)
                        host_code_for_email = (host_rec.get('host_code') or host_name).replace(' ', '').lower() if host_rec else host_name.replace(' ', '').lower()
                        host_code_for_search = host_rec.get('host_code') if host_rec else None
                    except Exception:
                        host_code_for_email = host_name.replace(' ', '').lower()
                        host_code_for_search = None
                    email = f"user{user_id}-key{key_number}@{host_code_for_email}.bot"
                    comment = f"{user_id}"
                elif action == "extend":
                    key_data = get_key_by_id(key_id)
                    if not key_data or key_data['user_id'] != user_id:
                        await callback.message.edit_text("❌ Ошибка: ключ для продления не найден.")
                        await state.clear()
                        return
                    email = key_data['key_email']
                    comment = f"{user_id}"
                    # Получаем host_code из ключа
                    try:
                        from shop_bot.data_manager.database import get_host
                        key_host_name = key_data.get('host_name')
                        if key_host_name:
                            host_rec = get_host(key_host_name)
                            if host_rec:
                                host_code_for_search = host_rec.get('host_code')
                    except Exception as e:
                        logger.warning(f"Failed to get host_code from key {key_id}: {e}")
                
                # Учитываем месяцы, дни и ЧАСЫ тарифа
                extra_days = int(plan.get('days') or 0) if plan else 0
                extra_hours = int(plan.get('hours') or 0) if plan else 0
                if extra_hours < 0:
                    extra_hours = 0
                if extra_hours > 24:
                    extra_hours = 24
                days_to_add = months * 30 + extra_days + (extra_hours / 24)
                
                # Для новых ключей формируем subscription заранее
                subscription = None
                telegram_chat_id = None
                if action == "new":
                    user_data = get_user(user_id)
                    username = user_data.get('username', '') if user_data else ''
                    subscription = f"{user_id}-{username}".lower().replace('@', '')
                    telegram_chat_id = user_id
                elif action == "extend":
                    # Получаем существующий subscription из key_data для обновления подписки
                    existing_subscription = key_data.get('subscription')
                    if existing_subscription:
                        subscription = existing_subscription
                    else:
                        logger.warning(f"Subscription not found for key_id={key_id}, email={email} during renewal. Subscription may not update correctly.")
                
                result = await xui_api.create_or_update_key_on_host(
                    host_name=host_name,
                    email=email,
                    days_to_add=days_to_add,
                    comment=comment,
                    sub_id=subscription,
                    telegram_chat_id=telegram_chat_id,
                    host_code=host_code_for_search
                )

                if not result:
                    await callback.message.edit_text(
                        "❌ Не удалось создать/обновить ключ в панели.\n\n"
                        "Возможные причины:\n"
                        "• Временная недоступность сервера\n"
                        "• Проблемы с сетью\n\n"
                        "Попробуйте позже или обратитесь в поддержку."
                    )
                    await state.clear()
                    return

                if action == "new":
                    
                    key_id = add_new_key(
                        user_id,
                        host_name,
                        result['client_uuid'],
                        result['email'],
                        result['expiry_timestamp_ms'],
                        connection_string=result.get('connection_string') or "",
                        plan_name=plan['plan_name'],
                        price=0.0,
                        subscription=subscription,
                        subscription_link=result.get('subscription_link'),
                        telegram_chat_id=telegram_chat_id,
                        comment=f"Бесплатный ключ для пользователя {fullname or username or user_id}"
                    )
                elif action == "extend":
                    update_key_info(key_id, result['client_uuid'], result['expiry_timestamp_ms'], result.get('subscription_link'))
                
                # Обновляем статистику
                update_user_stats(user_id, 0, months)
                
                # Логируем транзакцию
                user_info = get_user(user_id)
                log_username = user_info.get('username', 'N/A') if user_info else 'N/A'
                log_metadata = json.dumps({
                    "plan_id": plan_id,
                    "plan_name": plan['plan_name'],
                    "host_name": host_name,
                    "customer_email": customer_email
                })

                log_transaction(
                    username=log_username,
                    transaction_id=None,
                    payment_id=str(uuid.uuid4()),
                    user_id=user_id,
                    status='paid',
                    amount_rub=0.0,
                    amount_currency=None,
                    currency_name=None,
                    payment_method='Free',
                    metadata=log_metadata
                )
                
                # Отправляем результат пользователю
                connection_string = result['connection_string']
                new_expiry_date = datetime.fromtimestamp(result['expiry_timestamp_ms'] / 1000)
                
                all_user_keys = get_user_keys(user_id)
                key_number = next((i + 1 for i, key in enumerate(all_user_keys) if key['key_id'] == key_id), len(all_user_keys))

                # Получаем режим предоставления из тарифа
                provision_mode = plan.get('key_provision_mode', 'key')
                subscription_link = None
                
                # Если нужна подписка - получаем subscription link
                if provision_mode in ['subscription', 'both']:
                    try:
                        subscription_link = await xui_api.get_client_subscription_link(host_name, email)
                        if not subscription_link:
                            logger.warning(f"Failed to get subscription link for {email}, using key-only mode")
                            provision_mode = 'key'
                    except Exception as e:
                        logger.error(f"Error getting subscription link: {e}")
                        provision_mode = 'key'

                feature_enabled, user_timezone = _get_user_timezone_context(user_id)
                
                # Получаем данные для информации о тарифе
                plan_name = plan.get('plan_name') if plan else None
                plan_price = plan.get('price') if plan else None
                is_trial_key = False  # Бесплатный ключ не является триалом

                final_text = get_purchase_success_text(
                    action="создан" if action == "new" else "продлен",
                    key_number=key_number,
                    expiry_date=new_expiry_date,
                    connection_string=connection_string,
                    subscription_link=subscription_link,
                    provision_mode=provision_mode,
                    user_timezone=user_timezone,
                    feature_enabled=feature_enabled,
                    user_id=user_id,
                    key_id=key_id,
                    host_name=host_name,
                    plan_name=plan_name,
                    price=plan_price,
                    status=None,  # Для нового ключа статус еще не определен
                    is_trial=is_trial_key,
                )
                
                # Проверяем, что key_id не None перед созданием клавиатуры
                if key_id is not None:
                    await callback.message.edit_text(
                        text=final_text,
                        reply_markup=keyboards.create_key_info_keyboard(key_id, subscription_link),
                        parse_mode=ParseMode.HTML,
                    )
                else:
                    await callback.message.edit_text(
                        text=final_text,
                        parse_mode=ParseMode.HTML,
                    )
                
                await state.clear()
                return
                
            except Exception as e:
                logger.error(f"Error processing free plan for user {user_id}: {e}", exc_info=True)
                await callback.message.edit_text("❌ Ошибка при выдаче бесплатного ключа.")
                await state.clear()
                return

        try:
            price_str_for_api = f"{price_rub:.2f}"
            price_float_for_metadata = float(price_rub)

            # Определяем тестовый режим для YooKassa
            yookassa_test_mode = get_setting("yookassa_test_mode") == "true"
            
            # КРИТИЧЕСКИ ВАЖНО: Переинициализируем Configuration перед созданием платежа
            _reconfigure_yookassa()
            
            # Логируем активный режим после переинициализации
            from yookassa import Configuration
            logger.info(
                f"[YOOKASSA_PAYMENT_PURCHASE] user_id={user_id}, plan_id={plan_id}, amount={price_rub} RUB, "
                f"test_mode={yookassa_test_mode}, "
                f"active_shop_id={Configuration.account_id[:8] if Configuration.account_id else 'None'}..., "
                f"api_url={getattr(Configuration, 'api_url', 'default')}"
            )

            receipt = None
            if customer_email and is_valid_email(customer_email):
                receipt = {
                    "customer": {"email": customer_email},
                    "items": [{
                        "description": "Подписка на сервис",
                        "quantity": "1.00",
                        "amount": {"value": price_str_for_api, "currency": "RUB"},
                        "vat_code": "1"
                    }]
                }
            return_url = get_yookassa_return_url()
            payment_payload = {
                "amount": {"value": price_str_for_api, "currency": "RUB"},
                "confirmation": {"type": "redirect", "return_url": return_url},
                "capture": True,
                "description": "Подписка на сервис",
                "test": yookassa_test_mode,  # Критически важно для определения режима YooKassa
                "metadata": {
                    "user_id": user_id, "months": months, "days": days, "hours": hours, "price": price_float_for_metadata, 
                    "action": action, "key_id": key_id, "host_name": host_name,
                    "plan_id": plan_id, "customer_email": customer_email,
                    "host_code": host_code,
                    "payment_method": "YooKassa", "promo_code": data.get('promo_code')
                }
            }
            if receipt:
                payment_payload['receipt'] = receipt
            
            # Логируем return_url для диагностики
            logger.info(
                f"[YOOKASSA_PAYMENT_PURCHASE] Created payment payload with return_url: {return_url}"
            )

            payment_metadata = {
                "user_id": user_id,
                "months": months,
                "days": days,
                "hours": hours,
                "price": price_float_for_metadata,
                "action": action,
                "key_id": key_id,
                "host_name": host_name,
                "host_code": host_code,
                "plan_id": plan_id,
                "plan_name": plan.get('plan_name', ''),  # Добавляем plan_name в metadata
                "customer_email": customer_email,
                "payment_method": "YooKassa",
                "promo_code": data.get('promo_code'),
                "promo_usage_id": data.get('promo_usage_id')
            }

            if _should_use_yookassa_stub():
                stub_payment_id = f"stub-{uuid.uuid4()}"
                stub_metadata = dict(payment_metadata)
                stub_metadata.update({
                    "payment_id": stub_payment_id,
                    "yookassa_stub": True
                })
                # Для stub режима создаем фиктивный payment_payload для api_request
                stub_payment_payload = dict(payment_payload)
                stub_payment_payload['id'] = stub_payment_id
                create_pending_transaction(
                    stub_payment_id, 
                    user_id, 
                    float(price_rub), 
                    stub_metadata,
                    payment_link=None,  # Stub не имеет реальной ссылки
                    api_request=json.dumps(stub_payment_payload, ensure_ascii=False)
                )
                # Очищаем состояние для stub режима, так как платеж обрабатывается сразу
                await state.clear()
                await callback.message.edit_text(
                    "🧪 Тестовый режим YooKassa: платеж эмулирован локально.\n\n"
                    "Выдаю доступ...",
                    reply_markup=keyboards.create_back_to_menu_keyboard()
                )
                try:
                    await process_successful_payment(callback.message.bot, stub_metadata)
                except Exception as stub_error:
                    logger.error(f"Failed to process YooKassa stub purchase: {stub_error}", exc_info=True)
                    await callback.message.answer("❌ Ошибка при обработке тестового платежа YooKassa.")
                return

            # Выполняем создание платежа в отдельном потоке с таймаутом, чтобы не блокировать event loop
            start_time = time.time()
            try:
                payment = await asyncio.wait_for(
                    asyncio.to_thread(Payment.create, payment_payload, uuid.uuid4()),
                    timeout=30.0
                )
                elapsed_time = time.time() - start_time
                logger.info(
                    f"[YOOKASSA_PAYMENT_PURCHASE] Payment created successfully in {elapsed_time:.2f}s, "
                    f"payment_id={payment.id}"
                )
            except asyncio.TimeoutError:
                elapsed_time = time.time() - start_time
                logger.error(
                    f"[YOOKASSA_PAYMENT_PURCHASE] Timeout after {elapsed_time:.2f}s while creating payment "
                    f"for user_id={user_id}"
                )
                await callback.message.answer(
                    "❌ Не удалось создать ссылку на оплату. Пожалуйста, попробуйте снова или выберите другой "
                    "способ оплаты. Если проблема повториться обратитесь в службу поддержки"
                )
                await state.clear()
                return
            except Exception as e:
                elapsed_time = time.time() - start_time
                logger.error(
                    f"[YOOKASSA_PAYMENT_PURCHASE] Failed to create payment after {elapsed_time:.2f}s: {e}",
                    exc_info=True
                )
                await callback.message.answer(
                    "❌ Не удалось создать ссылку на оплату. Пожалуйста, попробуйте снова или выберите другой "
                    "способ оплаты. Если проблема повториться обратитесь в службу поддержки"
                )
                await state.clear()
                return
            
            # Создаем транзакцию в базе данных с сохранением payment_link и api_request
            create_pending_transaction(
                payment.id, 
                user_id, 
                float(price_rub), 
                payment_metadata,
                payment_link=payment.confirmation.confirmation_url if payment.confirmation else None,
                api_request=json.dumps(payment_payload, ensure_ascii=False)
            )
            
            # Устанавливаем состояние ожидания оплаты вместо очистки
            await state.set_state(PaymentProcess.waiting_for_payment)
            
            # Формируем текст с информацией о выбранных параметрах
            plan_name = plan.get('plan_name', 'Неизвестный тариф')
            price_text = f"{float(price_rub):.2f} RUB"
            payment_method_text = "СБП / Банковская карта" if get_setting("sbp_enabled") == "true" else "Банковская карта"
            
            payment_text = (
                "Вы выбрали:\n\n"
                f"✅ Хост: {host_name}\n"
                f"✅ Тариф: {plan_name}\n"
                f"✅ Стоимость: {price_text}\n"
                f"✅ Способ оплаты: {payment_method_text}\n\n"
                "➡️ Для оплаты нажмите на кнопку:"
            )
            
            await callback.message.edit_text(
                payment_text,
                reply_markup=keyboards.create_payment_keyboard(payment.confirmation.confirmation_url)
            )
        except Exception as e:
            logger.error(f"Failed to create YooKassa payment: {e}", exc_info=True)
            await callback.message.answer(
                "❌ Не удалось создать ссылку на оплату. Пожалуйста, попробуйте снова или выберите другой "
                "способ оплаты. Если проблема повториться обратитесь в службу поддержки"
            )
            await state.clear()

    @user_router.callback_query(PaymentProcess.waiting_for_payment_method, F.data == "pay_cryptobot")
    @measure_performance("create_cryptobot_invoice")
    async def create_cryptobot_invoice_handler(callback: types.CallbackQuery, state: FSMContext):
        await callback.answer("Создаю счет в Crypto Pay...")
        
        data = await state.get_data()
        user_data = get_user(callback.from_user.id)
        
        plan_id = data.get('plan_id')
        user_id = data.get('user_id', callback.from_user.id)
        customer_email = data.get('customer_email')
        host_name = data.get('host_name')
        action = data.get('action')
        key_id = data.get('key_id')

        cryptobot_token = get_setting('cryptobot_token')
        if not cryptobot_token:
            logger.error(f"Attempt to create Crypto Pay invoice failed for user {user_id}: cryptobot_token is not set.")
            await callback.message.edit_text("❌ Оплата криптовалютой временно недоступна. (Администратор не указал токен).")
            await state.clear()
            return

        plan = get_plan_by_id(plan_id)
        if not plan:
            logger.error(f"Attempt to create Crypto Pay invoice failed for user {user_id}: Plan with id {plan_id} not found.")
            await callback.message.edit_text("❌ Произошла ошибка при выборе тарифа.")
            await state.clear()
            return
        
        plan_id = data.get('plan_id')
        plan = get_plan_by_id(plan_id)

        if not plan:
            await callback.message.answer("Произошла ошибка при выборе тарифа.")
            await state.clear()
            return

        base_price = Decimal(str(plan['price']))
        price_rub = base_price

        if user_data.get('referred_by') and user_data.get('total_spent', 0) == 0:
            discount_percentage_str = get_setting("referral_discount") or "0"
            discount_percentage = Decimal(discount_percentage_str)
            if discount_percentage > 0:
                discount_amount = (base_price * discount_percentage / 100).quantize(Decimal("0.01"))
                price_rub = base_price - discount_amount
        months = plan['months']
        days = int(plan.get('days') or 0)
        hours = int(plan.get('hours') or 0)
        
        try:
            exchange_rate = await get_usdt_rub_rate()

            if not exchange_rate:
                logger.warning("Failed to get live exchange rate. Falling back to the rate from settings.")
                if not exchange_rate:
                    await callback.message.edit_text("❌ Не удалось получить курс валют. Попробуйте позже.")
                    await state.clear()
                    return

            margin = Decimal("1.03")
            price_usdt = (price_rub / exchange_rate * margin).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            
            logger.info(f"Creating Crypto Pay invoice for user {user_id}. Plan price: {price_rub} RUB. Converted to: {price_usdt} USDT.")

            crypto = CryptoPay(cryptobot_token)
            
            payload_data = f"{user_id}:{months}:{days}:{hours}:{float(price_rub)}:{action}:{key_id}:{host_name}:{plan_id}:{customer_email}:CryptoBot"

            invoice = await crypto.create_invoice(
                currency_type="fiat",
                fiat="RUB",
                amount=float(price_rub),
                description="Подписка на сервис",
                payload=payload_data,
                expires_in=3600
            )
            
            if not invoice or not invoice.pay_url:
                raise Exception("Failed to create invoice or pay_url is missing.")

            # Устанавливаем состояние ожидания оплаты вместо очистки
            await state.set_state(PaymentProcess.waiting_for_payment)
            
            await callback.message.edit_text(
                "Нажмите на кнопку ниже для оплаты:",
                reply_markup=keyboards.create_payment_keyboard(invoice.pay_url)
            )

        except Exception as e:
            logger.error(f"Failed to create Crypto Pay invoice for user {user_id}: {e}", exc_info=True)
            await callback.message.edit_text(f"❌ Не удалось создать счет для оплаты криптовалютой.\n\n<pre>Ошибка: {e}</pre>")
            await state.clear()
        
    @user_router.callback_query(PaymentProcess.waiting_for_payment_method, F.data == "pay_heleket")
    @measure_performance("create_heleket_invoice")
    async def create_heleket_invoice_handler(callback: types.CallbackQuery, state: FSMContext):
        await callback.answer("Создаю счет Heleket...")
        
        data = await state.get_data()
        plan = get_plan_by_id(data.get('plan_id'))
        user_data = get_user(callback.from_user.id)
        
        if not plan:
            await callback.message.edit_text("❌ Произошла ошибка при выборе тарифа.")
            await state.clear()
            return

        plan_id = data.get('plan_id')
        plan = get_plan_by_id(plan_id)

        if not plan:
            await callback.message.answer("Произошла ошибка при выборе тарифа.")
            await state.clear()
            return

        base_price = Decimal(str(plan['price']))
        price_rub_decimal = base_price

        if user_data.get('referred_by') and user_data.get('total_spent', 0) == 0:
            discount_percentage_str = get_setting("referral_discount") or "0"
            discount_percentage = Decimal(discount_percentage_str)
            if discount_percentage > 0:
                discount_amount = (base_price * discount_percentage / 100).quantize(Decimal("0.01"))
                price_rub_decimal = base_price - discount_amount
        months = plan['months']
        days = int(plan.get('days') or 0)
        hours = int(plan.get('hours') or 0)
        
        final_price_float = float(price_rub_decimal)

        pay_url = await _create_heleket_payment_request(
            user_id=callback.from_user.id,
            price=final_price_float,
            months=plan['months'],
            days=days,
            hours=hours,
            host_name=data.get('host_name'),
            state_data=data
        )
        
        if pay_url:
            # Устанавливаем состояние ожидания оплаты вместо очистки
            await state.set_state(PaymentProcess.waiting_for_payment)
            
            await callback.message.edit_text(
                "Нажмите на кнопку ниже для оплаты:",
                reply_markup=keyboards.create_payment_keyboard(pay_url)
            )
        else:
            await callback.message.edit_text("❌ Не удалось создать счет Heleket. Попробуйте другой способ оплаты.")

    @user_router.callback_query(PaymentProcess.waiting_for_payment_method, F.data == "pay_tonconnect")
    @measure_performance("create_ton_invoice")
    async def create_ton_invoice_handler(callback: types.CallbackQuery, state: FSMContext):
        logger.info(f"User {callback.from_user.id}: Entered create_ton_invoice_handler.")
        data = await state.get_data()
        user_id = callback.from_user.id
        wallet_address = get_setting("ton_wallet_address")
        plan = get_plan_by_id(data.get('plan_id'))
        
        if not wallet_address or not plan:
            await callback.message.edit_text("❌ Оплата через TON временно недоступна.")
            await state.clear()
            return
            
        # Проверяем формат адреса кошелька
        if not wallet_address.startswith('EQ') and not wallet_address.startswith('UQ'):
            await callback.message.edit_text("❌ Неверный формат адреса TON кошелька. Адрес должен начинаться с EQ или UQ.")
            await state.clear()
            return

        await callback.answer("Создаю ссылку и QR-код для TON Connect...")
        
        # Используем явную проверку на None, чтобы корректно обрабатывать случай когда final_price = 0
        final_price_from_state = data.get('final_price')
        if final_price_from_state is not None:
            price_rub = Decimal(str(final_price_from_state))
        else:
            price_rub = Decimal(str(plan['price']))

        usdt_rub_rate = await get_usdt_rub_rate()
        ton_usdt_rate = await get_ton_usdt_rate()

        if not usdt_rub_rate or not ton_usdt_rate:
            await callback.message.edit_text("❌ Не удалось получить курс TON. Попробуйте позже.")
            await state.clear()
            return

        # Проверяем, если цена 0 рублей - обрабатываем бесплатно
        if price_rub == 0:
            await callback.message.edit_text("🎉 Бесплатный тариф! Обрабатываю ваш запрос...")
            
            # Получаем данные из state
            action = data.get('action')
            key_id = data.get('key_id')
            host_name = data.get('host_name')
            
            # Создаем ключ бесплатно
            try:
                email = ""
                host_code_for_search = None
                if action == "new":
                    key_number = get_next_key_number(user_id)
                    # Строим email на основе стабильного host_code (если есть)
                    try:
                        from shop_bot.data_manager.database import get_host
                        host_rec = get_host(host_name)
                        host_code_for_email = (host_rec.get('host_code') or host_name).replace(' ', '').lower() if host_rec else host_name.replace(' ', '').lower()
                        host_code_for_search = host_rec.get('host_code') if host_rec else None
                    except Exception:
                        host_code_for_email = host_name.replace(' ', '').lower()
                        host_code_for_search = None
                    email = f"user{user_id}-key{key_number}@{host_code_for_email}.bot"
                    comment = f"{user_id}"
                elif action == "extend":
                    key_data = get_key_by_id(key_id)
                    if not key_data or key_data['user_id'] != user_id:
                        await callback.message.edit_text("❌ Ошибка: ключ для продления не найден.")
                        await state.clear()
                        return
                    email = key_data['key_email']
                    comment = f"{user_id}"
                    # Получаем host_code из ключа
                    try:
                        from shop_bot.data_manager.database import get_host
                        key_host_name = key_data.get('host_name')
                        if key_host_name:
                            host_rec = get_host(key_host_name)
                            if host_rec:
                                host_code_for_search = host_rec.get('host_code')
                    except Exception as e:
                        logger.warning(f"Failed to get host_code from key {key_id}: {e}")
                
                months = plan['months']
                plan_id = plan['plan_id']
                extra_days = int(plan.get('days') or 0)
                extra_hours = int(plan.get('hours') or 0)
                if extra_hours < 0:
                    extra_hours = 0
                if extra_hours > 24:
                    extra_hours = 24
                days_to_add = months * 30 + extra_days + (extra_hours / 24)
                
                # Для новых ключей формируем subscription заранее
                subscription = None
                telegram_chat_id = None
                if action == "new":
                    user_data = get_user(user_id)
                    username = user_data.get('username', '') if user_data else ''
                    subscription = f"{user_id}-{username}".lower().replace('@', '')
                    telegram_chat_id = user_id
                elif action == "extend":
                    # Получаем существующий subscription из key_data для обновления подписки
                    existing_subscription = key_data.get('subscription')
                    if existing_subscription:
                        subscription = existing_subscription
                    else:
                        logger.warning(f"Subscription not found for key_id={key_id}, email={email} during renewal. Subscription may not update correctly.")
                
                result = await xui_api.create_or_update_key_on_host(
                    host_name=host_name,
                    email=email,
                    days_to_add=days_to_add,
                    comment=comment,
                    sub_id=subscription,
                    telegram_chat_id=telegram_chat_id,
                    host_code=host_code_for_search
                )

                if not result:
                    await callback.message.edit_text(
                        "❌ Не удалось создать/обновить ключ в панели.\n\n"
                        "Возможные причины:\n"
                        "• Временная недоступность сервера\n"
                        "• Проблемы с сетью\n\n"
                        "Попробуйте позже или обратитесь в поддержку."
                    )
                    await state.clear()
                    return

                if action == "new":
                    
                    key_id = add_new_key(
                        user_id,
                        host_name,
                        result['client_uuid'],
                        result['email'],
                        result['expiry_timestamp_ms'],
                        connection_string=result.get('connection_string') or "",
                        plan_name=plan['plan_name'],
                        price=0.0,
                        subscription=subscription,
                        subscription_link=result.get('subscription_link'),
                        telegram_chat_id=telegram_chat_id,
                        comment=f"Бесплатный ключ для пользователя {fullname or username or user_id}"
                    )
                elif action == "extend":
                    update_key_info(key_id, result['client_uuid'], result['expiry_timestamp_ms'], result.get('subscription_link'))
                
                # Обновляем статистику
                update_user_stats(user_id, 0, months)
                
                # Логируем транзакцию
                user_info = get_user(user_id)
                log_username = user_info.get('username', 'N/A') if user_info else 'N/A'
                log_metadata = json.dumps({
                    "plan_id": plan_id,
                    "plan_name": plan['plan_name'],
                    "host_name": host_name,
                    "customer_email": data.get('customer_email')
                })

                log_transaction(
                    username=log_username,
                    transaction_id=None,
                    payment_id=str(uuid.uuid4()),
                    user_id=user_id,
                    status='paid',
                    amount_rub=0.0,
                    amount_currency=None,
                    currency_name=None,
                    payment_method='Free',
                    metadata=log_metadata
                )
                
                # Отправляем результат пользователю
                connection_string = result['connection_string']
                new_expiry_date = datetime.fromtimestamp(result['expiry_timestamp_ms'] / 1000)
                
                all_user_keys = get_user_keys(user_id)
                key_number = next((i + 1 for i, key in enumerate(all_user_keys) if key['key_id'] == key_id), len(all_user_keys))

                # Получаем provision_mode из тарифа
                provision_mode = 'key'  # по умолчанию
                subscription_link = result.get('subscription_link')
                if plan:
                    provision_mode = plan.get('key_provision_mode', 'key')
                
                # Если нужна подписка, но subscription_link отсутствует в результате - получаем дополнительно
                if provision_mode in ['subscription', 'both'] and not subscription_link:
                    try:
                        subscription_link = await xui_api.get_client_subscription_link(host_name, email)
                        if not subscription_link:
                            logger.warning(f"Failed to get subscription link for {email}, using key-only mode")
                            provision_mode = 'key'
                    except Exception as e:
                        logger.error(f"Error getting subscription link: {e}")
                        provision_mode = 'key'

                feature_enabled, user_timezone = _get_user_timezone_context(user_id)
                
                # Получаем данные для информации о тарифе
                plan_name = plan.get('plan_name') if plan else None
                plan_price = plan.get('price') if plan else None
                is_trial_key = False  # Бесплатный ключ не является триалом

                final_text = get_purchase_success_text(
                    action="создан" if action == "new" else "продлен",
                    key_number=key_number,
                    expiry_date=new_expiry_date,
                    connection_string=connection_string,
                    subscription_link=subscription_link,
                    provision_mode=provision_mode,
                    user_timezone=user_timezone,
                    feature_enabled=feature_enabled,
                    user_id=user_id,
                    key_id=key_id,
                    host_name=host_name,
                    plan_name=plan_name,
                    price=plan_price,
                    status=None,  # Для нового ключа статус еще не определен
                    is_trial=is_trial_key,
                )
                
                # Проверяем, что key_id не None перед созданием клавиатуры
                if key_id is not None:
                    await callback.message.edit_text(
                        text=final_text,
                        reply_markup=keyboards.create_key_info_keyboard(key_id, subscription_link),
                        parse_mode=ParseMode.HTML,
                    )
                else:
                    await callback.message.edit_text(
                        text=final_text,
                        parse_mode=ParseMode.HTML,
                    )
                
                await state.clear()
                return
                
            except Exception as e:
                logger.error(f"Error processing free plan for user {user_id}: {e}", exc_info=True)
                await callback.message.edit_text("❌ Ошибка при выдаче бесплатного ключа.")
                await state.clear()
                return

        price_ton = (price_rub / usdt_rub_rate / ton_usdt_rate).quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)
        amount_nanoton = int(price_ton * 1_000_000_000)
        
        payment_id = str(uuid.uuid4())
        metadata = {
            "user_id": user_id, "months": plan['months'], "days": int(plan.get('days') or 0), "hours": int(plan.get('hours') or 0), "price": float(price_rub),
            "action": data.get('action'), "key_id": data.get('key_id'),
            "host_name": data.get('host_name'), "plan_id": data.get('plan_id'),
            "plan_name": plan['plan_name'],  # Добавляем название плана
            "customer_email": data.get('customer_email'), "payment_method": "TON Connect",
            "payment_id": payment_id, "promo_code": data.get('promo_code'),  # Добавляем payment_id и promo_code в metadata
            "promo_usage_id": data.get('promo_usage_id')  # Добавляем promo_usage_id для обновления статуса
        }
        # Создаем ссылку для TON Connect (будет обновлена после создания)
        payment_link = f"https://t.me/wallet?attach=wallet&startattach=tonconnect-v__2-id__{payment_id[:8]}-r__--7B--22manifestUrl--22--3A--22https--3A--2F--2Fparis--2Edark--2Dmaximus--2Ecom--2F--2Ewell--2Dknown--2Ftonconnect--2Dmanifest--2Ejson--22--2C--22items--22--3A--5B--7B--22name--22--3A--22ton--5Faddr--22--7D--5D--7D"
        
        # Сохраняем pending транзакцию с правильными ценами и ссылкой
        create_pending_ton_transaction(payment_id, user_id, float(price_rub), float(price_ton), metadata, payment_link)

        # Создаем простой payload без комментария для TON Connect
        transaction_payload = {
            'valid_until': int(datetime.now().timestamp()) + 600,
            'messages': [{
                'address': wallet_address, 
                'amount': amount_nanoton
                # Убираем payload - он ломает TON Connect
            }]
        }
        
        # Логируем данные для отладки
        logger.info(f"TON Connect Debug - Wallet: {wallet_address}, Amount: {amount_nanoton}, Price TON: {price_ton}")
        logger.info(f"TON Connect Debug - Transaction payload: {transaction_payload}")

        try:
            # Получаем текущий экземпляр бота
            bot_instance = getattr(callback, 'bot', None)
            if bot_instance is None and hasattr(callback, 'message'):
                bot_instance = getattr(callback.message, 'bot', None)
            if bot_instance is None:
                try:
                    from aiogram import Bot
                    bot_instance = Bot.get_current()
                except Exception as e:
                    logger.debug(f"Failed to get bot instance for TON Connect: {e}")
                    bot_instance = None
            
            connect_url = await _start_ton_connect_process(user_id, transaction_payload, metadata, bot_instance)
            
            qr_img = qrcode.make(connect_url)
            bio = BytesIO()
            qr_img.save(bio, "PNG")
            qr_file = BufferedInputFile(bio.getvalue(), "ton_qr.png")

            await callback.message.delete()
            
            # Формируем текст с информацией о выбранных параметрах
            plan_name = plan.get('plan_name', 'Неизвестный тариф')
            host_name = data.get('host_name', 'Неизвестный хост')
            price_text = f"{price_ton} TON"
            
            caption_text = (
                "Вы выбрали:\n\n"
                f"✅ Хост: {host_name}\n"
                f"✅ Тариф: {plan_name}\n"
                f"✅ Стоимость: {price_text}\n"
                f"✅ Способ оплаты: 💎 TON Connect\n\n"
                "➡️ Для оплаты нажмите на кнопку или отсканируйте QR-код:\n\n"
                "💰 Способ 1 (на телефоне): Нажмите кнопку 'Открыть кошелек' ниже.\n\n"
                "📱 Способ 2 (на компьютере): Отсканируйте QR-код кошельком.\n\n"
                "После подключения кошелька подтвердите транзакцию."
            )
            
            await callback.message.answer_photo(
                photo=qr_file,
                caption=caption_text,
                reply_markup=keyboards.create_ton_connect_keyboard(connect_url)
            )
            await state.clear()

        except Exception as e:
            logger.error(f"Failed to generate TON Connect link for user {user_id}: {e}", exc_info=True)
            await callback.message.answer("❌ Не удалось создать ссылку для TON Connect. Попробуйте позже.")
            await state.clear()

    @user_router.callback_query(PaymentProcess.waiting_for_payment_method, F.data == "pay_stars")
    @measure_performance("create_stars_invoice")
    async def create_stars_invoice_handler(callback: types.CallbackQuery, state: FSMContext):
        logger.info(f"User {callback.from_user.id}: Entered create_stars_invoice_handler.")
        try:
            await callback.answer("Подготовка оплаты через Stars...")
            data = await state.get_data()

            user_id = callback.from_user.id
            plan_id = data.get('plan_id')
            action = data.get('action')
            key_id = int(data.get('key_id') or 0)
            host_name = data.get('host_name')
            customer_email = data.get('customer_email')

            plan = get_plan_by_id(plan_id)
            if not plan:
                await callback.message.edit_text("❌ Ошибка: Тариф не найден.")
                await state.clear()
                return

            months = int(data.get('months') or 0) or int((plan or {}).get('months') or 0)
            days = int(plan.get('days') or 0)
            hours = int(plan.get('hours') or 0)
            # Используем явную проверку на None, чтобы корректно обрабатывать случай когда final_price = 0
            final_price_from_state = data.get('final_price')
            if final_price_from_state is not None:
                price_rub = float(final_price_from_state)
            else:
                price_rub = float((plan or {}).get('price') or 0)

            # Бесплатный тариф — обрабатываем без счета
            if price_rub == 0:
                await callback.message.edit_text("🎉 Бесплатный тариф! Обрабатываю ваш запрос...")
                metadata = {
                    "user_id": user_id,
                    "months": months,
                    "days": days,
                    "hours": hours,
                    "price": 0.0,
                    "action": action,
                    "key_id": key_id,
                    "host_name": host_name,
                    "plan_id": plan_id,
                    "plan_name": plan.get('plan_name'),
                    "customer_email": customer_email,
                    "payment_method": "Stars",
                    "payment_id": str(uuid.uuid4()),
                    "promo_code": data.get('promo_code')
                }
                await process_successful_payment(callback.bot, metadata)
                await state.clear()
                return

            # Рассчитываем сумму в звездах
            conversion_rate = Decimal(str(get_setting("stars_conversion_rate") or "1.79"))
            if conversion_rate <= 0:
                conversion_rate = Decimal("1.0")
            amount_stars = int((Decimal(str(price_rub)) / conversion_rate).quantize(Decimal("1"), rounding=ROUND_CEILING))
            if amount_stars < 1:
                amount_stars = 1

            # Сохраняем данные для последующего создания инвойса
            await state.update_data(
                stars_amount_stars=amount_stars,
                stars_price_rub=price_rub,
                stars_conversion_rate=float(conversion_rate),
                stars_plan=plan,
                stars_metadata={
                    "user_id": user_id,
                    "months": months,
                    "days": days,
                    "hours": hours,
                    "action": action,
                    "key_id": key_id,
                    "host_name": host_name,
                    "plan_id": int(plan_id),
                    "customer_email": customer_email,
                    "promo_code": data.get('promo_code'),
                    "promo_usage_id": data.get('promo_usage_id')  # Добавляем promo_usage_id для обновления статуса
                }
            )

            # Показываем клавиатуру с кнопками оплаты
            from src.shop_bot.bot.keyboards import create_stars_payment_keyboard
            keyboard = create_stars_payment_keyboard(amount_stars, is_topup=False)
            
            # Формируем текст с информацией о выбранных параметрах
            plan_name = plan.get('plan_name', 'Неизвестный тариф')
            host_name = data.get('host_name', 'Неизвестный хост')
            price_text = f"{amount_stars} ⭐️"
            
            text = (
                "Вы выбрали:\n\n"
                f"✅ Хост: {host_name}\n"
                f"✅ Тариф: {plan_name}\n"
                f"✅ Стоимость: {price_text}\n"
                f"✅ Способ оплаты: ⭐️ Telegram Stars\n\n"
                "➡️ Для оплаты нажмите на кнопку:"
            )
            
            await callback.message.edit_text(text, reply_markup=keyboard)
        except Exception as e:
            logger.error(f"Failed to create Stars purchase invoice: {e}", exc_info=True)
            try:
                await callback.message.answer("❌ Не удалось создать счет через Stars. Попробуйте позже или выберите другой способ оплаты.")
            except Exception:
                pass
            await state.clear()

    @user_router.callback_query(PaymentProcess.waiting_for_payment_method, F.data == "confirm_stars_payment")
    async def confirm_stars_payment(callback: types.CallbackQuery, state: FSMContext):
        """Обработчик подтверждения оплаты звездами для покупки тарифа"""
        logger.info(f"User {callback.from_user.id}: Confirming Stars payment.")
        await callback.answer("Создаю счет через Stars...")
        data = await state.get_data()
        
        user_id = callback.from_user.id
        amount_stars = data.get('stars_amount_stars', 0)
        price_rub = data.get('stars_price_rub', 0)
        conversion_rate = data.get('stars_conversion_rate', 1.79)
        plan = data.get('stars_plan', {})
        metadata = data.get('stars_metadata', {})
        
        if amount_stars <= 0 or price_rub <= 0:
            await callback.message.edit_text("❌ Некорректные данные для оплаты.")
            await state.clear()
            return

        try:
            invoice_price = types.LabeledPrice(label=f"{plan.get('plan_name', 'Тариф')}", amount=amount_stars)

            payment_id = str(uuid.uuid4())
            payment_metadata = {
                **metadata,
                "price": float(price_rub),
                "payment_method": "Stars",
                "stars_rate": float(conversion_rate),
                "chat_id": callback.message.chat.id,
                "message_id": callback.message.message_id,
                "operation": "buy",
                "payment_id": payment_id
            }

            # Сохраняем pending транзакцию для последующей валидации pre_checkout/success
            create_pending_stars_transaction(
                payment_id=payment_id,
                user_id=user_id,
                amount_rub=float(price_rub),
                amount_stars=amount_stars,
                metadata=payment_metadata
            )

            await callback.message.answer_invoice(
                title=f"Покупка тарифа: {plan.get('plan_name', 'Тариф')}",
                description=f"Оплата тарифа через Telegram Stars",
                payload=payment_id,
                provider_token="STARS",
                currency="XTR",
                prices=[invoice_price]
            )
            await state.clear()
        except Exception as e:
            logger.error(f"Failed to create Stars purchase invoice: {e}", exc_info=True)
            try:
                await callback.message.answer("❌ Не удалось создать счет через Stars. Попробуйте позже или выберите другой способ оплаты.")
            except Exception:
                pass
            await state.clear()

    @user_router.callback_query(PaymentProcess.waiting_for_payment_method, F.data == "stars_payment_failed")
    @measure_performance("stars_payment_failed")
    async def stars_payment_failed(callback: types.CallbackQuery, state: FSMContext):
        """Обработчик кнопки 'Не удалось заплатить' для покупки тарифа"""
        from src.shop_bot.bot.keyboards import create_stars_payment_failed_keyboard
        
        text = (
            "💳 **Возможно вы не смогли заплатить из-за отсутствия валютной карты.**\n\n"
            "Иногда ваш счет в Telegram может или мог быть привязанным к ранее существовавшим VISA/Master картам.\n\n"
            "Можно купить звезды по карте РФ через официального \"Premium Bot\""
        )
        
        keyboard = create_stars_payment_failed_keyboard(is_topup=False)
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="Markdown")

    @user_router.callback_query(PaymentProcess.waiting_for_payment_method, F.data == "back_to_payment_methods")
    @registration_required
    @measure_performance("back_to_payment_methods")
    async def back_to_payment_methods(callback: types.CallbackQuery, state: FSMContext):
        """Возврат к выбору методов оплаты для покупки тарифа"""
        await callback.answer()
        data = await state.get_data()
        
        # Получаем данные для создания клавиатуры методов оплаты
        plan_id = data.get('plan_id')
        action = data.get('action', 'buy')
        key_id = int(data.get('key_id', 0))
        host_name = data.get('host_name', '')
        customer_email = data.get('customer_email', '')
        
        plan = get_plan_by_id(plan_id)
        if not plan:
            await callback.message.edit_text("❌ Ошибка: Тариф не найден.")
            await state.clear()
            return
        
        # Получаем пользователя и баланс
        user = get_user_by_id(callback.from_user.id)
        user_balance = user.get('balance', 0.0) if user else 0.0
        
        # Получаем доступные методы платежа
        payment_methods = get_available_payment_methods()
        
        # Создаем клавиатуру методов оплаты
        from src.shop_bot.bot.keyboards import create_payment_method_keyboard
        keyboard = create_payment_method_keyboard(
            payment_methods=payment_methods,
            action=action,
            key_id=key_id,
            user_balance=user_balance
        )
        
        text = (
            f"💳 **Выберите способ оплаты**\n\n"
            f"📦 Тариф: {plan.get('plan_name', 'Тариф')}\n"
            f"💰 Стоимость: {plan.get('price', 0)} RUB\n\n"
            f"Выберите удобный способ оплаты:"
        )
        
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="Markdown")

    @user_router.callback_query(PaymentProcess.waiting_for_payment_method, F.data == "pay_balance")
    @measure_performance("pay_with_balance")
    async def pay_with_internal_balance(callback: types.CallbackQuery, state: FSMContext):
        await callback.answer("Проверяю баланс и оформляю покупку...")
        try:
            data = await state.get_data()
            user_id = callback.from_user.id
            action = data.get('action')
            key_id = data.get('key_id')
            host_name = data.get('host_name')
            plan_id = data.get('plan_id')
            plan = get_plan_by_id(plan_id)
            months = int(data.get('months') or 0) or int((plan or {}).get('months') or 0)
            days = int((plan or {}).get('days') or 0)
            hours = int((plan or {}).get('hours') or 0)
            # Цена к списанию: учитываем возможную скидку, если была рассчитана
            # Используем явную проверку на None, чтобы корректно обрабатывать случай когда final_price = 0
            final_price_from_state = data.get('final_price')
            if final_price_from_state is not None:
                price = float(final_price_from_state)
            else:
                price = float((plan or {}).get('price') or 0)

            from shop_bot.data_manager.database import get_user_balance, add_to_user_balance
            current_balance = get_user_balance(user_id)
            if current_balance < price:
                await callback.message.answer(
                    f"❌ Недостаточно средств на балансе. Доступно: {current_balance:.2f} RUB, требуется: {price:.2f} RUB.",
                    reply_markup=keyboards.create_back_to_menu_keyboard()
                )
                return

            # Формируем текст с информацией о выбранных параметрах перед списанием
            plan_name = plan.get('plan_name', 'Неизвестный тариф') if plan else 'Неизвестный тариф'
            price_text = f"{price:.2f} RUB"
            
            payment_info_text = (
                "Вы выбрали:\n\n"
                f"✅ Хост: {host_name}\n"
                f"✅ Тариф: {plan_name}\n"
                f"✅ Стоимость: {price_text}\n"
                f"✅ Способ оплаты: С баланса\n\n"
            )
            
            # Списываем средства
            add_to_user_balance(user_id, -price)

            # Формируем metadata и запускаем общий процесс выдачи
            metadata = {
                "user_id": user_id,
                "months": months,
                "days": days,
                "hours": hours,
                "price": price,
                "action": action,
                "key_id": key_id,
                "host_name": host_name,
                "plan_id": plan_id,
                "customer_email": data.get('customer_email'),
                "payment_method": "Из баланса",
                "payment_id": str(uuid.uuid4()),
                "promo_code": data.get('promo_code'),
                "promo_usage_id": data.get('promo_usage_id')  # Добавляем promo_usage_id для обновления статуса
            }

            # Логируем транзакцию в БД
            try:
                user_info = get_user(user_id)
                log_username = user_info.get('username', 'N/A') if user_info else 'N/A'
                log_transaction(
                    username=log_username,
                    transaction_id=None,
                    payment_id=metadata['payment_id'],
                    user_id=user_id,
                    status='paid',
                    amount_rub=price,
                    amount_currency=None,
                    currency_name=None,
                    payment_method='Balance',
                    metadata=json.dumps(metadata)
                )
            except Exception as _:
                pass

            # Сообщаем пользователю о списании с баланса
            try:
                final_message = payment_info_text + f"✅ С баланса списано {price:.2f} RUB"
                await callback.message.answer(final_message)
            except Exception:
                pass

            await process_successful_payment(callback.bot, metadata)
            await state.clear()
        except Exception as e:
            logger.error(f"Balance payment failed: {e}", exc_info=True)
            await callback.message.answer("❌ Не удалось выполнить оплату с баланса. Попробуйте другой способ оплаты.")
            await state.clear()
        # После успешной оплаты с баланса не предлагаем альтернативные методы
        return

    @user_router.message(F.text)
    @measure_performance("promo_code_text")
    async def promo_code_text_handler(message: types.Message, state: FSMContext):
        """Обработчик текстовых сообщений для промокодов"""
        from shop_bot.data_manager.database import validate_promo_code
        
        user_id = message.from_user.id
        text = message.text.strip()
        
        print(f"DEBUG: TEXT HANDLER CALLED for user {user_id}, text: '{text}'")
        logger.info(f"TEXT HANDLER: User {user_id} sent text: '{text}'")
        
        # ИСКЛЮЧАЕМ КОМАНДУ /start - она должна обрабатываться специализированным обработчиком
        if text == '/start':
            print(f"DEBUG: TEXT HANDLER: Ignoring /start command for user {user_id}")
            return
        
        # Проверяем, зарегистрирован ли пользователь
        user_data = get_user(user_id)
        if not user_data:
            await message.answer("Пожалуйста, для начала работы со мной, отправьте команду /start")
            return
        
        # Расширенный список кнопок главного меню и интерфейса
        interface_buttons = [
            "🏠 Главное меню", "🛒 Купить", "🛒 Купить VPN", "🛒 Купить новый VPN",
            "👤 Мой профиль", "🔑 Мои ключи", "💰Пополнить баланс", "💳 Пополнить баланс",
            "🤝 Реферальная программа", "🌐 Инструкции❓",
            "🆘 Поддержка", "ℹ️ О проекте", "⚙️ Админ-панель", "🆓 Пробный период",
            "⁉️ Помощь и поддержка", "➕ Купить новый ключ", "🔄 Продлить ключ"
        ]

        # Проверяем, является ли сообщение промокодом
        # Промокод должен быть:
        # 1. Не командой (не начинается с /)
        # 2. Не кнопкой интерфейса
        # 3. Иметь длину от 3 до 20 символов
        # 4. Содержать только буквы, цифры и специальные символы промокодов
        # 5. НЕ содержать пробелы
        # 6. НЕ быть обычными словами (исключения для известных промокодов)
        is_command = text.startswith('/')
        is_interface_button = text in interface_buttons

        # Исключаем обычные русские слова, которые точно не промокоды
        common_russian_words = {
            'долбаёб', 'привет', 'пока', 'спасибо', 'пожалуйста', 'хорошо', 'плохо',
            'да', 'нет', 'может', 'быть', 'это', 'тот', 'эта', 'то', 'как', 'что',
            'где', 'когда', 'почему', 'зачем', 'кто', 'чей', 'какой', 'какая'
        }

        is_common_word = text.lower() in common_russian_words

        # Проверяем формат промокода: только буквы, цифры и специальные символы, без пробелов
        has_spaces = ' ' in text
        is_promo_format = (
            len(text) >= 3 and len(text) <= 20 and
            not has_spaces and  # Промокоды не содержат пробелов
            not is_common_word and  # Исключаем обычные слова
            text.replace('_', '').replace('-', '').replace('%', '').replace('₽', '').replace('Р', '').isalnum() and
            any(c.isalnum() for c in text)
        )

        # Обрабатываем как промокод только если это соответствует формату промокода
        if not is_command and not is_interface_button and is_promo_format:

            # Валидируем промокод
            result = validate_promo_code(text, "shop")

            if result['valid']:
                # Промокод найден - ЗАПИСЫВАЕМ ИСПОЛЬЗОВАНИЕ СРАЗУ
                try:
                    from shop_bot.data_manager.database import get_promo_code_by_code, record_promo_code_usage
                    promo_data = get_promo_code_by_code(text, "shop")
                    if promo_data:
                        # Записываем использование промокода
                        success = record_promo_code_usage(
                            promo_id=promo_data['promo_id'],
                            user_id=user_id,
                            bot="shop",
                            plan_id=promo_data.get('vpn_plan_id'),
                            discount_amount=promo_data.get('discount_amount', 0.0),
                            discount_percent=promo_data.get('discount_percent', 0.0),
                            discount_bonus=promo_data.get('discount_bonus', 0.0)
                        )
                        if success:
                            logger.info(f"Successfully recorded promo code usage via text handler: {text} for user {user_id}")
                        else:
                            logger.error(f"Failed to record promo code usage via text handler: {text} for user {user_id}")
                except Exception as e:
                    logger.error(f"Error recording promo code usage via text handler: {e}", exc_info=True)

                # Промокод найден
                response_text = f"{result['message']}\n\n{result['description']}\n\n"
                response_text += "💡 <b>Как использовать:</b>\n"
                response_text += "1. Выберите '🛒 Купить' в главном меню\n"
                response_text += "2. Выберите '🛒 Купить новый VPN'\n"
                response_text += "3. При оформлении заказа введите этот промокод\n\n"
                response_text += "Промокод будет автоматически применен к заказу!"

                await message.answer(response_text, reply_markup=keyboards.create_back_to_menu_keyboard())
            else:
                # Промокод не найден - показываем сообщение только если это действительно похоже на промокод
                await message.answer(
                    f"❌ {result['message']}\n\n"
                    "Проверьте правильность написания промокода.\n"
                    "Промокод должен быть введен точно как указано (с учетом регистра).",
                    reply_markup=keyboards.create_back_to_menu_keyboard()
                )
            return

        # Если это не промокод, проверяем команды
        if message.text.startswith('/'):
            await message.answer("Такой команды не существует. Попробуйте /start.")
        else:
            # Для обычных сообщений не показываем ошибку промокода
            # Просто игнорируем или показываем общее сообщение
            pass

    @user_router.pre_checkout_query()
    @measure_performance("pre_checkout")
    async def pre_checkout_handler(pre_checkout_query: types.PreCheckoutQuery):
        """Обработчик pre-checkout для Telegram Stars"""
        logger.info(f"Pre-checkout query received: {pre_checkout_query.id}")
        
        try:
            # Проверяем, что это Stars платеж
            if pre_checkout_query.currency != "XTR":
                await pre_checkout_query.answer(ok=False, error_message="Неподдерживаемая валюта")
                return
            
            # Проверяем payload
            if not pre_checkout_query.invoice_payload:
                await pre_checkout_query.answer(ok=False, error_message="Отсутствуют данные платежа")
                return
            
            # Получаем метаданные из БД по payment_id (payload)
            try:
                from shop_bot.data_manager.database import get_transaction_by_payment_id
                payment_id = pre_checkout_query.invoice_payload
                tx = get_transaction_by_payment_id(payment_id)
                if not tx:
                    await pre_checkout_query.answer(ok=False, error_message="Транзакция не найдена")
                    return
                metadata = tx.get('metadata') or {}
                user_id = int(metadata.get('user_id') or 0)
                # Ожидаемая сумма звезд: ceil(RUB / (RUB/Star))
                price_rub = Decimal(str(metadata.get('price', 0)))
                conversion_rate = Decimal(str(get_setting("stars_conversion_rate") or "1.79"))
                if conversion_rate <= 0:
                    conversion_rate = Decimal("1.0")
                expected_stars = int((price_rub / conversion_rate).quantize(Decimal("1"), rounding=ROUND_CEILING))
                
                # Проверяем, что пользователь существует
                user_data = get_user(user_id)
                if not user_data:
                    await pre_checkout_query.answer(ok=False, error_message="Пользователь не найден")
                    return
                
                if pre_checkout_query.total_amount != expected_stars:
                    await pre_checkout_query.answer(ok=False, error_message="Неверная сумма платежа")
                    return
                
                # Подтверждаем платеж
                await pre_checkout_query.answer(ok=True)
                logger.info(f"Pre-checkout approved for user {user_id}, amount: {expected_stars} stars")
                
            except (json.JSONDecodeError, ValueError, TypeError) as e:
                logger.error(f"Error parsing pre-checkout payload: {e}")
                await pre_checkout_query.answer(ok=False, error_message="Ошибка в данных платежа")
                
        except Exception as e:
            logger.error(f"Error in pre-checkout handler: {e}", exc_info=True)
            await pre_checkout_query.answer(ok=False, error_message="Внутренняя ошибка сервера")

    @user_router.message(F.content_type == types.ContentType.SUCCESSFUL_PAYMENT)
    @measure_performance("successful_payment")
    async def successful_payment_handler(message: types.Message):
        """Обработчик успешного платежа через Telegram Stars"""
        logger.info(f"Successful payment received from user {message.from_user.id}")
        
        try:
            payment = message.successful_payment
            
            # Проверяем, что это Stars платеж
            if payment.currency != "XTR":
                logger.warning(f"Received non-Stars payment: {payment.currency}")
                return
            
            # Получаем метаданные из БД по payment_id (payload)
            try:
                from shop_bot.data_manager.database import get_transaction_by_payment_id, update_transaction_on_payment
                payment_id = payment.invoice_payload
                tx = get_transaction_by_payment_id(payment_id)
                if not tx:
                    logger.error(f"Stars: transaction not found by payment_id: {payment_id}")
                    return
                metadata = tx.get('metadata') or {}
                user_id = int(metadata.get('user_id') or 0)
                operation = metadata.get('operation')
                months = int(metadata.get('months') or 0)
                price = float(metadata.get('price', 0))
                action = metadata.get('action')
                key_id = int(metadata.get('key_id') or 0)
                host_name = metadata.get('host_name')
                plan_id = int(metadata.get('plan_id') or 0)
                customer_email = metadata.get('customer_email')
                # Гарантируем наличие plan_name для таблицы
                if not metadata.get('plan_name'):
                    try:
                        plan_obj = get_plan_by_id(plan_id)
                        metadata['plan_name'] = plan_obj.get('plan_name', 'N/A') if plan_obj else 'N/A'
                    except Exception:
                        metadata['plan_name'] = 'N/A'
                
                logger.info(f"Processing Stars payment: user_id={user_id}, amount={payment.total_amount} stars, price={price} RUB, op={operation}")
                
                # Фиксируем оплату в транзакции и обрабатываем (пересчитываем RUB по текущему курсу)
                try:
                    # Берём курс из metadata на момент покупки, fallback на текущее значение
                    conversion_rate = Decimal(str(metadata.get('stars_rate') or get_setting("stars_conversion_rate") or "1.79"))
                    amount_rub_paid = float(Decimal(payment.total_amount) * conversion_rate)
                    # Сохраняем telegram_charge_id как transaction_hash для отображения в таблице
                    stars_tx_id = payment.telegram_payment_charge_id
                    # Дописываем, что было оплачено столько-то звёзд
                    metadata['stars_paid'] = int(payment.total_amount)
                    # Для Stars connection_string появится после создания/продления ключа в process_successful_payment,
                    # поэтому здесь просто обновляем сумму/ид и сохраним metadata без connection_string (будет добавлен позже)
                    update_transaction_on_payment(payment_id, 'paid', amount_rub_paid, tx_hash=stars_tx_id, metadata=metadata)
                except Exception as _:
                    pass
                if operation == 'topup':
                    # Пополнение баланса
                    from shop_bot.data_manager.database import add_to_user_balance
                    add_to_user_balance(user_id, price)
                    await message.answer(
                        f"✅ Баланс пополнен на {price:.2f} RUB",
                        reply_markup=keyboards.create_back_to_menu_keyboard()
                    )
                else:
                    await process_successful_payment(message.bot, metadata)
                
                # Сообщение об успехе отправляем только после фактической выдачи ключа в process_successful_payment
                
            except (json.JSONDecodeError, ValueError, TypeError) as e:
                logger.error(f"Error parsing successful payment payload: {e}")
                await message.answer("❌ Ошибка при обработке платежа. Обратитесь в поддержку.")
                
        except Exception as e:
            logger.error(f"Error in successful payment handler: {e}", exc_info=True)
            await message.answer("❌ Произошла ошибка при обработке платежа. Обратитесь в поддержку.")

    # Обработчики для сброса триала
    @user_router.callback_query(F.data == "admin_reset_trial")
    @registration_required
    @measure_performance("admin_reset_trial")
    async def admin_reset_trial_handler(callback: types.CallbackQuery, state: FSMContext):
        """Обработчик для начала процесса сброса триала"""
        await callback.answer()
        
        # Проверяем права администратора
        user_id = callback.from_user.id
        is_admin = str(user_id) == ADMIN_ID
        
        if not is_admin:
            await callback.message.answer("❌ У вас нет прав для выполнения этой операции.")
            return
        
        text = (
            "🔄 <b>Сброс триала пользователя</b>\n\n"
            "Эта функция полностью сбрасывает всю информацию о триале пользователя, "
            "будто он никогда не использовал пробный период.\n\n"
            "Введите Telegram ID пользователя:"
        )
        
        await callback.message.edit_text(text, parse_mode='HTML')
        await state.set_state(TrialResetStates.waiting_for_user_id)

    @user_router.message(TrialResetStates.waiting_for_user_id)
    @registration_required
    async def process_trial_reset_user_id(message: types.Message, state: FSMContext):
        """Обработчик для получения Telegram ID пользователя"""
        try:
            user_id_to_reset = int(message.text.strip())
        except ValueError:
            await message.answer("❌ Неверный формат ID. Пожалуйста, введите числовой Telegram ID.")
            return
        
        # Проверяем существование пользователя
        from shop_bot.data_manager.database import get_user
        user = get_user(user_id_to_reset)
        
        if not user:
            await message.answer(f"❌ Пользователь с ID {user_id_to_reset} не найден.")
            return
        
        username = user.get('username', 'N/A')
        trial_info = user.get('trial_used', 0)
        trial_days = user.get('trial_days_given', 0)
        trial_reuses = user.get('trial_reuses_count', 0)
        
        text = (
            f"🔄 <b>Подтверждение сброса триала</b>\n\n"
            f"<b>Пользователь:</b> {user_id_to_reset} (@{username})\n"
            f"<b>Текущий статус триала:</b>\n"
            f"• Использован: {'Да' if trial_info else 'Нет'}\n"
            f"• Дней выдано: {trial_days}\n"
            f"• Повторных использований: {trial_reuses}\n\n"
            f"⚠️ <b>Внимание!</b> Это действие необратимо.\n"
            f"После сброса пользователь сможет заново получить пробный период.\n\n"
            f"Подтвердите операцию:"
        )
        
        # Сохраняем ID пользователя в состоянии
        await state.update_data(user_id_to_reset=user_id_to_reset)
        
        keyboard = keyboards.create_trial_reset_keyboard()
        await message.answer(text, parse_mode='HTML', reply_markup=keyboard)

    @user_router.callback_query(F.data == "confirm_trial_reset")
    @registration_required
    @measure_performance("confirm_trial_reset")
    async def confirm_trial_reset_handler(callback: types.CallbackQuery, state: FSMContext):
        """Обработчик подтверждения сброса триала"""
        await callback.answer()
        
        # Проверяем права администратора
        user_id = callback.from_user.id
        is_admin = str(user_id) == ADMIN_ID
        
        if not is_admin:
            await callback.message.answer("❌ У вас нет прав для выполнения этой операции.")
            await state.clear()
            return
        
        # Получаем данные из состояния
        state_data = await state.get_data()
        user_id_to_reset = state_data.get('user_id_to_reset')
        
        if not user_id_to_reset:
            await callback.message.answer("❌ Ошибка: не найден ID пользователя для сброса.")
            await state.clear()
            return
        
        try:
            # Выполняем сброс триала
            from shop_bot.data_manager.database import admin_reset_trial_completely, get_user
            user = get_user(user_id_to_reset)
            username = user.get('username', 'N/A') if user else 'N/A'
            
            success = admin_reset_trial_completely(user_id_to_reset)
            
            if success:
                text = (
                    f"✅ <b>Триал успешно сброшен!</b>\n\n"
                    f"Пользователь {user_id_to_reset} (@{username}) теперь может заново получить пробный период."
                )
            else:
                text = f"❌ Ошибка при сбросе триала для пользователя {user_id_to_reset}."
                
        except Exception as e:
            text = f"❌ Произошла ошибка при сбросе триала: {str(e)}"
        
        await callback.message.edit_text(text, parse_mode='HTML')
        await state.clear()

    @user_router.callback_query(F.data == "cancel_trial_reset")
    @registration_required
    @measure_performance("cancel_trial_reset")
    async def cancel_trial_reset_handler(callback: types.CallbackQuery, state: FSMContext):
        """Обработчик отмены сброса триала"""
        await callback.answer()
        await state.clear()
        
        text = "❌ Сброс триала отменен."
        keyboard = keyboards.create_admin_panel_keyboard()
        await callback.message.edit_text(text, reply_markup=keyboard)

    @user_router.error()
    @measure_performance("user_router_error")
    async def user_router_error_handler(event: ErrorEvent, bot: Bot):
        """Глобальный обработчик ошибок для user_router"""
        # Пропускаем сетевые ошибки - они обрабатываются автоматически aiogram
        if isinstance(event.exception, TelegramNetworkError):
            logger.warning(
                f"Network error in user router (will retry automatically): {event.exception}"
            )
            return
        
        # Проверяем, не является ли это устаревшим callback query
        # Такие ошибки обрабатываются в самих handlers и не должны логироваться как CRITICAL
        if isinstance(event.exception, TelegramBadRequest):
            error_msg = str(event.exception).lower()
            if "query is too old" in error_msg or "response timeout expired" in error_msg or "query id is invalid" in error_msg:
                # Устаревшие callback queries обрабатываются в handlers, логируем как debug
                user_id = 'unknown'
                if event.update.callback_query and hasattr(event.update.callback_query, 'from_user'):
                    user_id = getattr(event.update.callback_query.from_user, 'id', 'unknown')
                logger.debug(
                    f"Expired callback query in user router for user {user_id}: {event.exception}"
                )
                # Не логируем как CRITICAL и не отправляем уведомления - handler уже обработал это
                return
        
        logger.critical(
            "Critical error in user router caused by %s", 
            event.exception, 
            exc_info=True
        )
        
        # Пытаемся определить тип update и отправить сообщение пользователю
        update = event.update
        user_id = None
        
        try:
            if update.message:
                user_id = update.message.from_user.id
                await update.message.answer(
                    "⚠️ Произошла ошибка при обработке вашего запроса.\n"
                    "Попробуйте позже или обратитесь в поддержку."
                )
            elif update.callback_query:
                user_id = update.callback_query.from_user.id
                try:
                    # Пытаемся ответить на callback query
                    await update.callback_query.answer(
                        "⚠️ Произошла ошибка. Попробуйте позже или обратитесь в поддержку.",
                        show_alert=True
                    )
                except TelegramBadRequest as e:
                    error_msg = str(e).lower()
                    # Если callback query устарел, отправляем обычное сообщение
                    if "query is too old" in error_msg or "response timeout expired" in error_msg or "query id is invalid" in error_msg:
                        logger.debug(
                            f"Callback query expired for user {user_id}, sending regular message instead"
                        )
                        try:
                            await bot.send_message(
                                chat_id=user_id,
                                text="⚠️ Произошла ошибка при обработке вашего запроса.\n"
                                     "Попробуйте позже или обратитесь в поддержку."
                            )
                        except Exception as send_error:
                            # Проверяем, не является ли это тоже устаревшим запросом
                            send_error_msg = str(send_error).lower()
                            if "query is too old" in send_error_msg or "response timeout expired" in send_error_msg or "query id is invalid" in send_error_msg:
                                logger.debug(
                                    f"Callback query expired for user {user_id} (second attempt). Skipping notification."
                                )
                            else:
                                logger.warning(
                                    f"Failed to send error notification message to user {user_id}: {send_error}"
                                )
                    else:
                        # Другие ошибки TelegramBadRequest просто логируем
                        logger.error(
                            f"Failed to answer callback query for user {user_id}: {e}"
                        )
        except Exception as notification_error:
            # Проверяем, не является ли это устаревшим callback query
            error_msg = str(notification_error).lower()
            if "query is too old" in error_msg or "response timeout expired" in error_msg or "query id is invalid" in error_msg:
                logger.debug(
                    f"Callback query expired for user {user_id} during error notification. Skipping."
                )
            else:
                logger.warning(f"Failed to send error notification to user {user_id}: {notification_error}")

    # Экспортируем функции для тестирования
    # Получаем функции из локальной области видимости и присваиваем глобальным переменным
    local_funcs = locals()
    globals_dict = globals()
    for func_name in ['create_yookassa_payment_handler', 'create_cryptobot_invoice_handler', 
                      'create_ton_invoice_handler', 'create_stars_invoice_handler', 
                      'create_heleket_invoice_handler', 'pay_with_internal_balance', 
                      'pre_checkout_handler', 'trial_period_callback_handler']:
        if func_name in local_funcs:
            globals_dict[func_name] = local_funcs[func_name]

    return user_router

_user_connectors: Dict[int, TonConnect] = {}
_listener_tasks: Dict[int, asyncio.Task] = {}

# Глобально подавим избыточные INFO/WARNING из pytonconnect, чтобы скрыть SSE ошибки в логах
try:
    import logging as _logging
    _logging.getLogger("pytonconnect").setLevel(_logging.ERROR)
except Exception:
    pass

async def _get_ton_connect_instance(user_id: int) -> TonConnect:
    if user_id not in _user_connectors:
        from shop_bot.data_manager.database import get_global_domain
        domain = get_global_domain()
        if not domain:
            raise ValueError(
                "Глобальный домен не настроен. Настройте global_domain в настройках панели для использования TON Connect."
            )
        manifest_url = f'{domain}/.well-known/tonconnect-manifest.json'
        _user_connectors[user_id] = TonConnect(manifest_url=manifest_url)
    return _user_connectors[user_id]

async def _listener_task(connector: TonConnect, user_id: int, transaction_payload: dict, payment_metadata: dict | None = None, bot_instance = None):
    try:
        wallet_connected = False
        for _ in range(120):
            if connector.connected:
                wallet_connected = True
                break
            await asyncio.sleep(1)

        if not wallet_connected:
            logger.warning(f"TON Connect: Timeout waiting for wallet connection from user {user_id}.")
            return

        logger.info(f"TON Connect: Wallet connected for user {user_id}. Address: {connector.account.address}")
        
        logger.info(f"TON Connect: Sending transaction request to user {user_id} with payload: {transaction_payload}")
        # Отлавливаем сетевые/SSE ошибки pytonconnect и выполняем безопасный ретрай один раз
        result = None
        for attempt_index in range(2):
            try:
                result = await connector.send_transaction(transaction_payload)
                break
            except Exception as sse_err:
                # Известная проблема: разрыв SSE (TransferEncodingError/ClientPayloadError)
                from aiohttp.client_exceptions import ClientPayloadError
                try:
                    from aiohttp.http_exceptions import TransferEncodingError as _TransferEncodingError
                except Exception:
                    _TransferEncodingError = tuple()

                is_transport_err = isinstance(sse_err, ClientPayloadError) or isinstance(sse_err, _TransferEncodingError) or (
                    "TransferEncodingError" in str(sse_err) or "Response payload is not completed" in str(sse_err)
                )

                if is_transport_err and attempt_index == 0:
                    logger.warning(
                        f"TON Connect: transient bridge/SSE error on attempt {attempt_index+1} for user {user_id}: {sse_err}. Retrying once..."
                    )
                    await asyncio.sleep(1.0)
                    continue
                # Вторая неудача или не-транспортная ошибка — логируем и уведомляем пользователя (если можем)
                logger.error(
                    f"TON Connect: send_transaction failed for user {user_id} on attempt {attempt_index+1}: {sse_err}",
                    exc_info=True
                )
                if bot_instance is not None:
                    try:
                        await bot_instance.send_message(
                            chat_id=user_id,
                            text=(
                                "❌ Не удалось отправить запрос в кошелёк через TON Connect.\n"
                                "Похоже, соединение с мостом временно прервалось.\n\n"
                                "Попробуйте: 1) открыть кошелёк ещё раз; 2) перезапустить приложение кошелька; 3) повторить оплату."
                            )
                        )
                    except Exception:
                        pass
                return
        
        logger.info(f"TON Connect: Transaction request sent successfully for user {user_id}.")
        
        # Обрабатываем успешное завершение транзакции
        if result and result.get('boc'):
            logger.info(f"TON Connect: Transaction completed successfully for user {user_id}")
            logger.info(f"TON Connect: Transaction result: {result}")
            
            # Обрабатываем платеж напрямую, так как TON Connect не отправляет webhook
            logger.info(f"TON Connect: Processing payment directly for user {user_id}")
            logger.info(f"TON Connect: payment_metadata available: {payment_metadata is not None}")
            logger.info(f"TON Connect: bot_instance available: {bot_instance is not None}")
            
            if payment_metadata and bot_instance:
                try:
                    # Извлекаем hash транзакции из result если доступен
                    tx_hash = result.get('boc')  # BOC содержит данные транзакции
                    
                    # Вызываем обработку успешного платежа (для Stars будем выводить идентификатор как transaction_hash)
                    await process_successful_payment(bot_instance, payment_metadata, tx_hash)
                    logger.info(f"TON Connect: Payment processed successfully for user {user_id}")
                except Exception as payment_error:
                    logger.error(f"TON Connect: Failed to process payment for user {user_id}: {payment_error}", exc_info=True)
            else:
                logger.error(f"TON Connect: Missing payment_metadata ({payment_metadata is not None}) or bot_instance ({bot_instance is not None}) for user {user_id}")
                if payment_metadata:
                    logger.info(f"TON Connect: metadata content: {payment_metadata}")
                else:
                    logger.error(f"TON Connect: payment_metadata is None!")

    except UserRejectsError:
        logger.warning(f"TON Connect: User {user_id} rejected the transaction.")
    except Exception as e:
        logger.error(f"TON Connect: An error occurred in the listener task for user {user_id}: {e}", exc_info=True)
    finally:
        # Корректное отключение коннектора, чтобы закрыть SSE и сокеты и не ловить TransferEncodingError
        try:
            if connector and getattr(connector, 'connected', False):
                # Даём кошельку время корректно завершить сессию, чтобы не показывалась «Техническая ошибка»
                try:
                    await asyncio.sleep(1.5)
                except Exception:
                    pass
                await connector.disconnect()
        except Exception:
            pass
        if user_id in _user_connectors:
            del _user_connectors[user_id]
        if user_id in _listener_tasks:
            del _listener_tasks[user_id]

async def _start_ton_connect_process(user_id: int, transaction_payload: dict, metadata: dict, bot_instance = None) -> str:
    if user_id in _listener_tasks and not _listener_tasks[user_id].done():
        _listener_tasks[user_id].cancel()

    try:
        connector = await _get_ton_connect_instance(user_id)
    except ValueError as e:
        # Глобальный домен не настроен - логируем и пробрасываем ошибку выше
        logger.error(f"TON Connect недоступен для user {user_id}: {e}")
        raise
    
    task = asyncio.create_task(
        _listener_task(connector, user_id, transaction_payload, metadata, bot_instance)
    )
    _listener_tasks[user_id] = task

    wallets = connector.get_wallets()
    return await connector.connect(wallets[0])

async def process_successful_onboarding(message_or_callback, state: FSMContext):
    """Завершает процесс онбординга"""
    # Сохраняем deeplink данные перед очисткой state
    state_data = await state.get_data()
    deeplink_groups = state_data.get('deeplink_applied_groups', [])
    deeplink_promos = state_data.get('deeplink_applied_promos', [])
    deeplink_already_applied_promos = state_data.get('deeplink_already_applied_promos', [])
    promo_data = state_data.get('promo_data', {})
    promo_code = state_data.get('promo_code')
    promo_usage_id = state_data.get('promo_usage_id')
    
    if hasattr(message_or_callback, 'answer'):
        await message_or_callback.answer("✅ Спасибо! Доступ предоставлен.")
    else:
        await message_or_callback.answer("✅ Спасибо! Доступ предоставлен.")
    
    user_id = message_or_callback.from_user.id
    
    # НЕ устанавливаем согласия автоматически - они должны быть установлены пользователем
    # Только устанавливаем статус подписки как подписан
    set_subscription_status(user_id, 'subscribed')
    
    await state.clear()
    
    # Восстанавливаем данные промокода если он был применен через deeplink
    if promo_code:
        await state.update_data(
            promo_code=promo_code,
            promo_usage_id=promo_usage_id,
            promo_data=promo_data
        )
    
    # Получаем сообщение для отправки
    if hasattr(message_or_callback, 'message'):
        message_to_send = message_or_callback.message
    else:
        message_to_send = message_or_callback
    
    # Показываем уведомление о deeplink параметрах (если были применены)
    if deeplink_groups or deeplink_promos or deeplink_already_applied_promos:
        message_parts = []
        if deeplink_groups:
            message_parts.append(f"✅ Вы добавлены в группу(ы): {', '.join(deeplink_groups)}")
        if deeplink_promos:
            bonus_amount = promo_data.get('discount_bonus', 0.0)
            if bonus_amount > 0:
                message_parts.append(f"✅ Применен промокод: {', '.join(deeplink_promos)}")
                message_parts.append(f"💰 На ваш баланс зачислено {bonus_amount} руб.")
            else:
                message_parts.append(f"✅ Применен промокод: {', '.join(deeplink_promos)}")
        if deeplink_already_applied_promos:
            message_parts.append(f"❌ Вы ранее использовали промокод: {', '.join(deeplink_already_applied_promos)}")
        
        if message_parts:
            await message_to_send.answer('\n'.join(message_parts))
            logger.info(f"Deeplink notification sent to user {user_id} via onboarding: groups={deeplink_groups}, promos={deeplink_promos}, already_applied={deeplink_already_applied_promos}")
    
    # Удаляем сообщение онбординга (если это callback)
    if hasattr(message_or_callback, 'message'):
        await message_or_callback.message.delete()
    
    # Показываем главное меню
    is_admin = str(user_id) == ADMIN_ID
    await message_to_send.answer("Приятного использования!", reply_markup=keyboards.get_main_reply_keyboard(is_admin))
    await show_main_menu(message_to_send)

async def is_url_reachable(url: str) -> bool:
    pattern = re.compile(
        r'^(https?://)'
        r'(([a-zA-Z0-9-]+\.)+[a-zA-Z]{2,})'
        r'(/.*)?$'
    )
    if not re.match(pattern, url):
        return False

    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=5)) as session:
            async with session.head(url, allow_redirects=True) as response:
                return response.status < 400
    except Exception as e:
        logger.warning(f"URL validation failed for {url}. Error: {e}")
        return False

async def notify_admin_of_purchase(bot: Bot, metadata: dict):
    """Отправляет уведомление создателю/админу о новой покупке. Логирует payment_id, user_id, notification_target для диагностики."""
    notification_target = ADMIN_ID
    if not notification_target:
        admin_str = get_setting("admin_telegram_id")
        if admin_str:
            try:
                notification_target = int(admin_str)
            except (ValueError, TypeError):
                pass
    if not notification_target:
        logger.warning(
            "Admin notification skipped: ADMIN_ID and admin_telegram_id are not set. "
            "Set admin_telegram_id in panel Settings to receive purchase notifications."
        )
        return

    payment_id = metadata.get("payment_id") or metadata.get("transaction_id")
    user_id = metadata.get("user_id")
    logger.info(
        "Sending creator purchase notification: payment_id=%s user_id=%s notification_target=%s",
        payment_id, user_id, notification_target,
    )

    try:
        months = metadata.get('months')
        price = float(metadata.get('price') or 0)
        host_name = metadata.get('host_name')
        plan_id = metadata.get('plan_id')
        payment_method = metadata.get('payment_method', 'Unknown')
        
        user_info = get_user(user_id) if user_id else None
        plan_info = get_plan_by_id(plan_id) if plan_id else None

        username = user_info.get('username', 'N/A') if user_info else 'N/A'
        plan_name = plan_info.get('plan_name', f'{months} мес.') if plan_info else f'{months} мес.'

        message_text = (
            "🎉 Новая покупка! 🎉\n\n"
            f"👤 Пользователь: <b>@{username}</b> (ID: <code>{user_id}</code>)\n"
            f"🌍 Сервер: <b>{host_name}</b>\n"
            f"📄 Тариф: <b>{plan_name}</b>\n"
            f"💰 Сумма: <b>{price:.2f} RUB</b>\n"
            f"💳 Способ оплаты: <b>{payment_method}</b>"
        )

        await bot.send_message(
            chat_id=notification_target,
            text=message_text,
            parse_mode='HTML'
        )
        logger.info(
            "Creator purchase notification sent: payment_id=%s user_id=%s notification_target=%s",
            payment_id, user_id, notification_target,
        )

    except Exception as e:
        logger.error(
            "Failed to send admin notification for purchase: payment_id=%s user_id=%s notification_target=%s error=%s",
            payment_id, user_id, notification_target, e,
            exc_info=True,
        )

async def _create_heleket_payment_request(user_id: int, price: float, months: int, days: int, hours: int, host_name: str, state_data: dict) -> str | None:
    merchant_id = get_setting("heleket_merchant_id")
    api_key = get_setting("heleket_api_key")
    bot_username = get_setting("telegram_bot_username")
    from shop_bot.data_manager.database import get_global_domain
    domain = get_global_domain()

    if not all([merchant_id, api_key, bot_username, domain]):
        logger.error("Heleket Error: Not all required settings are configured.")
        return None

    redirect_url = f"https://t.me/{bot_username}"
    order_id = str(uuid.uuid4())
    
    metadata = {
        "user_id": user_id, "months": months, "days": days, "hours": hours, "price": float(price),
        "action": state_data.get('action'), "key_id": state_data.get('key_id'),
        "host_name": host_name, "plan_id": state_data.get('plan_id'),
        "customer_email": state_data.get('customer_email'), "payment_method": "Heleket",
        "promo_usage_id": state_data.get('promo_usage_id')  # Добавляем promo_usage_id для обновления статуса
    }

    payload = {
        "amount": f"{price:.2f}",
        "currency": "RUB",
        "order_id": order_id,
        "description": json.dumps(metadata),
        "url_return": redirect_url,
        "url_success": redirect_url,
        "url_callback": f"https://{domain}/heleket-webhook",
        "lifetime": 1800,
        "is_payment_multiple": False
    }
    
    headers = {
        "merchant": merchant_id,
        "sign": _generate_heleket_signature(json.dumps(payload), api_key or ""),
        "Content-Type": "application/json",
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            url = "https://api.heleket.com/v1/payment"
            async with session.post(url, json=payload, headers=headers) as response:
                result = await response.json()
                if response.status == 200 and result.get("result", {}).get("url"):
                    return result["result"]["url"]
                else:
                    logger.error(f"Heleket API Error: Status {response.status}, Result: {result}")
                    return None
    except Exception as e:
        logger.error(f"Heleket request failed: {e}", exc_info=True)
        return None

def _generate_heleket_signature(data, api_key: str) -> str:
    if isinstance(data, dict):
        data_str = json.dumps(data, separators=(",", ":"), ensure_ascii=False)
    else:
        data_str = str(data)
    base64_encoded = base64.b64encode(data_str.encode()).decode()
    raw_string = f"{base64_encoded}{api_key}"
    return hashlib.md5(raw_string.encode()).hexdigest()

async def get_usdt_rub_rate() -> Decimal | None:
    url = "https://api.binance.com/api/v3/ticker/price"
    params = {"symbol": "USDTRUB"}
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as response:
                response.raise_for_status()
                data = await response.json()
                price_str = data.get('price')
                if price_str:
                    logger.info(f"Got USDT RUB: {price_str}")
                    return Decimal(price_str)
                logger.error("Can't find 'price' in Binance response.")
                return None
    except Exception as e:
        logger.error(f"Error getting USDT RUB Binance rate: {e}", exc_info=True)
        return None
    
async def get_telegram_stars_rate() -> Decimal | None:
    """Получает курс Telegram Stars (примерный)"""
    try:
        # К сожалению, у Telegram нет публичного API для получения курса Stars
        # Возвращаем примерный курс на основе данных из скриншота
        # 100 звезд = 179 рублей, значит 1 звезда = 1.79 рублей
        return Decimal("1.79")
    except Exception as e:
        logger.error(f"Error getting Telegram Stars rate: {e}")
        return None

async def get_ton_usdt_rate() -> Decimal | None:
    url = "https://api.binance.com/api/v3/ticker/price"
    params = {"symbol": "TONUSDT"}
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as response:
                response.raise_for_status()
                data = await response.json()
                price_str = data.get('price')
                if price_str:
                    logger.info(f"Got TON USDT: {price_str}")
                    return Decimal(price_str)
                logger.error("Can't find 'price' in Binance response.")
                return None
    except Exception as e:
        logger.error(f"Error getting TON USDT Binance rate: {e}", exc_info=True)
        return None

def get_ton_transaction_url(tx_hash: str) -> str:
    """
    Создает ссылку на транзакцию в TON Explorer (tonviewer.com)
    
    Args:
        tx_hash: hex-хеш транзакции (64 символа) или BOC (base64)
    
    Returns:
        URL для просмотра транзакции на tonviewer.com
    """
    if not tx_hash:
        return ""
    
    # Проверяем формат: hex-хеш обычно 64 символа (32 байта в hex)
    # BOC обычно длиннее и содержит base64 символы
    if len(tx_hash) == 64 and all(c in '0123456789abcdefABCDEF' for c in tx_hash):
        # Это hex-хеш, используем напрямую
        return f"https://tonviewer.com/transaction/{tx_hash}"
    else:
        # Вероятно это BOC или другой формат
        # Для tonviewer.com нужен hex-хеш, но если это BOC, нужно конвертировать
        # Пока возвращаем как есть - если в БД хранится hex-хеш, это сработает
        # Если хранится BOC, нужно будет добавить конвертацию через TON API
        logger.warning(f"get_ton_transaction_url: получен нестандартный формат хеша, длина: {len(tx_hash)}, первые 20 символов: {tx_hash[:20]}")
        return f"https://tonviewer.com/transaction/{tx_hash}"

async def process_successful_yookassa_payment(bot: Bot, metadata: dict):
    """Обрабатывает успешный платеж YooKassa с дополнительными данными"""
    try:
        # Импортируем здесь, чтобы функция была видима при любом пути выполнения
        from shop_bot.data_manager.database import update_yookassa_transaction
        
        def _to_int(val, default=0):
            try:
                if val is None:
                    return default
                s = str(val).strip()
                if s == '' or s.lower() == 'none':
                    return default
                return int(s)
            except Exception:
                return default

        def _to_float(val, default=0.0):
            try:
                if val is None:
                    return default
                s = str(val).strip()
                if s == '' or s.lower() == 'none':
                    return default
                return float(s)
            except Exception:
                return default

        user_id = _to_int(metadata.get('user_id'))
        operation = metadata.get('operation')
        months = _to_int(metadata.get('months'))
        days = _to_int(metadata.get('days', 0))
        hours = _to_int(metadata.get('hours', 0))
        price = _to_float(metadata.get('price'))
        action = metadata.get('action')
        key_id = _to_int(metadata.get('key_id'))
        host_name = metadata.get('host_name')
        host_code = metadata.get('host_code')  # Получаем из metadata
        plan_id = _to_int(metadata.get('plan_id'))
        customer_email = metadata.get('customer_email')
        payment_method_raw = metadata.get('payment_method')
        payment_method = (str(payment_method_raw).strip() if payment_method_raw is not None else "")
        payment_method_normalized = payment_method.lower()
        
        # Дополнительные данные YooKassa
        yookassa_payment_id = metadata.get('yookassa_payment_id')
        rrn = metadata.get('rrn')
        authorization_code = metadata.get('authorization_code')
        payment_type = metadata.get('payment_type')

        chat_id_to_delete = metadata.get('chat_id')
        message_id_to_delete = metadata.get('message_id')
        
    except (ValueError, TypeError) as e:
        logger.error(f"FATAL: Could not parse YooKassa metadata. Error: {e}. Metadata: {metadata}")
        return

    # Импортируем функции для работы с планами и хостами
    from shop_bot.data_manager.database import get_plan_by_id, get_host

    # Если host_code нет в metadata, получаем из хоста по host_name из плана
    if not host_code and plan_id:
        try:
            from shop_bot.data_manager.database import get_plan_by_id, get_host
            plan = get_plan_by_id(plan_id)
            if plan and plan.get('host_name'):
                host_from_plan = get_host(plan['host_name'])
                if host_from_plan:
                    host_code = host_from_plan.get('host_code')
                    host_name = plan['host_name']  # Используем правильное имя из плана
                    logger.info(f"Using host_code '{host_code}' and host_name '{host_name}' from plan {plan_id}")
        except Exception as e:
            logger.warning(f"Failed to get host_code from plan {plan_id}: {e}")

    # Пополнение баланса: отдельная ветка
    if operation == 'topup':
        try:
            from shop_bot.data_manager.database import add_to_user_balance
            payment_id = metadata.get('payment_id')
            if payment_id:
                update_yookassa_transaction(
                    payment_id, 'paid', price,
                    yookassa_payment_id, rrn, authorization_code, payment_type,
                    metadata
                )
            add_to_user_balance(user_id, price)
            await bot.send_message(user_id, f"✅ Баланс пополнен на {price:.2f} RUB", reply_markup=keyboards.create_back_to_menu_keyboard())
        except Exception as e:
            logger.error(f"Failed to process YooKassa topup for user {user_id}: {e}", exc_info=True)
        return

    if chat_id_to_delete and message_id_to_delete:
        try:
            await bot.delete_message(chat_id=chat_id_to_delete, message_id=message_id_to_delete)
        except TelegramBadRequest as e:
            logger.warning(f"Could not delete payment message: {e}")

    processing_message = await bot.send_message(
        chat_id=user_id,
        text=f"✅ Оплата получена! Обрабатываю ваш запрос на сервере \"{host_name}\"..."
    )
    try:
        email = ""
        comment = f"{user_id}"
        # Сохраняем host_code для поиска хоста (если еще не получен из metadata/плана)
        host_code_for_search = host_code
        if action == "new":
            key_number = get_next_key_number(user_id)
            try:
                from shop_bot.data_manager.database import get_host
                host_rec = get_host(host_name) if host_name else None
                # Для email используем нормализованный код
                host_code_for_email = (host_rec.get('host_code') or host_name).replace(' ', '').lower() if host_rec and host_name else (host_name or "").replace(' ', '').lower()
                # Если host_code_for_search еще не установлен, используем из хоста
                if not host_code_for_search and host_rec:
                    host_code_for_search = host_rec.get('host_code')
            except Exception:
                host_code_for_email = (host_name or "").replace(' ', '').lower()
            email = f"user{user_id}-key{key_number}@{host_code_for_email}.bot"
        elif action == "extend":
            key_data = get_key_by_id(key_id)
            if not key_data or key_data['user_id'] != user_id:
                await processing_message.edit_text("❌ Ошибка: ключ для продления не найден.")
                return
            email = key_data['key_email']
            # Если host_code_for_search еще не установлен, получаем из ключа
            if not host_code_for_search:
                try:
                    from shop_bot.data_manager.database import get_host
                    key_host_name = key_data.get('host_name')
                    if key_host_name:
                        host_rec = get_host(key_host_name)
                        if host_rec:
                            host_code_for_search = host_rec.get('host_code')
                except Exception as e:
                    logger.warning(f"Failed to get host_code from key {key_id}: {e}")
        
        # Учитываем дополнительные дни и трафик
        from shop_bot.data_manager.database import get_plan_by_id
        plan = get_plan_by_id(plan_id)
        
        # Используем days/hours из metadata (если есть), иначе из плана (fallback для старых платежей)
        extra_days = days if days > 0 else (int(plan.get('days') or 0) if plan else 0)
        extra_hours = hours if hours > 0 else (int(plan.get('hours') or 0) if plan else 0)
        
        if extra_hours < 0:
            extra_hours = 0
        if extra_hours > 24:
            extra_hours = 24
        traffic_gb = float(plan.get('traffic_gb') or 0) if plan else 0.0
        days_to_add = months * 30 + extra_days + (extra_hours / 24)
        
        logger.info(
            f"[PAYMENT_PROCESSING] Calculating days_to_add: months={months}, days={extra_days}, "
            f"hours={extra_hours}, total_days={days_to_add:.2f}"
        )
        if not host_name:
            await processing_message.edit_text("❌ Ошибка: не указан сервер.")
            return
            
        # Создаем или продлеваем ключ
        if action == "new":
            # Получаем данные пользователя для формирования subscription
            user_data = get_user(user_id)
            username = user_data.get('username', '') if user_data else ''
            fullname = user_data.get('fullname', '') if user_data else ''
            subscription = f"{user_id}-{username}".lower().replace('@', '')
            telegram_chat_id = user_id
            
            # Создаем новый ключ через XUI API с передачей sub_id
            result = await xui_api.create_or_update_key_on_host(
                host_name=host_name,
                email=email,
                days_to_add=days_to_add,
                comment=comment,
                traffic_gb=traffic_gb,
                sub_id=subscription,
                telegram_chat_id=telegram_chat_id,
                host_code=host_code_for_search
            )
            if result:
                
                # Атомарно создаем ключ и обновляем все связанные данные в одной транзакции БД
                payment_id = metadata.get('payment_id')
                promo_usage_id = metadata.get('promo_usage_id')
                
                from shop_bot.data_manager.database import create_key_with_stats_atomic
                key_id = create_key_with_stats_atomic(
                    user_id=user_id,
                    host_name=host_name,
                    xui_client_uuid=result['client_uuid'],
                    key_email=result['email'],
                    expiry_timestamp_ms=result['expiry_timestamp_ms'],
                    amount_spent=price,
                    months_purchased=months,
                    payment_id=payment_id,
                    promo_usage_id=promo_usage_id,
                    plan_id=plan_id,
                    connection_string=result.get('connection_string') or "",
                    plan_name=plan.get('plan_name') if plan else None,
                    price=price,
                    subscription=subscription,
                    subscription_link=result.get('subscription_link'),
                    telegram_chat_id=telegram_chat_id,
                    comment=f"Ключ для пользователя {fullname or username or user_id}"
                )
                
                # Если атомарная функция вернула None (ключ уже существует), пытаемся найти существующий
                if not key_id:
                    try:
                        key_data_fallback = get_key_by_email(result['email'])
                        if key_data_fallback:
                            key_id = key_data_fallback.get('key_id')
                            # Если ключ уже существует, обновляем статистику отдельно
                            update_user_stats(user_id, price, months)
                            if payment_id:
                                from shop_bot.data_manager.database import update_yookassa_transaction
                                update_yookassa_transaction(
                                    payment_id, 'paid', price,
                                    yookassa_payment_id, rrn, authorization_code, payment_type,
                                    metadata
                                )
                            if promo_usage_id:
                                from shop_bot.data_manager.database import update_promo_usage_status
                                update_promo_usage_status(promo_usage_id, plan_id)
                    except Exception:
                        key_id = None
                
                if key_id:
                    # Обновляем транзакцию YooKassa с дополнительными данными (если не обновлено атомарно)
                    if payment_id:
                        from shop_bot.data_manager.database import update_yookassa_transaction
                        # Обновляем только дополнительные поля YooKassa (статус уже обновлен атомарно)
                        update_yookassa_transaction(
                            payment_id, 'paid', price,
                            yookassa_payment_id, rrn, authorization_code, payment_type,
                            metadata
                        )

                    feature_enabled, user_timezone = _get_user_timezone_context(user_id)
                    connection_string = result.get('connection_string')
                    new_expiry_date = datetime.fromtimestamp(result['expiry_timestamp_ms'] / 1000)
                    subscription_link = result.get('subscription_link')
                    provision_mode = plan.get('key_provision_mode', 'key') if plan else 'key'
                    
                    # Сохраняем connection_string в metadata транзакции
                    if connection_string and payment_id:
                        try:
                            # Обновляем metadata с connection_string
                            updated_metadata = dict(metadata)
                            updated_metadata['connection_string'] = connection_string
                            
                            update_yookassa_transaction(
                                payment_id, 'paid', price,
                                yookassa_payment_id, rrn, authorization_code, payment_type,
                                updated_metadata
                            )
                            logger.info(f"[PAYMENT_PROCESSING] Saved connection_string to transaction metadata for payment_id={payment_id}")
                        except Exception as metadata_update_error:
                            logger.warning(f"[PAYMENT_PROCESSING] Failed to save connection_string to metadata: {metadata_update_error}")

                    # Получаем данные для информации о тарифе
                    plan_name = plan.get('plan_name') if plan else None
                    plan_price = price if price else None
                    is_trial_key = False  # Платный ключ не является триалом

                    final_text = get_purchase_success_text(
                        action="создан",
                        key_number=key_number,
                        expiry_date=new_expiry_date,
                        connection_string=connection_string,
                        subscription_link=subscription_link,
                        provision_mode=provision_mode,
                        user_timezone=user_timezone,
                        feature_enabled=feature_enabled,
                        user_id=user_id,
                        key_id=key_id,
                        host_name=host_name,
                        plan_name=plan_name,
                        price=plan_price,
                        status=None,  # Для нового ключа статус еще не определен
                        is_trial=is_trial_key,
                    )

                    try:
                        await processing_message.delete()
                    except TelegramBadRequest as e:
                        logger.warning(f"Could not delete processing message for user {user_id}: {e}")
                    await bot.send_message(
                        chat_id=user_id,
                        text=final_text,
                        reply_markup=keyboards.create_key_info_keyboard(key_id, subscription_link) if key_id else keyboards.create_back_to_menu_keyboard(),
                        parse_mode="HTML"
                    )
            else:
                await processing_message.edit_text("❌ Ошибка: не удалось создать ключ.")
        elif action == "extend":
            # Получаем существующий subscription из key_data для обновления подписки
            existing_subscription = key_data.get('subscription')
            if not existing_subscription:
                logger.warning(f"Subscription not found for key_id={key_id}, email={email} during renewal. Subscription may not update correctly.")
            
            # Продлеваем существующий ключ через XUI API
            result = await xui_api.create_or_update_key_on_host(
                host_name=host_name,
                email=email,
                days_to_add=days_to_add,
                comment=f"{user_id}",
                traffic_gb=traffic_gb if traffic_gb > 0 else None,
                sub_id=existing_subscription,  # передаем существующий subscription для обновления подписки
                telegram_chat_id=user_id,
                host_code=host_code_for_search
            )
            if result:
                # Обновляем ключ в базе данных
                update_key_info(key_id, result['client_uuid'], result['expiry_timestamp_ms'], result.get('subscription_link'))
                
                # Обновляем статистику пользователя
                update_user_stats(user_id, price, months)
                
                # Получаем номер ключа для пользователя
                all_user_keys = get_user_keys(user_id)
                key_number = next((i + 1 for i, key in enumerate(all_user_keys) if key['key_id'] == key_id), len(all_user_keys))
                
                # Получаем provision_mode из тарифа
                provision_mode = 'key'  # по умолчанию
                subscription_link = result.get('subscription_link')
                if plan:
                    provision_mode = plan.get('key_provision_mode', 'key')
                
                feature_enabled, user_timezone = _get_user_timezone_context(user_id)
                connection_string = result.get('connection_string')
                new_expiry_date = datetime.fromtimestamp(result['expiry_timestamp_ms'] / 1000)
                
                # Сохраняем connection_string в metadata транзакции
                payment_id = metadata.get('payment_id')
                if connection_string and payment_id:
                    try:
                        # Обновляем metadata с connection_string
                        updated_metadata = dict(metadata)
                        updated_metadata['connection_string'] = connection_string
                        
                        update_yookassa_transaction(
                            payment_id, 'paid', price,
                            yookassa_payment_id, rrn, authorization_code, payment_type,
                            updated_metadata
                        )
                        logger.info(f"[PAYMENT_PROCESSING] Saved connection_string to transaction metadata for renewal payment_id={payment_id}")
                    except Exception as metadata_update_error:
                        logger.warning(f"[PAYMENT_PROCESSING] Failed to save connection_string to metadata for renewal: {metadata_update_error}")
                elif payment_id:
                    # Обновляем транзакцию без connection_string (если ключ не был создан/обновлен)
                    update_yookassa_transaction(
                        payment_id, 'paid', price,
                        yookassa_payment_id, rrn, authorization_code, payment_type,
                        metadata
                    )
                
                # Обновляем статус промокода на 'used' если он был применен
                promo_usage_id = metadata.get('promo_usage_id')
                if promo_usage_id:
                    from shop_bot.data_manager.database import update_promo_usage_status
                    update_promo_usage_status(promo_usage_id, plan_id)
                
                # Получаем данные для информации о тарифе
                plan_name = plan.get('plan_name') if plan else None
                plan_price = price if price else None
                is_trial_key = False  # Платный ключ не является триалом
                
                # Получаем данные ключа для статуса
                key_data = get_key_by_id(key_id) if key_id else None
                key_status = None
                if key_data:
                    # Получаем статус из деталей ключа
                    try:
                        details = await xui_api.get_key_details_from_host(key_data)
                        key_status = details.get('status') if details else None
                    except Exception:
                        pass

                final_text = get_purchase_success_text(
                    action="продлен",
                    key_number=key_number,
                    expiry_date=new_expiry_date,
                    connection_string=connection_string,
                    subscription_link=subscription_link,
                    provision_mode=provision_mode,
                    user_timezone=user_timezone,
                    feature_enabled=feature_enabled,
                    user_id=user_id,
                    key_id=key_id,
                    host_name=host_name,
                    plan_name=plan_name,
                    price=plan_price,
                    status=key_status,
                    is_trial=is_trial_key,
                )
                
                try:
                    await processing_message.delete()
                except TelegramBadRequest as e:
                    logger.warning(f"Could not delete processing message after renewal for user {user_id}: {e}")
                
                await bot.send_message(
                    chat_id=user_id,
                    text=final_text,
                    reply_markup=keyboards.create_key_info_keyboard(key_id, subscription_link) if key_id else keyboards.create_back_to_menu_keyboard(),
                    parse_mode="HTML"
                )
            else:
                await processing_message.edit_text("❌ Ошибка: не удалось продлить ключ.")
    except Exception as e:
        logger.error(f"Failed to process YooKassa payment for user {user_id}: {e}", exc_info=True)
        await processing_message.edit_text("❌ Произошла ошибка при обработке платежа. Обратитесь в поддержку.")


async def process_successful_payment(bot: Bot, metadata: dict, tx_hash: str | None = None):
    try:
        # Импортируем здесь, чтобы функция была видима при любом пути выполнения
        from shop_bot.data_manager.database import update_transaction_on_payment
        def _to_int(val, default=0):
            try:
                if val is None:
                    return default
                s = str(val).strip()
                if s == '' or s.lower() == 'none':
                    return default
                return int(s)
            except Exception:
                return default

        def _to_float(val, default=0.0):
            try:
                if val is None:
                    return default
                s = str(val).strip()
                if s == '' or s.lower() == 'none':
                    return default
                return float(s)
            except Exception:
                return default

        user_id = _to_int(metadata.get('user_id'))
        operation = metadata.get('operation')
        months = _to_int(metadata.get('months'))
        days = _to_int(metadata.get('days', 0))
        hours = _to_int(metadata.get('hours', 0))
        price = _to_float(metadata.get('price'))
        action = metadata.get('action')
        key_id = _to_int(metadata.get('key_id'))
        host_name = metadata.get('host_name')
        host_code = metadata.get('host_code')  # Получаем из metadata
        plan_id = _to_int(metadata.get('plan_id'))
        customer_email = metadata.get('customer_email')
        payment_method_raw = metadata.get('payment_method')
        payment_method = (str(payment_method_raw).strip() if payment_method_raw is not None else "")
        payment_method_normalized = payment_method.lower()

        chat_id_to_delete = metadata.get('chat_id')
        message_id_to_delete = metadata.get('message_id')
        
    except (ValueError, TypeError) as e:
        logger.error(f"FATAL: Could not parse metadata. Error: {e}. Metadata: {metadata}")
        return

    # Если host_code нет в metadata, получаем из хоста по host_name из плана
    if not host_code and plan_id:
        try:
            from shop_bot.data_manager.database import get_plan_by_id, get_host
            plan = get_plan_by_id(plan_id)
            if plan and plan.get('host_name'):
                host_from_plan = get_host(plan['host_name'])
                if host_from_plan:
                    host_code = host_from_plan.get('host_code')
                    host_name = plan['host_name']  # Используем правильное имя из плана
                    logger.info(f"Using host_code '{host_code}' and host_name '{host_name}' from plan {plan_id}")
        except Exception as e:
            logger.warning(f"Failed to get host_code from plan {plan_id}: {e}")

    # Пополнение баланса: отдельная ветка
    if operation == 'topup':
        try:
            from shop_bot.data_manager.database import add_to_user_balance
            payment_id = metadata.get('payment_id')
            if payment_id:
                update_transaction_on_payment(payment_id, 'paid', price, tx_hash=tx_hash or "", metadata=metadata)
            add_to_user_balance(user_id, price)
            await bot.send_message(user_id, f"✅ Баланс пополнен на {price:.2f} RUB", reply_markup=keyboards.create_back_to_menu_keyboard())
        except Exception as e:
            logger.error(f"Failed to process topup for user {user_id}: {e}", exc_info=True)
        return
    
    # Списание средств с баланса при оплате с баланса (если еще не списано)
    if payment_method_normalized in ('balance', 'из баланса') and operation != 'topup':
        try:
            from shop_bot.data_manager.database import get_user_balance, add_to_user_balance
            current_balance = get_user_balance(user_id)
            # Проверяем, что средства еще не списаны (если баланс >= цены, значит еще не списали)
            # Если баланс меньше цены, значит уже списали или недостаточно средств
            if current_balance >= price:
                # Списываем средства с баланса
                add_to_user_balance(user_id, -price)
                logger.info(f"Process successful payment: Deducted {price} RUB from balance for user {user_id}. New balance: {current_balance - price}")
        except Exception as e:
            logger.error(f"Failed to deduct balance for user {user_id}: {e}", exc_info=True)

    if chat_id_to_delete and message_id_to_delete:
        try:
            await bot.delete_message(chat_id=chat_id_to_delete, message_id=message_id_to_delete)
        except TelegramBadRequest as e:
            logger.warning(f"Could not delete payment message: {e}")

    processing_message = await bot.send_message(
        chat_id=user_id,
        text=f"✅ Оплата получена! Обрабатываю ваш запрос на сервере \"{host_name}\"..."
    )
    try:
        email = ""
        comment = f"{user_id}"
        # Сохраняем host_code для поиска хоста (если еще не получен из metadata/плана)
        host_code_for_search = host_code
        if action == "new":
            key_number = get_next_key_number(user_id)
            try:
                from shop_bot.data_manager.database import get_host
                host_rec = get_host(host_name) if host_name else None
                # Для email используем нормализованный код
                host_code_for_email = (host_rec.get('host_code') or host_name).replace(' ', '').lower() if host_rec and host_name else (host_name or "").replace(' ', '').lower()
                # Если host_code_for_search еще не установлен, используем из хоста
                if not host_code_for_search and host_rec:
                    host_code_for_search = host_rec.get('host_code')
            except Exception:
                host_code_for_email = (host_name or "").replace(' ', '').lower()
            email = f"user{user_id}-key{key_number}@{host_code_for_email}.bot"
        elif action == "extend":
            key_data = get_key_by_id(key_id)
            if not key_data or key_data['user_id'] != user_id:
                await processing_message.edit_text("❌ Ошибка: ключ для продления не найден.")
                return
            email = key_data['key_email']
            # Если host_code_for_search еще не установлен, получаем из ключа
            if not host_code_for_search:
                try:
                    from shop_bot.data_manager.database import get_host
                    key_host_name = key_data.get('host_name')
                    if key_host_name:
                        host_rec = get_host(key_host_name)
                        if host_rec:
                            host_code_for_search = host_rec.get('host_code')
                except Exception as e:
                    logger.warning(f"Failed to get host_code from key {key_id}: {e}")
        
        # Учитываем дополнительные дни и трафик
        from shop_bot.data_manager.database import get_plan_by_id
        plan = get_plan_by_id(plan_id)
        
        # Используем days/hours из metadata (если есть), иначе из плана (fallback для старых платежей)
        extra_days = days if days > 0 else (int(plan.get('days') or 0) if plan else 0)
        extra_hours = hours if hours > 0 else (int(plan.get('hours') or 0) if plan else 0)
        
        if extra_hours < 0:
            extra_hours = 0
        if extra_hours > 24:
            extra_hours = 24
        traffic_gb = float(plan.get('traffic_gb') or 0) if plan else 0.0
        days_to_add = months * 30 + extra_days + (extra_hours / 24)
        
        logger.info(
            f"[PAYMENT_PROCESSING] Calculating days_to_add: months={months}, days={extra_days}, "
            f"hours={extra_hours}, total_days={days_to_add:.2f}"
        )
        if not host_name:
            await processing_message.edit_text("❌ Ошибка: не указан сервер.")
            return
        
        # Для новых ключей формируем subscription заранее
        subscription = None
        telegram_chat_id = None
        if action == "new":
            user_data = get_user(user_id)
            username = user_data.get('username', '') if user_data else ''
            fullname = user_data.get('fullname', '') if user_data else ''
            subscription = f"{user_id}-{username}".lower().replace('@', '')
            telegram_chat_id = user_id
        elif action == "extend":
            # Получаем существующий subscription из key_data для обновления подписки
            existing_subscription = key_data.get('subscription')
            if existing_subscription:
                subscription = existing_subscription
            else:
                logger.warning(f"Subscription not found for key_id={key_id}, email={email} during renewal. Subscription may not update correctly.")
            
        result = await xui_api.create_or_update_key_on_host(
            host_name=host_name,
            email=email,
            days_to_add=days_to_add,
            comment=comment,
            traffic_gb=traffic_gb if traffic_gb > 0 else None,
            sub_id=subscription,
            telegram_chat_id=telegram_chat_id,
            host_code=host_code_for_search
        )

        if not result:
            await processing_message.edit_text(
                "❌ Не удалось создать/обновить ключ в панели.\n\n"
                "Возможные причины:\n"
                "• Временная недоступность сервера\n"
                "• Проблемы с сетью\n\n"
                "Попробуйте позже или обратитесь в поддержку."
            )
            return

        price = float(metadata.get('price') or 0)
        payment_id = metadata.get('payment_id')
        promo_usage_id = metadata.get('promo_usage_id')
        
        if action == "new":
            logger.info(
                f"[PAYMENT_PROCESSING] Atomically creating key: user_id={user_id}, "
                f"email={result.get('email')}, key_number={key_number}, "
                f"host_name={host_name}"
            )
            
            # Атомарно создаем ключ и обновляем все связанные данные
            from shop_bot.data_manager.database import create_key_with_stats_atomic
            key_id = create_key_with_stats_atomic(
                user_id=user_id,
                host_name=host_name,
                xui_client_uuid=result['client_uuid'],
                key_email=result['email'],
                expiry_timestamp_ms=result['expiry_timestamp_ms'],
                amount_spent=price,
                months_purchased=months,
                payment_id=payment_id,
                promo_usage_id=promo_usage_id,
                plan_id=plan_id,
                connection_string=result.get('connection_string') or "",
                plan_name=(metadata.get('plan_name') or (plan.get('plan_name') if plan else None) or ""),
                price=price,
                subscription=subscription,
                subscription_link=result.get('subscription_link'),
                telegram_chat_id=telegram_chat_id,
                comment=f"Ключ для пользователя {fullname or username or user_id}"
            )
            
            if key_id:
                logger.info(f"[PAYMENT_PROCESSING] Successfully atomically created key: key_id={key_id}, email={result.get('email')}, user_id={user_id}")
            else:
                logger.warning(f"[PAYMENT_PROCESSING] create_key_with_stats_atomic returned None for email={result.get('email')}, user_id={user_id}")
                try:
                    key_data_fallback = get_key_by_email(result['email'])
                    if key_data_fallback:
                        key_id = key_data_fallback.get('key_id')
                        logger.info(f"[PAYMENT_PROCESSING] Found existing key via fallback: key_id={key_id}, email={result.get('email')}")
                        # Если ключ уже существует, обновляем статистику отдельно
                        update_user_stats(user_id, price, months)
                        if payment_id:
                            from shop_bot.data_manager.database import update_transaction_on_payment
                            update_transaction_on_payment(payment_id, 'paid', price, tx_hash=tx_hash or "", metadata=metadata)
                        if promo_usage_id:
                            from shop_bot.data_manager.database import update_promo_usage_status
                            update_promo_usage_status(promo_usage_id, plan_id)
                except Exception as e:
                    logger.error(f"[PAYMENT_PROCESSING] Fallback failed to find key by email: {e}")
                    key_id = None
        elif action == "extend":
            # Для продления используем транзакцию для атомарности
            try:
                from shop_bot.data_manager.database import DB_FILE
                with sqlite3.connect(DB_FILE, timeout=30) as conn:
                    cursor = conn.cursor()
                    cursor.execute("PRAGMA busy_timeout=30000")
                    cursor.execute("BEGIN IMMEDIATE")
                    
                    try:
                        # Обновляем ключ
                        from shop_bot.utils.datetime_utils import timestamp_to_utc_datetime, calculate_remaining_seconds
                        expiry_date = timestamp_to_utc_datetime(result['expiry_timestamp_ms'])
                        remaining_seconds = calculate_remaining_seconds(result['expiry_timestamp_ms'])
                        
                        # Получаем текущий ключ для проверки is_trial
                        cursor.execute("SELECT is_trial FROM vpn_keys WHERE key_id = ?", (key_id,))
                        key_row = cursor.fetchone()
                        current_is_trial = key_row[0] if key_row and key_row[0] is not None else 0
                        
                        # Если price > 0 и текущий ключ был триалом, устанавливаем is_trial = 0
                        is_trial_value = current_is_trial
                        if price > 0 and current_is_trial == 1:
                            is_trial_value = 0
                            logger.info(f"[PAYMENT_PROCESSING] Converting trial key {key_id} to paid key after payment extension")
                        
                        # Пересчитываем status на основе is_trial_value и remaining_seconds
                        if is_trial_value and remaining_seconds > 0:
                            status_value = 'trial-active'
                        elif is_trial_value and remaining_seconds <= 0:
                            status_value = 'trial-ended'
                        elif not is_trial_value and remaining_seconds > 0:
                            status_value = 'pay-active'
                        else:
                            status_value = 'pay-ended'
                        
                        if result.get('subscription_link'):
                            cursor.execute(
                                "UPDATE vpn_keys SET xui_client_uuid = ?, expiry_date = ?, remaining_seconds = ?, subscription_link = ?, is_trial = ?, status = ? WHERE key_id = ?",
                                (result['client_uuid'], expiry_date, remaining_seconds, result.get('subscription_link'), is_trial_value, status_value, key_id)
                            )
                        else:
                            cursor.execute(
                                "UPDATE vpn_keys SET xui_client_uuid = ?, expiry_date = ?, remaining_seconds = ?, is_trial = ?, status = ? WHERE key_id = ?",
                                (result['client_uuid'], expiry_date, remaining_seconds, is_trial_value, status_value, key_id)
                            )
                        
                        # Обновляем статистику пользователя
                        cursor.execute(
                            "UPDATE users SET total_spent = total_spent + ?, total_months = total_months + ? WHERE telegram_id = ?",
                            (price, months, user_id)
                        )
                        
                        # Обновляем транзакцию
                        if payment_id:
                            cursor.execute(
                                "UPDATE transactions SET status = 'paid', amount_rub = ? WHERE payment_id = ? AND status = 'pending'",
                                (price, payment_id)
                            )
                        
                        # Обновляем промокод
                        if promo_usage_id and plan_id:
                            cursor.execute(
                                """UPDATE promo_code_usage 
                                SET status = 'used', plan_id = ?, used_at = CURRENT_TIMESTAMP 
                                WHERE usage_id = ? AND status = 'applied'""",
                                (plan_id, promo_usage_id)
                            )
                        
                        cursor.execute("COMMIT")
                        logger.info(f"[PAYMENT_PROCESSING] Atomically extended key_id={key_id} for user_id={user_id}")
                    except sqlite3.Error as e:
                        cursor.execute("ROLLBACK")
                        logger.error(f"[PAYMENT_PROCESSING] Failed to atomically extend key: {e}", exc_info=True)
                        raise
            except Exception as e:
                logger.error(f"[PAYMENT_PROCESSING] Error in atomic extend: {e}", exc_info=True)
                # Fallback на старый метод
                update_key_info(key_id, result['client_uuid'], result['expiry_timestamp_ms'], result.get('subscription_link'))
                
                # Если price > 0, обновляем is_trial и status (для триальных ключей, которые были продлены с оплатой)
                if price > 0:
                    key_data = get_key_by_id(key_id)
                    if key_data and key_data.get('is_trial') == 1:
                        from shop_bot.data_manager.database import update_key_trial_status
                        update_key_trial_status(key_id, is_trial=0)
                        logger.info(f"[PAYMENT_PROCESSING] Converted trial key {key_id} to paid key in fallback method")
                
                update_user_stats(user_id, price, months)
                if payment_id:
                    from shop_bot.data_manager.database import update_transaction_on_payment
                    update_transaction_on_payment(payment_id, 'paid', price, tx_hash=tx_hash or "", metadata=metadata)
                if promo_usage_id:
                    from shop_bot.data_manager.database import update_promo_usage_status
                    update_promo_usage_status(promo_usage_id, plan_id)

        user_data = get_user(user_id)
        referrer_id = user_data.get('referred_by')

        if referrer_id:
            percentage = Decimal(get_setting("referral_percentage") or "0")
            
            reward = (Decimal(str(price)) * percentage / 100).quantize(Decimal("0.01"))
            
            if float(reward) > 0:
                add_to_referral_balance(referrer_id, float(reward))
                
                try:
                    # Получаем данные покупателя для отображения в сообщении
                    buyer_username = user_data.get('username', 'пользователь')
                    await bot.send_message(
                        referrer_id,
                        f"🎉 Ваш реферал @{buyer_username} совершил покупку на сумму {price:.2f} RUB!\n"
                        f"💰 На ваш баланс начислено вознаграждение: {reward:.2f} RUB."
                    )
                except Exception as e:
                    logger.warning(f"Could not send referral reward notification to {referrer_id}: {e}")

        update_user_stats(user_id, price, months)
        
        # Логируем информацию о платеже (промокод уже записан при применении)
        promo_code = metadata.get('promo_code')
        logger.info(f"Processing payment for user {user_id}, promo_code: {promo_code}, metadata: {metadata}")
        
        if promo_code:
            logger.info(f"Payment processed with promo code {promo_code} for user {user_id}")
        
        user_info = get_user(user_id)

        log_username = user_info.get('username', 'N/A') if user_info else 'N/A'
        log_status = 'paid'
        log_amount_rub = float(price)
        log_method = metadata.get('payment_method', 'Unknown')

        # Обновляем существующую транзакцию по исходному payment_id из metadata
        existing_payment_id = metadata.get('payment_id')
        if existing_payment_id:
            # Обогащаем metadata необходимыми полями (включая connection_string и key_id)
            enriched_metadata = dict(metadata)
            try:
                plan_id_val = metadata.get('plan_id')
                plan_obj = get_plan_by_id(int(plan_id_val)) if plan_id_val is not None else None
                plan_name_safe = plan_obj.get('plan_name', 'Unknown') if plan_obj else 'Unknown'
            except Exception:
                plan_name_safe = 'Unknown'
            enriched_metadata.update({
                "plan_name": plan_name_safe,
                "key_id": key_id,
                "connection_string": result.get('connection_string')
            })

            update_transaction_on_payment(
                payment_id=existing_payment_id,
                status=log_status,
                amount_rub=log_amount_rub,
                tx_hash=tx_hash,
                metadata=enriched_metadata
            )
            
            # Обновляем статус промокода на 'used' если он был применен
            promo_usage_id = metadata.get('promo_usage_id')
            if promo_usage_id:
                from shop_bot.data_manager.database import update_promo_usage_status
                update_promo_usage_status(promo_usage_id, plan_id)
        
        await processing_message.delete()
        
        connection_string = result['connection_string']
        new_expiry_date = datetime.fromtimestamp(result['expiry_timestamp_ms'] / 1000)
        
        # Используем номер ключа, который был использован при создании (для action == "new")
        # Для action == "extend" вычисляем номер из существующих ключей
        if action == "new" and key_number is not None:
            # Используем сохраненный номер ключа
            logger.info(f"[PAYMENT_PROCESSING] Using saved key_number={key_number} for key_id={key_id}")
        else:
            # Для extend или если key_number не был установлен, вычисляем из БД
            all_user_keys = get_user_keys(user_id)
            key_number = next((i + 1 for i, key in enumerate(all_user_keys) if key['key_id'] == key_id), len(all_user_keys))
            logger.info(f"[PAYMENT_PROCESSING] Computed key_number={key_number} for key_id={key_id} from database")

        # Получаем provision_mode из тарифа
        provision_mode = 'key'  # по умолчанию
        subscription_link = result.get('subscription_link')
        if plan:
            provision_mode = plan.get('key_provision_mode', 'key')
        
        feature_enabled, user_timezone = _get_user_timezone_context(user_id)
        
        # Получаем данные для информации о тарифе
        plan_name = plan.get('plan_name') if plan else None
        plan_price = price if price else None
        is_trial_key = False  # Платный ключ не является триалом
        
        # Получаем данные ключа для статуса (если ключ уже существует)
        key_status = None
        if key_id:
            key_data = get_key_by_id(key_id)
            if key_data:
                try:
                    details = await xui_api.get_key_details_from_host(key_data)
                    key_status = details.get('status') if details else None
                except Exception:
                    pass

        final_text = get_purchase_success_text(
            action="создан" if action == "new" else "продлен",
            key_number=key_number,
            expiry_date=new_expiry_date,
            connection_string=connection_string,
            subscription_link=subscription_link,
            provision_mode=provision_mode,
            user_timezone=user_timezone,
            feature_enabled=feature_enabled,
            user_id=user_id,
            key_id=key_id,
            host_name=host_name,
            plan_name=plan_name,
            price=plan_price,
            status=key_status,
            is_trial=is_trial_key,
        )
        
        # Добавляем информацию о транзакции, если есть
        if tx_hash and payment_method_normalized == "ton connect":
            transaction_url = get_ton_transaction_url(tx_hash)
            final_text += f"\n\n🔗 <a href='{transaction_url}'>Проверить транзакцию в TON Explorer</a>"
        
        # Если это автопродление, не отправляем сообщение "Ваш ключ готов"
        # Уведомление о списании отправит send_balance_deduction_notice в perform_auto_renewals
        if payment_method_normalized == 'auto-renewal':
            # Обновляем квоту и уведомляем админа даже при автопродлении
            try:
                from shop_bot.modules.xui_api import get_key_details_from_host
                from shop_bot.data_manager.database import update_key_quota
                details_payload = {
                    'host_name': host_name,
                    'xui_client_uuid': result.get('client_uuid'),
                    'key_email': result.get('email')
                }
                details = await get_key_details_from_host(details_payload)
                if details:
                    if key_id:
                        update_key_quota(
                            key_id,
                            details.get('quota_total_gb'),
                            details.get('traffic_down_bytes'),
                            details.get('quota_remaining_bytes')
                        )
            except Exception:
                pass
            
            await notify_admin_of_purchase(bot, metadata)
            return
        
        await bot.send_message(
            chat_id=user_id,
            text=final_text,
            reply_markup=keyboards.create_key_info_keyboard(key_id, subscription_link) if key_id else None,
            parse_mode="HTML"
        )

        # Сразу подтянем детали из панели и сохраним квоту, чтобы колонка "Общ / Исп / Ост" обновилась мгновенно
        try:
            from shop_bot.modules.xui_api import get_key_details_from_host
            from shop_bot.data_manager.database import update_key_quota
            details_payload = {
                'host_name': host_name,
                'xui_client_uuid': result.get('client_uuid'),
                'key_email': result.get('email')
            }
            details = await get_key_details_from_host(details_payload)
            if details:
                if key_id:
                    update_key_quota(
                        key_id,
                        details.get('quota_total_gb'),
                    details.get('traffic_down_bytes'),
                    details.get('quota_remaining_bytes')
                )
        except Exception:
            pass

        await notify_admin_of_purchase(bot, metadata)
        
    except Exception as e:
        logger.error(f"Error processing payment for user {user_id} on host {host_name}: {e}", exc_info=True)
        
        # Безопасная попытка отредактировать сообщение
        try:
            await processing_message.edit_text("❌ Ошибка при выдаче ключа.")
        except Exception as edit_error:
            # Если не удалось отредактировать, отправляем новое сообщение
            logger.warning(f"Could not edit processing message: {edit_error}")
            try:
                await bot.send_message(user_id, "❌ Ошибка при выдаче ключа.")
            except Exception as send_error:
                logger.error(f"Could not send error message to user {user_id}: {send_error}")
        
        # Возвращаем статус транзакции на pending при ошибке
        try:
            from shop_bot.data_manager.database import update_transaction_status
            payment_id = metadata.get('payment_id')
            if payment_id:
                update_transaction_status(payment_id, 'pending')
                logger.info(f"Transaction {payment_id} status reverted to pending due to error")
        except Exception as revert_error:
            logger.error(f"Failed to revert transaction status: {revert_error}")

async def show_terms_agreement_screen(message: types.Message, state: FSMContext):
    """Показывает экран согласия с условиями использования"""
    from shop_bot.data_manager.database import get_global_domain
    domain = get_global_domain()
    
    terms_url = None
    if is_production_server() and domain and not _is_local_address(domain):
        terms_url = normalize_web_app_url(f"{domain.rstrip('/')}/terms")
    
    if not terms_url:
        # Если условия не настроены, переходим к проверке документов
        await show_documents_agreement_screen(message, state)
        return
    
    text = (
        "<b>📄 Согласие с условиями</b>\n\n"
        "Для использования бота необходимо ознакомиться с условиями использования.\n\n"
        "После ознакомления нажмите кнопку согласия."
    )
    
    # Создаем клавиатуру только с условиями
    builder = InlineKeyboardBuilder()
    builder.button(text="📄 Условия использования", web_app={"url": terms_url})
    builder.button(text="✅ Я согласен с условиями", callback_data="agree_to_terms_only")
    builder.adjust(1)
    
    await message.answer(text, reply_markup=builder.as_markup())
    await state.set_state(Onboarding.waiting_for_terms_agreement)

async def show_documents_agreement_screen(message: types.Message, state: FSMContext):
    """Показывает экран согласия с политикой конфиденциальности"""
    from shop_bot.data_manager.database import get_global_domain
    domain = get_global_domain()
    
    privacy_url = None
    if is_production_server() and domain and not _is_local_address(domain):
        privacy_url = normalize_web_app_url(f"{domain.rstrip('/')}/privacy")
    
    if not privacy_url:
        # Если политика не настроена, переходим к проверке подписки
        await show_subscription_screen(message, state)
        return
    
    text = (
        "<b>🔒 Согласие с политикой конфиденциальности</b>\n\n"
        "Для использования бота необходимо ознакомиться с политикой конфиденциальности.\n\n"
        "После ознакомления нажмите кнопку согласия."
    )
    
    # Создаем клавиатуру только с политикой
    builder = InlineKeyboardBuilder()
    builder.button(text="🔒 Политика конфиденциальности", web_app={"url": privacy_url})
    builder.button(text="✅ Я согласен с политикой", callback_data="agree_to_documents_only")
    builder.adjust(1)
    
    await message.answer(text, reply_markup=builder.as_markup())
    await state.set_state(Onboarding.waiting_for_documents_agreement)

async def show_subscription_screen(message: types.Message, state: FSMContext):
    """Показывает экран проверки подписки на канал"""
    channel_url = get_setting("channel_url")
    is_subscription_forced = get_setting("force_subscription") == "true"
    
    if not is_subscription_forced or not channel_url:
        # Если подписка не принудительная, завершаем онбординг
        await process_successful_onboarding(message, state)
        return
    
    text = (
        "<b>📢 Проверка подписки</b>\n\n"
        "Для доступа ко всем функциям, пожалуйста, подпишитесь на наш канал.\n\n"
        "После подписки нажмите кнопку ниже."
    )
    
    keyboard = keyboards.create_subscription_keyboard(channel_url)
    await message.answer(text, reply_markup=keyboard)
    await state.set_state(Onboarding.waiting_for_subscription)

# Функция process_successful_onboarding_v2 удалена - используется основная process_successful_onboarding

# Инициализируем роутер для экспорта функций-обработчиков для тестирования
# Это нужно только для тестов, в production роутер инициализируется через bot_controller
if __name__ != "__main__":
    try:
        _ = get_user_router()
    except Exception:
        # Игнорируем ошибки инициализации при импорте (например, если БД еще не готова)
        pass