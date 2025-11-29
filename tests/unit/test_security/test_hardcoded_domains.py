#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Unit-тесты для проверки отсутствия жестко прописанных доменов в коде

Проверяет, что в коде не используются жестко прописанные домены dark-maximus.com,
а вместо этого используются настройки из БД или переменные окружения.
"""

import pytest
import allure
import sys
import re
from pathlib import Path

# Добавляем путь к проекту
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root / "src"))


@pytest.mark.unit
@allure.epic("Безопасность")
@allure.feature("Проверка жестко прописанных доменов")
@allure.label("package", "tests.unit.test_security")
class TestHardcodedDomains:
    """Тесты для проверки отсутствия жестко прописанных доменов"""

    @allure.title("Проверка отсутствия dark-maximus.com в Python коде")
    @allure.description("""
    Проверяет отсутствие жестко прописанного домена dark-maximus.com в Python коде.
    
    **Что проверяется:**
    - Отсутствие строки "dark-maximus.com" в файлах src/**/*.py
    - Исключение из проверки: документация (docs/), CHANGELOG.md, тесты (tests/)
    
    **Ожидаемый результат:**
    В Python коде не должно быть жестко прописанных доменов dark-maximus.com.
    """)
    @allure.severity(allure.severity_level.CRITICAL)
    @allure.tag("hardcoded", "domains", "security", "unit", "critical")
    def test_no_hardcoded_domains_in_python_code(self):
        """Проверка отсутствия dark-maximus.com в Python коде"""
        with allure.step("Поиск файлов Python в src/"):
            src_dir = project_root / "src"
            python_files = list(src_dir.rglob("*.py"))
            allure.attach(str(len(python_files)), "Количество Python файлов", allure.attachment_type.TEXT)
        
        with allure.step("Поиск жестко прописанных доменов"):
            hardcoded_pattern = re.compile(r'dark-maximus\.com', re.IGNORECASE)
            violations = []
            
            for file_path in python_files:
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                        lines = content.split('\n')
                        
                        for line_num, line in enumerate(lines, 1):
                            if hardcoded_pattern.search(line):
                                # Пропускаем комментарии, docstrings с примерами и fallback значения
                                stripped = line.strip()
                                # Проверяем предыдущую строку на наличие комментария о fallback
                                prev_line = lines[line_num - 2].strip() if line_num > 1 else ""
                                # Проверяем текущую строку на наличие комментария о fallback (может быть на той же строке)
                                has_fallback_comment = (
                                    'fallback' in stripped.lower() or
                                    'default' in stripped.lower() or
                                    '# fallback' in prev_line.lower() or
                                    '# default' in prev_line.lower() or
                                    'fallback' in prev_line.lower() or
                                    'для обратной совместимости' in prev_line.lower() or
                                    '# fallback' in stripped.lower() or
                                    '# default' in stripped.lower()
                                )
                                
                                if not (stripped.startswith('#') or 
                                        'example' in stripped.lower() or
                                        'test' in stripped.lower() or
                                        has_fallback_comment):
                                    violations.append({
                                        'file': str(file_path.relative_to(project_root)),
                                        'line': line_num,
                                        'content': line.strip()
                                    })
                except Exception as e:
                    allure.attach(str(e), f"Ошибка чтения {file_path}", allure.attachment_type.TEXT)
            
            allure.attach(str(len(violations)), "Количество нарушений", allure.attachment_type.TEXT)
            if violations:
                violations_text = '\n'.join([f"{v['file']}:{v['line']}: {v['content']}" for v in violations])
                allure.attach(violations_text, "Найденные нарушения", allure.attachment_type.TEXT)
        
        with allure.step("Проверка результата"):
            assert len(violations) == 0, f"Найдено {len(violations)} жестко прописанных доменов dark-maximus.com в Python коде"

    @allure.title("Проверка отсутствия жестко прописанных поддоменов в Python коде")
    @allure.description("""
    Проверяет отсутствие жестко прописанных поддоменов (panel.dark-maximus, help.dark-maximus, 
    docs.dark-maximus, app.dark-maximus) в Python коде.
    
    **Что проверяется:**
    - Отсутствие паттернов поддоменов в файлах src/**/*.py
    - Исключение из проверки: комментарии, примеры, тесты
    
    **Ожидаемый результат:**
    В Python коде не должно быть жестко прописанных поддоменов.
    """)
    @allure.severity(allure.severity_level.CRITICAL)
    @allure.tag("hardcoded", "subdomains", "security", "unit", "critical")
    def test_no_hardcoded_subdomains_in_python_code(self):
        """Проверка отсутствия жестко прописанных поддоменов в Python коде"""
        with allure.step("Поиск файлов Python в src/"):
            src_dir = project_root / "src"
            python_files = list(src_dir.rglob("*.py"))
        
        with allure.step("Поиск жестко прописанных поддоменов"):
            subdomain_patterns = [
                re.compile(r'panel\.dark-maximus', re.IGNORECASE),
                re.compile(r'help\.dark-maximus', re.IGNORECASE),
                re.compile(r'docs\.dark-maximus', re.IGNORECASE),
                re.compile(r'app\.dark-maximus', re.IGNORECASE),
                re.compile(r'allure\.dark-maximus', re.IGNORECASE),
                re.compile(r'tests\.dark-maximus', re.IGNORECASE),
            ]
            
            violations = []
            
            for file_path in python_files:
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                        lines = content.split('\n')
                        
                        for line_num, line in enumerate(lines, 1):
                            for pattern in subdomain_patterns:
                                if pattern.search(line):
                                    # Пропускаем комментарии и docstrings с примерами
                                    stripped = line.strip()
                                    # Проверяем предыдущую строку на наличие комментария о fallback
                                    prev_line = lines[line_num - 2].strip() if line_num > 1 else ""
                                    # Проверяем текущую строку на наличие комментария о fallback (может быть на той же строке)
                                    has_fallback_comment = (
                                        'fallback' in stripped.lower() or
                                        'default' in stripped.lower() or
                                        '# fallback' in prev_line.lower() or
                                        '# default' in prev_line.lower() or
                                        'fallback' in prev_line.lower() or
                                        'для обратной совместимости' in prev_line.lower() or
                                        '# fallback' in stripped.lower() or
                                        '# default' in stripped.lower()
                                    )
                                    
                                    if not (stripped.startswith('#') or 
                                            'example' in stripped.lower() or
                                            'test' in stripped.lower() or
                                            has_fallback_comment):
                                        violations.append({
                                            'file': str(file_path.relative_to(project_root)),
                                            'line': line_num,
                                            'content': line.strip(),
                                            'pattern': pattern.pattern
                                        })
                except Exception as e:
                    allure.attach(str(e), f"Ошибка чтения {file_path}", allure.attachment_type.TEXT)
            
            if violations:
                violations_text = '\n'.join([f"{v['file']}:{v['line']} ({v['pattern']}): {v['content']}" for v in violations])
                allure.attach(violations_text, "Найденные нарушения", allure.attachment_type.TEXT)
        
        with allure.step("Проверка результата"):
            assert len(violations) == 0, f"Найдено {len(violations)} жестко прописанных поддоменов в Python коде"

    @allure.title("Проверка использования переменных в nginx шаблоне")
    @allure.description("""
    Проверяет, что в nginx шаблоне используются переменные ${DOMAIN} вместо жестких значений.
    
    **Что проверяется:**
    - Отсутствие жестко прописанных доменов в deploy/nginx/*.tpl
    - Использование переменных ${MAIN_DOMAIN}, ${APP_DOMAIN}, ${HELP_DOMAIN} и т.д.
    
    **Ожидаемый результат:**
    В nginx шаблоне должны использоваться только переменные, а не жестко прописанные домены.
    """)
    @allure.severity(allure.severity_level.CRITICAL)
    @allure.tag("nginx", "templates", "hardcoded", "unit", "critical")
    def test_nginx_template_uses_variables(self):
        """Проверка использования переменных в nginx шаблоне"""
        with allure.step("Поиск nginx шаблонов"):
            deploy_dir = project_root / "deploy" / "nginx"
            template_files = list(deploy_dir.glob("*.tpl"))
            allure.attach(str(len(template_files)), "Количество шаблонов", allure.attachment_type.TEXT)
        
        with allure.step("Поиск жестко прописанных доменов"):
            hardcoded_patterns = [
                re.compile(r'dark-maximus\.com', re.IGNORECASE),
                re.compile(r'panel\.dark-maximus', re.IGNORECASE),
                re.compile(r'help\.dark-maximus', re.IGNORECASE),
                re.compile(r'docs\.dark-maximus', re.IGNORECASE),
                re.compile(r'app\.dark-maximus', re.IGNORECASE),
            ]
            
            violations = []
            
            for template_file in template_files:
                try:
                    with open(template_file, 'r', encoding='utf-8') as f:
                        content = f.read()
                        lines = content.split('\n')
                        
                        for line_num, line in enumerate(lines, 1):
                            for pattern in hardcoded_patterns:
                                if pattern.search(line):
                                    # Пропускаем комментарии
                                    stripped = line.strip()
                                    if not stripped.startswith('#'):
                                        violations.append({
                                            'file': str(template_file.relative_to(project_root)),
                                            'line': line_num,
                                            'content': line.strip(),
                                            'pattern': pattern.pattern
                                        })
                except Exception as e:
                    allure.attach(str(e), f"Ошибка чтения {template_file}", allure.attachment_type.TEXT)
            
            if violations:
                violations_text = '\n'.join([f"{v['file']}:{v['line']} ({v['pattern']}): {v['content']}" for v in violations])
                allure.attach(violations_text, "Найденные нарушения", allure.attachment_type.TEXT)
        
        with allure.step("Проверка результата"):
            assert len(violations) == 0, f"Найдено {len(violations)} жестко прописанных доменов в nginx шаблонах"

    @allure.title("Проверка использования переменных в скриптах установки")
    @allure.description("""
    Проверяет, что в скриптах установки используются переменные вместо жестких значений.
    
    **Что проверяется:**
    - Отсутствие жестко прописанных доменов в install.sh, ssl-install.sh, install-autotest.sh
    - Использование переменных ${MAIN_DOMAIN}, ${APP_DOMAIN} и т.д.
    
    **Ожидаемый результат:**
    В скриптах установки должны использоваться только переменные, а не жестко прописанные домены.
    """)
    @allure.severity(allure.severity_level.CRITICAL)
    @allure.tag("scripts", "hardcoded", "unit", "critical")
    def test_scripts_use_domain_variables(self):
        """Проверка использования переменных в скриптах установки"""
        with allure.step("Поиск скриптов установки"):
            script_files = [
                project_root / "install.sh",
                project_root / "ssl-install.sh",
                project_root / "install-autotest.sh",
            ]
            existing_scripts = [f for f in script_files if f.exists()]
            allure.attach(str(len(existing_scripts)), "Количество скриптов", allure.attachment_type.TEXT)
        
        with allure.step("Поиск жестко прописанных доменов"):
            hardcoded_patterns = [
                re.compile(r'dark-maximus\.com', re.IGNORECASE),
                re.compile(r'panel\.dark-maximus', re.IGNORECASE),
                re.compile(r'help\.dark-maximus', re.IGNORECASE),
                re.compile(r'docs\.dark-maximus', re.IGNORECASE),
                re.compile(r'app\.dark-maximus', re.IGNORECASE),
            ]
            
            violations = []
            
            for script_file in existing_scripts:
                try:
                    with open(script_file, 'r', encoding='utf-8') as f:
                        content = f.read()
                        lines = content.split('\n')
                        
                        for line_num, line in enumerate(lines, 1):
                            for pattern in hardcoded_patterns:
                                if pattern.search(line):
                                    # Пропускаем комментарии и примеры
                                    stripped = line.strip()
                                    if not (stripped.startswith('#') or 
                                            'example' in stripped.lower() or
                                            'test' in stripped.lower() or
                                            'fallback' in stripped.lower() or
                                            'default' in stripped.lower() or
                                            'localhost' in stripped.lower()):
                                        violations.append({
                                            'file': str(script_file.relative_to(project_root)),
                                            'line': line_num,
                                            'content': line.strip(),
                                            'pattern': pattern.pattern
                                        })
                except Exception as e:
                    allure.attach(str(e), f"Ошибка чтения {script_file}", allure.attachment_type.TEXT)
            
            if violations:
                violations_text = '\n'.join([f"{v['file']}:{v['line']} ({v['pattern']}): {v['content']}" for v in violations])
                allure.attach(violations_text, "Найденные нарушения", allure.attachment_type.TEXT)
        
        with allure.step("Проверка результата"):
            assert len(violations) == 0, f"Найдено {len(violations)} жестко прописанных доменов в скриптах установки"

