> Обновлено: 24.09.2025

# API: Пополнение баланса вручную

## Эндпоинт
- Метод: `POST`
- Путь: `/api/topup-balance`
- Аутентификация: админская сессия (`session` cookie)
- Заголовки: `Content-Type: application/json`

## Тело запроса
```json
{
  "user_id": 123456789,
  "amount": 500
}
```
- `user_id` (int, обязательно): Telegram ID пользователя.
- `amount` (number, обязательно): сумма пополнения в RUB (> 0).

## Ответы

### 200 OK
```json
{ "message": "Баланс успешно пополнен" }
```

### 400 Bad Request
```json
{ "message": "Некорректные данные: выберите пользователя и укажите сумму > 0" }
```

### 500 Internal Server Error
```json
{ "message": "Внутренняя ошибка сервера" }
```

## Поведение
- Баланс пользователя увеличивается на указанную сумму.
- В таблицу `transactions` добавляется запись со статусом `paid`, способом оплаты `Balance` и метаданными `{ "type": "balance_topup", "operation": "topup" }`.
- В админке на странице «Платежи» такая операция отображается как «Зачисление».

## Примеры

### CURL
```bash
curl -X POST "http://localhost:1488/api/topup-balance" \
  -H "Content-Type: application/json" \
  -b "session=<admin-session-cookie>" \
  -d '{"user_id":123456789, "amount":300}'
```


