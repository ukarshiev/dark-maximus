import logging
import uuid
import qrcode
import aiohttp
import re
import hashlib
import json
import base64
import asyncio

from urllib.parse import urlencode
from hmac import compare_digest
from functools import wraps
from yookassa import Payment
from io import BytesIO
from datetime import datetime, timedelta, timezone
from aiosend import CryptoPay, TESTNET
from decimal import Decimal, ROUND_HALF_UP, ROUND_CEILING
from typing import Dict

from pytonconnect import TonConnect
from pytonconnect.exceptions import UserRejectsError

from aiogram import Bot, Router, F, types, html
from aiogram.filters import Command, CommandObject, CommandStart, StateFilter
from aiogram.types import BufferedInputFile, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.enums import ChatMemberStatus
from aiogram.utils.keyboard import InlineKeyboardBuilder

from shop_bot.bot import keyboards
from shop_bot.modules import xui_api
from shop_bot.data_manager.database import (
    get_user, add_new_key, get_user_keys, update_user_stats,
    register_user_if_not_exists, get_next_key_number, get_key_by_id,
    update_key_info, set_trial_used, set_terms_agreed, get_setting, get_all_hosts,
    get_plans_for_host, get_plan_by_id, log_transaction, get_referral_count,
    add_to_referral_balance, create_pending_transaction, create_pending_ton_transaction, create_pending_stars_transaction, get_all_users,
    set_referral_balance, set_referral_balance_all, update_transaction_on_payment
)

from shop_bot.config import (
    get_profile_text, get_vpn_active_text, VPN_INACTIVE_TEXT, VPN_NO_DATA_TEXT,
    get_key_info_text, CHOOSE_PAYMENT_METHOD_MESSAGE, HOWTO_CHOOSE_OS_MESSAGE, get_purchase_success_text,
    VIDEO_INSTRUCTIONS_ENABLED, get_video_instruction_path, has_video_instruction, VIDEO_INSTRUCTIONS_DIR
)

from pathlib import Path

TELEGRAM_BOT_USERNAME = None
PAYMENT_METHODS = None
ADMIN_ID = None
CRYPTO_BOT_TOKEN = get_setting("cryptobot_token")

logger = logging.getLogger(__name__)
admin_router = Router()
user_router = Router()

class KeyPurchase(StatesGroup):
    waiting_for_host_selection = State()
    waiting_for_plan_selection = State()

class Onboarding(StatesGroup):
    waiting_for_subscription_and_agreement = State()

class PaymentProcess(StatesGroup):
    waiting_for_email = State()
    waiting_for_payment_method = State()

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
    waiting_for_details = State()

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
    user_id = message.chat.id
    user_db_data = get_user(user_id)
    user_keys = get_user_keys(user_id)
    
    trial_available = not (user_db_data and user_db_data.get('trial_used'))
    is_admin = str(user_id) == ADMIN_ID

    text = "🏠 <b>Главное меню</b>\n\nВыберите действие:"
    keyboard = keyboards.create_main_menu_keyboard(user_keys, trial_available, is_admin)
    
    if edit_message:
        try:
            await message.edit_text(text, reply_markup=keyboard)
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

