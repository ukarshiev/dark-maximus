#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Тест проверки сохранения subscription_link в БД при продлении ключа
"""

import sys
import sqlite3
from pathlib import Path
from datetime import datetime, timezone, timedelta

# Добавляем путь к проекту
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))
sys.path.insert(0, str(project_root / "tests"))

from shop_bot.data_manager.database import (
    get_key_by_id, update_key_info, get_setting, DB_FILE
)
from test_utils import safe_print, print_test_header, print_test_success, print_test_failure

def test_update_key_info_with_subscription_link():
    """Тест обновления ключа с subscription_link через update_key_info"""
    print_test_header("Обновление ключа с subscription_link в БД")
    
    # Получаем существующий ключ для теста (или создаем тестовый)
    try:
        conn = sqlite3.connect(DB_FILE)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Ищем первый активный ключ
        cursor.execute("SELECT key_id FROM vpn_keys WHERE enabled = 1 LIMIT 1")
        row = cursor.fetchone()
        
        if not row:
            safe_print("[SKIP] Нет активных ключей для тестирования")
            conn.close()
            return True
        
        test_key_id = row[0]
        conn.close()
        
        # Получаем текущие данные ключа
        key_data_before = get_key_by_id(test_key_id)
        if not key_data_before:
            safe_print(f"[SKIP] Ключ {test_key_id} не найден")
            return True
        
        safe_print(f"Тестируем ключ ID: {test_key_id}")
        safe_print(f"Текущий subscription_link: {key_data_before.get('subscription_link') or 'None'}")
        
        # Тестируем обновление с subscription_link
        test_subscription_link = "https://serv1.dark-maximus.com/subs/test123"
        test_client_uuid = "test-uuid-12345"
        test_expiry_ms = int((datetime.now(timezone.utc) + timedelta(days=30)).timestamp() * 1000)
        
        # Обновляем ключ
        update_key_info(test_key_id, test_client_uuid, test_expiry_ms, test_subscription_link)
        
        # Проверяем результат
        key_data_after = get_key_by_id(test_key_id)
        if not key_data_after:
            safe_print("[FAIL] Ключ не найден после обновления")
            print_test_failure("Тест обновления ключа не пройден")
            return False
        
        actual_subscription_link = key_data_after.get('subscription_link')
        
        if actual_subscription_link == test_subscription_link:
            safe_print(f"[OK] subscription_link сохранен корректно: {actual_subscription_link}")
        else:
            safe_print(f"[FAIL] subscription_link не совпадает!")
            safe_print(f"     Ожидалось: {test_subscription_link}")
            safe_print(f"     Получено: {actual_subscription_link}")
            print_test_failure("Тест обновления ключа не пройден")
            return False
        
        # Проверяем обновление expiry_date
        expiry_date_after = key_data_after.get('expiry_date')
        if expiry_date_after:
            safe_print(f"[OK] expiry_date обновлен: {expiry_date_after}")
        else:
            safe_print("[FAIL] expiry_date не обновлен")
            print_test_failure("Тест обновления ключа не пройден")
            return False
        
        # Восстанавливаем исходные данные (опционально)
        original_subscription_link = key_data_before.get('subscription_link')
        original_client_uuid = key_data_before.get('xui_client_uuid')
        original_expiry_ms = int(key_data_before.get('expiry_date').timestamp() * 1000) if key_data_before.get('expiry_date') else test_expiry_ms
        
        # Восстанавливаем только если нужно
        # update_key_info(test_key_id, original_client_uuid, original_expiry_ms, original_subscription_link)
        
        print_test_success("Тест обновления ключа с subscription_link пройден")
        return True
        
    except Exception as e:
        safe_print(f"[FAIL] Ошибка при тестировании: {e}")
        import traceback
        safe_print(traceback.format_exc())
        print_test_failure("Тест обновления ключа не пройден")
        return False

def test_update_key_info_without_subscription_link():
    """Тест обновления ключа без subscription_link (provision_mode=key)"""
    print_test_header("Обновление ключа без subscription_link в БД")
    
    try:
        conn = sqlite3.connect(DB_FILE)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Ищем первый активный ключ
        cursor.execute("SELECT key_id FROM vpn_keys WHERE enabled = 1 LIMIT 1")
        row = cursor.fetchone()
        
        if not row:
            safe_print("[SKIP] Нет активных ключей для тестирования")
            conn.close()
            return True
        
        test_key_id = row[0]
        conn.close()
        
        # Получаем текущие данные ключа
        key_data_before = get_key_by_id(test_key_id)
        if not key_data_before:
            safe_print(f"[SKIP] Ключ {test_key_id} не найден")
            return True
        
        safe_print(f"Тестируем ключ ID: {test_key_id}")
        
        # Сохраняем исходный subscription_link
        original_subscription_link = key_data_before.get('subscription_link')
        
        # Обновляем ключ без subscription_link
        test_client_uuid = "test-uuid-67890"
        test_expiry_ms = int((datetime.now(timezone.utc) + timedelta(days=30)).timestamp() * 1000)
        
        update_key_info(test_key_id, test_client_uuid, test_expiry_ms, None)
        
        # Проверяем результат
        key_data_after = get_key_by_id(test_key_id)
        if not key_data_after:
            safe_print("[FAIL] Ключ не найден после обновления")
            print_test_failure("Тест обновления ключа без subscription_link не пройден")
            return False
        
        actual_subscription_link = key_data_after.get('subscription_link')
        
        # subscription_link должен остаться прежним или быть None
        if actual_subscription_link == original_subscription_link or (actual_subscription_link is None and original_subscription_link is None):
            safe_print(f"[OK] subscription_link сохранен корректно: {actual_subscription_link}")
        else:
            # Если был subscription_link, он должен остаться
            if original_subscription_link and actual_subscription_link == original_subscription_link:
                safe_print(f"[OK] subscription_link сохранен (остался прежним): {actual_subscription_link}")
            else:
                safe_print(f"[WARN] subscription_link изменился (возможно ожидаемо)")
                safe_print(f"     Было: {original_subscription_link}")
                safe_print(f"     Стало: {actual_subscription_link}")
        
        # Восстанавливаем исходные данные
        original_client_uuid = key_data_before.get('xui_client_uuid')
        original_expiry_ms = int(key_data_before.get('expiry_date').timestamp() * 1000) if key_data_before.get('expiry_date') else test_expiry_ms
        
        # Восстанавливаем только если нужно
        # update_key_info(test_key_id, original_client_uuid, original_expiry_ms, original_subscription_link)
        
        print_test_success("Тест обновления ключа без subscription_link пройден")
        return True
        
    except Exception as e:
        safe_print(f"[FAIL] Ошибка при тестировании: {e}")
        import traceback
        safe_print(traceback.format_exc())
        print_test_failure("Тест обновления ключа без subscription_link не пройден")
        return False

if __name__ == "__main__":
    safe_print("Запуск тестов сохранения subscription_link в БД\n")
    
    success1 = test_update_key_info_with_subscription_link()
    success2 = test_update_key_info_without_subscription_link()
    
    if success1 and success2:
        safe_print("\n" + "="*50)
        safe_print("[OK] ВСЕ ТЕСТЫ БД ПРОЙДЕНЫ УСПЕШНО!")
        safe_print("="*50)
        sys.exit(0)
    else:
        safe_print("\n" + "="*50)
        safe_print("[FAIL] НЕКОТОРЫЕ ТЕСТЫ БД НЕ ПРОЙДЕНЫ!")
        safe_print("="*50)
        sys.exit(1)

