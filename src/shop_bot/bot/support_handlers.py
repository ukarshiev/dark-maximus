# -*- coding: utf-8 -*-
"""
Обработчики для бота поддержки
"""

import logging
import json

from aiogram import Bot, Router, F, types
from aiogram.filters import CommandStart, Command
from aiogram.enums import ParseMode
from aiogram.types import ErrorEvent
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from shop_bot.data_manager import database
from shop_bot.bot.handlers import process_successful_onboarding

logger = logging.getLogger(__name__)

router = Router()

# Состояния для онбординга
class Onboarding(StatesGroup):
    waiting_for_terms_agreement = State()
    waiting_for_subscription = State()

async def show_terms_agreement_screen(message: types.Message, state: FSMContext):
    """Показывает экран согласия с документами"""
    from shop_bot.data_manager.database import get_global_domain
    domain = get_global_domain()
    
    terms_url = None
    privacy_url = None
    if domain and not domain.startswith("http://localhost") and not domain.startswith("https://localhost"):
        terms_url = f"{domain.rstrip('/')}/terms"
        privacy_url = f"{domain.rstrip('/')}/privacy"
    
    if not terms_url or not privacy_url:
        # Если документы не настроены, переходим к проверке подписки
        await show_subscription_screen(message, state)
        return
    
    text = (
        "<b>🎉 Добро пожаловать!</b>\n\n"
        "Ознакомьтесь с документами ниже и примите их:\n\n"
        "• Условия использования\n"
        "• Политика конфиденциальности\n\n"
        "После ознакомления нажмите кнопку согласия."
    )
    
    # Создаем клавиатуру с кнопками
    builder = InlineKeyboardBuilder()
    if terms_url:
        builder.button(text="📄 Условия использования", web_app={"url": terms_url})
    if privacy_url:
        builder.button(text="🔒 Политика конфиденциальности", web_app={"url": privacy_url})
    builder.button(text="✅ Я согласен с документами", callback_data="agree_to_terms")
    builder.adjust(1)
    
    await message.answer(text, reply_markup=builder.as_markup())
    await state.set_state(Onboarding.waiting_for_terms_agreement)

async def show_subscription_screen(message: types.Message, state: FSMContext):
    """Показывает экран проверки подписки на канал"""
    channel_url = database.get_setting("channel_url")
    is_subscription_forced = database.get_setting("force_subscription") == "true"
    
    if not is_subscription_forced or not channel_url:
        # Если подписка не принудительная, завершаем онбординг
        await process_successful_onboarding(message, state)
        return
    
    text = (
        "<b>📢 Проверка подписки</b>\n\n"
        "Для доступа ко всем функциям, пожалуйста, подпишитесь на наш канал.\n\n"
        "После подписки нажмите кнопку ниже."
    )
    
    # Создаем клавиатуру с кнопками
    builder = InlineKeyboardBuilder()
    builder.button(text="📢 Перейти в канал", url=channel_url)
    builder.button(text="✅ Я подписался", callback_data="check_subscription_and_agree")
    builder.adjust(1)
    
    await message.answer(text, reply_markup=builder.as_markup())
    await state.set_state(Onboarding.waiting_for_subscription)

# Функция process_successful_onboarding перенесена в handlers.py

async def get_user_summary(user_id: int, username: str) -> str:
    keys = database.get_user_keys(user_id)
    latest_transaction = database.get_latest_transaction(user_id)

    summary_parts = [
        f"<b>Новый тикет от пользователя:</b> @{username} (ID: <code>{user_id}</code>)\n"
    ]

    if keys:
        summary_parts.append("<b>🔑 Активные ключи:</b>")
        for key in keys:
            expiry = key['expiry_date'].split(' ')[0]
            summary_parts.append(f"- <code>{key['key_email']}</code> (до {expiry} на хосте {key['host_name']})")
    else:
        summary_parts.append("<b>🔑 Активные ключи:</b> Нет")

    if latest_transaction:
        summary_parts.append("\n<b>💸 Последняя транзакция:</b>")
        metadata = json.loads(latest_transaction.get('metadata', '{}'))
        plan_name = metadata.get('plan_name', 'N/A')
        price = latest_transaction.get('amount_rub', 'N/A')
        date = latest_transaction.get('created_date', '').split(' ')[0]
        summary_parts.append(f"- {plan_name} за {price} RUB ({date})")
    else:
        summary_parts.append("\n<b>💸 Последняя транзакция:</b> Нет")

    return "\n".join(summary_parts)
