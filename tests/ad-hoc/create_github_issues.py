#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Скрипт для автоматического создания GitHub Issues из дефектов Allure

Использует GitHub API для создания Issues с правильными labels и заполненными данными.
"""

import json
import os
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional
import requests
from datetime import datetime

PROJECT_ROOT = Path(__file__).parent.parent.parent
EXPORT_FILE = PROJECT_ROOT / "tests" / "ad-hoc" / "reports" / "allure-defects-export.json"

# GitHub репозиторий (извлекается из git remote или задаётся вручную)
GITHUB_REPO = "ukarshiev/dark-maximus"
GITHUB_API_BASE = "https://api.github.com"
ALLURE_REPORT_URL = "http://localhost:50005/allure-docker-service/projects/default/reports/latest/index.html"


def get_github_token() -> Optional[str]:
    """Получить GitHub токен из переменной окружения"""
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        print("⚠️  GITHUB_TOKEN не установлен в переменных окружения")
        print("💡 Установите токен: $env:GITHUB_TOKEN='your-token' (PowerShell)")
        print("   Или: export GITHUB_TOKEN='your-token' (Bash)")
        return None
    return token


def load_exported_data() -> Dict[str, Any]:
    """Загрузить экспортированные данные"""
    if not EXPORT_FILE.exists():
        print(f"❌ Файл экспорта не найден: {EXPORT_FILE}")
        print("💡 Сначала запустите: python tests/ad-hoc/export_allure_defects.py")
        sys.exit(1)
    
    with open(EXPORT_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)


def format_issue_body(defect: Dict[str, Any]) -> str:
    """Форматировать тело Issue из шаблона"""
    # Извлекаем путь к тесту из full_name
    full_name = defect.get("full_name", "")
    test_path = ""
    if full_name:
        # Пример: unit.test_bot.test_handlers.TestHandlersLogic#test_user_registration_flow
        parts = full_name.split("#")
        if len(parts) > 0:
            module_path = parts[0].replace(".", "/")
            test_path = f"tests/{module_path}.py"
    
    # Определяем рекомендации
    recommendations = ""
    if defect.get("defect_type") == "Product defects":
        recommendations = f"""
1. Изучить код в модуле `{defect.get('module', 'unknown')}`
2. Найти причину ошибки: `{defect.get('error', 'N/A')}`
3. Исправить баг в коде
4. Запустить тест: `pytest {test_path}::{defect['name']}`
5. Проверить, что тест проходит
"""
    else:
        recommendations = """
1. Проанализировать тест
2. Определить причину:
   - Неправильный тест → исправить тест
   - Устаревший тест → обновить тест
   - Флаки тест → добавить retry или исправить условия
   - Ненужный тест → удалить тест
3. Исправить/удалить тест
4. Запустить тест и проверить результат
"""
    
    # Формируем ссылку на Allure
    allure_link = f"{ALLURE_REPORT_URL}#categories/{defect.get('uid', '')}"
    
    # Форматируем тело Issue
    body = f"""## 🐛 Информация о дефекте

**Тест:** `{defect['name']}`  
**Тип дефекта:** {defect.get('defect_type', 'N/A')}  
**Модуль:** `{defect.get('module', 'unknown')}`  
**Статус:** {defect.get('status', 'unknown')}  
**Критичная операция:** {defect.get('critical_operation', 'Нет')}

## 📋 Описание

{defect.get('description', 'Нет описания')}

## ❌ Ошибка

```
{defect.get('error', 'N/A')}
```

## 📍 Стек трейс

```
{defect.get('trace', 'N/A')}
```

## 🔗 Ссылки

- **Allure отчёт:** {allure_link}
- **Тест:** `{defect.get('full_name', 'N/A')}`
- **UID:** `{defect.get('uid', 'N/A')}`

## 🏷️ Приоритет

- [ ] Критичный (блокирует пользовательские операции)
- [ ] Важный (влияет на функциональность)
- [ ] Некритичный (косметическая проблема)

## 📝 Дополнительная информация

**Время выполнения:** {defect.get('duration_ms', 0)} мс  
**Теги:** {', '.join(defect.get('tags', []))}  
**Группа ошибок:** {defect.get('error_group', 'N/A')}

## 🔄 Шаги для воспроизведения

1. Запустить тест: `pytest {test_path}::{defect['name']}`
2. Проверить результат в Allure отчёте

## ✅ Ожидаемое поведение

Тест должен пройти успешно.

## ❌ Фактическое поведение

Тест падает с ошибкой: `{defect.get('error', 'N/A')}`

## 💡 Рекомендации по исправлению

{recommendations}

## 🔍 Checklist

