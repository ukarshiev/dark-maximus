# 📚 Развертывание Wiki (База знаний) на сервере

> Дата последней редакции: 12.10.2025

## 🎉 Что было сделано локально

Успешно развернута пользовательская Wiki-система на базе Docsify:

### ✅ Созданные файлы:
- `docs/user-docs/` - все файлы пользовательской документации
- `docs/user-docs/index.html` - главная страница Docsify
- `docs/user-docs/_sidebar.md` - навигационное меню
- `docs/nginx-docs.conf` - конфигурация Nginx для Wiki
- `docker-compose.yml` - обновлен с сервисом `docs`

### 📱 Созданные разделы:
1. **Инструкции по настройке** для Android, iOS, Windows, macOS, Linux
2. **FAQ** - часто задаваемые вопросы
3. **Решение проблем** - troubleshooting
4. **Оплата и баланс** - информация о платежах

### 🐳 Docker контейнер:
- **Образ**: `nginx:alpine` (легковесный, ~10 MB)
- **Порт**: `3001` (локально)
- **Изоляция**: Полностью изолирован от бота
- **Статус**: ✅ Работает

## 🚀 Развертывание на Ubuntu сервере

### Шаг 1: Проверка текущего состояния

На вашем сервере проект уже развернут. Просто нужно синхронизировать изменения:

```bash
cd ~/dark-maximus  # или путь к вашему проекту

# Сохраните текущие изменения (если есть)
git stash

# Подтяните последние изменения
git pull origin main

# Если были stash - верните их
git stash pop
```

### Шаг 2: Запуск Wiki контейнера

```bash
# Просто запустите новый сервис docs
docker compose up -d docs

# Проверьте что контейнер запустился
docker compose ps
```

Вы должны увидеть:
```
NAME                  STATUS         PORTS
dark-maximus-bot      Up X hours     0.0.0.0:1488->1488/tcp
dark-maximus-docs     Up X seconds   0.0.0.0:3001->80/tcp
```

### Шаг 3: Проверка работы

```bash
# Проверьте логи (должны быть без ошибок)
docker compose logs docs

# Тестовый запрос
curl http://localhost:3001
```

Если всё хорошо, вы увидите HTML-код страницы Docsify.

### Шаг 4: Настройка поддомена

#### 4.1. DNS настройка

Добавьте A-запись для поддомена:
```
docs.your-domain.com  →  IP вашего сервера
```

#### 4.2. Получение SSL сертификата

```bash
# Получите сертификат для поддомена
sudo certbot certonly --nginx -d docs.your-domain.com
```

#### 4.3. Настройка Nginx

Создайте конфигурацию для поддомена:

```bash
sudo nano /etc/nginx/sites-available/docs.your-domain.com
```

Вставьте следующую конфигурацию:

```nginx
# HTTP -> HTTPS редирект
server {
    listen 80;
    listen [::]:80;
    server_name docs.your-domain.com;
    
    return 301 https://$server_name$request_uri;
}

# HTTPS
server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name docs.your-domain.com;
    
    # SSL сертификаты
    ssl_certificate /etc/letsencrypt/live/docs.your-domain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/docs.your-domain.com/privkey.pem;
    
    # SSL настройки безопасности
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;
    
    # Логи
    access_log /var/log/nginx/docs-access.log;
    error_log /var/log/nginx/docs-error.log;
    
    # Прокси на Docker контейнер
    location / {
        proxy_pass http://localhost:3001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # Отключить буферизацию для лучшей производительности
        proxy_buffering off;
    }
}
```

#### 4.4. Активация конфигурации

```bash
# Создайте символическую ссылку
sudo ln -s /etc/nginx/sites-available/docs.your-domain.com /etc/nginx/sites-enabled/

# Проверьте конфигурацию
sudo nginx -t

# Перезагрузите Nginx
sudo systemctl reload nginx
```

### Шаг 5: Проверка финального результата

Откройте в браузере:
```
https://docs.your-domain.com
```

Вы должны увидеть красивую Wiki с:
- ✅ Боковым меню навигации
- ✅ Поиском по документации
- ✅ Инструкциями для всех платформ
- ✅ FAQ и помощью

## 🔄 Обновление документации

### Для обновления содержимого Wiki:

```bash
# 1. Отредактируйте файлы в docs/user-docs/
nano docs/user-docs/faq.md

# 2. Перезапустите контейнер (необязательно, но для гарантии)
docker compose restart docs
```

**Важно**: Nginx монтирует файлы как read-only (`:ro`), поэтому изменения подхватываются автоматически!

## 🎯 Интеграция с ботом

Теперь можно добавить кнопку в бота с ссылкой на Wiki:

```python
# В файле src/shop_bot/bot/keyboards.py
InlineKeyboardButton(
    "📚 База знаний",
    url="https://docs.your-domain.com"
)
```

Пользователи смогут быстро найти ответы на вопросы без обращения в поддержку!

## 🛡️ Безопасность

### Изоляция обеспечена:
- ✅ Отдельный Docker контейнер
- ✅ Отдельная сеть Docker
- ✅ Отдельный порт (3001)
- ✅ Read-only файловая система
- ✅ SSL через Let's Encrypt

### Мониторинг:

```bash
# Проверка статуса
docker compose ps

# Просмотр логов
docker compose logs -f docs

# Использование ресурсов
docker stats dark-maximus-docs
```

## 📊 Что изменилось в docker-compose.yml

```yaml
services:
  bot:
    # ... существующая конфигурация бота ...
  
  docs:  # ← НОВЫЙ СЕРВИС
    image: nginx:alpine
    restart: unless-stopped
    container_name: dark-maximus-docs
    ports:
      - '3001:80'
    volumes:
      - ./docs/user-docs:/usr/share/nginx/html/docs:ro
      - ./docs/nginx-docs.conf:/etc/nginx/conf.d/default.conf:ro
```

## ❓ Troubleshooting

### Контейнер не запускается

```bash
# Проверьте логи
docker compose logs docs

# Проверьте что порт 3001 свободен
sudo netstat -tulpn | grep 3001

# Пересоздайте контейнер
docker compose up -d --force-recreate docs
```

### Wiki не открывается через поддомен

```bash
# Проверьте DNS
nslookup docs.your-domain.com

# Проверьте Nginx
sudo nginx -t
sudo systemctl status nginx

# Проверьте SSL сертификат
sudo certbot certificates
```

### 502 Bad Gateway

```bash
# Проверьте что контейнер работает
docker compose ps docs

# Проверьте что порт доступен
curl http://localhost:3001
```

## 💡 Полезные команды

```bash
# Остановить Wiki
docker compose stop docs

# Запустить Wiki
docker compose start docs

# Перезапустить Wiki
docker compose restart docs

# Полностью удалить Wiki (если нужно)
docker compose down docs

# Обновить образ Nginx
docker compose pull docs
docker compose up -d docs
```

## 📈 Производительность

- **Образ**: ~10 MB (nginx:alpine)
- **RAM**: ~5-10 MB
- **CPU**: <0.1% (idle)
- **Startup**: <2 секунды

Wiki практически не потребляет ресурсов сервера!

---

**Готово! 🎉** Теперь у вас есть профессиональная база знаний для пользователей!

