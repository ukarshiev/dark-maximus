<!-- 1b9e0567-b759-437e-af75-ac5086447f70 c3620d53-9b28-4001-8a47-51fcec481e59 -->
# Исправление проблемы с редиректом Swagger

## Проблема

При переходе на `http://localhost:50005/allure-docker-service/swagger` пользователь видит страницу "Redirecting..." с текстом "You should be redirected automatically to the target URL: http://localhost:50005/allure-docker-service/swagger/".

### Корневая причина

1. При запросе `/swagger` (без trailing slash) allure-service возвращает **HTML-страницу "Redirecting..."** (часть редиректа 308)
2. При запросе `/swagger/` (с trailing slash) allure-service возвращает **реальный HTML Swagger UI**
3. Код в `apps/allure-homepage/app.py` обрабатывает HTTP-редиректы (301, 302, 303, 307, 308), но если allure-service возвращает HTML-страницу "Redirecting..." в теле ответа, эта страница отображается пользователю

### Текущее поведение

- Запрос `/allure-docker-service/swagger` → allure-service возвращает 308 редирект с HTML-страницей "Redirecting..."
- Код обрабатывает редирект 308 и делает внутренний запрос к `/swagger/`
- Но если в ответе есть HTML-страница "Redirecting...", она отображается пользователю

## Решение

### 1. Обработка HTML-страницы "Redirecting..."

**Файл:** `apps/allure-homepage/app.py`

**Изменения:**

1. **Добавить функцию для извлечения URL из HTML-страницы "Redirecting..."** (после строки 113):

   - Функция должна искать паттерн `href="..."` или текст "target URL: ..." в HTML
   - Извлекать URL из найденного паттерна
   - Возвращать путь без базового URL

2. **Обработать HTML-страницу "Redirecting..." в функции `proxy()`** (после строки 385):

   - Проверить, является ли контент HTML-страницей "Redirecting..."
   - Если да, извлечь URL из неё
   - Сделать внутренний запрос к этому URL
   - Вернуть результат напрямую, без редиректа браузера

3. **Улучшить обработку редиректов с trailing slash** (строки 305-346):

   - Убедиться, что внутренний запрос к `/swagger/` возвращает реальный контент, а не HTML-страницу "Redirecting..."
   - Если получена HTML-страница "Redirecting...", извлечь URL и сделать еще один внутренний запрос

### 2. Альтернативное решение: предварительная обработка пути

**Файл:** `apps/allure-homepage/app.py`

**Изменения:**

1. **Добавить проверку пути в начале функции `proxy()`** (после строки 232):

   - Если путь `swagger` (без trailing slash), сразу делать запрос к `swagger/` (с trailing slash)
   - Это избежит редиректа и HTML-страницы "Redirecting..."

2. **Применить ту же логику для других путей**, которые могут требовать trailing slash

## План реализации

1. **Добавить функцию для извлечения URL из HTML-страницы "Redirecting..."**

   - Функция `extract_redirect_url_from_html(html_content: str) -> str | None`
   - Ищет паттерны: `href="..."`, `target URL: ...`, `location.href = ...`

2. **Обработать HTML-страницу "Redirecting..." в функции `proxy()`**

   - После проверки на страницу логина (строка 385)
   - Проверить, является ли контент HTML-страницей "Redirecting..."
   - Если да, извлечь URL и сделать внутренний запрос

3. **Улучшить обработку редиректов с trailing slash**

   - Убедиться, что внутренний запрос возвращает реальный контент
   - Если получена HTML-страница "Redirecting...", обработать её

4. **Протестировать исправление**

   - Проверить переход на `/allure-docker-service/swagger`
   - Убедиться, что отображается Swagger UI, а не страница "Redirecting..."

## Технические детали

### Функция извлечения URL из HTML

```python
def extract_redirect_url_from_html(html_content: str) -> str | None:
    """
    Извлекает URL из HTML-страницы "Redirecting..." от allure-service.
    
    Args:
        html_content: HTML-контент страницы
        
    Returns:
        str: Путь без базового URL или None, если URL не найден
    """
    # Ищем паттерн href="..."
    import re
    patterns = [
        r'href="([^"]+)"',  # href="http://..."
        r'target URL: <a href="([^"]+)"',  # target URL: <a href="...">
        r'target URL: ([^\s<]+)',  # target URL: http://...
    ]
    
    for pattern in patterns:
        match = re.search(pattern, html_content, re.IGNORECASE)
        if match:
            url = match.group(1)
            # Убираем базовый URL, оставляем только путь
            url = url.replace('http://localhost:50005/allure-docker-service/', '')
            url = url.replace('http://localhost:50004/allure-docker-service/', '')
            url = url.replace('http://allure-service:5050/allure-docker-service/', '')
            if url.startswith('/'):
                url = url[1:]
            return url
    
    return None
```

### Обработка HTML-страницы "Redirecting..." в функции proxy()

```python
# После строки 385 (проверка на страницу логина)
# Проверяем, является ли контент HTML-страницей "Redirecting..."
if content_type.startswith('text/html'):
    try:
        content_str = content.decode('utf-8', errors='ignore')
        if 'Redirecting...' in content_str and 'target URL' in content_str.lower():
            logger.info("Обнаружена HTML-страница 'Redirecting...', извлекаю URL")
            redirect_url = extract_redirect_url_from_html(content_str)
            if redirect_url:
                logger.info(f"Извлечен URL из HTML: {redirect_url}, делаю внутренний запрос")
                # Делаем внутренний запрос к allure-service на новый путь
                new_target_url = urljoin(ALLURE_SERVICE_URL + '/allure-docker-service/', redirect_url)
                internal_response = requests.request(
                    method=method,
                    url=new_target_url,
                    params=params,
                    headers=headers,
                    data=data,
                    stream=True,
                    timeout=60,
                    allow_redirects=False
                )
                # Используем ответ от внутреннего запроса
                response = internal_response
                content = response.content
                content_type = response.headers.get('Content-Type', '')
                logger.info(f"Внутренний запрос к {new_target_url} завершен: status={response.status_code}")
    except Exception as e:
        logger.warning(f"Ошибка при обработке HTML-страницы 'Redirecting...': {e}")
```

## Ожидаемый результат

После исправления:

- При переходе на `/allure-docker-service/swagger` отображается Swagger UI, а не страница "Redirecting..."
- Редиректы обрабатываются автоматически без отображения промежуточных страниц
- Все запросы к allure-service проксируются корректно

### To-dos

- [ ] Добавить функцию extract_redirect_url_from_html() для извлечения URL из HTML-страницы 'Redirecting...'
- [ ] Обработать HTML-страницу 'Redirecting...' в функции proxy() после проверки на страницу логина
- [ ] Улучшить обработку редиректов с trailing slash, чтобы избежать HTML-страницы Redirecting...
- [ ] Протестировать исправление: проверить переход на /allure-docker-service/swagger и убедиться, что отображается Swagger UI