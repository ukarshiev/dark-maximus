#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Скрипт для отката лишних начислений бонусов по промокодам

Находит пользователей, у которых бонус был начислен многократно при переходе по deeplink ссылке,
и откатывает лишние начисления до корректного значения.

ИСПОЛЬЗОВАНИЕ:
    python rollback_promo_bonus.py --dry-run  # Просмотр без изменений
    python rollback_promo_bonus.py            # Выполнить откат

ВАЖНО: Скрипт работает с продакшн БД через SSH. Будьте осторожны!
"""

import sys
import sqlite3
import argparse
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Tuple

# Добавляем путь к проекту
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root / "src"))

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(project_root / "logs" / "rollback_promo_bonus.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def connect_to_db(db_path: str = "users.db") -> sqlite3.Connection:
    """
    Подключается к БД
    
    Args:
        db_path: Путь к БД (по умолчанию users.db в текущей директории)
    
    Returns:
        Соединение с БД
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def find_users_with_multiple_bonus_applications(conn: sqlite3.Connection, promo_code: str) -> List[Dict]:
    """
    Находит пользователей с многократными начислениями бонусов по промокоду
    
    Args:
        conn: Соединение с БД
        promo_code: Код промокода для проверки
    
    Returns:
        Список пользователей с информацией о начислениях
    """
    cursor = conn.cursor()
    
    # Получаем promo_id по коду
    cursor.execute("SELECT promo_id, discount_bonus FROM promo_codes WHERE code = ?", (promo_code,))
    promo = cursor.fetchone()
    
    if not promo:
        logger.warning(f"Промокод '{promo_code}' не найден в БД")
        return []
    
    promo_id = promo['promo_id']
    bonus_amount = promo['discount_bonus']
    
    logger.info(f"Промокод '{promo_code}' (ID: {promo_id}), бонус: {bonus_amount} RUB")
    
    # Находим всех пользователей, которые применяли этот промокод
    cursor.execute("""
        SELECT 
            pcu.user_id,
            u.username,
            u.balance,
            COUNT(*) as usage_count,
            GROUP_CONCAT(pcu.used_at) as usage_dates
        FROM promo_code_usage pcu
        JOIN users u ON pcu.user_id = u.telegram_id
        WHERE pcu.promo_id = ?
        GROUP BY pcu.user_id
        HAVING COUNT(*) > 1
    """, (promo_id,))
    
    users_with_multiple_usage = []
    for row in cursor.fetchall():
        user_data = dict(row)
        user_data['promo_code'] = promo_code
        user_data['promo_id'] = promo_id
        user_data['bonus_amount'] = bonus_amount
        user_data['expected_bonus'] = bonus_amount  # Должен быть начислен только один раз
        user_data['actual_bonus'] = bonus_amount * user_data['usage_count']  # Фактически начислено
        user_data['excess_bonus'] = user_data['actual_bonus'] - user_data['expected_bonus']  # Лишнее
        users_with_multiple_usage.append(user_data)
    
    return users_with_multiple_usage


def rollback_excess_bonus(conn: sqlite3.Connection, user_id: int, excess_bonus: float, dry_run: bool = True) -> bool:
    """
    Откатывает лишнее начисление бонуса
    
    Args:
        conn: Соединение с БД
        user_id: ID пользователя
        excess_bonus: Сумма лишнего бонуса для отката
        dry_run: Если True, только показывает что будет сделано без изменений
    
    Returns:
        True если откат успешен, False иначе
    """
    cursor = conn.cursor()
    
    # Получаем текущий баланс
    cursor.execute("SELECT balance FROM users WHERE telegram_id = ?", (user_id,))
    user = cursor.fetchone()
    
    if not user:
        logger.error(f"Пользователь {user_id} не найден")
        return False
    
    current_balance = user['balance']
    new_balance = current_balance - excess_bonus
    
    if new_balance < 0:
        logger.warning(f"Откат приведет к отрицательному балансу для пользователя {user_id}: {new_balance}")
        logger.warning(f"Текущий баланс: {current_balance}, откат: {excess_bonus}")
        # Можно решить, что делать в этом случае
        # Вариант 1: Откатить до 0
        # new_balance = 0
        # Вариант 2: Не откатывать
        return False
    
    if dry_run:
        logger.info(f"[DRY RUN] Пользователь {user_id}: баланс {current_balance} -> {new_balance} (откат {excess_bonus} RUB)")
        return True
    else:
        try:
            cursor.execute("UPDATE users SET balance = ? WHERE telegram_id = ?", (new_balance, user_id))
            conn.commit()
            logger.info(f"Пользователь {user_id}: баланс откачен {current_balance} -> {new_balance} (откат {excess_bonus} RUB)")
            return True
        except Exception as e:
            logger.error(f"Ошибка при откате баланса для пользователя {user_id}: {e}")
            conn.rollback()
            return False


