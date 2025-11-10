> Обновлено: 10.11.2025

# API: Получение детальной информации о транзакции

## Эндпоинт
- Метод: `GET`
- Путь: `/api/transaction/<int:transaction_id>`
- Аутентификация: админская сессия (`session` cookie)
- Заголовки: `Content-Type: application/json`

## Параметры URL
- `transaction_id` (int, обязательно): ID транзакции в базе данных

## Ответы

### 200 OK
```json
{
  "status": "success",
  "transaction": {
    "transaction_id": 123,
    "payment_id": "pay_123abc",
    "user_id": 987654321,
    "username": "john_doe",
    "status": "paid",
    "amount_rub": 500.00,
    "amount_currency": 300,
    "currency_name": "Stars",
    "payment_method": "Stars",
    "metadata": {
      "host_name": "server1",
      "plan_name": "Месячный тариф",
      "action": "new",
      "connection_string": "vless://...",
      "stars_paid": 300,
      "stars_rate": "1 ⭐️ = 1.67 RUB"
    },
    "transaction_hash": "tx_hash_123",
    "payment_link": "https://t.me/...",
    "created_date": "2025-10-09 07:00:00"
  }
}
```

### 404 Not Found
```json
{
  "status": "error",
  "message": "Транзакция не найдена"
}
```

### 500 Internal Server Error
```json
{
  "status": "error",
  "message": "Ошибка при загрузке данных транзакции"
}
```

## Поведение
- Возвращает детальную информацию о транзакции по её ID
- Метаданные автоматически парсятся из JSON-строки в объект
- Включает информацию о пользователе, способе оплаты, статусе и всех связанных данных
- Используется для отображения детальной информации в модальном окне на странице "Платежи"

## Примеры использования

### CURL
```bash
curl -X GET "http://localhost:50000/api/transaction/123" \
  -H "Content-Type: application/json" \
  -b "session=<admin-session-cookie>"
```

### JavaScript (Fetch API)
```javascript
fetch('/api/transaction/123')
  .then(response => response.json())
  .then(data => {
    if (data.status === 'success') {
      console.log('Transaction:', data.transaction);
    } else {
      console.error('Error:', data.message);
    }
  })
  .catch(error => console.error('Network error:', error));
```

## Структура отображения в UI

Данные транзакции отображаются в модальном окне (Drawer) со следующими группами:

### 1. Пользователь
- User ID
- Username

### 2. Платеж
- ID транзакции
- Дата создания
- Тип операции (Зачисление, Новый, Продление)
- Способ оплаты
- Сумма (RUB)
- Сумма (валюта)
- Валюта
- Статус
- ID платежа

### 3. Детали платежа
- Хеш транзакции
- Ссылка на оплату

### 4. Детали заказа
- Хост
- План
- Ключ (connection string)

### 5. Метаданные
- JSON в читаемом формате

## Структура метаданных
Поле `metadata` может содержать различные данные в зависимости от типа транзакции:

### Для транзакций покупки/продления VPN:
```json
{
  "host_name": "server1",
  "plan_name": "Месячный тариф",
  "action": "new",  // "new" или "renew"
  "connection_string": "vless://...",
  "is_trial": 0
}
```

### Для транзакций пополнения баланса:
```json
{
  "operation": "topup",
  "type": "balance_topup"
}
```

### Для транзакций Telegram Stars:
```json
{
  "stars_paid": 300,
  "stars_rate": "1 ⭐️ = 1.67 RUB",
  "host_name": "server1",
  "plan_name": "Месячный тариф"
}
```

## Примечания
- Требуется авторизация администратора
- Транзакции других пользователей доступны только администратору
- Метаданные могут быть пустыми или null для некоторых транзакций
- Дата возвращается в формате ISO 8601

