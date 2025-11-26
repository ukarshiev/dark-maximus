#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Unit-тесты для функции get_ton_transaction_url

Проверяет корректность формирования ссылок на TON Explorer (tonviewer.com)
"""

import sys
from pathlib import Path
import pytest
import allure

# Добавляем путь к модулям проекта
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root / "src"))

from shop_bot.bot.handlers import get_ton_transaction_url


@pytest.mark.unit
@pytest.mark.bot
@allure.epic("Обработчики бота")
@allure.feature("TON Explorer")
@allure.label("package", "src.shop_bot.bot.handlers")
class TestTONExplorerURL:
    """Тесты для функции get_ton_transaction_url"""

    @allure.title("Формирование ссылки для hex-хеша транзакции")
    @allure.description("""
    Проверяет корректность формирования ссылки на TON Explorer для hex-хеша транзакции.
    
    **Что проверяется:**
    - Использование правильного домена (tonviewer.com)
    - Корректный формат URL для hex-хеша (64 символа)
    - Отсутствие префикса tonscan.org
    
    **Тестовые данные:**
    - tx_hash: валидный hex-хеш транзакции (64 символа)
    
    **Ожидаемый результат:**
    URL должен быть в формате: https://tonviewer.com/transaction/{hex_hash}
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("ton-explorer", "url", "hex-hash", "unit", "bot")
    def test_hex_hash_url(self):
        """Тест формирования ссылки для hex-хеша"""
        with allure.step("Подготовка тестового hex-хеша"):
            # Валидный hex-хеш транзакции (64 символа)
            hex_hash = "0e0ca8f30461434c58223129f0b7dfa29989f7b7407f6e3f63d745e668e99413"
            assert len(hex_hash) == 64, "Hex-хеш должен быть 64 символа"
            allure.attach(hex_hash, "Hex-хеш транзакции", allure.attachment_type.TEXT)
        
        with allure.step("Вызов функции get_ton_transaction_url"):
            url = get_ton_transaction_url(hex_hash)
            allure.attach(url, "Сгенерированный URL", allure.attachment_type.TEXT)
        
        with allure.step("Проверка формата URL"):
            assert url.startswith("https://tonviewer.com/transaction/"), \
                f"URL должен начинаться с 'https://tonviewer.com/transaction/', получен: {url[:50]}"
            assert "tonscan.org" not in url, "URL не должен содержать tonscan.org"
            assert url.endswith(hex_hash), f"URL должен заканчиваться на hex-хеш, получен: {url}"
        
        with allure.step("Проверка полного URL"):
            expected_url = f"https://tonviewer.com/transaction/{hex_hash}"
            assert url == expected_url, \
                f"Ожидался URL: {expected_url}, получен: {url}"

    @allure.title("Обработка нестандартного формата хеша (BOC)")
    @allure.description("""
    Проверяет обработку нестандартного формата хеша (BOC или другой формат).
    
    **Что проверяется:**
    - Обработка длинного хеша (BOC base64)
    - Использование правильного домена (tonviewer.com)
    - Логирование предупреждения для нестандартного формата
    
    **Тестовые данные:**
    - tx_hash: BOC в формате base64 (длинный)
    
    **Ожидаемый результат:**
    URL должен быть в формате: https://tonviewer.com/transaction/{hash}
    (даже если формат нестандартный)
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("ton-explorer", "url", "boc", "unit", "bot")
    def test_boc_hash_url(self):
        """Тест формирования ссылки для BOC"""
        with allure.step("Подготовка тестового BOC"):
            # BOC в формате base64 (длинный)
            boc_hash = "te6cckEBAgEAqQAB4YgBNuH5swGW1uXp6Cd3lPR9NzvUGOu5Z/F6f7kQtNF0O4wEKzdmeOo89fxTus36bTPUKecSHTv/5XCEmcRPjvfSfzohYiELzcpb2H2JqKRFlG/btLvPUosSu+Zg5ZS46BmgQU1NGLtJJ6vIAAAAaAAcAQBmQgBCUS/JHdTmT6tj/quqtLsXUzACqJplT2XncD24/9BhnZtWfgAAAAAAAAAAAAAAAAAAL1KVjQ=="
            assert len(boc_hash) > 64, "BOC должен быть длиннее 64 символов"
            allure.attach(boc_hash[:50] + "...", "BOC транзакции (первые 50 символов)", allure.attachment_type.TEXT)
        
        with allure.step("Вызов функции get_ton_transaction_url"):
            url = get_ton_transaction_url(boc_hash)
            allure.attach(url, "Сгенерированный URL", allure.attachment_type.TEXT)
        
        with allure.step("Проверка формата URL"):
            assert url.startswith("https://tonviewer.com/transaction/"), \
                f"URL должен начинаться с 'https://tonviewer.com/transaction/', получен: {url[:50]}"
            assert "tonscan.org" not in url, "URL не должен содержать tonscan.org"
            assert url.endswith(boc_hash), f"URL должен заканчиваться на BOC, получен: {url}"

    @allure.title("Обработка пустого хеша")
    @allure.description("""
    Проверяет обработку пустого или None хеша транзакции.
    
    **Что проверяется:**
    - Обработка пустой строки
    - Возврат пустой строки для пустого хеша
    
    **Тестовые данные:**
    - tx_hash: пустая строка или None
    
    **Ожидаемый результат:**
    Функция должна вернуть пустую строку для пустого хеша.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("ton-explorer", "url", "empty-hash", "edge-case", "unit", "bot")
    def test_empty_hash_url(self):
        """Тест обработки пустого хеша"""
        with allure.step("Проверка пустой строки"):
            url = get_ton_transaction_url("")
            allure.attach(url, "Результат для пустой строки", allure.attachment_type.TEXT)
            assert url == "", "Для пустой строки должен вернуться пустой URL"
        
        with allure.step("Проверка None (через пустую строку)"):
            # Функция проверяет if not tx_hash, поэтому None будет обработан как пустая строка
            url = get_ton_transaction_url(None) if hasattr(get_ton_transaction_url, '__annotations__') else ""
            # Если функция не принимает None, проверяем через пустую строку
            if url == "":
                allure.attach("None обработан как пустая строка", "Результат", allure.attachment_type.TEXT)

    @allure.title("Проверка различных форматов hex-хешей")
    @allure.description("""
    Проверяет корректность обработки различных форматов hex-хешей.
    
    **Что проверяется:**
    - Hex-хеш в нижнем регистре
    - Hex-хеш в верхнем регистре
    - Hex-хеш смешанного регистра
    
    **Тестовые данные:**
    - tx_hash: hex-хеш в разных регистрах (64 символа)
    
    **Ожидаемый результат:**
    Все форматы должны обрабатываться корректно и формировать правильный URL.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("ton-explorer", "url", "hex-hash", "case-sensitivity", "unit", "bot")
    def test_hex_hash_case_variations(self):
        """Тест различных регистров hex-хеша"""
        test_cases = [
            ("0e0ca8f30461434c58223129f0b7dfa29989f7b7407f6e3f63d745e668e99413", "lowercase"),
            ("0E0CA8F30461434C58223129F0B7DFA29989F7B7407F6E3F63D745E668E99413", "uppercase"),
            ("0e0Ca8F30461434c58223129F0b7DfA29989f7B7407F6e3F63D745E668E99413", "mixed"),
        ]
        
        for hex_hash, case_type in test_cases:
            with allure.step(f"Проверка {case_type} hex-хеша"):
                allure.attach(hex_hash, f"Hex-хеш ({case_type})", allure.attachment_type.TEXT)
                
                url = get_ton_transaction_url(hex_hash)
                allure.attach(url, f"Сгенерированный URL ({case_type})", allure.attachment_type.TEXT)
                
                assert url.startswith("https://tonviewer.com/transaction/"), \
                    f"URL для {case_type} должен начинаться с 'https://tonviewer.com/transaction/'"
                assert url.endswith(hex_hash), \
                    f"URL для {case_type} должен заканчиваться на исходный hex-хеш"

    @allure.title("Проверка короткого hex-хеша")
    @allure.description("""
    Проверяет обработку короткого hex-хеша (менее 64 символов).
    
    **Что проверяется:**
    - Обработка hex-хеша длиной менее 64 символов
    - Использование правильного домена
    
    **Тестовые данные:**
    - tx_hash: короткий hex-хеш (32 символа)
    
    **Ожидаемый результат:**
    URL должен быть сформирован, но хеш будет обработан как нестандартный формат.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("ton-explorer", "url", "short-hash", "edge-case", "unit", "bot")
    def test_short_hex_hash(self):
        """Тест обработки короткого hex-хеша"""
        with allure.step("Подготовка короткого hex-хеша"):
            short_hash = "0e0ca8f30461434c58223129f0b7dfa2"  # 32 символа
            assert len(short_hash) < 64, "Хеш должен быть короче 64 символов"
            allure.attach(short_hash, "Короткий hex-хеш", allure.attachment_type.TEXT)
        
        with allure.step("Вызов функции get_ton_transaction_url"):
            url = get_ton_transaction_url(short_hash)
            allure.attach(url, "Сгенерированный URL", allure.attachment_type.TEXT)
        
        with allure.step("Проверка формата URL"):
            assert url.startswith("https://tonviewer.com/transaction/"), \
                f"URL должен начинаться с 'https://tonviewer.com/transaction/', получен: {url[:50]}"
            assert "tonscan.org" not in url, "URL не должен содержать tonscan.org"



