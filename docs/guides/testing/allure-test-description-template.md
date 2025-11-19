# Шаблон описания тестов для Allure

> **Дата последней редакции:** 15.01.2025

## Назначение

Этот документ описывает единый формат описаний тестов с использованием Allure декораторов для обеспечения понятности и единообразия в отчетах.

## Структура описания теста

Каждый тест должен иметь следующие Allure декораторы:

### 1. @allure.title()

Краткое, понятное название теста на русском языке.

**Пример:**
```python
@allure.title("Полный workflow администратора: навигация по основным разделам")
```

### 2. @allure.description()

Подробное описание теста в формате Markdown с обязательными разделами:

```python
@allure.description("""
**Что проверяется:**
- Конкретная функциональность или сценарий
- Бизнес-логика, которая тестируется

**Тестовые данные:**
- Входные параметры (user_id, payment_id, plan_id и т.д.)
- Значения фикстур (temp_db, test_setup)
- Моки и их возвращаемые значения

**Шаги теста:**
1. **Название шага**
   - Метод/функция: database.register_user_if_not_exists()
   - Параметры: user_id=123456789, username="test_user", fullname="Test User"
   - Ожидаемый результат: пользователь создан в БД с указанными данными
   - Проверка: database.get_user(123456789) возвращает объект пользователя
   - Проверяемые поля: telegram_id, username, registration_date
   
2. **Следующий шаг**
   - Метод/функция: bot.handlers.process_successful_payment()
   - Параметры: bot=mock_bot, metadata={user_id, operation, months, price, host_name, plan_id, payment_method, payment_id}
   - Ожидаемый результат: ключ создан на хосте через 3X-UI API
   - Проверка: database.get_user_keys(user_id) возвращает список с одним ключом
   - Проверяемые поля: key_id, user_id, host_name, expiry_date, status

**Предусловия:**
- Что должно быть готово перед запуском теста
- Какие данные должны существовать в БД
- Какие моки/фикстуры используются и что они возвращают
- Настройки окружения (временная БД, отключенные проверки)

**Используемые моки и фикстуры:**
- temp_db: временная SQLite БД с полной структурой таблиц (users, vpn_keys, transactions, plans, xui_hosts и т.д.)
- mock_bot: мок aiogram.Bot с методами send_message, edit_message_text, answer_callback_query
- mock_xui_api: мок py3xui.Api с методом create_or_update_key_on_host, возвращающий client_uuid, email, expiry_timestamp_ms
- test_setup: фикстура создает пользователя (user_id=123456789), хост (host_name='test-host') и план (plan_id, price=100.0)

**Проверяемые граничные случаи:** (если применимо)
- Обработка ошибок при недостаточном балансе
- Валидация некорректных данных
- Повторная обработка того же платежа (идемпотентность)
- Обработка истекших промокодов

**Ожидаемый результат:**
- Что должно произойти в итоге
- Какие данные должны быть созданы/изменены в БД
- Какие статусы должны быть возвращены
- Какие ключи должны быть созданы
- Какие транзакции должны быть залогированы
""")
```

### 3. @allure.severity()

Уровень важности теста:

- `allure.severity_level.CRITICAL` - критичные тесты (основной функционал)
- `allure.severity_level.NORMAL` - обычные тесты (стандартный функционал)
- `allure.severity_level.MINOR` - второстепенные тесты (дополнительный функционал)

**Пример:**
```python
@allure.severity(allure.severity_level.CRITICAL)
```

### 4. @allure.tag()

Теги для фильтрации и группировки тестов. Используются ключевые слова на русском или английском.

**Важно:** Для упрощения фильтрации по критичности, severity также добавляется в теги:
- `"critical"` для `allure.severity_level.CRITICAL`
- `"normal"` для `allure.severity_level.NORMAL`
- `"minor"` для `allure.severity_level.MINOR`

**Пример:**
```python
@allure.severity(allure.severity_level.CRITICAL)
@allure.tag("admin", "navigation", "workflow", "critical")
```

### 5. allure.step()

Шаги внутри теста для детализации выполнения. Используются для сложных тестов с несколькими действиями.

**Рекомендации по использованию:**
- Используйте `allure.step()` для каждого значимого действия в тесте
- Название шага должно быть понятным и описывать конкретное действие
- Внутри шага выполняйте одно логическое действие и его проверку
- Для сложных операций можно использовать вложенные шаги

