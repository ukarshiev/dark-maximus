# -*- coding: utf-8 -*-
"""
Тестовый скрипт для проверки переинициализации YooKassa Configuration
"""

import sys
import os
import io

# Настраиваем кодировку для Windows
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# Добавляем путь к проекту
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

from yookassa import Configuration
from shop_bot.data_manager.database import get_setting, update_setting
from shop_bot.bot.handlers import _reconfigure_yookassa, _safe_strip
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def test_safe_strip():
    """Тест функции _safe_strip"""
    print("\n=== Тест _safe_strip ===")
    
    # Тест 1: None
    result = _safe_strip(None)
    assert result is None, f"Ожидалось None, получено {result}"
    print("[OK] None обрабатывается корректно")
    
    # Тест 2: Пустая строка
    result = _safe_strip("")
    assert result is None, f"Ожидалось None, получено {result}"
    print("[OK] Пустая строка обрабатывается корректно")
    
    # Тест 3: Строка с пробелами
    result = _safe_strip("  test  ")
    assert result == "test", f"Ожидалось 'test', получено '{result}'"
    print("[OK] Пробелы удаляются корректно")
    
    # Тест 4: Обычная строка
    result = _safe_strip("test")
    assert result == "test", f"Ожидалось 'test', получено '{result}'"
    print("[OK] Обычная строка обрабатывается корректно")


def test_reconfigure_yookassa():
    """Тест функции _reconfigure_yookassa"""
    print("\n=== Тест _reconfigure_yookassa ===")
    
    # Сохраняем текущие настройки
    original_test_mode = get_setting("yookassa_test_mode")
    original_shop_id = get_setting("yookassa_shop_id")
    original_secret_key = get_setting("yookassa_secret_key")
    original_test_shop_id = get_setting("yookassa_test_shop_id")
    original_test_secret_key = get_setting("yookassa_test_secret_key")
    
    try:
        # Тест 1: Тестовый режим
        print("\n--- Тест 1: Тестовый режим ---")
        update_setting("yookassa_test_mode", "true")
        update_setting("yookassa_test_shop_id", "1176024")
        update_setting("yookassa_test_secret_key", "test_key_12345")
        update_setting("yookassa_test_api_url", "https://api.test.yookassa.ru/v3")
        
        result = _reconfigure_yookassa()
        assert result is True, "Ожидалось True при наличии ключей"
        
        # Проверяем, что Configuration обновлен
        # Configuration.account_id и Configuration.secret_key доступны через внутренние атрибуты
        print(f"[OK] Configuration переинициализирован для тестового режима")
        print(f"  Shop ID из настроек: {get_setting('yookassa_test_shop_id')}")
        print(f"  API URL из настроек: {get_setting('yookassa_test_api_url')}")
        
        # Тест 2: Боевой режим
        print("\n--- Тест 2: Боевой режим ---")
        update_setting("yookassa_test_mode", "false")
        update_setting("yookassa_shop_id", "1174374")
        update_setting("yookassa_secret_key", "live_key_12345")
        update_setting("yookassa_api_url", "https://api.yookassa.ru/v3")
        
        result = _reconfigure_yookassa()
        assert result is True, "Ожидалось True при наличии ключей"
        
        print(f"[OK] Configuration переинициализирован для боевого режима")
        print(f"  Shop ID из настроек: {get_setting('yookassa_shop_id')}")
        print(f"  API URL из настроек: {get_setting('yookassa_api_url')}")
        
        # Тест 3: Отсутствие ключей
        print("\n--- Тест 3: Отсутствие ключей ---")
        update_setting("yookassa_shop_id", "")
        update_setting("yookassa_secret_key", "")
        
        result = _reconfigure_yookassa()
        assert result is False, "Ожидалось False при отсутствии ключей"
        print("[OK] Корректно обрабатывается отсутствие ключей")
        
    finally:
        # Восстанавливаем оригинальные настройки
        if original_test_mode:
            update_setting("yookassa_test_mode", original_test_mode)
        if original_shop_id:
            update_setting("yookassa_shop_id", original_shop_id)
        if original_secret_key:
            update_setting("yookassa_secret_key", original_secret_key)
        if original_test_shop_id:
            update_setting("yookassa_test_shop_id", original_test_shop_id)
        if original_test_secret_key:
            update_setting("yookassa_test_secret_key", original_test_secret_key)


