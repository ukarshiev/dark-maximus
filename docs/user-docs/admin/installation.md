# 🚀 Установка Dark Maximus

> Полное руководство по установке и настройке Dark Maximus на сервере

## 📋 Содержание

1. [Требования](#требования)
2. [Быстрая установка](#быстрая-установка)
3. [Ручная установка](#ручная-установка)
4. [Настройка Nginx](#настройка-nginx)
5. [Настройка SSL](#настройка-ssl)
6. [Проверка установки](#проверка-установки)
7. [Устранение проблем](#устранение-проблем)

---

## Требования

### Минимальные требования:

- **ОС:** Ubuntu 20.04+ / Debian 11+ / CentOS 8+
- **RAM:** 2 GB (рекомендуется 4 GB)
- **Диск:** 20 GB свободного места
- **Процессор:** 2 ядра
- **Интернет:** стабильное подключение

### Обязательные требования:

1. **Сервер с root-доступом** по SSH
2. **Доменное имя** с настроенной A-записью на IP сервера
3. **Панель 3x-ui** установленная на одном или нескольких серверах

### Опциональные требования:

- Docker и Docker Compose (для быстрой установки)
- Nginx (для обратного прокси)
- Certbot (для SSL-сертификатов)

---

## Быстрая установка

### Автоматическая установка "под ключ"

Этот скрипт автоматически установит все необходимое: Docker, Nginx, Certbot (для SSL), скачает бота и настроит все для вас.

#### Шаг 1: Подключитесь к серверу

```bash
ssh root@your-server-ip
```

#### Шаг 2: Выполните команду установки

```bash
curl -sSL https://raw.githubusercontent.com/ukarshiev/dark-maximus/main/install.sh | sudo bash
```

#### Шаг 3: Следуйте инструкциям установщика

Установщик попросит вас ввести:

1. **Доменное имя** (например, `my-shop.com`)
2. **Email** (для регистрации SSL-сертификата Let's Encrypt)
3. **Порт для YooKassa webhook** (по умолчанию 443)

#### Шаг 4: Завершение установки

После завершения работы скрипта вы увидите сообщение:

```bash
=====================================================
      🎉 Установка и запуск успешно завершены! 🎉
=====================================================

Веб-панель доступна по адресу:
  - https://your-domain.com/login

Данные для первого входа:
  - Логин:   admin
  - Пароль:  admin

ПЕРВЫЕ ШАГИ:
1. Войдите в панель и сразу же смените логин и пароль.
2. На странице 'Настройки' введите ваш Telegram токен, username бота и ваш Telegram ID.
3. Нажмите 'Сохранить' и затем 'Запустить Бота'.

📖 Админская документация доступна по адресу:
  - https://your-domain.com/admin/quickstart
  - https://your-domain.com/admin/guide
  - https://your-domain.com/admin/security
  - https://your-domain.com/admin/api
```

#### Что делает скрипт автоматически:

- ✅ Проверяет и устанавливает Docker
- ✅ Проверяет и устанавливает Docker Compose
- ✅ Проверяет и устанавливает Nginx
- ✅ Проверяет и устанавливает Certbot
- ✅ Клонирует репозиторий
- ✅ Настраивает Nginx
- ✅ Получает SSL-сертификат
- ✅ Собирает и запускает Docker-контейнеры
- ✅ Разворачивает админскую документацию
- ✅ Настраивает автоматический запуск при перезагрузке

---

## Ручная установка

Если вы хотите установить проект вручную или у вас уже есть Docker:

### Шаг 1: Установите зависимости

```bash
# Обновление системы
sudo apt update && sudo apt upgrade -y

# Установка Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Установка Docker Compose
sudo apt install docker-compose-plugin -y

# Установка Nginx
sudo apt install nginx -y

# Установка Certbot
sudo apt install certbot python3-certbot-nginx -y
```

### Шаг 2: Клонируйте репозиторий

```bash
git clone https://github.com/ukarshiev/dark-maximus.git
cd dark-maximus
```

### Шаг 3: Настройте переменные окружения

```bash
cp env.example .env
nano .env
```

Отредактируйте файл `.env` и укажите:

```env
# Flask секретный ключ
FLASK_SECRET_KEY=your-super-secret-key-here-change-this

# Telegram Bot настройки
TELEGRAM_BOT_TOKEN=your-telegram-bot-token
TELEGRAM_BOT_USERNAME=your-bot-username
ADMIN_TELEGRAM_ID=your-admin-telegram-id

# Домен
DOMAIN=your-domain.com

# Пароль админ-панели
PANEL_PASSWORD=your-secure-password
```

### Шаг 4: Соберите и запустите контейнеры

```bash
docker-compose up -d --build
```

### Шаг 5: Настройте Nginx

Создайте конфигурацию Nginx:

```bash
sudo nano /etc/nginx/sites-available/dark-maximus.conf
```

Вставьте:

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:1488;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Активируйте конфигурацию:

```bash
sudo ln -s /etc/nginx/sites-available/dark-maximus.conf /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

---

## Настройка SSL

### Автоматическая настройка (рекомендуется)

```bash
sudo certbot --nginx -d your-domain.com
```

Certbot автоматически:
- Получит SSL-сертификат
- Настроит Nginx для использования HTTPS
- Настроит автоматическое обновление сертификата

### Ручная настройка

```bash
# Получить сертификат
sudo certbot certonly --standalone -d your-domain.com

# Обновить конфигурацию Nginx
sudo nano /etc/nginx/sites-available/dark-maximus.conf
```

Добавьте:

```nginx
server {
    listen 443 ssl http2;
    server_name your-domain.com;

    ssl_certificate /etc/letsencrypt/live/your-domain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/your-domain.com/privkey.pem;

    location / {
        proxy_pass http://127.0.0.1:1488;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}

server {
    listen 80;
    server_name your-domain.com;
    return 301 https://$server_name$request_uri;
}
```

Перезагрузите Nginx:

```bash
sudo systemctl reload nginx
```

---

## Проверка установки

### Проверка Docker-контейнеров

```bash
docker ps
```

Должны быть запущены контейнеры:
- `dark-maximus-bot` (порт 1488)
- `dark-maximus-docs` (порт 3001)
- `dark-maximus-codex-docs` (порт 3002)

### Проверка админ-панели

Откройте в браузере:

```
https://your-domain.com/login
```

Войдите с логином `admin` и паролем `admin`.

### Проверка документации

Откройте в браузере:

```
https://your-domain.com/
```

Должна открыться документация с разделом "📖 Админская документация".

### Проверка логов

```bash
# Логи бота
docker logs dark-maximus-bot

# Логи документации
docker logs dark-maximus-docs

# Логи codex.docs
docker logs dark-maximus-codex-docs
```

---

## Устранение проблем

### Проблема: Контейнер не запускается

**Решение:**

```bash
# Проверить логи
docker logs dark-maximus-bot

# Пересобрать контейнер
docker-compose down
docker-compose up -d --build
```

### Проблема: Ошибка подключения к базе данных

**Решение:**

```bash
# Проверить права на файл базы данных
ls -la users.db

# Создать резервную копию
cp users.db users.db.backup

# Пересоздать базу данных (ОСТОРОЖНО: удалит все данные!)
rm users.db
docker-compose restart
```

### Проблема: Nginx не запускается

**Решение:**

```bash
# Проверить конфигурацию
sudo nginx -t

# Проверить логи
sudo tail -f /var/log/nginx/error.log

# Перезапустить Nginx
sudo systemctl restart nginx
```

### Проблема: SSL-сертификат не получен

**Решение:**

```bash
# Проверить, что домен указывает на сервер
nslookup your-domain.com

# Проверить, что порты 80 и 443 открыты
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp

# Получить сертификат вручную
sudo certbot certonly --standalone -d your-domain.com
```

### Проблема: Документация не отображается

**Решение:**

```bash
# Проверить контейнер документации
docker ps | grep docs

# Перезапустить контейнер
docker restart dark-maximus-docs

# Проверить логи
docker logs dark-maximus-docs
```

---

## Обновление проекта

### Автоматическое обновление

```bash
sudo bash install.sh
```

Скрипт автоматически:
- Обновит код из Git
- Пересоберет контейнеры
- Обновит админскую документацию
- Перезапустит сервисы

### Ручное обновление

```bash
# Перейти в папку проекта
cd dark-maximus

# Обновить код
git pull

# Пересобрать контейнеры
docker-compose down
docker-compose up -d --build

# Обновить документацию
bash setup-admin-docs.sh
```

---

## Удаление проекта

### Полное удаление

```bash
# Остановить контейнеры
docker-compose down

# Удалить контейнеры и volumes
docker-compose down -v

# Удалить папку проекта
cd ..
rm -rf dark-maximus

# Удалить конфигурацию Nginx
sudo rm /etc/nginx/sites-available/dark-maximus.conf
sudo rm /etc/nginx/sites-enabled/dark-maximus.conf
sudo systemctl reload nginx

# Удалить SSL-сертификат (опционально)
sudo certbot delete --cert-name your-domain.com
```

---

## Дополнительные ресурсы

- [Быстрый старт](quickstart.md) — первые шаги после установки
- [Полное руководство](guide.md) — детальная документация по админ-панели
- [Чек-лист безопасности](security.md) — рекомендации по безопасности
- [API документация](api.md) — REST API для интеграции

---

## Поддержка

Если у вас возникли проблемы при установке:

1. Проверьте раздел [Устранение проблем](#устранение-проблем) выше
2. Проверьте [FAQ](../faq.md)
3. Проверьте [Решение проблем](../troubleshooting.md)
4. Обратитесь в поддержку проекта

**Полезные ссылки:**
- [GitHub Issues](https://github.com/ukarshiev/dark-maximus/issues)
- [Документация](https://github.com/ukarshiev/dark-maximus/docs)
- [Wiki](https://github.com/ukarshiev/dark-maximus/wiki)

---

**Версия документа:** 1.0  
**Последнее обновление:** 2025-01-XX  
**Автор:** Dark Maximus Team

