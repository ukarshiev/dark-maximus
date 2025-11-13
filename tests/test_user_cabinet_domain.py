#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Тест функции get_user_cabinet_domain и логики генерации ссылок"""

import sys
from pathlib import Path
from datetime import datetime, timezone

# Добавляем путь к проекту
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from shop_bot.data_manager.database import update_setting, get_setting
from shop_bot.config import get_user_cabinet_domain, get_purchase_success_text

def test_empty_domain():
    """Тест: пустой домен не должен показывать блок с кабинетом"""
    print("Тест 1: Пустой домен")
    update_setting('user_cabinet_domain', '')
    domain = get_user_cabinet_domain()
    assert domain is None, f"Ожидался None, получен: {domain}"
    
    text = get_purchase_success_text(
        'new', 1, datetime.now(timezone.utc),
        'test-key', 'test-link', 'key',
        cabinet_token='test-token-123'
    )
    
    has_cabinet = 'личный кабинет' in text.lower()
    has_fallback = 'test-link' in text
    
    assert not has_cabinet, "Блок с личным кабинетом не должен показываться при пустом домене"
    assert has_fallback, "Fallback ссылка должна показываться всегда"
    print("✓ Тест пройден: блок с кабинетом не показывается, fallback работает")

def test_localhost_domain():
    """Тест: localhost домен должен работать"""
    print("\nТест 2: Домен localhost:3003")
    update_setting('user_cabinet_domain', 'http://localhost:3003')
    domain = get_user_cabinet_domain()
    assert domain == 'http://localhost:3003', f"Ожидался 'http://localhost:3003', получен: {domain}"
    
    text = get_purchase_success_text(
        'new', 1, datetime.now(timezone.utc),
        'test-key', 'test-link', 'key',
        cabinet_token='test-token-123'
    )
    
    has_cabinet = 'личный кабинет' in text.lower()
    has_localhost = 'localhost:3003' in text
    has_token = 'test-token-123' in text
    
    assert has_cabinet, "Блок с личным кабинетом должен показываться"
    assert has_localhost, "Домен localhost:3003 должен быть в тексте"
    assert has_token, "Токен должен быть в ссылке"
    print("✓ Тест пройден: блок с кабинетом показывается с правильным доменом")

def test_domain_normalization():
    """Тест: нормализация домена"""
    print("\nТест 3: Нормализация домена")
    
    # Тест без протокола
    update_setting('user_cabinet_domain', 'app.dark-maximus.com')
    domain = get_user_cabinet_domain()
    assert domain == 'https://app.dark-maximus.com', f"Ожидался 'https://app.dark-maximus.com', получен: {domain}"
    print("✓ Тест пройден: протокол добавлен автоматически")
    
    # Тест со слэшем в конце
    update_setting('user_cabinet_domain', 'http://localhost:3003/')
    domain = get_user_cabinet_domain()
    assert domain == 'http://localhost:3003', f"Ожидался 'http://localhost:3003', получен: {domain}"
    print("✓ Тест пройден: слэш в конце удален")

def test_no_token():
    """Тест: без токена блок не показывается"""
    print("\nТест 4: Без токена")
    update_setting('user_cabinet_domain', 'http://localhost:3003')
    
    text = get_purchase_success_text(
        'new', 1, datetime.now(timezone.utc),
        'test-key', 'test-link', 'key',
        cabinet_token=None
    )
    
    has_cabinet = 'личный кабинет' in text.lower()
    assert not has_cabinet, "Блок с личным кабинетом не должен показываться без токена"
    print("✓ Тест пройден: блок не показывается без токена")

if __name__ == '__main__':
    try:
        test_empty_domain()
        test_localhost_domain()
        test_domain_normalization()
        test_no_token()
        print("\n✅ Все тесты пройдены успешно!")
    except AssertionError as e:
        print(f"\n❌ Тест провален: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Ошибка при выполнении теста: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

