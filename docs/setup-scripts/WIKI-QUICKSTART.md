# 🚀 Wiki для пользователей - Быстрый старт

## ✅ Что уже сделано (локально)

### 📁 Созданная структура:
```
docs/
├── user-docs/              # База знаний для пользователей
│   ├── index.html         # Docsify интерфейс
│   ├── _sidebar.md        # Навигация
│   ├── README.md          # Главная
│   ├── setup/             # Инструкции
│   │   ├── android.md
│   │   ├── ios.md
│   │   ├── windows.md
│   │   ├── macos.md
│   │   └── linux.md
│   ├── faq.md
│   ├── troubleshooting.md
│   └── payment.md
├── nginx-docs.conf         # Конфигурация nginx
└── wiki-deployment.md      # Полная инструкция по развертыванию
```

### 🐳 Docker контейнер:
- **Образ**: nginx:alpine (~10 MB)
- **Порт**: 3001
- **Статус**: ✅ Запущен и работает
- **URL**: http://localhost:3001

### 🎨 Возможности:
- ✅ Красивый интерфейс на базе Docsify
- ✅ Полнотекстовый поиск
- ✅ Навигация по разделам
- ✅ Копирование кода одним кликом
- ✅ Пагинация между страницами
- ✅ Адаптивный дизайн

---

## 🌐 Проверка локально

Откройте в браузере:
```
http://localhost:3001
```

Вы должны увидеть:
- Красивую главную страницу
- Боковое меню с разделами
- Поле поиска вверху
- Инструкции для всех платформ

---

## 🚀 Что делать дальше

### 1️⃣ Подготовьте поддомен

Зарегистрируйте A-запись в DNS:
```
docs.your-domain.com  →  IP сервера
```

### 2️⃣ Развертывание на сервере

Подробная инструкция: **[docs/wiki-deployment.md](docs/wiki-deployment.md)**

Краткая версия:
```bash
# На сервере
cd ~/dark-maximus
git pull origin main
docker compose up -d docs

# Настройка Nginx + SSL
sudo certbot certonly --nginx -d docs.your-domain.com
sudo nano /etc/nginx/sites-available/docs.your-domain.com
# (скопируйте конфигурацию из wiki-deployment.md)
sudo ln -s /etc/nginx/sites-available/docs.your-domain.com /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

### 3️⃣ Интеграция с ботом

Добавьте кнопку в бота:
```python
InlineKeyboardButton("📚 База знаний", url="https://docs.your-domain.com")
```

---

## 📝 Редактирование контента

Просто редактируйте `.md` файлы в `docs/user-docs/`:

```bash
# Отредактируйте любой файл
nano docs/user-docs/faq.md

# Перезапустите контейнер (опционально)
docker compose restart docs
```

Изменения применяются автоматически!

---

## 🔍 Проверка статуса

```bash
# Статус контейнеров
docker compose ps

# Логи Wiki
docker compose logs -f docs

# Потребление ресурсов
docker stats dark-maximus-docs
```

---

## 🎯 Что в итоге получилось

### Для пользователей:
- ✅ Красивая и понятная база знаний
- ✅ Инструкции по настройке для всех платформ
- ✅ FAQ и решение проблем
- ✅ Информация об оплате
- ✅ Поиск по документации

### Для вас:
- ✅ Меньше вопросов в поддержку
- ✅ Профессиональный вид проекта
- ✅ Простое обновление контента
- ✅ SEO-оптимизация (Google индексирует)
- ✅ Минимальное потребление ресурсов

### Технически:
- ✅ Полная изоляция от бота
- ✅ Независимый контейнер
- ✅ Легковесный (nginx:alpine)
- ✅ Безопасный (read-only volumes)
- ✅ Масштабируемый

---

## 📚 Полезные ссылки

- **[Полная инструкция по развертыванию](docs/wiki-deployment.md)**
- **[README Wiki](docs/user-docs/WIKI-README.md)**
- **[Документация Docsify](https://docsify.js.org/)**

---

## ❓ Нужна помощь?

Если что-то не работает:
1. Проверьте логи: `docker compose logs docs`
2. Проверьте статус: `docker compose ps`
3. Смотрите раздел Troubleshooting в `docs/wiki-deployment.md`

---

**🎉 Готово! Wiki развернута локально и готова к переносу на сервер!**

