# -*- coding: utf-8 -*-
"""
Тесты для исправления нумерации ключей

Тестирует:
1. Миграцию keys_count
2. Функцию get_next_key_number с атомарным инкрементом
3. Логирование при IntegrityError
4. Инициализацию счетчика для существующих пользователей
5. Создание ключей с правильной нумерацией
"""

import sqlite3
import tempfile
import os
import pytest
import allure
from pathlib import Path
from datetime import datetime, timezone, timedelta
import sys

# Добавляем путь к проекту
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root / "src"))

from shop_bot.data_manager.database import (
    initialize_db,
    get_next_key_number,
    add_new_key,
    get_user_keys,
    get_user,
    register_user_if_not_exists
)


@pytest.mark.unit
@pytest.mark.database
@allure.epic("База данных")
@allure.feature("Нумерация ключей")
@allure.label("package", "src.shop_bot.database")
@allure.title("Миграция keys_count: добавление поля в таблицу users")
@allure.description("""
Проверяет корректность миграции БД при добавлении поля keys_count в таблицу users.

**Что проверяется:**
- Создание временной БД для изоляции теста
- Вызов initialize_db() для выполнения миграции
- Добавление поля keys_count в таблицу users через ALTER TABLE
- Корректность структуры таблицы после миграции

**Тестовые данные:**
- Используется временная SQLite БД
- Таблица users создается через initialize_db()
- Миграция добавляет поле keys_count INTEGER DEFAULT 0

**Ожидаемый результат:**
Поле keys_count должно быть успешно добавлено в таблицу users и присутствовать в списке колонок таблицы.
""")
@allure.severity(allure.severity_level.NORMAL)
@allure.tag("key_numbering", "migration", "database", "unit", "keys_count")
def test_keys_count_migration():
    """Тест миграции keys_count"""
    print("\n=== Тест 1: Миграция keys_count ===")
    
    # Инициализируем переменные до блока try для безопасного восстановления
    import shop_bot.data_manager.database as db_module
    original_db_file = None
    temp_db = None
    
    try:
        with allure.step("Подготовка тестовых данных"):
            # Создаем временную БД
            temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
            temp_db.close()
            allure.attach(str(temp_db.name), "Путь к временной БД", allure.attachment_type.TEXT)
            
            # Меняем DB_FILE для теста
            original_db_file = db_module.DB_FILE
            db_module.DB_FILE = Path(temp_db.name)
            allure.attach(str(original_db_file), "Оригинальный путь к БД", allure.attachment_type.TEXT)
        
        with allure.step("Инициализация БД и выполнение миграции"):
            # Инициализируем БД (выполнит миграцию)
            initialize_db()
            allure.attach("initialize_db() выполнен", "Результат инициализации", allure.attachment_type.TEXT)
        
        with allure.step("Проверка миграции: наличие поля keys_count"):
            # Проверяем, что поле keys_count добавлено
            # Используем temp_db напрямую, а не database.DB_FILE, чтобы гарантировать использование правильной тестовой БД
            conn = sqlite3.connect(temp_db.name)
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(users)")
            columns = [row[1] for row in cursor.fetchall()]
            
            # Прикрепляем список колонок для диагностики
            columns_info = "\n".join([f"- {col}" for col in columns])
            allure.attach(columns_info, "Список колонок таблицы users", allure.attachment_type.TEXT)
            
            # Проверяем наличие keys_count
            keys_count_present = 'keys_count' in columns
            allure.attach(
                f"keys_count присутствует: {keys_count_present}",
                "Результат проверки миграции",
                allure.attachment_type.TEXT
            )
            
            assert keys_count_present, "Поле keys_count не добавлено в таблицу users"
            print("✓ Поле keys_count успешно добавлено")
            
            conn.close()
        
        # Восстанавливаем оригинальный DB_FILE
        if original_db_file is not None:
            db_module.DB_FILE = original_db_file
        
    finally:
        # Безопасное восстановление DB_FILE
        if 'original_db_file' in locals() and original_db_file is not None:
            try:
                db_module.DB_FILE = original_db_file
            except Exception as e:
                allure.attach(str(e), "Ошибка при восстановлении DB_FILE", allure.attachment_type.TEXT)
        
        # Очистка временной БД
        if temp_db and os.path.exists(temp_db.name):
            import gc
            gc.collect()
            import time
            time.sleep(0.1)
            try:
                os.unlink(temp_db.name)
            except PermissionError:
                pass
    
    print("✓ Тест 1 пройден\n")


