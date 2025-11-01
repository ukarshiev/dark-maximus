#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Диагностика и тестирование настроек кодировки Python в Windows
"""

import sys
import os
from pathlib import Path

# Добавляем путь к утилитам
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))
sys.path.insert(0, str(project_root / "tests"))

from test_utils import (
    safe_print, 
    print_test_header, 
    print_test_success, 
    print_test_failure,
    print_test_info,
    print_test_warning,
    print_test_error,
    print_test_step,
    get_encoding_info,
    test_unicode_output
)


def check_python_version():
    """Проверяет версию Python"""
    print_test_step(1, 6, "Проверка версии Python")
    
    version = sys.version_info
    safe_print(f"Python версия: {version.major}.{version.minor}.{version.micro}")
    
    if version.major >= 3 and version.minor >= 6:
        safe_print("  ✅ Версия Python поддерживается")
        return True
    else:
        safe_print("  ❌ Требуется Python 3.6 или выше")
        return False


def check_encoding_settings():
    """Проверяет настройки кодировки"""
    print_test_step(2, 6, "Проверка настроек кодировки")
    
    info = get_encoding_info()
    
    safe_print(f"Default encoding: {info['default_encoding']}")
    safe_print(f"stdout encoding: {info['stdout_encoding']}")
    safe_print(f"stderr encoding: {info['stderr_encoding']}")
    safe_print(f"stdin encoding: {info['stdin_encoding']}")
    safe_print("")
    safe_print(f"PYTHONIOENCODING: {info['pythonioencoding']}")
    safe_print(f"PYTHONUTF8: {info['pythonutf8']}")
    
    # Проверяем настройки
    issues = []
    
    if info['stdout_encoding'] != 'utf-8':
        issues.append(f"stdout использует {info['stdout_encoding']} вместо utf-8")
    
    if info['stderr_encoding'] != 'utf-8':
        issues.append(f"stderr использует {info['stderr_encoding']} вместо utf-8")
    
    if info['pythonioencoding'] == 'не установлен':
        issues.append("PYTHONIOENCODING не установлен")
    
    if info['pythonutf8'] == 'не установлен':
        issues.append("PYTHONUTF8 не установлен")
    
    if issues:
        safe_print("")
        print_test_warning("Обнаружены проблемы с кодировкой:")
        for issue in issues:
            safe_print(f"  • {issue}")
        return False
    else:
        safe_print("")
        safe_print("  ✅ Настройки кодировки корректны")
        return True


def test_console_output():
    """Тестирует вывод в консоль"""
    print_test_step(3, 6, "Тестирование вывода в консоль")
    
    test_cases = [
        ("Русский текст", "Привет, мир!"),
        ("Эмодзи", "✅ 🚀 🌍"),
        ("Смешанный текст", "Hello 世界! 🌍"),
        ("Специальные символы", "αβγδε αβγδε"),
        ("Кириллица + латиница", "Test тест Test")
    ]
    
    all_passed = True
    
    for test_name, test_text in test_cases:
        try:
            safe_print(f"  {test_name}: {test_text}")
        except Exception as e:
            safe_print(f"  ❌ {test_name}: Ошибка - {e}")
            all_passed = False
    
    if all_passed:
        safe_print("  ✅ Все тесты вывода пройдены")
    else:
        safe_print("  ❌ Есть проблемы с выводом")
    
    return all_passed


def test_file_operations():
    """Тестирует операции с файлами"""
    print_test_step(4, 6, "Тестирование операций с файлами")
    
    test_file = Path(__file__).parent / "test_encoding_temp.txt"
    test_content = "Тест кодировки: Привет, мир! ✅ 🚀"
    
    try:
        # Запись в файл
        with open(test_file, 'w', encoding='utf-8') as f:
            f.write(test_content)
        safe_print("  ✅ Запись в файл (UTF-8)")
        
        # Чтение из файла
        with open(test_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        if content == test_content:
            safe_print("  ✅ Чтение из файла (UTF-8)")
        else:
            safe_print("  ❌ Содержимое файла не совпадает")
            return False
        
        # Удаление тестового файла
        test_file.unlink()
        safe_print("  ✅ Файл удален")
        
        return True
        
    except Exception as e:
        safe_print(f"  ❌ Ошибка при работе с файлами: {e}")
        if test_file.exists():
            test_file.unlink()
        return False


def test_import_unicode():
    """Тестирует импорт модулей с Unicode"""
    print_test_step(5, 6, "Тестирование импорта модулей")
    
    try:
        # Тестируем импорт нашего модуля
        from shop_bot.utils.deeplink import create_deeplink, parse_deeplink
        safe_print("  ✅ Импорт deeplink модуля")
        
        # Тестируем создание deeplink
        link = create_deeplink("testbot", group_code="тест", promo_code="ПРОМО")
        safe_print(f"  ✅ Создание deeplink: {link}")
        
        # Тестируем парсинг
        param = link.split("?start=")[1]
        group, promo, referrer = parse_deeplink(param)
        safe_print(f"  ✅ Парсинг deeplink: group='{group}', promo='{promo}'")
        
        return True
        
    except Exception as e:
        safe_print(f"  ❌ Ошибка при импорте/тестировании модулей: {e}")
        return False


def provide_recommendations():
    """Предоставляет рекомендации по исправлению проблем"""
    print_test_step(6, 6, "Рекомендации по исправлению")
    
    safe_print("")
    safe_print("РЕКОМЕНДАЦИИ ПО ИСПРАВЛЕНИЮ ПРОБЛЕМ С КОДИРОВКОЙ:")
    safe_print("")
    
    safe_print("1. Настройка переменных окружения:")
    safe_print("   Установите следующие переменные окружения:")
    safe_print("   • PYTHONIOENCODING=utf-8")
    safe_print("   • PYTHONUTF8=1")
    safe_print("")
    
    safe_print("2. Автоматическая настройка:")
    safe_print("   Запустите скрипт настройки:")
    safe_print("   .\\tests\\setup_test_environment.ps1 -Global")
    safe_print("")
    
    safe_print("3. Ручная настройка в PowerShell:")
    safe_print("   [Console]::OutputEncoding = [System.Text.Encoding]::UTF8")
    safe_print("   [Console]::InputEncoding = [System.Text.Encoding]::UTF8")
    safe_print("   chcp 65001")
    safe_print("")
    
    safe_print("4. Проверка настроек:")
    safe_print("   python tests\\test_encoding.py")
    safe_print("")
    
    safe_print("5. Использование safe_print() в коде:")
    safe_print("   from tests.test_utils import safe_print")
    safe_print("   safe_print('✅ Текст с эмодзи')")
    safe_print("")


def main():
    """Основная функция диагностики"""
    print_test_header("Диагностика кодировки Python")
    
    # Выполняем все проверки
    results = []
    
    results.append(check_python_version())
    results.append(check_encoding_settings())
    results.append(test_console_output())
    results.append(test_file_operations())
    results.append(test_import_unicode())
    
    # Подсчитываем результаты
    passed = sum(results)
    total = len(results)
    
    safe_print("")
    safe_print("=" * 80)
    safe_print(f"РЕЗУЛЬТАТЫ ДИАГНОСТИКИ: {passed}/{total} проверок пройдено")
    safe_print("=" * 80)
    
    if passed == total:
        print_test_success("ВСЕ ПРОВЕРКИ ПРОЙДЕНЫ! Кодировка настроена корректно.")
    else:
        print_test_failure(f"ОБНАРУЖЕНЫ ПРОБЛЕМЫ! {total - passed} проверок не пройдено.")
        provide_recommendations()
    
    # Дополнительный тест Unicode
    safe_print("")
    test_unicode_output()
    
    return passed == total


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
