<!-- 54c2ae1c-9fbd-4830-a77d-d9d3ac124c94 2979ce9c-47dc-4312-960b-2b7c46d2356e -->
# YooKassa: Анализ, Исправления и Docker Management

**Linear:** KAR-34

## Приоритет: Сначала исправления YooKassa, потом Docker Management

## Этап 1: Полный анализ YooKassa по Best Practices

### Цель

Проверить текущую интеграцию на соответствие официальной документации YooKassa и выявить все проблемы.

### Что проверяем

**1.1. Конфигурация и инициализация**

Файлы: `bot_controller.py`, `handlers.py`, `app.py`

- Правильность использования `Configuration.configure()` с `account_id`, `secret_key`, `api_url`, `verify`
- Корректное различение тестового (`https://api.test.yookassa.ru/v3`) и боевого (`https://api.yookassa.ru/v3`) API URL
- Проверка fallback логики: если test ключи пустые, используются ли production ключи (это небезопасно)
- Проверка `verify_ssl` - должен быть `True` в production

**1.2. Создание платежей**

Файлы: `handlers.py` (функции `create_yookassa_payment_handler`, `topup_pay_yookassa`)

- Наличие **idempotency key** в каждом запросе создания платежа
- Формат idempotency key (должен быть уникальным UUID)
- Правильное использование `Payment.create()`
- Параметры платежа:
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                - `amount.value` и `amount.currency`
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                - `confirmation.type` и `confirmation.return_url`
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                - `capture` (true/false) - для одно/двухстадийных платежей
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                - `metadata` - передача данных для webhook
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                - `description` - описание платежа

**1.3. Обработка webhook уведомлений**

Файл: `app.py` (функция `yookassa_webhook_handler`)

- Проверка типов событий: `payment.succeeded`, `payment.waiting_for_capture`, `payment.canceled`
- Проверка `paid=true` перед обработкой успешного платежа
- Извлечение `metadata` для идентификации транзакции
- Обработка `authorization_details` (rrn, auth_code, three_d_secure)
- Логирование всех событий
- Проверка на дублирование обработки (idempotency на уровне БД)

**1.4. Поле `test` в Payment Object**

Согласно документации YooKassa, каждый Payment объект содержит поле `"test": true/false`.

- Проверяем ли мы это поле в webhook?
- Логируем ли мы, какой режим использовался для платежа?
- Есть ли риск обработки тестового платежа как боевого?

**1.5. Безопасность**

- HTTPS для webhook endpoint
- Проверка IP адресов YooKassa (опционально)
- Защита от replay attacks
- Валидация входящих данных

## Этап 2: Исправления YooKassa

### 2.1. Проблема: Configuration инициализируется только при старте

**Текущая ситуация:**

- `bot_controller.start_shop_bot()` настраивает YooKassa один раз при запуске
- `_reconfigure_yookassa()` вызывается перед созданием платежа, но может не полностью применяться

**Решение 1: Гарантированная переинициализация (рекомендуется)**

Файл: `handlers.py` (функции создания платежей)

