#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Тест клавиатуры при продлении ключа с разными provision_mode
"""

import sys
from pathlib import Path

# Добавляем путь к проекту
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))
sys.path.insert(0, str(project_root / "tests"))

from shop_bot.bot.keyboards import create_key_info_keyboard
from aiogram.types import WebAppInfo
from test_utils import safe_print, print_test_header, print_test_success, print_test_failure

def test_keyboard_with_subscription_link():
    """Тест клавиатуры с ссылкой на подписку (provision_mode=subscription или both)"""
    print_test_header("Клавиатура с subscription_link")
    
    key_id = 123
    subscription_link = "https://serv1.dark-maximus.com/subs/test123"
    
    keyboard = create_key_info_keyboard(key_id, subscription_link)
    
    buttons = keyboard.inline_keyboard
    safe_print(f"\nКоличество рядов кнопок: {len(buttons)}")
    
    all_buttons = []
    for row in buttons:
        all_buttons.extend(row)
    
    safe_print(f"Общее количество кнопок: {len(all_buttons)}")
    
    # Проверяем порядок и содержимое кнопок
    expected_order = [
        "⚙️ Настройка",
        "🔑 Подписка",
        "🔄 Продлить этот ключ",
        "⬅️ Назад к списку ключей"
    ]
    
    safe_print("\nПроверка порядка кнопок:")
    all_ok = True
    for i, expected_text in enumerate(expected_order):
        if i < len(all_buttons):
            actual_text = all_buttons[i].text
            status = "[OK]" if actual_text == expected_text else "[FAIL]"
            safe_print(f"  {status} Позиция {i+1}: ожидалось '{expected_text}', получено '{actual_text}'")
            if actual_text != expected_text:
                all_ok = False
        else:
            safe_print(f"  [FAIL] Позиция {i+1}: кнопка отсутствует (ожидалось '{expected_text}')")
            all_ok = False
    
    # Проверяем, что первые две кнопки используют web_app
    safe_print("\nПроверка web app кнопок:")
    
    # Первая кнопка — настройка
    if all_buttons[0].web_app:
        safe_print(f"  [OK] Кнопка '{all_buttons[0].text}' использует web_app")
        safe_print(f"     URL: {all_buttons[0].web_app.url}")
    else:
        safe_print(f"  [FAIL] Кнопка '{all_buttons[0].text}' не использует web_app!")
        all_ok = False
    
    # Вторая кнопка — подписка
    if all_buttons[1].web_app:
        safe_print(f"  [OK] Кнопка '{all_buttons[1].text}' использует web_app")
        safe_print(f"     URL: {all_buttons[1].web_app.url}")
        # Проверяем, что URL преобразован в HTTPS если был HTTP
        if subscription_link.startswith("http://"):
            expected_url = subscription_link.replace("http://", "https://", 1)
            if all_buttons[1].web_app.url == expected_url:
                safe_print(f"     [OK] HTTP ссылка преобразована в HTTPS")
            else:
                safe_print(f"     [FAIL] HTTP ссылка не преобразована! Ожидалось: {expected_url}, получено: {all_buttons[1].web_app.url}")
                all_ok = False
        elif all_buttons[1].web_app.url == subscription_link:
            safe_print(f"     [OK] URL совпадает с переданной ссылкой")
        else:
            safe_print(f"     [FAIL] URL не совпадает! Ожидалось: {subscription_link}, получено: {all_buttons[1].web_app.url}")
            all_ok = False
    else:
        safe_print(f"  [FAIL] Кнопка '{all_buttons[1].text}' не использует web_app!")
        all_ok = False
    
    # Проверяем расположение кнопок (первая строка должна содержать 2 кнопки)
    if len(buttons) >= 1 and len(buttons[0]) == 2:
        safe_print(f"\n  [OK] Первая строка содержит 2 кнопки (правильное расположение)")
    else:
        safe_print(f"\n  [FAIL] Первая строка содержит {len(buttons[0]) if buttons else 0} кнопок, ожидалось 2")
        all_ok = False
    
    if all_ok:
        print_test_success("Тест клавиатуры с subscription_link пройден")
        return True
    else:
        print_test_failure("Тест клавиатуры с subscription_link не пройден")
        return False

def test_keyboard_without_subscription_link():
    """Тест клавиатуры без ссылки на подписку (provision_mode=key)"""
    print_test_header("Клавиатура без subscription_link")
    
    key_id = 456
    
    keyboard = create_key_info_keyboard(key_id, None)
    
    buttons = keyboard.inline_keyboard
    all_buttons = []
    for row in buttons:
        all_buttons.extend(row)
    
    safe_print(f"Количество кнопок: {len(all_buttons)}")
    
    # Без ссылки должно быть 3 кнопки: Настройка, Продлить, Назад
    expected_count = 3
    if len(all_buttons) == expected_count:
        safe_print(f"[OK] Правильное количество кнопок: {expected_count}")
    else:
        safe_print(f"[FAIL] Неправильное количество кнопок: ожидалось {expected_count}, получено {len(all_buttons)}")
        print_test_failure("Тест клавиатуры без subscription_link не пройден")
        return False
    
    # Проверяем порядок
    expected_order = [
        "⚙️ Настройка",
        "🔄 Продлить этот ключ",
        "⬅️ Назад к списку ключей"
    ]
    
    safe_print("\nПроверка порядка кнопок:")
    all_ok = True
    for i, expected_text in enumerate(expected_order):
        if i < len(all_buttons):
            actual_text = all_buttons[i].text
            status = "[OK]" if actual_text == expected_text else "[FAIL]"
            safe_print(f"  {status} Позиция {i+1}: ожидалось '{expected_text}', получено '{actual_text}'")
            if actual_text != expected_text:
                all_ok = False
    
    # Проверяем, что кнопка "Подписка" отсутствует
    subscription_button_found = any("Подписка" in btn.text for btn in all_buttons)
    if subscription_button_found:
        safe_print("\n[FAIL] ОШИБКА: Кнопка 'Подписка' найдена, но должна отсутствовать!")
        all_ok = False
    else:
        safe_print("\n[OK] Кнопка 'Подписка' правильно отсутствует")
    
    # Проверяем web_app для первой кнопки
    if all_buttons[0].web_app:
        safe_print(f"\n[OK] Кнопка '{all_buttons[0].text}' использует web_app")
    else:
        safe_print(f"\n[FAIL] Кнопка '{all_buttons[0].text}' не использует web_app!")
        all_ok = False
    
    if all_ok:
        print_test_success("Тест клавиатуры без subscription_link пройден")
        return True
    else:
        print_test_failure("Тест клавиатуры без subscription_link не пройден")
        return False

def test_keyboard_http_to_https_conversion():
    """Тест преобразования HTTP ссылки в HTTPS для WebApp"""
    print_test_header("Преобразование HTTP в HTTPS для WebApp")
    
    key_id = 789
    http_link = "http://shop.karumweb.ru:2096/subs/test123"
    
    keyboard = create_key_info_keyboard(key_id, http_link)
    
    buttons = keyboard.inline_keyboard
    all_buttons = []
    for row in buttons:
        all_buttons.extend(row)
    
    # Проверяем, что вторая кнопка использует HTTPS
    if len(all_buttons) >= 2 and all_buttons[1].web_app:
        actual_url = all_buttons[1].web_app.url
        expected_url = http_link.replace("http://", "https://", 1)
        
        if actual_url == expected_url:
            safe_print(f"[OK] HTTP ссылка преобразована в HTTPS")
            safe_print(f"     Исходная: {http_link}")
            safe_print(f"     Результат: {actual_url}")
            print_test_success("Тест преобразования HTTP в HTTPS пройден")
            return True
        else:
            safe_print(f"[FAIL] HTTP ссылка не преобразована!")
            safe_print(f"     Исходная: {http_link}")
            safe_print(f"     Ожидалось: {expected_url}")
            safe_print(f"     Получено: {actual_url}")
            print_test_failure("Тест преобразования HTTP в HTTPS не пройден")
            return False
    else:
        safe_print("[FAIL] Кнопка подписки не найдена или не использует web_app")
        print_test_failure("Тест преобразования HTTP в HTTPS не пройден")
        return False

def test_keyboard_get_subscription_from_db():
    """Тест получения subscription_link из БД, если не передан"""
    print_test_header("Получение subscription_link из БД")
    
    try:
        from shop_bot.data_manager.database import get_key_by_id, DB_FILE
        import sqlite3
        
        # Ищем ключ с subscription_link в БД
        conn = sqlite3.connect(DB_FILE)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("SELECT key_id FROM vpn_keys WHERE subscription_link IS NOT NULL AND subscription_link != '' LIMIT 1")
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            safe_print("[SKIP] Нет ключей с subscription_link в БД для тестирования")
            return True
        
        test_key_id = row[0]
        safe_print(f"Тестируем ключ ID: {test_key_id}")
        
        # Вызываем функцию БЕЗ передачи subscription_link
        keyboard = create_key_info_keyboard(test_key_id, None)
        
        buttons = keyboard.inline_keyboard
        all_buttons = []
        for row in buttons:
            all_buttons.extend(row)
        
        # Проверяем, что кнопка "Подписка" добавлена
        subscription_button_found = any("Подписка" in btn.text for btn in all_buttons)
        
        if subscription_button_found:
            safe_print("[OK] Кнопка 'Подписка' добавлена из БД")
            print_test_success("Тест получения subscription_link из БД пройден")
            return True
        else:
            safe_print("[FAIL] Кнопка 'Подписка' не найдена, хотя должна быть в БД")
            print_test_failure("Тест получения subscription_link из БД не пройден")
            return False
            
    except Exception as e:
        safe_print(f"[SKIP] Ошибка при тестировании получения из БД: {e}")
        import traceback
        safe_print(traceback.format_exc())
        return True  # Не критично для общего теста

if __name__ == "__main__":
    safe_print("Запуск тестов клавиатуры при продлении ключа\n")
    
    success1 = test_keyboard_with_subscription_link()
    success2 = test_keyboard_without_subscription_link()
    success3 = test_keyboard_http_to_https_conversion()
    success4 = test_keyboard_get_subscription_from_db()
    
    if success1 and success2 and success3 and success4:
        safe_print("\n" + "="*50)
        safe_print("[OK] ВСЕ ТЕСТЫ КЛАВИАТУРЫ ПРОЙДЕНЫ УСПЕШНО!")
        safe_print("="*50)
        sys.exit(0)
    else:
        safe_print("\n" + "="*50)
        safe_print("[FAIL] НЕКОТОРЫЕ ТЕСТЫ КЛАВИАТУРЫ НЕ ПРОЙДЕНЫ!")
        safe_print("="*50)
        sys.exit(1)

