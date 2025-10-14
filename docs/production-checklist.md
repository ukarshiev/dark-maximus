# ✅ Чеклист подготовки к production

> Последнее обновление: 12.10.2025
> Версия: 2.39.2 | Дата: 29.12.2024

## 🧹 Очистка проекта

- [x] Удалены все тестовые файлы
- [x] Удалены временные скрипты
- [x] Удалены пустые директории
- [x] Проект готов к развертыванию

## 📋 Требования к серверу

### Минимальные требования
- [ ] Ubuntu 20.04+ / Debian 11+ / CentOS 8+
- [ ] 2 GB RAM (рекомендуется 4 GB)
- [ ] 2 CPU cores (рекомендуется 4 cores)
- [ ] 20 GB свободного места на диске
- [ ] Статический IP-адрес

### Доменные имена
- [ ] Основной домен: `panel.your-domain.com` (A-запись → IP сервера)
- [ ] Поддомен документации: `docs.your-domain.com` (A-запись → IP сервера)
- [ ] Поддомен админ-документации: `help.your-domain.com` (A-запись → IP сервера)
- [ ] Домен для 3x-ui панели: `panel.example.com` (опционально)
- [ ] Все DNS записи настроены и указывают на сервер

**Пример:**
- [ ] `panel.dark-maximus.com` → IP_СЕРВЕРА
- [ ] `docs.dark-maximus.com` → IP_СЕРВЕРА
- [ ] `help.dark-maximus.com` → IP_СЕРВЕРА

## 🔧 Установка базовых компонентов

### 1. Обновление системы
```bash
sudo apt update && sudo apt upgrade -y
```

### 2. Установка Docker
```bash
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER
```

### 3. Установка Docker Compose
```bash
sudo apt install -y docker-compose
```

### 4. Настройка файрвола
```bash
# UFW (Ubuntu/Debian)
sudo ufw allow ssh
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw allow 1488/tcp
sudo ufw --force enable
```

**Примечание**: Порты 3001 и 3002 (документация) НЕ нужно открывать в файрволе, так как они доступны только через localhost и проксируются через Nginx.

## 🚀 Установка проекта

### Автоматическая установка (рекомендуется)
```bash
curl -sSL https://raw.githubusercontent.com/ukarshiev/dark-maximus/main/install.sh | sudo bash
```

