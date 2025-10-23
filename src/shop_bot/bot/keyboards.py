# -*- coding: utf-8 -*-
"""
Клавиатуры для Telegram-бота
"""

import logging

from datetime import datetime

from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from shop_bot.data_manager.database import get_setting

logger = logging.getLogger(__name__)

def get_main_reply_keyboard(is_admin: bool = False) -> ReplyKeyboardMarkup:
    """Возвращает актуальную Reply-клавиатуру без пункта "Главное меню".
    Пункт "Реферальная программа" отображается только при включенной настройке.
    Пункт "Админ-панель" отображается только для администраторов.
    Пункт "Пробный период" отображается только при включенной настройке.
    """
    rows = []
    # Первая строка: Купить
    rows.append([KeyboardButton(text="🛒 Купить")])

    # Вторая строка: Профиль и Пополнить баланс
    rows.append([KeyboardButton(text="👤 Мой профиль"), KeyboardButton(text="💰Пополнить баланс")])

    # Третья строка: Помощь и поддержка
    rows.append([KeyboardButton(text="⁉️ Помощь и поддержка")])

    # Пробный период убран из главного меню

    # Пятая строка: Админ-панель (только для администраторов)
    if is_admin:
        rows.append([KeyboardButton(text="⚙️ Админ-панель")])

    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)


def create_buy_root_keyboard(user_keys: list) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    # Кнопка купить новый ключ
    builder.button(text="➕ Купить новый ключ", callback_data="buy_new_key")
    # Условная кнопка продления при наличии хотя бы одного ключа
    if user_keys:
        builder.button(text=f"✅🔄 Продлить текущий [{len(user_keys)}]", callback_data="manage_keys")
    builder.button(text="⬅️ Назад в меню", callback_data="back_to_main_menu")
    builder.adjust(1)
    return builder.as_markup()

def create_profile_menu_keyboard(total_keys_count: int | None = None, trial_used: int = 1) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    keys_suffix = f" [{total_keys_count}] шт." if isinstance(total_keys_count, int) and total_keys_count >= 0 else ""
    builder.button(text=f"🔑 Мои ключи{keys_suffix}", callback_data="manage_keys")
    
    builder.button(text="💳 Пополнить баланс", callback_data="topup_root")
    if get_setting("enable_referrals") == "true":
        builder.button(text="🤝 Реферальная программа", callback_data="show_referral_program")
    builder.button(text="⬅️ Назад в меню", callback_data="back_to_main_menu")
    builder.adjust(1)
    return builder.as_markup()

def create_service_selection_keyboard(trial_used: int = 1, total_keys_count: int = 0) -> InlineKeyboardMarkup:
    """Создает клавиатуру для выбора услуги"""
    builder = InlineKeyboardBuilder()
    builder.button(text="🆕 Купить новый VPN", callback_data="buy_new_vpn")
    
    # Добавляем кнопку продления только если есть хоть один ключ
    if total_keys_count > 0:
        builder.button(text="🔄 Продлить VPN", callback_data="manage_keys")
    
    # Добавляем пробный период только если он не использован
    if trial_used == 0:
        builder.button(text="🆓 Пробный период VPN", callback_data="trial_period")
    
    builder.button(text="⬅️ Назад в меню", callback_data="back_to_main_menu")
    builder.adjust(1)
    return builder.as_markup()

def create_help_center_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    try:
        support_enabled = get_setting("support_enabled") == "true"
    except Exception:
        support_enabled = False
    if support_enabled:
        builder.button(text="🆘 Поддержка", callback_data="show_help")
    builder.button(text="🌐 Как настроить VPN❓", callback_data="howto_vless")
    builder.button(text="ℹ️ О проекте", callback_data="show_about")
    builder.button(text="⬅️ Назад в меню", callback_data="back_to_main_menu")
    builder.adjust(1)
    return builder.as_markup()

def create_topup_amounts_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="179 рублей", callback_data="topup_amount_179")
    builder.button(text="300 рублей", callback_data="topup_amount_300")
    builder.button(text="500 рублей", callback_data="topup_amount_500")
    builder.button(text="Ввести другую сумму", callback_data="topup_amount_custom")
    # Возврат учитывает origin через состояние в обработчике
    builder.button(text="⬅️ Назад", callback_data="topup_back_to_origin")
    builder.adjust(1)
    return builder.as_markup()

