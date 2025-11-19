#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Общие фикстуры для pytest тестов
"""

import pytest
import sqlite3
import sys
import shutil
import logging
import time
import os
from pathlib import Path
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Определяем путь к корню проекта для загрузки .env файла
project_root = Path(__file__).parent.parent

# Загружаем переменные окружения из .env файла
# Явно указываем путь к .env файлу в корне проекта
env_path = project_root / ".env"
load_dotenv(dotenv_path=env_path, override=True)

# Игнорировать одноразовые скрипты из ad-hoc/tests/
def pytest_ignore_collect(collection_path, config):
    """Игнорировать файлы из tests/ad-hoc/tests/ при сборе тестов"""
    path_str = str(collection_path)
    if 'ad-hoc/tests' in path_str or 'ad-hoc\\tests' in path_str:
        return True
    return None

# Добавляем путь к src для импорта модулей
src_path = project_root / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from shop_bot.data_manager import database

# Настройка логирования
logger = logging.getLogger(__name__)

# Определяем пути для тестовой БД
TEST_DB_PATH = project_root / "temp_db.db"  # Постоянный путь для тестовой БД
PRODUCTION_DB_PATH = project_root / "users.db"  # Путь к реальной БД
CACHE_TIMEOUT_MINUTES = 5  # Время жизни кэша в минутах


def should_recreate_test_db() -> bool:
    """
    Проверяет, нужно ли пересоздавать тестовую БД.
    
    Returns:
        True если нужно пересоздать, False если можно использовать существующую
    """
    # Если БД не существует - нужно создать
    if not TEST_DB_PATH.exists():
        logger.info(f"ℹ️ Тестовая БД не найдена: {TEST_DB_PATH}. Нужно создать.")
        return True
    
    # Проверяем время модификации файла
    try:
        mtime = TEST_DB_PATH.stat().st_mtime
        file_age = datetime.now() - datetime.fromtimestamp(mtime)
        
        if file_age > timedelta(minutes=CACHE_TIMEOUT_MINUTES):
            logger.info(
                f"ℹ️ Тестовая БД устарела (возраст: {file_age.total_seconds():.0f} сек, "
                f"лимит: {CACHE_TIMEOUT_MINUTES} мин). Нужно пересоздать."
            )
            return True
        else:
            logger.debug(
                f"✅ Тестовая БД актуальна (возраст: {file_age.total_seconds():.0f} сек). "
                f"Используем существующую."
            )
            return False
    except OSError as e:
        logger.warning(f"⚠️ Не удалось проверить время модификации БД: {e}. Пересоздаем.")
        return True


def copy_production_db_to_test_db(force: bool = False) -> bool:
    """
    Копирует реальную БД в тестовую.
    
    Args:
        force: Если True, копирует даже если тестовая БД существует и актуальна
    
    Returns:
        True если копирование успешно, False в противном случае
    """
    # Проверяем, нужно ли копировать
    if not force and not should_recreate_test_db():
        logger.info(f"✅ Используем существующую тестовую БД: {TEST_DB_PATH}")
        return True
    
    # Проверяем наличие реальной БД
    if not PRODUCTION_DB_PATH.exists():
        logger.warning(
            f"⚠️ Реальная БД не найдена: {PRODUCTION_DB_PATH}. "
            f"Тесты будут использовать пустую БД."
        )
        return False
    
    if not PRODUCTION_DB_PATH.is_file():
        logger.error(f"❌ {PRODUCTION_DB_PATH} существует, но это не файл!")
        return False
    
    try:
        # Получаем размер реальной БД для логирования
        prod_size = PRODUCTION_DB_PATH.stat().st_size
        logger.info(
            f"📦 Копируем реальную БД ({prod_size / 1024:.1f} КБ) "
            f"из {PRODUCTION_DB_PATH} в {TEST_DB_PATH}"
        )
        
        start_time = time.time()
        
        # Копируем БД
        shutil.copy2(PRODUCTION_DB_PATH, TEST_DB_PATH)
        
        copy_time = time.time() - start_time
        
        # Проверяем целостность скопированной БД
        try:
            test_conn = sqlite3.connect(str(TEST_DB_PATH), timeout=5)
            cursor = test_conn.cursor()
            cursor.execute("PRAGMA integrity_check")
            integrity_result = cursor.fetchone()
            test_conn.close()
            
            if integrity_result and integrity_result[0] == "ok":
                test_size = TEST_DB_PATH.stat().st_size
                logger.info(
                    f"✅ БД успешно скопирована за {copy_time:.2f} сек. "
                    f"Размер: {test_size / 1024:.1f} КБ. Целостность: OK"
                )
                return True
            else:
                logger.error(
                    f"❌ Скопированная БД не прошла проверку целостности: {integrity_result}"
                )
                TEST_DB_PATH.unlink(missing_ok=True)
                return False
        except sqlite3.Error as e:
            logger.error(f"❌ Ошибка при проверке целостности скопированной БД: {e}")
            TEST_DB_PATH.unlink(missing_ok=True)
            return False
            
    except (OSError, PermissionError, shutil.Error) as e:
        logger.error(f"❌ Не удалось скопировать реальную БД: {e}")
        return False


def copy_templates_from_production_db(temp_db_path: Path):
    """
    Копирует все шаблоны из боевой БД users.db в тестовую БД
    
    Эта функция используется в тестах для проверки реальных шаблонов из боевой БД,
    что позволяет тестировать валидацию на актуальных данных.
    
    Args:
        temp_db_path: Путь к тестовой БД (Path объект)
    
    Returns:
        int: Количество скопированных шаблонов (0 если боевая БД не найдена)
    """
    import logging
    
    logger = logging.getLogger(__name__)
    
    # Определяем путь к боевой БД
    project_root = Path(__file__).parent.parent
    production_db = project_root / "users.db"
    
    # Проверяем, существует ли боевая БД
    if not production_db.exists():
        logger.debug(f"Боевая БД не найдена: {production_db}. Тесты будут использовать тестовые данные.")
        return 0
    
    try:
        # Подключаемся к боевой БД
        prod_conn = sqlite3.connect(str(production_db))
        prod_conn.row_factory = sqlite3.Row
        prod_cursor = prod_conn.cursor()
        
        # Получаем все шаблоны из боевой БД
        prod_cursor.execute("""
            SELECT template_key, category, provision_mode, template_text, 
                   description, variables, is_active, created_at, updated_at
            FROM message_templates
        """)
        templates = prod_cursor.fetchall()
        prod_conn.close()
        
        if not templates:
            logger.debug("В боевой БД нет шаблонов для копирования.")
            return 0
        
        # Подключаемся к тестовой БД и вставляем шаблоны
        test_conn = sqlite3.connect(str(temp_db_path))
        test_cursor = test_conn.cursor()
        
        # Используем транзакцию для эффективности
        test_cursor.execute("BEGIN TRANSACTION")
        
        copied_count = 0
        try:
            for template in templates:
                try:
                    test_cursor.execute("""
                        INSERT OR REPLACE INTO message_templates 
                        (template_key, category, provision_mode, template_text, 
                         description, variables, is_active, created_at, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        template['template_key'],
                        template['category'],
                        template['provision_mode'],
                        template['template_text'],
                        template['description'],
                        template['variables'],
                        template['is_active'],
                        template['created_at'],
                        template['updated_at']
                    ))
                    copied_count += 1
                except sqlite3.Error as e:
                    logger.warning(f"Ошибка при копировании шаблона {template['template_key']}: {e}")
                    # Продолжаем копирование остальных шаблонов
            
            test_cursor.execute("COMMIT")
        except Exception as e:
            # Откатываем транзакцию при ошибке
            test_cursor.execute("ROLLBACK")
            logger.warning(f"Ошибка при копировании шаблонов, транзакция откачена: {e}")
        
        test_conn.close()
        
        logger.info(f"Скопировано {copied_count} шаблонов из боевой БД в тестовую.")
        return copied_count
        
    except sqlite3.Error as e:
        # Логируем ошибку, но не прерываем выполнение тестов
        logger.warning(f"Не удалось скопировать шаблоны из боевой БД: {e}")
        return 0
    except Exception as e:
        logger.warning(f"Неожиданная ошибка при копировании шаблонов: {e}")
        return 0