**Пример:**
```python
def test_example():
    with allure.step("Шаг 1: Проверка доступа к главной странице"):
        response = client.get('/')
        assert response.status_code == 200
    
    with allure.step("Шаг 2: Проверка списка пользователей"):
        response = client.get('/users')
        assert response.status_code == 200
        assert len(response.json) > 0
```

**Пример с вложенными шагами:**
```python
async def test_payment_flow():
    with allure.step("Подготовка данных для платежа"):
        user_id = 123456789
        payment_id = f"test_{uuid.uuid4().hex[:16]}"
        metadata = {
            'user_id': user_id,
            'operation': 'new',
            'months': 1,
            'price': 100.0
        }
    
    with allure.step("Обработка успешного платежа"):
        with allure.step("Вызов process_successful_payment"):
            await process_successful_payment(mock_bot, metadata)
        
        with allure.step("Проверка создания ключа"):
            keys = get_user_keys(user_id)
            assert len(keys) > 0
```

## Полные примеры

### Пример 1: Тест веб-панели

```python
import allure
import pytest

@pytest.mark.integration
class TestAdminWorkflow:
    @allure.title("Полный workflow администратора: навигация по основным разделам")
    @allure.description("""
    Проверяет последовательность действий администратора при работе с веб-панелью:
    
    **Что проверяется:**
    - Доступность основных разделов административной панели
    - Корректная работа навигации между разделами
    - Отсутствие ошибок авторизации при переходе между страницами
    
    **Тестовые данные:**
    - Администратор авторизован через фикстуру authenticated_session
    - Временная БД (temp_db) используется для изоляции теста
    - Моки возвращают пустые данные для упрощения проверки
    
    **Шаги теста:**
    1. **Доступ к главной странице (Dashboard)**
       - Метод/эндпоинт: GET /
       - Параметры: сессия администратора (authenticated_session)
       - Ожидаемый результат: HTTP 200, страница загружается без ошибок
       - Проверка: response.status_code == 200
       - Мок: database.get_all_settings возвращает пустой словарь {}
    
    2. **Доступ к разделу пользователей**
       - Метод/эндпоинт: GET /users
       - Параметры: сессия администратора (authenticated_session)
       - Ожидаемый результат: HTTP 200, список пользователей отображается
       - Проверка: response.status_code == 200
       - Мок: database.get_all_users возвращает пустой список []
    
    3. **Доступ к разделу ключей**
       - Метод/эндпоинт: GET /keys
       - Параметры: сессия администратора (authenticated_session)
       - Ожидаемый результат: HTTP 200, список ключей отображается
       - Проверка: response.status_code == 200
       - Мок: database.get_paginated_keys возвращает ([], 0)
    
    **Предусловия:**
    - Администратор авторизован в системе (сессия активна через фикстуру authenticated_session)
    - Используется временная БД (temp_db)
    - CSRF защита отключена для тестов (WTF_CSRF_ENABLED = False)
    - Flask приложение настроено в тестовом режиме (TESTING = True)
    
    **Используемые моки и фикстуры:**
    - authenticated_session: Flask test client с активной сессией администратора
    - temp_db: временная SQLite БД с полной структурой таблиц
    - Моки для database.get_all_settings, get_all_users, get_paginated_keys
    
    **Ожидаемый результат:**
    Все три страницы должны успешно загружаться без ошибок авторизации или доступа.
    Статус код каждого запроса должен быть 200.
    """)
    @allure.severity(allure.severity_level.CRITICAL)
    @allure.tag("admin", "navigation", "workflow", "critical")
    def test_admin_full_workflow(self, authenticated_session):
        """Тест полного workflow администратора"""
        with patch('shop_bot.data_manager.database.get_all_settings', return_value={}):
            with allure.step("Проверка доступа к главной странице (Dashboard)"):
                response = authenticated_session.get('/')
                assert response.status_code == 200, f"Ожидался статус 200, получен {response.status_code}"
            
            with patch('shop_bot.data_manager.database.get_all_users', return_value=[]):
                with allure.step("Проверка доступа к разделу пользователей"):
                    response = authenticated_session.get('/users')
                    assert response.status_code == 200, f"Ожидался статус 200, получен {response.status_code}"
            
            with patch('shop_bot.data_manager.database.get_paginated_keys', return_value=([], 0)):
                with allure.step("Проверка доступа к разделу ключей"):
                    response = authenticated_session.get('/keys')
                    assert response.status_code == 200, f"Ожидался статус 200, получен {response.status_code}"
```

### Пример 2: Тест платежной системы

