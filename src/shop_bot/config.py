# -*- coding: utf-8 -*-
"""
Конфигурационные настройки для Telegram-бота
"""

CHOOSE_PLAN_MESSAGE = "Выберите подходящий тариф:"
CHOOSE_PAYMENT_METHOD_MESSAGE = "Выберите удобный способ оплаты:"
HOWTO_CHOOSE_OS_MESSAGE = "Выберите операционную систему устройства для получения инструкции по настройке:"
VPN_INACTIVE_TEXT = "❌ <b>Статус VPN:</b> Неактивен (срок истек)"
VPN_NO_DATA_TEXT = "ℹ️ <b>Статус VPN:</b> У вас пока нет активных ключей."

# Поддержка видеоинструкций
VIDEO_INSTRUCTIONS_ENABLED = True
VIDEO_INSTRUCTIONS_DIR = "video_instructions"

def get_profile_text(username, balance, total_spent, total_months, vpn_status_text):
    return (
        f"👤 <b>Профиль:</b> {username}\n"
        f"💰 <b>Баланс:</b> {balance:.2f} RUB\n\n"
        f"💰 <b>Потрачено всего:</b> {total_spent:.0f} RUB\n"
        f"📅 <b>Приобретено месяцев:</b> {total_months}\n\n"
        f"{vpn_status_text}"
    )

def get_vpn_active_text(days_left, hours_left):
    return (
        f"✅ <b>Статус VPN:</b> Активен\n"
        f"⏳ <b>Осталось:</b> {days_left} д. {hours_left} ч."
    )

def get_key_info_text(key_number, expiry_date, created_date, connection_string):
    expiry_formatted = expiry_date.strftime('%d.%m.%Y в %H:%M')
    created_formatted = created_date.strftime('%d.%m.%Y в %H:%M')
    
    return (
        f"<b>🔑 Информация о ключе #{key_number}</b>\n\n"
        f"<b>➕ Приобретён:</b> {created_formatted}\n"
        f"<b>⏳ Действителен до:</b> {expiry_formatted}\n\n"

        f"                    ⬇️ <b>НИЖЕ ВАШ КЛЮЧ</b> ⬇️\n"
        f"------------------------------------------------------------------------\n"
        f"<code>{connection_string}</code>\n"
        f"------------------------------------------------------------------------\n"
        f"💡<i>Просто нажмите на ключ один раз, чтобы скопировать</i>\n\n"

        f"<blockquote>⁉️ Если возник вопрос: Что делать дальше?</blockquote>\n"
        f"<blockquote>📢 Вам нужно скопировать этот ключ и вставить его в VPN приложение</blockquote>\n"
        f"<blockquote>Чтобы получить инструкцию как это сделать, нажмите на кнопку  [Инструкция как пользоваться]</blockquote>"
    )

def get_purchase_success_text(action: str, key_number: int, expiry_date, connection_string: str):
    action_text = "обновлен" if action == "extend" else "готов"
    expiry_formatted = expiry_date.strftime('%d.%m.%Y в %H:%M')

    return (
        f"🎉 <b>Ваш ключ #{key_number} {action_text}!</b>\n\n"
        f"⏳ <b>Он будет действовать до:</b> {expiry_formatted}\n\n"
        f"                    ⬇️ <b>НИЖЕ ВАШ КЛЮЧ</b> ⬇️\n"
        f"------------------------------------------------------------------------\n"
        f"<code>{connection_string}</code>\n"
        f"------------------------------------------------------------------------\n"
        f"💡<i>Просто нажмите на ключ один раз, чтобы скопировать</i>\n\n"

        f"<blockquote>⁉️ Если возник вопрос: Что делать дальше?</blockquote>\n"
        f"<blockquote>📢 Вам нужно скопировать этот ключ и вставить его в VPN приложение</blockquote>\n"
        f"<blockquote>Чтобы получить инструкцию как это сделать, нажмите на кнопку  [Инструкция как пользоваться]</blockquote>"
    )

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