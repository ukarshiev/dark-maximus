#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Unit-тесты для функциональности работы с настройками доменов

Проверяет корректность работы функций получения доменов из БД:
get_global_domain, get_user_cabinet_domain, get_setting для всех доменов.
"""

import pytest
import allure
import sys
from pathlib import Path

# Добавляем путь к проекту
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root / "src"))

from shop_bot.data_manager.database import (
    get_global_domain,
    get_setting,
    update_setting,
    initialize_db,
    get_server_environment,
    is_production_server,
    is_development_server,
)
from shop_bot.config import get_user_cabinet_domain


@pytest.mark.unit
@pytest.mark.database
@allure.epic("База данных")
@allure.feature("Настройки доменов")
@allure.label("package", "src.shop_bot.database")
class TestDomainSettings:
    """Тесты для функциональности работы с настройками доменов"""

    @allure.title("Чтение global_domain из БД")
    @allure.description("""
    Проверяет корректное чтение настройки global_domain из БД.
    
    **Что проверяется:**
    - Установка значения global_domain в БД
    - Чтение значения через get_global_domain()
    - Корректное возвращение установленного значения
    
    **Тестовые данные:**
    - global_domain: "https://example.com"
    
    **Ожидаемый результат:**
    get_global_domain() возвращает установленное значение.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("domain", "settings", "database", "unit")
    def test_get_global_domain_from_db(self, temp_db):
        """Проверка чтения global_domain из БД"""
        with allure.step("Установка global_domain в БД"):
            update_setting("global_domain", "https://example.com")
            allure.attach("https://example.com", "Установленное значение", allure.attachment_type.TEXT)
        
        with allure.step("Чтение global_domain из БД"):
            result = get_global_domain()
            allure.attach(str(result), "Полученное значение", allure.attachment_type.TEXT)
        
        with allure.step("Проверка результата"):
            assert result == "https://example.com"

    @allure.title("Fallback на domain если global_domain отсутствует")
    @allure.description("""
    Проверяет fallback на старый параметр domain если global_domain отсутствует.
    
    **Что проверяется:**
    - Установка только domain (без global_domain)
    - Чтение через get_global_domain()
    - Корректный fallback на domain
    
    **Тестовые данные:**
    - domain: "https://old-example.com"
    
    **Ожидаемый результат:**
    get_global_domain() возвращает значение из domain с добавлением https:// если нужно.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("domain", "settings", "fallback", "database", "unit")
    def test_get_global_domain_fallback_to_domain(self, temp_db):
        """Проверка fallback на domain если global_domain отсутствует"""
        with allure.step("Установка только domain (без global_domain)"):
            update_setting("domain", "old-example.com")
            allure.attach("old-example.com", "Установленное значение domain", allure.attachment_type.TEXT)
        
        with allure.step("Чтение через get_global_domain()"):
            result = get_global_domain()
            allure.attach(str(result), "Полученное значение", allure.attachment_type.TEXT)
        
        with allure.step("Проверка результата"):
            assert result == "https://old-example.com"

    @allure.title("Fallback на localhost в development если оба домена отсутствуют")
    @allure.description("""
    Проверяет fallback на localhost в development режиме если и global_domain и domain отсутствуют.
    
    **Что проверяется:**
    - Установка server_environment в "development"
    - Проверка сохранения настройки server_environment
    - Явная очистка global_domain и domain в БД
    - Отсутствие global_domain и domain в БД
    - Чтение через get_global_domain()
    - Fallback на дефолтное значение localhost в development
    
    **Ожидаемый результат:**
    get_global_domain() возвращает "https://localhost:8443" в development режиме.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("domain", "settings", "fallback", "database", "unit", "server-environment")
    def test_get_global_domain_fallback_to_localhost_in_development(self, temp_db):
        """Проверка fallback на localhost в development если оба домена отсутствуют"""
        import sqlite3
        import time
        
        # Вспомогательная функция для проверки удаления доменов с retry
        def _verify_domains_deleted(db_path, max_attempts=5, delay=0.1):
            """Проверяет, что домены удалены из БД, с retry логикой"""
            for attempt in range(max_attempts):
                try:
                    with sqlite3.connect(str(db_path), timeout=30.0) as conn:
                        cursor = conn.cursor()
                        cursor.execute("PRAGMA busy_timeout = 30000")
                        cursor.execute("SELECT key, value FROM bot_settings WHERE key IN ('global_domain', 'domain')")
                        remaining = cursor.fetchall()
                        if len(remaining) == 0:
                            return True, None
                        if attempt < max_attempts - 1:
                            time.sleep(delay)
                except sqlite3.Error as e:
                    if attempt < max_attempts - 1:
                        time.sleep(delay)
                        continue
                    return False, str(e)
            return False, remaining
        
        with allure.step("Проверка изоляции БД через monkeypatch"):
            # КРИТИЧНО: Проверяем, что database.DB_FILE действительно указывает на temp_db
            # Это гарантирует, что тест использует временную БД, а не реальную
            from shop_bot.data_manager import database
            # Сравниваем как строки, так как DB_FILE может быть Path объектом
            assert str(database.DB_FILE) == str(temp_db), (
                f"КРИТИЧЕСКАЯ ОШИБКА: database.DB_FILE ({database.DB_FILE}) не соответствует temp_db ({temp_db}). "
                f"Monkeypatch не применен корректно! Тест может использовать реальную БД."
            )
            allure.attach(
                f"database.DB_FILE: {database.DB_FILE}\ntemp_db: {temp_db}\nИзоляция БД: OK",
                "Проверка изоляции БД",
                allure.attachment_type.TEXT
            )
            
            # Проверяем начальное состояние БД
            with sqlite3.connect(str(temp_db), timeout=30.0) as conn:
                cursor = conn.cursor()
                cursor.execute("PRAGMA busy_timeout = 30000")
                cursor.execute("SELECT key, value FROM bot_settings WHERE key IN ('server_environment', 'global_domain', 'domain')")
                initial_settings = cursor.fetchall()
                allure.attach(
                    f"Начальное состояние БД: {initial_settings}",
                    "Начальные настройки БД",
                    allure.attachment_type.TEXT
                )
        
        with allure.step("Установка server_environment в development"):
            update_setting("server_environment", "development")
            allure.attach("development", "Установленное окружение", allure.attachment_type.TEXT)
        
        with allure.step("Проверка сохранения настройки server_environment"):
            saved_env = get_server_environment()
            allure.attach(f"server_environment: {saved_env}", "Сохраненное окружение", allure.attachment_type.TEXT)
            assert saved_env == "development", f"server_environment должен быть 'development', но получен: {saved_env}"
            
            # Дополнительная проверка через is_development_server()
            is_dev = is_development_server()
            allure.attach(f"is_development_server(): {is_dev}", "Результат проверки development", allure.attachment_type.TEXT)
            assert is_dev is True, f"is_development_server() должен возвращать True, но получен: {is_dev}"
        
        with allure.step("Явная очистка настроек доменов с retry-логикой"):
            # ВАЖНО: Используем прямое удаление через SQL с retry-логикой для надежности
            # Это избегает race condition и проблем с изоляцией соединений SQLite
            # Используем temp_db напрямую - это Path объект к временной БД
            # temp_db соответствует database.DB_FILE благодаря monkeypatch в фикстуре
            
            max_delete_attempts = 3
            delete_success = False
            
            for attempt in range(max_delete_attempts):
                try:
                    with sqlite3.connect(str(temp_db), timeout=30.0) as conn:
                        cursor = conn.cursor()
                        # Устанавливаем PRAGMA для предотвращения блокировок
                        cursor.execute("PRAGMA busy_timeout = 30000")
                        # Удаляем записи напрямую, включая возможные пустые строки
                        cursor.execute("DELETE FROM bot_settings WHERE key IN ('global_domain', 'domain')")
                        conn.commit()
                        
                        # Проверяем, что записи действительно удалены
                        cursor.execute("SELECT key, value FROM bot_settings WHERE key IN ('global_domain', 'domain')")
                        remaining = cursor.fetchall()
                        
                        if len(remaining) == 0:
                            delete_success = True
                            allure.attach(
                                f"Записи успешно удалены из БД (попытка {attempt + 1}/{max_delete_attempts})",
                                "Очистка настроек",
                                allure.attachment_type.TEXT
                            )
                            break
                        else:
                            allure.attach(
                                f"Попытка {attempt + 1}/{max_delete_attempts}: Остались записи: {remaining}",
                                "Диагностика удаления",
                                allure.attachment_type.TEXT
                            )
                            if attempt < max_delete_attempts - 1:
                                time.sleep(0.1)  # Небольшая задержка перед следующей попыткой
                except sqlite3.Error as e:
                    allure.attach(
                        f"Ошибка при удалении (попытка {attempt + 1}/{max_delete_attempts}): {e}",
                        "Ошибка очистки БД",
                        allure.attachment_type.TEXT
                    )
                    if attempt < max_delete_attempts - 1:
                        time.sleep(0.1)
                    continue
            
            # Проверяем успешность удаления
            assert delete_success, (
                f"Не удалось удалить записи доменов из БД после {max_delete_attempts} попыток. "
                f"Возможна проблема с блокировками SQLite или изоляцией БД."
            )
            
            # Используем функцию проверки с retry вместо sleep
            verify_success, verify_error = _verify_domains_deleted(temp_db, max_attempts=5, delay=0.1)
            assert verify_success, (
                f"Проверка удаления доменов не прошла: {verify_error}. "
                f"Записи все еще присутствуют в БД после удаления."
            )
            allure.attach(
                "Проверка удаления доменов успешна (через retry)",
                "Верификация очистки",
                allure.attachment_type.TEXT
            )
        
        with allure.step("Проверка отсутствия настроек доменов через get_setting()"):
            # Проверяем через get_setting() - должно возвращать None
            global_domain = get_setting("global_domain")
            domain = get_setting("domain")
            allure.attach(f"global_domain: {global_domain}, domain: {domain}", "Текущие настройки через get_setting()", allure.attachment_type.TEXT)
            
            # Убеждаемся, что настройки действительно отсутствуют (None или пустая строка)
            assert global_domain is None or global_domain == "", f"global_domain должен быть None или пустой строкой, но получен: {global_domain}"
            assert domain is None or domain == "", f"domain должен быть None или пустой строкой, но получен: {domain}"
        
        with allure.step("Дополнительная проверка через прямой SQL запрос"):
            # Проверяем через прямое SQL соединение для дополнительной уверенности
            with sqlite3.connect(str(temp_db), timeout=30.0) as conn:
                cursor = conn.cursor()
                cursor.execute("PRAGMA busy_timeout = 30000")
                cursor.execute("SELECT key, value FROM bot_settings WHERE key IN ('global_domain', 'domain')")
                remaining = cursor.fetchall()
                allure.attach(f"Оставшиеся записи в БД через SQL: {remaining}", "Проверка через SQL", allure.attachment_type.TEXT)
                assert len(remaining) == 0, f"В БД остались записи доменов: {remaining}"
        
        with allure.step("Финальная проверка целостности перед вызовом get_global_domain()"):
            # КРИТИЧНО: Проверяем все условия еще раз перед финальным вызовом
            from shop_bot.data_manager import database
            
            # Проверка изоляции БД
            assert str(database.DB_FILE) == str(temp_db), (
                f"КРИТИЧЕСКАЯ ОШИБКА: database.DB_FILE изменился! "
                f"Было: {temp_db}, стало: {database.DB_FILE}. Monkeypatch мог быть сброшен."
            )
            
            # Проверка окружения
            current_env = get_server_environment()
            is_dev_check = is_development_server()
            assert current_env == "development", (
                f"Окружение должно быть 'development', но получено: {current_env}. "
                f"Возможно, настройка была изменена другим тестом."
            )
            assert is_dev_check is True, (
                f"is_development_server() должен возвращать True, но получен: {is_dev_check}. "
                f"Проверка окружения не прошла."
            )
            
            # Проверка отсутствия доменов через SQL
            with sqlite3.connect(str(temp_db), timeout=30.0) as conn:
                cursor = conn.cursor()
                cursor.execute("PRAGMA busy_timeout = 30000")
                cursor.execute("SELECT key, value FROM bot_settings WHERE key IN ('global_domain', 'domain')")
                remaining_sql = cursor.fetchall()
                assert len(remaining_sql) == 0, (
                    f"В БД остались записи доменов через SQL: {remaining_sql}. "
                    f"Очистка не была успешной."
                )
            
            # Проверка через get_setting()
            global_domain_check = get_setting("global_domain")
            domain_check = get_setting("domain")
            assert global_domain_check is None or global_domain_check == "", (
                f"global_domain через get_setting() должен быть None или пустой строкой, "
                f"но получен: {global_domain_check}"
            )
            assert domain_check is None or domain_check == "", (
                f"domain через get_setting() должен быть None или пустой строкой, "
                f"но получен: {domain_check}"
            )
            
            # Логируем все диагностические данные
            integrity_info = {
                "database.DB_FILE": database.DB_FILE,
                "temp_db": str(temp_db),
                "server_environment": current_env,
                "is_development_server": is_dev_check,
                "global_domain_from_db_sql": remaining_sql,
                "global_domain_from_get_setting": global_domain_check,
                "domain_from_get_setting": domain_check,
                "expected_result": "https://localhost:8443",
            }
            allure.attach(
                str(integrity_info),
                "Финальная проверка целостности данных",
                allure.attachment_type.JSON
            )
        
        with allure.step("Чтение через get_global_domain()"):
            result = get_global_domain()
            allure.attach(str(result), "Полученное значение из get_global_domain()", allure.attachment_type.TEXT)
            
            # Дополнительная диагностика после вызова
            debug_info = {
                "result": result,
                "database.DB_FILE": database.DB_FILE,
                "server_environment": get_server_environment(),
                "is_development_server": is_development_server(),
                "global_domain_from_db": get_setting("global_domain"),
                "domain_from_db": get_setting("domain"),
                "expected": "https://localhost:8443",
            }
            allure.attach(str(debug_info), "Диагностическая информация после вызова", allure.attachment_type.JSON)
        
        with allure.step("Проверка результата"):
            assert result == "https://localhost:8443", (
                f"Ожидалось 'https://localhost:8443', но получено: {result}. "
                f"Проверьте диагностическую информацию выше для выяснения причины. "
                f"Возможные причины: "
                f"1) server_environment не установлен в 'development', "
                f"2) домены не были удалены из БД, "
                f"3) проблема с изоляцией БД (monkeypatch не применен)."
            )

    @allure.title("Возврат None в production если оба домена отсутствуют")
    @allure.description("""
    Проверяет возврат None в production режиме если и global_domain и domain отсутствуют.
    
    **Что проверяется:**
    - Установка server_environment в "production"
    - Явная очистка global_domain и domain в БД
    - Отсутствие global_domain и domain в БД
    - Чтение через get_global_domain()
    - Возврат None в production если домен не настроен
    
    **Ожидаемый результат:**
    get_global_domain() возвращает None в production режиме если домен не настроен.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("domain", "settings", "fallback", "database", "unit", "server-environment")
    def test_get_global_domain_returns_none_in_production(self, temp_db):
        """Проверка возврата None в production если оба домена отсутствуют"""
        import sqlite3
        import time
        
        with allure.step("Установка server_environment в production"):
            update_setting("server_environment", "production")
            allure.attach("production", "Установленное окружение", allure.attachment_type.TEXT)
        
        with allure.step("Проверка сохранения настройки server_environment"):
            saved_env = get_server_environment()
            allure.attach(f"server_environment: {saved_env}", "Сохраненное окружение", allure.attachment_type.TEXT)
            assert saved_env == "production", f"server_environment должен быть 'production', но получен: {saved_env}"
            
            # Дополнительная проверка через is_production_server()
            is_prod = is_production_server()
            allure.attach(f"is_production_server(): {is_prod}", "Результат проверки production", allure.attachment_type.TEXT)
            assert is_prod is True, f"is_production_server() должен возвращать True, но получен: {is_prod}"
        
        with allure.step("Явная очистка настроек доменов"):
            # ВАЖНО: Используем прямое удаление через SQL для гарантии отсутствия доменов
            # Это обеспечивает изоляцию теста от предыдущих тестов
            with sqlite3.connect(str(temp_db), timeout=30.0) as conn:
                cursor = conn.cursor()
                # Устанавливаем PRAGMA для предотвращения блокировок
                cursor.execute("PRAGMA busy_timeout = 30000")
                # Удаляем записи напрямую
                cursor.execute("DELETE FROM bot_settings WHERE key IN ('global_domain', 'domain')")
                conn.commit()
                # Проверяем, что записи действительно удалены
                cursor.execute("SELECT key, value FROM bot_settings WHERE key IN ('global_domain', 'domain')")
                remaining = cursor.fetchall()
                if remaining:
                    allure.attach(f"ВНИМАНИЕ: Остались записи после удаления: {remaining}", "Диагностика удаления", allure.attachment_type.TEXT)
                else:
                    allure.attach("Записи успешно удалены из БД", "Очистка настроек", allure.attachment_type.TEXT)
            
            # Закрываем все соединения и даем время для синхронизации
            time.sleep(0.2)
        
        with allure.step("Проверка отсутствия настроек доменов через get_setting()"):
            global_domain = get_setting("global_domain")
            domain = get_setting("domain")
            allure.attach(f"global_domain: {global_domain}, domain: {domain}", "Текущие настройки через get_setting()", allure.attachment_type.TEXT)
            
            # Убеждаемся, что настройки действительно отсутствуют
            assert global_domain is None or global_domain == "", f"global_domain должен быть None или пустой строкой, но получен: {global_domain}"
            assert domain is None or domain == "", f"domain должен быть None или пустой строкой, но получен: {domain}"
        
        with allure.step("Дополнительная проверка через прямой SQL запрос"):
            with sqlite3.connect(str(temp_db), timeout=30.0) as conn:
                cursor = conn.cursor()
                cursor.execute("PRAGMA busy_timeout = 30000")
                cursor.execute("SELECT key, value FROM bot_settings WHERE key IN ('global_domain', 'domain')")
                remaining = cursor.fetchall()
                allure.attach(f"Оставшиеся записи в БД через SQL: {remaining}", "Проверка через SQL", allure.attachment_type.TEXT)
                assert len(remaining) == 0, f"В БД остались записи доменов: {remaining}"
        
        with allure.step("Проверка окружения перед вызовом get_global_domain()"):
            current_env = get_server_environment()
            is_prod_check = is_production_server()
            allure.attach(
                f"server_environment: {current_env}, is_production_server(): {is_prod_check}",
                "Проверка окружения перед вызовом",
                allure.attachment_type.TEXT
            )
            assert current_env == "production", f"Окружение должно быть 'production', но получено: {current_env}"
            assert is_prod_check is True, f"is_production_server() должен возвращать True, но получен: {is_prod_check}"
        
        with allure.step("Чтение через get_global_domain()"):
            result = get_global_domain()
            allure.attach(str(result), "Полученное значение из get_global_domain()", allure.attachment_type.TEXT)
            
            # Дополнительная диагностика
            debug_info = {
                "result": result,
                "server_environment": get_server_environment(),
                "is_production_server": is_production_server(),
                "is_development_server": is_development_server(),
                "global_domain_from_db": get_setting("global_domain"),
                "domain_from_db": get_setting("domain"),
                "expected": None,
            }
            allure.attach(str(debug_info), "Диагностическая информация перед проверкой", allure.attachment_type.JSON)
        
        with allure.step("Проверка результата"):
            assert result is None, f"Ожидалось None, но получено: {result}"

    @allure.title("Чтение user_cabinet_domain из БД")
    @allure.description("""
    Проверяет корректное чтение настройки user_cabinet_domain из БД.
    
    **Что проверяется:**
    - Установка значения user_cabinet_domain в БД
    - Чтение значения через get_user_cabinet_domain()
    - Нормализация домена (добавление протокола)
    
    **Тестовые данные:**
    - user_cabinet_domain: "app.example.com"
    
    **Ожидаемый результат:**
    get_user_cabinet_domain() возвращает нормализованное значение с протоколом.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("domain", "settings", "cabinet", "database", "unit")
    def test_get_user_cabinet_domain_from_db(self, temp_db):
        """Проверка чтения user_cabinet_domain из БД"""
        with allure.step("Установка user_cabinet_domain в БД"):
            update_setting("user_cabinet_domain", "app.example.com")
            allure.attach("app.example.com", "Установленное значение", allure.attachment_type.TEXT)
        
        with allure.step("Чтение user_cabinet_domain из БД"):
            result = get_user_cabinet_domain()
            allure.attach(str(result), "Полученное значение", allure.attachment_type.TEXT)
        
        with allure.step("Проверка результата"):
            assert result == "https://app.example.com"
            assert result.startswith("https://")

    @allure.title("Возврат None если user_cabinet_domain отсутствует")
    @allure.description("""
    Проверяет возврат None если настройка user_cabinet_domain отсутствует.
    
    **Что проверяется:**
    - Отсутствие user_cabinet_domain в БД
    - Чтение через get_user_cabinet_domain()
    - Возврат None
    
    **Ожидаемый результат:**
    get_user_cabinet_domain() возвращает None.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("domain", "settings", "cabinet", "database", "unit")
    def test_get_user_cabinet_domain_returns_none(self, temp_db):
        """Проверка возврата None если настройка отсутствует"""
        with allure.step("Проверка отсутствия настройки"):
            setting = get_setting("user_cabinet_domain")
            allure.attach(str(setting), "Текущее значение", allure.attachment_type.TEXT)
        
        with allure.step("Чтение через get_user_cabinet_domain()"):
            result = get_user_cabinet_domain()
            allure.attach(str(result), "Полученное значение", allure.attachment_type.TEXT)
        
        with allure.step("Проверка результата"):
            assert result is None

    @allure.title("Чтение codex_docs_domain из БД")
    @allure.description("""
    Проверяет корректное чтение настройки codex_docs_domain из БД.
    
    **Что проверяется:**
    - Установка значения codex_docs_domain в БД
    - Чтение значения через get_setting()
    - Корректное возвращение установленного значения
    
    **Тестовые данные:**
    - codex_docs_domain: "https://help.example.com"
    
    **Ожидаемый результат:**
    get_setting("codex_docs_domain") возвращает установленное значение.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("domain", "settings", "codex-docs", "database", "unit")
    def test_get_codex_docs_domain_from_db(self, temp_db):
        """Проверка чтения codex_docs_domain из БД"""
        with allure.step("Установка codex_docs_domain в БД"):
            update_setting("codex_docs_domain", "https://help.example.com")
            allure.attach("https://help.example.com", "Установленное значение", allure.attachment_type.TEXT)
        
        with allure.step("Чтение codex_docs_domain из БД"):
            result = get_setting("codex_docs_domain")
            allure.attach(str(result), "Полученное значение", allure.attachment_type.TEXT)
        
        with allure.step("Проверка результата"):
            assert result == "https://help.example.com"

    @allure.title("Чтение docs_domain из БД")
    @allure.description("""
    Проверяет корректное чтение настройки docs_domain из БД.
    
    **Что проверяется:**
    - Установка значения docs_domain в БД
    - Чтение значения через get_setting()
    - Корректное возвращение установленного значения
    
    **Тестовые данные:**
    - docs_domain: "https://docs.example.com"
    
    **Ожидаемый результат:**
    get_setting("docs_domain") возвращает установленное значение.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("domain", "settings", "docs", "database", "unit")
    def test_get_docs_domain_from_db(self, temp_db):
        """Проверка чтения docs_domain из БД"""
        with allure.step("Установка docs_domain в БД"):
            update_setting("docs_domain", "https://docs.example.com")
            allure.attach("https://docs.example.com", "Установленное значение", allure.attachment_type.TEXT)
        
        with allure.step("Чтение docs_domain из БД"):
            result = get_setting("docs_domain")
            allure.attach(str(result), "Полученное значение", allure.attachment_type.TEXT)
        
        with allure.step("Проверка результата"):
            assert result == "https://docs.example.com"

    @allure.title("Нормализация user_cabinet_domain с протоколом")
    @allure.description("""
    Проверяет нормализацию user_cabinet_domain с добавлением протокола если отсутствует.
    
    **Что проверяется:**
    - Установка user_cabinet_domain без протокола
    - Чтение через get_user_cabinet_domain()
    - Автоматическое добавление https://
    
    **Тестовые данные:**
    - user_cabinet_domain: "app.example.com"
    
    **Ожидаемый результат:**
    get_user_cabinet_domain() возвращает "https://app.example.com".
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("domain", "normalization", "cabinet", "database", "unit")
    def test_user_cabinet_domain_normalization_with_protocol(self, temp_db):
        """Проверка нормализации user_cabinet_domain с протоколом"""
        with allure.step("Установка user_cabinet_domain без протокола"):
            update_setting("user_cabinet_domain", "app.example.com")
            allure.attach("app.example.com", "Установленное значение (без протокола)", allure.attachment_type.TEXT)
        
        with allure.step("Чтение через get_user_cabinet_domain()"):
            result = get_user_cabinet_domain()
            allure.attach(str(result), "Полученное значение", allure.attachment_type.TEXT)
        
        with allure.step("Проверка результата"):
            assert result == "https://app.example.com"
            assert result.startswith("https://")

    @allure.title("Нормализация user_cabinet_domain с удалением trailing slash")
    @allure.description("""
    Проверяет нормализацию user_cabinet_domain с удалением trailing slash.
    
    **Что проверяется:**
    - Установка user_cabinet_domain с trailing slash
    - Чтение через get_user_cabinet_domain()
    - Удаление trailing slash
    
    **Тестовые данные:**
    - user_cabinet_domain: "https://app.example.com/"
    
    **Ожидаемый результат:**
    get_user_cabinet_domain() возвращает "https://app.example.com" (без trailing slash).
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("domain", "normalization", "cabinet", "database", "unit")
    def test_user_cabinet_domain_normalization_remove_trailing_slash(self, temp_db):
        """Проверка нормализации user_cabinet_domain с удалением trailing slash"""
        with allure.step("Установка user_cabinet_domain с trailing slash"):
            update_setting("user_cabinet_domain", "https://app.example.com/")
            allure.attach("https://app.example.com/", "Установленное значение (с trailing slash)", allure.attachment_type.TEXT)
        
        with allure.step("Чтение через get_user_cabinet_domain()"):
            result = get_user_cabinet_domain()
            allure.attach(str(result), "Полученное значение", allure.attachment_type.TEXT)
        
        with allure.step("Проверка результата"):
            assert result == "https://app.example.com"
            assert not result.endswith("/")

    @allure.title("Получение server_environment из БД")
    @allure.description("""
    Проверяет корректное чтение настройки server_environment из БД.
    
    **Что проверяется:**
    - Установка значения server_environment в БД
    - Чтение значения через get_server_environment()
    - Корректное возвращение установленного значения
    
    **Тестовые данные:**
    - server_environment: "production"
    
    **Ожидаемый результат:**
    get_server_environment() возвращает установленное значение.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("server-environment", "settings", "database", "unit")
    def test_get_server_environment_from_db(self, temp_db):
        """Проверка чтения server_environment из БД"""
        with allure.step("Установка server_environment в БД"):
            update_setting("server_environment", "production")
            allure.attach("production", "Установленное значение", allure.attachment_type.TEXT)
        
        with allure.step("Чтение server_environment из БД"):
            result = get_server_environment()
            allure.attach(str(result), "Полученное значение", allure.attachment_type.TEXT)
        
        with allure.step("Проверка результата"):
            assert result == "production"

    @allure.title("Значение по умолчанию server_environment")
    @allure.description("""
    Проверяет возврат значения по умолчанию "production" если настройка отсутствует.
    
    **Что проверяется:**
    - Отсутствие server_environment в БД
    - Чтение через get_server_environment()
    - Возврат значения по умолчанию "production"
    
    **Ожидаемый результат:**
    get_server_environment() возвращает "production" по умолчанию.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("server-environment", "settings", "default", "database", "unit")
    def test_get_server_environment_default_value(self, temp_db):
        """Проверка значения по умолчанию server_environment"""
        with allure.step("Проверка отсутствия настройки"):
            setting = get_setting("server_environment")
            allure.attach(str(setting), "Текущее значение", allure.attachment_type.TEXT)
        
        with allure.step("Чтение через get_server_environment()"):
            result = get_server_environment()
            allure.attach(str(result), "Полученное значение", allure.attachment_type.TEXT)
        
        with allure.step("Проверка результата"):
            assert result == "production"

    @allure.title("Проверка is_production_server")
    @allure.description("""
    Проверяет корректность работы функции is_production_server().
    
    **Что проверяется:**
    - Установка server_environment в "production"
    - Проверка через is_production_server()
    - Возврат True для production
    
    **Ожидаемый результат:**
    is_production_server() возвращает True для "production".
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("server-environment", "settings", "database", "unit")
    def test_is_production_server(self, temp_db):
        """Проверка функции is_production_server"""
        with allure.step("Установка server_environment в production"):
            update_setting("server_environment", "production")
            allure.attach("production", "Установленное значение", allure.attachment_type.TEXT)
        
        with allure.step("Проверка через is_production_server()"):
            result = is_production_server()
            allure.attach(str(result), "Результат проверки", allure.attachment_type.TEXT)
        
        with allure.step("Проверка результата"):
            assert result is True

    @allure.title("Проверка is_development_server")
    @allure.description("""
    Проверяет корректность работы функции is_development_server().
    
    **Что проверяется:**
    - Установка server_environment в "development"
    - Проверка через is_development_server()
    - Возврат True для development
    
    **Ожидаемый результат:**
    is_development_server() возвращает True для "development".
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("server-environment", "settings", "database", "unit")
    def test_is_development_server(self, temp_db):
        """Проверка функции is_development_server"""
        with allure.step("Установка server_environment в development"):
            update_setting("server_environment", "development")
            allure.attach("development", "Установленное значение", allure.attachment_type.TEXT)
        
        with allure.step("Проверка через is_development_server()"):
            result = is_development_server()
            allure.attach(str(result), "Результат проверки", allure.attachment_type.TEXT)
        
        with allure.step("Проверка результата"):
            assert result is True