def get_user_router() -> Router:
    user_router = Router()

    @user_router.message(CommandStart())
    async def start_handler(message: types.Message, state: FSMContext, bot: Bot, command: CommandObject):
        user_id = message.from_user.id
        username = message.from_user.username or message.from_user.full_name
        referrer_id = None

        if command.args and command.args.startswith('ref_'):
            try:
                potential_referrer_id = int(command.args.split('_')[1])
                if potential_referrer_id != user_id:
                    referrer_id = potential_referrer_id
                    logger.info(f"New user {user_id} was referred by {referrer_id}")
            except (IndexError, ValueError):
                logger.warning(f"Invalid referral code received: {command.args}")
                
        user_id = message.from_user.id
        username = message.from_user.username or message.from_user.full_name
        register_user_if_not_exists(user_id, username, referrer_id)
        user_data = get_user(user_id)

        if user_data and user_data.get('agreed_to_terms'):
            await message.answer(
                f"👋 Снова здравствуйте, {html.bold(message.from_user.full_name)}!",
                reply_markup=keyboards.get_main_reply_keyboard()
            )
            await show_main_menu(message)
            return

        terms_url = get_setting("terms_url")
        privacy_url = get_setting("privacy_url")
        channel_url = get_setting("channel_url")

        if not channel_url or not terms_url or not privacy_url:
            set_terms_agreed(user_id)
            await message.answer(
                f"👋 Снова здравствуйте, {html.bold(message.from_user.full_name)}!",
                reply_markup=keyboards.get_main_reply_keyboard()
            )
            await show_main_menu(message)
            return

        is_subscription_forced = get_setting("force_subscription") == "true"
        
        show_welcome_screen = (is_subscription_forced and channel_url) or (terms_url and privacy_url)

        if not show_welcome_screen:
            set_terms_agreed(user_id)
            await message.answer(
                f"👋 Снова здравствуйте, {html.bold(message.from_user.full_name)}!",
                reply_markup=keyboards.get_main_reply_keyboard()
            )
            await show_main_menu(message)
            return

        welcome_parts = ["<b>Добро пожаловать!</b>\n"]
        
        if is_subscription_forced and channel_url:
            welcome_parts.append("Для доступа ко всем функциям, пожалуйста, подпишитесь на наш канал.\n")
        
        if terms_url:
            welcome_parts.append("Также необходимо ознакомиться и принять наши Условия использования.")
        elif privacy_url:
            welcome_parts.append("Также необходимо ознакомиться с нашей Политикой конфиденциальности.")
        elif terms_url and privacy_url:
            welcome_parts.append("Также необходимо ознакомиться с нашими Условиями использования и Политикой конфиденциальности.")

        welcome_parts.append("\nПосле этого нажмите кнопку ниже.")
        final_text = "\n".join(welcome_parts)
        
        await message.answer(
            final_text,
            reply_markup=keyboards.create_welcome_keyboard(
                channel_url=channel_url,
                is_subscription_forced=is_subscription_forced,
                terms_url=terms_url,
                privacy_url=privacy_url
            ),
            disable_web_page_preview=True
        )
        await state.set_state(Onboarding.waiting_for_subscription_and_agreement)

    @user_router.callback_query(Onboarding.waiting_for_subscription_and_agreement, F.data == "check_subscription_and_agree")
    async def check_subscription_handler(callback: types.CallbackQuery, state: FSMContext, bot: Bot):
        user_id = callback.from_user.id
        channel_url = get_setting("channel_url")
        is_subscription_forced = get_setting("force_subscription") == "true"

        if not is_subscription_forced or not channel_url:
            await process_successful_onboarding(callback, state)
            return
            
        try:
            if '@' not in channel_url and 't.me/' not in channel_url:
                logger.error(f"Неверный формат URL канала: {channel_url}. Пропускаем проверку подписки.")
                await process_successful_onboarding(callback, state)
                return

            channel_id = '@' + channel_url.split('/')[-1] if 't.me/' in channel_url else channel_url
            member = await bot.get_chat_member(chat_id=channel_id, user_id=user_id)
            
            if member.status in [ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR]:
                await process_successful_onboarding(callback, state)
            else:
                await callback.answer("Вы еще не подписались на канал. Пожалуйста, подпишитесь и попробуйте снова.", show_alert=True)

        except Exception as e:
            logger.error(f"Ошибка при проверке подписки для user_id {user_id} на канал {channel_url}: {e}")
            await callback.answer("Не удалось проверить подписку. Убедитесь, что бот является администратором канала. Попробуйте позже.", show_alert=True)

    @user_router.message(Onboarding.waiting_for_subscription_and_agreement)
    async def onboarding_fallback_handler(message: types.Message):
        await message.answer("Пожалуйста, выполните требуемые действия и нажмите на кнопку в сообщении выше.")

    @user_router.message(F.text == "🏠 Главное меню")
    @registration_required
    async def main_menu_handler(message: types.Message):
        # Обновляем/навешиваем актуальную Reply Keyboard на чат
        try:
            await message.answer("🏠 Главное меню", reply_markup=keyboards.get_main_reply_keyboard())
        except Exception:
            pass
        await show_main_menu(message)

    @user_router.callback_query(F.data == "back_to_main_menu")
    @registration_required
    async def back_to_main_menu_handler(callback: types.CallbackQuery):
        await callback.answer()
        # Гарантируем, что у пользователя установлена актуальная Reply Keyboard
        try:
            await callback.message.answer("🏠 Главное меню", reply_markup=keyboards.get_main_reply_keyboard())
        except Exception:
            pass
        await show_main_menu(callback.message, edit_message=True)

    @user_router.message(F.text == "🛒 Купить VPN")
    @registration_required
    async def buy_vpn_message_handler(message: types.Message):
        hosts = get_all_hosts()
        if not hosts:
            await message.answer("❌ В данный момент нет доступных серверов для покупки.")
            return
        # Скрываем сервера без настроенных тарифов
        try:
            hosts_with_plans = [h for h in hosts if get_plans_for_host(h['host_name'])]
        except Exception:
            hosts_with_plans = hosts
        if not hosts_with_plans:
            await message.answer("❌ В данный момент нет доступных серверов для покупки.")
            return
        user_id = message.from_user.id
        user_keys = get_user_keys(user_id)
        await message.answer(
            "Выберите сервер, на котором хотите приобрести ключ:",
            reply_markup=keyboards.create_host_selection_keyboard(hosts_with_plans, action="new", total_keys_count=len(user_keys) if user_keys else 0)
        )

    @user_router.callback_query(F.data == "buy_vpn_root")
    @registration_required
    async def buy_vpn_root_handler(callback: types.CallbackQuery):
        await callback.answer()
        hosts = get_all_hosts()
        if not hosts:
            await callback.message.edit_text("❌ В данный момент нет доступных серверов для покупки.")
            return
        # Скрываем сервера без настроенных тарифов
        try:
            hosts_with_plans = [h for h in hosts if get_plans_for_host(h['host_name'])]
        except Exception:
            hosts_with_plans = hosts
        if not hosts_with_plans:
            await callback.message.edit_text("❌ В данный момент нет доступных серверов для покупки.")
            return
        user_id = callback.from_user.id
        user_keys = get_user_keys(user_id)
        await callback.message.edit_text(
            "Выберите сервер, на котором хотите приобрести ключ:",
            reply_markup=keyboards.create_host_selection_keyboard(hosts_with_plans, action="new", total_keys_count=len(user_keys) if user_keys else 0)
        )

    @user_router.message(F.text == "⁉️ Помощь и поддержка")
    @registration_required
    async def help_center_message_handler(message: types.Message):
        await message.answer("⁉️ Помощь и поддержка:", reply_markup=keyboards.create_help_center_keyboard())

    @user_router.callback_query(F.data == "help_center")
    @registration_required
    async def help_center_callback_handler(callback: types.CallbackQuery):
        await callback.answer()
        await callback.message.edit_text("⁉️ Помощь и поддержка:", reply_markup=keyboards.create_help_center_keyboard())

    @user_router.message(F.text == "💰Пополнить баланс")
    @registration_required
    async def topup_message_handler(message: types.Message, state: FSMContext):
        await state.clear()
        await message.answer(
            "Выберите сумму пополнения:",
            reply_markup=keyboards.create_topup_amounts_keyboard()
        )

    @user_router.callback_query(F.data == "topup_root")
    @registration_required
    async def topup_root_handler(callback: types.CallbackQuery, state: FSMContext):
        await callback.answer()
        await state.clear()
        await callback.message.edit_text(
            "Выберите сумму пополнения:",
            reply_markup=keyboards.create_topup_amounts_keyboard()
        )

    @user_router.callback_query(F.data.in_(
        {"topup_amount_179","topup_amount_300","topup_amount_500"}
    ))
    @registration_required
    async def topup_select_preset_handler(callback: types.CallbackQuery, state: FSMContext):
        await callback.answer()
        mapping = {
            "topup_amount_179": 179,
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
    async def topup_custom_amount_prompt(callback: types.CallbackQuery, state: FSMContext):
        await callback.answer()
        await callback.message.edit_text(
            "Введите сумму пополнения в рублях (целое число)"
        )
        await state.set_state(TopupProcess.waiting_for_custom_amount)

    @user_router.message(TopupProcess.waiting_for_custom_amount)
    async def topup_custom_amount_receive(message: types.Message, state: FSMContext):
        try:
            amount = int(message.text.strip())
            try:
                min_topup = int(get_setting("minimum_topup") or 50)
            except Exception:
                min_topup = 50
            if amount < min_topup:
                await message.answer(f"Минимальная сумма пополнения {min_topup} RUB. Введите другую сумму:")
                return
        except Exception:
            await message.answer("Введите корректное целое число в рублях:")
            return
        await state.update_data(topup_amount=amount)
        await message.answer(
            f"Сумма пополнения: {amount} RUB\n\nВыберите способ оплаты:",
            reply_markup=keyboards.create_topup_payment_methods_keyboard()
        )
        await state.set_state(TopupProcess.waiting_for_payment_method)

    @user_router.callback_query(TopupProcess.waiting_for_payment_method, F.data == "topup_back_to_amounts")
    @registration_required
    async def topup_back_to_amounts(callback: types.CallbackQuery, state: FSMContext):
        await callback.answer()
        await state.clear()
        await callback.message.edit_text(
            "Выберите сумму пополнения:",
            reply_markup=keyboards.create_topup_amounts_keyboard()
        )
    @user_router.message(F.text == "👤 Мой профиль")
    @registration_required
    async def profile_handler_message(message: types.Message):
        user_id = message.from_user.id
        user_db_data = get_user(user_id)
        user_keys = get_user_keys(user_id)
        if not user_db_data:
            await message.answer("Не удалось получить данные профиля.")
            return
        username = html.bold(user_db_data.get('username', 'Пользователь'))
        total_spent, total_months = user_db_data.get('total_spent', 0), user_db_data.get('total_months', 0)
        from shop_bot.data_manager.database import get_user_balance
        balance = get_user_balance(user_id)
        now = datetime.now()
        active_keys = [key for key in user_keys if datetime.fromisoformat(key['expiry_date']) > now]
        if active_keys:
            latest_key = max(active_keys, key=lambda k: datetime.fromisoformat(k['expiry_date']))
            latest_expiry_date = datetime.fromisoformat(latest_key['expiry_date'])
            time_left = latest_expiry_date - now
            vpn_status_text = get_vpn_active_text(time_left.days, time_left.seconds // 3600)
        elif user_keys: vpn_status_text = VPN_INACTIVE_TEXT
        else: vpn_status_text = VPN_NO_DATA_TEXT
        final_text = get_profile_text(username, balance, total_spent, total_months, vpn_status_text)
        await message.answer(final_text, reply_markup=keyboards.create_profile_menu_keyboard(total_keys_count=len(user_keys or [])))

    @user_router.message(F.text == "🔑 Мои ключи")
    @registration_required
    async def manage_keys_message(message: types.Message):
        user_id = message.from_user.id
        user_keys = get_user_keys(user_id)
        await message.answer(
            "Ваши ключи:" if user_keys else "У вас пока нет ключей.",
            reply_markup=keyboards.create_keys_management_keyboard(user_keys)
        )

    @user_router.message(F.text == "🤝 Реферальная программа")
    @registration_required
    async def referral_program_message(message: types.Message):
        user_id = message.from_user.id
        user_data = get_user(user_id)
        bot_username = (await message.bot.get_me()).username
        referral_link = f"https://t.me/{bot_username}?start=ref_{user_id}"
        referral_count = get_referral_count(user_id)
        balance = user_data.get('referral_balance', 0)
        text = (
            "🤝 <b>Реферальная программа</b>\n\n"
            "Приглашайте друзей и получайте вознаграждение с <b>каждой</b> их покупки!\n\n"
            f"<b>Ваша реферальная ссылка:</b>\n<code>{referral_link}</code>\n\n"
            f"<b>Приглашено пользователей:</b> {referral_count}\n"
            f"<b>Ваш баланс:</b> {balance:.2f} RUB"
        )
        builder = InlineKeyboardBuilder()
        if balance >= 100:
            builder.button(text="💸 Оставить заявку на вывод", callback_data="withdraw_request")
        builder.button(text="⬅️ Назад", callback_data="back_to_main_menu")
        await message.answer(text, reply_markup=builder.as_markup())

    @user_router.message(F.text == "❓ Инструкция как пользоваться")
    @registration_required
    async def howto_message(message: types.Message):
        await message.answer(
            "Выберите вашу платформу для инструкции по подключению VLESS:",
            reply_markup=keyboards.create_howto_vless_keyboard(),
            disable_web_page_preview=True
        )

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
        support_text = get_setting("support_text")
        if support_user == None and support_text == None:
            await message.answer(
                "Информация о поддержке не установлена. Установите её в админ-панели.",
                reply_markup=keyboards.create_back_to_menu_keyboard()
            )
        elif support_text == None:
            await message.answer(
                "Для связи с поддержкой используйте кнопку ниже.",
                reply_markup=keyboards.create_support_keyboard(support_user)
            )
        else:
            await message.answer(
                support_text + "\n\n",
                reply_markup=keyboards.create_support_keyboard(support_user)
            )

    @user_router.message(F.text == "ℹ️ О проекте")
    @registration_required
    async def about_message(message: types.Message):
        about_text = get_setting("about_text")
        terms_url = get_setting("terms_url")
        privacy_url = get_setting("privacy_url")
        channel_url = get_setting("channel_url")
        final_text = about_text if about_text else "Информация о проекте не добавлена."
        keyboard = keyboards.create_about_keyboard(channel_url, terms_url, privacy_url)
        await message.answer(final_text, reply_markup=keyboard, disable_web_page_preview=True)

    @user_router.callback_query(F.data == "show_profile")
    @registration_required
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
        from shop_bot.data_manager.database import get_user_balance
        balance = get_user_balance(user_id)
        now = datetime.now()
        active_keys = [key for key in user_keys if datetime.fromisoformat(key['expiry_date']) > now]
        if active_keys:
            latest_key = max(active_keys, key=lambda k: datetime.fromisoformat(k['expiry_date']))
            latest_expiry_date = datetime.fromisoformat(latest_key['expiry_date'])
            time_left = latest_expiry_date - now
            vpn_status_text = get_vpn_active_text(time_left.days, time_left.seconds // 3600)
        elif user_keys: vpn_status_text = VPN_INACTIVE_TEXT
        else: vpn_status_text = VPN_NO_DATA_TEXT
        final_text = get_profile_text(username, balance, total_spent, total_months, vpn_status_text)
        await callback.message.edit_text(final_text, reply_markup=keyboards.create_profile_menu_keyboard(total_keys_count=len(user_keys or [])))

    @user_router.callback_query(F.data == "start_broadcast")
    @registration_required
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
    async def broadcast_message_received_handler(message: types.Message, state: FSMContext):
        await state.update_data(message_to_send=message.model_dump_json())
        
        await message.answer(
            "Сообщение получено. Хотите добавить к нему кнопку со ссылкой?",
            reply_markup=keyboards.create_broadcast_options_keyboard()
        )
        await state.set_state(Broadcast.waiting_for_button_option)

    @user_router.callback_query(Broadcast.waiting_for_button_option, F.data == "broadcast_add_button")
    async def add_button_prompt_handler(callback: types.CallbackQuery, state: FSMContext):
        await callback.answer()
        await callback.message.edit_text(
            "Хорошо. Теперь отправьте мне текст для кнопки.",
            reply_markup=keyboards.create_broadcast_cancel_keyboard()
        )
        await state.set_state(Broadcast.waiting_for_button_text)

    @user_router.message(Broadcast.waiting_for_button_text)
    async def button_text_received_handler(message: types.Message, state: FSMContext):
        await state.update_data(button_text=message.text)
        await message.answer(
            "Текст кнопки получен. Теперь отправьте ссылку (URL), куда она будет вести.",
            reply_markup=keyboards.create_broadcast_cancel_keyboard()
        )
        await state.set_state(Broadcast.waiting_for_button_url)

    @user_router.message(Broadcast.waiting_for_button_url)
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
    async def cancel_broadcast_handler(callback: types.CallbackQuery, state: FSMContext):
        await callback.answer("Рассылка отменена.")
        await state.clear()
        await show_main_menu(callback.message, edit_message=True)

    @user_router.callback_query(F.data == "show_referral_program")
    @registration_required
    async def referral_program_handler(callback: types.CallbackQuery):
        await callback.answer()
        user_id = callback.from_user.id
        user_data = get_user(user_id)
        bot_username = (await callback.bot.get_me()).username
        
        referral_link = f"https://t.me/{bot_username}?start=ref_{user_id}"
        referral_count = get_referral_count(user_id)
        balance = user_data.get('referral_balance', 0)

        text = (
            "🤝 <b>Реферальная программа</b>\n\n"
            "Приглашайте друзей и получайте вознаграждение с <b>каждой</b> их покупки!\n\n"
            f"<b>Ваша реферальная ссылка:</b>\n<code>{referral_link}</code>\n\n"
            f"<b>Приглашено пользователей:</b> {referral_count}\n"
            f"<b>Ваш баланс:</b> {balance:.2f} RUB"
        )

        builder = InlineKeyboardBuilder()
        if balance >= 100:
            builder.button(text="💸 Оставить заявку на вывод", callback_data="withdraw_request")
        builder.button(text="⬅️ Назад", callback_data="back_to_main_menu")
        await callback.message.edit_text(
            text, reply_markup=builder.as_markup()
        )

    @user_router.callback_query(F.data == "withdraw_request")
    @registration_required
    async def withdraw_request_handler(callback: types.CallbackQuery, state: FSMContext):
        await callback.answer()
        await callback.message.edit_text(
            "Пожалуйста, отправьте ваши реквизиты для вывода (номер карты или номер телефона и банк):"
        )
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

        admin_id = int(get_setting("admin_telegram_id"))
        text = (
            f"💸 <b>Заявка на вывод реферальных средств</b>\n"
            f"👤 Пользователь: @{user.get('username', 'N/A')} (ID: <code>{user_id}</code>)\n"
            f"💰 Сумма: <b>{balance:.2f} RUB</b>\n"
            f"📄 Реквизиты: <code>{details}</code>\n\n"
            f"/approve_withdraw_{user_id} /decline_withdraw_{user_id}"
        )
        await message.answer("Ваша заявка отправлена администратору. Ожидайте ответа.")
        await message.bot.send_message(admin_id, text, parse_mode="HTML")
        await state.clear()

    @user_router.message(Command(commands=["approve_withdraw"]))
    async def approve_withdraw_handler(message: types.Message):
        admin_id = int(get_setting("admin_telegram_id"))
        if message.from_user.id != admin_id:
            return
        try:
            user_id = int(message.text.split("_")[-1])
            user = get_user(user_id)
            balance = user.get('referral_balance', 0)
            if balance < 100:
                await message.answer("Баланс пользователя менее 100 руб.")
                return
            set_referral_balance(user_id, 0)
            set_referral_balance_all(user_id, 0)
            await message.answer(f"✅ Выплата {balance:.2f} RUB пользователю {user_id} подтверждена.")
            await message.bot.send_message(
                user_id,
                f"✅ Ваша заявка на вывод {balance:.2f} RUB одобрена. Деньги будут переведены в ближайшее время."
            )
        except Exception as e:
            await message.answer(f"Ошибка: {e}")

    @user_router.message(Command(commands=["decline_withdraw"]))
    async def decline_withdraw_handler(message: types.Message):
        admin_id = int(get_setting("admin_telegram_id"))
        if message.from_user.id != admin_id:
            return
        try:
            user_id = int(message.text.split("_")[-1])
            await message.answer(f"❌ Заявка пользователя {user_id} отклонена.")
            await message.bot.send_message(
                user_id,
                "❌ Ваша заявка на вывод отклонена. Проверьте корректность реквизитов и попробуйте снова."
            )
        except Exception as e:
            await message.answer(f"Ошибка: {e}")

    @user_router.message(Command(commands=["upload_video"]))
    async def upload_video_handler(message: types.Message):
        """Админская команда для загрузки видеоинструкций"""
        admin_id = int(get_setting("admin_telegram_id"))
        if message.from_user.id != admin_id:
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
        admin_id = int(get_setting("admin_telegram_id"))
        if message.from_user.id != admin_id:
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
        admin_id = int(get_setting("admin_telegram_id"))
        if message.from_user.id != admin_id:
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
    @registration_required
    async def about_handler(callback: types.CallbackQuery):
        await callback.answer()
        
        about_text = get_setting("about_text")
        terms_url = get_setting("terms_url")
        privacy_url = get_setting("privacy_url")
        channel_url = get_setting("channel_url")

        final_text = about_text if about_text else "Информация о проекте не добавлена."

        keyboard = keyboards.create_about_keyboard(channel_url, terms_url, privacy_url)

        await callback.message.edit_text(
            final_text,
            reply_markup=keyboard,
            disable_web_page_preview=True
        )

    @user_router.callback_query(F.data == "show_help")
    @registration_required
    async def about_handler(callback: types.CallbackQuery):
        await callback.answer()
        from shop_bot.data_manager.database import get_setting
        if get_setting("support_enabled") != "true":
            await callback.message.edit_text(
                "Раздел поддержки недоступен.",
                reply_markup=keyboards.create_back_to_menu_keyboard()
            )
            return
        support_user = get_setting("support_user")
        support_text = get_setting("support_text")

        if support_user == None and support_text == None:
            await callback.message.edit_text(
                "Информация о поддержке не установлена. Установите её в админ-панели.",
                reply_markup=keyboards.create_back_to_menu_keyboard()
            )
        elif support_text == None:
            await callback.message.edit_text(
                "Для связи с поддержкой используйте кнопку ниже.",
                reply_markup=keyboards.create_support_keyboard(support_user)
            )
        else:
            await callback.message.edit_text(
                support_text + "\n\n",
                reply_markup=keyboards.create_support_keyboard(support_user)
            )

    @user_router.callback_query(F.data == "manage_keys")
    @registration_required
    async def manage_keys_handler(callback: types.CallbackQuery):
        await callback.answer()
        user_id = callback.from_user.id
        user_keys = get_user_keys(user_id)
        await callback.message.edit_text(
            "Ваши ключи:" if user_keys else "У вас пока нет ключей.",
            reply_markup=keyboards.create_keys_management_keyboard(user_keys)
        )

    @user_router.callback_query(F.data == "get_trial")
    @registration_required
    async def trial_period_handler(callback: types.CallbackQuery, state: FSMContext):
        user_id = callback.from_user.id
        user_db_data = get_user(user_id)
        if user_db_data and user_db_data.get('trial_used'):
            await callback.answer("Вы уже использовали бесплатный пробный период.", show_alert=True)
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
    async def trial_host_selection_handler(callback: types.CallbackQuery):
        await callback.answer()
        host_name = callback.data[len("select_host_trial_"):]
        await process_trial_key_creation(callback.message, host_name)

    async def process_trial_key_creation(message: types.Message, host_name: str):
        user_id = message.chat.id
        await message.edit_text(f"Отлично! Создаю для вас бесплатный ключ на {get_setting('trial_duration_days')} дня на сервере \"{host_name}\"...")

        try:
            result = await xui_api.create_or_update_key_on_host(
                host_name=host_name,
                email=f"{user_id}",
                days_to_add=int(get_setting("trial_duration_days")),
                comment=f"user{user_id}-key{get_next_key_number(user_id)}-trial@telegram.bot"
            )
            if not result:
                await message.edit_text("❌ Не удалось создать пробный ключ. Ошибка на сервере.")
                return

            set_trial_used(user_id)
            
            new_key_id = add_new_key(
                user_id=user_id,
                host_name=host_name,
                xui_client_uuid=result['client_uuid'],
                key_email=result['email'],
                expiry_timestamp_ms=result['expiry_timestamp_ms'],
                connection_string=result.get('connection_string'),
                protocol='vless',
                is_trial=1
            )
            # Дополнительно сразу сохраним remaining_seconds и expiry_date
            try:
                from datetime import datetime, timezone
                from shop_bot.data_manager.database import update_key_remaining_seconds
            except Exception:
                update_key_remaining_seconds = None
            try:
                if update_key_remaining_seconds:
                    now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
                    remaining = max(0, int((result['expiry_timestamp_ms'] - now_ms) / 1000))
                    update_key_remaining_seconds(new_key_id, remaining, datetime.fromtimestamp(result['expiry_timestamp_ms']/1000))
            except Exception:
                pass
            
            await message.delete()
            new_expiry_date = datetime.fromtimestamp(result['expiry_timestamp_ms'] / 1000)
            final_text = get_purchase_success_text("готов", get_next_key_number(user_id) -1, new_expiry_date, result['connection_string'])
            await message.answer(text=final_text, reply_markup=keyboards.create_key_info_keyboard(new_key_id))

        except Exception as e:
            logger.error(f"Error creating trial key for user {user_id} on host {host_name}: {e}", exc_info=True)
            await message.edit_text("❌ Произошла ошибка при создании пробного ключа.")

    @user_router.callback_query(F.data.startswith("show_key_"))
    @registration_required
    async def show_key_handler(callback: types.CallbackQuery):
        key_id_to_show = int(callback.data.split("_")[2])
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
            
            all_user_keys = get_user_keys(user_id)
            key_number = next((i + 1 for i, key in enumerate(all_user_keys) if key['key_id'] == key_id_to_show), 0)
            
            final_text = get_key_info_text(key_number, expiry_date, created_date, connection_string)
            
            await callback.message.edit_text(
                text=final_text,
                reply_markup=keyboards.create_key_info_keyboard(key_id_to_show)
            )
        except Exception as e:
            logger.error(f"Error showing key {key_id_to_show}: {e}")
            await callback.message.edit_text("❌ Произошла ошибка при получении данных ключа.")


    @user_router.callback_query(F.data.startswith("copy_key_"))
    @registration_required
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
    
    @user_router.callback_query(F.data.startswith("howto_vless"))
    @registration_required
    async def show_instruction_handler(callback: types.CallbackQuery):
        await callback.answer()

        await callback.message.edit_text(
            HOWTO_CHOOSE_OS_MESSAGE,
            reply_markup=keyboards.create_howto_vless_keyboard(),
            disable_web_page_preview=True
        )

    @user_router.callback_query(F.data == "howto_android")
    @registration_required
    async def howto_android_handler(callback: types.CallbackQuery):
        await callback.answer()
        await _send_instruction_with_video(callback, 'android', keyboards.create_howto_vless_keyboard)

    @user_router.callback_query(F.data == "howto_ios")
    @registration_required
    async def howto_ios_handler(callback: types.CallbackQuery):
        await callback.answer()
        await _send_instruction_with_video(callback, 'ios', keyboards.create_howto_vless_keyboard)

    @user_router.callback_query(F.data == "howto_macos")
    @registration_required
    async def howto_macos_handler(callback: types.CallbackQuery):
        await callback.answer()
        await _send_instruction_with_video(callback, 'macos', keyboards.create_howto_vless_keyboard)

    @user_router.callback_query(F.data == "howto_windows")
    @registration_required
    async def howto_windows_handler(callback: types.CallbackQuery):
        await callback.answer()
        await _send_instruction_with_video(callback, 'windows', keyboards.create_howto_vless_keyboard)

    @user_router.callback_query(F.data == "howto_linux")
    @registration_required
    async def howto_linux_handler(callback: types.CallbackQuery):
        await callback.answer()
        await _send_instruction_with_video(callback, 'linux', keyboards.create_howto_vless_keyboard)

    @user_router.callback_query(F.data == "buy_new_key")
    @registration_required
    async def buy_new_key_handler(callback: types.CallbackQuery):
        await callback.answer()
        hosts = get_all_hosts()
        if not hosts:
            await callback.message.edit_text("❌ В данный момент нет доступных серверов для покупки.")
            return
        # Скрываем сервера без настроенных тарифов
        try:
            hosts_with_plans = [h for h in hosts if get_plans_for_host(h['host_name'])]
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
    async def select_host_for_purchase_handler(callback: types.CallbackQuery):
        await callback.answer()
        host_name = callback.data[len("select_host_new_"):]
        plans = get_plans_for_host(host_name)
        if not plans:
            await callback.message.edit_text(f"❌ Для сервера \"{host_name}\" не настроены тарифы.")
            return
        await callback.message.edit_text(
            "Выберите тариф для нового ключа:", 
            reply_markup=keyboards.create_plans_keyboard(plans, action="new", host_name=host_name)
        )

    @user_router.callback_query(F.data.startswith("extend_key_"))
    @registration_required
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

        if not plans:
            await callback.message.edit_text(
                f"❌ Извините, для сервера \"{host_name}\" в данный момент не настроены тарифы для продления."
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
    async def plan_selection_handler(callback: types.CallbackQuery, state: FSMContext):
        await callback.answer()
        
        parts = callback.data.split("_")[1:]
        action = parts[-2]
        key_id = int(parts[-1])
        plan_id = int(parts[-3])
        host_name = "_".join(parts[:-3])

        await state.update_data(
            action=action, key_id=key_id, plan_id=plan_id, host_name=host_name
        )
        
        await callback.message.edit_text(
            "📧 Пожалуйста, введите ваш email для отправки чека об оплате.\n\n"
            "Если вы не хотите указывать почту, нажмите кнопку ниже.",
            reply_markup=keyboards.create_skip_email_keyboard()
        )
        await state.set_state(PaymentProcess.waiting_for_email)

    @user_router.callback_query(PaymentProcess.waiting_for_email, F.data == "back_to_plans")
    async def back_to_plans_handler(callback: types.CallbackQuery, state: FSMContext):
        data = await state.get_data()
        await state.clear()
        
        action = data.get('action')

        if action == 'new':
            await buy_new_key_handler(callback)
        elif action == 'extend':
            await extend_key_handler(callback)
        else:
            await back_to_main_menu_handler(callback)

    @user_router.message(PaymentProcess.waiting_for_email)
    async def process_email_handler(message: types.Message, state: FSMContext):
        if is_valid_email(message.text):
            await state.update_data(customer_email=message.text)
            await message.answer(f"✅ Email принят: {message.text}")

            data = await state.get_data()
            from shop_bot.data_manager.database import get_user_balance
            user_balance = get_user_balance(message.chat.id)
            await message.answer(
                CHOOSE_PAYMENT_METHOD_MESSAGE,
                reply_markup=keyboards.create_payment_method_keyboard(
                    payment_methods=PAYMENT_METHODS,
                    action=data.get('action'),
                    key_id=data.get('key_id'),
                    user_balance=float(user_balance or 0)
                )
            )
            await state.set_state(PaymentProcess.waiting_for_payment_method)
            logger.info(f"User {message.chat.id}: State set to waiting_for_payment_method")
        else:
            await message.answer("❌ Неверный формат email. Попробуйте еще раз.")

    @user_router.callback_query(PaymentProcess.waiting_for_email, F.data == "skip_email")
    async def skip_email_handler(callback: types.CallbackQuery, state: FSMContext):
        await callback.answer()
        await state.update_data(customer_email=None)

        data = await state.get_data()
        from shop_bot.data_manager.database import get_user_balance
        user_balance = get_user_balance(callback.from_user.id)
        await callback.message.edit_text(
            CHOOSE_PAYMENT_METHOD_MESSAGE,
            reply_markup=keyboards.create_payment_method_keyboard(
                payment_methods=PAYMENT_METHODS,
                action=data.get('action'),
                key_id=data.get('key_id'),
                user_balance=float(user_balance or 0)
            )
        )
        await state.set_state(PaymentProcess.waiting_for_payment_method)
        logger.info(f"User {callback.from_user.id}: State set to waiting_for_payment_method")

    # ====== Topup flow payments via Stars and TON Connect ======
    @user_router.callback_query(TopupProcess.waiting_for_payment_method, F.data == "topup_pay_stars")
    async def topup_pay_stars(callback: types.CallbackQuery, state: FSMContext):
        await callback.answer("Создаю счет на пополнение через Stars...")
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

    @user_router.callback_query(TopupProcess.waiting_for_payment_method, F.data == "topup_pay_tonconnect")
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
    async def show_payment_options(message: types.Message, state: FSMContext):
        data = await state.get_data()
        user_data = get_user(message.chat.id)
        plan = get_plan_by_id(data.get('plan_id'))
        
        if not plan:
            await message.edit_text("❌ Ошибка: Тариф не найден.")
            await state.clear()
            return

        price = Decimal(str(plan['price']))
        final_price = price
        discount_applied = False
        message_text = CHOOSE_PAYMENT_METHOD_MESSAGE

        if user_data.get('referred_by') and user_data.get('total_spent', 0) == 0:
            discount_percentage_str = get_setting("referral_discount") or "0"
            discount_percentage = Decimal(discount_percentage_str)
            
            if discount_percentage > 0:
                discount_amount = (price * discount_percentage / 100).quantize(Decimal("0.01"))
                final_price = price - discount_amount

                message_text = (
                    f"🎉 Как приглашенному пользователю, на вашу первую покупку предоставляется скидка {discount_percentage_str}%!\n"
                    f"Старая цена: <s>{price:.2f} RUB</s>\n"
                    f"<b>Новая цена: {final_price:.2f} RUB</b>\n\n"
                ) + CHOOSE_PAYMENT_METHOD_MESSAGE

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
        
    @user_router.callback_query(PaymentProcess.waiting_for_payment_method, F.data == "back_to_email_prompt")
    async def back_to_email_prompt_handler(callback: types.CallbackQuery, state: FSMContext):
        await callback.message.edit_text(
            "📧 Пожалуйста, введите ваш email для отправки чека об оплате.\n\n"
            "Если вы не хотите указывать почту, нажмите кнопку ниже.",
            reply_markup=keyboards.create_skip_email_keyboard()
        )
        await state.set_state(PaymentProcess.waiting_for_email)


    @user_router.callback_query(PaymentProcess.waiting_for_payment_method, F.data == "pay_yookassa")
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

        if user_data.get('referred_by') and user_data.get('total_spent', 0) == 0:
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
        
        if not customer_email:
            customer_email = get_setting("receipt_email")

        plan = get_plan_by_id(plan_id)
        if not plan:
            await callback.message.answer("Произошла ошибка при выборе тарифа.")
            await state.clear()
            return

        months = plan['months']
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
                if action == "new":
                    key_number = get_next_key_number(user_id)
                    # Email теперь только ID пользователя
                    email = f"{user_id}"
                    comment = f"user{user_id}-key{key_number}@{host_name.replace(' ', '').lower()}.bot"
                elif action == "extend":
                    key_data = get_key_by_id(key_id)
                    if not key_data or key_data['user_id'] != user_id:
                        await callback.message.edit_text("❌ Ошибка: ключ для продления не найден.")
                        await state.clear()
                        return
                    email = key_data['key_email']
                    comment = key_data.get('connection_string') or ''
                
                # Учитываем месяцы, дни и ЧАСЫ тарифа
                extra_days = int(plan.get('days') or 0) if plan else 0
                extra_hours = int(plan.get('hours') or 0) if plan else 0
                if extra_hours < 0:
                    extra_hours = 0
                if extra_hours > 24:
                    extra_hours = 24
                days_to_add = months * 30 + extra_days + (extra_hours / 24)
                result = await xui_api.create_or_update_key_on_host(
                    host_name=host_name,
                    email=email,
                    days_to_add=days_to_add,
                    comment=comment
                )

                if not result:
                    await callback.message.edit_text("❌ Не удалось создать/обновить ключ в панели.")
                    await state.clear()
                    return

                if action == "new":
                    key_id = add_new_key(
                        user_id,
                        host_name,
                        result['client_uuid'],
                        result['email'],
                        result['expiry_timestamp_ms'],
                        connection_string=result.get('connection_string'),
                        plan_name=plan['plan_name'],
                        price=0.0
                    )
                elif action == "extend":
                    update_key_info(key_id, result['client_uuid'], result['expiry_timestamp_ms'])
                
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

                final_text = get_purchase_success_text(
                    action="создан" if action == "new" else "продлен",
                    key_number=key_number,
                    expiry_date=new_expiry_date,
                    connection_string=connection_string
                )
                
                await callback.message.edit_text(
                    text=final_text,
                    reply_markup=keyboards.create_key_info_keyboard(key_id)
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

            receipt = None
            if customer_email and is_valid_email(customer_email):
                receipt = {
                    "customer": {"email": customer_email},
                    "items": [{
                        "description": f"Подписка на {months} мес.",
                        "quantity": "1.00",
                        "amount": {"value": price_str_for_api, "currency": "RUB"},
                        "vat_code": "1"
                    }]
                }
            payment_payload = {
                "amount": {"value": price_str_for_api, "currency": "RUB"},
                "confirmation": {"type": "redirect", "return_url": f"https://t.me/{TELEGRAM_BOT_USERNAME}"},
                "capture": True,
                "description": f"Подписка на {months} мес.",
                "metadata": {
                    "user_id": user_id, "months": months, "price": price_float_for_metadata, 
                    "action": action, "key_id": key_id, "host_name": host_name,
                    "plan_id": plan_id, "customer_email": customer_email,
                    "payment_method": "YooKassa"
                }
            }
            if receipt:
                payment_payload['receipt'] = receipt

            payment = Payment.create(payment_payload, uuid.uuid4())
            
            await state.clear()
            
            await callback.message.edit_text(
                "Нажмите на кнопку ниже для оплаты:",
                reply_markup=keyboards.create_payment_keyboard(payment.confirmation.confirmation_url)
            )
        except Exception as e:
            logger.error(f"Failed to create YooKassa payment: {e}", exc_info=True)
            await callback.message.answer("Не удалось создать ссылку на оплату.")
            await state.clear()

    @user_router.callback_query(PaymentProcess.waiting_for_payment_method, F.data == "pay_cryptobot")
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
            
            payload_data = f"{user_id}:{months}:{float(price_rub)}:{action}:{key_id}:{host_name}:{plan_id}:{customer_email}:CryptoBot"

            invoice = await crypto.create_invoice(
                currency_type="fiat",
                fiat="RUB",
                amount=float(price_rub),
                description=f"Подписка на {months} мес.",
                payload=payload_data,
                expires_in=3600
            )
            
            if not invoice or not invoice.pay_url:
                raise Exception("Failed to create invoice or pay_url is missing.")

            await callback.message.edit_text(
                "Нажмите на кнопку ниже для оплаты:",
                reply_markup=keyboards.create_payment_keyboard(invoice.pay_url)
            )
            await state.clear()

        except Exception as e:
            logger.error(f"Failed to create Crypto Pay invoice for user {user_id}: {e}", exc_info=True)
            await callback.message.edit_text(f"❌ Не удалось создать счет для оплаты криптовалютой.\n\n<pre>Ошибка: {e}</pre>")
            await state.clear()
        
    @user_router.callback_query(PaymentProcess.waiting_for_payment_method, F.data == "pay_heleket")
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
        
        final_price_float = float(price_rub_decimal)

        pay_url = await _create_heleket_payment_request(
            user_id=callback.from_user.id,
            price=final_price_float,
            months=plan['months'],
            host_name=data.get('host_name'),
            state_data=data
        )
        
        if pay_url:
            await callback.message.edit_text(
                "Нажмите на кнопку ниже для оплаты:",
                reply_markup=keyboards.create_payment_keyboard(pay_url)
            )
            await state.clear()
        else:
            await callback.message.edit_text("❌ Не удалось создать счет Heleket. Попробуйте другой способ оплаты.")

    @user_router.callback_query(PaymentProcess.waiting_for_payment_method, F.data == "pay_tonconnect")
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
            
        price_rub = Decimal(str(data.get('final_price', plan['price'])))

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
                if action == "new":
                    key_number = get_next_key_number(user_id)
                    # Строим email на основе стабильного host_code (если есть)
                    try:
                        from shop_bot.data_manager.database import get_host
                        host_rec = get_host(host_name)
                        host_code = (host_rec.get('host_code') or host_name).replace(' ', '').lower() if host_rec else host_name.replace(' ', '').lower()
                    except Exception:
                        host_code = host_name.replace(' ', '').lower()
                    email = f"user{user_id}-key{key_number}@{host_code}.bot"
                elif action == "extend":
                    key_data = get_key_by_id(key_id)
                    if not key_data or key_data['user_id'] != user_id:
                        await callback.message.edit_text("❌ Ошибка: ключ для продления не найден.")
                        await state.clear()
                        return
                    email = key_data['key_email']
                
                months = plan['months']
                plan_id = plan['plan_id']
                extra_days = int(plan.get('days') or 0)
                extra_hours = int(plan.get('hours') or 0)
                if extra_hours < 0:
                    extra_hours = 0
                if extra_hours > 24:
                    extra_hours = 24
                days_to_add = months * 30 + extra_days + (extra_hours / 24)
                result = await xui_api.create_or_update_key_on_host(
                    host_name=host_name,
                    email=email,
                    days_to_add=days_to_add
                )

                if not result:
                    await callback.message.edit_text("❌ Не удалось создать/обновить ключ в панели.")
                    await state.clear()
                    return

                if action == "new":
                    key_id = add_new_key(
                        user_id,
                        host_name,
                        result['client_uuid'],
                        result['email'],
                        result['expiry_timestamp_ms'],
                        connection_string=result.get('connection_string'),
                        plan_name=plan['plan_name'],
                        price=0.0
                    )
                elif action == "extend":
                    update_key_info(key_id, result['client_uuid'], result['expiry_timestamp_ms'])
                
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

                final_text = get_purchase_success_text(
                    action="создан" if action == "new" else "продлен",
                    key_number=key_number,
                    expiry_date=new_expiry_date,
                    connection_string=connection_string
                )
                
                await callback.message.edit_text(
                    text=final_text,
                    reply_markup=keyboards.create_key_info_keyboard(key_id)
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
            "user_id": user_id, "months": plan['months'], "price": float(price_rub),
            "action": data.get('action'), "key_id": data.get('key_id'),
            "host_name": data.get('host_name'), "plan_id": data.get('plan_id'),
            "plan_name": plan['plan_name'],  # Добавляем название плана
            "customer_email": data.get('customer_email'), "payment_method": "TON Connect",
            "payment_id": payment_id  # Добавляем payment_id в metadata
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
                except Exception:
                    bot_instance = None
            
            connect_url = await _start_ton_connect_process(user_id, transaction_payload, metadata, bot_instance)
            
            qr_img = qrcode.make(connect_url)
            bio = BytesIO()
            qr_img.save(bio, "PNG")
            qr_file = BufferedInputFile(bio.getvalue(), "ton_qr.png")

            await callback.message.delete()
            await callback.message.answer_photo(
                photo=qr_file,
                caption=(
                    f"💎 **Оплата через TON Connect**\n\n"
                    f"Сумма к оплате: `{price_ton}` **TON**\n\n"
                    f"✅ **Способ 1 (на телефоне):** Нажмите кнопку **'Открыть кошелек'** ниже.\n"
                    f"✅ **Способ 2 (на компьютере):** Отсканируйте QR-код кошельком.\n\n"
                    f"После подключения кошелька подтвердите транзакцию."
                ),
                parse_mode="Markdown",
                reply_markup=keyboards.create_ton_connect_keyboard(connect_url)
            )
            await state.clear()

        except Exception as e:
            logger.error(f"Failed to generate TON Connect link for user {user_id}: {e}", exc_info=True)
            await callback.message.answer("❌ Не удалось создать ссылку для TON Connect. Попробуйте позже.")
            await state.clear()

    @user_router.callback_query(PaymentProcess.waiting_for_payment_method, F.data == "pay_stars")
    async def create_stars_invoice_handler(callback: types.CallbackQuery, state: FSMContext):
        logger.info(f"User {callback.from_user.id}: Entered create_stars_invoice_handler.")
        try:
            await callback.answer("Создаю счет через Stars...")
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
            price_rub = float(data.get('final_price') or (plan or {}).get('price') or 0)

            # Бесплатный тариф — обрабатываем без счета
            if price_rub == 0:
                await callback.message.edit_text("🎉 Бесплатный тариф! Обрабатываю ваш запрос...")
                metadata = {
                    "user_id": user_id,
                    "months": months,
                    "price": 0.0,
                    "action": action,
                    "key_id": key_id,
                    "host_name": host_name,
                    "plan_id": plan_id,
                    "plan_name": plan.get('plan_name'),
                    "customer_email": customer_email,
                    "payment_method": "Stars",
                    "payment_id": str(uuid.uuid4())
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

            invoice_price = types.LabeledPrice(label=f"{plan.get('plan_name', 'Тариф')}", amount=amount_stars)

            payment_id = str(uuid.uuid4())
            payment_metadata = {
                "user_id": user_id,
                "months": months,
                "price": float(price_rub),
                "action": action,
                "key_id": key_id,
                "host_name": host_name,
                "plan_id": int(plan_id),
                "plan_name": plan.get('plan_name'),
                "customer_email": customer_email,
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

    @user_router.callback_query(PaymentProcess.waiting_for_payment_method, F.data == "pay_balance")
    async def pay_with_internal_balance(callback: types.CallbackQuery, state: FSMContext):
        await callback.answer("Проверяю баланс и оформляю покупку...")
        try:
            data = await state.get_data()
            user_id = callback.from_user.id
            action = data.get('action')
            key_id = data.get('key_id')
            host_name = data.get('host_name')
            plan_id = data.get('plan_id')
            months = int(data.get('months') or 0) or int((get_plan_by_id(plan_id) or {}).get('months') or 0)
            # Цена к списанию: учитываем возможную скидку, если была рассчитана
            price = float(data.get('final_price') or (get_plan_by_id(plan_id) or {}).get('price') or 0)

            from shop_bot.data_manager.database import get_user_balance, add_to_user_balance
            current_balance = get_user_balance(user_id)
            if current_balance < price:
                await callback.message.answer(
                    f"❌ Недостаточно средств на балансе. Доступно: {current_balance:.2f} RUB, требуется: {price:.2f} RUB.",
                    reply_markup=keyboards.create_back_to_menu_keyboard()
                )
                return

            # Списываем средства
            add_to_user_balance(user_id, -price)

            # Формируем metadata и запускаем общий процесс выдачи
            metadata = {
                "user_id": user_id,
                "months": months,
                "price": price,
                "action": action,
                "key_id": key_id,
                "host_name": host_name,
                "plan_id": plan_id,
                "customer_email": data.get('customer_email'),
                "payment_method": "Из баланса",
                "payment_id": str(uuid.uuid4())
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
                await callback.message.answer(f"✅ С баланса списано {price:.2f} RUB")
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
        @registration_required
        async def unknown_message_handler(message: types.Message):
            if message.text.startswith('/'):
                await message.answer("Такой команды не существует. Попробуйте /start.")
            else:
                await message.answer("Я не понимаю эту команду. Пожалуйста, используйте кнопки меню.")

    @user_router.pre_checkout_query()
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
                user_id = int(metadata.get('user_id'))
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
                user_id = int(metadata.get('user_id'))
                operation = metadata.get('operation')
                months = int(metadata.get('months')) if metadata.get('months') else 0
                price = float(metadata.get('price', 0))
                action = metadata.get('action')
                key_id = int(metadata.get('key_id')) if metadata.get('key_id') else 0
                host_name = metadata.get('host_name')
                plan_id = int(metadata.get('plan_id')) if metadata.get('plan_id') else 0
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
        manifest_url = 'https://paris.dark-maximus.com/.well-known/tonconnect-manifest.json'
        _user_connectors[user_id] = TonConnect(manifest_url=manifest_url)
    return _user_connectors[user_id]

async def _listener_task(connector: TonConnect, user_id: int, transaction_payload: dict, payment_metadata: dict = None, bot_instance = None):
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

    connector = await _get_ton_connect_instance(user_id)
    
    task = asyncio.create_task(
        _listener_task(connector, user_id, transaction_payload, metadata, bot_instance)
    )
    _listener_tasks[user_id] = task

    wallets = connector.get_wallets()
    return await connector.connect(wallets[0])

async def process_successful_onboarding(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer("✅ Спасибо! Доступ предоставлен.")
    set_terms_agreed(callback.from_user.id)
    await state.clear()
    await callback.message.delete()
    await callback.message.answer("Приятного использования!", reply_markup=keyboards.get_main_reply_keyboard())
    await show_main_menu(callback.message)

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
    if not ADMIN_ID:
        logger.warning("Admin notification skipped: ADMIN_ID is not set.")
        return

    try:
        user_id = metadata.get('user_id')
        months = metadata.get('months')
        price = float(metadata.get('price'))
        host_name = metadata.get('host_name')
        plan_id = metadata.get('plan_id')
        payment_method = metadata.get('payment_method', 'Unknown')
        
        user_info = get_user(user_id)
        plan_info = get_plan_by_id(plan_id)

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
            chat_id=ADMIN_ID,
            text=message_text,
            parse_mode='HTML'
        )
        logger.info(f"Admin notification sent for a new purchase by user {user_id}.")

    except Exception as e:
        logger.error(f"Failed to send admin notification for purchase: {e}", exc_info=True)

async def _create_heleket_payment_request(user_id: int, price: float, months: int, host_name: str, state_data: dict) -> str | None:
    merchant_id = get_setting("heleket_merchant_id")
    api_key = get_setting("heleket_api_key")
    bot_username = get_setting("telegram_bot_username")
    domain = get_setting("domain")

    if not all([merchant_id, api_key, bot_username, domain]):
        logger.error("Heleket Error: Not all required settings are configured.")
        return None

    redirect_url = f"https://t.me/{bot_username}"
    order_id = str(uuid.uuid4())
    
    metadata = {
        "user_id": user_id, "months": months, "price": float(price),
        "action": state_data.get('action'), "key_id": state_data.get('key_id'),
        "host_name": host_name, "plan_id": state_data.get('plan_id'),
        "customer_email": state_data.get('customer_email'), "payment_method": "Heleket"
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
        "sign": _generate_heleket_signature(json.dumps(payload), api_key),
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
    """Создает ссылку на транзакцию в TON Explorer"""
    return f"https://tonscan.org/tx/{tx_hash}"

async def process_successful_payment(bot: Bot, metadata: dict, tx_hash: str = None):
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
        price = _to_float(metadata.get('price'))
        action = metadata.get('action')
        key_id = _to_int(metadata.get('key_id'))
        host_name = metadata.get('host_name')
        plan_id = _to_int(metadata.get('plan_id'))
        customer_email = metadata.get('customer_email')
        payment_method = metadata.get('payment_method')

        chat_id_to_delete = metadata.get('chat_id')
        message_id_to_delete = metadata.get('message_id')
        
    except (ValueError, TypeError) as e:
        logger.error(f"FATAL: Could not parse metadata. Error: {e}. Metadata: {metadata}")
        return

    # Пополнение баланса: отдельная ветка
    if operation == 'topup':
        try:
            from shop_bot.data_manager.database import add_to_user_balance
            payment_id = metadata.get('payment_id')
            if payment_id:
                update_transaction_on_payment(payment_id, 'paid', price, tx_hash=tx_hash, metadata=metadata)
            add_to_user_balance(user_id, price)
            await bot.send_message(user_id, f"✅ Баланс пополнен на {price:.2f} RUB", reply_markup=keyboards.create_back_to_menu_keyboard())
        except Exception as e:
            logger.error(f"Failed to process topup for user {user_id}: {e}", exc_info=True)
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
        if action == "new":
            key_number = get_next_key_number(user_id)
            try:
                from shop_bot.data_manager.database import get_host
                host_rec = get_host(host_name)
                host_code = (host_rec.get('host_code') or host_name).replace(' ', '').lower() if host_rec else host_name.replace(' ', '').lower()
            except Exception:
                host_code = host_name.replace(' ', '').lower()
            email = f"user{user_id}-key{key_number}@{host_code}.bot"
            try:
                from shop_bot.data_manager.database import get_host
                host_rec = get_host(host_name)
                host_code = (host_rec.get('host_code') or host_name).replace(' ', '').lower() if host_rec else host_name.replace(' ', '').lower()
            except Exception:
                host_code = host_name.replace(' ', '').lower()
            email = f"user{user_id}-key{key_number}@{host_code}.bot"
        elif action == "extend":
            key_data = get_key_by_id(key_id)
            if not key_data or key_data['user_id'] != user_id:
                await processing_message.edit_text("❌ Ошибка: ключ для продления не найден.")
                return
            email = key_data['key_email']
        
        # Учитываем дополнительные дни и трафик
        plan = get_plan_by_id(plan_id)
        extra_days = int(plan.get('days') or 0) if plan else 0
        extra_hours = int(plan.get('hours') or 0) if plan else 0
        if extra_hours < 0:
            extra_hours = 0
        if extra_hours > 24:
            extra_hours = 24
        traffic_gb = float(plan.get('traffic_gb') or 0) if plan else 0.0
        days_to_add = months * 30 + extra_days + (extra_hours / 24)
        result = await xui_api.create_or_update_key_on_host(
            host_name=host_name,
            email=email,
            days_to_add=days_to_add,
            traffic_gb=traffic_gb if traffic_gb > 0 else None
        )

        if not result:
            await processing_message.edit_text("❌ Не удалось создать/обновить ключ в панели.")
            return

        if action == "new":
            key_id = add_new_key(
                user_id, 
                host_name, 
                result['client_uuid'], 
                result['email'], 
                result['expiry_timestamp_ms'],
                connection_string=result.get('connection_string'),
                plan_name=(metadata.get('plan_name') or (plan.get('plan_name') if plan else None)),
                price=float(metadata.get('price', 0))
            )
        elif action == "extend":
            update_key_info(key_id, result['client_uuid'], result['expiry_timestamp_ms'])
        
        price = float(metadata.get('price')) 

        user_data = get_user(user_id)
        referrer_id = user_data.get('referred_by')

        if referrer_id:
            percentage = Decimal(get_setting("referral_percentage") or "0")
            
            reward = (Decimal(str(price)) * percentage / 100).quantize(Decimal("0.01"))
            
            if float(reward) > 0:
                add_to_referral_balance(referrer_id, float(reward))
                
                try:
                    referrer_username = user_data.get('username', 'пользователь')
                    await bot.send_message(
                        referrer_id,
                        f"🎉 Ваш реферал @{referrer_username} совершил покупку на сумму {price:.2f} RUB!\n"
                        f"💰 На ваш баланс начислено вознаграждение: {reward:.2f} RUB."
                    )
                except Exception as e:
                    logger.warning(f"Could not send referral reward notification to {referrer_id}: {e}")

        update_user_stats(user_id, price, months)
        
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
                plan_obj = get_plan_by_id(metadata.get('plan_id'))
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
        
        await processing_message.delete()
        
        connection_string = result['connection_string']
        new_expiry_date = datetime.fromtimestamp(result['expiry_timestamp_ms'] / 1000)
        
        all_user_keys = get_user_keys(user_id)
        key_number = next((i + 1 for i, key in enumerate(all_user_keys) if key['key_id'] == key_id), len(all_user_keys))

        final_text = get_purchase_success_text(
            action="создан" if action == "new" else "продлен",
            key_number=key_number,
            expiry_date=new_expiry_date,
            connection_string=connection_string
        )
        
        # Добавляем информацию о транзакции, если есть
        if tx_hash and payment_method == "TON Connect":
            transaction_url = get_ton_transaction_url(tx_hash)
            final_text += f"\n\n🔗 <a href='{transaction_url}'>Проверить транзакцию в TON Explorer</a>"
        
        await bot.send_message(
            chat_id=user_id,
            text=final_text,
            reply_markup=keyboards.create_key_info_keyboard(key_id),
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
        await processing_message.edit_text("❌ Ошибка при выдаче ключа.")
        
        # Возвращаем статус транзакции на pending при ошибке
        try:
            from shop_bot.data_manager.database import update_transaction_status
            payment_id = metadata.get('payment_id')
            if payment_id:
                update_transaction_status(payment_id, 'pending')
                logger.info(f"Transaction {payment_id} status reverted to pending due to error")
        except Exception as revert_error:
            logger.error(f"Failed to revert transaction status: {revert_error}")