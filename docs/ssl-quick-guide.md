# 🔒 SSL для 3x-ui - Быстрая шпаргалка

> Последнее обновление: 12.10.2025

## ⚠️ ВАЖНО: НЕ используйте встроенный SSL в 3x-ui!

**Проблема:** Встроенный SSL в 3x-ui нестабилен - сертификаты "слетают" через некоторое время.

**Решение:** Используйте Nginx + Let's Encrypt

## 🚀 Быстрая установка (1 команда)

```bash
curl -sSL https://raw.githubusercontent.com/ukarshiev/dark-maximus/main/setup-ssl.sh | sudo bash
```

## 📋 Архитектура

```
Интернет → Nginx (SSL) → 3x-ui (localhost, без SSL)
```

## ⚙️ Настройки 3x-ui после установки SSL

В панели 3x-ui установите:

- **Listen IP**: `127.0.0.1` ⚠️
- **Port**: `2053`
- **TLS/SSL**: `❌ ОТКЛЮЧИТЬ` ⚠️

## 🔍 Проверка работы

```bash
# Проверка сертификатов
sudo certbot certificates

# Тест автообновления
sudo certbot renew --dry-run

# Проверка доступности
curl -I https://your-domain.com
```

## 🛠️ Быстрое решение проблем

### Проблема: Сертификат не работает
```bash
sudo nginx -t
sudo systemctl restart nginx
```

### Проблема: 3x-ui не доступен
```bash
# Проверьте, что 3x-ui на localhost
sudo netstat -tlnp | grep 2053
```

### Проблема: Не обновляется автоматически
```bash
# Проверьте cron
sudo crontab -l

# Принудительное обновление
sudo certbot renew --force-renewal
```

## 📚 Полная документация

Подробности: [docs/ssl-setup-guide.md](docs/ssl-setup-guide.md)

## 🆘 Поддержка

- [FAQ](docs/FAQ.md)
- [Issues](https://github.com/ukarshiev/dark-maximus/issues)
- Telegram: [@ukarshiev](https://t.me/ukarshiev)

---

**Помните:** SSL обрабатывает Nginx, а не 3x-ui!
