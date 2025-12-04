<!-- c6397e7f-a9a5-4f49-939e-09e36e16f9a9 e1c77d4c-ea68-47bc-a20d-1532bf7fa7f6 -->
# План: Добавление настройки "Прямая ссылка на базу знаний"

## Проблема

На тестовом сервере кнопка "Настройка" после оплаты не работает, так как формируется из `codex_docs_domain + /setup`, что даёт `http://localhost:50002/setup`. Telegram не позволяет использовать HTTP-ссылки в Web App кнопках.

На боевом сервере работает, так как там настроен HTTPS домен.

## Решение

Создать отдельную настройку "Прямая ссылка на базу знаний" в панели, которая будет использоваться вместо `codex_docs_domain + /setup` для кнопки "Настройка".

## Изменения

### 1. Веб-панель: добавление поля настройки

**Файл:** [`src/shop_bot/webhook_server/templates/settings.html`](src/shop_bot/webhook_server/templates/settings.html)

**Действие:** Добавить новое поле после `codex_docs_domain` (после строки 320):

```html
<div class="form-group">
    <label for="setup_direct_link">Прямая ссылка на базу знаний:</label>
    <div class="input-with-button">
        <input
            type="url"
            id="setup_direct_link"
            name="setup_direct_link"
            value="{{ settings.setup_direct_link or '' }}"
            placeholder="https://help.dark-maximus.com/setup"
            title="Прямая ссылка на страницу настройки VPN"
        />
        <button type="button" class="button button-secondary button-sm" onclick="openDomain('setup_direct_link')" title="Открыть ссылку в новой вкладке">
            <i class="fas fa-external-link-alt"></i>
        </button>
    </div>
    <small class="text-muted">Ссылка вшита в кнопку "Настройка" после оплаты. Если не указана, используется домен codex-docs с путём /setup</small>
</div>
```

### 2. Backend: сохранение настройки

**Файл:** [`src/shop_bot/webhook_server/app.py`](src/shop_bot/webhook_server/app.py)

**Действие:** Добавить `'setup_direct_link'` в список `panel_keys` в функции `save_panel_settings()` (строка 1201):

```python
panel_keys = ['panel_login', 'global_domain', 'docs_domain', 'codex_docs_domain', 'setup_direct_link', 'user_cabinet_domain', 'allure_domain', 'admin_timezone', 'server_environment', 'monitoring_max_metrics', 'monitoring_slow_threshold', 'monitoring_cleanup_hours']
```

### 3. Логика кнопки "Настройка": использование прямой ссылки

**Файл:** [`src/shop_bot/bot/keyboards.py`](src/shop_bot/bot/keyboards.py)

**Действие:** Изменить логику формирования `setup_url` (строки 619-635):

```python
# Кнопка настройки - использует setup_direct_link из БД с fallback на codex_docs_domain + /setup
setup_url = None
try:
    # Сначала пробуем получить прямую ссылку
    setup_direct_link = get_setting("setup_direct_link")
    if setup_direct_link and setup_direct_link.strip():
        setup_url = setup_direct_link.strip()
    else:
        # Fallback: используем codex_docs_domain + /setup
        codex_docs_domain = get_setting("codex_docs_domain")
        if codex_docs_domain and codex_docs_domain.strip():
            # Нормализуем домен: убираем trailing slash, добавляем протокол если нужно
            domain = codex_docs_domain.strip().rstrip('/')
            if not domain.startswith(('http://', 'https://')):
                domain = f'https://{domain}'
            # Добавляем путь /setup к домену
            setup_url = f"{domain}/setup"
        else:
            # Fallback на жестко прописанный URL если настройка не задана (для обратной совместимости)
            setup_url = "https://help.dark-maximus.com/setup"
except Exception as e:
    logger.warning(f"Failed to get setup_direct_link or codex_docs_domain for setup button: {e}, using fallback")
    setup_url = "https://help.dark-maximus.com/setup"  # fallback для обработки ошибок
```

## Приоритет использования

1. **`setup_direct_link`** - если указана, используется она
2. **`codex_docs_domain + /setup`** - если `setup_direct_link` не указана
3. **`https://help.dark-maximus.com/setup`** - жёстко прописанный fallback

## Тестирование

После внедрения:

1. Открыть веб-панель → Настройки → вкладка "Панель"
2. Убедиться, что новое поле "Прямая ссылка на базу знаний" отображается после поля "Домен codex-docs для Базы знаний"
3. Ввести значение `https://help.dark-maximus.com/setup`
4. Сохранить настройки
5. Выполнить тестовую покупку и проверить, что кнопка "Настройка" работает корректно