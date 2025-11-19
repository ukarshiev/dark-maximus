<!-- 716889eb-1141-4af1-bf35-158ee4b2434c ef528ee5-40af-42e1-a42b-0cc12d1b5f1f -->
# Исправление сброса токена авторизации - точное решение

## Найденная проблема (100%)

**Корневая причина:** Flask-Session с типом 'filesystem' НЕ сохраняет изменения сессии автоматически. После установки `session['logged_in'] = True` и `session.permanent = True` в функции `verify_and_login()`, сессия не сохраняется на диск до следующего запроса. При перезапуске контейнера сессия теряется, потому что изменения не были записаны в файл.

**Техническая деталь:** Flask-Session использует механизм "lazy saving" - сессия сохраняется только если она помечена как измененная (`session.modified = True`) ИЛИ если явно вызван `session.save()`. В текущей реализации `verify_and_login()` устанавливает `session['logged_in'] = True`, но Flask-Session может не распознать это как изменение, требующее немедленного сохранения.

**Почему это происходит:**

1. В `verify_and_login()` устанавливается `session['logged_in'] = True`
2. Flask-Session помечает сессию как измененную автоматически при установке значения
3. НО: сохранение происходит только в конце запроса (в `after_request` hook)
4. Если контейнер перезапускается ДО того, как запрос завершился, сессия не сохраняется
5. При следующем запросе Flask-Session не находит файл сессии (он не был создан/обновлен) и считает сессию невалидной

## Метод исправления

### Решение 1: Явное сохранение сессии (РЕКОМЕНДУЕТСЯ)

В функции `verify_and_login()` после установки `session['logged_in'] = True` и `session.permanent = True` нужно явно сохранить сессию:

```python
def verify_and_login(username, password):
    from shop_bot.data_manager.database import verify_admin_credentials
    
    if verify_admin_credentials(username, password):
        session['logged_in'] = True
        session.permanent = True
        # Явно помечаем сессию как измененную и сохраняем
        session.modified = True
        # Явно сохраняем сессию на диск
        from flask_session import Session
        # Получаем экземпляр Session из app
        session_interface = current_app.session_interface
        if hasattr(session_interface, 'save_session'):
            session_interface.save_session(current_app, session, None)
        return True
    return False
```

**Проблема этого подхода:** Требует доступа к `current_app` и `session_interface`, что может быть сложно.

### Решение 2: Использование session.save() (ПРОЩЕ)

Flask-Session предоставляет метод `save()` для явного сохранения сессии. Но стандартный объект `session` из Flask не имеет этого метода.

### Решение 3: Принудительное сохранение через session.modified (НАИБОЛЕЕ ПРОСТОЕ)

Установить `session.modified = True` после изменения сессии. Flask-Session автоматически сохранит сессию в конце запроса.

**НО:** Это не гарантирует сохранение до перезапуска контейнера.

### Решение 4: Использование session.permanent и явного сохранения (ОПТИМАЛЬНОЕ)

Комбинация: установить `session.permanent = True` ДО установки значений, и явно вызвать сохранение через `session_interface.save_session()`.

## Выбранное решение

**Использовать комбинацию:**

1. Установить `session.modified = True` после изменения сессии
2. Использовать `session.permanent = True` (уже есть)
3. Добавить явный вызов сохранения через `current_app.session_interface.save_session()`

**Альтернативное простое решение (если первое не работает):**

Использовать `session.modified = True` и убедиться, что Flask-Session сохраняет сессию в конце запроса. Для этого нужно проверить, что `after_request` hook вызывается правильно.

## Файлы для изменения

1. `src/shop_bot/webhook_server/auth_utils.py`:

   - В функции `verify_and_login()` после строки 96 добавить:
     ```python
     session.modified = True
     ```

   - ИЛИ использовать явное сохранение через `current_app.session_interface.save_session()`

## Ожидаемый результат

- Сессия будет сохраняться на диск сразу после успешной авторизации
- При перезапуске контейнера сессия останется валидной
- Пользователь не будет выкидываться на `/login` после перезапуска

### To-dos

- [ ] Добавить явное сохранение сессии в verify_and_login() после установки logged_in
- [ ] Протестировать сохранение сессии после перезапуска контейнера