# 🚀 Руководство по развертыванию на сервере

> Обновлено: 29.12.2024

## 📋 Требования к серверу

### Минимальные требования
- **ОС**: Ubuntu 20.04+ / Debian 11+ / CentOS 8+
- **RAM**: 2 GB (рекомендуется 4 GB)
- **CPU**: 2 ядра (рекомендуется 4 ядра)
- **Диск**: 20 GB свободного места
- **Сеть**: Статический IP-адрес

### Рекомендуемые характеристики
- **RAM**: 4-8 GB
- **CPU**: 4+ ядер
- **Диск**: 50+ GB SSD
- **Сеть**: Выделенный IP, домен с SSL

## 🔧 Подготовка сервера

### 1. Обновление системы

```bash
# Ubuntu/Debian
sudo apt update && sudo apt upgrade -y

# CentOS/RHEL
sudo yum update -y
# или для новых версий
sudo dnf update -y
```

### 2. Установка необходимых пакетов

```bash
# Ubuntu/Debian
sudo apt install -y curl wget git unzip software-properties-common

# CentOS/RHEL
sudo yum install -y curl wget git unzip epel-release
```

### 3. Настройка файрвола

```bash
# UFW (Ubuntu/Debian)
sudo ufw allow ssh
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw allow 1488/tcp
sudo ufw --force enable

# FirewallD (CentOS/RHEL)
sudo firewall-cmd --permanent --add-service=ssh
sudo firewall-cmd --permanent --add-service=http
sudo firewall-cmd --permanent --add-service=https
sudo firewall-cmd --permanent --add-port=1488/tcp
sudo firewall-cmd --reload
```

## 🐳 Установка Docker

### Автоматическая установка (рекомендуется)

```bash
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER
```

### Ручная установка

```bash
# Ubuntu/Debian
sudo apt install -y docker.io docker-compose
sudo systemctl start docker
sudo systemctl enable docker

# CentOS/RHEL
sudo yum install -y docker docker-compose
sudo systemctl start docker
sudo systemctl enable docker
```

## 🌐 Настройка домена и DNS

### 1. Покупка домена
- Рекомендуемые регистраторы: Namecheap, GoDaddy, REG.RU
- Выберите домен с поддержкой DNS-записей

### 2. Настройка DNS-записей
Создайте A-запись, указывающую на IP вашего сервера:

```
Тип: A
Имя: @ (или ваш домен)
Значение: IP_АДРЕС_СЕРВЕРА
TTL: 300 (5 минут)
```

### 3. Проверка DNS
```bash
# Проверьте, что домен указывает на ваш сервер
nslookup your-domain.com
dig your-domain.com
```

## 🚀 Установка проекта

### Автоматическая установка (рекомендуется)

```bash
# Скачайте и запустите скрипт установки
curl -sSL https://raw.githubusercontent.com/ukarshiev/dark-maximus/main/install.sh | sudo bash
```

Скрипт автоматически:
- Установит все зависимости
- Настроит Nginx
- Получит SSL-сертификат
- Запустит проект в Docker

### Ручная установка

#### 1. Клонирование репозитория

```bash
git clone https://github.com/ukarshiev/dark-maximus.git
cd dark-maximus
```

#### 2. Настройка переменных окружения

```bash
cp env.example .env
nano .env
```

Основные настройки в `.env`:
```env
# Основные настройки
DEBUG=False
SECRET_KEY=your-secret-key-here
DOMAIN=your-domain.com

# База данных
DATABASE_URL=sqlite:///users.db

# Telegram
TELEGRAM_BOT_TOKEN=your-bot-token
TELEGRAM_BOT_USERNAME=your-bot-username
ADMIN_TELEGRAM_ID=your-telegram-id

# YooKassa
YOOKASSA_SHOP_ID=your-shop-id
YOOKASSA_SECRET_KEY=your-secret-key
```

#### 3. Запуск через Docker

```bash
# Сборка и запуск
docker-compose up -d --build

# Проверка статуса
docker-compose ps

# Просмотр логов
docker-compose logs -f
```

## 🔒 Настройка SSL-сертификата

### ⚠️ Важно: НЕ используйте встроенный SSL в 3x-ui!

**Проблемы встроенного SSL в 3x-ui:**
- Сертификаты нестабильны и часто "слетают"
- Сложная отладка проблем
- Конфликты с автообновлением
- Ограниченные возможности настройки

**Рекомендуемая архитектура:**
```
Интернет → Nginx (SSL) → 3x-ui (без SSL, localhost)
```

