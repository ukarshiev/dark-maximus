<!-- 4884fa66-08bf-487a-ad50-5b20726068ef a62d7dca-bc79-48b1-bd81-2e2b303c2b01 -->
# План: Постоянный токен для личного кабинета

**Дата создания/обновления:** 12.11.2025 12:48

**Версия:** 1.0

## Цель

Реализовать постоянный токен для доступа к личному кабинету, который:

- Уникален для каждой пары (user_id, key_id)
- Хранится в БД и не меняется при перезагрузках
- Отображается в профиле пользователя при просмотре ключа
- Используется для авторизации в личном кабинете

## Текущее состояние

- Таблица `user_tokens` уже существует в БД
- Личный кабинет работает без токена (просто `/`)
- Функции `get_key_info_text()` и `get_purchase_success_text()` не принимают `key_id` и `user_id`
- Токен не создается при создании ключа

## Изменения

### 1. Функции работы с постоянным токеном в БД

**Файл:** `src/shop_bot/data_manager/database.py`

**1.1. Функция получения/создания постоянного токена**

Добавить функцию `get_or_create_permanent_token(user_id: int, key_id: int) -> str`:

- Проверяет наличие токена в БД для пары (user_id, key_id)
- Если токен существует - возвращает его
- Если токена нет - генерирует новый через `secrets.token_urlsafe(32)` и сохраняет в БД
- Возвращает токен

**1.2. Функция получения токена по key_id**

Добавить функцию `get_permanent_token_by_key_id(key_id: int) -> str | None`:

- Ищет токен в БД по key_id
- Возвращает токен или None если не найден

**1.3. Функция валидации постоянного токена**

Обновить или создать функцию `validate_permanent_token(token: str) -> dict | None`:

- Проверяет существование токена в БД
- Проверяет активность ключа (expiry_date, status, enabled)
- Обновляет статистику использования (last_used_at, access_count)
- Возвращает данные токена или None

### 2. Обновление функций формирования текстов

**Файл:** `src/shop_bot/config.py`

**2.1. Обновление `get_key_info_text()`**

Добавить параметры `user_id` и `key_id`:

```python
def get_key_info_text(
    key_number,
    expiry_date,
    created_date,
    connection_string,
    status: str | None = None,
    subscription_link: str = None,
    provision_mode: str = 'key',
    *,
    user_id: int | None = None,
    key_id: int | None = None,
    user_timezone: str | None = None,
    feature_enabled: bool = False,
    is_trial: bool = False,
):
```

В функции:

- Если `user_id` и `key_id` переданы - получаем токен через `get_or_create_permanent_token(user_id, key_id)`
- Формируем ссылку: `f"{cabinet_domain}/auth/{token}"`
- Добавляем ссылку в `cabinet_text` для всех режимов

**2.2. Обновление `get_purchase_success_text()`**

Добавить параметры `user_id` и `key_id`:

```python
def get_purchase_success_text(
    action: str,
    key_number: int,
    expiry_date,
    connection_string: str = None,
    subscription_link: str = None,
    provision_mode: str = 'key',
    *,
    user_id: int | None = None,
    key_id: int | None = None,
    user_timezone: str | None = None,
    feature_enabled: bool = False,
    is_trial: bool = False,
):
```

В функции:

- Если `user_id` и `key_id` переданы - получаем токен через `get_or_create_permanent_token(user_id, key_id)`
- Формируем ссылку: `f"{cabinet_domain}/auth/{token}"`
- Использовать токен во всех местах, где формируется `cabinet_url`

### 3. Обновление обработчиков бота

**Файл:** `src/shop_bot/bot/handlers.py`

**3.1. Обновление `show_key_handler()`**

В функции `show_key_handler()` (строка ~3406):

- Передать `user_id` и `key_id_to_show` в `get_key_info_text()`:
```python
final_text = get_key_info_text(
    key_number,
    expiry_date,
    created_date,
    connection_string,
    status,
    subscription_link,
    provision_mode,
    user_id=user_id,
    key_id=key_id_to_show,
    user_timezone=user_timezone,
    feature_enabled=feature_enabled,
    is_trial=is_trial,
)
```


**3.2. Обновление всех вызовов `get_purchase_success_text()`**

Найти все места, где вызывается `get_purchase_success_text()` (строки ~3211, ~3342, ~4826, ~5314, ~6757, ~6843, ~7161):

- Добавить параметры `user_id=user_id` и `key_id=key_id` во все вызовы

**3.3. Создание токена при создании ключа**

В функции `process_successful_payment()` или там, где создается новый ключ:

- После создания ключа вызвать `get_or_create_permanent_token(user_id, key_id)` для автоматического создания токена

### 4. Обновление личного кабинета

**Файл:** `apps/user-cabinet/app.py`

**4.1. Восстановление проверки токена**

Восстановить декоратор `require_token` и маршрут `/auth/<token>`:

- Использовать функцию `validate_permanent_token(token)` для проверки
- Сохранять данные в сессию (user_id, key_id, subscription_link)
- Получать информацию о ключе через `get_key_by_id(key_id)`

**4.2. Обновление маршрута `/`**

Маршрут `/` должен:

- Проверять наличие токена в query параметрах или сессии
- Если токен есть - валидировать и показывать кабинет
- Если токена нет - показывать сообщение о необходимости токена

### 5. Миграция существующих ключей (опционально)

**Файл:** `src/shop_bot/data_manager/database.py`

Добавить функцию для создания токенов для существующих ключей:

- При первом запуске после обновления создать токены для всех активных ключей
- Можно выполнить через отдельный скрипт или при старте приложения

## Логика работы

1. При создании нового ключа автоматически создается постоянный токен
2. При просмотре ключа в профиле токен получается из БД (или создается если отсутствует)
3. Ссылка формируется как `{cabinet_domain}/auth/{token}`
4. Личный кабинет проверяет токен и показывает информацию о конкретном ключе
5. Токен не меняется при перезагрузках, так как хранится в БД

## Безопасность

- Токен генерируется криптографически стойким способом (`secrets.token_urlsafe`)
- Проверяется активность ключа при валидации токена
- Rate limiting остается для защиты от злоупотреблений
- Токен уникален для каждой пары (user_id, key_id)

## Тестирование

1. Создать новый ключ и проверить создание токена в БД
2. Открыть профиль → ключи → просмотреть ключ → проверить ссылку на ЛК
3. Перейти по ссылке и проверить авторизацию в личном кабинете
4. Проверить, что токен не меняется при перезагрузке
5. Проверить работу для разных режимов предоставления (key, subscription, both, cabinet, cabinet_subscription)

### To-dos

- [x] Создать структуру проекта apps/user-cabinet/
- [x] Создать миграцию БД: таблица user_tokens
- [x] Настроить Flask-приложение с базовыми роутами
- [x] Создать Dockerfile для нового сервиса
- [x] Добавить сервис в docker-compose.yml
- [x] Реализовать генерацию токенов при создании ключа
- [x] Создать middleware для проверки токенов с rate limiting
- [x] Реализовать роут авторизации с проверкой активности подписки
- [x] Добавить логирование доступа к кабинету
- [x] Обновить CHANGELOG.md