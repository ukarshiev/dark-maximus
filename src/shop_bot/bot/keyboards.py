# -*- coding: utf-8 -*-
"""
Клавиатуры для Telegram-бота
"""

import logging
from datetime import datetime
from urllib.parse import urlparse

from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from aiogram.utils.keyboard import InlineKeyboardBuilder

from shop_bot.data_manager.database import get_setting, has_any_instructions_enabled, is_production_server, is_development_server, get_global_domain

logger = logging.getLogger(__name__)


def _is_https_url(url: str | None) -> bool:
    """Проверяет, что ссылка использует HTTPS и содержит хост."""
    if not url:
        return False
    try:
        parsed = urlparse(url)
        return parsed.scheme.lower() == "https" and bool(parsed.netloc)
    except Exception:
        return False


def _is_http_like_url(url: str | None) -> bool:
    """Проверяет, что ссылка использует HTTP(S) и имеет хост (для fallback без WebApp)."""
    if not url:
        return False
    try:
        parsed = urlparse(url)
        return parsed.scheme.lower() in {"http", "https"} and bool(parsed.netloc)
    except Exception:
        return False


def _convert_to_https(url: str | None) -> str | None:
    """Преобразует HTTP ссылку в HTTPS для использования в WebApp."""
    if not url:
        return None
    try:
        parsed = urlparse(url)
        if parsed.scheme.lower() == "http" and parsed.netloc:
            # Заменяем http:// на https://
            return url.replace("http://", "https://", 1)
        return url
    except Exception:
        return url


def normalize_web_app_url(url: str) -> str:
    """
    Нормализует URL для использования в Web App кнопках Telegram.
    Telegram требует только HTTPS для Web App URL.
    
    Args:
        url: Исходный URL (может быть с http://, https:// или без протокола)
        
    Returns:
        URL с протоколом https://
    """
    if not url:
        return ""
    
    url = url.strip().rstrip('/')
    
    # Убираем протокол если есть
    if url.startswith('http://'):
        url = url[7:]  # Убираем 'http://'
    elif url.startswith('https://'):
        url = url[8:]  # Убираем 'https://'
    
    # Всегда добавляем HTTPS для Web App
    return f"https://{url}"

def _is_local_address(url: str) -> bool:
    """
    Проверяет, является ли URL локальным адресом (localhost, 127.0.0.1, 0.0.0.0, ::1).
    Telegram не принимает локальные адреса в Web App URL.
    
    Args:
        url: URL для проверки (может быть с протоколом или без)
        
    Returns:
        True если URL содержит локальный адрес, False иначе
    """
    if not url:
        return False
    
    url_lower = url.lower().strip()
    
    # Проверяем различные варианты локальных адресов
    local_patterns = [
        'localhost',
        '127.0.0.1',
        '0.0.0.0',
        '::1',  # IPv6 localhost
    ]
    
    # Убираем протокол для проверки
    url_without_protocol = url_lower
    if url_without_protocol.startswith('http://'):
        url_without_protocol = url_without_protocol[7:]
    elif url_without_protocol.startswith('https://'):
        url_without_protocol = url_without_protocol[8:]
    
    # Проверяем наличие локальных адресов
    for pattern in local_patterns:
        if pattern in url_without_protocol:
            return True
    
    return False

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

def create_profile_menu_keyboard(total_keys_count: int | None = None, trial_used: int = 1, auto_renewal_enabled: bool = True) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    keys_suffix = f" [{total_keys_count}] шт." if isinstance(total_keys_count, int) and total_keys_count >= 0 else ""
    builder.button(text=f"🔑 Мои ключи{keys_suffix}", callback_data="manage_keys")
    
    # Кнопка автопродления с динамическим статусом
    auto_renewal_text = "Автопродление с баланса (вкл🟢)" if auto_renewal_enabled else "Автопродление с баланса (откл🔴)"
    builder.button(text=auto_renewal_text, callback_data="toggle_auto_renewal")
    
    # Кнопка изменения часового пояса
    builder.button(text="🌍 Изменить часовой пояс", callback_data="change_timezone")
    
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
    if has_any_instructions_enabled():
        builder.button(text="🌐 Инструкции❓", callback_data="howto_vless")
    builder.button(text="ℹ️ О проекте", callback_data="show_about")
    builder.button(text="⬅️ Назад в меню", callback_data="back_to_main_menu")
    builder.adjust(1)
    return builder.as_markup()

