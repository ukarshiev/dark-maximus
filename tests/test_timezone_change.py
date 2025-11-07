#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Тест смены timezone для реального пользователя"""
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, 'src')

from shop_bot.data_manager.database import get_user_timezone, set_user_timezone, get_user
from datetime import datetime, timezone
from shop_bot.utils.datetime_utils import format_datetime_for_user

# Используем реального пользователя из БД
test_user_id = 1588069616  # GMEnergy

print("=" * 60)
print(f"Test timezone change dlya user_id = {test_user_id}")
print("=" * 60)

# 1. Проверяем текущий timezone
current_tz = get_user_timezone(test_user_id)
print(f"\n1. Tekushchiy timezone: {current_tz}")

# 2. Устанавливаем Auckland timezone
print("\n2. Ustanavlivaem Pacific/Auckland (UTC+12)...")
success = set_user_timezone(test_user_id, "Pacific/Auckland")
print(f"   Result: {'SUCCESS' if success else 'FAILED'}")

# 3. Проверяем изменение
new_tz = get_user_timezone(test_user_id)
print(f"\n3. Novyy timezone: {new_tz}")

# 4. Тестируем форматирование
test_date = datetime(2025, 11, 7, 7, 17, 0, tzinfo=timezone.utc)
formatted_old = format_datetime_for_user(test_date, user_timezone="Europe/Moscow", feature_enabled=True)
formatted_new = format_datetime_for_user(test_date, user_timezone=new_tz, feature_enabled=True)

print(f"\n4. Formattirovanie daty (2025-11-07 07:17:00 UTC):")
print(f"   S Moscow TZ: {formatted_old}")
print(f"   S Auckland TZ: {formatted_new}")

# 5. Возвращаем обратно Moscow
print("\n5. Vozvrashchaem Moscow timezone...")
set_user_timezone(test_user_id, "Europe/Moscow")
final_tz = get_user_timezone(test_user_id)
print(f"   Final timezone: {final_tz}")

print("=" * 60)