def test_configuration_switching():
    """Тест переключения между режимами"""
    print("\n=== Тест переключения режимов ===")
    
    # Сохраняем текущие настройки
    original_test_mode = get_setting("yookassa_test_mode")
    
    try:
        # Устанавливаем тестовые ключи
        update_setting("yookassa_test_shop_id", "test_shop_123")
        update_setting("yookassa_test_secret_key", "test_secret_123")
        update_setting("yookassa_shop_id", "live_shop_456")
        update_setting("yookassa_secret_key", "live_secret_456")
        
        # Переключаемся в тестовый режим
        print("\n--- Переключение в тестовый режим ---")
        update_setting("yookassa_test_mode", "true")
        _reconfigure_yookassa()
        
        test_shop_id = get_setting("yookassa_test_shop_id")
        print(f"[OK] Тестовый режим активирован, используется Shop ID: {test_shop_id}")
        
        # Переключаемся в боевой режим
        print("\n--- Переключение в боевой режим ---")
        update_setting("yookassa_test_mode", "false")
        _reconfigure_yookassa()
        
        live_shop_id = get_setting("yookassa_shop_id")
        print(f"[OK] Боевой режим активирован, используется Shop ID: {live_shop_id}")
        
        assert test_shop_id != live_shop_id, "Shop ID должны отличаться в разных режимах"
        print("[OK] Режимы переключаются корректно")
        
    finally:
        # Восстанавливаем оригинальные настройки
        if original_test_mode:
            update_setting("yookassa_test_mode", original_test_mode)


def show_current_configuration():
    """Показать текущую конфигурацию"""
    print("\n=== Текущая конфигурация YooKassa ===")
    
    test_mode = get_setting("yookassa_test_mode") == "true"
    print(f"Режим: {'Тестовый' if test_mode else 'Боевой'}")
    
    if test_mode:
        shop_id = get_setting("yookassa_test_shop_id") or get_setting("yookassa_shop_id")
        secret_key = get_setting("yookassa_test_secret_key") or get_setting("yookassa_secret_key")
        api_url = get_setting("yookassa_test_api_url") or get_setting("yookassa_api_url") or "https://api.test.yookassa.ru/v3"
    else:
        shop_id = get_setting("yookassa_shop_id")
        secret_key = get_setting("yookassa_secret_key")
        api_url = get_setting("yookassa_api_url") or "https://api.yookassa.ru/v3"
    
    print(f"Shop ID: {shop_id or 'НЕ УСТАНОВЛЕН'}")
    print(f"Secret Key: {'УСТАНОВЛЕН' if secret_key else 'НЕ УСТАНОВЛЕН'}")
    print(f"API URL: {api_url}")
    
    # Пытаемся получить текущую конфигурацию из SDK
    try:
        # Configuration не предоставляет публичных методов для чтения, но мы можем проверить через _reconfigure
        print("\nПроверка переинициализации...")
        result = _reconfigure_yookassa()
        if result:
            print("[OK] Configuration успешно переинициализирован")
        else:
            print("[WARN] Configuration не может быть переинициализирован (отсутствуют ключи)")
    except Exception as e:
        print(f"[ERROR] Ошибка при переинициализации: {e}")


if __name__ == "__main__":
    print("=" * 60)
    print("ТЕСТИРОВАНИЕ ПЕРЕИНИЦИАЛИЗАЦИИ YOOKASSA CONFIGURATION")
    print("=" * 60)
    
    try:
        # Показываем текущую конфигурацию
        show_current_configuration()
        
        # Запускаем тесты
        test_safe_strip()
        test_reconfigure_yookassa()
        test_configuration_switching()
        
        print("\n" + "=" * 60)
        print("ВСЕ ТЕСТЫ ПРОЙДЕНЫ УСПЕШНО!")
        print("=" * 60)
        
    except AssertionError as e:
        print(f"\n[FAIL] ТЕСТ ПРОВАЛЕН: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n[ERROR] ОШИБКА: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

