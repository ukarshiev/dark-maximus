#!/bin/bash
# Генерация самоподписанных SSL сертификатов

# Создаем приватный ключ
openssl genrsa -out key.pem 2048

# Создаем самоподписанный сертификат
openssl req -new -x509 -key key.pem -out cert.pem -days 365 \
    -subj "/C=RU/ST=Moscow/L=Moscow/O=DarkMaximus/OU=IT/CN=dark-maximus.com"

echo "SSL сертификаты созданы:"
echo "- key.pem (приватный ключ)"
echo "- cert.pem (сертификат)"
