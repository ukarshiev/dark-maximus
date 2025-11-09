# Риски безопасности Docker Socket

> **Дата создания:** 08.11.2025  
> **Версия:** 1.0  
> **Статус:** ⚠️ КРИТИЧНЫЙ

## Проблема

Docker socket (`/var/run/docker.sock`) даёт контейнеру полный контроль над хостом.

Это Unix-сокет, через который Docker CLI общается с Docker Daemon. Когда контейнер монтирует этот сокет, он получает те же права, что и Docker Daemon, который обычно работает с правами root.

## Риски

### 1. Container Escape

**Описание:**
- Контейнер может создать privileged контейнер
- Из privileged контейнера можно получить root на хосте
- Монтирование файловой системы хоста в контейнер

**Пример атаки:**
```bash
# Из контейнера с доступом к Docker socket
docker run -it --privileged --pid=host debian nsenter -t 1 -m -u -n -i sh
# Теперь вы root на хосте
```

### 2. Data Exfiltration

**Описание:**
- Доступ к volumes других контейнеров
- Чтение файлов хоста через bind mounts
- Извлечение секретов и конфигураций

**Пример атаки:**
```bash
# Монтируем корень хоста
docker run -v /:/host alpine cat /host/etc/shadow
```

### 3. Denial of Service

**Описание:**
- Остановка критичных контейнеров
- Удаление данных
- Потребление всех ресурсов хоста

**Пример атаки:**
```bash
# Остановка всех контейнеров
docker stop $(docker ps -q)

# Удаление всех образов
docker rmi -f $(docker images -q)
```

### 4. Code Execution

**Описание:**
- Запуск произвольных контейнеров
- Монтирование `/` хоста в контейнер
- Изменение критичных файлов хоста

**Пример атаки:**
```bash
# Запуск контейнера с root доступом к хосту
docker run -v /:/rootfs alpine sh -c "echo 'malicious code' >> /rootfs/etc/crontab"
```

## Текущие меры защиты

В проекте Dark Maximus реализованы следующие меры:

### 1. ✅ Аутентификация

Все эндпоинты защищены декоратором `@login_required`:

```python
@flask_app.route('/api/docker/restart-all', methods=['POST'])
@login_required
def docker_restart_all():
    # ...
```

### 2. ✅ Rate Limiting

Ограничение попыток входа (10 попыток/мин):

```python
@rate_limit.limit("10 per minute")
def login():
    # ...
```

### 3. ✅ Логирование всех действий

Каждая Docker операция логируется с username:

```python
logger.info(f"[DOCKER_API] restart-bot initiated by {session.get('username')}")
```

### 4. ✅ HTTPS

При правильной настройке SSL все запросы шифруются.

### 5. ✅ Ограниченный набор операций

Доступны только безопасные операции:
- `docker compose restart` (не privileged)
- `docker compose build`
- `docker compose up -d`

**НЕТ доступа к:**
- `docker run --privileged`
- `docker exec`
- Прямым Docker API вызовам

## Рекомендации

### Краткосрочные (реализовать сейчас)

1. **Используйте СИЛЬНЫЙ пароль**
   - Минимум 16 символов
   - Буквы, цифры, спецсимволы
   - Не используйте словарные слова

2. **Не давайте доступ третьим лицам**
   - Доступ только для доверенных администраторов
   - Не делитесь паролем
   - Используйте отдельные аккаунты при необходимости

3. **Регулярно проверяйте логи**
   ```bash
   tail -f logs/application.log | grep DOCKER_API
   ```

4. **Включите HTTPS**
   - Используйте Let's Encrypt
   - Принудительное перенаправление HTTP → HTTPS
   - HSTS заголовки

5. **Ограничьте сетевой доступ**
   - Доступ к панели только с доверенных IP
   - Используйте VPN
   - Настройте firewall

### Долгосрочные (для production)

#### 1. Заменить Docker socket на SSH

**Преимущества:**
- Нет прямого доступа к Docker socket
- Аудит через syslog
- Управление правами через SSH ключи
- Можно использовать разные ключи для разных операций

**Реализация:**

```python
import paramiko

class DockerSSHManager:
    def __init__(self, host='localhost', username='deploy', key_path='/keys/id_rsa'):
        self.ssh = paramiko.SSHClient()
        self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self.ssh.connect(host, username=username, key_filename=key_path)
    
    def restart_bot(self):
        stdin, stdout, stderr = self.ssh.exec_command('docker compose restart bot')
        return stdout.read().decode(), stderr.read().decode()
    
    def close(self):
        self.ssh.close()
```

**Настройка:**
1. Создать пользователя `deploy` на хосте
2. Ограничить его права через sudoers:
   ```
   deploy ALL=(ALL) NOPASSWD: /usr/bin/docker compose restart *
   deploy ALL=(ALL) NOPASSWD: /usr/bin/docker compose build *
   ```
3. Настроить SSH ключи
4. Запретить пароль для SSH

#### 2. Добавить 2FA (Two-Factor Authentication)