```python
def _reconfigure_yookassa():
    """Переинициализирует Configuration с актуальными настройками из БД"""
    from yookassa import Configuration
    
    yookassa_test_mode = get_setting("yookassa_test_mode") == "true"
    
    if yookassa_test_mode:
        shop_id = _safe_strip(get_setting("yookassa_test_shop_id")) or _safe_strip(get_setting("yookassa_shop_id"))
        secret_key = _safe_strip(get_setting("yookassa_test_secret_key")) or _safe_strip(get_setting("yookassa_secret_key"))
        api_url = _safe_strip(get_setting("yookassa_test_api_url")) or _safe_strip(get_setting("yookassa_api_url")) or "https://api.test.yookassa.ru/v3"
        verify_ssl = get_setting("yookassa_test_verify_ssl") != "false"
    else:
        shop_id = _safe_strip(get_setting("yookassa_shop_id"))
        secret_key = _safe_strip(get_setting("yookassa_secret_key"))
        api_url = _safe_strip(get_setting("yookassa_api_url")) or "https://api.yookassa.ru/v3"
        verify_ssl = get_setting("yookassa_verify_ssl") != "false"
    
    if shop_id and secret_key:
        # КРИТИЧНО: Явно логируем режим и параметры
        logger.info(
            f"[YOOKASSA_RECONFIGURE] mode={'TEST' if yookassa_test_mode else 'PRODUCTION'}, "
            f"shop_id={shop_id[:4]}..., api_url={api_url}, verify_ssl={verify_ssl}"
        )
        Configuration.configure(
            account_id=shop_id,
            secret_key=secret_key,
            api_url=api_url,
            verify=verify_ssl
        )
        return True
    else:
        logger.warning("[YOOKASSA_RECONFIGURE] Missing shop_id or secret_key")
        return False
```

**Решение 2: Предупреждение в UI (обязательно)**

Файл: `settings.html`

Добавить информационное сообщение около чекбокса "Тестовый режим YooKassa":

```html
<div class="alert alert-warning" style="margin-top: 10px;">
    <i class="fas fa-exclamation-triangle"></i>
    <strong>Важно:</strong> После изменения режима YooKassa необходимо перезапустить бот для применения изменений.
    Используйте кнопку "Рестарт бота" в шапке панели.
</div>
```

### 2.2. Улучшение UI: Индикатор активного режима

**Текущая ситуация:**

Есть небольшой текст под чекбоксом, показывающий режим из БД. Но это не показывает **реально активный** режим бота.

**Решение:**

Файл: `app.py` (роут `/settings`)

Добавить в контекст шаблона:

```python
@flask_app.route('/settings', methods=['GET'])
@login_required
def settings_page():
    # ... существующий код ...
    
    # Получаем РЕАЛЬНЫЙ активный режим из Configuration
    from yookassa import Configuration
    active_shop_id = Configuration.account_id if hasattr(Configuration, 'account_id') else None
    db_shop_id = settings.get('yookassa_shop_id', '')
    db_test_shop_id = settings.get('yookassa_test_shop_id', '')
    
    # Определяем активный режим
    if active_shop_id == db_test_shop_id:
        active_mode = 'test'
    elif active_shop_id == db_shop_id:
        active_mode = 'production'
    else:
        active_mode = 'unknown'
    
    return render_template(
        'settings.html',
        settings=settings,
        yookassa_active_mode=active_mode,  # Новое
        # ... остальное ...
    )
```

Файл: `settings.html`

```html
<div class="form-group form-group-checkbox">
    <label for="yookassa_test_mode">
        <input type="checkbox" id="yookassa_test_mode" name="yookassa_test_mode" value="true" 
               {% if settings.yookassa_test_mode == 'true' %}checked{% endif %}>
        <span>Тестовый режим YooKassa</span>
    </label>
    
    <!-- Индикатор из БД -->
    <small style="display: block; margin-top: 5px; color: #999;">
        В БД: 
        {% if settings.yookassa_test_mode == 'true' %}
            <strong style="color: #f39c12;">Тестовый</strong>
        {% else %}
            <strong style="color: #e74c3c;">Боевой</strong>
        {% endif %}
    </small>
    
    <!-- Индикатор реального активного режима -->
    <small style="display: block; margin-top: 5px;">
        Активный режим бота: 
        {% if yookassa_active_mode == 'test' %}
            <strong style="color: #f39c12;">🟡 Тестовый</strong>
        {% elif yookassa_active_mode == 'production' %}
            <strong style="color: #27ae60;">🟢 Боевой</strong>
        {% else %}
            <strong style="color: #e74c3c;">🔴 Неизвестно</strong>
        {% endif %}
    </small>
    
    <!-- Предупреждение если режимы не совпадают -->
    {% if (settings.yookassa_test_mode == 'true' and yookassa_active_mode != 'test') or 
          (settings.yookassa_test_mode != 'true' and yookassa_active_mode != 'production') %}
    <div class="alert alert-warning" style="margin-top: 10px; font-size: 12px;">
        <i class="fas fa-sync-alt"></i>
        Требуется перезапуск бота для применения изменений!
    </div>
    {% endif %}
</div>
```

