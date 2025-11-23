#!/usr/bin/env bash

set -euo pipefail

# Параметры
DOMAIN="${1:?Ошибка: укажите домен как первый аргумент}"

CONF_AVAIL="/etc/nginx/sites-available/subs.conf"
CONF_ENAB="/etc/nginx/sites-enabled/subs.conf"
CERT_DIR="/root/cert/${DOMAIN}"

# Значения по умолчанию для портов
CONFIG_PANEL_PORT="${2:-8443}"
SUBS_PORT="${3:-2096}"

echo "=========================================="
echo "Проверка установки 3x-ui и nginx"
echo "Домен: ${DOMAIN}"
echo "=========================================="
echo ""

# Массив для хранения результатов проверок
declare -a CHECKS
declare -a RESULTS

# Функция для добавления проверки
add_check() {
    local name="$1"
    local result="$2"
    CHECKS+=("$name")
    RESULTS+=("$result")
}

# 1. Проверка статуса сервисов
echo "[1/8] Проверка статуса сервисов..."

if systemctl is-active --quiet nginx; then
    echo "✓ Nginx работает"
    add_check "Статус nginx" "✓"
else
    echo "✗ Nginx не работает"
    add_check "Статус nginx" "✗"
fi

if systemctl list-unit-files | grep -q "x-ui.service"; then
    if systemctl is-active --quiet x-ui 2>/dev/null; then
        echo "✓ 3x-ui работает"
        add_check "Статус 3x-ui" "✓"
    else
        echo "⚠ 3x-ui не работает (но это может быть нормально)"
        add_check "Статус 3x-ui" "⚠"
    fi
else
    echo "⚠ Сервис x-ui не найден в systemd"
    add_check "Статус 3x-ui" "⚠"
fi

echo ""

# 2. Проверка доступности портов локально
echo "[2/8] Проверка доступности портов локально..."

if curl -k -s -o /dev/null -w "%{http_code}" --connect-timeout 2 http://127.0.0.1:${CONFIG_PANEL_PORT}/configpanel 2>/dev/null | grep -q "200\|301\|302"; then
    echo "✓ Порт ${CONFIG_PANEL_PORT} (configpanel) доступен локально"
    add_check "Порт ${CONFIG_PANEL_PORT} (configpanel)" "✓"
else
    echo "✗ Порт ${CONFIG_PANEL_PORT} (configpanel) недоступен локально"
    add_check "Порт ${CONFIG_PANEL_PORT} (configpanel)" "✗"
fi

if curl -k -s -o /dev/null -w "%{http_code}" --connect-timeout 2 http://127.0.0.1:${SUBS_PORT}/subs/ 2>/dev/null | grep -q "200\|301\|302"; then
    echo "✓ Порт ${SUBS_PORT} (subs) доступен локально"
    add_check "Порт ${SUBS_PORT} (subs)" "✓"
else
    echo "✗ Порт ${SUBS_PORT} (subs) недоступен локально"
    add_check "Порт ${SUBS_PORT} (subs)" "✗"
fi

echo ""

# 3. Проверка конфигурации nginx
echo "[3/8] Проверка конфигурации nginx..."

if nginx -t >/dev/null 2>&1; then
    echo "✓ Синтаксис конфигурации nginx корректен"
    add_check "Синтаксис nginx" "✓"
else
    echo "✗ Ошибка в конфигурации nginx"
    nginx -t 2>&1 | head -5
    add_check "Синтаксис nginx" "✗"
fi

if [ -f "$CONF_AVAIL" ]; then
    echo "✓ Конфигурация найдена: $CONF_AVAIL"
    add_check "Конфигурация nginx (sites-available)" "✓"
else
    echo "✗ Конфигурация не найдена: $CONF_AVAIL"
    add_check "Конфигурация nginx (sites-available)" "✗"
fi

if [ -L "$CONF_ENAB" ]; then
    echo "✓ Символическая ссылка найдена: $CONF_ENAB"
    add_check "Конфигурация nginx (sites-enabled)" "✓"
