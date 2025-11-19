# -*- coding: utf-8 -*-
"""
Скрипт для проверки и исправления шаблонов сообщений в справочнике "Тексты бота"
"""

import sys
import re
from pathlib import Path

# Добавляем корневую директорию проекта в путь
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

from shop_bot.data_manager.database import (
    get_all_message_templates,
    update_message_template,
    get_message_template_statistics
)
from shop_bot.security.validators import InputValidator

def check_template_issues(template_text: str) -> list[dict]:
    """
    Проверяет шаблон на наличие проблем
    
    Returns:
        Список словарей с информацией о проблемах
    """
    issues = []
    
    if not template_text or not template_text.strip():
        issues.append({
            'type': 'empty',
            'severity': 'error',
            'message': 'Шаблон пустой или содержит только пробелы'
        })
        return issues
    
    # Проверка на теги <br> (Telegram их не поддерживает)
    br_pattern = re.compile(r'<br\s*/?>', re.IGNORECASE)
    br_matches = br_pattern.findall(template_text)
    if br_matches:
        issues.append({
            'type': 'br_tags',
            'severity': 'error',
            'message': f'Найдено {len(br_matches)} тегов <br>, которые Telegram не поддерживает. Нужно заменить на \\n',
            'count': len(br_matches)
        })
    
    # Проверка на неправильные переменные
    invalid_vars = ['{fallback_text}', '{cabinet_text}']
    for var in invalid_vars:
        if var in template_text:
            issues.append({
                'type': 'invalid_variable',
                'severity': 'error',
                'message': f'Найдена неправильная переменная {var}. Это внутренняя переменная кода, не должна быть в шаблоне',
                'variable': var
            })
    
    # Проверка валидности HTML-тегов
    is_valid, errors = InputValidator.validate_html_tags(template_text)
    if not is_valid:
        issues.append({
            'type': 'html_validation',
            'severity': 'error',
            'message': f'Ошибки валидации HTML: {", ".join(errors)}',
            'errors': errors
        })
    
    # Проверка на неподдерживаемые теги (кроме валидных)
    valid_tags = {'b', 'i', 'u', 's', 'a', 'code', 'pre', 'blockquote'}
    tag_pattern = re.compile(r'<([a-zA-Z][a-zA-Z0-9]*)([^>]*)>', re.IGNORECASE)
    found_tags = set()
    for match in tag_pattern.finditer(template_text):
        tag_name = match.group(1).lower()
        if tag_name not in valid_tags and tag_name not in ['br']:  # br уже проверяется отдельно
            found_tags.add(tag_name)
    
    if found_tags:
        issues.append({
            'type': 'unsupported_tags',
            'severity': 'warning',
            'message': f'Найдены неподдерживаемые Telegram теги: {", ".join(sorted(found_tags))}',
            'tags': list(found_tags)
        })
    
    return issues

def fix_template_text(template_text: str) -> tuple[str, list[str]]:
    """
    Исправляет проблемы в тексте шаблона
    
    Returns:
        Tuple[исправленный_текст, список_исправлений]
    """
    fixed_text = template_text
    fixes = []
    
    # Заменяем <br> на \n
    br_pattern = re.compile(r'<br\s*/?>', re.IGNORECASE)
    br_count = len(br_pattern.findall(fixed_text))
    if br_count > 0:
        fixed_text = br_pattern.sub('\n', fixed_text)
        fixes.append(f'Заменено {br_count} тегов <br> на переносы строки')
    
    # Удаляем неправильные переменные
    if '{fallback_text}' in fixed_text:
        fixed_text = fixed_text.replace('{fallback_text}', '')
        fixes.append('Удалена переменная {fallback_text}')
    
    if '{cabinet_text}' in fixed_text:
        fixed_text = fixed_text.replace('{cabinet_text}', '')
        fixes.append('Удалена переменная {cabinet_text}')
    
    return fixed_text, fixes

def main():
    """Основная функция проверки и исправления шаблонов"""
    print("=" * 80)
    print("Проверка шаблонов сообщений в справочнике 'Тексты бота'")
    print("=" * 80)
    print()
    
    # Получаем статистику
    stats = get_message_template_statistics()
    print(f"📊 Статистика:")
    print(f"   Всего шаблонов: {stats.get('total', 0)}")
    print(f"   Активных: {stats.get('active', 0)}")
    print(f"   Категорий: {stats.get('categories', 0)}")
    print()
    
    # Получаем все шаблоны
    templates = get_all_message_templates()
    
    if not templates:
        print("❌ Шаблоны не найдены в базе данных")
        return
    
    print(f"🔍 Проверка {len(templates)} шаблонов...")
    print()
    
    total_issues = 0
    templates_with_issues = []
    templates_to_fix = []
    
    for template in templates:
        template_id = template.get('template_id')
        template_key = template.get('template_key')
        category = template.get('category')
        provision_mode = template.get('provision_mode') or 'all'
        template_text = template.get('template_text', '')
        is_active = template.get('is_active', 0)
        
        # Проверяем только активные шаблоны
        if not is_active:
            continue
        
        issues = check_template_issues(template_text)
        
        if issues:
            total_issues += len(issues)
            templates_with_issues.append({
                'template': template,
                'issues': issues
            })
            
            # Определяем, можно ли автоматически исправить
            can_auto_fix = all(
                issue['type'] in ['br_tags', 'invalid_variable']
                for issue in issues
            )
            
            if can_auto_fix:
                templates_to_fix.append(template)
    
    # Выводим результаты проверки
    if templates_with_issues:
        print(f"⚠️  Найдено проблем в {len(templates_with_issues)} шаблонах (всего {total_issues} проблем):")
        print()
        
        for item in templates_with_issues:
            template = item['template']
            issues = item['issues']
            
            print(f"📝 Шаблон: {template['template_key']}")
            print(f"   ID: {template['template_id']}")
            print(f"   Категория: {template['category']}")
            print(f"   Режим: {template.get('provision_mode') or 'all'}")
            print(f"   Проблем: {len(issues)}")
            
            for issue in issues:
                severity_icon = '❌' if issue['severity'] == 'error' else '⚠️'
                print(f"   {severity_icon} {issue['message']}")
            
            print()
    else:
        print("✅ Все шаблоны корректны!")
        print()
        return
    
    # Предлагаем исправления
    if templates_to_fix:
        print(f"🔧 Найдено {len(templates_to_fix)} шаблонов, которые можно исправить автоматически:")
        print()
        
        for template in templates_to_fix:
            template_id = template['template_id']
            template_key = template['template_key']
            original_text = template['template_text']
            
            fixed_text, fixes = fix_template_text(original_text)
            
            print(f"📝 Шаблон: {template_key} (ID: {template_id})")
            for fix in fixes:
                print(f"   ✓ {fix}")
            print()
            
            # Применяем исправление
            try:
                update_message_template(
                    template_id=template_id,
                    template_text=fixed_text,
                    description=template.get('description')
                )
                print(f"   ✅ Шаблон исправлен и сохранен в БД")
            except Exception as e:
                print(f"   ❌ Ошибка при сохранении: {e}")
            print()
    
    print("=" * 80)
    print("Проверка завершена")
    print("=" * 80)

if __name__ == '__main__':
    main()

