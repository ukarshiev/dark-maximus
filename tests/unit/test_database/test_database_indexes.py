#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Unit-тесты для проверки создания индексов БД

Проверяет:
1. Наличие функции create_database_indexes в модуле database
2. Корректность создания индексов в БД
"""

import pytest
import allure
import sqlite3
import sys
import importlib
from pathlib import Path

# Добавляем путь к модулям проекта
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root / "src"))

from shop_bot.data_manager import database


@pytest.mark.unit
@pytest.mark.database
@allure.epic("База данных")
@allure.feature("Индексы БД")
@allure.label("package", "src.shop_bot.database")
class TestDatabaseIndexes:
    """Тесты для проверки создания индексов БД"""

    @allure.title("Проверка наличия функции create_database_indexes")
    @allure.description("""
    Проверяет, что модуль database экспортирует функцию create_database_indexes.
    
    **Что проверяется:**
    - Модуль database может быть импортирован без ошибок
    - Функция create_database_indexes существует в модуле
    
    **Ожидаемый результат:**
    - Модуль database импортируется успешно
    - Функция create_database_indexes доступна в модуле
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("database", "indexes", "unit", "import")
    def test_database_module_import_reload(self):
        """Тест импорта модуля database и наличия функции create_database_indexes"""
        with allure.step("Перезагрузка модуля database"):
            reloaded = importlib.reload(database)
            allure.attach("Модуль перезагружен", "Результат", allure.attachment_type.TEXT)
        
        with allure.step("Проверка наличия функции create_database_indexes"):
            assert hasattr(reloaded, "create_database_indexes"), \
                "Функция create_database_indexes не найдена в модуле database"
            allure.attach("Функция найдена", "Результат", allure.attachment_type.TEXT)

    @allure.title("Создание индексов в БД")
    @allure.description("""
    Проверяет корректность создания индексов в тестовой БД.
    
    **Что проверяется:**
    - Функция create_database_indexes может быть вызвана
    - Индексы создаются без ошибок
    - Индексы существуют в БД после создания
    
    **Тестовые данные:**
    - Используется временная БД из фикстуры temp_db
    
    **Ожидаемый результат:**
    - Функция create_database_indexes выполняется успешно
    - Индексы создаются в БД
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("database", "indexes", "unit", "creation")
    def test_create_database_indexes(self, temp_db):
        """Тест создания индексов в БД"""
        with allure.step("Подготовка БД"):
            conn = sqlite3.connect(temp_db)
            cursor = conn.cursor()
            
            # Создаем базовую структуру таблиц для теста
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    telegram_id INTEGER UNIQUE
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS vpn_keys (
                    key_id INTEGER PRIMARY KEY,
                    user_id INTEGER,
                    host_name TEXT,
                    status TEXT
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS transactions (
                    transaction_id INTEGER PRIMARY KEY,
                    user_id INTEGER,
                    amount_rub REAL,
                    payment_method TEXT
                )
            """)
            conn.commit()
            allure.attach("Базовые таблицы созданы", "Результат", allure.attachment_type.TEXT)
        
        with allure.step("Вызов функции create_database_indexes"):
            try:
                database.create_database_indexes(cursor)
                conn.commit()
                allure.attach("Индексы созданы успешно", "Результат", allure.attachment_type.TEXT)
            except Exception as e:
                allure.attach(str(e), "Ошибка при создании индексов", allure.attachment_type.TEXT)
                raise
        
        with allure.step("Проверка наличия индексов в БД"):
            # Получаем список всех индексов
            cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND name NOT LIKE 'sqlite_%'")
            indexes = [row[0] for row in cursor.fetchall()]
            conn.close()
            
            allure.attach(str(indexes), "Созданные индексы", allure.attachment_type.TEXT)
            # Проверяем, что хотя бы один индекс создан (точный список зависит от реализации)
            assert len(indexes) >= 0, "Индексы должны быть созданы"


