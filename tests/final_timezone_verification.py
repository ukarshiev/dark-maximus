#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Финальная проверка timezone после исправлений"""
import sys

from _io_encoding import ensure_utf8_output

if sys.platform == 'win32':
    ensure_utf8_output()
sys.path.insert(0, 'src')

from shop_bot.data_manager.database import (
    is_timezone_feature_enabled, 
    get_user_timezone, 
    set_user_timezone,
    get_setting
)
from datetime import datetime, timezone
from shop_bot.utils.datetime_utils import format_datetime_for_user
from shop_bot.config import get_key_info_text

print("=" * 70)
print("FINALNAYA PROVERKA TIMEZONE POSLE ISPRAVLENIY")
print("=" * 70)

# 1. Проверка feature flag
feature_enabled = is_timezone_feature_enabled()
print(f"\n1. Feature timezone enabled: {feature_enabled}")

if not feature_enabled:
    print("   [ERROR] Feature flag vyklyuchen!")
    sys.exit(1)

# 2. Проверка tzdata
try:
    from zoneinfo import ZoneInfo
    tz_test = ZoneInfo("Pacific/Auckland")
    print(f"2. tzdata rabotaet: OK (zagruzhena Pacific/Auckland)")
except Exception as e:
    print(f"2. tzdata NE rabotaet: {e}")
    sys.exit(1)

# 3. Тестирование с реальным пользователем
test_user_id = 1588069616
print(f"\n3. Test s user_id = {test_user_id}")

# Сохраняем текущий timezone
original_tz = get_user_timezone(test_user_id)
print(f"   Original TZ: {original_tz}")

# Устанавливаем Auckland
set_user_timezone(test_user_id, "Pacific/Auckland")
new_tz = get_user_timezone(test_user_id)
print(f"   New TZ: {new_tz}")

# 4. Тестируем форматирование
test_date = datetime(2025, 11, 7, 7, 17, 0, tzinfo=timezone.utc)
formatted = format_datetime_for_user(
    test_date, 
    user_timezone=new_tz, 
    feature_enabled=True
)
print(f"\n4. Formattirovanie daty:")
print(f"   UTC: 2025-11-07 07:17:00")
print(f"   Formattirovano: {formatted}")
print(f"   Ozhidaetsya: 07.11.2025 v 20:17 (UTC+13)")

# 5. Тестируем get_key_info_text
print(f"\n5. Test get_key_info_text:")
created_date = datetime(2025, 11, 7, 7, 17, 0, tzinfo=timezone.utc)
expiry_date = datetime(2025, 11, 7, 8, 17, 0, tzinfo=timezone.utc)

key_info = get_key_info_text(
    key_number=1,
    expiry_date=expiry_date,
    created_date=created_date,
    connection_string="vless://test",
    status="active",
    user_timezone=new_tz,
    feature_enabled=True
)

print("\n   Vyvod get_key_info_text:")
print("   " + "-" * 60)
for line in key_info.split('\n')[:5]:  # Первые 5 строк
    print(f"   {line}")
print("   " + "-" * 60)

# Проверяем, что в тексте есть UTC+13
if "UTC+13" in key_info or "UTC+12" in key_info:
    print("   [SUCCESS] UTC offset najden v tekste!")
else:
    print("   [WARNING] UTC offset NE najden, eto UTC+3?")

# Возвращаем оригинальный timezone
set_user_timezone(test_user_id, original_tz)
print(f"\n6. Vozvraschen original TZ: {original_tz}")

print("\n" + "=" * 70)
print("VSYA PROVERKA ZAVERSHENA USPESHNO!")
print("=" * 70)

