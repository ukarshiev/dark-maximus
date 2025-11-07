#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys
from pathlib import Path
project_root = Path(__file__).parent.parent
src_path = project_root / "src"
sys.path.insert(0, str(src_path))

from shop_bot.data_manager.database import get_key_by_id, get_user, get_auto_renewal_enabled, get_user_balance
from datetime import datetime, timezone

key = get_key_by_id(117)
if not key:
    print("Key 117 not found!")
    sys.exit(1)

user_id = key.get('user_id')
user = get_user(user_id) if user_id else None

print("=== Key 117 ===")
print(f"User ID: {user_id}")
print(f"Expiry: {key.get('expiry_date')}")
print(f"Status: {key.get('status')}")
print(f"Plan: {key.get('plan_name')}")
print(f"Price: {key.get('price')}")
print(f"Host: {key.get('host_name')}")

print("\n=== User ===")
print(f"Username: {user.get('username') if user else 'Not found'}")
print(f"Auto-renewal: {get_auto_renewal_enabled(user_id) if user_id else 'N/A'}")
print(f"Balance: {get_user_balance(user_id) if user_id else 'N/A'}")

now = datetime.now(timezone.utc).replace(tzinfo=None)
expiry = datetime.fromisoformat(key['expiry_date'])
if expiry.tzinfo:
    expiry = expiry.replace(tzinfo=None)

time_left = (expiry - now).total_seconds()
hours_left = time_left / 3600

print(f"\n=== Time Analysis ===")
print(f"Now (UTC): {now}")
print(f"Expiry (UTC): {expiry}")
print(f"Time left: {time_left:.0f} seconds ({hours_left:.2f} hours)")

# Проверяем логику уведомлений
NOTIFY_BEFORE_HOURS = {24, 1}
total_seconds_left = int(time_left)
total_hours_left = int(time_left / 3600)

print(f"\n=== Notification Logic Check ===")
print(f"total_seconds_left: {total_seconds_left}")
print(f"total_hours_left: {total_hours_left}")
print(f"NOTIFY_BEFORE_HOURS: {NOTIFY_BEFORE_HOURS}")

for hours_mark in sorted(NOTIFY_BEFORE_HOURS):
    mark_seconds = hours_mark * 3600
    should_notify = total_seconds_left <= mark_seconds
    print(f"  Marker {hours_mark}h ({mark_seconds}s): should_notify={should_notify}")

