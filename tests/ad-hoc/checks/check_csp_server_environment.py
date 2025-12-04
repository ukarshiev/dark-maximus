#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Диагностический скрипт для проверки server_environment и CSP заголовков
Используется для диагностики проблемы с тестом test_csp_has_valid_wildcard_for_subdomains
"""

import sys
import os
from pathlib import Path

# Определяем путь к проекту
if os.path.exists("/app/project"):
    PROJECT_ROOT = Path("/app/project")
else:
    PROJECT_ROOT = Path(__file__).parent.parent.parent.parent

sys.path.insert(0, str(PROJECT_ROOT / "src"))

from shop_bot.data_manager.database import (
    get_setting,
    get_server_environment,
    is_development_server,
    is_production_server,
    get_all_settings
)

def main():
    print("=" * 80)
    print("ДИАГНОСТИКА: Проверка server_environment и CSP заголовков")
    print("=" * 80)
    print()
    
    # Проверяем настройку server_environment
    print("1. Проверка настройки server_environment в БД:")
    print("-" * 80)
    
    server_env = get_server_environment()
    print(f"   get_server_environment() = '{server_env}'")
    
    server_env_setting = get_setting("server_environment")
    print(f"   get_setting('server_environment') = {repr(server_env_setting)}")
    
    is_dev = is_development_server()
    print(f"   is_development_server() = {is_dev}")
    
    is_prod = is_production_server()
    print(f"   is_production_server() = {is_prod}")
    
    print()
    
    # Проверяем домены
    print("2. Проверка доменов из настроек БД:")
    print("-" * 80)
    
    settings = get_all_settings()
    global_domain = settings.get('global_domain', '').strip()
    codex_docs_domain = settings.get('codex_docs_domain', '').strip()
    
    print(f"   global_domain = {repr(global_domain)}")
    print(f"   codex_docs_domain = {repr(codex_docs_domain)}")
    
    # Очищаем домены от протокола
    if global_domain:
        main_domain = global_domain.replace('http://', '').replace('https://', '').split('/')[0].split(':')[0]
    else:
        main_domain = 'dark-maximus.com'  # fallback
    
    if codex_docs_domain:
        help_domain = codex_docs_domain.replace('http://', '').replace('https://', '').split('/')[0].split(':')[0]
    else:
        help_domain = 'help.dark-maximus.com'  # fallback
    
    print(f"   main_domain (очищенный) = {repr(main_domain)}")
    print(f"   help_domain (очищенный) = {repr(help_domain)}")
    
    print()
    
    # Показываем, какие CSP заголовки будут использоваться
    print("3. Ожидаемые CSP заголовки:")
    print("-" * 80)
    
    if is_dev:
        print("   РЕЖИМ: development")
        print()
        print("   frame-src будет:")
        print("     'self' http: https:")
        print("   (БЕЗ wildcard паттерна)")
        print()
        print("   connect-src будет:")
        print(f"     'self' https://api.2ip.ru https://api.2ip.io https://ipwho.is https://{help_domain} https://*.{main_domain}")
        print("   (С wildcard паттерном)")
    else:
        print("   РЕЖИМ: production")
        print()
        print("   frame-src будет:")
        print(f"     'self' https://{help_domain} https://*.{main_domain} https:")
        print("   (С wildcard паттерном)")
        print()
        print("   connect-src будет:")
        print(f"     'self' https://api.2ip.ru https://api.2ip.io https://ipwho.is https://{help_domain} https://*.{main_domain}")
        print("   (С wildcard паттерном)")
    
    print()
    
    # Диагностика проблемы
    print("4. Диагностика проблемы:")
    print("-" * 80)
    
    if is_dev:
        print("   ⚠️  ПРОБЛЕМА ОБНАРУЖЕНА:")
        print("   - server_environment установлен в 'development'")
        print("   - В development режиме frame-src НЕ содержит wildcard паттерн")
        print("   - Тест test_csp_has_valid_wildcard_for_subdomains проверяет wildcard в frame-src")
        print("   - Тест будет падать, так как wildcard паттерн отсутствует")
        print()
        print("   РЕШЕНИЕ:")
        print("   1. Установить server_environment = 'production' через веб-панель")
        print("      (/settings → Глобальные параметры → Тип сервера)")
        print("   2. Перезапустить user-cabinet контейнер:")
        print("      docker compose restart user-cabinet")
    else:
        print("   ✅ Настройка корректна:")
        print("   - server_environment установлен в 'production'")
        print("   - CSP заголовки должны содержать wildcard паттерны")
        print("   - Если тест все еще падает, проверьте другие причины")
    
    print()
    print("=" * 80)

if __name__ == "__main__":
    main()