```python
import allure
import pytest
from datetime import datetime, timezone, timedelta
import uuid

@pytest.mark.integration
class TestPaymentFlow:
    @allure.title("Полный flow YooKassa: от создания платежа до получения ключа")
    @allure.description("""
    Проверяет полный цикл обработки платежа через YooKassa от создания транзакции до выдачи VPN ключа:
    
    **Что проверяется:**
    - Создание транзакции с методом оплаты YooKassa
    - Обработка успешного платежа через process_successful_payment
    - Создание VPN ключа на хосте через 3X-UI API
    - Обновление статуса транзакции на 'paid'
    
    **Тестовые данные:**
    - user_id: 123456789 (создается через test_setup)
    - payment_id: yookassa_<hex> (генерируется в тесте)
    - plan_id: создается через test_setup, price=100.0
    - host_name: 'test-host' (из sample_host)
    - expiry_timestamp_ms: текущее время + 30 дней в миллисекундах
    
    **Шаги теста:**
    1. **Подготовка окружения**
       - Метод: настройка временной БД и моков
       - Параметры: temp_db, test_setup, mock_bot, mock_xui_api
       - Ожидаемый результат: окружение готово для теста
       - Проверка: database.DB_FILE указывает на temp_db
       - Мок: mock_xui_api.create_or_update_key_on_host возвращает client_uuid, email, expiry_timestamp_ms
    
    2. **Создание транзакции**
       - Метод: database.log_transaction()
       - Параметры: payment_id='yookassa_abc123', user_id=123456789, status='pending', amount_rub=100.0, payment_method='yookassa'
       - Ожидаемый результат: транзакция создана в БД со статусом 'pending'
       - Проверка: database.get_transaction_by_payment_id(payment_id) возвращает транзакцию
       - Проверяемые поля: payment_id, user_id, status='pending', amount_rub=100.0
    
    3. **Обработка успешного платежа**
       - Метод: bot.handlers.process_successful_payment()
       - Параметры: bot=mock_bot, metadata={user_id, operation='new', months=1, price=100.0, host_name, plan_id, payment_method='yookassa', payment_id}
       - Ожидаемый результат: ключ создан на хосте, транзакция обновлена на 'paid'
       - Проверка: mock_xui_api.create_or_update_key_on_host вызван с правильными параметрами
       - Проверка: database.get_transaction_by_payment_id(payment_id).status == 'paid'
    
    4. **Проверка создания ключа**
       - Метод: database.get_user_keys()
       - Параметры: user_id=123456789
       - Ожидаемый результат: список содержит один ключ
       - Проверка: len(keys) == 1
       - Проверяемые поля: key_id, user_id=123456789, host_name='test-host', status='active'
    
    **Предусловия:**
    - Пользователь зарегистрирован (user_id: 123456789) через test_setup
    - Хост создан в БД (xui_hosts) через test_setup
    - План создан для хоста (plan_id, price=100.0) через test_setup
    - Используется временная БД (temp_db)
    - Моки для bot и xui_api настроены
    
    **Используемые моки и фикстуры:**
    - temp_db: временная SQLite БД с полной структурой таблиц
    - test_setup: фикстура создает пользователя (user_id=123456789), хост (host_name='test-host') и план (plan_id, price=100.0)
    - mock_bot: мок aiogram.Bot с методами send_message, edit_message_text
    - mock_xui_api: мок py3xui.Api с методом create_or_update_key_on_host, возвращающий:
      * client_uuid: UUID строки
      * email: user{user_id}-key1@testcode.bot
      * expiry_timestamp_ms: текущее время + 30 дней
      * subscription_link: https://example.com/subscription
      * connection_string: vless://test
    
    **Ожидаемый результат:**
    После обработки платежа должен быть создан VPN ключ для пользователя.
    Транзакция должна быть обновлена со статусом 'paid'.
    Ключ должен быть привязан к правильному пользователю и хосту.
    """)
    @allure.severity(allure.severity_level.CRITICAL)
    @allure.tag("payments", "yookassa", "integration", "critical")
    @pytest.mark.asyncio
    async def test_yookassa_full_flow(self, temp_db, test_setup, mock_bot, mock_xui_api):
        """Тест полного flow от создания платежа до получения ключа"""
        # Патчим DB_FILE для использования временной БД
        from shop_bot.data_manager import database
        original_db_file = database.DB_FILE
        database.DB_FILE = temp_db
        
        # Патчим xui_api
        with patch('shop_bot.modules.xui_api.create_or_update_key_on_host', new_callable=AsyncMock) as mock_create_key:
            expiry_timestamp_ms = int((datetime.now(timezone.utc) + timedelta(days=30)).timestamp() * 1000)
            mock_create_key.return_value = {
                'client_uuid': str(uuid.uuid4()),
                'email': f"user{test_setup['user_id']}-key1@testcode.bot",
                'expiry_timestamp_ms': expiry_timestamp_ms,
                'subscription_link': 'https://example.com/subscription',
                'connection_string': 'vless://test'
            }
            
            with allure.step("Создание транзакции YooKassa"):
                payment_id = f"yookassa_{uuid.uuid4().hex[:16]}"
                log_transaction(
                    payment_id=payment_id,
                    user_id=test_setup['user_id'],
                    status='pending',
                    amount_rub=test_setup['price'],
                    payment_method='yookassa'
                )
            
            with allure.step("Обработка успешного платежа"):
                metadata = {
                    'user_id': test_setup['user_id'],
                    'operation': 'new',
                    'months': 1,
                    'price': test_setup['price'],
                    'host_name': test_setup['host_name'],
                    'plan_id': test_setup['plan_id'],
                    'payment_method': 'yookassa',
                    'payment_id': payment_id
                }
                await process_successful_payment(mock_bot, metadata)
            
            with allure.step("Проверка создания ключа"):
                keys = get_user_keys(test_setup['user_id'])
                assert len(keys) > 0, "Должен быть создан ключ"
                assert keys[0]['user_id'] == test_setup['user_id']
                assert keys[0]['host_name'] == test_setup['host_name']
            
            with allure.step("Проверка обновления транзакции"):
                transaction = get_transaction_by_payment_id(payment_id)
                assert transaction is not None
                assert transaction['status'] == 'paid'
        
        # Восстанавливаем оригинальный DB_FILE
        database.DB_FILE = original_db_file
```