**Варианты:**
- TOTP (Google Authenticator, Authy)
- SMS коды
- Email коды
- Hardware tokens (YubiKey)

**Библиотеки:**
- `pyotp` для TOTP
- `flask-security-too` для комплексного решения

#### 3. Rate Limiting для Docker API

```python
from flask_limiter import Limiter

limiter = Limiter(key_func=get_client_ip)

@flask_app.route('/api/docker/restart-bot', methods=['POST'])
@limiter.limit("1 per minute")  # Не более 1 рестарта в минуту
@login_required
def docker_restart_bot():
    # ...
```

#### 4. Уведомления в Telegram

```python
async def notify_admin_docker_action(action, username):
    """Отправляет уведомление администратору о Docker операции"""
    admin_id = get_setting("admin_telegram_id")
    message = f"⚠️ Docker операция: {action}\nПользователь: {username}\nВремя: {datetime.now()}"
    await bot.send_message(admin_id, message)
```

#### 5. Аудит логов

- Централизованное хранение логов (ELK Stack, Graylog)
- Автоматический анализ подозрительной активности
- Alerts при необычных операциях
- Ротация и архивирование логов

#### 6. Принцип наименьших привилегий

Вместо монтирования всего Docker socket, использовать:
- Docker socket proxy (tecnativa/docker-socket-proxy)
- Ограничение только нужными API вызовами
- Read-only доступ где возможно

**Пример docker-compose.yml:**

```yaml
services:
  docker-proxy:
    image: tecnativa/docker-socket-proxy
    environment:
      CONTAINERS: 1
      POST: 1
      SERVICES: 0
      IMAGES: 0
      NETWORKS: 0
      VOLUMES: 0
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock:ro
    networks:
      - internal

  bot:
    depends_on:
      - docker-proxy
    environment:
      DOCKER_HOST: tcp://docker-proxy:2375
    networks:
      - internal
```

## Альтернативные решения

### 1. Watchtower

Автоматическое обновление контейнеров:

```yaml
services:
  watchtower:
    image: containrrr/watchtower
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
    command: --interval 300
```

**Плюсы:**
- Автоматические обновления
- Нет необходимости в ручном рестарте

**Минусы:**
- Нет контроля над временем обновления
- Может сломать продакшн

### 2. Kubernetes/Docker Swarm

Оркестрация контейнеров:
- Rolling updates
- Health checks
- Automatic restarts
- Service discovery

**Плюсы:**
- Production-ready
- Масштабируемость
- Self-healing

**Минусы:**
- Сложность настройки
- Избыточно для небольших проектов

### 3. CI/CD Pipeline

Автоматизация через GitLab CI, GitHub Actions, Jenkins:
- Push to repository → Automatic deploy
- Тесты перед деплоем
- Rollback при ошибках

**Плюсы:**
- Нет ручного вмешательства
- Контроль версий
- Автотесты

**Минусы:**
- Требует настройки CI/CD
- Задержка между commit и deploy

## Проверка безопасности

### Аудит прав контейнера

```bash
# Проверка монтированных volumes
docker inspect bot | jq '.[0].Mounts'

# Проверка capabilities
docker inspect bot | jq '.[0].HostConfig.CapAdd'

# Проверка privileged режима
docker inspect bot | jq '.[0].HostConfig.Privileged'
```

### Сканирование образов

```bash
# Trivy
trivy image dark-maximus-bot:latest

# Snyk
snyk container test dark-maximus-bot:latest

# Docker Scout
docker scout cves dark-maximus-bot:latest
```

### Проверка логов

```bash
# Поиск подозрительных команд
grep -i "exec\|run\|privileged" logs/application.log

# Мониторинг Docker событий
docker events --filter 'type=container' --filter 'event=start'
```

## Ссылки и ресурсы

### Документация

- [Docker Security Best Practices](https://docs.docker.com/engine/security/)
- [OWASP Docker Security](https://cheatsheetseries.owasp.org/cheatsheets/Docker_Security_Cheat_Sheet.html)
- [CIS Docker Benchmark](https://www.cisecurity.org/benchmark/docker)

### Инструменты безопасности

- [Docker Bench Security](https://github.com/docker/docker-bench-security)
- [Falco](https://falco.org/) - Runtime security monitoring
- [Aqua Security](https://www.aquasec.com/)
- [Sysdig Secure](https://sysdig.com/products/secure/)

### Статьи

- [Threat Matrix for Kubernetes](https://www.microsoft.com/security/blog/2020/04/02/attack-matrix-kubernetes/)
- [Docker Socket Security](https://raesene.github.io/blog/2016/03/06/The-Dangers-Of-Docker.sock/)
- [Container Escape Techniques](https://blog.trailofbits.com/2019/07/19/understanding-docker-container-escapes/)

---

**⚠️ ВАЖНО:** Этот документ следует регулярно пересматривать и обновлять по мере появления новых уязвимостей и методов защиты.

**Последнее обновление:** 08.11.2025  
**Следующий пересмотр:** 08.02.2026

