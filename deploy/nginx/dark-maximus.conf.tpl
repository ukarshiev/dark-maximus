# Upstream серверы для Docker контейнеров (localhost)
upstream bot_backend {
    server 127.0.0.1:1488;
    keepalive 32;
}

upstream docs_backend {
    server 127.0.0.1:3001;
    keepalive 32;
}

upstream codex_docs_backend {
    server 127.0.0.1:3002;
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

    # Пер-доменный CSP для help: допускаем безопасные внешние источники при необходимости
    add_header Content-Security-Policy "default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval' https:; style-src 'self' 'unsafe-inline' https: data:; img-src 'self' data: https:; font-src 'self' data:; connect-src 'self' wss: https:; frame-ancestors 'none';" always;

    # Health check
    location /health {
        proxy_pass http://codex_docs_backend/;
        access_log off;
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


