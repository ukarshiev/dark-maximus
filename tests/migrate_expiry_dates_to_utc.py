#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Скрипт миграции дат expiry_date в UTC

Этот скрипт анализирует и мигрирует даты в таблице vpn_keys,
конвертируя их из локального времени (UTC+3) в UTC.

ВАЖНО: По умолчанию работает в режиме dry-run (не применяет изменения)
Для применения изменений используйте флаг --apply

Использование:
    python tests/migrate_expiry_dates_to_utc.py                 # dry-run режим
    python tests/migrate_expiry_dates_to_utc.py --apply         # применить изменения
    python tests/migrate_expiry_dates_to_utc.py --analyze       # только анализ
"""

import sys
import sqlite3
import argparse
from datetime import datetime, timezone, timedelta
from pathlib import Path
import shutil
import logging

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('tests/migration_expiry_dates.log'),
        logging.StreamHandler()
    ]
)

# Константы
DB_FILE = "users.db"
MOSCOW_TZ = timezone(timedelta(hours=3))
UTC = timezone.utc


def create_backup(db_path: Path) -> Path:
    """Создает резервную копию БД"""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_dir = Path("backups")
    backup_dir.mkdir(exist_ok=True)
    
    backup_path = backup_dir / f"users_{timestamp}_before_expiry_migration.db"
    shutil.copy2(db_path, backup_path)
    
    logging.info(f"✅ Резервная копия создана: {backup_path}")
    return backup_path


def analyze_expiry_dates(db_path: Path) -> dict:
    """
    Анализирует даты в БД и определяет, нужна ли миграция
    
    Returns:
        dict с результатами анализа
    """
    logging.info("🔍 Начинаем анализ дат в БД...")
    
    results = {
        'total_keys': 0,
        'active_keys': 0,
        'expired_keys': 0,
        'dates_analyzed': [],
        'need_migration': False,
        'estimated_offset_hours': 0
    }
    
    try:
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Получаем все ключи с датами
            cursor.execute("""
                SELECT key_id, key_email, expiry_date, status, created_date
                FROM vpn_keys
                ORDER BY key_id
            """)
            
            rows = cursor.fetchall()
            results['total_keys'] = len(rows)
            
            if results['total_keys'] == 0:
                logging.warning("⚠️ В БД нет ключей для анализа")
                return results
            
            # Анализируем каждую дату
            now_utc = datetime.now(UTC)
            suspected_offset_hours = []
            
            for row in rows:
                key_id = row['key_id']
                expiry_str = row['expiry_date']
                status = row['status']
                
                if not expiry_str:
                    logging.warning(f"⚠️ Ключ {key_id}: expiry_date отсутствует")
                    continue
                
                # Парсим дату (предполагаем формат ISO или Python default)
                try:
                    expiry_naive = datetime.fromisoformat(expiry_str.replace('Z', '+00:00'))
                    if expiry_naive.tzinfo:
                        expiry_naive = expiry_naive.replace(tzinfo=None)
                except ValueError:
                    try:
                        expiry_naive = datetime.strptime(expiry_str, '%Y-%m-%d %H:%M:%S')
                    except ValueError:
                        logging.error(f"❌ Не удалось распарсить дату для ключа {key_id}: {expiry_str}")
                        continue
                
                # Проверяем статус
                is_active = status in ['trial-active', 'pay-active']
                if is_active:
                    results['active_keys'] += 1
                else:
                    results['expired_keys'] += 1
                
                # Предполагаем, что дата в БД - это UTC+3
                expiry_as_moscow = expiry_naive.replace(tzinfo=MOSCOW_TZ)
                expiry_as_utc_from_moscow = expiry_as_moscow.astimezone(UTC).replace(tzinfo=None)
                
                # Или дата уже в UTC?
                expiry_as_utc = expiry_naive.replace(tzinfo=UTC)
                
                # Разница между интерпретациями
                diff_hours = (expiry_as_utc_from_moscow - expiry_naive).total_seconds() / 3600
                
                results['dates_analyzed'].append({
                    'key_id': key_id,
                    'key_email': row['key_email'],
                    'expiry_naive': expiry_naive,
                    'expiry_as_moscow': expiry_as_utc_from_moscow,
                    'diff_hours': diff_hours,
                    'status': status
                })
                
                # Собираем статистику по offset
                if abs(diff_hours) > 0.1:  # Если разница больше 6 минут
                    suspected_offset_hours.append(diff_hours)
            
            # Определяем, нужна ли миграция
            if suspected_offset_hours:
                avg_offset = sum(suspected_offset_hours) / len(suspected_offset_hours)
                results['estimated_offset_hours'] = round(avg_offset, 2)
                
                # Если средний offset близок к 3 часам, значит даты в локальном времени
                if abs(avg_offset + 3) < 0.5:  # offset = -3 (нужно вычесть 3 часа)
                    results['need_migration'] = True
                    logging.warning(f"⚠️ Обнаружено смещение ~{avg_offset:.2f} часов - даты вероятно в UTC+3")
                else:
                    logging.info(f"ℹ️ Обнаружено смещение {avg_offset:.2f} часов - неясно, нужна ли миграция")
            
            logging.info(f"📊 Анализ завершен:")
            logging.info(f"   - Всего ключей: {results['total_keys']}")
            logging.info(f"   - Активных: {results['active_keys']}")
            logging.info(f"   - Истекших: {results['expired_keys']}")
            logging.info(f"   - Оценочное смещение: {results['estimated_offset_hours']} часов")
            logging.info(f"   - Миграция нужна: {'ДА' if results['need_migration'] else 'НЕТ'}")
            
            return results
            
    except sqlite3.Error as e:
        logging.error(f"❌ Ошибка при анализе БД: {e}")
        raise


def migrate_expiry_dates(db_path: Path, dry_run: bool = True) -> dict:
    """
    Мигрирует даты из локального времени (UTC+3) в UTC
    
    Args:
        db_path: путь к БД
        dry_run: если True, не применяет изменения
        
    Returns:
        dict с результатами миграции
    """
    results = {
        'total_migrated': 0,
        'failed': 0,
        'skipped': 0,
        'changes': []
    }
    
    mode_text = "DRY-RUN" if dry_run else "ПРИМЕНЕНИЕ"
    logging.info(f"🔄 Начинаем миграцию ({mode_text})...")
    
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            
            # Получаем все ключи
            cursor.execute("""
                SELECT key_id, key_email, expiry_date, status
                FROM vpn_keys
                WHERE expiry_date IS NOT NULL
                ORDER BY key_id
            """)
            
            rows = cursor.fetchall()
            
            for row in rows:
                key_id, key_email, expiry_str, status = row
                
                try:
                    # Парсим дату
                    try:
                        expiry_naive = datetime.fromisoformat(expiry_str.replace('Z', '+00:00'))
                        if expiry_naive.tzinfo:
                            expiry_naive = expiry_naive.replace(tzinfo=None)
                    except ValueError:
                        expiry_naive = datetime.strptime(expiry_str, '%Y-%m-%d %H:%M:%S')
                    
                    # Предполагаем, что дата в БД - это UTC+3 (локальное время)
                    # Конвертируем в UTC: вычитаем 3 часа
                    expiry_utc = expiry_naive - timedelta(hours=3)
                    
                    # Форматируем для записи в БД
                    expiry_utc_str = expiry_utc.strftime('%Y-%m-%d %H:%M:%S')
                    
                    # Логируем изменение
                    change = {
                        'key_id': key_id,
                        'key_email': key_email,
                        'old_date': expiry_str,
                        'new_date': expiry_utc_str,
                        'diff_hours': -3
                    }
                    results['changes'].append(change)
                    
                    if not dry_run:
                        # Применяем изменение
                        cursor.execute("""
                            UPDATE vpn_keys
                            SET expiry_date = ?
                            WHERE key_id = ?
                        """, (expiry_utc_str, key_id))
                        
                        logging.debug(f"✅ Ключ {key_id}: {expiry_str} -> {expiry_utc_str}")
                    else:
                        logging.debug(f"📝 Ключ {key_id}: {expiry_str} -> {expiry_utc_str} (DRY-RUN)")
                    
                    results['total_migrated'] += 1
                    
                except Exception as e:
                    logging.error(f"❌ Ошибка при миграции ключа {key_id}: {e}")
                    results['failed'] += 1
            
            if not dry_run:
                conn.commit()
                logging.info("✅ Изменения сохранены в БД")
            else:
                logging.info("📝 DRY-RUN: изменения не применены")
            
            logging.info(f"📊 Результаты миграции:")
            logging.info(f"   - Мигрировано: {results['total_migrated']}")
            logging.info(f"   - Ошибок: {results['failed']}")
            logging.info(f"   - Пропущено: {results['skipped']}")
            
            return results
            
    except sqlite3.Error as e:
        logging.error(f"❌ Ошибка при миграции БД: {e}")
        raise


def print_analysis_report(results: dict):
    """Выводит детальный отчет по анализу"""
    print("\n" + "="*80)
    print("📋 ДЕТАЛЬНЫЙ ОТЧЕТ АНАЛИЗА")
    print("="*80)
    
    print(f"\n📊 Общая статистика:")
    print(f"   - Всего ключей: {results['total_keys']}")
    print(f"   - Активных: {results['active_keys']}")
    print(f"   - Истекших: {results['expired_keys']}")
    print(f"   - Оценочное смещение: {results['estimated_offset_hours']} часов")
    print(f"   - Миграция нужна: {'ДА ✅' if results['need_migration'] else 'НЕТ ❌'}")
    
    if results['dates_analyzed']:
        print(f"\n🔍 Примеры дат (первые 5):")
        for i, item in enumerate(results['dates_analyzed'][:5], 1):
            print(f"\n   {i}. Ключ {item['key_id']} ({item['key_email']}):")
            print(f"      - Дата в БД (naive):     {item['expiry_naive']}")
            print(f"      - Если это UTC+3 -> UTC: {item['expiry_as_moscow']}")
            print(f"      - Разница: {item['diff_hours']:.2f} часов")
            print(f"      - Статус: {item['status']}")
    
    print("\n" + "="*80)


def main():
    parser = argparse.ArgumentParser(
        description='Миграция дат expiry_date в UTC',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    
    parser.add_argument(
        '--apply',
        action='store_true',
        help='Применить изменения (по умолчанию: dry-run)'
    )
    
    parser.add_argument(
        '--analyze',
        action='store_true',
        help='Только анализ, без миграции'
    )
    
    parser.add_argument(
        '--db',
        default=DB_FILE,
        help=f'Путь к БД (по умолчанию: {DB_FILE})'
    )
    
    args = parser.parse_args()
    
    db_path = Path(args.db)
    
    if not db_path.exists():
        logging.error(f"❌ БД не найдена: {db_path}")
        sys.exit(1)
    
    print("\n" + "="*80)
    print("🔧 МИГРАЦИЯ EXPIRY_DATE В UTC")
    print("="*80)
    
    # Анализ
    analysis_results = analyze_expiry_dates(db_path)
    
    if args.analyze:
        print_analysis_report(analysis_results)
        return
    
    # Если миграция не нужна, предупреждаем
    if not analysis_results['need_migration']:
        print("\n⚠️ Анализ показал, что миграция не требуется.")
        print("   Даты вероятно уже в UTC или имеют другой формат.")
        
        response = input("\n❓ Продолжить миграцию? (yes/no): ").strip().lower()
        if response not in ['yes', 'y', 'да', 'д']:
            print("❌ Миграция отменена пользователем")
            return
    
    # Создаем бэкап (если не dry-run)
    if args.apply:
        create_backup(db_path)
    
    # Миграция
    dry_run = not args.apply
    migration_results = migrate_expiry_dates(db_path, dry_run=dry_run)
    
    # Финальный отчет
    print("\n" + "="*80)
    print("✅ МИГРАЦИЯ ЗАВЕРШЕНА")
    print("="*80)
    print(f"\nРежим: {'DRY-RUN (изменения не применены)' if dry_run else 'ПРИМЕНЕНО'}")
    print(f"Мигрировано: {migration_results['total_migrated']}")
    print(f"Ошибок: {migration_results['failed']}")
    
    if dry_run:
        print("\n💡 Для применения изменений запустите с флагом --apply:")
        print(f"   python {sys.argv[0]} --apply")
    else:
        print("\n✅ Изменения успешно применены!")
        print(f"📦 Резервная копия сохранена в папке backups/")
    
    print("="*80 + "\n")


if __name__ == '__main__':
    main()