### Автоматическая настройка SSL (рекомендуется)

Используйте специальный скрипт для настройки SSL через Nginx и Let's Encrypt:

```bash
# Скачайте и запустите скрипт
curl -sSL https://raw.githubusercontent.com/ukarshiev/dark-maximus/main/setup-ssl.sh -o setup-ssl.sh
chmod +x setup-ssl.sh
sudo ./setup-ssl.sh
```

Скрипт автоматически:
- Установит Certbot
- Получит SSL-сертификаты для бота и 3x-ui панели
- Настроит Nginx как reverse proxy
- Настроит автообновление сертификатов

### Ручная настройка

```bash
# 1. Установка Certbot
sudo apt install -y certbot python3-certbot-nginx

# 2. Получение сертификата для бота
sudo certbot --nginx -d your-domain.com --email your-email@example.com --agree-tos --non-interactive --redirect

# 3. Получение сертификата для 3x-ui панели (если отдельный домен)
sudo certbot --nginx -d panel.your-domain.com --email your-email@example.com --agree-tos --non-interactive --redirect

# 4. Автоматическое обновление
sudo crontab -e
# Добавьте строку:
# 0 12 * * * /usr/bin/certbot renew --quiet --post-hook "systemctl reload nginx"
```

### Настройка 3x-ui для работы с Nginx

После настройки SSL в Nginx, настройте 3x-ui:

1. Зайдите в 3x-ui панель
2. Перейдите в настройки панели
3. Установите:
   - **Listen IP**: `127.0.0.1` (только localhost)
   - **Port**: `2053` (или другой локальный порт)
   - **TLS**: `Отключить` ⚠️ (SSL обрабатывает Nginx)

4. Сохраните настройки и перезапустите 3x-ui

### Проверка работы SSL

```bash
# Проверка сертификатов
sudo certbot certificates

# Тест обновления
sudo certbot renew --dry-run

# Проверка Nginx
sudo nginx -t

# Проверка доступности
curl -I https://your-domain.com
curl -I https://panel.your-domain.com
```

## ⚙️ Настройка Nginx

### Конфигурация для production

```nginx
server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name your-domain.com;

    ssl_certificate /etc/letsencrypt/live/your-domain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/your-domain.com/privkey.pem;
    include /etc/letsencrypt/options-ssl-nginx.conf;
    ssl_dhparam /etc/letsencrypt/ssl-dhparams.pem;

    # Безопасность
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header Referrer-Policy "no-referrer-when-downgrade" always;
    add_header Content-Security-Policy "default-src 'self' http: https: data: blob: 'unsafe-inline'" always;

    # Основное приложение
    location / {
        proxy_pass http://127.0.0.1:1488;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # Таймауты
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }

    # Вебхуки
    location /yookassa-webhook {
        proxy_pass http://127.0.0.1:1488;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /cryptobot-webhook {
        proxy_pass http://127.0.0.1:1488;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}

# Редирект с HTTP на HTTPS
server {
    listen 80;
    listen [::]:80;
    server_name your-domain.com;
    return 301 https://$server_name$request_uri;
}
```

### Применение конфигурации

```bash
# Проверка конфигурации
sudo nginx -t

# Перезагрузка Nginx
sudo systemctl reload nginx

# Проверка статуса
sudo systemctl status nginx
```

## 🔧 Первоначальная настройка

### 1. Вход в веб-панель

Откройте браузер и перейдите по адресу: `https://your-domain.com/login`

**Данные по умолчанию:**
- Логин: `admin`
- Пароль: `admin`

⚠️ **ВАЖНО**: Сразу же смените логин и пароль!

### 2. Настройка Telegram бота

