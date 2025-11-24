# -*- coding: utf-8 -*-
"""
Конфигурационные настройки для Telegram-бота
"""

import logging
import re
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from html import escape
from typing import Optional

from shop_bot.utils.datetime_utils import ensure_utc_datetime, format_datetime_for_user


CHOOSE_PLAN_MESSAGE = "Выберите подходящий тариф:"
CHOOSE_PAYMENT_METHOD_MESSAGE = "Выберите удобный способ оплаты:"

def get_payment_method_message_with_plan(host_name: str, plan_name: str, price: float, original_price: float | None = None, promo_code: str | None = None) -> str:
    """Генерирует сообщение с информацией о выбранном тарифе для формы оплаты"""
    message = "Вы выбрали:\n\n"
    message += f"✅ Хост: {host_name}\n"
    message += f"✅ Тариф: {plan_name}\n"
    
    if original_price and original_price != price:
        # Если есть скидка, показываем итоговую цену
        message += f"✅ Стоимость: {price:.2f} RUB\n"
        if promo_code:
            message += f"🎫 Промокод '{promo_code}' применен!\n"
    else:
        message += f"✅ Стоимость: {price:.2f} RUB\n"
    
    message += "\n➡️ Теперь выберите удобный способ оплаты:"
    return message


def build_payment_summary_text(
    *,
    description: str,
    final_price: float | Decimal,
    payment_method_label: str,
    currency: str = "RUB",
    original_price: float | Decimal | None = None,
    promo_code: str | None = None,
    discount_amount: float | Decimal | None = None,
) -> str:
    """
    Формирует текст резюме перед оплатой.
    description — что именно выбирает пользователь (пример: "🇫🇮 Финляндия: 💜 F.Friends - Start")
    """

    def _to_decimal(value: float | Decimal) -> Decimal:
        if isinstance(value, Decimal):
            return value
        return Decimal(str(value))

    def _format_amount(value: Decimal) -> str:
        quantized = value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        return format(quantized, ".2f")

    description_safe = escape(description.strip())
    payment_method_safe = escape(payment_method_label.strip())

    final_price_dec = _to_decimal(final_price)
    summary_lines = [f"🧾 <b>Вы выбрали:</b> {description_safe}"]

    price_line: str
    original_price_dec: Optional[Decimal] = None

    if original_price is not None:
        original_price_dec = _to_decimal(original_price)

    if original_price_dec is not None and original_price_dec > final_price_dec:
        price_line = (
            f"💰 <b>Стоимость:</b> {_format_amount(original_price_dec)} {currency} → "
            f"<b>{_format_amount(final_price_dec)} {currency}</b>"
        )
        summary_lines.append(price_line)

        if discount_amount is None:
            discount_amount_dec = original_price_dec - final_price_dec
        else:
            discount_amount_dec = _to_decimal(discount_amount)

        if discount_amount_dec > Decimal("0"):
            discount_value = _format_amount(discount_amount_dec)
            if promo_code:
                summary_lines.append(
                    f"🎫 <b>Промокод:</b> {escape(promo_code)} — скидка {discount_value} {currency}"
                )
            else:
                summary_lines.append(f"🎁 <b>Скидка:</b> {discount_value} {currency}")
    else:
        price_line = f"💰 <b>Стоимость:</b> {_format_amount(final_price_dec)} {currency}"
        summary_lines.append(price_line)
        if promo_code:
            summary_lines.append(f"🎫 <b>Промокод:</b> {escape(promo_code)}")

    summary_lines.append(f"💳 <b>Тип оплаты:</b> {payment_method_safe}")
    return "\n".join(summary_lines)
HOWTO_CHOOSE_OS_MESSAGE = "Выберите операционную систему устройства для получения инструкции по настройке:"
VPN_INACTIVE_TEXT = "❌ <b>Статус VPN:</b> Неактивен (срок истек)"
VPN_NO_DATA_TEXT = "У вас пока нет активных ключей."

# Поддержка видеоинструкций
VIDEO_INSTRUCTIONS_ENABLED = True
VIDEO_INSTRUCTIONS_DIR = "video_instructions"

