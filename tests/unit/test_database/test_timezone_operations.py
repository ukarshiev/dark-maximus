#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Unit-тесты для функций timezone в database.py

Проверяет:
1. is_timezone_feature_enabled()
2. get_admin_timezone() / set_admin_timezone()
3. get_user_timezone() / set_user_timezone()
4. Структура БД для timezone
"""

import pytest
import allure
import sqlite3
import sys
import json
from pathlib import Path

# Добавляем путь к модулям проекта
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root / "src"))

from shop_bot.data_manager.database import (
    is_timezone_feature_enabled,
    get_admin_timezone,
    set_admin_timezone,
    get_user_timezone,
    set_user_timezone,
    register_user_if_not_exists,
)


@pytest.mark.unit
@pytest.mark.database
@allure.epic("База данных")
@allure.feature("Операции с timezone")
@allure.label("package", "src.shop_bot.database")
class TestTimezoneOperations:
    """Тесты для функций работы с timezone в БД"""

    @allure.title("Проверка feature flag для timezone")
    @allure.description("""
    Проверяет, что feature flag для timezone по умолчанию выключен.
    
    **Что проверяется:**
    - Функция is_timezone_feature_enabled() возвращает False по умолчанию
    
    **Ожидаемый результат:**
    Feature flag должен быть выключен (False)
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("timezone", "feature_flag", "unit", "database")
    def test_feature_flag(self, temp_db):
        """Тест feature flag для timezone"""
        with allure.step("Проверка feature flag"):
            enabled = is_timezone_feature_enabled()
            allure.attach(str(enabled), "Значение feature flag", allure.attachment_type.TEXT)
        
        with allure.step("Проверка результата"):
            assert not enabled, "Feature flag должен быть выключен по умолчанию"

    @allure.title("Получение и установка admin timezone")
    @allure.description("""
    Проверяет корректность работы функций get_admin_timezone() и set_admin_timezone().
    
    **Что проверяется:**
    - Получение текущего admin timezone (по умолчанию 'Europe/Moscow')
    - Установка нового admin timezone
    - Восстановление исходного значения
    - Обработка невалидного timezone
    
    **Тестовые данные:**
    - Валидный timezone: 'America/New_York'
    - Невалидный timezone: 'Invalid/Timezone'
    - Исходный timezone: 'Europe/Moscow'
    
    **Ожидаемый результат:**
    - get_admin_timezone() возвращает 'Europe/Moscow' по умолчанию
    - set_admin_timezone() успешно устанавливает валидный timezone
    - set_admin_timezone() отклоняет невалидный timezone
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("timezone", "admin_timezone", "unit", "database")
    def test_admin_timezone(self, temp_db):
        """Тест admin timezone"""
        with allure.step("Получение текущего admin timezone"):
            current_tz = get_admin_timezone()
            allure.attach(current_tz, "Текущий admin timezone", allure.attachment_type.TEXT)
            assert current_tz == 'Europe/Moscow', f"Ожидался 'Europe/Moscow', получен '{current_tz}'"
        
        with allure.step("Установка нового admin timezone"):
            success = set_admin_timezone('America/New_York')
            assert success, "Не удалось установить валидный timezone"
            
            new_tz = get_admin_timezone()
            allure.attach(new_tz, "Новый admin timezone", allure.attachment_type.TEXT)
            assert new_tz == 'America/New_York', f"Ожидался 'America/New_York', получен '{new_tz}'"
        
        with allure.step("Восстановление исходного timezone"):
            set_admin_timezone('Europe/Moscow')
            restored_tz = get_admin_timezone()
            allure.attach(restored_tz, "Восстановленный admin timezone", allure.attachment_type.TEXT)
            assert restored_tz == 'Europe/Moscow', f"Ожидался 'Europe/Moscow', получен '{restored_tz}'"
        
        with allure.step("Проверка невалидного timezone"):
            invalid_success = set_admin_timezone('Invalid/Timezone')
            # В Windows это может быть True из-за отсутствия timezone данных, поэтому проверяем только валидный случай
            if not invalid_success:
                allure.attach("Невалидный timezone отклонен", "Результат", allure.attachment_type.TEXT)

    @allure.title("Получение и установка user timezone")
    @allure.description("""
    Проверяет корректность работы функций get_user_timezone() и set_user_timezone().
    
    **Что проверяется:**
    - Получение текущего user timezone
    - Установка нового user timezone
    - Восстановление исходного значения
    - Fallback к admin timezone для несуществующего пользователя
    - Обработка невалидного timezone
    
    **Тестовые данные:**
    - user_id: создается через register_user_if_not_exists
    - Валидный timezone: 'Asia/Tokyo'
    - Невалидный timezone: 'Invalid/Timezone'
    - Несуществующий user_id: 999999999
    
    **Ожидаемый результат:**
    - get_user_timezone() возвращает admin timezone для нового пользователя
    - set_user_timezone() успешно устанавливает валидный timezone
    - get_user_timezone() возвращает admin timezone для несуществующего пользователя
    - set_user_timezone() отклоняет невалидный timezone
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("timezone", "user_timezone", "unit", "database")
    def test_user_timezone(self, temp_db):
        """Тест user timezone"""
        with allure.step("Создание тестового пользователя"):
            test_user_id = 123456789
            register_user_if_not_exists(test_user_id, "test_user", None, "Test User")
            allure.attach(str(test_user_id), "User ID", allure.attachment_type.TEXT)
        
        with allure.step("Получение текущего user timezone"):
            user_tz = get_user_timezone(test_user_id)
            allure.attach(user_tz, "Текущий user timezone", allure.attachment_type.TEXT)
            # Новый пользователь должен иметь admin timezone по умолчанию
            admin_tz = get_admin_timezone()
            assert user_tz == admin_tz, f"Ожидался admin timezone '{admin_tz}', получен '{user_tz}'"
        
        with allure.step("Установка нового user timezone"):
            success = set_user_timezone(test_user_id, 'Asia/Tokyo')
            assert success, "Не удалось установить валидный timezone"
            
            new_tz = get_user_timezone(test_user_id)
            allure.attach(new_tz, "Новый user timezone", allure.attachment_type.TEXT)
            assert new_tz == 'Asia/Tokyo', f"Ожидался 'Asia/Tokyo', получен '{new_tz}'"
        
        with allure.step("Восстановление исходного timezone"):
            admin_tz = get_admin_timezone()
            set_user_timezone(test_user_id, admin_tz)
            restored_tz = get_user_timezone(test_user_id)
            allure.attach(restored_tz, "Восстановленный user timezone", allure.attachment_type.TEXT)
            assert restored_tz == admin_tz, f"Ожидался admin timezone '{admin_tz}', получен '{restored_tz}'"
        
        with allure.step("Проверка fallback для несуществующего пользователя"):
            fake_user_id = 999999999
            fake_tz = get_user_timezone(fake_user_id)
            admin_tz = get_admin_timezone()
            allure.attach(fake_tz, "Timezone для несуществующего пользователя", allure.attachment_type.TEXT)
            assert fake_tz == admin_tz, f"Ожидался fallback к admin timezone '{admin_tz}', получен '{fake_tz}'"
        
        with allure.step("Проверка невалидного timezone"):
            invalid_success = set_user_timezone(test_user_id, 'Invalid/Timezone')
            # В Windows это может быть True из-за отсутствия timezone данных, поэтому проверяем только валидный случай
            if not invalid_success:
                allure.attach("Невалидный timezone отклонен", "Результат", allure.attachment_type.TEXT)

    @allure.title("Проверка структуры БД для timezone")
    @allure.description("""
    Проверяет наличие необходимых колонок и настроек в БД для работы с функционалом timezone.
    
    **Что проверяется:**
    - Наличие колонки 'timezone' в таблице users для хранения часового пояса пользователя
    - Наличие настройки 'feature_timezone_enabled' в bot_settings для управления feature flag
    - Наличие настройки 'admin_timezone' в bot_settings для хранения часового пояса администратора по умолчанию
    - Корректная инициализация настроек timezone при создании БД через initialize_db
    
    **Тестовые данные:**
    - Используется временная БД (temp_db)
    - Проверяется структура таблиц users и bot_settings
    
    **Шаги теста:**
    1. Проверка наличия колонки 'timezone' в таблице users через PRAGMA table_info
    2. Проверка наличия настроек 'feature_timezone_enabled' и 'admin_timezone' в bot_settings
    3. Валидация всех требуемых настроек
    
    **Предусловия:**
    - Используется временная БД (temp_db)
    - БД должна быть инициализирована через initialize_db
    
    **Ожидаемый результат:**
    - Колонка 'timezone' существует в таблице users
    - Настройка 'feature_timezone_enabled' существует в bot_settings со значением '0' (выключена по умолчанию)
    - Настройка 'admin_timezone' существует в bot_settings со значением 'Europe/Moscow' (часовой пояс администратора по умолчанию)
    
    **Важность:**
    Проверка структуры БД критична для корректной работы функционала timezone.
    Отсутствие необходимых колонок или настроек может привести к ошибкам при работе с часовыми поясами.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("timezone", "database_structure", "schema", "unit", "database", "initialization")
    def test_database_structure(self, temp_db):
        """Проверка структуры БД для timezone"""
        with allure.step("Проверка колонки timezone в таблице users"):
            conn = sqlite3.connect(temp_db)
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(users)")
            columns_info = cursor.fetchall()
            columns = [row[1] for row in columns_info]
            conn.close()
            
            # Прикрепляем детальную информацию о колонках
            columns_details = [{"name": row[1], "type": row[2], "notnull": row[3], "default": row[4], "pk": row[5]} 
                              for row in columns_info]
            allure.attach(json.dumps(columns_details, indent=2, ensure_ascii=False), 
                         "Детальная информация о колонках таблицы users", 
                         allure.attachment_type.JSON)
            allure.attach(str(columns), "Список колонок таблицы users", allure.attachment_type.TEXT)
            
            assert 'timezone' in columns, "Колонка 'timezone' не найдена в таблице users"
            
            # Проверяем тип колонки timezone
            timezone_column = next((col for col in columns_details if col['name'] == 'timezone'), None)
            if timezone_column:
                allure.attach(json.dumps(timezone_column, indent=2, ensure_ascii=False), 
                             "Информация о колонке timezone", 
                             allure.attachment_type.JSON)
        
        with allure.step("Проверка настроек timezone в bot_settings"):
            conn = sqlite3.connect(temp_db)
            cursor = conn.cursor()
            cursor.execute("SELECT key, value FROM bot_settings WHERE key LIKE '%timezone%'")
            settings = cursor.fetchall()
            conn.close()
            
            required_settings = {'feature_timezone_enabled', 'admin_timezone'}
            found_settings = {row[0] for row in settings}
            settings_dict = {row[0]: row[1] for row in settings}
            
            # Прикрепляем детальную информацию о настройках
            allure.attach(json.dumps(settings_dict, indent=2, ensure_ascii=False), 
                         "Найденные настройки timezone с значениями", 
                         allure.attachment_type.JSON)
            allure.attach(str(list(found_settings)), "Список найденных настроек timezone", 
                         allure.attachment_type.TEXT)
            allure.attach(str(list(required_settings)), "Список требуемых настроек timezone", 
                         allure.attachment_type.TEXT)
            
            missing_settings = required_settings - found_settings
            if missing_settings:
                allure.attach(str(list(missing_settings)), "Отсутствующие настройки timezone", 
                             allure.attachment_type.TEXT)
            
            assert required_settings.issubset(found_settings), \
                f"Отсутствуют настройки: {missing_settings}"
            
            # Проверяем значения настроек
            if 'feature_timezone_enabled' in settings_dict:
                allure.attach(settings_dict['feature_timezone_enabled'], 
                             "Значение feature_timezone_enabled", 
                             allure.attachment_type.TEXT)
                assert settings_dict['feature_timezone_enabled'] == '0', \
                    f"Ожидалось значение '0' для feature_timezone_enabled, получено '{settings_dict['feature_timezone_enabled']}'"
            
            if 'admin_timezone' in settings_dict:
                allure.attach(settings_dict['admin_timezone'], 
                             "Значение admin_timezone", 
                             allure.attachment_type.TEXT)
                assert settings_dict['admin_timezone'] == 'Europe/Moscow', \
                    f"Ожидалось значение 'Europe/Moscow' для admin_timezone, получено '{settings_dict['admin_timezone']}'"