def get_support_router() -> Router:
    support_router = Router()
    
    @support_router.message(Command("check_test"))
    async def check_test_command(message: types.Message, bot: Bot):
        """Команда для тестирования бота поддержки без проверки тем"""
        user_id = message.from_user.id
        is_admin = str(user_id) == database.get_setting("admin_telegram_id")
        
        if not is_admin:
            await message.answer("❌ У вас нет прав для выполнения этой команды.")
            return
        
        try:
            # Получаем настройки
            support_group_id = database.get_setting("support_group_id")
            support_bot_token = database.get_setting("support_bot_token")
            
            test_info = f"🧪 <b>Тест бота поддержки:</b>\n\n"
            test_info += f"📋 Support Group ID: {support_group_id or 'Не настроено'}\n"
            test_info += f"🔑 Support Bot Token: {'Настроено' if support_bot_token else 'Не настроено'}\n\n"
            
            if not support_group_id:
                test_info += "❌ <b>Ошибка:</b> ID группы поддержки не настроен\n"
            elif not support_bot_token:
                test_info += "❌ <b>Ошибка:</b> Токен бота поддержки не настроен\n"
            else:
                # Простая проверка доступности группы
                try:
                    chat_info = await bot.get_chat(support_group_id)
                    test_info += f"✅ <b>Группа найдена:</b> {chat_info.title}\n"
                    test_info += f"📊 <b>Тип группы:</b> {chat_info.type}\n"
                    test_info += f"🆔 <b>ID группы:</b> {chat_info.id}\n"
                    
                    # Проверяем права бота
                    try:
                        bot_member = await bot.get_chat_member(support_group_id, bot.id)
                        test_info += f"👤 <b>Статус бота:</b> {bot_member.status}\n"
                        
                        if bot_member.status in ['administrator', 'creator']:
                            test_info += "✅ <b>Права:</b> Бот является администратором\n"
                        else:
                            test_info += "❌ <b>Права:</b> Бот не является администратором\n"
                            test_info += "💡 <b>Решение:</b> Сделайте бота администратором группы\n"
                            
                    except Exception as member_error:
                        test_info += f"❌ <b>Ошибка проверки прав:</b> {member_error}\n"
                    
                    test_info += "\n🧪 <b>Тест отправки сообщения:</b>\n"
                    try:
                        await bot.send_message(
                            chat_id=support_group_id,
                            text="🧪 Тестовое сообщение от бота поддержки",
                            disable_notification=True
                        )
                        test_info += "✅ Сообщение отправлено успешно\n"
                    except Exception as send_error:
                        test_info += f"❌ Ошибка отправки: {send_error}\n"
                        
                except Exception as e:
                    test_info += f"❌ <b>Ошибка доступа к группе:</b> {e}\n"
                    test_info += "💡 <b>Возможные решения:</b>\n"
                    test_info += "• Убедитесь, что ID группы правильный\n"
                    test_info += "• Проверьте, что бот добавлен в группу\n"
                    if "upgraded to a supergroup" in str(e):
                        test_info += "• <b>ВАЖНО:</b> Группа была мигрирована в супергруппу!\n"
                        test_info += "• При включении тем Telegram автоматически мигрирует группу\n"
                        test_info += "• Новый ID обычно начинается с -100 (например: -1002919676196)\n"
                        test_info += "• Обновите ID группы в настройках веб-интерфейса\n"
                    else:
                        test_info += "• Группа могла быть мигрирована в супергруппу\n"
            
            await message.answer(test_info, parse_mode=ParseMode.HTML)
            
        except Exception as e:
            logger.error(f"Error in check_test command: {e}")
            await message.answer(f"❌ Ошибка при выполнении теста: {e}")

    @support_router.message(Command("check_config"))
    async def check_config_command(message: types.Message, bot: Bot):
        """Команда для проверки конфигурации бота поддержки"""
        user_id = message.from_user.id
        is_admin = str(user_id) == database.get_setting("admin_telegram_id")
        
        if not is_admin:
            await message.answer("❌ У вас нет прав для выполнения этой команды.")
            return
        
        try:
            # Проверяем настройки
            support_group_id = database.get_setting("support_group_id")
            support_bot_token = database.get_setting("support_bot_token")
            
            config_info = f"🔧 <b>Конфигурация бота поддержки:</b>\n\n"
            config_info += f"📋 Support Group ID: {support_group_id or 'Не настроено'}\n"
            config_info += f"🔑 Support Bot Token: {'Настроено' if support_bot_token else 'Не настроено'}\n\n"
            
            if not support_group_id:
                config_info += "❌ <b>Ошибка:</b> ID группы поддержки не настроен\n"
            elif not support_bot_token:
                config_info += "❌ <b>Ошибка:</b> Токен бота поддержки не настроен\n"
            else:
                # Проверяем доступность группы
                try:
                    chat_info = await bot.get_chat(support_group_id)
                    config_info += f"✅ <b>Группа найдена:</b> {chat_info.title}\n"
                    
                    # Проверяем включение тем через попытку создания тестовой темы
                    try:
                        test_topic = await bot.create_forum_topic(chat_id=support_group_id, name="Тестовая тема для проверки")
                        await bot.delete_forum_topic(chat_id=support_group_id, message_thread_id=test_topic.message_thread_id)
                        config_info += f"📊 <b>Тип:</b> Темы включены\n"
                        config_info += "✅ <b>Статус:</b> Группа настроена корректно\n"
                    except Exception as forum_error:
                        config_info += f"📊 <b>Тип:</b> Обычная группа\n"
                        config_info += "❌ <b>Ошибка:</b> Темы не включены в группе!\n"
                        config_info += "💡 <b>Решение:</b> Включите функцию 'Темы' в настройках группы\n"
                        
                except Exception as e:
                    config_info += f"❌ <b>Ошибка доступа к группе:</b> {e}\n"
                    if "upgraded to a supergroup" in str(e):
                        config_info += "💡 <b>ВАЖНО:</b> Группа была мигрирована в супергруппу!\n"
                        config_info += "• При включении тем Telegram автоматически мигрирует группу\n"
                        config_info += "• Новый ID обычно начинается с -100 (например: -1002919676196)\n"
                        config_info += "• Обновите ID группы в настройках веб-интерфейса\n"
                    else:
                        config_info += "💡 <b>Решение:</b> Убедитесь, что бот добавлен в группу и имеет права администратора\n"
            
            await message.answer(config_info, parse_mode=ParseMode.HTML)
            
        except Exception as e:
            logger.error(f"Error checking support bot config: {e}")
            await message.answer(f"❌ Ошибка при проверке конфигурации: {e}")

    @support_router.message(CommandStart())
    async def handle_start(message: types.Message, bot: Bot):
        user_id = message.from_user.id
        username = message.from_user.username or message.from_user.full_name
        
        print(f"DEBUG: SUPPORT BOT START HANDLER CALLED for user {user_id} ({username})")
        logger.info(f"SUPPORT BOT START HANDLER: User {user_id} ({username}) started support bot")
        
        thread_id = database.get_support_thread_id(user_id)
        
        if not thread_id:
            # Получаем ID группы поддержки из базы данных
            support_group_id = database.get_setting("support_group_id")
            if not support_group_id:
                logger.error("Support bot: support_group_id is not configured!")
                await message.answer("Извините, служба поддержки временно недоступна.")
                return

            try:
                # Сначала проверяем, что группа существует и в ней включены темы
                try:
                    chat_info = await bot.get_chat(support_group_id)
                    # Проверяем включение тем через попытку создания тестовой темы
                    try:
                        test_topic = await bot.create_forum_topic(chat_id=support_group_id, name="Тестовая тема для проверки")
                        await bot.delete_forum_topic(chat_id=support_group_id, message_thread_id=test_topic.message_thread_id)
                    except Exception as forum_error:
                        logger.error(f"Support group {support_group_id} topics are not enabled: {forum_error}")
                        await message.answer("❌ Темы не включены в группе поддержки. Обратитесь к администратору.")
                        return
                except Exception as chat_error:
                    logger.error(f"Support group {support_group_id} not found or inaccessible: {chat_error}")
                    if "upgraded to a supergroup" in str(chat_error):
                        await message.answer("❌ Группа поддержки была мигрирована в супергруппу. Обратитесь к администратору для обновления ID группы.")
                    else:
                        await message.answer("❌ Группа поддержки не найдена или недоступна. Обратитесь к администратору.")
                    return
                
                thread_name = f"Тикет от @{username} ({user_id})"
                new_thread = await bot.create_forum_topic(chat_id=support_group_id, name=thread_name)
                thread_id = new_thread.message_thread_id
                
                database.add_support_thread(user_id, thread_id)
                
                summary_text = await get_user_summary(user_id, username)
                await bot.send_message(
                    chat_id=support_group_id,
                    message_thread_id=thread_id,
                    text=summary_text,
                    parse_mode=ParseMode.HTML
                )
                logger.info(f"Created new support thread {thread_id} for user {user_id}")
                
            except Exception as e:
                logger.error(f"Failed to create support thread for user {user_id}: {e}", exc_info=True)
                if "chat not found" in str(e).lower():
                    await message.answer("❌ Группа поддержки не найдена. Обратитесь к администратору.")
                elif "upgraded to a supergroup" in str(e).lower():
                    await message.answer("❌ Группа поддержки была мигрирована в супергруппу. Обратитесь к администратору для обновления ID группы.")
                elif "not a forum" in str(e).lower() or "topics" in str(e).lower():
                    await message.answer("❌ Темы не включены в группе поддержки. Обратитесь к администратору.")
                else:
                    await message.answer("❌ Не удалось создать тикет в поддержке. Пожалуйста, попробуйте позже.")
                return

        await message.answer("Напишите ваш вопрос, и администратор скоро с вами свяжется.")

    @support_router.message(F.chat.type == "private")
    async def from_user_to_admin(message: types.Message, bot: Bot):
        user_id = message.from_user.id
        text = message.text or "NO_TEXT"
        
        print(f"DEBUG: SUPPORT BOT PRIVATE MESSAGE HANDLER for user {user_id}, text: '{text}'")
        
        thread_id = database.get_support_thread_id(user_id)
        support_group_id = database.get_setting("support_group_id")
        
        if thread_id and support_group_id:
            await bot.copy_message(
                chat_id=support_group_id,
                from_chat_id=user_id,
                message_id=message.message_id,
                message_thread_id=thread_id
            )
        else:
            await message.answer("Пожалуйста, сначала нажмите /start, чтобы создать тикет в поддержке.")

    @support_router.message(F.message_thread_id)
    async def from_admin_to_user(message: types.Message, bot: Bot):
        thread_id = message.message_thread_id
        user_id = database.get_user_id_by_thread(thread_id)
        
        if message.from_user.id == bot.id:
            return
            
        if user_id:
            support_group_id = database.get_setting("support_group_id")
            if support_group_id:
                try:
                    await bot.copy_message(
                        chat_id=user_id,
                        from_chat_id=support_group_id,
                        message_id=message.message_id
                    )
                except Exception as e:
                    logger.error(f"Failed to send message from thread {thread_id} to user {user_id}: {e}")
                    await message.reply("❌ Не удалось доставить сообщение этому пользователю (возможно, он заблокировал бота).")
    
    @support_router.error()
    async def support_router_error_handler(event: ErrorEvent):
        """Глобальный обработчик ошибок для support_router"""
        logger.critical(
            "Critical error in support router caused by %s", 
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
                    "⚠️ Произошла ошибка в системе поддержки.\n"
                    "Попробуйте позже или напишите напрямую администратору."
                )
            elif update.callback_query:
                user_id = update.callback_query.from_user.id
                await update.callback_query.answer(
                    "⚠️ Ошибка. Попробуйте позже.",
                    show_alert=True
                )
        except Exception as notification_error:
            logger.error(f"Failed to send error notification to user {user_id}: {notification_error}")
    
    return support_router