@pytest.fixture(scope="session")
def test_db_session():
    """
    Session-scope фикстура для копирования реальной БД в тестовую.
    
    Выполняется один раз при запуске всех тестов.
    Копирует реальную БД users.db в temp_db.db, заменяя существующую.
    """
    logger.info("=" * 60)
    logger.info("🚀 Начало сессии тестов - подготовка тестовой БД")
    logger.info("=" * 60)
    
    # Принудительно копируем БД (заменяем существующую)
    success = copy_production_db_to_test_db(force=True)
    
    if success:
        logger.info(f"✅ Тестовая БД готова: {TEST_DB_PATH}")
    else:
        logger.warning(
            f"⚠️ Не удалось скопировать реальную БД. "
            f"Тесты будут использовать пустую БД (если она будет создана)."
        )
    
    yield TEST_DB_PATH
    
    # После завершения всех тестов можно оставить БД для следующего запуска
    # или удалить её (раскомментируйте следующую строку, если нужно удалять)
    # TEST_DB_PATH.unlink(missing_ok=True)
    # logger.info(f"🧹 Тестовая БД удалена: {TEST_DB_PATH}")


@pytest.fixture
def temp_db(test_db_session, monkeypatch):
    """
    Создает временную БД для тестов.
    
    ВАЖНО: Всегда создает новую БД с правильной структурой через initialize_db(),
    чтобы избежать проблем с несовместимыми структурами из production БД.
    """
    # Сохраняем оригинальный DB_FILE
    original_db_file = database.DB_FILE
    
    # Патчим DB_FILE для использования тестовой БД
    monkeypatch.setattr(database, 'DB_FILE', TEST_DB_PATH)
    
    # ВАЖНО: Всегда удаляем старую БД перед созданием новой
    # Это гарантирует, что БД создается с правильной структурой
    if TEST_DB_PATH.exists():
        try:
            # Закрываем все возможные соединения с БД перед удалением
            import sqlite3
            import time
            max_attempts = 5
            for attempt in range(max_attempts):
                try:
                    # Пытаемся подключиться и закрыть все соединения
                    conn = sqlite3.connect(str(TEST_DB_PATH), timeout=1)
                    conn.close()
                    break
                except sqlite3.OperationalError:
                    if attempt < max_attempts - 1:
                        time.sleep(0.1)
                        continue
                    else:
                        logger.warning(f"⚠️ Не удалось закрыть соединения с БД, продолжаем удаление...")
            
            TEST_DB_PATH.unlink()
            # Небольшая задержка, чтобы система освободила файл
            time.sleep(0.1)
            logger.debug(f"🗑️ Удалена старая тестовая БД: {TEST_DB_PATH}")
        except Exception as e:
            logger.warning(f"⚠️ Не удалось удалить старую БД: {e}")
            # Если не удалось удалить, пытаемся продолжить - возможно, БД уже правильная
    
    # ВАЖНО: Инициализируем БД после патчинга DB_FILE
    # Это создаст БД с правильной структурой через initialize_db()
    max_init_attempts = 3
    for attempt in range(max_init_attempts):
        try:
            database.initialize_db()
            logger.debug(f"✅ БД инициализирована с правильной структурой: {TEST_DB_PATH}")
            break
        except Exception as e:
            error_str = str(e).lower()
            # Если ошибка связана с правами доступа или readonly, пытаемся исправить
            if "readonly" in error_str or "permission" in error_str or "no such table" in error_str:
                if attempt < max_init_attempts - 1:
                    logger.warning(f"⚠️ Проблема с БД (попытка {attempt + 1}/{max_init_attempts}): {e}. Пересоздаем...")
                    # Удаляем БД и создаем заново
                    try:
                        if TEST_DB_PATH.exists():
                            TEST_DB_PATH.unlink()
                    except Exception:
                        pass
                    continue
                else:
                    logger.error(f"❌ Не удалось исправить проблему с БД после {max_init_attempts} попыток: {e}")
                    raise
            else:
                logger.error(f"❌ Ошибка при инициализации БД: {e}")
                raise
    
    yield TEST_DB_PATH
    
    # Восстанавливаем оригинальный DB_FILE
    monkeypatch.setattr(database, 'DB_FILE', original_db_file)
    
    # НЕ удаляем БД - она будет использоваться другими тестами в рамках сессии


