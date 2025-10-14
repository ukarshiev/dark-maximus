# ✅ Чеклист развертывания на боевом сервере

> Последнее обновление: 14.10.2025  
> Версия: 2.66.13

## 📋 Подготовка к развертыванию

### 1. Требования к серверу

- [ ] **ОС**: Ubuntu 20.04+ / Debian 11+
- [ ] **RAM**: минимум 2 GB (рекомендуется 4 GB)
- [ ] **CPU**: минимум 2 ядра (рекомендуется 4)
- [ ] **Диск**: минимум 20 GB свободного места
- [ ] **Сеть**: Статический IP-адрес
- [ ] **Доступ**: SSH доступ с правами sudo

### 2. Домены и DNS

- [ ] Куплен основной домен (например, `dark-maximus.com`)
- [ ] Настроены DNS A-записи для всех поддоменов:
  ```
  panel.your-domain.com        → IP_СЕРВЕРА (основной бот)
  docs.your-domain.com         → IP_СЕРВЕРА (пользовательская документация)
  help.your-domain.com         → IP_СЕРВЕРА (админская документация)
  ```
- [ ] Проверена работа DNS (можно использовать `nslookup` или `dig`)
- [ ] Дождались распространения DNS (обычно 5-15 минут)

**Пример:**
```
panel.dark-maximus.com       → IP_СЕРВЕРА
docs.dark-maximus.com        → IP_СЕРВЕРА
help.dark-maximus.com        → IP_СЕРВЕРА
```

### 3. Файрвол

