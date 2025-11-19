# -*- coding: utf-8 -*-
"""
Unit-тесты для функций работы с автопродлением ключей
"""

import pytest
import allure
from pathlib import Path
import sqlite3

from shop_bot.data_manager import database


@allure.epic("База данных")
@allure.feature("Автопродление ключей")
@allure.label("package", "src.shop_bot.database")
@pytest.mark.unit
@pytest.mark.database
class TestKeyAutoRenewal:
    """Тесты для функций работы с автопродлением ключей"""

    @allure.title("Получение статуса автопродления ключа по умолчанию (включено)")
    @allure.description("Проверяет получение статуса автопродления ключа по умолчанию через get_key_auto_renewal_enabled. **Что проверяется:** возврат True для ключа без явно установленного auto_renewal_enabled. **Тестовые данные:** user_id=123456789, key без auto_renewal_enabled. **Ожидаемый результат:** функция возвращает True (автопродление включено по умолчанию).")
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("auto_renewal", "database", "unit")
    def test_get_key_auto_renewal_enabled_default(self, temp_db):
        with allure.step("Подготовка тестовых данных"):
            # Создаем пользователя и ключ
            user_id = 123456789
            conn = sqlite3.connect(str(temp_db))
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO users (telegram_id, username, balance) VALUES (?, ?, ?)",
                (user_id, "test_user", 100.0)
            )
            cursor.execute(
                """INSERT INTO vpn_keys (user_id, host_name, xui_client_uuid, key_email, expiry_date, status)
                   VALUES (?, ?, ?, ?, datetime('now', '+30 days'), ?)""",
                (user_id, "test_host", "test-uuid", "test@example.com", "active")
            )
            conn.commit()
            key_id = cursor.lastrowid
            conn.close()
            allure.attach(str(key_id), "Key ID", allure.attachment_type.TEXT)

        with allure.step("Вызов функции get_key_auto_renewal_enabled"):
            result = database.get_key_auto_renewal_enabled(key_id)
            allure.attach(str(result), "Результат функции", allure.attachment_type.TEXT)

        with allure.step("Проверка результата"):
            assert result is True, "По умолчанию автопродление должно быть включено"

    @allure.title("Получение явно установленного статуса автопродления ключа")
    @allure.description("Проверяет получение явно установленного статуса автопродления ключа через get_key_auto_renewal_enabled. **Что проверяется:** возврат False для ключа с auto_renewal_enabled=0. **Тестовые данные:** user_id=123456789, key с auto_renewal_enabled=0. **Ожидаемый результат:** функция возвращает False (автопродление отключено).")
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("auto_renewal", "database", "unit")
    def test_get_key_auto_renewal_enabled_explicit(self, temp_db):
        with allure.step("Подготовка тестовых данных"):
            user_id = 123456789
            conn = sqlite3.connect(str(temp_db))
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO users (telegram_id, username, balance) VALUES (?, ?, ?)",
                (user_id, "test_user", 100.0)
            )
            # Создаем ключ с явно отключенным автопродлением
            cursor.execute(
                """INSERT INTO vpn_keys (user_id, host_name, xui_client_uuid, key_email, expiry_date, status, auto_renewal_enabled)
                   VALUES (?, ?, ?, ?, datetime('now', '+30 days'), ?, ?)""",
                (user_id, "test_host", "test-uuid", "test@example.com", "active", 0)
            )
            conn.commit()
            key_id = cursor.lastrowid
            conn.close()

        with allure.step("Вызов функции get_key_auto_renewal_enabled"):
            result = database.get_key_auto_renewal_enabled(key_id)

        with allure.step("Проверка результата"):
            assert result is False, "Автопродление должно быть отключено"

    @allure.title("Установка статуса автопродления ключа")
    @allure.description("Проверяет установку статуса автопродления ключа через set_key_auto_renewal_enabled. **Что проверяется:** обновление auto_renewal_enabled в БД, возврат True при успехе. **Тестовые данные:** user_id=123456789, key_id, enabled=False. **Ожидаемый результат:** статус автопродления успешно обновлен в БД, функция возвращает True.")
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("auto_renewal", "database", "unit")
    def test_set_key_auto_renewal_enabled(self, temp_db):
        with allure.step("Подготовка тестовых данных"):
            user_id = 123456789
            conn = sqlite3.connect(str(temp_db))
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO users (telegram_id, username, balance) VALUES (?, ?, ?)",
                (user_id, "test_user", 100.0)
            )
            cursor.execute(
                """INSERT INTO vpn_keys (user_id, host_name, xui_client_uuid, key_email, expiry_date, status)
                   VALUES (?, ?, ?, ?, datetime('now', '+30 days'), ?)""",
                (user_id, "test_host", "test-uuid", "test@example.com", "active")
            )
            conn.commit()
            key_id = cursor.lastrowid
            conn.close()

        with allure.step("Отключение автопродления"):
            result = database.set_key_auto_renewal_enabled(key_id, False)
            assert result is True, "set_key_auto_renewal_enabled должна вернуть True"

        with allure.step("Проверка изменения в БД"):
            conn = sqlite3.connect(str(temp_db))
            cursor = conn.cursor()
            cursor.execute("SELECT auto_renewal_enabled FROM vpn_keys WHERE key_id = ?", (key_id,))
            row = cursor.fetchone()
            conn.close()
            assert row is not None, "Ключ должен существовать в БД"
            assert row[0] == 0, "auto_renewal_enabled должен быть 0 (отключено)"

        with allure.step("Включение автопродления"):
            result = database.set_key_auto_renewal_enabled(key_id, True)
            assert result is True, "set_key_auto_renewal_enabled должна вернуть True"

        with allure.step("Проверка изменения в БД"):
            conn = sqlite3.connect(str(temp_db))
            cursor = conn.cursor()
            cursor.execute("SELECT auto_renewal_enabled FROM vpn_keys WHERE key_id = ?", (key_id,))
            row = cursor.fetchone()
            conn.close()
            assert row[0] == 1, "auto_renewal_enabled должен быть 1 (включено)"

    @allure.title("Обработка отсутствия колонки auto_renewal_enabled")
    @allure.description("Проверяет обработку отсутствия колонки auto_renewal_enabled в get_key_auto_renewal_enabled. **Что проверяется:** возврат True по умолчанию при отсутствии колонки в БД. **Тестовые данные:** user_id=123456789, key без колонки auto_renewal_enabled. **Ожидаемый результат:** функция возвращает True (обработка ошибки SQL, возврат значения по умолчанию).")
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("auto_renewal", "database", "unit", "error_handling")
    def test_get_key_auto_renewal_enabled_missing_column(self, temp_db):
        with allure.step("Подготовка тестовых данных"):
            user_id = 123456789
            conn = sqlite3.connect(str(temp_db))
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO users (telegram_id, username, balance) VALUES (?, ?, ?)",
                (user_id, "test_user", 100.0)
            )
            # Создаем ключ без колонки auto_renewal_enabled
            cursor.execute(
                """INSERT INTO vpn_keys (user_id, host_name, xui_client_uuid, key_email, expiry_date, status)
                   VALUES (?, ?, ?, ?, datetime('now', '+30 days'), ?)""",
                (user_id, "test_host", "test-uuid", "test@example.com", "active")
            )
            conn.commit()
            key_id = cursor.lastrowid

            # Удаляем колонку, если она существует
            try:
                cursor.execute("ALTER TABLE vpn_keys DROP COLUMN auto_renewal_enabled")
                conn.commit()
            except sqlite3.OperationalError:
                pass  # Колонка уже не существует
            conn.close()

        with allure.step("Вызов функции get_key_auto_renewal_enabled"):
            result = database.get_key_auto_renewal_enabled(key_id)

        with allure.step("Проверка результата"):
            assert result is True, "При отсутствии колонки должно возвращаться True по умолчанию"

    @allure.title("Проверка значения по умолчанию для новых ключей")
    @allure.description("Проверяет значение по умолчанию auto_renewal_enabled для новых ключей через get_key_auto_renewal_enabled. **Что проверяется:** возврат True для ключа без явно установленного auto_renewal_enabled. **Тестовые данные:** user_id=123456789, новый key без auto_renewal_enabled. **Ожидаемый результат:** функция возвращает True (автопродление включено по умолчанию для новых ключей).")
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("auto_renewal", "database", "unit", "default_value")
    def test_key_auto_renewal_default(self, temp_db):
        with allure.step("Подготовка тестовых данных"):
            user_id = 123456789
            conn = sqlite3.connect(str(temp_db))
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO users (telegram_id, username, balance) VALUES (?, ?, ?)",
                (user_id, "test_user", 100.0)
            )
            # Создаем ключ без явного указания auto_renewal_enabled
            cursor.execute(
                """INSERT INTO vpn_keys (user_id, host_name, xui_client_uuid, key_email, expiry_date, status)
                   VALUES (?, ?, ?, ?, datetime('now', '+30 days'), ?)""",
                (user_id, "test_host", "test-uuid", "test@example.com", "active")
            )
            conn.commit()
            key_id = cursor.lastrowid
            conn.close()

        with allure.step("Проверка значения по умолчанию"):
            result = database.get_key_auto_renewal_enabled(key_id)
            assert result is True, "Новые ключи должны иметь автопродление включенным по умолчанию"