### Пример 3: Тест покупки VPN

```python
import allure
import pytest

@pytest.mark.integration
class TestVPNPurchase:
    @allure.title("Полный цикл покупки VPN для нового пользователя")
    @allure.description("""
    Проверяет полный цикл покупки VPN ключа для нового пользователя от регистрации до получения ключа:
    
    **Что проверяется:**
    - Регистрация нового пользователя
    - Обработка платежа
    - Создание ключа на хосте через 3X-UI API
    - Проверка принадлежности ключа пользователю и хосту
    
    **Тестовые данные:**
    - user_id: 123456800 (создается в тесте)
    - username: 'test_user_new'
    - fullname: 'Test User New'
    - host_name: 'test-host' (из sample_host)
    - plan_id: создается через test_setup, price=100.0, months=1
    - payment_id: test_<hex> (генерируется в тесте)
    
    **Шаги теста:**
    1. **Регистрация пользователя**
       - Метод: database.register_user_if_not_exists()
       - Параметры: user_id=123456800, username='test_user_new', fullname='Test User New'
       - Ожидаемый результат: пользователь создан в БД
       - Проверка: database.get_user(123456800) возвращает объект пользователя
       - Проверяемые поля: telegram_id=123456800, username='test_user_new', registration_date не None
    
    2. **Подготовка метаданных платежа**
       - Метод: создание словаря metadata
       - Параметры: user_id, operation='new', months=1, price=100.0, host_name, plan_id, payment_method='yookassa', payment_id
       - Ожидаемый результат: metadata содержит все необходимые данные для обработки платежа
       - Проверка: все обязательные поля присутствуют в metadata
    
    3. **Обработка успешного платежа**
       - Метод: bot.handlers.process_successful_payment()
       - Параметры: bot=mock_bot, metadata={...}
       - Ожидаемый результат: ключ создан на хосте через mock_xui_api
       - Проверка: mock_xui_api.create_or_update_key_on_host вызван один раз
       - Проверка: mock_bot.send_message вызван для уведомления пользователя
    
    4. **Проверка создания ключа**
       - Метод: database.get_user_keys()
       - Параметры: user_id=123456800
       - Ожидаемый результат: список содержит один ключ
       - Проверка: len(keys) == 1
       - Проверяемые поля: key_id, user_id=123456800, host_name='test-host', status='active', expiry_date не None
    
    5. **Проверка принадлежности ключа**
       - Метод: database.get_key_by_id()
       - Параметры: key_id из предыдущего шага
       - Ожидаемый результат: ключ принадлежит правильному пользователю и хосту
       - Проверка: key['user_id'] == 123456800
       - Проверка: key['host_name'] == 'test-host'
    
    **Предусловия:**
    - Хост создан в БД (xui_hosts) через test_setup
    - План создан для хоста (plan_id, price=100.0, months=1) через test_setup
    - Используется временная БД (temp_db)
    - Моки для bot и xui_api настроены
    
    **Используемые моки и фикстуры:**
    - temp_db: временная SQLite БД с полной структурой таблиц
    - test_setup: фикстура создает хост (host_name='test-host') и план (plan_id, price=100.0)
    - mock_bot: мок aiogram.Bot с методами send_message, edit_message_text
    - mock_xui_api: мок py3xui.Api с методом create_or_update_key_on_host, возвращающий:
      * client_uuid: UUID строки
      * email: user{user_id}-key1@testcode.bot
      * expiry_timestamp_ms: текущее время + 30 дней
      * subscription_link: https://example.com/subscription
      * connection_string: vless://test
    
    **Проверяемые граничные случаи:**
    - Обработка нового пользователя (без существующих ключей)
    - Корректное создание ключа с правильным сроком действия
    - Привязка ключа к правильному хосту
    
    **Ожидаемый результат:**
    После обработки платежа должен быть создан VPN ключ для нового пользователя.
    Ключ должен быть привязан к правильному пользователю (user_id=123456800) и хосту (host_name='test-host').
    Ключ должен иметь статус 'active' и корректный срок действия (expiry_date).
    """)
    @allure.severity(allure.severity_level.CRITICAL)
    @allure.tag("vpn", "purchase", "new-user", "integration", "critical")
    @pytest.mark.asyncio
    async def test_full_purchase_flow_new_user(self, temp_db, test_setup, mock_bot, mock_xui_api):
        """Тест полного цикла для нового пользователя"""
        # Реализация теста...
```