### 2.3. Логирование режима в каждом платеже

Файл: `handlers.py` (все функции создания платежей)

Добавить логирование перед `Payment.create()`:

```python
# Перед созданием платежа
_reconfigure_yookassa()

# Логируем режим
from yookassa import Configuration
logger.info(
    f"[YOOKASSA_PAYMENT] Creating payment: user_id={user_id}, amount={amount}, "
    f"shop_id={Configuration.account_id[:4] if Configuration.account_id else 'None'}..., "
    f"api_url={Configuration.api_url if hasattr(Configuration, 'api_url') else 'default'}"
)

payment = Payment.create({...})
```

### 2.4. Проверка поля `test` в webhook

Файл: `app.py` (функция `yookassa_webhook_handler`)

```python
@flask_app.route('/yookassa/webhook', methods=['POST'])
def yookassa_webhook_handler():
    try:
        event_json = request.json
        event_type = event_json.get("event")
        payment_object = event_json.get("object", {})
        
        # НОВОЕ: Извлекаем и логируем поле test
        is_test_payment = payment_object.get("test", False)
        payment_id = payment_object.get("id")
        
        logger.info(
            f"[YOOKASSA_WEBHOOK] event={event_type}, payment_id={payment_id}, "
            f"test={is_test_payment}, paid={payment_object.get('paid')}"
        )
        
        # Проверяем соответствие режимов
        db_test_mode = get_setting("yookassa_test_mode") == "true"
        if is_test_payment != db_test_mode:
            logger.warning(
                f"[YOOKASSA_WEBHOOK] Mode mismatch! webhook test={is_test_payment}, "
                f"db test_mode={db_test_mode}"
            )
        
        # ... остальная обработка ...
```

### 2.5. Добавление idempotency key (если отсутствует)

Файл: `handlers.py` (все функции создания платежей)

```python
import uuid

# При создании платежа
idempotency_key = str(uuid.uuid4())

payment = Payment.create({
    "amount": {
        "value": str(amount),
        "currency": "RUB"
    },
    # ... остальные параметры ...
}, idempotency_key)

logger.info(f"[YOOKASSA_PAYMENT] idempotency_key={idempotency_key}")
```

## Этап 3: Docker Management UI

### Цель

Добавить 3 кнопки управления Docker в header-panel-right для удобного рестарта без SSH.

### 3.1. Docker Socket

**Файл:** `docker-compose.yml`

```yaml
services:
  bot:
    volumes:
      # ... существующие volumes ...
      - /var/run/docker.sock:/var/run/docker.sock
```

**Безопасность:**

- Временное решение с полным доступом
- TODO: Заменить на SSH ключи в будущем
- Только для авторизованных администраторов

### 3.2. Backend API

**Файл:** `src/shop_bot/webhook_server/app.py`