else
    echo "✗ Символическая ссылка не найдена: $CONF_ENAB"
    add_check "Конфигурация nginx (sites-enabled)" "✗"
fi

echo ""

# 4. Проверка SSL-сертификатов
echo "[4/8] Проверка SSL-сертификатов..."

if [ -f "${CERT_DIR}/fullchain.pem" ]; then
    echo "✓ fullchain.pem найден"
    add_check "Сертификат fullchain.pem" "✓"
    
    # Проверка валидности сертификата
    if openssl x509 -in "${CERT_DIR}/fullchain.pem" -noout -dates >/dev/null 2>&1; then
        NOT_BEFORE=$(openssl x509 -in "${CERT_DIR}/fullchain.pem" -noout -startdate | cut -d= -f2)
        NOT_AFTER=$(openssl x509 -in "${CERT_DIR}/fullchain.pem" -noout -enddate | cut -d= -f2)
        echo "  Действителен с: ${NOT_BEFORE}"
        echo "  Действителен до: ${NOT_AFTER}"
        
        # Проверка, не истек ли сертификат
        EXPIRY_EPOCH=$(date -d "$NOT_AFTER" +%s 2>/dev/null || echo "0")
        CURRENT_EPOCH=$(date +%s)
        if [ "$EXPIRY_EPOCH" -gt "$CURRENT_EPOCH" ]; then
            DAYS_LEFT=$(( (EXPIRY_EPOCH - CURRENT_EPOCH) / 86400 ))
            echo "  Осталось дней: ${DAYS_LEFT}"
            add_check "Срок действия сертификата" "✓ (${DAYS_LEFT} дней)"
        else
            echo "  ⚠ Сертификат истек!"
            add_check "Срок действия сертификата" "✗ (истек)"
        fi
    else
        echo "  ✗ Сертификат невалиден"
        add_check "Валидность сертификата" "✗"
    fi
else
    echo "✗ fullchain.pem не найден"
    add_check "Сертификат fullchain.pem" "✗"
fi

if [ -f "${CERT_DIR}/privkey.pem" ]; then
    echo "✓ privkey.pem найден"
    add_check "Приватный ключ privkey.pem" "✓"
    
    # Проверка прав доступа
    PERMS=$(stat -c "%a" "${CERT_DIR}/privkey.pem" 2>/dev/null || echo "000")
    if [ "$PERMS" = "600" ]; then
        echo "  ✓ Права доступа корректны (600)"
        add_check "Права доступа privkey.pem" "✓"
    else
        echo "  ⚠ Права доступа: ${PERMS} (должно быть 600)"
        add_check "Права доступа privkey.pem" "⚠"
    fi
else
    echo "✗ privkey.pem не найден"
    add_check "Приватный ключ privkey.pem" "✗"
fi

echo ""

# 5. Проверка доступности через HTTPS
echo "[5/8] Проверка доступности через HTTPS..."

