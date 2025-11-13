#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Тест функционала создания токена и формирования ссылки личного кабинета
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from shop_bot.data_manager.database import (
    get_user_keys,
    get_key_by_id,
    get_or_create_permanent_token,
    get_permanent_token_by_key_id,
    get_plans_for_host,
    get_setting
)
from shop_bot.config import (
    get_purchase_success_text,
    get_key_info_text,
    get_user_cabinet_domain
)
from datetime import datetime, timezone

def test_token_creation():
    """Тест создания токена"""
    print("=" * 60)
    print("ТЕСТ: Создание токена")
    print("=" * 60)
    
    # Находим последний ключ
    last_key = None
    for user_id in range(1, 1000):
        keys = get_user_keys(user_id)
        if keys:
            last_key = keys[-1]
            break
    
    if not last_key:
        print("❌ Ключи не найдены в БД")
        return False
    
    key_id = last_key['key_id']
    user_id = last_key['user_id']
    
    print(f"\n✅ Найден ключ: key_id={key_id}, user_id={user_id}")
    
    # Проверяем существующий токен
    existing_token = get_permanent_token_by_key_id(key_id)
    if existing_token:
        print(f"✅ Токен уже существует: {existing_token[:40]}...")
        token = existing_token
    else:
        print("⚠️  Токен не найден, создаем новый...")
        try:
            token = get_or_create_permanent_token(user_id, key_id)
            print(f"✅ Токен создан: {token[:40]}...")
        except Exception as e:
            print(f"❌ Ошибка создания токена: {e}")
            return False
    
    return True, user_id, key_id, token

def test_link_generation(user_id, key_id, token):
    """Тест генерации ссылки"""
    print("\n" + "=" * 60)
    print("ТЕСТ: Генерация ссылки")
    print("=" * 60)
    
    # Получаем данные ключа
    key_data = get_key_by_id(key_id)
    if not key_data:
        print("❌ Данные ключа не найдены")
        return False
    
    print(f"\n📋 Данные ключа:")
    print(f"   plan_name: {key_data.get('plan_name')}")
    print(f"   host_name: {key_data.get('host_name')}")
    print(f"   subscription_link: {key_data.get('subscription_link')}")
    
    # Получаем provision_mode
    host_name = key_data.get('host_name')
    plan_name = key_data.get('plan_name')
    provision_mode = 'key'
    
    if host_name and plan_name:
        plans = get_plans_for_host(host_name)
        plan = next((p for p in plans if p.get('plan_name') == plan_name), None)
        if plan:
            provision_mode = plan.get('key_provision_mode', 'key')
            print(f"   provision_mode: {provision_mode}")
    
    # Проверяем домен
    cabinet_domain = get_user_cabinet_domain()
    print(f"\n🌐 Домен личного кабинета: {cabinet_domain}")
    
    if not cabinet_domain:
        print("❌ Домен не настроен!")
        return False
    
    # Тестируем get_purchase_success_text
    print("\n📝 Тест get_purchase_success_text:")
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
    
    # Проверяем наличие токена в ссылке
    has_token = '/auth/' in test_text
    has_localhost = 'localhost' in test_text
    
    print(f"   Ссылка содержит /auth/: {has_token}")
    print(f"   Ссылка содержит localhost: {has_localhost}")
    
    if has_token:
        import re
        match = re.search(r'href="([^"]+)"', test_text)
        if match:
            url = match.group(1)
            print(f"   ✅ URL: {url}")
            if '/auth/' in url:
                token_in_url = url.split('/auth/')[-1].split('"')[0].split('>')[0]
                print(f"   ✅ Токен в URL: {token_in_url[:40]}...")
                if token_in_url == token:
                    print(f"   ✅ Токен совпадает с созданным!")
                else:
                    print(f"   ⚠️  Токен не совпадает!")
            else:
                print(f"   ❌ Токен НЕ в URL!")
        else:
            print(f"   ❌ URL не найден в тексте!")
    else:
        print(f"   ❌ Ссылка БЕЗ токена!")
        match = re.search(r'href="([^"]+)"', test_text)
        if match:
            url = match.group(1)
            print(f"   URL без токена: {url}")
    
    # Тестируем get_key_info_text
    print("\n📝 Тест get_key_info_text:")
    test_text2 = get_key_info_text(
        key_number=8,
        expiry_date=datetime.now(timezone.utc),
        created_date=datetime.now(timezone.utc),
        connection_string=key_data.get('connection_string'),
        status='active',
        subscription_link=key_data.get('subscription_link'),
        provision_mode=provision_mode,
        user_id=user_id,
        key_id=key_id,
    )
    
    has_token2 = '/auth/' in test_text2
    print(f"   Ссылка содержит /auth/: {has_token2}")
    
    if has_token2:
        match = re.search(r'href="([^"]+)"', test_text2)
        if match:
            url = match.group(1)
            print(f"   ✅ URL: {url}")
    
    return has_token and has_token2

def main():
    """Основная функция тестирования"""
    print("\n" + "=" * 60)
    print("ТЕСТИРОВАНИЕ ФУНКЦИОНАЛА ТОКЕНА ЛИЧНОГО КАБИНЕТА")
    print("=" * 60)
    
    try:
        # Тест 1: Создание токена
        result = test_token_creation()
        if not result:
            print("\n❌ Тест создания токена провален")
            return
        
        success, user_id, key_id, token = result
        
        # Тест 2: Генерация ссылки
        link_result = test_link_generation(user_id, key_id, token)
        
        print("\n" + "=" * 60)
        print("РЕЗУЛЬТАТЫ ТЕСТИРОВАНИЯ")
        print("=" * 60)
        
        if success and link_result:
            print("✅ Все тесты пройдены успешно!")
            print(f"✅ Токен создан: {token[:40]}...")
            print(f"✅ Ссылка содержит токен")
        else:
            print("❌ Некоторые тесты провалены")
            if not success:
                print("   - Создание токена")
            if not link_result:
                print("   - Генерация ссылки")
        
    except Exception as e:
        print(f"\n❌ Ошибка при тестировании: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()

