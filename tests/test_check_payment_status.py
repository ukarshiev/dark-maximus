#!/usr/bin/env python3
"""Временный скрипт для проверки статуса платежа YooKassa"""
import sys
sys.path.insert(0, '/app/project')

from yookassa import Configuration, Payment
from shop_bot.data_manager.database import get_setting

payment_id = '30a29228-000f-5000-b000-1091368acfc8'

yookassa_test_mode = get_setting("yookassa_test_mode") == "true"

if yookassa_test_mode:
    shop_id = (get_setting("yookassa_test_shop_id") or "").strip() or (get_setting("yookassa_shop_id") or "").strip()
    secret_key = (get_setting("yookassa_test_secret_key") or "").strip() or (get_setting("yookassa_secret_key") or "").strip()
    api_url = (get_setting("yookassa_test_api_url") or "").strip() or (get_setting("yookassa_api_url") or "").strip() or "https://api.test.yookassa.ru/v3"
else:
    shop_id = (get_setting("yookassa_shop_id") or "").strip()
    secret_key = (get_setting("yookassa_secret_key") or "").strip()
    api_url = (get_setting("yookassa_api_url") or "").strip() or "https://api.yookassa.ru/v3"

Configuration.account_id = shop_id
Configuration.secret_key = secret_key
Configuration.api_url = api_url

# Отключаем проверку SSL для тестового режима
if yookassa_test_mode:
    verify_ssl = get_setting("yookassa_test_verify_ssl") != "false"
    if not verify_ssl:
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        import ssl
        ssl._create_default_https_context = ssl._create_unverified_context

print(f"Config: test_mode={yookassa_test_mode}, api_url={api_url}, shop_id={shop_id[:8]}..., verify_ssl={verify_ssl if yookassa_test_mode else True}")

try:
    payment = Payment.find_one(payment_id)
    print(f"Status: {payment.status}")
    print(f"Paid: {payment.paid}")
    print(f"Test: {payment.test if hasattr(payment, 'test') else False}")
    print(f"Amount: {payment.amount.value} {payment.amount.currency}")
    print(f"Metadata: {payment.metadata if hasattr(payment, 'metadata') else {}}")
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()