CONFIGPANEL_STATUS=$(curl -k -s -o /dev/null -w "%{http_code}" --connect-timeout 5 https://${DOMAIN}/configpanel 2>/dev/null || echo "000")
if [ "$CONFIGPANEL_STATUS" = "200" ] || [ "$CONFIGPANEL_STATUS" = "301" ] || [ "$CONFIGPANEL_STATUS" = "302" ]; then
    echo "✓ Configpanel доступен через HTTPS (HTTP ${CONFIGPANEL_STATUS})"
    add_check "Configpanel через HTTPS" "✓"
else
    echo "✗ Configpanel недоступен через HTTPS (HTTP ${CONFIGPANEL_STATUS})"
    add_check "Configpanel через HTTPS" "✗"
fi

SUBS_STATUS=$(curl -k -s -o /dev/null -w "%{http_code}" --connect-timeout 5 https://${DOMAIN}/subs/ 2>/dev/null || echo "000")
if [ "$SUBS_STATUS" = "200" ] || [ "$SUBS_STATUS" = "301" ] || [ "$SUBS_STATUS" = "302" ]; then
    echo "✓ Subs доступен через HTTPS (HTTP ${SUBS_STATUS})"
    add_check "Subs через HTTPS" "✓"
else
    echo "✗ Subs недоступен через HTTPS (HTTP ${SUBS_STATUS})"
    add_check "Subs через HTTPS" "✗"
fi

echo ""

# 6. Проверка редиректа HTTP → HTTPS
echo "[6/8] Проверка редиректа HTTP → HTTPS..."

HTTP_REDIRECT=$(curl -s -o /dev/null -w "%{http_code}" --connect-timeout 5 http://${DOMAIN}/configpanel 2>/dev/null || echo "000")
if [ "$HTTP_REDIRECT" = "301" ]; then
    echo "✓ Редирект HTTP → HTTPS работает (HTTP 301)"
    add_check "Редирект HTTP → HTTPS" "✓"
else
    echo "✗ Редирект HTTP → HTTPS не работает (HTTP ${HTTP_REDIRECT})"
    add_check "Редирект HTTP → HTTPS" "✗"
fi

echo ""

# 7. Проверка логов nginx
echo "[7/8] Проверка логов nginx..."

if [ -f /var/log/nginx/error.log ]; then
    ERROR_COUNT=$(tail -n 10 /var/log/nginx/error.log | grep -i error | wc -l)
    if [ "$ERROR_COUNT" -gt 0 ]; then
        echo "⚠ Обнаружены ошибки в логах nginx (последние 10 строк)"
        echo "   Последние ошибки:"
        tail -n 10 /var/log/nginx/error.log | grep -i error | head -3
        add_check "Логи nginx" "⚠ (${ERROR_COUNT} ошибок)"
    else
        echo "✓ Ошибок в логах nginx не обнаружено"
        add_check "Логи nginx" "✓"
    fi
else
    echo "⚠ Файл логов не найден: /var/log/nginx/error.log"
    add_check "Логи nginx" "⚠"
fi

echo ""

# 8. Вывод подробного отчета
echo "[8/8] Итоговый отчет"
echo ""
echo "=========================================="
echo "Результаты проверки:"
echo "=========================================="
echo ""

# Подсчет результатов
SUCCESS=0
WARNING=0
FAILED=0

for i in "${!CHECKS[@]}"; do
    RESULT="${RESULTS[$i]}"
    if [[ "$RESULT" == "✓"* ]]; then
        SUCCESS=$((SUCCESS + 1))
    elif [[ "$RESULT" == "⚠"* ]]; then
        WARNING=$((WARNING + 1))
    else
        FAILED=$((FAILED + 1))
    fi
done

# Вывод таблицы результатов
printf "%-50s %s\n" "Проверка" "Результат"
printf "%-50s %s\n" "--------------------------------------------------" "--------"
for i in "${!CHECKS[@]}"; do
    printf "%-50s %s\n" "${CHECKS[$i]}" "${RESULTS[$i]}"
done

echo ""
echo "=========================================="
echo "Статистика:"
echo "  Успешно: ${SUCCESS}"
echo "  Предупреждения: ${WARNING}"
echo "  Ошибки: ${FAILED}"
echo "=========================================="
echo ""

# Итоговый статус
if [ "$FAILED" -eq 0 ] && [ "$WARNING" -eq 0 ]; then
    echo "✓ Все проверки пройдены успешно!"
    exit 0
elif [ "$FAILED" -eq 0 ]; then
    echo "⚠ Есть предупреждения, но критических ошибок нет"
    exit 0
else
    echo "✗ Обнаружены ошибки. Проверьте результаты выше."
    echo ""
    echo "Рекомендации:"
    echo "  1. Проверьте статус сервисов: systemctl status nginx"
    echo "  2. Проверьте логи nginx: tail -f /var/log/nginx/error.log"
    echo "  3. Проверьте доступность портов 3x-ui локально"
    echo "  4. Убедитесь, что DNS настроен правильно"
    exit 1
fi

