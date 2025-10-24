# Схема типизации CQRS для {{PROJECT_NAME}}

## Оглавление
- [Обзор CQRS](#обзор-cqrs)
- [Базовые типы](#базовые-типы)
- [Команды (Commands)](#команды-commands)
- [Запросы (Queries)](#запросы-queries)
- [События (Events)](#события-events)
- [Handlers](#handlers)
- [DTO и Value Objects](#dto-и-value-objects)
- [Валидация](#валидация)
- [Обработка ошибок](#обработка-ошибок)
- [Примеры использования](#примеры-использования)

## Обзор CQRS

CQRS (Command Query Responsibility Segregation) - это архитектурный паттерн, который разделяет операции чтения и записи данных. В контексте {{PROJECT_NAME}} это позволяет:

- **Команды (Commands)** - Изменяют состояние системы (создание пользователей, обработка платежей)
- **Запросы (Queries)** - Получают данные без изменения состояния (получение профиля, статистики)
- **События (Events)** - Уведомляют о произошедших изменениях

### Преимущества CQRS для проекта
1. **Четкое разделение ответственности** - Команды и запросы имеют разные цели
2. **Масштабируемость** - Можно оптимизировать чтение и запись независимо
3. **Типобезопасность** - Строгая типизация всех операций
4. **Тестируемость** - Легко тестировать команды и запросы отдельно
5. **Аудит** - Все изменения проходят через команды

## Базовые типы

### Базовые интерфейсы
```python
from abc import ABC, abstractmethod
from typing import Generic, TypeVar, Any, Optional
from dataclasses import dataclass
from enum import Enum

# Типы для Generic
TCommand = TypeVar('TCommand')
TQuery = TypeVar('TQuery')
TEvent = TypeVar('TEvent')
TResult = TypeVar('TResult')

# Базовые интерфейсы
class Command(ABC):
    """Базовый интерфейс для команд."""
    pass

class Query(ABC):
    """Базовый интерфейс для запросов."""
    pass

class Event(ABC):
    """Базовый интерфейс для событий."""
    pass

class CommandHandler(ABC, Generic[TCommand, TResult]):
    """Базовый интерфейс для обработчиков команд."""
    
    @abstractmethod
    async def handle(self, command: TCommand) -> TResult:
        pass

class QueryHandler(ABC, Generic[TQuery, TResult]):
    """Базовый интерфейс для обработчиков запросов."""
    
    @abstractmethod
    async def handle(self, query: TQuery) -> TResult:
        pass

class EventHandler(ABC, Generic[TEvent]):
    """Базовый интерфейс для обработчиков событий."""
    
    @abstractmethod
    async def handle(self, event: TEvent) -> None:
        pass
```

### Результаты операций
```python
from typing import Union, List, Optional

@dataclass
class SuccessResult:
    """Успешный результат операции."""
    success: bool = True
    data: Optional[Any] = None
    message: Optional[str] = None

@dataclass
class ErrorResult:
    """Результат с ошибкой."""
    success: bool = False
    error_code: str
    error_message: str
    details: Optional[dict] = None

@dataclass
class ValidationError:
    """Ошибка валидации."""
    field: str
    message: str
    value: Any

@dataclass
class ValidationResult:
    """Результат валидации."""
    is_valid: bool
    errors: List[ValidationError]

# Тип результата
OperationResult = Union[SuccessResult, ErrorResult]
```

## Команды (Commands)

### Пользователи

#### 1. Создание пользователя
```python
@dataclass
class CreateUserCommand(Command):
    """Команда создания пользователя."""
    telegram_id: int
    username: str
    referrer_id: Optional[int] = None
    registration_source: str = "telegram"

@dataclass
class CreateUserResult:
    """Результат создания пользователя."""
    user_id: int
    is_new_user: bool
    referral_bonus: Optional[float] = None

class CreateUserHandler(CommandHandler[CreateUserCommand, CreateUserResult]):
    """Обработчик создания пользователя."""
    
    def __init__(self, user_repository, referral_service):
        self.user_repo = user_repository
        self.referral_service = referral_service
    
    async def handle(self, command: CreateUserCommand) -> CreateUserResult:
        # Проверка существования пользователя
        existing_user = await self.user_repo.get_by_telegram_id(command.telegram_id)
        if existing_user:
            return CreateUserResult(
                user_id=existing_user.id,
                is_new_user=False
            )
        
        # Создание пользователя
        user_data = {
            'telegram_id': command.telegram_id,
            'username': command.username,
            'referred_by': command.referrer_id,
            'registration_source': command.registration_source
        }
        
        user_id = await self.user_repo.create(user_data)
        
        # Обработка реферала
        referral_bonus = None
        if command.referrer_id:
            referral_bonus = await self.referral_service.process_referral(
                referrer_id=command.referrer_id,
                new_user_id=user_id
            )
        
        return CreateUserResult(
            user_id=user_id,
            is_new_user=True,
            referral_bonus=referral_bonus
        )
```

#### 2. Обновление баланса
```python
@dataclass
class UpdateUserBalanceCommand(Command):
    """Команда обновления баланса пользователя."""
    user_id: int
    amount: float
    operation_type: str  # 'add', 'subtract', 'set'
    reason: str
    transaction_id: Optional[str] = None

@dataclass
class UpdateBalanceResult:
    """Результат обновления баланса."""
    new_balance: float
    previous_balance: float
    transaction_id: Optional[str] = None

class UpdateUserBalanceHandler(CommandHandler[UpdateUserBalanceCommand, UpdateBalanceResult]):
    """Обработчик обновления баланса."""
    
    def __init__(self, user_repository, transaction_service):
        self.user_repo = user_repository
        self.transaction_service = transaction_service
    
    async def handle(self, command: UpdateUserBalanceCommand) -> UpdateBalanceResult:
        # Получение текущего баланса
        user = await self.user_repo.get_by_id(command.user_id)
        if not user:
            raise ValueError(f"Пользователь {command.user_id} не найден")
        
        previous_balance = user.balance
        
        # Вычисление нового баланса
        if command.operation_type == 'add':
            new_balance = previous_balance + command.amount
        elif command.operation_type == 'subtract':
            new_balance = max(0, previous_balance - command.amount)
        elif command.operation_type == 'set':
            new_balance = command.amount
        else:
            raise ValueError(f"Неподдерживаемый тип операции: {command.operation_type}")
        
        # Обновление баланса
        await self.user_repo.update_balance(command.user_id, new_balance)
        
        # Логирование транзакции
        if command.transaction_id:
            await self.transaction_service.log_balance_transaction(
                user_id=command.user_id,
                amount=command.amount,
                operation_type=command.operation_type,
                reason=command.reason,
                transaction_id=command.transaction_id
            )
        
        return UpdateBalanceResult(
            new_balance=new_balance,
            previous_balance=previous_balance,
            transaction_id=command.transaction_id
        )
```

### VPN Ключи

#### 1. Создание ключа
```python
@dataclass
class CreateVpnKeyCommand(Command):
    """Команда создания VPN ключа."""
    user_id: int
    host_name: str
    plan_id: int
    is_trial: bool = False
    custom_duration_days: Optional[int] = None

@dataclass
class CreateVpnKeyResult:
    """Результат создания VPN ключа."""
    key_id: int
    connection_string: str
    expiry_date: datetime
    xui_client_uuid: str

class CreateVpnKeyHandler(CommandHandler[CreateVpnKeyCommand, CreateVpnKeyResult]):
    """Обработчик создания VPN ключа."""
    
    def __init__(self, key_repository, xui_service, plan_service):
        self.key_repo = key_repository
        self.xui_service = xui_service
        self.plan_service = plan_service
    
    async def handle(self, command: CreateVpnKeyCommand) -> CreateVpnKeyResult:
        # Получение информации о тарифе
        plan = await self.plan_service.get_by_id(command.plan_id)
        if not plan:
            raise ValueError(f"Тариф {command.plan_id} не найден")
        
        # Вычисление даты истечения
        if command.custom_duration_days:
            duration_days = command.custom_duration_days
        else:
            duration_days = plan.months * 30 + plan.days
        
        expiry_date = datetime.now() + timedelta(days=duration_days)
        
        # Создание клиента в 3x-ui
        xui_result = await self.xui_service.create_client(
            host_name=command.host_name,
            plan=plan,
            expiry_timestamp=int(expiry_date.timestamp() * 1000)
        )
        
        if not xui_result.success:
            raise RuntimeError(f"Ошибка создания клиента в 3x-ui: {xui_result.error}")
        
        # Сохранение ключа в БД
        key_data = {
            'user_id': command.user_id,
            'host_name': command.host_name,
            'xui_client_uuid': xui_result.client_uuid,
            'key_email': xui_result.email,
            'expiry_date': expiry_date,
            'connection_string': xui_result.connection_string,
            'plan_name': plan.plan_name,
            'price': plan.price,
            'protocol': plan.protocol,
            'is_trial': command.is_trial
        }
        
        key_id = await self.key_repo.create(key_data)
        
        return CreateVpnKeyResult(
            key_id=key_id,
            connection_string=xui_result.connection_string,
            expiry_date=expiry_date,
            xui_client_uuid=xui_result.client_uuid
        )
```

### Платежи

#### 1. Создание платежа
```python
@dataclass
class CreatePaymentCommand(Command):
    """Команда создания платежа."""
    user_id: int
    plan_id: int
    payment_method: str  # 'yookassa', 'cryptobot', 'ton', 'stars', 'balance'
    amount: float
    currency: str = 'RUB'
    metadata: Optional[dict] = None

@dataclass
class CreatePaymentResult:
    """Результат создания платежа."""
    payment_id: str
    payment_url: Optional[str] = None
    qr_code: Optional[str] = None
    status: str = 'pending'

class CreatePaymentHandler(CommandHandler[CreatePaymentCommand, CreatePaymentResult]):
    """Обработчик создания платежа."""
    
    def __init__(self, payment_service, plan_service):
        self.payment_service = payment_service
        self.plan_service = plan_service
    
    async def handle(self, command: CreatePaymentCommand) -> CreatePaymentResult:
        # Получение информации о тарифе
        plan = await self.plan_service.get_by_id(command.plan_id)
        if not plan:
            raise ValueError(f"Тариф {command.plan_id} не найден")
        
        # Создание платежа в зависимости от метода
        if command.payment_method == 'yookassa':
            result = await self.payment_service.create_yookassa_payment(
                user_id=command.user_id,
                amount=command.amount,
                plan=plan,
                metadata=command.metadata
            )
        elif command.payment_method == 'cryptobot':
            result = await self.payment_service.create_cryptobot_payment(
                user_id=command.user_id,
                amount=command.amount,
                plan=plan,
                metadata=command.metadata
            )
        elif command.payment_method == 'ton':
            result = await self.payment_service.create_ton_payment(
                user_id=command.user_id,
                amount=command.amount,
                plan=plan,
                metadata=command.metadata
            )
        elif command.payment_method == 'balance':
            result = await self.payment_service.process_balance_payment(
                user_id=command.user_id,
                amount=command.amount,
                plan=plan,
                metadata=command.metadata
            )
        else:
            raise ValueError(f"Неподдерживаемый способ оплаты: {command.payment_method}")
        
        return CreatePaymentResult(
            payment_id=result.payment_id,
            payment_url=result.payment_url,
            qr_code=result.qr_code,
            status=result.status
        )
```

## Запросы (Queries)

### Пользователи

#### 1. Получение профиля пользователя
```python
@dataclass
class GetUserProfileQuery(Query):
    """Запрос профиля пользователя."""
    user_id: int
    include_keys: bool = True
    include_transactions: bool = False

@dataclass
class UserProfileData:
    """Данные профиля пользователя."""
    user_id: int
    username: str
    balance: float
    total_spent: float
    total_months: int
    registration_date: datetime
    is_banned: bool
    referral_balance: float
    keys: List[VpnKeyData] = None
    recent_transactions: List[TransactionData] = None

class GetUserProfileHandler(QueryHandler[GetUserProfileQuery, UserProfileData]):
    """Обработчик получения профиля пользователя."""
    
    def __init__(self, user_repository, key_repository, transaction_repository):
        self.user_repo = user_repository
        self.key_repo = key_repository
        self.transaction_repo = transaction_repository
    
    async def handle(self, query: GetUserProfileQuery) -> UserProfileData:
        # Получение данных пользователя
        user = await self.user_repo.get_by_id(query.user_id)
        if not user:
            raise ValueError(f"Пользователь {query.user_id} не найден")
        
        # Получение ключей (если запрошено)
        keys = None
        if query.include_keys:
            keys = await self.key_repo.get_by_user_id(query.user_id)
        
        # Получение транзакций (если запрошено)
        transactions = None
        if query.include_transactions:
            transactions = await self.transaction_repo.get_recent_by_user_id(
                query.user_id, limit=10
            )
        
        return UserProfileData(
            user_id=user.id,
            username=user.username,
            balance=user.balance,
            total_spent=user.total_spent,
            total_months=user.total_months,
            registration_date=user.registration_date,
            is_banned=user.is_banned,
            referral_balance=user.referral_balance,
            keys=keys,
            recent_transactions=transactions
        )
```

#### 2. Получение статистики
```python
@dataclass
class GetAnalyticsQuery(Query):
    """Запрос аналитики."""
    period_days: int = 30
    include_users: bool = True
    include_revenue: bool = True
    include_keys: bool = True

@dataclass
class AnalyticsData:
    """Данные аналитики."""
    period_days: int
    total_users: int
    new_users: int
    total_revenue: float
    total_keys: int
    active_keys: int
    daily_stats: List[DailyStats]

@dataclass
class DailyStats:
    """Статистика за день."""
    date: str
    new_users: int
    revenue: float
    new_keys: int

class GetAnalyticsHandler(QueryHandler[GetAnalyticsQuery, AnalyticsData]):
    """Обработчик получения аналитики."""
    
    def __init__(self, analytics_service):
        self.analytics_service = analytics_service
    
    async def handle(self, query: GetAnalyticsQuery) -> AnalyticsData:
        # Получение общей статистики
        total_users = await self.analytics_service.get_total_users()
        new_users = await self.analytics_service.get_new_users(query.period_days)
        total_revenue = await self.analytics_service.get_total_revenue(query.period_days)
        total_keys = await self.analytics_service.get_total_keys()
        active_keys = await self.analytics_service.get_active_keys()
        
        # Получение ежедневной статистики
        daily_stats = await self.analytics_service.get_daily_stats(query.period_days)
        
        return AnalyticsData(
            period_days=query.period_days,
            total_users=total_users,
            new_users=new_users,
            total_revenue=total_revenue,
            total_keys=total_keys,
            active_keys=active_keys,
            daily_stats=daily_stats
        )
```

## События (Events)

### 1. События пользователей
```python
@dataclass
class UserCreatedEvent(Event):
    """Событие создания пользователя."""
    user_id: int
    username: str
    referrer_id: Optional[int] = None
    timestamp: datetime = field(default_factory=datetime.now)

@dataclass
class UserBalanceUpdatedEvent(Event):
    """Событие обновления баланса пользователя."""
    user_id: int
    previous_balance: float
    new_balance: float
    amount: float
    operation_type: str
    timestamp: datetime = field(default_factory=datetime.now)

@dataclass
class UserBannedEvent(Event):
    """Событие блокировки пользователя."""
    user_id: int
    reason: str
    admin_id: int
    timestamp: datetime = field(default_factory=datetime.now)
```

### 2. События платежей
```python
@dataclass
class PaymentCreatedEvent(Event):
    """Событие создания платежа."""
    payment_id: str
    user_id: int
    amount: float
    payment_method: str
    timestamp: datetime = field(default_factory=datetime.now)

@dataclass
class PaymentCompletedEvent(Event):
    """Событие завершения платежа."""
    payment_id: str
    user_id: int
    amount: float
    transaction_hash: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)

@dataclass
class PaymentFailedEvent(Event):
    """Событие неудачного платежа."""
    payment_id: str
    user_id: int
    amount: float
    error_reason: str
    timestamp: datetime = field(default_factory=datetime.now)
```

### 3. События VPN ключей
```python
@dataclass
class VpnKeyCreatedEvent(Event):
    """Событие создания VPN ключа."""
    key_id: int
    user_id: int
    host_name: str
    plan_name: str
    expiry_date: datetime
    is_trial: bool
    timestamp: datetime = field(default_factory=datetime.now)

@dataclass
class VpnKeyExpiredEvent(Event):
    """Событие истечения VPN ключа."""
    key_id: int
    user_id: int
    host_name: str
    timestamp: datetime = field(default_factory=datetime.now)
```

## Handlers

### 1. Event Bus
```python
class EventBus:
    """Шина событий для обработки событий."""
    
    def __init__(self):
        self._handlers: Dict[Type[Event], List[EventHandler]] = {}
    
    def register_handler(self, event_type: Type[Event], handler: EventHandler):
        """Регистрация обработчика события."""
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)
    
    async def publish(self, event: Event):
        """Публикация события."""
        event_type = type(event)
        handlers = self._handlers.get(event_type, [])
        
        for handler in handlers:
            try:
                await handler.handle(event)
            except Exception as e:
                logger.error(f"Ошибка обработки события {event_type.__name__}: {e}")
```

### 2. Command Bus
```python
class CommandBus:
    """Шина команд для обработки команд."""
    
    def __init__(self):
        self._handlers: Dict[Type[Command], CommandHandler] = {}
    
    def register_handler(self, command_type: Type[Command], handler: CommandHandler):
        """Регистрация обработчика команды."""
        self._handlers[command_type] = handler
    
    async def execute(self, command: Command) -> OperationResult:
        """Выполнение команды."""
        command_type = type(command)
        handler = self._handlers.get(command_type)
        
        if not handler:
            return ErrorResult(
                error_code="HANDLER_NOT_FOUND",
                error_message=f"Обработчик для команды {command_type.__name__} не найден"
            )
        
        try:
            result = await handler.handle(command)
            return SuccessResult(data=result)
        except Exception as e:
            logger.error(f"Ошибка выполнения команды {command_type.__name__}: {e}")
            return ErrorResult(
                error_code="COMMAND_EXECUTION_ERROR",
                error_message=str(e)
            )
```

### 3. Query Bus
```python
class QueryBus:
    """Шина запросов для обработки запросов."""
    
    def __init__(self):
        self._handlers: Dict[Type[Query], QueryHandler] = {}
    
    def register_handler(self, query_type: Type[Query], handler: QueryHandler):
        """Регистрация обработчика запроса."""
        self._handlers[query_type] = handler
    
    async def execute(self, query: Query) -> OperationResult:
        """Выполнение запроса."""
        query_type = type(query)
        handler = self._handlers.get(query_type)
        
        if not handler:
            return ErrorResult(
                error_code="HANDLER_NOT_FOUND",
                error_message=f"Обработчик для запроса {query_type.__name__} не найден"
            )
        
        try:
            result = await handler.handle(query)
            return SuccessResult(data=result)
        except Exception as e:
            logger.error(f"Ошибка выполнения запроса {query_type.__name__}: {e}")
            return ErrorResult(
                error_code="QUERY_EXECUTION_ERROR",
                error_message=str(e)
            )
```

## DTO и Value Objects

### 1. Value Objects
```python
@dataclass(frozen=True)
class Money:
    """Value Object для денежных сумм."""
    amount: float
    currency: str = 'RUB'
    
    def __post_init__(self):
        if self.amount < 0:
            raise ValueError("Сумма не может быть отрицательной")
        if not self.currency:
            raise ValueError("Валюта обязательна")

@dataclass(frozen=True)
class Email:
    """Value Object для email адресов."""
    value: str
    
    def __post_init__(self):
        if '@' not in self.value:
            raise ValueError("Некорректный email адрес")

@dataclass(frozen=True)
class TelegramId:
    """Value Object для Telegram ID."""
    value: int
    
    def __post_init__(self):
        if self.value <= 0:
            raise ValueError("Telegram ID должен быть положительным числом")
```

### 2. DTO для передачи данных
```python
@dataclass
class UserDto:
    """DTO для пользователя."""
    id: int
    telegram_id: int
    username: str
    balance: float
    total_spent: float
    registration_date: datetime
    is_banned: bool

@dataclass
class VpnKeyDto:
    """DTO для VPN ключа."""
    id: int
    user_id: int
    host_name: str
    connection_string: str
    expiry_date: datetime
    plan_name: str
    price: float
    is_trial: bool

@dataclass
class TransactionDto:
    """DTO для транзакции."""
    id: int
    user_id: int
    payment_id: str
    amount: float
    currency: str
    payment_method: str
    status: str
    created_date: datetime
```

## Валидация

### 1. Валидаторы команд
```python
class CommandValidator(ABC, Generic[TCommand]):
    """Базовый валидатор команд."""
    
    @abstractmethod
    async def validate(self, command: TCommand) -> ValidationResult:
        pass

class CreateUserCommandValidator(CommandValidator[CreateUserCommand]):
    """Валидатор команды создания пользователя."""
    
    async def validate(self, command: CreateUserCommand) -> ValidationResult:
        errors = []
        
        # Валидация Telegram ID
        if command.telegram_id <= 0:
            errors.append(ValidationError(
                field="telegram_id",
                message="Telegram ID должен быть положительным числом",
                value=command.telegram_id
            ))
        
        # Валидация username
        if not command.username or len(command.username) < 3:
            errors.append(ValidationError(
                field="username",
                message="Username должен содержать минимум 3 символа",
                value=command.username
            ))
        
        # Валидация referrer_id
        if command.referrer_id is not None and command.referrer_id <= 0:
            errors.append(ValidationError(
                field="referrer_id",
                message="Referrer ID должен быть положительным числом",
                value=command.referrer_id
            ))
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors
        )
```

### 2. Валидаторы запросов
```python
class QueryValidator(ABC, Generic[TQuery]):
    """Базовый валидатор запросов."""
    
    @abstractmethod
    async def validate(self, query: TQuery) -> ValidationResult:
        pass

class GetUserProfileQueryValidator(QueryValidator[GetUserProfileQuery]):
    """Валидатор запроса профиля пользователя."""
    
    async def validate(self, query: GetUserProfileQuery) -> ValidationResult:
        errors = []
        
        # Валидация user_id
        if query.user_id <= 0:
            errors.append(ValidationError(
                field="user_id",
                message="User ID должен быть положительным числом",
                value=query.user_id
            ))
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors
        )
```

## Обработка ошибок

### 1. Исключения CQRS
```python
class CQRSException(Exception):
    """Базовое исключение CQRS."""
    pass

class CommandExecutionException(CQRSException):
    """Исключение выполнения команды."""
    pass

class QueryExecutionException(CQRSException):
    """Исключение выполнения запроса."""
    pass

class ValidationException(CQRSException):
    """Исключение валидации."""
    def __init__(self, validation_result: ValidationResult):
        self.validation_result = validation_result
        super().__init__(f"Ошибки валидации: {[e.message for e in validation_result.errors]}")
```

### 2. Обработка ошибок в handlers
```python
class CreateUserHandler(CommandHandler[CreateUserCommand, CreateUserResult]):
    """Обработчик создания пользователя с обработкой ошибок."""
    
    def __init__(self, user_repository, validator: CreateUserCommandValidator):
        self.user_repo = user_repository
        self.validator = validator
    
    async def handle(self, command: CreateUserCommand) -> CreateUserResult:
        # Валидация команды
        validation_result = await self.validator.validate(command)
        if not validation_result.is_valid:
            raise ValidationException(validation_result)
        
        try:
            # Основная логика
            return await self._create_user(command)
        except DatabaseError as e:
            raise CommandExecutionException(f"Ошибка базы данных: {e}")
        except Exception as e:
            raise CommandExecutionException(f"Неожиданная ошибка: {e}")
    
    async def _create_user(self, command: CreateUserCommand) -> CreateUserResult:
        # Реализация создания пользователя
        pass
```

## Примеры использования

### 1. Использование команд
```python
# Создание пользователя
create_user_command = CreateUserCommand(
    telegram_id=12345,
    username="testuser",
    referrer_id=67890
)

result = await command_bus.execute(create_user_command)
if result.success:
    user_data = result.data
    print(f"Пользователь создан: {user_data.user_id}")
else:
    print(f"Ошибка: {result.error_message}")

# Обновление баланса
update_balance_command = UpdateUserBalanceCommand(
    user_id=12345,
    amount=100.0,
    operation_type='add',
    reason='Пополнение баланса'
)

result = await command_bus.execute(update_balance_command)
if result.success:
    balance_data = result.data
    print(f"Новый баланс: {balance_data.new_balance}")
```

### 2. Использование запросов
```python
# Получение профиля пользователя
profile_query = GetUserProfileQuery(
    user_id=12345,
    include_keys=True,
    include_transactions=True
)

result = await query_bus.execute(profile_query)
if result.success:
    profile = result.data
    print(f"Пользователь: {profile.username}")
    print(f"Баланс: {profile.balance}")
    print(f"Ключей: {len(profile.keys)}")
```

### 3. Обработка событий
```python
# Обработчик события создания пользователя
class UserCreatedEventHandler(EventHandler[UserCreatedEvent]):
    async def handle(self, event: UserCreatedEvent) -> None:
        # Отправка приветственного сообщения
        await send_welcome_message(event.user_id)
        
        # Логирование в аналитику
        await analytics_service.track_user_creation(event)

# Регистрация обработчика
event_bus.register_handler(UserCreatedEvent, UserCreatedEventHandler())
```

---

*Документация создана {{DATE}}*
*Владелец проекта: {{OWNER}}*
