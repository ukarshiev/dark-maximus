<!-- 6aa3ac51-5ce0-4838-ac77-837c92728af4 ef7f5c6e-cd60-42d5-badd-138a4a6c2944 -->
# Исправление потери сессии при проксировании запросов к allure-service

## Проблема

При переходе на `/allure-docker-service/swagger` или `/allure-docker-service/projects/default/reports/latest/index.html` происходит потеря Flask сессии и редирект на страницу логина.

### Факты из исследования:

1. **allure-service возвращает 308 редирект** при запросе `/swagger` на `/swagger/` (с trailing slash)
2. **allure-service возвращает 200** при запросе `/swagger/` (с trailing slash) - это HTML Swagger UI, не страница логина
3. **В логах видно 302 редиректы** на `/login` при запросах с IP 127.0.0.1 (внутренние редиректы Flask)
4. **Функция proxy вызывается** для `/swagger` (без trailing slash) и возвращает 200
5. **Функция proxy НЕ вызывается** для `/swagger/` (с trailing slash) - декоратор @login_required делает редирект на `/login` до вызова функции

### Корневая причина:

При обработке редиректа 308 от allure-service (`/swagger` -> `/swagger/`) код делает редирект на `/allure-docker-service/swagger/`, но:

- Браузер делает новый запрос на `/allure-docker-service/swagger/`
- Этот запрос проходит через декоратор @login_required
- Декоратор проверяет сессию, но сессия не сохраняется из-за того, что редирект происходит внутри функции proxy, а не через Flask redirect
- В результате сессия теряется и пользователь перенаправляется на `/login`

## Решение

### 1. Исправить обработку редиректов с trailing slash

**Файл:** `apps/allure-homepage/app.py`

**Проблема:** При редиректе 308 от allure-service (`/swagger` -> `/swagger/`) код делает редирект через Flask `redirect()`, но это создает новый запрос, который проходит через декоратор @login_required и теряет сессию.

**Решение:** Вместо редиректа на новый URL, нужно сделать внутренний запрос к allure-service на новый путь и вернуть результат напрямую, без редиректа.

**Изменения:**

- В строках 303-311: вместо `return redirect(f'/allure-docker-service/{location_path}', code=response.status_code)` нужно сделать внутренний запрос к allure-service на новый путь и вернуть результат
- Это позволит избежать нового HTTP запроса от браузера и сохранить сессию

### 2. Улучшить логирование для диагностики

**Файл:** `apps/allure-homepage/app.py`

**Изменения:**

- Добавить логирование в начале функции proxy для отслеживания всех запросов
- Добавить логирование состояния сессии при обработке редиректов
- Добавить логирование при обнаружении редиректов с trailing slash

### 3. Проверить настройки сессии

**Файл:** `src/shop_bot/webhook_server/auth_utils.py`

**Проверка:**

- Убедиться, что `SESSION_COOKIE_PATH` установлен правильно
- Убедиться, что `SESSION_COOKIE_SAMESITE` установлен в 'Lax' (не 'Strict')
- Проверить, что сессия сохраняется при редиректах внутри приложения

## План реализации

1. **Исправить обработку редиректов с trailing slash** (строки 303-311 в `apps/allure-homepage/app.py`):

   - Вместо Flask redirect на новый URL, сделать внутренний запрос к allure-service
   - Вернуть результат напрямую, без редиректа браузера
   - Это сохранит сессию и избежит повторной проверки @login_required

2. **Улучшить логирование**:

   - Добавить логирование в начале функции proxy
   - Добавить логирование состояния сессии
   - Добавить логирование при обработке редиректов

3. **Протестировать исправление**:

   - Проверить переход на `/allure-docker-service/swagger`
   - Проверить переход на `/allure-docker-service/projects/default/reports/latest/index.html`
   - Убедиться, что сессия сохраняется и пользователь не перенаправляется на `/login`

## Технические детали

### Текущая логика (строки 303-311):

```python
if location.endswith('/') and not path.endswith('/'):
    location_path = location.replace(ALLURE_SERVICE_URL + '/allure-docker-service/', '')
    location_path = location_path.replace('/allure-docker-service/', '')
    if location_path == path + '/':
        logger.info(f"Редирект на путь с trailing slash: {path} -> {location_path}, делаю редирект")
        return redirect(f'/allure-docker-service/{location_path}', code=response.status_code)
```

### Новая логика:

```python
if location.endswith('/') and not path.endswith('/'):
    location_path = location.replace(ALLURE_SERVICE_URL + '/allure-docker-service/', '')
    location_path = location_path.replace('/allure-docker-service/', '')
    if location_path == path + '/':
        logger.info(f"Редирект на путь с trailing slash: {path} -> {location_path}, делаю внутренний запрос")
        # Делаем внутренний запрос к allure-service на новый путь, без редиректа браузера
        new_target_url = urljoin(ALLURE_SERVICE_URL + '/allure-docker-service/', location_path)
        # Повторяем запрос к новому URL и возвращаем результат напрямую
        # (код будет добавлен в следующем шаге)
```

## Ожидаемый результат

После исправления:

- При переходе на `/allure-docker-service/swagger` сессия сохраняется
- При переходе на `/allure-docker-service/projects/default/reports/latest/index.html` сессия сохраняется
- Пользователь не перенаправляется на `/login` после авторизации
- Все запросы к allure-service проксируются корректно с сохранением сессии

### To-dos

- [x] 
- [x] 
- [x] 