def create_topup_amounts_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="150 рублей", callback_data="topup_amount_150")
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
    
    # Проверяем, что URL не локальные адреса
    if terms_url and _is_local_address(terms_url):
        terms_url = None
    if privacy_url and _is_local_address(privacy_url):
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
    
    builder.button(text="⬅️ Назад к тарифам", callback_data="back_to_plans")
    builder.adjust(1)
    return builder.as_markup()

def create_ton_connect_keyboard(
    connect_url: str,
    *,
    back_callback: str = "back_to_plans",
    back_text: str = "⬅️ Назад к тарифам",
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="🚀 Открыть кошелек", url=connect_url)
    if back_callback:
        builder.button(text=back_text, callback_data=back_callback)
    builder.adjust(1)
    return builder.as_markup()

def create_payment_keyboard(
    payment_url: str,
    *,
    back_callback: str = "back_to_plans",
    back_text: str = "⬅️ Назад к тарифам",
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Перейти к оплате", url=payment_url)
    if back_callback:
        builder.button(text=back_text, callback_data=back_callback)
    builder.adjust(1)
    return builder.as_markup()

def create_keys_management_keyboard(keys: list, trial_used: int = 1) -> InlineKeyboardMarkup:
    from shop_bot.data_manager.database import get_key_auto_renewal_enabled
    
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
            
            # Формируем номер
            key_number = i + 1
            
            # Получаем статус автопродления
            auto_renewal_status = get_key_auto_renewal_enabled(key['key_id'])
            auto_renewal_icon = "🟢" if auto_renewal_status else "🔴"
            
            # Получаем флаг хоста
            host_name = key.get('host_name', '')
            # Берём первые 2 символа для флага (флаги стран состоят из 2 региональных индикаторов)
            # Если меньше 2 символов - используем fallback, так как один символ не является полноценным флагом
            if len(host_name) >= 2:
                host_flag = host_name[:2]
            else:
                host_flag = '🌐'
            
            # Определяем название тарифа или TRIAL
            plan_name = key.get('plan_name', '')
            is_trial = key.get('is_trial') == 1
            
            if is_trial:
                tariff_display = "TRIAL"
            elif plan_name:
                tariff_display = plan_name
            else:
                tariff_display = ""
            
            # Форматируем цену
            price = key.get('price')
            if price is not None:
                if price == int(price):
                    price_display = f"{int(price)}₽"
                else:
                    price_display = f"{price:.2f}₽"
            else:
                price_display = ""
            
            # Формируем дату в формате DD.MM.YY (год из двух символов)
            expiry_date_str = expiry_date.strftime('%d.%m.%y')
            
            # Формируем компоненты строки
            parts = [
                f"{status_icon} #{key_number}",
                host_flag,
                tariff_display,
                price_display,
                f"до {expiry_date_str}",
                auto_renewal_icon
            ]
            
            # Убираем пустые компоненты и собираем через разделитель |
            button_text = " | ".join(part for part in parts if part)
            builder.button(text=button_text, callback_data=f"show_key_{key['key_id']}")
    
    # Добавляем пробный период только если он не использован
    if trial_used == 0:
        builder.button(text="🆓 Пробный период", callback_data="trial_period")
    
    builder.button(text="➕ Купить новый ключ", callback_data="buy_new_key")
    builder.button(text="⬅️ Назад", callback_data="show_profile")
    builder.adjust(1)
    return builder.as_markup()

def create_key_info_keyboard(key_id: int, subscription_link: str | None = None, key_auto_renewal_enabled: bool | None = None) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    subscription_button_added = False
    cabinet_button_added = False
    key_data = None

    try:
        from shop_bot.data_manager.database import get_key_by_id, get_key_auto_renewal_enabled, get_plans_for_host, get_or_create_permanent_token
        from shop_bot.config import get_user_cabinet_domain
        key_data = get_key_by_id(key_id)
        # Если статус автопродления не передан, получаем его из БД
        if key_auto_renewal_enabled is None:
            key_auto_renewal_enabled = get_key_auto_renewal_enabled(key_id)
    except Exception as e:
        logger.warning(f"Failed to get key data for key {key_id}: {e}")
        # Если не удалось получить статус, используем значение по умолчанию
        if key_auto_renewal_enabled is None:
            key_auto_renewal_enabled = True

    # Извлекаем ссылку на подписку из БД, если она не передана
    if not subscription_link and key_data:
        subscription_link = key_data.get('subscription_link')

    # Определяем provision_mode для проверки необходимости показа кнопки "Личный кабинет"
    provision_mode = 'key'  # по умолчанию
    if key_data:
        plan_name = key_data.get('plan_name')
        if plan_name:
            # Получаем тариф по имени и хосту
            host_name = key_data.get('host_name')
            try:
                plans = get_plans_for_host(host_name)
                plan = next((p for p in plans if p.get('plan_name') == plan_name), None)
                if plan:
                    provision_mode = plan.get('key_provision_mode', 'key')
            except Exception as e:
                logger.warning(f"Failed to get provision_mode for key {key_id}: {e}")

    # Кнопка "Личный кабинет" (только для production и режимов cabinet/cabinet_subscription)
    try:
        is_prod = is_production_server()
        if (is_prod and 
            provision_mode in ('cabinet', 'cabinet_subscription') and 
            key_data):
            try:
                user_id = key_data.get('user_id')
                cabinet_domain = get_user_cabinet_domain()
                
                if cabinet_domain and user_id and not _is_local_address(cabinet_domain):
                    # Получаем или создаем токен для доступа к личному кабинету
                    cabinet_token = get_or_create_permanent_token(user_id, key_id)
                    
                    if cabinet_token:
                        cabinet_url = f"{cabinet_domain}/auth/{cabinet_token}"
                    else:
                        cabinet_url = f"{cabinet_domain}/"
                    
                    # Дополнительная проверка после формирования URL
                    if not _is_local_address(cabinet_url) and _is_https_url(cabinet_url):
                        builder.button(
                            text="🗂️ Личный кабинет",
                            url=cabinet_url  # Обычная ссылка вместо web_app
                        )
                        cabinet_button_added = True
                    else:
                        logger.warning(
                            f"Cabinet URL для ключа {key_id} не является HTTPS или является локальным адресом: {cabinet_url}"
                        )
                elif not cabinet_domain:
                    logger.debug(f"Cabinet domain не настроен для ключа {key_id}")
                elif not user_id:
                    logger.warning(f"User ID не найден для ключа {key_id}")
            except Exception as e:
                logger.warning(f"Failed to create cabinet button for key {key_id}: {e}", exc_info=True)
    except Exception as e:
        logger.error(f"Ошибка при проверке условий для кнопки личного кабинета для ключа {key_id}: {e}", exc_info=True)

    # Кнопка настройки - использует setup_direct_link из БД с fallback на codex_docs_domain + /setup
    setup_url = None
    try:
        # Сначала пробуем получить прямую ссылку
        setup_direct_link = get_setting("setup_direct_link")
        if setup_direct_link and setup_direct_link.strip():
            setup_url = setup_direct_link.strip()
        else:
            # Fallback: используем codex_docs_domain + /setup
            codex_docs_domain = get_setting("codex_docs_domain")
            if codex_docs_domain and codex_docs_domain.strip():
                # Нормализуем домен: убираем trailing slash, добавляем протокол если нужно
                domain = codex_docs_domain.strip().rstrip('/')
                if not domain.startswith(('http://', 'https://')):
                    domain = f'https://{domain}'
                # Добавляем путь /setup к домену
                setup_url = f"{domain}/setup"
            else:
                # Fallback на жестко прописанный URL если настройка не задана (для обратной совместимости)
                setup_url = "https://help.dark-maximus.com/setup"
    except Exception as e:
        logger.warning(f"Failed to get setup_direct_link or codex_docs_domain for setup button: {e}, using fallback")
        setup_url = "https://help.dark-maximus.com/setup"  # fallback для обработки ошибок
    
    if setup_url:
        builder.button(
            text="⚙️ Настройка",
            web_app=WebAppInfo(url=setup_url)
        )

    if subscription_link and _is_http_like_url(subscription_link):
        builder.button(
            text="🔑 Подписка",
            url=subscription_link
        )
        subscription_button_added = True
    elif subscription_link:
        logger.warning(
            "Subscription link %s имеет неподдерживаемый формат; кнопка не будет добавлена.",
            subscription_link
        )

    # Кнопка продления
    builder.button(text="🔁 Продлить этот ключ", callback_data=f"extend_key_{key_id}")
    
    # Кнопка переключения автопродления
    auto_renewal_text = "🔄 Автопродление: 🟢Вкл" if key_auto_renewal_enabled else "🔄 Автопродление: 🔴Выкл"
    builder.button(text=auto_renewal_text, callback_data=f"toggle_key_auto_renewal_{key_id}")

    # Кнопка возврата
    builder.button(text="⬅️ Назад к списку ключей", callback_data="manage_keys")

    # Настройка расположения кнопок
    if cabinet_button_added:
        if subscription_button_added:
            # Личный кабинет, затем Настройка и Подписка в одном ряду, затем остальные
            builder.adjust(1, 2, 1, 1, 1)
        else:
            # Личный кабинет, затем Настройка, затем остальные
            builder.adjust(1, 1, 1, 1, 1)
    else:
        if subscription_button_added:
            # Настройка и Подписка в одном ряду, затем остальные
            builder.adjust(2, 1, 1, 1)
        else:
            # Настройка, затем остальные
            builder.adjust(1, 1, 1, 1)
    return builder.as_markup()

def create_qr_keyboard(key_id: int) -> InlineKeyboardMarkup:
    """Клавиатура для QR-кода ключа"""
    builder = InlineKeyboardBuilder()
    builder.button(text="📑 Скопировать ключ", callback_data=f"copy_key_{key_id}")
    if has_any_instructions_enabled():
        builder.button(text="🌐 Инструкции❓", callback_data=f"howto_vless_{key_id}")
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
    
    # Проверяем, что URL не локальные адреса
    if terms_url and _is_local_address(terms_url):
        terms_url = None
    if privacy_url and _is_local_address(privacy_url):
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


def create_timezone_selection_keyboard(page: int = 0, current_timezone: str = None) -> InlineKeyboardMarkup:
    """
    Создает клавиатуру для выбора часового пояса с пагинацией
    
    Args:
        page: Номер страницы (начиная с 0)
        current_timezone: Текущий часовой пояс пользователя для выделения
        
    Returns:
        InlineKeyboardMarkup с кнопками выбора часового пояса
    """
    from shop_bot.data.timezones import get_timezones_page
    
    builder = InlineKeyboardBuilder()
    
    # Получаем часовые пояса для текущей страницы
    timezones_on_page, total_pages, has_prev, has_next = get_timezones_page(page)
    
    # Добавляем кнопки для каждого часового пояса
    for tz_name, tz_display, tz_offset in timezones_on_page:
        # Добавляем маркер, если это текущий часовой пояс
        button_text = f"✅ {tz_display}" if tz_name == current_timezone else tz_display
        builder.button(text=button_text, callback_data=f"select_tz:{tz_name}")
    
    # Добавляем кнопки навигации
    nav_buttons = []
    if has_prev:
        nav_buttons.append(InlineKeyboardButton(text="⬅️ Назад", callback_data=f"tz_page:{page-1}"))
    
    # Показываем номер страницы
    nav_buttons.append(InlineKeyboardButton(text=f"📄 {page+1}/{total_pages}", callback_data="tz_page_info"))
    
    if has_next:
        nav_buttons.append(InlineKeyboardButton(text="➡️ Вперёд", callback_data=f"tz_page:{page+1}"))
    
    # Добавляем кнопку "Назад в профиль"
    builder.adjust(1)  # Все часовые пояса по одной кнопке в ряд
    
    # Добавляем навигационные кнопки
    markup = builder.as_markup()
    if nav_buttons:
        markup.inline_keyboard.append(nav_buttons)
    
    # Добавляем кнопку возврата
    markup.inline_keyboard.append([InlineKeyboardButton(text="⬅️ Назад в профиль", callback_data="back_to_profile")])
    
    return markup


def create_timezone_confirmation_keyboard(timezone_name: str) -> InlineKeyboardMarkup:
    """
    Создает клавиатуру подтверждения выбора часового пояса
    
    Args:
        timezone_name: Имя выбранного часового пояса
        
    Returns:
        InlineKeyboardMarkup с кнопками подтверждения
    """
    builder = InlineKeyboardBuilder()
    
    builder.button(text="✅ Подтвердить", callback_data=f"confirm_tz:{timezone_name}")
    builder.button(text="❌ Отмена", callback_data="change_timezone")
    
    builder.adjust(2)
    return builder.as_markup()

