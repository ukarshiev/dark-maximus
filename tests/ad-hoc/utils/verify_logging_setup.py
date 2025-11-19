# -*- coding: utf-8 -*-
"""
Проверка настройки логирования для отслеживания создания ключей

Проверяет, что все необходимые логи будут записаны при создании ключа
"""

import sys
from pathlib import Path
import inspect

sys.path.insert(0, str(Path(__file__).parent.parent))

# Импортируем модули для проверки
from src.shop_bot.data_manager import database
from src.shop_bot.bot import handlers


def verify_logging_points():
    """Проверяет наличие точек логирования"""
    print("=" * 60)
    print("ПРОВЕРКА ТОЧЕК ЛОГИРОВАНИЯ")
    print("=" * 60 + "\n")
    
    checks = []
    
    # 1. Проверка логирования в get_next_key_number
    print("1. Проверка логирования в get_next_key_number:")
    source = inspect.getsource(database.get_next_key_number)
    has_logging = 'logging.info' in source or 'logging.warning' in source
    checks.append(("get_next_key_number", has_logging))
    print(f"   {'✓' if has_logging else '❌'} Логирование: {'найдено' if has_logging else 'не найдено'}")
    
    # 2. Проверка логирования в add_new_key при создании
    print("\n2. Проверка логирования в add_new_key (INSERT):")
    source = inspect.getsource(database.add_new_key)
    has_insert_logging = 'Inserting new key' in source or 'Successfully created new key' in source
    checks.append(("add_new_key (INSERT)", has_insert_logging))
    print(f"   {'✓' if has_insert_logging else '❌'} Логирование INSERT: {'найдено' if has_insert_logging else 'не найдено'}")
    
    # 3. Проверка логирования IntegrityError в add_new_key
    print("\n3. Проверка логирования IntegrityError в add_new_key:")
    has_integrity_logging = 'IntegrityError' in source and 'logging.warning' in source
    checks.append(("add_new_key (IntegrityError)", has_integrity_logging))
    print(f"   {'✓' if has_integrity_logging else '❌'} Логирование IntegrityError: {'найдено' if has_integrity_logging else 'не найдено'}")
    
    # 4. Проверка логирования в process_successful_payment
    print("\n4. Проверка логирования в process_successful_payment:")
    source = inspect.getsource(handlers.process_successful_payment)
    has_payment_logging = 'PAYMENT_PROCESSING' in source or 'key_number' in source
    checks.append(("process_successful_payment", has_payment_logging))
    print(f"   {'✓' if has_payment_logging else '❌'} Логирование: {'найдено' if has_payment_logging else 'не найдено'}")
    
    # 5. Проверка использования сохраненного key_number
    print("\n5. Проверка использования сохраненного key_number:")
    has_saved_key_number = 'saved key_number' in source.lower() or 'Using saved' in source
    checks.append(("saved key_number usage", has_saved_key_number))
    print(f"   {'✓' if has_saved_key_number else '❌'} Использование сохраненного номера: {'найдено' if has_saved_key_number else 'не найдено'}")
    
    # Итоги
    print("\n" + "=" * 60)
    print("ИТОГИ:")
    passed = sum(1 for _, check in checks if check)
    total = len(checks)
    
    for name, check in checks:
        status = "✓ ПРОЙДЕН" if check else "❌ ПРОВАЛЕН"
        print(f"   {status}: {name}")
    
    print(f"\nВсего: {passed}/{total} проверок пройдено")
    print("=" * 60 + "\n")
    
    return passed == total


if __name__ == "__main__":
    success = verify_logging_points()
    sys.exit(0 if success else 1)

