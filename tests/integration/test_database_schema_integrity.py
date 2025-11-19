#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Тест для проверки целостности схемы базы данных на продакшне.

Этот тест сравнивает структуру продакшн БД с эталонной локальной БД,
проверяя:
- Наличие всех таблиц
- Структуру всех колонок (типы, ограничения, значения по умолчанию)
- Наличие всех индексов
- PRAGMA настройки

ВАЖНО: Тест запускается ТОЛЬКО на продакшне при установке ENVIRONMENT=production в .env

Настройки через .env:
- ENVIRONMENT=production - включить тест (development/test - отключить)
- Пути к БД определяются автоматически
"""

import pytest
import sqlite3
import os
import json
import tempfile
from pathlib import Path
from typing import Dict, List, Tuple, Any, Optional
import allure

# Добавляем путь к src для импорта модулей
import sys
project_root = Path(__file__).parent.parent.parent
src_path = project_root / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from shop_bot.data_manager import database


def is_production_environment() -> bool:
    """
    Проверяет, запущен ли тест в продакшн окружении.
    Читает из .env файла (загружается через conftest.py).
    
    Returns:
        True если ENVIRONMENT=production в .env
    """
    env = os.getenv("ENVIRONMENT", "").strip().lower()
    # Обрабатываем случай, когда в .env файле комментарий в той же строке
    # Например: "ENVIRONMENT=production - комментарий"
    if " " in env:
        env = env.split()[0]  # Берем только первое слово до пробела
    return env == "production"


def get_reference_db_path() -> Optional[Path]:
    """
    Получает путь к эталонной БД.
    Автоматически ищет локальную users.db в корне проекта.
    
    Returns:
        Path к эталонной БД или None если нужно создать из кода
    """
    # Ищем локальную БД в корне проекта
    local_db = project_root / "users.db"
    if local_db.exists():
        return local_db
    
    # Если не найдена - вернем None, создадим из кода
    return None


def get_production_db_path() -> Path:
    """
    Получает путь к продакшн БД.
    Автоматически определяет путь к продакшн БД.
    
    Returns:
        Path к продакшн БД
    """
    # Стандартный путь для Docker контейнера
    default_path = Path("/app/project/users.db")
    if default_path.exists():
        return default_path
    
    # Fallback: путь из database.DB_FILE
    if database.DB_FILE.exists():
        return database.DB_FILE
    
    raise FileNotFoundError(
        f"Продакшн БД не найдена. Проверьте, что БД существует по пути: {default_path}"
    )


def create_reference_db_from_code() -> Path:
    """
    Создает эталонную БД из кода (только структура, без данных).
    
    Returns:
        Path к созданной временной БД
    """
    # Создаем временную БД
    temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
    temp_db_path = Path(temp_db.name)
    temp_db.close()
    
    # Инициализируем БД через database.initialize_db()
    # Временно меняем DB_FILE для создания эталонной БД
    original_db_file = database.DB_FILE
    try:
        database.DB_FILE = temp_db_path
        database.initialize_db()
    finally:
        database.DB_FILE = original_db_file
    
    return temp_db_path


def get_database_schema(db_path: Path) -> Dict[str, Any]:
    """
    Извлекает полную схему базы данных.
    
    Args:
        db_path: Путь к файлу БД
        
    Returns:
        Словарь с полной схемой БД:
        - tables: список таблиц с их колонками
        - indexes: список индексов
        - pragmas: PRAGMA настройки
    """
    schema = {
        "tables": {},
        "indexes": [],
        "pragmas": {}
    }
    
    if not db_path.exists():
        raise FileNotFoundError(f"База данных не найдена: {db_path}")
    
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    
    try:
        # Получаем список всех таблиц
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name NOT LIKE 'sqlite_%'
            ORDER BY name
        """)
        tables = [row[0] for row in cursor.fetchall()]
        
        # Для каждой таблицы получаем структуру колонок
        for table_name in tables:
            cursor.execute(f"PRAGMA table_info({table_name})")
            columns_info = cursor.fetchall()
            
            # Структура: (cid, name, type, notnull, dflt_value, pk)
            columns = []
            for col_info in columns_info:
                columns.append({
                    "name": col_info[1],
                    "type": col_info[2],
                    "notnull": bool(col_info[3]),
                    "default": col_info[4],
                    "primary_key": bool(col_info[5])
                })
            
            # Получаем CREATE TABLE SQL для проверки ограничений
            cursor.execute("""
                SELECT sql FROM sqlite_master 
                WHERE type='table' AND name=?
            """, (table_name,))
            create_sql = cursor.fetchone()
            
            schema["tables"][table_name] = {
                "columns": columns,
                "create_sql": create_sql[0] if create_sql else None
            }
        
        # Получаем все индексы
        cursor.execute("""
            SELECT name, tbl_name, sql FROM sqlite_master 
            WHERE type='index' AND name NOT LIKE 'sqlite_%'
            ORDER BY tbl_name, name
        """)
        indexes = cursor.fetchall()
        
        for idx_info in indexes:
            schema["indexes"].append({
                "name": idx_info[0],
                "table": idx_info[1],
                "sql": idx_info[2]
            })
        
        # Получаем важные PRAGMA настройки
        pragma_settings = [
            "journal_mode",
            "synchronous",
            "cache_size",
            "temp_store",
            "busy_timeout",
            "foreign_keys",
            "page_size"
        ]
        
        for pragma in pragma_settings:
            try:
                cursor.execute(f"PRAGMA {pragma}")
                result = cursor.fetchone()
                if result:
                    schema["pragmas"][pragma] = result[0]
            except sqlite3.Error:
                # Некоторые PRAGMA могут не поддерживаться
                pass
        
    finally:
        conn.close()
    
    return schema