def get_profile_text(username, balance, total_spent, total_months, vpn_status_text, referral_balance=None, show_referral=False, referral_link=None, referral_percentage=None, auto_renewal_enabled=True, timezone_display=None):
    text = (
        f"👤 <b>Профиль:</b> {username}\n"
        f"💰 <b>Баланс:</b> {balance:.2f} RUB\n"
        f"🔄 <b>Автопродление с баланса:</b> {'Включено 🟢' if auto_renewal_enabled else 'Отключено 🔴'}\n"
    )
    
    # Добавляем часовой пояс, если передан
    if timezone_display:
        text += f"🌍 <b>Часовой пояс:</b> {timezone_display}\n"
    
    text += (
        f"\n💸 <b>Потрачено всего:</b> {total_spent:.2f} RUB\n"
        f"📅 <b>Приобретено месяцев:</b> {total_months}\n"
        f"ℹ️ <b>Статус VPN:</b> {vpn_status_text}\n"
    )
    
    # Добавляем реферальную информацию, если реферальная система включена
    if show_referral and referral_balance is not None:
        text += f"\n💸<b>Реферальный баланс:</b> {referral_balance:.2f} RUB"
        if referral_link:
            text += f"\n🔗<b>Реферальная ссылка:</b> <code>{referral_link}</code>"
        if referral_percentage is not None:
            text += f"\n<i>🗣 Расскажите о нас друзьям и получайте {referral_percentage}% от их расходов!</i>"
    
    return text

def get_vpn_active_text(days_left, hours_left):
    return (
        f"✅ <b>Статус VPN:</b> Активен\n"
        f"⏳ <b>Осталось:</b> {days_left} д. {hours_left} ч."
    )

def get_status_icon_and_text(status: str) -> tuple[str, str]:
    """Возвращает иконку и русское название статуса ключа"""
    status_mapping = {
        'trial-active': ('✅', 'Пробный активный'),
        'trial-ended': ('❌', 'Пробный закончился'),
        'pay-active': ('✅', 'Платный активный'),
        'pay-ended': ('❌', 'Платный закончился'),
        'deactivate': ('❌', 'Деактивирован')
    }
    
    icon, text = status_mapping.get(status, ('❓', 'Неизвестный статус'))
    return icon, text

def format_tariff_info(
    host_name: str | None = None,
    plan_name: str | None = None,
    price: float | None = None,
    is_trial: bool = False,
    status: str | None = None,
    expiry_date = None,
) -> dict[str, str]:
    """
    Формирует переменные для информации о тарифе в шаблонах
    
    Args:
        host_name: название хоста (первые 2 символа используются как флаг)
        plan_name: название тарифа
        price: цена тарифа
        is_trial: является ли ключ пробным
        status: статус ключа
        expiry_date: дата истечения (для определения истёкших ключей)
    
    Returns:
        Словарь с переменными:
        - status_icon: ✅ или ❌
        - host_flag: флаг страны или 🌐
        - tariff_name: TRIAL или plan_name
        - price_formatted: цена в формате X₽ или 0₽
        - tariff_info: готовая строка {status_icon} {host_flag} | {tariff_name} | {price_formatted}
    """
    # Определяем статус иконку
    if expiry_date:
        expiry_dt = expiry_date if isinstance(expiry_date, datetime) else datetime.fromisoformat(str(expiry_date))
        expiry_dt_aware = expiry_dt if expiry_dt.tzinfo else expiry_dt.replace(tzinfo=timezone.utc)
        current_time = datetime.now(timezone.utc)
        is_expired = expiry_dt_aware <= current_time
        
        if is_expired:
            status_icon = "❌"
        elif status and status in ['deactivate']:
            status_icon = "❌"
        else:
            status_icon = "✅"
    elif status and status in ['deactivate']:
        status_icon = "❌"
    else:
        status_icon = "✅"
    
    # Получаем флаг хоста
    if host_name and len(host_name) >= 2:
        host_flag = host_name[:2]
    else:
        host_flag = '🌐'
    
    # Определяем название тарифа
    if is_trial:
        tariff_name = "TRIAL"
    elif plan_name:
        tariff_name = plan_name
    else:
        tariff_name = ""
    
    # Форматируем цену
    if is_trial:
        price_formatted = "0₽"
    elif price is not None:
        if price == int(price):
            price_formatted = f"{int(price)}₽"
        else:
            price_formatted = f"{price:.2f}₽"
    else:
        price_formatted = ""
    
    # Формируем готовую строку
    parts = [status_icon, host_flag, tariff_name, price_formatted]
    tariff_info = " | ".join(part for part in parts if part)
    
    return {
        'status_icon': status_icon,
        'host_flag': host_flag,
        'tariff_name': tariff_name,
        'price_formatted': price_formatted,
        'tariff_info': tariff_info,
    }

