<!-- 4276ec02-8b3a-4ae2-8b53-bc83cbcd2168 924fb031-7cf6-4efd-ae83-c8f03d319f91 -->
# Исправление тестов webhook server users

## Проблема

Два теста падают с ошибкой 400:

1. `test_update_user` - пытается обновить `username` и `fullname`, но эти поля не разрешены в эндпоинте
2. `test_reset_user_trial` - пытается сбросить триал через параметр `reset_trial`, но эндпоинт не обрабатывает этот параметр

## Анализ

Эндпоинт `/api/update-user/<int:user_id>` в `src/shop_bot/webhook_server/app.py` (строка 4408):

- Разрешает только поля: `['fio', 'email', 'group_id', 'balance']` (строка 4424)
- Не обрабатывает `username`, `fullname` и `reset_trial`
- В БД существуют поля `username` и `fullname` (добавляются через ALTER TABLE)
- Функция `reset_trial_used(user_id)` существует в `database.py`

## Решение

### 1. Добавить поддержку `username` и `fullname` в эндпоинт

**Файл:** `src/shop_bot/webhook_server/app.py`

**Строка:** 4424

**Изменение:** Добавить `'username'` и `'fullname'` в список `allowed_fields`

```python
allowed_fields = ['fio', 'email', 'group_id', 'balance', 'username', 'fullname']
```

### 2. Добавить обработку `reset_trial` в эндпоинт

**Файл:** `src/shop_bot/webhook_server/app.py`

**Строка:** После строки 4430 (после проверки `if not update_fields`)

**Изменение:** Добавить обработку параметра `reset_trial` перед основным циклом обновления полей

```python
# Обрабатываем reset_trial отдельно (специальная логика)
if data.get('reset_trial') is True:
    from shop_bot.data_manager.database import reset_trial_used
    reset_trial_used(user_id)
    logger.info(f"Trial reset for user {user_id}")
```

## Тестирование

После исправления:

1. Запустить `test_update_user` - должен проходить
2. Запустить `test_reset_user_trial` - должен проходить  
3. Запустить `test_delete_user_keys` - должен продолжать проходить
4. Проверить отчеты в Allure для подтверждения успешного выполнения

### To-dos

- [ ] Добавить 'username' и 'fullname' в allowed_fields эндпоинта /api/update-user
- [ ] Добавить обработку параметра reset_trial в эндпоинт /api/update-user
- [ ] Запустить тест test_update_user и проверить результат
- [ ] Запустить тест test_reset_user_trial и проверить результат
- [ ] Запустить все три теста вместе и проверить отчеты в Allure