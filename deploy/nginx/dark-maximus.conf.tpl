# Upstream серверы для Docker контейнеров (localhost)
upstream bot_backend {
    server 127.0.0.1:50000;
    keepalive 32;
}

upstream docs_backend {
    server 127.0.0.1:50001;
    keepalive 32;
}

upstream codex_docs_backend {
    server 127.0.0.1:50002;
    keepalive 32;
}

upstream user_cabinet_backend {
    server 127.0.0.1:50003;
    keepalive 32;
}

upstream allure_backend {
    server 127.0.0.1:50005;
    keepalive 32;
}

# HTTP редирект на HTTPS для основного домена
server {
    listen 80;
    server_name ${MAIN_DOMAIN};
    return 301 https://$host$request_uri;
}

# HTTPS сервер для основного домена (редирект на пользовательскую документацию)
server {
    listen 443 ssl http2;
    server_name ${MAIN_DOMAIN};

    # SSL сертификаты
    ssl_certificate /etc/letsencrypt/live/${MAIN_DOMAIN}/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/${MAIN_DOMAIN}/privkey.pem;
    include /etc/nginx/snippets/ssl-params.conf;

    # Основной домен не должен открывать панель → делаем редирект на документацию
    location / {
        return 302 https://${DOCS_DOMAIN}$request_uri;
    }
}

# HTTP редирект на HTTPS для panel поддомена
server {
    listen 80;
    server_name ${PANEL_DOMAIN};
    return 301 https://$host$request_uri;
}

# HTTPS сервер для panel поддомена
server {
    listen 443 ssl http2;
    server_name ${PANEL_DOMAIN};

    # SSL сертификаты
    ssl_certificate /etc/letsencrypt/live/${PANEL_DOMAIN}/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/${PANEL_DOMAIN}/privkey.pem;
    include /etc/nginx/snippets/ssl-params.conf;

    # Ограничение размера загружаемых файлов
    client_max_body_size 20m;

    # Проксирование на bot сервис
    location / {
        proxy_pass http://bot_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Forwarded-Host $host;
        proxy_set_header X-Forwarded-Port $server_port;

        # Таймауты
        proxy_connect_timeout 30s;
        proxy_send_timeout 30s;
        proxy_read_timeout 30s;

        # Буферизация
        proxy_buffering on;
        proxy_buffer_size 4k;
        proxy_buffers 8 4k;
    }

    # Health check
    location /health {
        proxy_pass http://bot_backend/health;
        access_log off;
    }
}

# HTTP редирект на HTTPS для документации
server {
    listen 80;
    server_name ${DOCS_DOMAIN};
    return 301 https://$host$request_uri;
}

# HTTPS сервер для документации
server {
    listen 443 ssl http2;
    server_name ${DOCS_DOMAIN};

    # SSL сертификаты
    ssl_certificate /etc/letsencrypt/live/${DOCS_DOMAIN}/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/${DOCS_DOMAIN}/privkey.pem;
    include /etc/nginx/snippets/ssl-params.conf;

    # Ограничение размера загружаемых файлов
    client_max_body_size 20m;

    # Проксирование на docs сервис (разрешаем внешние CDN для docsify)
    location / {
        proxy_pass http://docs_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Forwarded-Host $host;
        proxy_set_header X-Forwarded-Port $server_port;

        # Таймауты
        proxy_connect_timeout 30s;
        proxy_send_timeout 30s;
        proxy_read_timeout 30s;
    }

    # Пер-доменный CSP для docs: разрешаем jsdelivr CDN для скриптов/стилей и data: для стилей/шрифтов
    add_header Content-Security-Policy "default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.jsdelivr.net; style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net data:; img-src 'self' data: https:; font-src 'self' data:; connect-src 'self' wss: https:; frame-ancestors 'none';" always;

    # Health check
    location /health {
        proxy_pass http://docs_backend/health;
        access_log off;
    }
}

# HTTP редирект на HTTPS для Allure
server {
    listen 80;
    server_name ${ALLURE_DOMAIN};
    return 301 https://$host$request_uri;
}

# HTTPS сервер для Allure
server {
    listen 443 ssl http2;
    server_name ${ALLURE_DOMAIN};

    # SSL сертификаты
    ssl_certificate /etc/letsencrypt/live/${ALLURE_DOMAIN}/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/${ALLURE_DOMAIN}/privkey.pem;
    include /etc/nginx/snippets/ssl-params.conf;

    # Ограничение размера загружаемых файлов
    client_max_body_size 20m;

    # Проксирование на allure-homepage сервис
    location / {
        proxy_pass http://allure_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Forwarded-Host $host;
        proxy_set_header X-Forwarded-Port $server_port;

        # Таймауты
        proxy_connect_timeout 30s;
        proxy_send_timeout 30s;
        proxy_read_timeout 30s;

        # Буферизация
        proxy_buffering on;
        proxy_buffer_size 4k;
        proxy_buffers 8 4k;
    }

    # Health check
    location /health {
        proxy_pass http://allure_backend/health;
        access_log off;
    }
}

