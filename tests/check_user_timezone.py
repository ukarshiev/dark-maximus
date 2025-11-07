#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Проверка timezone пользователя"""
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, 'src')

from shop_bot.data_manager.database import get_user_timezone, is_timezone_feature_enabled, get_user
from datetime import datetime, timezone
from shop_bot.utils.datetime_utils import format_datetime_for_user

test_user_id = 5598780981  # ID из скриншота

print("=" * 60)
print(f"Proverka timezone dlya user_id = {test_user_id}")
print("=" * 60)

# Проверяем feature flag
feature_enabled = is_timezone_feature_enabled()
print(f"\n1. Feature enabled: {feature_enabled}")

# Получаем timezone пользователя
user_tz = get_user_timezone(test_user_id)
print(f"2. User timezone: {user_tz}")

# Получаем полные данные пользователя
user_data = get_user(test_user_id)
if user_data:
    print(f"3. User data timezone field: {user_data.get('timezone', 'NOT SET')}")
else:
    print("3. User not found in database")

# Тестируем форматирование даты
test_date = datetime(2025, 11, 7, 7, 17, 0, tzinfo=timezone.utc)  # 07.11.2025 10:17 UTC+3
formatted = format_datetime_for_user(test_date, user_timezone=user_tz, feature_enabled=feature_enabled)
print(f"\n4. Test date formatting:")
print(f"   UTC time: 2025-11-07 07:17:00")
print(f"   Formatted: {formatted}")
print(f"   Expected for Auckland (UTC+12): 07.11.2025 v 19:17 (UTC+12)")

print("=" * 60)