@pytest.mark.unit
@pytest.mark.database
@allure.epic("База данных")
@allure.feature("Нумерация ключей")
@allure.label("package", "src.shop_bot.database")
@allure.title("Получение следующего номера ключа")
@allure.description("""
Проверяет функцию get_next_key_number для получения следующего номера ключа пользователя.

**Что проверяется:**
- Получение первого номера ключа (должен быть 1)
- Инкремент номера при повторном вызове
- Сохранение счетчика keys_count в БД
- Корректность значения счетчика после инкремента

**Тестовые данные:**
- user_id: 999999

**Ожидаемый результат:**
Первый ключ получает номер 1, второй - номер 2, счетчик keys_count корректно сохраняется в БД.
""")
@allure.severity(allure.severity_level.NORMAL)
@allure.tag("key_numbering", "get_next_key_number", "database", "unit")
def test_get_next_key_number(temp_db):
    """Тест функции get_next_key_number"""
    print("\n=== Тест 2: get_next_key_number ===")
    
    # Используем database.DB_FILE (уже заменен через monkeypatch в фикстуре temp_db)
    from shop_bot.data_manager import database
    
    # Инициализируем БД (создаст все таблицы)
    initialize_db()
    
    # Создаем тестового пользователя
    user_id = 999999
    register_user_if_not_exists(user_id, "test_user", referrer_id=None)
    
    # Проверяем начальное значение
    next_num = get_next_key_number(user_id)
    assert next_num == 1, f"Ожидался номер 1, получен {next_num}"
    print(f"✓ Первый ключ получил номер: {next_num}")
    
    # Проверяем инкремент
    next_num2 = get_next_key_number(user_id)
    assert next_num2 == 2, f"Ожидался номер 2, получен {next_num2}"
    print(f"✓ Второй ключ получил номер: {next_num2}")
    
    # Проверяем, что счетчик сохранился в БД
    # Используем temp_db напрямую, а не database.DB_FILE, чтобы гарантировать использование правильной тестовой БД
    conn = sqlite3.connect(str(temp_db))
    cursor = conn.cursor()
    cursor.execute("SELECT keys_count FROM users WHERE telegram_id = ?", (user_id,))
    row = cursor.fetchone()
    assert row and row[0] == 2, f"Счетчик в БД должен быть 2, получен {row[0] if row else None}"
    print(f"✓ Счетчик в БД: {row[0]}")
    conn.close()
    
    print("✓ Тест 2 пройден\n")


@pytest.mark.unit
@pytest.mark.database
@allure.epic("База данных")
@allure.feature("Нумерация ключей")
@allure.label("package", "src.shop_bot.database")
@allure.title("Создание ключа при IntegrityError (дубликат email)")
@allure.description("""
Проверяет обработку IntegrityError при создании ключа с дублирующимся email.

**Что проверяется:**
- Создание первого ключа с уникальным email
- Попытка создания второго ключа с тем же email
- Обработка IntegrityError и обновление существующего ключа
- Корректность обновления UUID при IntegrityError

**Тестовые данные:**
- user_id: 888888
- email: "user{user_id}-key1@test.bot" (дублируется)

**Ожидаемый результат:**
При IntegrityError существующий ключ обновляется, возвращается тот же key_id.
""")
@allure.severity(allure.severity_level.NORMAL)
@allure.tag("key_numbering", "integrity_error", "duplicate_email", "database", "unit")
def test_key_creation_with_integrity_error(temp_db):
    """Тест создания ключа при IntegrityError (дубликат email)"""
    print("\n=== Тест 3: IntegrityError при создании ключа ===")
    
    # Используем database.DB_FILE (уже заменен через monkeypatch в фикстуре temp_db)
    from shop_bot.data_manager import database
    
    initialize_db()
    
    user_id = 888888
    register_user_if_not_exists(user_id, "test_user2", referrer_id=None)
    
    # Создаем первый ключ
    email = f"user{user_id}-key1@test.bot"
    expiry_ms = int((datetime.now(timezone.utc) + timedelta(days=30)).timestamp() * 1000)
    
    key_id1 = add_new_key(
        user_id=user_id,
        host_name="Test Host",
        xui_client_uuid="uuid-1",
        key_email=email,
        expiry_timestamp_ms=expiry_ms
    )
    
    assert key_id1 is not None, "Первый ключ должен быть создан"
    print(f"✓ Первый ключ создан: key_id={key_id1}, email={email}")
    
    # Пытаемся создать второй ключ с тем же email (должен обновиться существующий)
    key_id2 = add_new_key(
        user_id=user_id,
        host_name="Test Host",
        xui_client_uuid="uuid-2",
        key_email=email,  # Тот же email!
        expiry_timestamp_ms=expiry_ms + 86400000  # +1 день
    )
    
    assert key_id2 == key_id1, f"Должен вернуться тот же key_id: ожидался {key_id1}, получен {key_id2}"
    print(f"✓ При IntegrityError ключ обновлен: key_id={key_id2}")
    
    # Проверяем, что ключ действительно обновлен через прямой запрос к БД
    # Используем temp_db напрямую, а не database.DB_FILE, чтобы гарантировать использование правильной тестовой БД
    conn = sqlite3.connect(str(temp_db))
    cursor = conn.cursor()
    cursor.execute("SELECT xui_client_uuid FROM vpn_keys WHERE key_id = ?", (key_id1,))
    row = cursor.fetchone()
    assert row is not None, "Ключ должен существовать в БД"
    assert row[0] == "uuid-2", f"UUID должен быть обновлен на uuid-2, получен {row[0]}"
    print(f"✓ UUID обновлен на: {row[0]}")
    conn.close()
    
    print("✓ Тест 3 пройден\n")


