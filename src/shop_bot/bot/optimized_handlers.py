# -*- coding: utf-8 -*-
"""
Оптимизированные обработчики команд с использованием асинхронной БД
"""

import logging
import asyncio
from typing import Dict, Any, Optional
from aiogram import Router, F, types
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from shop_bot.bot import keyboards
from shop_bot.data_manager.async_database import (
    get_user_async, get_all_hosts_async, get_plans_for_host_async,
    register_user_if_not_exists_async, get_setting_async
)
from shop_bot.config import get_profile_text, get_vpn_active_text, VPN_INACTIVE_TEXT, VPN_NO_DATA_TEXT
from shop_bot.utils.performance_monitor import measure_performance

logger = logging.getLogger(__name__)

# Кэш для часто запрашиваемых данных
_hosts_cache: Dict[str, Any] = {}
_plans_cache: Dict[int, Any] = {}
_cache_ttl = 300  # 5 минут
_cache_timestamps: Dict[str, float] = {}

async def _is_cache_valid(cache_key: str) -> bool:
    """Проверка валидности кэша"""
    if cache_key not in _cache_timestamps:
        return False
    return (asyncio.get_event_loop().time() - _cache_timestamps[cache_key]) < _cache_ttl

async def _get_cached_hosts() -> list:
    """Получение хостов с кэшированием"""
    cache_key = "hosts"
    if await _is_cache_valid(cache_key):
        return _hosts_cache.get(cache_key, [])
    
    hosts = await get_all_hosts_async()
    _hosts_cache[cache_key] = hosts
    _cache_timestamps[cache_key] = asyncio.get_event_loop().time()
    return hosts

async def _get_cached_plans(host_id: int) -> list:
    """Получение планов для хоста с кэшированием"""
    cache_key = f"plans_{host_id}"
    if await _is_cache_valid(cache_key):
        return _plans_cache.get(cache_key, [])
    
    plans = await get_plans_for_host_async(host_id)
    _plans_cache[cache_key] = plans
    _cache_timestamps[cache_key] = asyncio.get_event_loop().time()
    return plans

async def show_main_menu_optimized(message: types.Message, edit_message: bool = False):
    """Оптимизированная функция показа главного меню"""
    try:
        user_id = message.from_user.id
        user_data = await get_user_async(user_id)
        
        if not user_data:
            await message.answer("Ошибка: пользователь не найден. Попробуйте /start")
            return
        
        # Проверяем статус VPN
        vpn_status_text = VPN_NO_DATA_TEXT
        if user_data.get('key_id'):
            # Здесь можно добавить проверку активности ключа
            vpn_status_text = VPN_INACTIVE_TEXT
        
        # Формируем текст профиля
        text = get_profile_text(
            username=user_data.get('username', 'Пользователь'),
            balance=user_data.get('balance', 0.0),
            total_spent=user_data.get('total_spent', 0.0),
            total_months=user_data.get('total_months', 0),
            vpn_status_text=vpn_status_text,
            referral_balance=user_data.get('referral_balance', 0.0),
            show_referral=True,
            referral_link=f"https://t.me/{await get_setting_async('telegram_bot_username')}?start=ref_{user_id}",
            referral_percentage=10
        )
        
        keyboard = keyboards.get_main_inline_keyboard()
        
        if edit_message:
            await message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
        else:
            await message.answer(text, reply_markup=keyboard, parse_mode="HTML")
            
    except Exception as e:
        logger.error(f"Error in show_main_menu_optimized: {e}")
        await message.answer("Произошла ошибка. Попробуйте позже.")

@measure_performance("buy_handler")
async def buy_handler_optimized(message: types.Message):
    """Оптимизированный обработчик команды покупки"""
    try:
        user_id = message.from_user.id
        
        # Получаем хосты с кэшированием
        hosts = await _get_cached_hosts()
        
        if not hosts:
            await message.answer("❌ В данный момент нет доступных серверов.")
            return
        
        # Создаем клавиатуру для выбора хоста
        builder = InlineKeyboardBuilder()
        for host in hosts:
            builder.button(
                text=f"🌐 {host['host_name']}",
                callback_data=f"host_{host['host_id']}"
            )
        
        builder.button(text="🔙 Назад в меню", callback_data="back_to_main_menu")
        builder.adjust(1)
        
        await message.answer(
            "🌐 <b>Выберите сервер:</b>\n\n"
            "Выберите сервер для подключения к VPN:",
            reply_markup=builder.as_markup(),
            parse_mode="HTML"
        )
        
    except Exception as e:
        logger.error(f"Error in buy_handler_optimized: {e}")
        await message.answer("Произошла ошибка при загрузке серверов. Попробуйте позже.")

@measure_performance("host_selection_handler")
async def host_selection_handler_optimized(callback: types.CallbackQuery, state: FSMContext):
    """Оптимизированный обработчик выбора хоста"""
    try:
        host_id = int(callback.data.split("_")[1])
        
        # Получаем планы для хоста с кэшированием
        plans = await _get_cached_plans(host_id)
        
        if not plans:
            await callback.answer("❌ Нет доступных тарифов для этого сервера.")
            return
        
        # Создаем клавиатуру для выбора тарифа
        builder = InlineKeyboardBuilder()
        for plan in plans:
            price_text = f"{plan['price']:.2f} RUB"
            if plan.get('days', 0) > 0:
                days_text = f"{plan['days']} дн."
            else:
                days_text = f"{plan.get('hours', 0)} ч."
            
            builder.button(
                text=f"📦 {plan['plan_name']} - {price_text} ({days_text})",
                callback_data=f"plan_{plan['plan_id']}"
            )
        
        builder.button(text="🔙 Назад к серверам", callback_data="buy_new_vpn")
        builder.adjust(1)
        
        await callback.message.edit_text(
            "📦 <b>Выберите тариф:</b>\n\n"
            "Выберите подходящий тариф для подключения:",
            reply_markup=builder.as_markup(),
            parse_mode="HTML"
        )
        
    except Exception as e:
        logger.error(f"Error in host_selection_handler_optimized: {e}")
        await callback.answer("Произошла ошибка при загрузке тарифов.")

