"""
Тест для проверки наличия переменной payment_method_normalized
в функциях обработки платежей.

Проверяет, что исправлена ошибка NameError: name 'payment_method_normalized' is not defined
в функции process_successful_payment.
"""

import ast
import sys
from pathlib import Path


def check_function_has_payment_method_normalized(func_node: ast.FunctionDef) -> tuple[bool, str]:
    """
    Проверяет, что функция определяет payment_method_normalized перед использованием.
    
    Returns:
        tuple: (success: bool, message: str)
    """
    # Ищем использование payment_method_normalized
    uses_normalized = False
    defines_normalized = False
    
    for node in ast.walk(func_node):
        # Проверяем использование переменной
        if isinstance(node, ast.Name) and node.id == 'payment_method_normalized':
            uses_normalized = True
        
        # Проверяем определение переменной (присваивание)
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == 'payment_method_normalized':
                    defines_normalized = True
    
    if uses_normalized and not defines_normalized:
        return False, f"[FAIL] Функция '{func_node.name}' использует payment_method_normalized, но не определяет её!"
    
    if uses_normalized and defines_normalized:
        return True, f"[OK] Функция '{func_node.name}' корректно определяет и использует payment_method_normalized"
    
    return True, f"[INFO] Функция '{func_node.name}' не использует payment_method_normalized"


def main():
    # Путь к файлу handlers.py
    handlers_path = Path(__file__).parent.parent / "src" / "shop_bot" / "bot" / "handlers.py"
    
    if not handlers_path.exists():
        print(f"[ERROR] Файл не найден: {handlers_path}")
        sys.exit(1)
    
    print(f"Проверяю файл: {handlers_path}\n")
    
    # Читаем и парсим файл
    with open(handlers_path, 'r', encoding='utf-8') as f:
        source_code = f.read()
    
    try:
        tree = ast.parse(source_code)
    except SyntaxError as e:
        print(f"[ERROR] Ошибка синтаксиса в файле: {e}")
        sys.exit(1)
    
    # Функции, которые нужно проверить
    target_functions = [
        'process_successful_payment',
        'process_successful_yookassa_payment'
    ]
    
    all_passed = True
    found_functions = []
    
    # Проходим по всем функциям в файле
    for node in ast.walk(tree):
        if isinstance(node, ast.AsyncFunctionDef) and node.name in target_functions:
            found_functions.append(node.name)
            success, message = check_function_has_payment_method_normalized(node)
            print(message)
            
            if not success:
                all_passed = False
    
    # Проверяем, что все нужные функции найдены
    print()
    for func_name in target_functions:
        if func_name not in found_functions:
            print(f"[WARNING] Функция '{func_name}' не найдена в файле")
            all_passed = False
    
    print("\n" + "="*60)
    
    if all_passed and len(found_functions) == len(target_functions):
        print("[SUCCESS] Все проверки пройдены успешно!")
        print("[SUCCESS] Исправление ошибки NameError подтверждено.")
        sys.exit(0)
    else:
        print("[FAIL] Обнаружены проблемы!")
        sys.exit(1)


if __name__ == "__main__":
    main()

