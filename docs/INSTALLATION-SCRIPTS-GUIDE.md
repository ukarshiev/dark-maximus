# Руководство по скриптам установки Dark Maximus

*Последнее обновление: 17.10.2025*

## Обзор архитектуры

Система установки Dark Maximus состоит из двух независимых скриптов:

1. **`install.sh`** - базовая установка системы
2. **`ssl-install.sh`** - настройка SSL сертификатов

## 1. install.sh - Базовая установка

### Назначение
- Устанавливает систему и зависимости
- Настраивает Docker и контейнеры
- Создает HTTP nginx конфигурацию
- Запускает все сервисы

### Использование
```bash
# С доменом как аргумент
curl -sSL https://raw.githubusercontent.com/ukarshiev/dark-maximus/main/install.sh | sudo bash -s -- example.com

# С доменом через переменную окружения
DOMAIN=example.com curl -sSL https://raw.githubusercontent.com/ukarshiev/dark-maximus/main/install.sh | sudo bash

# Интерактивный режим (если запущен локально)
sudo ./install.sh example.com
```

### Что делает
1. Клонирует репозиторий в `/opt/dark-maximus`
2. Устанавливает системные зависимости
3. Устанавливает Docker и Docker Compose
4. Создает временную nginx конфигурацию
5. Запускает Docker контейнеры
6. Активирует полную HTTP nginx конфигурацию
7. Настраивает UFW файрвол
8. Создает systemd сервис для автозапуска

### Результат
- Система работает по HTTP
- Все сервисы доступны на localhost портах
- Nginx проксирует запросы на контейнеры
- В конце показывается команда для настройки SSL

## 2. ssl-install.sh - Настройка SSL

### Назначение
- Получает SSL сертификаты Let's Encrypt
- Создает HTTPS nginx конфигурацию
- Настраивает автообновление сертификатов

### Использование
```bash
# С доменом как аргумент
curl -sSL https://raw.githubusercontent.com/ukarshiev/dark-maximus/main/ssl-install.sh | sudo bash -s -- example.com

# Интерактивный режим
sudo ./ssl-install.sh example.com
```

### Что делает
1. **Проверяет/создает HTTP nginx конфигурацию** (если нужно)
2. **Проверяет/запускает Docker контейнеры** (если нужно)
3. Проверяет DNS записи
4. Устанавливает Certbot
5. Получает SSL сертификаты
6. Создает HTTPS nginx конфигурацию с редиректами
7. Настраивает автообновление сертификатов

### Результат
- Все сервисы работают по HTTPS
- HTTP автоматически редиректится на HTTPS
- Сертификаты обновляются автоматически

## Сценарии использования

### 1. Первая установка
```bash
# 1. Установка системы
curl -sSL https://raw.githubusercontent.com/ukarshiev/dark-maximus/main/install.sh | sudo bash -s -- example.com

# 2. Настройка DNS записей для всех поддоменов
# panel.example.com -> IP сервера
# docs.example.com -> IP сервера  
# help.example.com -> IP сервера

# 3. Настройка SSL
curl -sSL https://raw.githubusercontent.com/ukarshiev/dark-maximus/main/ssl-install.sh | sudo bash -s -- example.com
```

### 2. Обновление кода (без потери SSL)
```bash
# Только переустановка системы
curl -sSL https://raw.githubusercontent.com/ukarshiev/dark-maximus/main/install.sh | sudo bash -s -- example.com
# SSL настройки остаются нетронутыми
```

### 3. Переустановка SSL
```bash
# Только переустановка SSL
curl -sSL https://raw.githubusercontent.com/ukarshiev/dark-maximus/main/ssl-install.sh | sudo bash -s -- example.com
```

### 4. Тестирование без SSL
```bash
# Установка только HTTP версии
curl -sSL https://raw.githubusercontent.com/ukarshiev/dark-maximus/main/install.sh | sudo bash -s -- example.com
# SSL не настраивается, система работает по HTTP
```

## Преимущества архитектуры

### ✅ Гибкость
- Можно установить систему без SSL для тестирования
- Можно настроить SSL позже, когда DNS готов
- Можно переустановить только SSL без переустановки системы

### ✅ Безопасность
- SSL настройка не мешает основной установке
- Можно безопасно обновлять код без потери SSL
- Отладочные порты доступны только с localhost

### ✅ Надежность
- Каждый скрипт решает свою задачу
- Улучшенная обработка ошибок
- Подробная диагностика проблем

### ✅ Простота
- Понятные команды для каждого сценария
- Автоматическая проверка зависимостей
- Подробные инструкции в конце установки

## Устранение неполадок

### Проблема: "nginx конфигурация не найдена"
**Решение**: Запустите сначала `install.sh`

### Проблема: "Контейнеры не запущены"
**Решение**: `ssl-install.sh` автоматически запустит их

### Проблема: "DNS записи не настроены"
**Решение**: Настройте A-записи для всех поддоменов на IP сервера

### Проблема: "Домен не указан"
**Решение**: Передайте домен как аргумент: `sudo bash -s -- example.com`

## Полезные команды

```bash
# Проверка статуса контейнеров
cd /opt/dark-maximus && docker compose ps

# Просмотр логов
cd /opt/dark-maximus && docker compose logs -f

# Проверка nginx
nginx -t

# Перезапуск nginx
systemctl restart nginx

# Проверка SSL сертификатов
certbot certificates

# Тест обновления SSL
certbot renew --dry-run
```

## Файлы конфигурации

- **HTTP nginx**: `/etc/nginx/sites-available/dark-maximus`
- **HTTPS nginx**: `/etc/nginx/sites-available/dark-maximus-ssl`
- **SSL параметры**: `/etc/nginx/snippets/ssl-params.conf`
- **SSL сертификаты**: `/etc/letsencrypt/live/`
- **Проект**: `/opt/dark-maximus/`
- **Логи SSL**: `/var/log/ssl-renewal.log`
