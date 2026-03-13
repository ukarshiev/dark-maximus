# 🔌 API Документация

> REST API для интеграции с админ-панелью Dark Maximus
> Обновлено: 13.03.2026

## 📋 Содержание

1. [Общая информация](#общая-информация)
2. [Авторизация](#авторизация)
3. [Эндпоинты](#эндпоинты)
4. [Формат ответов](#формат-ответов)
5. [Примеры использования](#примеры-использования)
6. [Обработка ошибок](#обработка-ошибок)

---

## Общая информация

### Базовый URL

```
Разработка: http://localhost:50001
Продакшн: https://your-domain.com
```

### Версия API

Текущая версия: **v1**

### Формат данных

- **Content-Type:** `application/json`
- **Accept:** `application/json`

---

## Авторизация

### Сессионная авторизация

Для большинства эндпоинтов требуется авторизация через сессию:

1. Войдите в админ-панель через браузер
2. Сессия сохранится в cookies
3. Все последующие запросы будут авторизованы

### Токен авторизации (в разработке)

```http
Authorization: Bearer YOUR_API_TOKEN
```

---

## Эндпоинты

### 👥 Пользователи

#### Получить детали пользователя

```http
GET /api/user-details/<user_id>
```

**Параметры:**
- `user_id` (path, required) — Telegram ID пользователя

**Ответ:**
```json
{
  "success": true,
  "data": {
    "user_id": 123456789,
    "username": "username",
    "first_name": "Имя",
    "last_name": "Фамилия",
    "balance": 100.50,
    "keys_count": 2,
    "registration_date": "2025-01-01T00:00:00"
  }
}
```

#### Обновить пользователя

```http
POST /api/update-user/<user_id>
```

**Тело запроса:**
```json
{
  "first_name": "Новое имя",
  "last_name": "Новая фамилия"
}
```

#### Пополнить баланс

```http
POST /api/topup-balance
```

**Тело запроса:**
```json
{
  "user_id": 123456789,
  "amount": 100.00,
  "description": "Пополнение баланса"
}
```

#### Получить историю платежей

```http
GET /api/user-payments/<user_id>
```

#### Получить ключи пользователя

```http
GET /api/user-keys/<user_id>
```

#### Получить баланс пользователя

```http
GET /api/user-balance/<user_id>
```

#### Получить заработанную сумму

```http
GET /api/user-earned/<user_id>
```

#### Получить уведомления пользователя

```http
GET /api/user-notifications/<user_id>
```

#### Поиск пользователей

```http
GET /api/search-users?query=username&limit=10
```

**Параметры:**
- `query` (query, optional) — поисковый запрос
- `limit` (query, optional) — лимит результатов (по умолчанию 10)

---

### 🔑 Ключи

#### Получить детали ключа

```http
GET /api/key/<key_id>
```

#### Включить/выключить ключ

```http
POST /api/toggle-key-enabled
```

**Тело запроса:**
```json
{
  "key_id": 123,
  "enabled": true
}
```

#### Обновить все ключи

```http
POST /refresh-keys
```

Назначение: только синхронизация полей ключей в БД по данным 3x-ui (без удаления клиентов на панели). Синхронизация выполняется только по привязанному inbound хоста (`host_inbound_id`).

#### Обновить ключи пользователя

```http
POST /refresh-user-keys
```

**Тело запроса:**
```json
{
  "user_id": 123456789
}
```

Примечание: по политике безопасности планировщик не удаляет ключи и orphan-клиентов с панели; выполняются только чтение и обновление. Удаление из панели этими эндпоинтами не выполняется.

#### Удалить ошибочные ключи

```http
POST /delete-error-keys
```

---

### 💰 Транзакции

#### Получить детали транзакции

```http
GET /api/transaction/<transaction_id>
```

#### Обновить транзакции

```http
POST /refresh-transactions
```

#### Проверить платеж

```http
GET /check-payment?user_id=123456789&amount=100
```

**Параметры:**
- `user_id` (query, required) — Telegram ID пользователя
- `amount` (query, required) — сумма платежа

---

### 🎟️ Промокоды

#### Получить список промокодов

```http
GET /api/promo-codes
```

**Ответ:**
```json
{
  "success": true,
  "data": [
    {
      "id": 1,
      "code": "SUMMER2024",
      "discount_percent": 20,
      "discount_amount": 0,
      "discount_bonus": 0,
      "usage_limit": 100,
      "used_count": 5,
      "is_active": true
    }
  ]
}
```

#### Создать промокод

```http
POST /api/promo-codes
```

**Тело запроса:**
```json
{
  "code": "SUMMER2024",
  "discount_percent": 20,
  "discount_amount": 0,
  "discount_bonus": 0,
  "usage_limit": 100,
  "is_active": true
}
```

#### Получить детали промокода

```http
GET /api/promo-codes/<promo_id>
```

#### Обновить промокод

```http
PUT /api/promo-codes/<promo_id>
```

**Тело запроса:**
```json
{
  "discount_percent": 25,
  "is_active": true
}
```

#### Удалить промокод

```http
DELETE /api/promo-codes/<promo_id>
```

#### Получить историю использования

```http
GET /api/promo-codes/<promo_id>/usage
```

#### Проверить промокод

```http
POST /api/validate-promo-code
```

**Тело запроса:**
```json
{
  "code": "SUMMER2024",
  "user_id": 123456789
}
```

---

### 🖥️ Хосты

#### Получить список хостов

```http
GET /api/hosts
```

#### Обновить ключи хоста

```http
POST /api/refresh-keys-by-host
```

**Тело запроса:**
```json
{
  "host_name": "Сервер 1"
}
```

---

### 📢 Уведомления

#### Создать уведомление

```http
POST /create-notification
```

**Тело запроса:**
```json
{
  "user_id": 123456789,
  "message": "Текст уведомления",
  "type": "info"
}
```

#### Повторить отправку

```http
POST /resend-notification/<notification_id>
```

---

## Формат ответов

### Успешный ответ

```json
{
  "success": true,
  "data": { ... },
  "message": "Операция выполнена успешно"
}
```

### Ответ с ошибкой

```json
{
  "success": false,
  "error": "Описание ошибки",
  "code": "ERROR_CODE"
}
```

---

## Примеры использования

### Python

```python
import requests

# Базовый URL
BASE_URL = "https://your-domain.com"

# Получить детали пользователя
response = requests.get(f"{BASE_URL}/api/user-details/123456789")
data = response.json()

if data["success"]:
    user = data["data"]
    print(f"Пользователь: {user['username']}")
    print(f"Баланс: {user['balance']} руб.")
```

### JavaScript

```javascript
const BASE_URL = "https://your-domain.com";

// Получить детали пользователя
fetch(`${BASE_URL}/api/user-details/123456789`)
  .then(response => response.json())
  .then(data => {
    if (data.success) {
      const user = data.data;
      console.log(`Пользователь: ${user.username}`);
      console.log(`Баланс: ${user.balance} руб.`);
    }
  });
```

### cURL

```bash
# Получить детали пользователя
curl -X GET https://your-domain.com/api/user-details/123456789

# Пополнить баланс
curl -X POST https://your-domain.com/api/topup-balance \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": 123456789,
    "amount": 100.00,
    "description": "Пополнение баланса"
  }'
```

---

## Обработка ошибок

### Коды ошибок

| Код | Описание |
|-----|----------|
| `UNAUTHORIZED` | Требуется авторизация |
| `FORBIDDEN` | Доступ запрещен |
| `NOT_FOUND` | Ресурс не найден |
| `VALIDATION_ERROR` | Ошибка валидации данных |
| `INTERNAL_ERROR` | Внутренняя ошибка сервера |

### Пример обработки ошибок

```python
import requests

try:
    response = requests.get(f"{BASE_URL}/api/user-details/123456789")
    data = response.json()
    
    if not data["success"]:
        error_code = data.get("code", "UNKNOWN")
        error_message = data.get("error", "Неизвестная ошибка")
        
        if error_code == "NOT_FOUND":
            print("Пользователь не найден")
        elif error_code == "UNAUTHORIZED":
            print("Требуется авторизация")
        else:
            print(f"Ошибка: {error_message}")
    else:
        # Обработка успешного ответа
        user = data["data"]
        print(f"Пользователь найден: {user['username']}")
        
except requests.exceptions.RequestException as e:
    print(f"Ошибка сети: {e}")
```

---

## Rate Limiting

API имеет ограничения на количество запросов:

- **Общие эндпоинты:** 60 запросов в минуту
- **Авторизация:** 10 попыток в минуту
- **Webhook эндпоинты:** без ограничений

При превышении лимита возвращается ошибка:

```json
{
  "success": false,
  "error": "Too many requests. Please try again later.",
  "code": "RATE_LIMIT_EXCEEDED"
}
```

---

## Webhook эндпоинты

### YooKassa Webhook

```http
POST /yookassa-webhook
```

**Описание:** Принимает уведомления от YooKassa о статусе платежей.

### CryptoBot Webhook

```http
POST /cryptobot-webhook
```

**Описание:** Принимает уведомления от CryptoBot о статусе платежей.

### Heleket Webhook

```http
POST /heleket-webhook
```

**Описание:** Принимает уведомления от Heleket о статусе платежей.

### TON Webhook

```http
POST /ton-webhook
```

**Описание:** Принимает уведомления о TON платежах.

---

## Дополнительные ресурсы

- **[Полное руководство по админ-панели](../guides/admin/admin-panel-guide.md)**
- **[Быстрый старт](../../tutorials/admin-quickstart.md)**
- **[FAQ](../guides/user/faq.md)**

---

**Версия API:** 1.0  
**Последнее обновление:** 2025-01-XX