def create_topup_payment_methods_keyboard() -> InlineKeyboardBuilder:
    builder = InlineKeyboardBuilder()
    
    # Проверяем доступные методы платежа
    from src.shop_bot.data_manager.database import get_setting
    
    # YooKassa - используем ту же логику, что и в bot_controller
    yookassa_test_mode = get_setting("yookassa_test_mode") == "true"
    if yookassa_test_mode:
        # Тестовый режим - используем тестовые ключи, но если они не работают, используем боевые
        yookassa_shop_id = get_setting("yookassa_test_shop_id") or get_setting("yookassa_shop_id")
        yookassa_secret_key = get_setting("yookassa_test_secret_key") or get_setting("yookassa_secret_key")
    else:
        # Боевой режим
        yookassa_shop_id = get_setting("yookassa_shop_id")
        yookassa_secret_key = get_setting("yookassa_secret_key")
    
    yookassa_enabled = bool(yookassa_shop_id and yookassa_secret_key)
    
    if yookassa_enabled:
        if get_setting("sbp_enabled") == "true":
            builder.button(text="🏦 СБП / Банковская карта", callback_data="topup_pay_yookassa")
        else:
            builder.button(text="🏦 Банковская карта", callback_data="topup_pay_yookassa")
    
    # Оплата через Stars и TON Connect
    builder.button(text="⭐ Telegram Звезды (Stars)", callback_data="topup_pay_stars")
    builder.button(text="🪙 TonCoin (криптовалюта)", callback_data="topup_pay_tonconnect")
    builder.button(text="⬅️ Назад", callback_data="topup_back_to_amounts")
    builder.adjust(1)
    return builder.as_markup()

def create_stars_payment_keyboard(amount_stars: int, is_topup: bool = False) -> InlineKeyboardMarkup:
    """Создает клавиатуру для оплаты звездами с кнопкой 'Не удалось заплатить'"""
    builder = InlineKeyboardBuilder()
    
    # Основная кнопка оплаты
    builder.button(text=f"Заплатить {amount_stars} ⭐", callback_data="confirm_stars_payment")
    
    # Кнопка "Не удалось заплатить"
    callback_data = "topup_stars_payment_failed" if is_topup else "stars_payment_failed"
    builder.button(text="Не удалось заплатить", callback_data=callback_data)
    
    builder.adjust(1)
    return builder.as_markup()

def create_stars_payment_failed_keyboard(is_topup: bool = False) -> InlineKeyboardMarkup:
    """Создает клавиатуру для меню 'Не удалось заплатить'"""
    builder = InlineKeyboardBuilder()
    
    # Кнопка перехода к Premium Bot
    builder.button(text="Пополнить RUB", url="https://t.me/PremiumBot")
    
    # Кнопка "Назад в меню"
    callback_data = "topup_back_to_payment_methods" if is_topup else "back_to_payment_methods"
    builder.button(text="Назад", callback_data=callback_data)
    
    builder.adjust(1)
    return builder.as_markup()

def create_broadcast_options_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="➕ Добавить кнопку", callback_data="broadcast_add_button")
    builder.button(text="➡️ Пропустить", callback_data="broadcast_skip_button")
    builder.button(text="❌ Отмена", callback_data="cancel_broadcast")
    builder.adjust(2, 1)
    return builder.as_markup()

def create_broadcast_confirmation_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Отправить всем", callback_data="confirm_broadcast")
    builder.button(text="❌ Отмена", callback_data="cancel_broadcast")
    builder.adjust(2)
    return builder.as_markup()

def create_broadcast_cancel_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="❌ Отмена", callback_data="cancel_broadcast")
    return builder.as_markup()