def get_key_info_text(
    key_number,
    expiry_date,
    created_date,
    connection_string,
    status: str | None = None,
    subscription_link: str = None,
    provision_mode: str = 'key',
    *,
    user_id: int | None = None,
    key_id: int | None = None,
    user_timezone: str | None = None,
    feature_enabled: bool = False,
    is_trial: bool = False,
    host_name: str | None = None,
    plan_name: str | None = None,
    price: float | None = None,
    key_auto_renewal_enabled: bool | None = None,
):
    """
    Формирует текст информации о ключе
    
    Args:
        key_number: номер ключа
        expiry_date: дата истечения (в UTC)
        created_date: дата создания (в UTC)
        connection_string: VLESS ключ (опционально)
        status: статус ключа
        subscription_link: ссылка на подписку (опционально)
        provision_mode: режим предоставления ('key', 'subscription', 'both', 'cabinet', 'cabinet_subscription')
        user_id: ID пользователя (для генерации токена личного кабинета)
        key_id: ID ключа (для генерации токена личного кабинета)
        is_trial: является ли ключ пробным
    """
    expiry_dt = expiry_date if isinstance(expiry_date, datetime) else datetime.fromisoformat(str(expiry_date))
    created_dt = created_date if isinstance(created_date, datetime) else datetime.fromisoformat(str(created_date))

    expiry_dt_aware = expiry_dt if expiry_dt.tzinfo else expiry_dt.replace(tzinfo=timezone.utc)
    created_dt_aware = created_dt if created_dt.tzinfo else created_dt.replace(tzinfo=timezone.utc)

    expiry_utc = ensure_utc_datetime(expiry_dt_aware)
    created_utc = ensure_utc_datetime(created_dt_aware)

    expiry_formatted = format_datetime_for_user(expiry_utc, user_timezone=user_timezone, feature_enabled=feature_enabled)
    created_formatted = format_datetime_for_user(created_utc, user_timezone=user_timezone, feature_enabled=feature_enabled)
    
    # Определяем иконку и текст статуса на основе реального времени истечения
    current_time = datetime.now(timezone.utc)
    is_expired = expiry_dt_aware <= current_time
    
    if is_expired:
        status_icon, status_text = "❌", "Истёк"
    elif status and status in ['deactivate']:
        status_icon, status_text = "❌", "Деактивирован"
    elif status:
        # Для активных ключей используем статус из БД, но проверяем время
        status_icon, status_text = get_status_icon_and_text(status)
    else:
        status_icon, status_text = "❓", "Статус неизвестен"
    
    trial_suffix = " (Пробный)" if is_trial else ""
    
    # Формируем информацию о тарифе
    tariff_vars = format_tariff_info(
        host_name=host_name,
        plan_name=plan_name,
        price=price,
        is_trial=is_trial,
        status=status,
        expiry_date=expiry_date,
    )
    
    # Определяем template_key на основе provision_mode
    template_key_mapping = {
        'key': 'key_info_key',
        'subscription': 'key_info_subscription',
        'both': 'key_info_both',
        'cabinet': 'key_info_cabinet',
        'cabinet_subscription': 'key_info_cabinet_subscription',
    }
    template_key = template_key_mapping.get(provision_mode, 'key_info_key')
    
    # Формируем информацию об автопродлении
    auto_renewal_status = "Включено 🟢" if (key_auto_renewal_enabled if key_auto_renewal_enabled is not None else True) else "Отключено 🔴"
    
    # Формируем base_text для fallback
    base_text = (
        f"<b>🔑 Информация о ключе #{key_number}{trial_suffix}</b>\n\n"
        f"<b>➕ Приобретён:</b> {created_formatted}\n"
        f"<b>⏳ Действителен до:</b> {expiry_formatted}\n"
        f"<b>{status_icon} Статус:</b> {status_text}\n"
        f"<b>🔄 Автопродление:</b> {auto_renewal_status}\n\n"
    )
    
    # Получаем токен для личного кабинета, если user_id и key_id переданы
    cabinet_token = None
    if user_id and key_id:
        try:
            from shop_bot.data_manager.database import get_or_create_permanent_token
            cabinet_token = get_or_create_permanent_token(user_id, key_id)
            if cabinet_token:
                logging.info(f"[get_key_info_text] Generated cabinet token for user {user_id}, key {key_id}: {cabinet_token[:20]}...")
            else:
                logging.error(f"[get_key_info_text] Token creation returned None for user {user_id}, key {key_id}")
        except Exception as e:
            logging.error(f"[get_key_info_text] Failed to get/create permanent token for user {user_id}, key {key_id}: {e}", exc_info=True)
            cabinet_token = None
    else:
        logging.warning(f"[get_key_info_text] Missing user_id or key_id for cabinet token: user_id={user_id} (type: {type(user_id)}), key_id={key_id} (type: {type(key_id)})")
    
    # Получаем cabinet_url для шаблонов
    cabinet_domain = get_user_cabinet_domain()
    cabinet_url = None
    if cabinet_domain:
        cabinet_is_https = cabinet_domain.lower().startswith("https://")
        if cabinet_token:
            cabinet_url = f"{cabinet_domain}/auth/{cabinet_token}"
        else:
            cabinet_url = f"{cabinet_domain}/"
        if not cabinet_is_https:
            logging.warning("[get_key_info_text] Cabinet domain %s is not HTTPS; Telegram buttons will be disabled.", cabinet_domain)
    
    # Формируем fallback текст (текущая логика)
    fallback_text = ""
    
    # Обработка режимов с личным кабинетом
    if provision_mode == 'cabinet':
        if cabinet_domain and cabinet_url:
            content_text = (
                f"⬇️ <b>ВАШ ЛИЧНЫЙ КАБИНЕТ</b> ⬇️\n------------------------------------------------------------------------\n"
                f"<a href=\"{cabinet_url}\">{cabinet_url}</a>\n------------------------------------------------------------------------\n\n"
                f"<blockquote>⁉️ Чтобы настроить VPN, перейдите по ссылке или нажмите на кнопку [⚙️ Настройка]</blockquote>"
            )
            fallback_text = base_text + content_text
        else:
            fallback_text = base_text

    elif provision_mode == 'cabinet_subscription' and subscription_link:
        if cabinet_domain and cabinet_url:
            content_text = (
                f"⬇️ <b>ВАШ ЛИЧНЫЙ КАБИНЕТ</b> ⬇️\n------------------------------------------------------------------------\n"
                f"<a href=\"{cabinet_url}\">{cabinet_url}</a>\n------------------------------------------------------------------------\n\n"
                f"<blockquote>⁉️ Чтобы настроить VPN, перейдите по ссылке или нажмите на кнопку [⚙️ Настройка]</blockquote>"
            )
            fallback_text = base_text + content_text
        else:
            fallback_text = base_text
    
    # Формируем текст в зависимости от режима
    elif provision_mode == 'subscription' and subscription_link:
        # Только подписка
        content_text = (
            f"⬇️ <b>ВАША ПОДПИСКА</b> ⬇️\n------------------------------------------------------------------------\n"
            f"{subscription_link}\n------------------------------------------------------------------------\n"
            f"<blockquote>⁉️ Чтобы настроить VPN, перейдите по ссылке или нажмите на кнопку [⚙️ Настройка]</blockquote>"
        )
        fallback_text = base_text + content_text
    elif provision_mode == 'both' and connection_string and subscription_link:
        # Ключ + подписка
        content_text = (
            f"⬇️ <b>НИЖЕ ВАШ КЛЮЧ</b> ⬇️\n------------------------------------------------------------------------\n"
            f"<code>{connection_string}</code>\n------------------------------------------------------------------------\n"
            f"💡<i>Просто нажмите на ключ один раз, чтобы скопировать</i>\n\n"
            f"⬇️ <b>ВАША ПОДПИСКА</b> ⬇️\n------------------------------------------------------------------------\n"
            f"{subscription_link}\n------------------------------------------------------------------------\n"
            f"<blockquote>⁉️ Чтобы настроить VPN, перейдите по ссылке или нажмите на кнопку [⚙️ Настройка]</blockquote>"
        )
        fallback_text = base_text + content_text
    else:
        # Только ключ (по умолчанию)
        content_text = (
            f"⬇️ <b>НИЖЕ ВАШ КЛЮЧ</b> ⬇️\n------------------------------------------------------------------------\n"
            f"<code>{connection_string}</code>\n------------------------------------------------------------------------\n"
            f"<blockquote>⁉️ Чтобы настроить VPN, перейдите по ссылке или нажмите на кнопку [⚙️ Настройка]</blockquote>"
        )
        fallback_text = base_text + content_text
    
    # Подготавливаем переменные для подстановки в шаблон
    template_variables = {
        'key_number': str(key_number),
        'trial_suffix': trial_suffix,
        'created_formatted': created_formatted,
        'expiry_formatted': expiry_formatted,
        'status_icon': status_icon,
        'status_text': status_text,
        'connection_string': connection_string or '',
        'subscription_link': subscription_link or '',
        'cabinet_url': cabinet_url or '',
        **tariff_vars,  # Добавляем переменные о тарифе
    }
    
    # Пытаемся получить шаблон из справочника
    try:
        template_result = get_message_text(
            template_key=template_key,
            variables=template_variables,
            fallback_text=fallback_text,
            provision_mode=provision_mode
        )
        
        # Если шаблон найден и активен, возвращаем его
        if template_result != fallback_text:
            logging.info(f"[get_key_info_text] Using template from database: {template_key} for provision_mode={provision_mode}")
            return template_result
        else:
            logging.debug(f"[get_key_info_text] Template {template_key} not found or inactive, using fallback")
    except Exception as e:
        logging.warning(f"[get_key_info_text] Failed to get template {template_key}: {e}, using fallback")
    
    # Возвращаем fallback текст (текущая логика)
    return fallback_text

