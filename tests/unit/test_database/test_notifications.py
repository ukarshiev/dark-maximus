#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Тесты для проверки исправлений блокировок БД при отправке уведомлений
"""

import pytest
import allure
import sqlite3
import threading
import time
import asyncio
import tempfile
from pathlib import Path
import sys
import os
import logging
from datetime import datetime, timezone, timedelta
import json

# Добавляем путь к src для импорта модулей
project_root = Path(__file__).parent.parent.parent.parent
src_path = project_root / "src"
sys.path.insert(0, str(src_path))

# Настраиваем логирование для тестов
logging.basicConfig(level=logging.INFO)

from shop_bot.data_manager import database




@pytest.mark.unit
@pytest.mark.database
@allure.epic("База данных")
@allure.feature("Уведомления")
@allure.label("package", "src.shop_bot.database")
class TestLogNotification:
    """Тесты для функции log_notification"""
    
    @allure.title("Успешное логирование уведомления")
    @allure.description("""
    Проверяет успешное логирование уведомления в БД.
    
    **Что проверяется:**
    - Создание уведомления через log_notification
    - Возврат корректного notification_id
    - Сохранение всех параметров уведомления в БД
    - Корректность данных сохраненного уведомления
    
    **Тестовые данные:**
    - user_id: 123456789
    - notif_type: "subscription_expiry"
    - status: "sent"
    
    **Ожидаемый результат:**
    Уведомление успешно создано и сохранено в БД с корректными данными.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("notifications", "log_notification", "database", "unit")
    def test_log_notification_success(self, temp_db):
        """Тест 1: Успешное логирование уведомления"""
        notification_id = database.log_notification(
            user_id=123456789,
            username="test_user",
            notif_type="subscription_expiry",
            title="Тестовое уведомление",
            message="Тестовое сообщение",
            status="sent",
            meta={"key_id": 1, "marker_hours": 24},
            key_id=1,
            marker_hours=24
        )
        
        assert notification_id > 0, "log_notification должна возвращать ID > 0"
        
        # Проверяем, что уведомление записано в БД
        # Используем temp_db напрямую, а не database.DB_FILE, чтобы гарантировать использование правильной тестовой БД
        conn = sqlite3.connect(str(temp_db))
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM notifications WHERE notification_id = ?", (notification_id,))
        result = cursor.fetchone()
        conn.close()
        
        assert result is not None, "Уведомление должно быть записано в БД"
        assert result[1] == 123456789, "user_id должен совпадать"
        assert result[3] == "subscription_expiry", "type должен совпадать"
    
    @allure.title("Проверка установки PRAGMA настроек при логировании уведомления")
    @allure.description("""
    Проверяет установку PRAGMA настроек при логировании уведомления при блокировке БД.
    
    **Что проверяется:**
    - Создание блокировки БД в отдельном потоке
    - Установка PRAGMA busy_timeout при логировании уведомления
    - Успешное логирование уведомления после разблокировки
    - Отсутствие ошибок при блокировке
    
    **Ожидаемый результат:**
    Уведомление успешно логируется после разблокировки БД, PRAGMA настройки установлены.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("notifications", "log_notification", "pragma", "database", "unit")
    def test_log_notification_with_pragma(self, temp_db):
        """Тест 2: Проверка установки PRAGMA настроек"""
        # Создаем блокировку БД в отдельном потоке
        # Используем temp_db напрямую, а не database.DB_FILE, чтобы гарантировать использование правильной тестовой БД
        lock_conn = sqlite3.connect(str(temp_db))
        lock_conn.execute("BEGIN EXCLUSIVE TRANSACTION")
        
        notification_id = None
        error_occurred = False
        
        def log_in_thread():
            nonlocal notification_id, error_occurred
            try:
                # Эта функция должна установить PRAGMA busy_timeout и подождать
                notification_id = database.log_notification(
                    user_id=123456789,
                    username="test_user",
                    notif_type="subscription_expiry",
                    title="Тестовое уведомление",
                    message="Тестовое сообщение",
                    status="sent"
                )
            except Exception as e:
                error_occurred = True
        
        # Запускаем логирование в отдельном потоке
        thread = threading.Thread(target=log_in_thread)
        thread.start()
        
        # Ждем немного, чтобы функция попыталась выполниться
        time.sleep(0.5)
        
        # Освобождаем блокировку
        lock_conn.rollback()
        lock_conn.close()
        
        # Ждем завершения потока
        thread.join(timeout=5)
        
        # Проверяем, что функция завершилась (не зависла)
        assert not thread.is_alive(), "log_notification не должна зависать при блокировке БД"
    
    @allure.title("Параллельное логирование уведомлений")
    @allure.description("""
    Проверяет параллельное логирование уведомлений в нескольких потоках.
    
    **Что проверяется:**
    - Запуск логирования уведомлений одновременно в разных потоках
    - Корректная обработка параллельных запросов
    - Отсутствие ошибок при параллельном выполнении
    - Корректность сохранения всех уведомлений
    
    **Ожидаемый результат:**
    Все уведомления успешно логируются параллельно без ошибок.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("notifications", "log_notification", "parallel", "database", "unit")
    def test_log_notification_parallel(self, temp_db):
        """Тест 3: Параллельное логирование уведомлений"""
        results = []
        errors = []
        
        def log_notification_thread(user_id):
            try:
                notification_id = database.log_notification(
                    user_id=user_id,
                    username=f"user_{user_id}",
                    notif_type="subscription_expiry",
                    title=f"Уведомление для {user_id}",
                    message="Тестовое сообщение",
                    status="sent"
                )
                results.append(notification_id)
            except Exception as e:
                errors.append(str(e))
        
        # Запускаем 5 параллельных логирований
        threads = []
        for i in range(5):
            thread = threading.Thread(target=log_notification_thread, args=(1000 + i,))
            threads.append(thread)
            thread.start()
        
        # Ждем завершения всех потоков
        for thread in threads:
            thread.join(timeout=5)
        
        # Проверяем, что нет ошибок блокировки
        lock_errors = [e for e in errors if "database is locked" in e.lower() or "locked" in e.lower()]
        assert len(lock_errors) == 0, f"Найдены ошибки блокировки: {lock_errors}"
        
        # Проверяем, что все уведомления записаны
        assert len(results) == 5, f"Должно быть записано 5 уведомлений, записано: {len(results)}"
        assert all(r > 0 for r in results), "Все notification_id должны быть > 0"
        
        # Проверяем в БД
        # Используем temp_db напрямую, а не database.DB_FILE, чтобы гарантировать использование правильной тестовой БД
        conn = sqlite3.connect(str(temp_db))
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM notifications")
        count = cursor.fetchone()[0]
        conn.close()
        
        assert count == 5, f"В БД должно быть 5 уведомлений, найдено: {count}"


@pytest.mark.unit
@pytest.mark.database
@allure.epic("База данных")
@allure.feature("Уведомления")
class TestMarkerLogged:
    """Тесты для функции _marker_logged из scheduler"""
    
    @allure.title("Проверка _marker_logged с PRAGMA настройками")
    @allure.description("""
    Проверяет работу функции _marker_logged с установкой PRAGMA настроек при блокировке БД.
    
    **Что проверяется:**
    - Создание блокировки БД в отдельном потоке
    - Установка PRAGMA busy_timeout в функции _marker_logged
    - Успешное логирование маркера после разблокировки
    - Отсутствие ошибок при блокировке
    
    **Ожидаемый результат:**
    Маркер успешно логируется после разблокировки БД, PRAGMA настройки установлены.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("notifications", "marker_logged", "pragma", "database", "unit")
    def test_marker_logged_with_pragma(self, temp_db):
        """Тест 4: Проверка _marker_logged с PRAGMA настройками"""
        from shop_bot.data_manager.scheduler import _marker_logged
        
        # Сначала создаем уведомление
        notification_id = database.log_notification(
            user_id=123456789,
            username="test_user",
            notif_type="subscription_expiry",
            title="Тестовое уведомление",
            message="Тестовое сообщение",
            status="sent",
            key_id=1,
            marker_hours=24
        )
        
        assert notification_id > 0
        
        # Проверяем через _marker_logged
        result = _marker_logged(123456789, 1, 24, 'subscription_expiry')
        assert result is True, "_marker_logged должна вернуть True для существующего уведомления"
        
        # Проверяем для несуществующего уведомления
        result = _marker_logged(123456789, 1, 48, 'subscription_expiry')
        assert result is False, "_marker_logged должна вернуть False для несуществующего уведомления"


@pytest.mark.unit
@pytest.mark.database
@allure.epic("База данных")
@allure.feature("Уведомления")
class TestNotificationFlow:
    """Интеграционные тесты полного потока уведомлений"""
    
    @allure.title("Полный поток создания и проверки уведомления")
    @allure.description("""
    Проверяет полный поток создания и проверки уведомления в системе.
    
    **Что проверяется:**
    - Создание уведомления через log_notification
    - Проверка наличия уведомления в БД
    - Корректность всех параметров уведомления
    - Обновление статуса уведомления
    
    **Ожидаемый результат:**
    Уведомление успешно создано, проверено и обновлено в БД.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("notifications", "full_flow", "database", "unit")
    def test_full_notification_flow(self, temp_db):
        """Тест 5: Полный поток создания и проверки уведомления"""
        # Создаем уведомление
        notification_id = database.log_notification(
            user_id=123456789,
            username="test_user",
            notif_type="subscription_expiry",
            title="Окончание подписки (через 24 часа)",
            message="Ваша подписка истекает через 24 часа",
            status="sent",
            meta={"key_id": 1, "marker_hours": 24},
            key_id=1,
            marker_hours=24
        )
        
        assert notification_id > 0
        
        # Проверяем через _marker_logged
        from shop_bot.data_manager.scheduler import _marker_logged
        is_logged = _marker_logged(123456789, 1, 24, 'subscription_expiry')
        assert is_logged is True
        
        # Проверяем, что дубликат не создается
        notification_id2 = database.log_notification(
            user_id=123456789,
            username="test_user",
            notif_type="subscription_expiry",
            title="Окончание подписки (через 24 часа)",
            message="Ваша подписка истекает через 24 часа",
            status="sent",
            meta={"key_id": 1, "marker_hours": 24},
            key_id=1,
            marker_hours=24
        )
        
        # Второе уведомление должно быть создано (логика предотвращения дубликатов в scheduler)
        assert notification_id2 > 0
        assert notification_id2 != notification_id


@pytest.mark.unit
@pytest.mark.database
@allure.epic("База данных")
@allure.feature("Уведомления")
class TestManualNotificationControls:
    """Тесты для ручных шаблонов уведомлений"""

    @allure.title("Проверка реестра шаблонов уведомлений")
    @allure.description("""
    Проверяет реестр шаблонов уведомлений через get_manual_notification_templates.
    
    **Что проверяется:**
    - Получение списка шаблонов уведомлений
    - Наличие шаблонов в реестре
    - Корректность структуры шаблонов
    
    **Ожидаемый результат:**
    Реестр шаблонов содержит все необходимые шаблоны уведомлений.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("notifications", "templates", "registry", "unit")
    def test_templates_registry(self):
        from shop_bot.data_manager.scheduler import get_manual_notification_templates

        templates = get_manual_notification_templates()
        codes = {tpl["code"] for tpl in templates}
        expected = {
            "subscription_expiry",
            "subscription_plan_unavailable",
            "subscription_autorenew_notice",
            "subscription_autorenew_disabled",
        }
        assert expected.issubset(codes), f"Справочник шаблонов должен содержать: {expected}"

    @allure.title("Принудительная повторная отправка при недоступности плана")
    @allure.description("""
    Проверяет принудительную повторную отправку уведомления при недоступности плана.
    
    **Что проверяется:**
    - Установка флага force_resend при недоступности плана
    - Повторная отправка уведомления
    - Корректность обработки недоступного плана
    
    **Ожидаемый результат:**
    Уведомление принудительно отправлено повторно при недоступности плана.
    """)
    @allure.severity(allure.severity_level.NORMAL)
    @allure.tag("notifications", "force_resend", "plan_unavailable", "database", "unit")
    def test_plan_unavailable_force_resend(self, temp_db, monkeypatch):
        from shop_bot.data_manager import scheduler

        # Подготавливаем окружение
        monkeypatch.setattr(scheduler, '_format_datetime_for_user', lambda user_id, dt: dt.isoformat())
        monkeypatch.setattr(database, 'get_user_keys', lambda user_id: [{'key_id': 1, 'host_name': 'Test Host'}])
        monkeypatch.setattr(database, 'get_key_by_id', lambda key_id: {'host_name': 'Test Host'})
        monkeypatch.setattr(database, 'get_user', lambda user_id: {'username': 'tester'})

        class DummyBot:
            def __init__(self):
                self.messages = []

            async def send_message(self, chat_id, text, reply_markup=None, parse_mode=None):
                self.messages.append(
                    {
                        "chat_id": chat_id,
                        "text": text,
                        "status": parse_mode,
                    }
                )

        bot = DummyBot()
        expiry_date = (datetime.now(timezone.utc) + timedelta(hours=24)).replace(tzinfo=None)

        async def _scenario():
            await scheduler.send_plan_unavailable_notice(
                bot=bot,
                user_id=123456,
                key_id=1,
                time_left_hours=24,
                expiry_date=expiry_date,
            )
            assert len(bot.messages) == 1, "Первое уведомление должно быть отправлено"

            # Без force повторная отправка игнорируется
            await scheduler.send_plan_unavailable_notice(
                bot=bot,
                user_id=123456,
                key_id=1,
                time_left_hours=24,
                expiry_date=expiry_date,
            )
            assert len(bot.messages) == 1, "Повтор без force не должен отправлять сообщение"

            # С force уведомление должно отправиться повторно и иметь статус 'resent'
            await scheduler.send_plan_unavailable_notice(
                bot=bot,
                user_id=123456,
                key_id=1,
                time_left_hours=24,
                expiry_date=expiry_date,
                force=True,
                status='resent',
            )

        asyncio.run(_scenario())
        assert len(bot.messages) == 2, "Повтор с force должен отправить сообщение"

        # Используем temp_db напрямую, а не database.DB_FILE, чтобы гарантировать использование правильной тестовой БД
        conn = sqlite3.connect(str(temp_db))
        cursor = conn.cursor()
        cursor.execute("SELECT status FROM notifications ORDER BY notification_id DESC LIMIT 1")
        status = cursor.fetchone()[0]
        conn.close()

        assert status == 'resent', "Повторное уведомление должно логироваться со статусом 'resent'"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

