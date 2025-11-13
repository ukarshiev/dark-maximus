#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Тест клавиатуры с web app кнопками для ключа
"""

import sys
from pathlib import Path

# Добавляем путь к проекту
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))
sys.path.insert(0, str(project_root / "tests"))

from shop_bot.bot.keyboards import create_key_info_keyboard
from aiogram.types import WebAppInfo
from test_utils import safe_print

def test_keyboard_with_subscription_link():
    """Тест клавиатуры с ссылкой на подписку"""
    safe_print("=== Тест клавиатуры с ссылкой на подписку ===")
    
    key_id = 123
    subscription_link = "http://shop.karumweb.ru:2096/subs/5243157300-k4rum"
    
    keyboard = create_key_info_keyboard(key_id, subscription_link)
    
    # Проверяем количество кнопок (должно быть 4: Настройка, Подписка, Продлить, Назад)
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
    for i, expected_text in enumerate(expected_order):
        if i < len(all_buttons):
            actual_text = all_buttons[i].text
            status = "[OK]" if actual_text == expected_text else "[FAIL]"
            safe_print(f"  {status} Позиция {i+1}: ожидалось '{expected_text}', получено '{actual_text}'")
        else:
            safe_print(f"  [FAIL] Позиция {i+1}: кнопка отсутствует (ожидалось '{expected_text}')")
    
    # Проверяем, что кнопка "Инструкции" отсутствует
    instructions_found = any("Инструкции" in btn.text for btn in all_buttons)
    if instructions_found:
        safe_print("\n[FAIL] ОШИБКА: Кнопка 'Инструкции' найдена, но должна быть скрыта!")
        return False
    else:
        safe_print("\n[OK] Кнопка 'Инструкции' правильно скрыта")
    
    # Проверяем, что первые две кнопки используют web_app
    safe_print("\nПроверка web app кнопок:")
    
    # Первая кнопка — настройка
    if all_buttons[0].web_app:
        safe_print(f"  [OK] Кнопка '{all_buttons[0].text}' использует web_app")
        safe_print(f"     URL: {all_buttons[0].web_app.url}")
    else:
        safe_print(f"  [FAIL] Кнопка '{all_buttons[0].text}' не использует web_app!")
        return False
    
    # Вторая кнопка — подписка
    if all_buttons[1].web_app:
        safe_print(f"  [OK] Кнопка '{all_buttons[1].text}' использует web_app")
        safe_print(f"     URL: {all_buttons[1].web_app.url}")
        if all_buttons[1].web_app.url == subscription_link:
            safe_print(f"     [OK] URL совпадает с переданной ссылкой")
        else:
            safe_print(f"     [FAIL] URL не совпадает! Ожидалось: {subscription_link}")
            return False
    else:
        safe_print(f"  [FAIL] Кнопка '{all_buttons[1].text}' не использует web_app!")
        return False
    
    # Проверяем, что остальные кнопки используют callback_data
    safe_print("\nПроверка callback кнопок:")
    if all_buttons[2].callback_data:
        safe_print(f"  [OK] Кнопка '{all_buttons[2].text}' использует callback_data: {all_buttons[2].callback_data}")
    else:
        safe_print(f"  [FAIL] Кнопка '{all_buttons[2].text}' не использует callback_data!")
        return False
    
    if all_buttons[3].callback_data:
        safe_print(f"  [OK] Кнопка '{all_buttons[3].text}' использует callback_data: {all_buttons[3].callback_data}")
    else:
        safe_print(f"  [FAIL] Кнопка '{all_buttons[3].text}' не использует callback_data!")
        return False
    
    safe_print("\n[OK] Все проверки пройдены успешно!")
    return True

def test_keyboard_without_subscription_link():
    """Тест клавиатуры без ссылки на подписку"""
    safe_print("\n=== Тест клавиатуры без ссылки на подписку ===")
    
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
        return False
    
    # Проверяем порядок
    expected_order = [
        "⚙️ Настройка",
        "🔄 Продлить этот ключ",
        "⬅️ Назад к списку ключей"
    ]
    
    safe_print("\nПроверка порядка кнопок:")
    for i, expected_text in enumerate(expected_order):
        if i < len(all_buttons):
            actual_text = all_buttons[i].text
            status = "[OK]" if actual_text == expected_text else "[FAIL]"
            safe_print(f"  {status} Позиция {i+1}: ожидалось '{expected_text}', получено '{actual_text}'")
            if actual_text != expected_text:
                return False
    
    # Проверяем, что кнопка "Инструкции" отсутствует
    instructions_found = any("Инструкции" in btn.text for btn in all_buttons)
    if instructions_found:
        safe_print("\n[FAIL] ОШИБКА: Кнопка 'Инструкции' найдена, но должна быть скрыта!")
        return False
    else:
        safe_print("\n[OK] Кнопка 'Инструкции' правильно скрыта")
    
    # Проверяем web_app для первой кнопки
    if all_buttons[0].web_app:
        safe_print(f"\n[OK] Кнопка '{all_buttons[0].text}' использует web_app")
    else:
        safe_print(f"\n[FAIL] Кнопка '{all_buttons[0].text}' не использует web_app!")
        return False
    
    safe_print("\n[OK] Все проверки пройдены успешно!")
    return True

if __name__ == "__main__":
    safe_print("Запуск тестов клавиатуры с web app кнопками\n")
    
    success1 = test_keyboard_with_subscription_link()
    success2 = test_keyboard_without_subscription_link()
    
    if success1 and success2:
        safe_print("\n" + "="*50)
        safe_print("[OK] ВСЕ ТЕСТЫ ПРОЙДЕНЫ УСПЕШНО!")
        safe_print("="*50)
        sys.exit(0)
    else:
        safe_print("\n" + "="*50)
        safe_print("[FAIL] НЕКОТОРЫЕ ТЕСТЫ НЕ ПРОЙДЕНЫ!")
        safe_print("="*50)
        sys.exit(1)

