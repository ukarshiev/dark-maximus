# 🔧 Продвинутая настройка Dark Maximus

> Обновлено: 10.11.2025  
> Версия: 2.71.0

## 📋 Содержание

- [Docker архитектура](#-docker-архитектура)
- [Настройка дополнительных компонентов](#-настройка-дополнительных-компонентов)
- [Настройка поддоменов](#-настройка-поддоменов)
- [Настройка уведомлений](#-настройка-уведомлений)
- [Мониторинг и логирование](#-мониторинг-и-логирование)
- [Резервное копирование](#-резервное-копирование)
- [Производительность и масштабирование](#-производительность-и-масштабирование)
- [Безопасность](#-безопасность)

## 🐳 Docker архитектура

### Обзор контейнеров

Dark Maximus состоит из трех основных Docker контейнеров:

```
┌─────────────────────────────────────────────────────────────┐
│                Системный nginx (порт 80/443)               │
│  ┌─────────────────┬─────────────────┬─────────────────┐    │
│  │ docs.dark-      │ help.dark-      │ panel.dark-     │    │
│  │ maximus.com     │ maximus.com     │ maximus.com     │    │
│  └─────────────────┴─────────────────┴─────────────────┘    │
└─────────────────────────────────────────────────────────────┘
           │                    │                    │
           ▼                    ▼                    ▼
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│ localhost:3001  │  │ localhost:3002  │  │ localhost:50000 │
│   docs:80       │  │ codex-docs:3000 │  │    bot:50000    │
│   (nginx)       │  │   (Express)     │  │   (Python)      │
└─────────────────┘  └─────────────────┘  └─────────────────┘
```

### 1. **bot** - Основной Telegram бот

**Dockerfile**: `Dockerfile` (multi-stage build)
- **Stage 1**: Node.js для сборки Tailwind CSS
- **Stage 2**: Python 3.11-slim для основного приложения

**Особенности:**
- Автоматическая сборка CSS из Tailwind
- Автоматическое развертывание админской документации
- Healthcheck endpoint на `/health`

**Volumes:**
```yaml
volumes:
  - ./src/shop_bot:/app/src/shop_bot
  - ./logs:/app/logs
  - ./backups:/app/backups
  - ./sessions:/app/sessions
```

### 2. **docs** - Пользовательская документация

**Dockerfile**: `Dockerfile.docs` (multi-stage build)
- **Stage 1**: Alpine для сборки статики
- **Stage 2**: Nginx unprivileged для обслуживания

**Особенности:**
- Не-root пользователь (nginx) для безопасности
- Gzip сжатие и кэширование статики
- Healthcheck endpoint на `/health`

**Volumes:**
```yaml
volumes:
  - ./docs/user-docs:/usr/share/nginx/html
```

### 3. **codex-docs** - Админская документация

**Dockerfile**: `Dockerfile.codex-docs` (multi-stage build)
- **Stage 1**: Node.js для сборки приложения
- **Stage 2**: Node.js для production

**Особенности:**
- WebSocket поддержка для real-time обновлений
- Healthcheck endpoint на `/`
- Volumes для данных и загрузок

**Volumes:**
```yaml
volumes:
  - codex_docs_data:/app/data
  - codex_docs_uploads:/app/uploads
```

## 🛠️ Настройка дополнительных компонентов

### Настройка Codex Docs

Codex Docs - это интерактивная админская документация на базе [codex.docs](https://docs.codex.so/).

#### Автоматическая настройка

```bash
# Запуск Codex Docs
cd codex.docs
yarn install
yarn start
```

#### Настройка через Docker

```bash
cd codex.docs
docker-compose up -d
```

#### Добавление админской документации

1. Откройте Codex Docs: `http://localhost:3002`
2. Создайте новую секцию "📖 Админская документация"
3. Добавьте подстраницы:
   - ⚡ Быстрый старт
   - 📖 Полное руководство
   - 🔒 Чек-лист безопасности
   - 🔌 API документация

#### Структура документации

```
📖 Админская документация (родительская страница)
├── ⚡ Быстрый старт
├── 📖 Полное руководство
│   ├── Авторизация
│   ├── Dashboard
│   ├── Управление транзакциями
│   ├── Управление ключами
│   ├── Управление пользователями
│   ├── Управление промокодами
│   ├── Настройки
│   └── ...
├── 🔒 Чек-лист безопасности
└── 🔌 API документация
```

### Настройка Wiki

Wiki система интегрирована в админ-панель и доступна через раздел "Wiki редактор".

#### Быстрый старт

1. В админ-панели перейдите в "Wiki редактор"
2. Нажмите кнопку "Вики"
3. Настройте структуру документации
4. Добавьте контент для пользователей

## 🌐 Настройка поддоменов

### Архитектура поддоменов

Dark Maximus использует несколько поддоменов для разных сервисов:

- `panel.your-domain.com` - основная панель управления (bot сервис)
- `docs.your-domain.com` - документация проекта (docs сервис)  
- `help.your-domain.com` - справочная система (codex-docs сервис)

### Настройка DNS

#### A-записи

Создайте следующие A-записи в вашем DNS провайдере:

```
panel.your-domain.com    A    YOUR_SERVER_IP
docs.your-domain.com     A    YOUR_SERVER_IP  
help.your-domain.com     A    YOUR_SERVER_IP
```

#### CNAME записи (альтернатива)

Если у вас есть основной домен, можете использовать CNAME:

```
panel.your-domain.com    CNAME    your-domain.com
docs.your-domain.com     CNAME    your-domain.com
help.your-domain.com     CNAME    your-domain.com
```

### SSL сертификаты для поддоменов

#### Настройка Let's Encrypt

```bash
# Получение сертификатов для всех поддоменов
sudo certbot certonly --nginx \
  -d panel.your-domain.com \
  -d docs.your-domain.com \
  -d help.your-domain.com \
  --email your-email@example.com \
  --agree-tos \
  --non-interactive
```

#### Nginx конфигурация

```nginx
# Основной бот
server {
    listen 443 ssl http2;
    server_name panel.your-domain.com;
    
    ssl_certificate /etc/letsencrypt/live/panel.your-domain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/panel.your-domain.com/privkey.pem;
    
    location / {
        proxy_pass http://127.0.0.1:50000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}

# Пользовательская документация
server {
    listen 443 ssl http2;
    server_name docs.your-domain.com;
    
    ssl_certificate /etc/letsencrypt/live/docs.your-domain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/docs.your-domain.com/privkey.pem;
    
    location / {
        proxy_pass http://127.0.0.1:3001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}

# Админская документация
server {
    listen 443 ssl http2;
    server_name help.your-domain.com;
    
    ssl_certificate /etc/letsencrypt/live/help.your-domain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/help.your-domain.com/privkey.pem;
    
    location / {
        proxy_pass http://127.0.0.1:3002;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # WebSocket поддержка
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

## 📧 Настройка уведомлений

### Настройка уведомлений GitHub

После пуша в Git могут приходить множественные email-уведомления от GitHub Actions, Dependabot и других сервисов.

#### Настройка уведомлений в GitHub

1. Перейдите в настройки GitHub: https://github.com/settings/notifications
2. В разделе "Email notifications" отключите:
   - ✅ Actions (отключить уведомления о GitHub Actions)
   - ✅ Pull requests (оставить только важные)
   - ✅ Issues (оставить только важные)
   - ✅ Security alerts (оставить включенными для безопасности)

#### Настройка уведомлений по репозиторию

1. Перейдите в настройки репозитория: https://github.com/ukarshiev/dark-maximus/settings/notifications
2. Выберите "Custom" и настройте:
   - Actions: ❌ Disable
   - Dependabot alerts: ✅ Enable (для безопасности)
   - Security alerts: ✅ Enable (для безопасности)

#### Настройка фильтров в почте

Создайте фильтры в Gmail/другой почте для автоматической сортировки:
- Отправитель содержит "noreply@github.com"
- Тема содержит "CI/CD Pipeline" или "Docker Build"
- Автоматически перемещать в папку "GitHub Notifications" или удалять

### Настройка уведомлений Telegram

#### Настройка бота для уведомлений

1. Создайте бота через [@BotFather](https://t.me/BotFather)
2. Получите токен бота
3. Добавьте токен в настройки Dark Maximus
4. Настройте уведомления о:
   - Новых пользователях
   - Платежах
   - Ошибках системы

## 📊 Мониторинг и логирование

### Настройка логирования

#### Docker логи

```bash
# Настройка ротации логов Docker
sudo nano /etc/docker/daemon.json
```

Добавьте:
```json
{
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "10m",
    "max-file": "3"
  }
}
```

#### Logrotate для приложения

```bash
# /etc/logrotate.d/dark-maximus
/opt/dark-maximus/logs/*.log {
    daily
    missingok
    rotate 30
    compress
    delaycompress
    notifempty
    create 644 root root
    postrotate
        docker compose -f /opt/dark-maximus/docker-compose.yml restart bot
    endscript
}
```

### Мониторинг ресурсов

#### Prometheus + Grafana (опционально)

```yaml
# docker-compose.monitoring.yml
version: '3.8'
services:
  prometheus:
    image: prom/prometheus
    ports:
      - "9090:9090"
    volumes:
      - ./monitoring/prometheus.yml:/etc/prometheus/prometheus.yml
  
  grafana:
    image: grafana/grafana
    ports:
      - "3000:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin
    volumes:
      - grafana_data:/var/lib/grafana
```

#### Простой мониторинг

```bash
# Скрипт мониторинга
#!/bin/bash
# /usr/local/bin/monitor-dark-maximus.sh

# Проверка контейнеров
docker compose ps | grep -q "Up" || {
    echo "ALERT: Dark Maximus containers are down!"
    # Отправить уведомление
}

# Проверка использования диска
DISK_USAGE=$(df /opt/dark-maximus | tail -1 | awk '{print $5}' | sed 's/%//')
if [ $DISK_USAGE -gt 80 ]; then
    echo "WARNING: Disk usage is ${DISK_USAGE}%"
fi

# Проверка памяти
MEMORY_USAGE=$(free | grep Mem | awk '{printf "%.0f", $3/$2 * 100.0}')
if [ $MEMORY_USAGE -gt 90 ]; then
    echo "WARNING: Memory usage is ${MEMORY_USAGE}%"
fi
```

### Health Checks

#### Настройка health checks

```yaml
# docker-compose.yml
services:
  bot:
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:50000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
  
  docs:
    healthcheck:
      test: ["CMD", "wget", "--no-verbose", "--tries=1", "--spider", "http://localhost:80/health"]
      interval: 30s
      timeout: 10s
      retries: 3
  
  codex-docs:
    healthcheck:
      test: ["CMD", "wget", "--no-verbose", "--tries=1", "--spider", "http://localhost:3000/"]
      interval: 30s
      timeout: 10s
      retries: 3
```

## 💾 Резервное копирование

### Автоматическое резервное копирование

#### Скрипт резервного копирования

```bash
#!/bin/bash
# /usr/local/bin/backup-dark-maximus.sh

BACKUP_DIR="/opt/dark-maximus/backups"
DATE=$(date +%Y%m%d_%H%M%S)

# Создание директории для бэкапов
mkdir -p $BACKUP_DIR

# Бэкап базы данных
cp /opt/dark-maximus/users.db $BACKUP_DIR/users_$DATE.db

# Бэкап конфигураций
tar -czf $BACKUP_DIR/config_$DATE.tar.gz \
    /opt/dark-maximus/.env \
    /opt/dark-maximus/docker-compose.yml \
    /etc/nginx/sites-available/dark-maximus*

# Бэкап Docker volumes
docker run --rm \
    -v dark-maximus_sessions_data:/data \
    -v $BACKUP_DIR:/backup \
    alpine tar czf /backup/sessions_data_$DATE.tar.gz /data

# Очистка старых бэкапов (старше 30 дней)
find $BACKUP_DIR -name "*.db" -mtime +30 -delete
find $BACKUP_DIR -name "*.tar.gz" -mtime +30 -delete

echo "Backup completed: $DATE"
```

#### Настройка cron

```bash
# Добавить в crontab
0 2 * * * /usr/local/bin/backup-dark-maximus.sh
```

### Восстановление из бэкапа

```bash
# Восстановление базы данных
cp /opt/dark-maximus/backups/users_YYYYMMDD_HHMMSS.db /opt/dark-maximus/users.db

# Восстановление конфигураций
tar -xzf /opt/dark-maximus/backups/config_YYYYMMDD_HHMMSS.tar.gz -C /

# Восстановление Docker volumes
docker run --rm \
    -v dark-maximus_sessions_data:/data \
    -v /opt/dark-maximus/backups:/backup \
    alpine tar xzf /backup/sessions_data_YYYYMMDD_HHMMSS.tar.gz -C /
```

## ⚡ Производительность и масштабирование

### Оптимизация Docker

#### Настройка ресурсов

```yaml
# docker-compose.yml
services:
  bot:
    deploy:
      resources:
        limits:
          memory: 1G
          cpus: '0.5'
        reservations:
          memory: 512M
          cpus: '0.25'
```

#### Оптимизация Nginx

```nginx
# nginx.conf
worker_processes auto;
worker_connections 1024;

http {
    # Кэширование
    proxy_cache_path /var/cache/nginx levels=1:2 keys_zone=my_cache:10m max_size=1g inactive=60m;
    
    # Gzip сжатие
    gzip on;
    gzip_vary on;
    gzip_min_length 1024;
    gzip_types text/plain text/css application/json application/javascript text/xml application/xml;
    
    # Keep-alive
    keepalive_timeout 65;
    keepalive_requests 100;
}
```

### Масштабирование

#### Горизонтальное масштабирование

```yaml
# docker-compose.scale.yml
version: '3.8'
services:
  bot:
    scale: 3
    deploy:
      replicas: 3
      update_config:
        parallelism: 1
        delay: 10s
      restart_policy:
        condition: on-failure
```

#### Load Balancer

```nginx
# nginx.conf
upstream bot_backend {
    least_conn;
    server bot_1:50000;
    server bot_2:50000;
    server bot_3:50000;
}

server {
    location / {
        proxy_pass http://bot_backend;
    }
}
```

## 🔐 Безопасность

### Дополнительные меры безопасности

#### Настройка fail2ban

```bash
# Установка fail2ban
sudo apt install -y fail2ban

# Конфигурация для Dark Maximus
sudo nano /etc/fail2ban/jail.d/dark-maximus.conf
```

```ini
[dark-maximus]
enabled = true
port = 50000,443
filter = dark-maximus
logpath = /opt/dark-maximus/logs/application.log
maxretry = 5
bantime = 3600
findtime = 600
```

#### Настройка UFW

```bash
# Базовые правила
sudo ufw default deny incoming
sudo ufw default allow outgoing

# Разрешенные порты
sudo ufw allow ssh
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw allow 50000/tcp

# Включение UFW
sudo ufw --force enable
```

#### Регулярные обновления

```bash
# Скрипт автоматических обновлений
#!/bin/bash
# /usr/local/bin/update-dark-maximus.sh

# Обновление системы
apt update && apt upgrade -y

# Обновление Docker образов
docker compose pull

# Перезапуск сервисов
docker compose up -d

# Очистка неиспользуемых образов
docker image prune -f
```

### Мониторинг безопасности

#### Логирование безопасности

```bash
# Настройка аудита
sudo apt install -y auditd

# Правила аудита
sudo nano /etc/audit/rules.d/dark-maximus.rules
```

```bash
# Аудит доступа к файлам конфигурации
-w /opt/dark-maximus/.env -p wa -k dark-maximus-config
-w /opt/dark-maximus/users.db -p wa -k dark-maximus-db

# Аудит Docker команд
-w /usr/bin/docker -p x -k docker-commands
```

#### Мониторинг подозрительной активности

```bash
# Скрипт мониторинга безопасности
#!/bin/bash
# /usr/local/bin/security-monitor.sh

# Проверка неудачных попыток входа
grep "Failed password" /var/log/auth.log | tail -10

# Проверка подозрительных IP
netstat -tn | awk '{print $5}' | cut -d: -f1 | sort | uniq -c | sort -nr | head -10

# Проверка использования ресурсов
ps aux --sort=-%cpu | head -10
```

## 📚 Дополнительные ресурсы

- [Installation Guide](INSTALLATION.md) - полное руководство по установке
- [SSL Setup Guide](ssl-setup.md) - настройка SSL сертификатов
- [Deployment Checklist](deployment-checklist.md) - чеклист развертывания
- [User Guides](../user/getting-started.md) - руководства для пользователей

## 🆘 Поддержка

Если у вас возникли проблемы с продвинутой настройкой:

1. Проверьте логи: `docker compose logs -f`
2. Проверьте конфигурации: `nginx -t`, `docker compose config`
3. Создайте Issue в репозитории
4. Обратитесь в Telegram: [@ukarshiev](https://t.me/ukarshiev)

---

*Удачной настройки! 🚀*