def create_admin_panel_keyboard() -> InlineKeyboardMarkup:
    """Создает клавиатуру админ-панели"""
    builder = InlineKeyboardBuilder()
    builder.button(text="📢 Рассылка", callback_data="start_broadcast")
    builder.button(text="🔄 Сбросить триал", callback_data="admin_reset_trial")
    builder.button(text="⬅️ Назад в меню", callback_data="back_to_main_menu")
    builder.adjust(1)
    return builder.as_markup()

def create_trial_reset_keyboard() -> InlineKeyboardMarkup:
    """Создает клавиатуру для сброса триала"""
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Подтвердить сброс", callback_data="confirm_trial_reset")
    builder.button(text="❌ Отмена", callback_data="cancel_trial_reset")
    builder.adjust(1)
    return builder.as_markup()

def create_about_keyboard(channel_url: str | None, terms_url: str | None, privacy_url: str | None) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    
    # Проверяем, что URL не localhost
    if terms_url and (terms_url.startswith("http://localhost") or terms_url.startswith("https://localhost")):
        terms_url = None
    if privacy_url and (privacy_url.startswith("http://localhost") or privacy_url.startswith("https://localhost")):
        privacy_url = None
    
    if channel_url:
        builder.button(text="📰 Наш канал", url=channel_url)
    if terms_url:
        builder.button(text="📄 Условия использования", web_app={"url": terms_url})
    if privacy_url:
        builder.button(text="🔒 Политика конфиденциальности", web_app={"url": privacy_url})
    # Возврат в центр помощи
    builder.button(text="⬅️ Назад", callback_data="help_center")
    builder.adjust(1)
    return builder.as_markup()
    
def create_support_keyboard(support_user: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="🆘 Написать в поддержку", url=support_user)
    builder.button(text="⬅️ Назад", callback_data="help_center")
    builder.adjust(1)
    return builder.as_markup()

def create_host_selection_keyboard(hosts: list, action: str, total_keys_count: int | None = None, back_to: str | None = None) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for host in hosts:
        callback_data = f"select_host_{action}_{host['host_name']}"
        builder.button(text=host['host_name'], callback_data=callback_data)
    # Возможность переопределить точку возврата
    if back_to:
        back_callback = back_to
    else:
        back_callback = "manage_keys" if action == 'new' else "back_to_main_menu"
    builder.button(text="⬅️ Назад", callback_data=back_callback)
    builder.adjust(1)
    return builder.as_markup()

def create_plans_keyboard(plans: list[dict], action: str, host_name: str, key_id: int = 0) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for plan in plans:
        callback_data = f"buy_{host_name}_{plan['plan_id']}_{action}_{key_id}"
        months = int(plan.get('months') or 0)
        days = int(plan.get('days') or 0)
        traffic = plan.get('traffic_gb') or 0
        suffix_parts = []
        if months > 0:
            suffix_parts.append(f"{months} мес")
        if days > 0:
            suffix_parts.append(f"{days} дн")
        traffic_str = "∞" if not traffic or float(traffic) == 0 else f"{float(traffic):.0f} ГБ"
        suffix = (" · "+"; ".join(suffix_parts)) if suffix_parts else ""
        text = f"{plan['plan_name']} - {plan['price']:.2f} RUB{suffix} · Трафик: {traffic_str}"
        builder.button(text=text, callback_data=callback_data)
    # Для extend возвращаемся к списку ключей, для new - к списку серверов
    if action == "extend":
        back_callback = f"show_key_{key_id}" if key_id else "manage_keys"
    else:
        back_callback = "buy_new_key"
    builder.button(text="⬅️ Назад", callback_data=back_callback)
    builder.adjust(1) 
    return builder.as_markup()

def create_skip_email_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="➡️ Продолжить без почты", callback_data="skip_email")
    builder.button(text="⬅️ Назад к тарифам", callback_data="back_to_plans")
    builder.adjust(1)
    return builder.as_markup()

def create_back_to_payment_methods_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="⬅️ Назад к способам оплаты", callback_data="back_to_payment_methods")
    builder.adjust(1)
    return builder.as_markup()

