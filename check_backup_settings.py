import sqlite3

conn = sqlite3.connect('users.db')
cursor = conn.cursor()

# Проверяем таблицы
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = cursor.fetchall()
print("Таблицы:", tables)

# Проверяем backup_settings
cursor.execute("SELECT * FROM backup_settings")
backup_settings = cursor.fetchall()
print("Настройки бекапов:", backup_settings)

# Проверяем bot_settings
cursor.execute("SELECT * FROM bot_settings WHERE key LIKE 'backup_%'")
bot_settings = cursor.fetchall()
print("Настройки бекапов в bot_settings:", bot_settings)

conn.close()