def get_purchase_success_text(
    action: str,
    key_number: int,
    expiry_date,
    connection_string: str = None,
    subscription_link: str = None,
    provision_mode: str = 'key',
    *,
    user_id: int | None = None,
    key_id: int | None = None,
    user_timezone: str | None = None,
    feature_enabled: bool = False,
    is_trial: bool = False,
    host_name: str | None = None,
    plan_name: str | None = None,
    price: float | None = None,
    status: str | None = None,
):
    """
    Формирует сообщение об успешной покупке/обновлении ключа
    
    Args:
        action: тип действия ("extend" или другое значение для нового ключа)
        key_number: номер ключа
        expiry_date: дата истечения (в UTC)
        connection_string: VLESS ключ (опционально)
        subscription_link: ссылка на подписку (опционально)
        provision_mode: режим предоставления ('key', 'subscription', 'both', 'cabinet', 'cabinet_subscription')
        user_id: ID пользователя (для генерации токена личного кабинета)
        key_id: ID ключа (для генерации токена личного кабинета)
        is_trial: является ли ключ пробным
    """
    action_normalized = (str(action or "").strip().lower())
    if action_normalized in {"extend", "продлен", "продлён"}:
        action_text = "продлен"
    elif action_normalized in {"new", "создан"}:
        action_text = "готов"
    else:
        action_text = "готов"
    expiry_dt = expiry_date if isinstance(expiry_date, datetime) else datetime.fromisoformat(str(expiry_date))
    expiry_utc = ensure_utc_datetime(expiry_dt if expiry_dt.tzinfo else expiry_dt.replace(tzinfo=timezone.utc))
    expiry_formatted = format_datetime_for_user(expiry_utc, user_timezone=user_timezone, feature_enabled=feature_enabled)

    trial_suffix = " (Пробный)" if is_trial else ""
    base_text = (
        f"🎉 <b>Ваш ключ #{key_number}{trial_suffix} {action_text}!</b>\n\n"
        f"⏳ <b>Он будет действовать до:</b> {expiry_formatted}\n\n"
    )

    # Получаем токен для личного кабинета, если user_id и key_id переданы
    cabinet_token = None
    if user_id and key_id:
        try:
            from shop_bot.data_manager.database import get_or_create_permanent_token
            cabinet_token = get_or_create_permanent_token(user_id, key_id)
            if cabinet_token:
                logging.info(f"[get_purchase_success_text] Generated cabinet token for user {user_id}, key {key_id}: {cabinet_token[:20]}...")
            else:
                logging.error(f"[get_purchase_success_text] Token creation returned None for user {user_id}, key {key_id}")
        except Exception as e:
            logging.error(f"[get_purchase_success_text] Failed to get/create permanent token for user {user_id}, key {key_id}: {e}", exc_info=True)
            cabinet_token = None
    else:
        logging.warning(f"[get_purchase_success_text] Missing user_id or key_id for cabinet token: user_id={user_id} (type: {type(user_id)}), key_id={key_id} (type: {type(key_id)})")

    # Подготовка данных для личного кабинета
    cabinet_domain = get_user_cabinet_domain()
    cabinet_url = None
    cabinet_link_markup = ""
    cabinet_text = ""  # Отключено: больше не показываем личный кабинет в сообщениях
    
    # Формируем cabinet_url для использования в шаблонах (если нужно)
    if cabinet_domain:
        cabinet_is_https = cabinet_domain.lower().startswith("https://")
        if cabinet_token:
            cabinet_url = f"{cabinet_domain}/auth/{cabinet_token}"
        else:
            cabinet_url = f"{cabinet_domain}/"
        if not cabinet_is_https:
            logging.warning("[get_purchase_success_text] Cabinet domain %s is not HTTPS; Telegram buttons will be disabled.", cabinet_domain)
        cabinet_link_markup = f'<a href="{cabinet_url}">{cabinet_url}</a>'

    # Определяем template_key на основе provision_mode
    template_key_mapping = {
        'key': 'purchase_success_key',
        'subscription': 'purchase_success_subscription',
        'both': 'purchase_success_both',
        'cabinet': 'purchase_success_cabinet',
        'cabinet_subscription': 'purchase_success_cabinet_subscription',
    }
    template_key = template_key_mapping.get(provision_mode, 'purchase_success_key')

    # Формируем информацию о тарифе
    tariff_vars = format_tariff_info(
        host_name=host_name,
        plan_name=plan_name,
        price=price,
        is_trial=is_trial,
        status=status,
        expiry_date=expiry_date,
    )
    
    # Формируем fallback текст (синхронизировано с шаблонами из справочника)
    fallback_text = ""
    
    # Обработка режимов с личным кабинетом
    if provision_mode == 'cabinet':
        if cabinet_domain and cabinet_url:
            # Точный текст из справочника для режима cabinet
            fallback_text = (
                f"🎉 <b>Ваш ключ #{key_number}{trial_suffix} {action_text}!</b>\n\n"
                f"⏳ <b>Он будет действовать до:</b> {expiry_formatted}\n\n"
                f"⬇️ <b>ВАШ ЛИЧНЫЙ КАБИНЕТ</b> ⬇️\n------------------------------------------------------------------------\n"
                f"<a href=\"{cabinet_url}\">{cabinet_url}</a>\n------------------------------------------------------------------------\n"
                f"<blockquote>⁉️ Чтобы настроить VPN, перейдите по ссылке или нажмите на кнопку [⚙️ Настройка]</blockquote>"
            )
        else:
            fallback_text = base_text

    elif provision_mode == 'cabinet_subscription' and subscription_link:
        if cabinet_domain and cabinet_url:
            # Точный текст из справочника для режима cabinet_subscription
            fallback_text = (
                f"🎉 <b>Ваш ключ #{key_number}{trial_suffix} {action_text}!</b>\n\n"
                f"⏳ <b>Он будет действовать до:</b> {expiry_formatted}\n\n"
                f"⬇️ <b>ВАШ ЛИЧНЫЙ КАБИНЕТ</b> ⬇️\n------------------------------------------------------------------------\n"
                f"<a href=\"{cabinet_url}\">{cabinet_url}</a>\n------------------------------------------------------------------------\n"
                f"<blockquote>⁉️ Чтобы настроить VPN, перейдите по ссылке или нажмите на кнопку [⚙️ Настройка]</blockquote>"
            )
        else:
            fallback_text = base_text

    # Формируем текст в зависимости от режима
    elif provision_mode == 'subscription' and subscription_link:
        # Точный текст из справочника для режима subscription
        fallback_text = (
            f"🎉 <b>Ваш ключ #{key_number}{trial_suffix} {action_text}!</b>\n\n"
            f"⏳ <b>Он будет действовать до:</b> {expiry_formatted}\n\n"
            f"⬇️ <b>ВАША ПОДПИСКА</b> ⬇️\n------------------------------------------------------------------------\n"
            f"{subscription_link}\n------------------------------------------------------------------------\n"
            f"<blockquote>⁉️ Чтобы настроить VPN, перейдите по ссылке или нажмите на кнопку [⚙️ Настройка]</blockquote>"
        )

    elif provision_mode == 'both' and connection_string and subscription_link:
        # Точный текст из справочника для режима both
        fallback_text = (
            f"🎉 <b>Ваш ключ #{key_number}{trial_suffix} {action_text}!</b>\n\n"
            f"⏳ <b>Он будет действовать до:</b> {expiry_formatted}\n\n"
            f"⬇️ <b>НИЖЕ ВАШ КЛЮЧ</b> ⬇️\n------------------------------------------------------------------------\n"
            f"<code>{connection_string}</code>\n------------------------------------------------------------------------\n\n"
            f"⬇️ <b>ВАША ПОДПИСКА</b> ⬇️\n------------------------------------------------------------------------\n"
            f"{subscription_link}\n------------------------------------------------------------------------\n"
            f"<blockquote>⁉️ Чтобы настроить VPN, перейдите по ссылке или нажмите на кнопку [⚙️ Настройка]</blockquote>"
        )

    else:
        # Точный текст из справочника для режима key (по умолчанию)
        fallback_text = (
            f"🎉 <b>Ваш ключ #{key_number}{trial_suffix} {action_text}!</b>\n\n"
            f"⏳ <b>Он будет действовать до:</b> {expiry_formatted}\n\n"
            f"⬇️ <b>НИЖЕ ВАШ КЛЮЧ</b> ⬇️\n------------------------------------------------------------------------\n"
            f"<code>{connection_string or ''}</code>\n------------------------------------------------------------------------\n"
            f"<blockquote>⁉️ Чтобы настроить VPN, перейдите по ссылке или нажмите на кнопку [⚙️ Настройка]</blockquote>"
        )

    # Подготавливаем переменные для подстановки в шаблон
    template_variables = {
        'key_number': str(key_number),
        'trial_suffix': trial_suffix,
        'action_text': action_text,
        'expiry_formatted': expiry_formatted,
        'connection_string': connection_string or '',
        'subscription_link': subscription_link or '',
        'cabinet_url': cabinet_url or '',
        'cabinet_text': cabinet_text,
        'fallback_text': '',
        **tariff_vars,  # Добавляем переменные о тарифе
    }

    # Пытаемся получить шаблон из справочника
    try:
        template_result = get_message_text(
            template_key=template_key,
            variables=template_variables,
            fallback_text=fallback_text,
            provision_mode=provision_mode
        )
        
        # Если шаблон найден и активен, возвращаем его
        if template_result != fallback_text:
            logging.info(f"[get_purchase_success_text] Using template from database: {template_key} for provision_mode={provision_mode}, cabinet_text length: {len(cabinet_text)}")
            return template_result
        else:
            logging.debug(f"[get_purchase_success_text] Template {template_key} not found or inactive, using fallback")
    except Exception as e:
        logging.warning(f"[get_purchase_success_text] Failed to get template {template_key}: {e}, using fallback")
    
    # Возвращаем fallback текст (текущая логика)
    return fallback_text