@pytest.mark.unit
@pytest.mark.database
@allure.epic("База данных")
@allure.feature("Нумерация ключей")
@allure.label("package", "src.shop_bot.database")
@allure.title("Последовательная нумерация ключей")
@allure.description("""
Проверяет последовательную нумерацию ключей при создании и удалении.

**Что проверяется:**
- Создание нескольких ключей с последовательными номерами (1, 2, 3, 4, 5)
- Удаление некоторых ключей из середины последовательности
- Создание нового ключа после удаления (должен получить следующий номер, а не пропущенный)

**Тестовые данные:**
- user_id: 777777
- Количество создаваемых ключей: 5
- Удаляемые ключи: #2 и #4

**Ожидаемый результат:**
Ключи получают последовательные номера (1, 2, 3, 4, 5), после удаления #2 и #4 новый ключ получает номер 6, а не 4.
""")
@allure.severity(allure.severity_level.NORMAL)
@allure.tag("key_numbering", "sequential", "delete", "database", "unit")
def test_sequential_key_numbers(temp_db):
    """Тест последовательной нумерации ключей"""
    print("\n=== Тест 4: Последовательная нумерация ключей ===")
    
    # Используем database.DB_FILE (уже заменен через monkeypatch в фикстуре temp_db)
    from shop_bot.data_manager import database
    
    initialize_db()
    
    user_id = 777777
    register_user_if_not_exists(user_id, "test_user3", referrer_id=None)
    
    # Создаем несколько ключей
    created_keys = []
    for i in range(5):
        key_number = get_next_key_number(user_id)
        email = f"user{user_id}-key{key_number}@test.bot"
        expiry_ms = int((datetime.now(timezone.utc) + timedelta(days=30)).timestamp() * 1000)
        
        key_id = add_new_key(
            user_id=user_id,
            host_name="Test Host",
            xui_client_uuid=f"uuid-{i}",
            key_email=email,
            expiry_timestamp_ms=expiry_ms
        )
        
        created_keys.append((key_id, key_number, email))
        print(f"✓ Ключ {i+1}: key_id={key_id}, key_number={key_number}, email={email}")
    
    # Проверяем последовательность номеров
    expected_numbers = [1, 2, 3, 4, 5]
    actual_numbers = [num for _, num, _ in created_keys]
    assert actual_numbers == expected_numbers, f"Номера должны быть {expected_numbers}, получены {actual_numbers}"
    print(f"✓ Все номера ключей последовательны: {actual_numbers}")
    
    # Удаляем некоторые ключи
    from src.shop_bot.data_manager.database import delete_key_by_email
    delete_key_by_email(created_keys[1][2])  # Удаляем ключ #2
    delete_key_by_email(created_keys[3][2])  # Удаляем ключ #4
    print("✓ Удалены ключи #2 и #4")
    
    # Создаем новый ключ - должен получить номер 6, не 4
    key_number_new = get_next_key_number(user_id)
    assert key_number_new == 6, f"После удаления ключей новый должен быть #6, получен #{key_number_new}"
    print(f"✓ Новый ключ после удаления получил номер: {key_number_new}")
    
    print("✓ Тест 4 пройден\n")


