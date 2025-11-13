#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Тест постоянного токена для личного кабинета
"""

import sys
import os
from pathlib import Path

# Добавляем путь к проекту
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from shop_bot.data_manager.database import (
    get_or_create_permanent_token,
    get_permanent_token_by_key_id,
    validate_permanent_token,
    get_key_by_id,
    get_user_keys
)

def test_permanent_token():
    """Тестирование функций работы с постоянным токеном"""
    
    print("=" * 60)
    print("Тестирование постоянного токена для личного кабинета")
    print("=" * 60)
    
    # Тест 1: Создание токена для существующего ключа
    print("\n1. Тест создания токена для существующего ключа")
    print("-" * 60)
    
    # Получаем первого пользователя с ключами
    try:
        # Пробуем найти существующий ключ
        test_user_id = None
        test_key_id = None
        
        # Ищем активные ключи
        for user_id in range(1, 1000):  # Проверяем первые 1000 пользователей
            keys = get_user_keys(user_id)
            if keys:
                test_user_id = user_id
                test_key_id = keys[0]['key_id']
                break
        
        if not test_user_id or not test_key_id:
            print("⚠️  Не найдено активных ключей для тестирования")
            print("   Создайте тестовый ключ через бота")
            return False
        
        print(f"   Найден ключ: user_id={test_user_id}, key_id={test_key_id}")
        
        # Создаем токен
        token1 = get_or_create_permanent_token(test_user_id, test_key_id)
        print(f"   ✅ Токен создан: {token1[:20]}...")
        
        # Проверяем, что повторный вызов возвращает тот же токен
        token2 = get_or_create_permanent_token(test_user_id, test_key_id)
        if token1 == token2:
            print(f"   ✅ Токен постоянный (повторный вызов вернул тот же токен)")
        else:
            print(f"   ❌ ОШИБКА: Токены не совпадают!")
            return False
        
    except Exception as e:
        print(f"   ❌ Ошибка при создании токена: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Тест 2: Получение токена по key_id
    print("\n2. Тест получения токена по key_id")
    print("-" * 60)
    
    try:
        token_by_key = get_permanent_token_by_key_id(test_key_id)
        if token_by_key == token1:
            print(f"   ✅ Токен получен по key_id: {token_by_key[:20]}...")
        else:
            print(f"   ❌ ОШИБКА: Токены не совпадают!")
            return False
    except Exception as e:
        print(f"   ❌ Ошибка при получении токена по key_id: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Тест 3: Валидация токена
    print("\n3. Тест валидации токена")
    print("-" * 60)
    
    try:
        token_data = validate_permanent_token(token1)
        if token_data:
            print(f"   ✅ Токен валиден")
            print(f"   - user_id: {token_data.get('user_id')}")
            print(f"   - key_id: {token_data.get('key_id')}")
            print(f"   - access_count: {token_data.get('access_count')}")
            
            # Проверяем, что данные совпадают
            if token_data['user_id'] != test_user_id:
                print(f"   ❌ ОШИБКА: user_id не совпадает!")
                return False
            if token_data['key_id'] != test_key_id:
                print(f"   ❌ ОШИБКА: key_id не совпадает!")
                return False
        else:
            print(f"   ❌ ОШИБКА: Токен не прошел валидацию!")
            return False
    except Exception as e:
        print(f"   ❌ Ошибка при валидации токена: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Тест 4: Валидация несуществующего токена
    print("\n4. Тест валидации несуществующего токена")
    print("-" * 60)
    
    try:
        fake_token = "fake_token_12345"
        token_data = validate_permanent_token(fake_token)
        if token_data is None:
            print(f"   ✅ Несуществующий токен правильно отклонен")
        else:
            print(f"   ❌ ОШИБКА: Несуществующий токен прошел валидацию!")
            return False
    except Exception as e:
        print(f"   ❌ Ошибка при валидации несуществующего токена: {e}")
        return False
    
    # Тест 5: Проверка формирования ссылки
    print("\n5. Тест формирования ссылки на личный кабинет")
    print("-" * 60)
    
    try:
        from shop_bot.config import get_user_cabinet_domain
        
        cabinet_domain = get_user_cabinet_domain()
        if cabinet_domain:
            cabinet_url = f"{cabinet_domain}/auth/{token1}"
            print(f"   ✅ Ссылка сформирована: {cabinet_url}")
        else:
            print(f"   ⚠️  Домен личного кабинета не настроен")
    except Exception as e:
        print(f"   ❌ Ошибка при формировании ссылки: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    print("\n" + "=" * 60)
    print("✅ Все тесты пройдены успешно!")
    print("=" * 60)
    
    return True

if __name__ == "__main__":
    success = test_permanent_token()
    sys.exit(0 if success else 1)

