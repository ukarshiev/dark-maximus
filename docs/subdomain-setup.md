# Настройка поддоменов для Dark Maximus

## Обзор

Проект Dark Maximus использует несколько поддоменов для разных сервисов:

- `panel.dark-maximus.com` - основная панель управления (bot сервис)
- `docs.dark-maximus.com` - документация проекта (docs сервис)  
- `help.dark-maximus.com` - справочная система (codex-docs сервис)

## Архитектура

```
┌─────────────────────────────────────────────────────────────┐
│                    nginx-proxy (порт 80/443)               │
│  ┌─────────────────┬─────────────────┬─────────────────┐    │
│  │ docs.dark-      │ help.dark-      │ panel.dark-     │    │
│  │ maximus.com     │ maximus.com     │ maximus.com     │    │
│  └─────────────────┴─────────────────┴─────────────────┘    │
└─────────────────────────────────────────────────────────────┘
           │                    │                    │
           ▼                    ▼                    ▼
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│   docs:80       │  │ codex-docs:3000 │  │    bot:1488     │
│   (nginx)       │  │   (Express)     │  │   (Python)      │
└─────────────────┘  └─────────────────┘  └─────────────────┘
```

## Настройка DNS

### 1. A-записи

Создайте следующие A-записи в вашем DNS провайдере:

```
panel.dark-maximus.com    A    YOUR_SERVER_IP
docs.dark-maximus.com     A    YOUR_SERVER_IP  
help.dark-maximus.com     A    YOUR_SERVER_IP
```

### 2. CNAME записи (альтернатива)

Если у вас есть основной домен, можете использовать CNAME:

```
panel.dark-maximus.com    CNAME    dark-maximus.com
docs.dark-maximus.com     CNAME    dark-maximus.com
help.dark-maximus.com     CNAME    dark-maximus.com
```

## SSL сертификаты

### Текущая настройка

Сейчас используются самоподписанные сертификаты для тестирования. Они находятся в `nginx/ssl/`:
- `cert.pem` - сертификат
- `key.pem` - приватный ключ

### Настройка Let's Encrypt (рекомендуется для продакшена)

1. Установите certbot:
```bash
sudo apt install certbot
```

2. Получите сертификаты:
```bash
sudo certbot certonly --standalone -d panel.dark-maximus.com
sudo certbot certonly --standalone -d docs.dark-maximus.com  
sudo certbot certonly --standalone -d help.dark-maximus.com
```

3. Обновите nginx конфигурацию для использования реальных сертификатов:
```nginx
ssl_certificate /etc/letsencrypt/live/panel.dark-maximus.com/fullchain.pem;
ssl_certificate_key /etc/letsencrypt/live/panel.dark-maximus.com/privkey.pem;
```

## Проверка работы

### Локальная проверка

```bash
# Проверка HTTP редиректов
curl -H "Host: docs.dark-maximus.com" -I http://localhost
curl -H "Host: help.dark-maximus.com" -I http://localhost
curl -H "Host: panel.dark-maximus.com" -I http://localhost

# Проверка HTTPS
curl -k -H "Host: docs.dark-maximus.com" -I https://localhost
curl -k -H "Host: help.dark-maximus.com" -I https://localhost
curl -k -H "Host: panel.dark-maximus.com" -I https://localhost
```

### Проверка через браузер

1. Откройте `https://docs.dark-maximus.com` - должна загрузиться документация
2. Откройте `https://help.dark-maximus.com` - должна загрузиться справочная система
3. Откройте `https://panel.dark-maximus.com` - должна загрузиться панель управления

## Устранение проблем

### Ошибка ERR_CONNECTION_CLOSED

Эта ошибка возникает, когда:
1. DNS записи не настроены или не применились
2. nginx-proxy контейнер не запущен
3. Брандмауэр блокирует порты 80/443

**Решение:**
1. Проверьте DNS записи: `nslookup docs.dark-maximus.com`
2. Проверьте статус контейнеров: `docker compose ps`
3. Проверьте логи: `docker compose logs nginx-proxy`

### Ошибка SSL

Если браузер показывает ошибку SSL:
1. Для тестирования - добавьте исключение для самоподписанного сертификата
2. Для продакшена - настройте Let's Encrypt сертификаты

## Мониторинг

### Health checks

Каждый сервис имеет health check:
- nginx-proxy: `http://localhost/health`
- docs: `http://localhost:3001/health`
- codex-docs: `http://localhost:3002/`

### Логи

```bash
# Логи nginx-proxy
docker compose logs -f nginx-proxy

# Логи всех сервисов
docker compose logs -f
```

## Обновление конфигурации

После изменения nginx конфигурации:

```bash
# Перезапуск nginx-proxy
docker compose restart nginx-proxy

# Или полный перезапуск
docker compose up -d --build
```

---

**Дата последнего обновления:** 16.10.2025
