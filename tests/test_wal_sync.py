# -*- coding: utf-8 -*-
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from shop_bot.data_manager.database import get_setting, update_setting

print("До изменения:")
print(f"yookassa_test_mode: {get_setting('yookassa_test_mode')}")

print("\nИзменяю на false...")
update_setting('yookassa_test_mode', 'false')

print("\nПосле изменения:")
print(f"yookassa_test_mode: {get_setting('yookassa_test_mode')}")

print("\nИзменяю обратно на true...")
update_setting('yookassa_test_mode', 'true')

print("\nПосле обратного изменения:")
print(f"yookassa_test_mode: {get_setting('yookassa_test_mode')}")

