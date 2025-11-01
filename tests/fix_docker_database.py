#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Исправление базы данных в Docker контейнере"""

import subprocess

def fix_docker_database():
    cmd = '''import sqlite3
conn = sqlite3.connect('/app/project/users.db')
cursor = conn.cursor()

print('Current UNIQUE constraint:')
cursor.execute('SELECT sql FROM sqlite_master WHERE type="table" AND name="promo_code_usage"')
table_sql = cursor.fetchone()[0]
print(table_sql)

print('\\nApplying migration...')
cursor.execute('CREATE TABLE promo_code_usage_new (usage_id INTEGER PRIMARY KEY AUTOINCREMENT, promo_id INTEGER NOT NULL, user_id INTEGER, bot TEXT NOT NULL, plan_id INTEGER, discount_amount REAL DEFAULT 0, discount_percent REAL DEFAULT 0, discount_bonus REAL DEFAULT 0, metadata TEXT, used_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, status TEXT DEFAULT "applied", FOREIGN KEY (promo_id) REFERENCES promo_codes (promo_id), FOREIGN KEY (plan_id) REFERENCES plans (plan_id), FOREIGN KEY (user_id) REFERENCES users (telegram_id), UNIQUE (promo_id, user_id, bot))')

cursor.execute('INSERT INTO promo_code_usage_new SELECT * FROM promo_code_usage')

cursor.execute('DROP TABLE promo_code_usage')
cursor.execute('ALTER TABLE promo_code_usage_new RENAME TO promo_code_usage')

cursor.execute('CREATE INDEX IF NOT EXISTS idx_promo_code_usage_promo_id ON promo_code_usage(promo_id)')
cursor.execute('CREATE INDEX IF NOT EXISTS idx_promo_code_usage_user_id ON promo_code_usage(user_id)')
cursor.execute('CREATE INDEX IF NOT EXISTS idx_promo_code_usage_bot ON promo_code_usage(bot)')
cursor.execute('CREATE INDEX IF NOT EXISTS idx_promo_code_usage_status ON promo_code_usage(status)')

cursor.execute('INSERT INTO migration_history (migration_id) VALUES ("promo_code_usage_fix_unique_constraint")')

conn.commit()
print('Migration completed successfully!')

print('\\nNew UNIQUE constraint:')
cursor.execute('SELECT sql FROM sqlite_master WHERE type="table" AND name="promo_code_usage"')
table_sql = cursor.fetchone()[0]
print('UNIQUE constraint correct:', 'UNIQUE (promo_id, user_id, bot)' in table_sql)

conn.close()'''
    
    result = subprocess.run(['docker', 'exec', 'dark-maximus-bot', 'python', '-c', cmd], 
                          capture_output=True, text=True)
    
    print("STDOUT:")
    print(result.stdout)
    print("\nSTDERR:")
    print(result.stderr)
    print(f"\nReturn code: {result.returncode}")

if __name__ == "__main__":
    fix_docker_database()
