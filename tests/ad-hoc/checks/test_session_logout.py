#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Тест для проверки проблемы с логаутом при переходе на кабинет

Проверяет:
1. Авторизацию в панели
2. Сохранение cookie сессии
3. Переход на кабинет
4. Состояние сессии панели после перехода
"""

import requests
import sys
from pathlib import Path

# Добавляем путь к проекту
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from shop_bot.data_manager.database import get_setting

# URL сервисов
PANEL_URL = "http://localhost:50000"
CABINET_URL = "http://localhost:50003"

def test_session_behavior():
    """Тестирует поведение сессий при переходе на кабинет"""
    
    # Создаем сессию для панели
    panel_session = requests.Session()
    
    print("=" * 60)
    print("ТЕСТ: Проверка поведения сессий при переходе на кабинет")
    print("=" * 60)
    
    # Шаг 1: Получаем логин и пароль из БД
    try:
        login = get_setting("panel_login")
        password = get_setting("panel_password")
        
        if not login or not password:
            print("❌ ОШИБКА: Логин или пароль не найдены в БД")
            return False
            
        print(f"✓ Логин получен из БД: {login}")
    except Exception as e:
        print(f"❌ ОШИБКА при получении логина/пароля: {e}")
        return False
    
    # Шаг 2: Авторизация в панели
    print("\n[1] Авторизация в панели...")
    try:
        login_response = panel_session.post(
            f"{PANEL_URL}/login",
            data={"username": login, "password": password},
            allow_redirects=True  # Разрешаем редиректы
        )
        
        print(f"   Статус: {login_response.status_code}")
        print(f"   Финальный URL: {login_response.url}")
        print(f"   История редиректов: {[r.url for r in login_response.history]}")
        
        # Проверяем cookie после логина
        panel_cookies = panel_session.cookies.get_dict()
        print(f"   Cookie после логина: {panel_cookies}")
        print(f"   Все cookie объекты: {list(panel_session.cookies)}")
        
        # Проверяем заголовки Set-Cookie
        if hasattr(login_response, 'headers'):
            set_cookie_headers = login_response.headers.get('Set-Cookie', '')
            print(f"   Set-Cookie заголовок: {set_cookie_headers}")
        
        if login_response.status_code != 200:
            print(f"⚠️ Неожиданный статус: {login_response.status_code}")
            
        if 'session' not in panel_cookies:
            print("⚠️ Cookie 'session' не найден в словаре, проверяем все cookie...")
            for cookie in panel_session.cookies:
                print(f"      Cookie: {cookie.name} = {cookie.value[:20]}... (domain={cookie.domain}, path={cookie.path})")
        else:
            print("✓ Cookie 'session' найден")
            
        print("✓ Авторизация выполнена")
        
    except Exception as e:
        print(f"❌ ОШИБКА при авторизации: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Шаг 3: Проверяем доступ к защищенной странице панели
    print("\n[2] Проверка доступа к защищенной странице панели...")
    try:
        dashboard_response = panel_session.get(f"{PANEL_URL}/dashboard", allow_redirects=False)
        print(f"   Статус: {dashboard_response.status_code}")
        
        if dashboard_response.status_code == 302:
            redirect_location = dashboard_response.headers.get('Location', '')
            print(f"   Редирект на: {redirect_location}")
            if 'login' in redirect_location:
                print("❌ ОШИБКА: Произошел редирект на логин - сессия не работает")
                return False
        elif dashboard_response.status_code == 200:
            print("✓ Доступ к панели есть, сессия работает")
        else:
            print(f"⚠️ Неожиданный статус: {dashboard_response.status_code}")
            
    except Exception as e:
        print(f"❌ ОШИБКА при проверке доступа: {e}")
        return False
    
    # Шаг 4: Получаем ссылку на кабинет
    print("\n[3] Получение ссылки на кабинет...")
    try:
        # Получаем dashboard для получения latest_cabinet_link
        dashboard_response = panel_session.get(f"{PANEL_URL}/dashboard")
        if dashboard_response.status_code != 200:
            print(f"❌ ОШИБКА: Не удалось получить dashboard (статус {dashboard_response.status_code})")
            return False
        
        # Ищем ссылку на кабинет в HTML
        import re
        cabinet_link_match = re.search(r'href="([^"]*localhost:50003[^"]*)"', dashboard_response.text)
        
        if not cabinet_link_match:
            print("⚠️ Ссылка на кабинет не найдена в dashboard")
            # Используем базовый URL кабинета
            cabinet_url = f"{CABINET_URL}/"
        else:
            cabinet_url = cabinet_link_match.group(1)
            print(f"✓ Найдена ссылка на кабинет: {cabinet_url}")
        
    except Exception as e:
        print(f"❌ ОШИБКА при получении ссылки на кабинет: {e}")
        return False
    
    # Шаг 5: Открываем кабинет в той же сессии (симуляция перехода)
    print("\n[4] Открытие кабинета (симуляция перехода)...")
    try:
        cabinet_response = panel_session.get(cabinet_url, allow_redirects=True)
        print(f"   Статус: {cabinet_response.status_code}")
        print(f"   Финальный URL: {cabinet_response.url}")
        
        # Проверяем cookie после перехода на кабинет
        cookies_after_cabinet = panel_session.cookies.get_dict()
        print(f"   Cookie после перехода на кабинет: {cookies_after_cabinet}")
        
        # Проверяем, изменился ли cookie session
        if 'session' in cookies_after_cabinet:
            if cookies_after_cabinet['session'] != panel_cookies.get('session'):
                print("⚠️ ВНИМАНИЕ: Cookie 'session' изменился после перехода на кабинет!")
            else:
                print("✓ Cookie 'session' не изменился")
        else:
            print("⚠️ Cookie 'session' отсутствует после перехода на кабинет")
            
    except Exception as e:
        print(f"❌ ОШИБКА при открытии кабинета: {e}")
        return False
    
    # Шаг 6: Проверяем, работает ли еще сессия панели
    print("\n[5] Проверка сессии панели после перехода на кабинет...")
    try:
        dashboard_check = panel_session.get(f"{PANEL_URL}/dashboard", allow_redirects=False)
        print(f"   Статус: {dashboard_check.status_code}")
        
        if dashboard_check.status_code == 302:
            redirect_location = dashboard_check.headers.get('Location', '')
            print(f"   Редирект на: {redirect_location}")
            if 'login' in redirect_location:
                print("❌ ПРОБЛЕМА ПОДТВЕРЖДЕНА: Сессия панели потеряна после перехода на кабинет!")
                return False
            else:
                print("✓ Редирект, но не на логин")
        elif dashboard_check.status_code == 200:
            print("✓ Сессия панели все еще работает")
        else:
            print(f"⚠️ Неожиданный статус: {dashboard_check.status_code}")
            
    except Exception as e:
        print(f"❌ ОШИБКА при проверке сессии: {e}")
        return False
    
    # Шаг 7: Создаем отдельную сессию для кабинета (как в реальном браузере)
    print("\n[6] Тест с отдельной сессией для кабинета (как в реальном браузере)...")
    try:
        # Создаем новую сессию для кабинета (симуляция новой вкладки)
        cabinet_session = requests.Session()
        
        # Копируем cookie из панели (симуляция того, что браузер может отправить)
        if 'session' in panel_session.cookies:
            cabinet_session.cookies.set('session', panel_session.cookies.get('session'), domain='localhost')
        
        # Пытаемся открыть кабинет
        cabinet_test = cabinet_session.get(cabinet_url, allow_redirects=True)
        print(f"   Статус кабинета: {cabinet_test.status_code}")
        print(f"   Cookie кабинета: {cabinet_session.cookies.get_dict()}")
        
        # Проверяем панель снова
        panel_final_check = panel_session.get(f"{PANEL_URL}/dashboard", allow_redirects=False)
        print(f"   Статус панели после теста кабинета: {panel_final_check.status_code}")
        
        if panel_final_check.status_code == 302 and 'login' in panel_final_check.headers.get('Location', ''):
            print("❌ ПРОБЛЕМА ПОДТВЕРЖДЕНА: Сессия панели потеряна!")
            return False
        
    except Exception as e:
        print(f"❌ ОШИБКА при тесте с отдельной сессией: {e}")
        return False
    
    print("\n" + "=" * 60)
    print("✓ ТЕСТ ЗАВЕРШЕН: Сессия панели не потеряна")
    print("=" * 60)
    return True

if __name__ == "__main__":
    success = test_session_behavior()
    sys.exit(0 if success else 1)