```python
import subprocess

@flask_app.route('/api/docker/restart-all', methods=['POST'])
@login_required
def docker_restart_all():
    """Перезапускает все сервисы через docker compose restart"""
    try:
        logger.info(f"[DOCKER_API] restart-all initiated by {session.get('username')}")
        result = subprocess.run(
            ['docker', 'compose', 'restart'],
            cwd='/app/project',
            capture_output=True,
            text=True,
            timeout=90
        )
        logger.info(f"[DOCKER_API] restart-all completed: returncode={result.returncode}")
        return jsonify({
            'success': result.returncode == 0,
            'message': 'Restart initiated' if result.returncode == 0 else result.stderr,
            'reload_after': 35
        })
    except Exception as e:
        logger.error(f"[DOCKER_API] restart-all failed: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

@flask_app.route('/api/docker/restart-bot', methods=['POST'])
@login_required
def docker_restart_bot():
    """Перезапускает только бот"""
    try:
        logger.info(f"[DOCKER_API] restart-bot initiated by {session.get('username')}")
        result = subprocess.run(
            ['docker', 'compose', 'restart', 'bot'],
            cwd='/app/project',
            capture_output=True,
            text=True,
            timeout=60
        )
        logger.info(f"[DOCKER_API] restart-bot completed: returncode={result.returncode}")
        return jsonify({
            'success': result.returncode == 0,
            'message': 'Bot restart initiated' if result.returncode == 0 else result.stderr,
            'reload_after': 20
        })
    except Exception as e:
        logger.error(f"[DOCKER_API] restart-bot failed: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

@flask_app.route('/api/docker/rebuild', methods=['POST'])
@login_required
def docker_rebuild():
    """Пересобирает и перезапускает с очисткой кеша"""
    try:
        logger.info(f"[DOCKER_API] rebuild initiated by {session.get('username')}")
        # Сборка без кеша
        build_result = subprocess.run(
            ['docker', 'compose', 'build', '--no-cache'],
            cwd='/app/project',
            capture_output=True,
            text=True,
            timeout=300
        )
        if build_result.returncode != 0:
            logger.error(f"[DOCKER_API] build failed: {build_result.stderr}")
            return jsonify({'success': False, 'message': f'Build failed: {build_result.stderr}'}), 500
        
        # Перезапуск с force-recreate
        up_result = subprocess.run(
            ['docker', 'compose', 'up', '-d', '--force-recreate'],
            cwd='/app/project',
            capture_output=True,
            text=True,
            timeout=120
        )
        logger.info(f"[DOCKER_API] rebuild completed: returncode={up_result.returncode}")
        return jsonify({
            'success': up_result.returncode == 0,
            'message': 'Rebuild completed' if up_result.returncode == 0 else up_result.stderr,
            'reload_after': 200
        })
    except Exception as e:
        logger.error(f"[DOCKER_API] rebuild failed: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500
```

### 3.3. Frontend кнопки

**Файл:** `src/shop_bot/webhook_server/templates/base.html`

```html
<div class="header-panel-right">
    {% block header_buttons %}{% endblock %}
    
    <!-- Docker Management кнопки -->
    <div class="docker-management-buttons">
        <button class="btn-docker" data-action="restart-all" title="Перезапустить все сервисы">
            <i class="fas fa-sync-alt"></i>
            <span>Рестарт всего</span>
        </button>
        <button class="btn-docker" data-action="restart-bot" title="Перезапустить бота">
            <i class="fas fa-robot"></i>
            <span>Рестарт бота</span>
        </button>
        <button class="btn-docker btn-docker-rebuild" data-action="rebuild" title="Ребилд без кеша">
            <i class="fas fa-hammer"></i>
            <span>Ребилд</span>
        </button>
    </div>
</div>
```

### 3.4. Модальные окна

**Файл:** `src/shop_bot/webhook_server/templates/base.html` (в конце body)

```html
<!-- Docker Action Confirmation Modal -->
<div id="dockerActionModal" class="modal" style="display: none;">
    <div class="modal-content">
        <h3 id="dockerActionTitle">Подтверждение</h3>
        <p id="dockerActionMessage"></p>
        <div class="modal-actions">
            <button class="btn-cancel" onclick="closeDockerModal()">Отмена</button>
            <button class="btn-confirm" onclick="confirmDockerAction()">Подтвердить</button>
        </div>
    </div>
</div>

<!-- Docker Progress Modal -->
<div id="dockerProgressModal" class="modal" style="display: none;">
    <div class="modal-content">
        <div class="spinner"></div>
        <h3 id="dockerProgressTitle">Выполняется...</h3>
        <p id="dockerProgressMessage"></p>
        <p id="dockerCountdown"></p>
    </div>
</div>
```

