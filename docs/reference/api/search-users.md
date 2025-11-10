> Обновлено: 10.11.2025

# API: Поиск пользователей

## Эндпоинт
- Метод: `GET`
- Путь: `/api/search-users`
- Аутентификация: админская сессия (`session` cookie)
- Заголовки: `Accept: application/json` или `*/*`

### Параметры запроса
- `q` (string, обязательно) — часть Telegram ID или username. Регистр игнорируется для username.
- `limit` (int, необязательно) — максимальное число записей, по умолчанию 10, диапазон 1–50.

## Ответы

### 200 OK
```json
{
  "users": [
    {
      "telegram_id": 123456789,
      "username": "example_user",
      "is_banned": false,
      "agreed_to_documents": true,
      "subscription_status": "subscribed",
      "balance": 1250.0
    }
  ]
}
```
- Список пуст, если совпадений нет.

### 400 Bad Request
- Возвращается, когда параметр `q` отсутствует или пуст.

### 500 Internal Server Error
- Возникает при ошибках БД. Логи: `Failed to handle user search...`.

## Примеры

### CURL
```bash
curl "http://localhost:50000/api/search-users?q=karsh" \
  -H "Accept: application/json" \
  -b "session=<admin-session-cookie>"
```

### JavaScript fetch
```js
const resp = await fetch("/api/search-users?q=alex", { credentials: "include" });
const data = await resp.json();
console.log(data.users);
```

## Примечания
- Ответ всегда сериализуется в JSON, даже при `Accept: */*`.
- Для пустых или пробельных запросов возвращается пустой список.
- Контролируйте `limit`, чтобы не перегружать интерфейс суггестов.
