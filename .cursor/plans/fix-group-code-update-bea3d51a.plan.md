<!-- bea3d51a-db58-4e4a-8a2e-b962e9dcf4c4 a8cf9420-0059-4be1-9a11-88a0d94b315d -->
# План исправления бага с обновлением кода группы

## Корневая причина

**Проблема найдена в `src/shop_bot/webhook_server/app.py:4830`:**

```python
group_code = data.get('group_code', '').strip()
```

Когда ключ `group_code` отсутствует в JSON, `.get()` возвращает пустую строку `''` (default значение), а не `None`. Это приводит к тому, что в функцию `update_user_group()` всегда передается строка (пустая или с значением), но никогда `None`.

**Вторая проблема в `src/shop_bot/data_manager/database.py:6941`:**

Условие проверяет `group_code.strip() == ""`, но если передана пустая строка, то функция генерирует новый код из названия группы, игнорируя переданное значение.

## Решение

### 1. Исправить API endpoint (app.py)

**Файл**: `src/shop_bot/webhook_server/app.py`

**Строки**: 4827-4830

**Текущий код**:

```python
data = request.get_json()
group_name = data.get('group_name', '').strip()
group_description = data.get('group_description', '').strip()
group_code = data.get('group_code', '').strip()
```

**Исправленный код**:

```python
data = request.get_json()
group_name = data.get('group_name', '').strip()
group_description = data.get('group_description', '').strip()
# Если group_code отсутствует или пустой, передаем None
group_code = data.get('group_code')
if group_code is not None:
    group_code = group_code.strip()
    if not group_code:  # Если после strip пустая строка
        group_code = None
```

**Обоснование**: Теперь API endpoint корректно различает три случая:

- Ключ отсутствует → `None`
- Ключ есть, но пустая строка → `None`
- Ключ есть со значением → значение после `.strip()`

### 2. Улучшить логику в database.py (опционально, но рекомендуется)

**Файл**: `src/shop_bot/data_manager/database.py`

**Строки**: 6940-6959

**Текущий код работает корректно**, но можно улучшить читаемость:

```python
# Если group_code не указан (None) или пустая строка, генерируем его из group_name
if group_code is None or group_code.strip() == "":
```

**Улучшенный код** (опционально):

```python
# Если group_code не указан, генерируем его из group_name
if not group_code:  # None или пустая строка
```

**Обоснование**: После исправления API endpoint, `group_code` всегда будет либо `None`, либо непустой строкой.

### 3. Добавить логирование для отладки

**Файл**: `src/shop_bot/webhook_server/app.py`

**После строки 4830**

**Добавить**:

```python
logger.debug(f"API update_user_group: group_id={group_id}, group_name={group_name}, group_code={group_code}")
```

**Файл**: `src/shop_bot/data_manager/database.py`

**После строки 6938**

**Добавить**:

```python
logging.debug(f"update_user_group called: group_id={group_id}, group_name={group_name}, group_code={group_code}")
```

### 4. Тестирование

После внесения изменений протестировать:

1. **Изменение только кода группы** - должно сохраниться
2. **Изменение только названия группы** - код должен сгенерироваться автоматически
3. **Изменение и названия, и кода** - оба должны сохраниться
4. **Создание новой группы без кода** - код должен сгенерироваться

### 5. Обновить CHANGELOG

**Файл**: `CHANGELOG.md`

Добавить запись о критическом исправлении бага с обновлением кода группы.

## Проверка результата

После исправления выполнить:

```python
python -c "import sqlite3; conn = sqlite3.connect('users.db'); cursor = conn.cursor(); cursor.execute('SELECT group_id, group_name, group_code FROM user_groups WHERE group_id = 148'); result = cursor.fetchone(); print(f'ID: {result[0]}, Name: {result[1]}, Code: {result[2]}'); conn.close()"
```

Ожидаемый результат: `Code: test_fixed_code` (или другое значение, которое было введено)

## Best Practices применены

1. **Явная обработка None vs пустая строка** - различаем отсутствие значения и пустое значение
2. **Логирование для отладки** - позволяет отслеживать проблемы в production
3. **Минимальные изменения** - исправляем только проблемное место, не трогая рабочий код
4. **Обратная совместимость** - изменения не ломают существующий функционал

### To-dos

- [ ] Исправить обработку group_code в API endpoint (app.py:4827-4830)
- [ ] Добавить debug логирование в API endpoint и database.py
- [ ] Протестировать все сценарии изменения группы
- [ ] Проверить, что изменения сохраняются в базе данных
- [ ] Обновить CHANGELOG.md и pyproject.toml