## Правила оформления

1. **Язык:** Все описания на русском языке
2. **Структура:** Обязательные разделы: "Что проверяется", "Тестовые данные", "Шаги теста", "Предусловия", "Используемые моки и фикстуры", "Ожидаемый результат"
3. **Детализация:** Указывать конкретные эндпоинты, методы, параметры вызовов, ожидаемые статусы и значения
4. **Шаги:** Использовать `allure.step()` для каждого значимого действия в тесте
5. **Шаги теста:** Для каждого шага указывать:
   - Метод/функцию, которая вызывается
   - Параметры вызова с конкретными значениями
   - Ожидаемый результат
   - Проверки, которые выполняются
   - Проверяемые поля/атрибуты
6. **Тестовые данные:** Описывать все входные данные: user_id, payment_id, plan_id, значения фикстур
7. **Моки и фикстуры:** Детально описывать, что возвращают моки и какие данные создают фикстуры
8. **Граничные случаи:** Указывать проверяемые граничные случаи, если они есть
9. **Docstrings:** Сохранять существующие docstrings как дополнительную документацию
10. **Логика:** Не изменять логику тестов, только добавлять описания

## Типы тестов

### Unit-тесты

Для unit-тестов описание может быть короче, но должно включать:
- Что проверяется (конкретная функция/метод)
- Входные данные
- Ожидаемый результат

### Integration-тесты

Для интеграционных тестов обязательно:
- Полное описание сценария
- Все шаги выполнения
- Используемые эндпоинты/API
- Предусловия и моки

### E2E-тесты

Для E2E-тестов необходимо:
- Описание полного пользовательского сценария
- Все шаги от начала до конца
- Ожидаемые результаты на каждом этапе
- Бизнес-логика сценария

## Проверка качества

Перед коммитом убедитесь, что:

- [ ] Все тесты имеют `@allure.title()`
- [ ] Все тесты имеют `@allure.description()` с обязательными разделами:
  - [ ] "Что проверяется"
  - [ ] "Тестовые данные"
  - [ ] "Шаги теста" (с конкретными методами, параметрами, проверками)
  - [ ] "Предусловия"
  - [ ] "Используемые моки и фикстуры"
  - [ ] "Проверяемые граничные случаи" (если применимо)
  - [ ] "Ожидаемый результат"
- [ ] Указан `@allure.severity()`
- [ ] Добавлены релевантные `@allure.tag()` (включая severity в тегах)
- [ ] Для каждого значимого действия используется `allure.step()`
- [ ] Описания написаны на русском языке
- [ ] Указаны конкретные эндпоинты/методы с параметрами
- [ ] Описаны ожидаемые результаты и проверяемые поля
- [ ] Указаны возвращаемые значения моков и фикстур

## Связанные документы

- [Структура тестов](testing-structure.md)
- [Запуск тестов](running-tests.md)
- [Управление дефектами в Allure](allure-defects-management.md)

