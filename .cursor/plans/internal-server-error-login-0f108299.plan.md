<!-- 0f108299-b9e0-4aed-a364-90396036849b bc88530e-4019-4c9a-86f9-a146a57cd3cc -->
# Исправление ошибки Internal Server Error на /login

## Проблема

При обращении к `http://localhost:50000/login` возникает `Internal Server Error` из-за `AttributeError: 'Flask' object has no attribute 'session_cookie_name'` на строке 433 в `src/shop_bot/webhook_server/app.py`.

## Причина

Код пытается получить имя cookie сессии через несуществующий атрибут `current_app.session_cookie_name`. Flask-Session хранит это значение в конфигурации приложения, а не как атрибут объекта.

## Решение

Заменить `current_app.session_cookie_name` на правильный способ получения имени cookie из конфигурации Flask.

## Изменения

### Файл: `src/shop_bot/webhook_server/app.py`

**Строка 433:** Заменить неправильное обращение к атрибуту на получение из конфигурации:

```python
# Было:
cookie_name = current_app.session_cookie_name

# Станет:
cookie_name = current_app.config.get('SESSION_COOKIE_NAME', 'session')
```

Flask-Session использует конфигурацию `SESSION_COOKIE_NAME` (по умолчанию 'session'), поэтому нужно получать значение через `config.get()`.

## Тестирование

После исправления проверить:

1. GET запрос на `/login` - должна отображаться страница входа
2. POST запрос на `/login` с корректными учетными данными - должен происходить редирект на dashboard без ошибок
3. Проверить логи - не должно быть AttributeError

## Дополнительно

Это исправление не влияет на функциональность, только на логирование информации о cookie. Если логирование не критично, можно также обернуть этот блок в try-except для предотвращения подобных ошибок в будущем.

### To-dos

- [ ] Заменить current_app.session_cookie_name на current_app.config.get('SESSION_COOKIE_NAME', 'session') в строке 433 файла src/shop_bot/webhook_server/app.py
- [ ] Протестировать GET /login - должна отображаться страница входа без ошибок
- [ ] Протестировать POST /login с корректными учетными данными - должен происходить редирект без ошибок