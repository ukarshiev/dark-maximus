#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Скрипт для анализа дефектов Allure и создания структурированного отчёта

Анализирует экспортированные данные и создаёт отчёт с:
- Группировкой по модулям
- Приоритизацией
- Рекомендациями по исправлению
"""

import json
import sys
from pathlib import Path
from typing import Dict, List, Any
from collections import defaultdict
from datetime import datetime

PROJECT_ROOT = Path(__file__).parent.parent.parent
EXPORT_FILE = PROJECT_ROOT / "tests" / "ad-hoc" / "reports" / "allure-defects-export.json"
OUTPUT_DIR = PROJECT_ROOT / "tests" / "ad-hoc" / "reports"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
REPORT_FILE = OUTPUT_DIR / "allure-defects-report.md"


def load_exported_data() -> Dict[str, Any]:
    """Загрузить экспортированные данные"""
    if not EXPORT_FILE.exists():
        print(f"❌ Файл экспорта не найден: {EXPORT_FILE}")
        print("💡 Сначала запустите: python tests/ad-hoc/export_allure_defects.py")
        sys.exit(1)
    
    with open(EXPORT_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)


def group_by_module(defects: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    """Группировать дефекты по модулям"""
    grouped = defaultdict(list)
    for defect in defects:
        module = defect.get("module", "unknown")
        grouped[module].append(defect)
    return dict(grouped)


def prioritize_defects(defects: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    """Приоритизировать дефекты"""
    priorities = {
        "Критичные": [],
        "Важные": [],
        "Некритичные": [],
    }
    
    for defect in defects:
        if defect.get("is_critical", False):
            priorities["Критичные"].append(defect)
        elif defect.get("defect_type") == "Product defects":
            priorities["Важные"].append(defect)
        else:
            priorities["Некритичные"].append(defect)
    
    return priorities


def generate_markdown_report(data: Dict[str, Any]) -> str:
    """Генерировать Markdown отчёт"""
    defects = data["defects"]
    summary = data["summary"]
    
    report = f"""# Отчёт о дефектах Allure

**Дата создания:** {datetime.now().strftime('%d.%m.%Y %H:%M')}  
**Источник:** Allure Report

## 📊 Общая статистика

- **Product defects:** {summary['product_defects']}
- **Test defects:** {summary['test_defects']}
- **Всего дефектов:** {summary['total']}
- **Критичных дефектов:** {summary['critical_count']}

---

## 🚨 Критичные дефекты (приоритет исправления)

Критичные дефекты блокируют пользовательские операции и требуют немедленного исправления.

