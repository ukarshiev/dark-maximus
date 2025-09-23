# Обзор модулей {{PROJECT_NAME}}

## Оглавление
- [Обзор архитектуры модулей](#обзор-архитектуры-модулей)
- [Основные модули](#основные-модули)
- [Модули интеграции](#модули-интеграции)
- [Служебные модули](#служебные-модули)
- [Веб-модули](#веб-модули)
- [Модули данных](#модули-данных)
- [Зависимости между модулями](#зависимости-между-модулями)
- [Конфигурация модулей](#конфигурация-модулей)
- [Тестирование модулей](#тестирование-модулей)

## Обзор архитектуры модулей

Проект {{PROJECT_NAME}} построен по модульной архитектуре, где каждый модуль отвечает за определенную функциональность. Модули организованы в пакеты и следуют принципам:

- **Единственная ответственность** - Каждый модуль решает одну задачу
- **Слабая связанность** - Модули взаимодействуют через четко определенные интерфейсы
- **Высокая сплоченность** - Внутренние компоненты модуля тесно связаны
- **Инверсия зависимостей** - Модули зависят от абстракций, а не от конкретных реализаций

### Структура модулей
```
src/shop_bot/
├── __init__.py                 # Инициализация пакета
├── __main__.py                 # Точка входа
├── config.py                   # Конфигурация
├── bot_controller.py           # Контроллер бота
├── ton_monitor.py              # Мониторинг TON
├── bot/                        # Telegram Bot модули
│   ├── __init__.py
│   ├── handlers.py             # Обработчики команд
│   ├── keyboards.py            # Клавиатуры
│   └── middlewares.py          # Промежуточное ПО
├── data_manager/               # Управление данными
│   ├── __init__.py
│   ├── database.py             # Работа с БД
│   └── scheduler.py            # Планировщик
├── modules/                    # Модули интеграции
│   ├── __init__.py
│   └── xui_api.py              # API 3x-ui
└── webhook_server/             # Веб-панель
    ├── __init__.py
    ├── app.py                  # Flask приложение
    ├── templates/              # HTML шаблоны
    └── static/                 # Статические файлы
```

## Основные модули

### 1. config.py - Конфигурация системы
**Назначение**: Централизованное управление конфигурацией приложения.

**Основные функции**:
- Загрузка настроек из переменных окружения
- Валидация конфигурации
- Предоставление настроек другим модулям

**Ключевые компоненты**:
```python
class Config:
    """Основной класс конфигурации."""
    
    # Telegram Bot
    TELEGRAM_BOT_TOKEN: str
    TELEGRAM_BOT_USERNAME: str
    ADMIN_TELEGRAM_ID: int
    
    # 3x-ui Panel
    XUI_PANEL_URL: str
    XUI_PANEL_USERNAME: str
    XUI_PANEL_PASSWORD: str
    
    # Платежные системы
    YOOKASSA_SHOP_ID: str
    YOOKASSA_SECRET_KEY: str
    CRYPTOBOT_TOKEN: str
    TON_WALLET_ADDRESS: str
    TONAPI_KEY: str
    
    # База данных
    DATABASE_URL: str
    
    # Настройки приложения
    DEBUG: bool
    LOG_LEVEL: str
```

**Использование**:
```python
from shop_bot.config import settings

# Получение токена бота
bot_token = settings.TELEGRAM_BOT_TOKEN

# Проверка режима отладки
if settings.DEBUG:
    print("Приложение в режиме отладки")
```

### 2. bot_controller.py - Контроллер бота
**Назначение**: Главный контроллер для управления Telegram ботом.

**Основные функции**:
- Инициализация бота и диспетчера
- Регистрация обработчиков и middleware
- Запуск и остановка бота
- Управление жизненным циклом

**Ключевые компоненты**:
```python
class BotController:
    """Контроллер Telegram бота."""
    
    def __init__(self, config: Config):
        self.config = config
        self.bot = Bot(token=config.TELEGRAM_BOT_TOKEN)
        self.dp = Dispatcher()
        self._setup_handlers()
        self._setup_middlewares()
    
    async def start(self):
        """Запуск бота."""
        await self.dp.start_polling(self.bot)
    
    async def stop(self):
        """Остановка бота."""
        await self.bot.session.close()
    
    def _setup_handlers(self):
        """Настройка обработчиков."""
        # Регистрация обработчиков команд
        pass
    
    def _setup_middlewares(self):
        """Настройка middleware."""
        # Регистрация middleware
        pass
```

### 3. ton_monitor.py - Мониторинг TON
**Назначение**: Мониторинг TON-транзакций и их обработка.

**Основные функции**:
- Отслеживание входящих TON-транзакций
- Проверка соответствия сумм платежам
- Автоматическое завершение транзакций
- Уведомления о статусе платежей

**Ключевые компоненты**:
```python
class TONMonitor:
    """Мониторинг TON-транзакций."""
    
    def __init__(self, tonapi_key: str, wallet_address: str):
        self.tonapi_key = tonapi_key
        self.wallet_address = wallet_address
        self.is_running = False
    
    async def start_monitoring(self):
        """Запуск мониторинга."""
        self.is_running = True
        while self.is_running:
            await self._check_transactions()
            await asyncio.sleep(30)  # Проверка каждые 30 секунд
    
    async def _check_transactions(self):
        """Проверка новых транзакций."""
        # Получение последних транзакций
        # Сопоставление с ожидающими платежами
        # Завершение найденных транзакций
        pass
```

## Модули интеграции

### 1. modules/xui_api.py - API 3x-ui панели
**Назначение**: Интеграция с панелью управления 3x-ui для управления VPN серверами.

**Основные функции**:
- Создание и удаление VPN клиентов
- Получение статистики использования
- Управление настройками серверов
- Синхронизация данных

**Ключевые компоненты**:
```python
class XUIApiClient:
    """Клиент для работы с 3x-ui API."""
    
    def __init__(self, panel_url: str, username: str, password: str):
        self.panel_url = panel_url
        self.username = username
        self.password = password
        self.session = None
    
    async def authenticate(self) -> bool:
        """Аутентификация в панели."""
        # Логин в панель управления
        pass
    
    async def create_client(self, host_name: str, plan_data: dict) -> dict:
        """Создание VPN клиента."""
        # Создание клиента на сервере
        pass
    
    async def delete_client(self, host_name: str, client_uuid: str) -> bool:
        """Удаление VPN клиента."""
        # Удаление клиента с сервера
        pass
    
    async def get_client_stats(self, host_name: str, client_uuid: str) -> dict:
        """Получение статистики клиента."""
        # Получение данных об использовании
        pass
    
    async def update_client_expiry(self, host_name: str, client_uuid: str, 
                                  expiry_timestamp: int) -> bool:
        """Обновление времени истечения клиента."""
        # Продление или изменение срока действия
        pass
```

**Использование**:
```python
from shop_bot.modules.xui_api import XUIApiClient

# Создание клиента
xui_client = XUIApiClient(
    panel_url="https://panel.example.com",
    username="admin",
    password="password"
)

# Аутентификация
await xui_client.authenticate()

# Создание VPN клиента
client_data = await xui_client.create_client(
    host_name="server1",
    plan_data={
        "email": "user@example.com",
        "expiry_time": 1640995200000,
        "protocol": "vless"
    }
)
```

### 2. modules/payment_processors.py - Платежные системы
**Назначение**: Интеграция с различными платежными системами.

**Поддерживаемые системы**:
- YooKassa (банковские карты, СБП)
- CryptoBot (криптовалюты)
- TON Connect (TON блокчейн)
- Telegram Stars (внутриплатформенные платежи)
- Heleket (альтернативные криптовалюты)

**Ключевые компоненты**:
```python
class PaymentProcessor(ABC):
    """Базовый класс для платежных процессоров."""
    
    @abstractmethod
    async def create_payment(self, amount: float, currency: str, 
                           metadata: dict) -> dict:
        """Создание платежа."""
        pass
    
    @abstractmethod
    async def verify_payment(self, payment_id: str) -> dict:
        """Проверка статуса платежа."""
        pass

class YooKassaProcessor(PaymentProcessor):
    """Процессор YooKassa."""
    
    def __init__(self, shop_id: str, secret_key: str):
        self.shop_id = shop_id
        self.secret_key = secret_key
        self.client = Client(shop_id, secret_key)
    
    async def create_payment(self, amount: float, currency: str, 
                           metadata: dict) -> dict:
        """Создание платежа через YooKassa."""
        payment = Payment.create({
            "amount": {"value": str(amount), "currency": currency},
            "confirmation": {"type": "redirect"},
            "metadata": metadata
        })
        return {
            "payment_id": payment.id,
            "payment_url": payment.confirmation.confirmation_url,
            "status": payment.status
        }

class CryptoBotProcessor(PaymentProcessor):
    """Процессор CryptoBot."""
    
    def __init__(self, token: str):
        self.token = token
        self.api_url = f"https://pay.crypt.bot/api/{token}"
    
    async def create_payment(self, amount: float, currency: str, 
                           metadata: dict) -> dict:
        """Создание платежа через CryptoBot."""
        # Реализация создания платежа
        pass
```

## Служебные модули

### 1. data_manager/database.py - Работа с базой данных
**Назначение**: Централизованная работа с базой данных SQLite.

**Основные функции**:
- CRUD операции для всех сущностей
- Миграции схемы базы данных
- Оптимизированные запросы
- Транзакционная безопасность

**Ключевые компоненты**:
```python
class DatabaseManager:
    """Менеджер базы данных."""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._init_database()
    
    def _init_database(self):
        """Инициализация базы данных."""
        # Создание таблиц
        # Запуск миграций
        pass
    
    # Пользователи
    async def create_user(self, user_data: dict) -> int:
        """Создание пользователя."""
        pass
    
    async def get_user(self, user_id: int) -> dict:
        """Получение пользователя."""
        pass
    
    async def update_user_balance(self, user_id: int, amount: float) -> bool:
        """Обновление баланса пользователя."""
        pass
    
    # VPN ключи
    async def create_vpn_key(self, key_data: dict) -> int:
        """Создание VPN ключа."""
        pass
    
    async def get_user_keys(self, user_id: int) -> list:
        """Получение ключей пользователя."""
        pass
    
    async def update_key_expiry(self, key_id: int, expiry_date: datetime) -> bool:
        """Обновление времени истечения ключа."""
        pass
    
    # Транзакции
    async def create_transaction(self, transaction_data: dict) -> int:
        """Создание транзакции."""
        pass
    
    async def update_transaction_status(self, payment_id: str, status: str) -> bool:
        """Обновление статуса транзакции."""
        pass
```

### 2. data_manager/scheduler.py - Планировщик задач
**Назначение**: Выполнение периодических задач и уведомлений.

**Основные функции**:
- Проверка истекающих ключей
- Отправка уведомлений
- Очистка старых данных
- Синхронизация с внешними сервисами

**Ключевые компоненты**:
```python
class TaskScheduler:
    """Планировщик задач."""
    
    def __init__(self, database_manager: DatabaseManager):
        self.db = database_manager
        self.tasks = []
        self.is_running = False
    
    async def start(self):
        """Запуск планировщика."""
        self.is_running = True
        await self._run_tasks()
    
    async def _run_tasks(self):
        """Выполнение задач."""
        while self.is_running:
            await self._check_expiring_keys()
            await self._send_notifications()
            await self._cleanup_old_data()
            await asyncio.sleep(300)  # Каждые 5 минут
    
    async def _check_expiring_keys(self):
        """Проверка истекающих ключей."""
        # Поиск ключей, истекающих в ближайшие 24 часа
        # Отправка уведомлений пользователям
        pass
    
    async def _send_notifications(self):
        """Отправка уведомлений."""
        # Получение очереди уведомлений
        # Отправка через Telegram Bot API
        pass
    
    async def _cleanup_old_data(self):
        """Очистка старых данных."""
        # Удаление старых логов
        # Очистка завершенных транзакций
        pass
```

## Веб-модули

### 1. webhook_server/app.py - Flask приложение
**Назначение**: Веб-панель администратора и API для внешних сервисов.

**Основные функции**:
- Административная панель
- API для webhook'ов платежных систем
- Статистика и аналитика
- Управление пользователями и серверами

**Ключевые компоненты**:
```python
from flask import Flask, render_template, request, jsonify
from shop_bot.data_manager.database import DatabaseManager

app = Flask(__name__)

class WebhookServer:
    """Веб-сервер для административной панели."""
    
    def __init__(self, database_manager: DatabaseManager):
        self.db = database_manager
        self.app = Flask(__name__)
        self._setup_routes()
    
    def _setup_routes(self):
        """Настройка маршрутов."""
        
        @self.app.route('/')
        def dashboard():
            """Главная панель."""
            stats = self.db.get_system_stats()
            return render_template('dashboard.html', stats=stats)
        
        @self.app.route('/users')
        def users():
            """Управление пользователями."""
            users = self.db.get_all_users()
            return render_template('users.html', users=users)
        
        @self.app.route('/api/webhook/yookassa', methods=['POST'])
        def yookassa_webhook():
            """Webhook для YooKassa."""
            data = request.json
            # Обработка уведомления о платеже
            return jsonify({"status": "ok"})
        
        @self.app.route('/api/webhook/cryptobot', methods=['POST'])
        def cryptobot_webhook():
            """Webhook для CryptoBot."""
            data = request.json
            # Обработка уведомления о платеже
            return jsonify({"status": "ok"})
```

### 2. webhook_server/templates/ - HTML шаблоны
**Назначение**: Шаблоны для веб-интерфейса администратора.

**Основные шаблоны**:
- `base.html` - Базовый шаблон
- `dashboard.html` - Главная панель
- `users.html` - Управление пользователями
- `keys.html` - Управление ключами
- `transactions.html` - История транзакций
- `settings.html` - Настройки системы

**Пример базового шаблона**:
```html
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{PROJECT_NAME}} - Админ панель</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="{{ url_for('static', filename='css/style.css') }}" rel="stylesheet">
</head>
<body>
    <nav class="navbar navbar-expand-lg navbar-dark bg-dark">
        <div class="container">
            <a class="navbar-brand" href="{{ url_for('dashboard') }}">{{PROJECT_NAME}}</a>
            <!-- Навигационное меню -->
        </div>
    </nav>
    
    <main class="container mt-4">
        {% block content %}{% endblock %}
    </main>
    
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js"></script>
    <script src="{{ url_for('static', filename='js/script.js') }}"></script>
</body>
</html>
```

### 3. webhook_server/static/ - Статические файлы
**Назначение**: CSS, JavaScript и изображения для веб-интерфейса.

**Структура**:
```
static/
├── css/
│   └── style.css          # Основные стили
├── js/
│   └── script.js          # JavaScript функциональность
├── img/
│   ├── logo.png           # Логотип
│   └── burger.png         # Иконка меню
└── logo.svg               # SVG логотип
```

## Модули данных

### 1. bot/handlers.py - Обработчики команд
**Назначение**: Обработка команд и сообщений от пользователей Telegram.

**Основные обработчики**:
- Команды бота (`/start`, `/help`, `/profile`)
- Callback-запросы от inline клавиатур
- Текстовые сообщения в различных состояниях
- Обработка платежей и webhook'ов

**Ключевые компоненты**:
```python
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

router = Router()

@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    """Обработка команды /start."""
    # Регистрация пользователя
    # Показ главного меню
    pass

@router.callback_query(F.data.startswith("plan_"))
async def handle_plan_selection(callback: CallbackQuery, state: FSMContext):
    """Обработка выбора тарифа."""
    # Получение данных тарифа
    # Переход к выбору способа оплаты
    pass

@router.callback_query(F.data.startswith("payment_"))
async def handle_payment_selection(callback: CallbackQuery, state: FSMContext):
    """Обработка выбора способа оплаты."""
    # Создание платежа
    # Показ инструкций по оплате
    pass
```

### 2. bot/keyboards.py - Клавиатуры
**Назначение**: Создание inline и reply клавиатур для интерфейса бота.

**Основные клавиатуры**:
- Главное меню
- Выбор тарифов
- Способы оплаты
- Управление профилем
- Административные функции

**Ключевые компоненты**:
```python
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup

def create_main_menu_keyboard() -> InlineKeyboardMarkup:
    """Создание главного меню."""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🛒 Купить ключ", callback_data="buy_key"),
            InlineKeyboardButton(text="👤 Мой профиль", callback_data="profile")
        ],
        [
            InlineKeyboardButton(text="🔑 Мои ключи", callback_data="my_keys"),
            InlineKeyboardButton(text="💰 Баланс", callback_data="balance")
        ]
    ])
    return keyboard

def create_plans_keyboard(plans: list) -> InlineKeyboardMarkup:
    """Создание клавиатуры тарифов."""
    keyboard_buttons = []
    for plan in plans:
        button_text = f"{plan['plan_name']} - {plan['price']} RUB"
        callback_data = f"plan_{plan['plan_id']}"
        keyboard_buttons.append([
            InlineKeyboardButton(text=button_text, callback_data=callback_data)
        ])
    
    keyboard_buttons.append([
        InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_main")
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
```

### 3. bot/middlewares.py - Промежуточное ПО
**Назначение**: Middleware для обработки запросов и добавления дополнительной функциональности.

**Основные middleware**:
- Аутентификация пользователей
- Логирование действий
- Rate limiting
- Валидация данных

**Ключевые компоненты**:
```python
from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery

class AuthMiddleware(BaseMiddleware):
    """Middleware для аутентификации."""
    
    async def __call__(self, handler, event, data):
        user = event.from_user
        if not user:
            return await handler(event, data)
        
        # Проверка блокировки
        if await is_user_banned(user.id):
            await event.answer("❌ Вы заблокированы в системе")
            return
        
        # Регистрация пользователя
        await register_user_if_not_exists(user.id, user.username)
        
        return await handler(event, data)

class LoggingMiddleware(BaseMiddleware):
    """Middleware для логирования."""
    
    async def __call__(self, handler, event, data):
        user = event.from_user
        action = "unknown"
        
        if isinstance(event, Message):
            action = f"message: {event.text[:50]}"
        elif isinstance(event, CallbackQuery):
            action = f"callback: {event.data}"
        
        logger.info(f"User {user.id} ({user.username}): {action}")
        return await handler(event, data)
```

## Зависимости между модулями

### Диаграмма зависимостей
```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   bot_controller│    │  webhook_server │    │   ton_monitor   │
│                 │    │                 │    │                 │
└─────────┬───────┘    └─────────┬───────┘    └─────────┬───────┘
          │                      │                      │
          └──────────────────────┼──────────────────────┘
                                 │
                    ┌─────────────┴─────────────┐
                    │                           │
            ┌───────▼───────┐           ┌───────▼───────┐
            │ data_manager  │           │    modules    │
            │               │           │               │
            │ - database    │           │ - xui_api     │
            │ - scheduler   │           │ - payments    │
            └───────────────┘           └───────────────┘
                    │
            ┌───────▼───────┐
            │    config     │
            │               │
            │ - settings    │
            │ - validation  │
            └───────────────┘
```

### Правила зависимостей
1. **config** - Не зависит ни от кого, используется всеми
2. **data_manager** - Зависит только от config
3. **modules** - Зависят от config и data_manager
4. **bot_controller** - Зависит от всех модулей
5. **webhook_server** - Зависит от data_manager и modules
6. **ton_monitor** - Зависит от data_manager и modules

## Конфигурация модулей

### 1. Инициализация модулей
```python
# main.py
from shop_bot.config import Config
from shop_bot.data_manager.database import DatabaseManager
from shop_bot.modules.xui_api import XUIApiClient
from shop_bot.bot_controller import BotController
from shop_bot.webhook_server.app import WebhookServer

async def main():
    # Загрузка конфигурации
    config = Config()
    
    # Инициализация базы данных
    db_manager = DatabaseManager(config.DATABASE_URL)
    
    # Инициализация модулей интеграции
    xui_client = XUIApiClient(
        config.XUI_PANEL_URL,
        config.XUI_PANEL_USERNAME,
        config.XUI_PANEL_PASSWORD
    )
    
    # Инициализация контроллера бота
    bot_controller = BotController(config, db_manager, xui_client)
    
    # Инициализация веб-сервера
    webhook_server = WebhookServer(config, db_manager)
    
    # Запуск всех сервисов
    await asyncio.gather(
        bot_controller.start(),
        webhook_server.start(),
        ton_monitor.start()
    )
```

### 2. Dependency Injection
```python
class ServiceContainer:
    """Контейнер зависимостей."""
    
    def __init__(self, config: Config):
        self.config = config
        self._services = {}
    
    def get_database_manager(self) -> DatabaseManager:
        """Получение менеджера базы данных."""
        if 'database_manager' not in self._services:
            self._services['database_manager'] = DatabaseManager(self.config.DATABASE_URL)
        return self._services['database_manager']
    
    def get_xui_client(self) -> XUIApiClient:
        """Получение клиента 3x-ui."""
        if 'xui_client' not in self._services:
            self._services['xui_client'] = XUIApiClient(
                self.config.XUI_PANEL_URL,
                self.config.XUI_PANEL_USERNAME,
                self.config.XUI_PANEL_PASSWORD
            )
        return self._services['xui_client']
```

## Тестирование модулей

### 1. Unit тесты
```python
# tests/test_database_manager.py
import pytest
from unittest.mock import Mock, patch
from shop_bot.data_manager.database import DatabaseManager

class TestDatabaseManager:
    def test_create_user(self):
        """Тест создания пользователя."""
        db_manager = DatabaseManager(":memory:")
        
        user_data = {
            "telegram_id": 12345,
            "username": "testuser"
        }
        
        user_id = db_manager.create_user(user_data)
        assert user_id is not None
        
        user = db_manager.get_user(user_id)
        assert user["telegram_id"] == 12345
        assert user["username"] == "testuser"
```

### 2. Интеграционные тесты
```python
# tests/test_payment_flow.py
import pytest
from shop_bot.modules.payment_processors import YooKassaProcessor
from shop_bot.data_manager.database import DatabaseManager

class TestPaymentFlow:
    @pytest.mark.asyncio
    async def test_yookassa_payment_creation(self):
        """Тест создания платежа через YooKassa."""
        processor = YooKassaProcessor("test_shop_id", "test_secret_key")
        
        with patch('yookassa.Payment.create') as mock_create:
            mock_create.return_value = Mock(
                id="test_payment_id",
                confirmation=Mock(confirmation_url="https://example.com/pay"),
                status="pending"
            )
            
            result = await processor.create_payment(
                amount=100.0,
                currency="RUB",
                metadata={"user_id": 12345}
            )
            
            assert result["payment_id"] == "test_payment_id"
            assert result["status"] == "pending"
```

### 3. E2E тесты
```python
# tests/test_bot_commands.py
import pytest
from aiogram.testing import make_request
from shop_bot.bot_controller import BotController

class TestBotCommands:
    @pytest.mark.asyncio
    async def test_start_command(self):
        """Тест команды /start."""
        bot_controller = BotController(test_config)
        
        # Симуляция команды /start
        request = make_request("/start", user_id=12345, username="testuser")
        response = await bot_controller.handle_message(request)
        
        assert response.text.startswith("Добро пожаловать")
        assert response.reply_markup is not None
```

---

*Документация создана {{DATE}}*
*Владелец проекта: {{OWNER}}*
