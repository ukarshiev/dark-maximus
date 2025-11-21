# Исправление 502 Bad Gateway для allure.dark-maximus.com/allure-docker-service/

## Описание проблемы

При обращении к `https://allure.dark-maximus.com/allure-docker-service/` возникает ошибка **502 Bad Gateway**.

## Архитектура

Текущая схема проксирования:
```
allure.dark-maximus.com → nginx → allure-homepage:50005 → allure-service:5050
```

## Диагностика

### Шаг 1: Выполнение скрипта диагностики на сервере

Подключитесь к боевому серверу через SSH:
```bash
ssh root@31.56.27.129
```

Выполните скрипт диагностики:

**Для Linux/Bash:**
```bash
cd /path/to/dark-maximus
chmod +x scripts/diagnose-allure-502.sh
./scripts/diagnose-allure-502.sh
```

**Для PowerShell (если доступен):**
```powershell
cd /path/to/dark-maximus
chmod +x scripts/diagnose-allure-502.ps1
./scripts/diagnose-allure-502.ps1
```

### Шаг 2: Ручная диагностика (если скрипт недоступен)

#### 2.1. Проверка статуса контейнеров
```bash
docker ps | grep allure
```

Ожидаемый результат:
- `dark-maximus-allure` (allure-service) - должен быть запущен
- `dark-maximus-allure-homepage` - должен быть запущен

#### 2.2. Проверка логов контейнеров
```bash
# Логи allure-homepage
docker logs --tail 100 dark-maximus-allure-homepage

# Логи allure-service
docker logs --tail 100 dark-maximus-allure
```

Ищите ошибки:
- `Connection refused` - проблема с подключением к allure-service
- `502 Bad Gateway` - allure-homepage не может подключиться к allure-service
- `Name resolution failed` - проблема с DNS внутри Docker сети

#### 2.3. Проверка доступности портов
```bash
# Проверка allure-homepage
curl -v http://127.0.0.1:50005/health

# Проверка проксирования через allure-homepage
curl -v http://127.0.0.1:50005/allure-docker-service/
```

#### 2.4. Проверка подключения allure-homepage к allure-service
```bash
# Проверка изнутри контейнера allure-homepage
docker exec dark-maximus-allure-homepage curl -v http://allure-service:5050/allure-docker-service/ --max-time 5
```

#### 2.5. Проверка переменных окружения
```bash
docker exec dark-maximus-allure-homepage printenv ALLURE_SERVICE_URL
```

Ожидаемое значение: `http://allure-service:5050`

#### 2.6. Проверка логов nginx
```bash
tail -50 /var/log/nginx/error.log | grep allure.dark-maximus.com
```

#### 2.7. Проверка конфигурации nginx
```bash
nginx -t
```

#### 2.8. Проверка upstream в конфигурации nginx
```bash
grep -A 3 "upstream allure_backend" /etc/nginx/sites-enabled/dark-maximus.conf
```

Ожидаемое значение: `server 127.0.0.1:50005;`

## Решения

### Решение 1: Перезапуск контейнеров

Если контейнеры запущены, но не отвечают:

```bash
# Перезапуск allure-service
docker restart dark-maximus-allure

# Перезапуск allure-homepage
docker restart dark-maximus-allure-homepage

# Проверка статуса
docker ps | grep allure
```

### Решение 2: Проверка сети Docker

Убедитесь, что оба контейнера находятся в одной сети:

```bash
# Проверка сети контейнеров
docker inspect dark-maximus-allure | grep -A 10 Networks
docker inspect dark-maximus-allure-homepage | grep -A 10 Networks
```

Оба контейнера должны быть в сети `dark-maximus-network`.

### Решение 3: Проверка переменных окружения

Проверьте `docker-compose.yml` на сервере:

```bash
cd /path/to/dark-maximus
grep -A 5 "allure-homepage:" docker-compose.yml | grep ALLURE_SERVICE_URL
```

Должно быть: `ALLURE_SERVICE_URL=http://allure-service:5050`

Если значение неправильное, исправьте и перезапустите:

```bash
docker-compose up -d allure-homepage
```

### Решение 4: Обновление конфигурации nginx

Если конфигурация nginx устарела, обновите её:

1. Скопируйте обновленный файл `deploy/nginx/dark-maximus.conf.tpl` на сервер
2. Сгенерируйте конфигурацию (если используется шаблон)
3. Проверьте конфигурацию:
   ```bash
   nginx -t
   ```
4. Перезагрузите nginx:
   ```bash
   systemctl reload nginx
   ```

### Решение 5: Проверка доступности allure-service

Проверьте, что allure-service доступен на внутреннем порту:

```bash
# Из контейнера allure-homepage
docker exec dark-maximus-allure-homepage curl -v http://allure-service:5050/allure-docker-service/ --max-time 5
```

Если это не работает, проверьте:
1. Запущен ли контейнер `dark-maximus-allure`
2. Находится ли он в сети `dark-maximus-network`
3. Открыт ли порт 5050 внутри контейнера

### Решение 6: Пересоздание контейнеров

Если ничего не помогает, пересоздайте контейнеры:

```bash
cd /path/to/dark-maximus
docker-compose stop allure-service allure-homepage
docker-compose rm -f allure-service allure-homepage
docker-compose up -d allure-service allure-homepage
```

## Проверка исправления

После выполнения исправлений проверьте:

1. **Доступность через nginx:**
   ```bash
   curl -I https://allure.dark-maximus.com/allure-docker-service/
   ```

2. **Health check:**
   ```bash
   curl https://allure.dark-maximus.com/health
   ```

3. **Логи nginx:**
   ```bash
   tail -f /var/log/nginx/error.log
   ```

## Предотвращение проблемы

1. **Мониторинг контейнеров:**
   - Настройте мониторинг статуса контейнеров
   - Используйте health checks в docker-compose.yml

2. **Логирование:**
   - Регулярно проверяйте логи контейнеров
   - Настройте алерты на ошибки 502

3. **Автоматический перезапуск:**
   - Убедитесь, что в docker-compose.yml установлен `restart: unless-stopped`

## Связанные файлы

- `docker-compose.yml` - конфигурация сервисов
- `deploy/nginx/dark-maximus.conf.tpl` - шаблон конфигурации nginx
- `scripts/diagnose-allure-502.sh` - скрипт диагностики (Bash)
- `scripts/diagnose-allure-502.ps1` - скрипт диагностики (PowerShell)

## Дополнительная информация

- [Документация Allure Docker Service](https://github.com/frankescobar/allure-docker-service)
- [Документация nginx](https://nginx.org/ru/docs/)