def create_payment_method_keyboard(payment_methods: dict | None, action: str, key_id: int, user_balance: float | None = None) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    # Предлагаем оплату с внутреннего баланса первой кнопкой
    balance_suffix = f" {user_balance:.2f} RUB" if isinstance(user_balance, (int, float)) else ""
    builder.button(text=f"💰 С баланса{balance_suffix}", callback_data="pay_balance")
    
    # Если payment_methods не передан, используем пустой словарь
    if payment_methods is None:
        payment_methods = {}

    if payment_methods and payment_methods.get("yookassa"):
        if get_setting("sbp_enabled"):
            builder.button(text="🏦 СБП / Банковская карта", callback_data="pay_yookassa")
        else:
            builder.button(text="🏦 Банковская карта", callback_data="pay_yookassa")
    if payment_methods and payment_methods.get("heleket"):
        builder.button(text="💎 Криптовалюта", callback_data="pay_heleket")
    if payment_methods and payment_methods.get("cryptobot"):
        builder.button(text="🤖 CryptoBot", callback_data="pay_cryptobot")
    if payment_methods and payment_methods.get("tonconnect"):
        callback_data_ton = "pay_tonconnect"
        logger.info(f"Creating TON button with callback_data: '{callback_data_ton}'")
        builder.button(text="🪙 TonCoin (криптовалюта)", callback_data=callback_data_ton)
    # Показываем Stars, если включено либо в переданном списке, либо в актуальных настройках
    try:
        stars_enabled_setting = get_setting("stars_enabled") == "true"
    except Exception:
        stars_enabled_setting = False
    if (payment_methods and payment_methods.get("stars")) or stars_enabled_setting:
        builder.button(text="⭐ Telegram Звезды (Stars)", callback_data="pay_stars")

    # Кнопка для применения промокода
    builder.button(text="🎫 Применить промокод", callback_data="apply_promo_code")
    
    builder.button(text="⬅️ Назад", callback_data="back_to_email_prompt")
    builder.adjust(1)
    return builder.as_markup()

def create_ton_connect_keyboard(connect_url: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="🚀 Открыть кошелек", url=connect_url)
    return builder.as_markup()