### 3.5. JavaScript обработка

**Файл:** `src/shop_bot/webhook_server/static/js/script.js`

```javascript
const DOCKER_ACTIONS = {
    'restart-all': {
        title: 'Перезапуск всех сервисов',
        message: 'Это перезапустит все сервисы (bot, docs, codex-docs). Продолжить?',
        duration: 35,
        endpoint: '/api/docker/restart-all'
    },
    'restart-bot': {
        title: 'Перезапуск бота',
        message: 'Это перезапустит только бот. Продолжить?',
        duration: 20,
        endpoint: '/api/docker/restart-bot'
    },
    'rebuild': {
        title: 'Ребилд без кеша',
        message: 'Это полностью пересоберёт образ без кеша (займёт 3-5 минут). Продолжить?',
        duration: 200,
        endpoint: '/api/docker/rebuild'
    }
};

let currentDockerAction = null;

document.addEventListener('DOMContentLoaded', function() {
    document.querySelectorAll('.btn-docker').forEach(btn => {
        btn.addEventListener('click', function() {
            const action = this.dataset.action;
            currentDockerAction = DOCKER_ACTIONS[action];
            showDockerConfirmModal(currentDockerAction);
        });
    });
});

function showDockerConfirmModal(action) {
    document.getElementById('dockerActionTitle').textContent = action.title;
    document.getElementById('dockerActionMessage').textContent = action.message;
    document.getElementById('dockerActionModal').style.display = 'flex';
}

function closeDockerModal() {
    document.getElementById('dockerActionModal').style.display = 'none';
    currentDockerAction = null;
}

async function confirmDockerAction() {
    if (!currentDockerAction) return;
    
    document.getElementById('dockerActionModal').style.display = 'none';
    showDockerProgress(currentDockerAction);
    
    try {
        const response = await fetch(currentDockerAction.endpoint, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            credentials: 'same-origin'
        });
        
        const data = await response.json();
        
        if (data.success) {
            document.getElementById('dockerProgressMessage').textContent = 'Готово!';
            startCountdown(data.reload_after || currentDockerAction.duration);
        } else {
            showDockerError(data.message);
        }
    } catch (error) {
        showDockerError('Ошибка выполнения команды: ' + error.message);
    }
}

function showDockerProgress(action) {
    document.getElementById('dockerProgressTitle').textContent = action.title;
    document.getElementById('dockerProgressMessage').textContent = 'Выполняется...';
    document.getElementById('dockerProgressModal').style.display = 'flex';
}

function startCountdown(seconds) {
    let remaining = seconds;
    const countdownEl = document.getElementById('dockerCountdown');
    
    const interval = setInterval(() => {
        countdownEl.textContent = `Страница обновится через ${remaining} сек...`;
        remaining--;
        
        if (remaining < 0) {
            clearInterval(interval);
            window.location.reload();
        }
    }, 1000);
}

function showDockerError(message) {
    document.getElementById('dockerProgressTitle').textContent = 'Ошибка';
    document.getElementById('dockerProgressMessage').textContent = message;
    document.getElementById('dockerCountdown').textContent = '';
    setTimeout(() => {
        document.getElementById('dockerProgressModal').style.display = 'none';
    }, 5000);
}
```

### 3.6. CSS стили

**Файл:** `src/shop_bot/webhook_server/static/css/style.css`