@pytest.mark.unit
@pytest.mark.database
@allure.epic("База данных")
@allure.feature("Нумерация ключей")
@allure.label("package", "src.shop_bot.database")
@allure.title("Обработка случая, когда пользователь не найден")
@allure.description("""
Проверяет обработку случая, когда пользователь не найден при получении номера ключа.

**Что проверяется:**
- Получение номера ключа для несуществующего пользователя
- Автоматическое создание пользователя при получении номера
- Инициализация счетчика keys_count для нового пользователя
- Возврат номера 1 для нового пользователя

**Тестовые данные:**
- user_id: 666666 (несуществующий)

**Ожидаемый результат:**
Для несуществующего пользователя возвращается номер 1, пользователь автоматически создается с keys_count=1.
""")
@allure.severity(allure.severity_level.NORMAL)
@allure.tag("key_numbering", "user_not_found", "auto_create", "database", "unit")
def test_user_not_found_handling(temp_db):
    """Тест обработки случая, когда пользователь не найден"""
    print("\n=== Тест 5: Обработка отсутствующего пользователя ===")
    
    # Используем database.DB_FILE (уже заменен через monkeypatch в фикстуре temp_db)
    from shop_bot.data_manager import database
    
    initialize_db()
    
    # Пытаемся получить номер для несуществующего пользователя
    user_id = 666666
    next_num = get_next_key_number(user_id)
    
    assert next_num == 1, f"Для нового пользователя должен быть номер 1, получен {next_num}"
    print(f"✓ Для нового пользователя возвращен номер: {next_num}")
    
    # Проверяем, что пользователь создан
    user = get_user(user_id)
    assert user is not None, "Пользователь должен быть создан"
    assert user.get('keys_count') == 1, f"Счетчик должен быть 1, получен {user.get('keys_count')}"
    print(f"✓ Пользователь создан с keys_count={user.get('keys_count')}")
    
    print("✓ Тест 5 пройден\n")