- [ ] Открыты необходимые порты:
  - `22` (SSH)
  - `80` (HTTP для Let's Encrypt)
  - `443` (HTTPS)
  - `1488` (основной бот)
- [ ] **НЕ нужно** открывать порты 3001 и 3002 (они доступны только через localhost)

## 🚀 Развертывание

### 1. Подключение к серверу

```bash
ssh user@your-server-ip
```

### 2. Запуск установки

```bash
curl -sSL https://raw.githubusercontent.com/ukarshiev/dark-maximus/main/install.sh | sudo bash
```

### 3. Следование инструкциям установщика

- [ ] Введен основной домен (например, `your-domain.com`)
- [ ] Введен email для SSL-сертификатов
- [ ] Выбран порт для вебхуков (443 или 8443)
- [ ] Дождались завершения установки

### 4. Проверка установки

```bash
# Проверка статуса контейнеров
docker compose ps

# Ожидаемый результат:
# NAME                      STATUS         PORTS
# dark-maximus-bot          Up X seconds   0.0.0.0:1488->1488/tcp
# dark-maximus-docs         Up X seconds   0.0.0.0:3001->8080/tcp
# dark-maximus-codex-docs   Up X seconds   0.0.0.0:3002->3000/tcp
```

### 5. Проверка доступности

- [ ] Основной бот: `https://panel.your-domain.com/login`
- [ ] Пользовательская документация: `https://docs.your-domain.com`
- [ ] Админская документация: `https://help.your-domain.com`

## ⚙️ Первоначальная настройка

### 1. Вход в админ-панель

- [ ] Открыт `https://your-domain.com/login`
- [ ] Войдено с логином `admin` и паролем `admin`

### 2. Смена учетных данных (ОБЯЗАТЕЛЬНО!)

- [ ] Переход в Настройки → Настройки Панели
- [ ] Изменен логин администратора
- [ ] Изменен пароль администратора (сильный пароль 12+ символов)

### 3. Настройка Telegram бота

- [ ] Получен токен бота от [@BotFather](https://t.me/BotFather)
- [ ] Введен токен бота в настройки
- [ ] Введен username бота (без @)
- [ ] Введен Telegram ID администратора

### 4. Добавление сервера 3x-ui

- [ ] Добавлен первый сервер в разделе "Управление Хостами"
- [ ] Введены данные подключения к 3x-ui панели
- [ ] Проверено подключение к панели

### 5. Создание тарифов

- [ ] Создан хотя бы один тарифный план
- [ ] Указана цена в рублях
- [ ] Указан период действия (дни)
- [ ] Указан лимит трафика (ГБ)

### 6. Запуск бота

- [ ] Нажата кнопка "Сохранить все настройки"
- [ ] Нажата зеленая кнопка "Запустить Бота" в шапке
- [ ] Проверена работа бота в Telegram

## 💳 Настройка платежных систем

### YooKassa

- [ ] Зарегистрированы на [yookassa.ru](https://yookassa.ru)
- [ ] Получены Shop ID и Secret Key
- [ ] Введены данные в настройки бота
- [ ] Настроен webhook URL в личном кабинете YooKassa:
  ```
  https://your-domain.com/yookassa-webhook
  ```
- [ ] Проверена работа платежей (тестовая транзакция)

### CryptoBot

- [ ] Создано приложение в [@CryptoBot](https://t.me/CryptoBot)
- [ ] Получен API токен
- [ ] Введены данные в настройки бота
- [ ] Настроен webhook URL в CryptoBot:
  ```
  https://your-domain.com/cryptobot-webhook
  ```
- [ ] Проверена работа платежей

## 🔒 Безопасность

### SSH

- [ ] Отключен вход под root (если возможно)
- [ ] Настроены SSH ключи вместо паролей
- [ ] Изменен стандартный порт SSH (опционально)

### Fail2ban

```bash
sudo apt install -y fail2ban
sudo systemctl enable fail2ban
sudo systemctl start fail2ban
```

- [ ] Установлен и запущен fail2ban

### Автоматические обновления

```bash
sudo apt install -y unattended-upgrades
sudo dpkg-reconfigure -plow unattended-upgrades
```

- [ ] Настроены автоматические обновления системы

## 📊 Мониторинг

### Логи

```bash
# Логи всех сервисов
docker compose logs -f

# Логи конкретного сервиса
docker compose logs -f bot
docker compose logs -f docs
docker compose logs -f codex-docs
```

### Использование ресурсов

```bash
# Мониторинг ресурсов
docker stats

# Использование диска
df -h

# Использование памяти
free -h
```

### Healthcheck

```bash
# Проверка здоровья контейнеров
docker compose ps

# Детальная информация
docker inspect dark-maximus-bot | grep Health -A 10
```

## 💾 Резервное копирование

### База данных

```bash
# Создание бэкапа
cp users.db backups/users_$(date +%Y%m%d_%H%M%S).db

# Автоматические бэкапы (настроить в cron)
0 2 * * * cd /path/to/dark-maximus && cp users.db backups/users_$(date +\%Y\%m\%d).db
```

- [ ] Настроено регулярное резервное копирование базы данных
- [ ] Настроено резервное копирование в облако (опционально)

### Docker Volumes

```bash
# Бэкап volumes
docker run --rm -v dark-maximus_sessions_data:/data -v $(pwd)/backups:/backup alpine tar czf /backup/sessions_data_$(date +%Y%m%d).tar.gz /data
```

- [ ] Настроено резервное копирование Docker volumes

## 🔄 Обновления

### Автоматическое обновление

```bash
curl -sSL https://raw.githubusercontent.com/ukarshiev/dark-maximus/main/install.sh | sudo bash
```

### Ручное обновление

```bash
# Обновление кода
git pull origin main

# Пересборка и перезапуск
docker compose down
docker compose build
docker compose up -d

# Проверка статуса
docker compose ps
```

## ✅ Финальная проверка

### Функциональность

- [ ] Бот отвечает на команду `/start`
- [ ] Меню отображается корректно
- [ ] Можно просмотреть тарифы
- [ ] Создается тестовая транзакция
- [ ] Webhook получает уведомления
- [ ] Ключи создаются автоматически

### Безопасность

- [ ] SSL сертификаты действительны
- [ ] Все пароли изменены
- [ ] SSH защищен
- [ ] Файрвол настроен
- [ ] Fail2ban активен

### Документация

- [ ] Документация доступна по всем адресам
- [ ] Все ссылки работают
- [ ] Поиск работает

## 📚 Дополнительные ресурсы

- [Docker Architecture](docker-architecture.md)
- [Installation Guide](installation.md)
- [Production Checklist](production-checklist.md)
- [Security Checklist](security-checklist.md)
- [Admin Quickstart](admin-quickstart.md)
- [Admin Panel Guide](admin-panel-guide.md)

## 🆘 Поддержка

Если возникли проблемы:

1. Проверьте [FAQ](FAQ.md)
2. Проверьте [Troubleshooting](troubleshooting.md)
3. Проверьте логи: `docker compose logs -f`
4. Создайте Issue в репозитории
5. Обратитесь в Telegram: [@ukarshiev](https://t.me/ukarshiev)

---

**Готово к production!** 🚀

*Последнее обновление: 14.10.2025*

