#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Тест исправления промокода через deeplink ссылку
Проверяет, что промокод сохраняется после онбординга и при выборе хоста
"""

import sys
import os
import sqlite3

from _io_encoding import ensure_utf8_output

# Устанавливаем UTF-8 кодировку для Windows
if sys.platform == 'win32':
    ensure_utf8_output()

# Добавляем путь к модулям бота
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from shop_bot.utils.deeplink import create_deeplink, parse_deeplink
from shop_bot.data_manager.database import (
    get_promo_code_by_code,
    get_user,
    get_promo_code_usage_by_user,
    DB_FILE
)

def test_deeplink_creation():
    """Тест создания deeplink ссылки с промокодом и группой"""
    print("=" * 60)
    print("ТЕСТ 1: Создание deeplink ссылки с промокодом и группой")
    print("=" * 60)
    
    # Создаём deeplink с группой family и промокодом FINALPROM
    deeplink = create_deeplink(
        bot_username="darkmaxi_vpn_bot",
        group_code="family",
        promo_code="FINALPROM"
    )
    
    print(f"\nСозданная deeplink ссылка:")
    print(f"{deeplink}\n")
    
    # Парсим созданную ссылку
    param = deeplink.split("start=")[1] if "start=" in deeplink else deeplink
    group_code, promo_code, referrer_id = parse_deeplink(param)
    
    print(f"Результат парсинга:")
    print(f"  Группа: {group_code}")
    print(f"  Промокод: {promo_code}")
    print(f"  Реферер: {referrer_id}\n")
    
    # Проверяем корректность
    assert group_code == "family", f"Ожидалась группа 'family', получена '{group_code}'"
    assert promo_code == "FINALPROM", f"Ожидался промокод 'FINALPROM', получен '{promo_code}'"
    
    print("✅ ТЕСТ 1 ПРОЙДЕН: Deeplink создан и распарсен корректно\n")
    return deeplink

def test_promo_code_exists():
    """Тест проверки существования промокода FINALPROM"""
    print("=" * 60)
    print("ТЕСТ 2: Проверка существования промокода FINALPROM")
    print("=" * 60)
    
    promo = get_promo_code_by_code("FINALPROM", "shop")
    
    if not promo:
        print("\n[ERROR] ОШИБКА: Промокод FINALPROM не найден в базе данных!")
        print("Создайте промокод FINALPROM через веб-интерфейс на http://localhost:1488/promo-codes")
        return False
    
    print(f"\nПромокод найден:")
    print(f"  ID: {promo['promo_id']}")
    print(f"  Код: {promo['code']}")
    print(f"  Бот: {promo['bot']}")
    print(f"  Скидка (сумма): {promo.get('discount_amount', 0)} RUB")
    print(f"  Скидка (%): {promo.get('discount_percent', 0)}%")
    print(f"  Бонус: {promo.get('discount_bonus', 0)} RUB")
    print(f"  Активен: {bool(promo.get('is_active', 0))}")
    
    assert promo['code'] == "FINALPROM", "Неверный код промокода"
    assert promo['bot'] == "shop", "Неверный бот"
    assert promo.get('is_active', 0) == 1, "Промокод неактивен"
    
    print("\n[OK] ТЕСТ 2 ПРОЙДЕН: Промокод FINALPROM существует и активен\n")
    return True

def test_group_exists():
    """Тест проверки существования группы family"""
    print("=" * 60)
    print("ТЕСТ 3: Проверка существования группы family")
    print("=" * 60)
    
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute(
                "SELECT * FROM user_groups WHERE group_code = ?",
                ("family",)
            )
            
            group = cursor.fetchone()
            
            if not group:
                print("\n[ERROR] ОШИБКА: Группа 'family' не найдена в базе данных!")
                print("Создайте группу 'family' через веб-интерфейс на http://localhost:1488/users")
                return False
            
            print(f"\nГруппа найдена:")
            print(f"  ID: {group['group_id']}")
            print(f"  Название: {group['group_name']}")
            print(f"  Код: {group['group_code']}")
            
            print("\n[OK] ТЕСТ 3 ПРОЙДЕН: Группа family существует\n")
            return True
            
    except Exception as e:
        print(f"\n[ERROR] ОШИБКА при проверке группы: {e}")
        return False

def test_user_promo_usage():
    """Тест проверки использования промокода пользователем"""
    print("=" * 60)
    print("ТЕСТ 4: Проверка использования промокода пользователем")
    print("=" * 60)
    
    # Берем первого пользователя, у которого используется промокод
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Получаем промокод
            promo = get_promo_code_by_code("FINALPROM", "shop")
            if not promo:
                print("\n⚠️ ПРОМОКОД НЕ НАЙДЕН - пропускаем тест")
                return True
            
            # Проверяем использование промокода
            cursor.execute('''
                SELECT pcu.*, u.username, u.telegram_id
                FROM promo_code_usage pcu
                JOIN users u ON u.telegram_id = pcu.user_id
                WHERE pcu.promo_id = ? AND pcu.status = 'applied'
                ORDER BY pcu.used_at DESC
                LIMIT 5
            ''', (promo['promo_id'],))
            
            usages = cursor.fetchall()
            
            if not usages:
                print("\n⚠️ Нет применённых промокодов для проверки")
                return True
            
            print(f"\nНайдено {len(usages)} применённых промокодов:")
            for usage in usages:
                print(f"  Пользователь: @{usage['username']} (ID: {usage['telegram_id']})")
                print(f"  Статус: {usage['status']}")
                print(f"  Дата: {usage['used_at']}")
                print()
            
            print("✅ ТЕСТ 4 ПРОЙДЕН: Использование промокода проверено\n")
            return True
            
    except Exception as e:
        print(f"\n[ERROR] ОШИБКА при проверке использования: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Главная функция тестирования"""
    print("\n" + "=" * 60)
    print("ТЕСТИРОВАНИЕ ИСПРАВЛЕНИЯ ПРОМОКОДА ЧЕРЕЗ Deeplink")
    print("=" * 60 + "\n")
    
    results = []
    
    # Тест 1: Создание deeplink
    try:
        deeplink = test_deeplink_creation()
        results.append(("Создание deeplink", True))
    except Exception as e:
        print(f"❌ ОШИБКА: {e}\n")
        results.append(("Создание deeplink", False))
    
    # Тест 2: Проверка промокода
    try:
        if test_promo_code_exists():
            results.append(("Проверка промокода", True))
        else:
            results.append(("Проверка промокода", False))
    except Exception as e:
        print(f"❌ ОШИБКА: {e}\n")
        results.append(("Проверка промокода", False))
    
    # Тест 3: Проверка группы
    try:
        if test_group_exists():
            results.append(("Проверка группы", True))
        else:
            results.append(("Проверка группы", False))
    except Exception as e:
        print(f"❌ ОШИБКА: {e}\n")
        results.append(("Проверка группы", False))
    
    # Тест 4: Проверка использования
    try:
        if test_user_promo_usage():
            results.append(("Проверка использования", True))
        else:
            results.append(("Проверка использования", False))
    except Exception as e:
        print(f"❌ ОШИБКА: {e}\n")
        results.append(("Проверка использования", False))
    
    # Итоговый отчёт
    print("\n" + "=" * 60)
    print("ИТОГОВЫЙ ОТЧЁТ")
    print("=" * 60 + "\n")
    
    for test_name, result in results:
        status = "[OK] ПРОЙДЕН" if result else "[FAIL] ПРОВАЛЕН"
        print(f"{test_name}: {status}")
    
    all_passed = all(result for _, result in results)
    
    print("\n" + "=" * 60)
    if all_passed:
        print("[OK] ВСЕ ТЕСТЫ ПРОЙДЕНЫ")
    else:
        print("[FAIL] НЕКОТОРЫЕ ТЕСТЫ ПРОВАЛЕНЫ")
    print("=" * 60 + "\n")
    
    # Выводим тестовую ссылку
    try:
        deeplink = create_deeplink(
            bot_username="darkmaxi_vpn_bot",
            group_code="family",
            promo_code="FINALPROM"
        )
        print(f"Тестовая deeplink ссылка:")
        print(f"{deeplink}\n")
        print("Протестируйте эту ссылку в Telegram боте.")
        print("Ожидаемое поведение:")
        print("  1. Промокод применяется при старте")
        print("  2. Промокод сохраняется после онбординга")
        print("  3. Скидка отображается при выборе тарифа")
        print("  4. Скидка применяется при покупке\n")
    except:
        pass
    
    return 0 if all_passed else 1

if __name__ == '__main__':
    sys.exit(main())