```css
.docker-management-buttons {
    display: flex;
    gap: 10px;
    align-items: center;
}

.btn-docker {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 8px 16px;
    background: #2c3e50;
    color: white;
    border: 1px solid #34495e;
    border-radius: 4px;
    cursor: pointer;
    transition: all 0.3s;
    font-size: 14px;
}

.btn-docker:hover {
    background: #34495e;
    transform: translateY(-2px);
}

.btn-docker-rebuild {
    background: #e74c3c;
    border-color: #c0392b;
}

.btn-docker-rebuild:hover {
    background: #c0392b;
}

.modal {
    display: none;
    position: fixed;
    z-index: 9999;
    left: 0;
    top: 0;
    width: 100%;
    height: 100%;
    background-color: rgba(0,0,0,0.7);
    align-items: center;
    justify-content: center;
}

.modal-content {
    background-color: #2c3e50;
    padding: 30px;
    border-radius: 8px;
    max-width: 500px;
    text-align: center;
    color: white;
}

.modal-actions {
    display: flex;
    gap: 15px;
    justify-content: center;
    margin-top: 20px;
}

.btn-cancel, .btn-confirm {
    padding: 10px 20px;
    border: none;
    border-radius: 4px;
    cursor: pointer;
    font-size: 14px;
}

.btn-cancel {
    background: #95a5a6;
    color: white;
}

.btn-confirm {
    background: #008771;
    color: white;
}

.spinner {
    border: 4px solid #f3f3f3;
    border-top: 4px solid #008771;
    border-radius: 50%;
    width: 50px;
    height: 50px;
    animation: spin 1s linear infinite;
    margin: 0 auto 20px;
}

@keyframes spin {
    0% { transform: rotate(0deg); }
    100% { transform: rotate(360deg); }
}
```

## Этап 4: Тестирование и документация

### 4.1. Тестирование YooKassa исправлений

- Переключение режима test/production в UI
- Проверка логов при создании платежа
- Проверка индикаторов активного режима
- Проверка webhook с полем `test`
- Рестарт бота через новую кнопку
- Проверка применения изменений

### 4.2. Тестирование Docker Management

- Кнопка "Рестарт всего"
- Кнопка "Рестарт бота"
- Кнопка "Ребилд"
- Модальные окна
- Таймеры обратного отсчёта
- Обработка ошибок

### 4.3. Документация

- Обновить `docs/guides/admin/admin-panel-guide.md`
- Добавить раздел "Docker Management"
- Описать риски безопасности (Docker socket)
- TODO для SSH ключей
- Обновить CHANGELOG.md

## Риски и ограничения

### Безопасность Docker Socket

- КРИТИЧНО: Проброс Docker socket даёт контейнеру полный контроль над хостом
- Необходима сильная защита админки
- TODO: Заменить на SSH ключи для production

### UX ограничения

- Невозможно показать реальные логи (панель упадёт)
- Невозможно показать реальный прогресс
- Можем показать только таймер обратного отсчёта
- Можем автоматически обновить страницу

### Timing

- Таймеры приблизительные (зависит от железа, интернета)
- Ребилд может занять больше времени на слабом железе
- Если страница обновится раньше завершения - покажет ошибку

## Следующие шаги

После реализации:

1. Добавить логирование всех Docker действий в отдельный файл
2. Добавить уведомления в Telegram при выполнении критичных действий
3. Реализовать SSH ключи вместо Docker socket
4. Добавить 2FA для админки
5. Добавить rate limiting для Docker API (не более 1 действия в минуту)

### To-dos

- [ ] Добавить Docker socket в docker-compose.yml и проверить Docker CLI в контейнере
- [ ] Создать 3 защищённых API эндпоинта для Docker команд в app.py
- [ ] Добавить 3 кнопки в header-panel-right в base.html с иконками
- [ ] Создать модальные окна для подтверждения и отображения прогресса
- [ ] Реализовать JavaScript обработку кликов, AJAX запросы и таймеры
- [ ] Добавить CSS стили для кнопок, модалок и спиннера
- [ ] Протестировать все 3 кнопки на Windows и Ubuntu
- [ ] Обновить документацию с описанием новых кнопок и рисков безопасности