**Скрипт установит:**
- ✅ Все зависимости
- ✅ Nginx
- ✅ SSL сертификаты (Let's Encrypt)
- ✅ Docker контейнеры
- ✅ Базовую конфигурацию

## 🔒 Настройка SSL (КРИТИЧЕСКИ ВАЖНО!)

### ⚠️ НЕ используйте встроенный SSL в 3x-ui!

**Проблема:** Встроенный SSL в 3x-ui нестабилен и "слетает" через некоторое время.

### Решение: Nginx + Let's Encrypt

```bash
# Автоматическая настройка
curl -sSL https://raw.githubusercontent.com/ukarshiev/dark-maximus/main/setup-ssl.sh | sudo bash
```

### Настройка 3x-ui после SSL
- [ ] Listen IP: `127.0.0.1`
- [ ] Port: `2053`
- [ ] TLS/SSL: **ОТКЛЮЧИТЬ** ⚠️

**Архитектура:**
```
Интернет → Nginx (SSL) → 3x-ui (localhost без SSL)
```

## ⚙️ Первоначальная настройка

### 1. Вход в веб-панель
- [ ] Откройте: `https://your-domain.com/login`
- [ ] Логин: `admin`
- [ ] Пароль: `admin`

### 2. Изменение учетных данных (ОБЯЗАТЕЛЬНО!)
- [ ] Смените логин администратора
- [ ] Смените пароль администратора
- [ ] Используйте сильный пароль (минимум 12 символов)

### 3. Настройка Telegram бота
- [ ] Получите токен у [@BotFather](https://t.me/BotFather)
- [ ] Введите токен бота
- [ ] Введите username бота (без @)
- [ ] Введите Telegram ID администратора

### 4. Добавление сервера 3x-ui
- [ ] Название сервера
- [ ] URL панели 3x-ui
- [ ] Логин администратора
- [ ] Пароль администратора

### 5. Создание тарифов
- [ ] Минимум 1 тарифный план
- [ ] Название тарифа
- [ ] Цена в рублях
- [ ] Период действия (дни)
- [ ] Лимит трафика (ГБ)

### 6. Настройка платежных систем

#### YooKassa
- [ ] Зарегистрируйтесь на [yookassa.ru](https://yookassa.ru)
- [ ] Получите Shop ID
- [ ] Получите Secret Key
- [ ] Введите данные в панель
- [ ] Настройте webhook: `https://your-domain.com/yookassa-webhook`

#### CryptoBot
- [ ] Создайте приложение в [@CryptoBot](https://t.me/CryptoBot)
- [ ] Получите API токен
- [ ] Введите данные в панель
- [ ] Настройте webhook: `https://your-domain.com/cryptobot-webhook`

### 7. Запуск бота
- [ ] Нажмите "Сохранить все настройки"
- [ ] Нажмите "Запустить Бота" в шапке сайта

## 🔐 Безопасность

### SSH
- [ ] Отключите root-логин
- [ ] Используйте SSH ключи вместо паролей
- [ ] Измените стандартный порт SSH (опционально)

### Fail2ban
```bash
sudo apt install -y fail2ban
sudo systemctl enable fail2ban
sudo systemctl start fail2ban
```

### Регулярные бэкапы
```bash
# Создание бэкапа базы данных
cp users.db backups/users_$(date +%Y%m%d_%H%M%S).db
```

### Обновления системы
```bash
# Настройте автоматические обновления
sudo apt install -y unattended-upgrades
sudo dpkg-reconfigure -plow unattended-upgrades
```

## 📊 Мониторинг

### Логи Docker
```bash
docker-compose logs -f
docker-compose logs -f bot
```

### Использование ресурсов
```bash
docker stats
df -h
free -h
```

### Проверка SSL
```bash
sudo certbot certificates
sudo certbot renew --dry-run
```

## ✅ Проверка работоспособности

### Веб-панель
- [ ] Доступна по HTTPS без ошибок
- [ ] Логин работает корректно
- [ ] Все страницы загружаются

### Telegram бот
- [ ] Бот отвечает на команду /start
- [ ] Меню отображается корректно
- [ ] Можно просмотреть тарифы

### Платежи
- [ ] Создается тестовая транзакция
- [ ] Webhook получает уведомления
- [ ] Ключи создаются автоматически

### 3x-ui
- [ ] Панель доступна через Nginx
- [ ] SSL работает корректно
- [ ] Ключи создаются в панели

## 🔄 Обновления

### Проверка обновлений
```bash
cd dark-maximus
git pull origin main
```

### Обновление через скрипт
```bash
curl -sSL https://raw.githubusercontent.com/ukarshiev/dark-maximus/main/install.sh | sudo bash
```

### Ручное обновление
```bash
docker-compose down
git pull origin main
docker-compose up -d --build
```

## 🆘 Устранение проблем

### Бот не запускается
```bash
docker-compose logs bot
docker-compose restart bot
```

### SSL не работает
```bash
sudo nginx -t
sudo systemctl restart nginx
sudo certbot renew --force-renewal
```

### 3x-ui не доступен
```bash
# Проверьте, что 3x-ui на localhost
sudo netstat -tlnp | grep 2053

# Проверьте настройки в панели 3x-ui
```

### База данных повреждена
```bash
# Восстановите из бэкапа
cp backups/users_YYYYMMDD_HHMMSS.db users.db
docker-compose restart
```

## 📚 Документация

### Основные руководства
- [Полное руководство по развертыванию](server-deployment.md)
- [Настройка SSL для 3x-ui](ssl-setup-guide.md)
- [Быстрая шпаргалка по SSL](ssl-quick-guide.md)
- [FAQ](FAQ.md)

### API документация
- [Поиск пользователей](api/search-users.md)
- [Пополнение баланса](api/topup-balance.md)
- [Управление уведомлениями](api/create-notification.md)

## 📞 Поддержка

### Получение помощи
- **GitHub Issues**: [Создать Issue](https://github.com/ukarshiev/dark-maximus/issues)
- **Telegram**: [@ukarshiev](https://t.me/ukarshiev)
- **Email**: support@example.com

### Полезные команды
```bash
# Статус всех сервисов
docker-compose ps

# Перезапуск всех сервисов
docker-compose restart

# Просмотр логов
docker-compose logs -f

# Проверка дискового пространства
df -h

# Очистка Docker
docker system prune -a
```

## ✨ Готово к production!

После выполнения всех пунктов чеклиста ваш сервис готов к работе в production-среде!

**Важные напоминания:**
- 🔒 Регулярно обновляйте систему и компоненты
- 💾 Делайте бэкапы базы данных
- 📊 Мониторьте использование ресурсов
- 🔐 Следите за безопасностью
- 📈 Анализируйте логи

---

*Успешного запуска! 🚀*
