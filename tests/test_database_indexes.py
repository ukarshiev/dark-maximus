import importlib

import shop_bot.data_manager.database as database


def test_database_module_import_reload():
    """Убеждаемся, что модуль `database` без синтаксических ошибок и экспортирует функцию индексации."""
    reloaded = importlib.reload(database)
    assert hasattr(reloaded, "create_database_indexes")