def remove_duplicate_promo_usage(conn: sqlite3.Connection, user_id: int, promo_id: int, dry_run: bool = True) -> bool:
    """
    Удаляет дублирующиеся записи в promo_code_usage, оставляя только первую
    
    Args:
        conn: Соединение с БД
        user_id: ID пользователя
        promo_id: ID промокода
        dry_run: Если True, только показывает что будет сделано без изменений
    
    Returns:
        True если удаление успешно, False иначе
    """
    cursor = conn.cursor()
    
    # Получаем все записи для этого пользователя и промокода
    cursor.execute("""
        SELECT usage_id, used_at, status
        FROM promo_code_usage
        WHERE user_id = ? AND promo_id = ?
        ORDER BY used_at ASC
    """, (user_id, promo_id))
    
    records = cursor.fetchall()
    
    if len(records) <= 1:
        logger.info(f"Пользователь {user_id}, промокод {promo_id}: дублирующихся записей нет")
        return True
    
    # Оставляем первую запись, удаляем остальные
    first_record = records[0]
    duplicate_records = records[1:]
    
    if dry_run:
        logger.info(f"[DRY RUN] Пользователь {user_id}, промокод {promo_id}: оставить запись {first_record['usage_id']}, удалить {len(duplicate_records)} дублей")
        for record in duplicate_records:
            logger.info(f"  [DRY RUN] Удалить запись {record['usage_id']} (дата: {record['used_at']}, статус: {record['status']})")
        return True
    else:
        try:
            for record in duplicate_records:
                cursor.execute("DELETE FROM promo_code_usage WHERE usage_id = ?", (record['usage_id'],))
                logger.info(f"Удалена запись {record['usage_id']} (дата: {record['used_at']}, статус: {record['status']})")
            conn.commit()
            logger.info(f"Пользователь {user_id}, промокод {promo_id}: удалено {len(duplicate_records)} дублирующихся записей")
            return True
        except Exception as e:
            logger.error(f"Ошибка при удалении дублирующихся записей для пользователя {user_id}: {e}")
            conn.rollback()
            return False


def main():
    parser = argparse.ArgumentParser(description="Откат лишних начислений бонусов по промокодам")
    parser.add_argument("--dry-run", action="store_true", help="Просмотр без изменений")
    parser.add_argument("--db-path", type=str, default="users.db", help="Путь к БД (по умолчанию users.db)")
    parser.add_argument("--promo-code", type=str, default="FIVEH", help="Код промокода для проверки (по умолчанию FIVEH)")
    parser.add_argument("--specific-users", type=str, help="Список user_id через запятую для отката (например: 6044240344,976124857)")
    
    args = parser.parse_args()
    
    logger.info("=" * 80)
    logger.info(f"Скрипт отката лишних начислений бонусов по промокодам")
    logger.info(f"Дата запуска: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"Режим: {'DRY RUN (без изменений)' if args.dry_run else 'PRODUCTION (с изменениями)'}")
    logger.info(f"БД: {args.db_path}")
    logger.info(f"Промокод: {args.promo_code}")
    logger.info("=" * 80)
    
    # Подключаемся к БД
    try:
        conn = connect_to_db(args.db_path)
        logger.info(f"Подключение к БД успешно: {args.db_path}")
    except Exception as e:
        logger.error(f"Ошибка подключения к БД: {e}")
        return 1
    
    # Находим пользователей с многократными начислениями
    users = find_users_with_multiple_bonus_applications(conn, args.promo_code)
    
    if not users:
        logger.info("Пользователей с многократными начислениями не найдено")
        return 0
    
    logger.info(f"Найдено пользователей с многократными начислениями: {len(users)}")
    logger.info("")
    
    # Фильтруем пользователей, если указаны конкретные ID
    if args.specific_users:
        specific_user_ids = [int(uid.strip()) for uid in args.specific_users.split(',')]
        users = [u for u in users if u['user_id'] in specific_user_ids]
        logger.info(f"Фильтрация по user_id: {specific_user_ids}")
        logger.info(f"Пользователей после фильтрации: {len(users)}")
        logger.info("")
    
    # Выводим информацию о каждом пользователе
    total_excess = 0
    for user in users:
        logger.info(f"Пользователь: {user['user_id']} (@{user['username']})")
        logger.info(f"  Текущий баланс: {user['balance']} RUB")
        logger.info(f"  Количество применений промокода: {user['usage_count']}")
        logger.info(f"  Ожидаемый бонус: {user['expected_bonus']} RUB")
        logger.info(f"  Фактически начислено: {user['actual_bonus']} RUB")
        logger.info(f"  Лишнее начисление: {user['excess_bonus']} RUB")
        logger.info(f"  Даты применения: {user['usage_dates']}")
        logger.info("")
        total_excess += user['excess_bonus']
    
    logger.info(f"Общая сумма лишних начислений: {total_excess} RUB")
    logger.info("")
    
    # Выполняем откат
    if not args.dry_run:
        confirm = input("Выполнить откат? (yes/no): ")
        if confirm.lower() != 'yes':
            logger.info("Откат отменен пользователем")
            return 0
    
    success_count = 0
    fail_count = 0
    
    for user in users:
        logger.info(f"Обработка пользователя {user['user_id']}...")
        
        # Откатываем баланс
        if rollback_excess_bonus(conn, user['user_id'], user['excess_bonus'], args.dry_run):
            # Удаляем дублирующиеся записи
            if remove_duplicate_promo_usage(conn, user['user_id'], user['promo_id'], args.dry_run):
                success_count += 1
            else:
                fail_count += 1
        else:
            fail_count += 1
        
        logger.info("")
    
    logger.info("=" * 80)
    logger.info(f"Обработано пользователей: {len(users)}")
    logger.info(f"Успешно: {success_count}")
    logger.info(f"Ошибок: {fail_count}")
    logger.info(f"Откачено бонусов: {total_excess} RUB")
    logger.info("=" * 80)
    
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())

