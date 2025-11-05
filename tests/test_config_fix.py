# -*- coding: utf-8 -*-
"""
Тестовый скрипт для проверки исправления в config.py
Проверяет, что функция get_status_icon_and_text доступна без импорта внутри get_key_info_text
"""

import sys
import io
from pathlib import Path

# Устанавливаем UTF-8 кодировку для вывода
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# Добавляем путь к корню проекта
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from datetime import datetime, timezone, timedelta
from shop_bot.config import get_key_info_text, get_status_icon_and_text


def test_get_status_icon_and_text():
    """Тест функции get_status_icon_and_text напрямую"""
    print("=" * 60)
    print("Тест 1: Проверка функции get_status_icon_and_text")
    print("=" * 60)
    
    test_cases = [
        ('trial-active', ('✅', 'Пробный активный')),
        ('trial-ended', ('❌', 'Пробный закончился')),
        ('pay-active', ('✅', 'Платный активный')),
        ('pay-ended', ('❌', 'Платный закончился')),
        ('deactivate', ('❌', 'Деактивирован')),
        ('unknown-status', ('❓', 'Неизвестный статус')),
    ]
    
    for status, expected in test_cases:
        icon, text = get_status_icon_and_text(status)
        assert (icon, text) == expected, f"Ожидалось {expected}, получено ({icon}, {text})"
        status_ok = "OK" if (icon, text) == expected else "FAIL"
        print(f"[{status_ok}] {status:20} -> {icon} {text}")
    
    print("\n[OK] Все тесты функции get_status_icon_and_text пройдены!\n")


def test_get_key_info_text_with_status():
    """Тест функции get_key_info_text с различными статусами"""
    print("=" * 60)
    print("Тест 2: Проверка функции get_key_info_text с разными статусами")
    print("=" * 60)
    
    # Создаём тестовые даты
    now = datetime.now(timezone.utc)
    created_date = now - timedelta(days=30)
    expiry_date = now + timedelta(days=10)
    
    test_key_number = 1
    test_connection_string = "vless://test-key-string"
    
    test_statuses = [
        ('trial-active', 'trial-active'),
        ('pay-active', 'pay-active'),
        ('deactivate', 'deactivate'),
        (None, None),  # Нет статуса
    ]
    
    for status, expected_status in test_statuses:
        try:
            result = get_key_info_text(
                key_number=test_key_number,
                expiry_date=expiry_date,
                created_date=created_date,
                connection_string=test_connection_string,
                status=status,
                provision_mode='key'
            )
            
            # Проверяем, что результат содержит ожидаемый текст
            assert "🔑 Информация о ключе" in result, "Результат должен содержать заголовок"
            assert test_connection_string in result, "Результат должен содержать ключ"
            
            # Проверяем статус в результате
            if expected_status == 'trial-active':
                assert "Пробный активный" in result or "✅" in result
            elif expected_status == 'pay-active':
                assert "Платный активный" in result or "✅" in result
            elif expected_status == 'deactivate':
                assert "Деактивирован" in result or "❌" in result
            elif expected_status is None:
                assert "Статус неизвестен" in result or "❓" in result
            
            print(f"[OK] Статус '{status}' обработан корректно")
            print(f"   Длина результата: {len(result)} символов")
            
        except Exception as e:
            print(f"[FAIL] Ошибка при обработке статуса '{status}': {e}")
            raise
    
    print("\n[OK] Все тесты функции get_key_info_text пройдены!\n")


def test_get_key_info_text_expired():
    """Тест функции get_key_info_text с истёкшим ключом"""
    print("=" * 60)
    print("Тест 3: Проверка функции get_key_info_text с истёкшим ключом")
    print("=" * 60)
    
    # Создаём тестовые даты (ключ истёк)
    now = datetime.now(timezone.utc)
    created_date = now - timedelta(days=30)
    expiry_date = now - timedelta(days=1)  # Истёк вчера
    
    result = get_key_info_text(
        key_number=1,
        expiry_date=expiry_date,
        created_date=created_date,
        connection_string="vless://expired-key",
        status='pay-active',  # Даже если в БД активный, но время истекло
        provision_mode='key'
    )
    
    # Проверяем, что статус показывает "Истёк"
    assert "Истёк" in result or "❌" in result, "Истёкший ключ должен показывать статус 'Истёк'"
    print("[OK] Истёкший ключ корректно обработан")
    print(f"   Длина результата: {len(result)} символов")
    print("\n[OK] Все тесты пройдены успешно!\n")


def main():
    """Запуск всех тестов"""
    print("\n" + "=" * 60)
    print("ТЕСТИРОВАНИЕ ИСПРАВЛЕНИЯ В config.py")
    print("Проверка доступности get_status_icon_and_text без импорта")
    print("=" * 60 + "\n")
    
    try:
        # Тест 1: Прямой вызов get_status_icon_and_text
        test_get_status_icon_and_text()
        
        # Тест 2: Использование внутри get_key_info_text
        test_get_key_info_text_with_status()
        
        # Тест 3: Истёкший ключ
        test_get_key_info_text_expired()
        
        print("=" * 60)
        print("[SUCCESS] ВСЕ ТЕСТЫ ПРОЙДЕНЫ УСПЕШНО!")
        print("[SUCCESS] Исправление работает корректно!")
        print("=" * 60)
        return 0
        
    except Exception as e:
        print("=" * 60)
        print(f"[ERROR] ОШИБКА ПРИ ТЕСТИРОВАНИИ: {e}")
        print("=" * 60)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())

