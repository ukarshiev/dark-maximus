#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Скрипт для экспорта данных о дефектах из Allure отчёта

Экспортирует:
- Список всех упавших тестов из категории "Product defects"
- Список всех упавших тестов из категории "Test defects"
- Детали каждого теста (название, ошибка, стектрейс, время выполнения)
- Связь с критичными операциями
"""

import json
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime

# Пути к файлам Allure
PROJECT_ROOT = Path(__file__).parent.parent.parent
ALLURE_REPORT_DIR = PROJECT_ROOT / "allure-report" / "data"
ALLURE_RESULTS_DIR = PROJECT_ROOT / "allure-results"
OUTPUT_DIR = PROJECT_ROOT / "tests" / "ad-hoc" / "reports"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Критичные операции из плана
CRITICAL_OPERATIONS = {
    "Регистрация пользователя": [
        "test_register_user_if_not_exists",
        "test_register_user_with_referrer",
        "test_user_registration_flow",
        "test_register_user_twice",
    ],
    "Покупка VPN-ключа": [
        "test_key_creation_with_integrity_error",
        "test_token_creation_on_key_creation",
    ],
    "Оплата": [
        "test_update_transaction_status",
        "test_update_transaction_on_payment",
        "test_log_transaction",
    ],
    "Получение ключа": [
        "test_get_next_key_number",
        "test_token_deletion_on_user_key_deletion",
        "test_validate_token_with_deleted_key",
    ],
    "Пополнение баланса": [
        "test_get_user_balance",
    ],
    "Использование промокодов": [
        "test_create_promo_code",
        "test_get_promo_code_by_code",
        "test_get_promo_code_by_id",
        "test_update_promo_code",
        "test_delete_promo_code",
        "test_can_user_use_promo_code",
        "test_promo_code_limit_reached",
        "test_record_promo_code_usage",
        "test_calculate_discount_amount",
        "test_calculate_discount_percent",
    ],
}


def load_json_file(file_path: Path) -> Optional[Dict[str, Any]]:
    """Загрузить JSON файл"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"⚠️  Файл не найден: {file_path}")
        return None
    except json.JSONDecodeError as e:
        print(f"❌ Ошибка парсинга JSON {file_path}: {e}")
        return None


def find_critical_operation(test_name: str) -> Optional[str]:
    """Найти критичную операцию для теста"""
    for operation, tests in CRITICAL_OPERATIONS.items():
        if test_name in tests:
            return operation
    return None


def extract_test_details(test_uid: str, test_name: str) -> Dict[str, Any]:
    """Извлечь детали теста из файла test-cases"""
    test_case_file = ALLURE_REPORT_DIR / "test-cases" / f"{test_uid}.json"
    test_data = load_json_file(test_case_file)
    
    if not test_data:
        return {
            "name": test_name,
            "uid": test_uid,
            "error": "Детали теста не найдены",
            "trace": "",
            "duration": 0,
        }
    
    # Извлекаем информацию об ошибке
    status_message = test_data.get("statusMessage", "")
    status_trace = test_data.get("statusTrace", "")
    time_info = test_data.get("time", {})
    duration = time_info.get("duration", 0) if isinstance(time_info, dict) else 0
    
    # Извлекаем модуль из fullName
    full_name = test_data.get("fullName", "")
    module = ""
    if full_name:
        parts = full_name.split(".")
        if len(parts) > 0:
            module = parts[0] if parts[0] != "unit" else ".".join(parts[:2])
    
    # Извлекаем теги
    labels = test_data.get("labels", [])
    tags = [label.get("value", "") for label in labels if label.get("name") == "tag"]
    
    return {
        "name": test_name,
        "uid": test_uid,
        "full_name": full_name,
        "module": module,
        "tags": tags,
        "status": test_data.get("status", "unknown"),
        "error": status_message,
        "trace": status_trace,
        "duration_ms": duration,
        "description": test_data.get("description", ""),
    }


def extract_defects_from_categories() -> Dict[str, List[Dict[str, Any]]]:
    """Извлечь дефекты из categories.json"""
    categories_file = ALLURE_REPORT_DIR / "categories.json"
    categories_data = load_json_file(categories_file)
    
    if not categories_data:
        return {"Product defects": [], "Test defects": []}
    
    defects = {
        "Product defects": [],
        "Test defects": [],
    }
    
    # Рекурсивно обходим структуру категорий
    def process_category(category: Dict[str, Any], category_name: str):
        if category.get("name") in ["Product defects", "Test defects"]:
            # Обрабатываем детей этой категории
            children = category.get("children", [])
            for child in children:
                process_error_group(child, category.get("name"))
        else:
            # Продолжаем рекурсию
            for child in category.get("children", []):
                process_category(child, category_name)
    
    def process_error_group(error_group: Dict[str, Any], defect_type: str):
        """Обработать группу ошибок"""
        error_name = error_group.get("name", "")
        children = error_group.get("children", [])
        
        for test in children:
            test_name = test.get("name", "")
            test_uid = test.get("uid", "")
            
            if not test_name or not test_uid:
                continue
            
            # Извлекаем детали теста
            test_details = extract_test_details(test_uid, test_name)
            test_details["error_group"] = error_name
            test_details["defect_type"] = defect_type
            
            # Определяем критичность
            critical_operation = find_critical_operation(test_name)
            test_details["critical_operation"] = critical_operation
            test_details["is_critical"] = critical_operation is not None
            
            defects[defect_type].append(test_details)
    
    # Начинаем обработку с корневого элемента
    root = categories_data.get("children", [])
    for category in root:
        process_category(category, "")
    
    return defects


def export_to_json(defects: Dict[str, List[Dict[str, Any]]]) -> Path:
    """Экспортировать дефекты в JSON"""
    output_file = OUTPUT_DIR / "allure-defects-export.json"
    
    export_data = {
        "export_date": datetime.now().isoformat(),
        "summary": {
            "product_defects": len(defects["Product defects"]),
            "test_defects": len(defects["Test defects"]),
            "total": len(defects["Product defects"]) + len(defects["Test defects"]),
            "critical_count": sum(
                1 for d in defects["Product defects"] + defects["Test defects"]
                if d.get("is_critical", False)
            ),
        },
        "defects": defects,
    }
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(export_data, f, ensure_ascii=False, indent=2)
    
    print(f"✅ Данные экспортированы в: {output_file}")
    return output_file


def main():
    """Основная функция"""
    print("🔍 Экспорт дефектов из Allure...")
    print(f"📁 Allure Report: {ALLURE_REPORT_DIR}")
    
    if not ALLURE_REPORT_DIR.exists():
        print(f"❌ Директория Allure отчёта не найдена: {ALLURE_REPORT_DIR}")
        print("💡 Запустите генерацию Allure отчёта: allure generate allure-results -o allure-report")
        sys.exit(1)
    
    # Извлекаем дефекты
    defects = extract_defects_from_categories()
    
    # Выводим статистику
    print(f"\n📊 Статистика дефектов:")
    print(f"   Product defects: {len(defects['Product defects'])}")
    print(f"   Test defects: {len(defects['Test defects'])}")
    print(f"   Всего: {len(defects['Product defects']) + len(defects['Test defects'])}")
    
    critical_count = sum(
        1 for d in defects["Product defects"] + defects["Test defects"]
        if d.get("is_critical", False)
    )
    print(f"   Критичных: {critical_count}")
    
    # Экспортируем в JSON
    export_file = export_to_json(defects)
    
    print(f"\n✅ Экспорт завершён!")
    print(f"📄 Файл: {export_file}")
    
    return defects


if __name__ == "__main__":
    main()

