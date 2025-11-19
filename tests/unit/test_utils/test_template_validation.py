#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Unit-тесты для проверки корректности всех шаблонов в справочнике "Тексты бота"

Проверяет все активные шаблоны на:
- Отсутствие тегов <br> (не поддерживаются Telegram)
- Отсутствие неправильных переменных ({fallback_text}, {cabinet_text})
- Валидность HTML-тегов
- Отсутствие пустых шаблонов
"""

import sys
import re
from pathlib import Path
from unittest.mock import patch

import pytest
import allure

# Добавляем путь к модулям проекта
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root / "src"))

from shop_bot.data_manager.database import (
    get_all_message_templates,
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


@pytest.mark.unit
@pytest.mark.database
@allure.epic("Валидация шаблонов")
@allure.feature("Проверка справочника 'Тексты бота'")
@allure.label("package", "src.shop_bot.database")
class TestTemplateValidation:
    """Тесты для проверки корректности всех шаблонов в БД"""

    @allure.title("Проверка всех активных шаблонов на корректность")
    @allure.description("""
    ## Предварительные условия:
    1. База данных инициализирована с таблицей `message_templates`
    2. В БД есть хотя бы один активный шаблон (is_active = 1)
    3. Шаблоны содержат корректные данные (template_key, template_text, category)
    
    ## Шаги выполнения:
    1. **Подготовка**: Подключение к тестовой БД
    2. **Получение статистики**: Запрос статистики шаблонов (всего, активных, категорий)
    3. **Загрузка шаблонов**: Получение всех шаблонов из БД и фильтрация активных
    4. **Проверка каждого шаблона**: 
       - Проверка на теги `<br>` (не поддерживаются Telegram)
       - Проверка на неправильные переменные ({fallback_text}, {cabinet_text})
       - Валидация HTML-тегов через InputValidator
       - Проверка на неподдерживаемые Telegram теги
       - Проверка на пустые шаблоны
    5. **Агрегация результатов**: Сбор всех найденных проблем
    6. **Формирование отчета**: Создание детального отчета о проблемах
    
    ## Ожидаемые результаты:
    - ✅ Все активные шаблоны не содержат тегов `<br>`
    - ✅ Все активные шаблоны не содержат неправильных переменных
    - ✅ Все активные шаблоны проходят валидацию HTML
    - ✅ Все активные шаблоны не пустые
    - ✅ Все активные шаблоны содержат только поддерживаемые Telegram теги
    
    ## Критичность:
    - **CRITICAL**: Некорректные шаблоны могут вызывать ошибки при отправке сообщений
    - Ошибки валидации HTML приводят к использованию fallback из кода вместо шаблонов из БД
    - Неправильные переменные могут вызывать ошибки при подстановке значений
    - Теги `<br>` вызывают ошибку Telegram API: "can't parse entities: Unsupported start tag 'br'"
    
    ## Связанные компоненты:
    - `shop_bot.data_manager.database.get_all_message_templates()`
    - `shop_bot.data_manager.database.get_message_template_statistics()`
    - `shop_bot.security.validators.InputValidator.validate_html_tags()`
    - `shop_bot.config.get_message_text()`
    """)
    @allure.severity(allure.severity_level.CRITICAL)
    @allure.tag("templates", "validation", "database", "unit", "critical", "message-templates", "html-validation")
    @allure.link("http://localhost:50001/docs/guides/testing/template-validation", name="Документация по валидации шаблонов")
    def test_all_active_templates_are_valid(self, temp_db):
        """Тест проверки всех активных шаблонов на корректность"""
        from shop_bot.data_manager import database
        
        with allure.step("Подготовка: подключение к тестовой БД"):
            pass
        
        with allure.step("Шаг 1: Получение статистики шаблонов и создание тестовых данных"):
            # Сначала проверяем, есть ли шаблоны (используем правильные ключи)
            stats = get_message_template_statistics()
            total = stats.get('total_templates', stats.get('total', 0))
            active = stats.get('active_templates', stats.get('active', 0))
            categories = stats.get('categories_count', stats.get('categories', 0))
            
            # Если в БД нет шаблонов, создаем тестовые шаблоны для проверки
            if total == 0:
                with allure.step("Создание тестовых шаблонов для проверки"):
                    import sqlite3
                    conn = sqlite3.connect(str(temp_db))
                    cursor = conn.cursor()
                    
                    # Создаем несколько тестовых шаблонов (корректных)
                    test_templates = [
                        ('purchase_success_key', 'purchase', 'key', 
                         '🎉 <b>Ваш ключ #{key_number} готов!</b>\n\n⏳ <b>Он будет действовать до:</b> {expiry_formatted}\n\n⬇️ <b>НИЖЕ ВАШ КЛЮЧ</b> ⬇️\n------------------------------------------------------------------------\n<code>{connection_string}</code>\n------------------------------------------------------------------------',
                         'Тестовый шаблон для режима key', '[]', 1),
                        ('purchase_success_subscription', 'purchase', 'subscription',
                         '🎉 <b>Ваш ключ #{key_number} готов!</b>\n\n⏳ <b>Он будет действовать до:</b> {expiry_formatted}\n\n⬇️ <b>ВАША ПОДПИСКА</b> ⬇️\n------------------------------------------------------------------------\n{subscription_link}\n------------------------------------------------------------------------',
                         'Тестовый шаблон для режима subscription', '[]', 1),
                    ]
                    
                    for template_data in test_templates:
                        try:
                            cursor.execute('''
                                INSERT INTO message_templates 
                                (template_key, category, provision_mode, template_text, description, variables, is_active)
                                VALUES (?, ?, ?, ?, ?, ?, ?)
                            ''', template_data)
                        except sqlite3.IntegrityError:
                            # Шаблон уже существует, пропускаем
                            pass
                    
                    conn.commit()
                    conn.close()
                    
                    # Очищаем кэш шаблонов перед обновлением статистики
                    from shop_bot.data_manager.database import _template_cache
                    _template_cache.clear()
                    
                    # Обновляем статистику (используем правильные ключи)
                    stats = get_message_template_statistics()
                    total = stats.get('total_templates', stats.get('total', 0))
                    active = stats.get('active_templates', stats.get('active', 0))
                    categories = stats.get('categories_count', stats.get('categories', 0))
                    
                    allure.attach(
                        f"Создано {total} тестовых шаблонов (активных: {active})",
                        "Тестовые шаблоны созданы",
                        allure.attachment_type.TEXT
                    )
            
            stats_text = (
                f"📊 Статистика шаблонов:\n"
                f"   Всего шаблонов: {total}\n"
                f"   Активных: {active}\n"
                f"   Категорий: {categories}\n"
                f"   Неактивных: {total - active if total >= active else 0}"
            )
            
            allure.attach(stats_text, "Статистика шаблонов", allure.attachment_type.TEXT)
            allure.attach(str(stats), "Статистика (JSON)", allure.attachment_type.JSON)
            
            # Проверяем предварительное условие
            if total == 0:
                pytest.skip("Не удалось создать тестовые шаблоны")
            if active == 0:
                pytest.skip("В БД нет активных шаблонов для проверки")
        
        with allure.step("Шаг 2: Получение всех шаблонов из БД"):
            templates = get_all_message_templates()
            active_templates = [t for t in templates if t.get('is_active', 0)]
            inactive_templates = [t for t in templates if not t.get('is_active', 0)]
            
            if not active_templates:
                pytest.skip("Нет активных шаблонов для проверки")
            
            templates_info = (
                f"📋 Загружено шаблонов:\n"
                f"   Всего: {len(templates)}\n"
                f"   Активных: {len(active_templates)} ✅\n"
                f"   Неактивных: {len(inactive_templates)} (пропускаются)\n\n"
                f"Будет проверено: {len(active_templates)} активных шаблонов"
            )
            
            allure.attach(templates_info, "Количество шаблонов", allure.attachment_type.TEXT)
            
            # Создаем список шаблонов для проверки
            templates_list = []
            for t in active_templates:
                templates_list.append({
                    'id': t.get('template_id'),
                    'key': t.get('template_key'),
                    'category': t.get('category'),
                    'provision_mode': t.get('provision_mode') or 'all',
                    'text_length': len(t.get('template_text', ''))
                })
            
            import json
            allure.attach(
                json.dumps(templates_list, ensure_ascii=False, indent=2),
                "Список шаблонов для проверки",
                allure.attachment_type.JSON
            )
        
        with allure.step("Шаг 3: Проверка каждого активного шаблона"):
            all_issues = []
            checked_count = 0
            valid_count = 0
            
            for template in active_templates:
                template_id = template.get('template_id')
                template_key = template.get('template_key')
                category = template.get('category')
                provision_mode = template.get('provision_mode') or 'all'
                template_text = template.get('template_text', '')
                
                checked_count += 1
                
                with allure.step(f"Проверка шаблона {checked_count}/{len(active_templates)}: {template_key}"):
                    issues = check_template_issues(template_text)
                    
                    if issues:
                        all_issues.append({
                            'template': template,
                            'issues': issues
                        })
                        
                        # Прикрепляем информацию о проблемах к Allure
                        issue_details = "\n".join([
                            f"{'❌ ERROR' if issue['severity'] == 'error' else '⚠️ WARNING'}: {issue['message']}"
                            for issue in issues
                        ])
                        
                        problem_report = (
                            f"🔴 НАЙДЕНЫ ПРОБЛЕМЫ\n\n"
                            f"Шаблон: {template_key}\n"
                            f"ID: {template_id}\n"
                            f"Категория: {category}\n"
                            f"Режим: {provision_mode}\n"
                            f"Длина текста: {len(template_text)} символов\n"
                            f"Количество проблем: {len(issues)}\n\n"
                            f"Детали проблем:\n{issue_details}"
                        )
                        
                        allure.attach(
                            problem_report,
                            f"❌ Проблемы в шаблоне {template_key}",
                            allure.attachment_type.TEXT
                        )
                        
                        # Прикрепляем сам текст шаблона для анализа
                        allure.attach(
                            template_text,
                            f"Текст шаблона {template_key}",
                            allure.attachment_type.HTML
                        )
                        
                        # Прикрепляем JSON с деталями проблем
                        import json
                        allure.attach(
                            json.dumps({
                                'template_id': template_id,
                                'template_key': template_key,
                                'category': category,
                                'provision_mode': provision_mode,
                                'issues': issues
                            }, ensure_ascii=False, indent=2),
                            f"Детали проблем (JSON) - {template_key}",
                            allure.attachment_type.JSON
                        )
                    else:
                        valid_count += 1
                        allure.attach(
                            f"✅ Шаблон {template_key} корректен\n"
                            f"   ID: {template_id}\n"
                            f"   Категория: {category}\n"
                            f"   Режим: {provision_mode}\n"
                            f"   Длина текста: {len(template_text)} символов",
                            f"✅ Шаблон {template_key} валиден",
                            allure.attachment_type.TEXT
                        )
            
            # Итоговая статистика проверки
            check_summary = (
                f"📊 Итоги проверки:\n"
                f"   Проверено шаблонов: {checked_count}\n"
                f"   Корректных: {valid_count} ✅\n"
                f"   С проблемами: {len(all_issues)} ❌\n"
                f"   Всего проблем: {sum(len(item['issues']) for item in all_issues)}"
            )
            allure.attach(check_summary, "Итоги проверки", allure.attachment_type.TEXT)
        
        with allure.step("Шаг 4: Формирование итогового отчета"):
            if all_issues:
                total_issues = sum(len(item['issues']) for item in all_issues)
                
                # Подсчет проблем по типам
                issue_types = {}
                for item in all_issues:
                    for issue in item['issues']:
                        issue_type = issue['type']
                        issue_types[issue_type] = issue_types.get(issue_type, 0) + 1
                
                error_message = (
                    f"❌ ОБНАРУЖЕНЫ ПРОБЛЕМЫ В ШАБЛОНАХ\n\n"
                    f"📊 Общая статистика:\n"
                    f"   Шаблонов с проблемами: {len(all_issues)}\n"
                    f"   Всего проблем: {total_issues}\n\n"
                    f"📋 Распределение по типам:\n"
                )
                
                for issue_type, count in sorted(issue_types.items()):
                    error_message += f"   - {issue_type}: {count}\n"
                
                error_message += "\n📝 Детали проблем:\n\n"
                
                for idx, item in enumerate(all_issues, 1):
                    template = item['template']
                    issues = item['issues']
                    error_message += (
                        f"{idx}. Шаблон: {template['template_key']} (ID: {template['template_id']})\n"
                        f"   Категория: {template['category']}\n"
                        f"   Режим: {template.get('provision_mode') or 'all'}\n"
                        f"   Проблем: {len(issues)}\n"
                    )
                    for issue in issues:
                        error_message += f"      ❌ {issue['message']}\n"
                    error_message += "\n"
                
                # Прикрепляем детальный отчет
                allure.attach(error_message, "❌ Детальный отчет о проблемах", allure.attachment_type.TEXT)
                
                # Прикрепляем JSON с полной информацией
                import json
                full_report = {
                    'summary': {
                        'total_templates_checked': len(active_templates),
                        'templates_with_issues': len(all_issues),
                        'total_issues': total_issues,
                        'issue_types': issue_types
                    },
                    'templates_with_issues': [
                        {
                            'template_id': item['template']['template_id'],
                            'template_key': item['template']['template_key'],
                            'category': item['template']['category'],
                            'provision_mode': item['template'].get('provision_mode') or 'all',
                            'issues': item['issues']
                        }
                        for item in all_issues
                    ]
                }
                allure.attach(
                    json.dumps(full_report, ensure_ascii=False, indent=2),
                    "Полный отчет о проблемах (JSON)",
                    allure.attachment_type.JSON
                )
                
                pytest.fail(error_message)
            else:
                success_message = (
                    f"✅ ВСЕ ШАБЛОНЫ КОРРЕКТНЫ\n\n"
                    f"📊 Результаты проверки:\n"
                    f"   Проверено шаблонов: {len(active_templates)}\n"
                    f"   Корректных: {len(active_templates)} ✅\n"
                    f"   Проблем: 0\n\n"
                    f"Все активные шаблоны готовы к использованию!"
                )
                
                allure.attach(success_message, "✅ Результат проверки", allure.attachment_type.TEXT)
                
                # Прикрепляем список всех проверенных шаблонов
                import json
                valid_templates = [
                    {
                        'id': t['template_id'],
                        'key': t['template_key'],
                        'category': t['category'],
                        'provision_mode': t.get('provision_mode') or 'all'
                    }
                    for t in active_templates
                ]
                allure.attach(
                    json.dumps(valid_templates, ensure_ascii=False, indent=2),
                    "Список корректных шаблонов",
                    allure.attachment_type.JSON
                )

    @allure.title("Проверка отсутствия тегов <br> в шаблонах")
    @allure.description("""
    ## Предварительные условия:
    1. База данных инициализирована с таблицей `message_templates`
    2. В БД есть активные шаблоны
    
    ## Шаги выполнения:
    1. **Загрузка шаблонов**: Получение всех активных шаблонов из БД
    2. **Поиск тегов <br>**: Проверка каждого шаблона на наличие тегов `<br>`, `<br/>`, `<br />`, `<BR>` (любой регистр)
    3. **Агрегация результатов**: Сбор всех шаблонов с тегами `<br>`
    4. **Формирование отчета**: Создание детального отчета о найденных проблемах
    
    ## Ожидаемые результаты:
    - ✅ Ни один активный шаблон не содержит тегов `<br>` в любом варианте написания
    - ✅ Все переносы строк используют символ `\\n` вместо HTML-тегов
    
    ## Критичность:
    - **CRITICAL**: Telegram Bot API не поддерживает тег `<br>`
    - Использование `<br>` вызывает ошибку: "can't parse entities: Unsupported start tag 'br'"
    - Это приводит к использованию fallback из кода вместо шаблонов из БД
    
    ## Решение проблемы:
    - Заменить все `<br>`, `<br/>`, `<br />` на `\\n` (перенос строки)
    - Использовать скрипт `tools/check_templates.py` для автоматического исправления
    """)
    @allure.severity(allure.severity_level.CRITICAL)
    @allure.tag("templates", "br-tag", "validation", "unit", "critical", "html", "telegram-api")
    @allure.link("http://localhost:50001/docs/guides/testing/template-validation", name="Документация по валидации шаблонов")
    def test_no_br_tags_in_templates(self, temp_db):
        """Тест проверки отсутствия тегов <br> в шаблонах"""
        # Используем database.DB_FILE (уже заменен через monkeypatch в фикстуре temp_db)
        from shop_bot.data_manager import database
        
        with allure.step("Шаг 1: Загрузка всех активных шаблонов"):
            templates = get_all_message_templates()
            active_templates = [t for t in templates if t.get('is_active', 0)]
            
            if not active_templates:
                pytest.skip("Нет активных шаблонов для проверки")
            
            allure.attach(
                f"Загружено {len(active_templates)} активных шаблонов для проверки",
                "Количество шаблонов",
                allure.attachment_type.TEXT
            )
        
        with allure.step("Шаг 2: Поиск тегов <br> в шаблонах"):
            br_pattern = re.compile(r'<br\s*/?>', re.IGNORECASE)
            templates_with_br = []
            
            for template in active_templates:
                template_text = template.get('template_text', '')
                br_matches = br_pattern.findall(template_text)
                if br_matches:
                    templates_with_br.append({
                        'template': template,
                        'count': len(br_matches),
                        'matches': br_matches
                    })
                    
                    # Прикрепляем информацию о проблеме
                    allure.attach(
                        f"❌ Найдено {len(br_matches)} тегов <br> в шаблоне {template['template_key']}\n"
                        f"   ID: {template['template_id']}\n"
                        f"   Варианты тегов: {', '.join(set(br_matches))}",
                        f"Теги <br> в шаблоне {template['template_key']}",
                        allure.attachment_type.TEXT
                    )
        
        with allure.step("Шаг 3: Формирование отчета"):
            if templates_with_br:
                total_br_tags = sum(item['count'] for item in templates_with_br)
                error_message = (
                    f"❌ НАЙДЕНЫ ТЕГИ <br> В ШАБЛОНАХ\n\n"
                    f"📊 Статистика:\n"
                    f"   Шаблонов с тегами <br>: {len(templates_with_br)}\n"
                    f"   Всего тегов <br>: {total_br_tags}\n\n"
                    f"📝 Детали:\n"
                )
                
                for item in templates_with_br:
                    template = item['template']
                    error_message += (
                        f"  - {template['template_key']} (ID: {template['template_id']}): "
                        f"{item['count']} тегов <br>\n"
                    )
                
                # Прикрепляем JSON отчет
                import json
                br_report = {
                    'total_templates_with_br': len(templates_with_br),
                    'total_br_tags': total_br_tags,
                    'templates': [
                        {
                            'template_id': item['template']['template_id'],
                            'template_key': item['template']['template_key'],
                            'br_count': item['count'],
                            'br_variants': list(set(item['matches']))
                        }
                        for item in templates_with_br
                    ]
                }
                allure.attach(
                    json.dumps(br_report, ensure_ascii=False, indent=2),
                    "Отчет о тегах <br> (JSON)",
                    allure.attachment_type.JSON
                )
                
                allure.attach(error_message, "❌ Детали проблем", allure.attachment_type.TEXT)
                pytest.fail(error_message)
            else:
                success_message = (
                    f"✅ ВСЕ ШАБЛОНЫ НЕ СОДЕРЖАТ ТЕГОВ <br>\n\n"
                    f"📊 Результаты:\n"
                    f"   Проверено шаблонов: {len(active_templates)}\n"
                    f"   Шаблонов с тегами <br>: 0 ✅\n\n"
                    f"Все переносы строк используют символ \\n"
                )
                allure.attach(success_message, "✅ Результат проверки", allure.attachment_type.TEXT)

    @allure.title("Проверка отсутствия неправильных переменных в шаблонах")
    @allure.description("""
    ## Предварительные условия:
    1. База данных инициализирована с таблицей `message_templates`
    2. В БД есть активные шаблоны
    
    ## Шаги выполнения:
    1. **Загрузка шаблонов**: Получение всех активных шаблонов из БД
    2. **Поиск неправильных переменных**: Проверка каждого шаблона на наличие переменных:
       - `{fallback_text}` - внутренняя переменная кода
       - `{cabinet_text}` - внутренняя переменная кода
    3. **Агрегация результатов**: Сбор всех шаблонов с неправильными переменными
    4. **Формирование отчета**: Создание детального отчета о найденных проблемах
    
    ## Ожидаемые результаты:
    - ✅ Ни один активный шаблон не содержит переменных `{fallback_text}` и `{cabinet_text}`
    - ✅ Все переменные в шаблонах являются валидными и подставляются из словаря `variables`
    
    ## Критичность:
    - **CRITICAL**: Неправильные переменные не подставляются при форматировании
    - Это приводит к появлению текста `{fallback_text}` или `{cabinet_text}` в сообщениях пользователям
    - Переменные `{fallback_text}` и `{cabinet_text}` являются внутренними переменными кода и не должны быть в шаблонах БД
    
    ## Решение проблемы:
    - Удалить переменные `{fallback_text}` и `{cabinet_text}` из шаблонов
    - Использовать скрипт `tools/check_templates.py` для автоматического исправления
    - Проверить логику формирования шаблонов в коде
    
    ## Валидные переменные:
    - `{key_number}` - номер ключа
    - `{expiry_formatted}` - дата истечения (отформатированная)
    - `{created_formatted}` - дата создания (отформатированная)
    - `{connection_string}` - строка подключения VLESS
    - `{subscription_link}` - ссылка на подписку
    - `{cabinet_url}` - URL личного кабинета
    - `{status_icon}` - иконка статуса
    - `{status_text}` - текст статуса
    - И другие переменные из словаря `template_variables` в функции `get_message_text()`
    """)
    @allure.severity(allure.severity_level.CRITICAL)
    @allure.tag("templates", "variables", "validation", "unit", "critical", "template-variables")
    @allure.link("http://localhost:50001/docs/guides/testing/template-validation", name="Документация по валидации шаблонов")
    def test_no_invalid_variables_in_templates(self, temp_db):
        """Тест проверки отсутствия неправильных переменных в шаблонах"""
        # Используем database.DB_FILE (уже заменен через monkeypatch в фикстуре temp_db)
        from shop_bot.data_manager import database
        
        with allure.step("Шаг 1: Загрузка всех активных шаблонов"):
            templates = get_all_message_templates()
            active_templates = [t for t in templates if t.get('is_active', 0)]
            
            if not active_templates:
                pytest.skip("Нет активных шаблонов для проверки")
            
            allure.attach(
                f"Загружено {len(active_templates)} активных шаблонов для проверки",
                "Количество шаблонов",
                allure.attachment_type.TEXT
            )
        
        with allure.step("Шаг 2: Поиск неправильных переменных"):
            invalid_vars = ['{fallback_text}', '{cabinet_text}']
            templates_with_invalid_vars = []
            
            for template in active_templates:
                template_text = template.get('template_text', '')
                found_vars = [var for var in invalid_vars if var in template_text]
                if found_vars:
                    templates_with_invalid_vars.append({
                        'template': template,
                        'variables': found_vars
                    })
                    
                    # Прикрепляем информацию о проблеме
                    allure.attach(
                        f"❌ Найдены неправильные переменные в шаблоне {template['template_key']}\n"
                        f"   ID: {template['template_id']}\n"
                        f"   Переменные: {', '.join(found_vars)}\n"
                        f"   Категория: {template['category']}\n"
                        f"   Режим: {template.get('provision_mode') or 'all'}",
                        f"Неправильные переменные в шаблоне {template['template_key']}",
                        allure.attachment_type.TEXT
                    )
        
        with allure.step("Шаг 3: Формирование отчета"):
            if templates_with_invalid_vars:
                total_invalid_vars = sum(len(item['variables']) for item in templates_with_invalid_vars)
                error_message = (
                    f"❌ НАЙДЕНЫ НЕПРАВИЛЬНЫЕ ПЕРЕМЕННЫЕ В ШАБЛОНАХ\n\n"
                    f"📊 Статистика:\n"
                    f"   Шаблонов с неправильными переменными: {len(templates_with_invalid_vars)}\n"
                    f"   Всего неправильных переменных: {total_invalid_vars}\n\n"
                    f"📝 Детали:\n"
                )
                
                for item in templates_with_invalid_vars:
                    template = item['template']
                    error_message += (
                        f"  - {template['template_key']} (ID: {template['template_id']}): "
                        f"{', '.join(item['variables'])}\n"
                    )
                
                # Прикрепляем JSON отчет
                import json
                vars_report = {
                    'total_templates_with_invalid_vars': len(templates_with_invalid_vars),
                    'total_invalid_vars': total_invalid_vars,
                    'invalid_variables': ['{fallback_text}', '{cabinet_text}'],
                    'templates': [
                        {
                            'template_id': item['template']['template_id'],
                            'template_key': item['template']['template_key'],
                            'category': item['template']['category'],
                            'provision_mode': item['template'].get('provision_mode') or 'all',
                            'invalid_variables': item['variables']
                        }
                        for item in templates_with_invalid_vars
                    ]
                }
                allure.attach(
                    json.dumps(vars_report, ensure_ascii=False, indent=2),
                    "Отчет о неправильных переменных (JSON)",
                    allure.attachment_type.JSON
                )
                
                allure.attach(error_message, "❌ Детали проблем", allure.attachment_type.TEXT)
                pytest.fail(error_message)
            else:
                success_message = (
                    f"✅ ВСЕ ШАБЛОНЫ НЕ СОДЕРЖАТ НЕПРАВИЛЬНЫХ ПЕРЕМЕННЫХ\n\n"
                    f"📊 Результаты:\n"
                    f"   Проверено шаблонов: {len(active_templates)}\n"
                    f"   Шаблонов с неправильными переменными: 0 ✅\n\n"
                    f"Все переменные в шаблонах являются валидными"
                )
                allure.attach(success_message, "✅ Результат проверки", allure.attachment_type.TEXT)

