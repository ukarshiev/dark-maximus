# API диалогов {{PROJECT_NAME}}

## Оглавление
- [Обзор](#обзор)
- [Архитектура диалогов](#архитектура-диалогов)
- [Состояния пользователей](#состояния-пользователей)
- [Обработчики команд](#обработчики-команд)
- [Клавиатуры и интерфейс](#клавиатуры-и-интерфейс)
- [Промежуточное ПО](#промежуточное-по)
- [Система уведомлений](#система-уведомлений)
- [Интеграция с платежами](#интеграция-с-платежами)
- [Обработка ошибок](#обработка-ошибок)
- [Тестирование диалогов](#тестирование-диалогов)

## Обзор

API диалогов {{PROJECT_NAME}} построен на основе aiogram 3.x и обеспечивает полную автоматизацию взаимодействия с пользователями через Telegram. Система поддерживает сложные диалоговые сценарии, обработку платежей, управление VPN-ключами и интеграцию с внешними сервисами.

### Основные компоненты
- **Handlers** - Обработчики команд и сообщений
- **Keyboards** - Клавиатуры и интерфейс
- **Middlewares** - Промежуточное ПО
- **States** - Управление состояниями пользователей
- **Callbacks** - Обработка callback-запросов

## Архитектура диалогов

### Схема взаимодействия
```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Telegram      │    │   Bot Handler   │    │   Middleware    │
│   User          │◄──►│                 │◄──►│                 │
│                 │    │  - Commands     │    │  - Auth         │
│  - Messages     │    │  - Messages     │    │  - Logging      │
│  - Callbacks    │    │  - Callbacks    │    │  - Rate Limit   │
│  - Payments     │    │  - States       │    │  - Validation   │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                │
                                ▼
                       ┌─────────────────┐
                       │   Business      │
                       │   Logic         │
                       │                 │
                       │  - Database     │
                       │  - Payments     │
                       │  - VPN Keys     │
                       │  - Notifications│
                       └─────────────────┘
```

### Принципы дизайна
1. **Разделение ответственности** - Каждый handler отвечает за конкретную функцию
2. **Состояние-ориентированность** - Диалоги управляются через состояния
3. **Модульность** - Легко добавлять новые команды и функции
4. **Обработка ошибок** - Graceful handling всех исключений
5. **Логирование** - Полное отслеживание действий пользователей

## Состояния пользователей

### Основные состояния
```python
from aiogram.fsm.state import State, StatesGroup

class MainMenu(StatesGroup):
    """Главное меню пользователя."""
    main = State()

class KeyPurchase(StatesGroup):
    """Процесс покупки ключа."""
    choose_plan = State()
    choose_payment = State()
    processing_payment = State()
    payment_success = State()

class ProfileManagement(StatesGroup):
    """Управление профилем."""
    view_profile = State()
    view_keys = State()
    view_transactions = State()

class SupportDialog(StatesGroup):
    """Диалог с поддержкой."""
    waiting_message = State()
    in_support = State()

class AdminPanel(StatesGroup):
    """Административная панель."""
    main = State()
    user_management = State()
    server_management = State()
    analytics = State()
```

### Управление состояниями
```python
from aiogram.fsm.context import FSMContext

async def start_purchase_flow(message: Message, state: FSMContext):
    """Начало процесса покупки ключа."""
    await state.set_state(KeyPurchase.choose_plan)
    await show_plans_keyboard(message)

async def handle_plan_selection(callback: CallbackQuery, state: FSMContext):
    """Обработка выбора тарифа."""
    plan_id = callback.data.split('_')[1]
    await state.update_data(selected_plan=plan_id)
    await state.set_state(KeyPurchase.choose_payment)
    await show_payment_methods(callback.message)

async def reset_to_main_menu(message: Message, state: FSMContext):
    """Возврат в главное меню."""
    await state.clear()
    await state.set_state(MainMenu.main)
    await show_main_menu(message)
```

## Обработчики команд

### Основные команды

#### 1. Команда /start
```python
@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    """Обработка команды /start."""
    user_id = message.from_user.id
    username = message.from_user.username or "Unknown"
    
    # Регистрация пользователя
    await register_user_if_not_exists(user_id, username)
    
    # Проверка подписки на канал (если включена)
    if await check_subscription_required():
        if not await check_user_subscription(user_id):
            await show_subscription_required(message)
            return
    
    # Показ главного меню
    await state.set_state(MainMenu.main)
    await show_main_menu(message)
```

#### 2. Команда /help
```python
@router.message(Command("help"))
async def cmd_help(message: Message):
    """Показ справки пользователю."""
    help_text = """
🤖 <b>Справка по боту {{PROJECT_NAME}}</b>

<b>Основные команды:</b>
/start - Начать работу с ботом
/help - Показать эту справку
/profile - Мой профиль
/keys - Мои ключи
/balance - Мой баланс
/support - Связаться с поддержкой

<b>Как пользоваться:</b>
1. Выберите тариф в главном меню
2. Выберите способ оплаты
3. Оплатите заказ
4. Получите ключ для подключения

<b>Поддержка:</b>
Если у вас возникли вопросы, обратитесь в поддержку через /support
    """
    await message.answer(help_text, parse_mode="HTML")
```

#### 3. Команда /profile
```python
@router.message(Command("profile"))
async def cmd_profile(message: Message, state: FSMContext):
    """Показ профиля пользователя."""
    user_id = message.from_user.id
    user_data = await get_user_data(user_id)
    
    if not user_data:
        await message.answer("❌ Пользователь не найден. Используйте /start")
        return
    
    # Формирование текста профиля
    profile_text = format_user_profile(user_data)
    
    # Создание клавиатуры профиля
    keyboard = create_profile_keyboard()
    
    await state.set_state(ProfileManagement.view_profile)
    await message.answer(profile_text, reply_markup=keyboard, parse_mode="HTML")
```

### Callback обработчики

#### 1. Обработка выбора тарифа
```python
@router.callback_query(F.data.startswith("plan_"))
async def handle_plan_selection(callback: CallbackQuery, state: FSMContext):
    """Обработка выбора тарифа."""
    plan_id = int(callback.data.split("_")[1])
    
    # Получение информации о тарифе
    plan_data = await get_plan_by_id(plan_id)
    if not plan_data:
        await callback.answer("❌ Тариф не найден", show_alert=True)
        return
    
    # Сохранение выбранного тарифа
    await state.update_data(selected_plan=plan_data)
    await state.set_state(KeyPurchase.choose_payment)
    
    # Показ способов оплаты
    payment_keyboard = create_payment_methods_keyboard(plan_data)
    await callback.message.edit_text(
        f"Вы выбрали {host_name}: {plan_data['plan_name']} - {plan_data['price']:.0f} RUB\n\n"
        f"Теперь выберите удобный способ оплаты:",
        reply_markup=payment_keyboard,
        parse_mode="HTML"
    )
    await callback.answer()
```

#### 2. Обработка платежей
```python
@router.callback_query(F.data.startswith("payment_"))
async def handle_payment_selection(callback: CallbackQuery, state: FSMContext):
    """Обработка выбора способа оплаты."""
    payment_method = callback.data.split("_")[1]
    user_data = await state.get_data()
    plan_data = user_data.get("selected_plan")
    
    if not plan_data:
        await callback.answer("❌ Тариф не выбран", show_alert=True)
        return
    
    # Создание платежа
    payment_result = await create_payment(
        user_id=callback.from_user.id,
        plan_data=plan_data,
        payment_method=payment_method
    )
    
    if payment_result["success"]:
        await state.set_state(KeyPurchase.processing_payment)
        await show_payment_instructions(callback.message, payment_result)
    else:
        await callback.answer(f"❌ Ошибка: {payment_result['error']}", show_alert=True)
    
    await callback.answer()
```

### Обработка текстовых сообщений

#### 1. Обработка в состоянии поддержки
```python
@router.message(SupportDialog.waiting_message)
async def handle_support_message(message: Message, state: FSMContext):
    """Обработка сообщения в поддержку."""
    user_id = message.from_user.id
    username = message.from_user.username or "Unknown"
    support_text = message.text
    
    # Отправка сообщения в поддержку
    support_result = await send_to_support(
        user_id=user_id,
        username=username,
        message=support_text
    )
    
    if support_result["success"]:
        await message.answer(
            "✅ Ваше сообщение отправлено в поддержку. "
            "Мы ответим вам в ближайшее время."
        )
        await state.set_state(MainMenu.main)
        await show_main_menu(message)
    else:
        await message.answer(
            "❌ Ошибка отправки сообщения. Попробуйте позже."
        )
```

## Клавиатуры и интерфейс

### Основные клавиатуры

#### 1. Главное меню
```python
def create_main_menu_keyboard() -> InlineKeyboardMarkup:
    """Создание клавиатуры главного меню."""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🛒 Купить ключ", callback_data="buy_key"),
            InlineKeyboardButton(text="👤 Мой профиль", callback_data="profile")
        ],
        [
            InlineKeyboardButton(text="🔑 Мои ключи", callback_data="my_keys"),
            InlineKeyboardButton(text="💰 Баланс", callback_data="balance")
        ],
        [
            InlineKeyboardButton(text="📊 Статистика", callback_data="stats"),
            InlineKeyboardButton(text="❓ Поддержка", callback_data="support")
        ],
        [
            InlineKeyboardButton(text="ℹ️ О боте", callback_data="about")
        ]
    ])
    return keyboard
```

#### 2. Клавиатура тарифов
```python
def create_plans_keyboard(plans: List[Dict]) -> InlineKeyboardMarkup:
    """Создание клавиатуры с тарифами."""
    keyboard_buttons = []
    
    for plan in plans:
        button_text = f"{plan['plan_name']} - {plan['price']} RUB"
        callback_data = f"plan_{plan['plan_id']}"
        keyboard_buttons.append([
            InlineKeyboardButton(text=button_text, callback_data=callback_data)
        ])
    
    # Кнопка "Назад"
    keyboard_buttons.append([
        InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_main")
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
```

#### 3. Клавиатура способов оплаты
```python
def create_payment_methods_keyboard(plan_data: Dict) -> InlineKeyboardMarkup:
    """Создание клавиатуры способов оплаты."""
    keyboard_buttons = []
    
    # YooKassa (карты и СБП)
    keyboard_buttons.append([
        InlineKeyboardButton(
            text="💳 Банковская карта / СБП", 
            callback_data="payment_yookassa"
        )
    ])
    
    # CryptoBot
    keyboard_buttons.append([
        InlineKeyboardButton(
            text="₿ CryptoBot", 
            callback_data="payment_cryptobot"
        )
    ])
    
    # TON Connect
    keyboard_buttons.append([
        InlineKeyboardButton(
            text="💎 TON Connect", 
            callback_data="payment_ton"
        )
    ])
    
    # Telegram Stars
    keyboard_buttons.append([
        InlineKeyboardButton(
            text="⭐ Telegram Stars", 
            callback_data="payment_stars"
        )
    ])
    
    # Баланс (если достаточно средств)
    if plan_data["price"] <= user_balance:
        keyboard_buttons.append([
            InlineKeyboardButton(
                text=f"💰 С баланса ({user_balance} RUB)", 
                callback_data="payment_balance"
            )
        ])
    
    # Кнопка "Назад"
    keyboard_buttons.append([
        InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_plans")
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
```

### Reply клавиатуры

#### 1. Главное меню (Reply)
```python
def create_reply_keyboard() -> ReplyKeyboardMarkup:
    """Создание Reply клавиатуры."""
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            ["🛒 Купить ключ", "👤 Профиль"],
            ["🔑 Мои ключи", "💰 Баланс"],
            ["❓ Поддержка", "ℹ️ Справка"]
        ],
        resize_keyboard=True,
        one_time_keyboard=False
    )
    return keyboard
```

## Промежуточное ПО

### 1. Middleware аутентификации
```python
class AuthMiddleware(BaseMiddleware):
    """Middleware для проверки аутентификации пользователей."""
    
    async def __call__(self, handler, event, data):
        user = event.from_user
        
        if not user:
            return await handler(event, data)
        
        # Проверка блокировки пользователя
        if await is_user_banned(user.id):
            await event.answer("❌ Вы заблокированы в системе")
            return
        
        # Регистрация пользователя если не зарегистрирован
        await register_user_if_not_exists(user.id, user.username)
        
        return await handler(event, data)
```

### 2. Middleware логирования
```python
class LoggingMiddleware(BaseMiddleware):
    """Middleware для логирования действий пользователей."""
    
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

### 3. Middleware rate limiting
```python
class RateLimitMiddleware(BaseMiddleware):
    """Middleware для ограничения частоты запросов."""
    
    def __init__(self):
        self.user_requests = {}
        self.max_requests = 10  # Максимум запросов
        self.time_window = 60   # За 60 секунд
    
    async def __call__(self, handler, event, data):
        user_id = event.from_user.id
        current_time = time.time()
        
        # Очистка старых записей
        if user_id in self.user_requests:
            self.user_requests[user_id] = [
                req_time for req_time in self.user_requests[user_id]
                if current_time - req_time < self.time_window
            ]
        else:
            self.user_requests[user_id] = []
        
        # Проверка лимита
        if len(self.user_requests[user_id]) >= self.max_requests:
            await event.answer("⏰ Слишком много запросов. Попробуйте позже.")
            return
        
        # Добавление текущего запроса
        self.user_requests[user_id].append(current_time)
        
        return await handler(event, data)
```

## Система уведомлений

### 1. Отправка уведомлений
```python
async def send_notification_to_user(
    user_id: int, 
    notification_type: str, 
    title: str, 
    message: str,
    **kwargs
) -> bool:
    """Отправка уведомления пользователю."""
    try:
        # Логирование уведомления в БД
        notification_id = await log_notification(
            user_id=user_id,
            notification_type=notification_type,
            title=title,
            message=message,
            **kwargs
        )
        
        # Отправка сообщения
        await bot.send_message(
            chat_id=user_id,
            text=f"🔔 <b>{title}</b>\n\n{message}",
            parse_mode="HTML"
        )
        
        # Обновление статуса
        await update_notification_status(notification_id, "sent")
        return True
        
    except Exception as e:
        logger.error(f"Ошибка отправки уведомления пользователю {user_id}: {e}")
        await update_notification_status(notification_id, "failed")
        return False
```

### 2. Типы уведомлений
```python
class NotificationTypes:
    """Типы уведомлений."""
    
    # Платежи
    PAYMENT_SUCCESS = "payment_success"
    PAYMENT_FAILED = "payment_failed"
    PAYMENT_PENDING = "payment_pending"
    
    # Ключи
    KEY_CREATED = "key_created"
    KEY_EXPIRING = "key_expiring"
    KEY_EXPIRED = "key_expired"
    
    # Рефералы
    REFERRAL_BONUS = "referral_bonus"
    REFERRAL_SIGNUP = "referral_signup"
    
    # Системные
    SYSTEM_MAINTENANCE = "system_maintenance"
    SYSTEM_UPDATE = "system_update"
```

### 3. Автоматические уведомления
```python
async def check_expiring_keys():
    """Проверка истекающих ключей."""
    expiring_keys = await get_expiring_keys(hours=24)  # За 24 часа
    
    for key in expiring_keys:
        await send_notification_to_user(
            user_id=key["user_id"],
            notification_type=NotificationTypes.KEY_EXPIRING,
            title="⏰ Ключ скоро истекает",
            message=f"Ваш ключ #{key['key_id']} истекает через {key['hours_left']} часов",
            key_id=key["key_id"]
        )
```

## Интеграция с платежами

### 1. Обработка webhook'ов
```python
@router.message(F.text.startswith("payment_"))
async def handle_payment_webhook(message: Message):
    """Обработка webhook'ов от платежных систем."""
    payment_data = json.loads(message.text)
    
    if payment_data["system"] == "yookassa":
        await handle_yookassa_webhook(payment_data)
    elif payment_data["system"] == "cryptobot":
        await handle_cryptobot_webhook(payment_data)
    elif payment_data["system"] == "ton":
        await handle_ton_webhook(payment_data)
```

### 2. Обработка успешных платежей
```python
async def handle_successful_payment(payment_data: Dict):
    """Обработка успешного платежа."""
    user_id = payment_data["user_id"]
    plan_data = payment_data["plan_data"]
    
    # Создание VPN ключа
    key_result = await create_vpn_key(user_id, plan_data)
    
    if key_result["success"]:
        # Уведомление пользователя
        await send_notification_to_user(
            user_id=user_id,
            notification_type=NotificationTypes.PAYMENT_SUCCESS,
            title="✅ Платеж успешно обработан",
            message=f"Ваш ключ #{key_result['key_id']} готов к использованию!",
            key_id=key_result["key_id"]
        )
        
        # Отправка ключа
        await send_vpn_key_to_user(user_id, key_result["key_data"])
    else:
        # Уведомление об ошибке
        await send_notification_to_user(
            user_id=user_id,
            notification_type=NotificationTypes.PAYMENT_FAILED,
            title="❌ Ошибка обработки платежа",
            message="Произошла ошибка при создании ключа. Обратитесь в поддержку."
        )
```

## Обработка ошибок

### 1. Глобальный обработчик ошибок
```python
@router.error()
async def error_handler(event, exception):
    """Глобальный обработчик ошибок."""
    logger.error(f"Ошибка в диалоге: {exception}", exc_info=True)
    
    if isinstance(event, Message):
        await event.answer(
            "❌ Произошла ошибка. Попробуйте позже или обратитесь в поддержку."
        )
    elif isinstance(event, CallbackQuery):
        await event.answer(
            "❌ Ошибка обработки запроса", 
            show_alert=True
        )

# Регистрация обработчика
dp.error.register(error_handler)
```

### 2. Обработка специфических ошибок
```python
@router.callback_query(F.data.startswith("plan_"))
async def handle_plan_selection(callback: CallbackQuery, state: FSMContext):
    """Обработка выбора тарифа с обработкой ошибок."""
    try:
        plan_id = int(callback.data.split("_")[1])
        plan_data = await get_plan_by_id(plan_id)
        
        if not plan_data:
            raise ValueError("Тариф не найден")
        
        # Основная логика...
        
    except ValueError as e:
        await callback.answer(f"❌ Ошибка: {e}", show_alert=True)
    except DatabaseError as e:
        logger.error(f"Ошибка БД при выборе тарифа: {e}")
        await callback.answer("❌ Ошибка базы данных", show_alert=True)
    except Exception as e:
        logger.error(f"Неожиданная ошибка при выборе тарифа: {e}")
        await callback.answer("❌ Произошла ошибка", show_alert=True)
```

## Тестирование диалогов

### 1. Unit тесты для handlers
```python
import pytest
from unittest.mock import AsyncMock, MagicMock
from aiogram.types import Message, CallbackQuery, User

@pytest.mark.asyncio
async def test_start_command():
    """Тест команды /start."""
    # Создание мок-объектов
    message = MagicMock(spec=Message)
    message.from_user.id = 12345
    message.from_user.username = "testuser"
    message.answer = AsyncMock()
    
    state = MagicMock()
    state.set_state = AsyncMock()
    
    # Вызов handler'а
    await cmd_start(message, state)
    
    # Проверки
    message.answer.assert_called_once()
    state.set_state.assert_called_once_with(MainMenu.main)
```

### 2. Интеграционные тесты
```python
@pytest.mark.asyncio
async def test_purchase_flow():
    """Тест полного процесса покупки."""
    # Начало процесса
    message = create_test_message("/start")
    await cmd_start(message, state)
    
    # Выбор тарифа
    callback = create_test_callback("plan_1")
    await handle_plan_selection(callback, state)
    
    # Выбор способа оплаты
    callback = create_test_callback("payment_yookassa")
    await handle_payment_selection(callback, state)
    
    # Проверка состояния
    current_state = await state.get_state()
    assert current_state == KeyPurchase.processing_payment
```

### 3. Тестирование клавиатур
```python
def test_main_menu_keyboard():
    """Тест создания главного меню."""
    keyboard = create_main_menu_keyboard()
    
    assert len(keyboard.inline_keyboard) == 4  # 4 ряда кнопок
    assert len(keyboard.inline_keyboard[0]) == 2  # Первый ряд - 2 кнопки
    
    # Проверка текста кнопок
    first_row = keyboard.inline_keyboard[0]
    assert first_row[0].text == "🛒 Купить ключ"
    assert first_row[1].text == "👤 Мой профиль"
```

---

*Документация создана {{DATE}}*
*Владелец проекта: {{OWNER}}*
