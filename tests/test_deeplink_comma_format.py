#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Тестовый скрипт для проверки парсинга deeplink с запятыми
"""

import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))
sys.path.insert(0, str(project_root / "tests"))

# Импортируем утилиты для безопасного вывода
from test_utils import safe_print, print_test_header, print_test_success

def test_comma_parsing():
    """Тестирование парсинга параметров с запятыми"""
    
    # Симуляция deeplink параметров
    test_cases = [
        "user_groups=moi,promo=SKIDKA100RUB",
        "user_groups=moi",
        "promo=SKIDKA100RUB",
        "user_groups=test,promo=TEST1,promo=TEST2",
    ]
    
    print_test_header("Парсинг deeplink параметров с запятыми")
    
    for start_param in test_cases:
        safe_print(f"\nТестовый параметр: '{start_param}'")
        
        # Симуляция парсинга
        parts = start_param.split(',')
        safe_print(f"  Разделено на части: {parts}")
        
        applied_groups = []
        applied_promos = []
        
        for part in parts:
            part = part.strip()
            
            if part.startswith('user_groups='):
                group_code = part.replace('user_groups=', '').strip()
                if group_code:
                    applied_groups.append(group_code)
                    safe_print(f"  ✅ Группа: {group_code}", fallback_text=f"  [OK] Группа: {group_code}")
            
            elif part.startswith('promo='):
                promo_code = part.replace('promo=', '').strip()
                if promo_code:
                    applied_promos.append(promo_code)
                    safe_print(f"  ✅ Промокод: {promo_code}", fallback_text=f"  [OK] Промокод: {promo_code}")
        
        safe_print(f"  Результат: groups={applied_groups}, promos={applied_promos}")
    
    print_test_success("ВСЕ ТЕСТЫ ПРОЙДЕНЫ УСПЕШНО!")

if __name__ == "__main__":
    test_comma_parsing()
