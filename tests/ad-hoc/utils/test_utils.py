#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Утилиты для безопасной работы с Unicode в тестах
"""

import sys
import os
from typing import Optional, Union


def safe_print(text: str, fallback_text: Optional[str] = None, file=None) -> None:
    """
    Безопасный вывод текста с обработкой ошибок кодировки
    
    Args:
        text: Текст для вывода
        fallback_text: Альтернативный текст при ошибке кодировки
        file: Файл для вывода (по умолчанию sys.stdout)
    
    Examples:
        >>> safe_print("✅ Тест пройден")
        ✅ Тест пройден
        
        >>> safe_print("✅ Тест пройден", fallback_text="[OK] Тест пройден")
        ✅ Тест пройден
        
        >>> safe_print("✅ Тест пройден", fallback_text="[OK] Тест пройден")
        [OK] Тест пройден  # если эмодзи не поддерживается
    """
    if file is None:
        file = sys.stdout
    
    try:
        print(text, file=file)
    except UnicodeEncodeError:
        if fallback_text:
            print(fallback_text, file=file)
        else:
            # Автоматическая замена Unicode символов на ASCII
            safe_text = text.encode('ascii', 'replace').decode('ascii')
            print(safe_text, file=file)


def safe_print_error(text: str, fallback_text: Optional[str] = None) -> None:
    """
    Безопасный вывод текста в stderr с обработкой ошибок кодировки
    
    Args:
        text: Текст для вывода
        fallback_text: Альтернативный текст при ошибке кодировки
    """
    safe_print(text, fallback_text, file=sys.stderr)


def get_encoding_info() -> dict:
    """
    Получает информацию о текущих настройках кодировки
    
    Returns:
        Словарь с информацией о кодировке
    """
    return {
        'default_encoding': sys.getdefaultencoding(),
        'stdout_encoding': sys.stdout.encoding,
        'stderr_encoding': sys.stderr.encoding,
        'stdin_encoding': sys.stdin.encoding,
        'pythonioencoding': os.environ.get('PYTHONIOENCODING', 'не установлен'),
        'pythonutf8': os.environ.get('PYTHONUTF8', 'не установлен'),
        'platform': sys.platform,
        'version': sys.version
    }


def print_encoding_info() -> None:
    """
    Выводит информацию о текущих настройках кодировки
    """
    info = get_encoding_info()
    
    safe_print("=" * 60)
    safe_print("ИНФОРМАЦИЯ О КОДИРОВКЕ PYTHON")
    safe_print("=" * 60)
    safe_print("")
    
    safe_print(f"Default encoding: {info['default_encoding']}")
    safe_print(f"stdout encoding: {info['stdout_encoding']}")
    safe_print(f"stderr encoding: {info['stderr_encoding']}")
    safe_print(f"stdin encoding: {info['stdin_encoding']}")
    safe_print("")
    safe_print(f"PYTHONIOENCODING: {info['pythonioencoding']}")
    safe_print(f"PYTHONUTF8: {info['pythonutf8']}")
    safe_print("")
    safe_print(f"Platform: {info['platform']}")
    safe_print(f"Python version: {info['version'].split()[0]}")
    safe_print("")


def test_unicode_output() -> bool:
    """
    Тестирует возможность вывода Unicode символов
    
    Returns:
        True если тест пройден, False если есть проблемы
    """
    test_cases = [
        ("✅ Эмодзи", "[OK] Эмодзи"),
        ("🚀 Ракета", "[ROCKET] Ракета"),
        ("🌍 Мир", "[WORLD] Мир"),
        ("Привет, мир!", "Привет, мир!"),
        ("Hello 世界!", "Hello [WORLD]!"),
        ("Тест: αβγδε", "Тест: [GREEK]")
    ]
    
    safe_print("=" * 60)
    safe_print("ТЕСТ UNICODE ВЫВОДА")
    safe_print("=" * 60)
    safe_print("")
    
    all_passed = True
    
    for original, fallback in test_cases:
        try:
            safe_print(f"Тест: {original}")
            safe_print("  ✓ Успешно")
        except Exception as e:
            safe_print(f"  ✗ Ошибка: {e}")
            safe_print(f"  Fallback: {fallback}")
            all_passed = False
    
    safe_print("")
    if all_passed:
        safe_print("✅ ВСЕ ТЕСТЫ UNICODE ПРОЙДЕНЫ")
    else:
        safe_print("❌ ЕСТЬ ПРОБЛЕМЫ С UNICODE")
    
    return all_passed


def print_test_header(title: str, width: int = 80) -> None:
    """
    Выводит заголовок теста с красивым оформлением
    
    Args:
        title: Заголовок теста
        width: Ширина рамки
    """
    safe_print("=" * width)
    safe_print(f"ТЕСТ: {title}")
    safe_print("=" * width)
    safe_print("")


def print_test_success(message: str = "ТЕСТ ПРОЙДЕН УСПЕШНО!") -> None:
    """
    Выводит сообщение об успешном завершении теста
    
    Args:
        message: Сообщение для вывода
    """
    safe_print("")
    safe_print("=" * 80)
    safe_print(f"✅ {message}")
    safe_print("=" * 80)


def print_test_failure(message: str = "ТЕСТ НЕ ПРОЙДЕН!") -> None:
    """
    Выводит сообщение о неудачном завершении теста
    
    Args:
        message: Сообщение для вывода
    """
    safe_print("")
    safe_print("=" * 80)
    safe_print(f"❌ {message}")
    safe_print("=" * 80)


def print_test_info(message: str) -> None:
    """
    Выводит информационное сообщение теста
    
    Args:
        message: Сообщение для вывода
    """
    safe_print(f"ℹ️  {message}")


def print_test_warning(message: str) -> None:
    """
    Выводит предупреждение теста
    
    Args:
        message: Сообщение для вывода
    """
    safe_print(f"⚠️  {message}")


def print_test_error(message: str) -> None:
    """
    Выводит сообщение об ошибке теста
    
    Args:
        message: Сообщение для вывода
    """
    safe_print(f"❌ {message}")


def print_test_step(step: int, total: int, description: str) -> None:
    """
    Выводит шаг теста с прогрессом
    
    Args:
        step: Номер текущего шага
        total: Общее количество шагов
        description: Описание шага
    """
    safe_print(f"{step}/{total}. {description}")


if __name__ == "__main__":
    # Демонстрация функций
    print_encoding_info()
    test_unicode_output()