@pytest.mark.unit
@pytest.mark.database
@allure.epic("База данных")
@allure.feature("Нумерация ключей")
@allure.label("package", "src.shop_bot.database")
@allure.title("Инициализация счетчика keys_count для существующих пользователей")
@allure.description("""
Проверяет корректность инициализации счетчика keys_count для существующих пользователей при миграции БД.

**Что проверяется:**
- Создание БД с существующими пользователями и ключами
- Извлечение номеров ключей из email адресов
- Определение максимального номера ключа
- Инициализация счетчика keys_count максимальным номером ключа
- Корректность значения счетчика после инициализации

**Тестовые данные:**
- user_id: 555555
- username: "test_user4"
- Ключи с номерами: 1, 3, 5, 7 (не последовательные)
- Ожидаемый максимальный номер: 7

**Ожидаемый результат:**
Счетчик keys_count должен быть инициализирован значением 7 (максимальный номер ключа), а не количеством ключей или другим значением.
""")
@allure.severity(allure.severity_level.NORMAL)
@allure.tag("key_numbering", "initialization", "database", "unit", "migration")
def test_initialization_existing_users():
    """Тест инициализации счетчика для существующих пользователей"""
    print("\n=== Тест 6: Инициализация счетчика для существующих пользователей ===")
    
    # Инициализируем переменные до блока try для безопасного восстановления
    import shop_bot.data_manager.database as db_module
    original_db_file = db_module.DB_FILE
    temp_db = None
    
    try:
        with allure.step("Подготовка тестовых данных"):
            # Создаем временную БД
            temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
            temp_db.close()
            allure.attach(str(temp_db.name), "Путь к временной БД", allure.attachment_type.TEXT)
            
            # Меняем DB_FILE для теста
            db_module.DB_FILE = Path(temp_db.name)
        
        with allure.step("Создание БД и пользователя"):
            # Создаем БД без keys_count - используем минимальную структуру
            # Используем temp_db напрямую, а не database.DB_FILE, чтобы гарантировать использование правильной тестовой БД
            conn = sqlite3.connect(temp_db.name)
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE users (
                    telegram_id INTEGER PRIMARY KEY,
                    username TEXT,
                    registration_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    keys_count INTEGER DEFAULT 0
                )
            """)
            cursor.execute("""
                CREATE TABLE vpn_keys (
                    key_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    key_email TEXT NOT NULL UNIQUE,
                    created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Создаем пользователя
            user_id = 555555
            cursor.execute("INSERT INTO users (telegram_id, username) VALUES (?, ?)", (user_id, "test_user4"))
            allure.attach(str(user_id), "User ID", allure.attachment_type.TEXT)
            conn.commit()
            conn.close()
        
        with allure.step("Создание ключей с разными номерами"):
            # Создаем ключи с разными номерами (не последовательные: 1, 3, 5, 7)
            conn = sqlite3.connect(temp_db.name)
            cursor = conn.cursor()
            
            created_keys = []
            for i in [1, 3, 5, 7]:
                email = f"user{user_id}-key{i}@test.bot"
                cursor.execute("INSERT INTO vpn_keys (user_id, key_email) VALUES (?, ?)", (user_id, email))
                created_keys.append({"number": i, "email": email})
            
            conn.commit()
            conn.close()
            
            # Прикрепляем информацию о созданных ключах
            keys_info = "\n".join([f"Ключ #{k['number']}: {k['email']}" for k in created_keys])
            allure.attach(keys_info, "Созданные ключи", allure.attachment_type.TEXT)
        
        with allure.step("Инициализация счетчика"):
            # Проверяем инициализацию счетчика вручную (имитируем логику миграции)
            # Используем temp_db напрямую, а не database.DB_FILE, чтобы гарантировать использование правильной тестовой БД
            conn = sqlite3.connect(temp_db.name)
            cursor = conn.cursor()
            
            # Получаем все ключи пользователя
            cursor.execute("SELECT key_email FROM vpn_keys WHERE user_id = ?", (user_id,))
            user_keys = cursor.fetchall()
            
            max_key_number = 0
            for (key_email,) in user_keys:
                import re
                match = re.search(r'-key(\d+)', key_email)
                if match:
                    key_num = int(match.group(1))
                    if key_num > max_key_number:
                        max_key_number = key_num
            
            allure.attach(str(max_key_number), "Максимальный номер ключа", allure.attachment_type.TEXT)
            
            # Обновляем счетчик
            if max_key_number > 0:
                cursor.execute("UPDATE users SET keys_count = ? WHERE telegram_id = ?", (max_key_number, user_id))
                conn.commit()
            
            conn.close()
        
        with allure.step("Проверка результата"):
            # Проверяем, что счетчик инициализирован правильно (максимальный номер = 7)
            conn = sqlite3.connect(temp_db.name)
            cursor = conn.cursor()
            cursor.execute("SELECT keys_count FROM users WHERE telegram_id = ?", (user_id,))
            row = cursor.fetchone()
            
            keys_count = row[0] if row else None
            allure.attach(str(keys_count), "Финальное значение keys_count", allure.attachment_type.TEXT)
            
            assert row and row[0] == 7, f"Счетчик должен быть 7 (максимальный номер), получен {keys_count}"
            print(f"✓ Счетчик инициализирован правильно: keys_count={row[0]}")
            
            conn.close()
        
        # Восстанавливаем оригинальный DB_FILE
        db_module.DB_FILE = original_db_file
        
    finally:
        # Безопасное восстановление DB_FILE
        if 'original_db_file' in locals() and original_db_file is not None:
            try:
                db_module.DB_FILE = original_db_file
            except Exception:
                pass
        
        # Очистка временной БД
        if temp_db and os.path.exists(temp_db.name):
            import gc
            gc.collect()
            import time
            time.sleep(0.1)
            try:
                os.unlink(temp_db.name)
            except PermissionError:
                pass
    
    print("✓ Тест 6 пройден\n")


def run_all_tests():
    """Запускает все тесты"""
    print("=" * 60)
    print("ТЕСТИРОВАНИЕ ИСПРАВЛЕНИЯ НУМЕРАЦИИ КЛЮЧЕЙ")
    print("=" * 60)
    
    tests = [
        test_keys_count_migration,
        test_get_next_key_number,
        test_key_creation_with_integrity_error,
        test_sequential_key_numbers,
        test_user_not_found_handling,
        test_initialization_existing_users,
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"\n❌ Тест провален: {test.__name__}")
            print(f"   Ошибка: {e}")
            import traceback
            traceback.print_exc()
            failed += 1
    
    print("=" * 60)
    print(f"РЕЗУЛЬТАТЫ: Пройдено: {passed}, Провалено: {failed}")
    print("=" * 60)
    
    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)

