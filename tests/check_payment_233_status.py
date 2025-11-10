#!/usr/bin/env python3
import sys
import os
from pathlib import Path

project_root = Path("/app/project") if os.path.exists("/app/project") else Path("/opt/dark-maximus")
sys.path.insert(0, str(project_root / "src"))

from shop_bot.data_manager.database import get_transaction_by_payment_id, get_user_keys
from shop_bot.webhook_server.app import _ensure_host_metadata
import json

payment_id = "30a48370-000f-5001-9000-16231fa0ad0c"

print("="*80)
print("Проверка платежа ID 233")
print("="*80)

tx = get_transaction_by_payment_id(payment_id)
if not tx:
    print("❌ Транзакция не найдена!")
    sys.exit(1)

md = tx.get('metadata', {})
if isinstance(md, str):
    md = json.loads(md)

print(f"\nТранзакция:")
print(f"  - ID: {tx.get('transaction_id')}")
print(f"  - Status: {tx.get('status')}")
print(f"  - Payment ID: {tx.get('payment_id')}")

print(f"\nMetadata:")
print(f"  - host_code: {md.get('host_code')}")
print(f"  - host_name: {md.get('host_name')}")
print(f"  - plan_id: {md.get('plan_id')}")
print(f"  - user_id: {md.get('user_id')}")

print(f"\nТест функции _ensure_host_metadata():")
test_md = md.copy()
host_ok, host_record = _ensure_host_metadata(test_md, payment_id)
print(f"  - Результат: {'✅ OK' if host_ok else '❌ FAILED'}")
if host_record:
    print(f"  - Хост найден: {host_record.get('host_name')}")
    print(f"  - Host code: {host_record.get('host_code')}")

user_id = md.get('user_id')
if user_id:
    print(f"\nКлючи пользователя {user_id}:")
    keys = get_user_keys(int(user_id))
    print(f"  - Всего ключей: {len(keys)}")
    finland_keys = [k for k in keys if 'Финляндия' in str(k.get('host_name', ''))]
    print(f"  - Ключей для Финляндии: {len(finland_keys)}")
    if finland_keys:
        latest = finland_keys[-1]
        print(f"  - Последний ключ ID: {latest.get('key_id')}")
        print(f"  - Создан: {latest.get('created_date')}")

print("\n" + "="*80)

