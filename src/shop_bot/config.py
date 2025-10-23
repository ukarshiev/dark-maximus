# -*- coding: utf-8 -*-
"""
Конфигурационные настройки для Telegram-бота
"""

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
HOWTO_CHOOSE_OS_MESSAGE = "Выберите операционную систему устройства для получения инструкции по настройке:"
VPN_INACTIVE_TEXT = "❌ <b>Статус VPN:</b> Неактивен (срок истек)"
VPN_NO_DATA_TEXT = "У вас пока нет активных ключей."

# Поддержка видеоинструкций
VIDEO_INSTRUCTIONS_ENABLED = True
VIDEO_INSTRUCTIONS_DIR = "video_instructions"

def get_profile_text(username, balance, total_spent, total_months, vpn_status_text, referral_balance=None, show_referral=False, referral_link=None, referral_percentage=None):
    text = (
        f"👤 <b>Профиль:</b> {username}\n"
        f"💰 <b>Баланс:</b> {balance:.2f} RUB\n\n"
        f"💸 <b>Потрачено всего:</b> {total_spent:.2f} RUB\n"
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

def get_key_info_text(key_number, expiry_date, created_date, connection_string, status: str | None = None, subscription_link: str = None, provision_mode: str = 'key'):
    """
    Формирует текст информации о ключе
    
    Args:
        key_number: номер ключа
        expiry_date: дата истечения (в UTC)
        created_date: дата создания (в UTC)
        connection_string: VLESS ключ (опционально)
        status: статус ключа
        subscription_link: ссылка на подписку (опционально)
        provision_mode: режим предоставления ('key', 'subscription', 'both')
    """
    from datetime import datetime, timezone, timedelta
    # Конвертируем время из UTC в UTC+3 (Moscow) для отображения пользователю
    moscow_tz = timezone(timedelta(hours=3))
    
    # Убедимся, что даты в UTC
    if expiry_date.tzinfo is None:
        expiry_date = expiry_date.replace(tzinfo=timezone.utc)
    if created_date.tzinfo is None:
        created_date = created_date.replace(tzinfo=timezone.utc)
    
    # Конвертируем в московское время для отображения
    expiry_moscow = expiry_date.astimezone(moscow_tz)
    created_moscow = created_date.astimezone(moscow_tz)
    
    expiry_formatted = expiry_moscow.strftime('%d.%m.%Y в %H:%M')
    created_formatted = created_moscow.strftime('%d.%m.%Y в %H:%M')
    
    # Определяем иконку и текст статуса на основе реального времени истечения
    current_time = datetime.now(timezone.utc)
    is_expired = expiry_date <= current_time
    
    if is_expired:
        status_icon, status_text = "❌", "Истёк"
    elif status and status in ['deactivate']:
        status_icon, status_text = "❌", "Деактивирован"
    elif status:
        # Для активных ключей используем статус из БД, но проверяем время
        from shop_bot.config import get_status_icon_and_text
        status_icon, status_text = get_status_icon_and_text(status)
    else:
        status_icon, status_text = "❓", "Статус неизвестен"
    
    base_text = (
        f"<b>🔑 Информация о ключе #{key_number}</b>\n\n"
        f"<b>➕ Приобретён:</b> {created_formatted}\n"
        f"<b>⏳ Действителен до:</b> {expiry_formatted}\n"
        f"<b>{status_icon} Статус:</b> {status_text}\n\n"
    )
    
    # Формируем текст в зависимости от режима
    if provision_mode == 'subscription' and subscription_link:
        # Только подписка
        content_text = (
            f"                    ⬇️ <b>ВАША ПОДПИСКА</b> ⬇️\n"
            f"------------------------------------------------------------------------\n"
            f"{subscription_link}\n"
            f"------------------------------------------------------------------------\n"
            f"💡<i>Просто нажмите на ссылку один раз, чтобы перейти на страницу подписки</i>\n\n"
            f"<blockquote>⁉️ Если возник вопрос: Что делать дальше?</blockquote>\n"
            f"<blockquote>📢 Вставьте эту ссылку в VPN приложение как URL подписки</blockquote>\n"
            f"<blockquote>Чтобы получить инструкцию, нажмите на кнопку [🌐 Как настроить VPN❓]</blockquote>"
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
            f"💡<i>Просто нажмите на текст один раз, чтобы перейти на страницу подписки</i>\n\n"
            f"<blockquote>⁉️ Если возник вопрос: Что делать дальше?</blockquote>\n"
            f"<blockquote>📢 Вы можете использовать либо ключ, либо подписку - вставьте один из них в VPN приложение</blockquote>\n"
            f"<blockquote>Чтобы получить инструкцию, нажмите на кнопку [🌐 Как настроить VPN❓]</blockquote>"
        )
    else:
        # Только ключ (по умолчанию)
        content_text = (
            f"                    ⬇️ <b>НИЖЕ ВАШ КЛЮЧ</b> ⬇️\n"
            f"------------------------------------------------------------------------\n"
            f"<code>{connection_string}</code>\n"
            f"------------------------------------------------------------------------\n"
            f"💡<i>Просто нажмите на ключ один раз, чтобы скопировать</i>\n\n"
            f"<blockquote>⁉️ Если возник вопрос: Что делать дальше?</blockquote>\n"
            f"<blockquote>📢 Вам нужно скопировать этот ключ и вставить его в VPN приложение</blockquote>\n"
            f"<blockquote>Чтобы получить инструкцию как это сделать, нажмите на кнопку  [🌐 Как настроить VPN❓]</blockquote>"
        )
    
    return base_text + content_text

def get_purchase_success_text(action: str, key_number: int, expiry_date, connection_string: str = None, subscription_link: str = None, provision_mode: str = 'key'):
    """
    Формирует сообщение об успешной покупке/обновлении ключа
    
    Args:
        action: тип действия ("extend" или другое значение для нового ключа)
        key_number: номер ключа
        expiry_date: дата истечения (в UTC)
        connection_string: VLESS ключ (опционально)
        subscription_link: ссылка на подписку (опционально)
        provision_mode: режим предоставления ('key', 'subscription', 'both')
    """
    from datetime import timezone, timedelta
    action_text = "обновлен" if action == "extend" else "готов"
    
    # Конвертируем время из UTC в UTC+3 (Moscow) для отображения пользователю
    moscow_tz = timezone(timedelta(hours=3))
    if expiry_date.tzinfo is None:
        expiry_date = expiry_date.replace(tzinfo=timezone.utc)
    expiry_moscow = expiry_date.astimezone(moscow_tz)
    expiry_formatted = expiry_moscow.strftime('%d.%m.%Y в %H:%M')

    base_text = (
        f"🎉 <b>Ваш ключ #{key_number} {action_text}!</b>\n\n"
        f"⏳ <b>Он будет действовать до:</b> {expiry_formatted}\n\n"
    )

    # Формируем текст в зависимости от режима
    if provision_mode == 'subscription' and subscription_link:
        # Только подписка
        content_text = (
            f"                    ⬇️ <b>ВАША ПОДПИСКА</b> ⬇️\n"
            f"------------------------------------------------------------------------\n"
            f"{subscription_link}\n"
            f"------------------------------------------------------------------------\n"
            f"💡<i>Просто нажмите на ссылку один раз, чтобы перейти на страницу подписки</i>\n\n"
            f"<blockquote>⁉️ Что делать с подпиской?</blockquote>\n"
            f"<blockquote>📢 Вставьте эту ссылку в VPN приложение как URL подписки</blockquote>\n"
            f"<blockquote>Чтобы получить инструкцию, нажмите на кнопку [🌐 Как настроить VPN❓]</blockquote>"
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
            f"💡<i>Просто нажмите на текст один раз, чтобы перейти на страницу подписки</i>\n\n"
            f"<blockquote>⁉️ Если возник вопрос: Что делать дальше?</blockquote>\n"
            f"<blockquote>📢 Вы можете использовать либо ключ, либо подписку - вставьте один из них в VPN приложение</blockquote>\n"
            f"<blockquote>Чтобы получить инструкцию, нажмите на кнопку [🌐 Как настроить VPN❓]</blockquote>"
        )
    else:
        # Только ключ (по умолчанию)
        content_text = (
            f"                    ⬇️ <b>НИЖЕ ВАШ КЛЮЧ</b> ⬇️\n"
            f"------------------------------------------------------------------------\n"
            f"<code>{connection_string}</code>\n"
            f"------------------------------------------------------------------------\n"
            f"💡<i>Просто нажмите на ключ один раз, чтобы скопировать</i>\n\n"
            f"<blockquote>⁉️ Если возник вопрос: Что делать дальше?</blockquote>\n"
            f"<blockquote>📢 Вам нужно скопировать этот ключ и вставить его в VPN приложение</blockquote>\n"
            f"<blockquote>Чтобы получить инструкцию как это сделать, нажмите на кнопку  [🌐 Как настроить VPN❓]</blockquote>"
        )

    return base_text + content_text

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