@measure_performance("profile_handler")
async def profile_handler_optimized(message: types.Message):
    """Оптимизированный обработчик профиля"""
    try:
        user_id = message.from_user.id
        user_data = await get_user_async(user_id)
        
        if not user_data:
            await message.answer("Ошибка: пользователь не найден. Попробуйте /start")
            return
        
        # Проверяем статус VPN
        vpn_status_text = VPN_NO_DATA_TEXT
        if user_data.get('key_id'):
            # Здесь можно добавить проверку активности ключа
            vpn_status_text = VPN_INACTIVE_TEXT
        
        # Формируем текст профиля
        text = get_profile_text(
            username=user_data.get('username', 'Пользователь'),
            balance=user_data.get('balance', 0.0),
            total_spent=user_data.get('total_spent', 0.0),
            total_months=user_data.get('total_months', 0),
            vpn_status_text=vpn_status_text,
            referral_balance=user_data.get('referral_balance', 0.0),
            show_referral=True,
            referral_link=f"https://t.me/{await get_setting_async('telegram_bot_username')}?start=ref_{user_id}",
            referral_percentage=10
        )
        
        keyboard = keyboards.get_profile_keyboard()
        
        await message.answer(text, reply_markup=keyboard, parse_mode="HTML")
        
    except Exception as e:
        logger.error(f"Error in profile_handler_optimized: {e}")
        await message.answer("Произошла ошибка при загрузке профиля. Попробуйте позже.")

@measure_performance("start_handler")
async def start_handler_optimized(message: types.Message, state: FSMContext, command):
    """Оптимизированный обработчик команды /start"""
    try:
        user_id = message.from_user.id
        username = message.from_user.username or message.from_user.full_name
        referrer_id = None
        
        # Обработка реферальной ссылки
        if command.args and command.args.startswith('ref_'):
            try:
                potential_referrer_id = int(command.args.split('_')[1])
                if potential_referrer_id != user_id:
                    referrer_id = potential_referrer_id
                    logger.info(f"New user {user_id} was referred by {referrer_id}")
            except (IndexError, ValueError):
                logger.warning(f"Invalid referral code received: {command.args}")
        
        # Регистрируем пользователя если не существует
        await register_user_if_not_exists_async(
            user_id, username, referrer_id, message.from_user.full_name
        )
        
        # Получаем данные пользователя
        user_data = await get_user_async(user_id)
        
        if not user_data:
            await message.answer("Ошибка при регистрации. Попробуйте позже.")
            return
        
        # Проверяем согласие с документами
        if not user_data.get('agreed_to_documents'):
            # Показываем форму согласия
            from shop_bot.data_manager.database import get_global_domain
            domain = get_global_domain()
            
            terms_url = None
            privacy_url = None
            if domain and not domain.startswith("http://localhost") and not domain.startswith("https://localhost"):
                terms_url = f"{domain.rstrip('/')}/terms"
                privacy_url = f"{domain.rstrip('/')}/privacy"
            
            if terms_url and privacy_url:
                keyboard = keyboards.get_terms_agreement_keyboard(terms_url, privacy_url)
                await message.answer(
                    "📋 <b>Согласие с условиями</b>\n\n"
                    "Для использования бота необходимо ознакомиться с условиями использования и политикой конфиденциальности.",
                    reply_markup=keyboard,
                    parse_mode="HTML"
                )
                return
        
        # Проверяем подписку на канал если требуется
        force_subscription = await get_setting_async("force_subscription")
        channel_url = await get_setting_async("channel_url")
        
        if force_subscription == "true" and channel_url:
            # Здесь можно добавить проверку подписки
            pass
        
        # Показываем главное меню
        is_admin = str(user_id) == await get_setting_async("admin_telegram_id")
        await message.answer(
            f"👋 Добро пожаловать, {message.from_user.full_name}!",
            reply_markup=keyboards.get_main_reply_keyboard(is_admin)
        )
        await show_main_menu_optimized(message)
        
    except Exception as e:
        logger.error(f"Error in start_handler_optimized: {e}")
        await message.answer("Произошла ошибка при запуске. Попробуйте позже.")

# Функция для очистки кэша
async def clear_cache():
    """Очистка всех кэшей"""
    global _hosts_cache, _plans_cache, _cache_timestamps
    _hosts_cache.clear()
    _plans_cache.clear()
    _cache_timestamps.clear()
    logger.info("Cache cleared")

# Функция для получения статистики кэша
def get_cache_stats() -> Dict[str, Any]:
    """Получение статистики кэша"""
    return {
        "hosts_cache_size": len(_hosts_cache),
        "plans_cache_size": len(_plans_cache),
        "cache_timestamps_size": len(_cache_timestamps),
        "cache_ttl": _cache_ttl
    }