- [ ] Дефект проанализирован
- [ ] Причина определена
- [ ] План исправления создан
- [ ] Исправление выполнено
- [ ] Тест проходит успешно
- [ ] Allure отчёт обновлён
"""
    
    return body


def get_issue_labels(defect: Dict[str, Any]) -> List[str]:
    """Получить labels для Issue"""
    labels = ["allure"]
    
    if defect.get("defect_type") == "Product defects":
        labels.append("bug")
    else:
        labels.append("test")
    
    if defect.get("is_critical", False):
        labels.append("critical")
    
    # Добавляем теги как labels (если они есть)
    tags = defect.get("tags", [])
    for tag in tags:
        if tag not in ["unit", "integration", "e2e"]:  # Исключаем общие теги
            labels.append(tag)
    
    return labels


def create_github_issue(
    token: str,
    title: str,
    body: str,
    labels: List[str],
    dry_run: bool = False
) -> Optional[Dict[str, Any]]:
    """Создать GitHub Issue"""
    url = f"{GITHUB_API_BASE}/repos/{GITHUB_REPO}/issues"
    
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
    }
    
    data = {
        "title": title,
        "body": body,
        "labels": labels,
    }
    
    if dry_run:
        print(f"🔍 [DRY RUN] Создал бы Issue:")
        print(f"   Title: {title}")
        print(f"   Labels: {', '.join(labels)}")
        print(f"   Body length: {len(body)} символов")
        return None
    
    try:
        response = requests.post(url, json=data, headers=headers, timeout=30)
        response.raise_for_status()
        
        issue_data = response.json()
        print(f"✅ Issue создан: #{issue_data['number']} - {title}")
        print(f"   URL: {issue_data['html_url']}")
        return issue_data
    except requests.exceptions.RequestException as e:
        print(f"❌ Ошибка при создании Issue '{title}': {e}")
        if hasattr(e, 'response') and e.response is not None:
            try:
                error_data = e.response.json()
                print(f"   Детали: {error_data}")
            except:
                print(f"   Ответ: {e.response.text}")
        return None


def check_existing_issues(token: str, test_name: str) -> bool:
    """Проверить, существует ли уже Issue для этого теста"""
    url = f"{GITHUB_API_BASE}/repos/{GITHUB_REPO}/issues"
    
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
    }
    
    params = {
        "state": "all",
        "labels": "allure",
        "per_page": 100,
    }
    
    try:
        response = requests.get(url, headers=headers, params=params, timeout=30)
        response.raise_for_status()
        
        issues = response.json()
        for issue in issues:
            if test_name in issue.get("title", ""):
                return True
        return False
    except requests.exceptions.RequestException:
        # В случае ошибки продолжаем создание
        return False


def main():
    """Основная функция"""
    print("🔍 Создание GitHub Issues из дефектов Allure...")
    
    # Проверяем токен
    token = get_github_token()
    if not token:
        print("\n⚠️  Продолжаю в режиме DRY RUN (без создания Issues)")
        dry_run = True
    else:
        dry_run = False
    
    # Загружаем данные
    data = load_exported_data()
    defects = data["defects"]
    
    # Объединяем все дефекты
    all_defects = defects["Product defects"] + defects["Test defects"]
    
    print(f"\n📊 Найдено дефектов: {len(all_defects)}")
    print(f"   Product defects: {len(defects['Product defects'])}")
    print(f"   Test defects: {len(defects['Test defects'])}")
    
    if dry_run:
        print("\n🔍 Режим DRY RUN - Issues не будут созданы")
    
    # Создаём Issues
    created_count = 0
    skipped_count = 0
    error_count = 0
    
    for defect in all_defects:
        test_name = defect["name"]
        title = f"[ALLURE] {test_name}"
        
        # Проверяем, существует ли уже Issue
        if not dry_run and token:
            if check_existing_issues(token, test_name):
                print(f"⏭️  Issue уже существует для: {test_name}")
                skipped_count += 1
                continue
        
        # Формируем тело Issue
        body = format_issue_body(defect)
        labels = get_issue_labels(defect)
        
        # Создаём Issue
        issue = create_github_issue(token or "", title, body, labels, dry_run)
        
        if issue:
            created_count += 1
        elif not dry_run:
            error_count += 1
        
        # Небольшая задержка, чтобы не превысить rate limit
        if not dry_run:
            import time
            time.sleep(1)
    
    # Итоговая статистика
    print(f"\n📊 Итоговая статистика:")
    print(f"   ✅ Создано: {created_count}")
    print(f"   ⏭️  Пропущено: {skipped_count}")
    print(f"   ❌ Ошибок: {error_count}")
    
    if dry_run:
        print(f"\n💡 Для реального создания Issues установите GITHUB_TOKEN")


if __name__ == "__main__":
    main()