def create_payment_keyboard(payment_url: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Перейти к оплате", url=payment_url)
    return builder.as_markup()

def create_keys_management_keyboard(keys: list, trial_used: int = 1) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if keys:
        for i, key in enumerate(keys):
            expiry_date = datetime.fromisoformat(key['expiry_date'])
            # Убираем timezone info для корректного сравнения
            if expiry_date.tzinfo is not None:
                expiry_date = expiry_date.replace(tzinfo=None)
            
            # Определяем статус по реальному времени истечения, а не по статусу в БД
            current_time = datetime.now()
            is_expired = expiry_date <= current_time
            
            if is_expired:
                status_icon = "❌"
            else:
                # Проверяем, есть ли статус в БД для дополнительной информации
                status = key.get('status')
                if status and status in ['deactivate']:
                    status_icon = "❌"  # Деактивированный ключ
                else:
                    status_icon = "✅"
            
            host_name = key.get('host_name', 'Неизвестный хост')
            button_text = f"{status_icon} Ключ #{i+1} ({host_name}) (до {expiry_date.strftime('%d.%m.%Y')})"
            builder.button(text=button_text, callback_data=f"show_key_{key['key_id']}")
    
    # Добавляем пробный период только если он не использован
    if trial_used == 0:
        builder.button(text="🆓 Пробный период", callback_data="trial_period")
    
    builder.button(text="➕ Купить новый ключ", callback_data="buy_new_key")
    builder.button(text="⬅️ Назад", callback_data="show_profile")
    builder.adjust(1)
    return builder.as_markup()

def create_key_info_keyboard(key_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="🔄 Продлить этот ключ", callback_data=f"extend_key_{key_id}")
    builder.button(text="📑 Скопировать ключ", callback_data=f"copy_key_{key_id}")    
    builder.button(text="📱 Сканировать QR ключа", callback_data=f"show_qr_{key_id}")
    builder.button(text="🌐 Как настроить VPN❓", callback_data=f"howto_vless_{key_id}")
    builder.button(text="⬅️ Назад к списку ключей", callback_data="manage_keys")
    builder.adjust(1, 2, 1, 1)
    return builder.as_markup()

def create_qr_keyboard(key_id: int) -> InlineKeyboardMarkup:
    """Клавиатура для QR-кода ключа"""
    builder = InlineKeyboardBuilder()
    builder.button(text="📑 Скопировать ключ", callback_data=f"copy_key_{key_id}")
    builder.button(text="🌐 Как настроить VPN❓", callback_data=f"howto_vless_{key_id}")
    builder.button(text="⬅️ Назад к списку ключей", callback_data="manage_keys")
    builder.adjust(1, 1, 1)
    return builder.as_markup()

def create_howto_vless_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    
    # Сначала добавляем кнопки платформ (всегда в одном порядке)
    from shop_bot.data_manager.database import get_instruction_display_setting
    
    if get_instruction_display_setting('android'):
        builder.button(text="📱 Android", callback_data="howto_android")
    if get_instruction_display_setting('ios'):
        builder.button(text="📱 iOS", callback_data="howto_ios")
    if get_instruction_display_setting('windows'):
        builder.button(text="💻 Windows", callback_data="howto_windows")
    if get_instruction_display_setting('macos'):
        builder.button(text="🖥 MacOS", callback_data="howto_macos")
    if get_instruction_display_setting('linux'):
        builder.button(text="🐧 Linux", callback_data="howto_linux")
    
    # Добавляем кнопку "Видеоинструкции" если она включена (после платформ)
    from shop_bot.data_manager.database import get_video_instructions_display_setting
    if get_video_instructions_display_setting():
        builder.button(text="🎬 Видеоинструкции", callback_data="video_instructions_list")
    
    # Кнопка возврата в центр помощи
    builder.button(text="⬅️ Назад", callback_data="help_center")
    
    # Настройка расположения: 2 кнопки в первом ряду, 3 во втором, остальные по 1
    builder.adjust(2, 3, 1, 1)
    return builder.as_markup()

def create_howto_vless_keyboard_key(key_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    
    # Добавляем кнопку "Видеоинструкции" если она включена
    from shop_bot.data_manager.database import get_video_instructions_display_setting
    if get_video_instructions_display_setting():
        builder.button(text="🎬 Видеоинструкции", callback_data="video_instructions_list")
    
    # Добавляем кнопки платформ только если они включены
    from shop_bot.data_manager.database import get_instruction_display_setting
    
    if get_instruction_display_setting('android'):
        builder.button(text="📱 Android", callback_data="howto_android")
    if get_instruction_display_setting('ios'):
        builder.button(text="📱 iOS", callback_data="howto_ios")
    if get_instruction_display_setting('windows'):
        builder.button(text="💻 Windows", callback_data="howto_windows")
    if get_instruction_display_setting('macos'):
        builder.button(text="🖥 MacOS", callback_data="howto_macos")
    if get_instruction_display_setting('linux'):
        builder.button(text="🐧 Linux", callback_data="howto_linux")
    
    builder.button(text="⬅️ Назад к ключу", callback_data=f"show_key_{key_id}")
    builder.adjust(1, 2, 3, 1)
    return builder.as_markup()

def create_back_to_instructions_keyboard() -> InlineKeyboardMarkup:
    """Создает клавиатуру для возврата к инструкциям"""
    builder = InlineKeyboardBuilder()
    builder.button(text="⬅️ Назад к инструкциям", callback_data="back_to_instructions")
    return builder.as_markup()

def create_user_promo_codes_keyboard(user_promo_codes: list) -> InlineKeyboardMarkup:
    """Создает клавиатуру для управления применёнными промокодами пользователя"""
    builder = InlineKeyboardBuilder()
    
    for promo in user_promo_codes:
        # Кнопка удаления промокода
        builder.button(
            text=f"🗑️ {promo['code']} - удалить", 
            callback_data=f"remove_promo_{promo['usage_id']}"
        )
    
    # Возврат в профиль
    builder.button(text="⬅️ Назад", callback_data="show_profile")
    
    # Настраиваем расположение кнопок (по 1 в ряд)
    builder.adjust(1)
    return builder.as_markup()

def create_back_to_menu_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="⬅️ Назад в меню", callback_data="back_to_main_menu")
    return builder.as_markup()

def create_welcome_keyboard(channel_url: str | None, is_subscription_forced: bool = False, terms_url: str | None = None, privacy_url: str | None = None) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    
    # Проверяем, что URL не localhost
    if terms_url and (terms_url.startswith("http://localhost") or terms_url.startswith("https://localhost")):
        terms_url = None
    if privacy_url and (privacy_url.startswith("http://localhost") or privacy_url.startswith("https://localhost")):
        privacy_url = None

    if channel_url and terms_url and privacy_url and is_subscription_forced:
        builder.button(text="📢 Перейти в канал", url=channel_url)
        builder.button(text="📄 Условия использования", web_app={"url": terms_url})
        builder.button(text="🔒 Политика конфиденциальности", web_app={"url": privacy_url})
        builder.button(text="✅ Я подписался", callback_data="check_subscription_and_agree")
    elif channel_url and terms_url and privacy_url:
        builder.button(text="📢 Наш канал (не обязательно)", url=channel_url)
        builder.button(text="📄 Условия использования", web_app={"url": terms_url})
        builder.button(text="🔒 Политика конфиденциальности", web_app={"url": privacy_url})
        builder.button(text="✅ Принимаю условия", callback_data="check_subscription_and_agree")
    elif terms_url and privacy_url:
        builder.button(text="📄 Условия использования", web_app={"url": terms_url})
        builder.button(text="🔒 Политика конфиденциальности", web_app={"url": privacy_url})
        builder.button(text="✅ Принимаю условия", callback_data="check_subscription_and_agree")
    elif terms_url:
        builder.button(text="📄 Условия использования", web_app={"url": terms_url})
        builder.button(text="✅ Принимаю условия", callback_data="check_subscription_and_agree")
    elif privacy_url:
        builder.button(text="🔒 Политика конфиденциальности", web_app={"url": privacy_url})
        builder.button(text="✅ Принимаю условия", callback_data="check_subscription_and_agree")
    else:
        builder.button(text="📢 Наш канал (не обязательно)", url=channel_url)
        builder.button(text="✅ Я подписался", callback_data="check_subscription_and_agree")
    builder.adjust(1)
    return builder.as_markup()

def get_main_menu_button() -> InlineKeyboardButton:
    return InlineKeyboardButton(text="🏠 В главное меню", callback_data="show_main_menu")

def get_buy_button() -> InlineKeyboardButton:
    return InlineKeyboardButton(text="💳 Купить подписку", callback_data="buy_vpn")

def create_terms_agreement_keyboard(terms_url: str, privacy_url: str) -> InlineKeyboardMarkup:
    """Создает клавиатуру для согласия с документами"""
    builder = InlineKeyboardBuilder()
    builder.button(text="📄 Условия использования", web_app={"url": terms_url})
    builder.button(text="🔒 Политика конфиденциальности", web_app={"url": privacy_url})
    builder.button(text="✅ Принимаю условия", callback_data="agree_to_terms")
    builder.adjust(1, 1, 1)
    return builder.as_markup()

def create_subscription_keyboard(channel_url: str) -> InlineKeyboardMarkup:
    """Создает клавиатуру для проверки подписки"""
    builder = InlineKeyboardBuilder()
    builder.button(text="📢 Перейти в канал", url=channel_url)
    builder.button(text="✅ Я подписался", callback_data="check_subscription")
    builder.adjust(1)
    return builder.as_markup()

def create_video_instructions_keyboard(videos: list) -> InlineKeyboardMarkup:
    """Создает клавиатуру со списком видеоинструкций"""
    from shop_bot.data_manager.database import get_global_domain
    
    builder = InlineKeyboardBuilder()
    
    # Получаем домен для формирования URL
    domain = get_global_domain() or "yourdomain.com"
    
    for video in videos:
        video_url = f"https://{domain}/video/player/{video['video_id']}"
        builder.button(
            text=f"🎬 {video['title']}", 
            web_app={"url": video_url}
        )
    
    builder.button(text="⬅️ Назад", callback_data="back_to_instructions")
    builder.adjust(1)
    return builder.as_markup()