"""
    
    # Группируем критичные дефекты по операциям
    critical_defects = [
        d for d in defects["Product defects"] + defects["Test defects"]
        if d.get("is_critical", False)
    ]
    
    critical_by_operation = defaultdict(list)
    for defect in critical_defects:
        operation = defect.get("critical_operation", "Другое")
        critical_by_operation[operation].append(defect)
    
    # Выводим по операциям
    operation_order = [
        "Регистрация пользователя",
        "Покупка VPN-ключа",
        "Оплата",
        "Получение ключа",
        "Пополнение баланса",
        "Использование промокодов",
    ]
    
    for operation in operation_order:
        if operation not in critical_by_operation:
            continue
        
        operation_defects = critical_by_operation[operation]
        report += f"### {operation} ({len(operation_defects)} дефектов)\n\n"
        
        for defect in operation_defects:
            report += f"#### {defect['name']}\n\n"
            report += f"- **Тип:** {defect['defect_type']}\n"
            report += f"- **Модуль:** `{defect.get('module', 'unknown')}`\n"
            report += f"- **Статус:** {defect['status']}\n"
            report += f"- **Ошибка:** `{defect['error']}`\n"
            report += f"- **Время выполнения:** {defect['duration_ms']} мс\n\n"
            
            if defect.get("trace"):
                report += f"**Стек трейс:**\n```\n{defect['trace']}\n```\n\n"
            
            if defect.get("description"):
                report += f"**Описание:** {defect['description']}\n\n"
            
            report += "---\n\n"
    
    # Product defects по модулям
    report += "## 🐛 Product Defects (по модулям)\n\n"
    product_defects = defects["Product defects"]
    product_by_module = group_by_module(product_defects)
    
    for module, module_defects in sorted(product_by_module.items()):
        report += f"### {module} ({len(module_defects)} дефектов)\n\n"
        
        for defect in module_defects:
            critical_marker = "🚨 **КРИТИЧНЫЙ**" if defect.get("is_critical") else ""
            report += f"- {critical_marker} **{defect['name']}**\n"
            report += f"  - Ошибка: `{defect['error']}`\n"
            if defect.get("critical_operation"):
                report += f"  - Критичная операция: {defect['critical_operation']}\n"
            report += "\n"
        
        report += "\n"
    
    # Test defects по модулям
    report += "## 🧪 Test Defects (по модулям)\n\n"
    test_defects = defects["Test defects"]
    test_by_module = group_by_module(test_defects)
    
    for module, module_defects in sorted(test_by_module.items()):
        report += f"### {module} ({len(module_defects)} дефектов)\n\n"
        
        for defect in module_defects:
            report += f"- **{defect['name']}**\n"
            report += f"  - Ошибка: `{defect['error']}`\n"
            report += f"  - Группа ошибок: {defect.get('error_group', 'N/A')}\n"
            report += "\n"
        
        report += "\n"
    
    # Приоритизация
    report += "## 📋 Приоритизация дефектов\n\n"
    priorities = prioritize_defects(product_defects + test_defects)
    
    for priority, priority_defects in priorities.items():
        if not priority_defects:
            continue
        
        report += f"### {priority} ({len(priority_defects)} дефектов)\n\n"
        
        for defect in priority_defects[:10]:  # Показываем первые 10
            report += f"- **{defect['name']}** ({defect.get('module', 'unknown')})\n"
        
        if len(priority_defects) > 10:
            report += f"\n*... и ещё {len(priority_defects) - 10} дефектов*\n"
        
        report += "\n"
    
    # Рекомендации
    report += """## 💡 Рекомендации по исправлению

### Порядок исправления

1. **Критичные дефекты** — исправлять в первую очередь, начиная с:
   - Регистрация пользователя
   - Покупка VPN-ключа
   - Оплата
   - Получение ключа
   - Пополнение баланса
   - Использование промокодов

2. **Product defects** — исправлять после критичных, по модулям:
   - `unit.test_database` — операции с БД
   - `unit.test_bot` — логика бота
   - `unit.test_security` — безопасность
   - `unit.test_utils` — утилиты

3. **Test defects** — исправлять/удалять проблемные тесты:
   - Неправильные тесты → исправить
   - Устаревшие тесты → обновить
   - Флаки тесты → добавить retry или исправить условия
   - Ненужные тесты → удалить

### Процесс исправления

1. Для каждого дефекта создать GitHub Issue
2. Исправить дефект в коде/тесте
3. Запустить тесты: `pytest tests/ --alluredir=allure-results`
4. Проверить, что дефект исправлен
5. Закрыть GitHub Issue
6. Обновить этот отчёт

---

**Следующие шаги:**
1. Создать GitHub Issues для всех дефектов
2. Начать исправление с критичных дефектов
3. Настроить автоматическую категоризацию
4. Автоматизировать процесс создания Issues
"""
    
    return report


def main():
    """Основная функция"""
    print("🔍 Анализ дефектов Allure...")
    
    # Загружаем данные
    data = load_exported_data()
    
    # Генерируем отчёт
    report = generate_markdown_report(data)
    
    # Сохраняем отчёт
    with open(REPORT_FILE, 'w', encoding='utf-8') as f:
        f.write(report)
    
    print(f"✅ Отчёт создан: {REPORT_FILE}")
    print(f"📊 Всего дефектов: {data['summary']['total']}")
    print(f"🚨 Критичных: {data['summary']['critical_count']}")


if __name__ == "__main__":
    main()

