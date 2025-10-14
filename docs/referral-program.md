# Реферальная программа Dark Maximus

**Последнее обновление:** 19.01.2025 12:45

## Оглавление
- [Обзор](#обзор)
- [Как работает реферальная программа](#как-работает-реферальная-программа)
- [Настройки](#настройки)
- [Техническая реализация](#техническая-реализация)
- [База данных](#база-данных)
- [API функции](#api-функции)
- [Известные проблемы и исправления](#известные-проблемы-и-исправления)

## Обзор

Реферальная программа Dark Maximus позволяет пользователям приглашать друзей и получать вознаграждение с каждой их покупки. Система включает в себя:

- **Реферальные ссылки** - уникальные ссылки для приглашения друзей
- **Скидки для рефералов** - скидка на первую покупку для приглашенных пользователей
- **Реферальные бонусы** - процент с каждой покупки реферала
- **Вывод средств** - возможность вывести накопленные реферальные средства

## Как работает реферальная программа

### 1. Регистрация по реферальной ссылке

Когда пользователь переходит по реферальной ссылке вида:
```
https://t.me/BOT_USERNAME?start=ref_USER_ID
```

Система:
1. Определяет ID реферера из параметра `ref_USER_ID`
2. При регистрации нового пользователя сохраняет `referred_by = USER_ID` в базе данных
3. Связь между реферером и рефералом устанавливается навсегда

**Код регистрации:**
```python
# src/shop_bot/bot/handlers.py:493-500
potential_referrer_id = int(command.args.split('_')[1])
if potential_referrer_id != user_id:
    referrer_id = potential_referrer_id
    logger.info(f"New user {user_id} was referred by {referrer_id}")

register_user_if_not_exists(user_id, username, referrer_id, message.from_user.full_name)
```

### 2. Скидка для реферала при первой покупке

При первой покупке (когда `total_spent == 0`) реферал получает скидку:

**Размер скидки:** Настраивается через `referral_discount` (по умолчанию 5%)

**Применение скидки:**
```python
# src/shop_bot/bot/handlers.py:2599-2611
if user_data.get('referred_by') and user_data.get('total_spent', 0) == 0:
    discount_percentage_str = get_setting("referral_discount") or "0"
    discount_percentage = Decimal(discount_percentage_str)
    
    if discount_percentage > 0:
        discount_amount = (price * discount_percentage / 100).quantize(Decimal("0.01"))
        final_price = price - discount_amount
```

**Важно:** Скидка применяется только один раз - при первой покупке.

### 3. Начисление реферального бонуса

При каждой покупке реферала (включая первую) реферер получает процент от суммы покупки:

**Размер бонуса:** Настраивается через `referral_percentage` (по умолчанию 10%)

**Расчет бонуса:**
```python
# src/shop_bot/bot/handlers.py:4795-4812
if referrer_id:
    percentage = Decimal(get_setting("referral_percentage") or "0")
    
    reward = (Decimal(str(price)) * percentage / 100).quantize(Decimal("0.01"))
    
    if float(reward) > 0:
        add_to_referral_balance(referrer_id, float(reward))
        
        # Отправка уведомления рефереру
        try:
            buyer_username = user_data.get('username', 'пользователь')
            await bot.send_message(
                referrer_id,
                f"🎉 Ваш реферал @{buyer_username} совершил покупку на сумму {price:.2f} RUB!\n"
                f"💰 На ваш баланс начислено вознаграждение: {reward:.2f} RUB."
            )
        except Exception as e:
            logger.warning(f"Could not send referral reward notification to {referrer_id}: {e}")
```

**Важные особенности:**
- Бонус начисляется с фактически оплаченной суммы (с учетом всех скидок и промокодов)
- Бонус начисляется при каждой покупке реферала
- Реферер получает уведомление о каждой покупке реферала

### 4. Реферальный баланс

У каждого пользователя есть два баланса:
- `referral_balance` - текущий доступный баланс для вывода
- `referral_balance_all` - общий накопленный баланс (для статистики)

**Отображение в профиле:**
Реферальный баланс отображается в разделе "Мой профиль" только при включенной реферальной системе. Если реферальная система выключена в настройках, строка с реферальным балансом скрывается.

**Начисление:**
```python
# src/shop_bot/data_manager/database.py:2706-2720
def add_to_referral_balance(user_id: int, amount: float):
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET referral_balance = referral_balance + ? WHERE telegram_id = ?", 
                         (amount, user_id))
            conn.commit()
    except sqlite3.Error as e:
        logging.error(f"Failed to add to referral balance for user {user_id}: {e}")
```

### 5. Вывод средств

**Минимальная сумма для вывода:** 100 RUB (настраивается через `minimum_withdrawal`)

**Процесс вывода:**

#### Шаг 1: Выбор способа вывода
Пользователь нажимает "💸 Оставить заявку на вывод" и выбирает способ:
- 📱 По номеру телефона **(Рекомендуемый)**
- 💳 По номеру банковской карты

#### Шаг 2: Выбор банка (только для телефона)
Если выбран телефон, пользователь выбирает банк из списка:
- 🏦 Сбербанк
- 🏦 ВТБ
- 🏦 Альфа-Банк
- 🏦 Тинькофф
- 🏦 Газпромбанк
- 🏦 Райффайзенбанк
- 🏦 Другой банк

**Важно:** Комиссия банка (до 50 рублей) оплачивается нами.

#### Шаг 3: Ввод реквизитов
В зависимости от выбранного способа:
- **Для телефона:** вводит номер телефона (формат: +7XXXXXXXXXX)
- **Для карты:** вводит номер банковской карты (формат: XXXX XXXX XXXX XXXX)

#### Шаг 4: Отправка заявки
Заявка отправляется администратору с inline-кнопками "✅ Одобрить" и "❌ Отклонить"

#### Шаг 5: Одобрение/отклонение
Администратор нажимает на соответствующую кнопку для одобрения или отклонения заявки.

**При отклонении заявки:**
1. Администратор нажимает кнопку "❌ Отклонить"
2. Бот показывает полные данные заявки и запрашивает причину отклонения
3. Администратор вводит причину отклонения (например, "Ошибка в реквизитах", "Высокая комиссия банка")
4. Бот отправляет пользователю сообщение с полными данными заявки и причиной отклонения
5. Заявка помечается как отклоненная с указанием причины

**Пример сообщения для администратора при запросе причины:**
```
📝 Укажите причину отклонения заявки

Данные заявки пользователя:
👤 Пользователь: @username
💰 Сумма: 250.00 RUB
📱 Способ вывода: по номеру телефона
🏦 Банк: Сбербанк
📱 Номер телефона: +79991234567

Напишите причину отклонения заявки. Это сообщение будет отправлено пользователю.
```

**Пример сообщения для пользователя при отклонении:**
```
❌ Ваша заявка на вывод отклонена

Данные вашей заявки:
👤 Пользователь: @username
💰 Сумма: 250.00 RUB
📱 Способ вывода: по номеру телефона
🏦 Банк: Сбербанк
📱 Номер телефона: +79991234567

⚠️ Причина: Ошибка в реквизитах
Пожалуйста, проверьте корректность реквизитов и попробуйте снова.
```

**Отображение заявки для администратора (телефон):**
```
💸 Заявка на вывод реферальных средств
👤 Пользователь: @username (ID: 12345)
💰 Сумма: 250.00 RUB
📱 Способ вывода: по номеру телефона
🏦 Банк: Сбербанк
📱 Номер телефона: +79991234567
```

**Отображение заявки для администратора (карта):**
```
💸 Заявка на вывод реферальных средств
👤 Пользователь: @username (ID: 12345)
💰 Сумма: 250.00 RUB
💳 Способ вывода: по номеру банковской карты
💳 Номер карты: 1234 5678 9012 3456
```

**Одобрение вывода через кнопку:**
```python
# src/shop_bot/bot/handlers.py:1597-1640
@user_router.callback_query(F.data.startswith("approve_withdraw_"))
async def approve_withdraw_callback(callback: types.CallbackQuery):
    user_id = int(callback.data.split("_")[-1])
    user = get_user(user_id)
    balance = user.get('referral_balance', 0)
    
    set_referral_balance(user_id, 0)
    
    # Обновляем сообщение с заявкой
    await callback.message.edit_text(
        f"✅ <b>Заявка одобрена</b>\n"
        f"👤 Пользователь: {user.get('username', 'N/A')} (ID: <code>{user_id}</code>)\n"
        f"💰 Выплачено: <b>{balance:.2f} RUB</b>",
        parse_mode="HTML"
    )
    
    # Уведомляем пользователя
    await callback.bot.send_message(
        user_id,
        f"✅ Ваша заявка на вывод {balance:.2f} RUB одобрена. Деньги будут переведены в ближайшее время."
    )
```

**Отклонение вывода через кнопку:**
```python
# src/shop_bot/bot/handlers.py:1813-1844
@user_router.callback_query(F.data.startswith("decline_withdraw_"))
async def decline_withdraw_callback(callback: types.CallbackQuery, state: FSMContext):
    user_id = int(callback.data.split("_")[-1])
    user = get_user(user_id)
    
    # Сохраняем user_id в состоянии для последующего использования
    await state.update_data(decline_user_id=user_id, decline_message_id=callback.message.message_id)
    
    # Запрашиваем причину отклонения
    await callback.message.edit_text(
        f"📝 <b>Укажите причину отклонения заявки</b>\n\n"
        f"👤 Пользователь: {user.get('username', 'N/A')} (ID: <code>{user_id}</code>)\n\n"
        f"Напишите причину отклонения заявки. Это сообщение будет отправлено пользователю.",
        parse_mode="HTML"
    )
    
    await state.set_state(DeclineWithdrawStates.waiting_for_decline_reason)
```

**Обработчик получения причины отклонения:**
```python
# src/shop_bot/bot/handlers.py:1894-1984
@user_router.message(DeclineWithdrawStates.waiting_for_decline_reason)
async def decline_withdraw_reason_handler(message: types.Message, state: FSMContext):
    data = await state.get_data()
    user_id = data.get('decline_user_id')
    reason = message.text
    
    # Получаем данные заявки из состояния
    username = data.get('decline_username', user.get('username', 'N/A'))
    amount = data.get('decline_amount', '0.00')
    method_text = data.get('decline_method_text', 'не указан')
    bank_name = data.get('decline_bank_name')
    details = data.get('decline_details')
    method_icon = data.get('decline_method_icon', '💳')
    
    # Формируем сообщение для пользователя с полными данными заявки
    user_message = (
        f"❌ <b>Ваша заявка на вывод отклонена</b>\n\n"
        f"<b>Данные вашей заявки:</b>\n"
        f"👤 Пользователь: @{username}\n"
        f"💰 Сумма: {amount} RUB\n"
        f"{method_icon} Способ вывода: {method_text}"
    )
    
    if bank_name:
        user_message += f"\n🏦 Банк: {bank_name}"
    
    if details:
        if method_icon == "📱":
            user_message += f"\n📱 Номер телефона: {details}"
        else:
            user_message += f"\n💳 Номер карты: {details}"
    
    user_message += f"\n\n⚠️ <b>Причина:</b> {reason}\n\n"
    user_message += "Пожалуйста, проверьте корректность реквизитов и попробуйте снова."
    
    # Отправляем сообщение пользователю
    await message.bot.send_message(user_id, user_message, parse_mode="HTML")
    
    # Обновляем сообщение с заявкой
    await message.bot.edit_message_text(
        f"❌ <b>Заявка отклонена</b>\n"
        f"👤 Пользователь: {username} (ID: <code>{user_id}</code>)\n\n"
        f"📝 <b>Причина:</b> {reason}",
        chat_id=admin_id,
        message_id=message_id,
        parse_mode="HTML"
    )
    
    await state.clear()
```

**Обработка ошибок парсинга HTML:**
При возникновении ошибок парсинга HTML-сущностей (например, при использовании специальных символов в реквизитах), система автоматически отправляет сообщение без HTML-форматирования:

```python
# src/shop_bot/bot/handlers.py:1544-1564
try:
    await message.bot.send_message(admin_id, text, parse_mode="HTML", reply_markup=keyboard)
except TelegramBadRequest as e:
    error_msg = str(e)
    if "can't parse entities" in error_msg or "unsupported start tag" in error_msg:
        # Отправляем без форматирования
        text_plain = (
            f"💸 Заявка на вывод реферальных средств\n"
            f"👤 Пользователь: @{username} (ID: {user_id})\n"
            f"💰 Сумма: {balance:.2f} RUB\n"
            f"📄 Реквизиты: {details}"
        )
        await message.bot.send_message(admin_id, text_plain, reply_markup=keyboard)
```

**Важно:** 
- При одобрении вывода `referral_balance` обнуляется, а `referral_balance_all` сохраняется (для статистики)
- Команды `/approve_withdraw` и `/decline_withdraw` по-прежнему работают для обратной совместимости
- При нажатии на кнопку сообщение с заявкой обновляется с информацией о статусе

### 6. Реферальная ссылка

Каждый пользователь получает уникальную реферальную ссылку:
```
https://t.me/BOT_USERNAME?start=ref_USER_ID
```

**Генерация ссылки:**
```python
# src/shop_bot/bot/handlers.py:1127
bot_username = (await message.bot.get_me()).username
referral_link = f"https://t.me/{bot_username}?start=ref_{user_id}"
```

## Настройки

Все настройки реферальной программы хранятся в таблице `settings`:

| Параметр | Описание | Значение по умолчанию |
|----------|----------|----------------------|
| `enable_referrals` | Включить/выключить реферальную программу | `true` |
| `referral_percentage` | Процент от покупки реферала для реферера | `10` |
| `referral_discount` | Скидка для реферала на первую покупку (%) | `5` |
| `minimum_withdrawal` | Минимальная сумма для вывода (RUB) | `100` |

**Инициализация настроек:**
```python
# src/shop_bot/data_manager/database.py:394-400
"enable_referrals": "true",
"referral_percentage": "10",
"referral_discount": "5",
"minimum_withdrawal": "100",
```

## Техническая реализация

### Архитектура

```
┌─────────────────────────────────────────────────────────────┐
│                     Реферальная программа                    │
└─────────────────────────────────────────────────────────────┘
                            │
                ┌───────────┴───────────┐
                │                       │
        ┌───────▼────────┐      ┌──────▼───────┐
        │  Регистрация   │      │   Покупка    │
        │   по ссылке    │      │  реферала    │
        └───────┬────────┘      └──────┬───────┘
                │                      │
                │                      │
        ┌───────▼────────┐      ┌──────▼───────┐
        │  Сохранение    │      │  Начисление  │
        │  referred_by   │      │    бонуса    │
        └────────────────┘      └──────┬───────┘
                                       │
                              ┌────────▼────────┐
                              │  Уведомление    │
                              │    реферера     │
                              └─────────────────┘
```

### Поток данных

1. **Регистрация:**
   ```
   Пользователь → /start ref_12345 → Сохранение referred_by=12345
   ```

2. **Покупка реферала:**
   ```
   Реферал покупает → Проверка referred_by → Расчет бонуса → 
   Начисление на referral_balance → Уведомление реферера
   ```

3. **Вывод средств:**
   ```
   Пользователь → Заявка на вывод → Администратор → Одобрение → 
   Обнуление балансов → Уведомление пользователя
   ```

## База данных

### Таблица `users`

```sql
CREATE TABLE users (
    telegram_id INTEGER PRIMARY KEY,
    username TEXT,
    referred_by INTEGER,              -- ID пользователя, который пригласил
    referral_balance REAL DEFAULT 0,   -- Текущий доступный баланс
    referral_balance_all REAL DEFAULT 0, -- Общий накопленный баланс
    total_spent REAL DEFAULT 0,        -- Общая сумма потраченных средств
    ...
);
```

**Индексы:**
```sql
CREATE INDEX idx_users_referred_by ON users(referred_by);
```

### Таблица `settings`

```sql
CREATE TABLE settings (
    key TEXT PRIMARY KEY,
    value TEXT
);
```

**Настройки реферальной программы:**
```sql
INSERT INTO settings (key, value) VALUES 
    ('enable_referrals', 'true'),
    ('referral_percentage', '10'),
    ('referral_discount', '5'),
    ('minimum_withdrawal', '100');
```

## API функции

### Получение количества рефералов

```python
def get_referral_count(user_id: int) -> int:
    """Возвращает количество рефералов пользователя"""
    cursor.execute("SELECT COUNT(*) FROM users WHERE referred_by = ?", (user_id,))
    return cursor.fetchone()[0] or 0
```

### Начисление реферального бонуса

```python
def add_to_referral_balance(user_id: int, amount: float):
    """Добавляет сумму на реферальный баланс пользователя"""
    cursor.execute("UPDATE users SET referral_balance = referral_balance + ? WHERE telegram_id = ?", 
                  (amount, user_id))
```

### Установка реферального баланса

```python
def set_referral_balance(user_id: int, value: float):
    """Устанавливает текущий реферальный баланс"""
    cursor.execute("UPDATE users SET referral_balance = ? WHERE telegram_id = ?", 
                  (value, user_id))
```

### Установка общего реферального баланса

```python
def set_referral_balance_all(user_id: int, value: float):
    """Устанавливает общий реферальный баланс"""
    cursor.execute("UPDATE users SET referral_balance_all = ? WHERE telegram_id = ?", 
                  (value, user_id))
```

## Известные проблемы и исправления

### Улучшение от 19.01.2025 12:00

**Изменение:** Добавлена возможность указания причины отклонения заявки на вывод реферальных средств с отображением полных данных заявки.

**Что изменилось:**
- При нажатии кнопки "❌ Отклонить" администратор видит полные данные заявки (пользователь, сумма, способ вывода, банк, реквизиты)
- Администратор должен указать причину отклонения
- Причина отклонения отправляется пользователю в виде уведомления с полными данными заявки
- В сообщении с заявкой сохраняется информация о причине отклонения
- Улучшен UX: пользователь получает конкретную информацию о причине отклонения заявки и видит все данные своей заявки

**Примеры причин отклонения:**
- "Ошибка в реквизитах"
- "Высокая комиссия банка"
- "Некорректный номер телефона"
- "Некорректный номер карты"

**Пример сообщения для администратора при запросе причины:**
```
📝 Укажите причину отклонения заявки

Данные заявки пользователя:
👤 Пользователь: @username
💰 Сумма: 250.00 RUB
📱 Способ вывода: по номеру телефона
🏦 Банк: Сбербанк
📱 Номер телефона: +79991234567

Напишите причину отклонения заявки. Это сообщение будет отправлено пользователю.
```

**Пример сообщения для пользователя при отклонении:**
```
❌ Ваша заявка на вывод отклонена

Данные вашей заявки:
👤 Пользователь: @username
💰 Сумма: 250.00 RUB
📱 Способ вывода: по номеру телефона
🏦 Банк: Сбербанк
📱 Номер телефона: +79991234567

⚠️ Причина: Ошибка в реквизитах
Пожалуйста, проверьте корректность реквизитов и попробуйте снова.
```

**Код:**
```python
# src/shop_bot/bot/handlers.py:141-142
class DeclineWithdrawStates(StatesGroup):
    waiting_for_decline_reason = State()
```

**Обработчик запроса причины:**
```python
# src/shop_bot/bot/handlers.py:1813-1892
@user_router.callback_query(F.data.startswith("decline_withdraw_"))
async def decline_withdraw_callback(callback: types.CallbackQuery, state: FSMContext):
    user_id = int(callback.data.split("_")[-1])
    user = get_user(user_id)
    
    # Извлекаем данные заявки из текста сообщения
    message_text = callback.message.text or callback.message.caption or ""
    
    # Парсим данные из сообщения
    username_match = re.search(r'👤 Пользователь: @?([^\s]+)', message_text)
    amount_match = re.search(r'💰 Сумма: ([0-9.]+) RUB', message_text)
    method_match = re.search(r'📱 Способ вывода: ([^\n]+)', message_text)
    bank_match = re.search(r'🏦 Банк: ([^\n]+)', message_text)
    phone_match = re.search(r'📱 Номер телефона: ([^\n]+)', message_text)
    card_match = re.search(r'💳 Номер карты: ([^\n]+)', message_text)
    
    # Сохраняем все данные в состоянии
    await state.update_data(
        decline_user_id=user_id,
        decline_message_id=callback.message.message_id,
        decline_username=username,
        decline_amount=amount,
        decline_method_text=method_text,
        decline_bank_name=bank_name,
        decline_details=details,
        decline_method_icon=method_icon
    )
    
    # Формируем текст с полными данными заявки
    request_text = (
        f"📝 <b>Укажите причину отклонения заявки</b>\n\n"
        f"<b>Данные заявки пользователя:</b>\n"
        f"👤 Пользователь: @{username}\n"
        f"💰 Сумма: {amount} RUB\n"
        f"{method_icon} Способ вывода: {method_text}"
    )
    
    if bank_name:
        request_text += f"\n🏦 Банк: {bank_name}"
    
    if phone:
        request_text += f"\n📱 Номер телефона: {phone}"
    elif card:
        request_text += f"\n💳 Номер карты: {card}"
    
    request_text += "\n\nНапишите причину отклонения заявки. Это сообщение будет отправлено пользователю."
    
    await callback.message.edit_text(request_text, parse_mode="HTML")
    await state.set_state(DeclineWithdrawStates.waiting_for_decline_reason)
```

**Обработчик получения причины (поддерживает текст и фото):**
```python
# src/shop_bot/bot/handlers.py:1913-2029
@user_router.message(DeclineWithdrawStates.waiting_for_decline_reason)
async def decline_withdraw_reason_handler(message: types.Message, state: FSMContext):
    data = await state.get_data()
    user_id = data.get('decline_user_id')
    
    # Получаем текст причины (может быть в тексте сообщения или в подписи к фото)
    reason = message.text or message.caption or ""
    
    # Если есть фото, отправляем фото с текстом
    if message.photo:
        photo = message.photo[-1]
        await message.bot.send_photo(
            user_id,
            photo.file_id,
            caption=user_message,
            parse_mode="HTML"
        )
    else:
        # Отправляем только текст
        await message.bot.send_message(
            user_id,
            user_message,
            parse_mode="HTML"
        )
    
    # Обновляем сообщение с заявкой
    decline_status = f"📝 <b>Причина:</b> {reason}"
    if message.photo:
        decline_status += " (со скриншотом)"
    
    await message.bot.edit_message_text(
        f"❌ <b>Заявка отклонена</b>\n"
        f"👤 Пользователь: {username} (ID: <code>{user_id}</code>)\n\n"
        f"{decline_status}",
        chat_id=admin_id,
        message_id=message_id,
        parse_mode="HTML"
    )
    
    await state.clear()
```

**Новое:** Теперь можно отправлять фото (скриншот ошибки) вместе с текстом причины отклонения. Фото будет отправлено пользователю вместе с причиной.

**Файлы:** `src/shop_bot/bot/handlers.py`

### Улучшение от 14.10.2025 00:12

**Изменение:** Улучшен процесс вывода средств с выбором банка.

**Что изменилось:**
- Добавлена метка "(Рекомендуемый)" для вывода по номеру телефона
- Добавлен отдельный шаг выбора банка при выводе на телефон
- Создан список популярных банков: Сбербанк, ВТБ, Альфа-Банк, Тинькофф, Газпромбанк, Райффайзенбанк, Другой банк
- Добавлена информация о комиссии банка (до 50 рублей), которая оплачивается нами
- В заявке для администратора теперь отдельно отображаются банк и номер телефона
- Для вывода на карту добавлена отдельная строка "Номер карты"
- Улучшен UX: пользователь видит выбранный банк перед вводом номера телефона

**Код выбора банка:**
```python
# src/shop_bot/bot/handlers.py:1535-1571
if method == "phone":
    text = (
        "🏦 <b>Выбор банка для перевода</b>\n\n"
        "Выберите банк, на который будет произведен перевод.\n\n"
        "💡 <i>Комиссия банка (до 50 рублей) оплачивается нами.</i>"
    )
    
    # Создаем клавиатуру с популярными банками
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🏦 Сбербанк", callback_data="bank_sberbank")
        ],
        [
            InlineKeyboardButton(text="🏦 ВТБ", callback_data="bank_vtb")
        ],
        # ... остальные банки
    ])
```

**Обработчик выбора банка:**
```python
# src/shop_bot/bot/handlers.py:1582-1613
@user_router.callback_query(WithdrawStates.waiting_for_bank, F.data.startswith("bank_"))
@registration_required
async def withdraw_bank_handler(callback: types.CallbackQuery, state: FSMContext):
    bank_key = callback.data.replace("bank_", "")
    bank_names = {
        "sberbank": "Сбербанк",
        "vtb": "ВТБ",
        "alfabank": "Альфа-Банк",
        "tinkoff": "Тинькофф",
        "gazprombank": "Газпромбанк",
        "raiffeisenbank": "Райффайзенбанк",
        "other": "Другой банк"
    }
    bank_name = bank_names.get(bank_key, "Неизвестный банк")
    
    # Сохраняем выбранный банк в состоянии
    await state.update_data(bank_name=bank_name)
    
    # Просим ввести номер телефона
    text = (
        "📱 <b>Ввод номера телефона</b>\n\n"
        f"Выбран банк: <b>{bank_name}</b>\n\n"
        "Пожалуйста, отправьте номер телефона для перевода.\n\n"
        "Формат: +7XXXXXXXXXX"
    )
```

**Отображение заявки с банком:**
```python
# src/shop_bot/bot/handlers.py:1648-1667
if method == "phone" and bank_name:
    # Для телефона показываем банк и номер телефона
    text = (
        f"💸 <b>Заявка на вывод реферальных средств</b>\n"
        f"👤 Пользователь: @{username_safe} (ID: <code>{user_id}</code>)\n"
        f"💰 Сумма: <b>{balance:.2f} RUB</b>\n"
        f"{method_icon} Способ вывода: <b>{method_text}</b>\n"
        f"🏦 Банк: <b>{bank_name}</b>\n"
        f"📱 Номер телефона: <code>{details_safe}</code>"
    )
```

**Файлы:** `src/shop_bot/bot/handlers.py`

### Улучшение от 14.10.2025 00:05

**Изменение:** Добавлен выбор способа вывода средств в реферальной программе.

**Что изменилось:**
- Перед вводом реквизитов пользователь теперь выбирает способ вывода через кнопки
- Доступны два способа: "📱 По номеру телефона" и "💳 По номеру банковской карты"
- Выбранный способ вывода отображается в заявке для администратора
- Добавлена иконка способа вывода (📱 для телефона, 💳 для карты) в сообщении админу
- Улучшен UX: пользователь видит формат ввода реквизитов в зависимости от выбранного способа

**Код:**
```python
# src/shop_bot/bot/handlers.py:1495-1519
@user_router.callback_query(F.data == "withdraw_request")
@registration_required
async def withdraw_request_handler(callback: types.CallbackQuery, state: FSMContext):
    # Создаем клавиатуру для выбора способа вывода
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📱 По номеру телефона", callback_data="withdraw_method_phone")
        ],
        [
            InlineKeyboardButton(text="💳 По номеру банковской карты", callback_data="withdraw_method_card")
        ],
        [
            InlineKeyboardButton(text="⬅️ Назад", callback_data="show_referral_program")
        ]
    ])
    
    await callback.message.edit_text(
        "💸 <b>Вывод реферальных средств</b>\n\n"
        "Выберите способ вывода средств:",
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    await state.set_state(WithdrawStates.waiting_for_payment_method)
```

**Обработчик выбора способа:**
```python
# src/shop_bot/bot/handlers.py:1521-1548
@user_router.callback_query(WithdrawStates.waiting_for_payment_method, F.data.in_(["withdraw_method_phone", "withdraw_method_card"]))
@registration_required
async def withdraw_method_handler(callback: types.CallbackQuery, state: FSMContext):
    method = "phone" if callback.data == "withdraw_method_phone" else "card"
    method_text = "по номеру телефона" if method == "phone" else "по номеру банковской карты"
    
    # Сохраняем способ вывода в состоянии
    await state.update_data(withdrawal_method=method, withdrawal_method_text=method_text)
    
    # Просим ввести реквизиты
    if method == "phone":
        text = (
            "📱 <b>Вывод по номеру телефона</b>\n\n"
            "Пожалуйста, отправьте номер телефона и банк для перевода.\n\n"
            "Формат: +7XXXXXXXXXX, название банка"
        )
    else:
        text = (
            "💳 <b>Вывод по номеру банковской карты</b>\n\n"
            "Пожалуйста, отправьте номер банковской карты для перевода.\n\n"
            "Формат: XXXX XXXX XXXX XXXX"
        )
    
    await callback.message.edit_text(text, parse_mode="HTML")
    await state.set_state(WithdrawStates.waiting_for_details)
```

**Отображение способа вывода в заявке:**
```python
# src/shop_bot/bot/handlers.py:1550-1588
# Получаем способ вывода из состояния
data = await state.get_data()
method = data.get('withdrawal_method', 'unknown')
method_text = data.get('withdrawal_method_text', 'не указан')

# Определяем иконку в зависимости от способа вывода
method_icon = "📱" if method == "phone" else "💳"

text = (
    f"💸 <b>Заявка на вывод реферальных средств</b>\n"
    f"👤 Пользователь: @{username_safe} (ID: <code>{user_id}</code>)\n"
    f"💰 Сумма: <b>{balance:.2f} RUB</b>\n"
    f"{method_icon} Способ вывода: <b>{method_text}</b>\n"
    f"📄 Реквизиты: <code>{details_safe}</code>"
)
```

**Файлы:** `src/shop_bot/bot/handlers.py`

### Улучшение от 14.10.2025 00:01

**Изменение:** Заменены команды на inline-кнопки для одобрения/отклонения заявок на вывод.

**Что изменилось:**
- Вместо команд `/approve_withdraw {user_id}` и `/decline_withdraw {user_id}` теперь используются inline-кнопки
- Добавлены кнопки "✅ Одобрить" и "❌ Отклонить" в сообщении с заявкой
- После нажатия кнопки сообщение обновляется с информацией о статусе заявки
- Улучшен UX: больше не нужно копировать команды

**Код:**
```python
# src/shop_bot/bot/handlers.py:1534-1540
keyboard = InlineKeyboardMarkup(inline_keyboard=[
    [
        InlineKeyboardButton(text="✅ Одобрить", callback_data=f"approve_withdraw_{user_id}"),
        InlineKeyboardButton(text="❌ Отклонить", callback_data=f"decline_withdraw_{user_id}")
    ]
])
```

**Обработка ошибок парсинга HTML:**
Добавлена автоматическая обработка ошибок парсинга HTML-сущностей:
- При ошибке "can't parse entities" сообщение отправляется без HTML-форматирования
- Ошибка "unsupported start tag" теперь отображается как "Неподдерживаемый HTML-тег в сообщении"

**Файлы:** `src/shop_bot/bot/handlers.py`, `src/shop_bot/utils/error_handler.py`

### Исправление от 09.01.2025

**Проблема:** В уведомлении рефереру отображался username покупателя вместо username реферала.

**Исправление:**
```python
# Было:
referrer_username = user_data.get('username', 'пользователь')

# Стало:
buyer_username = user_data.get('username', 'пользователь')
```

**Файл:** `src/shop_bot/bot/handlers.py:4804`

## Примеры использования

### Пример 1: Регистрация по реферальной ссылке

```
Пользователь A (ID: 12345) → Реферальная ссылка: https://t.me/bot?start=ref_12345
Пользователь B → Переходит по ссылке → Регистрация → referred_by = 12345
```

### Пример 2: Покупка реферала

```
Пользователь B (реферал) → Покупает тариф за 1000 RUB
→ Скидка 5% = 50 RUB → Финальная цена = 950 RUB
→ Реферер получает 10% от 950 RUB = 95 RUB
→ Реферер получает уведомление: "Ваш реферал @username совершил покупку на сумму 950.00 RUB! На ваш баланс начислено вознаграждение: 95.00 RUB."
```

### Пример 3: Вывод средств

```
Реферер → Баланс: 250 RUB → Заявка на вывод → Администратор → Одобрение
→ Баланс обнулен → Уведомление: "Ваша заявка на вывод 250.00 RUB одобрена."
```

## Рекомендации

1. **Мониторинг:** Регулярно проверяйте статистику рефералов и начислений
2. **Модерация:** Проверяйте заявки на вывод перед одобрением
3. **Уведомления:** Убедитесь, что рефереры получают уведомления о покупках
4. **Документация:** Информируйте пользователей о реферальной программе

## Улучшение от 19.01.2025 12:45

**Изменение:** Добавлена поддержка отправки скриншотов при отклонении заявки на вывод.

**Что изменилось:**
- Теперь можно отправить фото (скриншот ошибки) вместе с текстом причины отклонения
- Фото отправляется пользователю вместе с причиной отклонения заявки
- Улучшена обработка ошибок получения данных из состояния FSM
- Добавлено логирование ошибок для диагностики проблем с получением данных заявки
- Обновлен текст запроса причины отклонения с указанием возможности отправки фото

**Как использовать:**
1. Нажмите кнопку "❌ Отклонить" в заявке на вывод
2. Введите причину отклонения текстом ИЛИ отправьте фото с подписью (например, скриншот ошибки)
3. Пользователь получит сообщение с причиной отклонения (и фото, если оно было отправлено)

**Код:**
```python
# src/shop_bot/bot/handlers.py:1913-2029
@user_router.message(DeclineWithdrawStates.waiting_for_decline_reason)
async def decline_withdraw_reason_handler(message: types.Message, state: FSMContext):
    # Получаем текст причины (может быть в тексте сообщения или в подписи к фото)
    reason = message.text or message.caption or ""
    
    # Если есть фото, отправляем фото с текстом
    if message.photo:
        photo = message.photo[-1]
        await message.bot.send_photo(
            user_id,
            photo.file_id,
            caption=user_message,
            parse_mode="HTML"
        )
    else:
        # Отправляем только текст
        await message.bot.send_message(
            user_id,
            user_message,
            parse_mode="HTML"
        )
```

**Файлы:** `src/shop_bot/bot/handlers.py`

## Поддержка

При возникновении проблем с реферальной программой:
1. Проверьте настройки в таблице `settings`
2. Проверьте логи на наличие ошибок
3. Убедитесь, что пользователь зарегистрирован по реферальной ссылке
4. Проверьте, что реферер существует в базе данных

---

**Документация актуальна на:** 19.01.2025 12:00  
**Версия:** 1.4.0

