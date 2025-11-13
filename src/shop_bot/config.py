# -*- coding: utf-8 -*-
"""
Конфигурационные настройки для Telegram-бота
"""

import logging
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from html import escape
from typing import Optional

from shop_bot.utils.datetime_utils import ensure_utc_datetime, format_datetime_for_user


CHOOSE_PLAN_MESSAGE = "Выберите подходящий тариф:"
CHOOSE_PAYMENT_METHOD_MESSAGE = "Выберите удобный способ оплаты:"

def get_payment_method_message_with_plan(host_name: str, plan_name: str, price: float, original_price: float | None = None, promo_code: str | None = None) -> str:
    """Генерирует сообщение с информацией о выбранном тарифе для формы оплаты"""
    if original_price and original_price != price:
        # Если есть скидка, показываем старую и новую цену с информацией о промокоде
        discount_amount = original_price - price
        message = f"Вы выбрали {host_name}: {plan_name}\n\n"
        if promo_code:
            message += f"🎫 Промокод '{promo_code}' применен!\n"
        message += f"💰 Стоимость тарифа: {original_price:.2f} RUB\n"
        message += f"🎁 Скидка: {discount_amount:.2f} RUB\n"
        message += f"✅ Итоговая цена: {price:.2f} RUB\n\n"
        message += "Теперь выберите удобный способ оплаты:"
        return message
    else:
        return f"Вы выбрали {host_name}: {plan_name} - {price:.2f} RUB\n\nТеперь выберите удобный способ оплаты:"


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
    base_text = (
        f"<b>🔑 Информация о ключе #{key_number}{trial_suffix}</b>\n\n"
        f"<b>➕ Приобретён:</b> {created_formatted}\n"
        f"<b>⏳ Действителен до:</b> {expiry_formatted}\n"
        f"<b>{status_icon} Статус:</b> {status_text}\n\n"
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
    
    # Обработка режимов с личным кабинетом
    if provision_mode == 'cabinet':
        cabinet_domain = get_user_cabinet_domain()
        if cabinet_domain:
            cabinet_is_https = cabinet_domain.lower().startswith("https://")
            if cabinet_token:
                cabinet_url = f"{cabinet_domain}/auth/{cabinet_token}"
                logging.info(f"[get_key_info_text] Using token in cabinet URL for user {user_id}, key {key_id}")
            else:
                cabinet_url = f"{cabinet_domain}/"
                logging.warning(f"[get_key_info_text] No token available, using URL without token for user {user_id}, key {key_id}")
            if not cabinet_is_https:
                logging.warning("[get_key_info_text] Cabinet domain %s is not HTTPS; Telegram buttons will be disabled.", cabinet_domain)
            cabinet_link_markup = f'<a href="{cabinet_url}">{cabinet_url}</a>'
            content_text = (
                f"                    ⬇️ <b>ВАШ ЛИЧНЫЙ КАБИНЕТ</b> ⬇️\n"
                f"------------------------------------------------------------------------\n"
                f"{cabinet_link_markup}\n"
                f"------------------------------------------------------------------------\n\n"
                f"<blockquote>⁉️ Чтобы настроить VPN, перейдите по ссылке или нажмите на кнопку [⚙️ Настройка]</blockquote>\n"
            )
            return base_text + content_text

    elif provision_mode == 'cabinet_subscription' and subscription_link:
        cabinet_domain = get_user_cabinet_domain()
        if cabinet_domain:
            cabinet_is_https = cabinet_domain.lower().startswith("https://")
            if cabinet_token:
                cabinet_url = f"{cabinet_domain}/auth/{cabinet_token}"
                logging.info(f"[get_key_info_text] Using token in cabinet_subscription URL for user {user_id}, key {key_id}")
            else:
                cabinet_url = f"{cabinet_domain}/"
                logging.warning(f"[get_key_info_text] No token available for cabinet_subscription, using URL without token for user {user_id}, key {key_id}")
            if not cabinet_is_https:
                logging.warning("[get_key_info_text] Cabinet domain %s is not HTTPS; Telegram buttons will be disabled.", cabinet_domain)
            cabinet_link_markup = f'<a href="{cabinet_url}">{cabinet_url}</a>'
            content_text = (
                f"                    ⬇️ <b>ВАШ ЛИЧНЫЙ КАБИНЕТ</b> ⬇️\n"
                f"------------------------------------------------------------------------\n"
                f"{cabinet_link_markup}\n"
                f"------------------------------------------------------------------------\n\n"
                f"<blockquote>⁉️ Чтобы настроить VPN, перейдите по ссылке или нажмите на кнопку [⚙️ Настройка]</blockquote>\n"
            )
            return base_text + content_text
    
    # Формируем текст в зависимости от режима
    if provision_mode == 'subscription' and subscription_link:
        # Только подписка
        content_text = (
            f"                    ⬇️ <b>ВАША ПОДПИСКА</b> ⬇️\n"
            f"------------------------------------------------------------------------\n"
            f"{subscription_link}\n"
            f"------------------------------------------------------------------------\n"
            #f"💡<i>Просто нажмите на ссылку один раз, чтобы перейти на страницу подписки</i>\n\n"
            f"<blockquote>⁉️ Чтобы настроить VPN, перейдите по ссылке или нажмите на кнопку [⚙️ Настройка]</blockquote>\n"
            #f"<blockquote>📢 Вставьте эту ссылку в VPN приложение как URL подписки</blockquote>\n"
            #f"<blockquote>Чтобы получить инструкцию, нажмите на кнопку [🌐 Инструкции❓]</blockquote>"
        )
    elif provision_mode == 'both' and connection_string and subscription_link:
        # Ключ + подписка
        content_text = (
            f"                    ⬇️ <b>НИЖЕ ВАШ КЛЮЧ</b> ⬇️\n"
            f"------------------------------------------------------------------------\n"
            f"<code>{connection_string}</code>\n"
            f"------------------------------------------------------------------------\n"
            f"💡<i>Просто нажмите на ключ один раз, чтобы скопировать</i>\n\n"
            f"                    ⬇️ <b>ВАША ПОДПИСКА</b> ⬇️\n"
            f"------------------------------------------------------------------------\n"
            f"{subscription_link}\n"
            f"------------------------------------------------------------------------\n"
            #f"💡<i>Просто нажмите на текст один раз, чтобы перейти на страницу подписки</i>\n\n"
            f"<blockquote>⁉️ Чтобы настроить VPN, перейдите по ссылке или нажмите на кнопку [⚙️ Настройка]</blockquote>\n"
            #f"<blockquote>📢 Вставьте эту ссылку в VPN приложение как URL подписки</blockquote>\n"
            #f"<blockquote>Чтобы получить инструкцию, нажмите на кнопку [🌐 Инструкции❓]</blockquote>"
        )
    else:
        # Только ключ (по умолчанию)
        content_text = (
            f"                    ⬇️ <b>НИЖЕ ВАШ КЛЮЧ</b> ⬇️\n"
            f"------------------------------------------------------------------------\n"
            f"<code>{connection_string}</code>\n"
            f"------------------------------------------------------------------------\n"
            #f"💡<i>Просто нажмите на ключ один раз, чтобы скопировать</i>\n\n"
            f"<blockquote>⁉️ Чтобы настроить VPN, перейдите по ссылке или нажмите на кнопку [⚙️ Настройка]</blockquote>\n"
            #f"<blockquote>📢 Вставьте эту ссылку в VPN приложение как URL подписки</blockquote>\n"
            #f"<blockquote>Чтобы получить инструкцию, нажмите на кнопку [🌐 Инструкции❓]</blockquote>"
        )
    
    # Добавляем ссылку на личный кабинет (только если домен настроен) для существующих режимов
    cabinet_text = ""
    cabinet_domain = get_user_cabinet_domain()
    if cabinet_domain:
        cabinet_is_https = cabinet_domain.lower().startswith("https://")
        if cabinet_token:
            cabinet_url = f"{cabinet_domain}/auth/{cabinet_token}"
        else:
            cabinet_url = f"{cabinet_domain}/"
        if not cabinet_is_https:
            logging.warning("[get_key_info_text] Cabinet domain %s is not HTTPS; Telegram buttons will be disabled.", cabinet_domain)
        cabinet_link_markup = f'<a href="{cabinet_url}">{cabinet_url}</a>'
        cabinet_text = f"\n\n📱 <b>Ваш личный кабинет (рекомендуется):</b>\n{cabinet_link_markup}\n"
    
    return base_text + content_text + cabinet_text

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

    # Обработка режимов с личным кабинетом
    if provision_mode == 'cabinet':
        cabinet_domain = get_user_cabinet_domain()
        if cabinet_domain:
            cabinet_is_https = cabinet_domain.lower().startswith("https://")
            if cabinet_token:
                cabinet_url = f"{cabinet_domain}/auth/{cabinet_token}"
                logging.info(f"[get_purchase_success_text] Using token in cabinet URL for user {user_id}, key {key_id}")
            else:
                cabinet_url = f"{cabinet_domain}/"
                logging.warning(f"[get_purchase_success_text] No token available, using URL without token for user {user_id}, key {key_id}")
            if not cabinet_is_https:
                logging.warning("[get_purchase_success_text] Cabinet domain %s is not HTTPS; Telegram buttons will be disabled.", cabinet_domain)
            cabinet_link_markup = f'<a href="{cabinet_url}">{cabinet_url}</a>'
            content_text = (
                f"                    ⬇️ <b>ВАШ ЛИЧНЫЙ КАБИНЕТ</b> ⬇️\n"
                f"------------------------------------------------------------------------\n"
                f"{cabinet_link_markup}\n"
                f"------------------------------------------------------------------------\n"
                f"<blockquote>⁉️ Чтобы настроить VPN, перейдите по ссылке или нажмите на кнопку [⚙️ Настройка]</blockquote>\n"
            )
            # Не добавляем fallback для режима cabinet
            return base_text + content_text

    elif provision_mode == 'cabinet_subscription' and subscription_link:
        cabinet_domain = get_user_cabinet_domain()
        if cabinet_domain:
            cabinet_is_https = cabinet_domain.lower().startswith("https://")
            if cabinet_token:
                cabinet_url = f"{cabinet_domain}/auth/{cabinet_token}"
                logging.info(f"[get_purchase_success_text] Using token in cabinet_subscription URL for user {user_id}, key {key_id}")
            else:
                cabinet_url = f"{cabinet_domain}/"
                logging.warning(f"[get_purchase_success_text] No token available for cabinet_subscription, using URL without token for user {user_id}, key {key_id}")
            if not cabinet_is_https:
                logging.warning("[get_purchase_success_text] Cabinet domain %s is not HTTPS; Telegram buttons will be disabled.", cabinet_domain)
            cabinet_link_markup = f'<a href="{cabinet_url}">{cabinet_url}</a>'
            content_text = (
                f"                    ⬇️ <b>ВАШ ЛИЧНЫЙ КАБИНЕТ</b> ⬇️\n"
                f"------------------------------------------------------------------------\n"
                f"{cabinet_link_markup}\n"
                f"------------------------------------------------------------------------\n"
                f"<blockquote>⁉️ Чтобы настроить VPN, перейдите по ссылке или нажмите на кнопку [⚙️ Настройка]</blockquote>\n"
            )
            return base_text + content_text

    # Формируем текст в зависимости от режима
    if provision_mode == 'subscription' and subscription_link:
        # Только подписка
        content_text = (
            f"                    ⬇️ <b>ВАША ПОДПИСКА</b> ⬇️\n"
            f"------------------------------------------------------------------------\n"
            f"{subscription_link}\n"
            f"------------------------------------------------------------------------\n"
            #f"💡<i>Просто нажмите на ссылку один раз, чтобы перейти на страницу подписки</i>\n\n"
            f"<blockquote>⁉️ Чтобы настроить VPN, перейдите по ссылке или нажмите на кнопку [⚙️ Настройка]</blockquote>\n"
            #f"<blockquote>📢 Вставьте эту ссылку в VPN приложение как URL подписки</blockquote>\n"
            #f"<blockquote>Чтобы получить инструкцию, нажмите на кнопку [🌐 Инструкции❓]</blockquote>"
        )
    elif provision_mode == 'both' and connection_string and subscription_link:
        # Ключ + подписка
        content_text = (
            f"                    ⬇️ <b>НИЖЕ ВАШ КЛЮЧ</b> ⬇️\n"
            f"------------------------------------------------------------------------\n"
            f"<code>{connection_string}</code>\n"
            f"------------------------------------------------------------------------\n\n"
            f"                    ⬇️ <b>ВАША ПОДПИСКА</b> ⬇️\n"
            f"------------------------------------------------------------------------\n"
            f"{subscription_link}\n"
            f"------------------------------------------------------------------------\n"
            #f"💡<i>Просто нажмите на текст один раз, чтобы перейти на страницу подписки</i>\n\n"
            f"<blockquote>⁉️ Чтобы настроить VPN, перейдите по ссылке или нажмите на кнопку [⚙️ Настройка]</blockquote>\n"
            #f"<blockquote>📢 Вставьте эту ссылку в VPN приложение как URL подписки</blockquote>\n"
            #f"<blockquote>Чтобы получить инструкцию, нажмите на кнопку [🌐 Инструкции❓]</blockquote>"
        )
    else:
        # Только ключ (по умолчанию)
        content_text = (
            f"                    ⬇️ <b>НИЖЕ ВАШ КЛЮЧ</b> ⬇️\n"
            f"------------------------------------------------------------------------\n"
            f"<code>{connection_string}</code>\n"
            f"------------------------------------------------------------------------\n"
            #f"💡<i>Просто нажмите на ключ один раз, чтобы скопировать</i>\n\n"
            f"<blockquote>⁉️ Чтобы настроить VPN, перейдите по ссылке или нажмите на кнопку [⚙️ Настройка]</blockquote>\n"
            #f"<blockquote>📢 Вставьте эту ссылку в VPN приложение как URL подписки</blockquote>\n"
            #f"<blockquote>Чтобы получить инструкцию, нажмите на кнопку [🌐 Инструкции❓]</blockquote>"
        )
    
    # Добавляем ссылку на личный кабинет (только если домен настроен) для существующих режимов
    cabinet_text = ""
    cabinet_domain = get_user_cabinet_domain()
    if cabinet_domain:
        cabinet_is_https = cabinet_domain.lower().startswith("https://")
        if cabinet_token:
            cabinet_url = f"{cabinet_domain}/auth/{cabinet_token}"
        else:
            cabinet_url = f"{cabinet_domain}/"
        if not cabinet_is_https:
            logging.warning("[get_purchase_success_text] Cabinet domain %s is not HTTPS; Telegram buttons will be disabled.", cabinet_domain)
        cabinet_link_markup = f'<a href="{cabinet_url}">{cabinet_url}</a>'
        cabinet_text = f"\n\n📱 <b>Ваш личный кабинет (рекомендуется):</b>\n{cabinet_link_markup}\n"
    
    return base_text + content_text + cabinet_text

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
    
    # Добавляем протокол если отсутствует
    if not domain.startswith(('http://', 'https://')):
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
    
    # Пытаемся получить шаблон из БД
    template = get_message_template(template_key, provision_mode)
    
    if template and template.get('is_active') and template.get('template_text'):
        try:
            # Подставляем переменные в шаблон
            text = template['template_text']
            for key, value in variables.items():
                # Экранируем фигурные скобки в значениях
                safe_value = str(value).replace('{', '{{').replace('}', '}}')
                text = text.replace(f'{{{key}}}', safe_value)
            return text
        except Exception as e:
            logging.warning(f"Failed to format template {template_key}: {e}")
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