1. Перейдите в **Настройки → Настройки Панели**
2. Заполните обязательные поля:
   - **Токен бота**: Получите у [@BotFather](https://t.me/BotFather)
   - **Username бота**: Без символа @
   - **Telegram ID Администратора**: Ваш Telegram ID

### 3. Добавление сервера

1. В разделе **Настройки** найдите "Управление Хостами"
2. Добавьте данные вашей панели 3x-ui:
   - **Название**: Любое понятное название
   - **URL**: Адрес панели (например, `https://your-panel.com`)
   - **Логин**: Логин администратора панели
   - **Пароль**: Пароль администратора панели

### 4. Создание тарифов

1. После добавления хоста создайте тарифные планы
2. Пример тарифа:
   - **Название**: "1 месяц"
   - **Цена**: 100 RUB
   - **Период**: 30 дней
   - **Описание**: "Месячный доступ к VPN"

### 5. Запуск бота

1. Нажмите **"Сохранить все настройки"**
2. В шапке сайта нажмите зеленую кнопку **"Запустить Бота"**

## 💳 Настройка платежных систем

### YooKassa

1. **Регистрация**: Зарегистрируйтесь на [yookassa.ru](https://yookassa.ru)
2. **Получение ключей**: В личном кабинете получите Shop ID и Secret Key
3. **Настройка в панели**: Введите ключи в разделе "Настройки Платежных Систем"
4. **Вебхук**: Укажите URL: `https://your-domain.com/yookassa-webhook`

### CryptoBot

1. **Создание приложения**: В [@CryptoBot](https://t.me/CryptoBot) создайте приложение
2. **Настройка вебхука**: Включите вебхуки на `https://your-domain.com/cryptobot-webhook`
3. **Настройка в панели**: Введите данные приложения в настройках

## 📊 Мониторинг и логи

### Просмотр логов

```bash
# Все сервисы
docker-compose logs -f

# Только бот
docker-compose logs -f bot

# Только веб-сервер
docker-compose logs -f web
```

### Мониторинг ресурсов

```bash
# Использование ресурсов контейнерами
docker stats

# Использование диска
df -h

# Использование памяти
free -h

# Загрузка процессора
top
```

### Настройка логирования

```bash
# Ротация логов Docker
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

## 🔄 Обновления

### Автоматическое обновление

```bash
# Обновление до последней версии
curl -sSL https://raw.githubusercontent.com/ukarshiev/dark-maximus/main/install.sh | sudo bash
```

### Ручное обновление

```bash
# Остановка сервисов
docker-compose down

# Обновление кода
git pull origin main

# Пересборка и запуск
docker-compose up -d --build

# Проверка статуса
docker-compose ps
```

## 🛡️ Безопасность

### Рекомендации по безопасности

1. **Регулярные обновления**:
   ```bash
   sudo apt update && sudo apt upgrade -y
   ```

2. **Настройка SSH**:
   ```bash
   sudo nano /etc/ssh/sshd_config
   ```
   - Отключите root-логин
   - Используйте ключи вместо паролей
   - Измените стандартный порт

3. **Настройка fail2ban**:
   ```bash
   sudo apt install -y fail2ban
   sudo systemctl enable fail2ban
   ```

4. **Регулярные бэкапы**:
   ```bash
   # Создание бэкапа базы данных
   cp users.db backups/users_$(date +%Y%m%d_%H%M%S).db
   ```

### Мониторинг безопасности

```bash
# Проверка открытых портов
sudo netstat -tlnp

# Проверка активных соединений
sudo ss -tuln

# Проверка логов безопасности
sudo journalctl -u ssh
sudo tail -f /var/log/auth.log
```

## 🚨 Устранение неполадок

### Частые проблемы

#### 1. Бот не запускается
```bash
# Проверьте логи
docker-compose logs bot

# Проверьте настройки
docker-compose exec bot python -c "from shop_bot.config import *; print('Config OK')"
```

#### 2. Проблемы с SSL
```bash
# Проверьте сертификат
sudo certbot certificates

# Обновите сертификат
sudo certbot renew --force-renewal
```

#### 3. Проблемы с Nginx
```bash
# Проверьте конфигурацию
sudo nginx -t

# Проверьте статус
sudo systemctl status nginx

# Перезапустите
sudo systemctl restart nginx
```

#### 4. Проблемы с Docker
```bash
# Очистка неиспользуемых ресурсов
docker system prune -a

# Перезапуск Docker
sudo systemctl restart docker
```

### Диагностика

```bash
# Проверка всех сервисов
docker-compose ps
sudo systemctl status nginx
sudo systemctl status docker

# Проверка портов
sudo netstat -tlnp | grep -E ':(80|443|1488)'

# Проверка DNS
nslookup your-domain.com
```

## 📞 Поддержка

Если у вас возникли проблемы:

1. **Проверьте FAQ**: [docs/FAQ.md](FAQ.md)
2. **Создайте Issue**: [GitHub Issues](https://github.com/ukarshiev/dark-maximus/issues)
3. **Telegram поддержка**: [@ukarshiev](https://t.me/ukarshiev)

## 📝 Дополнительные ресурсы

- [Архитектура проекта](architecture-rules.md)
- [API документация](api/)
- [Модули и интеграции](modules.md)
- [Безопасность](security.md)

---

*Удачного развертывания! Если у вас есть вопросы, не стесняйтесь обращаться за помощью.*