def compare_schemas(reference_schema: Dict[str, Any], 
                   production_schema: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """
    Сравнивает две схемы БД и возвращает список различий.
    
    Args:
        reference_schema: Эталонная схема (локальная БД)
        production_schema: Схема продакшн БД
        
    Returns:
        Кортеж (is_match, differences):
        - is_match: True если схемы идентичны
        - differences: список строк с описанием различий
    """
    differences = []
    
    # Проверяем таблицы
    ref_tables = set(reference_schema["tables"].keys())
    prod_tables = set(production_schema["tables"].keys())
    
    # Отсутствующие таблицы в продакшне
    missing_tables = ref_tables - prod_tables
    for table in missing_tables:
        differences.append(f"❌ Таблица '{table}' отсутствует в продакшн БД")
    
    # Лишние таблицы в продакшне
    extra_tables = prod_tables - ref_tables
    for table in extra_tables:
        differences.append(f"⚠️ Таблица '{table}' присутствует в продакшн БД, но отсутствует в эталонной")
    
    # Проверяем структуру общих таблиц
    common_tables = ref_tables & prod_tables
    for table in common_tables:
        ref_table = reference_schema["tables"][table]
        prod_table = production_schema["tables"][table]
        
        # Проверяем колонки
        ref_columns = {col["name"]: col for col in ref_table["columns"]}
        prod_columns = {col["name"]: col for col in prod_table["columns"]}
        
        # Отсутствующие колонки
        missing_columns = set(ref_columns.keys()) - set(prod_columns.keys())
        for col_name in missing_columns:
            differences.append(
                f"❌ Таблица '{table}': колонка '{col_name}' отсутствует в продакшн БД"
            )
        
        # Лишние колонки
        extra_columns = set(prod_columns.keys()) - set(ref_columns.keys())
        for col_name in extra_columns:
            differences.append(
                f"⚠️ Таблица '{table}': колонка '{col_name}' присутствует в продакшн БД, но отсутствует в эталонной"
            )
        
        # Проверяем свойства общих колонок
        common_columns = set(ref_columns.keys()) & set(prod_columns.keys())
        for col_name in common_columns:
            ref_col = ref_columns[col_name]
            prod_col = prod_columns[col_name]
            
            # Тип колонки
            if ref_col["type"].upper() != prod_col["type"].upper():
                differences.append(
                    f"⚠️ Таблица '{table}': колонка '{col_name}' имеет разный тип "
                    f"(эталон: {ref_col['type']}, продакшн: {prod_col['type']})"
                )
            
            # NOT NULL
            if ref_col["notnull"] != prod_col["notnull"]:
                differences.append(
                    f"⚠️ Таблица '{table}': колонка '{col_name}' имеет разное ограничение NOT NULL "
                    f"(эталон: {ref_col['notnull']}, продакшн: {prod_col['notnull']})"
                )
            
            # PRIMARY KEY
            if ref_col["primary_key"] != prod_col["primary_key"]:
                differences.append(
                    f"❌ Таблица '{table}': колонка '{col_name}' имеет разный статус PRIMARY KEY "
                    f"(эталон: {ref_col['primary_key']}, продакшн: {prod_col['primary_key']})"
                )
            
            # DEFAULT значение (нормализуем для сравнения)
            ref_default = str(ref_col["default"]).lower() if ref_col["default"] else None
            prod_default = str(prod_col["default"]).lower() if prod_col["default"] else None
            if ref_default != prod_default:
                differences.append(
                    f"⚠️ Таблица '{table}': колонка '{col_name}' имеет разное значение по умолчанию "
                    f"(эталон: {ref_col['default']}, продакшн: {prod_col['default']})"
                )
    
    # Проверяем индексы
    ref_indexes = {(idx["table"], idx["name"]) for idx in reference_schema["indexes"]}
    prod_indexes = {(idx["table"], idx["name"]) for idx in production_schema["indexes"]}
    
    # Отсутствующие индексы
    missing_indexes = ref_indexes - prod_indexes
    for table, idx_name in missing_indexes:
        differences.append(
            f"❌ Индекс '{idx_name}' на таблице '{table}' отсутствует в продакшн БД"
        )
    
    # Лишние индексы (предупреждение, не критично)
    extra_indexes = prod_indexes - ref_indexes
    for table, idx_name in extra_indexes:
        differences.append(
            f"⚠️ Индекс '{idx_name}' на таблице '{table}' присутствует в продакшн БД, но отсутствует в эталонной"
        )
    
    # Проверяем PRAGMA настройки (только важные)
    important_pragmas = ["journal_mode", "synchronous", "foreign_keys"]
    for pragma in important_pragmas:
        ref_value = reference_schema["pragmas"].get(pragma)
        prod_value = production_schema["pragmas"].get(pragma)
        
        if ref_value != prod_value:
            differences.append(
                f"⚠️ PRAGMA {pragma} различается "
                f"(эталон: {ref_value}, продакшн: {prod_value})"
            )
    
    return len(differences) == 0, differences


@pytest.mark.integration
@pytest.mark.database
@allure.epic("Интеграционные тесты")
@allure.feature("Целостность базы данных")
@allure.label("package", "tests.integration")
class TestDatabaseSchemaIntegrity:
    """Тесты для проверки целостности схемы базы данных на продакшне"""
    
    @pytest.fixture(autouse=True)
    def check_production_environment(self):
        """Проверяет, что тест запущен в продакшн окружении (из .env)"""
        if not is_production_environment():
            pytest.skip(
                "Тест запускается только на продакшне. "
                "Установите ENVIRONMENT=production в .env файле"
            )
    
    @pytest.fixture
    def reference_db_path(self):
        """Получает или создает эталонную БД"""
        ref_path = get_reference_db_path()
        
        if ref_path is None:
            # Создаем эталонную БД из кода
            allure.attach(
                "Эталонная БД не найдена. Создана из кода (только структура, без данных).",
                "Информация",
                allure.attachment_type.TEXT
            )
            temp_db = create_reference_db_from_code()
            yield temp_db
            # Удаляем временную БД после теста
            try:
                temp_db.unlink()
            except:
                pass
        else:
            yield ref_path
    
    @allure.story("Проверка целостности схемы БД")
    @allure.title("Сравнение структуры продакшн БД с эталонной локальной БД")
    @allure.description("""
    Проверяет, что структура продакшн БД полностью соответствует эталонной локальной БД.
    
    **Что проверяется:**
    - Наличие всех таблиц
    - Структура всех колонок (типы, ограничения, значения по умолчанию)
    - Наличие всех индексов
    - Важные PRAGMA настройки
    
    **Настройки через .env:**
    - ENVIRONMENT=production - включить тест (development/test - отключить)
    - Пути к БД определяются автоматически
    
    **Предусловия:**
    - Тест запускается только при ENVIRONMENT=production в .env
    - Обе БД должны существовать и быть доступны
    
    **Ожидаемый результат:**
    Структура продакшн БД полностью соответствует эталонной локальной БД.
    """)
    @allure.severity(allure.severity_level.CRITICAL)
    @allure.tag("database", "schema", "integrity", "production", "critical")
    def test_production_db_schema_matches_reference(self, reference_db_path):
        """Проверяет, что структура продакшн БД соответствует эталонной"""
        # Получаем путь к продакшн БД (автоматическое определение)
        production_db_path = get_production_db_path()
        
        with allure.step("Проверка наличия БД"):
            assert reference_db_path.exists(), \
                f"Эталонная БД не найдена: {reference_db_path}"
            assert production_db_path.exists(), \
                f"Продакшн БД не найдена: {production_db_path}"
            
            # Определяем источник эталонной БД
            ref_source = "локальная users.db из корня проекта" if (project_root / "users.db").exists() else \
                        "создана из кода"
            
            prod_source = "стандартный путь (/app/project/users.db)" if production_db_path == Path("/app/project/users.db") else \
                         f"database.DB_FILE ({production_db_path})"
            
            allure.attach(
                f"Эталонная БД: {reference_db_path}\n"
                f"Источник: {ref_source}\n"
                f"Продакшн БД: {production_db_path}\n"
                f"Источник: {prod_source}\n"
                f"ENVIRONMENT: {os.getenv('ENVIRONMENT', 'не установлен')}",
                "Конфигурация теста",
                allure.attachment_type.TEXT
            )
        
        with allure.step("Извлечение схемы эталонной БД"):
            reference_schema = get_database_schema(reference_db_path)
            allure.attach(
                json.dumps({
                    "tables_count": len(reference_schema["tables"]),
                    "indexes_count": len(reference_schema["indexes"]),
                    "tables": list(reference_schema["tables"].keys())
                }, indent=2, ensure_ascii=False),
                "Схема эталонной БД",
                allure.attachment_type.JSON
            )
        
        with allure.step("Извлечение схемы продакшн БД"):
            production_schema = get_database_schema(production_db_path)
            allure.attach(
                json.dumps({
                    "tables_count": len(production_schema["tables"]),
                    "indexes_count": len(production_schema["indexes"]),
                    "tables": list(production_schema["tables"].keys())
                }, indent=2, ensure_ascii=False),
                "Схема продакшн БД",
                allure.attachment_type.JSON
            )
        
        with allure.step("Сравнение схем БД"):
            is_match, differences = compare_schemas(reference_schema, production_schema)
            
            if differences:
                differences_text = "\n".join(differences)
                allure.attach(
                    differences_text,
                    "Различия в схемах БД",
                    allure.attachment_type.TEXT
                )
                
                # Разделяем критические и некритические различия
                critical_diffs = [d for d in differences if d.startswith("❌")]
                warnings = [d for d in differences if d.startswith("⚠️")]
                
                if critical_diffs:
                    allure.attach(
                        "\n".join(critical_diffs),
                        "Критические различия",
                        allure.attachment_type.TEXT
                    )
                
                if warnings:
                    allure.attach(
                        "\n".join(warnings),
                        "Предупреждения",
                        allure.attachment_type.TEXT
                    )
            
            # Проверяем результат
            assert is_match, (
                f"Структура продакшн БД не соответствует эталонной!\n\n"
                f"Найдено различий: {len(differences)}\n\n"
                f"Различия:\n" + "\n".join(differences)
            )

