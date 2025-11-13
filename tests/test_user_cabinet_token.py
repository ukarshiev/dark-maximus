#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Временный скрипт для создания тестового токена"""

import sys
from pathlib import Path

# Добавляем путь к проекту
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

import sqlite3
from shop_bot.data_manager.database import create_user_token

def main():
    # Подключаемся к БД
    DB_FILE = PROJECT_ROOT / "users.db"

    if not DB_FILE.exists():
        print(f"База данных не найдена: {DB_FILE}")
        return

    conn = sqlite3.connect(str(DB_FILE))
    cursor = conn.cursor()

    # Ищем активный ключ
    cursor.execute("""
        SELECT user_id, key_id 
        FROM vpn_keys 
        WHERE status != 'deactivate' AND enabled = 1 
        LIMIT 1
    """)

    row = cursor.fetchone()
    conn.close()

    if not row:
        print("Нет активных ключей в БД для тестирования")
        return

    user_id, key_id = row
    print(f"Найден ключ: user_id={user_id}, key_id={key_id}")

    # Создаем токен
    try:
        token = create_user_token(user_id, key_id)
        print(f"\nТокен создан успешно!")
        print(f"Token: {token}")
        print(f"\nURL для тестирования:")
        print(f"http://localhost:3003/auth/{token}")
    except Exception as e:
        print(f"Ошибка при создании токена: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()

