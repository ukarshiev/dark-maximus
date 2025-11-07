#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Включение feature flag для timezone"""
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, 'src')

from shop_bot.data_manager.database import update_setting, is_timezone_feature_enabled

print("=" * 60)
print("Vklyuchenie timezone feature flag...")
print("=" * 60)

# Проверяем текущее состояние
before = is_timezone_feature_enabled()
print(f"\nDo: feature_timezone_enabled = {before}")

# Включаем feature flag
update_setting('feature_timezone_enabled', '1')

# Проверяем после изменения
after = is_timezone_feature_enabled()
print(f"Posle: feature_timezone_enabled = {after}")

if after:
    print("\n[SUCCESS] Feature flag uspeshno vklyuchen!")
    print("Teper timezone budet rabotat dlya vseh polzovateley.")
else:
    print("\n[ERROR] Feature flag ne udalos' vklyuchit'")

print("=" * 60)