def _create_empty_db_structure(db_path: Path):
    """
    Создает пустую БД с полной структурой таблиц.
    Используется как fallback, если реальная БД не найдена.
    """
    logger.info(f"📝 Создаем пустую БД с полной структурой: {db_path}")
    
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    
    # Таблица users
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            telegram_id INTEGER PRIMARY KEY,
            username TEXT,
            fullname TEXT,
            total_spent REAL DEFAULT 0,
            total_months INTEGER DEFAULT 0,
            trial_used INTEGER DEFAULT 0,
            agreed_to_terms INTEGER DEFAULT 0,
            agreed_to_documents INTEGER DEFAULT 0,
            subscription_status TEXT DEFAULT 'not_checked',
            registration_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_banned INTEGER DEFAULT 0,
            balance REAL DEFAULT 0,
            auto_renewal_enabled INTEGER DEFAULT 1,
            user_id INTEGER,
            referred_by INTEGER,
            referral_balance REAL DEFAULT 0,
            referral_balance_all REAL DEFAULT 0,
            group_id INTEGER,
            keys_count INTEGER DEFAULT 0,
            trial_days_given INTEGER DEFAULT 0,
            trial_reuses_count INTEGER DEFAULT 0
        )
    ''')
    
    # Таблица migration_history
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS migration_history (
            migration_id TEXT PRIMARY KEY,
            applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Таблица bot_settings
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS bot_settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    ''')
    
    # Таблица backup_settings
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS backup_settings (
            key TEXT PRIMARY KEY,
            value TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Таблица promo_code_usage
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS promo_code_usage (
            usage_id INTEGER PRIMARY KEY AUTOINCREMENT,
            promo_id INTEGER NOT NULL,
            user_id INTEGER,
            bot TEXT NOT NULL,
            plan_id INTEGER,
            discount_amount REAL DEFAULT 0,
            discount_percent REAL DEFAULT 0,
            discount_bonus REAL DEFAULT 0,
            metadata TEXT,
            used_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            status TEXT DEFAULT 'applied'
        )
    ''')
    
    # Таблица promo_codes
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS promo_codes (
            promo_id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT NOT NULL UNIQUE,
            bot TEXT NOT NULL,
            vpn_plan_id TEXT,
            tariff_code TEXT,
            discount_amount REAL DEFAULT 0,
            discount_percent REAL DEFAULT 0,
            discount_bonus REAL DEFAULT 0,
            usage_limit_per_bot INTEGER DEFAULT 1,
            is_active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            burn_after_value INTEGER,
            burn_after_unit TEXT,
            valid_until TEXT,
            target_group_ids TEXT,
            bot_username TEXT
        )
    ''')
    
    # Таблица user_groups
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_groups (
            group_id INTEGER PRIMARY KEY AUTOINCREMENT,
            group_name TEXT NOT NULL UNIQUE,
            group_code TEXT,
            group_description TEXT,
            is_default BOOLEAN DEFAULT 0,
            created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Создаём группу по умолчанию для тестов
    cursor.execute('''
        INSERT OR IGNORE INTO user_groups (group_name, group_code, is_default)
        VALUES ('default', 'default', 1)
    ''')
    
    # Таблица vpn_keys
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS vpn_keys (
            key_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            host_name TEXT NOT NULL,
            xui_client_uuid TEXT NOT NULL,
            key_email TEXT NOT NULL UNIQUE,
            expiry_date TIMESTAMP,
            created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            protocol TEXT DEFAULT 'vless',
            is_trial INTEGER DEFAULT 0,
            connection_string TEXT,
            plan_name TEXT,
            price REAL,
            status TEXT DEFAULT 'active',
            enabled INTEGER DEFAULT 1,
            subscription TEXT,
            subscription_link TEXT,
            telegram_chat_id INTEGER,
            comment TEXT,
            remaining_seconds INTEGER,
            start_date TIMESTAMP,
            quota_remaining_bytes INTEGER,
            quota_total_gb REAL,
            traffic_down_bytes INTEGER,
            expiry_timestamp_ms INTEGER
        )
    ''')
    
    # Таблица user_tokens (для permanent tokens)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_tokens (
            token TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            key_id INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            last_used_at TEXT,
            access_count INTEGER DEFAULT 0,
            FOREIGN KEY (user_id) REFERENCES users (telegram_id),
            FOREIGN KEY (key_id) REFERENCES vpn_keys (key_id)
        )
    ''')
    
    # Таблица transactions
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS transactions (
            transaction_id INTEGER PRIMARY KEY AUTOINCREMENT,
            payment_id TEXT UNIQUE NOT NULL,
            user_id INTEGER NOT NULL,
            status TEXT NOT NULL,
            amount_rub REAL NOT NULL,
            username TEXT,
            amount_currency REAL,
            currency_name TEXT,
            payment_method TEXT,
            metadata TEXT,
            transaction_hash TEXT,
            payment_link TEXT,
            created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            api_request TEXT,
            api_response TEXT
        )
    ''')
    
    # Таблица plans
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS plans (
            plan_id INTEGER PRIMARY KEY AUTOINCREMENT,
            host_name TEXT NOT NULL,
            plan_name TEXT NOT NULL,
            months INTEGER NOT NULL,
            days INTEGER DEFAULT 0,
            hours INTEGER DEFAULT 0,
            price REAL NOT NULL,
            traffic_gb REAL DEFAULT 0,
            key_provision_mode TEXT DEFAULT 'key',
            display_mode TEXT DEFAULT 'all',
            display_mode_groups TEXT
        )
    ''')
    
    # Таблица xui_hosts
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS xui_hosts (
            host_name TEXT NOT NULL PRIMARY KEY,
            host_url TEXT NOT NULL,
            host_username TEXT NOT NULL,
            host_pass TEXT NOT NULL,
            host_inbound_id INTEGER NOT NULL,
            host_code TEXT
        )
    ''')
    
    # Таблица notifications
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS notifications (
            notification_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            username TEXT,
            type TEXT NOT NULL,
            title TEXT NOT NULL,
            message TEXT NOT NULL,
            status TEXT NOT NULL,
            meta TEXT,
            key_id INTEGER,
            marker_hours INTEGER,
            created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Таблица message_templates (справочник текстов бота)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS message_templates (
            template_id INTEGER PRIMARY KEY AUTOINCREMENT,
            template_key TEXT UNIQUE NOT NULL,
            category TEXT NOT NULL,
            provision_mode TEXT,
            template_text TEXT NOT NULL,
            description TEXT,
            variables TEXT,
            is_active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Создаем индексы
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_user_tokens_user_id ON user_tokens(user_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_user_tokens_key_id ON user_tokens(key_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_vpn_keys_user_id ON vpn_keys(user_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_vpn_keys_email ON vpn_keys(key_email)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_template_key ON message_templates(template_key)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_category ON message_templates(category)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_provision_mode ON message_templates(provision_mode)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_is_active ON message_templates(is_active)')
    
    conn.commit()
    conn.close()
    
    logger.info(f"✅ Пустая БД создана: {db_path}")


@pytest.fixture
def mock_bot():
    """Мок для aiogram.Bot"""
    from unittest.mock import AsyncMock, MagicMock
    
    bot = MagicMock()
    bot.send_message = AsyncMock()
    bot.edit_message_text = AsyncMock()
    bot.answer_callback_query = AsyncMock()
    bot.delete_message = AsyncMock()
    
    return bot


@pytest.fixture
def mock_xui_api():
    """Мок для py3xui.Api"""
    from unittest.mock import MagicMock, AsyncMock
    
    api = MagicMock()
    api.login = MagicMock()
    
    # Мок для inbound
    mock_inbound = MagicMock()
    mock_inbound.id = 1
    mock_inbound.port = 443
    mock_inbound.settings = MagicMock()
    mock_inbound.settings.clients = []
    
    # Моки для методов API
    api.inbound.get_list = MagicMock(return_value=[mock_inbound])
    api.inbound.get_by_id = MagicMock(return_value=mock_inbound)
    api.inbound.update = MagicMock()
    api.client.update = MagicMock()
    api.client.delete = MagicMock(return_value=True)  # Возвращаем True для успешного удаления
    
    return api


@pytest.fixture
def expired_callback_query():
    """Фикстура для создания мока CallbackQuery с эмуляцией устаревшего callback query"""
    from unittest.mock import MagicMock, AsyncMock
    from aiogram.types import CallbackQuery, User, Message, Chat
    from aiogram.exceptions import TelegramBadRequest
    
    callback = MagicMock(spec=CallbackQuery)
    callback.data = "manage_keys"
    callback.from_user = MagicMock(spec=User)
    callback.from_user.id = 123456
    callback.message = MagicMock(spec=Message)
    callback.message.edit_text = AsyncMock()
    callback.message.answer = AsyncMock()
    callback.message.delete = AsyncMock()
    callback.message.chat = MagicMock(spec=Chat)
    callback.message.chat.id = 123456
    
    # Настраиваем answer() чтобы выбрасывать TelegramBadRequest для устаревших queries
    async def expired_answer(*args, **kwargs):
        raise TelegramBadRequest(
            method="answerCallbackQuery",
            message="Bad Request: query is too old and response timeout expired or query ID is invalid"
        )
    
    callback.answer = AsyncMock(side_effect=expired_answer)
    
    return callback


@pytest.fixture
def sample_host():
    """Тестовый хост для БД"""
    return {
        'host_name': 'test-host',
        'host_url': 'https://test.example.com:8443/configpanel',
        'host_username': 'admin',
        'host_pass': 'password',
        'host_inbound_id': 1,
        'host_code': 'test-code'
    }


@pytest.fixture
def mock_yookassa():
    """Мок для YooKassa Payment"""
    from unittest.mock import MagicMock
    
    payment = MagicMock()
    payment.create = MagicMock(return_value={
        'id': 'test_payment_id',
        'status': 'pending',
        'confirmation': {
            'confirmation_url': 'https://yookassa.ru/test'
        }
    })
    
    return payment


@pytest.fixture
def mock_cryptobot():
    """Мок для CryptoBot API"""
    from unittest.mock import MagicMock, AsyncMock
    
    api = MagicMock()
    api.create_invoice = AsyncMock(return_value={
        'result': {
            'invoice_id': 'test_invoice_id',
            'pay_url': 'https://crypt.bot/test',
            'status': 'active'
        }
    })
    api.get_invoices = AsyncMock(return_value={
        'result': {
            'items': [{
                'invoice_id': 'test_invoice_id',
                'status': 'paid',
                'amount': '100.0'
            }]
        }
    })
    
    return api


@pytest.fixture
def mock_ton_connect():
    """Мок для TON Connect"""
    from unittest.mock import MagicMock, AsyncMock
    
    connector = MagicMock()
    connector.connected = False
    connector.account = MagicMock()
    connector.account.address = 'test_address'
    connector.send_transaction = AsyncMock(return_value={
        'boc': 'test_boc',
        'transaction': {
            'hash': 'test_hash'
        }
    })
    connector.connect = AsyncMock()
    connector.disconnect = AsyncMock()
    
    return connector


@pytest.fixture
def mock_heleket():
    """Мок для Heleket API"""
    from unittest.mock import MagicMock, AsyncMock
    
    api = MagicMock()
    api.create_invoice = AsyncMock(return_value={
        'id': 'test_invoice_id',
        'pay_url': 'https://heleket.com/test',
        'status': 'pending'
    })
    api.get_invoice = AsyncMock(return_value={
        'id': 'test_invoice_id',
        'status': 'paid',
        'amount': 100.0
    })
    
    return api


@pytest.fixture
def sample_plan():
    """Тестовый план для БД"""
    return {
        'plan_id': 1,
        'host_name': 'test-host',
        'plan_name': 'Test Plan',
        'months': 1,
        'days': 0,
        'hours': 0,
        'price': 100.0,
        'traffic_gb': 0.0
    }


@pytest.fixture
def sample_promo_code():
    """Тестовый промокод для БД"""
    return {
        'promo_id': 1,
        'code': 'TESTPROMO',
        'bot': 'test_bot',
        'discount_amount': 10.0,
        'discount_percent': 0.0,
        'discount_bonus': 0.0,
        'is_active': 1,
        'usage_limit_per_bot': 1
    }


@pytest.fixture
def admin_credentials():
    """Возвращает учетные данные администратора из переменных окружения"""
    username = os.getenv('PANEL_LOGIN', 'test_admin')
    password = os.getenv('PANEL_PASSWORD', '')
    
    if not password:
        # Диагностика: проверяем, загрузилась ли переменная
        env_path = project_root / ".env"
        if env_path.exists():
            logger.warning(
                f"⚠️ .env файл найден: {env_path}, но PANEL_PASSWORD не загружен. "
                f"Проверьте формат переменной в .env (без кавычек, без пробелов вокруг =)"
            )
            # Пытаемся прочитать файл для диагностики
            try:
                with open(env_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    if 'PANEL_PASSWORD' in content:
                        logger.warning("⚠️ PANEL_PASSWORD найден в .env, но не загружен. Возможна проблема с форматом.")
                    else:
                        logger.warning("⚠️ PANEL_PASSWORD отсутствует в .env файле")
            except Exception as e:
                logger.warning(f"⚠️ Не удалось прочитать .env файл для диагностики: {e}")
        else:
            logger.warning(f"⚠️ .env файл не найден: {env_path}")
        pytest.skip("PANEL_PASSWORD не установлен в .env файле")
    
    return {
        'username': username,
        'password': password
    }


@pytest.fixture
def authenticated_client(temp_db, admin_credentials):
    """Фикстура для создания аутентифицированного Flask клиента"""
    from src.shop_bot.webhook_server.app import create_webhook_app
    from unittest.mock import MagicMock, patch
    
    mock_bot_controller = MagicMock()
    app = create_webhook_app(mock_bot_controller)
    client = app.test_client()
    
    # Входим в систему с учетными данными из .env
    with patch('src.shop_bot.webhook_server.app.verify_admin_credentials', return_value=True):
        client.post('/login', data=admin_credentials, follow_redirects=True)
    
    return client