def get_user_cabinet_domain() -> str | None:
    """
    Получить домен личного кабинета из настроек
    
    Returns:
        Домен личного кабинета (нормализованный) или None если не указан
    """
    from shop_bot.data_manager.database import get_setting
    
    domain = get_setting("user_cabinet_domain")
    if not domain or not domain.strip():
        return None
    
    # Нормализация домена
    domain = domain.strip().rstrip('/')
    
    # Определяем исходный протокол
    original_protocol = None
    if domain.lower().startswith("https://"):
        original_protocol = "https://"
        domain = domain[8:]  # Убираем "https://"
    elif domain.lower().startswith("http://"):
        original_protocol = "http://"
        domain = domain[7:]  # Убираем "http://"
    
    # Убираем путь (всё после первого /)
    if "/" in domain:
        domain = domain.split("/")[0]
    
    # Порт сохраняем (не удаляем)
    
    # Восстанавливаем исходный протокол, если он был указан, иначе используем https://
    if original_protocol:
        domain = f'{original_protocol}{domain}'
    else:
        # Если протокол не был указан, добавляем https:// по умолчанию
        domain = f'https://{domain}'
    
    return domain


def get_message_text(template_key: str, variables: dict, fallback_text: str, provision_mode: str = None) -> str:
    """
    Получить текст сообщения из справочника с fallback на код
    
    Args:
        template_key: ключ шаблона (например: 'purchase_success_key')
        variables: словарь переменных для подстановки
        fallback_text: текст по умолчанию если шаблон не найден
        provision_mode: режим предоставления для фильтрации
    
    Returns:
        Отформатированный текст сообщения
    """
    from shop_bot.data_manager.database import get_message_template
    from shop_bot.security.validators import InputValidator
    
    # Пытаемся получить шаблон из БД
    template = get_message_template(template_key, provision_mode)
    
    if template and template.get('is_active') and template.get('template_text'):
        try:
            # Подставляем переменные в шаблон
            text = template['template_text']
            for key, value in variables.items():
                # Экранируем фигурные скобки в значениях
                safe_value = str(value).replace('{', '{{').replace('}', '}}')
                # Заменяем все вхождения переменной в шаблоне
                placeholder = f'{{{key}}}'
                if placeholder in text:
                    text = text.replace(placeholder, safe_value)
                    logging.debug(f"[get_message_text] Replaced {placeholder} with value (length: {len(safe_value)})")
            
            # Заменяем невалидные HTML-теги на поддерживаемые Telegram
            # <br>, <br/>, <br /> -> \n (новая строка)
            text = re.sub(r'<br\s*/?>', '\n', text, flags=re.IGNORECASE)
            
            # Валидация HTML-тегов после подстановки переменных
            is_valid, errors = InputValidator.validate_html_tags(text)
            if not is_valid:
                logging.warning(
                    f"[get_message_text] HTML validation failed for template {template_key}: {errors}. "
                    f"Using fallback text to prevent Telegram API error."
                )
                return fallback_text
            
            logging.debug(f"[get_message_text] Template {template_key} formatted successfully, result length: {len(text)}")
            return text
        except Exception as e:
            logging.warning(f"Failed to format template {template_key}: {e}", exc_info=True)
            return fallback_text
    
    # Fallback на код если шаблон не найден или неактивен
    return fallback_text

def get_video_instruction_path(platform: str) -> str:
    """Возвращает путь к видеоинструкции для платформы"""
    video_mapping = {
        'android': 'android_video.mp4',
        'ios': 'ios_video.mp4', 
        'windows': 'windows_video.mp4',
        'macos': 'macos_video.mp4',
        'linux': 'linux_video.mp4',
    }
    return f"{VIDEO_INSTRUCTIONS_DIR}/{video_mapping.get(platform, 'android_video.mp4')}"

def has_video_instruction(platform: str) -> bool:
    """Проверяет, есть ли видеоинструкция для платформы"""
    if not VIDEO_INSTRUCTIONS_ENABLED:
        return False
    
    from pathlib import Path
    video_path = Path(get_video_instruction_path(platform))
    return video_path.exists()