# HTTP редирект на HTTPS для админской документации
server {
    listen 80;
    server_name ${HELP_DOMAIN};
    return 301 https://$host$request_uri;
}

# HTTPS сервер для админской документации
server {
    listen 443 ssl http2;
    server_name ${HELP_DOMAIN};

    # SSL сертификаты
    ssl_certificate /etc/letsencrypt/live/${HELP_DOMAIN}/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/${HELP_DOMAIN}/privkey.pem;
    include /etc/nginx/snippets/ssl-params.conf;

    # Ограничение размера загружаемых файлов
    client_max_body_size 20m;

    # Проксирование на codex-docs сервис (может требовать внешние ресурсы)
    location / {
        proxy_pass http://codex_docs_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Forwarded-Host $host;
        proxy_set_header X-Forwarded-Port $server_port;

        # WebSocket поддержка с оптимизацией
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_read_timeout 60m;
        proxy_buffering off;

        # Таймауты
        proxy_connect_timeout 30s;
        proxy_send_timeout 30s;
    }

    # Убираем заголовки, запрещающие встраивание, и разрешаем iframe из личного кабинета
    proxy_hide_header X-Frame-Options;
    proxy_hide_header Content-Security-Policy;
    add_header X-Frame-Options "ALLOWALL" always;
    add_header Content-Security-Policy "default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval' https:; style-src 'self' 'unsafe-inline' https: data:; img-src 'self' data: https:; font-src 'self' data:; connect-src 'self' wss: https:; frame-ancestors 'self' https://${APP_DOMAIN} http://localhost:50003;" always;

    # Health check
    location /health {
        proxy_pass http://codex_docs_backend/;
        access_log off;
    }
}

# HTTP редирект на HTTPS для личного кабинета
server {
    listen 80;
    server_name ${APP_DOMAIN};
    return 301 https://$host$request_uri;
}

# HTTPS сервер для личного кабинета
server {
    listen 443 ssl http2;
    server_name ${APP_DOMAIN};

    # SSL сертификаты
    ssl_certificate /etc/letsencrypt/live/${APP_DOMAIN}/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/${APP_DOMAIN}/privkey.pem;
    include /etc/nginx/snippets/ssl-params.conf;

    # Ограничение размера загружаемых файлов
    client_max_body_size 20m;

    # Проксирование на user-cabinet сервис
    location / {
        proxy_pass http://user_cabinet_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Forwarded-Host $host;
        proxy_set_header X-Forwarded-Port $server_port;

        # Таймауты
        proxy_connect_timeout 30s;
        proxy_send_timeout 30s;
        proxy_read_timeout 30s;

        # Буферизация
        proxy_buffering on;
        proxy_buffer_size 4k;
        proxy_buffers 8 4k;
    }

    # Скрываем CSP заголовки от backend, чтобы nginx мог установить свои
    proxy_hide_header Content-Security-Policy;

    # Разрешаем фреймы для встраивания help.dark-maximus.com и subscription links
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header Content-Security-Policy "default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.jsdelivr.net https://api.2ip.ru; style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; img-src 'self' data: https:; font-src 'self' data:; connect-src 'self' https://api.2ip.ru https://api.2ip.io https://ipwho.is https://${HELP_DOMAIN} https://*.${MAIN_DOMAIN}; frame-src 'self' https://${HELP_DOMAIN} https://*.${MAIN_DOMAIN}; frame-ancestors 'self';" always;

    # Health check
    location /health {
        proxy_pass http://user_cabinet_backend/health;
        access_log off;
        # CSP заголовки для health endpoint (для тестирования)
        add_header Content-Security-Policy "default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.jsdelivr.net https://api.2ip.ru; style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; img-src 'self' data: https:; font-src 'self' data:; connect-src 'self' https://api.2ip.ru https://api.2ip.io https://ipwho.is https://${HELP_DOMAIN} https://*.${MAIN_DOMAIN}; frame-src 'self' https://${HELP_DOMAIN} https://*.${MAIN_DOMAIN}; frame-ancestors 'self';" always;
    }
}

# Блокировка неопознанных доменов
server {
    listen 80 default_server;
    server_name _;
    return 444;
}

server {
    listen 443 ssl default_server;
    server_name _;

    # Заглушка SSL сертификат
    ssl_certificate /etc/letsencrypt/live/${MAIN_DOMAIN}/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/${MAIN_DOMAIN}/privkey.pem;
    include /etc/nginx/snippets/ssl-params.conf;

    return 444;
}


