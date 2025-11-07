#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Проверка статуса feature flag для timezone"""
import sys

from _io_encoding import ensure_utf8_output

if sys.platform == 'win32':
    ensure_utf8_output()
sys.path.insert(0, 'src')

from shop_bot.data_manager.database import get_setting, is_timezone_feature_enabled, get_user_timezone

# Проверяем feature flag
feature_enabled = is_timezone_feature_enabled()
print(f"[OK] Feature timezone enabled: {feature_enabled}")

# Получаем значение из БД напрямую
feature_value = get_setting('feature_timezone_enabled')
print(f"[OK] Feature timezone value in DB: {feature_value}")

# Проверим timezone тестового пользователя (если есть)
test_user_id = 5598780981  # ID из скриншота
user_tz = get_user_timezone(test_user_id)
print(f"[OK] User {test_user_id} timezone: {user_tz}")

print("\n" + "="*60)
if not feature_enabled:
    print("[WARNING] PROBLEMA: Feature flag vyklyuchen!")
    print("   Dlya vklyucheniya vypolnite:")
    print('   UPDATE bot_settings SET value = "1" WHERE key = "feature_timezone_enabled";')
else:
    print("[OK] Feature flag vklyuchen, timezone dolzhen rabotat")

