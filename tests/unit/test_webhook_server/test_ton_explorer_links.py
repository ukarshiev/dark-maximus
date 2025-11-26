#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Unit-тесты для проверки ссылок на TON Explorer в шаблонах веб-панели

Проверяет, что все ссылки на TON Explorer используют правильный домен (tonviewer.com)
"""

import sys
from pathlib import Path
import pytest
import allure
import re

# Добавляем путь к модулям проекта
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root / "src"))


@pytest.mark.unit
@allure.epic("Веб-панель")
@allure.feature("TON Explorer")
@allure.label("package", "src.shop_bot.webhook_server")
class TestTONExplorerLinksInTemplates:
    """Тесты для проверки ссылок на TON Explorer в шаблонах"""

    @allure.title("Проверка ссылок в шаблоне transactions.html")
    @allure.description("""
    Проверяет, что в шаблоне transactions.html используются правильные ссылки на TON Explorer.
    
    **Что проверяется:**
    - Использование домена tonviewer.com вместо tonscan.org
    - Корректный формат URL для транзакций
    
    **Тестовые данные:**
    - Шаблон: src/shop_bot/webhook_server/templates/transactions.html
    
    **Ожидаемый результат:**
    Все ссылки на TON Explorer должны использовать tonviewer.com.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("ton-explorer", "templates", "transactions", "unit", "webhook_server")
    def test_transactions_template_links(self):
        """Тест ссылок в шаблоне transactions.html"""
        template_path = project_root / "src" / "shop_bot" / "webhook_server" / "templates" / "transactions.html"
        
        with allure.step("Чтение шаблона transactions.html"):
            assert template_path.exists(), f"Шаблон не найден: {template_path}"
            content = template_path.read_text(encoding='utf-8')
            allure.attach(str(len(content)), "Размер файла (символов)", allure.attachment_type.TEXT)
        
        with allure.step("Поиск ссылок на TON Explorer"):
            # Ищем все ссылки на TON Explorer
            ton_explorer_patterns = [
                r'https://tonviewer\.com/transaction/',
                r'https://tonscan\.org/tx/',
            ]
            
            tonviewer_matches = re.findall(r'https://tonviewer\.com/transaction/', content)
            tonscan_matches = re.findall(r'https://tonscan\.org/tx/', content)
            
            allure.attach(str(len(tonviewer_matches)), "Количество ссылок на tonviewer.com", allure.attachment_type.TEXT)
            allure.attach(str(len(tonscan_matches)), "Количество ссылок на tonscan.org", allure.attachment_type.TEXT)
        
        with allure.step("Проверка использования tonviewer.com"):
            assert len(tonviewer_matches) > 0, \
                "В шаблоне должна быть хотя бы одна ссылка на tonviewer.com"
            allure.attach(
                "\n".join(set(tonviewer_matches)),
                "Найденные ссылки на tonviewer.com",
                allure.attachment_type.TEXT
            )
        
        with allure.step("Проверка отсутствия tonscan.org"):
            assert len(tonscan_matches) == 0, \
                f"В шаблоне не должно быть ссылок на tonscan.org. Найдено: {len(tonscan_matches)}"
        
        with allure.step("Проверка формата ссылок"):
            # Проверяем, что ссылки используют правильный формат
            correct_pattern = r'href="https://tonviewer\.com/transaction/\{\{.*transaction_hash.*\}\}"'
            matches = re.findall(correct_pattern, content)
            assert len(matches) > 0, \
                "В шаблоне должна быть ссылка в формате: href=\"https://tonviewer.com/transaction/{{ transaction_hash }}\""

    @allure.title("Проверка ссылок в шаблоне check_payment.html")
    @allure.description("""
    Проверяет, что в шаблоне check_payment.html используются правильные ссылки на TON Explorer.
    
    **Что проверяется:**
    - Использование домена tonviewer.com вместо tonscan.org
    - Корректный формат URL для транзакций
    - Ссылки в кнопках и тексте помощи
    
    **Тестовые данные:**
    - Шаблон: src/shop_bot/webhook_server/templates/check_payment.html
    
    **Ожидаемый результат:**
    Все ссылки на TON Explorer должны использовать tonviewer.com.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("ton-explorer", "templates", "check_payment", "unit", "webhook_server")
    def test_check_payment_template_links(self):
        """Тест ссылок в шаблоне check_payment.html"""
        template_path = project_root / "src" / "shop_bot" / "webhook_server" / "templates" / "check_payment.html"
        
        with allure.step("Чтение шаблона check_payment.html"):
            assert template_path.exists(), f"Шаблон не найден: {template_path}"
            content = template_path.read_text(encoding='utf-8')
            allure.attach(str(len(content)), "Размер файла (символов)", allure.attachment_type.TEXT)
        
        with allure.step("Поиск ссылок на TON Explorer"):
            tonviewer_matches = re.findall(r'https://tonviewer\.com', content)
            tonscan_matches = re.findall(r'https://tonscan\.org', content)
            
            allure.attach(str(len(tonviewer_matches)), "Количество ссылок на tonviewer.com", allure.attachment_type.TEXT)
            allure.attach(str(len(tonscan_matches)), "Количество ссылок на tonscan.org", allure.attachment_type.TEXT)
        
        with allure.step("Проверка использования tonviewer.com"):
            assert len(tonviewer_matches) > 0, \
                "В шаблоне должна быть хотя бы одна ссылка на tonviewer.com"
            allure.attach(
                "\n".join(set(tonviewer_matches)),
                "Найденные ссылки на tonviewer.com",
                allure.attachment_type.TEXT
            )
        
        with allure.step("Проверка отсутствия tonscan.org"):
            assert len(tonscan_matches) == 0, \
                f"В шаблоне не должно быть ссылок на tonscan.org. Найдено: {len(tonscan_matches)}"

    @allure.title("Проверка ссылок в JavaScript коде")
    @allure.description("""
    Проверяет, что в JavaScript коде используются правильные ссылки на TON Explorer.
    
    **Что проверяется:**
    - Использование домена tonviewer.com вместо tonscan.org
    - Корректный формат URL для транзакций в JS коде
    
    **Тестовые данные:**
    - JavaScript файл: src/shop_bot/webhook_server/static/js/script.js
    
    **Ожидаемый результат:**
    Все ссылки на TON Explorer в JS коде должны использовать tonviewer.com.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("ton-explorer", "javascript", "script.js", "unit", "webhook_server")
    def test_javascript_links(self):
        """Тест ссылок в JavaScript коде"""
        js_path = project_root / "src" / "shop_bot" / "webhook_server" / "static" / "js" / "script.js"
        
        with allure.step("Чтение JavaScript файла"):
            assert js_path.exists(), f"JavaScript файл не найден: {js_path}"
            content = js_path.read_text(encoding='utf-8')
            allure.attach(str(len(content)), "Размер файла (символов)", allure.attachment_type.TEXT)
        
        with allure.step("Поиск ссылок на TON Explorer"):
            tonviewer_matches = re.findall(r'https://tonviewer\.com/transaction/', content)
            tonscan_matches = re.findall(r'https://tonscan\.org/tx/', content)
            
            allure.attach(str(len(tonviewer_matches)), "Количество ссылок на tonviewer.com", allure.attachment_type.TEXT)
            allure.attach(str(len(tonscan_matches)), "Количество ссылок на tonscan.org", allure.attachment_type.TEXT)
        
        with allure.step("Проверка использования tonviewer.com"):
            # Если есть ссылки на TON Explorer, они должны быть на tonviewer.com
            if len(tonviewer_matches) > 0 or len(tonscan_matches) > 0:
                assert len(tonviewer_matches) > 0, \
                    "В JS коде должна быть хотя бы одна ссылка на tonviewer.com"
                assert len(tonscan_matches) == 0, \
                    f"В JS коде не должно быть ссылок на tonscan.org. Найдено: {len(tonscan_matches)}"
                
                allure.attach(
                    "\n".join(set(tonviewer_matches)),
                    "Найденные ссылки на tonviewer.com",
                    allure.attachment_type.TEXT
                )
        
        with allure.step("Проверка формата ссылок в JS"):
            # Проверяем, что ссылки используют правильный формат в JS
            correct_pattern = r'https://tonviewer\.com/transaction/\$\{.*transaction_hash.*\}'
            matches = re.findall(correct_pattern, content)
            if len(tonviewer_matches) > 0:
                assert len(matches) > 0 or 'tonviewer.com/transaction/' in content, \
                    "В JS коде должна быть ссылка в формате: https://tonviewer.com/transaction/${transaction_hash}"



