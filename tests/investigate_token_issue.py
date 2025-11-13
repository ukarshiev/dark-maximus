#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Исследование проблемы с токеном в ссылке личного кабинета
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from shop_bot.data_manager.database import (
    get_key_by_id,
    get_permanent_token_by_key_id,
    get_plans_for_host,
    get_user_keys
)

def investigate():
    """Исследование проблемы"""
    
    print("=" * 60)
    print("ИССЛЕДОВАНИЕ ПРОБЛЕМЫ С ТОКЕНОМ")
    print("=" * 60)
    
    # 1. Находим последний ключ
    print("\n1. Поиск последнего ключа...")
    last_key = None
    for user_id in range(1, 1000):
        keys = get_user_keys(user_id)
        if keys:
            last_key = keys[-1]  # Берем последний ключ
            break
    
    if not last_key:
        print("   ❌ Ключи не найдены")
        return
    
    key_id = last_key['key_id']
    user_id = last_key['user_id']
    print(f"   ✅ Найден ключ: key_id={key_id}, user_id={user_id}")
    
    # 2. Проверяем токен
    print("\n2. Проверка токена...")
    token = get_permanent_token_by_key_id(key_id)
    if token:
        print(f"   ✅ Токен существует: {token[:40]}...")
    else:
        print(f"   ❌ Токен НЕ найден!")
    
    # 3. Проверяем данные ключа
    print("\n3. Данные ключа...")
    key_data = get_key_by_id(key_id)
    print(f"   plan_name: {key_data.get('plan_name')}")
    print(f"   host_name: {key_data.get('host_name')}")
    print(f"   subscription_link: {key_data.get('subscription_link')}")
    print(f"   connection_string: {'ЕСТЬ' if key_data.get('connection_string') else 'НЕТ'}")
    
    # 4. Проверяем provision_mode плана
    print("\n4. Проверка provision_mode плана...")
    host_name = key_data.get('host_name')
    plan_name = key_data.get('plan_name')
    if host_name and plan_name:
        plans = get_plans_for_host(host_name)
        plan = next((p for p in plans if p.get('plan_name') == plan_name), None)
        if plan:
            provision_mode = plan.get('key_provision_mode', 'key')
            print(f"   ✅ provision_mode: {provision_mode}")
        else:
            print(f"   ⚠️  План не найден")
            provision_mode = 'key'
    else:
        print(f"   ⚠️  Нет данных о плане")
        provision_mode = 'key'
    
    # 5. Проверяем формирование ссылки
    print("\n5. Проверка формирования ссылки...")
    from shop_bot.config import get_user_cabinet_domain, get_purchase_success_text
    from datetime import datetime, timezone
    
    cabinet_domain = get_user_cabinet_domain()
    print(f"   Домен: {cabinet_domain}")
    
    # Симулируем вызов функции
    test_text = get_purchase_success_text(
        action="готов",
        key_number=8,
        expiry_date=datetime.now(timezone.utc),
        connection_string=key_data.get('connection_string'),
        subscription_link=key_data.get('subscription_link'),
        provision_mode=provision_mode,
        user_id=user_id,
        key_id=key_id,
    )
    
    # Проверяем наличие токена в тексте
    has_token = '/auth/' in test_text
    has_localhost = 'localhost' in test_text
    
    print(f"   Ссылка содержит /auth/: {has_token}")
    print(f"   Ссылка содержит localhost: {has_localhost}")
    
    if has_token:
        # Извлекаем ссылку
        import re
        match = re.search(r'href="([^"]+)"', test_text)
        if match:
            url = match.group(1)
            print(f"   ✅ URL: {url}")
            if '/auth/' in url:
                token_in_url = url.split('/auth/')[-1].split('"')[0].split('>')[0]
                print(f"   ✅ Токен в URL: {token_in_url[:40]}...")
            else:
                print(f"   ❌ Токен НЕ в URL!")
    else:
        print(f"   ❌ Ссылка БЕЗ токена!")
        # Ищем ссылку без токена
        match = re.search(r'href="([^"]+)"', test_text)
        if match:
            url = match.group(1)
            print(f"   URL без токена: {url}")
    
    print("\n" + "=" * 60)
    print("РЕЗУЛЬТАТ ИССЛЕДОВАНИЯ")
    print("=" * 60)
    
    if not token:
        print("❌ ПРОБЛЕМА: Токен не создан в БД")
    elif not has_token:
        print("❌ ПРОБЛЕМА: Токен не добавляется в ссылку")
    else:
        print("✅ Всё работает корректно")

if __name__ == "__main__":
    investigate()

